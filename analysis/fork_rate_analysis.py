"""Reproducibility of the Table-2 transition-state barriers under repeated runs.
The mode-1 load pattern comes from an Arpack eigen solve with a random start vector (perturbation
~1e-16); on composite-frame pushes that pass the gravity-connection strength cliff this can select a
different post-peak branch.  Input: logs/fork_rate.csv (canonical push and two fresh re-runs per state,
W and exit type by build_tables.w_collapse).  Output: analysis/fork_rate.json with, per model and
push direction, the share of states whose exit type changes or whose W changes by more than 1 %, and
the undamped coefficient median E0_crit/W recomputed with each re-run."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

A = Path(__file__).resolve().parent
fr = pd.read_csv(Path(r"E:\n0r53\logs\fork_rate.csv"))
lt = pd.read_csv(A / "law_table.csv", low_memory=False)
lt["E_u"] = pd.to_numeric(lt["E_u"], errors="coerce")
lt["key"] = lt["model"] + "|" + lt["rid"] + "|" + lt["level"].astype(str) + "|" + lt["t_r"].map(lambda x: f"{float(x):.4f}")
fr["key"] = fr["model"] + "|" + fr["rid"] + "|" + fr["level"].astype(str) + "|" + fr["t_r"].map(lambda x: f"{float(x):.4f}")
fr = fr.merge(lt[["key", "E_u"]].drop_duplicates("key"), on="key", how="left")


def changed(a_w, a_l, b_w, b_l):
    return (a_l != b_l) | (np.abs(b_w - a_w) > 0.01 * np.maximum(np.abs(a_w), 1e-9))


out = {}
for m, g in fr.groupby("model"):
    res = {"n": int(len(g))}
    c1 = changed(g["W_canon"], g["lim_canon"], g["W_r1"], g["lim_r1"])
    c2 = changed(g["W_canon"], g["lim_canon"], g["W_r2"], g["lim_r2"])
    c12 = changed(g["W_r1"], g["lim_r1"], g["W_r2"], g["lim_r2"])
    any_ = c1 | c2 | c12
    res["share_changed_any"] = float(any_.mean())
    for s, nm in ((1.0, "fwd"), (-1.0, "bwd")):
        k = g["sgn"] == s
        res[f"n_{nm}"] = int(k.sum())
        res[f"share_changed_{nm}"] = float(any_[k].mean()) if k.any() else None
    res["exit_change_examples"] = (g.loc[g["lim_canon"] != g["lim_r1"], ["rid", "level", "t_r", "lim_canon", "lim_r1"]]
                                   .head(5).astype(str).values.tolist())
    ok = g["E_u"].notna()
    meds = {}
    for col in ("W_canon", "W_r1", "W_r2"):
        k = ok & (g[col] > 0)
        meds[col] = float(np.median(g.loc[k, "E_u"] / g.loc[k, col])) if k.any() else None
    res["c0_median"] = meds
    vals = [v for v in meds.values() if v is not None]
    res["c0_median_max_shift"] = float(max(vals) - min(vals)) if vals else None
    out[m] = res
    print(m, json.dumps({k: v for k, v in res.items() if k != "exit_change_examples"}))
out["_summary"] = {"max_c0_shift": max(v["c0_median_max_shift"] for k, v in out.items() if not k.startswith("_")
                                       and v["c0_median_max_shift"] is not None)}
(A / "fork_rate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(out["_summary"])
