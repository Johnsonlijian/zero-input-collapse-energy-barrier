"""QA: list every macro range '\\A--\\B' in the manuscript with the full family of values,
so that hand-picked endpoints (min/max frame) can be checked against the data."""
import re
from pathlib import Path

MS = Path(r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate"
          r"\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21\manuscript")
num = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", (MS / "numbers.tex").read_text(encoding="utf-8")))
FR = "(TwoB|TwoCG|FourB|FourCG|EightB|EightCG|TwelveB|TwelveCG|TwentyB|TwentyCG)"
pat = re.compile(r"\\(\w+)(?:\{\})?\\?%?\s*(?:--|\$\\to\$)\s*\\(\w+)")


def fam(name):
    m = re.match(rf"(\w*?){FR}(All|FF|NF)?$", name)
    return (m.group(1), m.group(3) or "") if m else (None, None)


for f in ("abstract.tex", "sec_intro.tex", "sec_results.tex", "sec_discussion.tex", "sec_methods.tex",
          "figures.tex", "supplement.tex"):
    tex = (MS / f).read_text(encoding="utf-8")
    for a, b in pat.findall(tex):
        fa, fb = fam(a), fam(b)
        if fa[0] is None or fa[0] != fb[0]:
            continue
        base, sfx = fa
        vals = {}
        for k, v in num.items():
            m = re.match(rf"{base}{FR}(All|FF|NF)?$", k)
            if m and (m.group(2) or "") in ("", sfx, "All", "FF"):
                vals.setdefault(m.group(1), v)
        try:
            fv = {k: float(v) for k, v in vals.items()}
        except ValueError:
            fv = {}
        lo, hi = (min(fv, key=fv.get), max(fv, key=fv.get)) if fv else ("?", "?")
        flag = "" if (fam(a) and a.endswith(tuple([lo + s for s in ("", "All", "FF", "NF")])) and
                      b.endswith(tuple([hi + s for s in ("", "All", "FF", "NF")]))) else "  <-- check"
        print(f"{f}: {a}={num.get(a)} -- {b}={num.get(b)} | family min {lo}={vals.get(lo)} max {hi}={vals.get(hi)}"
              f" | {dict(sorted(vals.items()))}{flag}")
