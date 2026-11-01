"""Summarise analysis/fork_rate.csv into analysis/fork_rate.json (A13).

Six-class partition per state:
  identical          same step count, exit class and work on all three runs
  same_work_diffstep identical work+exit but different step counts
  deviated_work      work deviates >1e-6 relative, exit class unchanged
  exit_flip          exit class differs between runs
  missed_repetition  canonical ok, >=1 repetition produced no barrier
  missed_canonical   canonical failed, >=1 repetition produced a barrier
  no_barrier         no run produced a barrier
"""
import csv
import json
from collections import Counter
from pathlib import Path

ANA = Path(r"E:\n0r53\analysis")


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    rows = list(csv.DictReader((ANA / "fork_rate.csv").open(encoding="utf-8-sig")))
    cat = Counter()
    by_model = {}
    spreads = []
    for r in rows:
        m = r["model"]
        W = [f(r["W_canon"]), f(r["W_r1"]), f(r["W_r2"])]
        lim = [r["lim_canon"], r["lim_r1"], r["lim_r2"]]
        st = [f(r["n_steps_canon"]), f(r["n_steps_r1"]), f(r["n_steps_r2"])]
        have = [w is not None for w in W]
        if not any(have):
            c = "no_barrier"
        elif have[0] and not (have[1] and have[2]):
            c = "missed_repetition"
        elif not have[0] and (have[1] or have[2]):
            c = "missed_canonical"
        elif len(set(lim)) > 1:
            c = "exit_flip"
        else:
            rel = (max(W) - min(W)) / max(1e-9, max(abs(w) for w in W))
            if rel > 1e-6:
                c = "deviated_work"
                spreads.append((m, rel))
            elif len(set(int(x) for x in st)) > 1:
                c = "same_work_diffstep"
            else:
                c = "identical"
        cat[c] += 1
        d = by_model.setdefault(m, Counter())
        d[c] += 1
    out = {
        "n_states": len(rows),
        "classes": dict(cat),
        "by_model": {m: dict(c) for m, c in sorted(by_model.items())},
        "work_spread_pct_median": sorted(s[1] for s in spreads)[len(spreads) // 2] * 100 if spreads else None,
        "work_spread_pct_max": max((s[1] for s in spreads), default=0) * 100,
        "note": ("A13 repeat-run audit partition; A17 deterministic-phi re-run "
                 "lands in runs/push_det and is compared in fork_det.json"),
    }
    (ANA / "fork_rate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["classes"]))
    for m, c in sorted(by_model.items()):
        print(f"  {m}: {dict(c)}")


if __name__ == "__main__":
    main()
