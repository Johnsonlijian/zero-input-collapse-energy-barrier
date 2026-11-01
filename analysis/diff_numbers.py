"""Diff two numbers.tex files: changed, added and removed macros."""
import re
import sys

PAT = re.compile(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}")
a = dict(PAT.findall(open(sys.argv[1], encoding="utf-8").read()))
b = dict(PAT.findall(open(sys.argv[2], encoding="utf-8").read()))
ch = [(k, a[k], b[k]) for k in a if k in b and a[k] != b[k]]
print(f"old {len(a)}  new {len(b)}  changed {len(ch)}  added {len(set(b) - set(a))}  removed {len(set(a) - set(b))}")
filt = sys.argv[3] if len(sys.argv) > 3 else ""
for k, x, y in ch:
    if filt in k:
        print(f"  {k}: {x} -> {y}")
print("added:", " ".join(sorted(k for k in set(b) - set(a) if filt in k))[:3000])
print("removed:", " ".join(sorted(set(a) - set(b)))[:2000])
