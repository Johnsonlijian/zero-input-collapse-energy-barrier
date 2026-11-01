# Zero-input collapse of steel moment frames 鈥?analysis code and derived outputs

Reproducibility companion to the study **鈥淶ero-input collapse of steel moment frames is
governed by a damaged-state energy barrier鈥?* (Lijian Ren, Inner Mongolia University of
Technology). The manuscript is in preparation; this repository holds the frozen protocol,
the analysis code and the derived numerical outputs behind its tables and figures, and is
the archive cited by its data- and code-availability statements.

**What the study does.** Instead of calling a numerical model collapsed when its drift
exceeds a limit, the ground motion is halted along collapse histories of ten published
steel moment-frame archetypes (2鈥?0 storeys, bare `B` and composite-gravity `CG`
variants, 100 FEMA P695 records each) and the damaged state is released under zero input.
The study tests whether commitment to collapse is an *energy* event 鈥?the kinetic energy
needed to push a released damaged state over its edge versus the quasi-static work of
carrying that damaged configuration to the collapse surface along a declared first-mode
path 鈥?and follows the consequences for damping, coda erosion of the barrier,
truncated-record collapse capacity and retained-capacity assessment.

## Repository layout

```
protocol/     frozen protocol R53v1.0 with dated addenda A1鈥揂20
code/         simulation drivers (driver53.py, campaign53.py, addenda53*.py)
  server/     queue / launch / supervisor scripts used on the compute host
  code_copy_R52/  frozen R52-era analysis code reused for IDA and t95 tasks
analysis/     post-processing scripts (Python)
  outputs/    derived JSON/CSV that the tables and figures are generated from
  tables/     generated LaTeX tables and numbers.tex (all macros used in the manuscript)
  figures/    generated figures (PDF vector masters + PNG previews)
```

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install openseespy==3.8.0.0 numpy==2.5.4 scipy==1.18.1 matplotlib
export N0R53_RUNS=/path/to/runs                  # where per-state outputs are written
python code/campaign53.py --help
```

The analysis scripts default to the author's archive root (`E:\n0r53` on Windows,
`/mnt/e/n0r53` in WSL). Either reproduce that layout or edit the `RUNS`/`MS` constants at
the top of each script; see `REPRODUCIBLE_RUNBOOK.md`.

## What is and is not in this repository

- **Included**: protocol, drivers, all post-processing scripts, every derived JSON/CSV used
  by the tables and figures, generated tables, figures and `numbers.tex`.
- **Not included**: the ground-motion records (FEMA P695 far-field and near-field
  components from the PEER NGA database, redistribution not permitted), the published
  archetype model scripts (Elkady & Lignos, GPL-3.0 鈥?cited, not redistributed), and the
  per-state OpenSees output set (鈮? GB of JSON, 55 427 files). See
  `DATASETS_AND_LINKS.csv` for how to obtain the inputs and `REPRODUCIBLE_RUNBOOK.md` for
  what can be regenerated without them.

## Citation and archive

- Repository: <https://github.com/Johnsonlijian/zero-input-collapse-energy-barrier>
- Archived release (v1.0.0) with a DOI: <https://doi.org/10.5281/zenodo.23853670>

If you use this code or the derived outputs, cite the archived release (see `CITATION.cff`) and
the manuscript once published.

## License

Code: MIT (`LICENSE`). Derived data, tables and figures: CC BY 4.0 (`LICENSE-DATA.md`).
Third-party material keeps its own license and is not redistributed here.
