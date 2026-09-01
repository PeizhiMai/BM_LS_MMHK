# Safe handoff: approved 25-panel campaign to the 861-wedge complement

The user's active parent goal supplies standing authorization to submit the
missing full-observable jobs. No further user confirmation is required after
the real frozen decision gate produces `decision=APPROVE_EXPANSION` with exit
status 0. **That certificate remains the mandatory machine gate:** do not copy
this package to CADES, create the expansion batch, or call `sbatch` for a
`NO_EXPANSION` certificate (exit 3), a missing certificate, or an invalid gate.
Those outcomes terminate this branch without remote changes.

## Fixed contract

- source batch: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820`
- expansion batch: `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821`
- expansion: 12 cases × 836 new coordinates = 10,032 jobs
- reused: 12 cases × 25 hash-pinned coordinates = 300 outputs
- combined: 12 × 861 = 10,332 outputs; quadrature weight 1600/case
- semantic plan SHA-256: `368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e`
- materialized manifest SHA-256: `53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31`
- job names: `F4CNN861X` and reserved repair name `F4CNN861R`
- solver/source/libqbasis hashes: `b85cefa...c0b`, `f68ecd...e73`, `be10e2...a85`

## 1. Local certificate gate (read-only)

Use the actual fresh paths emitted by `decision_gate.py`:

```bash
cd /Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark
PKG="$PWD/scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821"
CERT="/absolute/path/to/the/real/fig4_cnn_861_decision.json"

~/.venvs/myenv/bin/python "$PKG/generate_batch.py" \
  --verify-certificate --decision-certificate "$CERT"
CERT_SHA="$(shasum -a 256 "$CERT" | awk '{print $1}')"
test -n "$CERT_SHA"
```

Require `VERIFY_CERTIFICATE_ONLY`, `APPROVE_EXPANSION`, schema algorithm
`fig4_cnn_25_to_861_quadrature_v2`, the exact 300-output inventory digest,
the fixed `5e-4` propagated-slope tolerance, and at least one declared trigger.
This mode validates the full package ledger and writes nothing.

## 2. Transfer to fresh remote holding paths (only after step 1 passes)

The certificate stays outside the package so it cannot violate the immutable
package-file inventory. The holding package is not the final batch.

```bash
REMOTE_ROOT=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn
REMOTE_PKG="$REMOTE_ROOT/reviewed_packages/fullobs_861expand_fig4_cnn_20260821_${CERT_SHA}"
REMOTE_CERT="$REMOTE_ROOT/decision_certificates/fig4_cnn_861_${CERT_SHA}.json"
INCOMING="${REMOTE_PKG}.incoming"

ssh cades "set -eu; umask 077; \
  test ! -e '$REMOTE_PKG'; test ! -e '$INCOMING'; test ! -e '$REMOTE_CERT'; \
  mkdir -p '$REMOTE_ROOT/reviewed_packages' '$REMOTE_ROOT/decision_certificates'; \
  mkdir '$INCOMING'"
rsync -a --exclude='__pycache__/' "$PKG/" "cades:$INCOMING/"
scp "$CERT" "cades:${REMOTE_CERT}.incoming"
ssh cades "set -eu; \
  test \"\$(sha256sum '${REMOTE_CERT}.incoming' | awk '{print \$1}')\" = '$CERT_SHA'; \
  /usr/bin/python3.11 '$INCOMING/generate_batch.py' --dry-run >/tmp/f4cnn861x_dryrun_$$.json; \
  /usr/bin/python3.11 '$INCOMING/generate_batch.py' --verify-certificate \
    --decision-certificate '${REMOTE_CERT}.incoming' >/tmp/f4cnn861x_cert_$$.json; \
  mv '${REMOTE_CERT}.incoming' '$REMOTE_CERT'; mv '$INCOMING' '$REMOTE_PKG'; \
  cat /tmp/f4cnn861x_dryrun_$$.json; cat /tmp/f4cnn861x_cert_$$.json; \
  unlink /tmp/f4cnn861x_dryrun_$$.json; \
  unlink /tmp/f4cnn861x_cert_$$.json"
