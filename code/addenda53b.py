"""R53v1.0+A6b: deep barrier re-pushes (max_droof=0.20) for the A6 experiments.

  a6_barrier_deep   : re-push W_fwd/W_bwd on the stored settled states of
                      RUNS/aftershock_a6 and RUNS/aftershock_ms (resumable).
  barrier_intact_deep: intact-frame barriers to 0.20 roof drift, all models,
                      with storey-control fallback for descent nonconvergence.
"""
import argparse, hashlib, json, math, multiprocessing as mp, os, sys, time, traceback
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "code_copy"))

from records import load_all
from driver53 import Frame53
import campaign53 as c53
import addenda53 as a53
from addenda53 import Frame53A, DOFS, GM_PAT, _settle

RUNS = a53.RUNS
MAX_DROOF = 0.20


def code_sha256() -> dict:
    files = [Path(__file__), Path(a53.__file__), Path(c53.__file__),
             Path(sys.modules[Frame53.__module__].__file__),
             Path(c53.__file__).parent.parent / "code_copy" / "driver.py"]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16] for f in files}


def _zero_vels():
    for nd in ops.getNodeTags():
        for dof in DOFS:
            ops.setNodeVel(nd, dof, 0.0, "-commit")
            ops.setNodeAccel(nd, dof, 0.0, "-commit")


# ---------------------------------------------------------------- a6_barrier_deep
def _reproduce(model: str, st: dict, keep_hist=False):
    """Rebuild the settled state exactly as the producing task did."""
    j, rec, scale = st["_stored"], st["_rec"], st["_scale"]
    T_set, T1 = j["settle"]["T_set"], j["settle"]["T1"]
    if st["_family"] == "ms":
        dur = (len(rec.acc) - 1) * rec.dt
        def repro(f):
            return f.run53(rec.acc, rec.dt, scale, dur + T_set, t_release=None,
                           dt_anal=c53.dt_anal(rec), settle_check=False,
                           keep_history=keep_hist, hist_every=0.05,
                           hist_from=dur + T_set - 2.0 * T1)
    else:
        t_r = st["t_r"]
        def repro(f):
            return _settle(f, rec, scale, t_r, T_set, T1, keep_hist=keep_hist)
    return repro


def task_a6_barrier_deep(model: str, st: dict) -> dict:
    j = st["_stored"]
    out = {"type": "a6_barrier_deep", "max_droof": MAX_DROOF,
           "family": st["_family"], "src_status": j.get("status"),
           "icr": j["icr"], "sgn": j["sgn"]}
    icr, sgn = int(j["icr"]), float(j["sgn"])
    repro = _reproduce(model, st)
    # settle check on one reproduction
    fr = Frame53A(model)
    res = repro(fr)
    out["repro_status"] = res["status"]
    fs = np.asarray(res.get("final_sdr") or [], float)
    stored = np.asarray(j["settle"].get("final_sdr") or [], float)
    out["settle_max_abs_diff_sdr"] = (
        float(np.max(np.abs(fs - stored))) if fs.size == stored.size and fs.size else None)
    if res["status"] != "ok":
        out["status"] = "repro_failed"
        return out
    _zero_vels()
    try:
        ops.remove("loadPattern", GM_PAT)
    except Exception:
        pass
    fr.scale_motion(0.0)
    out["W_fwd"] = fr.barrier(sgn, "mode1", icr, max_droof=MAX_DROOF)
    fb = Frame53A(model)
    rb = repro(fb)
    out["repro2_status"] = rb["status"]
    _zero_vels()
    try:
        ops.remove("loadPattern", GM_PAT)
    except Exception:
        pass
    fb.scale_motion(0.0)
    out["W_bwd"] = fb.barrier(-sgn, "mode1", icr, max_droof=MAX_DROOF)
    out["status"] = "ok"
    return out


# ------------------------------------------------------------- barrier_intact_deep
def task_barrier_intact_deep(model: str, state: dict | None = None) -> dict:
    fr = Frame53A(model)
    fr.build()
    phi = np.asarray(fr.geo.phi1, float)
    dd = np.abs(np.diff(np.concatenate([[0.0], phi])))
    icr = int(np.argmax(dd))
    out = {"type": "barrier_intact_deep", "icr": icr, "max_droof": MAX_DROOF,
           "phi1_interstorey": dd.tolist(), "T1": fr.geo.periods[0]}
    for tag, s in (("W_fwd", 1.0), ("W_bwd", -1.0)):
        fb = Frame53A(model)
        fb.build()
        fb.scale_motion(0.0)
        res = fb.barrier(s, "mode1", icr, max_droof=MAX_DROOF)
        res["method"] = "barrier_roof_ctrl"
        if not res.get("converged"):
            # robust fallback: control the critical-storey node directly
            fb2 = Frame53A(model)
            fb2.build()
            fb2.scale_motion(0.0)
            f = fb2.pattern_vector("mode1", icr)
            res2 = fb2.barrier_pattern(f, icr, s, max_droof=MAX_DROOF)
            res2["method"] = "barrier_pattern_ctrl_icr"
            res2["fallback_of"] = {k: res[k] for k in
                                   ("converged", "n_steps", "lam_peak", "sdr_edge")
                                   if k in res}
            res = res2 if res2.get("converged") or len(res2.get("curve", [])) > len(res.get("curve", [])) else res
        out[tag] = res
    return out


# =================================================================== driver
_TASKS = {"a6_barrier_deep": task_a6_barrier_deep,
          "barrier_intact_deep": task_barrier_intact_deep}
_PROTOCOL = {k: "R53v1.0+A6b" for k in _TASKS}


def _out_path(phase, model, st):
    if phase == "barrier_intact_deep":
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


_SKIP = {"mainshock_collapse", "not_recoverable", "no_intact_capacity",
         "repro_failed", None}


def _a6_states(model: str):
    """Load stored a6/ms JSONs needing deep barriers."""
    out = []
    for fam, ph in (("a6", "aftershock_a6"), ("ms", "aftershock_ms")):
        d = RUNS / ph / model
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                j = json.loads(p.read_text())
            except Exception:
                continue
            if j.get("status") in _SKIP or j.get("icr") is None or j.get("sgn") is None:
                continue
            if not (j.get("settle") or {}).get("final_sdr"):
                continue
            st = dict(j["state"]); st["_family"] = fam; st["_stored"] = j
            st["_fname"] = p.name
            rid = st["rid"]
            rec, scale = c53._common(model, rid, st.get("sa") if fam == "a6" else 1.0)
            if fam == "ms":
                scale = st["q"] * j["S_hi"] / j["sa_unscaled"]
            st["_rec"], st["_scale"] = rec, scale
            out.append(("a6_barrier_deep", model, st))
    return out


def build_tasks(phase, model):
    if phase == "barrier_intact_deep":
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
