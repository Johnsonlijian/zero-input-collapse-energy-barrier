"""Audit: barrier pushes whose 'edge' exit occurs at a vanishing roof-drift increment.
A push that returns lambda <= 0 within a few steps of its start, at a roof-drift increment
below DR_TINY, by a jump of lambda (not a descending branch), reports a near-zero barrier
that is a solver branch jump rather than a loss of resistance.  Scans every barrier curve in
the run tree and writes analysis/early_edge_audit.json."""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "early_edge_audit.json"
DIRS = ["push", "push_deep", "push_shape", "push_story", "aftershock_ms", "aftershock_a6", "a6_barrier_deep",
        "barrier_intact", "barrier_intact_deep", "barrier_intact_deep_d"]
DR_TINY = 1e-3          # roof-drift travel before the exit


def barriers(obj, path=()):
    if isinstance(obj, dict):
        if "curve" in obj and "reached_edge" in obj:
            yield path, obj
        for k, v in obj.items():
            if k != "curve":
                yield from barriers(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                yield from barriers(v, path + (i,))


res = {}
for dname in DIRS:
    base = RUNS / dname
    if not base.exists():
        continue
    files = list(base.glob("*.json")) + list(base.glob("*/*.json"))
    cnt, flagged = Counter(), defaultdict(list)
    for p in files:
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        model = p.parent.name if p.parent != base else p.stem
        for kp, b in barriers(d):
            cnt[model] += 1
            if not b.get("reached_edge"):
                continue
            c = np.asarray(b["curve"], float)
            if len(c) < 2:
                continue
            travel = abs(c[-1, 0] - c[0, 0])
            if travel >= DR_TINY:
                continue
            lam = c[:, 1]
            jump = float(lam[-2] - lam[-1]) / max(abs(float(np.max(lam))), 1e-12)
            flagged[model].append({"file": p.name, "key": "/".join(map(str, kp)), "n_pts": int(len(c)),
                                   "travel": float(travel), "lam_peak": float(np.max(lam)),
                                   "lam_last": float(lam[-1]), "rel_jump": jump,
                                   "W_max": float(np.max(c[:, 3]))})
    res[dname] = {m: {"n_barriers": cnt[m], "n_flagged": len(flagged[m]), "flagged": flagged[m]} for m in sorted(cnt)}
    print(dname, {m: f"{len(flagged[m])}/{cnt[m]}" for m in sorted(cnt)}, flush=True)
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print("wrote", OUT)
