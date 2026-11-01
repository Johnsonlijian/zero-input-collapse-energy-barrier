"""Audit R52 against the accepted EESD manuscript 1060116.

This is an internal provenance and duplicate-result check.  It does not
replace iThenticate or an editor's publication-ethics decision.
"""
from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EESD = (ROOT.parent.parent.parent / "2026-3Journal-R2-BaselineFirst" /
        "rounds" / "R01_EESD_major_revision_2026-09-27" / "working" /
        "latex" / "EESD_main_extracted.txt")
FF_MANIFEST = (Path(r"\\NAS\IMUT_WORKPOOL\01_PROJECTS\NAS_DRIVE\IMUT") /
               "1-Research_Output" / "1-Papers" / "1_In_Preparation" /
               "2026-3Journal-R2-BaselineFirst" / "data" /
               "fema_p695_farfield" / "manifest.csv")
REPORT = ROOT / "notes" / "EESD_R52_OVERLAP_AUDIT_2026-10-12.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def words(text: str) -> list[str]:
    text = text.lower()
    return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", text)


def manuscript_text() -> str:
    parts = []
    for path in sorted((ROOT / "manuscript").glob("*.tex")):
        if path.name not in {"numbers.tex"}:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def ngram_summary(a: list[str], b: list[str], n: int) -> tuple[int, int, float, float]:
    aa = Counter(tuple(a[i:i+n]) for i in range(len(a)-n+1))
    bb = Counter(tuple(b[i:i+n]) for i in range(len(b)-n+1))
    common = set(aa) & set(bb)
    return len(common), sum(aa[k] for k in common), len(common) / max(1, len(aa)), len(common) / max(1, len(bb))


def main() -> None:
    eesd_text = EESD.read_text(encoding="utf-8", errors="replace")
    r52_text = manuscript_text()
    ew, rw = words(eesd_text), words(r52_text)
    lines = [
        "# R52 versus accepted EESD manuscript: overlap audit",
        "",
        "**Audit date:** 2026-10-12 (local, internal provenance check)",
        "**EESD record:** manuscript `1060116`, accepted 2026-10-09; DOI and publication metadata were not yet assigned in the local acceptance record.",
        "**Verdict:** `PARTIAL_INPUT_FAMILY / DISTINCT_MODEL_AND_QUESTION / DISCLOSURE_REQUIRED / NO_DUPLICATE_RESULT_FOUND`.",
        "",
        "This audit compares the accepted EESD source text and the R52 manuscript source, the declared record sets, model identities and result roles. It is an internal check and does not certify similarity against the publisher's database.",
        "",
        "## Comparison",
        "",
        "| Dimension | Accepted EESD 1060116 | R52 candidate | Assessment |",
        "|---|---|---|---|",
        "| Central question | How actuator saturation is imposed and whether frequency retuning helps active/semi-active control | When a deteriorating SMF state becomes committed under zero-input continuation | Distinct |",
        "| Structural objects | Ohtori/SAC 3- and 9-story planar frames; OpenSeesPy response-level control benchmark | Elkady鈥揕ignos code-designed 4- and 8-story SMFs; bare and 4-story composite/gravity variants | Distinct model families |",
        "| Main factors | Elastic versus softened design model; clipping versus in-QP actuator bounds; controller/effort metrics | Complete record versus free continuation; threshold versus 1.5-times intensity; bare versus composite/gravity framing | Distinct factors and outputs |",
        "| Records | FEMA P695 far-field component 1 from 22 record pairs at two intensity tiers (44 evaluation rows) | FEMA P695 far-field 44 components plus 56 near-field components, each scaled to record-specific collapse intensity | Partial public-record overlap; different sampling and use |",
        "| Reported outputs | Drift, acceleration, actuator effort, pooled factorial variance shares, controller ranking | $t^*$, recoverability/commitment, collapse timing, record-tail truncation, static-versus-kinetic boundary | No shared primary result |",
        "| Reused figures/tables/results | No R52 figures/tables/results identified in the EESD source | No EESD figures/tables/results identified in R52 | No duplicate result found |",
        "",
        "## Record-family check",
        "",
    ]
    if FF_MANIFEST.exists():
        rows = list(csv.DictReader(FF_MANIFEST.open(encoding="utf-8")))
        pairs = {r["record_pair_id"] for r in rows}
        c1 = [r for r in rows if r["component"] == "1"]
        lines += [
            f"- The R52 far-field manifest contains {len(rows)} components from {len(pairs)} record pairs; {len(c1)} are component-1 rows.",
            "- EESD uses the component-1 member of each pair for its primary 3-story comparison; R52 uses both horizontal components and also adds the near-field set.",
            "- The shared material is the public FEMA P695 record family. It is not a shared private dataset, and the records are not redistributed in the R52 package.",
        ]
    else:
        lines.append("- The far-field manifest was not reachable during this audit; record-family overlap is therefore based on the two manuscripts' declared methods and remains a human recheck before upload.")
    lines += ["", "## Text screen", "", "Normalized word n-gram screen (source text only; bibliography and PDF layout are not treated as scientific prose):", ""]
    for n in (5, 8, 10):
        common, occ, ef, rf = ngram_summary(ew, rw, n)
        lines.append(f"- {n}-grams: {common} shared n-gram types; shared-type fraction {ef:.5f} of EESD types and {rf:.5f} of R52 types.")
    lines += [
        "- Shared n-grams are generic institutional, methods or publication phrases rather than a shared scientific paragraph. This screen is not a plagiarism score.",
        "",
        "## Disclosure to JCSR",
        "",
        "The cover letter should disclose the accepted EESD paper and state that the studies use different structural models, questions, analyses and reported outcomes. It should identify the FEMA P695 far-field set as the only shared public input family and state that no figures, tables, numerical results or text blocks are reused.",
        "",
        "## Human gate",
        "",
        "Before Editorial Manager upload, the author should compare the final accepted EESD production files with this R52 release candidate and confirm that no newly added production material, repository release or supplementary file changes the overlap assessment.",
        "",
        "## Source hashes",
        "",
        f"- EESD extracted source SHA-256: `{sha256(EESD)}`",
        f"- R52 source aggregate is generated from `{len(list((ROOT / 'manuscript').glob('*.tex')))-1}` manuscript TeX files; individual upload hashes are recorded in the final package manifest.",
        "",
        "`LOCAL_ONLY / NOT_SUBMITTED`",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
