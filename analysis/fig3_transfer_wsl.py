"""Fig.3 - transfer of the energy law across frames.
(a) damped coefficient c_c = E_crit/W_rem^c per frame (median, IQR) vs storeys;
(b) undamped c0_c vs storeys; (c) dissipation toll D/W_rem vs storeys;
(d) per-frame classifier accuracy: energy rule at c_dev vs drift rule.
Data: analysis/summary_by_frame.json.
"""
import json
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(r"/mnt/e/n0r53/analysis")
S = json.loads((OUT / "summary_by_frame.json").read_text())
C_DEV = S.get("_protocol", {}).get("c_dev", 1.13)
plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "axes.labelsize": 8, "legend.fontsize": 7, "figure.dpi": 200})

def nst(model):
    return int(re.match(r"SMF(\d+)", model).group(1))

def key_for(model):
    for k in (f"{model}|ALL", f"{model}|FF"):
        if k in S and S[k].get("n_transition_c"):
            return k
    return None

MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
COL = {"B": "#1f77b4", "CG": "#d95f02"}
rows = []
for m in MODELS:
    k = key_for(m)
    if not k:
        continue
    s = S[k]
    rows.append(dict(model=m, n=nst(m), cg=m.endswith("CG"), key=k,
                     cc=s["c_c"], cci=s["c_c_iqr"], c0=s["c0_c"], c0i=s["c0_c_iqr"],
                     D=[s["D_over_W"][0], 0, 0],
                     Di=s["D_over_W_p10p90"],
                     nt=s["n_transition_c"],
                     accE=s.get("acc_cdev_Wc"), accD=s.get("acc_drift_dev_thr")))
x = [r["n"] + (0.35 if r["cg"] else -0.35) for r in rows]

fig, ax = plt.subplots(2, 2, figsize=(7.0, 4.8))
a, b, c, d = ax.flat

def series(axis, field, ifield, ylab, devline):
    for cg, mk, lbl in ((False, "o", "bare"), (True, "s", "composite+gravity")):
        xs = [r["n"] + (0.3 if cg else -0.3) for r in rows if r["cg"] == cg and r[field]]
        ys = [r[field][0] for r in rows if r["cg"] == cg and r[field]]
        lo = [max(r[field][0] - r[ifield][0], 0.0) for r in rows if r["cg"] == cg and r[field]]
        hi = [max(r[ifield][1] - r[field][0], 0.0) for r in rows if r["cg"] == cg and r[field]]
        if not xs:
            continue
        axis.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, ms=4.5, mfc="white" if cg else COL["CG" if cg else "B"],
                      mec=COL["CG" if cg else "B"], ecolor=COL["CG" if cg else "B"], elinewidth=0.8,
                      capsize=2, label=lbl, zorder=3)
        for xx, yy, r in zip(xs, ys, [r for r in rows if r["cg"] == cg and r[field]]):
            if cg:
                off = (9, -8) if (field == "D" or r["n"] == 2) else (9, 5)
                axis.annotate(f"{r['model'].replace('SMF','')}", (xx, yy), fontsize=5.5,
                              xytext=off, textcoords="offset points", ha="left")
            else:
                axis.annotate(f"{r['model'].replace('SMF','')}", (xx, yy), fontsize=5.5,
                              xytext=(-9, -8), textcoords="offset points", ha="right")
    if devline:
        axis.axhline(devline, color="k", ls="--", lw=0.7)
    axis.axhline(1.0, color="k", lw=0.6, alpha=0.6)
    axis.set_ylabel(ylab)
    axis.set_xscale("log"); axis.set_xticks([2, 4, 8, 12, 20]); axis.set_xticklabels([2, 4, 8, 12, 20])
    axis.set_xlim(1.35, 30)
    axis.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    axis.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axis.set_xlabel("storeys")

# (a) damping toll: beta_crit^2 vs damping scale s on 24 paired 4B states
try:
    SENS = json.loads((OUT / "sens_damp_bcrit.json").read_text())
    sx = [0.0, 0.5, 1.0, 2.0]
    sk = {s_: f"{s_:g}" for s_ in sx}
    for k, v in SENS.items():
        b2 = [v.get(sk[s_]) for s_ in sx]
        if all(b is not None for b in b2):
            a.plot(sx, [bb * bb for bb in b2], color="#bbbbbb", lw=0.5, zorder=1)
    meds = [float(np.median([v[sk[s_]] ** 2 for v in SENS.values() if v.get(sk[s_]) is not None])) for s_ in sx]
    a.plot(sx, meds, "o-", color="#1f77b4", ms=5, lw=1.4, zorder=3, label="median $\\beta_{\\mathrm{crit}}^2$")
    a.set_xlabel("damping scale $s$"); a.set_ylabel("$\\beta_{\\mathrm{crit}}^2$")
    a.set_xlim(-0.12, 2.12)
    a.annotate("24 paired 4B states;\n$s\\to0$ intercept matches\nmeasured undamped (1.001)",
               (0.06, 0.03), xycoords="axes fraction", fontsize=6, va="bottom")
    a.legend(loc="upper left", frameon=False, fontsize=6.5)
except Exception:
    a.text(0.5, 0.5, "sens data missing", transform=a.transAxes, ha="center")
a.set_title("a  escape energy is affine in damping", fontsize=8, loc="left")

series(b, "c0", "c0i", "$c_f^0=E_{\\mathrm{crit}}^0/W_{\\mathrm{rem}}$ (undamped)", None)
b.set_title("b  undamped escape energy over barrier", fontsize=8, loc="left")
b.set_ylim(0.55, 1.75)

series(c, "D", "Di", "$D/W_{\\mathrm{rem}}$", None)
c.set_title("c  dissipation toll over barrier", fontsize=8, loc="left")

# (d) accuracy per frame, energy at c_dev vs drift rule
yy = np.arange(len(rows))
w = 0.36
d.barh(yy - w / 2, [100 * (r["accE"] or 0) for r in rows], height=w, color="#1f77b4", label="energy ($c_{dev}$)")
d.barh(yy + w / 2, [100 * (r["accD"] or 0) for r in rows], height=w, color="#999999", label="drift rule")
d.set_yticks(yy); d.set_yticklabels([r["model"].replace("SMF", "") for r in rows], fontsize=6.5)
d.set_xlim(40, 102); d.set_xlabel("accuracy on released states (%)")
d.legend(loc="lower right", frameon=False, fontsize=6.5)
d.invert_yaxis()
d.set_title("d  per-frame classifier accuracy", fontsize=8, loc="left")

fig.tight_layout(w_pad=1.7, h_pad=1.6)
for ext in ("pdf", "png"):
    fig.savefig(OUT / f"fig3_transfer.{ext}")
print("wrote fig3_transfer.pdf/.png")
