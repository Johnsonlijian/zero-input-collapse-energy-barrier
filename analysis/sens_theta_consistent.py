"""Consistent theta_c redefinition test on drift-limited frames (4CG, 8CG).

For each transition state (ta, tstar) the barrier W_rem(theta') is re-cut from the
stored mode-1 push curve at theta' in {0.10, 0.15, 0.20}: work to the earlier of
(a) the resistance edge (lam returns to <= 0 after being positive) and (b) the first
crossing of the peak storey drift through theta' (interpolated), with the harness
rule (build_tables.w_collapse).  Curves come from RUNS/push_deep (max_droof = 0.16,
coincident with RUNS/push over the common range) where available, else RUNS/push
(max_droof = 0.08); a curve that reaches neither exit is 'trunc' (lower bound on W,
upper bound on c).  beta_crit is measured under the SAME drift limit
(kick_theta010 / kick / kick_theta020) and c(theta') = beta_crit^2 KE / W_rem(theta').

If the balance is physical rather than definitional, c(theta') stays near the
theta_c = 0.15 value when both quantities move to the new surface.
Writes analysis/sens_theta_consistent.json (rows + summary with event-cluster CIs).
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from build_tables import w_collapse

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(r"E:\n0r53\analysis\sens_theta_consistent.json")
MODELS = ["SMF4CG", "SMF8CG"]
THETAS = [0.10, 0.15, 0.20]
KICK_PHASE = {0.10: "kick_theta010", 0.15: "kick", 0.20: "kick_theta020"}
N_BOOT = 10000


def event_id(rid):
    return rid.split("_")[0] if rid.startswith("NF") else rid[:-1]


def jl(p):
    return json.loads(p.read_text()) if p.exists() else None


def med_ci(rows, key, rng):
    g = defaultdict(list)
    for r in rows:
        if r.get(key) is not None and np.isfinite(r[key]):
            g[r["event"]].append(r[key])
    keys = sorted(g)
    if len(keys) < 2:
        return None
    allv = np.concatenate([g[k] for k in keys])
    meds = [np.median(np.concatenate([g[keys[i]] for i in rng.integers(0, len(keys), len(keys))]))
            for _ in range(N_BOOT)]
    return {"n": int(len(allv)), "n_events": len(keys), "median": float(np.median(allv)),
            "ci95": [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))],
            "p10": float(np.percentile(allv, 10)), "p90": float(np.percentile(allv, 90))}


def main():
    rng = np.random.default_rng(2020)
    out = {}
    for model in MODELS:
        rows = []
        for p in sorted((RUNS / "push" / model).glob("*.json")):
            pm = jl(p)
            st = pm.get("state", {})
            if st.get("tag") not in ("ta", "tstar"):
                continue
            pdp = jl(RUNS / "push_deep" / model / p.name)
            src, d = ("push_deep", pdp) if pdp and pdp.get("curve") else ("push", pm)
            if not d.get("curve"):
                continue
            ke = pm.get("ke_reproduced") or (st.get("snapshot") or {}).get("ke")
            if not ke or ke <= 0:
                continue
            c = np.asarray(d["curve"], float)
            row = {"rid": st["rid"], "event": event_id(st["rid"]), "t_r": st["t_r"], "tag": st["tag"],
                   "ke": ke, "curve_src": src, "sdr_max_curve": float(np.max(c[:, 2]))}
            for th in THETAS:
                w, kind = w_collapse(d, drift_limit=th)
                kj = jl(RUNS / KICK_PHASE[th] / model / p.name)
                bc = None if kj is None else kj.get("beta_crit")
                row[f"w_{th:.2f}"], row[f"exit_{th:.2f}"], row[f"bc_{th:.2f}"] = w, kind, bc
                row[f"c_{th:.2f}"] = bc * bc * ke / w if (w and w > 0 and bc is not None) else None
            for th in (0.10, 0.20):
                a, b = row.get(f"c_{th:.2f}"), row.get("c_0.15")
                row[f"r_{th:.2f}"] = a / b if (a is not None and b) else None
            rows.append(row)
        summ = {"n_states": len(rows), "curve_src": dict(Counter(r["curve_src"] for r in rows))}
        for th in THETAS:
            t = f"{th:.2f}"
            summ[t] = {"exit": dict(Counter(r[f"exit_{t}"] for r in rows)),
                       "beta_crit_zero": int(sum(1 for r in rows if r[f"bc_{t}"] == 0.0)),
                       "c_all": med_ci(rows, f"c_{t}", rng),
                       "c_resolved": med_ci([r for r in rows if r[f"exit_{t}"] in ("drift", "edge", "stall")], f"c_{t}", rng)}
            if th != 0.15:
                summ[t]["paired_ratio_to_015"] = med_ci(rows, f"r_{t}", rng)
                summ[t]["paired_ratio_resolved"] = med_ci(
                    [r for r in rows if r[f"exit_{t}"] in ("drift", "edge", "stall") and r["exit_0.15"] in ("drift", "edge", "stall")],
                    f"r_{t}", rng)
            if th == 0.20:
                for lab, ok in (("all", lambda r: True),
                                ("resolved", lambda r: r["exit_0.20"] in ("drift", "edge", "stall")
                                 and r["exit_0.15"] in ("drift", "edge", "stall"))):
                    S = [r for r in rows if r.get("w_0.20") and r.get("w_0.15") and r["bc_0.15"]
                         and r["bc_0.20"] and ok(r)]
                    if len(S) > 2:
                        w = np.array([r["w_0.20"] / r["w_0.15"] for r in S])
                        e = np.array([(r["bc_0.20"] / r["bc_0.15"]) ** 2 for r in S])
                        summ[t][f"lockstep_{lab}"] = {
                            "n": len(S), "W_ratio_median": float(np.median(w)),
                            "W_ratio_p10": float(np.percentile(w, 10)), "W_ratio_p90": float(np.percentile(w, 90)),
                            "E_ratio_median": float(np.median(e)),
                            "corr_logW_logE": float(np.corrcoef(np.log(w), np.log(e))[0, 1])}
            print(model, t, json.dumps(summ[t]), flush=True)
        out[model] = {"summary": summ, "rows": rows}
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
