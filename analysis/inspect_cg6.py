import csv
import numpy as np

rows = list(csv.DictReader(open(r"E:\n0r53\analysis\law_table.csv", encoding="utf-8")))

for model in ("SMF4CG", "SMF2CG", "SMF4B", "SMF2B", "SMF8B"):
    ts = [r for r in rows if r["model"] == model and r["tag"] in ("ta", "tstar") and r["W_m1"] and float(r["W_m1"]) > 0 and r["E_d"]]
    ew = np.array([float(r["E_d"]) / float(r["W_m1"]) for r in ts])
    th = np.array([float(r["theta_c"]) for r in ts])
    kb = np.array([float(r["ke"]) / float(r["Wb"]) if r["Wb"] else np.nan for r in ts])
    wb = np.array([float(r["W_m1"]) / float(r["Wb"]) if r["Wb"] else np.nan for r in ts])
    print(f"\n{model}  n={len(ts)}  E/W med={np.median(ew):.3f}")
    print("  corr(E/W, release drift theta_c)      :", round(float(np.corrcoef(ew, th)[0, 1]), 3))
    ok = np.isfinite(wb) & np.isfinite(kb)
    print("  corr(E/W, W/Wb remaining barrier frac):", round(float(np.corrcoef(ew[ok], wb[ok])[0, 1]), 3))
    print("  corr(E/W, KE/Wb)                      :", round(float(np.corrcoef(ew[ok], kb[ok])[0, 1]), 3))
    # E/W split by drift terciles
    q = np.quantile(th, [0.33, 0.67])
    for lab, m in (("low-drift", th < q[0]), ("mid", (th >= q[0]) & (th < q[1])), ("high-drift", th >= q[1])):
        if m.sum():
            print(f"  {lab:10s} n={int(m.sum()):3d} E/W med={np.median(ew[m]):.3f}  theta_c med={np.median(th[m]):.4f}")
