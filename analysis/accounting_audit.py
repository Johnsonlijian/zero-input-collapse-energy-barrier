"""Per-frame accounting of the coefficient sample (hostile-review finding 1b).

Transition states (ta, tstar, E_d>0) -> pushed -> resolved positive barrier
-> measured undamped escape energy -> in coefficient.  Also counts:
beta_u=0 (committed from rest, undamped), missing pushes, W<=0 exits,
and lam_min extremes (tangent eigenvalue diagnostic).  Writes
analysis/accounting_audit.json and analysis/table_accounting.tex.
"""
import csv, json
from pathlib import Path

A = Path(__file__).resolve().parent
rows = list(csv.DictReader((A / "law_table.csv").open()))
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
SHORT = {"SMF2B": "2B", "SMF2CG": "2CG", "SMF4B": "4B", "SMF4CG": "4CG",
         "SMF8B": "8B", "SMF8CG": "8CG", "SMF12B": "12B", "SMF12CG": "12CG",
         "SMF20B": "20B", "SMF20CG": "20CG"}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


out = {}
tex = ["\\begin{tabular}{lrrrrrr}", "\\toprule",
       "Frame & $n_{t_a,t^*}$ & pushed & $W>0$ & $E_u>0$ & in $c^0$ & excluded \\\\", "\\midrule"]
for m in MODELS:
    T = [r for r in rows if r["model"] == m and r["tag"] in ("ta", "tstar") and f(r["E_d"]) > 0]
    pushed = [r for r in T if r["Wc_m1"] != "" and r["Wc_m1"] is not None]
    pos = [r for r in pushed if f(r["Wc_m1"]) > 0]
    eu = [r for r in T if f(r["E_u"]) > 0]
    inc = [r for r in T if f(r["Wc_m1"]) > 0 and f(r["E_u"]) > 0]
    bzero = sum(1 for r in T if r["beta_u"] != "" and f(r["beta_u"]) == 0)
    miss = len(T) - len(pushed)
    neg = len(pushed) - len(pos)
    lam_big = sum(1 for r in T if r["lam_min"] != "" and f(r["lam_min"]) < -1e6)
    out[SHORT[m]] = dict(n_trans=len(T), pushed=len(pushed), w_pos=len(pos),
                         e_u=len(eu), in_coeff=len(inc), excluded=len(T) - len(inc),
                         beta_u_zero=bzero, no_push=miss, w_nonpos=neg, lam_min_big=lam_big)
    tex.append(f"{SHORT[m]} & {len(T)} & {len(pushed)} & {len(pos)} & {len(eu)} & {len(inc)} & {len(T)-len(inc)} \\\\")
tex += ["\\bottomrule", "\\end{tabular}"]

(A / "accounting_audit.json").write_text(json.dumps(out, indent=1))
(A / "table_accounting.tex").write_text("\n".join(tex))
for m in MODELS:
    print(SHORT[m], json.dumps(out[SHORT[m]]))
