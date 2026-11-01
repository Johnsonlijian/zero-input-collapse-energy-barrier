"""Diagnostic: residual-capacity indicator comparison restricted to resolved settled barriers.
Reads aftershock_analysis.json rows (ms family). Prints, per frame and subset:
n, R/w median, zero-param log RMSE, LOEO fitted log RMSE (w, res), partial rank correlations."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aftershock_analysis import pred_block, partial_spearman, spearman  # noqa: E402

d = json.loads((Path(__file__).resolve().parent / "aftershock_analysis.json").read_text())
rng = np.random.default_rng(7)
RES = ("drift", "edge", "stall")


def show(tag, rows):
    unc = [r for r in rows if r["status"] == "ok" and r["w"] > 0]
    if len(unc) < 12:
        print(f"  {tag:<28} n={len(unc)} (too few)")
        return
    lr = np.log([r["R"] / r["w"] for r in unc])
    pb = pred_block(unc, ("w", "res"))
    pc = partial_spearman(rows, rng)
    rw = spearman([r["R"] for r in rows], [r["w"] for r in rows])
    rr = -spearman([r["R"] for r in rows], [r["res"] for r in rows])
    print(f"  {tag:<28} n={len(unc):4d} R/w={np.exp(np.median(lr)):.3f} "
          f"rmse0={pb['w_zero_param']:.3f} w_cv={pb['w_fitted_cv']:.3f} res_cv={pb['res_fitted_cv']:.3f} "
          f"rho_w={rw:.3f} rho_res={rr:.3f} "
          f"w|res={pc['w_given_res']:.2f}[{pc['w_given_res_ci95'][0]:.2f},{pc['w_given_res_ci95'][1]:.2f}] "
          f"res|w={pc['res_given_w']:.2f}[{pc['res_given_w_ci95'][0]:.2f},{pc['res_given_w_ci95'][1]:.2f}]")


for m, v in d.items():
    ms = [r for r in v["rows"] if r["family"] == "aftershock_ms"]
    print(m, "ms", len(ms), dict(Counter(r["lim"] for r in ms)))
    show("all", ms)
    show("resolved", [r for r in ms if r["lim"] in RES])
    show("resolved, own-dir intact", [r for r in ms if r["lim"] in RES and r["intact_src"] != "mirror"])
    show("resolved, mirror intact", [r for r in ms if r["lim"] in RES and r["intact_src"] == "mirror"])
    show("trunc only", [r for r in ms if r["lim"] == "trunc"])
    unc = sorted([r for r in ms if r["status"] == "ok" and r["w"] > 0], key=lambda r: abs(np.log(r["R"] / r["w"])))
    print("   worst |log R/w|:", [(r["rid"], r["tag"], round(r["R"], 3), round(r["w"], 4), r["lim"], round(r["res"], 4))
                                   for r in unc[-6:]])
