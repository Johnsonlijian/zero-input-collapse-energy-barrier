"""Diagnostic: Table-2 coefficients split by push direction (sign of the collapse-direction drift).
The composite frames are not mirror-symmetric (intact_symmetry.json), so the undamped coefficient
c0_c = E0_crit / W_rem^c and the exit types are compared between forward (+) and backward (-)
transition states.  Event-cluster bootstrap of the median ratio fwd/bwd.  Writes
analysis/direction_split.json."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from build_tables import event_id

A = Path(__file__).resolve().parent
RUNS = Path(r"E:\n0r53\runs")
TALL = {"SMF12B", "SMF12CG", "SMF20B", "SMF20CG"}
rng = np.random.default_rng(5)

lt = pd.read_csv(A / "law_table.csv", low_memory=False)
for c in ("E_u", "E_d", "Wc_m1", "t_r"):
    lt[c] = pd.to_numeric(lt[c], errors="coerce")
out = {}
for m in ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]:
    df = lt[(lt["model"] == m) & lt["tag"].isin(["ta", "tstar"]) & ((lt["set"] == "FF") if m in TALL else True)
            & lt["label_r52"].isin(["committed", "recoverable"])]
    rows = []
    for _, r in df.iterrows():
        stem = f"{r['rid']}__{r['level']}__{r['t_r']:.4f}"
        p = None
        for ph in ("push_deep", "push"):
            for q in (RUNS / ph / m / f"{stem}__push.json", RUNS / ph / m / f"{stem}.json"):
                if q.exists():
                    p = q
                    break
            if p:
                break
        if p is None:
            continue
        j = json.loads(p.read_text())
        sgn = j.get("sgn") or (j.get("W_fwd") or {}).get("sgn")
        if sgn is None:
            continue
        rows.append({"sgn": float(sgn), "c0": r["E_u"] / r["Wc_m1"] if r["Wc_m1"] > 0 else np.nan,
                     "c": r["E_d"] / r["Wc_m1"] if r["Wc_m1"] > 0 else np.nan,
                     "lim": r["lim_m1"], "event": event_id(r["rid"])})
    if not rows:
        continue
    res = {}
    for s, nm in ((1.0, "fwd"), (-1.0, "bwd")):
        sub = [x for x in rows if x["sgn"] == s]
        c0 = np.array([x["c0"] for x in sub if np.isfinite(x["c0"])])
        res[nm] = {"n": len(sub), "c0_median": float(np.median(c0)) if len(c0) else None,
                   "c_median": float(np.nanmedian([x["c"] for x in sub])) if sub else None,
                   "lim": {k: sum(x["lim"] == k for x in sub) for k in ("drift", "edge", "stall", "trunc", "downhill")}}
    f_ = [x for x in rows if x["sgn"] > 0 and np.isfinite(x["c0"])]
    b_ = [x for x in rows if x["sgn"] < 0 and np.isfinite(x["c0"])]
    if len(f_) >= 5 and len(b_) >= 5:
        ev = defaultdict(list)
        for i, x in enumerate(f_ + b_):
            ev[x["event"]].append(i)
        allr = f_ + b_
        ek = sorted(ev)
        reps = []
        for _ in range(5000):
            idx = np.concatenate([ev[ek[k]] for k in rng.integers(0, len(ek), len(ek))])
            fs = [allr[i]["c0"] for i in idx if allr[i]["sgn"] > 0]
            bs = [allr[i]["c0"] for i in idx if allr[i]["sgn"] < 0]
            if fs and bs:
                reps.append(np.median(fs) / np.median(bs))
        res["c0_fwd_over_bwd"] = [float(np.median([x["c0"] for x in f_]) / np.median([x["c0"] for x in b_])),
                                  float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))]
    out[m] = res
    print(m, json.dumps(res))
(A / "direction_split.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
