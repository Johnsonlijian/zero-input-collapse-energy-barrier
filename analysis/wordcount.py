"""Approximate word counts of the manuscript parts (texcount-like): comments dropped,
\\cite/\\ref/\\label removed, inline math counted as one word, macros as one word."""
import re
import sys
from pathlib import Path

MS = Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate"
          r"\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21\manuscript")


def words(tex: str) -> int:
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = re.sub(r"\\(cite|ref|label|includegraphics|input)\{[^}]*\}", " ", tex)
    tex = re.sub(r"\\(begin|end)\{[^}]*\}(\[[^\]]*\])?", " ", tex)
    tex = re.sub(r"\$[^$]*\$", " MATH ", tex)
    tex = re.sub(r"\\(section|subsection)\*?\{([^}]*)\}", r" \2 ", tex)
    tex = re.sub(r"\\(textbf|emph|textit|texttt|textsc)\{([^}]*)\}", r" \2 ", tex)
    tex = re.sub(r"\\[A-Za-z]+", " W ", tex)
    tex = re.sub(r"[{}~\\]", " ", tex)
    return len([t for t in re.split(r"\s+", tex) if re.search(r"[A-Za-z0-9]", t)])


for f in ("abstract.tex", "sec_intro.tex", "sec_results.tex", "sec_discussion.tex", "sec_methods.tex"):
    print(f"{f:20s} {words((MS / f).read_text(encoding='utf-8'))}")
fig = (MS / "figures.tex").read_text(encoding="utf-8")
for i, cap in enumerate(re.findall(r"\\caption\{(.*?)\}\n\\label", fig, flags=re.S), 1):
    print(f"figure {i} legend      {words(cap)}")
tab = (MS / "tables.tex").read_text(encoding="utf-8")
for i, cap in enumerate(re.findall(r"\\caption\{(.*?)\}\n", tab), 1):
    print(f"table {i} caption      {words(cap)}")
