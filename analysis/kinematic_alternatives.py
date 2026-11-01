"""Kinematic alternatives to the energy rule (post hoc control, Discussion limitation).

On the classified released states of every frame (rows of law_table.csv with a finite
collapse-surface barrier Wc_m1; 12/20-storey frames far-field only, as in the harness):
  E      committed iff KE >= c_dev * Wc_m1                (c_dev = 1.13, development constant)
  D      committed iff peak_sdr >= thr_dev                (instantaneous peak storey drift)
  Drun   committed iff peak_sdr_so_far >= thr_run_dev     (running-maximum drift)
  K2     logistic on [peak_sdr, log KE]                   (drift + velocity information)
  K3     logistic on [peak_sdr, peak_sdr_so_far, log KE]
Transfer variants: thresholds / logistic coefficients fitted once on the development set
(SMF4B far-field, as for thr_dev) and applied unchanged to every frame.
Oracle variants (upper bounds): per-frame fit, scored by leave-one-event-out
cross-validation (thresholds: best on the training events; logistic: refit).
Paired event-cluster bootstrap (10 000) of accuracy(E) - accuracy(rule) per frame.
Writes analysis/kinematic_alternatives.json.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from build_tables import C_DEV, event_id

A = Path(__file__).resolve().parent
OUT = A / "kinematic_alternatives.json"
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG", "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
TALL = {"SMF12B", "SMF12CG", "SMF20B", "SMF20CG"}
N_BOOT = 10000


def best_thr(x, y):
    return max((float(np.mean((x >= t) == y)), t) for t in np.unique(x))[1]


def logit_fit(X, y, ridge=1e-6, iters=100):
    mu, sd = X.mean(0), X.std(0) + 1e-12
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    b = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ b, -30, 30)))
        g = Z.T @ (y - p) - ridge * b
        H = (Z * (p * (1 - p))[:, None]).T @ Z + ridge * np.eye(len(b))
        step = np.linalg.solve(H, g)
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return lambda Xn: (1.0 / (1.0 + np.exp(-np.clip(np.column_stack([np.ones(len(Xn)), (Xn - mu) / sd]) @ b, -30, 30)))) >= 0.5


def feats(df, k):
    lke = np.log(np.maximum(df["ke"].to_numpy(float), 1e-9))
    if k == "K2":
        return np.column_stack([df["peak_sdr"].to_numpy(float), lke])
    return np.column_stack([df["peak_sdr"].to_numpy(float), df["peak_sdr_so_far"].to_numpy(float), lke])


def main():
    lt = pd.read_csv(A / "law_table.csv")
    for c in ("ke", "peak_sdr", "peak_sdr_so_far", "Wc_m1"):
        lt[c] = pd.to_numeric(lt[c], errors="coerce")
    lt = lt[np.isfinite(lt["Wc_m1"]) & lt["label_r52"].isin(["committed", "recoverable"])].copy()
    lt["y"] = lt["label_r52"] == "committed"
    lt["event"] = lt["rid"].map(event_id)

    dev = lt[(lt["model"] == "SMF4B") & (lt["set"] == "FF")]
    yd = dev["y"].to_numpy()
    thr = best_thr(dev["peak_sdr"].to_numpy(float), yd)
    thr_run = best_thr(dev["peak_sdr_so_far"].to_numpy(float), yd)
    k2 = logit_fit(feats(dev, "K2"), yd)
    k3 = logit_fit(feats(dev, "K3"), yd)
    out = {"_protocol": {"c_dev": C_DEV, "thr_dev": float(thr), "thr_run_dev": float(thr_run),
                         "states": "law_table rows with finite Wc_m1, labels recoverable/committed; 12/20 FF only",
                         "unit": "event_id", "n_boot": N_BOOT}}
    rng = np.random.default_rng(2026)
    for m in MODELS:
        df = lt[(lt["model"] == m) & ((lt["set"] == "FF") if m in TALL else True)]
        if len(df) < 10:
            continue
        y = df["y"].to_numpy()
        ke, W = df["ke"].to_numpy(float), df["Wc_m1"].to_numpy(float)
        pk, pr = df["peak_sdr"].to_numpy(float), df["peak_sdr_so_far"].to_numpy(float)
        pred = {"E": ke >= C_DEV * W, "D": pk >= thr, "Drun": pr >= thr_run,
                "K2": k2(feats(df, "K2")), "K3": k3(feats(df, "K3"))}
        # oracle (leave-one-event-out within the frame)
        ev = df["event"].to_numpy()
        lme = np.log(np.maximum(ke, 1e-9) / np.maximum(W, 1e-9))
        orc = {k: np.zeros(len(df), bool) for k in ("E_cv", "D_cv", "Drun_cv", "K2_cv", "K3_cv")}
        for e in np.unique(ev):
            te, tr = ev == e, ev != e
            if tr.sum() < 5 or len(np.unique(y[tr])) < 2:
                continue
            orc["E_cv"][te] = lme[te] >= best_thr(lme[tr], y[tr])
            orc["D_cv"][te] = pk[te] >= best_thr(pk[tr], y[tr])
            orc["Drun_cv"][te] = pr[te] >= best_thr(pr[tr], y[tr])
            for k in ("K2", "K3"):
                F = feats(df, k)
                orc[f"{k}_cv"][te] = logit_fit(F[tr], y[tr])(F[te])
        pred.update(orc)
        acc = {k: float(np.mean(v == y)) for k, v in pred.items()}
        # paired event bootstrap: E minus each rule (transfer) and E_cv minus each oracle
        idx_by = defaultdict(list)
        for i, e in enumerate(ev):
            idx_by[e].append(i)
        ek = sorted(idx_by)
        corr = {k: (v == y).astype(float) for k, v in pred.items()}
        pairs = [("E", "D"), ("E", "Drun"), ("E", "K2"), ("E", "K3"), ("E_cv", "K2_cv"), ("E_cv", "K3_cv"),
                 ("E_cv", "Drun_cv")]
        reps = {f"{a}-{b}": [] for a, b in pairs}
        for _ in range(N_BOOT):
            ii = np.concatenate([idx_by[ek[j]] for j in rng.integers(0, len(ek), len(ek))])
            for a, b in pairs:
                reps[f"{a}-{b}"].append(corr[a][ii].mean() - corr[b][ii].mean())
        diff = {k: [float(np.mean(corr[k.split('-')[0]] - corr[k.split('-')[1]])),
                    float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in reps.items()}
        out[m] = {"n": int(len(df)), "n_events": int(len(ek)), "acc": acc, "diff": diff}
        print(m, len(df), {k: round(100 * v, 1) for k, v in acc.items()},
              {k: [round(100 * x, 1) for x in v] for k, v in diff.items() if k in ("E-K2", "E_cv-K2_cv", "E-Drun")},
              flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("thr_dev", thr, "thr_run_dev", thr_run, "wrote", OUT)


if __name__ == "__main__":
    main()
