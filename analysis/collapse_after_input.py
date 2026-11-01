"""Capacity consequence of the record-end convention.

For each record at its collapse bracket (lowest collapsing intensity run),
report whether the forced collapse occurs after the input ends or after t95.
A 'stop at input end' / 'truncate at significant duration' analysis would
label these collapses as survivals.
"""
import json
from pathlib import Path

import numpy as np

RUNS = Path(r"E:\n0r53\runs\ida")
OUT = Path(r"E:\n0r53\analysis\collapse_after_input.json")

res = {}
for mdir in sorted(RUNS.iterdir()):
    if not mdir.is_dir():
        continue
    n_coll = n_after_end = n_after_95 = 0
    dts_end, dts_95 = [], []
    for f in mdir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        runs = [r for r in d.get("runs", []) if r.get("collapse")]
        if not runs:
            continue
        r = min(runs, key=lambda x: x.get("sa", 1e9))
        tc = r.get("t_coll")
        tend = r.get("t_record_end") or d.get("duration")
        t95 = d.get("t95")
        if tc is None or tend is None:
            continue
        n_coll += 1
        dts_end.append(tc - tend)
        dts_95.append(tc - t95 if t95 is not None else np.nan)
        if tc > tend:
            n_after_end += 1
        if t95 is not None and tc > t95:
            n_after_95 += 1
    res[mdir.name] = dict(
        n_coll=n_coll, after_end=n_after_end, after_t95=n_after_95,
        med_dt_end=float(np.median(dts_end)) if dts_end else None,
        med_dt_95=float(np.nanmedian(dts_95)) if dts_95 else None)
    print(mdir.name, res[mdir.name])

OUT.write_text(json.dumps(res, indent=2))
print("wrote", OUT)
