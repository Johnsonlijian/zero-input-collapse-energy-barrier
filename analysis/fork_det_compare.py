"""Compare the A17 deterministic-phi re-run (runs/push_det) against the three
original A13 runs (canonical + two repetitions), per state.

For every state in analysis/fork_rate.csv with a push_det output we record:
  W_det, lim_det, whether the det barrier falls inside the original spread
  (min..max of the up-to-three original runs), and the relative deviation of
  W_det from the canonical value.
Outputs analysis/fork_det.json.
"""
import csv
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ANA = Path(r"E:\n0r53\analysis")
RUNS = Path(r"E:\n0r53\runs")
sys.path.insert(0, str(ANA))
from build_tables import w_collapse  # noqa: E402


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    rows = list(csv.DictReader((ANA / "fork_rate.csv").open(encoding="utf-8-sig")))
    det_dir = RUNS / "push_det"
    res = []
    for r in rows:
        if not det_dir.exists():
            break
        name = f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}.json"
        p = det_dir / r["model"] / name
        if not p.exists():
            continue
        try:
            j = json.loads(p.read_text(errors="replace"))
        except Exception:
            continue
        Wd, limd = w_collapse({"curve": j.get("curve") or [],
                               "sgn": j.get("sgn", 1),
                               "downhill": j.get("downhill"),
                               "W_barrier": j.get("W_barrier")})
        orig = [f(r["W_canon"]), f(r["W_r1"]), f(r["W_r2"])]
        orig = [w for w in orig if w is not None]
        in_spread = bool(orig and Wd is not None
                         and min(orig) - 1e-9 <= Wd <= max(orig) + 1e-9)
        dev_c = (abs(Wd - orig[0]) / max(abs(orig[0]), 1e-9)
                 if orig and Wd is not None else None)
        res.append({"model": r["model"], "rid": r["rid"], "t_r": r["t_r"],
                    "W_det": Wd, "lim_det": limd, "in_orig_spread": in_spread,
                    "rel_dev_canon": dev_c})
    per = {}
    for m in sorted({x["model"] for x in res}):
        xs = [x for x in res if x["model"] == m]
        got = [x for x in xs if x["W_det"] is not None]
        devs = [x["rel_dev_canon"] for x in got if x["rel_dev_canon"] is not None]
        per[m] = {
            "n": len(xs), "n_barrier": len(got),
            "in_orig_spread": sum(x["in_orig_spread"] for x in got),
            "rel_dev_canon_median": st.median(devs) if devs else None,
            "rel_dev_canon_max": max(devs) if devs else None,
            "lim_diff_from_canon": sum(
                1 for x in got
                if x["lim_det"] is not None and str(x["lim_det"]) !=
                next((r["lim_canon"] for r in rows
                      if r["model"] == m and r["rid"] == x["rid"]
                      and r["t_r"] == x["t_r"]), None)),
        }
    out = {"n_states": len(res), "per_model": per,
           "classes": dict(Counter(
               "in_spread" if x["in_orig_spread"] else
               ("outside_spread" if x["W_det"] is not None else "no_barrier")
               for x in res))}
    (ANA / "fork_det.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["classes"]))
    for m, v in per.items():
        print(f"  {m}: {v['n_barrier']}/{v['n']} barriers, "
              f"{v['in_orig_spread']} in orig spread, "
              f"med dev {v['rel_dev_canon_median']}")


if __name__ == "__main__":
    main()
