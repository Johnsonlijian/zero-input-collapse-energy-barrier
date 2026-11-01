"""Protocol addenda A6 (aftershock residual capacity) and A7 (kick energy closure).

NEW MODULE — driver53.py / campaign53.py are FROZEN (running workers stamp their
sha256).  Frame53A subclasses driver53.Frame53; the buggy earlier attempt
(apply_second_motion / continue_transient in driver53.py, task_aftershock in
campaign53.py) is NOT used.

A6 `aftershock_a6`: settle a recoverable released state (mainshock truncated at
t_r, free vibration for T_set = max(30, 15*T1) s), then apply the SAME record
from its beginning scaled by sa2/sa_unscaled; bracket the collapse intensity
sa2 (x1.25 ladder, geometric bisection to 3%) and report R = sa2_hi / S_hi.

A7 `kick_energy`: repeat the critical damped kicks with in-run viscous-work
accounting: per step, ops.reactions() -> R_s (no damping) and
ops.reactions("-rayleigh") -> R_sd (with Rayleigh), F_d = R_sd - R_s;
trapezoidal W_s, W_d on the full nodal displacement vector; energy series every
0.01 s: KE, KE_full, W_s, W_d, residual = KE_full0 - KE_full - W_s - W_d.

CLI: python addenda53.py {aftershock_a6|kick_energy} --models ... --tags ...
     --workers N --rid-stride K [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent          # E:\n0r53\code
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code_copy"))

RUNS = Path(os.environ.get("N0R53_RUNS", r"E:\n0r53\runs"))
CODE_DIR = HERE

import campaign53 as c53                        # noqa: E402  (select_states, _common, crit_story, _label, dt_anal, H_ZIC, out_path helpers)


def code_sha256() -> dict:
    out = {}
    for f in ("driver53.py", "campaign53.py", "addenda53.py"):
        p = CODE_DIR / f
        out[f] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    p = CODE_DIR.parent / "code_copy" / "driver.py"
    out["code_copy/driver.py"] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return out


DOFS = (1, 2, 3)
GM2_TS = 7003
GM2_PAT = 7003


# =================================================================== Frame53A
from driver53 import Frame53                    # noqa: E402
from driver import GM_PAT, G_IN_S2              # noqa: E402
import openseespy.opensees as ops               # noqa: E402


class Frame53A(Frame53):
    """Frame53 + second-motion analysis and optional in-run energy tracking."""

    def __init__(self, name: str, track_energy: bool = False):
        super().__init__(name)
        self.track_energy = track_energy
        self._trk = None                        # dict, set at release instant

    # ---------------------------------------------------------------- A6
    def second_motion(self, acc2, dt2, scale2) -> None:
        """Zero all nodal velocities/accelerations, remove the first GM
        pattern, reset the clock, install the second UniformExcitation
        (Path series 7003, factor scale2*G_IN_S2), rebuild the transient stack."""
        for nd in ops.getNodeTags():
            for dof in DOFS:
                ops.setNodeVel(nd, dof, 0.0, "-commit")
                ops.setNodeAccel(nd, dof, 0.0, "-commit")
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        ops.setTime(0.0)
        vals = np.asarray(acc2, float).tolist()
        ops.timeSeries("Path", GM2_TS, "-dt", float(dt2), "-values", *vals,
                       "-factor", float(scale2) * G_IN_S2)
        ops.pattern("UniformExcitation", GM2_PAT, 1, "-accel", GM2_TS)
        ops.wipeAnalysis()
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("SparseGeneral")
        self._default_solver()
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

    def continue_transient(self, t_stop: float, dt: float, drift_limit: float = 0.15) -> dict:
        """Advance the current analysis to ``t_stop`` (mirrors run53's loop)."""
        wall0 = time.time()
        nst = len(self.geo.h)
        peak = np.zeros(nst)
        status = "ok"
        t_coll = None
        t = ops.getTime()
        while t < t_stop - 1.0e-9:
            t_target = min(t + dt, t_stop)
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
            d, de = self.drifts()
            dd = np.maximum(np.abs(d), np.abs(de))
            peak = np.maximum(peak, dd)
            if t_coll is None and float(dd.max()) >= drift_limit:
                t_coll = t
            if float(peak.max()) >= drift_limit:
                status = "collapse"
                break
        return {"status": status, "t_end": float(ops.getTime()),
                "max_sdr": float(peak.max()), "peak_sdr": peak.tolist(),
                "final_sdr": list(self.drifts()[0]),
                "t_coll": t_coll, "wall_s": round(time.time() - wall0, 3)}

    # ---------------------------------------------------------------- A7 energy tracking
    def _all_disp(self) -> np.ndarray:
        return np.array([ops.nodeDisp(n, d) for n in ops.getNodeTags() for d in DOFS])

    def _reaction_vec(self):
        """(R0, R1) reaction vectors at all nodes/dofs.

        Toy-model verified semantics (E:\\n0r53\\pilot\\a7_toy_reactions.py):
        R0 = nodeReaction()           -> F_int + F_d,nodal - P (contains the nodal
             alphaM damping force, NOT the element betaK part).
        R1 = nodeReaction('-rayleigh')-> total viscous force (aM nodal + bK ele)
             for elements that implement addRayleighDampingForces; exactly
             0.0000 with damping removed.  ModElasticBeam2d is not exposed.
        """
        ops.reactions()
        r0 = np.array([ops.nodeReaction(n, d) for n in ops.getNodeTags() for d in DOFS])
        ops.reactions("-rayleigh")
        r1 = np.array([ops.nodeReaction(n, d) for n in ops.getNodeTags() for d in DOFS])
        return r0, r1

    def _ke_full(self) -> float:
        v = np.array([ops.nodeVel(n, d) for n in ops.getNodeTags() for d in DOFS])
        m = np.array([ops.nodeMass(n, d) for n in ops.getNodeTags() for d in DOFS])
        return float(0.5 * np.sum(m * v * v))

    def scale_motion(self, beta: float, undamped: bool = False, damping_scale=None) -> None:
        super().scale_motion(beta, undamped=undamped, damping_scale=damping_scale)
        if self.track_energy:
            r0, r1 = self._reaction_vec()
            m = np.array([ops.nodeMass(n, d) for n in ops.getNodeTags() for d in DOFS])
            v = np.array([ops.nodeVel(n, d) for n in ops.getNodeTags() for d in DOFS])
            aM = _alphaM_vec(self.name) * (
                0.0 if undamped else (float(damping_scale) if damping_scale is not None else 1.0))
            self._trk = {
                "u_prev": self._all_disp(),
                "r0_prev": r0, "r1_prev": r1, "fdn_prev": aM * m * v,
                "aM": aM, "m": m,
                "W_R0": 0.0, "W_node": 0.0, "W_R1": 0.0,
                "KE0": self.kinetic_energy(), "KE_full0": self._ke_full(),
                "series": [], "t_next": None,
            }

    def advance(self, t_target: float, dt: float) -> int:
        rc = super().advance(t_target, dt)
        if rc == 0 and self._trk is not None:
            tr = self._trk
            r0, r1 = self._reaction_vec()
            u = self._all_disp()
            v = np.array([ops.nodeVel(n, d) for n in ops.getNodeTags() for d in DOFS])
            fdn = tr["aM"] * tr["m"] * v
            du = u - tr["u_prev"]
            tr["W_R0"] += 0.5 * float(np.dot(tr["r0_prev"] + r0, du))
            tr["W_R1"] += 0.5 * float(np.dot(tr["r1_prev"] + r1, du))
            tr["W_node"] += 0.5 * float(np.dot(tr["fdn_prev"] + fdn, du))
            tr["u_prev"], tr["r0_prev"], tr["r1_prev"], tr["fdn_prev"] = u, r0, r1, fdn
            t = ops.getTime()
            if tr["t_next"] is None or t >= tr["t_next"] - 1e-12:
                ke = self.kinetic_energy()
                ke_full = self._ke_full()
                d, de = self.drifts()
                w_int = tr["W_R0"] - tr["W_node"]
                tr["series"].append({
                    "t": round(t, 5), "KE": ke, "KE_full": ke_full,
                    "W_R0": tr["W_R0"], "W_node": tr["W_node"],
                    "W_R1": tr["W_R1"], "W_int": w_int,
                    "W_visc_diff": tr["KE_full0"] - ke_full - w_int,
                    "res_R1": tr["KE_full0"] - ke_full - w_int - tr["W_R1"],
                    "sdr": np.maximum(np.abs(d), np.abs(de)).tolist(),
                })
                tr["t_next"] = (tr["t_next"] if tr["t_next"] is not None else t) + 0.01
        return rc

    def energy_series(self) -> list | None:
        return None if self._trk is None else self._trk["series"]

    def energy_summary(self) -> dict | None:
        if self._trk is None:
            return None
        tr = self._trk
        ser = tr["series"]
        i_min = int(np.argmin([s["KE_full"] for s in ser])) if ser else None
        km = ser[i_min] if i_min is not None else {}
        mx = max((abs(s["res_R1"]) for s in ser), default=0.0)
        return {"KE0": tr["KE0"], "KE_full0": tr["KE_full0"],
                "W_R0_end": tr["W_R0"], "W_node_end": tr["W_node"],
                "W_R1_end": tr["W_R1"],
                "W_int_end": tr["W_R0"] - tr["W_node"],
                "W_visc_diff_end": tr["KE_full0"] - ser[-1]["KE_full"] - (tr["W_R0"] - tr["W_node"]) if ser else None,
                "ke_min": {"i": i_min, "t": km.get("t"), "KE_full": km.get("KE_full"),
                           "W_int": km.get("W_int"), "W_node": km.get("W_node"),
                           "W_R1": km.get("W_R1"), "W_visc_diff": km.get("W_visc_diff"),
                           "res_R1": km.get("res_R1")},
                "max_abs_res_R1_over_KE0": mx / max(tr["KE_full0"], 1e-12),
                "max_abs_W_R1": max((abs(s["W_R1"]) for s in ser), default=0.0)}


# =================================================================== A6 task
def _alphaM_vec(model: str) -> np.ndarray:
    """alphaM per node/dof from the command-log region commands."""
    from opsmodel import load_log
    aM_node = {}
    _, cmds = load_log(model)
    for cmd, args in cmds:
        if cmd == "region" and "-rayleigh" in args:
            i = args.index("-rayleigh")
            alpha = float(args[i + 1])
            for tok in args[1:i]:
                if isinstance(tok, str) and tok.startswith("-"):
                    continue
                try:
                    aM_node[int(tok)] = alpha
                except (ValueError, TypeError):
                    pass
    return np.array([aM_node.get(n, 0.0) for n in ops.getNodeTags() for _ in DOFS])


def _settle(fr, rec, scale, t_r, T_set, T1, keep_hist=True):
    return fr.run53(rec.acc, rec.dt, scale, t_r + T_set, t_release=t_r,
                    dt_anal=c53.dt_anal(rec), settle_check=False,
                    keep_history=keep_hist, hist_every=0.05,
                    hist_from=t_r + T_set - 2.0 * T1)


def task_aftershock_a6(model: str, state: dict) -> dict:
    rec, scale = c53._common(model, state["rid"], state["sa"])
    ida = json.loads((RUNS / "ida" / model / f"{state['rid']}.json").read_text())
    t_r = state["t_r"]
    out = {"type": "aftershock_a6", "S_hi": ida["S_hi"], "S_lo": ida["S_lo"],
           "sa_unscaled": ida["sa_unscaled"]}
    if ida["S_hi"] is None:
        out["status"] = "no_intact_capacity"
        return out
    fr = Frame53A(model)
    fr.build()
    T1 = fr.geo.periods[0]
    T_set = max(30.0, 15.0 * T1)
    res = _settle(fr, rec, scale, t_r, T_set, T1)
    out["settle_status"] = res["status"]
    if res["status"] != "ok":
        out["status"] = "not_recoverable"
        out["settle"] = {"status": res["status"], "max_sdr": res["max_sdr"],
                         "t_end": res["t_end"]}
        return out
    # --- settle diagnostics
    final_sdr = np.asarray(res["final_sdr"], float)
    ht, hd = np.asarray(res["hist_t"]), np.asarray(res["hist_d"])
    win = hd[ht >= t_r + T_set - 2.0 * T1 - 1e-9]
    out["settle"] = {
        "T_set": T_set, "T1": T1, "t_end": res["t_end"],
        "max_sdr": res["max_sdr"],                       # peak over mainshock+settle
        "final_sdr": res["final_sdr"],                   # residual profile
        "residual_roof_disp": float(fr.floor_disp()[-1]),
        "ke_end": float(fr.kinetic_energy()),
        "drift_range_last_2T1": float(np.max(win.max(axis=0) - win.min(axis=0))) if len(win) else None,
    }
    snap_rel = res["snapshots"].get("release")
    if snap_rel and state.get("snapshot"):
        s0 = np.asarray(state["snapshot"]["sdr"])
        out["settle"]["snapshot_max_abs_diff_sdr"] = float(
            np.max(np.abs(np.asarray(snap_rel["sdr"]) - s0)))

    out["T_set"] = T_set
    _downstream(model, ida, rec,
                lambda f: _settle(f, rec, scale, t_r, T_set, T1, keep_hist=False),
                final_sdr, out)
    return out


def _downstream(model: str, ida: dict, rec, reproduce, final_sdr, out: dict,
                rec2=None, ida2=None) -> None:
    """Shared aftershock downstream: settled-state barriers + second-motion bracket.
    reproduce(fb) must run the damage-producing first phase on the fresh frame fb
    and return the run53 result dict (status ok, final_sdr). rec2/ida2 allow the
    second motion to be a different record (sibling component) than the
    damage-producing one; the bracket and R are then normalised by the second
    record's own intact collapse intensity."""
    if rec2 is None:
        rec2, ida2 = rec, ida
    # --- settled-state barriers, both directions (fresh reproductions)
    icr, sgn = c53.crit_story({"sdr": final_sdr})
    out["icr"], out["sgn"] = icr, sgn
    rep = []
    for tag, s in (("W_fwd", sgn), ("W_bwd", -sgn)):
        fb = Frame53A(model)
        rb = reproduce(fb)
        rep.append(float(np.max(np.abs(np.asarray(rb["final_sdr"]) - final_sdr))))
        for nd in ops.getNodeTags():
            for dof in DOFS:
                ops.setNodeVel(nd, dof, 0.0, "-commit")
                ops.setNodeAccel(nd, dof, 0.0, "-commit")
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        fb.scale_motion(0.0)          # zero motion + rebuild (velocities already 0)
        out[tag] = fb.barrier(float(s), "mode1", icr)
        out[tag]["settle_status"] = rb["status"]
    out["settle_repro_max_abs_diff"] = max(rep)

    # --- second-motion collapse bracket
    sa1 = ida2["sa_unscaled"]
    dur2 = (len(rec2.acc) - 1) * rec2.dt
    dt_a = c53.dt_anal(rec2)
    S_hi = ida2["S_hi"]
    cache = {}

    def coll(sa2: float) -> bool:
        key = round(sa2, 6)
        if key in cache:
            return cache[key]["collapse"]
        f2 = Frame53A(model)
        r0 = reproduce(f2)
        if r0["status"] != "ok":
            cache[key] = {"sa": key, "status": r0["status"], "collapse": None}
            return False
        f2.second_motion(rec2.acc, rec2.dt, key / sa1)
        r1 = f2.continue_transient(t_stop=dur2 + 30.0, dt=dt_a)
        ent = {"sa": key, "status": r1["status"], "max_sdr": r1["max_sdr"],
               "t_coll": r1["t_coll"], "wall_s": r1["wall_s"],
               "collapse": bool(r1["status"] == "collapse" or
                                (r1["status"] == "nonconv" and r1["max_sdr"] >= 0.10))}
        cache[key] = ent
        return ent["collapse"]

    lo, hi = None, None
    sa = float(S_hi)
    if coll(sa):
        while True:
            hi = sa                    # last collapsing intensity
            sa /= 1.25
            if not coll(sa):
                lo = sa
                break
            if sa < 0.05 * S_hi:
                out.update({"status": "collapse_at_floor", "sa2_lo": None, "sa2_hi": sa})
                break
    else:
        while True:
            sa *= 1.25
            if sa > 2.5 * S_hi:
                out.update({"status": "censored_high", "sa2_lo": sa / 1.25, "sa2_hi": None})
                break
            if coll(sa):
                hi = sa
                break
            lo = sa
    if lo is not None and hi is not None:
        while hi / lo - 1.0 > 0.03:
            mid = math.sqrt(lo * hi)
            if coll(mid):
                hi = mid
            else:
                lo = mid
        out.update({"status": "ok", "sa2_lo": lo, "sa2_hi": hi})
    if out.get("sa2_hi") is not None:
        out["R"] = out["sa2_hi"] / S_hi
    out["runs"] = [cache[k] for k in sorted(cache)]
    out["FV"] = 30.0
    out["tol"] = 0.03
    out["ladder"] = 1.25


# =================================================================== A15: sibling-record second motion
def _event_key(rid: str) -> str:
    """Event grouping: FF/NF rids carry a component suffix; the event key drops it."""
    return rid.rsplit("_", 1)[0] if "_" in rid else rid[:-1]


def sibling_rid(model: str, rid: str) -> str | None:
    """The other horizontal component of the same event, looked up in the IDA dir."""
    sib = [p.stem for p in (RUNS / "ida" / model).glob("*.json")
           if _event_key(p.stem) == _event_key(rid) and p.stem != rid]
    return sib[0] if len(sib) == 1 else None


def task_aftershock_ms_sib(model: str, state: dict) -> dict:
    """A15: same as aftershock_ms, but the second motion is the OTHER horizontal
    component of the same event. Tests whether the settled barrier predicts
    retained capacity beyond the repeated record."""
    q = float(state["q"])
    rid = state["rid"]
    sib = sibling_rid(model, rid)
    out = {"type": "aftershock_ms_sib", "q": q, "rid2": sib}
    if sib is None:
        out["status"] = "no_sibling"
        return out
    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    ida2 = json.loads((RUNS / "ida" / model / f"{sib}.json").read_text())
    if ida["S_hi"] is None or ida2["S_hi"] is None:
        out["status"] = "no_intact_capacity"
        return out
    out.update({"S_hi": ida["S_hi"], "S_lo": ida["S_lo"],
                "sa_unscaled": ida["sa_unscaled"],
                "S_hi_2": ida2["S_hi"], "sa_unscaled_2": ida2["sa_unscaled"]})
    rec, _ = c53._common(model, rid, 1.0)
    rec2, _ = c53._common(model, sib, 1.0)
    S_hi = ida["S_hi"]
    scale = q * S_hi / ida["sa_unscaled"]
    dur = (len(rec.acc) - 1) * rec.dt
    dt_a = c53.dt_anal(rec)

    fr = Frame53A(model)
    fr.build()
    T1 = fr.geo.periods[0]
    T_set = max(30.0, 15.0 * T1)
    hist_from = dur + T_set - 2.0 * T1

    def reproduce(f: Frame53A):
        return f.run53(rec.acc, rec.dt, scale, dur + T_set, t_release=None,
                       dt_anal=dt_a, settle_check=False, keep_history=True,
                       hist_every=0.05, hist_from=hist_from)

    res = reproduce(fr)
    out["settle_status"] = res["status"]
    if res["status"] != "ok":
        out["status"] = "mainshock_collapse"
        out["settle"] = {"status": res["status"], "max_sdr": res["max_sdr"],
                         "t_end": res["t_end"]}
        return out
    final_sdr = np.asarray(res["final_sdr"], float)
    ht, hd = np.asarray(res["hist_t"]), np.asarray(res["hist_d"])
    win = hd[ht >= hist_from - 1e-9]
    out["settle"] = {
        "T_set": T_set, "T1": T1, "t_end": res["t_end"], "sa_mainshock": q * S_hi,
        "max_sdr": res["max_sdr"],
        "final_sdr": res["final_sdr"],
        "residual_roof_disp": float(fr.floor_disp()[-1]),
        "ke_end": float(fr.kinetic_energy()),
        "drift_range_last_2T1": float(np.max(win.max(axis=0) - win.min(axis=0))) if len(win) else None,
    }
    out["T_set"] = T_set
    _downstream(model, ida, rec, reproduce, final_sdr, out, rec2=rec2, ida2=ida2)
    return out


# =================================================================== A6b: mainshock-damaged family
def task_aftershock_ms(model: str, state: dict) -> dict:
    """Classical mainshock-damaged state: full record at Sa = q*S_hi, settle, then
    the same second-motion bracket as aftershock_a6."""
    q = float(state["q"])
    rid = state["rid"]
    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    out = {"type": "aftershock_ms", "q": q, "S_hi": ida["S_hi"], "S_lo": ida["S_lo"],
           "sa_unscaled": ida["sa_unscaled"]}
    if ida["S_hi"] is None:
        out["status"] = "no_intact_capacity"
        return out
    rec, _ = c53._common(model, rid, 1.0)
    S_hi = ida["S_hi"]
    scale = q * S_hi / ida["sa_unscaled"]
    dur = (len(rec.acc) - 1) * rec.dt
    dt_a = c53.dt_anal(rec)

    fr = Frame53A(model)
    fr.build()
    T1 = fr.geo.periods[0]
    T_set = max(30.0, 15.0 * T1)
    hist_from = dur + T_set - 2.0 * T1

    def reproduce(f: Frame53A):
        return f.run53(rec.acc, rec.dt, scale, dur + T_set, t_release=None,
                       dt_anal=dt_a, settle_check=False, keep_history=True,
                       hist_every=0.05, hist_from=hist_from)

    res = reproduce(fr)
    out["settle_status"] = res["status"]
    if res["status"] != "ok":
        out["status"] = "mainshock_collapse"
        out["settle"] = {"status": res["status"], "max_sdr": res["max_sdr"],
                         "t_end": res["t_end"]}
        return out
    final_sdr = np.asarray(res["final_sdr"], float)
    ht, hd = np.asarray(res["hist_t"]), np.asarray(res["hist_d"])
    win = hd[ht >= hist_from - 1e-9]
    out["settle"] = {
        "T_set": T_set, "T1": T1, "t_end": res["t_end"], "sa_mainshock": q * S_hi,
        "max_sdr": res["max_sdr"],
        "final_sdr": res["final_sdr"],
        "residual_roof_disp": float(fr.floor_disp()[-1]),
        "ke_end": float(fr.kinetic_energy()),
        "drift_range_last_2T1": float(np.max(win.max(axis=0) - win.min(axis=0))) if len(win) else None,
    }
    out["T_set"] = T_set
    _downstream(model, ida, rec, reproduce, final_sdr, out)
    return out


# =================================================================== barrier_intact
def task_barrier_intact(model: str, state: dict | None = None) -> dict:
    """Undeformed gravity-loaded frame barrier, both directions; icr = argmax of
    |phi1 interstorey drift| (phi1 normalised roof=1)."""
    fr = Frame53A(model)
    fr.build()
    phi = np.asarray(fr.geo.phi1, float)
    dd = np.abs(np.diff(np.concatenate([[0.0], phi])))
    icr = int(np.argmax(dd))
    out = {"type": "barrier_intact", "icr": icr,
           "phi1": phi.tolist(), "phi1_interstorey": dd.tolist(),
           "T1": fr.geo.periods[0]}
    for tag, s in (("W_fwd", 1.0), ("W_bwd", -1.0)):
        fb = Frame53A(model)
        fb.build()
        fb.scale_motion(0.0)          # zero-input transient stack (settled-case parity)
        out[tag] = fb.barrier(s, "mode1", icr)
    return out


# =================================================================== A7 task
def task_kick_energy(model: str, state: dict) -> dict:
    kpath = RUNS / "kick" / model / f"{state['rid']}__{state['level']}__{state['t_r']:.4f}.json"
    out = {"type": "kick_energy"}
    if not kpath.exists():
        out["status"] = "no_kick_json"
        return out
    kj = json.loads(kpath.read_text())
    beta_lo, beta_hi = kj.get("beta_lo"), kj.get("beta_hi")
    if beta_hi is None or beta_hi == 0:
        out["status"] = "no_bracket"
        return out
    rec, scale = c53._common(model, state["rid"], state["sa"])
    t_r = state["t_r"]
    runs = {}
    for beta in (beta_lo, beta_hi):
        if not beta or beta <= 0:
            continue
        key = f"{beta:.5f}"
        fr = Frame53A(model, track_energy=True)
        res = fr.run53(rec.acc, rec.dt, scale, t_r + c53.H_ZIC, t_release=t_r,
                       dt_anal=c53.dt_anal(rec), vel_scale=beta)
        lab = c53._label(res)
        old = (kj.get("runs") or {}).get(key)
        comp = None
        if old:
            comp = {"label_match": bool(old["label"] == lab),
                    "old_label": old["label"],
                    "max_sdr_diff": abs(res["max_sdr"] - old["max_sdr"])}
        summ = fr.energy_summary()
        runs[key] = {"beta": beta, "label": lab, "status": res["status"],
                     "t_end": res["t_end"], "max_sdr": res["max_sdr"],
                     "t_coll": res["first_passage"].get("0.15"),
                     "KE0": summ["KE_full0"], "KE0_paper": summ["KE0"],
                     "energy": summ, "series": fr.energy_series(),
                     "compare_kick_json": comp, "wall_s": res["wall_s"]}
    out["runs"] = runs
    out["status"] = "ok"
    return out


# =================================================================== push_deep task
def task_push_deep(model: str, state: dict) -> dict:
    """task_push with barrier max_droof=0.16 (theta_c=0.20 surface on CG frames)."""
    rec, scale = c53._common(model, state["rid"], state["sa"])
    fr = Frame53A(model)
    t_r = state["t_r"]
    res = fr.run53(rec.acc, rec.dt, scale, t_r + 1.0, t_release=t_r,
                   dt_anal=c53.dt_anal(rec), settle_check=False, stop_at_release=True)
    out = {"type": "push_deep", "pattern": "mode1", "max_droof": 0.16,
           "reproduce_status": res["status"]}
    snap = res["snapshots"].get("release")
    if res["status"] != "released" or snap is None:
        return out
    icr, sgn = c53.crit_story(snap)
    out.update(fr.barrier(sgn, "mode1", icr, max_droof=0.16))
    out["release_snapshot"] = {k: snap[k] for k in ("sdr", "floor_vel", "ke", "roof_disp") if k in snap}
    if state.get("snapshot"):
        s0 = np.asarray(state["snapshot"]["sdr"])
        s1 = np.asarray(snap["sdr"])
        out["snapshot_max_abs_diff_sdr"] = float(np.max(np.abs(s0 - s1)))
        out["ke_reproduced"] = snap["ke"]
    return out


# =================================================================== driver
_TASKS = {"aftershock_a6": task_aftershock_a6,
          "aftershock_ms": task_aftershock_ms,
          "aftershock_ms_sib": task_aftershock_ms_sib,
          "barrier_intact": task_barrier_intact,
          "kick_energy": task_kick_energy,
          "push_deep": task_push_deep}
_PROTOCOL = {"aftershock_a6": "R53v1.0+A6",
             "aftershock_ms": "R53v1.0+A6",
             "aftershock_ms_sib": "R53v1.0+A15",
             "barrier_intact": "R53v1.0+A6",
             "kick_energy": "R53v1.0+A7",
             "push_deep": "R53v1.0+A8"}


def _out_path(phase: str, model: str, state: dict) -> Path:
    if phase == "barrier_intact":
        return RUNS / phase / f"{model}.json"
    if phase in ("aftershock_ms", "aftershock_ms_sib"):
        return RUNS / phase / model / f"{state['rid']}__q{state['q']:.2f}.json"
    return c53.out_path(phase, model, state["rid"], state["level"], state["t_r"])


def _worker(args):
    phase, model, state = args
    path = _out_path(phase, model, state)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.name, "skip", 0.0
    logd = path.parent / "logs"
    logd.mkdir(exist_ok=True)
    ops.logFile(str(logd / f"ops_{os.getpid()}.log"), "-noEcho")
    t0 = time.time()
    try:
        res = _TASKS[phase](model, state)
        res.update({"state": {k: state[k] for k in
                              ("rid", "level", "tag", "t_r", "committed", "sa",
                               "model", "t_star", "q") if k in state},
                    "protocol": _PROTOCOL[phase], "code_sha256": code_sha256(),
                    "task_wall_s": round(time.time() - t0, 1)})
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
        return path.name, "ok", time.time() - t0
    except Exception:
        path.with_suffix(".err").write_text(traceback.format_exc(), encoding="utf-8")
        return path.name, "error", time.time() - t0


_MS_Q = (0.5, 0.7, 0.85, 0.95)


def build_tasks(phase: str, model: str, sets, tags, rid_stride, limit) -> list:
    tasks = []
    if phase == "barrier_intact":
        return [(phase, model, {"rid": "__intact__", "model": model})]
    if phase in ("aftershock_ms", "aftershock_ms_sib"):
        ida_dir = RUNS / "ida" / model
        rids = sorted(p.stem for p in ida_dir.glob("*.json")
                      if json.loads(p.read_text()).get("S_hi") is not None)
        if sets:
            rids = [r for r in rids if c53.record_set(r) in sets]
        if phase == "aftershock_ms_sib":
            rids = [r for r in rids if sibling_rid(model, r) is not None]
        if rid_stride and rid_stride > 1:
            rids = rids[::rid_stride]
        for r in rids:
            for q in _MS_Q:
                tasks.append((phase, model,
                              {"rid": r, "q": q, "tag": "ms", "level": f"q{q:.2f}",
                               "t_r": 0.0, "model": model}))
        return tasks[:limit] if limit else tasks
    states = [s for s in c53.select_states(model) if s["tag"] in tags]
    if sets:
        states = [s for s in states if c53.record_set(s["rid"]) in sets]
    if rid_stride and rid_stride > 1:
        rids = sorted({s["rid"] for s in states})
        keep = set(rids[::rid_stride])
        states = [s for s in states if s["rid"] in keep]
    for s in states:
        tasks.append((phase, model, s))
    if limit:
        tasks = tasks[:limit]
    return tasks


def run_phase(phase: str, models, sets, tags, workers, rid_stride, limit):
    tasks = []
    for m in models:
        tasks += build_tasks(phase, m, sets, tags, rid_stride, limit)
    print(f"{len(tasks)} tasks, {workers} workers, RUNS={RUNS}", flush=True)
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers) as pool:
        for k, (name, st, w) in enumerate(pool.imap_unordered(_worker, tasks), 1):
            print(f"[{k}/{len(tasks)} {time.time()-t0:7.0f}s] {name} {st} {w:.0f}s",
                  flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=list(_TASKS))
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--tags", nargs="+", default=["ta", "tstar"])
    ap.add_argument("--sets", nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rid-stride", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    run_phase(a.phase, a.models, a.sets, a.tags, a.workers, a.rid_stride, a.limit)
