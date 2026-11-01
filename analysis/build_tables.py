"""R53 analysis harness (lead-authored). Reads the campaign layout under RUNS and writes

  analysis/law_table.csv        one row per released state with any of W / E / E0
  analysis/history_table.csv    one row per collapse history (hi): timing, theta*, barriers, last crossing
  analysis/summary_by_frame.json medians with 95 % bootstrap CIs (event-cluster resampling: the two
horizontal components of each ground-motion event co-enter every replicate) per frame x set, H1-H7 metrics

Protocol: PROTOCOL_R53 v1.0 (c_dev = 1.13; drift threshold fixed on the development set SMF4B x FF).
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RUNS = Path(os.environ.get("N0R53_RUNS", r"E:\n0r53\runs"))
OUT = Path(os.environ.get("N0R53_OUT", r"E:\n0r53\analysis"))      # override only for audit builds
OUT.mkdir(exist_ok=True)
NO_DEEP = os.environ.get("N0R53_NO_DEEP") == "1"                    # audit: standard 0.08 pushes only
C_DEV = 1.13
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
MC_PATHS = [Path(r"E:\n0r53\results\model_checks.json"),
            Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R52_N0_ZERO_INPUT_COMMITMENT_2026-10-11\results\model_checks.json")]
RNG = np.random.default_rng(20261021)
NBOOT = 10000


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def model_checks() -> dict:
    mc = {}
    for p in MC_PATHS:
        if p.exists():
            for k, v in jload(p).items():
                mc.setdefault(k, v)
    return mc


def rset(rid: str) -> str:
    return "FF" if rid.startswith("FF") else "NF"


def key_of(rid, level, t_r) -> str:
    return f"{rid}__{level}__{float(t_r):.4f}"


# ----------------------------------------------------------------------------- loaders
def load_tree(phase: str, model: str) -> dict:
    d = RUNS / phase / model
    out = {}
    if d.exists():
        for p in d.glob("*.json"):
            if p.name.startswith("_"):
                continue
            stem = p.stem
            for sfx in ("__push_shape", "__push_story", "__push", "__kick"):
                if stem.endswith(sfx):
                    stem = stem[: -len(sfx)]
                    break
            try:
                out[stem] = jload(p)
            except Exception:
                pass
    return out


DRIFT_LIMIT = 0.15
STALL_FRAC = 0.01        # post hoc (A11): stall with lambda <= 1 % of its peak counts as at the edge


def w_collapse(d: dict, drift_limit: float = DRIFT_LIMIT):
    """Work to the collapse-admissible edge: peak work up to the EARLIER of
    (i) loss of effective resistance (first lambda<=0 after positive) and
    (ii) the collapse drift limit.  Returns (W_c, edge_type).  Falls back to
    W_barrier when no curve is stored; downhill -> (0.0, 'downhill')."""
    if d is None:
        return None, None
    if d.get("downhill"):
        return 0.0, "downhill"
    W_bar = d.get("W_barrier")
    c = np.asarray(d.get("curve") or [], dtype=float)
    if c.size == 0:
        return W_bar, ("edge" if W_bar is not None else None)
    sdr, lam, w = c[:, 2], c[:, 1], c[:, 3]
    pos = np.where(lam > 0)[0]
    if not len(pos):
        return 0.0, "downhill"
    i1 = int(pos[0])
    neg = np.where(lam[i1:] <= 0)[0]
    i_edge = i1 + int(neg[0]) if len(neg) else len(c)
    di = np.where(sdr >= drift_limit)[0]
    i_drift = int(di[0]) if len(di) else len(c)
    i = min(i_edge, i_drift)
    if i >= len(c):
        # solver stalled before an exit: with the load factor already below STALL_FRAC of its
        # peak the push is at the resistance edge for practical purposes ('stall', W complete);
        # otherwise the barrier is a genuine lower bound ('trunc')
        if lam[-1] <= STALL_FRAC * float(np.max(lam)):
            return float(np.max(w)), "stall"
        return float(np.max(w)), "trunc"
    w_at = float(w[i])
    if i_drift <= i_edge and sdr[i] >= drift_limit:
        if i > 0:
            ds = sdr[i] - sdr[i - 1]
            t = min(1.0, max(0.0, (drift_limit - sdr[i - 1]) / ds)) if ds > 0 else 0.0
            w_at = float(w[i - 1] + t * (w[i] - w[i - 1]))
        kind = "drift"
    else:
        if i > 0:
            dl = lam[i - 1] - lam[i]
            t = min(1.0, max(0.0, lam[i - 1] / dl)) if dl > 0 else 0.0
            w_at = float(w[i - 1] + t * (w[i] - w[i - 1]))
        kind = "edge"
    peak_before = float(np.max(w[:i])) if i > 0 else w_at
    return float(max(0.0, max(w_at, peak_before))), kind


def push_fields(d: dict, prefix: str) -> dict:
    if d is None or d.get("reproduce_status") not in ("released", None) and "W_barrier" not in d:
        return {f"W_{prefix}": None}
    Wc, lim = w_collapse(d)
    return {f"W_{prefix}": d.get("W_barrier"), f"Wmin_{prefix}": d.get("W_barrier_from_min"), f"lam0_{prefix}": d.get("lam0"),
            f"downhill_{prefix}": d.get("downhill"), f"edge_{prefix}": d.get("reached_edge"), f"sdr_edge_{prefix}": d.get("sdr_edge"),
            f"conv_{prefix}": d.get("converged"), f"ladder_{prefix}": d.get("first_step_ladder"),
            f"Wc_{prefix}": Wc, f"lim_{prefix}": lim}


def kick_fields(d: dict, prefix: str) -> dict:
    if d is None:
        return {f"beta_{prefix}": None}
    st = d.get("state", {})
    ke = st.get("snapshot", {}).get("ke") if st else None
    if ke is None:
        for rr in (d.get("runs") or {}).values():
            ke = (rr.get("snapshot_release") or {}).get("ke")
            if ke is not None:
                break
    b = d.get("beta_crit")
    return {f"beta_{prefix}": b, f"beta_lo_{prefix}": d.get("beta_lo"), f"beta_hi_{prefix}": d.get("beta_hi"),
            f"label1_{prefix}": d.get("label_beta1"), f"censored_{prefix}": d.get("censored_at") is not None or (b is None and d.get("beta_lo") == 8.0),
            f"E_{prefix}": (b * b * ke) if (b is not None and ke is not None) else None}


# ----------------------------------------------------------------------------- tables
def build():
    mc = model_checks()
    law_rows, hist_rows = [], []
    for model in MODELS:
        zic = load_tree("zic", model)
        if not zic:
            continue
        ida = load_tree("ida", model)
        rest = load_tree("rest", model)
        push = load_tree("push", model)
        # A8: first-mode pushes extended to 0.16 roof drift (same state, same solver) replace the
        # standard 0.08 pushes where available (4CG, 8CG, 12B, 12CG, 20B, 20CG)
        for k, v in ({} if NO_DEEP else load_tree("push_deep", model)).items():
            if v is not None and v.get("curve"):
                push[k] = v
        push_st = load_tree("push_story", model)
        push_sh = load_tree("push_shape", model)
        kick = load_tree("kick", model)
        kick_u = load_tree("kick_undamped", model)
        ktan = load_tree("ktan", model)
        eros = load_tree("erosion", model)
        mcm = mc.get(model) or {}
        Wb = mcm.get("work_to_zero_V_kipin") or mcm.get("work_to_peak_kipin")
        h_story = None
        # ---- per released state (from zic releases; attach W/E/E0)
        for stem, z in zic.items():
            rid, level = stem.split("__")[0], stem.split("__")[1]
            ts, ta = z.get("t_star"), z.get("t_a")
            tc = (z.get("ref") or {}).get("t_coll")
            for rk, rel in (z.get("releases") or {}).items():
                snap = rel.get("snapshot")
                if not snap:
                    continue
                t_r = float(rel["t_r"])
                k = key_of(rid, level, t_r)
                pm, pst, psh, kd, ku = push.get(k), push_st.get(k), push_sh.get(k), kick.get(k), kick_u.get(k)
                if pm is None and kd is None and ku is None:
                    continue
                kt = ktan.get(k)
                rz = rest.get(f"{rid}__{level}") or {}
                sdr = np.asarray(snap["sdr"], float)
                icr = int(np.argmax(np.abs(sdr)))
                row = dict(model=model, rid=rid, set=rset(rid), level=level, t_r=t_r,
                           dt_star=(ts - t_r) if (ts is not None and level == "hi") else None,
                           tag=(kd or ku or pm or {}).get("state", {}).get("tag"),
                           label_r52=("committed" if rel.get("committed") else "recoverable"),
                           ke=float(snap["ke"]), peak_sdr=float(np.max(np.abs(sdr))), peak_sdr_so_far=float(np.max(snap.get("peak_sdr_so_far", sdr))),
                           theta_c=float(sdr[icr]), icr=icr + 1, roof_disp=snap.get("roof_disp"), Wb=Wb)
                row.update(push_fields(pm, "m1"))
                if pst is not None:
                    row.update(push_fields(pst, "st"))
                if psh is not None:
                    row["W_shape"] = psh.get("W_shape", psh.get("W_barrier"))
                    row["KE_phi"] = psh.get("KE_phi")
                    wcs, lcs = w_collapse(psh)
                    row["Wc_shape"] = wcs
                    row["lim_shape"] = lcs
                row.update(kick_fields(kd, "d"))
                row.update(kick_fields(ku, "u"))
                if kt is not None and kt.get("reproduce_status") == "released":
                    row["ktan_unstable"] = bool(kt.get("ktan_unstable"))
                    row["lam_min"] = kt.get("lam_min")
                rr = (rz.get("rests") or {}).get(f"{t_r:.4f}")
                if rr is not None:
                    row["rest_committed"] = bool(rr.get("committed"))
                law_rows.append(row)
        # ---- per collapse history
        for stem, z in zic.items():
            rid, level = stem.split("__")[0], stem.split("__")[1]
            if level != "hi" or z.get("t_star") is None:
                continue
            ts, ta = float(z["t_star"]), float(z["t_a"])
            tc = float(z["ref"]["t_coll"])
            idj = ida.get(rid, {})
            t95 = idj.get("t95")
            rj = rest.get(stem, {})
            hist = z.get("hist") or {}
            ht = np.asarray(hist.get("t", []), float); hke = np.asarray(hist.get("ke", []), float)
            D = np.asarray(hist.get("d", []), float)
            theta_star = float(np.interp(ts, ht, np.max(np.abs(D), axis=1))) if len(ht) else None
            ke_star = float(np.interp(ts, ht, hke)) if len(ht) else None
            # W at t* and t_a from push tree
            W_star = (push.get(key_of(rid, "hi", ts)) or {}).get("W_barrier")
            W_a = (push.get(key_of(rid, "hi", ta)) or {}).get("W_barrier")
            # erosion knots
            kn = []
            for k2, e in eros.items():
                if not k2.startswith(f"{rid}__hi__"):
                    continue
                if e.get("converged") and e.get("W_barrier") is not None:
                    t_rk = e.get("t_r")
                    if t_rk is None:
                        t_rk = (e.get("state") or {}).get("t_r")
                    if t_rk is None:
                        t_rk = float(k2.split("__")[2])
                    kn.append((float(t_rk), float(e["W_barrier"])))
            kn.sort()
            t_last = W_t95 = W_first = None
            n_knots = len(kn)
            if n_knots >= 3 and len(ht):
                tk = np.array([p[0] for p in kn]); Wk = np.array([p[1] for p in kn])
                ke_k = np.array([hke[(ht >= a - 0.125) & (ht <= a + 0.125)].max() if np.any((ht >= a - 0.125) & (ht <= a + 0.125)) else np.nan for a in tk])
                cross = ke_k >= C_DEV * Wk
                if cross.any():
                    j = len(cross) - 1
                    while j >= 0 and cross[j]:
                        j -= 1
                    if j < len(cross) - 1:
                        t_last = float(tk[j + 1])
                if t95 is not None and tk[0] <= t95 <= tk[-1]:
                    W_t95 = float(np.interp(t95, tk, Wk))
                W_first = float(Wk[0])
            hist_rows.append(dict(model=model, rid=rid, set=rset(rid), sa_c=z.get("sa"), t95=t95, t_a=ta, t_star=ts, t_c=tc,
                                  t_star_static=rj.get("t_star_static"), rest_star_committed=rj.get("rest_star_committed"),
                                  theta_star=theta_star, ke_star=ke_star, W_star=W_star, W_a=W_a, W_t95=W_t95, W_first=W_first,
                                  n_knots=n_knots, t_last=t_last, dl=(t_last - ts) if t_last is not None else None, Wb=Wb,
                                  non_monotonic=z.get("non_monotonic")))
    # write
    for name, rows in (("law_table.csv", law_rows), ("history_table.csv", hist_rows)):
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with (OUT / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    print(f"law_table: {len(law_rows)} rows; history_table: {len(hist_rows)} rows")
    return law_rows, hist_rows


# ----------------------------------------------------------------------------- statistics
def event_id(rid: str) -> str:
    """FEMA P695 component ID -> ground-motion event (pairs the two horizontal components);
    same convention as holdout_bootstrap.event_id."""
    rid = str(rid)
    return rid.split("_")[0] if rid.startswith("NF") else rid[:-1]


def boot_median(values: np.ndarray, groups: np.ndarray) -> tuple[float, float, float]:
    """Median with 95 % CI by resampling ground-motion EVENTS with replacement: the
    component IDs passed in ``groups`` are mapped to event IDs, so the two horizontal
    components of one event always enter a replicate together."""
    values = np.asarray(values, float); groups = np.asarray([event_id(g) for g in groups])
    ok = np.isfinite(values)
    values, groups = values[ok], groups[ok]
    if len(values) == 0:
        return (np.nan, np.nan, np.nan)
    ug = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ug}
    meds = np.empty(NBOOT)
    for b in range(NBOOT):
        pick = RNG.choice(ug, size=len(ug), replace=True)
        sel = np.concatenate([idx[g] for g in pick])
        meds[b] = np.median(values[sel])
    return (float(np.median(values)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5)))


def fnum(x):
    try:
        v = float(x)
        return v
    except Exception:
        return np.nan


def summarize(law_rows, hist_rows):
    S = {}
    # development drift threshold: best on SMF4B x FF states with a barrier (as in the pilot), fixed thereafter
    dev = [r for r in law_rows if r["model"] == "SMF4B" and r["set"] == "FF" and fnum(r.get("W_m1")) == fnum(r.get("W_m1"))]
    y = np.array([r["label_r52"] == "committed" for r in dev]); pk = np.array([r["peak_sdr"] for r in dev])
    thr_dev = max((float(np.mean((pk >= t) == y)), t) for t in np.unique(pk))[1] if len(dev) else 0.1126
    S["_protocol"] = dict(c_dev=C_DEV, drift_threshold_dev=float(thr_dev), nboot=NBOOT)
    for model in MODELS:
        L = [r for r in law_rows if r["model"] == model]
        H = [r for r in hist_rows if r["model"] == model]
        if not L and not H:
            continue
        for sset in ("FF", "NF", "ALL"):
            Ls = [r for r in L if sset == "ALL" or r["set"] == sset]
            Hs = [r for r in H if sset == "ALL" or r["set"] == sset]
            if not Ls and not Hs:
                continue
            out = {"n_states": len(Ls)}
            T = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_d")) > 0 and fnum(r.get("W_m1")) > 0]
            g = np.array([r["rid"] for r in T])
            if T:
                c = np.array([r["E_d"] / r["W_m1"] for r in T])
                out["c_f"] = boot_median(c, g); out["c_f_iqr"] = [float(np.percentile(c, 25)), float(np.percentile(c, 75))]
                out["c_f_p10p90"] = [float(np.percentile(c, 10)), float(np.percentile(c, 90))]; out["c_f_logsd"] = float(np.log(c).std()); out["n_transition"] = len(T)
            Tc = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_d")) > 0 and fnum(r.get("Wc_m1")) > 0]
            if Tc:
                cc = np.array([r["E_d"] / r["Wc_m1"] for r in Tc]); gc = np.array([r["rid"] for r in Tc])
                out["c_c"] = boot_median(cc, gc); out["c_c_iqr"] = [float(np.percentile(cc, 25)), float(np.percentile(cc, 75))]
                out["c_c_p10p90"] = [float(np.percentile(cc, 10)), float(np.percentile(cc, 90))]
                out["c_c_logsd"] = float(np.log(cc).std()); out["n_transition_c"] = len(Tc)
                lm = np.array([r.get("lim_m1") for r in Tc])
                for k_ in ("drift", "edge", "stall", "trunc", "downhill"):
                    out[f"lim_{k_}_n"] = int((lm == k_).sum())
                oc = np.array([float(r["W_m1"]) / float(r["Wc_m1"]) for r in Tc if fnum(r.get("W_m1")) > 0 and fnum(r.get("Wc_m1")) > 0])
                if len(oc):
                    out["W_over_Wc"] = [float(np.median(oc)), float(np.percentile(oc, 10)), float(np.percentile(oc, 90))]
            Ts = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_d")) > 0 and fnum(r.get("W_shape")) > 0]
            if Ts:
                cs = np.array([r["E_d"] / r["W_shape"] for r in Ts]); gs = np.array([r["rid"] for r in Ts])
                out["c_shape"] = boot_median(cs, gs); out["c_shape_iqr"] = [float(np.percentile(cs, 25)), float(np.percentile(cs, 75))]
                out["n_shape"] = len(Ts)
            Tsc = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_d")) > 0 and fnum(r.get("Wc_shape")) > 0]
            if Tsc:
                csc = np.array([r["E_d"] / r["Wc_shape"] for r in Tsc]); gsc = np.array([r["rid"] for r in Tsc])
                out["c_cshape"] = boot_median(csc, gsc); out["c_cshape_iqr"] = [float(np.percentile(csc, 25)), float(np.percentile(csc, 75))]
                pe = [r for r in Ts if fnum(r.get("KE_phi")) > 0 and r.get("beta_d")]
                if pe:
                    cp = np.array([r["beta_d"] ** 2 * r["KE_phi"] / r["W_shape"] for r in pe])
                    out["c_phi"] = boot_median(cp, np.array([r["rid"] for r in pe]))
                    out["c_phi_iqr"] = [float(np.percentile(cp, 25)), float(np.percentile(cp, 75))]
                    pu = [r for r in pe if r.get("beta_u") is not None]
                    if pu:
                        cu = np.array([r["beta_u"] ** 2 * r["KE_phi"] / r["W_shape"] for r in pu])
                        out["c0_phi"] = boot_median(cu, np.array([r["rid"] for r in pu]))
                        out["c0_phi_iqr"] = [float(np.percentile(cu, 25)), float(np.percentile(cu, 75))]
            T0 = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_u")) > 0 and fnum(r.get("W_m1")) > 0]
            if T0:
                c0 = np.array([r["E_u"] / r["W_m1"] for r in T0]); g0 = np.array([r["rid"] for r in T0])
                out["c0_f"] = boot_median(c0, g0); out["c0_iqr"] = [float(np.percentile(c0, 25)), float(np.percentile(c0, 75))]
                out["c0_p10p90"] = [float(np.percentile(c0, 10)), float(np.percentile(c0, 90))]; out["c0_logsd"] = float(np.log(c0).std())
                out["H1a_pass"] = bool(0.90 <= out["c0_f"][0] <= 1.05 and np.log(out["c0_iqr"][1] / out["c0_iqr"][0]) <= 0.20)
                D = np.array([(r["E_d"] - r["E_u"]) / r["W_m1"] for r in T0 if fnum(r.get("E_d")) > 0])
                if len(D):
                    out["D_over_W"] = boot_median(D, np.array([r["rid"] for r in T0 if fnum(r.get("E_d")) > 0]))
                    out["D_over_W_p10p90"] = [float(np.percentile(D, 10)), float(np.percentile(D, 90))]
            BD = [r for r in Ls if r.get("tag") in ("ta", "tstar") and r.get("beta_d") is not None]
            if BD:
                out["b2_damped"] = float(np.median([r["beta_d"] ** 2 for r in BD]))
            BU = [r for r in Ls if r.get("tag") in ("ta", "tstar") and r.get("beta_u") is not None]
            if BU:
                out["b2_undamped"] = float(np.median([r["beta_u"] ** 2 for r in BU]))
            T0c = [r for r in Ls if r.get("tag") in ("ta", "tstar") and fnum(r.get("E_u")) > 0 and fnum(r.get("Wc_m1")) > 0]
            if T0c:
                c0c = np.array([r["E_u"] / r["Wc_m1"] for r in T0c]); g0c = np.array([r["rid"] for r in T0c])
                out["c0_c"] = boot_median(c0c, g0c); out["c0_c_iqr"] = [float(np.percentile(c0c, 25)), float(np.percentile(c0c, 75))]
                out["c0_c_p10p90"] = [float(np.percentile(c0c, 10)), float(np.percentile(c0c, 90))]
                out["c0_c_logsd"] = float(np.log(c0c).std())
            # pattern independence
            P = [r for r in Ls if fnum(r.get("W_st")) > 0 and fnum(r.get("W_m1")) > 0]
            if P:
                pr = np.array([r["W_st"] / r["W_m1"] for r in P])
                out["W_story_over_m1"] = [float(np.median(pr)), float(np.percentile(pr, 10)), float(np.percentile(pr, 90)), len(P)]
            # downhill vs rest-committed
            DH = [r for r in Ls if r.get("W_m1") is not None and r.get("beta_d") is not None]
            if DH:
                dh = np.array([fnum(r["W_m1"]) == 0 for r in DH]); rc = np.array([fnum(r["beta_d"]) == 0 for r in DH])
                out["downhill_n"] = int(dh.sum()); out["downhill_rest_committed"] = int((dh & rc).sum())
                out["rest_committed_n"] = int(rc.sum()); out["rest_committed_downhill"] = int((rc & dh).sum())
            # classifier
            Cl = [r for r in Ls if fnum(r.get("W_m1")) == fnum(r.get("W_m1"))]
            if Cl:
                yy = np.array([r["label_r52"] == "committed" for r in Cl]); ke = np.array([r["ke"] for r in Cl]); W = np.array([fnum(r["W_m1"]) for r in Cl])
                pk2 = np.array([r["peak_sdr"] for r in Cl])
                cf = out.get("c_f", [C_DEV])[0]
                out["acc_energy_cdev"] = float(np.mean((ke >= C_DEV * W) == yy))
                out["acc_energy_cf"] = float(np.mean((ke >= cf * W) == yy))
                out["acc_drift_dev_thr"] = float(np.mean((pk2 >= thr_dev) == yy))
                out["acc_drift_own_best"] = max(float(np.mean((pk2 >= t) == yy)) for t in np.unique(pk2))
                out["n_classified"] = len(Cl)
                with np.errstate(divide="ignore"):
                    m = np.where(W > 0, np.log(np.maximum(ke, 1e-9) / (cf * np.maximum(W, 1e-9))), np.inf)
                bands = {}
                for lo, hi in ((0, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 1.0), (1.0, np.inf)):
                    k = (np.abs(m) >= lo) & ((np.abs(m) < hi) if np.isfinite(hi) else (np.abs(m) >= lo))
                    if k.sum():
                        bands[f"[{lo},{hi})"] = [int(k.sum()), float(np.mean(((ke >= cf * W) == yy)[k]))]
                out["acc_by_margin_band"] = bands
                near = np.array([r.get("dt_star") is not None and abs(fnum(r["dt_star"])) < 1.0 for r in Cl])
                if near.sum():
                    out["acc_energy_cf_near1s"] = float(np.mean(((ke >= cf * W) == yy)[near]))
                    out["acc_drift_dev_near1s"] = float(np.mean(((pk2 >= thr_dev) == yy)[near]))
                    out["n_near1s"] = int(near.sum())
            # classifier with collapse-surface barrier W_c
            Clc = [r for r in Ls if fnum(r.get("Wc_m1")) == fnum(r.get("Wc_m1"))]
            if Clc:
                yy = np.array([r["label_r52"] == "committed" for r in Clc]); ke = np.array([r["ke"] for r in Clc]); W = np.array([fnum(r["Wc_m1"]) for r in Clc])
                cf = out.get("c_c", [C_DEV])[0]
                out["acc_cdev_Wc"] = float(np.mean((ke >= C_DEV * W) == yy))
                out["acc_cf_Wc"] = float(np.mean((ke >= cf * W) == yy))
                out["n_classified_Wc"] = len(Clc)
                # near-boundary (|t_r - t*| < 1 s) comparison on the collapse-surface barrier, both rules
                # transferred (c_dev, development drift threshold) and both frame-fitted (c_c; the
                # frame's own best drift threshold on all its classified states); paired event-cluster CI
                pkc = np.array([r["peak_sdr"] for r in Clc])
                nearc = np.array([r.get("dt_star") is not None and abs(fnum(r["dt_star"])) < 1.0 for r in Clc])
                if nearc.sum() >= 5:
                    thr_own = max(np.unique(pkc), key=lambda t: float(np.mean((pkc >= t) == yy)))
                    hitE = ((ke >= C_DEV * W) == yy).astype(float)
                    hitD = ((pkc >= thr_dev) == yy).astype(float)
                    out["near1s_Wc"] = {
                        "n": int(nearc.sum()),
                        "acc_E_cdev": float(hitE[nearc].mean()),
                        "acc_E_own": float(((ke >= cf * W) == yy)[nearc].mean()),
                        "acc_D_dev": float(hitD[nearc].mean()),
                        "acc_D_own": float(((pkc >= thr_own) == yy)[nearc].mean())}
                    evn = defaultdict(list)
                    for i in np.where(nearc)[0]:
                        evn[event_id(Clc[i]["rid"])].append(i)
                    ekn = sorted(evn)
                    rng_n = np.random.default_rng(11)
                    reps = []
                    for _ in range(5000):
                        ii = np.concatenate([evn[ekn[k]] for k in rng_n.integers(0, len(ekn), len(ekn))])
                        reps.append(hitE[ii].mean() - hitD[ii].mean())
                    out["near1s_Wc"]["diff_E_cdev_minus_D_dev_ci95"] = [float(np.percentile(reps, 2.5)),
                                                                        float(np.percentile(reps, 97.5))]
            # two-branch intact-energy rule: committed iff drift>=thr or KE>=Wb
            Cb = [r for r in Ls if r.get("Wb")]
            if Cb:
                yy = np.array([r["label_r52"] == "committed" for r in Cb])
                pk2 = np.array([r["peak_sdr"] for r in Cb]); ke = np.array([r["ke"] for r in Cb])
                Wb = np.array([r["Wb"] for r in Cb])
                out["acc_two_branch"] = float(np.mean(((pk2 >= thr_dev) | (ke >= Wb)) == yy))
                out["acc_ke_intact"] = float(np.mean((ke >= Wb) == yy))
                out["n_two_branch"] = len(Cb)
            # rest-release basin test: from-rest committed share per tag
            for tg in ("ta", "tstar"):
                S2 = [r for r in Ls if r.get("tag") == tg and r.get("rest_committed") is not None]
                if S2:
                    out[f"rest_committed_share_{tg}"] = float(np.mean([r["rest_committed"] for r in S2]))
                    out[f"rest_n_{tg}"] = len(S2)
            # histories
            if Hs:
                gh = np.array([r["rid"] for r in Hs])
                for name, fn in (("theta_star", lambda r: r["theta_star"]), ("t_star_minus_t95", lambda r: (r["t_star"] - r["t95"]) if r.get("t95") is not None else np.nan),
                                 ("tc_minus_tstar", lambda r: r["t_c"] - r["t_star"]), ("tstar_static_minus_tstar", lambda r: (r["t_star_static"] - r["t_star"]) if r.get("t_star_static") is not None else np.nan),
                                 ("W_star_over_Wb", lambda r: (r["W_star"] / r["Wb"]) if (r.get("W_star") is not None and r.get("Wb")) else np.nan),
                                 ("W_t95_over_Wb", lambda r: (r["W_t95"] / r["Wb"]) if (r.get("W_t95") is not None and r.get("Wb")) else np.nan),
                                 ("W_star_over_W_t95", lambda r: (r["W_star"] / r["W_t95"]) if (r.get("W_star") is not None and r.get("W_t95")) else np.nan),
                                 ("t_last_minus_tstar", lambda r: r["dl"] if r.get("dl") is not None else np.nan),
                                 ("ke_star_over_Wb", lambda r: (r["ke_star"] / r["Wb"]) if (r.get("ke_star") is not None and r.get("Wb")) else np.nan)):
                    vals = np.array([fnum(fn(r)) for r in Hs])
                    if np.isfinite(vals).sum():
                        out[name] = boot_median(vals, gh) + (int(np.isfinite(vals).sum()),)
                dl = np.array([fnum(r["dl"]) if r.get("dl") is not None else np.nan for r in Hs]); okdl = np.isfinite(dl)
                if okdl.sum():
                    out["t_last_within_0p5"] = [int(np.sum(np.abs(dl[okdl]) <= 0.5)), int(okdl.sum())]
                    out["H4_pass"] = bool(np.mean(np.abs(dl[okdl]) <= 0.5) >= 0.75)
                out["share_tstar_after_t95"] = float(np.mean([r["t_star"] > r["t95"] for r in Hs if r.get("t95") is not None])) if any(r.get("t95") is not None for r in Hs) else None
                out["rest_star_recovers_share"] = float(np.mean([not r["rest_star_committed"] for r in Hs if r.get("rest_star_committed") is not None])) if any(r.get("rest_star_committed") is not None for r in Hs) else None
                out["n_histories"] = len(Hs)
            S[f"{model}|{sset}"] = out
    (OUT / "summary_by_frame.json").write_text(json.dumps(S, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o)), encoding="utf-8")
    # compact printout
    for k, v in S.items():
        if k.startswith("_"):
            print(k, v); continue
        cf = v.get("c_f"); c0 = v.get("c0_f"); cc = v.get("c_c"); c0c = v.get("c0_c")
        print(f"{k:14s} nT={v.get('n_transition','-'):>4} c_f={cf[0]:.3f} [{cf[1]:.3f},{cf[2]:.3f}]" if cf else f"{k:14s} nT=-",
              f" c_c={cc[0]:.3f} [{cc[1]:.3f},{cc[2]:.3f}]" if cc else "",
              f" c0={c0[0]:.3f}" if c0 else "", f" c0_c={c0c[0]:.3f} [{c0c[1]:.3f},{c0c[2]:.3f}]" if c0c else "",
              f" lim(drift/edge/trunc)={v.get('lim_drift_n','-')}/{v.get('lim_edge_n','-')}/{v.get('lim_trunc_n','-')}" if v.get("n_transition_c") else "",
              f" accWc(cdev)={v.get('acc_cdev_Wc', float('nan')):.3f} accWc(cf)={v.get('acc_cf_Wc', float('nan')):.3f}" if v.get("n_classified_Wc") else "",
              f" acc E(cdev)={v.get('acc_energy_cdev', float('nan')):.3f} E(cf)={v.get('acc_energy_cf', float('nan')):.3f} drift(dev)={v.get('acc_drift_dev_thr', float('nan')):.3f}" if v.get("n_classified") else "",
              f" | nH={v.get('n_histories','-')} th*={v['theta_star'][0]:.4f} t*-t95={v['t_star_minus_t95'][0]:.2f} W*/Wb={v['W_star_over_Wb'][0]:.4f}" if v.get("theta_star") and v.get("t_star_minus_t95") and v.get("W_star_over_Wb") else "",
              f" tlast-t*={v['t_last_minus_tstar'][0]:+.3f} within0.5={v.get('t_last_within_0p5')}" if v.get("t_last_minus_tstar") else "")


if __name__ == "__main__":
    law, hist = build()
    summarize(law, hist)
