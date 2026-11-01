"""Within-set test of the duration-erosion mechanism (partial J3 cover).

Record duration proxy = t95 (95% Arias time) per record from history_table.csv.
Per frame, Spearman correlation across records of:
  a) t95 vs erosion depth at t*  (W_star / W_t95, lower = more erosion)
  b) t95 vs commitment timing   ((t_star - t95)/t95 on collapsing histories)

A positive duration effect predicts (a) negative rho (longer records ->
deeper erosion at commitment) and (b) positive rho (commitment lands later
in the coda on longer records).

Outputs analysis/duration_erosion.json
"""
import json
import pandas as pd
import numpy as np
from scipy.stats import spearmanr

OUT = r"E:\n0r53\analysis\duration_erosion.json"
df = pd.read_csv(r"E:\n0r53\analysis\history_table.csv")

# collapse histories only: t_star defined
g = df[df.t_star.notna() & df.t95.notna() & (df.t95 > 0)].copy()
g["erosion_at_star"] = g.W_star / g.W_t95
g["coda_frac"] = (g.t_star - g.t95) / g.t95

out = {}
for mdl, gg in g.groupby("model"):
    rec = gg.groupby("rid").agg(t95=("t95", "median"),
                                er=("erosion_at_star", "median"),
                                cf=("coda_frac", "median"),
                                n=("rid", "size"))
    rec = rec[rec.er.notna() & rec.cf.notna()]
    if len(rec) < 10:
        continue
    r1 = spearmanr(rec.t95, rec.er)
    r2 = spearmanr(rec.t95, rec.cf)
    dl = gg.groupby("rid").agg(t95=("t95", "median"),
                               delay=("t_star", lambda s: float("nan"))).copy()
    dl["delay"] = gg.groupby("rid").apply(
        lambda x: (x.t_star - x.t95).median(), include_groups=False)
    dl = dl.dropna()
    r3 = spearmanr(dl.t95, dl.delay)
    out[mdl] = {"n_records": int(len(rec)),
                "t95_med": float(rec.t95.median()),
                "rho_t95_erosion": float(r1.statistic), "p1": float(r1.pvalue),
                "rho_t95_codafrac": float(r2.statistic), "p2": float(r2.pvalue),
                "rho_t95_delay_abs": float(r3.statistic), "p3": float(r3.pvalue),
                "delay_med": float(dl.delay.median())}
    print(mdl, "n=", len(rec), "rho_er=%.2f(p=%.3f)" % (r1.statistic, r1.pvalue),
          "rho_cf=%.2f(p=%.3f)" % (r2.statistic, r2.pvalue),
          "rho_delay=%.2f(p=%.3f) med=%.1fs" % (r3.statistic, r3.pvalue, dl.delay.median()), flush=True)

open(OUT, "w").write(json.dumps(out, indent=1))
print("wrote", OUT)
