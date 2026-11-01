"""EWS control: do generic early-warning statistics (variance, lag-1 AR1,
skewness, kurtosis of the pre-release roof-drift window) predict commitment?

For every state in analysis/law_table.csv, slice the forced history
(runs/zic/{model}/{rid}__{level}.json -> hist.t, hist.d) on [t_r - W, t_r]
and compute canonical critical-transition statistics.  Compare AUC and
dev-fitted classification against the energy rule and drift baseline.

Post hoc addendum (A14): analysis of existing runs only; no new simulation.
"""
import json, csv, math, glob, os
import numpy as np

ROOT = r"E:\n0r53"
LAW = os.path.join(ROOT, "analysis", "law_table.csv")
OUT = os.path.join(ROOT, "analysis", "ews_control.json")
C_DEV = 1.13           # development constant (protocol)
THR_DEV = 0.1173397626 # development drift threshold
W = 2.5                # s, pre-release window
MINP = 20              # min samples in window
DEV = "SMF4B"

def feats(d):
    d = np.asarray(d, float)
    n = d.size
    cur = abs(d[-1])
    std_raw = float(np.std(d))
    t = np.arange(n)
    # linear detrending
    A = np.vstack([t, np.ones(n)]).T
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    r = d - A @ coef
    sd = float(np.std(r))
    if sd > 0:
        r0 = r[:-1] - r[:-1].mean(); r1 = r[1:] - r[1:].mean()
        den = math.sqrt(float((r0*r0).sum()*(r1*r1).sum()))
        ar1 = float((r0*r1).sum()/den) if den > 0 else float("nan")
        skew = float(np.mean((r/sd)**3))
        kurt = float(np.mean((r/sd)**4))
    else:
        ar1 = skew = kurt = float("nan")
    return cur, std_raw, sd, ar1, skew, kurt

def auc(y, s):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    m = ~np.isnan(s)
    y, s = y[m], s[m]
    if y.sum() == 0 or (~y).sum() == 0 or len(y) == 0:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s)+1)
    # tie-average ranks
    for v in np.unique(s):
        idx = s == v
        if idx.sum() > 1:
            ranks[idx] = ranks[idx].mean()
    return float((ranks[y].sum() - y.sum()*(y.sum()+1)/2) / (y.sum()*(~y).sum()))

def best_acc(y, s):
    """Accuracy at the threshold maximising Youden's J on (y,s) -> returns (acc,thr)."""
    y = np.asarray(y, bool); s = np.asarray(s, float)
    m = ~np.isnan(s); y, s = y[m], s[m]
    c = np.unique(s)
    best = (0.0, c[0], 1)
    for thr in c:
        for sign in (1, -1):
            pred = (sign*s >= sign*thr)
            tp = (pred & y).sum(); tn = (~pred & ~y).sum()
            j = tp/max(y.sum(),1) + tn/max((~y).sum(),1) - 1
            if j > best[0]:
                best = (float((tp+tn)/len(y)), float(thr), sign)
    return best

def acc_at(y, s, thr, sign):
    y = np.asarray(y, bool); s = np.asarray(s, float)
    m = ~np.isnan(s); y, s = y[m], s[m]
    pred = (sign*s >= sign*thr)
    return float((pred == y).mean()) if len(y) else float("nan")

