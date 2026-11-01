import csv, json, glob, os
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

for model in ("SMF4CG", "SMF2CG", "SMF4B", "SMF2B", "SMF8B"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    grav_col, mf_col, other = 0, 0, 0
    r_grav, r_mf = [], []
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
        fm = float(np.max(np.abs(run["final_sdr"])))
        ratio = float(r["E_d"]) / float(r["W_m1"])
        if fm < 0.145:          # moment frame below limit at collapse step -> gravity frame triggered
            grav_col += 1
            r_grav.append(ratio)
        elif fm >= 0.149:
            mf_col += 1
            r_mf.append(ratio)
        else:
            other += 1
    tot = grav_col + mf_col + other
    print(f"{model}: n={len(ts)} checked={tot}  gravity-frame-collapse={grav_col} ({100*grav_col/max(tot,1):.0f}%)  mf={mf_col} edge={other}")
    if r_grav:
        print("   E/W median gravity-frame collapses:", round(float(np.median(r_grav)), 3), f"(n={len(r_grav)})")
    if r_mf:
        print("   E/W median moment-frame collapses :", round(float(np.median(r_mf)), 3), f"(n={len(r_mf)})")