```

Require exactly 10,032 expansion rows, 10,032 unique expansion seeds, zero
source overlap, and the fixed semantic plan hash above.

## 3. Remote source and runtime gate (still read-only)

```bash
ssh cades /bin/bash -s <<'REMOTE'
set -eu
S=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820
B=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821
test ! -e "$B"
/usr/bin/python3.11 "$S/audit_status.py" --batch "$S" \
  --job-name F4CNN25 --job-name F4CNN25R \
  --pin-file PINNED_SHA256SUMS --require-pins \
  --submission-log repair_submission.tsv --since 2026-08-20 \
  --expect-targets 300 --expect-per-case 25 \
  --expect-account ccsd --expect-account cnms --expect-partition burst \
  --expect-cpus 32 --expect-nodes 1 --expect-memory 100G \
  --expect-time-limit 08:00:00 --strict --json | \
 /usr/bin/python3.11 -c 'import json,sys; p=json.load(sys.stdin); assert p["counts"]=={"COMPLETE":300}; assert not p["scheduler_errors"] and not p["warnings"] and not p["repair_candidates"]; assert not any(p["anomalies"].values()); assert len(p["pin_audit"])==3 and all(x["match"] for x in p["pin_audit"]); print("SOURCE_AUDIT_GATE_OK")'
test -z "$(squeue -h -r -u "$USER" -n F4CNN25,F4CNN25R,F4CNN861X,F4CNN861R)"
printf "%s  %s\n" \
 b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/Hubbard_sym_testobs_UV.x \
 f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73 /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/Hubbard_sym_testobs_UV.cc \
 be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85 /home/9pm/installs/lib/libqbasis.so | sha256sum -c -
REMOTE
```

Require 300/300 valid COMPLETE, zero activity/anomalies/repair candidates,
and 3/3 pinned hashes. The generator independently repeats these gates and
rederives all decision-driving target metrics from the exact source bytes.

## 4. Materialize without submission

```bash
ssh cades "set -eu; /usr/bin/python3.11 '$REMOTE_PKG/generate_batch.py' \
  --materialize --decision-certificate '$REMOTE_CERT'"
```

The generator has no `sbatch` call. It creates a transaction marker first,
removes a caught-failure tree, and removes the marker only after a successful
immutable preflight. An uncatchable interrupted tree retains
`MATERIALIZATION_INCOMPLETE` and must be inspected manually; never submit it.

Then require all of the following:

```bash
ssh cades /bin/bash -s <<'REMOTE'
set -eu
B=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821
test ! -e "$B/MATERIALIZATION_INCOMPLETE"
test "$(sha256sum "$B/manifest.tsv" | awk "{print \$1}")" = 53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31
/usr/bin/python3.11 "$B/preflight.py"
/usr/bin/python3.11 "$B/audit_status.py" --batch "$B" \
 --job-name F4CNN861X --job-name F4CNN861R \
 --pin-file PINNED_SHA256SUMS --require-pins \
 --submission-log repair_submission.tsv --since 2026-08-21 \
 --expect-targets 10032 --expect-per-case 836 \
 --expect-account ccsd --expect-account cnms --expect-partition burst \
 --expect-cpus 32 --expect-nodes 1 --expect-memory 100G \
 --expect-time-limit 08:00:00 --strict --json | \
 /usr/bin/python3.11 -c 'import json,sys; p=json.load(sys.stdin); assert p["counts"]=={"UNSUBMITTED":10032}; assert not p["batch_active_queue_counts"] and not p["scheduler_errors"] and not p["warnings"] and not p["repair_candidates"]; assert not any(p["anomalies"].values()); assert len(p["pin_audit"])==3 and all(x["match"] for x in p["pin_audit"]); print("EXPANSION_DRY_AUDIT_GATE_OK")'
