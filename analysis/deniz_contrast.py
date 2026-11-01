"""Addendum A18: numeric contrast against a cumulative input-energy index
(Deniz, Song & Hajjar 2017, Eng. Struct. 141:1-13).

Deniz-style criterion: the structure collapses once the cumulative energy
input from the ground motion reaches the energy capacity of the frame; the
capacity is estimated from the monotonic pushover.  For every released state
in law_table.csv we evaluate the input energy actually delivered to the
structure up to the release instant,

    E_I(t_r) = -int_0^{t_r}  ug''(t) * sum_i m_i * u'_i(t)  dt

with floor velocities u'_i reconstructed from the stored per-storey SDR
histories (u_i = cumsum(SDR_k * h_k)) and ug'' the applied (scaled) record,
normalised by the intact pushover work W_b measured in the same push
direction -- the energy-capacity proxy used by the criterion.

The released labels (committed / recoverable under zero input) are compared
against (i) the literal criterion eta = E_I/W_b >= 1, (ii) the best-threshold
(oracle) accuracy of eta per frame, and (iii) Spearman rho(eta, committed).
The decisive contrast is on (t_a, t*) pairs: same record, ~0.01-0.02 s apart,
opposite labels -- any purely record-driven running index gives Delta eta ~ 0
there and cannot locate the point of no return.

Reads:  analysis/law_table.csv, runs/zic/<model>/<rid>__<level>.json,
        models/command_logs/<model>.json (via code_copy/opsmodel replay for
        exact floor masses), E:/n0r52/gm/records.npz, analysis/summary_by_frame.json
Writes: analysis/deniz_contrast.json
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"E:\n0r53")
sys.path.insert(0, str(ROOT / "code_copy"))
from opsmodel import replay  # noqa: E402
from records import sa_spectrum  # noqa: E402
import openseespy.opensees as ops  # noqa: E402

G_IN_S2 = 386.1
RUNS = ROOT / "runs" / "zic"
NPZ = Path(r"E:\n0r52\gm\records.npz")
LAW = ROOT / "analysis" / "law_table.csv"
SUM = ROOT / "analysis" / "summary_by_frame.json"
OUT = ROOT / "analysis" / "deniz_contrast.json"

_geom: dict = {}
_recs: dict = {}
_recdt: dict = {}


def geometry(model):
    """(story heights, floor masses, T1) from a one-time OpenSees replay."""
    if model not in _geom:
        info = replay(model)
        h = np.array(info.story_heights, float)
        elev = np.cumsum(h)
        fm = np.zeros(len(info.mf_floor_nodes))
        for nd in ops.getNodeTags():
            m = ops.nodeMass(nd, 1)
            if m > 1.0e-6:
                y = ops.nodeCoord(nd, 2)
                k = int(np.argmin(np.abs(elev - y)))
                if abs(elev[k] - y) > 30.0:
                    raise RuntimeError(f"{model}: mass node {nd} at y={y}")
                fm[k] += m
        _geom[model] = (h, fm, float(info.periods[0]))
    return _geom[model]


def load_records():
    z = np.load(NPZ, allow_pickle=True)
    for rid, rset, rsn, ev, sta, comp, dt, src, sha in z["__meta__"]:
        _recs[rid] = z[rid]
        _recdt[rid] = float(dt)


def applied_accel(rid, sa_target, T1):
    """Applied ground acceleration history in in/s^2 (record in g, scaled so
    its 5%-damped Sa(T1) equals sa_target, times g)."""
    acc = np.asarray(_recs[rid], float)
    dt = _recdt[rid]
    sa0 = float(sa_spectrum(acc, dt, [T1])[0])
    return acc * (sa_target / sa0) * G_IN_S2, dt


def input_energy(j, model, sa_target, h, fm):
    """Cumulative input energy E_I(t) (kip-in) sampled on hist.t."""
    t = np.asarray(j["hist"]["t"], float)
    d = np.asarray(j["hist"]["d"], float)          # (nt, n_story) SDR
    if d.ndim != 2 or d.shape[0] != len(t):
        return None, None
    u = np.cumsum(d * h[None, :], axis=1)           # (nt, n_floor) disp, in
    dt_hist = np.gradient(t)
    v = np.gradient(u, axis=0) / dt_hist[:, None]   # floor vel, in/s
    _, _, T1 = geometry(model)
    ag, dt_g = applied_accel(j["rid"], sa_target, T1)
    ag_h = np.interp(t, np.arange(len(ag)) * dt_g, ag)  # in/s^2
    power = -ag_h * (v @ fm)                        # kip-in/s
    return t, np.cumsum(power * dt_hist)


def main():
    load_records()
    rows = list(csv.DictReader(LAW.open(encoding="utf-8")))
    summary = json.loads(SUM.read_text())

    # group rows by run file
    by_run: dict = {}
    for r in rows:
        lab = r["label_r52"]
        if lab not in ("committed", "recoverable"):
            continue
        try:
            t_r = float(r["t_r"]); Wb = float(r["Wb"]); sa = float(r["sa"]) if r.get("sa") else None
        except (TypeError, ValueError):
            continue
        by_run.setdefault((r["model"], r["rid"], r["level"]), []).append(
            {"t_r": t_r, "label": lab, "Wb": Wb, "tag": r["tag"], "sa": sa})

    out = {}
    t0 = None
    n_files = n_rows = 0
    for (model, rid, level), states in sorted(by_run.items()):
        fp = RUNS / model / f"{rid}__{level}.json"
        if not fp.exists():
            continue
        j = json.loads(fp.read_text())
        sa = j.get("sa")
        if sa is None:
            continue
        h, fm, T1 = geometry(model)
        t, EI = input_energy(j, model, sa, h, fm)
        if EI is None:
            continue
        EI_end = float(EI[-1])
        block = out.setdefault(model, {"rows": [], "acc_energy_cdev":
                                       (summary.get(f"{model}|ALL") or {}).get("acc_energy_cdev"),
                                       "acc_drift_dev_thr":
                                       (summary.get(f"{model}|ALL") or {}).get("acc_drift_dev_thr")})
        for s in states:
            eta = float(np.interp(s["t_r"], t, EI) / s["Wb"]) if s["Wb"] > 0 else None
            block["rows"].append({"rid": rid, "level": level, "tag": s["tag"],
                                  "t_r": s["t_r"], "label": s["label"],
                                  "eta": eta, "EI_frac": float(np.interp(s["t_r"], t, EI)) / EI_end if EI_end else None})
        n_files += 1; n_rows += len(states)

    def spearman(x, y):
        from scipy.stats import rankdata
        rx, ry = rankdata(x), rankdata(y)
        if np.std(rx) < 1e-12 or np.std(ry) < 1e-12:
            return None
        return float(np.corrcoef(rx, ry)[0, 1])

    def best_acc(eta, lab):
        cands = np.unique(eta)
        best = max(float(np.mean((eta >= c) == lab)) for c in cands)
        return best

    report = {}
    for m, blk in out.items():
        rows = [r for r in blk["rows"] if r["eta"] is not None]
        eta = np.array([r["eta"] for r in rows])
        lab = np.array([r["label"] == "committed" for r in rows])
        # paired t_a/t* contrast per (rid,level)
        pairs = {}
        for r in rows:
            if r["tag"] in ("ta", "tstar"):
                pairs.setdefault((r["rid"], r["level"]), {})[r["tag"]] = r["eta"]
        dpairs = [abs(p["tstar"] - p["ta"]) for p in pairs.values() if "ta" in p and "tstar" in p]
        order_ok = [p["tstar"] > p["ta"] for p in pairs.values() if "ta" in p and "tstar" in p]
        eif = [r["EI_frac"] for r in rows if r["tag"] == "tstar" and r["EI_frac"] is not None]
        report[m] = {
            "n": len(rows), "n_committed": int(lab.sum()),
            "rho_eta_committed": spearman(eta, lab.astype(float)),
            "acc_literal_eta_ge_1": float(np.mean((eta >= 1.0) == lab)),
            "acc_oracle_eta": best_acc(eta, lab),
            "acc_energy_cdev": blk["acc_energy_cdev"],
            "acc_drift_dev_thr": blk["acc_drift_dev_thr"],
            "n_pairs": len(dpairs),
            "pair_deta_med": float(np.median(dpairs)) if dpairs else None,
            "pair_deta_max": float(np.max(dpairs)) if dpairs else None,
            "pair_order_correct_share": float(np.mean(order_ok)) if order_ok else None,
            "EI_frac_at_tstar_med": float(np.median(eif)) if eif else None,
        }
    report["_protocol"] = {
        "aggregate_stamp": None,
        "generator": "deniz_contrast.py",
        "declared_inputs": ["analysis/law_table.csv", "runs/zic", "models/command_logs",
                            "E:/n0r52/gm/records.npz", "analysis/summary_by_frame.json"],
        "note": "A18: Deniz-style cumulative input-energy index vs released-state labels",
        "files": n_files, "rows": n_rows,
    }
    OUT.write_text(json.dumps(report, indent=1))
    for m in sorted(report):
        if m.startswith("_"):
            continue
        r = report[m]
        print(m, "n=", r["n"], "rho=", r["rho_eta_committed"],
              "acc_lit=", round(r["acc_literal_eta_ge_1"], 3),
              "acc_oracle=", round(r["acc_oracle_eta"], 3),
              "acc_E=", None if r["acc_energy_cdev"] is None else round(r["acc_energy_cdev"], 3),
              "deta_med=", r["pair_deta_med"], "EIfrac*=", r["EI_frac_at_tstar_med"])
    print("files", n_files, "rows", n_rows)


if __name__ == "__main__":
    main()
