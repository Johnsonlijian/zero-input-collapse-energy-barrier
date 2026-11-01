"""Supplementary tables for A7 (energy budget) and A6 (residual capacity).
Writes manuscript/table_budget.tex and manuscript/table_residual.tex from
analysis/kick_energy_analysis.json and analysis/aftershock_analysis.json.
Rows appear only for frames with data, so the tables never reference undefined macros."""
import json
from pathlib import Path

A = Path(r"/mnt/e/n0r53/analysis")
MS = Path(r"/mnt/w/01_PROJECTS/NAS_DRIVE/IMUT/1-Research_Output/1-Papers/1_In_Preparation/ai_civil_slate_codex_goal_gate"
          r"/rounds/R53_N0_TOPTIER_REBUILD_2026-10-21/manuscript")
LAB = {"SMF2B": "2B", "SMF2CG": "2CG", "SMF4B": "4B", "SMF4CG": "4CG", "SMF8B": "8B", "SMF8CG": "8CG",
       "SMF12B": "12B", "SMF12CG": "12CG", "SMF20B": "20B", "SMF20CG": "20CG"}
ORDER = ["SMF2B", "SMF4B", "SMF8B", "SMF4CG", "SMF8CG"]


def jl(name):
    p = A / name
    return json.loads(p.read_text()) if p.exists() else {}


def mci(s, nd=2):
    return f"{s['median']:.{nd}f} [{s['ci95'][0]:.{nd}f}, {s['ci95'][1]:.{nd}f}]" if s else "--"


def med(s, nd=2):
    return f"{s['median']:.{nd}f}" if s else "--"


# ---------------------------------------------------------------- A7 budget
ke = jl("kick_energy_analysis.json")
L = [r"\begin{table}[h]", r"/centering", r"/footnotesize",
     r"\caption{Energy budget of the critical escape (addendum A7). At the kinetic-energy minimum before "
     r"collapse on the committed continuation just above $\beta_{\mathrm{crit}}$: internal work $W_{\mathrm{int}}$, "
     r"Rayleigh-viscous work $W_{\mathrm{visc}}$ and remaining kinetic energy, each divided by $W_{\mathrm{rem}}$ of "
     r"the same state; medians with 95\% event-cluster intervals. $c$ and $c^0$ are the damped and undamped "
     r"coefficients of the same states; $r$ is the state-wise correlation between $W_{\mathrm{visc}}/W_{\mathrm{rem}}$ "
     r"and $c-c^0$. Source: \texttt{analysis/kick\_energy\_analysis.json}.}",
     r"\label{tab:sbudget}", r"\begin{tabular}{lrccccccc}", r"/toprule",
     r"Frame & $n$ & $c$ & $c^0$ & $W_{\mathrm{int}}/W_{\mathrm{rem}}$ & $W_{\mathrm{visc}}/W_{\mathrm{rem}}$ & "
     r"KE$/W_{\mathrm{rem}}$ & $c-c^0$ & $r$ \\", r"/midrule"]
for m in ORDER:
    s = (ke.get(m) or {}).get("summary")
    if not s or not s.get("a_int"):
        continue
    r = s.get("toll_corr")
    L.append(f"{LAB[m]} & {s['a_int']['n']} & {med(s['c'])} & {med(s.get('c0'))} & {mci(s['a_int'])} & "
             f"{mci(s['b_visc'])} & {med(s['k_ke'])} & {med(s.get('toll_inferred'))} & "
             f"{'--' if r is None else f'{r:.2f}'} \\\\")
L += [r"/bottomrule", r"\end{tabular}", r"\end{table}", ""]
(MS / "table_budget.tex").write_text("\n".join(L), encoding="utf-8")

# ---------------------------------------------------------------- A6 residual capacity
af = jl("aftershock_analysis.json")
TAGS = [("q0.50", r"mainshock $0.50\,S_{a,c}$"), ("q0.70", r"mainshock $0.70\,S_{a,c}$"),
        ("q0.85", r"mainshock $0.85\,S_{a,c}$"), ("q0.95", r"mainshock $0.95\,S_{a,c}$"),
        ("early1", "halted, earliest recoverable"), ("early2", "halted, second recoverable"),
        ("ta", r"halted at $t_a$")]
