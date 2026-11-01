"""Residual collapse capacity of settled damaged states (A6) vs damage indicators.

Sources (addenda53, protocol R53v1.0+A6):
  RUNS/aftershock_a6/<model>  near-boundary states: mainshock at S_a,c truncated at the
                              recoverable releases early1/early2/t_a, then settled
  RUNS/aftershock_ms/<model>  classical mainshock-damaged states: full record at q*S_a,c
                              (q = 0.5, 0.7, 0.85, 0.95), then settled
  RUNS/barrier_intact/<model> barrier of the undeformed frame (normaliser)
Second motion: the same record from its beginning, collapse intensity bracketed to 3 %.
R = S_a,c(damaged) / S_a,c(intact, same record).  'collapse_at_floor' (R <= 0.05/1.25)
and 'censored_high' (R > 2.5) are kept as rank ties at the bound.

Damage indicators, all from the settled state before the second motion:
  w      = W_rem(settled, residual-drift direction) / W_rem(intact), harness barrier rule
  res    = max |residual storey drift|
  roof   = |residual roof drift|
  peak   = peak storey drift over mainshock + settling
Statistics: Spearman rank correlation of R with each indicator, event-cluster bootstrap
(10 000) of rho and of the paired differences rho(w) - rho(other); log-log slope of R on w
(uncensored states).  Writes analysis/aftershock_analysis.json.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata as _sp_rankdata

from build_tables import w_collapse, event_id

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "aftershock_analysis.json"
N_BOOT = 10000
FLOOR_R = 0.05 / 1.25
CAP_R = 2.5


def jl(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def rankdata(x):
    """0-based average ranks (ties averaged); identical to the former loop implementation."""
    return _sp_rankdata(np.asarray(x, float), method="average") - 1.0


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b)
    return float(np.corrcoef(ra, rb)[0, 1])


RESOLVED = ("drift", "edge", "stall")


def w_intact(model: str) -> dict:
    """Intact-frame barrier per push direction (+1: 'W_fwd', -1: 'W_bwd'), harness rule.
    barrier_intact_deep (0.20 roof drift) preferred; the 0.08 barrier_intact is a fallback
    whose 'trunc' exits are flagged.  Returns {sgn: (W, lim, src)}."""
    out, deep = {}, {}
    for src in ("barrier_intact", "barrier_intact_deep"):          # later source overrides
        d = jl(RUNS / src / f"{model}.json")
        if d is None:
            continue
        for k, sgn in (("W_fwd", 1.0), ("W_bwd", -1.0)):
            if d.get(k):
                w, lim = w_collapse(d[k])
                if w and w > 0 and (lim in RESOLVED or src == "barrier_intact"):
                    out[sgn] = (w, lim, src)
                    if src == "barrier_intact_deep":
                        deep[sgn] = (w, lim, src)
    # undeformed frame is geometrically symmetric: where one direction's deep push stalls with
    # resistance left (CG forward pushes, A6d ladder did not resolve them), use the resolved
    # opposite direction ('mirror'); rows record this so a resolved-direction-only check is possible
    for sgn in (1.0, -1.0):
        if sgn not in deep and -sgn in deep:
            out[sgn] = (deep[-sgn][0], deep[-sgn][1], "mirror")
    return out


def w_settled(model: str, fname: str, j: dict):
    """Settled-state barrier in the residual-drift direction: a6_barrier_deep (0.20) if
    present and its settle reproduction matched, else the A6 output's own 0.08 push."""
    dp = jl(RUNS / "a6_barrier_deep" / model / fname)
    if dp and dp.get("status") == "ok" and (dp.get("settle_max_abs_diff_sdr") or 0.0) <= 1e-9 and dp.get("W_fwd"):
        w, lim = w_collapse(dp["W_fwd"])
        return w, lim, "deep"
    wf = j.get("W_fwd")
    if not wf:
        return None, None, None
    w, lim = w_collapse(wf)
    return w, lim, "std"


