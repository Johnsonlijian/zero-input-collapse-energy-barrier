"""Fig. 3 - one collapse history with zero-input continuations around t*.

Re-runs the reference history and a few releases of one record with full
histories (the campaign stores outcomes only) and caches them in
results/fig3_<model>_<rid>.npz.  Usage:
    python fig_example.py SMF4B FF121421
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fig_style as fs  # noqa: E402
from records import arias_times, load_all  # noqa: E402

RUNS = Path(os.environ.get("N0R52_RUNS", r"E:\n0r52\runs"))
FIG = HERE.parent / "figures"
RES = HERE.parent / "results"


def simulate(model: str, rid: str, cache: Path) -> dict:
    from driver import Frame

    rec = load_all()[rid]
    z = json.loads((RUNS / "zic" / model / f"{rid}__hi.json").read_text())
    ida = json.loads((RUNS / "ida" / model / f"{rid}.json").read_text())
    scale = z["sa"] / ida["sa_unscaled"]
    ts, ta, tc = z["t_star"], z["t_a"], z["ref"]["t_coll"]
    fr = Frame(model)
    dta = min(rec.dt, 0.005)
    ref = fr.run(rec.acc, rec.dt, scale, rec.duration + 30, dt_anal=dta, keep_history=True, hist_every=0.02)
    data = {"t_ref": np.array(ref["hist_t"]), "d_ref": np.array(ref["hist_d"]), "scale": scale,
            "ts": ts, "ta": ta, "tc": tc}
    rel = sorted({round(ta - 4.0, 4), round(ta - 1.0, 4), ta, ts})
    for i, t_r in enumerate(rel):
        r = fr.run(rec.acc, rec.dt, scale, t_r + 30, t_release=t_r, dt_anal=dta, keep_history=True, hist_every=0.02)
        tt = np.array(r["hist_t"])
        m = tt >= t_r - 1e-9
        data[f"c{i}_t"] = tt[m]
        data[f"c{i}_d"] = np.array(r["hist_d"])[m]
        data[f"c{i}_tr"] = t_r
        data[f"c{i}_status"] = r["status"]
    np.savez_compressed(cache, **data)
    return dict(np.load(cache, allow_pickle=True))


def main(model: str, rid: str) -> None:
    rec = load_all()[rid]
    cache = RES / f"fig3_{model}_{rid}.npz"
    data = dict(np.load(cache, allow_pickle=True)) if cache.exists() else simulate(model, rid, cache)
    ts, ta, tc = float(data["ts"]), float(data["ta"]), float(data["tc"])
    scale = float(data["scale"])
    t_ref, d_ref = data["t_ref"], data["d_ref"]
    k = int(np.argmax(np.abs(d_ref).max(axis=0)))
    sgn = np.sign(d_ref[np.argmax(np.abs(d_ref[:, k])), k])
    t5, t95, _ = arias_times(rec.acc, rec.dt)
    conts = []
    i = 0
    while f"c{i}_t" in data:
        conts.append((float(data[f"c{i}_tr"]), data[f"c{i}_t"], data[f"c{i}_d"][:, k], str(data[f"c{i}_status"])))
        i += 1

    fs.apply()
    fig = plt.figure(figsize=(fs.DOUBLE, 0.42 * fs.DOUBLE))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0], height_ratios=[1, 2.2], wspace=0.22, hspace=0.28)
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[1, 0], sharex=ax0)
    ax2 = fig.add_subplot(gs[:, 1])
    tg = np.arange(len(rec.acc)) * rec.dt
    ax0.plot(tg, rec.acc * scale, color=fs.INK2, lw=0.45)
    ax0.set_ylabel("$a_g$ (g)")
    plt.setp(ax0.get_xticklabels(), visible=False)
    ax1.plot(t_ref, 100 * sgn * d_ref[:, k], color=fs.INK, lw=0.9)
    for ax in (ax0, ax1):
        for tv in (t95, rec.duration):
            ax.axvline(tv, color=fs.MUTED, lw=0.7)
        ax.axvline(ts, color=fs.COMMIT, lw=0.8)
    ymax = 16.0
    ax1.axhline(10, color=fs.MUTED, lw=0.6)
    ax1.axhline(15, color=fs.MUTED, lw=0.6)
    ax1.set_ylim(min(-2.0, 100 * np.min(sgn * d_ref[:, k]) - 1), ymax)
    ax1.set_xlim(0, rec.duration + 5)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel(f"Story {k + 1} drift (%)")
    ytop = ax0.get_ylim()[1]
    ax0.text(t95, ytop * 0.95, " $t_{95}$", fontsize=6.5, color=fs.INK2, va="top")
    ax0.text(rec.duration, ytop * 0.95, " end", fontsize=6.5, color=fs.INK2, va="top")
    ax0.text(ts, ytop * 0.95, " $t^*$", fontsize=6.5, color=fs.COMMIT, va="top")
    fs.panel_label(ax0, "(a)")
    fs.panel_label(ax1, "(b)")
    # zoom
    z0, z1 = ta - 5.0, tc + 4.0
    m = (t_ref >= z0) & (t_ref <= z1)
    ax2.plot(t_ref[m], 100 * sgn * d_ref[m, k], color=fs.INK, lw=1.1, label="full record", zorder=5)
    light = ["#9ec5f4", "#6da7ec"]
    j = 0
    for t_r, tt, dd, st in conts:
        mm = tt <= z1 + 6
        if abs(t_r - ts) < 1e-6:
            ax2.plot(tt[mm], 100 * sgn * dd[mm], color=fs.COMMIT, lw=1.3, zorder=6,
                     label=f"zero input from $t^*$ = {ts:.3f} s")
        elif abs(t_r - ta) < 1e-6:
            ax2.plot(tt[mm], 100 * sgn * dd[mm], color=fs.RECOVER, lw=1.3, zorder=6,
                     label=f"zero input from $t_a$ = {ta:.3f} s")
        else:
            ax2.plot(tt[mm], 100 * sgn * dd[mm], color=light[j % 2], lw=1.0, zorder=4,
                     label="zero input, earlier releases" if j == 0 else None)
            j += 1
        ax2.plot(t_r, 100 * sgn * dd[0], marker="o", ms=3.2, mfc="white",
                 mec=fs.COMMIT if abs(t_r - ts) < 1e-6 else fs.RECOVER, mew=0.9, zorder=7)
    ax2.axhline(10, color=fs.MUTED, lw=0.6)
    ax2.axhline(15, color=fs.MUTED, lw=0.6)
    ax2.text(z1 + 5.5, 9.85, "10%", fontsize=6.5, color=fs.INK2, ha="right", va="top")
    ax2.text(z1 + 5.5, 14.85, "15% (collapse)", fontsize=6.5, color=fs.INK2, ha="right", va="top")
    ax2.set_xlim(z0, z1 + 6)
    lo = 100 * np.min(sgn * d_ref[m, k]) - 1.0
    # head room above the collapse limit keeps the legend clear of the curves (all stop at 15 %)
    ax2.set_ylim(max(lo, 0.0), 18.3)
    ax2.set_yticks([t for t in range(int(np.ceil(max(lo, 0.0))), 16)])
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel(f"Story {k + 1} drift (%)")
    ax2.legend(loc="upper left", fontsize=6.5, handlelength=1.6, borderaxespad=0.3)
    fs.panel_label(ax2, "(c)")
    fig.savefig(FIG / "fig3_example.pdf")
    fig.savefig(FIG / "fig3_example.png", dpi=300)
    meta = {"model": model, "rid": rid, "t_star": ts, "t_a": ta, "t_c": tc, "t95": t95, "duration": rec.duration,
            "critical_story": k + 1, "scale": scale,
            "continuations": {f"{t:.3f}": {"status": st, "max_abs_drift": float(np.max(np.abs(dd)))}
                              for t, _, dd, st in conts}}
    (RES / "fig3_example_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["SMF4B", "FF121421"]))
