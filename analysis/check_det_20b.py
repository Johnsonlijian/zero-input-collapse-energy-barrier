import json
import numpy as np
from pathlib import Path

det = Path(r"E:\n0r53\runs\push_det\SMF20B")
can = Path(r"E:\n0r53\runs\push\SMF20B")
deep = Path(r"E:\n0r53\runs\push_deep\SMF20B")
n = 0
for f in sorted(det.glob("*.json")):
    jd = json.loads(f.read_text(errors="replace"))
    cp = can / f.name
    if not cp.exists():
        cp = deep / f.name
    if not cp.exists():
        continue
    jc = json.loads(cp.read_text(errors="replace"))
    Wd, Wc = jd.get("W_barrier"), jc.get("W_barrier")
    cd = np.asarray(jd.get("curve") or [])
    cc = np.asarray(jc.get("curve") or [])
    # first-divergence index in lam
    k = min(len(cd), len(cc))
    lam_d = cd[:k, 1] if k else []
    lam_c = cc[:k, 1] if k else []
    div = int(np.argmax(np.abs(lam_d - lam_c) > 1e-6 * max(1, np.abs(lam_c).max()))) if k else -1
    print(f.name, "Wd=", round(Wd or -1, 2), "Wc=", round(Wc or -1, 2),
          "lam0", round(jd.get("lam0") or 0, 2), "/", round(jc.get("lam0") or 0, 2),
          "steps", jd.get("n_steps"), jc.get("n_steps"), "div_idx", div)
    n += 1
    if n >= 12:
        break
