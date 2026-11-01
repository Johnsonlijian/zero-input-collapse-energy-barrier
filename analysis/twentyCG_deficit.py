"""Conditioned diagnostic of the 20CG sub-band escape-energy coefficient.

Splits the SMF20CG transition states by first-mode push exit class
(lim_m1: edge / stall / trunc) and convergence, plus the deterministic-rerun
work spread (fork_det.json) and the direction split (direction_split.json),
to bound what the observed deficit can and cannot be attributed to.

Outputs analysis/twentyCG_deficit.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

LAW = Path(r"E:\n0r53\analysis\law_table.csv")
OUT = Path(r"E:\n0r53\analysis\twentyCG_deficit.json")


def main():
    df = pd.read_csv(LAW)
    g = df[(df.model == "SMF20CG") & df.tag.isin(["ta", "tstar"])].copy()
    g["c0"] = g.E_u / g.W_m1

    out = {"n": int(len(g)), "c0_median": float(g.c0.median()), "by_exit": {}}
    for cls in ("edge", "stall", "trunc"):
        s = g[g.lim_m1 == cls]
        out["by_exit"][cls] = {"n": int(len(s)),
                               "c0_med": float(s.c0.median())}
    s = g[g.conv_m1 == True]
    out["converged"] = {"n": int(len(s)), "c0_med": float(s.c0.median())}

    fd = json.load(open(r"E:\n0r53\analysis\fork_det.json"))
    pm = fd["per_model"]["SMF20CG"]
    out["rerun_W_reldev_median"] = pm["rel_dev_canon_median"]
    out["rerun_W_reldev_max"] = pm["rel_dev_canon_max"]

    ds = json.load(open(r"E:\n0r53\analysis\direction_split.json"))["SMF20CG"]
    out["dir_c0_fwd"] = ds["fwd"]["c0_median"]
    out["dir_c0_bwd"] = ds["bwd"]["c0_median"]
    out["dir_ratio_ci"] = ds["c0_fwd_over_bwd"]

    mk = json.load(open(r"E:\n0r53\analysis\modal_ke.json"))
    out["ke1_transition"] = mk["SMF20CG"]["transition"]["ke1_med"]
    out["ke1_transition_20B"] = mk["SMF20B"]["transition"]["ke1_med"]

    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
