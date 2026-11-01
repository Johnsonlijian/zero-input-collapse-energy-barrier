"""NOT USED - ArcLength fallback failed validation V2 (forced arc on SMF8B fwd:
W 24165 vs 28381); superseded by lead decision.

R53v1.0+A6c: robust deep barrier pushes with ArcLength descent fallback.

Phases:
  barrier_intact_deep2 : intact-frame barriers to 0.20 roof drift; fallback chain
                         roof DisplacementControl -> icr storey control -> ArcLength.
  a6_barrier_deep2     : same fallback for settled-state pushes whose
                         a6_barrier_deep run ended by nonconvergence before exit.
"""
import argparse, hashlib, json, math, multiprocessing as mp, os, sys, time, traceback
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "code_copy"))

from records import load_all
from driver53 import Frame53, PO_TS, PO_PAT, GM_PAT
import campaign53 as c53
import addenda53 as a53
import addenda53b as a53b
from addenda53 import Frame53A, DOFS, _settle

RUNS = a53.RUNS
MAX_DROOF = 0.20


def code_sha256() -> dict:
    files = [Path(__file__), Path(a53.__file__), Path(a53b.__file__),
             Path(c53.__file__), Path(sys.modules[Frame53.__module__].__file__),
             Path(c53.__file__).parent.parent / "code_copy" / "driver.py"]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def _zero_vels():
    for nd in ops.getNodeTags():
        for dof in DOFS:
            ops.setNodeVel(nd, dof, 0.0, "-commit")
            ops.setNodeAccel(nd, dof, 0.0, "-commit")


def _exit_ok(res: dict) -> bool:
    """True if the push reached a natural exit rather than solver truncation."""
    if res.get("reached_edge"):
        return True
    c = res.get("curve") or []
    if not c:
        return False
    d = np.asarray(c)
    return bool(res.get("converged") and d[-1, 0] >= MAX_DROOF - 1e-9)


def _arc_continue(fr, sgn, icr, res, max_droof=MAX_DROOF):
    """Continue the push from the last converged state with ArcLength.

    Domain and PO_PAT are left live by the failed DisplacementControl run.
    Appends curve points into res in place.  Returns res (updated)."""
    c = res.get("curve") or []
    if not c:
        return res
    s = 1.0 if sgn >= 0 else -1.0
    H = fr.geo.height
    floors = fr.geo.floors
    roof = floors[-1]
    f = fr.pattern_vector("mode1", icr)
    # bookkeeping resumed from the last curve point
    arr = np.asarray(c, dtype=float)
    u_now = fr.floor_disp()
    x0 = float(u_now[-1]) - arr[-1, 0] * H * s       # reconstruct push-start roof disp
    droof_prev = arr[-1, 0]
    lam_prev = float(arr[-1, 1])
    work = float(arr[-1, 3])
    u_prev = u_now
    # last successful roof increment -> arc-length scale
    if len(arr) > 1:
        d_inc = abs(arr[-1, 0] - arr[-2, 0]) * H
    else:
        d_inc = abs(arr[-1, 0]) * H
    s_arc = max(d_inc, 1e-6)
    step0 = len(c)
    been_positive = bool(np.any(arr[:, 1] > 0))
    algs = (("Newton",), ("KrylovNewton",), ("NewtonLineSearch", 0.8))
    test = ("NormDispIncr", 1.0e-6, 200)

    def setup(alg, ss):
        ops.wipeAnalysis()
        ops.constraints("Plain"); ops.numberer("RCM"); ops.system("SparseGeneral")
        ops.test(*test); ops.algorithm(*alg)
        ops.integrator("ArcLength", ss, 0.0)
        ops.analysis("Static")

    stall = 0
    scale_i = 0
    t_arc0 = time.time()
    n_arc = 0
    while n_arc < 2000 and time.time() - t_arc0 < 1200:
        # try current s_arc with each algorithm
        ok = -1
        for alg in algs:
            setup(alg, s_arc)
            if ops.analyze(1) == 0:
                ok = 0
                break
        if ok != 0:
            s_arc /= 2.0
            scale_i += 1
            if scale_i > 6:          # s_arc down to 1/64
                break
            continue
        u = fr.floor_disp()
        lam = ops.getLoadFactor(PO_PAT) * s
        work += 0.5 * (lam + lam_prev) * s * float(np.dot(f, u - u_prev))
        droof = s * (u[-1] - x0) / H
        d, _ = fr.drifts()
        res["curve"].append((float(droof), float(lam), float(np.max(np.abs(d))), float(work)))
        u_prev, lam_prev = u, lam
        if lam > 0.0:
            been_positive = True
        if been_positive and lam <= 0.0:
            res["converged"] = True
            break
        if droof > max_droof:
            res["converged"] = True
            break
        n_arc += 1
        if abs(droof - droof_prev) < 1e-10:
            stall += 1
            s_arc /= 2.0
            if stall > 18 or s_arc < max(d_inc, 1e-6) / 64.0:
                break
        else:
            stall = 0
            s_arc = min(s_arc * 1.5, max(d_inc, s_arc))
        droof_prev = droof
    res["method_arc"] = {"start_step": step0, "s0": max(d_inc, 1e-6)}
    # recompute summary fields on the extended curve
    c2 = np.asarray(res["curve"], dtype=float)
    lam = c2[:, 1]
    W = c2[:, 3]
    res["lam0"] = float(lam[0])
    pos = np.where(lam > 0.0)[0]
    if len(pos):
        i1 = int(pos[0])
        neg = np.where(lam[i1:] <= 0.0)[0]
        i2 = int(i1 + neg[0]) if len(neg) else len(c2) - 1
        res["W_barrier"] = float(max(0.0, np.max(W[:i2 + 1])))
        res["W_barrier_from_min"] = float(np.max(W[:i2 + 1]) - np.min(W[:i1 + 1]))
        res["droof_positive"] = float(c2[i1, 0])
        res["droof_edge"] = float(c2[i2, 0])
        res["sdr_edge"] = float(c2[i2, 2])
        res["lam_peak"] = float(np.max(lam[:i2 + 1]))
        res["reached_edge"] = bool(len(neg))
    res["n_steps"] = len(res["curve"])
    return res


