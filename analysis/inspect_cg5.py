import csv, json, os
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

for model in ("SMF4CG", "SMF4B", "SMF2B", "SMF8B"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    opp, same = [], []
    for r in ts:
        key = f"{r['rid']}__{r['level']}__{float(r['t_r']):.4f}"
        kf = os.path.join(r"E:\n0r53\runs\kick", model, key + ".json")
        pf = os.path.join(r"E:\n0r53\runs\push", model, key + ".json")
        if not (os.path.exists(kf) and os.path.exists(pf)):
            continue
        k = json.load(open(kf)); p = json.load(open(pf))
        st = p.get("state") or {}
        sgn = float(st.get("sgn") or p.get("sgn") or 0.0)
        icr = int(st.get("icr") or p.get("icr") or r["icr"])
        cr = [x for x in k["runs"].values() if x["label"] == "committed" and x.get("t_coll")]
        if not cr:
            continue
        run = min(cr, key=lambda x: abs(x["beta"] - k["beta_crit"]))
        d_rel = np.asarray((run.get("snapshot_release") or {}).get("sdr") or [])
        d_fin = np.asarray(run["final_sdr"])
        if d_rel.size == 0 or d_fin.size == 0:
            continue
        dd = d_fin - d_rel
        if icr >= len(dd):
            icr = int(np.argmax(np.abs(dd)))
        esc_dir = np.sign(dd[icr])
        if esc_dir == 0:
            continue
        ratio = float(r["E_d"]) / float(r["W_m1"])
        (opp if esc_dir * sgn < 0 else same).append(ratio)
    print(f"{model}: same-dir n={len(same)} E/W med={round(float(np.median(same)),3) if same else '-'} | opp-dir n={len(opp)} E/W med={round(float(np.median(opp)),3) if opp else '-'}")
