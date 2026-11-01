"""Supplement figure: first-mode share of release KE vs height, with c0_c.

Two evidence lines for the tall-frame path divergence:
  - KE1/KE median on transition states (modal decomposition)
  - c0_c median (undamped escape energy / first-mode barrier)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MK = json.loads(Path(r"E:\n0r53\analysis\modal_ke.json").read_text())
SUM = json.loads(Path(r"E:\n0r53\analysis\summary_by_frame.json").read_text())
WORD = {"SMF2B": "2B", "SMF2CG": "2CG", "SMF4B": "4B", "SMF4CG": "4CG",
        "SMF8B": "8B", "SMF8CG": "8CG", "SMF12B": "12B", "SMF12CG": "12CG",
        "SMF20B": "20B", "SMF20CG": "20CG"}
ORDER = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
         "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
H = {"SMF2B": 2, "SMF2CG": 2, "SMF4B": 4, "SMF4CG": 4, "SMF8B": 8, "SMF8CG": 8,
     "SMF12B": 12, "SMF12CG": 12, "SMF20B": 20, "SMF20CG": 20}
SETKEY = {"SMF12B": "FF", "SMF12CG": "FF", "SMF20B": "FF", "SMF20CG": "FF"}


def c0c(model):
    skey = SETKEY.get(model, "ALL")
    v = SUM.get(f"{model}|{skey}", {})
    c = v.get("c0_c")
    return c if c else (None, None, None)


fig, ax = plt.subplots(figsize=(4.6, 3.2), dpi=200)
xb, xc, yke, yc, yc_lo, yc_hi = [], [], [], [], [], []
for m in ORDER:
    t = MK[m]["transition"]
    xb.append(H[m] - 0.25); yke.append(t["ke1_med"])
    med, lo, hi = c0c(m)
    if med is not None:
        xc.append(H[m] + 0.25); yc.append(med); yc_lo.append(lo); yc_hi.append(hi)

ax.plot(xb, yke, "o", color="#8c8c8c", ms=4, label=r"$\mathrm{KE}_1/\mathrm{KE}$ (median)")
ax.plot(xb, yke, "-", color="#8c8c8c", lw=0.7, alpha=0.6)
ax.errorbar(xc, yc, yerr=[np.array(yc) - np.array(yc_lo), np.array(yc_hi) - np.array(yc)],
            fmt="s", color="#d55e00", ms=4, capsize=2, lw=0.9, label=r"$c_f^0$ median [IQR]")
ax.axhline(1.0, color="k", lw=0.6)
ax.axhspan(0.90, 1.05, color="#1f77b4", alpha=0.08)
OFF = {"SMF2B": (-6, 6), "SMF2CG": (8, -10), "SMF4B": (-8, 6), "SMF4CG": (8, -11),
       "SMF8B": (-2, 7), "SMF8CG": (8, -11), "SMF12B": (-2, 7), "SMF12CG": (8, -11),
       "SMF20B": (-9, 2), "SMF20CG": (9, -10)}
for m in ORDER:
    t = MK[m]["transition"]
    ax.annotate(WORD[m], (H[m] - 0.25, t["ke1_med"]), textcoords="offset points",
                xytext=OFF[m], ha="center", fontsize=6)
ax.set_xlabel("storeys"); ax.set_ylabel("share / ratio")
ax.set_xscale("log"); ax.set_xticks([2, 4, 8, 12, 20]); ax.set_xticklabels([2, 4, 8, 12, 20])
ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
ax.set_xlim(1.6, 26); ax.set_ylim(0.55, 1.15)
ax.legend(fontsize=6, loc="lower left", frameon=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(rf"E:\n0r53\analysis\fig_s_modal.{ext}")
print("wrote fig_s_modal.pdf/.png")
