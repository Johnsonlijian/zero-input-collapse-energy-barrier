"""A8 audit: Table-2 coefficients with the extended (0.16 roof drift) pushes versus the standard
0.08 pushes only.  Requires the audit build
    N0R53_OUT=analysis/audit_nodeep  N0R53_NO_DEEP=1  python build_tables.py
Compares summary_by_frame.json of the two builds on the Table-2 rows (2/4/8 storeys: ALL;
12/20 storeys: FF) and writes analysis/deep_vs_std_audit.json."""
import json
from pathlib import Path

A = Path(__file__).resolve().parent
a = json.loads((A / "summary_by_frame.json").read_text())
b = json.loads((A / "audit_nodeep" / "summary_by_frame.json").read_text())
TALL = ("SMF12B", "SMF12CG", "SMF20B", "SMF20CG")
rows = {}
for m in ("SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG") + TALL:
    k = f"{m}|{'FF' if m in TALL else 'ALL'}"
    if k not in a or k not in b:
        continue
    r = {}
    for q in ("c_c", "c0_c"):
        x, y = a[k].get(q), b[k].get(q)
        if x is None or y is None:
            continue
        x, y = (float(v[0] if isinstance(v, list) else v) for v in (x, y))
        r[q] = {"deep": x, "std": y, "diff": x - y}
    r["n_transition"] = {"deep": a[k].get("n_transition"), "std": b[k].get("n_transition")}
    rows[m] = r
out = {"rows": rows}
for q in ("c_c", "c0_c"):
    m = max((mm for mm in rows if q in rows[mm]), key=lambda mm: abs(rows[mm][q]["diff"]))
    out[f"max_abs_{q}"] = {"model": m, "diff": abs(rows[m][q]["diff"])}
out["n_added"] = sum((v["n_transition"]["deep"] or 0) - (v["n_transition"]["std"] or 0) for v in rows.values())
(A / "deep_vs_std_audit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}))