def _deep_barrier(fb, sgn, icr, max_droof=MAX_DROOF):
    """Roof control -> icr storey control -> ArcLength; keep furthest exit."""
    res = fb.barrier(sgn, "mode1", icr, max_droof=max_droof)
    res["method"] = "roof"
    if not _exit_ok(res):
        fb2 = Frame53A(fb.name)
        fb2.build()
        fb2.scale_motion(0.0)
        f = fb2.pattern_vector("mode1", icr)
        res2 = fb2.barrier_pattern(f, icr, sgn, max_droof=max_droof)
        res2["method"] = "icr"
        # keep whichever is better: an exit beats truncation, else larger progress
        better = res2 if (_exit_ok(res2) or
                          len(res2.get("curve", [])) > len(res.get("curve", []))) else res
        if not _exit_ok(better):
            if better is res2:
                _arc_continue(fb2, sgn, icr, res2, max_droof)
                if _exit_ok(res2):
                    res2["method"] = "icr+arclength"
            else:
                _arc_continue(fb, sgn, icr, res, max_droof)
                if _exit_ok(res):
                    res["method"] = "roof+arclength"
            # prefer an exited curve over a merely longer one
            if _exit_ok(res2) and not _exit_ok(res):
                res = res2
        else:
            res = better
    return res


# ------------------------------------------------------------ intact deep2
def task_barrier_intact_deep2(model: str, state: dict | None = None) -> dict:
    fr = Frame53A(model)
    fr.build()
    phi = np.asarray(fr.geo.phi1, float)
    dd = np.abs(np.diff(np.concatenate([[0.0], phi])))
    icr = int(np.argmax(dd))
    out = {"type": "barrier_intact_deep2", "icr": icr, "max_droof": MAX_DROOF,
           "phi1_interstorey": dd.tolist(), "T1": fr.geo.periods[0]}
    for tag, s in (("W_fwd", 1.0), ("W_bwd", -1.0)):
        fb = Frame53A(model)
        fb.build()
        fb.scale_motion(0.0)
        out[tag] = _deep_barrier(fb, s, icr)
    return out