L = []
s4 = (af.get("SMF4B") or {}).get("summary")
if s4:
    rows4 = af["SMF4B"]["rows"]
    L += [r"\begin{table}[h]", r"/centering", r"/footnotesize",
          r"\caption{Residual capacity of settled damaged states of SMF4B by damage family (medians). "
          r"$w=W_{\mathrm{set}}/W_{\mathrm{int}}$; $R=S^{\mathrm{dam}}_{a,c}/S_{a,c}$; `floor': states collapsing "
          r"below $0.05\,S_{a,c}$, entered at $R=0.04$. Source: \texttt{analysis/aftershock\_analysis.json}.}",
          r"\label{tab:sres4b}", r"\begin{tabular}{lrrccccc}", r"/toprule",
          r"Damaged state & $n$ & floor & peak drift (\%) & residual drift (\%) & $w$ & $R$ & $R/w$ \\",
          r"/midrule"]
    for t, lab in TAGS:
        v = s4["by_tag"].get(t)
        if not v:
            continue
        nfl = sum(1 for r in rows4 if r["tag"] == t and r["status"] == "collapse_at_floor")
        L.append(f"{lab} & {v['n']} & {nfl} & {100 * v['peak_med']:.1f} & {100 * v['res_med']:.1f} & "
                 f"{v['w_med']:.3f} & {v['R_med']:.3f} & {v['R_over_w_med']:.2f} \\\\")
    L += [r"/bottomrule", r"\end{tabular}", r"\end{table}", ""]

MIN_EVENTS = 0           # all campaign frames are tabulated; the n (ev.) column exposes event coverage


def _own(m):
    return (((af.get(m) or {}).get("summary") or {}).get("ms_sub") or {}).get("own") or {}


RES_ORDER = ["SMF2B", "SMF4B", "SMF8B", "SMF12B", "SMF20B", "SMF2CG", "SMF4CG", "SMF8CG", "SMF12CG", "SMF20CG"]
fr = [m for m in RES_ORDER if _own(m).get("pred") and _own(m)["n_events"] >= MIN_EVENTS]
if fr:
    L += [r"\begin{table}[h]", r"/centering", r"/footnotesize",
          r"\caption{Mainshock-damaged states: retained capacity against damage indicators, per frame, on the "
          r"states where $w$ is a measured ratio (settled and intact pushes in the same direction both reach an "
          r"exit; addendum A12; the excluded states are analysed in Table~\ref{tab:sressens}). "
          r"$R/w$: median and 10th--90th percentile. Log-error: root-mean-square error "
          r"of $\log R$ for the calibration-free prediction $\hat R=w$ and for log-linear maps fitted with "
          r"leave-one-event-out cross-validation on $w$, residual storey drift (res), residual roof drift (roof), "
          r"peak storey drift (peak) and mainshock intensity ($q$); $\Delta$: RMSE of the fitted $w$ map minus that "
          r"of the fitted residual-drift map, event-cluster 95\% interval. Partial rank correlations of $R$ with $w$ "
          r"at fixed residual drift and with residual drift at fixed $w$, with event-cluster 95\% intervals.}",
          r"\label{tab:sresframes}", r"/scriptsize", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{lrcccccccccc}", r"/toprule",
          r" & & & \multicolumn{7}{c}{log-error of $R$} & \multicolumn{2}{c}{partial rank corr.} \\",
          r"\cmidrule(lr){4-10}\cmidrule(lr){11-12}",
          r"Frame & $n$ (ev.) & $R/w$ & $w$, no fit & $w$ & res & roof & peak & $q$ & $\Delta$ & $w\,|\,$res & res$\,|\,w$ \\",
          r"/midrule"]
    for m in fr:
        o = _own(m)
        rw, pr, pp = o["R_over_w"], o["pred"]["rmse"], o["partial"]
        dci = o["pred"]["d_rmse_ci95"]["w_fitted_cv_minus_res_fitted_cv"]

        def pci(k):
            if k not in pp or not all(x == x for x in pp[k + "_ci95"]):
                return "--"
            return f"{pp[k]:.2f} [{pp[k + '_ci95'][0]:.2f}, {pp[k + '_ci95'][1]:.2f}]"
        L.append(f"{LAB[m]} & {o['n_unc']} ({o['n_events']}) & {rw['median']:.2f} [{rw['p10']:.2f}, {rw['p90']:.2f}] & "
                 f"{pr['w_zero_param']:.2f} & {pr['w_fitted_cv']:.2f} & {pr['res_fitted_cv']:.2f} & "
                 f"{pr['roof_fitted_cv']:.2f} & {pr['peak_fitted_cv']:.2f} & {pr['q_fitted_cv']:.2f} & "
                 f"[{dci[0]:.2f}, {dci[1]:.2f}] & {pci('w_given_res')} & {pci('res_given_w')} \\\\".replace("-", "$-$"))
    L += [r"/bottomrule", r"\end{tabular}}", r"\end{table}", ""]

    # sensitivity: all states, mirror normaliser, unresolved (truncated) settled pushes
    L += [r"\begin{table}[h]", r"/centering", r"/footnotesize",
          r"\caption{Sensitivity of the mainshock-damaged comparison to the barrier-resolution rule (addendum A12). "
          r"Own: settled and intact pushes in the same direction both reach an exit (primary, Table~\ref{tab:sresframes}). "
          r"Resolved: settled push reaches an exit; where the intact push in that direction does not, the opposite-direction "
          r"intact barrier is used (the composite frames are not mirror-symmetric, so this normaliser is approximate). "
          r"All: every settled state, truncated pushes entered at the work they reached. Truncated: settled pushes "
          r"stopped by non-convergence before either exit, for which $w$ is a lower bound. "
          r"$\rho$: Spearman correlation of $R$ with $w$ and with (minus) residual drift; partial: $w\,|\,$res and res$\,|\,w$.}",
          r"\label{tab:sressens}", r"\setlength{\tabcolsep}{3.5pt}", r"\begin{tabular}{llrcccccc}", r"/toprule",
          r"Frame & subset & $n$ & $R/w$ & RMSE $w$, no fit & $\rho_w$ & $\rho_{\mathrm{res}}$ & $w\,|\,$res & res$\,|\,w$ \\",
          r"/midrule"]
    for m in fr:
        sb = af[m]["summary"]["ms_sub"]
        first = True
        for key, lab in (("own", "own"), ("resolved", "resolved"), ("all", "all"), ("trunc", "truncated")):
            b = sb.get(key) or {}
            if not b.get("pred"):
                if key == "trunc" and b.get("n"):
                    L.append(f"{'' if not first else LAB[m]} & {lab} & {b['n']} & \\multicolumn{{6}}{{c}}{{too few}} \\\\")
                    first = False
                continue
            row = (f"{'' if not first else LAB[m]} & {lab} & {b['n_unc']} & {b['R_over_w']['median']:.2f} & "
                   f"{b['pred']['rmse']['w_zero_param']:.2f} & {b['rho']['rho_signed']['w']:.2f} & "
                   f"{b['rho']['rho_signed']['res']:.2f} & {b['partial']['w_given_res']:.2f} & "
                   f"{b['partial']['res_given_w']:.2f} \\\\")
            L.append(row.replace("-", "$-$"))
            first = False
        L.append(r"/addlinespace")
    L += [r"/bottomrule", r"\end{tabular}", r"\end{table}", ""]