/usr/bin/python3.11 "$B/submit_fill.py" --account ccsd
REMOTE
```

Expected state is 10,032 `UNSUBMITTED`, 10,032 templates, zero claims, zero
activity/anomalies, 3/3 pins, and a dry-run-only submit report.

## 5. Policy-bound initial fill and one-time add-only rebalance

Every handoff mutation must be preceded by a fresh immutable **policy-state**
artifact.  The pinned tool recomputes the campaign-specific decision from the
remote deep audit; it never calls `sbatch`, `scancel`, or another scheduler
mutation.  The generated helper accepts a handoff action only when it receives
all three values from that artifact: the phase, its 64-hex state digest, and
its exact comma-separated interleaved manifest-index selection.

The policy records these inputs explicitly:

- `P`: exact-name scheduler `PENDING`;
- `Q`: audited `UNSUBMITTED` templates;
- `B=P+Q`;
- `Rc,Rn`: exact-name `RUNNING+COMPLETING` on `ccsd,cnms`;
- pending/running counts by account, the total-user active count on the target
  account, the declared account cap, and resulting live capacity.

It records the selected rule branch, Boolean `counts_changed`, target account,
requested `N`, cap-clipped effective `N`, and the exact round-robin manifest
indices.  Round-robin order is a fixed global sequence: first coordinate of
all twelve physics cases in manifest case order, then the second coordinate
of each case, and so on; each invocation filters that same sequence to the
still-unsubmitted set. Thus repeated one-job refills cannot reset to and drain
the first case. The manifest, coordinates,
seeds, template bytes, and semantic plan are unchanged.

Create a fresh private artifact directory and define all six exact paths:

```bash
RECEIPT_DIR="$PWD/results/automation_runs/fullobs_861_handoff_${CERT_SHA}"
mkdir -m 700 "$RECEIPT_DIR"
P0="$RECEIPT_DIR/policy_initial_launch.json"
P10="$RECEIPT_DIR/policy_rebalance_10m.json"
P20="$RECEIPT_DIR/policy_rebalance_20m.json"
R0="$RECEIPT_DIR/receipt_initial_launch.json"
R10="$RECEIPT_DIR/receipt_rebalance_10m.json"
R20="$RECEIPT_DIR/receipt_rebalance_20m.json"
```

All policy states and receipts are created with `O_CREAT|O_EXCL`, never via a
replace operation, fsynced with their parent directory, chmod `0444`, and
required to remain regular non-symlink files with link count one.  If any
output path exists, choose no replacement: stop and inspect it.

### Initial primary-account fill

Before any expansion `sbatch`, capture the empty-ledger/zero-activity state:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --capture-policy-state --certificate "$CERT" --phase initial_launch \
  --account-cap 150 --output "$P0"
ACTION_ID="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["state_digest"])' "$P0")"
N="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["policy"]["effective_n"])' "$P0")"
INDICES="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(",".join(map(str,json.load(open(sys.argv[1]))["policy"]["selected_manifest_indices"])))' "$P0")"
test "$N" -gt 0; test -n "$INDICES"
```

Submit exactly that bound selection to `ccsd`; automatic one-for-one refill
remains explicitly enabled in the jobs:

```bash
ssh cades "set -eu; B='$REMOTE_ROOT/fullobs_861expand_fig4_cnn_20260821'; cd \"\$B\"; \
 F4CNN861X_CONFIRM_SUBMIT=YES F4CNN861X_CHAIN_SUBMIT=YES \
 F4CNN861X_CCSD_USER_CAP=150 /usr/bin/python3.11 submit_fill.py \
 --submit --account ccsd --limit '$N' --submission-kind initial_launch \
 --action-id '$ACTION_ID' --expected-indices '$INDICES'"
```

Then bind the resulting action rows and Slurm job IDs:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --certificate "$CERT" --phase initial_launch --policy-state "$P0" \
  --output "$R0"
```

The receipt proves the pre-action ledger is an unchanged prefix and records
both the full append delta (including any concurrent self-refill rows) and the
exact action rows identified by `submission_kind`, `action_id`, and
`selection_rank`.  The action rows must match effective `N` and the policy's
interleaved indices exactly.  If live capacity or templates changed between
capture and submission, the helper/receipt fails closed before heartbeat
eligibility; never edit, replace, or reinterpret the artifact.

### +10-minute add-only decision

Wait at least 600 seconds after `R0`, then capture one fresh state:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --capture-policy-state --certificate "$CERT" --phase rebalance_10m \
  --previous-receipt "$R0" --account-cap 150 --output "$P10"
```

The pinned rule is:

1. If `B<=10`, `Q=0`, or `Rc+Rn=0`, requested `N=0`.
2. Otherwise, if `Rn=0` and `Rc>0`, request the deterministic probe
   `N=min(10,Q)` on `cnms`.
3. Otherwise request `N=floor(Q*Rn/(Rc+Rn)+0.5)` on `cnms`.
4. Effective `N=min(requested N,Q,max(0,150-current_cnms_user_jobs))`.

Read `ACTION_ID`, effective `N`, and `INDICES` from `P10` (never from the prior
artifact):

```bash
ACTION_ID="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["state_digest"])' "$P10")"
N="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["policy"]["effective_n"])' "$P10")"
INDICES="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(",".join(map(str,json.load(open(sys.argv[1]))["policy"]["selected_manifest_indices"])))' "$P10")"
```

If `N=0`, run no submission.  If `N>0`, require nonempty `INDICES` and use:

