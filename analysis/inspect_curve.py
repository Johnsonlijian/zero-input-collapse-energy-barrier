import json, os
import numpy as np

for model, key in (("SMF4CG", "FF120411__hi__23.0550"), ("SMF4B", None), ("SMF4CG", "FF120612__hi__20.6550")):
    if key is None:
        import glob
        fs = sorted(glob.glob(rf"E:\n0r53\runs\push\{model}\*.json"))
        key = os.path.basename(fs[0])[:-5]
    f = rf"E:\n0r53\runs\push\{model}\{key}.json"
    if not os.path.exists(f):
        print("missing", f); continue
    p = json.load(open(f))
    pat = p.get("pattern", "?")
    res = p.get("results", {}).get("mode1", p.get("mode1", {}))
    c = np.asarray(res.get("curve") or [])
    print(f"\n== {model} {key}  sgn={p.get('sgn')} icr={p.get('icr')}  W={res.get('W_barrier')} lam0={res.get('lam0')} lam_peak={res.get('lam_peak')} edge={res.get('reached_edge')} downhill={res.get('downhill')}")
    if c.size:
        print("  curve n=", len(c), " cols: droof lam sdr_max work")
        idx = np.linspace(0, len(c) - 1, min(15, len(c))).astype(int)
        for i in idx:
            print("   ", " ".join(f"{v:10.4f}" for v in c[i]))
