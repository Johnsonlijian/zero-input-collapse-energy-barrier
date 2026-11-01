import glob
import json
import os

import numpy as np

J = r"E:\n0r53\analysis\fork_det.json"
j = json.load(open(J))
out = {}
for mod in j["per_model"]:
    devs = []
    for d in glob.glob(rf"E:\n0r53\runs\push_det\{mod}\*.json"):
        n = os.path.basename(d)
        jd = json.load(open(d))
        cp = None
        for base in (r"E:\n0r53\runs\push", r"E:\n0r53\runs\push_deep"):
            p = os.path.join(base, mod, n)
            if os.path.exists(p):
                cp = p
                break
        if not cp:
            continue
        jc = json.load(open(cp))
        Wd, Wc = jd.get("W_barrier"), jc.get("W_barrier")
        if Wd and Wc and Wc > 0:
            devs.append(Wd / Wc - 1)
    a = np.abs(devs) if devs else np.array([])
    out[mod] = {"n": len(devs), "gt1pct": int((a > 0.01).sum()),
                "gt10pct": int((a > 0.10).sum()),
                "med": float(np.median(devs)) if len(devs) else None,
                "max": float(a.max()) if len(devs) else None}
j["dev_counts"] = out
json.dump(j, open(J, "w"), indent=1)
print(json.dumps(out, indent=1))
