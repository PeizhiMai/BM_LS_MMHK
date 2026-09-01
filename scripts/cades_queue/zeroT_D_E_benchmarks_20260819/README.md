# Zero-temperature E0/D CADES batch

This directory records the isolated 16-MMHK batch used for the Yao/Zhou
zero-temperature comparison.  The production copy lives at:

`/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/literature_benchmarks_20260819`

- `generate_batch.py` creates 5166 targets: six interacting sets times the
  861-point symmetry wedge.
- `buildUV.sh` compiles the lean E0/D executable with the same qbasis/MKL
  toolchain used by `fullobs`.
- `submit_initial_E0D.sh` fills an account without exceeding the 150-total-user
  job cap; it is protected by `E0D_CONFIRM_SUBMIT=YES`.
- `submit_next_E0D.sh` self-refills the account as jobs finish.
- `check_status_E0D.py` validates `COMPLETE`, 10,000-iteration result files and
  writes a missing-target manifest.

The batch does not modify the existing `fullobs` templates or UV-set files.

The `U=V=0` production scan is omitted because its energy and `D=1/4` are
available analytically. A single free-point solver run is retained only as a
code-validation check; all six production sets are interacting.
