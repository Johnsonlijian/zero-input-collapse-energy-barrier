"""Fig. 1 - zero-input commitment region of a softening oscillator (schematic).

Nonlinear-elastic restoring force with a negative post-yield branch (the net
effect of P-Delta), T = 1.5 s, 2 % damping, yield drift 1 %, post-yield
stiffness ratio -0.08 (static stability limit u_c = 13.5 % drift).  Every
state (u0, v0) on a grid is released with zero input and integrated for 20 s;
it is 'committed' if |u| reaches 25 % drift.  Illustrative only: the frames of
the paper are hysteretic multi-degree-of-freedom models.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fig_style as fs  # noqa: E402

T, ZETA, UY, ALPHA = 1.5, 0.02, 0.01, -0.08
W = 2 * np.pi / T
UC = UY * (1 - 1 / ALPHA)


def force(u):
    a = np.abs(u)
    return np.where(a <= UY, W**2 * u, np.sign(u) * W**2 * (UY + ALPHA * (a - UY)))


def outcome(u0, v0, t_end=20.0, dt=0.002, u_coll=0.25):
    u, v = u0.copy(), v0.copy()
    dead = np.zeros(u.shape, dtype=bool)
    for _ in range(int(t_end / dt)):
        acc = -2 * ZETA * W * v - force(u)
        v = v + dt * acc
        u = u + dt * v
        dead |= np.abs(u) >= u_coll
        u = np.where(dead, np.sign(u) * u_coll, u)
        v = np.where(dead, 0.0, v)
    return dead


def main(out: Path):
    fs.apply()
    du = np.linspace(-0.16, 0.16, 321)
    vmax = 0.30  # drift ratio per second
    dv = np.linspace(-vmax, vmax, 321)
    U, V = np.meshgrid(du, dv)
    dead = outcome(U, V)
    fig, ax = plt.subplots(figsize=(fs.SINGLE, 0.78 * fs.SINGLE))
    ax.contourf(U * 100, V * 100, dead.astype(float), levels=[-0.5, 0.5, 1.5],
                colors=["#dbe8f8", "#f8d9d6"], antialiased=True)
    ax.contour(U * 100, V * 100, dead.astype(float), levels=[0.5], colors=[fs.INK], linewidths=0.9)
    for th in (5, 10):
        for s in (-1, 1):
            ax.axvline(s * th, color=fs.MUTED, lw=0.7)
    for s in (-1, 1):
        ax.axvline(s * UC * 100, color=fs.VIOLET, lw=0.9)
    ax.set_xlim(-16, 16)
    ax.set_ylim(-vmax * 100, vmax * 100)
    ax.set_xlabel("Drift at release, $u$ (%)")
    ax.set_ylabel(r"Velocity at release, $\dot u$ (% per s)")
    ax.text(10.3, 28.5, "10 %\nlimit", color=fs.INK2, fontsize=6.5, va="top")
    ax.text(5.3, 28.5, "5 %\nlimit", color=fs.INK2, fontsize=6.5, va="top")
    ax.text(UC * 100 - 0.3, -28.5, "static\nstability\nlimit", color=fs.VIOLET, fontsize=6.5, va="bottom", ha="right")
    ax.text(-4.6, 1.0, "recoverable", color=fs.BLUE, fontsize=7.5, fontweight="bold")
    ax.text(-15.2, 22.5, "committed", color=fs.RED, fontsize=7.5, fontweight="bold")
    # two illustrative states
    pa, pb = (3.0, 20.0), (8.0, -4.0)
    da = outcome(np.array([pa[0] / 100]), np.array([pa[1] / 100]))[0]
    db = outcome(np.array([pb[0] / 100]), np.array([pb[1] / 100]))[0]
    for (x, y), lab, d in ((pa, "A", da), (pb, "B", db)):
        ax.plot(x, y, marker="o", ms=4.5, mfc=fs.RED if d else fs.BLUE, mec="white", mew=0.8, zorder=5)
        ax.text(x + 0.5, y + 1.2, lab, fontsize=7.5, fontweight="bold", color=fs.INK)
    ax.grid(False)
    fig.savefig(out / "fig1_concept.pdf")
    fig.savefig(out / "fig1_concept.png", dpi=300)
    print("A committed:", bool(da), "B committed:", bool(db), "u_c (%):", UC * 100)


if __name__ == "__main__":
    o = HERE.parent / "figures"
    o.mkdir(exist_ok=True)
    main(o)
