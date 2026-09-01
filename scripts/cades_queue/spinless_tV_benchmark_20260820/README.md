# Spinless 16-MMHK t-V benchmark batch

This isolated workflow benchmarks the spinless square-lattice model

`H = -t sum_<ij> (c_i^dagger c_j + h.c.) + V sum_<ij> n_i n_j`

against Zhou et al., PRB 109, 245107 (2024). There is one fermionic flavor,
so the local basis is `{|0>,|1>}` and there is no Hubbard `U` term.

Production parameters:

- 4x4 MMHK mixing resolution, `N=8`, `Q=(0,0)`, `t=1`, `t'=0`;
- `V/t = 0.45, 1, 2`;
- 861 symmetry-wedge targets per interaction, 2,583 targets total;
- 123 Slurm bundle scripts: one fixed-`kx` row per `V`, containing 1--41
  sequential targets;
- Lanczos ceiling 10,000, four CPUs, 8 GB, two-hour walltime per bundle.

The `V=0` result is analytical and is not included in production. Both the
MMHK and Zhou energies are compared per lattice site, so no factor of two is
used.

The remote root is:

`/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/spinless_tV_benchmark_20260820`

Production submission is disarmed unless `SLTV_CONFIRM_SUBMIT=YES` is set.
Preparing or compiling this folder does not submit any production jobs.

Validated preparation sequence on CADES:

```bash
cd /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/spinless_tV_benchmark_20260820
./buildUV.sh
./scripts/generate_batch.py
./scripts/check_status_spinless.py
```

The free pilot at `(kx,ky)=(7,13)` agrees with the exact fixed-`Q=(0,0)`
Slater-determinant energy to `5.3e-15`.  Finite-`V` pilots completed at all
three production interactions, and repeating the `V=1` pilot with a different
seed produced identical energy.

Only after explicit approval, production can be launched with, for example,

```bash
SLTV_CONFIRM_SUBMIT=YES ./scripts/submit_initial_spinless.sh ccsd
```

The 123 bundle templates collectively cover all 2,583 targets.  The submission
scripts enforce a 150-total-user-job cap and automatically refill from retained
templates; calling either submission script without the confirmation variable
returns without submitting.
