"""Shared figure style (Elsevier print: sans serif, thin marks, hairline grid).

Categorical slots follow the validated reference palette (slots 1-4 pass the
adjacent-pair CVD checks; slots 1-3 pass all pairs).  Identity is never colour
alone: every series also carries a marker shape and a legend/direct label.
"""
from __future__ import annotations

import matplotlib as mpl

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA, YELLOW, RED, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948", "#4a3aa7"
FRAME_COLOR = {"SMF4B": BLUE, "SMF8B": ORANGE, "SMF4CG": AQUA, "SMF8CG": YELLOW}
FRAME_MARK = {"SMF4B": "o", "SMF8B": "s", "SMF4CG": "^", "SMF8CG": "D"}
FRAME_LABEL = {"SMF4B": "4-story bare", "SMF8B": "8-story bare", "SMF4CG": "4-story CG", "SMF8CG": "8-story CG"}
COMMIT, RECOVER = RED, BLUE
MM = 1 / 25.4
SINGLE, DOUBLE = 90 * MM, 190 * MM


def apply() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.titlesize": 8,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.4,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "lines.linewidth": 1.2,
        "lines.markersize": 4,
        "legend.frameon": False,
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def panel_label(ax, text: str) -> None:
    ax.text(-0.02, 1.02, text, transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            fontweight="bold", color=INK)
