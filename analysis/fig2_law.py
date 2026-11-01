"""Fig.2 - the energy law on the development frame(s).
(a) damaged-state push curves at t_a for all collapse histories of a model (grey) + exemplar;
(b) velocity-scaling ladder for the exemplar state -> beta_crit;
(c) E_crit/W_rem at transition states vs W_rem, damped and undamped;
(d) classifier accuracy by energy-margin band vs the development-fitted drift rule.
Data: runs/{zic,push,kick,kick_undamped}/<model>, analysis/law_table.csv.
"""
import csv
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis")
RID, MODEL = "FF121421", "SMF4B"
BLUE, ORANGE, GREY, GREEN = "#1f77b4", "#d95f02", "#999999", "#1b9e77"
C_DEV = 1.13
plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "axes.labelsize": 8, "legend.fontsize": 7, "figure.dpi": 200})


def jload(p):
    return json.loads(p.read_text())


fig, ax = plt.subplots(2, 2, figsize=(7.0, 4.8))
a, b, c, d = ax.flat

# (a) push curves at t_a: edge-limited 4B (grey) vs drift-limited 4CG (purple)
zex = None
for p in (RUNS / "zic" / MODEL).glob("*__hi.json"):
    z = jload(p)
    if z.get("t_star") is None or not z["rid"].startswith("FF"):
        continue
    pp = RUNS / "push" / MODEL / f'{z["rid"]}__hi__{z["t_a"]:.4f}.json'
    if not pp.exists():
        continue
    pj = jload(pp)
    if not pj.get("curve"):
        continue
    cv = np.asarray(pj["curve"])
    if z["rid"] == RID:
        zex = cv
        continue
    a.plot(cv[:, 2], cv[:, 1], color=GREY, lw=0.4, alpha=0.35, zorder=1)
ncg = 0
for p in sorted((RUNS / "zic" / "SMF4CG").glob("FF*__hi.json")):
    z = jload(p)
    if z.get("t_star") is None:
        continue
    pp = RUNS / "push" / "SMF4CG" / f'{z["rid"]}__hi__{z["t_a"]:.4f}.json'
    if not pp.exists():
        continue
    pj = jload(pp)
    if not pj.get("curve"):
        continue
    cv = np.asarray(pj["curve"])
    a.plot(cv[:, 2], cv[:, 1], color="#7570b3", lw=0.4, alpha=0.4, zorder=2,
           label="4CG (drift-limited)" if ncg == 0 else None)
    ncg += 1
    if ncg >= 18:
        break
if zex is not None:
    a.plot(zex[:, 2], zex[:, 1], color=ORANGE, lw=1.4, zorder=3, label="4B exemplar (Fig.~1)")
a.axhline(0, color="k", lw=0.5)
a.axvline(0.15, color="k", ls=":", lw=0.6)
a.annotate("$\\theta_c$", (0.151, a.get_ylim()[0] * 0.85), fontsize=7, ha="left", va="center",
           bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.2))
a.set_xlabel("peak storey drift"); a.set_ylabel("$\\lambda$ (kip)")
a.legend(loc="upper right", frameon=False)
a.set_title("a  damaged-state pushes at $t_a$ (FF)", fontsize=8, loc="left")

# (b) beta ladder for exemplar
k = jload(RUNS / "kick" / MODEL / f"{RID}__hi__66.5500.json")
bs, ms, labs = [], [], []
for key, r in k["runs"].items():
    bs.append(float(r["beta"])); ms.append(r["max_sdr"]); labs.append(r["label"])
bs, ms, labs = map(np.array, zip(*sorted(zip(bs, ms, labs))))
b.plot(bs, ms, "-", color=GREY, lw=0.6, zorder=1)
com = labs == "committed"
b.scatter(bs[com], ms[com], c=ORANGE, marker="s", s=18, zorder=3, label="collapses")
b.scatter(bs[~com], ms[~com], c=BLUE, marker="o", s=18, zorder=3, label="settles")
b.axvline(k["beta_crit"], color="k", ls="--", lw=0.6)
b.annotate(f"$\\beta_{{crit}}$={k['beta_crit']:.3f}", (k["beta_crit"], 0.02), fontsize=7, ha="right", va="bottom",
           bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.2))
b.axhline(0.15, color="k", ls=":", lw=0.5)
b.set_xlabel("velocity scale $\\beta$"); b.set_ylabel("peak storey drift after release")
b.legend(loc="lower right", frameon=False)
b.set_title("b  escape-energy ladder at $t_a$ (exemplar)", fontsize=8, loc="left")

