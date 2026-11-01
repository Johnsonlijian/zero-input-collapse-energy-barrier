"""Paired comparison of the bare and composite+gravity 4-story frames (far-field set).

Per record: ratio of collapse intensities, difference of the drift at t*, of the
time from t* to collapse and of the drift at the static point of no return.
Medians with 95 % bootstrap confidence intervals (records resampled).
Writes results/cg_summary.json.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "results"
RNG = np.random.default_rng(4)
PAIRS = (("SMF4B", "SMF4CG"), ("SMF8B", "SMF8CG"))


def rows(name: str) -> list[dict]:
    p = RES / name
    if not p.exists():
        return []
    out = []
    for r in csv.DictReader(p.open(encoding="utf-8")):
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
        out.append(r)
    return out


def boot(x, n=10000):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return [None, None]
    idx = RNG.integers(0, len(x), size=(n, len(x)))
    v = np.sort(np.median(x[idx], axis=1))
    return [float(v[int(0.025 * n)]), float(v[int(0.975 * n) - 1])]


def stat(x) -> dict | None:
    x = [v for v in x if v is not None and np.isfinite(v)]
    if not x:
        return None
    return {"n": len(x), "median": float(np.median(x)), "CI95": boot(x), "min": float(np.min(x)),
            "max": float(np.max(x)), "frac_positive": float(np.mean(np.asarray(x) > 0))}


def main() -> None:
    ida = rows("ida_records.csv")
    out = {}
    for b, cg in PAIRS:
        zb = {r["rid"]: r for r in rows(f"zic_records_{b}.csv") if r["level"] == "hi" and r["status"] == "ok"}
        zc = {r["rid"]: r for r in rows(f"zic_records_{cg}.csv") if r["level"] == "hi" and r["status"] == "ok"}
        sb = {r["rid"]: r["S_hi"] for r in ida if r["model"] == b and r["S_hi"] is not None}
        sc = {r["rid"]: r["S_hi"] for r in ida if r["model"] == cg and r["S_hi"] is not None}
        # ground-motion scale factor at collapse: comparable between models with different T1
        fb = {r["rid"]: r["scale_hi"] for r in ida if r["model"] == b and r.get("scale_hi") is not None}
        fc = {r["rid"]: r["scale_hi"] for r in ida if r["model"] == cg and r.get("scale_hi") is not None}
        common_ida = sorted(set(sb) & set(sc))
        if not common_ida:
            continue
        common_z = sorted(set(zb) & set(zc))
        res = {
            "n_ida_pairs": len(common_ida),
            "Sc_ratio": stat([sc[k] / sb[k] for k in common_ida]),
            "Sc_frac_increase": float(np.mean([sc[k] / sb[k] > 1 + 1e-9 for k in common_ida])),
            "scale_ratio": stat([fc[k] / fb[k] for k in common_ida if k in fc and k in fb]),
            "scale_frac_increase": float(np.mean([fc[k] / fb[k] > 1 + 1e-9 for k in common_ida
                                                  if k in fc and k in fb])),
            "n_zic_pairs": len(common_z),
            "dtheta_star": stat([zc[k]["star_inst_sdr"] - zb[k]["star_inst_sdr"] for k in common_z]),
            "dlead_c": stat([zc[k]["lead_c"] - zb[k]["lead_c"] for k in common_z]),
            "dtheta_static": stat([zc[k]["theta_static"] - zb[k]["theta_static"] for k in common_z
                                   if zc[k].get("theta_static") is not None and zb[k].get("theta_static") is not None]),
            "dt_star_minus_t95": stat([(zc[k]["t_star"] - zc[k]["t95"]) - (zb[k]["t_star"] - zb[k]["t95"])
                                       for k in common_z]),
        }
        # Where can each frame come to rest?  The merged state table stores the
        # residual drift of every settled continuation.  Using the derived table
        # here keeps the post-correction rebuild independent of the unavailable
        # original raw-run tree.
        for tag, m in (("bare", b), ("cg", cg)):
            zr = [r for r in rows(f"zic_records_{m}.csv")
                  if r.get("level") == "hi" and r.get("status") == "ok" and str(r.get("rid", "")).startswith("FF")]
            zs = [r for r in rows(f"zic_states_{m}.csv")
                  if r.get("level") == "hi" and str(r.get("rid", "")).startswith("FF")
                  and not bool(r.get("committed"))]
            grouped = {}
            for r in zs:
                if r.get("zic_resid_max") is not None:
                    grouped.setdefault(r["rid"], []).append(float(r["zic_resid_max"]))
            res_max = [max(v) for v in grouped.values() if v]
            unresolved = sum(str(r.get("status", "")).startswith("recoverable_at_collapse")
                             for r in rows(f"zic_records_{m}.csv")
                             if r.get("level") == "hi" and str(r.get("rid", "")).startswith("FF"))
            res[f"{tag}_settled_resid_max"] = stat(res_max)
            res[f"{tag}_unresolved_late"] = unresolved
            # Releases from rest: histories in which no static point of no
            # return was found before collapse.  These fields are carried by
            # the per-history result table.
            nrest = len(zr)
            nost = sum(not bool(r.get("rest_star_committed")) and r.get("t_star_static") is None
                       for r in zr)
            res[f"{tag}_rest_n"] = nrest
            res[f"{tag}_no_static_before_collapse"] = nost
        out[cg] = res
        print(cg, json.dumps(res, indent=1))
    (RES / "cg_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
