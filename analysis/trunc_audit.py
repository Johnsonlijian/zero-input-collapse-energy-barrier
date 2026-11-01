"""Audit of 'trunc' barrier exits: does the push stall with the load factor already at ~zero
(effectively at the resistance edge) or with substantial resistance left (genuinely truncated)?
For every push curve classified 'trunc' by build_tables.w_collapse report final lambda / peak
lambda and the final roof drift.  Sources: RUNS/push (law barriers; transition states),
RUNS/push_deep (deep law barriers), RUNS/a6_barrier_deep (settled states), RUNS/barrier_intact_deep.
Writes analysis/trunc_audit.json."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from build_tables import w_collapse

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "trunc_audit.json"
NEAR = 0.01          # final lambda <= 1 % of the curve's peak lambda counts as 'at the edge'


def classify(push):
    W, lim = w_collapse(push)
    if lim != "trunc":
        return lim, None, None
    c = np.asarray(push.get("curve") or [], float)
    if c.size == 0:
        return "trunc", None, None
    lam = c[:, 1]
    fr = float(lam[-1] / max(lam.max(), 1e-12))
    return ("trunc_at_edge" if fr <= NEAR else "trunc_open"), fr, float(abs(c[-1, 0]))


def tally(pushes):
    n = defaultdict(int)
    fr_open = []
    for p in pushes:
        k, fr, dr = classify(p)
        n[k] += 1
        if k == "trunc_open":
            fr_open.append((fr, dr))
    return dict(n), fr_open


out = {}
for model in ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]:
    res = {}
    for phase in ("push", "push_deep"):
        d = RUNS / phase / model
        if not d.exists():
            continue
        ps = []
        for p in d.glob("*.json"):
            try:
                j = json.loads(p.read_text())
            except Exception:
                continue
            ps.append(j)
        n, fo = tally(ps)
        res[phase] = {"counts": n, "open_final_lam_frac_median": float(np.median([f for f, _ in fo])) if fo else None,
                      "open_final_droof_median": float(np.median([r for _, r in fo])) if fo else None}
    d = RUNS / "a6_barrier_deep" / model
    if d.exists():
        for k in ("W_fwd", "W_bwd"):
            ps = []
            for p in d.glob("*.json"):
                j = json.loads(p.read_text())
                if j.get(k):
                    ps.append(j[k])
            n, fo = tally(ps)
            res[f"a6_deep_{k}"] = {"counts": n}
    ip = RUNS / "barrier_intact_deep" / f"{model}.json"
    if ip.exists():
        j = json.loads(ip.read_text())
        res["intact_deep"] = {k: classify(j[k]) for k in ("W_fwd", "W_bwd")}
    out[model] = res
    print(model, json.dumps(res))
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
