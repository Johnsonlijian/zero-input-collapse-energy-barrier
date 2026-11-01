"""Fig.5 - consequences of the damaged-state barrier.
(a) energy budget of the critical escape at the pass (A7): internal work, viscous work and
    residual kinetic energy, each / W_rem, per frame; damped c and undamped c0 markers;
(b) residual collapse capacity of settled damaged states vs remaining-barrier ratio (A6, 4B);
(c) the same capacities vs residual storey drift;
(d) truncated-record (t95) bias of the median collapse capacity and of P_c at the
    full-record median, all ten frames (A9).
Data: analysis/{kick_energy_analysis,aftershock_analysis,t95_all}.json
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

A = Path(r"E:\n0r53\analysis")
BLUE, ORANGE, GREY, GREEN, PURPLE = "#1f77b4", "#d95f02", "#999999", "#1b9e77", "#7570b3"
plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "axes.labelsize": 8, "legend.fontsize": 6.5, "figure.dpi": 200})
LAB = {"SMF2B": "2B", "SMF2CG": "2CG", "SMF4B": "4B", "SMF4CG": "4CG", "SMF8B": "8B", "SMF8CG": "8CG",
       "SMF12B": "12B", "SMF12CG": "12CG", "SMF20B": "20B", "SMF20CG": "20CG"}


def jl(name):
    p = A / name
    return json.loads(p.read_text()) if p.exists() else {}


fig, ax = plt.subplots(2, 2, figsize=(7.0, 5.0))
a, b, c, d = ax.flat

# (a) energy budget at the pass
ke = jl("kick_energy_analysis.json")
models = [m for m in ("SMF2B", "SMF4B", "SMF8B", "SMF4CG", "SMF8CG") if m in ke]
for i, m in enumerate(models):
    s = ke[m]["summary"]
    ai, bv, kk = s["a_int"]["median"], s["b_visc"]["median"], s["k_ke"]["median"]
    a.barh(i, ai, color=BLUE, height=0.6, label="internal work" if i == 0 else None)
    a.barh(i, bv, left=ai, color=ORANGE, height=0.6, label="viscous work" if i == 0 else None)
    a.barh(i, kk, left=ai + bv, color=GREY, height=0.6, label="kinetic energy" if i == 0 else None)
    a.plot(s["c"]["median"], i, "kD", ms=3.5, label=r"$c=E_{\rm crit}/W_{\rm rem}$" if i == 0 else None)
    if s.get("c0"):
        a.plot(s["c0"]["median"], i, "o", mfc="white", mec="k", ms=4, label=r"$c^0$ (undamped)" if i == 0 else None)
    a.text(0.02, i, f"n={s['c']['n']}", va="center", ha="left", fontsize=6, color="white")
a.axvline(1.0, color="k", lw=0.5, ls=":")
a.set_yticks(range(len(models)))
a.set_yticklabels([LAB[m] for m in models])
a.invert_yaxis()
a.set_xlabel(r"energy at the pass / $W_{\rm rem}$ (median)")
a.set_xlim(0, 2.3)
a.legend(loc="center right", bbox_to_anchor=(1.0, 0.5), frameon=False, ncol=1, fontsize=6, borderaxespad=0.2)
a.set_title("a  escape-energy budget at the pass", loc="left", fontsize=8)

# (b), (c) residual capacity of settled damaged states (4B)
af = jl("aftershock_analysis.json").get("SMF4B")
if af:
    rows = af["rows"]
    cols = {"q0.50": "#c6dbef", "q0.70": "#6baed6", "q0.85": "#2171b5", "q0.95": "#08306b",
            "early1": "#fdae6b", "early2": ORANGE, "ta": "#7f2704"}
    for tag, col in cols.items():
        sub = [r for r in rows if r["tag"] == tag]
        if not sub:
            continue
        mk = "v" if any(r["status"] == "collapse_at_floor" for r in sub) and tag == "ta" else "o"
        lab = {"q0.50": r"mainshock $0.50\,S_{a,c}$", "q0.70": r"$0.70\,S_{a,c}$", "q0.85": r"$0.85\,S_{a,c}$",
               "q0.95": r"$0.95\,S_{a,c}$", "early1": "near-boundary (early)", "early2": None,
               "ta": r"near-boundary ($t_a$)"}[tag]
        b.scatter([max(r["w"], 1e-3) for r in sub], [r["R"] for r in sub], s=6, color=col, marker=mk,
                  lw=0, label=lab)
    xx = np.logspace(-3, 0.1, 50)
    b.plot(xx, xx, color="k", lw=0.6, ls="--", label=r"$R=w$")
    b.set_xscale("log"); b.set_yscale("log")
    b.set_xlim(1e-3, 1.3); b.set_ylim(0.03, 1.5)
    b.set_xlabel(r"retained barrier $w=W_{\rm set}/W_{\rm int}$")
    b.set_ylabel(r"retained capacity $R=S_{a,c}^{\rm dam}/S_{a,c}$")
    b.legend(loc="upper left", bbox_to_anchor=(0.0, 0.90), frameon=False, fontsize=5.5, handletextpad=0.2)
    sm = af["summary"]
    rw = sm.get("aftershock_ms_R_over_w")
    if rw:
        b.text(0.03, 0.97, rf"mainshock-damaged: median $R/w$ = {rw['median']:.2f} (n = {rw['n']})",
               transform=b.transAxes, va="top", fontsize=6)
b.set_title("b  retained barrier sets retained capacity (4B)", loc="left", fontsize=8)

# (c) prediction error of R on mainshock-damaged states, per frame
asj = jl("aftershock_analysis.json")
def _own(m):
    return ((asj.get(m) or {}).get("summary", {}).get("ms_sub") or {}).get("own") or {}


fr_c = [m for m in ("SMF2B", "SMF4B", "SMF8B", "SMF12B", "SMF20B", "SMF2CG", "SMF4CG", "SMF8CG", "SMF12CG", "SMF20CG")
        if _own(m).get("pred") and _own(m)["n_events"] >= 20]
keys = [("w_zero_param", "$w$, no fit"), ("w_fitted_cv", "$w$, fitted"), ("res_fitted_cv", "resid. drift"),
        ("roof_fitted_cv", "resid. roof"), ("peak_fitted_cv", "peak drift"), ("q_fitted_cv", "mainshock $S_a$")]
shades = ["#08306b", "#2171b5", "#6baed6", "#9ecae1", "#c6dbef"]
wbar = 0.8 / max(len(fr_c), 1)
for j, m in enumerate(fr_c):
    pr = _own(m)["pred"]["rmse"]
    xs = np.arange(len(keys)) - 0.4 + wbar * (j + 0.5)
    fam = [x for x in fr_c if x.endswith("B") == m.endswith("B")]
    pal = shades if m.endswith("B") else ["#00441b", "#238b45", "#66c2a4", "#99d8c9", "#ccece6"]
    c.bar(xs, [pr[k] for k, _ in keys], width=wbar * 0.92, color=pal[fam.index(m) % len(pal)],
          label=f"{LAB[m]} (n={_own(m)['n_unc']})")
c.set_xticks(range(len(keys))); c.set_xticklabels([l for _, l in keys], rotation=30, ha="right", fontsize=6.5)
c.axvspan(-0.5, 0.5, color=GREY, alpha=0.15, lw=0)
c.set_ylabel(r"log-error of $R$ (RMSE, cross-validated)")
c.legend(loc="upper center", frameon=False, fontsize=6, ncol=2, columnspacing=0.8, handletextpad=0.4)
c.set_title("c  barrier vs drift and intensity indicators", loc="left", fontsize=8)

# (d) truncated-record bias
tj = jl("t95_all.json")
ms = [m for m in LAB if m in tj]
x = np.arange(len(ms))
sh = np.array([100 * (tj[m]["ALL"]["median_shift"] - 1) for m in ms])
lo = np.array([100 * (tj[m]["ALL"]["median_shift_ci95"][0] - 1) for m in ms])
hi = np.array([100 * (tj[m]["ALL"]["median_shift_ci95"][1] - 1) for m in ms])
d.bar(x, sh, color=[BLUE if m.endswith("B") else GREEN for m in ms], width=0.6)
d.errorbar(x, sh, yerr=[sh - lo, hi - sh], fmt="none", ecolor="k", lw=0.6, capsize=1.5)
d.set_xticks(x); d.set_xticklabels([LAB[m] for m in ms], rotation=45, fontsize=6.5)
d.set_ylabel(r"overestimate of median $S_{a,c}$ (%)")
d2 = d.twinx()
pc = [100 * tj[m]["ALL"]["Pc_t95_at_med_full"] for m in ms]
d2.plot(x, pc, "s", color=ORANGE, ms=3)
d2.axhline(50, color=ORANGE, lw=0.5, ls=":")
d2.set_ylim(30, 55); d2.set_ylabel(r"$P_c$ at full-record median (%)", color=ORANGE)
d2.tick_params(axis="y", colors=ORANGE)
d.set_title(r"d  truncation at $t_{95}$ biases capacity", loc="left", fontsize=8)

fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(A / f"fig5_consequences.{ext}", bbox_inches="tight")
print("wrote fig5_consequences")