# ------------------------------------------------------------ a6 deep2
def task_a6_barrier_deep2(model: str, st: dict) -> dict:
    j = st["_stored"]
    out = {"type": "a6_barrier_deep2", "max_droof": MAX_DROOF,
           "family": st["_family"], "src_status": j.get("status"),
           "icr": j["icr"], "sgn": j["sgn"]}
    icr, sgn = int(j["icr"]), float(j["sgn"])
    repro = a53b._reproduce(model, st)
    for tag, s in (("W_fwd", sgn), ("W_bwd", -sgn)):
        fb = Frame53A(model)
        rb = repro(fb)
        if tag == "W_fwd":
            fs = np.asarray(rb.get("final_sdr") or [], float)
            stored = np.asarray(j["settle"].get("final_sdr") or [], float)
            out["settle_max_abs_diff_sdr"] = (
                float(np.max(np.abs(fs - stored))) if fs.size == stored.size and fs.size else None)
            out["repro_status"] = rb["status"]
        if rb["status"] != "ok":
            out["status"] = "repro_failed"
            return out
        _zero_vels()
        try:
            ops.remove("loadPattern", GM_PAT)
        except Exception:
            pass
        fb.scale_motion(0.0)
        out[tag] = _deep_barrier(fb, s, icr)
    out["status"] = "ok"
    return out


# =================================================================== driver
_TASKS = {"a6_barrier_deep2": task_a6_barrier_deep2,
          "barrier_intact_deep2": task_barrier_intact_deep2}
_PROTOCOL = {k: "R53v1.0+A6c" for k in _TASKS}


def _out_path(phase, model, st):
    if phase == "barrier_intact_deep2":
        return RUNS / phase / f"{model}.json"
    return RUNS / phase / model / st["_fname"]


def _worker(args):
    phase, model, st = args
    path = _out_path(phase, model, st)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.name, "skip", 0.0
    logd = path.parent / "logs"
    logd.mkdir(exist_ok=True)
    ops.logFile(str(logd / f"ops_{os.getpid()}.log"), "-noEcho")
    t0 = time.time()
    try:
        res = _TASKS[phase](model, st)
        keep = {k: st[k] for k in ("rid", "level", "tag", "t_r", "q", "model") if k in st}
        res.update({"state": keep, "protocol": _PROTOCOL[phase],
                    "code_sha256": code_sha256(),
                    "task_wall_s": round(time.time() - t0, 1)})
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
        return path.name, "ok", time.time() - t0
    except Exception:
        path.with_suffix(".err").write_text(traceback.format_exc(), encoding="utf-8")
        return path.name, "error", time.time() - t0


def _a6_states(model: str):
    """Settled states whose a6_barrier_deep run ended nonconverged pre-exit."""
    out = []
    dd = RUNS / "a6_barrier_deep" / model
    if not dd.exists():
        return out
    for p in sorted(dd.glob("*.json")):
        try:
            j = json.loads(p.read_text())
        except Exception:
            continue
        if j.get("status") != "ok":
            continue
        needs = any(not _exit_ok(j.get(t, {})) for t in ("W_fwd", "W_bwd"))
        if not needs:
            continue
        fam, ph = j["family"], j["src_status"]
        src = RUNS / ("aftershock_a6" if j["family"] == "a6" else "aftershock_ms") / model / p.name
        if not src.exists():
            continue
        sj = json.loads(src.read_text())
        st = dict(sj["state"]); st["_family"] = j["family"]; st["_stored"] = sj
        st["_fname"] = p.name
        rid = st["rid"]
        rec, scale = c53._common(model, rid, st.get("sa") if j["family"] == "a6" else 1.0)
        if j["family"] == "ms":
            scale = st["q"] * sj["S_hi"] / sj["sa_unscaled"]
        st["_rec"], st["_scale"] = rec, scale
        out.append(("a6_barrier_deep2", model, st))
    return out


def build_tasks(phase, model):
    if phase == "barrier_intact_deep2":
        return [(phase, model, {"model": model, "rid": "__intact__"})]
    return _a6_states(model)


def run_phase(phase, models, workers):
    tasks = []
    for m in models:
        tasks += build_tasks(phase, m)
    print(f"{len(tasks)} tasks, {workers} workers, RUNS={RUNS}", flush=True)
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers) as pool:
        for k, (name, st, w) in enumerate(pool.imap_unordered(_worker, tasks), 1):
            print(f"[{k}/{len(tasks)} {time.time()-t0:7.0f}s] {name} {st} {w:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=list(_TASKS))
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    run_phase(a.phase, a.models, a.workers)
