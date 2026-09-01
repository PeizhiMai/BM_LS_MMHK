# Fig. 4 finite-(U,V) C_NN fullobs campaign

Created on CADES: 2026-08-20T23:57:01-04:00

Batch root: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820`

Targets: 12 Mott-side (U,V) pairs x 25 deterministic maximin twists = 300
independent fullobs calculations.  No target result existed at generation.

Pairs:
- U=20, V=0
- U=20, V=2
- U=20, V=3
- U=20, V=4
- U=20, V=4.5
- U=40, V=6
- U=80, V=0
- U=80, V=4
- U=80, V=8
- U=80, V=12
- U=80, V=16
- U=80, V=18

Original solver: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/Hubbard_sym_testobs_UV.x`
Pinned executable actually run by every job: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.x`
Pinned source: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.cc`
Pinned qbasis runtime library: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/libqbasis.so`
Solver SHA-256: `b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b`
Source SHA-256: `f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73`
qbasis library SHA-256: `be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85`
The reviewed source calls `locate_E0_lanczos(..., 10000)`.

Physics: 4x4, Nup=Ndn=8, Q=(0,0), t'=0.
Resources per job: account placeholder, burst, 1 node, 32 tasks,
1 CPU/task, 100 GB, 8 hours, TERM warning at 120 s.
Job name: `F4CNN25`.

Safety:
- Generation is submission-free and refuses to overwrite an existing batch.
- `submit_fill.sh` is disarmed without `F4CNN25_CONFIRM_SUBMIT=YES`.
- Results are generated in isolated per-job work directories, validated for a
  standalone `status COMPLETE`, and then installed atomically.
- An incomplete root-level target is never deleted or overwritten.
- Each job runs the batch-local pinned executable and checks its reviewed
  SHA-256 before execution.  `PINNED_SHA256SUMS` pins the executable, source,
  and qbasis runtime library for monitor/audit use.  The pinned-library
  directory is first in `LD_LIBRARY_PATH`, and every job verifies that `ldd`
  resolves `libqbasis.so` to the pinned copy.
- Queue filling counts all of the user's jobs on the selected account and
  defaults to the established total-user cap of 150 per account.

Read-only validation:
```
/usr/bin/python3.11 preflight.py
/usr/bin/python3.11 dry_run_submit.py ccsd
/usr/bin/python3.11 status.py
```

Armed initial submission (not run by the generator):
```
F4CNN25_CONFIRM_SUBMIT=YES F4CNN25_CCSD_USER_CAP=150 ./submit_fill.sh ccsd
```
Each completed/skipped batch job calls `submit_next.sh`, keeping the campaign
moving without exceeding the selected total-user account cap.

Submission records:
- `logs/submit.log`: raw tab-separated timestamp, account, rendered script,
  and exact `sbatch` response.
- `submission.tsv`: header plus submitted_at, account, job_id, manifest index,
  U, V, kx, ky, rendered run script, and result path.

Final aggregation:
```
/usr/bin/python3.11 analyze.py
```
The primary C_NN estimator is the unweighted arithmetic mean over this exact
validated 25-twist panel.  The exchange-symmetry-weighted mean is emitted only
as a diagnostic.  Twist spread is explicitly not treated as a standard error.
At the existing U=40 all-twist controls (V=0,4,8,9), the primary panel-minus-
861-grid C_NN differences are -1.35e-7, -1.76e-7, -2.44e-7, and -2.69e-7.
