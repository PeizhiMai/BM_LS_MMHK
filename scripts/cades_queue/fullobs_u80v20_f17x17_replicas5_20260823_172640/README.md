# U80,V20 f17x17: five convergence-hardened true-seed replicas

This is a local, **not-yet-built and not-yet-submitted** package for five user-authorized additional replicas (ordinals 4--8). The original solver/library must not be reused: `QBASIS_LANCZOS_SEED` was inert because the reviewed qbasis `model.cc` hardcoded `seed = 1`, and the canonical plus first three replica CG traces were identical over every shared line. The original 10,000-iteration ceiling also failed to produce this target.

- Intended remote batch: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640`
- Exact Slurm job name: `F4U80R5`
- True fresh seeds: 436887014, 3276620531, 3952085789, 2430698334, 1012333963
- Runtime: patched batch-local qbasis library requiring and strictly parsing `QBASIS_LANCZOS_SEED` as a nonzero decimal uint32; patched solver raises the sole Lanczos/CG `maxit` call from 10,000 to 50,000.
- Resources per replica: `ccsd`, `burst`, one node, 32 tasks x 1 CPU, 100G, `47:00:00` (below the 48-hour burst ceiling).
- Isolation: sources, build tree, runtime pins, results, work, locks, and logs are batch-local. Canonical and all prior-replica paths are read-only and never promotion targets.
- Compute-node validation and seed proof use Bash/Awk/coreutils only; no Python is invoked by a replica job.

The bundled exact original sources, patched sources, and unified diffs are bound by `SOURCE_SHA256SUMS`. The package does **not** contain the unsafe old runtime binaries. After a controlled upload, build the new runtime once, without submitting:

The build gate runs the actual compiled solver sequentially with the first two selected seeds and one OpenMP/MKL thread, waits at most 720 seconds per run for one exact effective-seed marker plus a nonempty allowed Lanczos/CG trace, and ends only that new smoke process group after proof. A clean natural exit after final evidence is accepted without signaling. The receipt hashes stdout, stderr, traces, and equal-line trace prefixes and requires seed-dependent prefix content, so different file lengths alone cannot pass.

```sh
ssh cades "/usr/bin/python3.11 /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/build_pins.py"
```

Then run the read-only preflight:

```sh
ssh cades "/usr/bin/python3.11 /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/preflight.py"
```

Only after independent review of `BUILD_RECEIPT.json`, `BUILT_PIN_SHA256SUMS`, and a passing preflight, submit exactly once. The submission receipt binds both build-artifact hashes:

```sh
ssh cades "F4U80R5_CONFIRM_SUBMIT=YES /usr/bin/python3.11 /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/submit_replicas.py"
```

Read-only audit:

```sh
ssh cades "/usr/bin/python3.11 /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/audit_replicas.py --json"
```

Never automatically rerun a partial submission, resubmit, repair, rebalance, cancel, overwrite, delete, copy, or promote results. Any scheduler, pin, build, identity, resource, cardinality, seed-proof, canonical-path, package, or unmapped-activity anomaly is a stop condition.
