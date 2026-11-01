"""WSL-path copy of literal_numbers_audit.py."""
import re
from pathlib import Path

MS = Path("/mnt/w/01_PROJECTS/NAS_DRIVE/IMUT/1-Research_Output/1-Papers/1_In_Preparation/ai_civil_slate_codex_goal_gate"
          "/rounds/R53_N0_TOPTIER_REBUILD_2026-10-21/manuscript")
FILES = ["abstract.tex", "sec_intro.tex", "sec_results.tex", "sec_discussion.tex", "sec_methods.tex",
         "figures.tex", "supplement.tex"]
OUT = Path(__file__).resolve().parent / "literal_numbers_audit.txt"
SKIP = re.compile(r"(Fig(ure)?s?\.?~?\d|Table~?\d|Tables~?\d|Note~?\d|Notes~?\d|Supplementary (Note|Table|Fig)s?~?\d"
                  r"|\\cite\{[^}]*\}|\\ref\{[^}]*\}|\\label\{[^}]*\}|A\d{1,2}[a-z]?\b|R53v1\.0|v1\.0|SMF\d+|\b\d{1,2}(B|CG)\b"
                  r"|\b(19|20)\d\d\b|OpenSeesPy~?3\.8|P695|\\texttt\{[^}]*\})")
NUM = re.compile(r"(?<![\\A-Za-z])[-$]*\d+(\.\d+)?")
lines_out = []
for fn in FILES:
    tex = (MS / fn).read_text(encoding="utf-8")
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    for i, line in enumerate(tex.splitlines(), 1):
        clean = SKIP.sub(" ", line)
        clean = re.sub(r"\\[A-Za-z]+", " ", clean)
        for m in NUM.finditer(clean):
            tok = m.group(0).strip("$-")
            if tok in ("0", "1", "2") and len(tok) == 1:
                continue
            s = max(0, m.start() - 60)
            lines_out.append(f"{fn}:{i}: {tok:>8}  ...{clean[s:m.end() + 40].strip()}...")
OUT.write_text("\n".join(lines_out), encoding="utf-8")
print(len(lines_out), "literals ->", OUT)
