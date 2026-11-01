"""Pre-registered control H6(i): tangent-stiffness sign (Bernal) versus the zero-input label.
Rule: committed iff the tangent stiffness at the released state is indefinite (lam_min < 0,
frozen campaign53 task_ktan).  Scored on the classified states of the harness (law_table rows
with a finite collapse-surface barrier; 12/20-storey far-field), next to the energy rule E
(KE >= c_dev W_rem) on the same states; paired event-cluster bootstrap of the difference.
Writes analysis/ktan_control.json."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from build_tables import C_DEV, event_id

A = Path(__file__).resolve().parent
RUNS = Path(r"E:\n0r53\runs")
TALL = {"SMF12B", "SMF12CG", "SMF20B", "SMF20CG"}
N_BOOT = 10000

lt = pd.read_csv(A / "law_table.csv")
for c in ("ke", "Wc_m1", "t_r"):
    lt[c] = pd.to_numeric(lt[c], errors="coerce")
lt = lt[np.isfinite(lt["Wc_m1"]) & lt["label_r52"].isin(["committed", "recoverable"])].copy()
rng = np.random.default_rng(31)
out = {}
for m in ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]:
    df = lt[(lt["model"] == m) & ((lt["set"] == "FF") if m in TALL else True)]
    rows = []
    for _, r in df.iterrows():
        p = RUNS / "ktan" / m / f"{r['rid']}__{r['level']}__{r['t_r']:.4f}.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text())
        if j.get("lam_min") is None:
            continue
        rows.append({"y": r["label_r52"] == "committed", "unst": bool(j["ktan_unstable"]),
                     "E": bool(r["ke"] >= C_DEV * r["Wc_m1"]), "tag": r["tag"], "event": event_id(r["rid"])})
    if len(rows) < 10:
        continue
    y = np.array([r["y"] for r in rows]); u = np.array([r["unst"] for r in rows]); e = np.array([r["E"] for r in rows])
    tr = np.array([r["tag"] in ("ta", "tstar") for r in rows])
    ev = defaultdict(list)
    for i, r in enumerate(rows):
        ev[r["event"]].append(i)
    ek = sorted(ev)
    ce, cu = (e == y).astype(float), (u == y).astype(float)
    reps = []
    for _ in range(N_BOOT):
        ii = np.concatenate([ev[ek[k]] for k in rng.integers(0, len(ek), len(ek))])
        reps.append(ce[ii].mean() - cu[ii].mean())
    res = {"n": int(len(rows)), "n_events": len(ek), "share_indefinite": float(u.mean()),
           "share_indefinite_committed": float(u[y].mean()) if y.any() else None,
           "share_indefinite_recoverable": float(u[~y].mean()) if (~y).any() else None,
           "acc_ktan": float(cu.mean()), "acc_E": float(ce.mean()),
           "diff_E_minus_ktan": [float(ce.mean() - cu.mean()), float(np.percentile(reps, 2.5)),
                                 float(np.percentile(reps, 97.5))],
           "n_transition": int(tr.sum()),
           "acc_ktan_transition": float(cu[tr].mean()) if tr.any() else None,
           "share_indefinite_transition": float(u[tr].mean()) if tr.any() else None}
    out[m] = res
    print(m, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()})
(A / "ktan_control.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
