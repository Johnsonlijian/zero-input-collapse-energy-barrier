import re, glob, os

MS = r"W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21\manuscript"

defined = set()
for f in glob.glob(os.path.join(MS, "*.tex")):
    t = open(f, encoding="utf8").read()
    defined |= set(re.findall(r"\\newcommand\{\\(\w+)\}", t))
    defined |= set(re.findall(r"\\providecommand\{\\(\w+)\}", t))

used = {}
for f in glob.glob(os.path.join(MS, "*.tex")):
    t = open(f, encoding="utf8").read()
    for m in re.findall(r"\\([A-Za-z]+)", t):
        used.setdefault(m, set()).add(os.path.basename(f))

BUILTIN = set("""documentclass usepackage input include begin end section subsection
paragraph textbf textit emph cite citep citet ref label caption centering
includegraphics width textwidth linewidth columnwidth hline toprule midrule
bottomrule cmidrule multicolumn multirow footnotesize scriptsize small normalsize
large Large LARGE vspace hspace vspace* hspace* noindent newline linebreak pagebreak
clearpage newpage tableofcontents maketitle title author date thanks affiliation
frac sqrt sum int lim cdot ldots times leq geq neq approx sim propto infty partial
nabla alpha beta gamma delta epsilon theta lambda mu nu pi rho sigma tau phi chi
psi omega Gamma Delta Theta Lambda Pi Sigma Phi Psi Omega mathbb mathcal mathrm
mathit mathsf mathttmathbf mathbf left right langle rangle lceil rceil lfloor rfloor
mathrm overline underline overbrace underbrace hat tilde bar vec dot ddot
text dfrac tfrac binom quad qquad enskip thinspace medspace thickspace
item enumerate itemize description figure table tabular array equation align
alignat gather multline split cases minipage subfigure subcaption wrapfigure
setlength addtolength newcounter setcounter addtocounter refstepcounter
newcommand renewcommand providecommand newenvironment renewenvironment
definecolor colorbox fcolorbox rule raisebox parbox makebox framebox mbox
phantom hphantom vphantom smash bmod pmod mod operatorname argmax argmin
exp log ln sin cos tan arcsin arccos arctan sinh cosh tanh max min sup inf
limsup liminf deg gcd det dim ker hom Pr bibliographystyle bibliography
addbibresource printbibliography url href doi arXiv eprint footnote marginpar
chapter part appendix frontmatter mainmatter backmatter tableofcontents
listoffigures listoftables index glossary acronym glossaries si SI unit
per squared cubed milli micro nano kilo mega giga metre meter second gram
num range ang percent degree celsius kelvin volt ampere ohm hertz joule watt
newton pascal bar becquerel gray sievert katal mole candela lumen lux farad
henry siemens tesla weber astrophysics aastex emulateapj apj mnras nature
naturemag preprint twocolumn onecolumn draft final letterpaper a4paper
lineno linenumbers pageref autoref cref Cref eqref nameref hyperref cleveref
booktabs array xcolor graphicx amsmath amssymb amsthm natbib biblatex siunitx
caption subcaption float algorithm algorithmic listings minted verbatim
tikz pgfplots geometry setspace enumitem titlesec fancyhdr lastpage etoolbox
""".split())

missing = sorted(m for m in used if m not in defined and m not in BUILTIN and len(m) > 3)
for m in missing:
    print(m, "<-", sorted(used[m]))
print(len(missing), "candidate-undefined")
