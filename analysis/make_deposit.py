"""Assemble the R53 study package (local only; nothing is uploaded).

Layout under E:\\n0r53\\deposit\\N0_R53_package_<YYYYMMDD>\\:
  code/        frozen drivers and addenda modules (E:\\n0r53\\code), R52 code copy, server wrapper scripts
  models/      OpenSees command logs of the ten model variants (derived from the published scripts)
  protocol/    frozen protocol with dated addenda, decision record
  analysis/    analysis scripts and every derived JSON/CSV/TXT they write
  runs/        one zip per run phase (all per-state JSON outputs, incl. logs/ subfolders)
  manuscript/  LaTeX sources, bibliography, generated macro/table files, figure PDFs, main.pdf, supplement.pdf
  logs/        server run report, sync manifest, reproduction logs
  MANIFEST_SHA256.tsv  relative path, bytes, SHA-256 of every file in the package
  runs/<phase>.zip.manifest.tsv  SHA-256 of every member of each zip
  README.md
Excluded on purpose: ground-motion files (PEER/FEMA P695 terms; record IDs and scale factors are in
runs/ida and the analysis tables), the published model Tcl sources (cited, not redistributed),
runs_quarantine/ (superseded-era SMF8CG deep outputs, byte-identical duplicates documented in earlier
addenda) and server staging directories. quarantine/ IS included (A17 defective-phi1 evidence)."""
import hashlib
import shutil
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(r"E:\n0r53")
ROUND = Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate"
             r"\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21")
