"""Barrier path dependence: mode-1 vs storey-mechanism vs collapse-shape pushes.

For every transition state (tags ta, tstar) with an undamped escape energy E_u
(kick_undamped beta_crit^2 * KE), compute the collapse-surface barrier W_c with the
harness rule (build_tables.w_collapse: earlier of resistance edge / theta_c = 0.15,
'trunc' if neither is reached) along each declared static path:

  m1    : first-mode pattern (main protocol)          RUNS/push
  story : mass-restricted, floors >= critical storey  RUNS/push_story
  shape : collapse-shape aligned pattern               RUNS/push_shape

A static path only bounds the mountain pass from above, so the best available
barrier estimate is W_min = min over the paths computed for that state.
Reported per frame: paired W ratios, c0 = E_u / W along each path and along W_min,
damped c = E_d / W_min, exit-type counts, event-cluster bootstrap 95 % CIs (10 000).
Writes analysis/pattern_compare.json.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from build_tables import w_collapse

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "pattern_compare.json"
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
N_BOOT = 10000


def event_id(rid: str) -> str:
    return rid.split("_")[0] if rid.startswith("NF") else rid[:-1]


def jl(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def ke_of(push: dict, kick: dict):
    ke = push.get("ke_reproduced") or (push.get("release_snapshot") or {}).get("ke")
    if ke is None and kick:
        ke = ((kick.get("state") or {}).get("snapshot") or {}).get("ke")
        for rr in (kick.get("runs") or {}).values():
            ke = ke or (rr.get("snapshot_release") or {}).get("ke")
    return ke


def wc(d):
    """Harness rule, no convergence filter (identical to Table 2 for m1)."""
    if d is None or d.get("reproduce_status") not in ("released", None):
        return None, None
    return w_collapse(d)


RESOLVED = ("drift", "edge", "stall", "downhill")


def rows_for(model: str) -> list[dict]:
    rows = []
    for p in sorted((RUNS / "push" / model).glob("*.json")):
        pm = jl(p)
        st = pm.get("state") or {}
        if st.get("tag") not in ("ta", "tstar"):
            continue
        stem = p.stem
        ku = jl(RUNS / "kick_undamped" / model / f"{stem}.json")
        kd = jl(RUNS / "kick" / model / f"{stem}.json")
        ke = ke_of(pm, kd or ku)
        if not ke:
            continue
        r = {"rid": st["rid"], "event": event_id(st["rid"]), "tag": st["tag"], "ke": ke}
        b0 = None if ku is None else ku.get("beta_crit")
        bd = None if kd is None else kd.get("beta_crit")
        r["E_u"] = None if b0 is None else b0 * b0 * ke
        r["E_d"] = None if bd is None else bd * bd * ke
        for name, d in (("m1", pm), ("m1deep", jl(RUNS / "push_deep" / model / f"{stem}.json")),
                        ("story", jl(RUNS / "push_story" / model / f"{stem}.json")),
                        ("shape", jl(RUNS / "push_shape" / model / f"{stem}__push_shape.json"))):
            w, lim = wc(d)
            r[f"W_{name}"], r[f"lim_{name}"] = w, lim
        rows.append(r)
    return rows


def med_ci(vals_by_event: dict, rng) -> tuple:
    keys = sorted(vals_by_event)
    if not keys:
        return None, [None, None], 0
    allv = np.concatenate([vals_by_event[k] for k in keys])
    meds = np.empty(N_BOOT)
    for b in range(N_BOOT):
        pick = rng.integers(0, len(keys), len(keys))
        meds[b] = np.median(np.concatenate([vals_by_event[keys[i]] for i in pick]))
    return float(np.median(allv)), [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))], len(allv)


def grouped(rows, f):
    g = defaultdict(list)
    for r in rows:
        v = f(r)
        if v is not None and np.isfinite(v):
            g[r["event"]].append(v)
    return {k: np.asarray(v) for k, v in g.items()}


def pos(x):
    return x is not None and x > 0


def main():
    rng = np.random.default_rng(31415)
    out = {}
    for model in MODELS:
        rows = rows_for(model)
        if not rows:
            continue
        s = {"n_states": len(rows)}
        for alt in ("story", "shape"):
            sub = [r for r in rows if pos(r["W_m1"]) and pos(r[f"W_{alt}"]) and r[f"lim_{alt}"] in RESOLVED]
            s[f"{alt}_n_available"] = sum(r[f"W_{alt}"] is not None for r in rows)
            s[f"{alt}_lim"] = dict(Counter(r[f"lim_{alt}"] for r in rows if r[f"lim_{alt}"] is not None))
            if not sub:
                continue
            rat = np.array([r[f"W_{alt}"] / r["W_m1"] for r in sub])
            m, ci, n = med_ci(grouped(sub, lambda r: r[f"W_{alt}"] / r["W_m1"]), rng)
            s[f"{alt}_W_ratio"] = {"n": n, "median": m, "ci95": ci,
                                   "p10": float(np.percentile(rat, 10)), "p90": float(np.percentile(rat, 90)),
                                   "frac_below_095": float(np.mean(rat < 0.95))}
            pu = [r for r in sub if pos(r["E_u"])]
            for lab, f in (("c0_m1", lambda r: r["E_u"] / r["W_m1"]),
                           (f"c0_{alt}", lambda r: r["E_u"] / r[f"W_{alt}"])):
                m, ci, n = med_ci(grouped(pu, f), rng)
                s[f"{alt}_paired_{lab}"] = {"n": n, "median": m, "ci95": ci}
        s["lim_m1"] = dict(Counter(r["lim_m1"] for r in rows if r["lim_m1"] is not None))

        def alt_ok(r, k):
            return pos(r[f"W_{k}"]) and r[f"lim_{k}"] in RESOLVED

        def paths(r):
            ws = {"m1": r["W_m1"]}
            ws.update({k: r[f"W_{k}"] for k in ("story", "shape") if alt_ok(r, k)})
            return ws

        def wmin(r):
            return min(paths(r).values())

        def which(r):
            ws = paths(r)
            return min(ws, key=ws.get)

        full = [r for r in rows if pos(r["W_m1"]) and pos(r["E_u"])]
        multi = [r for r in full if alt_ok(r, "story") or alt_ok(r, "shape")]
        for lab, sub, f in (("c0_m1_all", full, lambda r: r["E_u"] / r["W_m1"]),
                            ("c0_m1_multi", multi, lambda r: r["E_u"] / r["W_m1"]),
                            ("c0_min_multi", multi, lambda r: r["E_u"] / wmin(r)),
                            ("cd_min_multi", [r for r in multi if pos(r["E_d"])], lambda r: r["E_d"] / wmin(r)),
                            ("cd_m1_multi", [r for r in multi if pos(r["E_d"])], lambda r: r["E_d"] / r["W_m1"])):
            m, ci, n = med_ci(grouped(sub, f), rng)
            s[lab] = {"n": n, "median": m, "ci95": ci}
        s["min_path_counts"] = dict(Counter(which(r) for r in multi))
        # extended (0.16 roof drift) first-mode pushes, where available (A8): resolves 'trunc' exits
        deep = [r for r in full if r["W_m1deep"] is not None and r["lim_m1deep"] in RESOLVED and pos(r["W_m1deep"])]
        if deep:
            s["m1deep_lim"] = dict(Counter(r["lim_m1deep"] for r in full if r["lim_m1deep"] is not None))
            s["m1_lim_on_deep_subset"] = dict(Counter(r["lim_m1"] for r in deep))
            for lab, f in (("c0_m1_on_deep_subset", lambda r: r["E_u"] / r["W_m1"]),
                           ("c0_m1deep", lambda r: r["E_u"] / r["W_m1deep"])):
                m, ci, n = med_ci(grouped(deep, f), rng)
                s[lab] = {"n": n, "median": m, "ci95": ci}

            def wmin_deep(r):
                ws = [r["W_m1deep"]] + [r[f"W_{k}"] for k in ("story", "shape") if alt_ok(r, k)]
                return min(ws)
            m, ci, n = med_ci(grouped(deep, lambda r: r["E_u"] / wmin_deep(r)), rng)
            s["c0_min_deep"] = {"n": n, "median": m, "ci95": ci}
        out[model] = s
        print(model, "c0_m1_all", s["c0_m1_all"], "| multi", s["c0_m1_multi"], "-> min", s["c0_min_multi"],
              "| min path", s["min_path_counts"], flush=True)
        for alt in ("story", "shape"):
            if f"{alt}_W_ratio" in s:
                print(f"   {alt}: W ratio {s[f'{alt}_W_ratio']}  lim {s[f'{alt}_lim']}", flush=True)
    out["_protocol"] = {"barrier_rule": "build_tables.w_collapse (theta_c=0.15, earlier exit)",
                        "unit": "event_id", "n_boot": N_BOOT, "tags": ["ta", "tstar"],
                        "W_min": "min of W_m1 (harness rule, as Table 2) and alternative-path W with a "
                                 "resolved exit (drift/edge); truncated/nonconvergent alt curves excluded"}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
