"""Model properties: periods, weights, gravity reaction, first-mode pushover.

Writes results/model_checks.json (curves included) for Table 1 and Fig. 2.
Design base shear per ASCE 7-10 for the archetype site (SDC Dmax:
SDS = 1.0 g, SD1 = 0.6 g, S1 = 0.6 g), R = 8, Ie = 1, T = Cu*Ta.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import openseespy.opensees as ops

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from driver import Frame  # noqa: E402

OUT = HERE.parent / "results"
SDS, SD1, S1, R, IE = 1.0, 0.6, 0.6, 8.0, 1.0


def design_cs(height_in: float) -> tuple[float, float]:
    h_ft = height_in / 12.0
    ta = 0.028 * h_ft**0.8
    T = 1.4 * ta
    cs = min(SDS / (R / IE), SD1 / (T * R / IE))
    cs = max(cs, 0.044 * SDS * IE, 0.01, 0.5 * S1 / (R / IE))
    return cs, T


def check(name: str) -> dict:
    fr = Frame(name)
    fr.build()
    ops.reactions()
    ry = sum(ops.nodeReaction(n, 2) for n in ops.getNodeTags() if abs(ops.nodeCoord(n, 2)) < 1e-6)
    W = float(fr.geo.floor_mass.sum() * 386.1)
    cs, Tdes = design_cs(fr.geo.height)
    out = {"model": name, "periods": fr.geo.periods, "T_design_CuTa": Tdes, "Cs": cs, "W_mass_kip": W,
           "gravity_reaction_kip": ry, "height_in": fr.geo.height, "n_story": len(fr.geo.h),
           "phi1": fr.geo.phi1.tolist(), "floor_mass": fr.geo.floor_mass.tolist(),
           "rayleigh": {k: v for k, v in fr.info.rayleigh.items() if k != "coeff_lines"}}
    po = fr.pushover(1.0, max_roof_drift=0.15, droof=0.05, stop_at_zero=False)
    c = np.array(po["curve"])
    k = int(np.argmax(c[:, 1]))
    z = [i for i in range(k, len(c)) if c[i, 1] <= 0.0]
    out.update({
        "Vmax_kip": float(c[k, 1]), "Vmax_over_W": float(c[k, 1] / W), "Omega_static": float(c[k, 1] / (cs * W)),
        "roof_drift_at_Vmax": float(c[k, 0]), "max_sdr_at_Vmax": float(c[k, 2]),
        "roof_drift_zero_V": float(c[z[0], 0]) if z else None,
        "max_sdr_zero_V": float(c[z[0], 2]) if z else None,
        "work_to_zero_V_kipin": float(c[z[0], 3]) if z else None,
        "work_to_peak_kipin": float(np.max(c[:, 3])),
        "curve": c[:: max(1, len(c) // 600)].tolist(),
    })
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or ["SMF4B", "SMF8B", "SMF4CG", "SMF8CG"]
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
