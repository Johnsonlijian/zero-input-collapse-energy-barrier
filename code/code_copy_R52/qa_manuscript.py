"""Final manuscript checks (run after compiling manuscript/main.tex).

* unresolved number macros ('??') and undefined references in the log
* overfull boxes
* abstract word count (<= 250), keywords (1-7), highlights (3-5, <= 85 chars)
* every \\cite key exists in refs.bib and every bib entry is cited
* figures referenced exist
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAN = HERE.parent / "manuscript"
PKG = HERE.parent / "package"
FIG = HERE.parent / "figures"


def tex_words(tex: str) -> int:
    t = re.sub(r"\\Num[A-Za-z]+", "0", tex)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", t)
    t = re.sub(r"[{}~$\\]", " ", t)
    return len([w for w in t.split() if re.search(r"[A-Za-z0-9]", w)])


def main() -> int:
    problems = []
    log = (MAN / "main.log").read_text(encoding="latin-1", errors="replace") if (MAN / "main.log").exists() else ""
    if "Citation" in log and "undefined" in log:
        problems.append("undefined citations in log")
    if re.search(r"Reference `[^']+' on page \d+ undefined", log):
        problems.append("undefined references in log")
    n_over = len(re.findall(r"Overfull \\hbox", log))
    if n_over:
        problems.append(f"{n_over} overfull hbox warnings")
    nums = (MAN / "numbers.tex").read_text(encoding="utf-8")
    miss = re.findall(r"\\newcommand\{\\Num([A-Za-z]+)\}\{\?\?\}", nums)
    used = set()
    for f in MAN.glob("*.tex"):
        if f.name != "numbers.tex":
            used |= set(re.findall(r"\\Num([A-Za-z]+)", f.read_text(encoding="utf-8")))
    miss_used = sorted(set(miss) & used)
    if miss_used:
        problems.append(f"unresolved macros used in text: {miss_used}")
    # unfinished text markers
    for f in list(MAN.glob("*.tex")) + list(PKG.glob("*.tex")) + list(PKG.glob("*.txt")):
        text = f.read_text(encoding="utf-8")
        if "TODO" in text:
            problems.append(f"TODO marker left in {f.name}")
        # numbers.tex contains deliberately defined placeholders for unused
        # optional macros.  Used placeholders are checked above; every other
        # submission-facing file must remain free of literal unresolved text.
        if "??" in text and f.name != "numbers.tex":
            problems.append(f"literal unresolved placeholder left in {f.name}")
    # the text states that no continuation was censored
    if not re.search(r"\\newcommand\{\\NumReleasesCensored\}\{0\}", nums):
        problems.append("censored continuations present (text claims none)")
    def num(name):
        m = re.search(r"\\newcommand\{\\Num" + name + r"\}\{\$?([+-]?)\$?([0-9.]+)\}", nums)
        return None if not m else float(m.group(1) + m.group(2))

    # "truncating records at t95 raised median collapse intensities" (both frames)
    for tag in ("FourB", "EightB"):
        v = num("TNinetyFiveMedShift" + tag)
        if v is None or v <= 0:
            problems.append(f"t95 truncation shift for {tag} is not positive: revise 'raised'")
    s4, s8 = num("TNinetyFiveMedShiftFourB"), num("TNinetyFiveMedShiftEightB")
    if s4 is None or s8 is None or abs(s4 - s8) > 2:
        problems.append(f"t95 shifts {s4} and {s8} differ: revise 'by about ... in both frames'")
    # "kinetic energy improves the classification only marginally" (hold-out errors, percentage points)
    d_err, dk_err = num("BestThetaErrHold"), num("RuleErrHold")
    if d_err is None or dk_err is None or dk_err > d_err or d_err - dk_err > 5:
        problems.append(f"hold-out errors D={d_err}, DK={dk_err}: revise 'reduces ... only marginally'")
    # the abstract states that the point of no return was located on every collapse history at S_a,c
    for tag in ("FourB", "EightB"):
        m = re.search(r"\\newcommand\{\\NumPNR" + tag + r"\}\{([^}]*)\}", nums)
        if not (m and m.group(1) == "100"):
            problems.append(f"PNR{tag} is not 100: revise 'located on every collapse history'")
    # the abstract and conclusions state that every frame released from rest at t* would have recovered
    for tag in ("FourB", "EightB"):
        m = re.search(r"\\newcommand\{\\NumKineticFrac" + tag + r"\}\{([^}]*)\}", nums)
        if not (m and m.group(1) == "100"):
            problems.append(f"KineticFrac{tag} is not 100: revise 'the frames would still have recovered'")
    # the text states that no IDA analysis failed numerically and every record collapsed
    if not re.search(r"\\newcommand\{\\NumIDANonconv\}\{0\}", nums):
        problems.append("non-converged IDA analyses present (text claims none)")
    if not re.search(r"\\newcommand\{\\NumIDACensored\}\{0\}", nums):
        problems.append("records without collapse present (text claims every record collapsed)")
    m_n = re.search(r"\\newcommand\{\\NumDtNrec\}\{([^}]*)\}", nums)
    m_t = re.search(r"\\newcommand\{\\NumDtNtotal\}\{([^}]*)\}", nums)
    if not (m_n and m_t and m_n.group(1) == m_t.group(1)):
        problems.append("time-step check: not every record could be compared (text assumes all)")
    defined = set(re.findall(r"\\newcommand\{\\Num([A-Za-z]+)\}", nums))
    undefined = sorted(used - defined)
    if undefined:
        problems.append(f"macros used but not defined: {undefined}")
    abs_words = tex_words((MAN / "abstract.tex").read_text(encoding="utf-8"))
    if abs_words > 250:
        problems.append(f"abstract has {abs_words} words (> 250)")
    main_tex = (MAN / "main.tex").read_text(encoding="utf-8")
    kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", main_tex, re.S)
    n_kw = len(kw.group(1).split("\\sep")) if kw else 0
    if not 1 <= n_kw <= 7:
        problems.append(f"{n_kw} keywords")
    hl = [ln.strip("-• \t") for ln in (PKG / "highlights.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not 3 <= len(hl) <= 5:
        problems.append(f"{len(hl)} highlights")
    for h in hl:
        if len(h) > 85:
            problems.append(f"highlight too long ({len(h)}): {h}")
    bib = (MAN / "refs.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    cited = set()
    for f in MAN.glob("*.tex"):
        for grp in re.findall(r"\\cite\{([^}]+)\}", f.read_text(encoding="utf-8")):
            cited |= {k.strip() for k in grp.split(",")}
    if cited - keys:
        problems.append(f"cited but missing in bib: {sorted(cited - keys)}")
    if keys - cited:
        problems.append(f"bib entries never cited: {sorted(keys - cited)}")
    for f in MAN.glob("*.tex"):
        for g in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", f.read_text(encoding="utf-8")):
            if not any((FIG / (g + ext)).exists() for ext in ("", ".pdf", ".png")):
                problems.append(f"missing figure {g}")
    print(f"abstract words: {abs_words}; keywords: {n_kw}; highlights: {[len(h) for h in hl]}; "
          f"cited refs: {len(cited)}; bib entries: {len(keys)}")
    for p in problems:
        print("PROBLEM:", p)
    print("QA:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
