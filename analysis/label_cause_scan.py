"""Count committed releases whose collapse is declared by solver non-convergence
(max_sdr of the committed continuation < theta_c) rather than drift passage.
Reads runs/zic/<model>/*.json releases. Writes label_cause.json."""
import json
from pathlib import Path

RUNS = Path(r"E:\n0r53\runs\zic")
out = {}
for mdir in sorted(RUNS.iterdir()):
    if not mdir.is_dir():
        continue
    com = nc = 0
    for f in mdir.glob("*.json"):
        try:
            z = json.loads(f.read_text())
        except Exception:
            continue
        rel = z.get("releases") or {}
        items = rel.values() if isinstance(rel, dict) else rel
        for r in items:
            if not isinstance(r, dict) or not r.get("committed"):
                continue
            com += 1
            ms = r.get("max_sdr")
            if ms is not None and ms < 0.15:
                nc += 1
    out[mdir.name] = dict(committed=com, nonconv=nc)
    print(mdir.name, com, nc)
Path(r"E:\n0r53\analysis\label_cause.json").write_text(json.dumps(out, indent=1))
