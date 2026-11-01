"""Residual static capacity of released states and its relation to commitment.

For every released state with pushover curves (task 'push') this computes, in
the outward direction (sign of the roof displacement):
  R0      residual lateral resistance at the released position, as base shear
          normalised by W (negative: the damaged frame cannot hold its position
          under gravity),
  margin  additional roof drift ratio to zero lateral resistance,
  Wb      static energy barrier: maximum external work needed to push the frame
          outward from the released position (kip-in; 0 if R0 <= 0),
and compares Wb with the kinetic energy at release.
Writes results/push_states_<model>.csv.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
OUT = HERE.parent / "results"


def outward_metrics(curve: list, sgn_out: float, W: float) -> dict:
    c = np.asarray(curve, dtype=float)
    if c.size == 0:
        return {"R0": None, "margin": None, "Wb": None, "Rmax": None}
    lam = c[:, 1] * sgn_out  # resistance in the outward direction (kip)
    work = c[:, 3]           # external work of the lateral pattern (kip-in), path-accumulated
    roof = c[:, 0]
    R0 = lam[0] / W
    neg = np.where(lam <= 0.0)[0]
    margin = abs(roof[neg[0]] - roof[0]) if len(neg) else None
    # barrier = largest accumulated work before the resistance vanishes
    upto = neg[0] + 1 if len(neg) else len(work)
    Wb = max(0.0, float(np.max(work[:upto]))) if upto > 0 else 0.0
    if lam[0] <= 0.0:
        Wb = 0.0
    return {"R0": float(R0), "margin": None if margin is None else float(margin), "Wb": float(Wb),
            "Rmax": float(np.max(lam[:upto]) / W), "reached_zero": bool(len(neg))}


def main(models):
    mc = json.loads((OUT / "model_checks.json").read_text())
    for m in models:
        rows = []
        W = mc[m]["W_mass_kip"]
        for p in sorted((RUNS / "push" / m).glob("*.json")):
            d = json.loads(p.read_text())
            for key, s in d["states"].items():
                if "error" in s:
                    continue
                snap = s["snapshot"]
                u, v = s["u_roof"], s["v_roof"]
                sgn_out = 1.0 if u >= 0 else -1.0
                fwd_is_out = (1.0 if v >= 0 else -1.0) == sgn_out
                cur_out = s["curves"]["fwd" if fwd_is_out else "bwd"]
                cur_in = s["curves"]["bwd" if fwd_is_out else "fwd"]
                if cur_out is None:
                    continue
                mo = outward_metrics(cur_out, sgn_out, W)
                ke = snap["ke"]
                rows.append({
                    "model": m, "rid": d["rid"], "set": d["rid"][:2], "level": d["level"], "t_r": s["t_r"],
                    "committed": int(s["committed"]), "inst_max_sdr": float(np.max(np.abs(snap["sdr"]))),
                    "peak_sdr_so_far": float(np.max(snap["peak_sdr_so_far"])),
                    "roof_drift": abs(u) / mc[m]["height_in"], "outward_velocity": bool(fwd_is_out),
                    "ke": ke, **mo,
                    "ke_over_Wb": (ke / mo["Wb"]) if mo["Wb"] not in (None, 0.0) else (np.inf if ke > 0 else 0.0),
                    "static_unstable": bool(mo["R0"] is not None and mo["R0"] <= 0.0),
                })
        if rows:
            OUT.mkdir(parents=True, exist_ok=True)
            keys = list(rows[0].keys())
            with (OUT / f"push_states_{m}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(rows)
            com = [r for r in rows if r["committed"]]
            rec = [r for r in rows if not r["committed"]]
            print(m, "states", len(rows), "committed", len(com))
            for name, grp in (("committed", com), ("recoverable", rec)):
                if not grp:
                    continue
                su = np.mean([r["static_unstable"] for r in grp])
                r0 = np.median([r["R0"] for r in grp])
                print(f"  {name:12s} static-unstable frac={su:.2f} median R0={r0:+.4f} "
                      f"median inst drift={np.median([r['inst_max_sdr'] for r in grp]):.4f}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["SMF4B", "SMF8B"])
