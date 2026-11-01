"""Merge the complete latest-transition rerun for the 1.5 S_a,c probe.

The x15 rerun is kept separate from the targeted threshold-intensity repair.
It replaces only SMF4B/x15 rows and preserves the corrected hi/lo rows already
written by merge_corrected_zic.py.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
R52 = HERE.parent
RUNS = R52 / "notes" / "rerun_x15"
OUT = R52 / "results"
MODEL = "SMF4B"
ORIGINAL_RUNS = Path(os.environ.get("N0R52_ORIGINAL_RUNS", r"E:\\n0r52\\runs"))

os.environ.setdefault(
    "N0R52_PAPERS_ROOT",
    r"\\NAS\IMUT_WORKPOOL\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation",
)
os.environ.setdefault("N0R52_GM_CACHE", str(R52 / "notes" / "records_test_cache.npz"))
os.environ["N0R52_RUNS"] = str(RUNS)
sys.path.insert(0, str(HERE))
import analyze_zic as az  # noqa: E402


def coerce(v):
    if v in (None, "", "None"):
        return None
    if v == "True":
        return True
    if v == "False":
        return False
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: coerce(v) for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def raw_outcomes(model: str, level: str) -> Counter:
    counts = Counter()
    for p in sorted((ORIGINAL_RUNS / "zic" / model).glob(f"*__{level}.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for release in data.get("releases", {}).values():
            if release.get("status") == "collapse":
                counts["committed_collapse"] += 1
            elif release.get("status") == "nonconv":
                counts["committed_nonconv" if release.get("max_sdr", 0) >= 0.10 else "censored_nonconv"] += 1
            elif release.get("settled_at") is not None:
                counts["recoverable_settled"] += 1
            else:
                counts["censored_horizon"] += 1
    return counts


def key(row: dict) -> tuple[str, str]:
    return str(row.get("rid")), str(row.get("level"))


def outcome(state: dict) -> str:
    if state.get("zic_status") == "collapse" or bool(state.get("committed")):
        return "committed_collapse"
    if state.get("zic_status") == "nonconv":
        return "censored_nonconv"
    return "recoverable_settled"


def main() -> None:
    fresh = az.analyze(MODEL)
    fresh_rows = [r for r in fresh["rows"] if r.get("level") == "x15"]
    fresh_states = [r for r in fresh["states"] if r.get("level") == "x15"]
    fresh_rest = [r for r in az.rest_states(MODEL) if r.get("level") == "x15"]
    target = {(r["rid"], "x15") for r in fresh_rows}
    if len(target) != 100:
        raise SystemExit(f"expected 100 x15 rows, got {len(target)}")
    if len(fresh_rows) != 100:
        raise SystemExit(f"fresh x15 analysis returned {len(fresh_rows)} rows")
    for rid, _ in sorted(target):
        if not (RUNS / "rest" / MODEL / f"{rid}__x15.json").exists():
            raise SystemExit(f"missing x15 rest output: {rid}")

    rows = read_csv(OUT / f"zic_records_{MODEL}.csv")
    states = read_csv(OUT / f"zic_states_{MODEL}.csv")
    rest = read_csv(OUT / f"rest_states_{MODEL}.csv")
    merged_rows = [r for r in rows if key(r) not in target] + fresh_rows
    merged_states = [r for r in states if key(r) not in target] + fresh_states
    merged_rest = [r for r in rest if key(r) not in target] + fresh_rest
    if len(merged_rows) != len(rows):
        raise SystemExit("x15 merge changed per-record row count")

    summaries_path = OUT / "zic_summary.json"
    summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
    summary = az.summarize(merged_rows, merged_states)
    for k, v in summary.items():
        if k.startswith("x15_"):
            summaries[MODEL][k] = v
    # The x15 replacement changes the global released-state totals as well.
    # Keep these aggregates synchronized with the merged state table.
    for k in ("n_states", "n_states_committed", "recoverable_inst_sdr_max",
              "recoverable_zic_max_sdr_max", "committed_inst_sdr_min",
              "frac_recoverable_states_above_10", "frac_committed_states_below_10"):
        if k in summary:
            summaries[MODEL][k] = summary[k]
    merge_manifest = json.loads((R52 / "notes" / "corrected_zic_merge_manifest.json").read_text(encoding="utf-8"))
    base_info = merge_manifest["models"][MODEL]
    base_counts = Counter(base_info["merged_outcomes"])
    old_x15_counts = raw_outcomes(MODEL, "x15")
    counts = base_counts - old_x15_counts + Counter(fresh["outcomes"])
    counts += Counter()
    total = int(base_info["merged_total_releases"] - sum(old_x15_counts.values()) + sum(fresh["outcomes"].values()))
    summaries[MODEL]["release_outcomes"] = dict(counts)
    summaries[MODEL]["n_releases_total"] = total
    summaries[MODEL]["n_censored"] = int(sum(v for k, v in counts.items() if k.startswith("censored")))
    summaries[MODEL]["n_release_snapshots"] = len(merged_states)
    summaries[MODEL]["n_releases_without_snapshot"] = total - len(merged_states)
    expected_states = int(base_info["merged_state_rows"] - sum(old_x15_counts.values()) + len(fresh_states))
    if len(merged_states) != expected_states:
        raise SystemExit(f"state count mismatch after x15 merge: {len(merged_states)} != {expected_states}")

    write_csv(OUT / f"zic_records_{MODEL}.csv", merged_rows)
    write_csv(OUT / f"zic_states_{MODEL}.csv", merged_states)
    write_csv(OUT / f"rest_states_{MODEL}.csv", merged_rest)
    summaries_path.write_text(json.dumps(summaries, indent=1), encoding="utf-8")
    manifest = {
        "model": MODEL,
        "level": "x15",
        "source": str(RUNS),
        "replaced_rows": len(fresh_rows),
        "fresh_state_rows": len(fresh_states),
        "fresh_rest_rows": len(fresh_rest),
        "fresh_outcomes": dict(fresh["outcomes"]),
        "base_outcomes": dict(base_counts),
        "old_x15_outcomes": dict(old_x15_counts),
        "final_merged_outcomes": dict(counts),
        "base_state_rows": int(base_info["merged_state_rows"]),
        "final_state_rows": len(merged_states),
        "n_non_monotonic_after_rerun": sum(bool(r.get("non_monotonic")) for r in fresh_rows),
        "not_ok": summary.get("x15_not_ok", []),
    }
    (R52 / "notes" / "corrected_x15_merge_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
