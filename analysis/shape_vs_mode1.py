"""Alternative-pattern barrier vs first-mode barrier, paired per state.

For every state with both a mode-1 push and a collapse-shape push (and,
where available, a storey push), compare:

  W_shape / W_m1            -- is the shape path a lower pass?
  c_shape = Ecrit0 / W_shape vs c0 = Ecrit0 / W_m1
  KE_phi / KE               -- share of release KE aligned with escape shape

If the tall-frame sub-unity c0 comes from the declared pattern overshooting
the true pass, W_shape should fall below W_m1 and c_shape should move
toward unity on the same states.

Outputs analysis/shape_vs_mode1.json
"""
import glob
import json
from pathlib import Path

import numpy as np

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis\shape_vs_mode1.json")
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]


def load(phase, model, rid, lvl, t_r, extra=""):
    p = RUNS / phase / model / f"{rid}__{lvl}__{t_r:.4f}{extra}.json"
    if not p.exists():
        p = RUNS / phase / model / f"{rid}__{lvl}__{t_r:.4f}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main():
    out = {}
    for model in MODELS:
        rows = []
        for p in sorted(glob.glob(str(RUNS / "push" / model / "*.json"))):
            d = json.loads(open(p).read())
            st = d.get("state", {})
            if st.get("tag") not in ("ta", "tstar"):
                continue
            w1 = d.get("W_barrier_from_min", d.get("W_barrier"))
            ke = d.get("ke_reproduced") or (st.get("snapshot") or {}).get("ke")
            if w1 is None or not ke:
                continue
            rid, lvl, t_r = st["rid"], st["level"], st["t_r"]
            ku = load("kick_undamped", model, rid, lvl, t_r)
            bc0 = None if ku is None else ku.get("beta_crit")
            e0 = None if bc0 is None else bc0 * bc0 * ke
            row = {"rid": rid, "t_r": t_r, "tag": st["tag"], "ke": ke,
                   "w1": w1, "e0": e0}
            sh = load("push_shape", model, rid, lvl, t_r, extra="__push_shape")
            if sh and sh.get("W_shape") is not None and sh.get("converged"):
                row["w_shape"] = sh["W_shape"]
                row["ke_phi"] = sh.get("KE_phi")
            stj = load("push_story", model, rid, lvl, t_r)
            if stj and stj.get("W_barrier_from_min") is not None:
                row["w_story"] = stj["W_barrier_from_min"]
            rows.append(row)
        if not rows:
            continue
        s = {}
        for key, wkey in (("shape", "w_shape"), ("story", "w_story")):
            sub = [r for r in rows if r.get(wkey) is not None and r["w1"] > 0]
            if not sub:
                continue
            rat = np.array([r[wkey] / r["w1"] for r in sub])
            s[f"{key}_n"] = len(sub)
            s[f"{key}_W_ratio_med"] = float(np.median(rat))
            s[f"{key}_W_ratio_p10"] = float(np.percentile(rat, 10))
            s[f"{key}_W_ratio_p90"] = float(np.percentile(rat, 90))
            both = [r for r in sub if r["e0"] is not None]
            if both:
                c0 = np.array([r["e0"] / r["w1"] for r in both])
                cs = np.array([r["e0"] / r[wkey] for r in both if r[wkey] > 0])
                s[f"{key}_paired_n"] = len(both)
                s[f"{key}_c0_med"] = float(np.median(c0))
                s[f"{key}_calt_med"] = float(np.median(cs)) if len(cs) else None
            kef = [r["ke_phi"] / r["ke"] for r in sub
                   if r.get("ke_phi") is not None and r["ke"] > 0]
            if kef:
                s[f"{key}_kefrac_med"] = float(np.median(kef))
        out[model] = {"n": len(rows), **s}
        print(model, json.dumps(s, indent=None), flush=True)
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
