import csv, json, os
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

H = {"SMF4CG": None, "SMF4B": None}  # storey heights filled from geo if needed; use drift sums (roof disp ∝ sum d_i h_i)

for model in ("SMF4CG", "SMF4B", "SMF2B"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    retreat, advance = [], []
    for r in ts:
        key = f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}"
        kf = os.path.join(r"E:\n0r53\runs\kick", model, key + ".json")
        if not os.path.exists(kf):
            continue
        k = json.load(open(kf))
        cr = [x for x in k["runs"].values() if x["label"] == "committed" and x.get("t_coll")]
        if not cr:
            continue
        run = min(cr, key=lambda x: abs(x["beta"] - k["beta_crit"]))
        # reconstruct floor disps: u_i = sum_{j<=i} d_j h_j ; roof = sum d_j h_j
        # storey heights unknown here -> use uniform proxy sum(d_j) when h uniform is wrong; instead read hist_d last row = final drifts, first row ~ release
        hd = np.asarray(run.get("hist_d") or [])
        if hd.size == 0:
            continue
        d_rel = np.asarray((run.get("snapshot_release") or {}).get("sdr") or hd[0])
        d_fin = hd[-1]
        # roof displacement proxy: cumulative sum of drifts (heights ~uniform within a frame; sign of change is what matters)
        u_rel = float(np.sum(d_rel)); u_fin = float(np.sum(d_fin))
        ratio = float(r["E_d"]) / float(r["W_m1"])
        (retreat if abs(u_fin) < abs(u_rel) else advance).append(ratio)
    print(f"{model}: n={len(retreat)+len(retreat)}  roof-retreat n={len(retreat)} E/W med={np.median(retreat) if retreat else '-'} | roof-advance n={len(advance)} E/W med={np.median(advance) if advance else '-'}")
