"""Energy decomposition of the critical escape (A7, kick_energy v2).

For every transition state with a damped kick bracket (beta_lo recoverable, beta_hi
committed) the two continuations were re-run with in-run accounting (addenda53):
  W_int(t)       static internal work = int (R0 - aM m v) . du   (strain, hysteresis, gravity)
  W_visc_diff(t) total viscous (Rayleigh) work = KE0 - KE(t) - W_int(t)
On the committed run the saddle passage is the global kinetic-energy minimum before
collapse (t_x).  Energy balance there: KE0 = KE(t_x) + W_int(t_x) + W_visc(t_x).
The recoverable run's stopping point (first KE < 0.5 % KE0 after its main excursion)
is reported as a check.  Normalised by the collapse-surface barrier W_rem of the same
state (harness rule) and compared with c = E_crit / W_rem and c0 = E0_crit / W_rem.

Writes analysis/kick_energy_analysis.json.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from build_tables import w_collapse, event_id

RUNS = Path(r"E:\n0r53\runs")
OUT = Path(__file__).resolve().parent / "kick_energy_analysis.json"
MODELS = ["SMF2B", "SMF2CG", "SMF4B", "SMF4CG", "SMF8B", "SMF8CG",
          "SMF12B", "SMF12CG", "SMF20B", "SMF20CG"]
N_BOOT = 10000


def jl(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def series(run):
    s = run["series"]
    return {k: np.array([x[k] for x in s]) for k in ("t", "KE", "W_int", "W_visc_diff")}


def state_row(model: str, p: Path):
    d = jl(p)
    if d.get("status") != "ok" or len(d.get("runs", {})) < 2:
        return None
    runs = sorted(d["runs"].values(), key=lambda r: r["beta"])
    rec, com = runs[0], runs[-1]
    if rec["label"] != "recoverable" or com["label"] != "committed":
        return None
    pm = jl(RUNS / "push" / model / p.name)
    kd = jl(RUNS / "kick" / model / p.name)
    ku = jl(RUNS / "kick_undamped" / model / p.name)
    if pm is None or kd is None or kd.get("beta_crit") is None:
        return None
    W, lim = w_collapse(pm)
    if not W or W <= 0:
        return None
    ke1 = com["KE0_paper"] / com["beta"] ** 2                 # KE at beta = 1
    E = kd["beta_crit"] ** 2 * ke1
    E0 = None if (ku is None or ku.get("beta_crit") is None) else ku["beta_crit"] ** 2 * ke1
    sc = series(com)
    t_coll = com.get("t_coll") or sc["t"][-1]
    m = sc["t"] < t_coll - 1e-9
    if m.sum() < 3:
        return None
    ix = int(np.argmin(np.where(m, sc["KE"], np.inf)))
    sr = series(rec)
    ke0r = rec["KE0"]
    after = np.where((sr["t"] > sr["t"][0] + 0.1) & (sr["KE"] < 0.005 * ke0r))[0]
    ir = int(after[0]) if len(after) else None
    st = d["state"]
    return {"model": model, "rid": st["rid"], "event": event_id(st["rid"]), "tag": st["tag"],
            "W_rem": W, "lim": lim, "E_crit": E, "E0_crit": E0, "KE0_hi": com["KE0"],
            "t_x_minus_tr": float(sc["t"][ix] - sc["t"][0]),
            "a_int": sc["W_int"][ix] / W, "b_visc": sc["W_visc_diff"][ix] / W, "k_ke": sc["KE"][ix] / W,
            "c": E / W, "c0": None if E0 is None else E0 / W,
            "a_int_rec": None if ir is None else sr["W_int"][ir] / W,
            "b_visc_rec": None if ir is None else sr["W_visc_diff"][ir] / W}


def med_ci(rows, key, rng):
    g = defaultdict(list)
    for r in rows:
        v = r.get(key)
        if v is not None and np.isfinite(v):
            g[r["event"]].append(v)
    keys = sorted(g)
    if len(keys) < 2:
        return None
    allv = np.concatenate([g[k] for k in keys])
    meds = [np.median(np.concatenate([g[keys[i]] for i in rng.integers(0, len(keys), len(keys))]))
            for _ in range(N_BOOT)]
    return {"n": int(len(allv)), "median": float(np.median(allv)),
            "ci95": [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))],
            "p10": float(np.percentile(allv, 10)), "p90": float(np.percentile(allv, 90))}


def main():
    rng = np.random.default_rng(7)
    out = {}
    for model in MODELS:
        d = RUNS / "kick_energy" / model
        if not d.exists():
            continue
        rows = [r for r in (state_row(model, p) for p in sorted(d.glob("*.json"))) if r]
        if not rows:
            continue
        for r in rows:
            r["toll_measured"] = r["b_visc"]
            r["toll_inferred"] = None if r["c0"] is None else r["c"] - r["c0"]
            r["a_minus_c0"] = None if r["c0"] is None else r["a_int"] - r["c0"]
        s = {k: med_ci(rows, k, rng) for k in ("c", "c0", "a_int", "b_visc", "k_ke", "a_int_rec",
                                                 "b_visc_rec", "toll_inferred", "a_minus_c0", "t_x_minus_tr")}
        pr = [r for r in rows if r["toll_inferred"] is not None]
        if len(pr) > 2:
            x, y = np.array([r["toll_inferred"] for r in pr]), np.array([r["toll_measured"] for r in pr])
            s["toll_corr"] = float(np.corrcoef(x, y)[0, 1])
        out[model] = {"summary": s, "rows": rows}
        print(model, {k: (None if v is None or not isinstance(v, dict) else round(v["median"], 3))
                      for k, v in s.items()}, "corr", s.get("toll_corr"), flush=True)
    out["_protocol"] = {"source": "RUNS/kick_energy (addenda53 v2, R53v1.0+A7)", "unit": "event_id",
                        "t_x": "global KE minimum before collapse on the committed (beta_hi) run",
                        "W_rem": "build_tables.w_collapse on RUNS/push (mode 1)"}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
