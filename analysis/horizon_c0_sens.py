"""Sensitivity of the undamped coefficient c0 to horizon-expired probes.

Recompute each kick_undamped task's bracket treating horizon-expired
'recoverable' probes as censored (dropped), then recompute the per-state
E_u = beta^2 * KE and the frame median of c0 = E_u / Wc_m1 over the same
states that enter Table 2 (law_table rows with kick_undamped results).
Also count how many law_table rows are horizon-expired zic releases and
their tags.
"""
import json, glob, os, csv
from collections import defaultdict
import numpy as np

ROOT = r"E:\n0r53"

def _k(b, d):
    for k in d:
        if abs(float(k) - b) < 1e-9:
            return k
    raise KeyError(b)

def _is_com(p):
    return p.get("committed") is True or p.get("label") == "committed"

def _is_rec(p):
    if _is_com(p):
        return False
    return p.get("committed") is False or p.get("label") == "recoverable" or p.get("status") == "ok"

def _is_horizon(p):
    return _is_rec(p) and p.get("settled_at") is None

def mid(rec, com):
    if not rec or not com:
        return None
    hi_rec = max(rec)
    lo_com = min((c for c in com if c > hi_rec), default=None)
    return None if lo_com is None else 0.5 * (hi_rec + lo_com)

def recrit(runs):
    bs = sorted(float(b) for b in runs)
    rec = [b for b in bs if _is_rec(runs[_k(b, runs)])]
    com = [b for b in bs if _is_com(runs[_k(b, runs)])]
    hor = set(b for b in bs if _is_horizon(runs[_k(b, runs)]))
    rec_s = [b for b in rec if b not in hor]
    return mid(rec, com), mid(rec_s, com)

def main():
    # per-task recomputed brackets
    tasks = {}
    for f in glob.glob(os.path.join(ROOT, "runs", "kick_undamped", "*", "*.json")):
        m = f.replace("\\", "/").split("/runs/")[1].split("/")[1]
        try:
            j = json.load(open(f))
        except Exception:
            continue
        runs = j.get("runs") or {}
        if len(runs) < 2:
            continue
        st = j.get("state") or {}
        bc, bc2 = recrit(runs)
        tasks[(m, st.get("rid"), round(float(st.get("t_r") or -1), 4))] = (bc, bc2)

    # join with law_table: transition-classified undamped states
    rows = list(csv.DictReader(open(os.path.join(ROOT, "analysis", "law_table.csv"),
                                   newline="", encoding="utf-8-sig")))
    print("law columns:", [c for c in rows[0] if 'ke' in c.lower() or 'W' in c or 'beta' in c.lower() or 'tag' in c])
    agg = defaultdict(lambda: dict(n=0, c0=[], c0sens=[], touched=0))
    for r in rows:
        key = (r["model"], r["rid"], round(float(r["t_r"]), 4))
        if key not in tasks:
            continue
        bc, bc2 = tasks[key]
        try:
            ke = float(r["ke"]); w = float(r["Wc_m1"])
        except (TypeError, ValueError):
            continue
        if ke <= 0 or w <= 0 or bc is None:
            continue
        a = agg[r["model"]]
        a["n"] += 1
        a["c0"].append(bc * bc * ke / w)
        if bc2 is not None and abs(bc2 - bc) > 1e-12:
            a["touched"] += 1
            a["c0sens"].append(bc2 * bc2 * ke / w)
        else:
            a["c0sens"].append(bc * bc * ke / w)
    out = {}
    for m, a in sorted(agg.items()):
        if not a["c0"]:
            continue
        med0, med1 = float(np.median(a["c0"])), float(np.median(a["c0sens"]))
        out[m] = dict(n=a["n"], touched=a["touched"],
                      c0_med=med0, c0_med_censored=med1, dmed=med1 - med0)
        print(m, out[m])
    json.dump(out, open(os.path.join(ROOT, "analysis", "horizon_c0_sens.json"), "w"), indent=1)
main()
