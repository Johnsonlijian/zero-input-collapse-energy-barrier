"""Post-repair audit: quarantined vs repaired SMF20B outputs.

Pairs each quarantined file with the repaired rerun of the same state and
classifies by the magnitude of the scientific difference:

  - noise   (max rel. deviation of lam0/W_barrier < 1e-6): the original
            already used a valid mode (generated before the defective
            cache existed or via an unaffected path); rerun redundant.
  - contaminated (deviation >= 1e-6, typically ~40% lam0): original used
            the defective roof-concentrated vector; rerun is required.
  - no_pair: repaired output not yet written (queue still running).

Writes analysis/quar_vs_repaired.json.
"""
import json
from pathlib import Path

ROOT = Path(r"E:\n0r53")
Q = ROOT / "quarantine" / "SMF20B_badphi_20261028"
FAMS = ("push_det", "aftershock_a6", "a6_barrier_deep")
OUT = ROOT / "analysis" / "quar_vs_repaired.json"
NOISE = 1e-6


def _nums(j):
    """Flatten every float in the output tree."""
    if isinstance(j, dict):
        for k, v in j.items():
            if k in ("task_wall_s", "wall_s", "code_sha256"):
                continue
            yield from _nums(v)
    elif isinstance(j, list):
        for v in j:
            yield from _nums(v)
    elif isinstance(j, float):
        yield j
    elif isinstance(j, int):
        yield float(j)


def maxrel(a, b):
    ma, mb = list(_nums(a)), list(_nums(b))
    n = min(len(ma), len(mb))
    worst = 0.0
    for x, y in zip(ma[:n], mb[:n]):
        d = abs(x - y) / max(abs(x), abs(y), 1e-30)
        if d > worst:
            worst = d
    return worst, len(ma), len(mb)


def main():
    res = {}
    for fam in FAMS:
        qdir = Q / fam
        rdir = ROOT / "runs" / fam / "SMF20B"
        noise, cont, no_pair, devs = [], [], [], []
        for qf in sorted(qdir.glob("*.json")):
            rf = rdir / qf.name
            if not rf.exists():
                no_pair.append(qf.name)
                continue
            q = json.loads(qf.read_text(encoding="utf-8"))
            r = json.loads(rf.read_text(encoding="utf-8"))
            d, na, nb = maxrel(q, r)
            devs.append({"file": qf.name, "maxrel": d, "n_a": na, "n_b": nb})
            (noise if d < NOISE else cont).append(qf.name)
        res[fam] = {"n_quar": len(list(qdir.glob('*.json'))),
                    "n_valid_noise": len(noise), "n_contaminated": len(cont),
                    "n_no_pair": len(no_pair),
                    "contaminated_names": cont[:30], "no_pair_names": no_pair[:30],
                    "devs": sorted(devs, key=lambda x: -x["maxrel"])}
        print(fam, {k: v for k, v in res[fam].items() if k not in ('devs',) and not k.endswith('_names')}, flush=True)
        for x in res[fam]["devs"][:5]:
            print("   worst:", x["file"], f"{x['maxrel']:.3e}")
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
