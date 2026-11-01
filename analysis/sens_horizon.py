"""Horizon-expiry sensitivity (addendum A16 follow-up, post hoc).

Two distinct exclusions, both reported per frame on the ta/tstar coefficient
and classifier samples of analysis/law_table.csv:

1. ZIC-label sensitivity: rows whose *release* run ended by 30-s horizon
   expiry (labelled recoverable without a settle event) are dropped from the
   classifier accuracy and from the coefficient samples.
2. Ladder sensitivity: rows whose damped (resp. undamped) beta bracket is
   "horizon-limited"---the smallest recoverable beta probe in the kick run
   ended by horizon expiry rather than the settle test---are dropped from the
   c_c (resp. c0_c) samples.  Such a probe bounds beta_crit from above only
   under the assumption that a bounded 30-s orbit will never escape, so the
   exclusion gives a robustness bound on the reported medians.

Outputs analysis/sens_horizon.json.
"""
import csv
import json
import statistics as st
from pathlib import Path

ANA = Path(r"E:\n0r53\analysis")
RUNS = Path(r"E:\n0r53\runs")
C_DEV = 1.13
THR_DEV = 0.1173397626


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def horizon_keys(family: str) -> dict:
    """(model, rid, level, t_r2) -> {top_horizon, any_horizon} per task."""
    out = {}
    d = RUNS / family
    if not d.exists():
        return out
    for f in d.glob("*/*.json"):
        try:
            j = json.loads(f.read_text(errors="replace"))
        except Exception:
            continue
        parts = f.stem.split("__")
        if len(parts) < 3:
            continue
        rid, level = parts[0], parts[1]
        try:
            t_r = round(float(parts[2]), 2)
        except ValueError:
            continue
        runs = j.get("runs") or {}
        any_hor = False
        for k, r in runs.items():
            if r.get("label") == "recoverable" and r.get("settled_at") is None:
                any_hor = True
        # the smallest recoverable beta bounds beta_crit from above; if that
        # probe ended by horizon expiry the bracket is horizon-limited.
        rec = [(float(k), r) for k, r in runs.items()
               if r.get("label") == "recoverable"]
        top_hor = bool(rec and
                       min(rec, key=lambda x: x[0])[1].get("settled_at") is None)
        out[(f.parent.name, rid, level, t_r)] = {
            "top_horizon": top_hor, "any_horizon": any_hor}
    return out


def main():
    rows = list(csv.DictReader((ANA / "law_table.csv").open(encoding="utf-8-sig")))
    ha = json.loads((ANA / "horizon_audit.json").read_text())
    zic_hor = {(m, s["rid"], s["level"], round(float(s["t_r"]), 2))
               for m, d in ha["zic"].items()
               for s in d.get("horizon_states") or []}
    kd = horizon_keys("kick")
    ku = horizon_keys("kick_undamped")

    def med(x):
        return float(st.median(x)) if x else None

    res = {}
    for m in sorted({r["model"] for r in rows}):
        Ls = [r for r in rows if r["model"] == m]
        T0c = [r for r in Ls if r.get("tag") in ("ta", "tstar")
               and fnum(r.get("E_u")) > 0 and fnum(r.get("Wc_m1")) > 0]
        Tc = [r for r in Ls if r.get("tag") in ("ta", "tstar")
              and fnum(r.get("E_d")) > 0 and fnum(r.get("Wc_m1")) > 0]
        Clc = [r for r in Ls if fnum(r.get("Wc_m1")) == fnum(r.get("Wc_m1"))]

        def key(r):
            return (r["model"], r["rid"], r["level"], round(fnum(r["t_r"]), 2))

        hz = {key(r) for r in Ls} & zic_hor
        hu = {key(r) for r in T0c if ku.get(key(r), {}).get("top_horizon")}
        hd = {key(r) for r in Tc if kd.get(key(r), {}).get("top_horizon")}
        hua = {key(r) for r in T0c if ku.get(key(r), {}).get("any_horizon")}

        c0_full = [fnum(r["E_u"]) / fnum(r["Wc_m1"]) for r in T0c]
        c0_ex = [fnum(r["E_u"]) / fnum(r["Wc_m1"]) for r in T0c if key(r) not in hu]
        cc_full = [fnum(r["E_d"]) / fnum(r["Wc_m1"]) for r in Tc]
        cc_ex = [fnum(r["E_d"]) / fnum(r["Wc_m1"]) for r in Tc if key(r) not in hd]

        yy = {key(r): (r["label_r52"] == "committed") for r in Clc}
        hitE = {key(r): (fnum(r["ke"]) >= C_DEV * fnum(r["Wc_m1"]))
                for r in Clc}
        acc_full = (sum(hitE[k] == yy[k] for k in hitE) / len(hitE)
                    if hitE else None)
        keep = [k for k in hitE if k not in hz]
        acc_ex = (sum(hitE[k] == yy[k] for k in keep) / len(keep)
                  if keep else None)

        res[m] = {
            "n_law": len(Ls),
            "n_zic_horizon": len(hz),
            "n_beta_u_top_horizon": len(hu),
            "n_beta_u_any_horizon": len(hua),
            "n_beta_d_top_horizon": len(hd),
            "c0_c_full": med([float(x) for x in c0_full]),
            "c0_c_excl": med([float(x) for x in c0_ex]),
            "n_c0_excl": len(c0_ex),
            "c_c_full": med([float(x) for x in cc_full]),
            "c_c_excl": med([float(x) for x in cc_ex]),
            "n_cc_excl": len(cc_ex),
            "acc_cdev_full": acc_full,
            "acc_cdev_excl_zic": acc_ex,
            "n_acc_excl": len(keep),
        }
        print(f"{m}: zic_hor={len(hz)} betaU_top_hor={len(hu)} "
              f"betaD_top_hor={len(hd)} "
              f"c0c {res[m]['c0_c_full']}->{res[m]['c0_c_excl']} "
              f"acc {acc_full and round(acc_full,3)}->"
              f"{acc_ex and round(acc_ex,3)}", flush=True)
    (ANA / "sens_horizon.json").write_text(json.dumps(res, indent=1))
    print("-> sens_horizon.json")


if __name__ == "__main__":
    main()