def rows_for(model: str, height: float,
             families=("aftershock_a6", "aftershock_ms")) -> list[dict]:
    Wi_dir = w_intact(model)
    rows = []
    for fam in families:
        d = RUNS / fam / model
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            j = jl(p)
            st = j.get("status")
            if st not in ("ok", "collapse_at_floor", "censored_high"):
                continue
            s = j.get("settle") or {}
            w, lim, wsrc = w_settled(model, p.name, j)
            wi = Wi_dir.get(float(j.get("sgn", 1.0)))
            if w is None or wi is None:
                continue
            Wi, lim_i, src_i = wi
            R = j.get("R")
            R = FLOOR_R if st == "collapse_at_floor" else (CAP_R if st == "censored_high" else R)
            stt = j["state"]
            rows.append({"family": fam, "rid": stt["rid"], "event": event_id(stt["rid"]),
                         "rid2": j.get("rid2"),
                         "tag": f"q{j['q']:.2f}" if fam.startswith("aftershock_ms") else stt.get("tag"),
                         "q": float(j["q"]) if fam.startswith("aftershock_ms") else None,
                         "status": st, "R": float(R),
                         "w": w / Wi, "lim": lim, "w_src": wsrc, "lim_intact": lim_i, "intact_src": src_i,
                         "res": float(np.max(np.abs(s["final_sdr"]))),
                         "roof": abs(float(s["residual_roof_disp"])) / height,
                         "peak": float(s["max_sdr"])})
    return rows


