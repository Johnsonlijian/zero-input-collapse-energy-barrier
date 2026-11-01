"""Per-state audits requested by the hostile theory review.

All from law_table.csv — no new simulations.

  A. Per-state c0 residual vs first-mode KE share (KE_phi/ke):
     if "low mode share -> first-mode push misses the escape pass" were the
     mechanism, per-state residuals should track per-state share.  Spearman
     per model + pooled (event-cluster bootstrap CI pooled only).
  B. Rescued states (tag=rescued): count per model and location relative to
     the energy-rule threshold, under two readings: ke >= c_f*W_m1 (audit
     default, frame's own fitted constant on the released-state barrier) and
     ke >= C_DEV*Wc_m1 (the reported transferred rule on the corrected
     collapse-surface barrier, same basis as accWcDev).
  C. Restricted classifier accuracy: energy rule vs dev drift threshold on the
     subset with resolved nonzero barriers (lim_m1 in drift/edge/stall, W_m1>0).
  D. Beta-bracket censoring counts (censored_u / censored_d) per model.
  E. Per-state c0 spread (p10-p90) and the share of drift-limited transition
     states (exit-class census on the transition set itself).
"""
import csv, json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

A = Path(__file__).resolve().parent
LT = A / "law_table.csv"
SJ = json.loads((A / "summary_by_frame.json").read_text())
OUT = A / "per_state_audit.json"

MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
RESOLVED = {"drift", "edge", "stall"}
C_DEV = 1.13


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


rows = list(csv.DictReader(LT.open()))
out = {}

for m in MODELS:
    L = [r for r in rows if r["model"] == m]
    blk = {}

    # --- A. c0 residual vs first-mode KE share (transition set: ta/tstar, E_u>0, W_m1>0)
    T = [r for r in L if r["tag"] in ("ta", "tstar") and fnum(r["E_u"]) > 0 and fnum(r["W_m1"]) > 0 and fnum(r["ke"]) > 0 and fnum(r["KE_phi"]) > 0]
    if len(T) >= 10:
        c0 = np.array([fnum(r["E_u"]) / fnum(r["W_m1"]) for r in T])
        sh = np.array([fnum(r["KE_phi"]) / fnum(r["ke"]) for r in T])
        resid = np.log(c0) - np.median(np.log(c0))
        rho, p = spearmanr(sh, resid)
        blk["c0res_vs_ke1"] = dict(n=len(T), rho=float(rho), p=float(p),
                                   med_share=float(np.median(sh)),
                                   c0_med=float(np.median(c0)),
                                   c0_p10=float(np.percentile(c0, 10)),
                                   c0_p90=float(np.percentile(c0, 90)))
        # split: states below/above median share
        lo = c0[sh < np.median(sh)]; hi = c0[sh >= np.median(sh)]
        blk["c0res_vs_ke1"]["c0_below_med_share"] = float(np.median(lo))
        blk["c0res_vs_ke1"]["c0_above_med_share"] = float(np.median(hi))

    # --- B. rescued states
    R = [r for r in L if r["tag"] == "rescued"]
    if R:
        cf = (SJ.get(f"{m}|ALL") or {}).get("c_f", [C_DEV])[0]
        above = sum(1 for r in R if fnum(r["ke"]) >= cf * fnum(r["W_m1"]))
        above_dev_wc = sum(1 for r in R if fnum(r["ke"]) >= C_DEV * fnum(r["Wc_m1"]))
        blk["rescued"] = dict(n=len(R), above_rule=above, above_rule_dev_wc=above_dev_wc,
                              labels=dict((k, sum(1 for r in R if r["label_r52"] == k)) for k in ("committed", "recoverable")))

    # --- C. restricted accuracy (resolved nonzero barrier)
    Cl = [r for r in L if fnum(r["W_m1"]) == fnum(r["W_m1"])]
    Res = [r for r in Cl if r["lim_m1"] in RESOLVED and fnum(r["W_m1"]) > 0]
    if Res:
        cf = (SJ.get(f"{m}|ALL") or {}).get("c_f", [C_DEV])[0]
        thr = SJ["_protocol"]["drift_threshold_dev"]
        yy = np.array([r["label_r52"] == "committed" for r in Res])
        ke = np.array([fnum(r["ke"]) for r in Res])
        W = np.array([fnum(r["W_m1"]) for r in Res])
        pk = np.array([fnum(r["peak_sdr"]) for r in Res])
        blk["acc_resolved"] = dict(n=len(Res),
                                   energy=float(np.mean((ke >= cf * W) == yy)),
                                   energy_dev=float(np.mean((ke >= C_DEV * W) == yy)),
                                   drift=float(np.mean((pk >= thr) == yy)))
    if Cl:
        blk["n_classified_all"] = len(Cl)
        blk["n_zeroW_or_unresolved"] = len(Cl) - len(Res)

    # --- D. censoring counts
    blk["censored_u"] = sum(1 for r in L if str(r["censored_u"]).strip() == "True")
    blk["censored_d"] = sum(1 for r in L if str(r["censored_d"]).strip() == "True")
    blk["n_rows"] = len(L)

    # --- E. transition-set exit census (drift-limited share of the c0 states)
    Tc = [r for r in L if r["tag"] in ("ta", "tstar") and fnum(r["E_d"]) > 0 and fnum(r["Wc_m1"]) == fnum(r["Wc_m1"])]
    if Tc:
        census = defaultdict(int)
        for r in Tc:
            census[r["lim_m1"] or "?"] += 1
        blk["trans_exit_census"] = dict(census)
        blk["trans_drift_share"] = census.get("drift", 0) / len(Tc)

    out[m] = blk

OUT.write_text(json.dumps(out, indent=1))
for m in MODELS:
    print(m, json.dumps(out[m], default=str)[:600])