# (c) E_crit/W_rem vs W_rem at transition states, all frames present in law_table
rows = []
with (OUT / "law_table.csv").open(newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r.get("tag") in ("ta", "tstar"):
            rows.append(r)
def fnum(x):
    try:
        return float(x)
    except Exception:
        return np.nan
cmap = {"SMF4B": BLUE, "SMF8B": ORANGE, "SMF2B": GREEN, "SMF2CG": "#7570b3", "SMF4CG": "#66a61e",
        "SMF8CG": "#e7298a", "SMF12B": "#a6761d", "SMF12CG": "#666666", "SMF20B": "#e6ab02", "SMF20CG": "#1f78b4"}
for damped, mk, lbl in ((True, "o", "damped"), (False, "^", "undamped")):
    for m, col in cmap.items():
        xs = [r for r in rows if r["model"] == m and fnum(r.get("Wc_m1")) > 0 and
              fnum(r.get("E_d" if damped else "E_u")) > 0]
        if not xs:
            continue
        W = [fnum(r["Wc_m1"]) for r in xs]
        R = [fnum(r["E_d" if damped else "E_u"]) / fnum(r["Wc_m1"]) for r in xs]
        c.scatter(W, R, c=col, marker=mk, s=9, lw=0, alpha=0.55 if damped else 0.45,
                  label=f"{m.replace('SMF','')}{'' if damped else ' $u$'}", zorder=3 if damped else 2)
c.axhline(1, color="k", lw=0.7)
c.axhline(C_DEV, color="k", lw=0.6, ls="--")
c.annotate(f"$c_{{dev}}$={C_DEV}", (1e5, C_DEV), fontsize=7, va="bottom", ha="right")
c.set_xscale("log"); c.set_yscale("log")
c.set_xlabel("$W_{\\mathrm{rem}}$ to the collapse surface (kip-in)"); c.set_ylabel("$E_{\\mathrm{crit}}/W_{\\mathrm{rem}}$")
c.legend(loc="lower left", frameon=False, ncol=2, fontsize=6, columnspacing=0.6, handletextpad=0.2)
c.set_title("c  escape energy over barrier at transition states", fontsize=8, loc="left")

# (d) accuracy by margin band, pooled across all frames with data;
# energy rule (per-frame c_f on W_rem^c) vs the development-fitted drift rule on the same states
bands = ["[0,0.1)", "[0.1,0.2)", "[0.2,0.4)", "[0.4,1.0)", "[1.0,inf)"]
allr = []
with (OUT / "law_table.csv").open(newline="", encoding="utf-8") as f:
    allr = list(csv.DictReader(f))
S = json.loads((OUT / "summary_by_frame.json").read_text())
DRIFT_THR_DEV = S.get("_protocol", {}).get("drift_threshold_dev", 0.1173)
Lall, cf_map = [], {}
for r in allr:
    m = r["model"]
    cf_m = (S.get(f"{m}|ALL") or {}).get("c_c")
    if not cf_m:
        continue
    if fnum(r.get("Wc_m1")) == fnum(r.get("Wc_m1")):
        cf_map[m] = cf_m[0]
        Lall.append(r)
yy = np.array([r["label_r52"] == "committed" for r in Lall])
ke = np.array([fnum(r["ke"]) for r in Lall])
W = np.array([fnum(r["Wc_m1"]) for r in Lall])
cfv = np.array([cf_map[r["model"]] for r in Lall])
pk = np.array([fnum(r["peak_sdr"]) for r in Lall])
with np.errstate(divide="ignore", invalid="ignore"):
    mgn = np.where(W > 0, np.log(np.maximum(ke, 1e-9) / (cfv * np.maximum(W, 1e-9))), np.inf)
width = 0.36
edges = [(0, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 1.0), (1.0, np.inf)]
ae, ad_, ns = [], [], []
for lo, hi in edges:
    kk = (np.abs(mgn) >= lo) & (np.abs(mgn) < hi if np.isfinite(hi) else np.abs(mgn) >= lo)
    ae.append(float(np.mean(((ke >= cfv * W) == yy)[kk])) if kk.sum() else np.nan)
    ad_.append(float(np.mean(((pk >= DRIFT_THR_DEV) == yy)[kk])) if kk.sum() else np.nan)
    ns.append(int(kk.sum()))
xx = np.arange(len(edges))
d.bar(xx - width / 2, np.nan_to_num(ae) * 100, width=width, color=BLUE, alpha=0.85, label="energy rule ($W_{\\mathrm{rem}}$)")
d.bar(xx + width / 2, np.nan_to_num(ad_) * 100, width=width, color=GREY, alpha=0.85, label="drift rule (dev)")
for x, n in zip(xx, ns):
    d.annotate(str(n), (x, 3), fontsize=6, ha="center")
d.set_xticks(xx)
d.set_xticklabels(["$<$0.1", "0.1-0.2", "0.2-0.4", "0.4-1.0", "$>$1.0"], fontsize=7)
d.set_xlabel("energy margin band  $|\\ln(\\mathrm{KE}/c_f W_{\\mathrm{rem}})|$")
d.set_ylabel("accuracy (%)"); d.set_ylim(0, 112)
d.legend(loc="upper left", frameon=False, fontsize=6.5, handlelength=1.2, borderaxespad=0.1)
d.set_title("d  rule accuracy by margin, all frames (n per band)", fontsize=8, loc="left")

fig.tight_layout(w_pad=1.7, h_pad=1.6)
for ext in ("pdf", "png"):
    fig.savefig(OUT / f"fig2_law.{ext}")
print("wrote fig2_law.pdf/.png")
