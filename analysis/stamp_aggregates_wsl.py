"""Provenance stamping for aggregate analysis JSONs.

Every published aggregate gets a `_protocol` block binding it to the generator
script (path + sha256), its declared inputs, the run timestamp and the host.
Idempotent: re-running only refreshes the stamp.  Does not touch run-level JSONs
(which already carry their own protocol tags).

Post-hoc addendum support (A16): analysis-layer bookkeeping only.
"""
import json, hashlib, socket, datetime
from pathlib import Path

ROOT = Path(r"/mnt/e/n0r53/analysis")

# aggregate file -> (generator script, declared inputs)
MAP = {
    "summary_by_frame.json":      ("build_tables.py",            ["analysis/law_table.csv", "runs/push*", "runs/kick*", "runs/push_deep"]),
    "aftershock_analysis.json":   ("aftershock_analysis.py",     ["runs/aftershock_ms", "runs/aftershock_a6", "runs/aftershock_ms_sib", "analysis/law_table.csv"]),
    "ews_control.json":           ("ews_control.py",             ["analysis/law_table.csv", "runs/zic"]),
    "kinematic_alternatives.json":("kinematic_alternatives.py",  ["analysis/law_table.csv", "runs/zic"]),
    "ktan_control.json":          ("ktan_control.py",            ["runs/ktan", "analysis/law_table.csv"]),
    "direction_split.json":       ("direction_split.py",         ["analysis/law_table.csv"]),
    "per_state_audit.json":       ("per_state_audit.py",         ["analysis/law_table.csv", "runs/kick*", "runs/push*"]),
    "modal_ke.json":              ("modal_ke.py",                ["runs/push*", "runs/kick*", "code/models"]),
    "collapse_after_input.json":  ("collapse_after_input.py",    ["runs/ida", "results/ida_summary.json"]),
    "shape_vs_mode1.json":        ("shape_vs_mode1.py",          ["runs/push_shape", "runs/push", "analysis/law_table.csv"]),
    "accounting_audit.json":      ("accounting_audit.py",        ["analysis/law_table.csv"]),
    "label_cause.json":           ("label_cause_scan.py",        ["analysis/law_table.csv", "runs/zic"]),
    "intact_symmetry.json":       ("intact_symmetry.py",         ["runs/barrier_intact"]),
    "deep_vs_std_audit.json":     ("deep_vs_std_audit.py",       ["runs/push_deep", "runs/push"]),
    "early_edge_audit.json":      ("early_edge_audit.py",        ["runs/push", "runs/push_deep"]),
    "trunc_audit.json":           ("t95_all.py",                 ["runs/t95"]),
    "t95_all.json":               ("t95_all.py",                 ["runs/t95"]),
    "sens_damp_bcrit.json":       ("sens_damp_quick.py",         ["runs/kick_damp05", "runs/kick_damp20", "runs/kick"]),
    "sens_theta_consistent.json": ("sens_theta_consistent.py",   ["runs/kick_theta010", "runs/kick_theta020", "runs/kick"]),
    "sens_dt2_consistent.json":   ("sens_dt2_consistent.py",     ["runs/kick_dt2", "runs/kick"]),
    "sens_variants.json":         ("sens_variants.py",           ["runs/kick", "runs/push"]),
    "kick_energy_analysis.json":  ("kick_energy_analysis.py",    ["runs/kick_energy"]),
    "check_push_deep.json":       ("check_push_deep.py",         ["runs/push_deep"]),
    "branch_jump_audit.json":     ("branch_jump_audit.py",       ["runs/push", "runs/barrier_intact"]),
    "pattern_compare.json":       ("pattern_compare.py",         ["analysis/law_table.csv"]),
    "horizon_audit.json":         ("horizon_audit.py",           ["runs/zic", "runs/kick", "runs/kick_undamped"]),
    "horizon_c0_sens.json":       ("horizon_c0_sens.py",         ["runs/kick_undamped", "analysis/law_table.csv"]),
    "horizon_kick_audit.json":    ("horizon_audit.py",           ["runs/kick", "runs/kick_undamped"]),
    "sens_horizon.json":          ("sens_horizon.py",            ["runs/kick", "runs/kick_undamped", "analysis/law_table.csv", "analysis/horizon_audit.json"]),
    "lam_spike_audit.json":       ("lam_spike_audit.py",         ["runs/push"]),
    "fork_rate.json":             ("fork_rate_json.py",          ["analysis/fork_rate.csv"]),
    "fork_det.json":              ("fork_det_compare.py",        ["analysis/fork_rate.csv", "runs/push_det"]),
    "sens_damp_frames.json":      ("sens_damp_frames.py",        ["runs/kick_damp05", "runs/kick_damp20", "runs/kick", "runs/kick_undamped"]),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for name, (gen, inputs) in MAP.items():
        p = ROOT / name
        if not p.exists():
            print("skip (absent):", name)
            continue
        gp = ROOT / gen
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            # list-typed aggregates get a sidecar stamp file instead of a schema change
            side = p.with_suffix(".prov.json")
            side.write_text(json.dumps({
                "stamped_file": name,
                "generator": gen,
                "generator_sha256_16": sha(gp) if gp.exists() else "absent",
                "declared_inputs": inputs,
                "stamped_utc": now,
                "host": socket.gethostname()}, indent=1), encoding="utf-8")
            print("sidecar:", name)
            continue
        stamp = {
            "generator": gen,
            "generator_sha256_16": sha(gp) if gp.exists() else "absent",
            "declared_inputs": inputs,
            "stamped_utc": now,
            "host": socket.gethostname(),
            "note": "aggregate-level provenance stamp added by stamp_aggregates.py; "
                    "statistics unchanged",
        }
        if "_protocol" in d and isinstance(d["_protocol"], dict):
            d["_protocol"].update({"aggregate_stamp": stamp})
        else:
            d["_protocol"] = {"aggregate_stamp": stamp}
        p.write_text(json.dumps(d, indent=1), encoding="utf-8")
        print("stamped:", name)


if __name__ == "__main__":
    main()