def boot(rows, rng, n_boot=N_BOOT):
    ev = defaultdict(list)
    for i, r in enumerate(rows):
        ev[r["event"]].append(i)
    keys = sorted(ev)
    R = np.array([r["R"] for r in rows])
    X = {k: np.array([r[k] for r in rows]) for k in ("w", "res", "roof", "peak")}
    sign = {"w": 1, "res": -1, "roof": -1, "peak": -1}     # expected direction
    point = {k: sign[k] * spearman(R, X[k]) for k in X}
    reps = defaultdict(list)
    for _ in range(n_boot):
        idx = np.concatenate([ev[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
        rho = {k: sign[k] * spearman(R[idx], X[k][idx]) for k in X}
        for k in X:
            reps[k].append(rho[k])
        for k in ("res", "roof", "peak"):
            reps[f"w_minus_{k}"].append(rho["w"] - rho[k])
    ci = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in reps.items()}
    return {"rho_signed": point, "ci95": ci,
            "note": "signed so that positive = indicator ranks capacity in the expected direction"}


def loeo_predictions(unc, keys):
    """Leave-one-event-out log-linear fits of log R on log(indicator); 'q' enters linearly.
    Also the calibration-free prediction R_hat = w.  Returns (log R, {name: prediction}, events)."""
    ev = defaultdict(list)
    for i, r in enumerate(unc):
        ev[r["event"]].append(i)
    y = np.log([r["R"] for r in unc])
    pred = {"w_zero_param": np.log([r["w"] for r in unc])}
    for key in keys:
        x = np.array([r[key] for r in unc]) if key == "q" else np.log([max(r[key], 1e-6) for r in unc])
        p = np.empty(len(unc))
        for e, idx in ev.items():
            tr = np.setdiff1d(np.arange(len(unc)), idx)
            A = np.vstack([x[tr], np.ones(len(tr))]).T
            b, a = np.linalg.lstsq(A, y[tr], rcond=None)[0]
            p[idx] = a + b * x[idx]
        pred[f"{key}_fitted_cv"] = p
    return y, pred, ev


def pred_block(unc, keys):
    y, pred, _ = loeo_predictions(unc, keys)
    return {k: float(np.sqrt(np.mean((y - v) ** 2))) for k, v in pred.items()}


def pred_detail(unc, keys, rng, n_boot=N_BOOT):
    """RMSE and median absolute log-error of each prediction, and event-cluster bootstrap intervals
    of the RMSE differences barrier-minus-competitor (cross-validated predictions held fixed)."""
    y, pred, ev = loeo_predictions(unc, keys)
    err2 = {k: (y - v) ** 2 for k, v in pred.items()}
    ek = sorted(ev)
    pairs = [(a, b) for a in ("w_zero_param", "w_fitted_cv") for b in pred if not b.startswith("w_")]
    reps = defaultdict(list)
    for _ in range(n_boot):
        idx = np.concatenate([ev[ek[i]] for i in rng.integers(0, len(ek), len(ek))])
        r = {k: np.sqrt(np.mean(e[idx])) for k, e in err2.items()}
        for a, b in pairs:
            reps[f"{a}_minus_{b}"].append(r[a] - r[b])
    return {"rmse": {k: float(np.sqrt(np.mean(e))) for k, e in err2.items()},
            "mae": {k: float(np.median(np.abs(y - v))) for k, v in pred.items()},
            "d_rmse_ci95": {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
                            for k, v in reps.items()}}


def ms_block(sub, rng, n_boot=N_BOOT, by_q=True):
    """Indicator comparison on one subset of settled states (see SUBSETS in main)."""
    unc = [r for r in sub if r["status"] == "ok" and r["w"] > 0]
    nev = len({r["event"] for r in sub})
    out = {"n": len(sub), "n_unc": len(unc), "n_events": nev}
    if len(unc) <= 10 or nev < 5:
        return out
    lr = np.log([r["R"] / r["w"] for r in unc])
    keys = ("w", "res", "roof", "peak", "q") if by_q else ("w", "res", "roof", "peak")
    out.update({"R_over_w": {"median": float(np.exp(np.median(lr))), "p10": float(np.exp(np.percentile(lr, 10))),
                             "p90": float(np.exp(np.percentile(lr, 90))), "frac_R_ge_w": float(np.mean(lr >= 0))},
                "pred": pred_detail(unc, keys, rng, n_boot),
                "rho": boot(sub, rng, n_boot),
                "partial": partial_spearman(sub, rng, n_boot)})
    if by_q:
        out["within_q"] = within_q(sub, rng)
    return out


def within_q(sub, rng):
    """Spearman of R with each indicator inside each mainshock level q, n-weighted mean;
    event-cluster bootstrap of the mean and of w minus each competitor."""
    keys = ("w", "res", "roof", "peak")
    sign = {"w": 1, "res": -1, "roof": -1, "peak": -1}

    def stat(rows):
        g = defaultdict(list)
        for r in rows:
            g[r["q"]].append(r)
        acc, n = defaultdict(float), 0
        for v in g.values():
            if len(v) < 5:
                continue
            R = [r["R"] for r in v]
            for k in keys:
                acc[k] += len(v) * sign[k] * spearman(R, [r[k] for r in v])
            n += len(v)
        return {k: acc[k] / n for k in keys} if n else None

    point = stat(sub)
    ev = defaultdict(list)
    for r in sub:
        ev[r["event"]].append(r)
    ek = sorted(ev)
    reps = defaultdict(list)
    for _ in range(2000):
        s = stat([r for i in rng.integers(0, len(ek), len(ek)) for r in ev[ek[i]]])
        if s is None:
            continue
        for k in keys:
            reps[k].append(s[k])
        for k in ("res", "roof", "peak"):
            reps[f"w_minus_{k}"].append(s["w"] - s[k])
    return {"rho_signed": point,
            "ci95": {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in reps.items()}}


def partial_spearman(rows, rng, n_boot=N_BOOT):
    """Rank partial correlations rho(R, w | res) and rho(R, res | w) (residual drift signed so
    that positive = expected direction), with event-cluster bootstrap intervals."""
    def pc(R, w, res):
        r = [rankdata(R), rankdata(w), -rankdata(res)]
        c = np.corrcoef(r)
        rw, rr, wr = c[0, 1], c[0, 2], c[1, 2]
        return ((rw - rr * wr) / np.sqrt((1 - rr ** 2) * (1 - wr ** 2)),
                (rr - rw * wr) / np.sqrt((1 - rw ** 2) * (1 - wr ** 2)))

    R = np.array([r["R"] for r in rows]); W = np.array([r["w"] for r in rows]); S = np.array([r["res"] for r in rows])
    p0 = pc(R, W, S)
    ev = defaultdict(list)
    for i, r in enumerate(rows):
        ev[r["event"]].append(i)
    ek = sorted(ev)
    a, b = [], []
    for _ in range(n_boot):
        idx = np.concatenate([ev[ek[i]] for i in rng.integers(0, len(ek), len(ek))])
        x, y = pc(R[idx], W[idx], S[idx])
        a.append(x); b.append(y)
    return {"w_given_res": float(p0[0]), "w_given_res_ci95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))],
            "res_given_w": float(p0[1]), "res_given_w_ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}


def main():
    rng = np.random.default_rng(66)
    mc = json.loads(Path(r"E:\n0r53\results\model_checks.json").read_text())
    out = {}
    for model in ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]:
        rows = rows_for(model, mc[model]["height_in"])
        if len(rows) < 8:
            continue
        res = {"n": len(rows), "n_events": len({r["event"] for r in rows}),
               "status": {s: sum(r["status"] == s for r in rows) for s in ("ok", "collapse_at_floor", "censored_high")},
               "pooled": boot(rows, rng)}
        for fam in ("aftershock_a6", "aftershock_ms"):
            sub = [r for r in rows if r["family"] == fam]
            if len(sub) >= 8:
                res[fam] = {"n": len(sub), **boot(sub, rng)}
        unc = [r for r in rows if r["status"] == "ok" and r["w"] > 0]
        if len(unc) > 5:
            x, y = np.log([r["w"] for r in unc]), np.log([r["R"] for r in unc])
            A = np.vstack([x, np.ones_like(x)]).T
            slope, icpt = np.linalg.lstsq(A, y, rcond=None)[0]
            ev = defaultdict(list)
            for i, r in enumerate(unc):
                ev[r["event"]].append(i)
            keys = sorted(ev)
            sl = []
            for _ in range(N_BOOT):
                idx = np.concatenate([ev[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
                sl.append(np.linalg.lstsq(A[idx], y[idx], rcond=None)[0][0])
            res["loglog"] = {"n": len(unc), "slope": float(slope), "intercept": float(icpt),
                             "slope_ci95": [float(np.percentile(sl, 2.5)), float(np.percentile(sl, 97.5))]}
        # calibration-free prediction R_hat = w versus fitted damage-indicator models
        if len(unc) > 10:
            ev = defaultdict(list)
            for i, r in enumerate(unc):
                ev[r["event"]].append(i)
            y = np.log([r["R"] for r in unc])
            pred = {"w_zero_param": np.log([r["w"] for r in unc])}
            for key in ("w", "res", "roof", "peak"):
                x = np.log([max(r[key], 1e-6) for r in unc])
                p = np.empty(len(unc))
                for e, idx in ev.items():                     # leave-one-event-out
                    tr = np.setdiff1d(np.arange(len(unc)), idx)
                    A = np.vstack([x[tr], np.ones(len(tr))]).T
                    b, a = np.linalg.lstsq(A, y[tr], rcond=None)[0]
                    p[idx] = a + b * x[idx]
                pred[f"{key}_fitted_cv"] = p
            res["prediction_log_rmse"] = {k: float(np.sqrt(np.mean((y - v) ** 2))) for k, v in pred.items()}
            res["prediction_log_mae"] = {k: float(np.median(np.abs(y - v))) for k, v in pred.items()}
            res["R_over_w"] = {"median": float(np.exp(np.median(y - pred["w_zero_param"]))),
                               "p10": float(np.exp(np.percentile(y - pred["w_zero_param"], 10))),
                               "p90": float(np.exp(np.percentile(y - pred["w_zero_param"], 90)))}
            for fam in ("aftershock_ms", "aftershock_a6"):
                fr_ = [np.log(r["R"] / r["w"]) for r in unc if r["family"] == fam and r["w"] > 0]
                if len(fr_) > 3:
                    res[f"{fam}_R_over_w"] = {"n": len(fr_), "median": float(np.exp(np.median(fr_))),
                                              "p10": float(np.exp(np.percentile(fr_, 10))),
                                              "p90": float(np.exp(np.percentile(fr_, 90))),
                                              "log_rmse": float(np.sqrt(np.mean(np.square(fr_))))}
            ms_unc = [r for r in unc if r["family"] == "aftershock_ms"]
            nm = [r for r in ms_unc if r["intact_src"] != "mirror"]
            if len(nm) < len(ms_unc) and len(nm) > 10:          # sensitivity: own-direction intact barrier only
                fr_ = [np.log(r["R"] / r["w"]) for r in nm]
                res["ms_no_mirror"] = {"n": len(nm), "R_over_w": float(np.exp(np.median(fr_))),
                                       "prediction_log_rmse": pred_block(nm, ("w", "res", "roof", "peak", "q")),
                                       "partial": partial_spearman([r for r in rows if r["family"] == "aftershock_ms"
                                                                    and r["intact_src"] != "mirror"], rng)}
            if len(ms_unc) > 10:
                res["ms_prediction_log_rmse"] = pred_block(ms_unc, ("w", "res", "roof", "peak", "q"))
                res["ms_rho_q"] = -spearman([r["R"] for r in ms_unc], [r["q"] for r in ms_unc])
                ms_all = [r for r in rows if r["family"] == "aftershock_ms"]
                res["ms_within_q"] = within_q(ms_all, rng)
                res["ms_partial"] = partial_spearman(ms_all, rng)
            res["partial_all"] = partial_spearman(rows, rng)
            # A12 (post hoc, 2026-10-27): w is a measured ratio only where BOTH barriers reach an exit
            # (settled push: drift/edge/stall; intact push in the same direction: drift/edge/stall, no
            # mirror -- intact_symmetry.json shows the CG frames are not mirror-symmetric).  'own' is the
            # primary subset; 'resolved' (mirror normaliser allowed), 'all' and 'trunc' are sensitivities.
            for fam, short in (("aftershock_ms", "ms"), ("aftershock_a6", "a6")):
                fr = [r for r in rows if r["family"] == fam]
                if len(fr) < 8:
                    continue
                subsets = {
                    "own": [r for r in fr if r["lim"] in RESOLVED and r["intact_src"] != "mirror"
                            and r["lim_intact"] in RESOLVED],
                    "resolved": [r for r in fr if r["lim"] in RESOLVED],
                    "all": fr,
                    "trunc": [r for r in fr if r["lim"] == "trunc"]}
                res[f"{short}_counts"] = {k: len(v) for k, v in subsets.items()} | {
                    "mirror": sum(r["intact_src"] == "mirror" for r in fr)}
                res[f"{short}_sub"] = {k: ms_block(v, rng, N_BOOT if k == "own" else 2000, by_q=fam == "aftershock_ms")
                                       for k, v in subsets.items()}
                ou = [r for r in subsets["own"] if r["status"] == "ok" and r["w"] > 0]
                if ou:
                    wr = max(ou, key=lambda r: abs(np.log(r["R"] / r["w"])))
                    lr = np.log([r["R"] / r["w"] for r in ou])
                    keep = np.abs(lr) < abs(np.log(wr["R"] / wr["w"]))
                    res[f"{short}_worst"] = {k: wr[k] for k in ("rid", "tag", "R", "w", "lim", "res")} | {
                        "log_R_over_w": float(np.log(wr["R"] / wr["w"])),
                        "rmse0_without": float(np.sqrt(np.mean(lr[keep] ** 2))) if keep.any() else None}
            res["floor_censored_w_max"] = max([r["w"] for r in rows if r["status"] == "collapse_at_floor"], default=None)
            # A15: sibling-component second motion -- same damaged state, different record.
            sib = rows_for(model, mc[model]["height_in"], families=("aftershock_ms_sib",))
            sib_own = [r for r in sib if r["lim"] in RESOLVED and r["intact_src"] != "mirror"
                       and r["lim_intact"] in RESOLVED]
            if len(sib_own) >= 8:
                res["ms_sib"] = {"n": len(sib_own), **ms_block(sib_own, rng, N_BOOT, by_q=True)}
                # paired: same (rid, q) damaged state under the repeated vs sibling component
                key = {(r["rid"], r["q"]): r for r in rows
                       if r["family"] == "aftershock_ms" and r["lim"] in RESOLVED
                       and r["intact_src"] != "mirror" and r["lim_intact"] in RESOLVED}
                pair = [(r, key[(r["rid"], r["q"])]) for r in sib_own
                        if (r["rid"], r["q"]) in key and r["status"] == "ok"
                        and key[(r["rid"], r["q"])]["status"] == "ok"]
                if len(pair) >= 8:
                    rb = [a["R"] for a, _ in pair]; ra = [b["R"] for _, b in pair]
                    ww = [a["w"] for a, _ in pair]
                    res["ms_sib"]["paired"] = {
                        "n": len(pair),
                        "rho_RA_RB": spearman(ra, rb),
                        "med_log_ratio": float(np.median(np.log(np.asarray(rb) / np.asarray(ra)))),
                        "rho_RB_w": spearman(rb, ww), "rho_RA_w": spearman(ra, ww),
                        "rmse_w_B": float(np.sqrt(np.mean(np.log(np.asarray(rb) / np.asarray(ww)) ** 2))),
                        "rmse_w_A": float(np.sqrt(np.mean(np.log(np.asarray(ra) / np.asarray(ww)) ** 2)))}
            res["settled_lim"] = {l: sum(r["lim"] == l for r in rows) for l in ("drift", "edge", "stall", "trunc", "downhill")}
            res["w_src"] = {s: sum(r["w_src"] == s for r in rows) for s in ("deep", "std")}
            res["intact_src_counts"] = {s: sum(r["intact_src"] == s for r in rows)
                                        for s in ("barrier_intact", "barrier_intact_deep", "mirror")}
            res["intact"] = sorted({(r["intact_src"], r["lim_intact"]) for r in rows})
        by_tag = defaultdict(list)
        for r in rows:
            by_tag[r["tag"]].append(r)
        res["by_tag"] = {t: {"n": len(v), "R_med": float(np.median([r["R"] for r in v])),
                             "R_over_w_med": float(np.median([r["R"] / r["w"] for r in v if r["w"] > 0])),
                             "w_med": float(np.median([r["w"] for r in v])),
                             "res_med": float(np.median([r["res"] for r in v])),
                             "peak_med": float(np.median([r["peak"] for r in v]))} for t, v in sorted(by_tag.items())}
        out[model] = {"summary": res, "rows": rows}
        print(model, json.dumps({k: v for k, v in res.items() if k not in ("by_tag",)}, indent=None)[:900], flush=True)
        for t, v in res["by_tag"].items():
            print("   ", t, v, flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
