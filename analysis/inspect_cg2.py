import csv, json, glob, os
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

for model in ("SMF4CG", "SMF4B", "SMF2B", "SMF8B"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    print(f"\n== {model}  n={len(ts)}")
    ratios, durs, excursions = [], [], []
    for r in ts:
        key = f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}"
        kf = os.path.join(r"E:\n0r53\runs\kick", model, key + ".json")
        if not os.path.exists(kf):
            continue
        k = json.load(open(kf))
        # committed run nearest beta_crit
        cr = [x for x in k["runs"].values() if x["label"] == "committed" and x.get("t_coll")]
        if not cr:
            continue
        run = min(cr, key=lambda x: abs(x["beta"] - k["beta_crit"]))
        dur = run["t_coll"] - float(r["t_r"])
        hd = np.asarray(run.get("hist_d") or [])
        excur = int(np.sum(hd[:, int(r["icr"])] > 0.05)) if hd.size else 0  # rough excursion count proxy
        ratios.append(float(r["E_d"]) / float(r["W_m1"]))
        durs.append(dur)
        excursions.append(excur)
    ratios, durs, excursions = np.array(ratios), np.array(durs), np.array(excursions)
    if len(ratios) > 5:
        print("E/W median:", round(float(np.median(ratios)), 3))
        print("corr(E/W, escape duration):", round(float(np.corrcoef(ratios, durs)[0, 1]), 3))
        print("corr(E/W, excursion count):", round(float(np.corrcoef(ratios, excursions)[0, 1]), 3))
        print("median escape duration:", round(float(np.median(durs)), 2), "s")
