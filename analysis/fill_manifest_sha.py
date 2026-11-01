"""Fill empty sha256 cells in logs/server_sync_manifest.csv.

relpath stores the bare file name; the same name can live under several
runs/<family>/<model>/ dirs.  A row is filled with the hash when every local
occurrence agrees (identical duplicates are the quarantine case); rows whose
occurrences disagree get CONFLICT:<n> and are listed for manual resolution.
"""
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

RUNS = Path(r"E:\n0r53\runs")
MAN = Path(r"E:\n0r53\logs\server_sync_manifest.csv")


def sha(p):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main():
    idx = defaultdict(set)
    for p in RUNS.rglob("*.json"):
        idx[p.name].add(sha(p))
    rows = list(csv.reader(MAN.open(encoding="utf-8")))
    hdr, data = rows[0], rows[1:]
    filled = conflict = missing = 0
    conflicts = []
    for r in data:
        if len(r) < 4 or r[1]:
            continue
        hs = idx.get(r[0])
        if not hs:
            missing += 1
            r[1] = "MISSING_LOCAL"
        elif len(hs) == 1:
            r[1] = hs.pop()
            filled += 1
        else:
            conflict += 1
            r[1] = f"CONFLICT:{len(hs)}"
            conflicts.append(r[0])
    with MAN.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(data)
    print(f"filled={filled} conflict={conflict} missing={missing}")
    for c in conflicts[:20]:
        print("  CONFLICT", c)


if __name__ == "__main__":
    main()
