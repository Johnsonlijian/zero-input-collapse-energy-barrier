import csv, json, os
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

def w_at_sdr(p, target=0.15):
    c = np.asarray(p.get("curve") or [], dtype=float)
    if c.size == 0:
        return np.nan
    sdr, w = c[:, 2], c[:, 3]
    i = np.argmax(sdr >= target)
    if i == 0 and sdr[0] < target:
        return np.nan            # never reaches target within measured curve
    if sdr[i] < target:
        return np.nan
    if i == 0:
        return float(w[0])
    t = (target - sdr[i - 1]) / max(sdr[i] - sdr[i - 1], 1e-12)
    return float(w[i - 1] + t * (w[i] - w[i - 1]))

for model in ("SMF4CG", "SMF4B", "SMF2B", "SMF8B", "SMF2CG"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    r_edge, r_15, r_both = [], [], []
    for r in ts:
        key = f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}"
        pf = os.path.join(r"E:\n0r53\runs\push", model, key + ".json")
        if not os.path.exists(pf):
            continue
        p = json.load(open(pf))
        w15 = w_at_sdr(p)
        e = float(r["E_d"])
        if np.isfinite(w15) and w15 > 0:
            r_15.append(e / w15)
            r_both.append((e, float(r["W_m1"]), w15))
        r_edge.append(e / float(r["W_m1"]))
    r_edge, r_15 = np.array(r_edge), np.array(r_15)
    print(f"{model}: n={len(r_edge)}  E/W_edge med={np.median(r_edge):.3f}  E/W_0.15 med={np.median(r_15):.3f} (n={len(r_15)})  "
          f"W_edge/W_15 med={np.median([b/w for _,b,w in r_both]):.3f}" if r_both else "")
