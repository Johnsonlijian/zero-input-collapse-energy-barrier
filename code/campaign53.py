"""WP4 campaign — R53 v1.0, model-agnostic.

Phases (one JSON per task in <RUNS>/<phase>/<model>/<rid>__<level>__<t_r>.json):

  push           reproduce released state (stop_at_release), mode1 pushover
                 barrier with icr/sgn from the REPRODUCED release snapshot
                 (WP34_CAMPAIGN_SPEC).  --story adds the storey-block pattern
                 into push_story/ (sensitivity subsets only).
  kick           damped beta-bisection escape energy, exactly as
                 pilotA_barrier.task_kick (probes 0,1,1.25,1.6,2,2.8,4,5.7,8;
                 tol max(0.01, 2%)); beta=1 history kept (0.01 s, from t_r-1).
  kick_undamped  same with undamped=True (all Rayleigh damping removed at t_r).
  erosion        pushes at t95-2, t95-1, t95, then t95+0.5k <= t_c-0.05
                 (cap 40, uniform step widening, step recorded), plus t_a, t*.
  states         print state counts only.

State selection = pilotA_barrier.select_states verbatim (hi: ta, tstar,
early1, early2, late, rescued; lo: lo_ke, lo_drift).  kick/kick_undamped take
--tags (defaults: kick -> ta tstar rescued lo_ke; kick_undamped -> ta tstar).

RUNS root: env N0R53_RUNS, default E:\\n0r53\\runs.  Resumable: existing JSON
skipped; failures write one .err per task.  Every output carries
protocol="R53v1.0" and the sha256 of driver53.py + campaign53.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
PROTOCOL = "R53v1.0"
H_ZIC = 30.0
BETA_MAX = 8.0
BETA_LADDER = (1.25, 1.6, 2.0, 2.8, 4.0, 5.7, BETA_MAX)
N_BISECT = 12
N_HI = 1000
COLLAPSE_SDR = 0.15
KICK_TAGS = ("ta", "tstar", "rescued", "lo_ke")
KICK_UND_TAGS = ("ta", "tstar")

_geo_cache = {}


def geo(model):
    if model not in _geo_cache:
        from driver53 import Frame53
        fr = Frame53(model)
        fr.build()
        _geo_cache[model] = fr.geo
    return _geo_cache[model]


def code_sha256() -> dict:
    # Full executed import graph (A17): campaign modules plus the frozen driver
    # stack they import and the deterministic first-mode files they may load.
    out = {}
    for p in sorted(CODE_DIR.glob("*.py")) + sorted((CODE_DIR.parent / "code_copy").glob("*.py")):
        out[str(p.relative_to(CODE_DIR.parent)).replace("\\", "/")] = \
            hashlib.sha256(p.read_bytes()).hexdigest()
    phi_dir = CODE_DIR.parent / "code_copy" / "phi1"
    if phi_dir.exists():
        for p in sorted(phi_dir.glob("*.json")):
            out[f"phi1/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def dt_anal(rec):
    return min(rec.dt, 0.005)


def crit_story(snapshot: dict) -> tuple[int, float]:
    sdr = np.asarray(snapshot["sdr"], float)
    i = int(np.argmax(np.abs(sdr)))
    return i, float(np.sign(sdr[i]) or 1.0)


# ------------------------------------------------------------------ state selection
def select_states(model: str) -> list[dict]:
    """Verbatim pilotA_barrier.select_states, reading from RUNS/zic."""
    zd = RUNS / "zic" / model
    if not zd.exists():
        return []
    rids = sorted(p.stem.split("__")[0] for p in zd.glob("*__hi.json"))[:N_HI]
    states = []
    for rid in rids:
        z = json.loads((zd / f"{rid}__hi.json").read_text())
        if z.get("status") != "ok" or z.get("t_star") is None:
            continue
        ts, ta, tc = z["t_star"], z["t_a"], z["ref"]["t_coll"]
        rel = sorted((r for r in z["releases"].values() if r.get("snapshot")),
                     key=lambda r: r["t_r"])
        rec_states = [r for r in rel if r["t_r"] <= ta + 1e-9 and not r["committed"]]
        com_after = [r for r in rel if r["t_r"] >= ts - 1e-9 and r["committed"]]
        rescued = [r for r in rel if r["t_r"] < ta - 1e-9 and r["committed"]]
        pick = {}
        for tag, cand in (("ta", rec_states[-1:]), ("tstar", com_after[:1]),
                          ("early1", rec_states[:1]), ("early2", rec_states[1:2]),
                          ("late", com_after[-1:]), ("rescued", rescued[-1:])):
            for r in cand:
                key = f"{r['t_r']:.4f}"
                if key not in pick:
                    pick[key] = dict(rid=rid, level="hi", tag=tag, t_r=r["t_r"],
                                     committed=bool(r["committed"]), sa=z["sa"],
                                     snapshot=r["snapshot"], t_star=ts, t_a=ta,
                                     t_c=tc, model=model)
        states += list(pick.values())
        lo_path = zd / f"{rid}__lo.json"
        if lo_path.exists():
            zl = json.loads(lo_path.read_text())
            rl = [r for r in zl.get("releases", {}).values() if r.get("snapshot")]
            if rl:
                by_ke = max(rl, key=lambda r: r["snapshot"]["ke"])
                by_dr = max(rl, key=lambda r: max(abs(v) for v in r["snapshot"]["sdr"]))
                for tag, r in (("lo_ke", by_ke), ("lo_drift", by_dr)):
                    if not any(s["rid"] == rid and s["level"] == "lo"
                               and abs(s["t_r"] - r["t_r"]) < 1e-6 for s in states):
                        states.append(dict(rid=rid, level="lo", tag=tag, t_r=r["t_r"],
                                           committed=bool(r["committed"]), sa=zl["sa"],
                                           snapshot=r["snapshot"], t_star=None,
                                           t_a=None, t_c=None, model=model))
    return states


def erosion_times(model: str, rid: str) -> dict | None:
    """Spec grid: t95-2, t95-1, t95, t95+0.5k <= t_c-0.05 (cap 40) + t_a, t*."""
    zp = RUNS / "zic" / model / f"{rid}__hi.json"
    ip = RUNS / "ida" / model / f"{rid}.json"
    if not zp.exists() or not ip.exists():
        return None
    z = json.loads(zp.read_text())
    ida = json.loads(ip.read_text())
    if z.get("status") != "ok" or z.get("t_star") is None:
        return None
    t95, tc = ida["t95"], z["ref"]["t_coll"]
    anchors = [t95 - 2.0, t95 - 1.0, t95, z["t_a"], z["t_star"]]
    anchors = [t for t in anchors if t is not None and t >= 1.0 - 1e-9]
    t1 = tc - 0.05
    step = 0.5
    interior = list(np.arange(t95 + step, t1 + 1e-9, step))
    cap = 40
    n_anchor = len(set(round(t, 4) for t in anchors))
    allow = cap - n_anchor
    if len(interior) > allow:
        step = (t1 - t95) / max(allow, 1)
        interior = list(np.linspace(t95 + step, t1, max(allow - 1, 0)))
    times = sorted({round(t, 6) for t in anchors + interior if 1.0 - 1e-9 <= t <= t1 + 1e-6})
    return {"rid": rid, "sa": z["sa"], "t95": t95, "t_c": tc,
            "t_a": z.get("t_a"), "t_star": z.get("t_star"),
            "step": float(step), "times": times}


# ------------------------------------------------------------------ tasks
def _common(model: str, rid: str, sa: float):
    from records import load_all
    rec = load_all()[rid]
    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    return rec, sa / ida["sa_unscaled"]


def task_push(model: str, state: dict, pattern: str, variant: str = None) -> dict:
    from driver53 import Frame53
    rec, scale = _common(model, state["rid"], state["sa"])
    fr = Frame53(model)
    t_r = state["t_r"]
    vk = dict(_SENS_VARIANTS[variant]) if variant else {}
    dt_a = dt_anal(rec) / vk.pop("dt_scale", 1.0)
    vk.pop("drift_limit", None)          # barrier is displacement-controlled; limit unused
    assert not vk, f"unsupported push variant params: {vk}"
    res = fr.run53(rec.acc, rec.dt, scale, t_r + 1.0, t_release=t_r,
                   dt_anal=dt_a, settle_check=False, stop_at_release=True)
    out = {"type": "push", "pattern": pattern, "reproduce_status": res["status"]}
    snap = res["snapshots"].get("release")
    if res["status"] != "released" or snap is None:
        return out
    icr, sgn = crit_story(snap)                     # reproduced release snapshot (spec)
    out.update(fr.barrier(sgn, pattern, icr))
    out["release_snapshot"] = {k: snap[k] for k in ("sdr", "floor_vel", "ke", "roof_disp") if k in snap}
    if state.get("snapshot"):
        s0 = np.asarray(state["snapshot"]["sdr"])
        s1 = np.asarray(snap["sdr"])
        out["snapshot_max_abs_diff_sdr"] = float(np.max(np.abs(s0 - s1)))
        out["ke_reproduced"] = snap["ke"]
    return out


def _label(res: dict) -> str:
    if res["status"] == "collapse" or (res["status"] == "nonconv" and res["max_sdr"] >= 0.10):
        return "committed"
    if res["status"] == "ok":
        return "recoverable"
    return "censored"


def task_ktan(model: str, state: dict) -> dict:
    """Smallest eigenvalue of the tangent stiffness at the released state.

    Bernal's static-instability criterion: K_t indefinite => the configuration
    is already past the saddle.  The released state is reproduced exactly as
    task_push does; the ground-motion pattern is then removed, a zero load
    step forms the committed tangent, and the dense matrix is reduced with
    eigvalsh.  Reported raw and normalised by the first-mode eigenvalue of
    the intact gravity-loaded frame (same convention as the modal eigen).
    """
    import openseespy.opensees as ops
    from driver53 import Frame53, GM_PAT
    rec, scale = _common(model, state["rid"], state["sa"])
    fr = Frame53(model)
    t_r = state["t_r"]
    res = fr.run53(rec.acc, rec.dt, scale, t_r + 1.0, t_release=t_r,
                   dt_anal=dt_anal(rec), settle_check=False, stop_at_release=True)
    out = {"type": "ktan", "reproduce_status": res["status"]}
    if res["status"] != "released":
        return out
    try:
        ops.remove("loadPattern", GM_PAT)
    except Exception:
        pass
    ops.setTime(0.0)
    # Bernal's sign test on the generalised eigenproblem K*phi = lam*M*phi:
    # with the lumped-mass model the lowest eigenvalues are physical, and
    # lam1 < 0 <=> the tangent stiffness has a negative-curvature direction.
    ops.wipeAnalysis()
    ev = sorted(float(v) for v in ops.eigen("-fullGenLapack", 4))
    out["lam"] = ev
    out["lam_min"] = ev[0]
    out["n_neg"] = int(sum(1 for v in ev if v < -1e-9))
    out["ktan_unstable"] = bool(ev[0] < -1e-9)
    ops.wipeAnalysis()
    snap = res["snapshots"].get("release")
    if snap:
        out["release_snapshot"] = {k: snap[k] for k in ("sdr", "ke", "roof_disp") if k in snap}
    return out


def task_aftershock(model: str, state: dict) -> dict:
    """Collapse capacity of the settled damaged state under a second motion.

    Reproduces the released state (stop_at_release), zeroes the velocities
    (settled configuration, hysteretic variables kept), then applies the same
    record re-scaled by sa2/sa_unscaled and integrates the full record.  The
    collapse intensity sa2 is bracketed (x1.25 ladder, sqrt bisection to 12%);
    reported together with the intact-frame IDA bracket S_lo/S_hi, so that
    R = sa2_hi / S_hi is the capacity retained by the damaged state.
    """
    import math
    from driver53 import Frame53
    rec, scale = _common(model, state["rid"], state["sa"])
    ida = json.loads((RUNS / "ida" / model / f"{state['rid']}.json").read_text())
    fr = Frame53(model)
    t_r = state["t_r"]
    out = {"type": "aftershock", "S_hi": ida["S_hi"], "S_lo": ida["S_lo"]}
    res0 = fr.run53(rec.acc, rec.dt, scale, t_r + 1.0, t_release=t_r,
                    dt_anal=dt_anal(rec), settle_check=False, stop_at_release=True)
    out["reproduce_status"] = res0["status"]
    if res0["status"] != "released":
        return out
    sa1 = ida["sa_unscaled"]
    dt_a = dt_anal(rec)
    dur = (len(rec.acc) - 1) * rec.dt
    cache = {}

    def coll(sa2: float) -> bool:
        """Re-run: rebuild -> reproduce state -> apply second motion -> continue."""
        key = round(sa2, 6)
        if key in cache:
            return cache[key]["collapse"]
        fr2 = Frame53(model)
        r0 = fr2.run53(rec.acc, rec.dt, scale, t_r + 1.0, t_release=t_r,
                       dt_anal=dt_a, settle_check=False, stop_at_release=True)
        if r0["status"] != "released":
            cache[key] = {"sa": key, "status": r0["status"], "collapse": None}
            return False
        fr2.apply_second_motion(rec.acc, rec.dt, key / sa1)
        r1 = fr2.continue_transient(t_stop=dur + 15.0, dt=dt_a)
        ent = {"sa": key, "status": r1["status"], "max_sdr": r1["max_sdr"],
               "collapse": bool(r1["status"] == "collapse" or
                                (r1["status"] == "nonconv" and r1["max_sdr"] >= 0.10)),
               "wall_s": r1.get("wall_s")}
        cache[key] = ent
        return ent["collapse"]

    # geometric bracket on the second-motion intensity sa2 (g, Sa(T1) scale)
    lo, hi = None, None
    sa = 0.05
    cap = 3.0 * (ida["S_hi"] or 1.0)
    while sa <= cap:
        if coll(sa):
            hi = sa
            break
        lo = sa
        sa *= 1.6
    if hi is None:
        out.update({"status": "censored", "sa2_lo": lo, "sa2_hi": None})
    else:
        if lo is not None:
            while hi / lo - 1.0 > 0.12:
                mid = math.sqrt(lo * hi)
                if coll(mid):
                    hi = mid
                else:
                    lo = mid
        out.update({"status": "ok", "sa2_lo": lo, "sa2_hi": hi})
    out["runs"] = [cache[k] for k in sorted(cache)]
    return out


_SENS_VARIANTS = {
    "damp05":   {"damping_scale": 0.5},
    "damp20":   {"damping_scale": 2.0},
    "dt2":      {"dt_scale": 2.0},       # halved analysis step
    "theta010": {"drift_limit": 0.10},
    "theta020": {"drift_limit": 0.20},
}


def task_kick(model: str, state: dict, undamped: bool = False, variant: str = None) -> dict:
    from driver53 import Frame53
    rec, scale = _common(model, state["rid"], state["sa"])
    fr = Frame53(model)
    t_r = state["t_r"]
    runs = {}
    vk = dict(_SENS_VARIANTS[variant]) if variant else {}
    dt_a = dt_anal(rec) / vk.pop("dt_scale", 1.0)
    drift_limit = vk.pop("drift_limit", 0.15)

    def probe(beta: float, keep: bool = False) -> str:
        key = f"{beta:.5f}"
        if key in runs:
            return runs[key]["label"]
        res = fr.run53(rec.acc, rec.dt, scale, t_r + H_ZIC, t_release=t_r,
                       dt_anal=dt_a, vel_scale=beta, keep_history=keep,
                       drift_limit=drift_limit,
                       hist_every=0.01, hist_from=t_r - 1.0, undamped=undamped, **vk)
        lab = _label(res)
        entry = {"beta": beta, "label": lab, "status": res["status"],
                 "t_end": res["t_end"], "max_sdr": res["max_sdr"],
                 "final_sdr": res["final_sdr"], "settled_at": res["settled_at"],
                 "t_coll": res["first_passage"].get(f"{drift_limit:.2f}"), "wall_s": res["wall_s"]}
        if keep:
            entry["hist_t"], entry["hist_d"], entry["hist_ke"] = \
                res["hist_t"], res["hist_d"], res["hist_ke"]
            entry["snapshot_release"] = res["snapshots"].get("release")
        runs[key] = entry
        return lab

    out = {"type": f"kick_{variant}" if variant else ("kick_undamped" if undamped else "kick"),
           "runs": runs}
    lab1 = probe(1.0, keep=True)
    out["label_beta1"] = lab1
    if lab1 == "censored":
        return out
    if lab1 == "committed":
        lo, hi = 0.0, 1.0
        if probe(0.0) == "committed":
            out["beta_lo"], out["beta_hi"] = 0.0, 0.0
            out["beta_crit"] = 0.0
            return out
    else:
        lo, hi = 1.0, None
        for b in BETA_LADDER:
            lab = probe(b)
            if lab == "committed":
                hi = b
                break
            if lab == "censored":
                out["censored_at"] = b
                return out
            lo = b
        if hi is None:
            out["beta_lo"], out["beta_hi"] = lo, None
            out["beta_crit"] = None
            return out
    for _ in range(N_BISECT):
        if hi - lo <= max(0.01, 0.02 * hi):
            break
        mid = 0.5 * (lo + hi)
        lab = probe(mid)
        if lab == "committed":
            hi = mid
        elif lab == "recoverable":
            lo = mid
        else:
            out["censored_at"] = mid
            break
    out["beta_lo"], out["beta_hi"] = lo, hi
    out["beta_crit"] = 0.5 * (lo + hi)
    return out


# ------------------------------------------------------------------ driver
def out_path(phase: str, model: str, rid: str, level: str, t_r: float) -> Path:
    d = RUNS / phase / model
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{rid}__{level}__{t_r:.4f}.json"


def _worker(args):
    phase, model, payload = args
    if phase == "erosion":
        rid, t_r, sa = payload
        path = out_path("erosion", model, rid, "hi", t_r)
        state = dict(rid=rid, level="hi", tag="erosion", t_r=t_r, sa=sa,
                     snapshot=None, committed=None, model=model,
                     t_star=None, t_a=None, t_c=None)
        fn = lambda: task_push(model, state, "mode1")
    else:
        state = payload
        if phase == "push_story":
            path = out_path("push_story", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_push(model, state, "story")
        elif phase == "push":
            path = out_path("push", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_push(model, state, "mode1")
        elif phase == "push_det":
            path = out_path("push_det", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_push(model, state, "mode1")
        elif phase.startswith("push_") and phase[5:] in _SENS_VARIANTS:
            path = out_path(phase, model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_push(model, state, "mode1", variant=phase[5:])
        elif phase == "kick":
            path = out_path("kick", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_kick(model, state, False)
        elif phase == "kick_undamped":
            path = out_path("kick_undamped", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_kick(model, state, True)
        elif phase == "ktan":
            path = out_path("ktan", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_ktan(model, state)
        elif phase == "aftershock":
            path = out_path("aftershock", model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_aftershock(model, state)
        elif phase.startswith("kick_") and phase[5:] in _SENS_VARIANTS:
            path = out_path(phase, model, state["rid"], state["level"], state["t_r"])
            fn = lambda: task_kick(model, state, False, variant=phase[5:])
        else:
            raise ValueError(phase)
    if path.exists():
        return path.name, "skip", 0.0
    import openseespy.opensees as ops
    logd = path.parent / "logs"
    logd.mkdir(exist_ok=True)
    ops.logFile(str(logd / f"ops_{os.getpid()}.log"), "-noEcho")
    t0 = time.time()
    try:
        res = fn()
        res.update({"state": {k: state[k] for k in
                              ("rid", "level", "tag", "t_r", "committed", "sa",
                               "model", "t_star") if k in state},
                    "protocol": PROTOCOL, "code_sha256": code_sha256(),
                    "task_wall_s": round(time.time() - t0, 1)})
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
        return path.name, "ok", time.time() - t0
    except Exception:
        path.with_suffix(".err").write_text(traceback.format_exc(), encoding="utf-8")
        return path.name, "error", time.time() - t0


def _load_fork_set() -> set:
    """States that entered the A13 repeat-run audit (analysis/fork_rate.csv);
    t_r rounded to 2 decimals as stored there."""
    p = CODE_DIR.parent / "analysis" / "fork_rate.csv"
    out = set()
    if p.exists():
        import csv
        for r in csv.DictReader(open(p, newline="", encoding="utf-8-sig")):
            out.add((r["model"], r["rid"], r["level"], round(float(r["t_r"]), 2)))
    return out


_FORK_SET = _load_fork_set()


def build_tasks(phase: str, model: str, sets, tags, story, limit) -> list:
    tasks = []
    if phase == "erosion":
        zd = RUNS / "zic" / model
        if not zd.exists():
            return tasks
        rids = sorted(p.stem.split("__")[0] for p in zd.glob("*__hi.json"))[:N_HI]
        rids = [r for r in rids if r.split("_")[0][:2] in sets or any(r.startswith(s) for s in sets)]
        for rid in rids:
            h = erosion_times(model, rid)
            if h is None:
                continue
            for t in h["times"]:
                tasks.append(("erosion", model, (rid, t, h["sa"])))
    else:
        for s in select_states(model):
            if s["rid"].split("_")[0][:2] not in sets and not any(s["rid"].startswith(x) for x in sets):
                continue
            if phase == "push_det":
                # A17 deterministic-eigenvector re-run of the A13 fork sample:
                # only states present in analysis/fork_rate.csv
                if (s["model"], s["rid"], s["level"], round(float(s["t_r"]), 2)) in _FORK_SET:
                    tasks.append(("push_det", model, s))
            elif phase in ("push", "push_story"):
                if phase == "push":
                    tasks.append(("push", model, s))
                if story:
                    tasks.append(("push_story", model, s))
            elif phase.startswith("push_") and phase[5:] in _SENS_VARIANTS:
                if s["tag"] in tags:
                    tasks.append((phase, model, s))
            elif phase in ("kick", "kick_undamped", "ktan", "aftershock") or \
                    (phase.startswith("kick_") and phase[5:] in _SENS_VARIANTS):
                if s["tag"] in tags:
                    tasks.append((phase, model, s))
            else:
                raise ValueError(phase)
    if limit:
        tasks = tasks[:limit]
    return tasks


def record_set(rid: str) -> str:
    return rid.split("_")[0][:2]


def run_phase(phase: str, models, sets, workers, tags, story, limit):
    tasks = []
    for m in models:
        tasks += build_tasks(phase, m, sets, tags, story, limit)
    print(f"{len(tasks)} tasks, {workers} workers, RUNS={RUNS}", flush=True)
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers) as pool:
        for k, (name, st, w) in enumerate(pool.imap_unordered(_worker, tasks), 1):
            print(f"[{k}/{len(tasks)} {time.time()-t0:7.0f}s] {name} {st} {w:.0f}s",
                  flush=True)


def cmd_states(models, sets, tags):
    for m in models:
        states = select_states(m)
        if not states:
            print(f"{m}: no states (no usable zic files in {RUNS / 'zic' / m})")
            continue
        from collections import Counter
        c = Counter(s["tag"] for s in states)
        ks = [s for s in states if s["tag"] in tags and record_set(s["rid"]) in sets]
        print(f"{m}: {len(states)} states {dict(c)} | kick-eligible({tags}) in {sets}: {len(ks)}")
        zd = RUNS / "zic" / m
        rids = [p.stem.split("__")[0] for p in zd.glob("*__hi.json")]
        rids = [r for r in rids if record_set(r) in sets]
        n_ero = sum(len(erosion_times(m, r)["times"]) for r in rids
                    if erosion_times(m, r))
        print(f"{m}: erosion histories {len(rids)}, release tasks {n_ero}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["push", "push_det", "kick", "kick_undamped", "erosion", "ktan", "aftershock", "states"]
                                     + [f"kick_{v}" for v in _SENS_VARIANTS]
                                     + [f"push_{v}" for v in _SENS_VARIANTS])
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--sets", nargs="+", default=["FF", "NF"])
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tags", nargs="+", default=None)
    ap.add_argument("--story", action="store_true")
    a = ap.parse_args()
    tags = a.tags or (KICK_UND_TAGS if a.phase == "kick_undamped" else KICK_TAGS)
    if a.phase == "states":
        cmd_states(a.models, a.sets, tags)
    else:
        run_phase(a.phase, a.models, a.sets, a.workers, tags, a.story, a.limit)
