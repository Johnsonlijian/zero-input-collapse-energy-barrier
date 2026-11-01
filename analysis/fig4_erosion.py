"""Fig.4 - barrier erosion in the coda across all collapse histories.
(a) W_rem(t)/W_b per collapse history aligned at t95 (grey), median + IQR (orange);
(b) KE(t)/W_rem(t) knots vs t*, marker = crossing state, t* marked; shows last crossing = t*;
(c) distribution of t* - t95 and t_last - t*;
(d) share of histories committed at t95+x vs intensity margin [optional fill-in].
Data: runs/{ida,zic,erosion}/SMF4B, results/model_checks.json (W_b).
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis")
MODEL, C_DEV = "SMF4B", 1.13
BLUE, ORANGE, GREY = "#1f77b4", "#d95f02", "#999999"
plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "axes.labelsize": 8, "legend.fontsize": 7, "figure.dpi": 200})


def jload(p):
    return json.loads(p.read_text())


MC = None
for p in (Path(r"E:\n0r53\results\model_checks.json"),
          Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R52_N0_ZERO_INPUT_COMMITMENT_2026-10-11\results\model_checks.json")):
    if p.exists():
        mc_all = jload(p)
        if MODEL in mc_all:
            MC = mc_all[MODEL]
            break
Wb = (MC or {}).get("work_to_zero_V_kipin")
print("Wb:", Wb)

fig, ax = plt.subplots(2, 2, figsize=(7.0, 4.8))
a, b, c, d = ax.flat

series, lastcross, dts, wstar = [], [], [], []
zdir = RUNS / "zic" / MODEL
for zp in sorted(zdir.glob("*__hi.json")):
    z = jload(zp)
    if z.get("t_star") is None:
        continue
    rid = z["rid"]
    ida = jload(RUNS / "ida" / MODEL / f"{rid}.json")
    t95, ts = ida.get("t95"), z["t_star"]
    if t95 is None:
        continue
    kn = []
    for p in (RUNS / "erosion" / MODEL).glob(f"{rid}__hi__*.json"):
        e = jload(p)
        if e.get("converged") and e.get("W_barrier") is not None:
            tr = e.get("t_r") or (e.get("state") or {}).get("t_r") or float(p.stem.split("__")[2])
            kn.append((float(tr), float(e["W_barrier"])))
    kn.sort()
    if len(kn) < 3:
        continue
    tk = np.array([x[0] for x in kn]); Wk = np.array([x[1] for x in kn])
    series.append((tk - t95, Wk / Wb))
    # last crossing of KE vs c_dev W: need KE(t) at knots from zic hist
    h = z["hist"]; ht = np.asarray(h["t"]); hk = np.asarray(h["ke"])
    ke_k = np.array([hk[(ht >= x - 0.125) & (ht <= x + 0.125)].max() if np.any((ht >= x - 0.125) & (ht <= x + 0.125)) else np.nan for x in tk])
    cross = ke_k >= C_DEV * Wk
    if cross.any():
        j = len(cross) - 1
        while j >= 0 and cross[j]:
            j -= 1
        if j < len(cross) - 1:
            lastcross.append(tk[j + 1] - ts)
    dts.append(ts - t95)
    wstar.append(Wk[-1] / Wb if tk[-1] >= ts - 0.05 else np.nan)
    b.plot(tk - ts, np.maximum(ke_k, 1e-3) / np.maximum(C_DEV * Wk, 1e-3), color=GREY, lw=0.4, alpha=0.35, zorder=1)
    b.plot(ts - ts, 1.0, marker="x", ms=0, alpha=0)  # anchor

# (a)
for xs, ys in series:
    a.plot(xs, ys, color=GREY, lw=0.4, alpha=0.35, zorder=1)
    a.plot(xs[-1], ys[-1], marker="o", ms=2, color=ORANGE, alpha=0.6, zorder=2)
xg = np.linspace(-2, max(x[0][-1] for x in series), 200)
med = np.array([np.median([np.interp(x, xs, ys) for xs, ys in series if xs[0] <= x <= xs[-1]]) for x in xg])
q25 = np.array([np.percentile([np.interp(x, xs, ys) for xs, ys in series if xs[0] <= x <= xs[-1]], 25) for x in xg])
q75 = np.array([np.percentile([np.interp(x, xs, ys) for xs, ys in series if xs[0] <= x <= xs[-1]], 75) for x in xg])
a.fill_between(xg, q25, q75, color=ORANGE, alpha=0.25, lw=0)
a.plot(xg, med, color=ORANGE, lw=1.3, label="median")
a.axvline(0, color="k", ls=":", lw=0.6); a.annotate("$t_{95}$", (0.3, 1.3), fontsize=7, va="top", ha="left")
for xa in (0, 10, 20, 30):
    nn = sum(1 for xs, ys in series if xs[0] <= xa <= xs[-1])
    a.annotate(f"n={nn}", (xa, 4e-6), fontsize=6, ha="center", color=GREY)
a.set_yscale("log"); a.set_xlabel("time since $t_{95}$ (s)"); a.set_ylabel("$W_{\\mathrm{rem}}/W_b$")
a.legend(loc="lower left", frameon=False)
a.set_title("a  barrier erosion across collapse histories", fontsize=8, loc="left")

# (b)
b.axhline(1, color="k", lw=0.7); b.axvline(0, color="k", ls="--", lw=0.6)
b.annotate("$t^\\ast$", (0.5, 3e-2), fontsize=7, va="bottom", ha="left")
b.set_yscale("log"); b.set_ylim(1e-2, 1e3)
b.set_xlabel("time relative to $t^\\ast$ (s)"); b.set_ylabel("$\\mathrm{KE}/c_{\\mathrm{dev}}W_{\\mathrm{rem}}$")
b.set_title("b  margin history centred at $t^\\ast$", fontsize=8, loc="left")

# (c)
dts = np.asarray(dts); lastcross = np.asarray(lastcross); wstar = np.asarray(wstar)
c.hist(dts, bins=20, color=BLUE, alpha=0.8)
c.set_xlabel("$t^\\ast-t_{95}$ (s)"); c.set_ylabel("histories")
oklc = np.isfinite(lastcross)
txt = (f"last energy crossing $-$ $t^\\ast$:\nmedian {np.median(lastcross[oklc]):+.2f} s,\n"
       f"{int(np.sum(np.abs(lastcross[oklc]) <= 0.5))}/{int(oklc.sum())} within $\\pm$0.5 s")
c.text(0.97, 0.95, txt, transform=c.transAxes, fontsize=6.5, va="top", ha="right",
       bbox=dict(fc="white", ec=GREY, lw=0.5, boxstyle="round,pad=0.3"))
c.set_title(f"c  commitment is a coda event (n={len(dts)})", fontsize=8, loc="left")

# (d) W_rem at t* vs t*-t95
ok = np.isfinite(wstar)
d.scatter(dts[ok], wstar[ok], s=10, c=BLUE, alpha=0.6)
d.set_yscale("log"); d.set_xlabel("$t^\\ast-t_{95}$ (s)"); d.set_ylabel("$W_{\\mathrm{rem}}(t^\\ast)/W_b$")
d.set_title("d  residual barrier at commitment", fontsize=8, loc="left")

fig.tight_layout(w_pad=1.8, h_pad=1.6)
for ext in ("pdf", "png"):
    fig.savefig(OUT / f"fig4_erosion.{ext}")
print(f"wrote fig4_erosion: {len(series)} histories, median t*-t95={np.median(dts):.2f} s, "
      f"median W*/Wb={np.nanmedian(wstar):.4f}, |t_last-t*|<=0.5: {np.mean(np.abs(lastcross)<=0.5):.2f}")
