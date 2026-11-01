"""R53v1.0+A6d: solver-parameter fallback for deep barrier pushes.

barrier_intact_deep W_fwd stalls mid-descent on all five CG models (genuine
nonconvergence at 60-100% of peak lambda).  This module continues the stalled
push from the last converged state with DisplacementControl at reduced
increments (/10, /100, /1000), each tried with the full
{Newton, NewtonLineSearch, KrylovNewton, ModifiedNewton -initial, BFGS, Broyden}
x {NormDispIncr 1e-6@500, EnergyIncr 1e-8@500} ladder; the increment grows back
x2 after 20 consecutive converged steps (up to the original).  If the
roof-controlled continuation fails, the same ladder is applied to the top node
of the storey with the largest current drift.

Phase:
  barrier_intact_deep_d : intact-frame barriers; W_fwd computed with the
                          fallback chain, W_bwd copied from barrier_intact_deep.
Output: RUNS/barrier_intact_deep_d/<model>.json  (protocol R53v1.0+A6d)
"""
import argparse, hashlib, json, multiprocessing as mp, os, sys, time, traceback
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "code_copy"))

import campaign53 as c53
import addenda53 as a53
import addenda53b as a53b
from addenda53 import Frame53A, DOFS
from driver53 import PO_PAT

RUNS = a53.RUNS
MAX_DROOF = 0.20
ALGS = (("Newton",), ("NewtonLineSearch", 0.8), ("KrylovNewton",),
        ("ModifiedNewton", "-initial"), ("BFGS",), ("Broyden",))
TESTS = (("NormDispIncr", 1.0e-6, 500), ("EnergyIncr", 1.0e-8, 500))
GROW_AFTER = 20


def code_sha256() -> dict:
    files = [Path(__file__), Path(a53.__file__), Path(a53b.__file__),
             Path(c53.__file__),
             Path(c53.__file__).parent.parent / "code_copy" / "driver.py"]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def _exit_ok(res: dict) -> bool:
    if res.get("reached_edge") or res.get("stall_exit"):
        return True
    c = res.get("curve") or []
    return bool(c and res.get("converged") and c[-1][0] >= MAX_DROOF - 1e-9)


def _refresh_summary(res):
    c = np.asarray(res["curve"], dtype=float)
    lam, W = c[:, 1], c[:, 3]
    pos = np.where(lam > 0.0)[0]
    res["lam0"] = float(lam[0])
    res["n_steps"] = len(c)
    if len(pos):
        i1 = int(pos[0])
        neg = np.where(lam[i1:] <= 0.0)[0]
        i2 = int(i1 + neg[0]) if len(neg) else len(c) - 1
        res["W_min_before_positive"] = float(np.min(W[:i1 + 1]))
        res["W_max"] = float(np.max(W[:i2 + 1]))
        res["W_barrier"] = float(max(0.0, np.max(W[:i2 + 1])))
        res["W_barrier_from_min"] = float(np.max(W[:i2 + 1]) - np.min(W[:i1 + 1]))
        res["droof_positive"] = float(c[i1, 0])
        res["droof_edge"] = float(c[i2, 0])
        res["sdr_edge"] = float(c[i2, 2])
        res["lam_peak"] = float(np.max(lam[:i2 + 1]))
        res["reached_edge"] = bool(len(neg))


def _small_continue(fr, sgn, icr, res, node, method, max_droof=MAX_DROOF):
    """Continue a stalled push with small-step DisplacementControl on `node`.

    `node` is a floor NODE TAG (roof for 'roof_small', storey top for
    'storey_small').  Returns res (updated in place)."""
    c = res.get("curve") or []
    if not c:
        return res
    arr = np.asarray(c, dtype=float)
    s = 1.0 if sgn >= 0 else -1.0
    H = fr.geo.height
    floors = fr.geo.floors
    roof = floors[-1]
    f = fr.pattern_vector("mode1", icr)
    u_now = fr.floor_disp()
    x0 = float(u_now[-1]) - arr[-1, 0] * H * s
    lam_prev = float(arr[-1, 1])
    work = float(arr[-1, 3])
    u_prev = u_now
    droof_prev = float(arr[-1, 0])
    been_positive = bool(np.any(arr[:, 1] > 0.0))
    lam_peak = float(res.get("lam_peak") or np.max(np.abs(arr[:, 1])))
    # last successful controlled-node increment (displacement units)
    inc0 = abs(arr[-1, 0] - arr[-2, 0]) * H if len(arr) > 1 else abs(arr[-1, 0]) * H
    inc0 = max(inc0, 1e-6)
    fallback_step = len(c)
    done = False
    for div in (10, 100, 1000):
        du = inc0 / div
        n_ok = 0
        failed = False
        steps = 0
        while not done and steps < 4000:
            # try this increment with the full alg x test ladder
            ok = -1
            for test in TESTS:
                for alg in ALGS:
                    fr._static_setup(node, s * du, test, alg)
                    ok = ops.analyze(1)
                    if ok == 0:
                        break
                if ok == 0:
                    break
            if ok != 0:
                failed = True
                break
            steps += 1
            u = fr.floor_disp()
            lam = ops.getLoadFactor(PO_PAT) * s
            work += 0.5 * (lam + lam_prev) * s * float(np.dot(f, u - u_prev))
            droof = s * (u[-1] - x0) / H
            d, _ = fr.drifts()
            res["curve"].append((float(droof), float(lam),
                                 float(np.max(np.abs(d))), float(work)))
            u_prev, lam_prev = u, lam
            if lam > 0.0:
                been_positive = True
            if been_positive and lam <= 0.0:
                res["converged"] = True; done = True; break
            if droof > max_droof:
                res["converged"] = True; done = True; break
            if been_positive and lam <= 0.01 * lam_peak:
                res["converged"] = True
                res["stall_exit"] = True
                done = True; break
            n_ok += 1
            if n_ok >= GROW_AFTER and du < inc0:
                du = min(du * 2.0, inc0)
                n_ok = 0
            droof_prev = droof
        if done:
            break
        if not failed and steps == 0:
            continue
        # a step failed even at this size -> go finer
        if not failed:
            break
    res["method"] = method
    res["fallback_step"] = fallback_step
    res["final_increment"] = du
    _refresh_summary(res)
    return res


