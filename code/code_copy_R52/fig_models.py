"""Table 1 (members), Table 2 (model properties) and Fig. 2 (pushover curves)."""
from __future__ import annotations

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
MAN = HERE.parent / "manuscript"
KIP_KN = 4.4482216

# SMF member sizes and doubler plates (mm) from the model package documentation (Table 1)
MEMBERS = {
    "4": [(4, "W21$\\times$57", "W24$\\times$62", "W24$\\times$62", "0", "7.9"),
          (3, "W21$\\times$57", "W24$\\times$103$^{a}$", "W24$\\times$103$^{a}$", "0", "7.9"),
          (2, "W21$\\times$73", "W24$\\times$103", "W24$\\times$103", "0", "7.9"),
          (1, "W21$\\times$73", "W24$\\times$103", "W24$\\times$103", "0", "7.9")],
    "8": [(8, "W21$\\times$68", "W24$\\times$94", "W24$\\times$94", "0", "7.9"),
          (7, "W24$\\times$84", "W24$\\times$131", "W24$\\times$131", "0", "14.3"),
          (6, "W24$\\times$84", "W24$\\times$131", "W24$\\times$131", "0", "11.1"),
          (5, "W27$\\times$94", "W24$\\times$131", "W24$\\times$176", "0", "14.3"),
          (4, "W27$\\times$94", "W24$\\times$131", "W24$\\times$176", "0", "7.9"),
          (3, "W30$\\times$116", "W24$\\times$146", "W24$\\times$192", "1.6", "15.9"),
          (2, "W30$\\times$116", "W24$\\times$146", "W24$\\times$192", "1.6", "11.1"),
          (1, "W30$\\times$108", "W24$\\times$146", "W24$\\times$192", "0", "9.5")],
}


def table_members() -> str:
    rows = []
    for nst in ("4", "8"):
        rows.append(f"\\multicolumn{{6}}{{@{{}}l}}{{\\textit{{{nst}-story SMF}}}}\\\\")
        for st, beam, ce, ci, de, di in MEMBERS[nst]:
            rows.append(f"{st} & {beam} & {ce} & {ci} & {de} & {di}\\\\")
    body = "\n".join(rows)
    return r"""\begin{table}[!tbp]
\centering
\caption{SMF member sizes and panel-zone doubler-plate thicknesses of the archetypes (from the model documentation \cite{ElkadyModels2019}). The beam of story $i$ is at floor $i+1$.}
\label{tab:members}
\small
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{@{}cccccc@{}}
\toprule
Story & Beam (RBS) & Exterior column & Interior column & \multicolumn{2}{c}{Doubler plate (mm)}\\
\cmidrule(l){5-6}
 & & & & Exterior & Interior\\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}
\end{adjustbox}

\smallskip
\footnotesize $^{a}$ Spliced to W24$\times$62 at mid-height of the third story.
\end{table}
"""


def table_props(mc: dict) -> str:
    lines = []
    for m in ("SMF4B", "SMF4CG", "SMF8B", "SMF8CG"):
        r = mc[m]
        T = r["periods"]
        zero = "--$^{b}$" if r["roof_drift_zero_V"] is None else f"{100 * r['roof_drift_zero_V']:.1f}"
        lines.append(
            f"{fs.FRAME_LABEL[m]} & {T[0]:.2f} & {T[1]:.2f} & {r['W_mass_kip'] * KIP_KN / 1000:.1f} & "
            f"{r['Vmax_over_W']:.3f} & {r['Omega_static']:.1f} & {100 * r['roof_drift_at_Vmax']:.1f} & {zero}\\\\")
    return r"""\begin{table}[!tbp]
\centering
\caption{Properties of the four models: first two periods, seismic weight $W$ of the planar model, peak base shear $V_{\max}$ of the first-mode pushover, static overstrength $\Omega$ relative to the ASCE 7-10 design base shear, roof drift ratio at $V_{\max}$ and roof drift ratio at which the lateral resistance vanishes.}
\label{tab:props}
\small
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{@{}lccccccc@{}}
\toprule
Model & $T_1$ (s) & $T_2$ (s) & $W$ (MN) & $V_{\max}/W$ & $\Omega$ & \makecell{Roof drift at\\$V_{\max}$ (\%)} & \makecell{Roof drift at\\$V = 0$ (\%)}\\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}

\smallskip
\footnotesize $^{b}$ The static solution of the CG models ends at 3.6\% (4-story) and 2.4\% (8-story) roof drift, when the composite shear-tab connections of the gravity frame reach the abrupt strength drop of their backbone; the dynamic analyses are not affected.
\end{table}
"""


def fig_pushover(mc: dict) -> None:
    fs.apply()
    fig, ax = plt.subplots(figsize=(fs.SINGLE * 1.25, 0.62 * fs.SINGLE * 1.25))
    for m in ("SMF4B", "SMF8B", "SMF4CG", "SMF8CG"):
        r = mc[m]
        c = np.array(r["curve"])
        W = r["W_mass_kip"]
        ax.plot(100 * c[:, 0], c[:, 1] / W, color=fs.FRAME_COLOR[m], lw=1.3, label=fs.FRAME_LABEL[m])
        k = int(np.argmax(c[:, 1]))
        ax.plot(100 * c[k, 0], c[k, 1] / W, marker=fs.FRAME_MARK[m], ms=5, color=fs.FRAME_COLOR[m],
                mec="white", mew=0.8, zorder=4)
        if r["roof_drift_zero_V"] is not None:
            ax.plot(100 * r["roof_drift_zero_V"], 0.0, marker="o", ms=3.5, mfc="white", mec=fs.FRAME_COLOR[m], mew=1.0, zorder=5)
            ax.annotate(f"{100 * r['roof_drift_zero_V']:.1f}%", (100 * r["roof_drift_zero_V"], 0.0),
                        xytext=(-5, -10), textcoords="offset points", ha="right", fontsize=6.5, color=fs.INK2)
        else:
            ax.plot(100 * c[-1, 0], c[-1, 1] / W, marker="x", ms=4.5, color=fs.FRAME_COLOR[m], mew=1.1, zorder=5)
    ax.axhline(0, color=fs.AXIS, lw=0.8)
    ax.set_xlabel("Roof drift ratio (%)")
    ax.set_ylabel("Base shear / $W$")
    ax.set_xlim(0, 12.5)
    ax.legend(loc="upper right", ncol=2, handlelength=1.6)
    fig.savefig(FIG / "fig2_pushover.pdf")
    fig.savefig(FIG / "fig2_pushover.png", dpi=300)


if __name__ == "__main__":
    mc = json.loads((RES / "model_checks.json").read_text())
    FIG.mkdir(exist_ok=True)
    (MAN / "tab_members.tex").write_text(table_members(), encoding="utf-8")
    (MAN / "tab_props.tex").write_text(table_props(mc), encoding="utf-8")
    fig_pushover(mc)
    print("ok")
