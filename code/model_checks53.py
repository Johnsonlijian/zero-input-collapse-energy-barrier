"""Model properties for all R53 frames, using the hardened Frame53.barrier push.

Same output schema as the R52 model_checks.py so downstream tools
(build_tables.py, make_tables_tex.py) can merge the files.  Writes
E:/n0r53/results/model_checks.json (merging any existing keys).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from driver53 import Frame53  # noqa: E402

OUT = Path(r"E:\n0r53\results")
SDS, SD1, S1, R, IE = 1.0, 0.6, 0.6, 8.0, 1.0


def design_cs(height_in: float) -> tuple[float, float]:
    h_ft = height_in / 12.0
    ta = 0.028 * h_ft**0.8
    T = 1.4 * ta
    cs = min(SDS / (R / IE), SD1 / (T * R / IE))
    cs = max(cs, 0.044 * SDS * IE, 0.01, 0.5 * S1 / (R / IE))
    return cs, T


def check(name: str) -> dict:
    fr = Frame53(name)
    fr.build()
    ops.reactions()
    ry = sum(ops.nodeReaction(n, 2) for n in ops.getNodeTags() if abs(ops.nodeCoord(n, 2)) < 1e-6)
    W = float(fr.geo.floor_mass.sum() * 386.1)
    cs, Tdes = design_cs(fr.geo.height)
    out = {"model": name, "periods": fr.geo.periods, "T_design_CuTa": Tdes, "Cs": cs, "W_mass_kip": W,
           "gravity_reaction_kip": ry, "height_in": fr.geo.height, "n_story": len(fr.geo.h),
           "phi1": fr.geo.phi1.tolist(), "floor_mass": fr.geo.floor_mass.tolist(),
           "rayleigh": {k: v for k, v in fr.info.rayleigh.items() if k != "coeff_lines"}}
    # intact first-mode push; barrier() stops at the zero-resistance edge or
    # max_droof, whichever first -- same convention as the campaign pushes.
    po = fr.barrier(1.0, "mode1", 0, max_droof=0.20)
    c = np.asarray(po["curve"], dtype=float)
    k = int(np.argmax(c[:, 1]))
    zv = bool(po.get("reached_edge"))
    out.update({
        "Vmax_kip": float(po.get("lam_peak", c[k, 1])),
        "Vmax_over_W": float(po.get("lam_peak", c[k, 1]) / W),
        "Omega_static": float(po.get("lam_peak", c[k, 1]) / (cs * W)),
        "roof_drift_at_Vmax": float(c[k, 0]), "max_sdr_at_Vmax": float(c[k, 2]),
        "roof_drift_zero_V": float(po["droof_edge"]) if zv else None,
        "max_sdr_zero_V": float(po["sdr_edge"]) if zv else None,
        "work_to_zero_V_kipin": float(po["W_barrier"]) if zv else None,
        "work_to_peak_kipin": float(np.max(c[:, 3])),
        "push_end_roof_drift": float(c[-1, 0]),
        "push_end_max_sdr": float(c[-1, 2]),
        "push_converged_end": bool(po.get("converged")),
        "push_reached_zero_V": zv,
        "curve": c[:: max(1, len(c) // 600)].tolist(),
    })
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
                             "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
    res = {}
    for nm in names:
        res[nm] = check(nm)
        r = res[nm]
        print(nm, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
                   if k not in ("curve", "phi1", "floor_mass", "rayleigh")}, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "model_checks.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(res)
    path.write_text(json.dumps(old, indent=1), encoding="utf-8")
    print("wrote", path)
