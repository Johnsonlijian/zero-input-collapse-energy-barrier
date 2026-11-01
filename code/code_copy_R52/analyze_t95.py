"""Collapse intensities of records truncated at t95 (task 't95').

Writes results/t95_records_<model>.csv and results/t95_summary.json.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
OUT = HERE.parent / "results"
RNG = np.random.default_rng(95)


def boot_ci(x, stat=np.median, n=10000):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return [None, None]
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    v = np.sort(stat(x[idx], axis=1))
    return [float(v[int(0.025 * n)]), float(v[int(0.975 * n) - 1])]


def main(models):
    summ = {}
    for m in models:
        rows = []
        for p in sorted((RUNS / "t95" / m).glob("*.json")):
            d = json.loads(p.read_text())
            if d.get("status") != "ok":
                continue
            rows.append({"model": m, "rid": d["rid"], "set": d["rid"][:2], "S_hi": d["S_hi"],
                         "S_hi_t95": d["S_hi_t95"], "S_lo_t95": d["S_lo_t95"],
                         "ratio": None if d["S_hi_t95"] is None else d["S_hi_t95"] / d["S_hi"],
                         "censored": d["S_hi_t95"] is None, "n_runs": len(d["runs"])})
        if not rows:
            continue
        with (OUT / f"t95_records_{m}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        s = {}
        for st in ("FF", "NF", "ALL"):
            sub = [r for r in rows if st == "ALL" or r["set"] == st]
            rat = np.array([r["ratio"] for r in sub if r["ratio"] is not None])
            full = np.array([r["S_hi"] for r in sub if r["ratio"] is not None])
            t95v = np.array([r["S_hi_t95"] for r in sub if r["ratio"] is not None])
            if len(rat) == 0:
                continue
            ch = rat[rat > 1.0 + 1e-9]
            # paired bootstrap (records resampled) of the shift of the record-set median
            idx = RNG.integers(0, len(rat), size=(10000, len(rat)))
            shifts = np.sort(np.exp(np.median(np.log(t95v[idx]), axis=1) - np.median(np.log(full[idx]), axis=1)))
            s[st] = {"n": len(sub), "censored": int(sum(r["censored"] for r in sub)),
                     "frac_unchanged": float(np.mean(rat <= 1.0 + 1e-9)),
                     "ratio_median_changed": float(np.median(ch)) if len(ch) else None,
                     "median_shift_CI95": [float(shifts[250]), float(shifts[9749])],
                     "ratio_median": float(np.median(rat)), "ratio_CI95": boot_ci(rat),
                     "ratio_p90": float(np.percentile(rat, 90)), "ratio_max": float(rat.max()),
                     "median_Sc_full": float(np.exp(np.median(np.log(full)))),
                     "median_Sc_t95": float(np.exp(np.median(np.log(t95v)))),
                     "median_shift": float(np.exp(np.median(np.log(t95v))) / np.exp(np.median(np.log(full))))}
        summ[m] = s
        print(m, json.dumps(s, indent=1))
    path = OUT / "t95_summary.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(summ)
    path.write_text(json.dumps(old, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or ["SMF4B", "SMF8B"])
