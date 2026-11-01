import csv
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))
ts = [r for r in rows if r["model"] == "SMF4CG" and r["tag"] in ("ta", "tstar")]
print("n transition:", len(ts))
for r in ts[:15]:
    print(f"{r['rid'][:12]:12s} {r['tag']:5s} W={float(r['W_m1'] or 0):9.1f} Wmin={float(r['Wmin_m1'] or 0):9.1f} "
          f"lam0={float(r['lam0_m1'] or 0):8.1f} edge={r['edge_m1']} sdrE={float(r['sdr_edge_m1'] or 0):.4f} "
          f"E_d={float(r['E_d'] or 0):9.1f} b_d={float(r['beta_d'] or 0):.3f} label={r['label_r52'][:3]} ke={float(r['ke'] or 0):.1f}")
rr = np.array([float(r["E_d"]) / float(r["W_m1"]) for r in ts if r["W_m1"] and float(r["W_m1"]) > 0])
print("E/W median:", np.median(rr), "p10-p90:", np.percentile(rr, [10, 90]), "n:", len(rr))
down = [r for r in ts if r.get("downhill_m1") == "True"]
print("downhill:", len(down))
# ratio by label
for lab in ("committed", "recoverable"):
    x = np.array([float(r["E_d"]) / float(r["W_m1"]) for r in ts if r["W_m1"] and float(r["W_m1"]) > 0 and r["label_r52"] == lab])
    if len(x):
        print(lab, "median E/W:", np.median(x), "n:", len(x))
# how often is the released drift already deep (theta_c close to sdr_edge)?
d = np.array([float(r["sdr_edge_m1"]) - float(r["theta_c"]) for r in ts if r["sdr_edge_m1"]])
print("sdr_edge - release drift: median", np.median(d), "p10-p90", np.percentile(d, [10, 90]))
