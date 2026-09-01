# U=80, V=20 Fig. 4 fullobs P25 package

Status: locally reviewed. Remote creation and submission are separate armed
actions.

- Remote batch: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_u80v20_fig4_cnn_20260822_213314`
- Normal job: `F4C80V20`
- Reserved repair name: `F4C80V20R` (do not use without separate review)
- Scope: one copy of 25 reviewed maximin twists at `U=80,V=20`, labelled
  `boundary`
- Primary account: `ccsd`; no rebalance because 25 is below the >50-task rule
- Resources: `burst`, 1 node, 32 tasks x 1 CPU, 100G, 08:00:00
- Canonical output: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f<KX>x<KY>Q0x0_obs.dat`
- Manifest SHA-256: `e5e95fa9b65d312b79f3a6349252a37c9ea60c1ce95df50a3be142b334c97117`
- Twist-panel SHA-256: `688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b`

The deep auditor applies common exact-metadata, finite/bounded C_NN,
four-identity, unique-seed/result, filename, pin, Slurm-resource,
unmapped-activity, and duplicate checks. Because the row is `boundary`, it
reports D/charge observables but does not apply the Mott-only `D_site < 0.25`
rejection.

## Final read-only gate

From the local package directory, before any remote write:

```bash
ssh cades /usr/bin/python3.11 - < remote_readonly_audit.py > /tmp/u80v20_precreate_audit.json
~/.venvs/myenv/bin/python -c 'import json; d=json.load(open("/tmp/u80v20_precreate_audit.json")); assert d["collision_free"] and d["remote_mutations"] == d["sbatch_calls"] == 0; print("PRECREATE COLLISION AUDIT PASS")'
```

## Create the isolated remote batch (no submission)

Use a fresh holding directory; never overwrite the destination:

```bash
HOLD=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/.holding_u80v20_20260822_213314
ssh cades "test ! -e $HOLD && mkdir -m 700 $HOLD"
scp setup_generator.py audit_status.py cades:$HOLD/
ssh cades "/usr/bin/python3.11 $HOLD/setup_generator.py"
```

Then verify the generated hashes and run the submission-free checks:

```bash
BATCH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_u80v20_fig4_cnn_20260822_213314
ssh cades "sha256sum $BATCH/manifest.tsv $BATCH/twist_panel.tsv"
ssh cades "/usr/bin/python3.11 $BATCH/preflight.py"
ssh cades "/usr/bin/python3.11 $BATCH/dry_run_submit.py ccsd"
ssh cades "/usr/bin/python3.11 $BATCH/audit_status.py --batch $BATCH --job-name F4C80V20 --job-name F4C80V20R --pin-file PINNED_SHA256SUMS --submission-log repair_submission.tsv --require-pins --since 2026-08-22 --expect-targets 25 --expect-per-case 25 --expect-account ccsd --expect-partition burst --expect-cpus 32 --expect-nodes 1 --expect-memory 100G --expect-time-limit 08:00:00 --write-report $BATCH/analysis/pre_submit_audit.json"
```

Require 25 targets/templates, 25 unique seeds/results, pins 3/3, zero
exact-name activity, no FAILED/INVALID/anomaly/scheduler error, the two exact
hashes above, and dry-run `would_submit=25`.

## Submit exactly one P25 wave

```bash
ssh cades "F4C80V20_CONFIRM_SUBMIT=YES F4C80V20_CCSD_USER_CAP=150 $BATCH/submit_fill.sh ccsd"
```

Immediately re-run the deep audit. Do not call the submit command a second
time; do not create replicas or rebalance. The queue-fill scripts are
target/template locked, and work/output/logs stay batch-local until atomic
canonical installation.
