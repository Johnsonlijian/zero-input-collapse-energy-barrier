"""Old-cache vs repaired comparison for a6_barrier_deep/SMF20CG.

Pairs each quarantined file (original fullGenLapack-derived cache, mode
within 2.5e-7 of canonical) with its rerun under the repaired
canonical-era frozen vector.  Deviation <1e-6 means the mode-provenance
difference is numerically irrelevant for that state; larger deviations
are genuine branch sensitivity seeded by the mode perturbation.
Writes analysis/quar_vs_repaired_20cg.json.
"""
import json
from pathlib import Path

ROOT = Path(r"E:\n0r53")
Q = ROOT / "quarantine" / "SMF20CG_origcache_20261028" / "a6_barrier_deep"
R = ROOT / "runs" / "a6_barrier_deep" / "SMF20CG"
OUT = ROOT / "analysis" / "quar_vs_repaired_20cg.json"
NOISE = 1e-6


def _nums(j):
    if isinstance(j, dict):
        for k, v in j.items():
            if k in ("task_wall_s", "wall_s", "code_sha256"):
                continue
            yield from _nums(v)
    elif isinstance(j, list):
        for v in j:
            yield from _nums(v)
    elif isinstance(j, (int, float)):
        yield float(j)


def main():
    rows = []
    for qf in sorted(Q.glob("*.json")):
        rf = R / qf.name
        if not rf.exists():
            rows.append({"file": qf.name, "status": "no_pair"})
            continue
        q = json.loads(qf.read_text(encoding="utf-8"))
        r = json.loads(rf.read_text(encoding="utf-8"))
        ma, mb = list(_nums(q)), list(_nums(r))
        d = 0.0
        for x, y in zip(ma, mb):
            d = max(d, abs(x - y) / max(abs(x), abs(y), 1e-30))
        rows.append({"file": qf.name, "maxrel": d,
                     "status": "valid_noise" if d < NOISE else "differ"})
    n_ok = sum(r["status"] == "valid_noise" for r in rows)
    n_df = sum(r["status"] == "differ" for r in rows)
    n_np = sum(r["status"] == "no_pair" for r in rows)
    res = {"n_quar": len(rows), "n_valid_noise": n_ok, "n_differ": n_df,
           "n_no_pair": n_np,
           "devs": sorted((r for r in rows if "maxrel" in r), key=lambda x: -x["maxrel"]),
           "no_pair": [r["file"] for r in rows if r["status"] == "no_pair"]}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("quar:", len(rows), "noise:", n_ok, "differ:", n_df, "no_pair:", n_np)
    for x in res["devs"][:10]:
        print("  worst:", x["file"], f"{x['maxrel']:.3e}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
