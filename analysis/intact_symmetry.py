"""Mirror-symmetry check of the intact-frame barrier pushes (barrier_intact_deep).
The undeformed frame is geometrically symmetric, so the fwd and bwd pushes should coincide
up to numerical noise.  Over the common roof-drift range of the two curves report the
largest load-factor difference relative to the peak load factor and the work difference
at the end of the common range; with the resolved direction's barrier (w_collapse) this
justifies a 'mirror' intact barrier when the other direction stalls numerically.
Writes analysis/intact_symmetry.json."""
import json
from pathlib import Path

import numpy as np

from build_tables import w_collapse

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "intact_symmetry.json"
res = {}
for p in sorted((RUNS / "barrier_intact_deep").glob("*.json")):
    d = json.loads(p.read_text())
    cf, cb = (np.asarray(d[k]["curve"], float) for k in ("W_fwd", "W_bwd"))
    xf, xb = np.abs(cf[:, 0]), np.abs(cb[:, 0])
    xmax = min(xf.max(), xb.max())
    grid = np.linspace(0.0, xmax, 400)
    lf, lb = np.interp(grid, xf, cf[:, 1]), np.interp(grid, xb, cb[:, 1])
    wf, wb = np.interp(xmax, xf, cf[:, 3]), np.interp(xmax, xb, cb[:, 3])
    lam_pk = max(cf[:, 1].max(), cb[:, 1].max())
    Wf, kf = w_collapse(d["W_fwd"])
    Wb, kb = w_collapse(d["W_bwd"])
    res[p.stem] = {"common_droof": float(xmax), "max_dlam_over_peak": float(np.max(np.abs(lf - lb)) / lam_pk),
                   "dW_common_rel": float(abs(wf - wb) / max(abs(wb), 1e-9)),
                   "W_fwd": Wf, "lim_fwd": kf, "W_bwd": Wb, "lim_bwd": kb,
                   "droof_end_fwd": float(xf.max()), "droof_end_bwd": float(xb.max()),
                   # pre-peak comparison: up to the smaller of the two peak-load drifts (insensitive to
                   # where each push meets its edge); peak load factors over the common range
                   "max_dlam_prepeak_over_peak": float(np.max(np.abs(lf - lb)[grid <= min(
                       xf[int(np.argmax(cf[:, 1]))], xb[int(np.argmax(cb[:, 1]))])]) / lam_pk),
                   "peak_lam_fwd": float(lf.max()), "peak_lam_bwd": float(lb.max()),
                   "peak_lam_rel_diff": float((lf.max() - lb.max()) / max(lf.max(), lb.max()))}
    r = res[p.stem]
    print(f"{p.stem:8s} common droof {xmax:.4f}  max|dlam|/peak {r['max_dlam_over_peak']:.4f}  "
          f"dW(common) {r['dW_common_rel']:.4f}  fwd {Wf:.0f} {kf} (end {xf.max():.3f})  bwd {Wb:.0f} {kb} (end {xb.max():.3f})")
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
