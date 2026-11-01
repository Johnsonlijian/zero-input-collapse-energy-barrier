"""One-time stored first-mode stamp (R53v1.0+A17).

The default ops.eigen(1) solve (band-symmetric Arpack) starts from a random
vector and returns first-mode vectors differing at ~1e-16 between fresh
processes.  For forward pushes of composite frames that perturbation is
amplified at the strength cliff of the gravity connections into observable
path bifurcations (A13 fork audit).  The deterministic banded/LAPACK solvers
either do not handle the generalised problem (symmBandLapack) or return
eigenpairs in arbitrary order with occasional complex values on these models
(fullGenLapack), so instead of re-solving we FREEZE the Arpack result: any
returned vector is a valid first-mode eigenvector (same eigenvalue, same
subspace); storing it removes the run-to-run noise, which is the only thing
the push pattern needed.  driver.Frame.build() loads the stored file when
present and stamps phi1_source='stored_arpack_frozen'.

For sanity the script also re-solves with a fresh Arpack call and reports
|dphi|; a large value would indicate a defective first-mode subspace.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "code_copy"))

import numpy as np
import openseespy.opensees as ops

from driver53 import Frame53

MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
OUT = HERE.parent / "code_copy" / "phi1"
OUT.mkdir(exist_ok=True)


def main():
    for m in MODELS:
        t0 = time.time()
        fr = Frame53(m)
        fr.build()
        phi = np.array(fr.geo.phi1, dtype=float)
        # fresh Arpack re-solve as a consistency check
        ops.wipeAnalysis()
        ops.eigen(1)
        phi2 = np.array([ops.nodeEigenvector(n, 1, 1) for n in fr.geo.floors])
        if phi2[-1] < 0:
            phi2 = -phi2
        phi2 = phi2 / phi2[-1]
        diff = float(np.max(np.abs(phi - phi2)))
        rec = {"model": m, "solver": "arpack_stored_frozen",
               "phi1": [float(x) for x in phi],
               "T1_s": float(fr.info.periods[0]) if fr.info.periods else None,
               "max_abs_diff_vs_fresh_arpack": diff}
        (OUT / f"{m}.json").write_text(json.dumps(rec, indent=1))
        print(f"{m}: T1={rec['T1_s']:.4f} |dphi|={diff:.2e} "
              f"({time.time()-t0:.0f}s)", flush=True)
    print(json.dumps({"n_models": len(MODELS)}))


if __name__ == "__main__":
    main()
