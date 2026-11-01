"""Check that RUNS/push_deep curves coincide with RUNS/push over their common range
(same state, same solver, larger max_droof), and tabulate how the exit classification and
W_c change when the deep curve replaces the standard one (build_tables.w_collapse)."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

from build_tables import w_collapse

RUNS = Path(r"E:\n0r53\runs")
RES = ("drift", "edge", "stall")
out = {}
both_all = []
for m in ["SMF4CG", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]:
    dd = RUNS / "push_deep" / m
    if not dd.exists():
        continue
    maxdiff, n, trans, dW, both = 0.0, 0, Counter(), [], []
    for p in dd.glob("*.json"):
        q = RUNS / "push" / m / p.name
        if not q.exists():
            continue
        a, b = json.loads(q.read_text()), json.loads(p.read_text())
        ca, cb = np.asarray(a.get("curve") or [], float), np.asarray(b.get("curve") or [], float)
        if ca.size and cb.size:
            k = min(len(ca), len(cb)) - 1
            if k > 0:
                maxdiff = max(maxdiff, float(np.max(np.abs(ca[:k] - cb[:k]))))
        Wa, la = w_collapse(a)
        Wb, lb = w_collapse(b)
        trans[(la, lb)] += 1
        if Wa and Wb and Wa > 0:
            dW.append(Wb / Wa)
            if la in RES and lb in RES:
                both.append(Wb / Wa)
        n += 1
    dW = np.array(dW)
    bb = np.array(both)
    both_all += both
    out[m] = {"n": n, "both_resolved_n": int(len(bb)),
              "both_resolved_median": float(np.median(bb)) if len(bb) else None,
              "both_resolved_max_abs_dev": float(np.max(np.abs(bb - 1))) if len(bb) else None,
              "transitions": {f"{a}->{b}": c for (a, b), c in trans.items()}}
    print(f"{m}: n={n} max|curve diff| on common rows={maxdiff:.3g}  W_deep/W_std median={np.median(dW):.4f} "
          f"p90={np.percentile(dW, 90):.3f} max={dW.max():.3f}  | both resolved n={len(bb)} "
          f"median={np.median(bb) if len(bb) else float('nan'):.4f} max|dev|={np.max(np.abs(bb - 1)) if len(bb) else float('nan'):.3f}")
    print("   exit std->deep:", dict(trans))
ba = np.array(both_all)
out["_all"] = {"both_resolved_n": int(len(ba)), "median": float(np.median(ba)), "max_abs_dev": float(np.max(np.abs(ba - 1)))}
(Path(__file__).resolve().parent / "check_push_deep.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("all both-resolved:", out["_all"])
