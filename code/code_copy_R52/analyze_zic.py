"""Point of no return, static/kinetic commitment and the released-state dataset.

Reads RUNS/zic/<model>/<rid>__<level>.json, RUNS/rest/<model>/<rid>__<level>.json
and the IDA results; writes results/zic_records_<model>.csv,
results/zic_states_<model>.csv and results/zic_summary.json.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from records import load_all  # noqa: E402

RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
OUT = HERE.parent / "results"
RNG = np.random.default_rng(5252)


def boot_ci(x, stat=np.median, n=10000):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], dtype=float)
    if len(x) < 2:
        return [None, None]
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    vals = np.sort(stat(x[idx], axis=1))
    return [float(vals[int(0.025 * n)]), float(vals[int(0.975 * n) - 1])]


def arias_cum(acc_g: np.ndarray, dt: float) -> np.ndarray:
    a2 = np.asarray(acc_g, dtype=float) ** 2
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (a2[1:] + a2[:-1]) * dt)])
    return cum / cum[-1]


def state_features(snap: dict, props: dict) -> dict:
    sdr = np.array(snap["sdr"])
    peak = np.array(snap["peak_sdr_so_far"])
    v = np.array(snap["floor_vel"])
    H = props["height_in"]
    u_roof = snap["roof_disp"]
    v_roof = v[-1]
    # drift velocity of the critical story (first story 180 in, upper stories 156 in in both archetypes)
    k = int(np.argmax(np.abs(sdr)))
    hk = 180.0 if k == 0 else 156.0
    dv = (v[k] - (v[k - 1] if k > 0 else 0.0)) / hk
    return {
        "inst_max_sdr": float(np.abs(sdr).max()),
        "inst_story": k + 1,
        "peak_sdr_so_far": float(peak.max()),
        "roof_drift": float(abs(u_roof) / H),
        "v_roof_in_s": float(v_roof),
        "outward": bool(u_roof * v_roof > 0),
        "story_outward": bool(sdr[k] * dv > 0),
        "story_drift_rate": float(np.sign(sdr[k]) * dv),  # positive: critical story moving outwards (1/s)
        "ke_kipin": float(snap["ke"]),
        "ke_norm": float(snap["ke"] / props["work_to_peak_kipin"]),
    }


def outcome(r: dict) -> str:
    """Outcome category of one continuation (zero-input or rest release)."""
    if r["status"] == "collapse":
        return "committed_collapse"
    if r["status"] == "nonconv":
        return "committed_nonconv" if r["max_sdr"] >= 0.10 else "censored_nonconv"
    return "recoverable_settled" if r.get("settled_at") is not None else "censored_horizon"


def analyze(model: str) -> dict:
    recs = load_all()
    outcomes: dict[str, int] = {}
    props = json.loads((OUT / "model_checks.json").read_text())[model]
    ida = {p.stem: json.loads(p.read_text()) for p in (RUNS / "ida" / model).glob("*.json")}
    rows, states = [], []
    for p in sorted((RUNS / "zic" / model).glob("*.json")):
        z = json.loads(p.read_text())
        rid, level = z["rid"], z["level"]
        rec = recs[rid]
        d = ida.get(rid, {})
        t95, t5 = d.get("t95"), d.get("t5")
        cum = arias_cum(rec.acc, rec.dt)
        tgrid = np.arange(len(rec.acc)) * rec.dt
        restp = RUNS / "rest" / model / f"{rid}__{level}.json"
        rest = json.loads(restp.read_text()) if restp.exists() else None
        for key, r in z.get("releases", {}).items():
            oc = outcome(r)
            outcomes[oc] = outcomes.get(oc, 0) + 1
            if r.get("snapshot") is None or (r["status"] == "nonconv" and not r["committed"]):
                continue
            f = state_features(r["snapshot"], props)
            states.append({"model": model, "rid": rid, "set": rid[:2], "level": level, "t_r": r["t_r"],
                           "committed": int(r["committed"]), "zic_status": r["status"],
                           "zic_t_coll": r["t_coll"], "zic_max_sdr": r["max_sdr"],
                           "zic_resid_max": float(np.max(np.abs(r["final_sdr"]))),
                           "t_rel_star": (r["t_r"] - z["t_star"]) if z.get("t_star") is not None else None,
                           **f})
        row = {"model": model, "rid": rid, "set": rid[:2], "level": level, "sa": z.get("sa"),
               "status": z.get("status"), "duration": rec.duration, "t5": t5, "t95": t95,
               "ref_status": z.get("ref", {}).get("status"), "ref_t_coll": z.get("ref", {}).get("t_coll"),
               "ref_max_sdr": z.get("ref", {}).get("max_sdr"),
               "ref_resid": float(np.max(np.abs(z["ref"]["final_sdr"]))) if z.get("ref") else None,
               "n_releases": len(z.get("releases", {})), "task_wall_s": z.get("task_wall_s"),
               "search_repaired": bool(z.get("search_repaired")),
               "legacy_t_star": z.get("legacy_t_star"), "legacy_t_a": z.get("legacy_t_a"),
               "n_transition_brackets": z.get("n_transition_brackets")}
        if level in ("hi", "x15") and z.get("status") == "ok":
            ts, ta = z["t_star"], z["t_a"]
            rel = {round(v["t_r"], 6): v for v in z["releases"].values()}
            rb, ra = rel[round(ts, 6)], rel[round(ta, 6)]
            fp = z["ref"]["first_passage"]
            fb = state_features(rb["snapshot"], props)
            fa = state_features(ra["snapshot"], props)
            rec_rel = [v for v in z["releases"].values() if not v["committed"] and v["status"] != "nonconv"]
            row.update({
                "t_star": ts, "t_a": ta, "resolution": ts - ta,
                "t10": fp["0.10"], "t05": fp["0.05"], "t15": fp["0.15"],
                "lead_10": None if fp["0.10"] is None else fp["0.10"] - ts,
                "passed10_before_star": fp["0.10"] is not None and fp["0.10"] < ts,
                "lead_c": z["ref"]["t_coll"] - ts,
                "star_inst_sdr": fb["inst_max_sdr"], "star_peak_sdr": fb["peak_sdr_so_far"],
                "star_roof_drift": fb["roof_drift"], "star_ke_kipin": fb["ke_kipin"], "star_ke_norm": fb["ke_norm"],
                "star_outward": fb["outward"], "star_story_outward": fb["story_outward"],
                "star_story_drift_rate": fb["story_drift_rate"], "a_story_drift_rate": fa["story_drift_rate"], "star_story": fb["inst_story"], "star_v_roof": fb["v_roof_in_s"],
                "a_inst_sdr": fa["inst_max_sdr"], "a_peak_sdr": fa["peak_sdr_so_far"],
                "a_zic_max_sdr": ra["max_sdr"], "a_resid_max": float(np.max(np.abs(ra["final_sdr"]))),
                "max_sdr_recoverable_continuation": max((v["max_sdr"] for v in rec_rel), default=None),
                "star_before_t95": None if t95 is None else ts < t95,
                "coll_after_end": z["ref"]["t_coll"] > rec.duration,
                "arias_remaining": float(1.0 - np.interp(ts, tgrid, cum)),
                "time_after_t95": None if t95 is None else ts - t95,
                "time_remaining_after_star": rec.duration - ts,
                "non_monotonic": bool(z.get("non_monotonic")),
                "star_zic_delay": rb["t_coll"] - ts,
                "a_zic_delay_settle": None if ra.get("settled_at") is None else ra["settled_at"] - ta,
            })
            if z.get("hist") and t95 is not None:
                ht = np.asarray(z["hist"]["t"])
                hd = np.abs(np.asarray(z["hist"]["d"])).max(axis=1)
                row["theta_at_t95"] = float(np.interp(t95, ht, hd))
            if rest is not None and rest.get("status") == "ok":
                kinetic = not rest["rest_star_committed"]
                tss = rest.get("t_star_static")
                theta_s = None
                if tss is not None and z.get("hist"):
                    ht = np.asarray(z["hist"]["t"])
                    hd = np.abs(np.asarray(z["hist"]["d"])).max(axis=1)
                    theta_s = float(np.interp(tss, ht, hd))
                row.update({
                    "rest_a_committed": rest["rest_a_committed"], "rest_star_committed": rest["rest_star_committed"],
                    "commitment_type": "kinetic" if kinetic else "static",
                    "t_star_static": tss,
                    "static_minus_star": (tss - ts) if tss is not None else None,
                    "theta_static": theta_s,
                })
        if level == "lo":
            row["rescued"] = len(z.get("rescued", []))
            rel = list(z.get("releases", {}).values())
            row["max_sdr_lo_continuations"] = max((v["max_sdr"] for v in rel), default=None)
            row["zic_exceeds_ref"] = int(sum(1 for v in rel if v["max_sdr"] > z["ref"]["max_sdr"] + 1e-4))
        rows.append(row)
    return {"rows": rows, "states": states, "outcomes": outcomes}


def summarize(rows: list[dict], states: list[dict]) -> dict:
    out = {}
    for level in ("hi", "x15"):
        lv = [r for r in rows if r["level"] == level and r.get("status") == "ok"]
        for st in ("FF", "NF", "ALL"):
            sub = [r for r in lv if st == "ALL" or r["set"] == st]
            if not sub:
                continue

            def col(k):
                return [r[k] for r in sub if r.get(k) is not None]

            s = {"n": len(sub)}
            for k in ("star_inst_sdr", "star_peak_sdr", "star_roof_drift", "lead_10", "lead_c", "arias_remaining",
                      "time_after_t95", "time_remaining_after_star", "a_resid_max", "a_zic_max_sdr",
                      "star_ke_norm", "star_zic_delay", "static_minus_star", "theta_static",
                      "max_sdr_recoverable_continuation", "star_story_drift_rate", "a_story_drift_rate"):
                v = col(k)
                if v:
                    s[k] = {"median": float(np.median(v)), "CI95": boot_ci(v), "p10": float(np.percentile(v, 10)),
                            "p90": float(np.percentile(v, 90)), "min": float(np.min(v)), "max": float(np.max(v)),
                            "n": len(v)}
            for k in ("star_before_t95", "passed10_before_star", "star_outward", "star_story_outward", "non_monotonic",
                      "search_repaired", "coll_after_end"):
                v = [bool(r[k]) for r in sub if r.get(k) is not None]
                if v:
                    s["frac_" + k] = float(np.mean(v))
                    s["n_" + k] = int(np.sum(v))
            # does commitment track the static stability limit of the damaged frame, record by record?
            pairs = [(r["star_inst_sdr"], r["theta_static"]) for r in sub if r.get("theta_static") is not None]
            if len(pairs) >= 5:
                a = np.array(pairs)
                ra = np.argsort(np.argsort(a[:, 0])).astype(float)
                rb = np.argsort(np.argsort(a[:, 1])).astype(float)
                s["spearman_star_static"] = float(np.corrcoef(ra, rb)[0, 1])
                s["pearson_star_static"] = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
                s["gap_static_minus_star_sdr"] = {"median": float(np.median(a[:, 1] - a[:, 0])),
                                                  "p10": float(np.percentile(a[:, 1] - a[:, 0], 10)),
                                                  "p90": float(np.percentile(a[:, 1] - a[:, 0], 90))}
            s["frac_star_inst_lt_10"] = float(np.mean([r["star_inst_sdr"] < 0.10 for r in sub]))
            s["frac_star_inst_lt_08"] = float(np.mean([r["star_inst_sdr"] < 0.08 for r in sub]))
            s["frac_star_inst_lt_05"] = float(np.mean([r["star_inst_sdr"] < 0.05 for r in sub]))
            types = [r["commitment_type"] for r in sub if r.get("commitment_type")]
            if types:
                s["n_rest"] = len(types)
                s["n_static"] = int(sum(t == "static" for t in types))
                s["frac_static"] = float(np.mean([t == "static" for t in types]))
                s["n_rest_a_committed"] = int(sum(bool(r.get("rest_a_committed")) for r in sub
                                                  if r.get("commitment_type")))
            out[f"{level}_{st}"] = s
        out[f"{level}_not_ok"] = [(r["rid"], r.get("status")) for r in rows
                                  if r["level"] == level and r.get("status") != "ok"]
    lo = [r for r in rows if r["level"] == "lo"]
    out["lo_records"] = len(lo)
    out["lo_rescued_records"] = int(sum(1 for r in lo if r.get("rescued", 0) > 0))
    out["lo_zic_exceeds_ref_records"] = int(sum(1 for r in lo if r.get("zic_exceeds_ref", 0) > 0))
    st_rec = [s for s in states if not s["committed"]]
    st_com = [s for s in states if s["committed"]]
    out["n_states"] = len(states)
    out["n_states_committed"] = len(st_com)
    if st_rec and st_com:
        out["recoverable_inst_sdr_max"] = float(max(s["inst_max_sdr"] for s in st_rec))
        out["recoverable_zic_max_sdr_max"] = float(max(s["zic_max_sdr"] for s in st_rec))
        out["committed_inst_sdr_min"] = float(min(s["inst_max_sdr"] for s in st_com))
        out["frac_recoverable_states_above_10"] = float(np.mean([s["inst_max_sdr"] >= 0.10 for s in st_rec]))
        out["frac_committed_states_below_10"] = float(np.mean([s["inst_max_sdr"] < 0.10 for s in st_com]))
    return out


def rest_states(model: str) -> list[dict]:
    """All rest releases with the outcome of the moving release at the same time."""
    rows = []
    for p in sorted((RUNS / "rest" / model).glob("*.json")):
        d = json.loads(p.read_text())
        zp = RUNS / "zic" / model / f"{d['rid']}__{d['level']}.json"
        if not zp.exists() or not d.get("rests"):
            continue
        rel = {round(v["t_r"], 6): v for v in json.loads(zp.read_text()).get("releases", {}).values()}
        for r in d["rests"].values():
            mv = rel.get(round(r["t_r"], 6))
            rows.append({"model": model, "rid": d["rid"], "set": d["rid"][:2], "level": d["level"], "t_r": r["t_r"],
                         "rest_committed": int(bool(r["committed"])), "rest_status": r["status"],
                         "moving_committed": None if mv is None else int(bool(mv["committed"])),
                         "t_star": d.get("t_star"), "t_a": d.get("t_a")})
    return rows


def main(models):
    OUT.mkdir(parents=True, exist_ok=True)
    allsum = {}
    for m in models:
        if not (RUNS / "zic" / m).exists():
            continue
        rs = rest_states(m)
        if rs:
            with (OUT / f"rest_states_{m}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rs[0].keys()))
                w.writeheader()
                w.writerows(rs)
        res = analyze(m)
        for name, data in (("records", res["rows"]), ("states", res["states"])):
            if data:
                keys = sorted({k for r in data for k in r})
                with (OUT / f"zic_{name}_{m}.csv").open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=keys)
                    w.writeheader()
                    w.writerows(data)
        allsum[m] = summarize(res["rows"], res["states"])
        allsum[m]["release_outcomes"] = res["outcomes"]
        allsum[m]["n_releases_total"] = int(sum(res["outcomes"].values()))
        allsum[m]["n_censored"] = int(sum(v for k, v in res["outcomes"].items() if k.startswith("censored")))
        print(m, json.dumps(allsum[m], indent=1)[:6000])
    path = OUT / "zic_summary.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(allsum)
    path.write_text(json.dumps(old, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or ["SMF4B", "SMF8B", "SMF4CG", "SMF8CG"])
