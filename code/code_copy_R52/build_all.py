"""Rebuild every derived table, number, figure and the manuscript from the raw runs.

Order: analyses -> macros/tables -> figures -> ledger -> LaTeX (manuscript, cover
letter) -> QA.  Raw runs are read from N0R52_RUNS (default E:\\n0r52\\runs) and
N0R52_RUNS_DT (time-step check).  Usage:  python code/build_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable

STEPS = [
    ["analyze_ida.py", "SMF4B", "SMF8B", "SMF4CG"],
    ["analyze_zic.py", "SMF4B", "SMF8B", "SMF4CG"],
    ["analyze_t95.py", "SMF4B", "SMF8B"],
    ["analyze_classify.py"],
    ["analyze_dt.py"],
    ["analyze_cg.py"],
    ["make_numbers.py"],
    ["fig_models.py"],
    ["fig_results.py", "4", "5", "6", "7"],
    ["make_ledger.py"],
]


def run(cmd: list[str], cwd: Path, full: bool = False) -> None:
    print(">>", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace")
    tail = "\n".join(r.stdout.strip().splitlines()[-3 if not full else 0:])
    if tail:
        print(tail, flush=True)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {' '.join(cmd)} (exit {r.returncode})")


def latex(cwd: Path, name: str, bib: bool) -> None:
    run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", name], cwd)
    if bib:
        run(["bibtex", name], cwd)
        run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", name], cwd)
    run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", name], cwd)


def main() -> None:
    os.environ.setdefault("N0R52_RUNS", r"E:\n0r52\runs")
    for step in STEPS:
        run([PY, str(HERE / step[0]), *step[1:]], ROOT)
    latex(ROOT / "manuscript", "main", bib=True)
    latex(ROOT / "package", "cover_letter_draft", bib=False)
    run([PY, str(HERE / "qa_manuscript.py")], ROOT, full=True)


if __name__ == "__main__":
    main()
