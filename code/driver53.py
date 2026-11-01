"""R53 extensions of the R52 response-history driver (R52 code untouched).

Adds to ``Frame``:
  * ``run53``  – same integration as ``Frame.run`` (identical solver settings and
                 settling rule) plus
                   - ``vel_scale``: at the release instant all nodal velocities and
                     accelerations are multiplied by ``vel_scale`` (0 = release from
                     rest, 1 = plain zero-input continuation, >1 = kicked state);
                   - ``hist_from``: history recording restricted to t >= hist_from;
                   - ``stop_at_release``: return as soon as t_r is reached with the
                     domain intact, so a static analysis can continue from it.
  * ``barrier`` – displacement-controlled static push from the current (released)
                 configuration in a chosen direction with a chosen force pattern,
                 continued until the resistance has been positive and returns to
                 zero (the static edge of the damaged frame), or until it is clear
                 that the state is already downhill.  Returns the external-work
                 path so that the static energy barrier can be evaluated.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code_copy"))

from driver import Frame, GM_PAT, PO_PAT, PO_TS, THRESHOLDS, _STRATEGIES  # noqa: E402


class Frame53(Frame):
    # ------------------------------------------------------------------ release manipulation
    def scale_motion(self, beta: float, undamped: bool = False, damping_scale=None) -> None:
        """Multiply all nodal velocities/accelerations by ``beta`` and restart the integrator."""
        for nd in ops.getNodeTags():
            for dof in (1, 2, 3):
                ops.setNodeVel(nd, dof, float(beta) * ops.nodeVel(nd, dof), "-commit")
                ops.setNodeAccel(nd, dof, float(beta) * ops.nodeAccel(nd, dof), "-commit")
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")
        if undamped:
            self.remove_damping()
        elif damping_scale is not None:
            self.scale_damping(damping_scale)

    def remove_damping(self) -> None:
        """Zero all Rayleigh damping: the global ``rayleigh`` command and every
        ``region`` command of the model's command log that carries ``-rayleigh``
        (same tags and element/node lists, the four factors set to 0)."""
        from opsmodel import load_log

        ops.rayleigh(0.0, 0.0, 0.0, 0.0)
        _, cmds = load_log(self.name)
        for cmd, args in cmds:
            if cmd == "region" and "-rayleigh" in args:
                a = list(args)
                a[a.index("-rayleigh") + 1: a.index("-rayleigh") + 5] = [0.0] * 4
                ops.region(*a)

    def scale_damping(self, s: float) -> None:
        """Multiply every Rayleigh damping coefficient by ``s``: the global
        ``rayleigh`` command of the command log and every ``region`` command
        carrying ``-rayleigh`` (same tags/lists, the four factors scaled)."""
        from opsmodel import load_log

        _, cmds = load_log(self.name)
        for cmd, args in cmds:
            if cmd == "rayleigh" and len(args) >= 4:
                ops.rayleigh(*[s * float(v) for v in args[:4]])
            elif cmd == "region" and "-rayleigh" in args:
                a = list(args)
                i = a.index("-rayleigh")
                a[i + 1: i + 5] = [s * float(v) for v in a[i + 1: i + 5]]
                ops.region(*a)

    # ------------------------------------------------------------------ response history
    GM_TS2, GM_PAT2 = 7003, 7003

    def apply_second_motion(self, acc2, dt2, scale2) -> None:
        """On a state reproduced by ``stop_at_release``: zero all nodal
        velocities/accelerations (the settled damaged configuration), remove
        the first ground-motion pattern, and install a new UniformExcitation
        driven by ``acc2`` at factor ``scale2``.  Reuses the same
        solver/integrator stack as ``scale_motion``."""
        for nd in ops.getNodeTags():
            for dof in (1, 2, 3):
                ops.setNodeVel(nd, dof, 0.0, "-commit")
                ops.setNodeAccel(nd, dof, 0.0, "-commit")
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        from driver import G_IN_S2
        ops.timeSeries("Path", self.GM_TS2, "-dt", float(dt2),
                       "-values", *np.asarray(acc2, float).tolist(),
                       "-factor", float(scale2) * G_IN_S2)
        ops.pattern("UniformExcitation", self.GM_PAT2, 1, "-accel", self.GM_TS2)
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

    def continue_transient(self, t_stop: float, dt: float, drift_limit=0.15) -> dict:
        """Advance the current analysis to ``t_stop`` after a second motion was
        installed; returns collapse diagnostics in the run53 schema."""
        t = ops.getTime()
        nst = len(self.geo.h)
        peak = np.zeros(nst)
        status = "ok"
        while t < t_stop - 1.0e-9:
            t_target = min(t + dt, t_stop)
            if self.advance(t_target, min(dt, t_target - t)) != 0:
                status = "nonconv"
                break
            t = ops.getTime()
            d, de = self.drifts()
            peak = np.maximum(peak, np.abs(np.maximum(d, de)))
            if float(peak.max()) >= drift_limit:
                status = "collapse"
                break
        return {"status": status, "t_end": float(ops.getTime()),
                "max_sdr": float(peak.max()), "peak_sdr": peak.tolist()}

    def run53(self, acc_g, dt_gm, scale, t_stop, *, t_release=None, drift_limit=0.15, dt_anal=None,
              settle_check=True, keep_history=False, hist_every=0.01, hist_from=None,
              state_at=(), build=True, vel_scale=None, stop_at_release=False,
              undamped: bool = False, damping_scale=None) -> dict:
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
        hist_t, hist_d, hist_ke = [], [], []
        snaps = {}
        pending = sorted(float(s) for s in state_at)
        need_stop_at_release = (vel_scale is not None or stop_at_release) and t_release is not None
        stops = sorted(set(pending) | ({t_input_end} if need_stop_at_release else set()))
        scaled = vel_scale is None or t_release is None
        status = "ok"
        t = 0.0
        t_next_hist = 0.0 if hist_from is None else float(hist_from)
        win_len = 2.0 * max(T1, 1.0)
        settle_start = t_input_end + 2.0 * T1
        w_lo = w_hi = w_sum = None
        w_n = 0
        w_t0 = None
        prev_mean = None
        amp_hist: list[float] = []
        settled_at = None
        released = False
        while t < t_stop - 1.0e-9:
            t_target = min(t + dt, t_stop)
            nxt = [s for s in stops if t + 1.0e-9 < s < t_target - 1.0e-9]
            if nxt:
                t_target = nxt[0]
            if self.advance(t_target, min(dt, t_target - t)) != 0:
                status = "nonconv"
                break
            t_new = ops.getTime()
            if t_new <= t + 1.0e-12:
                if self.advance(min(t + dt, t_stop), dt) != 0:
                    status = "nonconv"
                    break
                t_new = ops.getTime()
            t = t_new
            if t_release is not None and not released and t >= t_input_end - 1e-9:
                released = True
                d0, _ = self.drifts()
                snaps["release"] = self.snapshot(np.maximum(peak, np.abs(d0)))
                if stop_at_release:
                    status = "released"
                    break
                if not scaled:
                    self.scale_motion(vel_scale, undamped=undamped, damping_scale=damping_scale)
                    scaled = True
                elif undamped:
                    self.remove_damping()
                elif damping_scale is not None:
                    self.scale_damping(damping_scale)
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
                hist_d.append(d.tolist())
                hist_ke.append(self.kinetic_energy())
                t_next_hist = max(t_next_hist, t) + hist_every
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
            "status": status, "t_end": float(ops.getTime()), "t_input_end": float(t_input_end),
            "t_release": None if t_release is None else float(t_input_end), "scale": float(scale),
            "vel_scale": vel_scale, "undamped": undamped, "peak_sdr": peak.tolist(), "max_sdr": float(peak.max()),
            "t_peak": float(t_peak), "first_passage": first_pass, "final_sdr": final_d.tolist(),
            "settled_at": settled_at, "wall_s": round(time.time() - wall0, 3), "snapshots": snaps,
        }
        if keep_history:
            out["hist_t"], out["hist_d"], out["hist_ke"] = hist_t, hist_d, hist_ke
        return out

    # ------------------------------------------------------------------ static barrier
    def pattern_vector(self, kind: str, icr: int) -> np.ndarray:
        m = self.geo.floor_mass
        if kind == "mode1":
            f = m * self.geo.phi1
        elif kind == "story":
            f = np.where(np.arange(len(m)) >= icr, m, 0.0)
        elif kind == "uniform":
            f = m.copy()
        else:
            raise ValueError(kind)
        return f / f.sum()

    def barrier(self, sgn: float, pattern: str, icr: int, *, du_fine: float = 0.002, du: float = 0.02,
                n_fine: int = 10, max_droof: float = 0.08, max_steps: int = 20000) -> dict:
        """Static push from the current state; see module docstring.

        Returns the curve [(roof drift increment, lambda in the push direction (kip),
        peak story drift ratio, external work from the start (kip-in))] and summary
        quantities.  ``lambda`` is the base shear of the lateral pattern needed to hold
        the frame; negative means the frame has to be held back (net outward force).
        """
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        ops.setTime(0.0)
        floors = self.geo.floors
        f = self.pattern_vector(pattern, icr)
        ops.timeSeries("Linear", PO_TS)
        ops.pattern("Plain", PO_PAT, PO_TS)
        for nd, fi in zip(floors, f):
            ops.load(nd, float(fi), 0.0, 0.0)
        roof = floors[-1]
        H = self.geo.height
        s = 1.0 if sgn >= 0 else -1.0
        u_prev = self.floor_disp()
        x0 = u_prev[-1]
        lam_prev = 0.0
        work = 0.0
        curve = []
        been_positive = False
        downhill = None
        ok = 0
        step = 0
        self._static_setup(roof, s * du_fine)
        first_step_ladder = None
        first_step_ladder_detail = None
        while step < max_steps:
            inc = du_fine if step < n_fine else du
            if step == n_fine:
                self._static_setup(roof, s * du)
            ok = ops.analyze(1)
            if ok != 0:
                ok = self._pushover_substep(roof, s * inc)
                if ok != 0 and step == 0:
                    ok, first_step_ladder, first_step_ladder_detail = self._first_step_ladder(roof, s)
                    if ok == 0:
                        self._static_setup(roof, s * du_fine)
                if ok != 0:
                    break
            step += 1
            lam = ops.getLoadFactor(PO_PAT) * s          # resistance in the push direction
            u = self.floor_disp()
            work += 0.5 * (lam + lam_prev) * s * float(np.dot(f, u - u_prev))
            u_prev, lam_prev = u, lam
            d, _ = self.drifts()
            droof = s * (u[-1] - x0) / H
            curve.append((float(droof), float(lam), float(np.max(np.abs(d))), float(work)))
            if lam > 0.0:
                been_positive = True
            if been_positive and lam <= 0.0 and step > 1:
                downhill = False
                break
            if droof > max_droof:
                downhill = not been_positive
                break
        c = np.asarray(curve, dtype=float)
        out = {"pattern": pattern, "sgn": s, "icr": int(icr), "converged": ok == 0, "n_steps": len(curve),
               "first_step_ladder": first_step_ladder,
               "first_step_ladder_detail": first_step_ladder_detail,
               "curve": curve[::5] if len(curve) > 600 else curve}
        if len(c):
            lam = c[:, 1]
            W = c[:, 3]
            out["lam0"] = float(lam[0])
            pos = np.where(lam > 0.0)[0]
            if len(pos):
                i1 = int(pos[0])
                neg_after = np.where(lam[i1:] <= 0.0)[0]
                i2 = int(i1 + neg_after[0]) if len(neg_after) else len(c) - 1
                out["W_min_before_positive"] = float(np.min(W[:i1 + 1]))
                out["W_max"] = float(np.max(W[:i2 + 1]))
                out["W_barrier"] = float(max(0.0, np.max(W[:i2 + 1])))             # V(saddle) - V(start)
                out["W_barrier_from_min"] = float(np.max(W[:i2 + 1]) - np.min(W[:i1 + 1]))
                out["droof_positive"] = float(c[i1, 0])
                out["droof_edge"] = float(c[i2, 0])
                out["sdr_edge"] = float(c[i2, 2])
                out["lam_peak"] = float(np.max(lam[:i2 + 1]))
                out["reached_edge"] = bool(len(neg_after))
                out["downhill"] = False
            else:
                out["W_barrier"] = 0.0
                out["W_barrier_from_min"] = 0.0
                out["downhill"] = True
                out["reached_edge"] = False
        return out

    def barrier_pattern(self, f, ctrl_floor: int, sgn: float, *,
                        du_fine: float = 0.002, du: float = 0.02,
                        n_fine: int = 10, max_droof: float = 0.08,
                        max_steps: int = 20000) -> dict:
        """Static push along an explicit collapse-shape force pattern.

        Same algorithm as ``barrier`` but the lateral load vector is the given
        ``f`` (one entry per floor, already oriented along the collapse shape,
        unit L1 norm) and the displacement control acts on ``ctrl_floor``
        (index into ``geo.floors``) with increment sign ``sgn``.  ``lam_dir``
        is the raw load factor: positive = the pattern pushes along the shape,
        i.e. the frame resists.  Work accumulates as
        0.5*(lam+lam_prev)*dot(f, u-u_prev).
        """
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        ops.setTime(0.0)
        floors = self.geo.floors
        f = np.asarray(f, dtype=float)
        ops.timeSeries("Linear", PO_TS)
        ops.pattern("Plain", PO_PAT, PO_TS)
        for nd, fi in zip(floors, f):
            ops.load(nd, float(fi), 0.0, 0.0)
        ctrl = floors[ctrl_floor]
        H = self.geo.height
        s = 1.0 if sgn >= 0 else -1.0
        u_prev = self.floor_disp()
        u0 = float(u_prev[ctrl_floor])
        lam_prev = 0.0
        work = 0.0
        curve = []
        been_positive = False
        downhill = None
        ok = 0
        step = 0
        self._static_setup(ctrl, s * du_fine)
        first_step_ladder = None
        first_step_ladder_detail = None
        while step < max_steps:
            inc = du_fine if step < n_fine else du
            if step == n_fine:
                self._static_setup(ctrl, s * du)
            ok = ops.analyze(1)
            if ok != 0:
                ok = self._pushover_substep(ctrl, s * inc)
                if ok != 0 and step == 0:
                    ok, first_step_ladder, first_step_ladder_detail = self._first_step_ladder(ctrl, s)
                    if ok == 0:
                        self._static_setup(ctrl, s * du_fine)
                if ok != 0:
                    break
            step += 1
            lam_dir = ops.getLoadFactor(PO_PAT)
            u = self.floor_disp()
            work += 0.5 * (lam_dir + lam_prev) * float(np.dot(f, u - u_prev))
            u_prev, lam_prev = u, lam_dir
            d, _ = self.drifts()
            dctrl = s * (u[ctrl_floor] - u0) / H
            curve.append((float(dctrl), float(lam_dir), float(np.max(np.abs(d))), float(work)))
            if lam_dir > 0.0:
                been_positive = True
            if been_positive and lam_dir <= 0.0 and step > 1:
                downhill = False
                break
            if dctrl > max_droof:
                downhill = not been_positive
                break
        c = np.asarray(curve, dtype=float)
        out = {"pattern": "shape", "sgn": s, "ctrl_floor": int(ctrl_floor),
               "converged": ok == 0, "n_steps": len(curve),
               "first_step_ladder": first_step_ladder,
               "first_step_ladder_detail": first_step_ladder_detail,
               "curve": curve[::5] if len(curve) > 600 else curve}
        if len(c):
            lam = c[:, 1]
            W = c[:, 3]
            out["lam0"] = float(lam[0])
            pos = np.where(lam > 0.0)[0]
            if len(pos):
                i1 = int(pos[0])
                neg_after = np.where(lam[i1:] <= 0.0)[0]
                i2 = int(i1 + neg_after[0]) if len(neg_after) else len(c) - 1
                out["W_min_before_positive"] = float(np.min(W[:i1 + 1]))
                out["W_max"] = float(np.max(W[:i2 + 1]))
                out["W_barrier"] = float(max(0.0, np.max(W[:i2 + 1])))
                out["W_barrier_from_min"] = float(np.max(W[:i2 + 1]) - np.min(W[:i1 + 1]))
                out["droof_positive"] = float(c[i1, 0])
                out["droof_edge"] = float(c[i2, 0])
                out["sdr_edge"] = float(c[i2, 2])
                out["lam_peak"] = float(np.max(lam[:i2 + 1]))
                out["reached_edge"] = bool(len(neg_after))
                out["downhill"] = False
            else:
                out["W_barrier"] = 0.0
                out["W_barrier_from_min"] = 0.0
                out["downhill"] = True
                out["reached_edge"] = False
        return out

    QS_TS = 77
    QS_PAT = 78

    def barrier_quasistatic(self, f, ctrl_floor: int, sgn: float, *,
                            rate: float = 0.05, dt: float = 0.02,
                            settle_time: float = 5.0,
                            max_drift: float = 0.08, collapse_sdr: float = 0.15,
                            max_steps: int = 60000) -> dict:
        """Quasi-static barrier for states the static push cannot start.

        Same energy-barrier definition as ``barrier_pattern`` but driven by a
        slow displacement ramp at the control floor through a heavily damped
        transient analysis: removes the ground-motion pattern, zeroes all
        velocities/accelerations, adds a global mass-proportional Rayleigh
        term ``a0 = 2*0.7*(2*pi/T1)`` on top of the model's own (regional)
        damping, and imposes u_ctrl(t) = sgn*rate*t (rate in/s, dt s steps)
        via a single-point constraint.  lam_dir = signed reaction at the
        control node (positive = frame resisting the imposed motion) and
        work accumulates as the reaction work at the single imposed DOF.
        Termination: lam_dir positive then <= 0 -> edge; control drift
        increment > max_drift without positive -> downhill; peak story drift
        >= collapse_sdr -> downhill.
        """
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        self.scale_motion(0.0)
        T1 = self.geo.periods[0]
        a0 = 2.0 * 0.7 * (2.0 * math.pi / T1)
        ops.rayleigh(float(a0), 0.0, 0.0, 0.0)
        ops.setTime(0.0)
        ctrl = self.geo.floors[ctrl_floor]
        s = 1.0 if sgn >= 0 else -1.0
        # absolute ramp starting at the released control displacement:
        # u_ctrl(t) = u0 + s*rate*t via a Path series and sp value 1.0
        T_settle = settle_time
        T_ramp = T_settle + max_steps * dt
        u0 = float(ops.nodeDisp(ctrl, 1))
        # hold u_ctrl at u0 for T_settle so the released dynamic state relaxes
        # to the static manifold, then ramp u_ctrl = u0 + s*rate*(t-T_settle)
        ops.timeSeries("Path", self.QS_TS, "-time", 0.0, T_settle, T_ramp,
                       "-values", u0, u0, u0 + s * float(rate) * (T_ramp - T_settle))
        ops.pattern("Plain", self.QS_PAT, self.QS_TS)
        ops.sp(ctrl, 1, 1.0)
        f = np.asarray(f, dtype=float)
        # rebuild the analysis with Transformation constraints for the sp
        ops.wipeAnalysis()
        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")
        H = self.geo.height
        # ---- settle phase: hold u_ctrl, let the dynamic residual dissipate
        n_settle = int(round(T_settle / dt))
        ok = 0
        settle_sdr = 0.0
        settle_work = 0.0
        lam_prev = 0.0
        u_prev = self.floor_disp()
        for _ in range(n_settle):
            ok = ops.analyze(1, dt)
            if ok != 0:
                break
            ops.reactions()
            lam_dir = s * float(ops.nodeReaction(ctrl, 1))
            u = self.floor_disp()
            settle_work += 0.5 * (lam_dir + lam_prev) * s * float(u[ctrl_floor] - u_prev[ctrl_floor])
            u_prev, lam_prev = u, lam_dir
            d, _ = self.drifts()
            settle_sdr = max(settle_sdr, float(np.max(np.abs(d))))
        d0, _ = self.drifts()
        sdr0 = float(np.max(np.abs(d0)))
        sdr_limit = max(collapse_sdr, sdr0 + 0.05)
        if ok != 0 or settle_sdr >= sdr_limit:
            return {"pattern": "quasistatic", "sgn": s, "ctrl_floor": int(ctrl_floor),
                    "rate": rate, "dt": dt, "a0": float(a0),
                    "converged": ok == 0, "n_steps": 0,
                    "settle_failed": True, "settle_sdr": float(settle_sdr),
                    "downhill": True, "reached_edge": False,
                    "W_barrier": 0.0, "W_barrier_from_min": 0.0}
        # ---- ramp phase: work and lam re-baselined at the settled state
        u_prev = self.floor_disp()
        u0 = float(u_prev[ctrl_floor])
        lam_prev = 0.0
        work = 0.0
        curve = []
        pos_run = 0
        been_positive = False
        downhill = None
        step = 0
        truncated = False
        while step < max_steps:
            ok = ops.analyze(1, dt)
            if ok != 0:
                break
            step += 1
            ops.reactions()
            lam_dir = s * float(ops.nodeReaction(ctrl, 1))
            u = self.floor_disp()
            work += 0.5 * (lam_dir + lam_prev) * s * float(u[ctrl_floor] - u_prev[ctrl_floor])
            u_prev, lam_prev = u, lam_dir
            d, _ = self.drifts()
            dctrl = s * (u[ctrl_floor] - u0) / H
            sdr_max = float(np.max(np.abs(d)))
            curve.append((float(dctrl), float(lam_dir), sdr_max, float(work)))
            pos_run = pos_run + 1 if lam_dir > 0.0 else 0
            if pos_run >= 10:
                been_positive = True
            if been_positive and lam_dir <= 0.0 and step > 1:
                downhill = False
                break
            if sdr_max >= sdr_limit:
                downhill = True
                break
            if dctrl > max_drift:
                downhill = not been_positive
                break
        else:
            truncated = True
        c = np.asarray(curve, dtype=float)
        out = {"pattern": "quasistatic", "sgn": s, "ctrl_floor": int(ctrl_floor),
               "rate": rate, "dt": dt, "a0": float(a0),
               "settle_time": T_settle, "settle_sdr": float(settle_sdr),
               "settle_work": float(settle_work),
               "converged": ok == 0, "n_steps": len(curve), "truncated": truncated,
               "curve": curve[::5] if len(curve) > 600 else curve}
        if len(c):
            lam = c[:, 1]
            W = c[:, 3]
            out["lam0"] = float(lam[0])
            pos = np.where(lam > 0.0)[0]
            if len(pos):
                i1 = int(pos[0])
                neg_after = np.where(lam[i1:] <= 0.0)[0]
                i2 = int(i1 + neg_after[0]) if len(neg_after) else len(c) - 1
                out["W_min_before_positive"] = float(np.min(W[:i1 + 1]))
                out["W_max"] = float(np.max(W[:i2 + 1]))
                out["W_barrier"] = float(max(0.0, np.max(W[:i2 + 1])))
                out["W_barrier_from_min"] = float(np.max(W[:i2 + 1]) - np.min(W[:i1 + 1]))
                out["droof_positive"] = float(c[i1, 0])
                out["droof_edge"] = float(c[i2, 0])
                out["sdr_edge"] = float(c[i2, 2])
                out["lam_peak"] = float(np.max(lam[:i2 + 1]))
                out["reached_edge"] = bool(len(neg_after))
                out["downhill"] = False
            else:
                out["W_barrier"] = 0.0
                out["W_barrier_from_min"] = 0.0
                out["downhill"] = True
                out["reached_edge"] = False
        return out

    _FIRST_STEP_INCS = (0.0005, 0.0001, 0.00002)
    _FIRST_STEP_TESTS = (("NormDispIncr", 1.0e-6, 300), ("EnergyIncr", 1.0e-6, 300),
                         ("NormDispIncr", 1.0e-4, 500), ("NormUnbalance", 1.0e-1, 500),
                         ("RelativeNormUnbalance", 1.0e-3, 500))
    _FIRST_STEP_ALGS = (("KrylovNewton",), ("NewtonLineSearch", 0.8), ("Newton", "-initial"),
                        ("ModifiedNewton", "-initial"), ("BFGS",))

    def _first_step_ladder(self, roof: int, s: float):
        """Retry a failed first push increment with smaller steps, harder tests
        and alternative algorithms; increments x tests x algorithms, first
        success wins.  Returns (analyze_code, ladder_index, detail)."""
        for i, inc in enumerate(self._FIRST_STEP_INCS):
            for test in self._FIRST_STEP_TESTS:
                for alg in self._FIRST_STEP_ALGS:
                    self._static_setup(roof, s * inc, test, alg)
                    if ops.analyze(1) == 0:
                        return 0, i, {"inc": inc, "test": list(test), "alg": list(alg)}
        return -1, None, None
