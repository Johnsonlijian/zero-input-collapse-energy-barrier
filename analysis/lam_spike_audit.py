"""Audit lambda spikes inside the work-integrating window of pushes.

A3 measures W_c to the earlier of the first lambda<=0 (after positive) and the
drift limit; for 'trunc' exits the whole curve's cumulative work is the bound.
If |lambda| spikes inside that window the integrated work could be corrupted.
This audit counts, per frame, pushes whose curve contains |lam| > LAM_SPIKE
before the W_c truncation index, and reports the worst within-window spike.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"E:\n0r53\analysis")
from build_tables import DRIFT_LIMIT, w_collapse  # noqa: E402

RUNS = Path(r"E:\n0r53\runs")
LAM_SPIKE = 1.0e4
out = {}
for d in sorted(RUNS.glob("push/*")):
    if not d.is_dir():
        continue
    n = spk = inside = 0
    worst = 0.0
    lims = {}
    for f in d.glob("*.json"):
        try:
            j = json.loads(f.read_text(errors="replace"))
        except Exception:
            continue
        c = np.asarray(j.get("curve") or [], dtype=float)
        if c.size == 0:
            continue
        n += 1
        sdr, lam = c[:, 2], c[:, 1]
        pos = np.where(lam > 0)[0]
        if not len(pos):
            lims["downhill"] = lims.get("downhill", 0) + 1
            continue
        i1 = int(pos[0])
        neg = np.where(lam[i1:] <= 0)[0]
        i_edge = i1 + int(neg[0]) if len(neg) else len(c)
        di = np.where(sdr >= DRIFT_LIMIT)[0]
        i_drift = int(di[0]) if len(di) else len(c)
        i_exit = min(i_edge, i_drift)
        w = np.abs(lam) > LAM_SPIKE
        if w.any():
            spk += 1
            i_spk = int(np.argmax(w))
            worst = max(worst, float(np.max(np.abs(lam))))
            if i_spk < i_exit:
                inside += 1
        _, lim = w_collapse({"curve": j.get("curve") or [],
                             "downhill": j.get("downhill"),
                             "W_barrier": j.get("W_barrier")})
        lims[lim] = lims.get(lim, 0) + 1
    out[d.name] = {"n": n, "lam_spike": spk, "spike_inside_window": inside,
                   "worst_abs_lam": worst, "lims": lims}
    print(f"{d.name}: n={n} spikes={spk} inside={inside} "
          f"worst={worst:.2e} lims={lims}", flush=True)
Path(r"E:\n0r53\analysis\lam_spike_audit.json").write_text(json.dumps(out, indent=1))
