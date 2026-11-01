"""Generate manuscript/numbers.tex, tab_ida.tex and tab_pnr.tex from results/.

Every number quoted in the manuscript text is a macro defined here, so the
text cannot drift from the computed results.  Missing inputs produce '??'
(visible in the compiled PDF and caught by the final check).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "results"
MAN = HERE.parent / "manuscript"
KIP_KN = 4.4482216
MISSING = "??"


def jload(name):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def cload(name):
    p = RES / name
    if not p.exists():
        return []
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    for r in rows:
        for k, v in list(r.items()):
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


def f(x, nd=1, pct=False, sign=False):
    if x is None:
        return MISSING
    try:
        v = float(x) * (100.0 if pct else 1.0)
    except (TypeError, ValueError):
        return MISSING
    if not np.isfinite(v):
        return MISSING
    s = f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"
    return s


def get(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def main():
    mc = jload("model_checks.json")
    ida = jload("ida_summary.json")
    zs = jload("zic_summary.json")
    t95 = jload("t95_summary.json")
    cl = jload("classify_summary.json")
    ex = jload("fig3_example_meta.json")
    idarec = cload("ida_records.csv")
    N = {}
    tag = {"SMF4B": "FourB", "SMF8B": "EightB", "SMF4CG": "FourCG", "SMF8CG": "EightCG"}
    # --- models
    for m, t in tag.items():
        r = mc.get(m, {})
        N[f"Omega{t}"] = f(r.get("Omega_static"), 1)
        if m.endswith("B"):
            N[f"Grav{t}"] = f(None if r.get("gravity_reaction_kip") is None else r["gravity_reaction_kip"] * KIP_KN, 0)
            N[f"ZeroRoof{t}"] = f(r.get("roof_drift_zero_V"), 1, pct=True)
            N[f"ZeroSDR{t}"] = f(r.get("max_sdr_zero_V"), 1, pct=True)
        else:
            c = r.get("curve")
            N[f"POend{t}"] = f(None if not c else c[-1][0], 1, pct=True)
    for st, b, cg in (("Four", "SMF4B", "SMF4CG"), ("Eight", "SMF8B", "SMF8CG")):
        if mc.get(b) and mc.get(cg):
            N[f"CGgain{st}"] = f(mc[cg]["Vmax_kip"] / mc[b]["Vmax_kip"] - 1.0, 0, pct=True)
        else:
            N[f"CGgain{st}"] = MISSING
    for m, t in tag.items():
        per = (mc.get(m) or {}).get("periods")
        N[f"TOne{t}"] = f(per[0] if per else None, 2)
    # --- IDA
    n_runs = 0
    for m, t in tag.items():
        a = get(ida, m, "ALL") or {}
        N[f"Sc{t}"] = f(a.get("median_Sc"), 2)
        N[f"Beta{t}"] = f(a.get("beta_RTR"), 2)
        N[f"CMR{t}"] = f(a.get("CMR"), 2)
        N[f"AfterNinetyFive{t}"] = f(a.get("frac_coll_after_t95_at_Sc"), 0, pct=True)
        N[f"AfterEnd{t}"] = f(a.get("n_coll_after_record_at_Sc"), 0)
        N[f"TruncEndMax{t}"] = f(None if a.get("ratio_trunc_max") is None else a["ratio_trunc_max"] - 1, 0, pct=True)
        n_runs += sum(int(r.get("n_runs") or 0) for r in idarec if r["model"] == m)
    N["IDARuns"] = f"{n_runs:,}".replace(",", "\\,") if n_runs else MISSING
    N["IDANonconv"] = f(sum(int(get(ida, m, "ALL", "nonconv_runs") or 0) for m in tag), 0) if n_runs else MISSING
    N["IDACensored"] = f(sum(int(get(ida, m, "ALL", "censored") or 0) for m in tag), 0) if n_runs else MISSING
    tot_after = sum(int(get(ida, m, "ALL", "n_coll_after_record_at_Sc") or 0) for m in ("SMF4B", "SMF8B"))
    tot_n = sum(int(get(ida, m, "ALL", "n") or 0) for m in ("SMF4B", "SMF8B"))
    N["AfterEndPct"] = f(tot_after / tot_n if tot_n else None, 0, pct=True)
    # --- point of no return
    for m, t in tag.items():
        h = get(zs, m, "hi_ALL") or {}
        N[f"PNR{t}"] = f(h.get("n"), 0)
        N[f"ThetaStar{t}"] = f(get(h, "star_inst_sdr", "median"), 1, pct=True)
        lo, hi = get(h, "star_inst_sdr", "p10"), get(h, "star_inst_sdr", "p90")
        N[f"ThetaStarRange{t}"] = MISSING if lo is None else f"{100 * lo:.1f}--{100 * hi:.1f}"
        N[f"LeadC{t}"] = f(get(h, "lead_c", "median"), 1)
        N[f"StarRoof{t}"] = f(get(h, "star_roof_drift", "median"), 1, pct=True)
        N[f"PassTenBefore{t}"] = f(h.get("frac_passed10_before_star"), 0, pct=True)
        N[f"ResidA{t}"] = f(get(h, "a_resid_max", "median"), 1, pct=True)
        b95 = h.get("frac_star_before_t95")
        N[f"StarAfterNinetyFive{t}"] = f(None if b95 is None else 1 - b95, 0, pct=True)
        N[f"StarMinusNinetyFive{t}"] = f(get(h, "time_after_t95", "median"), 1)
        N[f"AriasRem{t}"] = f(get(h, "arias_remaining", "median"), 1, pct=True)
        N[f"StaticFrac{t}"] = f(h.get("frac_static"), 0, pct=True)
        N[f"KineticFrac{t}"] = f(None if h.get("frac_static") is None else 1 - h["frac_static"], 0, pct=True)
        N[f"StaticDelay{t}"] = f(get(h, "static_minus_star", "median"), 2)
        N[f"ThetaStatic{t}"] = f(get(h, "theta_static", "median"), 1, pct=True)
        N[f"RhoStarStatic{t}"] = f(h.get("spearman_star_static"), 2)
        N[f"GapStatic{t}"] = f(get(h, "gap_static_minus_star_sdr", "median"), 1, pct=True)
        N[f"OutwardFrac{t}"] = f(h.get("frac_star_story_outward"), 0, pct=True)  # critical story moving outwards
        N[f"KEStar{t}"] = f(get(h, "star_ke_norm", "median"), 1, pct=True)
        N[f"NonMono{t}"] = f(h.get("n_non_monotonic"), 0)
        N[f"SearchRepaired{t}"] = f(h.get("n_search_repaired"), 0)
        s = zs.get(m, {})
        N[f"LoRec{t}"] = f(s.get("lo_records"), 0)
        N[f"RescuedRec{t}"] = f(s.get("lo_rescued_records"), 0)
        # 1.5 x S_a,c (x15 level)
        x = get(zs, m, "x15_ALL") or {}
        N[f"XPNR{t}"] = f(x.get("n"), 0)
        N[f"XThetaStar{t}"] = f(get(x, "star_inst_sdr", "median"), 1, pct=True)
        lo, hi = get(x, "star_inst_sdr", "p10"), get(x, "star_inst_sdr", "p90")
        N[f"XThetaStarRange{t}"] = MISSING if lo is None else f"{100 * lo:.1f}--{100 * hi:.1f}"
        N[f"XLeadC{t}"] = f(get(x, "lead_c", "median"), 1)
        b95 = x.get("frac_star_before_t95")
        N[f"XStarAfterNinetyFive{t}"] = f(None if b95 is None else 1 - b95, 0, pct=True)
        N[f"XStarMinusNinetyFive{t}"] = f(get(x, "time_after_t95", "median"), 1)
        N[f"XAriasRem{t}"] = f(get(x, "arias_remaining", "median"), 1, pct=True)
        N[f"XKineticFrac{t}"] = f(None if x.get("frac_static") is None else 1 - x["frac_static"], 0, pct=True)
        N[f"XKEStar{t}"] = f(get(x, "star_ke_norm", "median"), 1, pct=True)
        N[f"XNonMono{t}"] = f(x.get("n_non_monotonic"), 0)
        N[f"XThetaStatic{t}"] = f(get(x, "theta_static", "median"), 1, pct=True)
        N[f"XNotOk{t}"] = f(len(s.get("x15_not_ok", [])) if "x15_not_ok" in s else None, 0)
        nok = s.get("x15_not_ok") if x else None
        N[f"XNoColl{t}"] = f(None if nok is None else sum(st == "reference_did_not_collapse" for _, st in nok), 0)
        N[f"XLate{t}"] = f(None if nok is None else sum(str(st).startswith("recoverable_at_collapse") for _, st in nok),
                           0)
        N[f"XOther{t}"] = f(None if nok is None else sum(st != "reference_did_not_collapse"
                                                          and not str(st).startswith("recoverable_at_collapse")
                                                          for _, st in nok), 0)
        N[f"XColl{t}"] = f(None if nok is None else x.get("n", 0) + len(nok)
                           - sum(st == "reference_did_not_collapse" for _, st in nok), 0)
        N[f"XPassTenBefore{t}"] = f(x.get("frac_passed10_before_star"), 0, pct=True)
        N[f"XOutwardFrac{t}"] = f(x.get("frac_star_story_outward"), 0, pct=True)
        N[f"XKEStarRatio{t}"] = f(None if not (get(x, "star_ke_norm", "median") and get(h, "star_ke_norm", "median"))
                                  else get(x, "star_ke_norm", "median") / get(h, "star_ke_norm", "median"), 0)
    # rescued-state descriptors (from the states tables)
    for m, t in tag.items():
        st = cload(f"zic_states_{m}.csv")
        resc = [r for r in st if r["level"] == "lo" and r["committed"] == 1]
        N[f"RescuedDrift{t}"] = f(np.median([r["inst_max_sdr"] for r in resc]) if resc else None, 1, pct=True)
        N[f"RescuedKE{t}"] = f(np.median([r["ke_norm"] for r in resc]) if resc else None, 1)
        rd = [r["inst_max_sdr"] for r in resc]
        N[f"RescuedDriftRange{t}"] = (f"{100 * np.percentile(rd, 10):.1f}--{100 * np.percentile(rd, 90):.1f}"
                                      if rd else MISSING)
        # committed states on collapse histories at and after t* (the static branch)
        comhi = [r for r in st if r["level"] == "hi" and r["committed"] == 1 and r.get("t_rel_star") is not None
                 and r["t_rel_star"] >= -1e-9]
        N[f"ComHiDriftPten{t}"] = f(np.percentile([r["inst_max_sdr"] for r in comhi], 10) if comhi else None, 1,
                                    pct=True)
        N[f"ComHiKE{t}"] = f(np.median([r["ke_norm"] for r in comhi]) if comhi else None, 2)
        zr = [r for r in cload(f"zic_records_{m}.csv") if r["level"] == "hi" and r["status"] == "ok"]
        res_ = [r["resolution"] for r in zr if r.get("resolution") is not None]
        N[f"ResMin{t}"] = f(min(res_) if res_ else None, 3)
        N[f"ResMax{t}"] = f(max(res_) if res_ else None, 3)
        st_hl = [r for r in st if r["level"] in ("hi", "lo")]  # states of Fig. 5 (no 1.5 S_a,c states)
        com = [r for r in st_hl if r["committed"] == 1]
        rec = [r for r in st_hl if r["committed"] == 0]
        N[f"ComBelowTen{t}"] = f(np.mean([r["inst_max_sdr"] < 0.10 for r in com]) if com else None, 0, pct=True)
        N[f"RecAboveTen{t}"] = f(np.mean([r["inst_max_sdr"] >= 0.10 for r in rec]) if rec else None, 0, pct=True)
        rr = cload(f"rest_states_{m}.csv")
        rl = [r for r in rr if r["level"] == "lo"]
        N[f"RescuedRestRecover{t}"] = f(np.mean([not r["rest_committed"] for r in rl]) if rl else None, 0, pct=True)
    # far-field subsets for the bare / composite+gravity comparison (4-story)
    for m, t in (("SMF4B", "FourB"), ("SMF4CG", "FourCG")):
        a = get(ida, m, "FF") or {}
        N[f"ScFF{t}"] = f(a.get("median_Sc"), 2)
        ci = a.get("median_Sc_CI95") or [None, None]
        N[f"ScFFCI{t}"] = MISSING if ci[0] is None else f"{ci[0]:.2f}--{ci[1]:.2f}"
        N[f"BetaFF{t}"] = f(a.get("beta_RTR"), 2)
        N[f"AfterNinetyFiveFF{t}"] = f(a.get("frac_coll_after_t95_at_Sc"), 0, pct=True)
        h = get(zs, m, "hi_FF") or {}
        N[f"PNRFF{t}"] = f(h.get("n"), 0)
        N[f"ThetaStarFF{t}"] = f(get(h, "star_inst_sdr", "median"), 1, pct=True)
        ci = get(h, "star_inst_sdr", "CI95") or [None, None]
        N[f"ThetaStarFFCI{t}"] = MISSING if ci[0] is None else f"{100 * ci[0]:.1f}--{100 * ci[1]:.1f}"
        N[f"LeadCFF{t}"] = f(get(h, "lead_c", "median"), 1)
        b95 = h.get("frac_star_before_t95")
        N[f"StarAfterNinetyFiveFF{t}"] = f(None if b95 is None else 1 - b95, 0, pct=True)
        N[f"KineticFracFF{t}"] = f(None if h.get("frac_static") is None else 1 - h["frac_static"], 0, pct=True)
        N[f"ThetaStaticFF{t}"] = f(get(h, "theta_static", "median"), 1, pct=True)
        N[f"StaticDelayFF{t}"] = f(get(h, "static_minus_star", "median"), 2)
        N[f"PassTenBeforeFF{t}"] = f(h.get("frac_passed10_before_star"), 0, pct=True)
    cg = jload("cg_summary.json").get("SMF4CG", {})
    sr = cg.get("Sc_ratio") or {}
    N["CGScRatio"] = f(None if sr.get("median") is None else sr["median"] - 1, 0, pct=True)
    ci = sr.get("CI95") or [None, None]
    N["CGScRatioCI"] = MISSING if ci[0] is None else f"{100 * (ci[0] - 1):.0f}--{100 * (ci[1] - 1):.0f}"
    N["CGScRatioPos"] = f(cg.get("Sc_frac_increase"), 0, pct=True)
    fr = cg.get("scale_ratio") or {}
    N["CGScaleRatio"] = f(None if fr.get("median") is None else fr["median"] - 1, 0, pct=True)
    ci = fr.get("CI95") or [None, None]
    N["CGScaleRatioCI"] = MISSING if ci[0] is None else f"{100 * (ci[0] - 1):.0f}--{100 * (ci[1] - 1):.0f}"
    N["CGScaleRatioMin"] = f(None if fr.get("min") is None else fr["min"] - 1, 0, pct=True)
    N["CGScalePos"] = f(cg.get("scale_frac_increase"), 0, pct=True)
    N["CGPairsIDA"] = f(cg.get("n_ida_pairs"), 0)
    for lab_, key in (("CG", "cg"), ("Bare", "bare")):
        s = cg.get(f"{key}_settled_resid_max") or {}
        N[f"{lab_}ResidMed"] = f(s.get("median"), 1, pct=True)
        N[f"{lab_}ResidMax"] = f(s.get("max"), 1, pct=True)
    N["CGLate"] = f(cg.get("cg_unresolved_late"), 0)
    N["CGRestN"] = f(cg.get("cg_rest_n"), 0)
    N["CGNoStatic"] = f(cg.get("cg_no_static_before_collapse"), 0)
    N["CGScRatioMin"] = f(None if sr.get("min") is None else sr["min"] - 1, 0, pct=True)
    for key, mac, nd in (("dtheta_star", "CGdTheta", 1), ("dtheta_static", "CGdThetaStatic", 1)):
        s = cg.get(key) or {}
        N[mac] = f(s.get("median"), nd, pct=True, sign=True)
        ci = s.get("CI95") or [None, None]
        N[mac + "CI"] = MISSING if ci[0] is None else f"{100 * ci[0]:+.1f} to {100 * ci[1]:+.1f}"
        N[mac + "Pos"] = f(s.get("frac_positive"), 0, pct=True) if s else MISSING
    s = cg.get("dlead_c") or {}
    N["CGdLeadC"] = f(s.get("median"), 1, sign=True)
    s = cg.get("dt_star_minus_t95") or {}
    N["CGdStarNinetyFive"] = f(s.get("median"), 1, sign=True)
    N["CGPairs"] = f(cg.get("n_zic_pairs"), 0)
    allres = [r["resolution"] for m in ("SMF4B", "SMF8B") for r in cload(f"zic_records_{m}.csv")
              if r["level"] == "hi" and r["status"] == "ok" and r.get("resolution") is not None]
    N["ResMinAll"] = f(min(allres) if allres else None, 2)
    N["ResMaxAll"] = f(max(allres) if allres else None, 2)
    # --- t95 truncation
    for m, t in tag.items():
        a = get(t95, m, "ALL") or {}
        fu = a.get("frac_unchanged")
        N[f"TNinetyFiveChanged{t}"] = f(None if fu is None else 1 - fu, 0, pct=True)
        N[f"TNinetyFiveRatio{t}"] = f(None if a.get("ratio_median_changed") is None else a["ratio_median_changed"] - 1,
                                      0, pct=True)
        N[f"TNinetyFiveMax{t}"] = f(None if a.get("ratio_max") is None else a["ratio_max"] - 1, 0, pct=True)
        N[f"TNinetyFiveMedShift{t}"] = f(None if a.get("median_shift") is None else a["median_shift"] - 1, 0, pct=True)
        ci = a.get("median_shift_CI95") or [None, None]
        N[f"TNinetyFiveMedShiftCI{t}"] = MISSING if ci[0] is None else f"{100 * (ci[0] - 1):.0f}--{100 * (ci[1] - 1):.0f}"
    # --- classification
    N["BestThetaDev"] = f(cl.get("theta_b"), 1, pct=True)
    N["BestThetaErrDev"] = f(get(cl, "dev", "D", "error"), 0, pct=True)
    N["BestThetaErrHold"] = f(get(cl, "holdout", "holdout_all", "D", "error"), 0, pct=True)
    N["RuleThetaS"] = f(cl.get("theta_s"), 1, pct=True)
    N["RuleKappa"] = f(cl.get("kappa"), 1)
    N["RuleErrDev"] = f(get(cl, "dev", "DK", "error"), 0, pct=True)
    N["RuleErrHold"] = f(get(cl, "holdout", "holdout_all", "DK", "error"), 0, pct=True)
    # extra test: states of the 4-story collapse histories at 1.5 S_a,c (rules fitted on the development set)
    N["BestThetaErrX"] = f(get(cl, "holdout", "SMF4B_x15", "D", "error"), 0, pct=True)
    N["RuleErrX"] = f(get(cl, "holdout", "SMF4B_x15", "DK", "error"), 0, pct=True)
    N["TenErrX"] = f(get(cl, "holdout", "SMF4B_x15", "D10", "error"), 0, pct=True)
    nx = get(cl, "holdout", "SMF4B_x15", "D", "n")
    N["NStatesX"] = MISSING if nx is None else f"{int(nx):,}".replace(",", "\\,")
    N["MissDX"] = f(get(cl, "holdout", "SMF4B_x15", "D", "miss_rate"), 0, pct=True)
    N["MissDKX"] = f(get(cl, "holdout", "SMF4B_x15", "DK", "miss_rate"), 0, pct=True)
    # --- totals
    n_rel = sum(int(get(zs, m, "n_releases_total") or 0) for m in tag)
    N["ReleasesTotal"] = f"{n_rel:,}".replace(",", "\\,") if n_rel else MISSING
    N["ReleasesCensored"] = f(sum(int(get(zs, m, "n_censored") or 0) for m in tag), 0) if n_rel else MISSING
    N["ReleasesNonconv"] = f(sum(int(get(zs, m, "release_outcomes", "committed_nonconv") or 0) for m in tag), 0) \
        if n_rel else MISSING
    n_rest = sum(len(cload(f"rest_states_{m}.csv")) for m in tag)
    N["RestTotal"] = f"{n_rest:,}".replace(",", "\\,") if n_rest else MISSING
    dts = jload("dt_sensitivity.json")
    N["DtNrec"] = f(dts.get("n_compared"), 0)
    N["DtMaxStar"] = f(dts.get("max_abs_dt_star_s"), 2)
    N["DtMaxTheta"] = f(dts.get("max_abs_dtheta_pct"), 2)
    N["DtMaxLead"] = f(dts.get("max_abs_dlead_s"), 2)
    N["DtMaxTc"] = f(dts.get("max_abs_dtc_s"), 2)
    N["DtNtotal"] = f(dts.get("n"), 0)
    N["DtNsmall"] = f(dts.get("n_dtheta_below_0p2pct"), 0)
    N["DtMaxThetaSmall"] = f(dts.get("max_abs_dtheta_small_pct"), 2)
    w = dts.get("worst") or {}
    N["DtWorstTheta"] = f(None if w.get("dtheta_pct") is None else abs(w["dtheta_pct"]), 1)
    N["DtWorstTc"] = f(None if w.get("dtc_s") is None else abs(w["dtc_s"]), 1)
    # --- example (Fig. 3)
    N["ExTstar"] = f(ex.get("t_star"), 3)
    N["ExTa"] = f(ex.get("t_a"), 3)
    N["ExRes"] = f(None if not ex else ex["t_star"] - ex["t_a"], 3)
    N["ExTc"] = f(ex.get("t_c"), 1)
    N["ExTninetyfive"] = f(ex.get("t95"), 1)
    exrow = next((r for r in cload(f"zic_records_{ex.get('model', 'SMF4B')}.csv")
                  if r["rid"] == ex.get("rid") and r["level"] == "hi"), {})
    N["ExTten"] = f(exrow.get("t10"), 1)
    N["ExThetaNinetyFive"] = f(exrow.get("theta_at_t95"), 1, pct=True)
    N["ExResidA"] = f(exrow.get("a_resid_max"), 1, pct=True)
    N["ExLeadC"] = f(exrow.get("lead_c"), 1)
    N["ExAriasDelivered"] = f(None if exrow.get("arias_remaining") is None else 1 - exrow["arias_remaining"], 1,
                              pct=True)
    N["ExStaticDelay"] = f(exrow.get("static_minus_star"), 2)
    N["ExGapTa"] = f(None if (exrow.get("t10") is None or not ex) else ex["t_a"] - exrow["t10"], 1)
    # --- IDA extras: 10 % collapse limit, stopping at the record end
    for m, t in tag.items():
        a = get(ida, m, "ALL") or {}
        N[f"ScTenRatioMin{t}"] = f(None if a.get("Sc10_ratio_min") is None else 1 - a["Sc10_ratio_min"], 0, pct=True)
        N[f"NoncollAboveTen{t}"] = f(a.get("noncoll_runs_above_10"), 0)
        vals = a.get("ratio_trunc_values_gt1") or []
        N[f"TruncEndN{t}"] = f(len(vals), 0) if a else MISSING
        big = sorted(v for v in vals if v > 1.03 + 1e-9)
        N[f"TruncEndBig{t}"] = (" and ".join(f"{100 * (v - 1):.0f}\\%" for v in big)) if big else "none"
        N[f"TruncEndNBig{t}"] = f(len(big), 0) if a else MISSING
    lines = ["%% generated by code/make_numbers.py -- do not edit"]
    for k in sorted(N):
        v = N[k]
        if v[:1] in "+-" and v[1:2].isdigit():  # typographic sign
            v = f"${v[0]}${v[1:]}"
        v = v.replace(" to -", " to $-$").replace(" to +", " to $+$")
        lines.append(f"\\newcommand{{\\Num{k}}}{{{v}}}")
    (MAN / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    missing = sorted(k for k, v in N.items() if v == MISSING)
    write_tables(ida, zs, t95)
    write_plain_abstract(N)
    print(f"{len(N)} macros; missing: {missing}")


def write_plain_abstract(N: dict) -> None:
    """Plain-text abstract for the submission form (macros expanded)."""
    import re

    t = (MAN / "abstract.tex").read_text(encoding="utf-8")
    t = re.sub(r"\\Num([A-Za-z]+)(\{\})?", lambda m: N.get(m.group(1), MISSING).replace("\\,", ""), t)
    for a, b in (("\\%", "%"), ("~", " "), ("--", "\u2013"), ("$", ""), ("\\,", " ")):
        t = t.replace(a, b)
    pkg = HERE.parent / "package"
    pkg.mkdir(exist_ok=True)
    (pkg / "abstract_plain.txt").write_text(" ".join(t.split()) + "\n", encoding="utf-8")


def write_tables(ida, zs, t95):
    order = [m for m in ("SMF4B", "SMF8B", "SMF4CG", "SMF8CG") if m in ida]
    lab = {"SMF4B": "4-story bare", "SMF8B": "8-story bare", "SMF4CG": "4-story CG", "SMF8CG": "8-story CG"}
    rows = []
    cg_t95_missing = False
    for m in order:
        for st in ("FF", "NF", "ALL"):
            a = get(ida, m, st)
            if not a:
                continue
            tt = get(t95, m, st) or {}
            ci = a.get("median_Sc_CI95") or [None, None]
            trunc = f(None if tt.get('median_shift') is None else tt['median_shift'] - 1, 0, pct=True)
            if m.endswith("CG") and tt.get("median_shift") is None:
                trunc = r"--$^{c}$"
                cg_t95_missing = True
            rows.append(
                f"{lab[m] if st == 'FF' else ''} & {st if st != 'ALL' else 'All'} & {a['n']} & "
                f"{f(a['median_Sc'], 2)} ({f(ci[0], 2)}--{f(ci[1], 2)}) & {f(a['beta_RTR'], 2)} & {f(a['CMR'], 2)} & "
                f"{f(a['frac_coll_after_t95_at_Sc'], 0, pct=True)} & {a['n_coll_after_record_at_Sc']} & "
                f"{trunc}\\\\")
        rows.append("\\addlinespace")
    tab = r"""\begin{table}[!tbp]
