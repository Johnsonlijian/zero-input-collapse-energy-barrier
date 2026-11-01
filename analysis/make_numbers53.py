"""Generate manuscript/numbers.tex from analysis/summary_by_frame.json (lead-authored).

Macro naming: \\<quantity><Frame><Set>, Frame in {TwoB, TwoCG, FourB, FourCG, EightB, EightCG, TwelveB, TwelveCG, TwentyB, TwentyCG},
Set in {FF, NF, All}.  Every number in the manuscript must come from here.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

SUMMARY = Path(r"E:\n0r53\analysis\summary_by_frame.json")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"E:\n0r53\analysis\numbers.tex")
WORD = {"SMF2B": "TwoB", "SMF2CG": "TwoCG", "SMF4B": "FourB", "SMF4CG": "FourCG", "SMF8B": "EightB", "SMF8CG": "EightCG",
        "SMF12B": "TwelveB", "SMF12CG": "TwelveCG", "SMF20B": "TwentyB", "SMF20CG": "TwentyCG"}
SETW = {"FF": "FF", "NF": "NF", "ALL": "All"}


def _minus(s):
    return "\\ensuremath{-}" + s[1:] if s.startswith("-") else s


def f(x, nd):
    try:
        x = float(x)
        if x != x or x in (float("inf"), float("-inf")):
            return "--"
        return _minus(f"{x:.{nd}f}")
    except Exception:
        return "--"


def pct(x, nd=0):
    try:
        return _minus(f"{100*float(x):.{nd}f}")
    except Exception:
        return "--"


def main():
    S = json.loads(SUMMARY.read_text(encoding="utf-8"))
    srcs = ["summary_by_frame.json", "holdout_bootstrap_20261025.json", "per_state_audit.json",
            "direction_split.json", "modal_ke.json", "collapse_after_input.json",
            "kinematic_alternatives.json", "ktan_control.json", "ews_control.json",
            "aftershock_analysis.json", "t95_all.json", "shape_vs_mode1.json",
            "accounting_audit.json", "label_cause.json", "fork_rate.csv",
            "intact_symmetry.json", "trunc_audit.json"]
    import hashlib, datetime
    self_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    lines = ["% AUTO-GENERATED -- do not edit by hand",
             f"% generator: make_numbers53.py (sha256:{self_sha})",
             f"% source aggregates: {', '.join(srcs)}",
             f"% generated: {datetime.datetime.now().isoformat(timespec='seconds')}", ""]
    prot = S.get("_protocol", {})
    lines.append(f"\\newcommand{{\\cdev}}{{{f(prot.get('c_dev'), 2)}}}")
    lines.append(f"\\newcommand{{\\driftthrdev}}{{{pct(prot.get('drift_threshold_dev'), 1)}}}")
    emitted = set()
    for key, v in S.items():
        if key.startswith("_"):
            continue
        model, sset = key.split("|")
        sfx = WORD[model] + SETW[sset]
        emitted.add(sfx)
        def mac(name, val):
            lines.append(f"\\newcommand{{\\{name}{sfx}}}{{{val}}}")
        if v.get("n_states") is not None:
            mac("nStates", str(v["n_states"]))
        nw = v.get("near1s_Wc")
        if nw:
            mac("nearN", str(nw["n"]))
            mac("nearE", pct(nw["acc_E_cdev"], 0)); mac("nearEown", pct(nw["acc_E_own"], 0))
            mac("nearD", pct(nw["acc_D_dev"], 0)); mac("nearDown", pct(nw["acc_D_own"], 0))
            mac("nearDiff", pct(nw["acc_E_cdev"] - nw["acc_D_dev"], 0))
            mac("nearDiffLo", pct(nw["diff_E_cdev_minus_D_dev_ci95"][0], 0))
            mac("nearDiffHi", pct(nw["diff_E_cdev_minus_D_dev_ci95"][1], 0))
        if v.get("c_f"):
            mac("cf", f(v["c_f"][0], 2)); mac("cfLo", f(v["c_f"][1], 2)); mac("cfHi", f(v["c_f"][2], 2))
            mac("cfIqrLo", f(v["c_f_iqr"][0], 2)); mac("cfIqrHi", f(v["c_f_iqr"][1], 2))
            mac("cfPten", f(v["c_f_p10p90"][0], 2)); mac("cfPninety", f(v["c_f_p10p90"][1], 2)); mac("cfLogsd", f(v["c_f_logsd"], 2))
            mac("nTrans", str(v["n_transition"]))
        if v.get("c_c"):
            mac("cc", f(v["c_c"][0], 2)); mac("ccLo", f(v["c_c"][1], 2)); mac("ccHi", f(v["c_c"][2], 2))
            mac("ccIqrLo", f(v["c_c_iqr"][0], 2)); mac("ccIqrHi", f(v["c_c_iqr"][1], 2))
            mac("ccPten", f(v["c_c_p10p90"][0], 2)); mac("ccPninety", f(v["c_c_p10p90"][1], 2))
            mac("nTransC", str(v["n_transition_c"]))
        if v.get("c0_c"):
            # 20-storey medians sit at the printed band edge at 2dp (0.8959->0.90); emit 3dp
            dp = 3 if model in ("SMF20B", "SMF20CG") else 2
            mac("czeroc", f(v["c0_c"][0], dp)); mac("czerocLo", f(v["c0_c"][1], dp)); mac("czerocHi", f(v["c0_c"][2], dp))
            mac("czerocPten", f(v["c0_c_p10p90"][0], 2)); mac("czerocPninety", f(v["c0_c_p10p90"][1], 2))
        if v.get("lim_drift_n") is not None:
            mac("limDrift", str(v["lim_drift_n"])); mac("limEdge", str(v["lim_edge_n"])); mac("limTrunc", str(v["lim_trunc_n"]))
            mac("limStall", str(v.get("lim_stall_n", 0)))
        if v.get("W_over_Wc"):
            mac("Wover", pct(v["W_over_Wc"][0] - 1.0)); mac("WoverPten", f(v["W_over_Wc"][1], 2)); mac("WoverPninety", f(v["W_over_Wc"][2], 2))
        if v.get("c_cshape"):
            mac("ccshape", f(v["c_cshape"][0], 2)); mac("ccshapeIqrLo", f(v["c_cshape_iqr"][0], 2)); mac("ccshapeIqrHi", f(v["c_cshape_iqr"][1], 2))
        if v.get("acc_cdev_Wc") is not None:
            mac("accWcDev", pct(v["acc_cdev_Wc"], 1)); mac("accWcCf", pct(v["acc_cf_Wc"], 1)); mac("nClassWc", str(v["n_classified_Wc"]))
        if v.get("c_shape"):
            mac("cshape", f(v["c_shape"][0], 2)); mac("cshapeIqrLo", f(v["c_shape_iqr"][0], 2)); mac("cshapeIqrHi", f(v["c_shape_iqr"][1], 2))
            mac("nShape", str(v["n_shape"]))
        if v.get("c_phi"):
            mac("cphi", f(v["c_phi"][0], 2)); mac("cphiIqrLo", f(v["c_phi_iqr"][0], 2)); mac("cphiIqrHi", f(v["c_phi_iqr"][1], 2))
        if v.get("c0_phi"):
            mac("czeroPhi", f(v["c0_phi"][0], 2)); mac("czeroPhiIqrLo", f(v["c0_phi_iqr"][0], 2)); mac("czeroPhiIqrHi", f(v["c0_phi_iqr"][1], 2))
        if v.get("c0_f"):
            mac("czero", f(v["c0_f"][0], 2)); mac("czeroLo", f(v["c0_f"][1], 2)); mac("czeroHi", f(v["c0_f"][2], 2))
            mac("czeroIqrLo", f(v["c0_iqr"][0], 2)); mac("czeroIqrHi", f(v["c0_iqr"][1], 2))
            mac("czeroPten", f(v["c0_p10p90"][0], 2)); mac("czeroPninety", f(v["c0_p10p90"][1], 2))
        if v.get("D_over_W"):
            mac("Dw", pct(v["D_over_W"][0])); mac("DwPten", pct(v["D_over_W_p10p90"][0])); mac("DwPninety", pct(v["D_over_W_p10p90"][1]))
        if v.get("b2_damped") is not None:
            mac("bscaleDamped", f(v["b2_damped"], 3))
        if v.get("b2_undamped") is not None:
            mac("bscaleUndamped", f(v["b2_undamped"], 3))
        if v.get("W_story_over_m1"):
            w = v["W_story_over_m1"]; mac("WstoryRatio", f(w[0], 3)); mac("WstoryPten", f(w[1], 3)); mac("WstoryPninety", f(w[2], 3))
        if v.get("downhill_n") is not None:
            mac("downhillN", str(v["downhill_n"])); mac("downhillRest", str(v["downhill_rest_committed"]))
            mac("restN", str(v["rest_committed_n"])); mac("restDownhill", str(v["rest_committed_downhill"]))
        if v.get("n_classified"):
            mac("accEcdev", pct(v["acc_energy_cdev"], 1)); mac("accEcf", pct(v["acc_energy_cf"], 1))
            mac("accDrift", pct(v["acc_drift_dev_thr"], 1)); mac("accDriftOwn", pct(v["acc_drift_own_best"], 1)); mac("nClass", str(v["n_classified"]))
            if v.get("n_near1s"):
                mac("accEnear", pct(v["acc_energy_cf_near1s"], 1)); mac("accDnear", pct(v["acc_drift_dev_near1s"], 1)); mac("nNear", str(v["n_near1s"]))
            band_tags = {"[0,0.1)": "A", "[0.1,0.2)": "B", "[0.2,0.4)": "C", "[0.4,1.0)": "D", "[1.0,inf)": "E"}
            for band, (n, a) in (v.get("acc_by_margin_band") or {}).items():
                tag = band_tags.get(band)
                if tag:
                    mac(f"accBand{tag}", pct(a, 1)); mac(f"nBand{tag}", str(n))
        if v.get("n_histories"):
            mac("nHist", str(v["n_histories"]))
            for name, m, nd, scale in (("thetaStar", "theta_star", 1, 100), ("tStarMinusTnf", "t_star_minus_t95", 1, 1), ("tcMinusTstar", "tc_minus_tstar", 1, 1),
                                        ("tStaticMinusTstar", "tstar_static_minus_tstar", 2, 1), ("WstarWb", "W_star_over_Wb", 1, 100), ("WtnfWb", "W_t95_over_Wb", 0, 100),
                                        ("WstarWtnf", "W_star_over_W_t95", 1, 100), ("tLastMinusTstar", "t_last_minus_tstar", 2, 1), ("keStarWb", "ke_star_over_Wb", 1, 100)):
                if v.get(m):
                    med, lo, hi = v[m][0], v[m][1], v[m][2]
                    mac(name, f(scale * med, nd)); mac(name + "Lo", f(scale * lo, nd)); mac(name + "Hi", f(scale * hi, nd))
            if v.get("t_last_within_0p5"):
                mac("tLastWithinK", str(v["t_last_within_0p5"][0])); mac("tLastWithinN", str(v["t_last_within_0p5"][1]))
            if v.get("share_tstar_after_t95") is not None:
                mac("shareAfterTnf", pct(v["share_tstar_after_t95"]))
            if v.get("rest_star_recovers_share") is not None:
                mac("restRecovers", pct(v["rest_star_recovers_share"]))
        if v.get("acc_two_branch") is not None:
            mac("accTwoBranch", pct(v["acc_two_branch"], 1)); mac("accKeIntact", pct(v["acc_ke_intact"], 1))
        for tg, tgname in (("ta", "Ta"), ("tstar", "Tstar")):
            if v.get(f"rest_committed_share_{tg}") is not None:
                mac(f"restCom{tgname}N", str(v[f"rest_n_{tg}"]))
                mac(f"restCom{tgname}K", str(int(round(v[f"rest_committed_share_{tg}"] * v[f"rest_n_{tg}"]))))
    # ---- sensitivity-suite macros (paired 4B FF ta/tstar subset) -------------
    def macg(name, val):
        lines.append(f"\\newcommand{{\\{name}}}{{{val}}}")
    sd = Path(r"E:\n0r53\analysis\sens_damp_bcrit.json")
    if sd.exists():
        import numpy as _np
        rows = json.loads(sd.read_text())
        ok = [r for r in rows.values() if all(r.get(s) is not None for s in ("0", "0.5", "1", "2"))]
        b2 = _np.array([[r[s] ** 2 for s in ("0", "0.5", "1", "2")] for r in ok])
        macg("sensNdamp", str(len(ok)))
        for nm, i in (("sensBtwoZero", 0), ("sensBtwoHalf", 1), ("sensBtwoOne", 2), ("sensBtwoTwo", 3)):
            macg(nm, f(_np.median(b2[:, i]), 3))
        s = _np.array([0.0, 0.5, 1.0, 2.0])
        rat = _np.array([_np.polyfit(s, y, 1)[1] / y[0] for y in b2 if y[0] > 0])
        macg("sensBtwoIntercept", f(_np.median(rat), 3))
        macg("sensBtwoInterceptLo", f(_np.percentile(rat, 10), 3))
        macg("sensBtwoInterceptHi", f(_np.percentile(rat, 90), 3))
    dt = Path(r"E:\n0r53\analysis\sens_dt2_consistent.json")
    if dt.exists():
        import numpy as _np
        rows = json.loads(dt.read_text())
        rat = _np.array([r["c_dt2"] / r["c_ref"] for r in rows])
        macg("sensNdtTwo", str(len(rows)))
        macg("sensDtTwoRatio", f(_np.median(rat), 3))
        macg("sensDtTwoRatioLo", f(_np.percentile(rat, 10), 3))
        macg("sensDtTwoRatioHi", f(_np.percentile(rat, 90), 3))
    th = Path(r"E:\n0r53\analysis\sens_theta.json")
    if th.exists():
        t = json.loads(th.read_text())
        macg("sensThetaSameK", str(t["same20"])); macg("sensThetaSameN", str(t["n20"]))
    # modal decomposition of the release kinetic energy (first-mode share)
    mk = Path(r"E:\n0r53\analysis\modal_ke.json")
    if mk.exists():
        mkj = json.loads(mk.read_text())
        for mdl, vv in mkj.items():
            w = WORD.get(mdl)
            if not w:
                continue
            t = vv["transition"]
            lines.append(f"\\newcommand{{\\keOne{w}}}{{{round(100*t['ke1_med'])}}}")
            lines.append(f"\\newcommand{{\\keOneLo{w}}}{{{round(100*t['ke1_p10'])}}}")
    # per-state audits: c0 residual vs first-mode KE share, rescued states,
    # restricted accuracy on resolved nonzero barriers, bracket censoring
    pa = Path(r"E:\n0r53\analysis\per_state_audit.json")
    if pa.exists():
        paj = json.loads(pa.read_text())
        for mdl, vv in paj.items():
            w = WORD.get(mdl)
            if not w:
                continue
            t = vv.get("c0res_vs_ke1")
            if t:
                macg(f"czresRho{w}", f(t["rho"], 2))
                macg(f"czresBelow{w}", f(t["c0_below_med_share"], 2))
                macg(f"czresAbove{w}", f(t["c0_above_med_share"], 2))
            if vv.get("rescued"):
                macg(f"rescN{w}", str(vv["rescued"]["n"]))
                macg(f"rescAbove{w}", str(vv["rescued"]["above_rule"]))
            if vv.get("acc_resolved"):
                macg(f"accResE{w}", str(round(100 * vv["acc_resolved"]["energy"])))
                macg(f"accResD{w}", str(round(100 * vv["acc_resolved"]["drift"])))
                macg(f"nRes{w}", str(vv["acc_resolved"]["n"]))
            macg(f"censD{w}", str(vv.get("censored_d", 0)))
            macg(f"nZeroUnres{w}", str(vv.get("n_zeroW_or_unresolved", 0)))
        n_resc = sum(vv["rescued"]["n"] for mdl, vv in paj.items()
                     if mdl in WORD and vv.get("rescued"))
        n_above_dev_wc = sum(vv["rescued"].get("above_rule_dev_wc", 0) for mdl, vv in paj.items()
                             if mdl in WORD and vv.get("rescued"))
        if n_resc:
            macg("rescNAll", str(n_resc))
            macg("rescAboveN", str(n_above_dev_wc))
            macg("rescAboveShare", str(round(100 * n_above_dev_wc / n_resc)))
    # direction-split undamped coefficients (push sign = drift-sign heuristic)
    ds = Path(r"E:\n0r53\analysis\direction_split.json")
    if ds.exists():
        dsj = json.loads(ds.read_text())
        for mdl, vv in dsj.items():
            w = WORD.get(mdl)
            if not w:
                continue
            if vv.get("fwd", {}).get("c0_median") is not None:
                macg(f"czFwd{w}", f(vv["fwd"]["c0_median"], 2))
                macg(f"nFwd{w}", str(vv["fwd"]["n"]))
                macg(f"nFwdTrunc{w}", str(vv["fwd"]["lim"].get("trunc", 0)))
            if vv.get("bwd", {}).get("c0_median") is not None:
                macg(f"czBwd{w}", f(vv["bwd"]["c0_median"], 2))
                macg(f"nBwd{w}", str(vv["bwd"]["n"]))
    # cross-variant range macros over the ten primary sets (12/20-storey report FF, others ALL)
    RANGE_SET = {"SMF2B": "ALL", "SMF2CG": "ALL", "SMF4B": "ALL", "SMF4CG": "ALL",
                 "SMF8B": "ALL", "SMF8CG": "ALL", "SMF12B": "FF", "SMF12CG": "FF",
                 "SMF20B": "FF", "SMF20CG": "FF"}
    def _rng(field):
        vals = [S[f"{m}|{s}"].get(field) for m, s in RANGE_SET.items()
                if f"{m}|{s}" in S and S[f"{m}|{s}"].get(field) is not None]
        return (pct(min(vals), 1), pct(max(vals), 1)) if vals else ("--", "--")
    lo, hi = _rng("acc_cdev_Wc"); macg("accWcDevMin", lo); macg("accWcDevMax", hi)
    lo, hi = _rng("acc_drift_dev_thr"); macg("accDriftMin", lo); macg("accDriftMax", hi)
    # placeholder "--" macros for frame/set combos with no data yet, so the manuscript compiles
    stubs = ["cf", "cfLo", "cfHi", "cfIqrLo", "cfIqrHi", "cfPten", "cfPninety", "cfLogsd", "nTrans", "nStates",
             "cc", "ccLo", "ccHi", "ccIqrLo", "ccIqrHi", "ccPten", "ccPninety", "nTransC",
             "czeroc", "czerocLo", "czerocHi", "czerocPten", "czerocPninety", "limDrift", "limEdge", "limTrunc", "limStall",
             "Wover", "WoverPten", "WoverPninety",
             "ccshape", "ccshapeIqrLo", "ccshapeIqrHi", "accWcDev", "accWcCf", "nClassWc",
             "cshape", "cshapeIqrLo", "cshapeIqrHi", "nShape", "cphi", "cphiIqrLo", "cphiIqrHi",
             "czeroPhi", "czeroPhiIqrLo", "czeroPhiIqrHi",
             "czero", "czeroLo", "czeroHi", "czeroIqrLo", "czeroIqrHi", "czeroPten", "czeroPninety",
             "Dw", "DwPten", "DwPninety", "WstoryRatio", "WstoryPten", "WstoryPninety",
             "downhillN", "downhillRest", "restN", "restDownhill",
             "accEcdev", "accEcf", "accDrift", "accDriftOwn", "nClass", "accEnear", "accDnear", "nNear",
             "nHist", "thetaStar", "thetaStarLo", "thetaStarHi", "tStarMinusTnf", "tStarMinusTnfLo", "tStarMinusTnfHi",
             "tcMinusTstar", "tcMinusTstarLo", "tcMinusTstarHi", "tStaticMinusTstar", "tStaticMinusTstarLo", "tStaticMinusTstarHi",
             "WstarWb", "WstarWbLo", "WstarWbHi", "WtnfWb", "WtnfWbLo", "WtnfWbHi", "WstarWtnf", "WstarWtnfLo", "WstarWtnfHi",
             "tLastMinusTstar", "tLastMinusTstarLo", "tLastMinusTstarHi", "keStarWb", "keStarWbLo", "keStarWbHi",
             "tLastWithinK", "tLastWithinN", "shareAfterTnf", "restRecovers",
             "accTwoBranch", "accKeIntact", "restComTaN", "restComTaK", "restComTstarN", "restComTstarK",
             "bscaleDamped", "bscaleUndamped"]
    for tag in "ABCDE":
        stubs += [f"accBand{tag}", f"nBand{tag}"]
    defined = {l.split("{")[1].split("}")[0] for l in lines if l.startswith("\\newcommand")}
    for model in WORD.values():
        for s in SETW.values():
            for st in stubs:
                name = st + model + s
                if "\\" + name not in defined:
                    lines.append(f"\\newcommand{{\\{name}}}{{--}}")
    # IDA collapse-bracket stats: end-of-record convention vs full continuation
    ida_p = Path(r"E:\n0r53\results\ida_summary.json")
    if ida_p.exists():
        ida = json.loads(ida_p.read_text())
        for mdl, vv in ida.items():
            w = WORD.get(mdl)
            if not w or "ALL" not in vv:
                continue
            a = vv["ALL"]
            lines.append(f"\\newcommand{{\\truncInflatedN{w}}}{{{a['ratio_trunc_records_gt1']}}}")
            if a.get("ratio_trunc_max") is not None and a["ratio_trunc_max"] > 1:
                lines.append(f"\\newcommand{{\\truncInflatedMax{w}}}{{{round(100*(a['ratio_trunc_max']-1))}}}")
            lines.append(f"\\newcommand{{\\collAfterEndIda{w}}}{{{round(100*a['frac_coll_after_record_at_Sc'])}}}")
            lines.append(f"\\newcommand{{\\medianSc{w}}}{{{f(a['median_Sc'],2)}}}")
            lines.append(f"\\newcommand{{\\cmr{w}}}{{{f(a['CMR'],2)}}}")
    cai_p = Path(r"E:\n0r53\analysis\collapse_after_input.json")
    if cai_p.exists():
        cai = json.loads(cai_p.read_text())
        wmap = {"SMF2B": "TwoB", "SMF2CG": "TwoCG", "SMF4B": "FourB", "SMF4CG": "FourCG",
                "SMF8B": "EightB", "SMF8CG": "EightCG", "SMF12B": "TwelveB", "SMF12CG": "TwelveCG",
                "SMF20B": "TwentyB", "SMF20CG": "TwentyCG"}
        for mdl, vv in cai.items():
            w = wmap.get(mdl)
            if not w or not vv.get("n_coll"):
                continue
            lines.append(f"\\newcommand{{\\collAfterEndShare{w}}}{{{round(100*vv['after_end']/vv['n_coll'])}}}")
            lines.append(f"\\newcommand{{\\collAfterTnfShare{w}}}{{{round(100*vv['after_t95']/vv['n_coll'])}}}")
            lines.append(f"\\newcommand{{\\collN{w}}}{{{vv['n_coll']}}}")
    # barrier path dependence: best-available barrier over m1/storey/shape paths
    pc_p = Path(r"E:\n0r53\analysis\pattern_compare.json")
    if pc_p.exists():
        pc = json.loads(pc_p.read_text())
        for mdl, vv in pc.items():
            w = WORD.get(mdl)
            if not w or not (vv.get("c0_min_multi") or {}).get("n"):
                continue
            a, b = vv["c0_m1_multi"], vv["c0_min_multi"]
            macg(f"nMulti{w}", str(b["n"]))
            macg(f"czeroMoneMulti{w}", f(a["median"], 3))
            macg(f"czeroMin{w}", f(b["median"], 3))
            macg(f"czeroMinLo{w}", f(b["ci95"][0], 3))
            macg(f"czeroMinHi{w}", f(b["ci95"][1], 3))
            for alt, nm in (("story", "Story"), ("shape", "Shape")):
                r = vv.get(f"{alt}_W_ratio")
                if r:
                    macg(f"Wratio{nm}{w}", f(r["median"], 3))
                    macg(f"Wratio{nm}N{w}", str(r["n"]))
                    macg(f"Wlower{nm}{w}", str(round(100 * r["frac_below_095"])))
        have = {l.split("{")[1].split("}")[0] for l in lines if l.startswith("\\newcommand")}
        for w in WORD.values():
            for nm in ("nMulti", "czeroMoneMulti", "czeroMin", "czeroMinLo", "czeroMinHi",
                       "WratioStory", "WratioStoryN", "WlowerStory", "WratioShape", "WratioShapeN", "WlowerShape"):
                if f"\\{nm}{w}" not in have:
                    macg(f"{nm}{w}", "--")
    # consistent theta_c redefinition on drift-limited frames (4CG, 8CG)
    stc_p = Path(r"E:\n0r53\analysis\sens_theta_consistent.json")
    if stc_p.exists():
        stc = json.loads(stc_p.read_text())
        for mdl, vv in stc.items():
            w = WORD.get(mdl)
            s = vv.get("summary") if w else None
            if not s:
                continue
            macg(f"thetaTenZeroK{w}", str(s["0.10"]["beta_crit_zero"]))
            macg(f"thetaTenN{w}", str(s["n_states"]))
            macg(f"thetaFifteenC{w}", f(s["0.15"]["c_all"]["median"], 2))
            t20 = s["0.20"]
            pr, ls = t20.get("paired_ratio_resolved"), t20.get("lockstep_resolved")
            if pr and ls:
                macg(f"thetaTwentyNres{w}", str(pr["n"]))
                macg(f"thetaTwentyC{w}", f(t20["c_resolved"]["median"], 2))
                macg(f"thetaTwentyRatio{w}", f(pr["median"], 2))
                macg(f"thetaTwentyRatioLo{w}", f(pr["ci95"][0], 2))
                macg(f"thetaTwentyRatioHi{w}", f(pr["ci95"][1], 2))
                macg(f"thetaTwentyW{w}", f(ls["W_ratio_median"], 2))
                macg(f"thetaTwentyWpninety{w}", f(ls["W_ratio_p90"], 1))
                macg(f"thetaTwentyE{w}", f(ls["E_ratio_median"], 2))
                macg(f"thetaTwentyCorr{w}", f(ls["corr_logW_logE"], 2))
                macg(f"thetaTwentyTrunc{w}", str(t20["exit"].get("trunc", 0)))
    # pre-registered control H6(i): tangent-stiffness sign
    kt_p = Path(r"E:\n0r53\analysis\ktan_control.json")
    if kt_p.exists():
        for mdl, s in json.loads(kt_p.read_text()).items():
            w = WORD.get(mdl)
            if not w:
                continue
            macg(f"ktN{w}", str(s["n"]))
            macg(f"ktAcc{w}", pct(s["acc_ktan"], 0))
            macg(f"ktAccE{w}", pct(s["acc_E"], 0))
            macg(f"ktIndef{w}", pct(s["share_indefinite"], 0))
            if s.get("share_indefinite_committed") is not None:
                macg(f"ktIndefC{w}", pct(s["share_indefinite_committed"], 0))
            if s.get("share_indefinite_recoverable") is not None:
                macg(f"ktIndefR{w}", pct(s["share_indefinite_recoverable"], 0))
            if s.get("acc_ktan_transition") is not None:
                macg(f"ktAccTr{w}", pct(s["acc_ktan_transition"], 0))
            d0, lo, hi = s["diff_E_minus_ktan"]
            macg(f"ktDiff{w}", f(100 * d0, 0)); macg(f"ktDiffLo{w}", f(100 * lo, 0)); macg(f"ktDiffHi{w}", f(100 * hi, 0))
    # kinematic alternatives (drift + kinetic-energy rules)
    ka_p = Path(r"E:\n0r53\analysis\kinematic_alternatives.json")
    if ka_p.exists():
        kaj = json.loads(ka_p.read_text())
        NUMW = {0: "Zero", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
                8: "Eight", 9: "Nine", 10: "Ten"}
        cnt = defaultdict(lambda: [0, 0, 0])
        for mdl, vv in kaj.items():
            w = WORD.get(mdl)
            if not w:
                continue
            def kname(s):
                return s.replace("_cv", "cv").replace("K2", "Ktwo").replace("K3", "Kthree").replace("-", "Minus")
            for k, v in vv["acc"].items():
                macg(f"ka{kname(k)}{w}", pct(v, 1))
            for k, (d0, lo, hi) in vv["diff"].items():
                nm = kname(k)
                macg(f"ka{nm}{w}", f(100 * d0, 1))
                macg(f"ka{nm}Lo{w}", f(100 * lo, 1))
                macg(f"ka{nm}Hi{w}", f(100 * hi, 1))
                cnt[nm][0 if lo > 0 else (2 if hi < 0 else 1)] += 1
        for nm, (win, tie, loss) in cnt.items():
            macg(f"ka{nm}Win", NUMW.get(win, str(win)).lower())
            macg(f"ka{nm}Tie", NUMW.get(tie, str(tie)).lower())
            macg(f"ka{nm}Loss", NUMW.get(loss, str(loss)).lower())
    ca_p = Path(r"E:\n0r53\analysis\collapse_after_input.json")
    if ca_p.exists():
        caj = json.loads(ca_p.read_text())
        for mdl, vv in caj.items():
            w = WORD.get(mdl)
            if not w:
                continue
            macg(f"collEnd{w}", str(vv["after_end"]))
            macg(f"collAfterTnf{w}", str(vv["after_t95"]))
    lc_p = Path(r"E:\n0r53\analysis\label_cause.json")
    if lc_p.exists():
        lcj = json.loads(lc_p.read_text())
        lcj = {k: v for k, v in lcj.items() if k.startswith("SMF")}
        macg("nCommittedAll", str(sum(v["committed"] for v in lcj.values())))
        macg("nCommittedNonconv", str(sum(v["nonconv"] for v in lcj.values())))
    # A14: generic early-warning-signal control on the pre-release window
    ew_p = Path(r"E:\n0r53\analysis\ews_control.json")
    if ew_p.exists():
        ewj = json.loads(ew_p.read_text())
        macg("ewsWindow", f(ewj["W"], 1))
        macg("ewsN", str(ewj["n"]))
        EWSM = {"std": "Var", "ar1": "Arone", "sdet": "VarDet"}
        for mdl, vv in ewj["per_model"].items():
            w = WORD.get(mdl)
            if not w:
                continue
            macg(f"ewsAucEnergy{w}", f(vv["energy_auc"], 2))
            macg(f"ewsAucDrift{w}", f(vv["drift_auc"], 2))
            for k, nm in EWSM.items():
                macg(f"ewsAuc{nm}{w}", f(vv[f"{k}_auc"], 2))
            best = max(vv[f"{k}_auc"] for k in EWSM)
            macg(f"ewsAucBest{w}", f(best, 2))
            macg(f"ewsGap{w}", f(100 * (vv["energy_auc"] - best), 0))
            if vv.get("auc_gap_ci95"):
                macg(f"ewsGapLo{w}", f(100 * vv["auc_gap_ci95"][0], 0))
                macg(f"ewsGapHi{w}", f(100 * vv["auc_gap_ci95"][1], 0))
            if vv.get("best_auc_ci95"):
                macg(f"ewsBestLo{w}", f(vv["best_auc_ci95"][0], 2))
                macg(f"ewsBestHi{w}", f(vv["best_auc_ci95"][1], 2))
            if vv.get("best_ews"):
                macg(f"ewsBestName{w}", vv["best_ews"])
            if vv.get("n_events") is not None:
                macg(f"ewsNEv{w}", str(vv["n_events"]))
        g = [vv["energy_auc"] - max(vv[f"{k}_auc"] for k in EWSM)
             for vv in ewj["per_model"].values()]
        macg("ewsGapMin", f(100 * min(g), 0))
        macg("ewsGapMax", f(100 * max(g), 0))
        bestAuc = [max(vv[f"{k}_auc"] for k in EWSM) for vv in ewj["per_model"].values()]
        macg("ewsBestMin", f(min(bestAuc), 2))
        macg("ewsBestMax", f(max(bestAuc), 2))
        enAuc = [vv["energy_auc"] for vv in ewj["per_model"].values()]
        macg("ewsAucEnMin", f(min(enAuc), 2))
        macg("ewsAucEnMax", f(max(enAuc), 2))
        for k, nm in EWSM.items():
            macg(f"ewsAuc{nm}Pool", f(ewj["pooled"][f"{k}_auc"], 2))
        macg("ewsAucEnPool", f(ewj["pooled"]["energy_auc"], 2))
        macg("ewsAucDriftPool", f(ewj["pooled"]["drift_auc"], 2))
    # A16 horizon-expiry audit: undecided-at-horizon recoverable labels
    hz_p = Path(r"E:\n0r53\analysis\horizon_audit.json")
    if hz_p.exists():
        hz = json.loads(hz_p.read_text())
        ztot = sum(v["rec_settled"] + v["rec_horizon"] + v["committed"] + v["censored"]
                   for v in hz["zic"].values())
        macg("hzZicN", str(sum(v["rec_horizon"] for v in hz["zic"].values())))
        macg("hzZicTot", str(ztot))
        macg("hzZicLawN", str(hz["law_hits"]["n"]))
        macg("hzKickN", str(sum(v["rec_horizon"] for v in hz["kick"].values())))
        macg("hzKickUN", str(sum(v["rec_horizon"] for v in hz["kick_undamped"].values())))
        for fam, pre in (("zic", "hzZic"), ("kick", "hzKick"), ("kick_undamped", "hzKickU")):
            for mdl, vv in hz[fam].items():
                w = WORD.get(mdl)
                if w:
                    macg(f"{pre}N{w}", str(vv["rec_horizon"]))
    cs_p = Path(r"E:\n0r53\analysis\horizon_c0_sens.json")
    if cs_p.exists():
        cs = json.loads(cs_p.read_text())
        for mdl, vv in cs.items():
            w = WORD.get(mdl)
            if w:
                macg(f"czeroSensD{w}", f(vv["dmed"], 3))
                macg(f"czeroSensTouched{w}", str(vv["touched"]))
                macg(f"czeroSensMed{w}", f(vv["c0_med_censored"], 3))
        dd = [v["dmed"] for k, v in cs.items() if k in WORD]
        macg("czeroSensDMin", f(min(dd), 3))
        macg("czeroSensDMax", f(max(dd), 3))
    sh_p = Path(r"E:\n0r53\analysis\sens_horizon.json")
    if sh_p.exists():
        sh = json.loads(sh_p.read_text())
        for mdl, vv in sh.items():
            w = WORD.get(mdl)
            if not w:
                continue
            macg(f"shNtopU{w}", str(vv["n_beta_u_top_horizon"]))
            macg(f"shCzeroEx{w}", f(vv["c0_c_excl"], 3))
            macg(f"shCzeroFull{w}", f(vv["c0_c_full"], 3))
            macg(f"shAccEx{w}", f(vv["acc_cdev_excl_zic"], 3))
        du = [abs((v["c0_c_excl"] or 0) - (v["c0_c_full"] or 0)) for k, v in sh.items() if k in WORD]
        da = [abs((v["acc_cdev_excl_zic"] or 0) - (v["acc_cdev_full"] or 0)) for k, v in sh.items() if k in WORD]
        macg("shCzeroDMax", f(max(du), 3))
        macg("shAccDMax", f(max(da), 3))
        macg("shNtopUTot", str(sum(v["n_beta_u_top_horizon"] for k, v in sh.items() if k in WORD)))
        macg("shNtopDTot", str(sum(v["n_beta_d_top_horizon"] for k, v in sh.items() if k in WORD)))
    # A18: Deniz-style cumulative input-energy index vs released-state labels
    dz_p = Path(r"E:\n0r53\analysis\deniz_contrast.json")
    if dz_p.exists():
        dz = json.loads(dz_p.read_text())
        blks = [v for k, v in dz.items() if not k.startswith("_") and isinstance(v, dict)]
        if blks:
            def rng(key, nd):
                vs = [b[key] for b in blks if b.get(key) is not None]
                fmt = (lambda x: pct(x, 0)) if nd == "pct" else (lambda x: f(x, nd))
                return (fmt(min(vs)), fmt(max(vs))) if vs else (None, None)
            macg("denizNtot", str(sum(b["n"] for b in blks)))
            macg("denizPairsTot", str(sum(b["n_pairs"] for b in blks)))
            for stem, key, nd in (("denizRho", "rho_eta_committed", 2),
                                  ("denizLit", "acc_literal_eta_ge_1", "pct"),
                                  ("denizOrc", "acc_oracle_eta", "pct"),
                                  ("denizAccE", "acc_energy_cdev", "pct"),
                                  ("denizDeta", "pair_deta_med", 3),
                                  ("denizEiFrac", "EI_frac_at_tstar_med", 3)):
                lo, hi = rng(key, nd)
                if lo is not None:
                    macg(stem + "Min", lo)
                    macg(stem + "Hi", hi)
    # A7 escape-energy budget at the pass
    ke_p = Path(r"E:\n0r53\analysis\kick_energy_analysis.json")
    if ke_p.exists():
        kej = json.loads(ke_p.read_text())
        for mdl, vv in kej.items():
            w = WORD.get(mdl)
            s = vv.get("summary") if w else None
            if not s or not s.get("a_int"):
                continue
            macg(f"keN{w}", str(s["a_int"]["n"]))
            for nm, key in (("keAint", "a_int"), ("keBvisc", "b_visc"), ("keKin", "k_ke"),
                            ("keC", "c"), ("keCzero", "c0"), ("keToll", "toll_inferred")):
                if s.get(key):
                    macg(f"{nm}{w}", f(s[key]["median"], 2))
                    macg(f"{nm}Lo{w}", f(s[key]["ci95"][0], 2))
                    macg(f"{nm}Hi{w}", f(s[key]["ci95"][1], 2))
            if s.get("toll_corr") is not None:
                macg(f"keTollCorr{w}", f(s["toll_corr"], 2))
    # event-cluster holdout bootstrap (results/holdout_bootstrap_20261025.json, as in table_bootstrap.tex)
    bs_p = Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate"
                r"\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21\results\holdout_bootstrap_20261025.json")
    if bs_p.exists():
        br = json.loads(bs_p.read_text(encoding="utf-8"))["results"]
        lab = {m: m.replace("SMF", "") for m in WORD}
        rows = {m: br[f"{m}|ALL"] for m in WORD if br.get(f"{m}|ALL", {}).get("classification")}
        dl = [v["classification"]["paired_difference_observed"] for v in rows.values()]
        macg("bsDeltaMin", pct(min(dl), 0)); macg("bsDeltaMax", pct(max(dl), 0))
        wf = [v["classification"]["energy_wins_record_fraction"] for v in rows.values()]
        macg("bsWinRecMin", pct(min(wf), 0)); macg("bsWinRecMax", pct(max(wf), 0))
        for m, v in rows.items():
            w = WORD.get(m)
            if w:
                macg(f"bsWinRec{w}", pct(v["classification"]["energy_wins_record_fraction"], 0))
        macg("bsExclZeroK", str(sum(v["classification"]["record_mean_paired_difference_ci95"][0] > 0 for v in rows.values())))
        macg("bsRowsN", str(len(rows)))
        inside, below = [], []
        for m, v in rows.items():
            lo, hi = v["undamped_ratio"]["median_ci95"][0], v["undamped_ratio"]["median_ci95"][2]
            med = v["undamped_ratio"]["median_observed"]
            if lo >= 0.90 and hi <= 1.05:
                inside.append(lab[m])
            elif lo < 0.90 and med >= 0.90 and hi <= 1.05 + 1e-9:
                below.append((lab[m], lo))
        def _join(xs):
            return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "--")
        macg("bsInsideN", str(len(inside))); macg("bsInsideList", _join(inside))
        if below:
            macg("bsBelowList", _join([b[0] for b in below]))
            macg("bsBelowLoMin", f(min(b[1] for b in below), 2)); macg("bsBelowLoMax", f(max(b[1] for b in below), 2))
    # near-boundary summary over the Table-2 rows (2/4/8: ALL, 12/20: FF)
    T2 = [f"{m}|{'FF' if m.startswith(('SMF12', 'SMF20')) else 'ALL'}" for m in WORD]
    nr = {k: S[k]["near1s_Wc"] for k in T2 if k in S and S[k].get("near1s_Wc")}
    if nr:
        d = {k: v["acc_E_cdev"] - v["acc_D_dev"] for k, v in nr.items()}
        macg("nearDiffMinAll", pct(min(d.values()), 0))
        macg("nearDiffMaxAll", pct(max(d.values()), 0))
        macg("nearExclZeroK", str(sum(v["diff_E_cdev_minus_D_dev_ci95"][0] > 0 for v in nr.values())))
        macg("nearRowsN", str(len(nr)))
        bare4 = [v["acc_D_dev"] for k, v in nr.items() if k.split("|")[0] in ("SMF4B", "SMF8B", "SMF12B", "SMF20B")]
        if bare4:
            macg("nearDbareMin", pct(min(bare4), 0)); macg("nearDbareMax", pct(max(bare4), 0))
        own = [v["acc_E_own"] - v["acc_D_own"] for v in nr.values()]
        macg("nearOwnDiffMin", pct(min(own), 0)); macg("nearOwnDiffMax", pct(max(own), 0))
    # direction split of the transition-state coefficients (composite frames not mirror-symmetric)
    ds_p = Path(r"E:\n0r53\analysis\direction_split.json")
    if ds_p.exists():
        for mdl, v in json.loads(ds_p.read_text()).items():
            w = WORD.get(mdl)
            if not w or "c0_fwd_over_bwd" not in v:
                continue
            macg(f"dirCzeroFwd{w}", f(v["fwd"]["c0_median"], 2))
            macg(f"dirCzeroBwd{w}", f(v["bwd"]["c0_median"], 2))
            macg(f"dirNFwd{w}", str(v["fwd"]["n"]))
            macg(f"dirNBwd{w}", str(v["bwd"]["n"]))
            macg(f"dirRatio{w}", f(v["c0_fwd_over_bwd"][0], 2))
            macg(f"dirRatioLo{w}", f(v["c0_fwd_over_bwd"][1], 2))
            macg(f"dirRatioHi{w}", f(v["c0_fwd_over_bwd"][2], 2))
    # A8: extended vs standard push where both reach an exit (check_push_deep.json)
    cp_p = Path(r"E:\n0r53\analysis\check_push_deep.json")
    if cp_p.exists():
        cp = json.loads(cp_p.read_text())["_all"]
        macg("pdBothMedian", f(cp["median"], 3)); macg("pdBothMaxDev", pct(cp["max_abs_dev"], 0))
        macg("pdBothN", str(cp["both_resolved_n"]))
    # A8 audit: extended versus standard pushes in Table 2
    dv_p = Path(r"E:\n0r53\analysis\deep_vs_std_audit.json")
    if dv_p.exists():
        dv = json.loads(dv_p.read_text())
        macg("deepShiftCzero", f(dv["max_abs_c0_c"]["diff"], 3))
        macg("deepShiftCc", f(math.ceil(dv["max_abs_c_c"]["diff"] * 1000) / 1000, 3))
        macg("deepShiftCcFrame", dv["max_abs_c_c"]["model"].replace("SMF", ""))
        macg("deepAddedN", str(dv["n_added"]))
    # intact fwd/bwd symmetry (peak load factor over the common range)
    sy_p = Path(r"E:\n0r53\analysis\intact_symmetry.json")
    if sy_p.exists():
        sy = json.loads(sy_p.read_text())
        cg = [abs(v["peak_lam_rel_diff"]) for k, v in sy.items() if k.endswith("CG") and "peak_lam_rel_diff" in v]
        bb = [abs(v["peak_lam_rel_diff"]) for k, v in sy.items() if k.endswith("B") and "peak_lam_rel_diff" in v]
        if cg and bb:
            macg("symPeakDiffMinCG", pct(min(cg), 0))
            macg("symPeakDiffMaxCG", pct(max(cg), 0))
            macg("symPeakDiffMaxB", pct(max(bb), 1))
    # A6 residual collapse capacity of settled damaged states
    as_p = Path(r"E:\n0r53\analysis\aftershock_analysis.json")
    if as_p.exists():
        asj = json.loads(as_p.read_text())
        for mdl, vv in asj.items():
            w = WORD.get(mdl)
            s = vv.get("summary") if w else None
            if not s:
                continue
            macg(f"asN{w}", str(s["n"]))
            macg(f"asEvents{w}", str(s["n_events"]))
            macg(f"asFloorN{w}", str(s["status"]["collapse_at_floor"]))
            rho, ci = s["pooled"]["rho_signed"], s["pooled"]["ci95"]
            for nm, key in (("asRhoW", "w"), ("asRhoRes", "res"), ("asRhoRoof", "roof"), ("asRhoPeak", "peak")):
                macg(f"{nm}{w}", f(rho[key], 2))
            for nm, key in (("asDres", "w_minus_res"), ("asDroof", "w_minus_roof"), ("asDpeak", "w_minus_peak")):
                macg(f"{nm}Lo{w}", f(ci[key][0], 3))
                macg(f"{nm}Hi{w}", f(ci[key][1], 3))
            pr = s.get("prediction_log_rmse")
            if pr:
                for nm, key in (("asRmseWzero", "w_zero_param"), ("asRmseWfit", "w_fitted_cv"),
                                ("asRmseRes", "res_fitted_cv"), ("asRmseRoof", "roof_fitted_cv"),
                                ("asRmsePeak", "peak_fitted_cv")):
                    macg(f"{nm}{w}", f(pr[key], 2))
            # A12: primary = 'own' subset (both barriers resolved, intact push in the same direction);
            # 'all' / 'resolved' / 'trunc' are reported sensitivities
            sub = s.get("ms_sub") or {}
            own = sub.get("own") or {}
            RK = (("RmseWzero", "w_zero_param"), ("RmseWfit", "w_fitted_cv"), ("RmseRes", "res_fitted_cv"),
                  ("RmseRoof", "roof_fitted_cv"), ("RmsePeak", "peak_fitted_cv"), ("RmseQ", "q_fitted_cv"))
            if own.get("pred"):
                for nm, key in RK:
                    macg(f"asMs{nm}{w}", f(own["pred"]["rmse"][key], 2))
                macg(f"asMsMaeWzero{w}", f(own["pred"]["mae"]["w_zero_param"], 2))
                for nm, key in (("DrmseRes", "w_fitted_cv_minus_res_fitted_cv"),
                                ("DrmseZeroRes", "w_zero_param_minus_res_fitted_cv")):
                    ci = own["pred"]["d_rmse_ci95"].get(key)
                    if ci:
                        macg(f"asMs{nm}Lo{w}", f(ci[0], 2))
                        macg(f"asMs{nm}Hi{w}", f(ci[1], 2))
                macg(f"asMsRhoQ{w}", f(s["ms_rho_q"], 2))
                pp = own["partial"]
                macg(f"asPartW{w}", f(pp["w_given_res"], 2))
                macg(f"asPartWLo{w}", f(pp["w_given_res_ci95"][0], 2))
                macg(f"asPartWHi{w}", f(pp["w_given_res_ci95"][1], 2))
                macg(f"asPartRes{w}", f(pp["res_given_w"], 2))
                macg(f"asPartResLo{w}", f(pp["res_given_w_ci95"][0], 2))
                macg(f"asPartResHi{w}", f(pp["res_given_w_ci95"][1], 2))
                rr = own["rho"]
                for nm, key in (("asMsRhoW", "w"), ("asMsRhoRes", "res")):
                    macg(f"{nm}{w}", f(rr["rho_signed"][key], 2))
                macg(f"asMsDrhoResLo{w}", f(rr["ci95"]["w_minus_res"][0], 3))
                macg(f"asMsDrhoResHi{w}", f(rr["ci95"]["w_minus_res"][1], 3))
                wq = own.get("within_q")
                if wq and wq.get("rho_signed"):
                    for nm, key in (("asWqRhoW", "w"), ("asWqRhoRes", "res"), ("asWqRhoRoof", "roof"), ("asWqRhoPeak", "peak")):
                        macg(f"{nm}{w}", f(wq["rho_signed"][key], 2))
                    for nm, key in (("asWqDres", "w_minus_res"), ("asWqDroof", "w_minus_roof"), ("asWqDpeak", "w_minus_peak")):
                        macg(f"{nm}Lo{w}", f(wq["ci95"][key][0], 3))
                        macg(f"{nm}Hi{w}", f(wq["ci95"][key][1], 3))
                ro = own["R_over_w"]
                macg(f"asRoverWMs{w}", f(ro["median"], 2))
                macg(f"asRoverWMsLo{w}", f(ro["p10"], 2))
                macg(f"asRoverWMsHi{w}", f(ro["p90"], 2))
                macg(f"asRoverWMsN{w}", str(own["n_unc"]))
                macg(f"asMsFracGe{w}", pct(ro["frac_R_ge_w"], 0))
                macg(f"asMsOwnN{w}", str(own["n"]))
                macg(f"asMsOwnEv{w}", str(own["n_events"]))
            wqa = s.get("ms_within_q")
            if wqa and wqa.get("rho_signed"):
                for nm, key in (("asWqAllRhoW", "w"), ("asWqAllRhoRes", "res")):
                    macg(f"{nm}{w}", f(wqa["rho_signed"][key], 2))
                macg(f"asWqAllDresLo{w}", f(wqa["ci95"]["w_minus_res"][0], 3))
                macg(f"asWqAllDresHi{w}", f(wqa["ci95"]["w_minus_res"][1], 3))
            nmv = s.get("ms_no_mirror")
            if nmv and nmv.get("R_over_w") is not None:
                macg(f"asNmN{w}", str(nmv["n"]))
                macg(f"asNmRoverW{w}", f(nmv["R_over_w"]["median"] if isinstance(nmv["R_over_w"], dict) else nmv["R_over_w"], 2))
                pn = nmv.get("prediction_log_rmse") or {}
                if pn:
                    macg(f"asNmRmseWzero{w}", f(pn.get("w_zero_param"), 2))
                    macg(f"asNmRmseRes{w}", f(pn.get("res_fitted_cv"), 2))
            cnt = s.get("ms_counts") or {}
            for nm, key in (("asMsAllN", "all"), ("asMsTruncN", "trunc"), ("asMsMirrorN", "mirror"),
                            ("asMsResolvedN", "resolved")):
                if key in cnt:
                    macg(f"{nm}{w}", str(cnt[key]))
            for tag, blk in (("All", sub.get("all")), ("Resolved", sub.get("resolved")), ("Trunc", sub.get("trunc"))):
                if not blk or not blk.get("pred"):
                    continue
                macg(f"asMs{tag}RoverW{w}", f(blk["R_over_w"]["median"], 2))
                for nm, key in RK[:3]:
                    macg(f"asMs{tag}{nm}{w}", f(blk["pred"]["rmse"][key], 2))
                macg(f"asMs{tag}RhoW{w}", f(blk["rho"]["rho_signed"]["w"], 2))
                macg(f"asMs{tag}RhoRes{w}", f(blk["rho"]["rho_signed"]["res"], 2))
                macg(f"asMs{tag}PartW{w}", f(blk["partial"]["w_given_res"], 2))
                macg(f"asMs{tag}PartRes{w}", f(blk["partial"]["res_given_w"], 2))
            wst = s.get("ms_worst")
            if wst:
                macg(f"asMsWorstR{w}", f(wst["R"], 2))
                macg(f"asMsWorstLogRw{w}", f(wst["log_R_over_w"], 1))
                if wst.get("rmse0_without") is not None:
                    macg(f"asMsRmseWzeroWo{w}", f(wst["rmse0_without"], 2))
            sb = s.get("ms_sib")                       # A15: sibling-component second motion
            if sb and sb.get("pred"):
                macg(f"asSibN{w}", str(sb["n"]))
                macg(f"asSibRhoW{w}", f(sb["rho"]["rho_signed"]["w"], 2))
                macg(f"asSibRhoRes{w}", f(sb["rho"]["rho_signed"]["res"], 2))
                macg(f"asSibRmseWzero{w}", f(sb["pred"]["rmse"]["w_zero_param"], 2))
                macg(f"asSibRmseRes{w}", f(sb["pred"]["rmse"]["res_fitted_cv"], 2))
                macg(f"asSibRoverW{w}", f(sb["R_over_w"]["median"], 2))
                pr_ = sb.get("paired")
                if pr_:
                    macg(f"asSibPairN{w}", str(pr_["n"]))
                    macg(f"asSibPairRhoAB{w}", f(pr_["rho_RA_RB"], 2))
                    macg(f"asSibPairRhoW{w}", f(pr_["rho_RB_w"], 2))
                    macg(f"asSibPairRmseB{w}", f(pr_["rmse_w_B"], 2))
                    macg(f"asSibPairRmseA{w}", f(pr_["rmse_w_A"], 2))
                    macg(f"asSibPairRhoWA{w}", f(pr_["rho_RA_w"], 2))
                    macg(f"asSibPairLogR{w}", f(pr_["med_log_ratio"], 3))
            nb = ((s.get("a6_sub") or {}).get("own")) or {}
            if nb.get("R_over_w"):
                macg(f"asRoverWNb{w}", f(nb["R_over_w"]["median"], 2))
                macg(f"asRoverWNbLo{w}", f(nb["R_over_w"]["p10"], 2))
                macg(f"asRoverWNbHi{w}", f(nb["R_over_w"]["p90"], 2))
                macg(f"asRoverWNbN{w}", str(nb["n_unc"]))
                macg(f"asNbFracGe{w}", pct(nb["R_over_w"]["frac_R_ge_w"], 0))
            if s.get("loglog"):
                macg(f"asSlope{w}", f(s["loglog"]["slope"], 2))
                macg(f"asSlopeLo{w}", f(s["loglog"]["slope_ci95"][0], 2))
                macg(f"asSlopeHi{w}", f(s["loglog"]["slope_ci95"][1], 2))
            for t, v in (s.get("by_tag") or {}).items():
                tw = {"q0.50": "QFifty", "q0.70": "QSeventy", "q0.85": "QEightyFive", "q0.95": "QNinetyFive",
                      "early1": "EarlyOne", "early2": "EarlyTwo", "ta": "Ta"}.get(t)
                if tw:
                    macg(f"asR{tw}{w}", f(v["R_med"], 2))
                    macg(f"asW{tw}{w}", f(v["w_med"], 2))
                    macg(f"asRes{tw}{w}", pct(v["res_med"], 1))
            nb = ((s.get("a6_sub") or {}).get("own")) or {}
        _nbv = [((vv.get("summary") or {}).get("a6_sub") or {}).get("own", {}).get("R_over_w")
                for mdl, vv in asj.items() if mdl in WORD]
        _nbv = [x for x in _nbv if x]
        if _nbv:
            macg("asRoverWNbMin", f(min(x["median"] for x in _nbv), 2))
            macg("asRoverWNbMax", f(max(x["median"] for x in _nbv), 2))
            macg("asNbFracGeMin", pct(min(x["frac_R_ge_w"] for x in _nbv), 0))
            macg("asNbFracGeMax", pct(max(x["frac_R_ge_w"] for x in _nbv), 0))
            macg("asNbFrames", str(len(_nbv)))
    # truncated (t95) vs full-record collapse capacity
    t95_p = Path(r"E:\n0r53\analysis\t95_all.json")
    if t95_p.exists():
        tj = json.loads(t95_p.read_text())
        for mdl, vv in tj.items():
            w = WORD.get(mdl)
            if not w or "ALL" not in vv:
                continue
            a = vv["ALL"]
            macg(f"tnfN{w}", str(a["n_records"]))
            macg(f"tnfChanged{w}", str(round(100 * a["frac_changed"])))
            macg(f"tnfShift{w}", str(round(100 * (a["median_shift"] - 1))))
            macg(f"tnfShiftLo{w}", str(round(100 * (a["median_shift_ci95"][0] - 1))))
            macg(f"tnfShiftHi{w}", str(round(100 * (a["median_shift_ci95"][1] - 1))))
            macg(f"tnfPc{w}", str(round(100 * a["Pc_t95_at_med_full"])))
            macg(f"tnfPcLo{w}", str(round(100 * a["Pc_t95_at_med_full_ci95"][0])))
            macg(f"tnfPcHi{w}", str(round(100 * a["Pc_t95_at_med_full_ci95"][1])))
            macg(f"tnfRatio{w}", str(round(100 * (a["ratio_median"] - 1))))
            macg(f"tnfRatioPninety{w}", str(round(100 * (a["ratio_p90"] - 1))))
            macg(f"tnfBetaFull{w}", f(a["beta_full"], 2))
            macg(f"tnfBetaTnf{w}", f(a["beta_t95"], 2))
    # repeat-run (fork) audit of static pushes, addendum A13
    fk = Path(r"E:\n0r53\analysis\fork_rate.csv")
    if fk.exists():
        import csv as _csv
        import statistics as _st
        fr = list(_csv.DictReader(fk.open(encoding="utf-8")))

        def _dev(r):
            if not (r["W_canon"] and r["W_r1"] and r["W_r2"]):
                return None
            w0 = float(r["W_canon"])
            if abs(w0) == 0:
                return None
            s = (max(w0, float(r["W_r1"]), float(r["W_r2"]))
                 - min(w0, float(r["W_r1"]), float(r["W_r2"]))) / abs(w0)
            flip = r["lim_r1"] != r["lim_canon"] or r["lim_r2"] != r["lim_canon"]
            return s, flip

        done = [r for r in fr if _dev(r) is not None]
        dev = [_dev(r) for r in done]
        ndev = sum(1 for s, fp in dev if s > 1e-6 or fp)
        nflip = sum(1 for s, fp in dev if fp)
        spreads = [s for s, fp in dev if s > 1e-6 or fp]
        bare_done = [r for r in done if r["model"].endswith("B")]
        bare_dev = [d for d in (_dev(r) for r in bare_done) if d and (d[0] > 1e-6 or d[1])]
        cg_done = [r for r in done if r["model"].endswith("CG")]
        cg_dev = [d for d in (_dev(r) for r in cg_done) if d and (d[0] > 1e-6 or d[1])]
        def _steps(r):
            try:
                return int(float(r["n_steps_canon"])), int(float(r["n_steps_r1"])), int(float(r["n_steps_r2"]))
            except Exception:
                return None
        sameW = sum(1 for r, (s, fp) in zip(done, dev)
                    if s <= 1e-6 and not fp
                    and (lambda t: t is not None and len(set(t)) > 1)(_steps(r)))
        ident = sum(1 for r, (s, fp) in zip(done, dev)
                    if s <= 1e-6 and not fp
                    and (lambda t: t is not None and len(set(t)) == 1)(_steps(r)))
        macg("forkNpush", str(len(fr)))
        macg("forkNdone", str(len(done)))
        macg("forkIdent", str(ident))
        macg("forkSameW", str(sameW))
        macg("forkDevW", str(ndev - nflip))
        macg("forkDev", str(ndev))
        macg("forkDevPct", str(round(100 * ndev / len(done))))
        macg("forkFlip", str(nflip))
        macg("forkSpreadMed", f(_st.median(spreads) * 100, 2) if spreads else "--")
        macg("forkSpreadMax", f(max(spreads) * 100, 1) if spreads else "--")
        macg("forkBareDev", str(len(bare_dev)))
        macg("forkBareN", str(len(bare_done)))
        macg("forkCGN", str(len(cg_done)))
        macg("forkCGDevPct", str(round(100 * len(cg_dev) / len(cg_done))))
        macg("forkMissR", str(sum(1 for r in fr if r["W_canon"] and (not r["W_r1"] or not r["W_r2"]))))
        macg("forkMissC", str(sum(1 for r in fr if not r["W_canon"] and (r["W_r1"] or r["W_r2"]))))
        macg("forkMissCBare", str(sum(1 for r in fr if not r["W_canon"] and (r["W_r1"] or r["W_r2"]) and r["model"].endswith("B"))))
        macg("forkNoBar", str(sum(1 for r in fr if not r["W_canon"] and not r["W_r1"] and not r["W_r2"])))
    # deterministic-rerun verdict (addendum A17): det vs canonical barrier work
    fdp = Path(r"E:\n0r53\analysis\fork_det.json")
    if fdp.exists():
        fdd = json.loads(fdp.read_text())
        dc = fdd.get("dev_counts") or {}
        n_tot = sum(v["n"] for v in dc.values())
        n_g1 = sum(v["gt1pct"] for v in dc.values())
        n_g10 = sum(v["gt10pct"] for v in dc.values())
        meds = [abs(v["med"]) for v in dc.values() if v["med"] is not None]
        macs = [v["max"] for v in dc.values() if v["max"] is not None]
        cg = [m for m in dc if m.endswith("CG")]
        macg("detCompN", str(n_tot))
        macg("detGtOneN", str(n_g1))
        macg("detGtOnePct", f(100 * n_g1 / n_tot, 1) if n_tot else "--")
        macg("detGtTenN", str(n_g10))
        macg("detGtTenPct", f(100 * n_g10 / n_tot, 1) if n_tot else "--")
        macg("detMedDevMax", f"{max(meds):.1e}" if meds else "--")
        macg("detMaxDev", f(max(macs) * 100, 0) if macs else "--")
        macg("detCGGtOneN", str(sum(dc[m]["gt1pct"] for m in cg)))
    # 20CG deficit conditioning (addendum: bounded diagnosis, twentyCG_deficit.json)
    tcg = Path(r"E:\n0r53\analysis\twentyCG_deficit.json")
    if tcg.exists():
        td = json.loads(tcg.read_text())
        be = td["by_exit"]
        macg("tcgCzeroEdge", f(be["edge"]["c0_med"], 2))
        macg("tcgNEdge", str(be["edge"]["n"]))
        macg("tcgCzeroStall", f(be["stall"]["c0_med"], 2))
        macg("tcgCzeroTrunc", f(be["trunc"]["c0_med"], 2))
        macg("tcgRerunMaxDev", pct(td["rerun_W_reldev_max"], 1))
    # release-velocity alignment with candidate patterns (escape_dir_align.json)
    eda = Path(r"E:\n0r53\analysis\escape_dir_align.json")
    if eda.exists():
        ej = json.loads(eda.read_text())
        for mdl, vv in ej.items():
            w = WORD.get(mdl)
            if not w:
                continue
            if vv.get("v2_shape"):
                macg(f"vAlignShape{w}", f(vv["v2_shape"]["med"], 2))
            if vv.get("v2_phi1"):
                macg(f"vAlignPhi{w}", f(vv["v2_phi1"]["med"], 2))
    # within-set duration test: commitment delay vs record t95 (duration_erosion.json)
    du = Path(r"E:\n0r53\analysis\duration_erosion.json")
    if du.exists():
        dj = json.loads(du.read_text())
        rhos = [v["rho_t95_delay_abs"] for v in dj.values()]
        meds = [v["delay_med"] for v in dj.values()]
        macg("durDelayRhoMin", f(min(rhos), 2))
        macg("durDelayRhoMax", f(max(rhos), 2))
        macg("durDelayMedMin", f(min(meds), 1))
        macg("durDelayMedMax", f(max(meds), 1))
        macg("durDelayFrames", str(len(dj)))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} lines -> {OUT}")


if __name__ == "__main__":
    main()
