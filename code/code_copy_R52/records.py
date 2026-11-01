"""FEMA P695 far-field and near-field record sets with verified time steps.

Far field: the 44 horizontal components of the ATC-63/FEMA P695 far-field set
read from the original PEER-NGA ``.AT2`` files (NPTS and DT taken from each
file header and cross-checked against the ATC-63 summary manifest).

Near field: the 56 components of the FEMA P695 near-field set (28 records,
fault-normal/fault-parallel pairs) stored as single-column files in g; the
time step of every component is taken from the accompanying parameter
workbook and the point count is checked against it.

All accelerations are returned in units of g.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PAPERS = Path(os.environ.get(
    "N0R52_PAPERS_ROOT",
    r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation",
))
FF_ROOT = PAPERS / "2026-3Journal-R2-BaselineFirst" / "data" / "fema_p695_farfield"
FF_AT2 = FF_ROOT / "accel_unscaled_peer" / "ATC-63_Far-Field_GroundMotionAccelTextFiles_Unscaled_Original"
NF_ROOT = (
    PAPERS / "ai_civil_slate_codex_goal_gate" / "rounds"
    / "R51_N0_JCSR_CODE_DESIGNED_REBUILD_2026-10-09" / "data" / "fema_p695_nearfield"
)
CACHE = Path(os.environ.get(
    "N0R52_GM_CACHE", "/mnt/e/n0r52/gm/records.npz" if os.name == "posix" else r"E:\n0r52\gm\records.npz"))


@dataclass
class Record:
    rid: str          # short identifier used in result tables
    rset: str         # 'FF' or 'NF'
    rsn: int
    event: str
    station: str
    component: str
    dt: float
    acc: np.ndarray   # g
    source: str
    sha256: str

    @property
    def duration(self) -> float:
        return self.dt * (len(self.acc) - 1)

    @property
    def pga(self) -> float:
        return float(np.max(np.abs(self.acc)))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_at2(path: Path) -> tuple[float, np.ndarray]:
    lines = path.read_text(encoding="latin-1").splitlines()
    head = lines[3]
    m_n = re.search(r"NPTS\s*=\s*(\d+)", head, flags=re.I)
    m_dt = re.search(r"DT\s*=\s*([0-9.Ee+-]+)", head, flags=re.I)
    m_old = re.match(r"\s*(\d+)\s+([0-9.Ee+-]+)\s+NPTS,\s*DT", head, flags=re.I)
    if m_n and m_dt:
        npts, dt = int(m_n.group(1)), float(m_dt.group(1))
    elif m_old:  # older PEER layout: "2999    0.0100    NPTS, DT"
        npts, dt = int(m_old.group(1)), float(m_old.group(2))
    else:
        raise ValueError(f"unexpected AT2 header in {path}: {head!r}")
    vals = np.array([float(v) for ln in lines[4:] for v in ln.split()], dtype=float)
    if len(vals) < npts:
        raise ValueError(f"{path}: {len(vals)} values < NPTS {npts}")
    return dt, vals[:npts]


def far_field() -> list[Record]:
    rows = list(csv.DictReader((FF_ROOT / "manifest.csv").open(encoding="utf-8")))
    out = []
    for r in rows:
        path = FF_AT2 / (r["peer_file"].replace("/", "\\") + ".AT2")
        dt, acc = read_at2(path)
        if abs(dt - float(r["dt_s"])) > 1e-9 or len(acc) != int(r["npts"]):
            raise ValueError(f"manifest mismatch for {path}")
        if abs(np.max(np.abs(acc)) - float(r["pga_g"])) > 1e-4:
            raise ValueError(f"PGA mismatch for {path}")
        out.append(Record(
            rid=f"FF{r['record_id']}", rset="FF", rsn=int(r["peer_rsn"]), event=r["earthquake"],
            station=r["station"], component=r["peer_file"].split("/")[-1], dt=dt, acc=acc,
            source=str(path), sha256=_sha(path),
        ))
    return out


def near_field() -> list[Record]:
    import pandas as pd

    meta = pd.read_excel(next(NF_ROOT.glob("*.xlsx")), header=None).iloc[1:, 1:7]
    meta.columns = ["rsn", "event", "station", "npts", "dt", "pga"]
    files = sorted(NF_ROOT.glob("RSN*.txt"))
    out = []
    for f in files:
        m = re.match(r"RSN(\d+)_([A-Z]+)_(.+)_(\d{3})$", f.stem)
        if not m:
            raise ValueError(f"unexpected near-field file name {f.name}")
        rsn, event, sta, ang = int(m.group(1)), m.group(2), m.group(3), m.group(4)
        cand = meta[meta.rsn.astype(int) == rsn]
        if cand.empty:
            raise ValueError(f"no metadata for RSN {rsn}")
        dt = float(cand.dt.iloc[0])
        npts = int(cand.npts.iloc[0])
        acc = np.loadtxt(f, dtype=float).ravel()
        if abs(len(acc) - npts) > 1:
            raise ValueError(f"{f.name}: {len(acc)} points vs metadata {npts}")
        out.append(Record(
            rid=f"NF{rsn}_{ang}", rset="NF", rsn=rsn, event=event, station=sta, component=ang,
            dt=dt, acc=acc, source=str(f), sha256=_sha(f),
        ))
    return out


def build_cache() -> None:
    recs = far_field() + near_field()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    meta = []
    for r in recs:
        payload[r.rid] = r.acc
        meta.append([r.rid, r.rset, r.rsn, r.event, r.station, r.component, r.dt, r.source, r.sha256])
    np.savez_compressed(CACHE, **payload, __meta__=np.array(meta, dtype=object))


def load_all() -> dict[str, Record]:
    if not CACHE.exists():
        build_cache()
    z = np.load(CACHE, allow_pickle=True)
    out = {}
    for rid, rset, rsn, event, station, comp, dt, src, sha in z["__meta__"]:
        out[rid] = Record(rid=rid, rset=rset, rsn=int(rsn), event=event, station=station,
                          component=comp, dt=float(dt), acc=z[rid], source=src, sha256=sha)
    return out


# --------------------------------------------------------------------------
# Intensity measures
# --------------------------------------------------------------------------
def sa_spectrum(acc_g: np.ndarray, dt: float, periods, zeta: float = 0.05) -> np.ndarray:
    """Pseudo-spectral acceleration (g) by the exact piecewise-linear recurrence
    (Nigam & Jennings 1969) for a linear SDOF oscillator."""
    periods = np.atleast_1d(np.asarray(periods, dtype=float))
    out = np.zeros_like(periods)
    ag = np.asarray(acc_g, dtype=float)
    for k, T in enumerate(periods):
        w = 2.0 * np.pi / T
        wd = w * np.sqrt(1.0 - zeta**2)
        e = np.exp(-zeta * w * dt)
        s, c = np.sin(wd * dt), np.cos(wd * dt)
        a11 = e * (zeta / np.sqrt(1 - zeta**2) * s + c)
        a12 = e / wd * s
        a21 = -w / np.sqrt(1 - zeta**2) * e * s
        a22 = e * (c - zeta / np.sqrt(1 - zeta**2) * s)
        t1 = (2 * zeta**2 - 1) / (w**2 * dt)
        t2 = 2 * zeta / (w**3 * dt)
        b11 = e * ((t1 + zeta / w) * s / wd + (t2 + 1 / w**2) * c) - t2
        b12 = -e * (t1 * s / wd + t2 * c) - 1 / w**2 + t2
        b21 = e * ((t1 + zeta / w) * (c - zeta / np.sqrt(1 - zeta**2) * s)
                   - (t2 + 1 / w**2) * (wd * s + zeta * w * c)) + 1 / (w**2 * dt)
        b22 = -e * (t1 * (c - zeta / np.sqrt(1 - zeta**2) * s) - t2 * (wd * s + zeta * w * c)) - 1 / (w**2 * dt)
        u = v = 0.0
        umax = 0.0
        for i in range(len(ag) - 1):
            p0, p1 = -ag[i], -ag[i + 1]
            u, v = a11 * u + a12 * v + b11 * p0 + b12 * p1, a21 * u + a22 * v + b21 * p0 + b22 * p1
            if abs(u) > umax:
                umax = abs(u)
        out[k] = umax * w**2
    return out


def arias_times(acc_g: np.ndarray, dt: float, lo: float = 0.05, hi: float = 0.95) -> tuple[float, float, float]:
    """Return (t_lo, t_hi, Ia) of the normalized Arias-intensity build-up (Husid plot)."""
    a = np.asarray(acc_g, dtype=float) * 9.80665
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (a[1:] ** 2 + a[:-1] ** 2) * dt)])
    ia = cum[-1] * np.pi / (2 * 9.80665)
    f = cum / cum[-1]
    t = np.arange(len(a)) * dt
    return float(np.interp(lo, f, t)), float(np.interp(hi, f, t)), float(ia)


if __name__ == "__main__":
    import json

    build_cache()
    recs = load_all()
    ff = [r for r in recs.values() if r.rset == "FF"]
    nf = [r for r in recs.values() if r.rset == "NF"]
    print(json.dumps({"FF": len(ff), "NF": len(nf),
                      "dt_FF": sorted({r.dt for r in ff}), "dt_NF": sorted({r.dt for r in nf})}))
