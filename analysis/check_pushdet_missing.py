import csv
from pathlib import Path
rows = list(csv.DictReader(open(r"E:\n0r53\analysis\fork_rate.csv", encoding="utf-8-sig")))
have = {f.name for d in Path(r"E:\n0r53\runs\push_det").glob("*") for f in d.glob("*.json")}
miss = [(r["model"], r["rid"], r["level"], r["t_r"]) for r in rows
        if f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}.json" not in have]
from collections import Counter
print(len(miss), Counter(m[0] for m in miss))
for m in miss[:10]:
    print(m)
