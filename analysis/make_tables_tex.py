"""Generate manuscript/tables.tex: Table 1 (frame properties) + Table 2 (per-frame law)."""
import json
from pathlib import Path

MC_CAND = [Path(r"E:\n0r53\results\model_checks.json"),
           Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R52_N0_ZERO_INPUT_COMMITMENT_2026-10-11\results\model_checks.json")]
S = json.loads(Path(r"E:\n0r53\analysis\summary_by_frame.json").read_text())
mc = {}
for p in MC_CAND:
    if p.exists():
        for k, v in json.loads(p.read_text()).items():
            mc.setdefault(k, v)
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
WORD = {"SMF2B": "TwoB", "SMF2CG": "TwoCG", "SMF4B": "FourB", "SMF4CG": "FourCG", "SMF8B": "EightB",
        "SMF8CG": "EightCG", "SMF12B": "TwelveB", "SMF12CG": "TwelveCG", "SMF20B": "TwentyB", "SMF20CG": "TwentyCG"}
LBL = {"SMF2B": "2, bare", "SMF2CG": "2, composite+gravity", "SMF4B": "4, bare", "SMF4CG": "4, composite+gravity",
       "SMF8B": "8, bare", "SMF8CG": "8, composite+gravity", "SMF12B": "12, bare", "SMF12CG": "12, composite+gravity",
       "SMF20B": "20, bare", "SMF20CG": "20, composite+gravity"}

L = []
L.append(r"\begin{table}[p]")
L.append(r"\centering")
L.append(r"\caption{\textbf{Archetype frames.} First-mode period $T_1$, seismic weight $W$, peak base-shear coefficient $V_{\max}/W$ and intact first-mode pushover work to peak resistance $W_b$. The composite-and-gravity (CG) variants add slab action and deteriorating gravity-frame connections; their intact pushover does not reach zero resistance within the analysis window (drift-limited), so $W_b$ is the work to the peak.}")
L.append(r"\label{tab:models}")
L.append(r"\begin{tabular}{llrrrr}")
L.append(r"\toprule")
L.append(r"frame & $T_1$ (s) & $W$ (kip) & $V_{\max}/W$ & $W_b$ (kip-in) \\")
L.append(r"\midrule")
for m in MODELS:
    d = mc.get(m)
    if not d:
        continue
    t1 = d["periods"][0]; w = d["W_mass_kip"]; vw = d["Vmax_over_W"]
    wb = d.get("work_to_zero_V_kipin") or d.get("work_to_peak_kipin")
    L.append(f"{LBL[m]} & {t1:.2f} & {w:,.0f} & {vw:.3f} & {wb:,.0f} \\\\")
L.append(r"\bottomrule")
L.append(r"\end{tabular}")
L.append(r"\end{table}")
L.append("")

L.append(r"\begin{table}[p]")
L.append(r"\centering")
L.append(r"\caption{\textbf{The energy law per frame.} On the transition states (last recoverable and first committed releases), medians with 95\% bootstrap confidence intervals over components. $c_f=E_{\mathrm{crit}}/W_{\mathrm{rem}}$ damped; $c^0_f=E^0_{\mathrm{crit}}/W_{\mathrm{rem}}$ undamped, with the barrier $W_{\mathrm{rem}}$ measured to the collapse surface (Methods). `d/e/s/t' counts the transition states whose barrier ends at the drift limit (d), at the resistance edge (e), with the solver stalled after the load factor had fallen below 1\% of its peak (s; at the edge for practical purposes, work complete), or before either exit with resistance remaining (t; lower-bound barrier and hence upper-bound ratio). Where available (4CG, 8CG and the 12- and 20-storey frames) the barrier is taken from the first-mode push extended to 0.16 roof drift (addendum A8). Accuracy: the rule `committed iff KE $\ge c_{\mathrm{dev}}W_{\mathrm{rem}}$' with $c_{\mathrm{dev}}=\cdev$ fixed on the development frame (E), the development-fitted drift threshold on the same states (drift), and each frame's own best drift threshold as an oracle bound (drift$^\ast$). The 12- and 20-storey frames are scored on the far-field set; the composite 2-storey set is thin.}")
L.append(r"\label{tab:law}")
L.append(r"\footnotesize")
L.append(r"\begin{tabular}{llccccc}")
L.append(r"\toprule")
L.append(r"frame & $n$ & $c_f$ [95\% CI] & $c^0_f$ [95\% CI] & exits d/e/s/t & acc.\ E / D / D$^\ast$ (\%) \\")
L.append(r"\midrule")
for m in MODELS:
    w = WORD[m]
    setl = "FF" if m in ("SMF12B", "SMF12CG", "SMF20B", "SMF20CG") else "All"
    L.append(f"{LBL[m]} & \\nTransC{w}{setl} & \\cc{w}{setl}~[\\ccLo{w}{setl},\\ccHi{w}{setl}] & "
             f"\\czeroc{w}{setl}~[\\czerocLo{w}{setl},\\czerocHi{w}{setl}] & "
             f"\\limDrift{w}{setl}/\\limEdge{w}{setl}/\\limStall{w}{setl}/\\limTrunc{w}{setl} & \\accWcDev{w}{setl}/\\accDrift{w}{setl}/\\accDriftOwn{w}{setl} \\\\")
L.append(r"\bottomrule")
L.append(r"\end{tabular}")
L.append(r"\end{table}")

out = Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21\manuscript\tables.tex")
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