DEST = ROOT / "deposit" / f"N0_R53_package_{time.strftime('%Y%m%d')}"
MS_EXT = {".tex", ".bib", ".bst", ".cls", ".sty", ".pdf"}
AN_EXT = {".py", ".ps1", ".json", ".csv", ".txt", ".md"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main():
    if DEST.exists():
        sys.exit(f"{DEST} exists; remove it or change the date before rebuilding")
    DEST.mkdir(parents=True)
    # code
    for p in (ROOT / "code").glob("*.py"):
        copy(p, DEST / "code" / p.name)
    for p in (ROOT / "code_copy").rglob("*.py"):
        copy(p, DEST / "code" / "code_copy_R52" / p.relative_to(ROOT / "code_copy"))
    phi_dir = ROOT / "code_copy" / "phi1"
    if phi_dir.exists():
        for p in phi_dir.glob("*.json"):
            copy(p, DEST / "code" / "code_copy_R52" / "phi1" / p.name)
    for p in list(ROOT.glob("*.py")) + list(ROOT.glob("*.ps1")):          # server wrapper, launch/sync scripts
        copy(p, DEST / "code" / "server" / p.name)
    # models (derived command logs only)
    for p in (ROOT / "models").rglob("*.json"):
        copy(p, DEST / "models" / p.relative_to(ROOT / "models"))
    # protocol
    for p in (ROUND / "notes").glob("*.md"):
        if p.name.startswith(("PROTOCOL_R53", "DECISION_RECORD")):
            copy(p, DEST / "protocol" / p.name)
    # analysis
    for p in (ROOT / "analysis").rglob("*"):
        if p.is_file() and p.suffix in AN_EXT and "__pycache__" not in p.parts:
            copy(p, DEST / "analysis" / p.relative_to(ROOT / "analysis"))
    for p in (ROUND / "code").glob("*.py"):
        copy(p, DEST / "analysis" / "round_code" / p.name)
    for p in (ROUND / "results").glob("*.json"):
        copy(p, DEST / "analysis" / "round_results" / p.name)
    # manuscript
    for p in (ROUND / "manuscript").iterdir():
        if p.is_file() and p.suffix in MS_EXT:
            copy(p, DEST / "manuscript" / p.name)
    # logs
    for name in ("server_run_report.md", "server_sync_manifest.csv", "server_sync_manifest.README.md",
                 "shepherd_state.md", "repro.log", "handoff_final_report.md"):
        p = ROOT / "logs" / name
        if p.exists():
            copy(p, DEST / "logs" / name)
    for name in ("delta_manifest.csv", "delta_list.txt"):
        p = ROOT / name
        if p.exists():
            copy(p, DEST / "logs" / name)
    # quarantine evidence (defective-phi1 A17 incident; kept for provenance)
    for p in (ROOT / "quarantine").rglob("*"):
        if p.is_file():
            copy(p, DEST / "quarantine" / p.relative_to(ROOT / "quarantine"))
    # runs: one zip per phase, with an inner manifest
    (DEST / "runs").mkdir()
    for d in sorted((ROOT / "runs").iterdir()):
        if not d.is_dir():
            continue
        zp = DEST / "runs" / f"{d.name}.zip"
        rows = []
        with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in sorted(d.rglob("*")):
                if f.is_file() and f.suffix not in (".tmp", ".lock"):
                    arc = f.relative_to(ROOT / "runs").as_posix()
                    z.write(f, arc)
                    rows.append(f"{arc}\t{f.stat().st_size}\t{sha(f)}")
        (DEST / "runs" / f"{d.name}.zip.manifest.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(f"zipped {d.name}: {len(rows)} files", flush=True)
    # README
    (DEST / "README.md").write_text(README, encoding="utf-8")
    # top-level manifest
    rows = []
    for f in sorted(DEST.rglob("*")):
        if f.is_file() and f.name != "MANIFEST_SHA256.tsv":
            rows.append(f"{f.relative_to(DEST).as_posix()}\t{f.stat().st_size}\t{sha(f)}")
    (DEST / "MANIFEST_SHA256.tsv").write_text("path\tbytes\tsha256\n" + "\n".join(rows) + "\n", encoding="utf-8")
    tot = sum(f.stat().st_size for f in DEST.rglob("*") if f.is_file())
    print(f"package {DEST}: {len(rows)} files, {tot / 1e6:.1f} MB")


README = """# N0 / R53 study package (local; not deposited)

Zero-input collapse of steel moment-frame archetypes: damaged-state energy barrier, escape energy,
coda erosion and residual capacity. Companion to the manuscript in `manuscript/` (main.pdf, supplement.pdf).

## Contents
- `code/` frozen drivers `driver53.py`, `campaign53.py` (protocol R53v1.0) and the post hoc addenda modules
  `addenda53.py` (A6/A7/A8 tasks), `addenda53b.py` (A6b deep settled barriers), `addenda53d.py` (A6d solver
  ladder); `addenda53c.py` (ArcLength fallback) failed validation and is NOT used by any result.
  `code_copy_R52/` the frozen R52 code used for IDA and t95 tasks. `server/` the queue wrapper, launch,
  supervisor and sync scripts of the server runs (they call the frozen modules unchanged).
- `models/` OpenSees command logs of the ten variants (2/4/8/12/20 storeys, bare B and composite-gravity CG)
  generated from the published archetype scripts (Elkady & Lignos); the Tcl sources are cited, not redistributed.
- `protocol/` frozen protocol v1.0 (2026-10-21) with dated addenda A1-A17 (full list in PROTOCOL_R53.md
  and Supplementary Note 1). `code/code_copy_R52/phi1/` stores the frozen first-mode vectors of addendum A17.
- `analysis/` every analysis script and the JSON/CSV it writes; `numbers.tex` macros and all tables/figures are
  generated from these files (`make_numbers53.py`, `make_tables_tex.py`, `make_supp_tables.py`, `fig*.py`).
- `runs/<phase>.zip` per-state outputs; every JSON records its protocol tag and the SHA-256 of the code that
  produced it. Inner manifests `runs/<phase>.zip.manifest.tsv`.
- `logs/` server run report (reproduction gate, version and hash parity), sync manifest (origin of every file
  produced on the server), reproduction logs, shepherd_state.md (session journal), delta manifests.
- `quarantine/` the A17 defective-phi1 incident evidence: README, file manifest and the 288 quarantined
  SMF20B outputs (excluded from every analysis input; preserved for provenance).

## Environment
Python 3.12.10, openseespy 3.8.0.0, numpy 2.5.4, scipy 1.18.1 (local and server identical).
Ground motions: FEMA P695 far-field (44) and near-field (56) horizontal components from the PEER NGA database;
not included -- obtain from PEER and place as expected by `code_copy_R52/records.py`.

## Regeneration order
analysis/build_tables.py -> analysis/regen_law_chain.ps1 -> audit build (N0R53_NO_DEEP=1) + deep_vs_std_audit.py
-> intact_symmetry.py, check_push_deep.py, direction_split.py, early_edge_audit.py, branch_jump_audit.py
-> aftershock_analysis.py -> make_numbers53.py, make_tables_tex.py, make_supp_tables.py -> fig*.py -> LaTeX.

## Status
Prepared locally for the author's review. No repository, DOI or upload has been created.
"""

if __name__ == "__main__":
    main()
