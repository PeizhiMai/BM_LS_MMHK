# BM/LS MMHK benchmark and zero-dispersion workflows

This repository contains the source code and reproducibility workflows for the
orbital-cluster MMHK benchmark, Green-function-zero dispersion analysis, and
the associated manuscript figures.

## Repository layout

- `code/`: C++/QBasis model and observable programs.
- `scripts/`: local analysis, validation, plotting, and CADES Slurm workflow
  scripts.  Batch subdirectories retain setup/monitor code and provenance,
  while generated queue ledgers and large manifests are intentionally omitted.
- `internal_tests/`: regression and workflow tests; generated test outputs are
  not versioned.
- `notes/` and `reports/`: dated implementation plans, audits, and technical
  derivations.
- `manuscript/`: active LaTeX sources and the figure assets needed to compile
  the paper and supplement.
- `results/`: a small tracked historical baseline plus selected canonical
  validation/provenance tables.  Bulk generated results are kept outside Git.

## Data policy

Raw Lanczos files, downloaded references, cluster work directories, local
Python environments, compiled executables, and generated plots/build trees are
excluded from Git.  They are large, host-specific, or reproducible from the
tracked source.  In particular, the canonical local raw-data tree is expected
under:

```text
data/Gcalpath/Lanczos_raw_data/
```

CADES workflows use batch-specific directories and validate each Green-function
pair before installation.  Generated manifests, submission ledgers, repair
state, and raw output should remain in those runtime directories rather than be
committed.

## Runtime conventions

Local Python analysis is run with the project environment at:

```bash
~/.venvs/myenv/bin/python
```

The CADES scripts record their required Python executable, Slurm resources,
seeds, validation policy, and source hashes in the corresponding batch
subdirectory.  Review a batch README/provenance file before submitting it.

## Reproducibility

Analysis scripts write machine-readable CSV/JSON audits alongside generated
figures.  Current axis-refinement coverage is summarized in:

- `results/gcalpath_axis_refinement_coverage_20260828.csv`
- `results/gcalpath_axis_refinement_provenance_20260828.json`

Do not overwrite raw-data filename conflicts during CADES-to-local transfer;
compare metadata and SHA-256 hashes first.