def _barrier_d(fb, sgn, icr, max_droof=MAX_DROOF):
    """barrier() -> icr storey-control (addenda53b parity) -> small-step ladder."""
    res = fb.barrier(sgn, "mode1", icr, max_droof=max_droof)
    res["method"] = "roof"
    host = fb
    if not _exit_ok(res):
        fb2 = Frame53A(fb.name)
        fb2.build()
        fb2.scale_motion(0.0)
        f = fb2.pattern_vector("mode1", icr)
        res2 = fb2.barrier_pattern(f, icr, sgn, max_droof=max_droof)
        res2["method"] = "icr"
        if _exit_ok(res2) or len(res2.get("curve", [])) > len(res.get("curve", [])):
            res, host = res2, fb2
    if not _exit_ok(res) and res.get("curve"):
        # trigger condition: stalled by nonconvergence above 1% of peak
        arr = np.asarray(res["curve"], dtype=float)
        peak = float(res.get("lam_peak") or np.max(np.abs(arr[:, 1])))
        last_lam = float(arr[-1, 1])
        if last_lam > 0.01 * peak:
            _small_continue(host, sgn, icr, res, host.geo.floors[-1],
                            "roof_small", max_droof)
            if not _exit_ok(res):
                # storey-control on the top node of the largest-drift storey
                d, _ = host.drifts()
                i_storey = int(np.argmax(np.abs(d)))
                node = host.geo.floors[min(i_storey + 1, len(host.geo.floors) - 1)]
                _small_continue(host, sgn, icr, res, node, "storey_small",
                                max_droof)
    return res


def task_barrier_intact_deep_d(model: str, state: dict | None = None) -> dict:
    fr = Frame53A(model)
    fr.build()
    phi = np.asarray(fr.geo.phi1, float)
    dd = np.abs(np.diff(np.concatenate([[0.0], phi])))
    icr = int(np.argmax(dd))
    out = {"type": "barrier_intact_deep", "icr": icr, "max_droof": MAX_DROOF,
           "phi1_interstorey": dd.tolist(), "T1": fr.geo.periods[0]}
    fb = Frame53A(model)
    fb.build()
    fb.scale_motion(0.0)
    out["W_fwd"] = _barrier_d(fb, 1.0, icr)
    src = RUNS / "barrier_intact_deep" / f"{model}.json"
    sj = json.loads(src.read_text()) if src.exists() else {}
    wb = dict(sj.get("W_bwd") or {})
    wb["copied"] = True
    out["W_bwd"] = wb
    return out


# =================================================================== driver
_TASKS = {"barrier_intact_deep_d": task_barrier_intact_deep_d}
_PROTOCOL = "R53v1.0+A6d"


def _worker(args):
    phase, model, st = args
    path = RUNS / phase / f"{model}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.name, "skip", 0.0
    logd = path.parent / "logs"
    logd.mkdir(exist_ok=True)
    ops.logFile(str(logd / f"ops_{os.getpid()}.log"), "-noEcho")
    t0 = time.time()
    try:
        res = _TASKS[phase](model, st)
        res.update({"state": {"model": model}, "protocol": _PROTOCOL,
                    "code_sha256": code_sha256(),
                    "task_wall_s": round(time.time() - t0, 1)})
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
        return path.name, "ok", time.time() - t0
    except Exception:
        path.with_suffix(".err").write_text(traceback.format_exc(), encoding="utf-8")
        return path.name, "error", time.time() - t0


def run_phase(phase, models, workers):
    tasks = [(phase, m, {"model": m}) for m in models]
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
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    run_phase(a.phase, a.models, a.workers)