```bash
ssh cades "set -eu; B='$REMOTE_ROOT/fullobs_861expand_fig4_cnn_20260821'; cd \"\$B\"; \
 F4CNN861X_CONFIRM_SUBMIT=YES F4CNN861X_CHAIN_SUBMIT=YES \
 F4CNN861X_CNMS_USER_CAP=150 /usr/bin/python3.11 submit_fill.py \
 --submit --account cnms --limit '$N' --submission-kind rebalance_10m \
 --action-id '$ACTION_ID' --expected-indices '$INDICES'"
```

Write the receipt whether `N` is zero or positive:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --certificate "$CERT" --phase rebalance_10m \
  --previous-receipt "$R0" --policy-state "$P10" --output "$R10"
```

### +20-minute final decision and heartbeat gate

Wait at least another 600 seconds after `R10`, then capture:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --capture-policy-state --certificate "$CERT" --phase rebalance_20m \
  --previous-receipt "$R10" --account-cap 150 --output "$P20"
```

`counts_changed` is recomputed from the exact per-account pending and
running/completing counts in `R10` versus `P20`.  If it is false, `B<=10`,
`Q=0`, or the `cnms` probe has not started (`Rn=0`), requested `N=0`.  Only
when counts changed and `Rn>0` does the rule request
`floor(Q*Rn/(Rc+Rn)+0.5)`, again clipped by `Q` and live `cnms` capacity.
Never cancel/move a submitted `PENDING` job or reuse an archived template.

If effective `N>0`, submit the exact `P20` indices with
`--submission-kind rebalance_20m`, `--action-id P20.state_digest`, and
`--expected-indices`; otherwise submit nothing. Extract the three values from
`P20` explicitly:

```bash
ACTION_ID="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["state_digest"])' "$P20")"
N="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["policy"]["effective_n"])' "$P20")"
INDICES="$(~/.venvs/myenv/bin/python -c \
 'import json,sys; print(",".join(map(str,json.load(open(sys.argv[1]))["policy"]["selected_manifest_indices"])))' "$P20")"
```

The positive-`N` command is:

```bash
ssh cades "set -eu; B='$REMOTE_ROOT/fullobs_861expand_fig4_cnn_20260821'; cd \"\$B\"; \
 F4CNN861X_CONFIRM_SUBMIT=YES F4CNN861X_CHAIN_SUBMIT=YES \
 F4CNN861X_CNMS_USER_CAP=150 /usr/bin/python3.11 submit_fill.py \
 --submit --account cnms --limit '$N' --submission-kind rebalance_20m \
 --action-id '$ACTION_ID' --expected-indices '$INDICES'"
```

Then close and verify:

```bash
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" \
  --certificate "$CERT" --phase rebalance_20m \
  --previous-receipt "$R10" --policy-state "$P20" --output "$R20"
~/.venvs/myenv/bin/python "$PKG/handoff_receipt.py" --verify-receipt "$R20"
```

Terminal verification recursively rechecks every 0444 policy state and
receipt, certificate/manifest/plan/pin binding, 600-second checkpoint, policy
recomputation, immutable predecessor hashes/digests, append-only ledger prefix,
selected manifest indices and Slurm job IDs, `counts_changed`, requested and
effective `N`, and explicit `allowed_refill_accounts`.  Require
`rebalance_cycle_complete=true` and
`eligible_for_two_hour_expansion_heartbeat=true`.  The dedicated two-hour
expansion heartbeat may take ownership only after this exact `R20` path
verifies.  It may refill only accounts listed in the terminal
`allowed_refill_accounts`; do not infer permission from a mutable scheduler
snapshot.

## 6. Completion, immutable snapshot, and analysis

At 10,032/10,032 expansion COMPLETE with zero exact-name activity:

```bash
ssh cades 'B=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821; /usr/bin/python3.11 "$B/preflight.py" && /usr/bin/python3.11 "$B/analyze.py"'

~/.venvs/myenv/bin/python \
  /Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/finalize_fullobs_861expand_fig4_cnn.py \
  --check-only

~/.venvs/myenv/bin/python \
  /Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/finalize_fullobs_861expand_fig4_cnn.py
```

The finalizer requires 10,032 valid complement outputs, 300 byte-identical
reused outputs, exact 861-coordinate wedges, zero activity/anomalies, the
runtime pins, preflight, independent remote/local analysis agreement, and a
stable inventory across transfer. It installs only the new read-only snapshot:

`data/fullobs/fullobs_861twist_fig4_cnn_20260821`

Only after that immutable snapshot passes may the 12 full-861 values replace
the 25-panel values in the pointwise Eq. (10) table and Fig. 4(a). Manuscript
and Overleaf edits remain a separate, freshly synchronized, compile-verified
release step.
