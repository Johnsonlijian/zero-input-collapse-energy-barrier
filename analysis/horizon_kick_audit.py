"""Bracket-level impact of horizon-expired 'recoverable' kick probes.

For each kick task, a probe that reached the 30-s horizon without settling
was labeled recoverable.  In the bisection that label can raise lo and
inflate beta_crit.  Recompute each task's bracket treating horizon-expired
probes as censored (dropped): beta_crit_new = midpoint of the last
recoverable-settled probe and the first committed probe.  Report per-model
n_tasks affected and the resulting median shift of E and c0.
"""
import json, glob, os, csv
from collections import defaultdict
import numpy as np

ROOT = r"E:\n0r53"

def recrit(runs):
    """runs: {beta_str: probe}.  Return (beta_crit_reported_style,
    beta_crit_censored, n_horizon_probes, bracket_touched)."""
    bs = sorted(float(b) for b in runs)
    rec = [b for b in bs if _is_rec(runs[_k(b, runs)])]
    com = [b for b in bs if _is_com(runs[_k(b, runs)])]
    hor = [b for b in bs if _is_horizon(runs[_k(b, runs)])]
    rec_s = [b for b in rec if b not in hor]
    def mid(rec_, com_):
        if not rec_ or not com_:
            return None
        return 0.5 * (max(rec_) + min(c for c in com_ if c > max(rec_))) if any(c > max(rec_) for c in com_) else None
    bc  = mid(rec, com)
    bc2 = mid(rec_s, com)
    touched = bool(hor) and bc is not None and bc != bc2
    return bc, bc2, len(hor), touched

def _k(b, d):
    for k in d:
        if abs(float(k) - b) < 1e-9:
            return k
    raise KeyError(b)

def _probe_status(p):
    return p.get("status"), p.get("committed"), p.get("settled_at")

def _is_rec(p):
    st, c, _ = _probe_status(p)
    if c is not None:
        return c is False and st == "ok"
    return p.get("label") == "recoverable" or st == "ok"

def _is_com(p):
    st, c, _ = _probe_status(p)
    return c is True or p.get("label") == "committed"

def _is_horizon(p):
    st, c, s = _probe_status(p)
    rec = _is_rec(p) and not _is_com(p)
    return rec and s is None

def main():
    out = {}
    for fam in ("kick", "kick_undamped"):
        rows = []
        for f in glob.glob(os.path.join(ROOT, "runs", fam, "*", "*.json")):
            m = f.replace("\\","/").split("/runs/")[1].split("/")[1]
            try:
                j = json.load(open(f))
            except Exception:
                continue
            runs = j.get("runs") or {}
            if len(runs) < 2:
                continue
            bc, bc2, nh, touched = recrit(runs)
            rows.append(dict(model=m, bc=bc, bc2=bc2, n_hor=nh, touched=touched,
                             beta_crit=j.get("beta_crit")))
        agg = defaultdict(lambda: dict(n=0, n_hor=0, touched=0, dE=[]))
        for r in rows:
            a = agg[r["model"]]
            a["n"] += 1
            a["n_hor"] += 1 if r["n_hor"] else 0
            if r["touched"]:
                a["touched"] += 1
                if r["bc"] and r["bc2"]:
                    a["dE"].append((r["bc2"]**2 - r["bc"]**2) / r["bc"]**2)
        out[fam] = {m: dict(n=a["n"], tasks_with_horizon=a["n_hor"],
                            brackets_touched=a["touched"],
                            median_dE_rel=(float(np.median(a["dE"])) if a["dE"] else None),
                            max_dE_rel=(float(max(a["dE"])) if a["dE"] else None))
                    for m, a in sorted(agg.items())}
    json.dump(out, open(os.path.join(ROOT,"analysis","horizon_kick_audit.json"),"w"), indent=1)
    for fam, d in out.items():
        print(fam)
        for m, v in d.items():
            print(" ", m, v)
main()