\centering
\caption{Incremental dynamic analysis at the record-specific collapse intensity $S_{a,c}$. Median $S_{a,c}$ with 95\% bootstrap confidence interval; $\beta$: logarithmic standard deviation of $S_{a,c}$; CMR: median $S_{a,c}$ divided by the MCE spectral acceleration at $T_1$; collapses completed after $t_{95}$ and after the record end at $S_{a,c}$; increase of the median $S_{a,c}$ when records are truncated at $t_{95}$ and followed by free vibration.}
\label{tab:ida}
\small
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{@{}llccccccc@{}}
\toprule
Model & Set & $n$ & \makecell{Median $S_{a,c}$ (g)\\(95\% CI)} & $\beta$ & CMR & \makecell{After\\$t_{95}$ (\%)} & \makecell{After\\end} & \makecell{$t_{95}$ trunc.\\(\%)}\\
\midrule
""" + "\n".join(rows[:-1]) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
""" + (r"\parbox{\textwidth}{\footnotesize $^{c}$ The $t_{95}$ truncation analysis was not run for the composite-and-gravity models; the corresponding cells are not applicable.}" if cg_t95_missing else "") + r"""
\end{table}
"""
    (MAN / "tab_ida.tex").write_text(tab, encoding="utf-8")
    prow = []
    for m in [m for m in ("SMF4B", "SMF8B", "SMF4CG", "SMF8CG") if m in zs]:
        for st in ("FF", "NF", "ALL"):
            h = get(zs, m, f"hi_{st}")
            if not h:
                continue

            def md(k, nd=1, pct=False):
                s = f(get(h, k, "median"), nd, pct=pct)
                return "$-$" + s[1:] if s.startswith("-") else s  # typographic minus

            prow.append(
                f"{lab[m] if st == 'FF' else ''} & {st if st != 'ALL' else 'All'} & {h['n']} & "
                f"{md('star_inst_sdr', 1, True)} & {md('star_roof_drift', 1, True)} & {md('lead_c', 1)} & "
                f"{md('lead_10', 1)} & {f(1 - h['frac_star_before_t95'], 0, pct=True) if h.get('frac_star_before_t95') is not None else MISSING} & "
                f"{md('arias_remaining', 1, True)} & {f(None if h.get('frac_static') is None else 1 - h['frac_static'], 0, pct=True)} & {md('static_minus_star', 2)}\\\\")
        prow.append("\\addlinespace")
    tab2 = r"""\begin{table}[!tbp]
\centering
\caption{Point of no return on the collapse histories at $S_{a,c}$ (medians). $\theta^*$: peak story drift ratio at $t^*$; $t_c$: collapse time; $t_{10}$: first passage of 10\% story drift (negative values: 10\% reached before $t^*$); Arias: share of the Arias intensity of the record delivered after $t^*$; kinetic: share of histories in which the frame released from rest at $t^*$ recovers; $t^*_s$: transition after release from rest.}
\label{tab:pnr}
\small
\begin{adjustbox}{max width=\textwidth}
\begin{tabular}{@{}llccccccccc@{}}
\toprule
Model & Set & $n$ & \makecell{$\theta^*$\\(\%)} & \makecell{Roof drift\\at $t^*$ (\%)} & \makecell{$t_c - t^*$\\(s)} & \makecell{$t_{10} - t^*$\\(s)} & \makecell{$t^* > t_{95}$\\(\%)} & \makecell{Arias after\\$t^*$ (\%)} & \makecell{Kinetic\\(\%)} & \makecell{$t^*_s - t^*$\\(s)}\\
\midrule
""" + "\n".join(prow[:-1]) + r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\end{table}
"""
    (MAN / "tab_pnr.tex").write_text(tab2, encoding="utf-8")


if __name__ == "__main__":
    main()
