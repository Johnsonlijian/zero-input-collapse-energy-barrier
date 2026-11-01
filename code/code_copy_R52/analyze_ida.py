"""Collapse capacities, post-input collapses and truncation bias from the IDA runs.

Writes results/ida_summary.json and results/ida_records.csv.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
OUT = HERE.parent / "results"
SM1, SMS = 0.9, 1.5  # FEMA P695 Dmax MCE spectral values (g); design site of the archetypes
RNG = np.random.default_rng(52)


def boot_ci(x, stat=np.median, n=10000, alpha=0.05):
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return [None, None]
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    vals = np.sort(stat(x[idx], axis=1))
    return [float(vals[int(alpha / 2 * n)]), float(vals[int((1 - alpha / 2) * n) - 1])]


def s_mt(T: float) -> float:
    ts = SM1 / SMS
    return SMS if T <= ts else SM1 / T


def load(model: str) -> list[dict]:
    rows = []
    for p in sorted((RUNS / "ida" / model).glob("*.json")):
        rows.append(json.loads(p.read_text()))
    return rows


def record_row(d: dict) -> dict:
    hi = d["S_hi"]
    runs = {round(r["sa"], 6): r for r in d["runs"]}
    r_hi = runs.get(round(hi, 6)) if hi is not None else None
    r_lo = runs.get(round(d["S_lo"], 6)) if d.get("S_lo") is not None else None
    out = {
        "model": d["model"], "rid": d["rid"], "set": d["rid"][:2], "T1": d["T1"], "duration": d["duration"],
        "dt": d["dt"], "t5": d["t5"], "t95": d["t95"], "S_lo": d["S_lo"], "S_hi": hi,
        "sa_unscaled": d["sa_unscaled"], "scale_hi": None if hi is None else hi / d["sa_unscaled"],
        "S_hi_trunc": d.get("S_hi_trunc"), "n_runs": len(d["runs"]), "task_wall_s": d.get("task_wall_s"),
    }
    if r_hi is not None:
        tc = r_hi["t_coll"]
        out.update({
            "t_coll_hi": tc,
            "coll_after_record": tc is not None and tc > d["duration"] + 1e-9,
            "coll_after_t95": tc is not None and tc > d["t95"],
            "t_coll_minus_end": None if tc is None else tc - d["duration"],
            "t10_hi": r_hi["first_passage"]["0.10"],
        })
    if r_lo is not None:
        out.update({"max_sdr_lo": r_lo["max_sdr"], "resid_lo": float(np.max(np.abs(r_lo["final_sdr"])))})
    # Collapse intensity if a 10 % drift limit were used: lowest analysed
    # intensity at which the peak drift reached 10 % (the runs bracket S_c, so
    # this is resolved to the bisection tolerance only near S_c)
    srt = sorted(d["runs"], key=lambda r: r["sa"])
    s10 = next((r["sa"] for r in srt if r["collapse"] or r["max_sdr"] >= 0.10), None)
    out["S_c10"] = s10
    out["S_c10_ratio"] = None if (s10 is None or hi is None) else s10 / hi
    out["n_noncoll_runs_above_10"] = sum(1 for r in d["runs"] if not r["collapse"] and r["max_sdr"] >= 0.10)
    # every collapsed run: post-record collapse?
    coll = [r for r in d["runs"] if r["collapse"]]
    out["n_coll_runs"] = len(coll)
    out["n_coll_after_record"] = sum(1 for r in coll if r["t_coll"] is not None and r["t_coll"] > d["duration"] + 1e-9)
    out["n_nonconv"] = sum(1 for r in d["runs"] if r["status"] == "nonconv")
    return out


def summarize(model: str) -> dict | None:
    data = load(model)
    if not data:
        return None
    rows = [record_row(d) for d in data]
    res = {"model": model, "n_records": len(rows), "T1": rows[0]["T1"], "S_MT": s_mt(rows[0]["T1"])}
    for st in ("FF", "NF", "ALL"):
        sub = [r for r in rows if st == "ALL" or r["set"] == st]
        sc = np.array([r["S_hi"] for r in sub if r["S_hi"] is not None])
        cens = sum(1 for r in sub if r["S_hi"] is None)
        if len(sc) == 0:
            continue
        lnsc = np.log(sc)
        med = float(np.exp(np.median(lnsc)))
        beta = float(np.std(lnsc, ddof=1))
        trunc = np.array([r["S_hi_trunc"] / r["S_hi"] for r in sub
                          if r["S_hi"] is not None and r.get("S_hi_trunc") is not None])
        sct = np.array([r["S_hi_trunc"] for r in sub if r.get("S_hi_trunc") is not None])
        after = [r for r in sub if r.get("coll_after_record")]
        after95 = [r for r in sub if r.get("coll_after_t95")]
        res[st] = {
            "n": int(len(sc)), "censored": cens,
            "median_Sc": med, "median_Sc_CI95": boot_ci(sc), "beta_RTR": beta,
            "CMR": med / res["S_MT"],
            "median_Sc_trunc": float(np.exp(np.median(np.log(sct)))) if len(sct) else None,
            "ratio_trunc_records_gt1": int(np.sum(trunc > 1 + 1e-9)),
            "ratio_trunc_max": float(trunc.max()) if len(trunc) else None,
            "ratio_trunc_values_gt1": sorted(float(v) for v in trunc[trunc > 1 + 1e-9]),
            "n_coll_after_record_at_Sc": len(after),
            "frac_coll_after_record_at_Sc": len(after) / len(sc),
            "frac_coll_after_record_at_Sc_CI95": boot_ci([1.0 if r.get("coll_after_record") else 0.0 for r in sub
                                                         if r["S_hi"] is not None], stat=np.mean),
            "n_coll_after_t95_at_Sc": len(after95),
            "frac_coll_after_t95_at_Sc": len(after95) / len(sc),
            "post_record_delays_s": sorted(r["t_coll_minus_end"] for r in after),
            "all_coll_runs": int(sum(r["n_coll_runs"] for r in sub)),
            "all_coll_runs_after_record": int(sum(r["n_coll_after_record"] for r in sub)),
            "nonconv_runs": int(sum(r["n_nonconv"] for r in sub)),
            "Sc10_ratio_median": float(np.median([r["S_c10_ratio"] for r in sub if r.get("S_c10_ratio") is not None])),
            "Sc10_ratio_min": float(np.min([r["S_c10_ratio"] for r in sub if r.get("S_c10_ratio") is not None])),
            "frac_Sc10_lower": float(np.mean([r["S_c10_ratio"] < 1 - 1e-9 for r in sub if r.get("S_c10_ratio") is not None])),
            "median_Sc10": float(np.exp(np.median(np.log([r["S_c10"] for r in sub if r.get("S_c10") is not None])))),
            "noncoll_runs_above_10": int(sum(r["n_noncoll_runs_above_10"] for r in sub)),
            "max_sdr_lo_median": float(np.median([r["max_sdr_lo"] for r in sub if r.get("max_sdr_lo") is not None])),
            "resid_lo_median": float(np.median([r["resid_lo"] for r in sub if r.get("resid_lo") is not None])),
        }
    res["_rows"] = rows
    return res


def main(models):
    OUT.mkdir(parents=True, exist_ok=True)
    allrows = []
    summ = {}
    for m in models:
        s = summarize(m)
        if s is None:
            continue
        allrows += s.pop("_rows")
        summ[m] = s
        print(json.dumps({m: {k: v for k, v in s.items() if k in ("n_records", "T1", "S_MT")}}))
        for st in ("FF", "NF", "ALL"):
            if st in s:
                x = s[st]
                print(f"  {st}: n={x['n']} cens={x['censored']} median Sc={x['median_Sc']:.3f} g "
                      f"CI={['%.3f' % v for v in x['median_Sc_CI95']]} beta={x['beta_RTR']:.3f} CMR={x['CMR']:.2f} | "
                      f"coll after record at Sc: {x['n_coll_after_record_at_Sc']} ({x['frac_coll_after_record_at_Sc']:.1%}); "
                      f"after t95: {x['n_coll_after_t95_at_Sc']} ({x['frac_coll_after_t95_at_Sc']:.1%}); "
                      f"trunc>Sc: {x['ratio_trunc_records_gt1']} (max ratio {x['ratio_trunc_max']}) nonconv={x['nonconv_runs']}")
    (OUT / "ida_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    if allrows:
        keys = sorted({k for r in allrows for k in r})
        with (OUT / "ida_records.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in allrows:
                w.writerow(r)


if __name__ == "__main__":
    main(sys.argv[1:] or ["SMF4B", "SMF8B", "SMF4CG", "SMF8CG"])