def main():
    rows = list(csv.DictReader(open(LAW, newline="", encoding="utf-8-sig")))
    cache = {}
    recs = []
    miss = 0
    for r in rows:
        key = (r["model"], r["rid"], r["level"])
        if key not in cache:
            f = os.path.join(ROOT, "runs", "zic", r["model"], f'{r["rid"]}__{r["level"]}.json')
            cache[key] = json.load(open(f)) if os.path.exists(f) else None
        j = cache[key]
        if j is None:
            miss += 1; continue
        t = np.asarray(j["hist"]["t"])
        d = np.abs(np.asarray(j["hist"]["d"], float)).max(axis=1)  # peak storey drift series
        tr = float(r["t_r"])
        m = (t <= tr + 1e-9) & (t >= tr - W)
        if m.sum() < MINP:
            continue
        dd = d[m]
        cur, std_raw, sdet, ar1, sk, ku = feats(dd)
        try:
            ke = float(r["ke"]); wc = float(r["Wc_m1"]); pdrift = float(r["peak_sdr_so_far"])
        except (TypeError, ValueError):
            continue
        recs.append(dict(model=r["model"], rid=r["rid"], y=r["label_r52"] == "committed",
                         ke=ke, wc=wc, pdrift=pdrift, cur=cur, std=std_raw,
                         sdet=sdet, ar1=ar1, skew=sk, kurt=ku,
                         event=(r["rid"].split("_")[0] if r["rid"].startswith("NF") else r["rid"][:-1])))
    print(f"states with EWS features: {len(recs)}  (missing zic: {miss})")
    models = sorted(set(x["model"] for x in recs))
    metrics = ["cur", "std", "sdet", "ar1", "skew", "kurt"]
    out = {"W": W, "n": len(recs), "per_model": {}}
    # fit EWS thresholds on dev frame
    dev = [x for x in recs if x["model"] == DEV]
    thr_fit = {}
    for mname in metrics:
        thr_fit[mname] = best_acc([x["y"] for x in dev], [x[mname] for x in dev])
    out["dev_fit"] = {k: dict(acc=v[0], thr=v[1], sign=v[2]) for k, v in thr_fit.items()}
    for mo in models:
        sub = [x for x in recs if x["model"] == mo]
        y = [x["y"] for x in sub]
        row = {"n": len(sub)}
        row["energy_acc"] = float(np.mean([(x["ke"] >= C_DEV*x["wc"]) == x["y"] for x in sub]))
        row["drift_acc"] = float(np.mean([(x["pdrift"] >= THR_DEV) == x["y"] for x in sub]))
        row["energy_auc"] = auc(y, [min(x["ke"]/x["wc"], 1e9) if x["wc"] > 0 else 1e9 for x in sub])
        row["drift_auc"] = auc(y, [x["pdrift"] for x in sub])
        for mname in metrics:
            row[f"{mname}_auc"] = auc(y, [x[mname] for x in sub])
            thr, sign = thr_fit[mname][1], thr_fit[mname][2]
            row[f"{mname}_acc"] = acc_at(y, [x[mname] for x in sub], thr, sign)
        # best EWS statistic selected by max AUC on this frame's full data (disclosed as
        # post hoc); event-cluster bootstrap of the paired AUC gap energy - best EWS and
        # of best EWS vs chance.
        e_sc = [min(x["ke"]/x["wc"], 1e9) if x["wc"] > 0 else 1e9 for x in sub]
        bname = max(metrics, key=lambda m: row[f"{m}_auc"] if row[f"{m}_auc"] == row[f"{m}_auc"] else -1)
        row["best_ews"] = bname
        b_sc = [x[bname] for x in sub]
        evs = {}
        for i, x in enumerate(sub):
            evs.setdefault(x["event"], []).append(i)
        ek = sorted(evs)
        rng = np.random.default_rng(7)
        dd, dv = [], []
        for _ in range(5000):
            ii = [i for k in rng.integers(0, len(ek), len(ek)) for i in evs[ek[k]]]
            yy = [sub[i]["y"] for i in ii]
            a_e = auc(yy, [e_sc[i] for i in ii]); a_b = auc(yy, [b_sc[i] for i in ii])
            if a_e == a_e and a_b == a_b:
                dd.append(a_e - a_b); dv.append(a_b)
        row["n_events"] = len(ek)
        row["auc_gap_ci95"] = [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))] if dd else [float("nan")]*2
        row["best_auc_ci95"] = [float(np.percentile(dv, 2.5)), float(np.percentile(dv, 97.5))] if dv else [float("nan")]*2
        out["per_model"][mo] = row
        print(mo, {k: round(v, 3) for k, v in row.items() if isinstance(v, float)}, "n=", row["n"])
    # pooled
    y = [x["y"] for x in recs]
    out["pooled"] = {f"{m}_auc": auc(y, [x[m] for x in recs]) for m in metrics}
    out["pooled"]["energy_auc"] = auc(y, [min(x["ke"]/x["wc"], 1e9) if x["wc"] > 0 else 1e9 for x in recs])
    out["pooled"]["drift_auc"] = auc(y, [x["pdrift"] for x in recs])
    json.dump(out, open(OUT, "w"), indent=1)
    print("pooled:", {k: round(v, 3) for k, v in out["pooled"].items()})
    print("wrote", OUT)

if __name__ == "__main__":
    main()
