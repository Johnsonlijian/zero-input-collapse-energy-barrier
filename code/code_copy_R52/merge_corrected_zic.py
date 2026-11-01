"""Merge targeted adaptive-ZIC reruns into the complete R52 result tables.

The original raw run tree is no longer on the active workpool.  This script
therefore replaces only the records that were rerun under the repaired latest-
transition search and preserves every unaffected derived row.  It refuses to
run until both ZIC and release-from-rest outputs exist for every targeted
record.
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
MIXED = R52 / "notes" / "rerun_nonmono"
BASELINE = R52 / "notes" / "pre_corrected_results_backup_20261012"
OUT = R52 / "results"
MODELS = ("SMF4B", "SMF8B", "SMF4CG")

# The source records are the checked UNC copy; S: is a mounted mirror whose
# IMUT project junction is stale on this host.  The cache itself was built
# from the verified FEMA manifests and source files.
os.environ.setdefault(
    "N0R52_PAPERS_ROOT",
    r"\\NAS\IMUT_WORKPOOL\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation",
)
os.environ.setdefault("N0R52_GM_CACHE", str(R52 / "notes" / "records_test_cache.npz"))
os.environ["N0R52_RUNS"] = str(MIXED)
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
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: coerce(v) for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def row_key(row: dict) -> tuple[str, str]:
    return str(row.get("rid")), str(row.get("level"))


def state_outcome(state: dict) -> str:
    """Map a release state to the outcome categories used in the summary."""
    status = state.get("zic_status")
    committed = bool(state.get("committed"))
    if status == "collapse" or committed:
        return "committed_collapse"
    if status == "nonconv":
        return "censored_nonconv"
    return "recoverable_settled"


def add_counts(dst: Counter, src: dict | Counter, sign: int = 1) -> None:
    for key, value in src.items():
        dst[key] += sign * int(value)
        if dst[key] == 0:
            del dst[key]


def normalize_old_rows(rows: list[dict]) -> None:
    """Make provenance booleans explicit in the immutable baseline rows."""
    for row in rows:
        if row.get("search_repaired") is None:
            row["search_repaired"] = False
        if row.get("non_monotonic") is None:
            row["non_monotonic"] = False
        if row.get("n_transition_brackets") is None:
            row["n_transition_brackets"] = 1


def merge_rows(old: list[dict], new: list[dict], keys: set[tuple[str, str]]) -> list[dict]:
    kept = [r for r in old if row_key(r) not in keys]
    return kept + [r for r in new if row_key(r) in keys]


def main() -> None:
    if not BASELINE.exists():
        raise SystemExit(f"immutable baseline not found: {BASELINE}")
    summaries_path = OUT / "zic_summary.json"
    summaries = json.loads((BASELINE / "zic_summary.json").read_text(encoding="utf-8"))
    manifest: dict[str, object] = {"mixed_runs": str(MIXED), "models": {}}
    staged: dict[str, dict[str, object]] = {}

    for model in MODELS:
        zic_paths = sorted((MIXED / "zic" / model).glob("*__hi.json"))
        if not zic_paths:
            raise SystemExit(f"{model}: no corrected ZIC files")
        target_ids = {json.loads(p.read_text(encoding="utf-8"))["rid"] for p in zic_paths}
        missing = [rid for rid in sorted(target_ids)
                   if not (MIXED / "rest" / model / f"{rid}__hi.json").exists()]
        if missing:
            raise SystemExit(f"{model}: release-from-rest outputs still missing: {missing}")

        # Analyze only the small corrected tree; the complete old tables are
        # merged below, so no old raw run files are needed here.
        fresh = az.analyze(model)
        fresh_rows = fresh["rows"]
        fresh_states = fresh["states"]
        fresh_rest = az.rest_states(model)
        keys = {(rid, "hi") for rid in target_ids}
        if {row_key(r) for r in fresh_rows} != keys:
            raise SystemExit(f"{model}: corrected analysis did not return exactly the target rows")

        rec_path = BASELINE / f"zic_records_{model}.csv"
        state_path = BASELINE / f"zic_states_{model}.csv"
        rest_path = BASELINE / f"rest_states_{model}.csv"
        old_rows = read_csv(rec_path)
        old_states = read_csv(state_path)
        old_rest = read_csv(rest_path)
        normalize_old_rows(old_rows)
        merged_rows = merge_rows(old_rows, fresh_rows, keys)
        merged_states = merge_rows(old_states, fresh_states, keys)
        merged_rest = merge_rows(old_rest, fresh_rest, keys)
        # The per-record table remains one row per release history.  The
        # corrected search can legitimately add release-state rows because it
        # bisects a later transition that the first pass did not bracket.
        if len(merged_rows) != len(old_rows):
            raise SystemExit(f"{model}: merge changed per-record table row count unexpectedly")
        # Recompute all model summary statistics from the merged tables.  The
        # state table intentionally has six fewer rows than the release count:
        # terminal collapse anchors can commit without returning a snapshot.
        summary = az.summarize(merged_rows, merged_states)
        outcome = Counter(summaries[model].get("release_outcomes", {}))
        old_target_states = [s for s in old_states if row_key(s) in keys]
        add_counts(outcome, Counter(state_outcome(s) for s in old_target_states), sign=-1)
        add_counts(outcome, fresh["outcomes"])
        if any(v < 0 for v in outcome.values()):
            raise SystemExit(f"{model}: negative merged outcome count: {dict(outcome)}")
        total_releases = int(sum(int(r.get("n_releases") or 0) for r in merged_rows))
        summary["release_outcomes"] = dict(outcome)
        summary["n_releases_total"] = total_releases
        summary["n_censored"] = int(sum(v for k, v in outcome.items() if k.startswith("censored")))
        summary["n_release_snapshots"] = len(merged_states)
        summary["n_releases_without_snapshot"] = total_releases - len(merged_states)
        summaries[model] = summary

        old_by_key = {row_key(r): r for r in old_rows}
        changes = []
        for row in fresh_rows:
            old = old_by_key.get(row_key(row), {})
            changes.append({
                "rid": row["rid"],
                "old_t_star": old.get("t_star"),
                "new_t_star": row.get("t_star"),
                "legacy_t_star": row.get("legacy_t_star"),
                "shift_s": None if old.get("t_star") is None else row.get("t_star") - old["t_star"],
                "search_repaired": bool(row.get("search_repaired")),
                "n_transition_brackets": row.get("n_transition_brackets"),
            })
        manifest["models"][model] = {
            "target_records": sorted(target_ids),
            "changes": changes,
            "fresh_state_rows": len(fresh_states),
            "fresh_rest_rows": len(fresh_rest),
            "merged_total_releases": total_releases,
            "merged_state_rows": len(merged_states),
            "merged_outcomes": dict(outcome),
            "releases_without_snapshot": total_releases - len(merged_states),
        }
        staged[model] = {"rows": merged_rows, "states": merged_states, "rest": merged_rest}

    # Write only after every model has passed the preflight above.
    for model, data in staged.items():
        write_csv(OUT / f"zic_records_{model}.csv", data["rows"])
        write_csv(OUT / f"zic_states_{model}.csv", data["states"])
        write_csv(OUT / f"rest_states_{model}.csv", data["rest"])
    summaries_path.write_text(json.dumps(summaries, indent=1), encoding="utf-8")
    (R52 / "notes" / "corrected_zic_merge_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
