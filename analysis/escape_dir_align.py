"""Alignment of the release velocity direction with candidate escape patterns.

For every push transition state (ta/tstar) the stored release_snapshot.floor_vel
is compared, in the mass-metric inner product <a,b>_M = a^T M b, against:

  phi1   -- intact first mode (the declared push pattern)
  shape  -- the collapse shape of the SAME state's committed continuation
            (peak per-storey SDR of the committed zic release at that t_r)
  storey -- uniform mechanism loading (unit vector)

cos_M = <v, p>_M / sqrt(<v,v>_M <p,p>_M); squared = share of v along p.

Outputs analysis/escape_dir_align.json
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"E:\n0r53\code")
sys.path.insert(0, r"E:\n0r53\code_copy")

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis\escape_dir_align.json")
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]

_mode_cache = {}


def modes(model):
    if model in _mode_cache:
        return _mode_cache[model]
    import openseespy.opensees as ops
    from driver53 import Frame53
    fr = Frame53(model)
    fr.build()
    n = len(fr.geo.floors)
    lam = ops.eigen(1)
    phi1 = np.array([ops.nodeEigenvector(nd, 1, 1) for nd in fr.geo.floors])
    m = np.asarray(fr.geo.floor_mass, float)
    _mode_cache[model] = (phi1, m)
    return phi1, m


def mcos(a, b, m):
    a = np.asarray(a, float); b = np.asarray(b, float)
    na = float(a @ (m * a)); nb = float(b @ (m * b))
    if na <= 0 or nb <= 0:
        return None
    return float(a @ (m * b)) / np.sqrt(na * nb)


def main():
    out = {}
    for model in MODELS:
        phi1, m = modes(model)
        n = len(m)
        unit = np.ones(n)
        # collapse shape per (rid, t_r): peak per-storey SDR of committed zic release
        shapes = {}
        for p in glob.glob(str(RUNS / "zic" / model / "*.json")):
            d = json.loads(open(p).read())
            for rel in (d.get("releases") or {}).values():
                if rel.get("committed") and rel.get("peak_sdr"):
                    shapes[(d["rid"], float(rel["t_r"]))] = np.asarray(
                        rel["peak_sdr"], float)
        rows = []
        for p in sorted(glob.glob(str(RUNS / "push" / model / "*.json"))):
            d = json.loads(open(p).read())
            st = d.get("state", {})
            if st.get("tag") not in ("ta", "tstar"):
                continue
            snap = d.get("release_snapshot") or {}
            v = snap.get("floor_vel")
            if v is None or len(v) != n:
                continue
            key = (st["rid"], float(st["t_r"]))
            sh = shapes.get(key)
            row = {"rid": st["rid"], "t_r": st["t_r"], "tag": st["tag"],
                   "committed": st.get("committed"),
                   "cos_phi1": mcos(v, phi1, m),
                   "cos_unit": mcos(v, unit, m),
                   "cos_shape": mcos(v, sh, m) if sh is not None and len(sh) == n else None}
            rows.append(row)
        if not rows:
            continue
        def agg(key):
            vals = [r[key] ** 2 for r in rows if r[key] is not None]
            if not vals:
                return None
            return {"n": len(vals), "med": float(np.median(vals)),
                    "p10": float(np.percentile(vals, 10)),
                    "p90": float(np.percentile(vals, 90))}
        out[model] = {"n": len(rows),
                      "n_with_shape": sum(r["cos_shape"] is not None for r in rows),
                      "v2_phi1": agg("cos_phi1"),
                      "v2_shape": agg("cos_shape"),
                      "v2_unit": agg("cos_unit")}
        a = out[model]
        print(model, "n=", a["n"], "shape_n=", a["n_with_shape"],
              "v2phi1=%.3f" % (a["v2_phi1"]["med"] if a["v2_phi1"] else -1),
              "v2shape=%.3f" % (a["v2_shape"]["med"] if a["v2_shape"] else -1),
              flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
