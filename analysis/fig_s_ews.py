"""Supplement figure: energy ratio vs generic early-warning statistics.

Per-frame AUC for the commitment label: energy ratio, running-maximum drift,
and the best of {variance, detrended variance, lag-1 autocorrelation} of the
peak-storey-drift window before release (analysis/ews_control.json).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EW = json.loads(Path(r"E:\n0r53\analysis\ews_control.json").read_text())
WORD = {"SMF2B": "2B", "SMF2CG": "2CG", "SMF4B": "4B", "SMF4CG": "4CG",
        "SMF8B": "8B", "SMF8CG": "8CG", "SMF12B": "12B", "SMF12CG": "12CG",
        "SMF20B": "20B", "SMF20CG": "20CG"}
ORDER = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
         "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
EWSM = ["std", "sdet", "ar1"]

labels, en, dr, best = [], [], [], []
for m in ORDER:
    v = EW["per_model"][m]
    labels.append(WORD[m])
    en.append(v["energy_auc"])
    dr.append(v["drift_auc"])
    best.append(max(v[f"{k}_auc"] for k in EWSM))

x = np.arange(len(labels))
w = 0.27
fig, ax = plt.subplots(figsize=(5.6, 3.0), dpi=200)
ax.bar(x - w, en, w, color="#1b4965", label="energy ratio $E/c_{\\rm dev}$")
ax.bar(x, dr, w, color="#8d99ae", label="running-max drift")
ax.bar(x + w, best, w, color="#e07a2f",
       label="best of $\\sigma^2$, detrended $\\sigma^2$, AR(1)")
ax.axhline(0.5, color="0.4", lw=0.8, ls=":")
ax.text(len(labels) - 0.5, 0.512, "chance", fontsize=6.5, color="0.4",
        ha="right", va="bottom")
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=7)
ax.set_ylabel("AUC vs commitment label", fontsize=8)
ax.set_ylim(0.3, 1.02)
ax.tick_params(axis="y", labelsize=7)
ax.legend(fontsize=6.5, frameon=False, loc="lower left", ncol=1)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.tight_layout()
out = Path(__file__).resolve().parent / "fig_s_ews.pdf"
fig.savefig(out)
print("wrote", out)
