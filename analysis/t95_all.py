"""Truncated-record (t95) collapse capacity vs full record, all frames.

Source: RUNS/t95/<model>/<rid>.json (R52 frozen task_t95: zero-input continuation of
the state at t95 for H=30 s; search starts at the full-record S_hi, factors 1.1 upward,
geometric bisection to 3 %; if the truncated record already collapses at S_hi the
capacity is reported as S_hi, i.e. no downward search -> ratio 1 is an upper bound).

Statistics (per frame, ALL/FF/NF):
  * frac_changed   : records whose truncated capacity exceeds S_hi (truncation hides collapse)
  * ratio          : per-record S_c,t95 / S_c,full (upper bracket of the truncated search)
  * median_shift   : median_t95 / median_full of the record-set collapse capacities
  * beta_full/t95  : log-standard deviation of the capacities (lognormal fragility dispersion)
  * Pc_t95_at_med  : truncated-analysis collapse probability at the full-record median
                     (empirical; 0.5 by construction for the full record)
Uncertainty: event-cluster bootstrap (the two horizontal components of an event are
resampled together), 10 000 replicates.
Writes analysis/t95_all.json and analysis/t95_all_records.csv.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
N_BOOT = 10000
TOL = 1e-9


def event_id(rid: str) -> str:
    """Same convention as holdout_bootstrap.event_id (pairs the two components)."""
    return rid.split("_")[0] if rid.startswith("NF") else rid[:-1]


def load(model: str) -> list[dict]:
    rows = []
    for p in sorted((RUNS / "t95" / model).glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("status") != "ok" or d.get("S_hi") is None:
            continue
        s_t = d["S_hi_t95"]
        rows.append({"model": model, "rid": d["rid"], "event": event_id(d["rid"]),
                     "set": d["rid"][:2], "S_full": d["S_hi"], "S_t95": s_t,
                     "S_lo_t95": d["S_lo_t95"], "censored": s_t is None,
                     "changed": s_t is None or s_t > d["S_hi"] * (1 + TOL),
                     "ratio": None if s_t is None else s_t / d["S_hi"],
                     "n_runs": len(d["runs"])})
    return rows


def stats(rows: list[dict]) -> dict:
    full = np.array([r["S_full"] for r in rows])
    t95 = np.array([np.inf if r["censored"] else r["S_t95"] for r in rows])
    rat = t95 / full
    lf, lt = np.log(full), np.log(t95)
    med_f = float(np.exp(np.median(lf)))
    out = {
        "n_records": len(rows), "n_events": len({r["event"] for r in rows}),
        "n_censored": int(np.sum(~np.isfinite(t95))),
        "frac_changed": float(np.mean(rat > 1 + TOL)),
        "ratio_median": float(np.median(rat)),
        "ratio_p75": float(np.percentile(rat, 75)),
        "ratio_p90": float(np.percentile(rat, 90)),
        "ratio_median_changed": float(np.median(rat[rat > 1 + TOL])) if np.any(rat > 1 + TOL) else None,
        "median_full": med_f, "median_t95": float(np.exp(np.median(lt))),
        "median_shift": float(np.exp(np.median(lt) - np.median(lf))),
        "beta_full": float(np.std(lf, ddof=1)),
        "beta_t95": float(np.std(lt[np.isfinite(lt)], ddof=1)) if np.sum(np.isfinite(lt)) > 2 else None,
        "Pc_t95_at_med_full": float(np.mean(t95 <= med_f)),
        "Pc_full_at_med_full": float(np.mean(full <= med_f)),
    }
    return out


def boot(rows: list[dict], rng) -> dict:
    ev = defaultdict(list)
    for r in rows:
        ev[r["event"]].append(r)
    keys = sorted(ev)
    reps = defaultdict(list)
    for _ in range(N_BOOT):
        pick = rng.integers(0, len(keys), len(keys))
        rr = [r for k in pick for r in ev[keys[k]]]
        s = stats(rr)
        for q in ("frac_changed", "ratio_median", "median_shift", "Pc_t95_at_med_full"):
            reps[q].append(s[q])
    return {f"{q}_ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
            for q, v in reps.items()}


def main():
    rng = np.random.default_rng(9595)
    res, allrows = {}, []
    for m in MODELS:
        rows = load(m)
        if not rows:
            continue
        allrows += rows
        res[m] = {"complete": len(rows) >= 100}
        for st in ("ALL", "FF", "NF"):
            sub = [r for r in rows if st == "ALL" or r["set"] == st]
            if len(sub) < 4:
                continue
            s = stats(sub)
            s.update(boot(sub, rng))
            res[m][st] = s
        a = res[m]["ALL"]
        print(f"{m:8s} n={a['n_records']:3d} ev={a['n_events']:2d} changed={a['frac_changed']:.2f} "
              f"{a['frac_changed_ci95']} ratio_med={a['ratio_median']:.3f} p90={a['ratio_p90']:.2f} "
              f"shift={a['median_shift']:.3f} {np.round(a['median_shift_ci95'], 3).tolist()} "
              f"Pc_t95@med={a['Pc_t95_at_med_full']:.2f} {a['Pc_t95_at_med_full_ci95']} "
              f"beta {a['beta_full']:.2f}->{a['beta_t95']:.2f}")
    res["_protocol"] = {"source": "RUNS/t95 (R52 task_t95, frozen code_copy)", "unit": "event_id",
                        "n_boot": N_BOOT, "no_downward_search": True,
                        "ratio_definition": "upper bracket S_hi_t95 / full-record S_hi"}
    (OUT / "t95_all.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    with (OUT / "t95_all_records.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
        w.writeheader()
        w.writerows(allrows)


if __name__ == "__main__":
    main()
