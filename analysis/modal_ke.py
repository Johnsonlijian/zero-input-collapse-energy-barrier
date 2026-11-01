"""Modal decomposition of the release kinetic energy, per frame.

For every push JSON (all release states, incl. transition states) the stored
``release_snapshot.floor_vel`` is projected onto the intact-frame elastic
mode shapes (M-orthonormal):

    KE_i = 0.5 * (v^T M phi_i)^2 / (phi_i^T M phi_i)

    sum_i KE_i = KE exactly for a complete basis; with n_storey modes the
    basis is complete for floor translational DOFs.

Outputs analysis/modal_ke.json:
  per model: median KE_1/KE and cumulative shares over transition states
  (ta, tstar tags) and over all states.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"E:\n0r53\code")
sys.path.insert(0, r"E:\n0r53\code_copy")

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis\modal_ke.json")
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]

_mode_cache = {}


N_MODES = 8


def modes(model):
    """First N_MODES elastic eigenmodes of the intact frame (floor X dofs)."""
    if model in _mode_cache:
        return _mode_cache[model]
    import openseespy.opensees as ops
    from driver53 import Frame53
    fr = Frame53(model)
    fr.build()
    n = len(fr.geo.floors)
    k = min(N_MODES, n)
    lam = ops.eigen(k)
    omega = np.sqrt(np.maximum(np.asarray(lam, float), 0.0))
    phi = np.zeros((n, k))
    for j, nd in enumerate(fr.geo.floors):
        for i in range(k):
            try:
                phi[j, i] = ops.nodeEigenvector(nd, i + 1, 1)
            except Exception:
                pass
    m = np.asarray(fr.geo.floor_mass, float)
    _mode_cache[model] = (omega, phi, m)
    return _mode_cache[model]


def modal_shares(v, phi, m):
    """KE_i/KE for the first modes plus the residual share in higher modes.

    The basis is incomplete (first k modes only): shares sum to <= 1 and the
    remainder is energy in modes > k (returned as ``resid``)."""
    v = np.asarray(v, float)
    ke = 0.5 * float(np.sum(m * v * v))
    if ke <= 0:
        return None, ke
    num = phi.T @ (m * v)
    den = phi.T @ (m[:, None] * phi)
    ke_i = 0.5 * num * num / np.diag(den)
    frac = ke_i / ke
    return np.append(frac, 1.0 - frac.sum()), ke


def main():
    out = {}
    for model in MODELS:
        omega, phi, m = modes(model)
        rows = []
        for p in sorted(glob.glob(str(RUNS / "push" / model / "*.json"))):
            d = json.loads(open(p).read())
            snap = d.get("release_snapshot") or {}
            v = snap.get("floor_vel")
            st = d.get("state", {})
            if v is None:
                v = (st.get("snapshot") or {}).get("floor_vel")
            if v is None or len(v) != len(m):
                continue
            shares, ke = modal_shares(v, phi, m)
            if shares is None:
                continue
            rows.append({"tag": st.get("tag"), "rid": st.get("rid"),
                         "t_r": st.get("t_r"), "committed": st.get("committed"),
                         "ke": ke, "shares": shares.tolist()})
        if not rows:
            continue
        tr = [r for r in rows if r["tag"] in ("ta", "tstar")]

        def agg(sub):
            S = np.array([r["shares"] for r in sub])
            return {"n": len(sub),
                    "ke1_med": float(np.median(S[:, 0])),
                    "ke1_p10": float(np.percentile(S[:, 0], 10)),
                    "ke1_p90": float(np.percentile(S[:, 0], 90)),
                    "cum2_med": float(np.median(S[:, :2].sum(1))),
                    "cum3_med": float(np.median(S[:, :3].sum(1))),
                    "resid_med": float(np.median(S[:, -1]))}
        out[model] = {"omega": omega.tolist(), "n_states": len(rows),
                      "transition": agg(tr), "all": agg(rows)}
        t = out[model]["transition"]
        print(f"{model}: T1={2*np.pi/omega[0]:.2f}s trans n={t['n']} "
              f"KE1/KE med={t['ke1_med']:.3f} [{t['ke1_p10']:.3f},{t['ke1_p90']:.3f}] "
              f"cum3={t['cum3_med']:.3f}", flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
