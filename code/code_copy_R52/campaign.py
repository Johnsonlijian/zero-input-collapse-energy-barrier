"""Computation campaign: IDA, zero-input commitment search, released-state pushovers.

Usage (Windows, local work folder):
    python campaign.py ida   --models SMF4B SMF8B --workers 30
    python campaign.py zic   --models SMF4B --workers 30
    python campaign.py push  --models SMF4B --workers 30

Every task writes one JSON file to RUNS/<phase>/<model>/<rid>.json and is
skipped if that file already exists, so the campaign is resumable.

Definitions (fixed before the runs; see notes/PROTOCOL_R52.md):
* IM: 5%-damped Sa(T1), T1 = first-mode period of the published model.
* Collapse: peak story drift ratio >= 0.15 (published limit), or a run that
  cannot be continued after the peak drift has exceeded 0.10.
* Full-record analyses are followed by up to FV = 30 s of free vibration
  (early stop once settled, see driver.run).
* IDA: upward hunt from Sa = 0.25 g with factor 1.5 (first collapse), then bisection until
  S_hi/S_lo - 1 <= 0.03.  S_hi is the record's collapse intensity S_c.
* Zero-input continuation (ZIC) of a state at t_r: same record truncated at
  t_r, integrated for up to H = 30 s.  Label 'committed' if it collapses,
  'recoverable' if it settles or reaches H without collapse.
* Point of no return t*: on the collapse trajectory at S_hi, the latest
  recoverable->committed transition found before collapse.  A backward
  exponential search supplies an initial bracket; all sampled transitions
  are then compared and the latest bracket is bisected to 0.02 s.  This
  matters because commitment during a forced response can be non-monotonic.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
FV = 30.0            # free vibration after a full record (s)
H_ZIC = 30.0         # zero-input horizon (s)
SA_START, SA_FACTOR, SA_MAX, TOL = 0.25, 1.5, 12.0, 0.03
BISECT_RES = 0.02    # s


def _dt_anal(rec) -> float:
    # N0R52_DT_FACTOR < 1 is used only for the time-step sensitivity check
    return min(rec.dt, 0.005) * float(os.environ.get("N0R52_DT_FACTOR", "1"))


def is_collapse(s: dict) -> bool:
    return s["status"] == "collapse" or (s["status"] == "nonconv" and s["max_sdr"] >= 0.10)


def t_collapse(s: dict) -> float | None:
    if s["status"] == "collapse":
        return s["first_passage"]["0.15"]
    if s["status"] == "nonconv" and s["max_sdr"] >= 0.10:
        return s["t_end"]
    return None


def _summ(res: dict, rec, sa: float) -> dict:
    out = {k: res[k] for k in ("status", "t_end", "t_input_end", "max_sdr", "peak_sdr", "first_passage",
                               "final_sdr", "settled_at", "t_peak", "wall_s")}
    out["sa"] = sa
    out["t_record_end"] = rec.duration
    out["t_coll"] = t_collapse(res)
    out["collapse"] = is_collapse(res)
    return out


# ----------------------------------------------------------------------------- IDA
def task_ida(model: str, rid: str) -> dict:
    from driver import Frame
    from records import load_all, sa_spectrum, arias_times

    rec = load_all()[rid]
    fr = Frame(model)
    fr.build()
    T1 = fr.geo.periods[0]
    sa1 = float(sa_spectrum(rec.acc, rec.dt, [T1])[0])
    t5, t95, ia = arias_times(rec.acc, rec.dt)
    cache: dict[float, dict] = {}

    def run_at(sa: float) -> dict:
        key = round(sa, 6)
        if key not in cache:
            res = fr.run(rec.acc, rec.dt, sa / sa1, rec.duration + FV, dt_anal=_dt_anal(rec))
            cache[key] = _summ(res, rec, key)
        return cache[key]

    def search(pred, start: float) -> tuple[float | None, float | None]:
        lo = hi = None
        sa = start
        if pred(run_at(sa)):
            hi = sa
            while lo is None:
                sa /= SA_FACTOR
                if sa < 0.05:
                    break
                if pred(run_at(sa)):
                    hi = sa
                else:
                    lo = sa
        else:
            lo = sa
            while hi is None:
                sa *= SA_FACTOR
                if sa > SA_MAX:
                    break
                if pred(run_at(sa)):
                    hi = sa
                else:
                    lo = sa
        if hi is None or lo is None:
            return lo, hi
        while hi / lo - 1.0 > TOL:
            mid = math.sqrt(lo * hi)
            if pred(run_at(mid)):
                hi = mid
            else:
                lo = mid
        return lo, hi

    lo, hi = search(is_collapse, SA_START)
    out = {"model": model, "rid": rid, "T1": T1, "sa_unscaled": sa1, "t5": t5, "t95": t95, "arias": ia,
           "duration": rec.duration, "dt": rec.dt, "S_lo": lo, "S_hi": hi}
    # Same search for an analysis that stops at the end of the record
    if hi is not None:
        def coll_by_end(s):
            return s["collapse"] and s["t_coll"] is not None and s["t_coll"] <= s["t_record_end"] + 1e-9
        lo_t, hi_t = search(coll_by_end, SA_START)
        out["S_lo_trunc"], out["S_hi_trunc"] = lo_t, hi_t
    out["runs"] = [cache[k] for k in sorted(cache)]
    return out


# ----------------------------------------------------------------------------- ZIC
def task_zic(model: str, rid: str, level: str) -> dict:
    """Locate the point of no return on the trajectory at the given intensity.

    level 'hi': collapse trajectory at S_hi; level 'x15': at 1.5 S_hi;
    level 'lo': non-collapse trajectory at S_lo (dangerous states only).
    """
    from driver import Frame
    from records import load_all, sa_spectrum

    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    rec = load_all()[rid]
    fr = Frame(model)
    fr.build()
    sa1 = ida["sa_unscaled"]
    sa = {"hi": ida["S_hi"], "x15": None if ida["S_hi"] is None else 1.5 * ida["S_hi"], "lo": ida["S_lo"]}[level]
    out = {"model": model, "rid": rid, "level": level, "sa": sa}
    if sa is None:
        out["status"] = "no_intensity"
        return out
    scale = sa / sa1
    dta = _dt_anal(rec)
    # Reference (full-record) trajectory
    ref = fr.run(rec.acc, rec.dt, scale, rec.duration + FV, dt_anal=dta, keep_history=True, hist_every=0.05)
    out["ref"] = {k: ref[k] for k in ("status", "t_end", "max_sdr", "peak_sdr", "first_passage", "final_sdr",
                                       "settled_at", "t_peak", "wall_s")}
    out["ref"]["t_coll"] = t_collapse(ref)
    out["hist"] = {"t": ref["hist_t"], "d": [[round(v, 6) for v in row] for row in ref["hist_d"]],
                   "u": [[round(v, 4) for v in row] for row in ref["hist_u"]], "ke": ref["hist_ke"]}
    releases: dict[str, dict] = {}

    def release(t_r: float) -> dict:
        t_r = round(round(t_r / rec.dt) * rec.dt, 6)
        key = f"{t_r:.4f}"
        if key not in releases:
            res = fr.run(rec.acc, rec.dt, scale, t_r + H_ZIC, t_release=t_r, dt_anal=dta, state_at=(t_r,))
            snap = next(iter(res["snapshots"].values()), None)
            releases[key] = {
                "t_r": t_r, "status": res["status"], "committed": is_collapse(res),
                "t_coll": t_collapse(res), "max_sdr": res["max_sdr"], "peak_sdr": res["peak_sdr"],
                "final_sdr": res["final_sdr"], "settled_at": res["settled_at"], "t_end": res["t_end"],
                "wall_s": res["wall_s"], "snapshot": snap,
            }
        return releases[key]

    t_coll = out["ref"]["t_coll"]
    if level in ("hi", "x15"):
        if t_coll is None:
            out["status"] = "reference_did_not_collapse"
            out["releases"] = releases
            return out
        # Backward exponential search for a recoverable release
        committed_times = []
        t_a = None
        for delta in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0):
            t_r = t_coll - delta
            if t_r <= rec.dt:
                break
            r = release(t_r)
            if r["committed"]:
                committed_times.append(r["t_r"])
            else:
                t_a = r["t_r"]
                break
        if t_a is None:
            out["status"] = "no_recoverable_release_found"
            out["releases"] = releases
            return out
        t_b = min(committed_times) if committed_times else None
        if t_b is None:
            # the release closest to collapse is already recoverable
            out["status"] = "recoverable_at_collapse_minus_0.25"
            out["releases"] = releases
            return out
        # Bisection on [t_a, t_b]
        while t_b - t_a > max(BISECT_RES, 1.5 * rec.dt):
            mid = 0.5 * (t_a + t_b)
            r = release(mid)
            if r["committed"]:
                t_b = r["t_r"]
            else:
                t_a = r["t_r"]
            if abs(r["t_r"] - mid) > 0.5 * rec.dt + 1e-9:
                break
        # Monotonicity checks between t_b and collapse
        checks = []
        ts = sorted(set(committed_times + [t_b]))
        for a, b in zip(ts[:-1], ts[1:]):
            checks.append(0.5 * (a + b))
        if t_coll - t_b > 0.5:
            checks.append(0.5 * (t_b + t_coll))
        for t_r in checks:
            release(t_r)
        # Additional recoverable states before t* for the released-state dataset
        for off in (0.5, 1.0, 2.0, 4.0):
            if t_a - off > rec.dt:
                release(t_a - off)
        # The initial bracket is not sufficient when a pulse temporarily
        # rescues a state after an earlier committed release.  Add the
        # collapse state as a committed anchor, inspect every sampled
        # recoverable->committed transition, and refine the latest one.
        legacy_t_a, legacy_t_b = t_a, t_b
        if t_coll > rec.dt:
            release(t_coll)
        sampled = sorted(releases.values(), key=lambda r: r["t_r"])
        transitions = [(a, b) for a, b in zip(sampled[:-1], sampled[1:])
                       if not a["committed"] and b["committed"]]
        if transitions:
            latest_a, latest_b = max(transitions, key=lambda ab: ab[0]["t_r"])
            while latest_b["t_r"] - latest_a["t_r"] > max(BISECT_RES, 1.5 * rec.dt):
                mid = 0.5 * (latest_a["t_r"] + latest_b["t_r"])
                r = release(mid)
                if r["committed"]:
                    latest_b = r
                else:
                    latest_a = r
            t_a, t_b = latest_a["t_r"], latest_b["t_r"]
        non_mono = [r for r in releases.values() if r["t_r"] > t_b and not r["committed"]]
        out.update({"status": "ok", "t_star": t_b, "t_a": t_a,
                    "legacy_t_star": legacy_t_b, "legacy_t_a": legacy_t_a,
                    "search_repaired": abs(t_b - legacy_t_b) > 0.5 * rec.dt,
                    "n_transition_brackets": len(transitions),
                    "non_monotonic": len(non_mono) > 0,
                    "non_monotonic_times": [r["t_r"] for r in non_mono]})
    else:  # 'lo': most dangerous states of a surviving trajectory
        hist_t = np.array(ref["hist_t"])
        dmax = np.abs(np.array(ref["hist_d"])).max(axis=1)
        ke = np.array(ref["hist_ke"])

        def peaks(arr):
            idx = [i for i in range(1, len(arr) - 1)
                   if arr[i] >= arr[i - 1] and arr[i] >= arr[i + 1] and hist_t[i] <= rec.duration]
            return sorted(idx, key=lambda i: -arr[i])

        cand: list[float] = []
        for arr, n_take in ((dmax, 4), (ke, 3)):  # 4 largest drift peaks, 3 largest kinetic-energy peaks
            taken = 0
            for i in peaks(arr):
                if all(abs(hist_t[i] - c) > 0.3 for c in cand):
                    cand.append(float(hist_t[i]))
                    taken += 1
                if taken >= n_take:
                    break
        for t_r in cand:
            release(t_r)
        out["status"] = "ok"
        out["rescued"] = [r["t_r"] for r in releases.values() if r["committed"]]
    out["releases"] = releases
    return out


# --------------------------------------------------------------------- rest release
def task_rest(model: str, rid: str, level: str) -> dict:
    """Static versus kinetic commitment.

    The released configuration (displacements and all hysteretic variables) is
    kept but every nodal velocity and acceleration is set to zero before the
    free response.  At t_a (last recoverable) and t* (first committed) the
    outcome is compared with the moving release.  If the frame at rest at t*
    recovers, its commitment was kinetic and the static point of no return
    t*_s (first state from which even a frame at rest collapses) is located on
    (t*, t_c) by bisection to 0.02 s.
    """
    from driver import Frame
    from records import load_all

    z = json.loads((RUNS / "zic" / model / f"{rid}__{level}.json").read_text())
    out = {"model": model, "rid": rid, "level": level, "status": z.get("status")}
    if z.get("status") != "ok":
        return out
    rec = load_all()[rid]
    scale = z["sa"] / json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())["sa_unscaled"]
    fr = Frame(model)
    dta = _dt_anal(rec)
    rests: dict[str, dict] = {}
    if level == "lo":
        # surviving histories: classify every committed (i.e. rescued) state
        for r in z["releases"].values():
            if r["committed"]:
                t_r = round(r["t_r"], 6)
                res = fr.run(rec.acc, rec.dt, scale, t_r + H_ZIC, t_release=t_r, dt_anal=dta, rest_at_release=True)
                rests[f"{t_r:.4f}"] = {"t_r": t_r, "status": res["status"], "committed": is_collapse(res),
                                       "t_coll": t_collapse(res), "max_sdr": res["max_sdr"],
                                       "final_sdr": res["final_sdr"], "wall_s": res["wall_s"]}
        out["rests"] = rests
        return out

    def rest(t_r: float) -> dict:
        t_r = round(round(t_r / rec.dt) * rec.dt, 6)
        key = f"{t_r:.4f}"
        if key not in rests:
            res = fr.run(rec.acc, rec.dt, scale, t_r + H_ZIC, t_release=t_r, dt_anal=dta, rest_at_release=True)
            rests[key] = {"t_r": t_r, "status": res["status"], "committed": is_collapse(res),
                          "t_coll": t_collapse(res), "max_sdr": res["max_sdr"], "final_sdr": res["final_sdr"],
                          "settled_at": res["settled_at"], "wall_s": res["wall_s"]}
        return rests[key]

    ts, ta, tc = z["t_star"], z["t_a"], z["ref"]["t_coll"]
    r_a, r_s = rest(ta), rest(ts)
    out.update({"t_star": ts, "t_a": ta, "t_c": tc, "rest_a_committed": r_a["committed"],
                "rest_star_committed": r_s["committed"]})
    if not r_s["committed"] and level == "x15":
        # at 1.5 S_hi only the type of commitment at t* is classified (no search for t*_s)
        out["t_star_static"] = None
    elif not r_s["committed"]:
        lo, hi = ts, None
        for delta in (0.25, 0.5, 1.0, 2.0, 4.0):
            t_try = min(ts + delta, tc - 0.02)
            if t_try <= lo:
                break
            r = rest(t_try)
            if r["committed"]:
                hi = r["t_r"]
                break
            lo = r["t_r"]
        if hi is not None:
            while hi - lo > max(BISECT_RES, 1.5 * rec.dt):
                r = rest(0.5 * (lo + hi))
                if r["committed"]:
                    hi = r["t_r"]
                else:
                    lo = r["t_r"]
        out["t_star_static"] = hi
        out["t_static_last_recoverable"] = lo
    else:
        out["t_star_static"] = ts if not r_a["committed"] else None
    # committed states before t_a were rescued by the remaining input: classify them
    for r in z["releases"].values():
        if r["committed"] and r["t_r"] < ta:
            rest(r["t_r"])
    out["rests"] = rests
    out["status"] = "ok"
    return out


# --------------------------------------------------------- truncation at t95
def task_t95(model: str, rid: str, level: str) -> dict:
    """Collapse intensity when the record is truncated at t95 (end of the
    5-95 % significant duration) and followed by free vibration.

    The predicate is the zero-input continuation of the state at t95.  The
    search starts at the full-record collapse intensity S_hi and moves up by
    factors of 1.1, then bisects to the IDA tolerance.  If the truncated record
    already collapses at S_hi, S_hi is reported (no downward search).
    """
    from driver import Frame
    from records import load_all

    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    rec = load_all()[rid]
    out = {"model": model, "rid": rid, "S_hi": ida["S_hi"], "t95": ida["t95"]}
    if ida["S_hi"] is None:
        out["status"] = "censored"
        return out
    fr = Frame(model)
    dta = _dt_anal(rec)
    t95 = round(round(ida["t95"] / rec.dt) * rec.dt, 6)
    cache: dict[float, dict] = {}

    def coll(sa: float) -> bool:
        key = round(sa, 6)
        if key not in cache:
            res = fr.run(rec.acc, rec.dt, sa / ida["sa_unscaled"], t95 + H_ZIC, t_release=t95, dt_anal=dta)
            cache[key] = {"sa": key, "status": res["status"], "collapse": is_collapse(res),
                          "t_coll": t_collapse(res), "max_sdr": res["max_sdr"], "wall_s": res["wall_s"]}
        return cache[key]["collapse"]

    lo, hi = None, None
    sa = ida["S_hi"]
    if coll(sa):
        hi = sa
    else:
        lo = sa
        while sa < SA_MAX:
            sa *= 1.1
            if coll(sa):
                hi = sa
                break
            lo = sa
        if hi is not None:
            while hi / lo - 1.0 > TOL:
                mid = math.sqrt(lo * hi)
                if coll(mid):
                    hi = mid
                else:
                    lo = mid
    out.update({"status": "ok", "S_hi_t95": hi, "S_lo_t95": lo, "runs": [cache[k] for k in sorted(cache)]})
    return out


# ------------------------------------------------------------------------ pushover
def task_push(model: str, rid: str, level: str) -> dict:
    """Residual-capacity pushovers from released states of a ZIC task."""
    from driver import Frame
    from records import load_all

    z = json.loads((RUNS / "zic" / model / f"{rid}__{level}.json").read_text())
    rec = load_all()[rid]
    fr = Frame(model)
    out = {"model": model, "rid": rid, "level": level, "states": {}}
    if not z.get("releases"):
        return out
    scale = z["sa"] / json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())["sa_unscaled"]
    rel = sorted(z["releases"].values(), key=lambda r: r["t_r"])
    if level in ("hi", "x15") and z.get("t_star") is not None:
        ts, ta = z["t_star"], z["t_a"]
        rec_states = [r for r in rel if r["t_r"] <= ta and not r["committed"]]
        com_states = [r for r in rel if r["t_r"] >= ts and r["committed"]]
        # recoverable: t_a and the two earliest extra states; committed: t*, the
        # middle and the latest committed release (spread towards collapse)
        pick = rec_states[-1:] + rec_states[:2]
        if com_states:
            pick += [com_states[0], com_states[len(com_states) // 2], com_states[-1]]
        seen, uniq = set(), []
        for r in pick:
            if r["t_r"] not in seen:
                seen.add(r["t_r"])
                uniq.append(r)
        pick = uniq
    else:
        # surviving histories: the three largest instantaneous-drift states
        pick = sorted(rel, key=lambda r: -max(abs(v) for v in r["snapshot"]["sdr"]))[:3]
    for r in pick:
        t_r = r["t_r"]
        snap = r.get("snapshot")
        if snap is None:
            out["states"][f"{t_r:.4f}"] = {"error": "no_snapshot"}
            continue
        vroof = snap["floor_vel"][-1]
        sgn_v = 1.0 if vroof >= 0 else -1.0
        curves = {}
        for name, sgn in (("fwd", sgn_v), ("bwd", -sgn_v)):
            # re-create the released state, then push statically from it
            res = fr.run(rec.acc, rec.dt, scale, t_r, dt_anal=_dt_anal(rec), settle_check=False)
            if res["status"] != "ok":
                curves[name] = None
                continue
            po = fr.pushover(direction=sgn, max_roof_drift=0.15, droof=0.05, from_current=True)
            curves[name] = po["curve"][::2] if len(po["curve"]) > 400 else po["curve"]
        out["states"][f"{t_r:.4f}"] = {"t_r": t_r, "committed": r["committed"], "snapshot": snap,
                                       "v_roof": vroof, "u_roof": snap["roof_disp"], "curves": curves}
    return out


# --------------------------------------------------------------------------- runner
def _worker(args):
    phase, model, rid, level = args
    sub = RUNS / phase / model
    sub.mkdir(parents=True, exist_ok=True)
    name = rid if phase in ("ida", "t95") else f"{rid}__{level}"
    path = sub / f"{name}.json"
    if path.exists():
        return name, "skip", 0.0
    import openseespy.opensees as ops

    log = RUNS / "logs"
    log.mkdir(parents=True, exist_ok=True)
    ops.logFile(str(log / f"ops_{os.getpid()}.log"), "-noEcho")
    t0 = time.time()
    try:
        if phase == "ida":
            res = task_ida(model, rid)
        elif phase == "zic":
            res = task_zic(model, rid, level)
        elif phase == "rest":
            res = task_rest(model, rid, level)
        elif phase == "t95":
            res = task_t95(model, rid, level)
        else:
            res = task_push(model, rid, level)
        res["task_wall_s"] = round(time.time() - t0, 1)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(path)
        return name, "ok", time.time() - t0
    except Exception:
        (sub / f"{name}.err").write_text(traceback.format_exc(), encoding="utf-8")
        return name, "error", time.time() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["ida", "zic", "push", "rest", "t95"])
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--sets", nargs="+", default=["FF", "NF"])
    ap.add_argument("--levels", nargs="+", default=["hi", "lo"])
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rids", nargs="+")
    ap.add_argument("--reverse", action="store_true", help="shortest records first")
    args = ap.parse_args()
    from records import load_all

    recs = load_all()
    rids = args.rids or [r for r in recs if recs[r].rset in args.sets]
    # longest records first for better load balance
    rids.sort(key=lambda r: -recs[r].duration)
    if args.reverse:
        rids.reverse()
    if args.limit:
        rids = rids[: args.limit]
    tasks = []
    for m in args.models:
        for rid in rids:
            if args.phase in ("ida", "t95"):
                tasks.append((args.phase, m, rid, None))
            else:
                for lv in args.levels:
                    tasks.append((args.phase, m, rid, lv))
    print(f"{len(tasks)} tasks, {args.workers} workers", flush=True)
    t0 = time.time()
    done = 0
    with mp.get_context("spawn").Pool(args.workers, maxtasksperchild=4) as pool:
        for name, st, wall in pool.imap_unordered(_worker, tasks, chunksize=1):
            done += 1
            print(f"[{done}/{len(tasks)} {time.time() - t0:7.0f}s] {name} {st} {wall:.0f}s", flush=True)


if __name__ == "__main__":
    main()
