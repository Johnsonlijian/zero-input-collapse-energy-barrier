"""Verify the repaired SMF20B/SMF20CG stored first-mode vectors (A17).

Builds the frame, loads the stored phi1 via Frame.build(), then re-solves with
a fresh Arpack draw and reports |dphi|.  A valid stored vector must agree to
~1e-12 or better.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code_copy"))

import numpy as np
import openseespy.opensees as ops
from driver53 import Frame53

for m in ("SMF20B", "SMF20CG"):
    fr = Frame53(m)
    fr.build()
    phi = np.array(fr.geo.phi1, float)
    src = getattr(fr.geo, "phi1_source", "?")
    ops.wipeAnalysis()
    ops.eigen(1)
    phi2 = np.array([ops.nodeEigenvector(n, 1, 1) for n in fr.geo.floors])
    if phi2[-1] < 0:
        phi2 = -phi2
    phi2 = phi2 / phi2[-1]
    d = float(np.max(np.abs(phi - phi2)))
    print(f"{m}: phi1_source={src} sum={phi.sum():.4f} |dphi|={d:.3e} "
          f"mono={float(np.mean(np.diff(phi) > 0)):.2f}", flush=True)
