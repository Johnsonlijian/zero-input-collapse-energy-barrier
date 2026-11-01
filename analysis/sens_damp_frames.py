"""Damping-ladder sensitivity, per frame (A6-style extension of the 4B dev check).

For each frame with kick_damp05/kick_damp20 runs, on states having all four
beta_crit (undamped, 0.5x, 1x, 2x damping): median beta^2 per scale and a
per-state linear fit beta^2 = a*s + b, reporting b/measured(0) so a spurious
undamped intercept would show as ratio != 1.
Writes analysis/sens_damp_frames.json.
"""
import glob
import json
import os

import numpy as np

BASE = r"E:\n0r53\runs"
OUT = r"E:\n0r53\analysis\sens_damp_frames.json"


def load(phase, model):
    out = {}
    for p in glob.glob(os.path.join(BASE, phase, model, "*.json")):
        try:
            out[os.path.basename(p)] = json.load(open(p, errors="replace"))
        except Exception:
            pass
    return out


models = sorted({d for ph in ("kick_damp05", "kick_damp20")
                 for d in (os.path.basename(x) for x in glob.glob(os.path.join(BASE, ph, "*")))})
res_all = {}
for m in models:
    phases = {"kick": 1.0, "kick_damp05": 0.5, "kick_damp20": 2.0, "kick_undamped": 0.0}
    D = {ph: load(ph, m) for ph in phases}
    keys = {k for k in (set(D["kick_damp05"]) | set(D["kick_damp20"]))}
    rows = []
    for k in sorted(keys):
        r = {"key": k}
        for ph, s in phases.items():
            d = D[ph].get(k)
            r[s] = d.get("beta_crit") if d else None
        rows.append(r)
    ok = [r for r in rows if all(r[s] is not None for s in (0.0, 0.5, 1.0, 2.0))]
    out = {"n_tasks": len(keys), "n_all4": len(ok)}
    if ok:
        out["b2_med"] = {str(s): float(np.median([r[s] ** 2 for r in ok]))
                         for s in (0.0, 0.5, 1.0, 2.0)}
        rr = []
        for r in ok:
            s = np.array([0.0, 0.5, 1.0, 2.0])
            y = np.array([r[s_] for s_ in s]) ** 2
            a, b = np.polyfit(s, y, 1)
            rr.append((a, b, y[0], b / y[0] if y[0] > 0 else np.nan))
        rr = np.array(rr)
        out["slope_med"] = float(np.median(rr[:, 0]))
        out["intercept_over_meas0"] = {
            "median": float(np.nanmedian(rr[:, 3])),
            "p10": float(np.nanpercentile(rr[:, 3], 10)),
            "p90": float(np.nanpercentile(rr[:, 3], 90))}
        # median per-state relative beta_crit change at s=0.5 and s=2
        out["rel_dbcrit"] = {
            str(s): float(np.median([(r[s] / r[1.0] - 1.0) for r in ok if r[1.0]]))
            for s in (0.0, 0.5, 2.0)}
    res_all[m] = out
    print(m, json.dumps(out), flush=True)
json.dump(res_all, open(OUT, "w"), indent=1)
print("->", OUT)
