"""Response-history driver for the zero-input continuation (ZIC) experiments.

A run integrates the frame under a scaled record; optionally the ground
acceleration is set to zero for all t > t_r ("release").  Because the release
only truncates the input, the state at t_r (displacements, velocities and all
hysteretic variables) is exactly the state of the full-record run at t_r, and
the continuation is the free (zero-input) response of that state.

Solution settings follow the published model package (Elkady & Lignos):
Plain constraints, RCM numbering, EnergyIncr 1e-3 test, KrylovNewton,
Newmark average acceleration.  The sparse SuperLU solver (SparseGeneral) is
used instead of UmfPack because it is faster for these models and gives
identical responses; the campaign uses an analysis step of
min(record step, 0.005 s).  A failed step is retried with smaller sub-steps and alternative
algorithms; a run that still fails is labelled ``nonconv``.  Collapse is the
first passage of the peak story drift ratio (moment frame or gravity frame)
through the published limit of 0.15.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

from opsmodel import G_IN_S2, replay

GM_TS, GM_PAT, PO_TS, PO_PAT = 7001, 7001, 7002, 7002
THRESHOLDS = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15)

_STRATEGIES = [
    # (test, algorithm, sub-step divisor)
    (("EnergyIncr", 1.0e-3, 100), ("KrylovNewton",), 1),
    (("EnergyIncr", 1.0e-3, 200), ("KrylovNewton",), 4),
    (("EnergyIncr", 1.0e-2, 200), ("KrylovNewton", "-initial"), 4),
    (("NormDispIncr", 1.0e-6, 200), ("NewtonLineSearch", 0.8), 8),
    (("EnergyIncr", 1.0e-2, 200), ("Newton",), 10),
    (("EnergyIncr", 1.0e-2, 500), ("ModifiedNewton", "-initial"), 20),
]


@dataclass
class FrameGeometry:
    floors: list
    egf: list
    h: np.ndarray
    floor_mass: np.ndarray
    mass_nodes: list
    mass_vals: np.ndarray
    periods: list
    height: float
    phi1: np.ndarray


class Frame:
    def __init__(self, name: str):
        self.name = name
        self.info = None
        self.geo: FrameGeometry | None = None

    # ------------------------------------------------------------------ model
    def build(self) -> None:
        self.info = replay(self.name)
        floors = list(self.info.mf_floor_nodes)
        egf = list(self.info.egf_floor_nodes)
        h = np.array(self.info.story_heights, dtype=float)
        elev = np.cumsum(h)
        mass_nodes, mass_vals, floor_mass = [], [], np.zeros(len(floors))
        for nd in ops.getNodeTags():
            m = ops.nodeMass(nd, 1)
            if m > 1.0e-6:
                y = ops.nodeCoord(nd, 2)
                k = int(np.argmin(np.abs(elev - y)))
                if abs(elev[k] - y) > 30.0:
                    raise RuntimeError(f"mass node {nd} at y={y} not near a floor")
                mass_nodes.append(nd)
                mass_vals.append(m)
                floor_mass[k] += m
        # First-mode shape of the gravity-loaded model (used for pushover patterns).
        # Deterministic-phi addendum (R53v1.0+A17): when a stored first-mode
        # vector exists in code_copy/phi1/<model>.json it is used verbatim and
        # phi1_source is recorded; otherwise the Arpack solve is used, whose
        # random start vector varies at ~1e-16 between fresh processes and was
        # traced as the source of the A13 composite-frame push bifurcations.
        phi_file = Path(__file__).resolve().parent / "phi1" / f"{self.name}.json"
        phi = None
        phi_src = "arpack_random_start"
        if phi_file.exists():
            try:
                phi = np.array(json.loads(phi_file.read_text())["phi1"], dtype=float)
                phi_src = "stored_arpack_frozen"
            except Exception:
                phi = None
        if phi is None:
            ops.wipeAnalysis()
            ops.eigen(1)
            phi = np.array([ops.nodeEigenvector(n, 1, 1) for n in floors])
        if phi[-1] < 0:
            phi = -phi
        phi = phi / phi[-1]
        ops.wipeAnalysis()
        self.geo = FrameGeometry(floors, egf, h, floor_mass, mass_nodes, np.array(mass_vals),
                                 list(self.info.periods), float(elev[-1]), phi)
        self.geo.phi1_source = phi_src

    # --------------------------------------------------------------- response
    def floor_disp(self) -> np.ndarray:
        return np.array([ops.nodeDisp(n, 1) for n in self.geo.floors])

    def drifts(self) -> tuple[np.ndarray, np.ndarray]:
        h = self.geo.h
        u = self.floor_disp()
        d = np.diff(np.concatenate([[0.0], u])) / h
        ue = np.array([ops.nodeDisp(n, 1) for n in self.geo.egf])
        de = np.diff(np.concatenate([[0.0], ue])) / h
        return d, de

    def kinetic_energy(self) -> float:
        v = np.array([ops.nodeVel(n, 1) for n in self.geo.mass_nodes])
        return float(0.5 * np.sum(self.geo.mass_vals * v * v))

    def floor_vel(self) -> np.ndarray:
        return np.array([ops.nodeVel(n, 1) for n in self.geo.floors])

    # --------------------------------------------------------------- analysis
    @staticmethod
    def _default_solver() -> None:
        test, alg, _ = _STRATEGIES[0]
        ops.test(*test)
        ops.algorithm(*alg)

    def setup_transient(self, acc_g: np.ndarray, dt_gm: float, scale: float, n_input: int | None) -> None:
        vals = np.asarray(acc_g if n_input is None else acc_g[:n_input], dtype=float)
        ops.timeSeries("Path", GM_TS, "-dt", float(dt_gm), "-values", *vals.tolist(),
                       "-factor", float(scale) * G_IN_S2)
        ops.pattern("UniformExcitation", GM_PAT, 1, "-accel", GM_TS)
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

    def advance(self, t_target: float, dt: float) -> int:
        """Advance the transient analysis to ``t_target``; 0 on success."""
        for k, (test, alg, div) in enumerate(_STRATEGIES):
            if k:
                ops.test(*test)
                ops.algorithm(*alg)
            h = dt / div
            failed = False
            while ops.getTime() < t_target - 1.0e-9:
                step = min(h, t_target - ops.getTime())
                if ops.analyze(1, step) != 0:
                    failed = True
                    break
            if not failed:
                if k:
                    self._default_solver()
                return 0
        self._default_solver()
        return -1

    def run(
        self,
        acc_g: np.ndarray,
        dt_gm: float,
        scale: float,
        t_stop: float,
        *,
        t_release: float | None = None,
        drift_limit: float = 0.15,
        dt_anal: float | None = None,
        settle_check: bool = True,
        keep_history: bool = False,
        hist_every: float = 0.02,
        state_at: tuple[float, ...] = (),
        build: bool = True,
        rest_at_release: bool = False,
    ) -> dict:
        """Integrate to ``t_stop`` (or collapse / settlement).

        ``t_release``: input is zero for t > t_release (ZIC).  Without it the
        record is applied in full and followed by free vibration up to t_stop.
        ``rest_at_release``: at t_release all nodal velocities and
        accelerations are set to zero (the released configuration and all
        hysteretic variables are kept), i.e. the frame is released from rest.
        ``state_at``: times at which released-state descriptors are stored.
        Settlement (early stop, free phase only, from t_input_end + 2 T1 on):
        consecutive windows of length 2 max(T1, 1 s) are compared; the run is
        declared settled when, for every story, the window-mean drift changes
        by < 5e-4, the drift range has decreased over two successive windows
        and is < 0.008, i.e. a decaying oscillation about a fixed residual
        drift (a dissipative free response that cannot reach collapse).
        """
        wall0 = time.time()
        if build:
            self.build()
        n_input = None
        t_input_end = (len(acc_g) - 1) * dt_gm
        if t_release is not None:
            n_input = int(round(t_release / dt_gm)) + 1
            t_input_end = (n_input - 1) * dt_gm
        self.setup_transient(acc_g, dt_gm, scale, n_input)
        dt = dt_anal or min(0.5 * dt_gm, 0.005)
        T1 = self.geo.periods[0]
        nst = len(self.geo.h)
        peak = np.zeros(nst)
        first_pass = {f"{th:.2f}": None for th in THRESHOLDS}
        t_peak = 0.0
        hist_t, hist_u, hist_d, hist_ke = [], [], [], []
        snaps = {}
        pending = sorted(float(s) for s in state_at)
        stops = sorted(set(pending) | ({t_input_end} if (rest_at_release and t_release is not None) else set()))
        rested = not (rest_at_release and t_release is not None)
        status = "ok"
        t = 0.0
        t_next_hist = 0.0
        win_len = 2.0 * max(T1, 1.0)
        settle_start = t_input_end + 2.0 * T1
        w_lo = w_hi = w_sum = None
        w_n = 0
        w_t0 = None
        prev_mean = None
        amp_hist: list[float] = []
        settled_at = None
        while t < t_stop - 1.0e-9:
            t_target = min(t + dt, t_stop)
            # stop times closer than the advance() tolerance (1e-9 s) count as reached;
            # a tighter tolerance here let round-off in the analysis time stall the loop
            nxt = [s for s in stops if t + 1.0e-9 < s < t_target - 1.0e-9]
            if nxt:
                t_target = nxt[0]
            if self.advance(t_target, min(dt, t_target - t)) != 0:
                status = "nonconv"
                break
            t_new = ops.getTime()
            if t_new <= t + 1.0e-12:  # no progress (cannot happen with the tolerance above): force a step
                if self.advance(min(t + dt, t_stop), dt) != 0:
                    status = "nonconv"
                    break
                t_new = ops.getTime()
            t = t_new
            if not rested and t >= t_input_end - 1e-9:
                self.zero_motion()
                rested = True
            d, de = self.drifts()
            dd = np.maximum(np.abs(d), np.abs(de))
            if dd.max() > peak.max():
                t_peak = t
            peak = np.maximum(peak, dd)
            dmax = float(dd.max())
            for th in THRESHOLDS:
                key = f"{th:.2f}"
                if first_pass[key] is None and dmax >= th:
                    first_pass[key] = t
            while pending and t >= pending[0] - 1e-9:
                snaps[f"{pending[0]:.4f}"] = self.snapshot(peak)
                pending.pop(0)
            if keep_history and t >= t_next_hist - 1e-12:
                hist_t.append(round(t, 5))
                hist_u.append(self.floor_disp().tolist())
                hist_d.append(d.tolist())
                hist_ke.append(self.kinetic_energy())
                t_next_hist = t + hist_every
            if dmax >= drift_limit:
                status = "collapse"
                break
            if settle_check and t > settle_start:
                if w_t0 is None:
                    w_t0, w_lo, w_hi, w_sum, w_n = t, d.copy(), d.copy(), d.copy(), 1
                else:
                    w_lo, w_hi = np.minimum(w_lo, d), np.maximum(w_hi, d)
                    w_sum += d
                    w_n += 1
                if t - w_t0 >= win_len:
                    mean = w_sum / w_n
                    amp = float(np.max(w_hi - w_lo))
                    amp_hist.append(amp)
                    if (prev_mean is not None and len(amp_hist) >= 3 and amp < 8.0e-3
                            and amp_hist[-1] < amp_hist[-2] < amp_hist[-3]
                            and float(np.max(np.abs(mean - prev_mean))) < 5.0e-4):
                        settled_at = t
                        break
                    prev_mean = mean
                    w_t0 = None
        final_d, _ = self.drifts()
        out = {
            "status": status,
            "t_end": float(ops.getTime()),
            "t_input_end": float(t_input_end),
            "t_release": None if t_release is None else float(t_input_end),
            "scale": float(scale),
            "peak_sdr": peak.tolist(),
            "max_sdr": float(peak.max()),
            "t_peak": float(t_peak),
            "first_passage": first_pass,
            "final_sdr": final_d.tolist(),
            "settled_at": settled_at,
            "wall_s": round(time.time() - wall0, 3),
            "snapshots": snaps,
        }
        if keep_history:
            out["hist_t"] = hist_t
            out["hist_u"] = hist_u
            out["hist_d"] = hist_d
            out["hist_ke"] = hist_ke
        return out

    def zero_motion(self) -> None:
        """Set all nodal velocities and accelerations to zero and restart the integrator.

        The Newmark integrator keeps its own copies of the velocity and
        acceleration vectors, so changing the nodal values alone has no
        effect; the transient analysis objects are therefore re-created, and
        the new integrator initialises its state from the (zeroed) nodes.
        """
        for nd in ops.getNodeTags():
            for dof in (1, 2, 3):
                ops.setNodeVel(nd, dof, 0.0, "-commit")
                ops.setNodeAccel(nd, dof, 0.0, "-commit")
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

    def snapshot(self, peak: np.ndarray) -> dict:
        d, _ = self.drifts()
        v = self.floor_vel()
        return {
            "t": float(ops.getTime()),
            "sdr": d.tolist(),
            "peak_sdr_so_far": peak.tolist(),
            "roof_disp": float(self.floor_disp()[-1]),
            "floor_vel": v.tolist(),
            "ke": self.kinetic_energy(),
        }

    # --------------------------------------------------------------- pushover
    def pushover(self, direction: float = 1.0, max_roof_drift: float = 0.12, droof: float = 0.02,
                 from_current: bool = False, stop_at_zero: bool = True) -> dict:
        """Displacement-controlled first-mode pushover with gravity held constant.

        ``from_current``: continue from the present (e.g. released) state,
        giving the residual-capacity curve of the damaged frame; the ground
        motion pattern is removed and velocities play no role in the static
        solution.  The lateral pattern is m_i*phi1_i normalised to unit sum,
        so the load factor equals the base shear (kip).  ``work`` is the
        external work of the lateral pattern (kip-in) accumulated from the
        starting position.
        """
        if not from_current:
            self.build()
        else:
            try:
                ops.remove("loadPattern", GM_PAT)
            except Exception:
                pass
        # DisplacementControl starts the load factor at the domain time; reset it
        # so that the lateral pattern starts from zero (gravity stays constant).
        ops.setTime(0.0)
        floors = self.geo.floors
        f = self.geo.floor_mass * self.geo.phi1
        f = f / f.sum()
        ops.timeSeries("Linear", PO_TS)
        ops.pattern("Plain", PO_PAT, PO_TS)
        for nd, fi in zip(floors, f):
            ops.load(nd, float(fi), 0.0, 0.0)
        roof = floors[-1]
        H = self.geo.height
        sgn = 1.0 if direction >= 0 else -1.0
        self._static_setup(roof, sgn * droof)
        x0 = ops.nodeDisp(roof, 1)
        u_prev = self.floor_disp()
        lam_prev = None
        work = 0.0
        curve = []
        n_max = int(math.ceil(max_roof_drift * H / droof)) + 5
        ok = 0
        for _ in range(n_max):
            ok = ops.analyze(1)
            if ok != 0:
                # adaptive recovery: smaller increments and alternative algorithms
                ok = self._pushover_substep(roof, sgn * droof)
                if ok != 0:
                    break
            lam = ops.getLoadFactor(PO_PAT)
            u = self.floor_disp()
            lam_avg = lam if lam_prev is None else 0.5 * (lam + lam_prev)
            work += lam_avg * float(np.dot(f, u - u_prev))
            u_prev, lam_prev = u, lam
            d, _ = self.drifts()
            curve.append((float(u[-1] / H), float(lam), float(np.max(np.abs(d))), float(work)))
            if abs(u[-1] - x0) / H > max_roof_drift:
                break
            if stop_at_zero and len(curve) > 3 and lam * sgn <= 0.0 and abs(u[-1] - x0) / H > 0.002:
                break
        return {"curve": curve, "pattern": f.tolist(), "direction": sgn, "converged_to_end": ok == 0}

    @staticmethod
    def _static_setup(roof: int, du: float, test=("NormDispIncr", 1.0e-6, 200), alg=("KrylovNewton",)) -> None:
        # Re-create the analysis objects; swapping the integrator under an
        # existing analysis object corrupts the heap in OpenSeesPy 3.8.
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        ops.test(*test)
        ops.algorithm(*alg)
        ops.integrator("DisplacementControl", roof, 1, du)
        ops.analysis("Static")

    def _pushover_substep(self, roof: int, du: float) -> int:
        """Cover one displacement increment ``du`` with sub-increments.

        The domain is left at the last converged state after a failure, so the
        sub-steps continue from wherever the previous attempt stopped; the
        target is the roof displacement at the start plus ``du``.
        """
        target = ops.nodeDisp(roof, 1) + du
        algs = (("KrylovNewton",), ("NewtonLineSearch", 0.8), ("Newton", "-initial"), ("ModifiedNewton",))
        tests = (("NormDispIncr", 1.0e-6, 200), ("EnergyIncr", 1.0e-8, 300), ("NormDispIncr", 1.0e-5, 500))
        for div in (2, 4, 8, 16, 32, 64):
            for test in tests:
                for alg in algs:
                    self._static_setup(roof, du / div, test, alg)
                    ok = 0
                    while (target - ops.nodeDisp(roof, 1)) * np.sign(du) > 1e-9 * abs(du):
                        ok = ops.analyze(1)
                        if ok != 0:
                            break
                    if ok == 0:
                        self._static_setup(roof, du)
                        return 0
        self._static_setup(roof, du)
        return -1