(MS / "table_residual.tex").write_text("\n".join(L), encoding="utf-8")

# ---------------------------------------------------------------- kinematic alternatives
ka = jl("kinematic_alternatives.json")
ALL10 = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
if ka:
    pr_ = ka["_protocol"]
    L = [r"\begin{table}[h]", r"/centering", r"/footnotesize", r"\setlength{\tabcolsep}{3.5pt}",
         r"\caption{Energy rule versus kinematic rules (accuracy, \%, on the classified released states; 12- and "
         r"20-storey frames far-field). Transfer: constants fitted once on SMF4B far-field and applied unchanged "
         r"--- E, $\mathrm{KE}\ge c_{\mathrm{dev}}W_{\mathrm{rem}}$; D, instantaneous peak storey drift "
         rf"$\ge{100 * pr_['thr_dev']:.1f}\%$; D$_{{\max}}$, running-maximum drift $\ge{100 * pr_['thr_run_dev']:.1f}\%$; "
         r"K2, logistic on peak drift and $\log\mathrm{KE}$; K3, logistic on peak drift, running-maximum drift and "
         r"$\log\mathrm{KE}$. Oracle (cv): each rule refitted per frame and scored by leave-one-event-out "
         r"cross-validation. $\Delta$: paired accuracy difference in percentage points with 95\% event-cluster "
         r"interval. Source: \texttt{analysis/kinematic\_alternatives.json}.}",
         r"\label{tab:skin}", r"\begin{tabular}{lrccccccccc}", r"/toprule",
         r" & & \multicolumn{5}{c}{transfer} & \multicolumn{2}{c}{oracle (cv)} & "
         r"\multicolumn{2}{c}{$\Delta$} \\", r"\cmidrule(lr){3-7}\cmidrule(lr){8-9}\cmidrule(lr){10-11}",
         r"Frame & $n$ & E & D & D$_{\max}$ & K2 & K3 & E & K2 & E$-$K2 & E$-$K2 (cv) \\", r"/midrule"]
    for m in ALL10:
        v = ka.get(m)
        if not v:
            continue
        a, d = v["acc"], v["diff"]

        def dd(k):
            x, lo, hi = (100 * t for t in d[k])
            return f"${x:.1f}$ [${lo:.1f}$, ${hi:.1f}$]"
        L.append(f"{LAB[m]} & {v['n']} & {100 * a['E']:.1f} & {100 * a['D']:.1f} & {100 * a['Drun']:.1f} & "
                 f"{100 * a['K2']:.1f} & {100 * a['K3']:.1f} & {100 * a['E_cv']:.1f} & {100 * a['K2_cv']:.1f} & "
                 f"{dd('E-K2')} & {dd('E_cv-K2_cv')} \\\\")
    L += [r"/bottomrule", r"\end{tabular}", r"\end{table}", ""]
    (MS / "table_kinematic.tex").write_text("\n".join(L), encoding="utf-8")
print("wrote table_budget.tex, table_residual.tex;", "budget frames:",
      [LAB[m] for m in ORDER if (ke.get(m) or {}).get("summary")], "residual frames:", [LAB[m] for m in fr])
