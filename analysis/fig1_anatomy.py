"""Fig.1 - anatomy of one collapse history (SMF4B, exemplar FF121421).
Panels: (a) peak storey drift + release outcomes + t95/ta/t*/tc; (b) storey drift profile at ta/t*;
(c) KE(t) vs W_rem(t) log scale with last crossing; (d) damaged-state push curve at ta with barrier shaded.
Data: runs/zic, runs/ida, runs/erosion, runs/push. Output: analysis/fig1_anatomy.pdf/.png
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis")
RID, MODEL = "FF121421", "SMF4B"
BLUE, ORANGE, GREY, GREEN = "#1f77b4", "#d95f02", "#7f7f7f", "#1b9e77"
C_DEV = 1.13

plt.rcParams.update({"font.size": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "axes.labelsize": 8, "legend.fontsize": 7, "figure.dpi": 200})


def jload(p):
    return json.loads(p.read_text())


z = jload(RUNS / "zic" / MODEL / f"{RID}__hi.json")
ida = jload(RUNS / "ida" / MODEL / f"{RID}.json")
h = z["hist"]
t = np.asarray(h["t"]); D = np.asarray(h["d"]); KE = np.asarray(h["ke"])
msdr = np.max(np.abs(D), axis=1)
pk = np.maximum.accumulate(msdr)
t95, tc, ts, ta = ida["t95"], z["ref"]["t_coll"], z["t_star"], z["t_a"]

rels = sorted(((float(r["t_r"]), bool(r["committed"])) for r in z["releases"].values()), key=lambda x: x[0])
tr = np.array([r[0] for r in rels]); com = np.array([r[1] for r in rels])
def profile_at(tt):
    return np.abs(D[int(np.argmin(np.abs(t - tt)))])

fig = plt.figure(figsize=(7.0, 6.1))
gs = fig.add_gridspec(3, 2, height_ratios=[0.62, 1.0, 1.0],
                      hspace=0.52, wspace=0.30,
                      top=0.96, bottom=0.08, left=0.09, right=0.98)
s = fig.add_subplot(gs[0, :])
a = fig.add_subplot(gs[1, 0]); b = fig.add_subplot(gs[1, 1])
c = fig.add_subplot(gs[2, 0]); d = fig.add_subplot(gs[2, 1])

# (a) protocol schematic: cut the input, carry the full state, continue free
s.axis("off"); s.set_xlim(0, 13.4); s.set_ylim(0, 2.9)
# waveform: record up to t_r, removed tail dotted
tw = np.linspace(0.35, 3.05, 300)
rngw = np.random.default_rng(7)
wav = np.convolve(rngw.standard_normal(300), np.hanning(31), "same")
wav = 0.42 * wav / np.abs(wav).max() * np.sin(np.linspace(0, np.pi, 300) ** 0.7)
i_cut = int(0.72 * len(tw)); t_cut = tw[i_cut]
s.plot(tw[:i_cut + 1], 1.55 + wav[:i_cut + 1], color=GREY, lw=0.8)
s.plot(tw[i_cut:], 1.55 + wav[i_cut:], color=GREY, lw=0.8, ls=":", alpha=0.45)
s.axvline(t_cut, color="k", lw=0.7, ls="--")
s.annotate("input removed", (t_cut, 2.35), fontsize=6.5, ha="center", va="bottom")
s.annotate("scaled record", (0.45, 1.02), fontsize=6.5, ha="left", va="top", color=GREY)
# state box
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
s.add_patch(FancyBboxPatch((3.75, 1.18), 1.75, 0.74, boxstyle="round,pad=0.06",
                           fc="#eef2f7", ec="k", lw=0.7))
s.annotate("state at $t_r$\n$\\{u,\\dot{u},z\\}$", (4.62, 1.55), fontsize=7,
           ha="center", va="center")
s.add_patch(FancyArrowPatch((t_cut + 0.03, 1.55), (3.72, 1.55),
                            arrowstyle="-|>", mutation_scale=9, color="k", lw=0.8))
# stick frame (4-storey, leaning)
xf0, xf1 = 6.35, 7.05
lean = 0.16
for k in range(5):
    y0 = 0.35 + 0.5 * k
    s.plot([xf0 + lean * k, xf1 + lean * k], [y0, y0], color="k", lw=1.1)
for k in range(4):
    y0, y1 = 0.35 + 0.5 * k, 0.35 + 0.5 * (k + 1)
    s.plot([xf0 + lean * k, xf0 + lean * (k + 1)], [y0, y1], color="k", lw=1.1)
    s.plot([xf1 + lean * k, xf1 + lean * (k + 1)], [y0, y1], color="k", lw=1.1)
s.scatter([xf0 + lean * 1, xf1 + lean * 3], [0.35 + 0.5, 0.35 + 1.5],
          marker="s", s=16, color=ORANGE, zorder=5)
s.annotate("damaged\nhinges", (6.05, 0.22), fontsize=6,
           ha="center", va="top", color=ORANGE)
s.add_patch(FancyArrowPatch((5.55, 1.55), (6.28, 1.55),
                            arrowstyle="-|>", mutation_scale=9, color="k", lw=0.8))
s.annotate("restart,\nzero input", (5.9, 1.78), fontsize=6, ha="center", va="bottom")
# outcomes: decaying vs runaway
xo0, xo1 = 8.15, 9.95
tt2 = np.linspace(0, 1, 120)
s.plot([xo0, xo1], [2.55, 2.55], color="#cccccc", lw=0.5)
s.plot(xo0 + tt2 * (xo1 - xo0), 2.55 + 0.24 * np.sin(9 * tt2) * np.exp(-2.6 * tt2),
       color=BLUE, lw=0.9)
s.annotate("recoverable", (xo0, 2.82), fontsize=6.5, color=BLUE, ha="left")
s.plot([xo0, xo1], [0.30, 0.30], color="#cccccc", lw=0.5)
s.plot(xo0 + tt2 * (xo1 - xo0),
       0.30 + 0.85 * (tt2 ** 2.6) + 0.05 * np.sin(7 * tt2) * tt2,
       color=ORANGE, lw=0.9)
s.plot([xo0, xo1], [1.02, 1.02], color="k", lw=0.5, ls="--")
s.annotate("$\\theta_c$", (xo1 - 0.04, 1.02), fontsize=6, ha="right", va="bottom")
s.annotate("committed to collapse", (xo0, 0.10), fontsize=6.5, color=ORANGE, ha="left")
s.add_patch(FancyArrowPatch((7.55, 1.55), (8.1, 2.45),
                            arrowstyle="-|>", mutation_scale=8, color="k", lw=0.7))
s.add_patch(FancyArrowPatch((7.55, 1.55), (8.1, 0.65),
                            arrowstyle="-|>", mutation_scale=8, color="k", lw=0.7))
s.annotate("free\ncontinuation", (7.72, 1.52), fontsize=6, ha="center", va="center",
           bbox=dict(fc="white", ec="none", pad=0.8))
# energy-margin cell: potential-well escape criterion (right of outcomes)
xw0, xw1 = 10.75, 13.15
q = np.linspace(0, 1, 300)
xq = xw0 + q * (xw1 - xw0)
ybase, yamp = 0.45, 1.55
qq = (q - 0.20) / (0.60 - 0.20)
U = ybase + yamp * np.clip(qq ** 2, 0, 1.0)
mask = q > 0.60
U[mask] = ybase + yamp - 2.6 * (q[mask] - 0.60)
s.plot(xq, U, color="k", lw=1.0)
x_ball = xw0 + 0.20 * (xw1 - xw0)
x_crest = xw0 + 0.60 * (xw1 - xw0)
y_crest = ybase + yamp
s.scatter([x_ball], [ybase + 0.05], s=34, color=BLUE, zorder=5)
s.annotate("", (x_ball + 0.42, y_crest - 0.06), (x_ball + 0.42, ybase + 0.06),
           arrowprops=dict(arrowstyle="<->", lw=0.7, color="k"))
s.annotate("$W_{\\mathrm{rem}}$", (x_ball + 0.52, ybase + 0.72), fontsize=7, ha="left", va="center")
s.add_patch(FancyArrowPatch((x_ball + 0.18, ybase + 0.42), (x_crest + 0.42, y_crest - 0.18),
                            connectionstyle="arc3,rad=-0.5", arrowstyle="-|>",
                            mutation_scale=9, color=ORANGE, lw=1.0))
s.annotate("escapes iff\n$\\mathrm{KE}\\geq c\\,W_{\\mathrm{rem}}$",
           (x_crest + 0.12, y_crest + 0.18), fontsize=6.5, ha="left", va="bottom", color=ORANGE)
s.annotate("$U(q)$", (xw0 + 0.06, 1.30), fontsize=6.5, ha="left", color="k")
s.annotate("configuration $q$", ((xw0 + xw1) / 2, 0.02), fontsize=6, ha="center", va="bottom", color=GREY)
s.set_title("a  the zero-input release and the escape criterion", fontsize=8, loc="left")

# (a) drift history + releases
a.plot(t, pk, color=GREY, lw=0.9, label="running peak drift")
a.plot(t, msdr, color="#bdbdbd", lw=0.5, label="inst. peak drift")
rel_sdr = np.interp(tr, t, msdr)
a.scatter(tr[~com], rel_sdr[~com], s=14, c=BLUE, marker="o", lw=0, zorder=5, label="recoverable release")
a.scatter(tr[com], rel_sdr[com], s=14, c=ORANGE, marker="s", lw=0, zorder=5, label="committed release")
for x, lab, yy in ((t95, "$t_{95}$", 0.175), (ta, "$t_a$", 0.155), (ts, "$t^\\ast$", 0.175), (tc, "$t_c$", 0.175)):
    a.axvline(x, color="k", lw=0.5, ls=":" if x == t95 else ("--" if x in (ta, ts) else "-"), alpha=0.8)
    a.annotate(lab, (x, yy), fontsize=7, ha="center", va="bottom",
               bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.2))
a.set_ylim(0, 0.19); a.set_xlim(t95 - 15, tc + 2)
a.set_xlabel("time (s)"); a.set_ylabel("peak storey drift")
a.legend(loc="center left", frameon=False, handlelength=1.2, borderaxespad=0)
a.set_title("b  drift history and released states", fontsize=8, loc="left")

# (b) drift profile at ta / t* (from the reference history at the release instant)
st = np.arange(1, D.shape[1] + 1)
for trk, mk, col, lab in ((ta, "o", BLUE, f"$t_a$={ta:.2f} s"), (ts, "s", ORANGE, f"$t^\\ast$={ts:.2f} s")):
    s = profile_at(trk)
    b.plot(s, st, marker=mk, ms=3.5, lw=0.9, color=col, label=lab, mfc="none" if trk == ta else col)
b.axvline(0.15, color="k", ls="--", lw=0.6); b.annotate("$\\theta_c$", (0.15, len(st) + 0.15), fontsize=7, ha="right")
b.set_xlabel("storey drift magnitude"); b.set_ylabel("storey")
b.set_ylim(0.5, len(st) + 0.5); b.legend(loc="lower right", frameon=False)
b.set_title("c  drift profile at the boundary", fontsize=8, loc="left")

# (c) KE(t) vs W_rem(t)
kn = []
for p in (RUNS / "erosion" / MODEL).glob(f"{RID}__hi__*.json"):
    e = jload(p)
    if e.get("converged") and e.get("W_barrier") is not None:
        t_rk = e.get("t_r") or (e.get("state") or {}).get("t_r") or float(p.stem.split("__")[2])
        kn.append((float(t_rk), float(e["W_barrier"])))
kn.sort()
tk = np.array([p[0] for p in kn]); Wk = np.array([p[1] for p in kn])
c.semilogy(t, np.maximum(KE, 1e-3), color=BLUE, lw=0.8, label="KE(t)")
c.semilogy(tk, C_DEV * np.maximum(Wk, 1e-1), color=ORANGE, lw=0.9, marker="o", ms=2.5, label="$c_{dev}\\,W_{rem}$")
for x, col in ((t95, ":"), (ta, "--"), (ts, "--"), (tc, "-")):
    c.axvline(x, color="k", lw=0.5, ls=col, alpha=0.8)
c.set_xlim(t95 - 3, tc + 2); c.set_xlabel("time (s)"); c.set_ylabel("energy (kip-in)")
c.set_ylim(1e-1, 3e4)
c.legend(loc="lower right", frameon=False)
c.set_title("d  energy race along the coda", fontsize=8, loc="left")

# (d) push curve at ta
p = jload(RUNS / "push" / MODEL / f"{RID}__hi__{ta:.4f}.json")
cv = np.asarray(p["curve"])
x, y = cv[:, 2], cv[:, 1]  # peak storey drift vs load factor
i_pos = np.argmax(y > 0) if np.any(y > 0) else 0
W = p["W_barrier"]
d.plot(x, y, color=ORANGE, lw=1.0)
d.axhline(0, color="k", lw=0.5)
if np.any(y > 0):
    i0 = np.argmax(y > 0); i1 = len(y) - 1
    pos = (y > 0)
    if pos.any():
        d.fill_between(x, 0, y, where=pos, color=ORANGE, alpha=0.25, label=f"$W_{{rem}}$={W:.0f} kip-in")
s0 = np.interp(ta, t, msdr)
d.axvline(s0, color="k", ls=":", lw=0.6); d.annotate("release drift", (s0, d.get_ylim()[1] * 0.97), fontsize=6, rotation=90, va="top", ha="left")
d.set_xlabel("peak storey drift"); d.set_ylabel("$\\lambda$ (kip)")
d.legend(loc="upper right", frameon=False)
d.set_title("e  damaged-state push at $t_a$", fontsize=8, loc="left")

for ext in ("pdf", "png"):
    fig.savefig(OUT / f"fig1_anatomy.{ext}")
print("wrote fig1_anatomy.pdf/.png")

