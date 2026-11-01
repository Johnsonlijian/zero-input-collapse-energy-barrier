"""Results figures 4-7 from results/*.csv|json.

Fig. 4  point of no return: drift at t*, time from t* to collapse, t* - t95
Fig. 5  released states in the drift / kinetic-energy plane (development and hold-out)
Fig. 6  record-specific collapse intensities: full analysis vs truncated analyses
Fig. 7  bare vs composite+gravity frames (if available)
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fig_style as fs  # noqa: E402

RES = HERE.parent / "results"
FIG = HERE.parent / "figures"
RNG = np.random.default_rng(7)


def read_csv(name: str) -> list[dict]:
    p = RES / name
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    for r in rows:
        for k, v in r.items():
            if v in ("", "None"):
                r[k] = None
            elif v in ("True", "False"):
                r[k] = v == "True"
            else:
                try:
                    r[k] = float(v)
                except (TypeError, ValueError):
                    pass
    return rows


def strip(ax, groups, values, colors, ylabel, ref=None, fmt="{:.1f}", pos=None):
    pos = list(range(len(groups))) if pos is None else list(pos)
    for i, g, vals, col in zip(pos, groups, values, colors):
        v = np.asarray([x for x in vals if x is not None and np.isfinite(x)], dtype=float)
        if len(v) == 0:
            continue
        jit = RNG.uniform(-0.18, 0.18, len(v))
        ax.scatter(i + jit, v, s=7, color=col, alpha=0.75, linewidths=0, zorder=3)
        med = float(np.median(v))
        ax.plot([i - 0.3, i + 0.3], [med, med], color=fs.INK, lw=1.4, zorder=4)
        ax.text(i + 0.33, med, fmt.format(med).replace("-", "−"), fontsize=6.5, color=fs.INK, va="center")
    ax.set_xticks(pos)
    ax.set_xticklabels(groups, fontsize=6.5)
    ax.set_xlim(min(pos) - 0.6, max(pos) + 0.8)
    ax.set_ylabel(ylabel)
    if ref:
        for y, lab in ref:
            ax.axhline(y, color=fs.MUTED, lw=0.7, zorder=1)
            if lab:
                # label at the left edge, clear of the medians and their labels
                ax.text(min(pos) - 0.57, y, lab, fontsize=6, color=fs.INK2, ha="left", va="bottom", zorder=5,
                        bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.8))
    ax.grid(axis="x", visible=False)


def fig4(models=("SMF4B", "SMF8B")):
    rows = []
    for m in models:
        rows += [r for r in read_csv(f"zic_records_{m}.csv") if r["level"] == "hi" and r["status"] == "ok"]
    if not rows:
        return
    mc = json.loads((RES / "model_checks.json").read_text())
    groups, cols, keys = [], [], []
    for m in models:
        for st in ("FF", "NF"):
            sub = [r for r in rows if r["model"] == m and r["set"] == st]
            if sub:
                groups.append(f"{m[3]}-st. {st}\n(n={len(sub)})" if m.endswith("B") else f"{m} {st}")
                cols.append(fs.FRAME_COLOR[m])
                keys.append(sub)
    fs.apply()
    fig, axs = plt.subplots(2, 2, figsize=(fs.DOUBLE * 0.82, 0.62 * fs.DOUBLE))
    axs = axs.ravel()
    lim = [100 * mc[m]["max_sdr_zero_V"] for m in models if mc[m].get("max_sdr_zero_V")]
    strip(axs[0], groups, [[100 * r["star_inst_sdr"] for r in k] for k in keys], cols,
          "Peak story drift at $t^*$ (%)",
          ref=[(10, ""), (float(np.mean(lim)), "")] if lim else [(10, "")])  # lines explained in the caption
    strip(axs[1], groups, [[r["lead_c"] for r in k] for k in keys], cols, "$t_c - t^*$ (s)", fmt="{:.1f}")
    strip(axs[2], groups, [[r["t_star"] - r["t95"] for r in k] for k in keys], cols, "$t^* - t_{95}$ (s)",
          ref=[(0, "")], fmt="{:+.1f}")
    strip(axs[3], groups, [[r.get("static_minus_star") for r in k] for k in keys], cols,
          "$t^*_s - t^*$ (s)", fmt="{:.2f}")
    for ax, lab in zip(axs, "abcd"):
        fs.panel_label(ax, f"({lab})")
    fig.tight_layout(w_pad=1.2, h_pad=1.0)
    fig.savefig(FIG / "fig4_point_of_no_return.pdf")
    fig.savefig(FIG / "fig4_point_of_no_return.png", dpi=300)


def fig5(models=("SMF4B", "SMF8B")):
    avail = [m for m in models if (RES / f"zic_states_{m}.csv").exists()]
    if not avail:
        return
    fs.apply()
    fig, axs = plt.subplots(1, len(avail), figsize=(fs.DOUBLE * (0.5 if len(avail) == 1 else 1.0), 0.42 * fs.DOUBLE),
                            sharey=True, squeeze=False)
    cl = json.loads((RES / "classify_summary.json").read_text()) if (RES / "classify_summary.json").exists() else {}
    floor = 1e-4
    handles = {}
    for ax, m in zip(axs[0], avail):
        st = read_csv(f"zic_states_{m}.csv")
        st = [s for s in st if s["level"] in ("hi", "lo")]  # states at S_a,c and S_a,lo
        rec = [s for s in st if not s["committed"]]
        com_hi = [s for s in st if s["committed"] and s["level"] == "hi"]
        com_lo = [s for s in st if s["committed"] and s["level"] == "lo"]

        def xy(ss):
            return (np.array([100 * s["inst_max_sdr"] for s in ss]),
                    np.maximum(np.array([s["ke_norm"] for s in ss]), floor))

        x, y = xy(rec)
        handles["rec"] = ax.scatter(x, y, s=5, marker="o", facecolors="none", edgecolors=fs.RECOVER,
                                    linewidths=0.5, alpha=0.8, zorder=3)
        x, y = xy(com_hi)
        handles["hi"] = ax.scatter(x, y, s=7, marker="^", color=fs.COMMIT, linewidths=0, alpha=0.7, zorder=4)
        if com_lo:
            x, y = xy(com_lo)
            handles["lo"] = ax.scatter(x, y, s=14, marker="^", facecolors="none", edgecolors=fs.COMMIT,
                                       linewidths=0.8, zorder=5)
        ax.set_yscale("log")
        ax.set_xlabel("Peak story drift at release (%)")
        ax.set_title(f"{fs.FRAME_LABEL[m]} ({'development' if m == 'SMF4B' else 'hold-out'}): "
                     f"{len(rec)} recoverable, {len(com_hi)} + {len(com_lo)} committed", fontsize=7)
        if cl:
            ts, ka = 100 * cl["theta_s"], cl["kappa"]
            ax.plot([ts, ts], [floor * 0.8, ka], color=fs.INK, lw=0.9, ls="--", zorder=6)
            ax.plot([0, ts], [ka, ka], color=fs.INK, lw=0.9, ls="--", zorder=6)
        ax.set_ylim(floor * 0.8, 30)
        ax.set_xlim(0, 15)
    axs[0][0].set_ylabel("Kinetic energy / $W_b$")
    for ax, lab in zip(axs[0], "ab"):
        fs.panel_label(ax, f"({lab})")
    labels = {"rec": "recoverable", "hi": "committed (collapse histories)",
              "lo": "committed, rescued by the subsequent input (surviving histories)"}
    hl = [handles[k] for k in ("rec", "hi", "lo") if k in handles]
    ll = [labels[k] for k in ("rec", "hi", "lo") if k in handles]
    if cl:
        from matplotlib.lines import Line2D
        hl.append(Line2D([], [], color=fs.INK, lw=0.9, ls="--"))
        ll.append(f"two-branch rule fitted on (a): $\\theta \\geq {100 * cl['theta_s']:.1f}$% or "
                  f"KE $\\geq {cl['kappa']:.1f}\\,W_b$")
    fig.legend(hl, ll, loc="upper center", ncol=2, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 1.0),
               handletextpad=0.4, columnspacing=1.5)
    fig.tight_layout(w_pad=1.0, rect=(0, 0, 1, 0.88))
    fig.savefig(FIG / "fig5_state_map.pdf")
    fig.savefig(FIG / "fig5_state_map.png", dpi=300)


def ecdf(ax, v, color, label, marker=None, lw=1.2, ls="-", zorder=3):
    v = np.sort(np.asarray([x for x in v if x is not None], dtype=float))
    if len(v) == 0:
        return
    p = (np.arange(1, len(v) + 1) - 0.5) / len(v)
    ax.step(v, p, where="post", color=color, lw=lw, ls=ls, label=label, zorder=zorder)


def fig6(models=("SMF4B", "SMF8B")):
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator

    ida = read_csv("ida_records.csv")
    t95 = {}
    for m in models:
        for r in read_csv(f"t95_records_{m}.csv"):
            t95[(m, r["rid"])] = r
    fs.apply()
    fig, axs = plt.subplots(1, len(models), figsize=(fs.DOUBLE, 0.36 * fs.DOUBLE), sharey=True)
    for ax, m in zip(np.atleast_1d(axs), models):
        sub = [r for r in ida if r["model"] == m and r["S_hi"] is not None]
        tt = [t95[(m, r["rid"])]["S_hi_t95"] for r in sub if (m, r["rid"]) in t95]
        if tt:
            ecdf(ax, tt, fs.ORANGE, "record truncated at $t_{95}$ + free vibration", lw=1.3, zorder=3)
        ecdf(ax, [r["S_hi"] for r in sub], fs.INK, "complete record + free vibration", lw=1.3, zorder=4)
        ecdf(ax, [r["S_hi_trunc"] for r in sub], fs.BLUE, "analysis stopped at record end", lw=1.1, ls=(0, (3, 2)),
             zorder=5)
        ax.set_xscale("log")
        ticks = [0.3, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0]
        lo_, hi_ = ax.get_xlim()
        ax.xaxis.set_major_locator(FixedLocator([v for v in ticks if lo_ <= v <= hi_]))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Collapse intensity $S_a(T_1)$ (g)")
        ax.set_title(fs.FRAME_LABEL[m], fontsize=7.5)
        ax.legend(loc="lower right", fontsize=6)
    np.atleast_1d(axs)[0].set_ylabel("Fraction of records collapsed")
    for ax, lab in zip(np.atleast_1d(axs), "ab"):
        fs.panel_label(ax, f"({lab})")
    fig.tight_layout(w_pad=1.0)
    fig.savefig(FIG / "fig6_truncation.pdf")
    fig.savefig(FIG / "fig6_truncation.png", dpi=300)


def fig7():
    """Effect of intensity (4-story bare, 1.5 S_a,c) and of composite action + gravity framing (4-story, FF)."""
    ida = read_csv("ida_records.csv")
    z4 = [r for r in read_csv("zic_records_SMF4B.csv") if r["status"] == "ok"]
    zcg = [r for r in read_csv("zic_records_SMF4CG.csv") if r["status"] == "ok" and r["level"] == "hi"]
    hi = [r for r in z4 if r["level"] == "hi"]
    x15 = [r for r in z4 if r["level"] == "x15"]
    if not x15 and not zcg:
        return
    light = "#6da7ec"
    groups, cols, rows_, pos, blocks = [], [], [], [], []
    if x15:
        groups += [f"$S_{{a,c}}$\n(n={len(hi)})", f"$1.5S_{{a,c}}$\n(n={len(x15)})"]
        cols += [fs.BLUE, light]
        rows_ += [hi, x15]
        pos += [0, 1]
        blocks.append((0.5, "bare, all records"))
    if zcg:
        hff = [r for r in hi if r["set"] == "FF"]
        off = 2.6 if x15 else 0
        groups += [f"bare\n(n={len(hff)})", f"CG\n(n={len(zcg)})"]
        cols += [fs.BLUE, fs.AQUA]
        rows_ += [hff, zcg]
        pos += [off, off + 1]
        blocks.append((off + 0.5, "$S_{a,c}$, far field"))
    fs.apply()
    ncol = 3 if zcg else 2
    fig, axs = plt.subplots(1, ncol, figsize=(fs.DOUBLE, 0.38 * fs.DOUBLE),
                            gridspec_kw={"width_ratios": [1.6, 1.6, 0.9][:ncol]})
    strip(axs[0], groups, [[100 * r["star_inst_sdr"] for r in rr] for rr in rows_], cols,
          "Peak story drift at $t^*$ (%)", ref=[(10, "")], pos=pos)
    strip(axs[1], groups, [[r["t_star"] - r["t95"] for r in rr] for rr in rows_], cols,
          "$t^* - t_{95}$ (s)", ref=[(0, "")], fmt="{:+.1f}", pos=pos)
    from matplotlib.transforms import blended_transform_factory
    for ax in axs[:2]:
        if x15 and zcg:
            ax.axvline(1.8, color=fs.AXIS, lw=0.6)
        tr = blended_transform_factory(ax.transData, ax.transAxes)
        for xc, head in blocks:
            ax.text(xc, 1.01, head, transform=tr, ha="center", va="bottom", fontsize=6.5, color=fs.INK2)
    if zcg:
        # the frames have different T1, so collapse capacities are compared through the record scale factors
        fb = {r["rid"]: r["scale_hi"] for r in ida if r["model"] == "SMF4B" and r.get("scale_hi") is not None}
        fc = {r["rid"]: r["scale_hi"] for r in ida if r["model"] == "SMF4CG" and r.get("scale_hi") is not None}
        ratio = [fc[k] / fb[k] for k in sorted(set(fb) & set(fc))]
        strip(axs[2], [f"CG / bare, FF\n(n={len(ratio)})"], [ratio], [fs.AQUA],
              "Ratio of collapse scale factors", ref=[(1.0, "")], fmt="{:.2f}")
    for ax, lab in zip(axs, "abc"):
        fs.panel_label(ax, f"({lab})")
    fig.tight_layout(w_pad=1.2)
    fig.savefig(FIG / "fig7_robustness.pdf")
    fig.savefig(FIG / "fig7_robustness.png", dpi=300)


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    which = sys.argv[1:] or ["4", "5", "6", "7"]
    if "4" in which:
        fig4()
    if "5" in which:
        fig5()
    if "6" in which:
        fig6()
    if "7" in which:
        fig7()
    print("ok")
