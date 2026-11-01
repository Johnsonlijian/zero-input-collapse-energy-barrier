"""Horizon-expired 'recoverable' audit (A16, analysis of existing runs only).

A continuation is labeled 'recoverable' by _label() whenever status=='ok',
i.e. also when the 30-s horizon expired without the settle test firing
(settled_at is null).  This audit counts those horizon-expired recoverable
labels per run family and, critically, joins them to law_table.csv to
establish how many classified/transition states carry the undecided label,
and how many bisection probes inside brackets were horizon-expired.
"""
import json, csv, os, glob
from collections import defaultdict

ROOT = r"E:\n0r53"
LAW = os.path.join(ROOT, "analysis", "law_table.csv")
OUT = os.path.join(ROOT, "analysis", "horizon_audit.json")


def scan_family(pattern, nested):
    """Return per-model counts of recoverable labels split by settled_at."""
    agg = defaultdict(lambda: dict(rec_settled=0, rec_horizon=0, committed=0, censored=0,
                                   files=0, horizon_states=[]))
    for f in glob.glob(pattern, recursive=True):
        model = f.replace("\\", "/").split("/runs/")[1].split("/")[1]
        try:
            j = json.load(open(f))
        except Exception:
            continue
        if nested == "zic":
            rels = list((j.get("releases") or {}).values())
        elif nested == "kick":
            rels = list((j.get("runs") or {}).values())
        else:
            rels = [j]
        a = agg[model]
        a["files"] += 1
        for r in rels:
            if not isinstance(r, dict):
                continue
            lab = r.get("label")
            if lab is None:
                # nested release dicts carry committed flag rather than label
                if r.get("committed") is True:
                    lab = "committed"
                elif r.get("committed") is False:
                    lab = "recoverable" if r.get("status") == "ok" else "censored"
            if lab == "committed":
                a["committed"] += 1
            elif lab == "recoverable":
                if r.get("settled_at") is None:
                    a["rec_horizon"] += 1
                    if r.get("t_r") is not None:
                        a["horizon_states"].append(
                            dict(rid=j.get("rid") or os.path.basename(f).split("__")[0],
                                 level=j.get("level") or "", t_r=r["t_r"]))
                else:
                    a["rec_settled"] += 1
            else:
                a["censored"] += 1
    return agg


def main():
    out = {}
    out["zic"] = scan_family(os.path.join(ROOT, "runs", "zic", "*", "*.json"), nested="zic")
    for fam in ("kick", "kick_undamped"):
        out[fam] = scan_family(os.path.join(ROOT, "runs", fam, "*", "*.json"),
                               nested="kick")
    # serialise
    ser = {}
    for fam, agg in out.items():
        ser[fam] = {m: {k: (v[k] if k != "horizon_states" else v[k][:50]) for k in v}
                    for m, v in agg.items()}
        for m in ser[fam]:
            ser[fam][m]["horizon_n_listed"] = len(agg[m]["horizon_states"])
    # join to law_table: how many law rows come from horizon-expired releases
    hz = set()
    for fam, agg in out.items():
        for m, v in agg.items():
            for h in v["horizon_states"]:
                hz.add((m, h["rid"], round(float(h["t_r"]), 4)))
    rows = list(csv.DictReader(open(LAW, newline="", encoding="utf-8-sig")))
    hits = [r for r in rows
            if (r["model"], r["rid"], round(float(r["t_r"]), 4)) in hz]
    ser["law_hits"] = dict(n=len(hits),
                           by_model={m: sum(1 for r in hits if r["model"] == m)
                                     for m in sorted({r["model"] for r in hits})},
                           by_role={})
    json.dump(ser, open(OUT, "w"), indent=1)
    print("wrote", OUT)
    for fam in ser:
        if fam == "law_hits":
            continue
        print(fam, {m: (v["rec_horizon"], v["rec_settled"], v["committed"])
                    for m, v in ser[fam].items()})
    print("law_hits:", ser["law_hits"]["n"], ser["law_hits"]["by_model"])


if __name__ == "__main__":
    main()
