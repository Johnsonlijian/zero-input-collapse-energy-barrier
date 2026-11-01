"""Audit of edge exits reached by a branch jump: at the step where the load factor first returns
to <= 0 (the edge), the drop of lambda in that single step exceeds the peak lambda reached
before it, i.e. the solver jumped to another equilibrium branch instead of following a
descending branch.  Counts per run directory and model; writes analysis/branch_jump_audit.json."""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "branch_jump_audit.json"
DIRS = ["push", "push_deep", "push_shape", "push_story", "aftershock_ms", "aftershock_a6", "a6_barrier_deep",
        "barrier_intact", "barrier_intact_deep", "barrier_intact_deep_d"]


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


def edge_jump(c):
    lam = c[:, 1]
    pos = np.where(lam > 0)[0]
    if not len(pos):
        return None
    i1 = int(pos[0])
    neg = np.where(lam[i1:] <= 0)[0]
    if not len(neg):
        return None
    i = i1 + int(neg[0])
    if i == 0:
        return None
    return float(lam[i - 1] - lam[i]) / max(float(np.max(lam[:i])), 1e-12), i, float(np.max(c[:i, 3]))


res = {}
for dname in DIRS:
    base = RUNS / dname
    if not base.exists():
        continue
    cnt, edges, fl = Counter(), Counter(), defaultdict(list)
    for p in list(base.glob("*.json")) + list(base.glob("*/*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        model = p.parent.name if p.parent != base else p.stem
        for kp, b in barriers(d):
            cnt[model] += 1
            c = np.asarray(b["curve"], float)
            if c.ndim != 2 or len(c) < 2:
                continue
            ej = edge_jump(c)
            if ej is None:
                continue
            edges[model] += 1
            if ej[0] > 1.0:
                fl[model].append({"file": p.name, "key": "/".join(map(str, kp)), "rel_drop": ej[0],
                                  "edge_index": ej[1], "n_pts": int(len(c)), "W_before": ej[2]})
    res[dname] = {m: {"n": cnt[m], "n_edge_return": edges[m], "n_jump": len(fl[m]), "jumps": fl[m]} for m in sorted(cnt)}
    print(dname, {m: f"{len(fl[m])}/{edges[m]}/{cnt[m]}" for m in sorted(cnt) if fl[m]}, flush=True)
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print("wrote", OUT)
