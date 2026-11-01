"""Can drift identify commitment?  Drift-only threshold versus a two-branch rule.

Development set: released states of SMF4B under far-field records.
Hold-out sets: SMF4B near-field, SMF8B far-field, SMF8B near-field (no refit).
Rules (fitted on the development set by minimising the misclassification rate):
  D : committed if theta >= theta_b
  DK: committed if theta >= theta_s or KE/W_b >= kappa (W_b: pushover work up to zero lateral resistance)
The released states are not a random sample of the response: they concentrate
near the point of no return and at the most demanding instants of surviving
histories, i.e. where the classification is hardest.
Writes results/classify_summary.json.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "results"


def load(model: str) -> list[dict]:
    p = OUT / f"zic_states_{model}.csv"
    if not p.exists():
        return []
    rows = []
    for r in csv.DictReader(p.open(encoding="utf-8")):
        rows.append({"model": model, "set": r["set"], "level": r["level"], "y": int(float(r["committed"])),
                     "theta": float(r["inst_max_sdr"]), "ke": float(r["ke_norm"])})
    return rows


def scores(y, pred):
    y, pred = np.asarray(y, bool), np.asarray(pred, bool)
    n_c, n_r = int(y.sum()), int((~y).sum())
    miss = float(np.mean(~pred[y])) if n_c else None
    fa = float(np.mean(pred[~y])) if n_r else None
    return {"n": int(len(y)), "n_committed": n_c, "error": float(np.mean(y != pred)),
            "miss_rate": miss, "false_alarm_rate": fa,
            "balanced_error": None if miss is None or fa is None else 0.5 * (miss + fa)}


def fit_D(dev):
    th = np.unique(np.round([d["theta"] for d in dev], 4))
    best = min(th, key=lambda t: np.mean([(d["theta"] >= t) != bool(d["y"]) for d in dev]))
    return float(best)


def fit_DK(dev):
    ths = np.round(np.arange(0.06, 0.16, 0.0025), 4)
    kas = np.round(10 ** np.arange(-1.5, 1.01, 0.05), 4)
    y = np.array([d["y"] for d in dev], bool)
    th = np.array([d["theta"] for d in dev])
    ke = np.array([d["ke"] for d in dev])
    best, best_err = None, 9.0
    for t in ths:
        for k in kas:
            err = np.mean(((th >= t) | (ke >= k)) != y)
            if err < best_err - 1e-12:
                best, best_err = (float(t), float(k)), err
    return best


def main():
    allstates = load("SMF4B") + load("SMF8B")
    # the pre-defined dataset: collapse histories at S_a,c and surviving histories at S_a,lo
    data = [d for d in allstates if d["level"] in ("hi", "lo")]
    if not data:
        return
    dev = [d for d in data if d["model"] == "SMF4B" and d["set"] == "FF"]
    holds = {
        "SMF4B_NF": [d for d in data if d["model"] == "SMF4B" and d["set"] == "NF"],
        "SMF8B_FF": [d for d in data if d["model"] == "SMF8B" and d["set"] == "FF"],
        "SMF8B_NF": [d for d in data if d["model"] == "SMF8B" and d["set"] == "NF"],
    }
    holds["holdout_all"] = holds["SMF4B_NF"] + holds["SMF8B_FF"] + holds["SMF8B_NF"]
    # additional test: states of the 4-story collapse histories at 1.5 S_a,c (not part of the pre-defined split)
    holds["SMF4B_x15"] = [d for d in allstates if d["model"] == "SMF4B" and d["level"] == "x15"]
    tb = fit_D(dev)
    ts, ka = fit_DK(dev)
    out = {"theta_b": tb, "theta_s": ts, "kappa": ka, "dev": {}, "holdout": {}}
    for name, rule in (("D", lambda d: d["theta"] >= tb), ("DK", lambda d: d["theta"] >= ts or d["ke"] >= ka),
                       ("D10", lambda d: d["theta"] >= 0.10)):
        out["dev"][name] = scores([d["y"] for d in dev], [rule(d) for d in dev])
        for hn, hs in holds.items():
            if hs:
                out["holdout"].setdefault(hn, {})[name] = scores([d["y"] for d in hs], [rule(d) for d in hs])
    (OUT / "classify_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
