"""Time-step sensitivity: point of no return with the analysis step halved.

Compares RUNS/zic/SMF4B/<rid>__hi.json (step = min(dt_record, 0.005 s)) with
RUNS_DT/zic/SMF4B/<rid>__hi.json (half that step).  Writes
results/dt_sensitivity.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
RUNS_DT = Path(os.environ.get("N0R52_RUNS_DT", r"E:\n0r52\runs_dt"))
OUT = HERE.parent / "results"


def star(z):
    if z.get("status") != "ok":
        return None
    rel = {round(v["t_r"], 6): v for v in z["releases"].values()}
    s = rel[round(z["t_star"], 6)]["snapshot"]
    return {"t_star": z["t_star"], "theta": float(np.max(np.abs(s["sdr"]))), "t_c": z["ref"]["t_coll"]}


def main():
    rows = []
    for p in sorted((RUNS_DT / "zic" / "SMF4B").glob("*__hi.json")):
        z2 = json.loads(p.read_text())
        z1 = json.loads((RUNS / "zic" / "SMF4B" / p.name).read_text())
        a, b = star(z1), star(z2)
        rows.append({"rid": z2["rid"], "base": a, "half_step": b,
                     "ref_status_half": z2.get("ref", {}).get("status"), "status_half": z2.get("status")})
    ok = [r for r in rows if r["base"] and r["half_step"]]
    out = {"rows": rows, "n": len(rows), "n_compared": len(ok)}
    if ok:
        out["max_abs_dt_star_s"] = float(max(abs(r["base"]["t_star"] - r["half_step"]["t_star"]) for r in ok))
        out["max_abs_dtheta_pct"] = float(100 * max(abs(r["base"]["theta"] - r["half_step"]["theta"]) for r in ok))
        out["max_abs_dtc_s"] = float(max(abs(r["base"]["t_c"] - r["half_step"]["t_c"]) for r in ok))
        out["max_abs_dlead_s"] = float(max(abs((r["base"]["t_c"] - r["base"]["t_star"])
                                               - (r["half_step"]["t_c"] - r["half_step"]["t_star"])) for r in ok))
        dth = sorted((abs(r["base"]["theta"] - r["half_step"]["theta"]), r) for r in ok)
        small = [d for d, _ in dth if d < 0.002]
        out["n_dtheta_below_0p2pct"] = len(small)
        out["max_abs_dtheta_small_pct"] = float(100 * max(small)) if small else None
        worst = dth[-1][1]
        out["worst"] = {"rid": worst["rid"], "dtheta_pct": float(100 * (worst["half_step"]["theta"] - worst["base"]["theta"])),
                        "dtc_s": float(worst["half_step"]["t_c"] - worst["base"]["t_c"]),
                        "dt_star_s": float(worst["half_step"]["t_star"] - worst["base"]["t_star"])}
    (OUT / "dt_sensitivity.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
