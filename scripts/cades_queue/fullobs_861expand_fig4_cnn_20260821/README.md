# Conditional Fig. 4 `C_NN` 25→861 expansion package

This is a **local review package only**. It has not been copied to CADES and
has not submitted any job. The user's active parent goal supplies standing
authorization for the missing full-observable jobs, but remote action remains
strictly conditional on a real, valid `APPROVE_EXPANSION` certificate.

The exact gated transfer/materialization/submission/finalization sequence is in
`HANDOFF.md`.  `HEARTBEAT_PROMPT.md` is the dedicated two-hour monitor prompt;
it must not be activated before a real approval certificate has been remotely
revalidated, the batch has materialized, and the chained +10/+20-minute
handoff receipt is complete. `audit_status.py` is the pinned scheduler-aware
read-only audit installed into that batch; `handoff_receipt.py` captures fresh
pre-action policy states and post-action receipts and never mutates CADES.
Every artifact is exclusively created (no replace), fsynced, mode `0444`, and
recursively hash/digest verified before heartbeat eligibility.

## Exact scope

- Same twelve cases as the reviewed 25-panel campaign:
  `(20,0)`, `(20,2)`, `(20,3)`, `(20,4)`, `(20,4.5)`, `(40,6)`,
  `(80,0)`, `(80,4)`, `(80,8)`, `(80,12)`, `(80,16)`, `(80,18)`.
- Canonical wedge: all 861 integer coordinates satisfying
  `0 <= kx <= ky <= 40`.
- Reused source set: the exact 25 coordinates in the reviewed source manifest
  (`SHA-256 baa6f80f...381e5`), required to be 300/300 COMPLETE and bytewise
  identical to the decision certificate inventory.
- New set: the exact 836-coordinate set difference per case, or 10,032 jobs.
- Combined set: 861 coordinates per case, or 10,332 outputs.

`wedge_861.tsv` and `complement_836.tsv` are immutable coordinate contracts.
The generator rejects duplicates, overlap, missing coordinates, wrong order,
wrong quadrature metadata, seed collisions, result-name collisions, and any
pre-existing complement result path.

## Quantitative decision gate

`decision_gate.py` first runs the frozen reviewed analyzer against all 300
source outputs. Thus no certificate is possible before the exact source
manifest, provenance, solver hashes, twelve-case inventory, 25 coordinates per
case, COMPLETE markers, physical ranges, and four observable identities pass.
It independently reproduces the four U=40 full-861 controls.

The U=40 calibration has:

- maximum `|C_NN(25)-C_NN(861)| = 2.6920934537e-7`;
- maximum bias/panel-range ratio `0.0088256605`;
- maximum panel range `5.2291416567e-5`;
- maximum `|C_NN(symmetry weighted)-C_NN(primary)| = 1.4500127483e-6`;
- maximum bias/symmetry-diagnostic ratio `0.2683572052`;
- maximum uninflated propagated Eq. (10) shift `1.2331524853e-6`.

For each of the twelve new cases the gate forms

```text
B_C = 5 * max(max_U40_abs_bias,
              max_U40_abs_bias_to_range_ratio * target_panel_range,
              max_U40_abs_bias_to_symmetry_ratio
                * |target_symmetry_weighted - target_primary|)
B_s = |2 * (2U-V)/(U-V)| * B_C
```

The factor five is a conservative transfer factor, not a statistical
confidence interval. The primary materiality threshold is the fixed,
dimensionless `B_s >= 5e-4`. This is half of a `0.001` slope
reporting/figure increment, so a shift at the threshold can change a value at
that declared precision. Expansion is approved if **any** target meets one of
these predeclared conditions:

1. conservative propagated `|delta s_NN| >= 5e-4`;
2. panel range is greater than four times the largest U=40 control range; or
3. absolute symmetry-weighted-minus-primary diagnostic is greater than four
   times the largest U=40 control diagnostic.

The two fourfold rules are operational out-of-calibration guards. They are not
confidence intervals and do not claim that the U=40 controls formally bound
the other interaction families.

The dimensionless Eq. (10) residual and its dimensionless ratio to `B_s` are
recorded under `secondary_eq10_diagnostics`, but neither participates in the
decision. The raw GZ curve-fit RMSE is an energy-unit curve-shape misfit, not a
coefficient uncertainty. It is therefore never read, compared with `B_s`, or
used as a denominator. A persistent regression test changes the RMSE by 24
orders of magnitude and requires an identical decision certificate.

Otherwise the certificate says `NO_EXPANSION`: the calibrated quadrature
bias stays below the fixed slope tolerance and both target quadrature
diagnostics remain inside their operational calibration envelopes. Exit status
is `0` for `APPROVE_EXPANSION`, `3` for a valid `NO_EXPANSION` decision, and
`2` for incomplete or invalid inputs.

The five U=40 calibration maxima are an exact numerical contract, not values
trusted from arbitrary certificate fields. At materialization the generator
also hashes the actual 300 source outputs, parses their `<C1_NN>` values, and
independently rederives every target panel range and symmetry diagnostic. It
then regenerates the bias envelopes and trigger logic. Consequently, a
coherently hand-edited `APPROVE_EXPANSION` certificate cannot authorize a
batch whose decision-driving values differ from the exact source bytes.

After the immutable 25-panel snapshot exists:

```bash
~/.venvs/myenv/bin/python \
  scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821/decision_gate.py \
  --campaign-root data/fullobs/fullobs_25twist_fig4_cnn_20260820 \
  --analysis-output-dir tmp/fig4_cnn_861_decision_analysis \
  --certificate tmp/fig4_cnn_861_decision.json
```

Both output paths must be new. Nothing is overwritten.

## Default dry run

The generator defaults to a read-only plan audit and contains no generator-side
`sbatch` call:

```bash
~/.venvs/myenv/bin/python \
  scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821/generate_batch.py
```

Reviewed dry-run result:

- expansion rows: 10,032;
- unique expansion seeds: 10,032, with zero overlap with the 300 source seeds;
- coordinate/result overlap with reused rows: zero;
- deterministic plan SHA-256:
  `368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e`.

## Conditional CADES materialization (not run)

Only an `APPROVE_EXPANSION` certificate can pass this command:

```bash
/usr/bin/python3.11 generate_batch.py \
  --materialize \
  --decision-certificate /absolute/path/fig4_cnn_861_decision.json
```

Intended fresh remote batch:

`/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821`

Fresh job names are `F4CNN861X` and reserved repair name `F4CNN861R`;
templates start with `job_f4cnn861x_`.

Materialization is itself submission-free. It copies and rechecks the same
reviewed solver, source, and `libqbasis.so`, records the 10k Lanczos setting and
unchanged `4x4, Nup=Ndn=8, Q=(0,0), t'=0` physics, and creates a generated
`submit_fill.py` that still defaults to a dry run. Actual submission is
double-armed with both `--submit` and `F4CNN861X_CONFIRM_SUBMIT=YES`.

Before materialization succeeds, it pins both the complete manifest byte hash
and its semantic plan digest, writes an aggregate `TEMPLATE_SHA256SUMS` ledger
for all 10,032 template contents, pins the generated preflight program, and
runs that preflight once. Before every later `sbatch`, `submit_fill.py` verifies
and runs the pinned preflight, rechecks the manifest and aggregate template
ledger, and verifies the selected template bytes plus rendered Bash syntax.
Manifest or template tampering therefore refuses before submission.
Each selected template is atomically moved to a claim path before `sbatch`; an
ambiguous successful submission leaves that blocking claim in place rather
than returning the template to the queue and risking a duplicate job.
The optional `--limit N` argument permits an exact, positive, deterministic
second-account rebalance count while still clipping to the total-user cap.
Selection filters a fixed global round-robin order across all twelve physics
cases rather than restarting from a contiguous manifest block on every call.
Every actual submission also requires an explicit
`submission_kind` and `action_id`; the ledger records both plus the selection
rank. Handoff submissions additionally require the exact expected manifest
indices from the immutable policy state, so a live race fails before `sbatch`.

The three policy states record and replay `P`, `Q`, `B=P+Q`, `Rc`, `Rn`, the
per-account pending/running counts, total-user capacity input, Boolean
`counts_changed`, requested/effective `N`, target account, rule branch, and
interleaved indices. The three receipts prove the earlier ledger is an
unchanged prefix and bind action indices to returned Slurm job IDs. Only the
terminal schema-2 receipt can set heartbeat eligibility, and it carries an
explicit `allowed_refill_accounts` list.

Materialization now creates an explicit incomplete marker. A caught exception
removes the newly created batch tree (the generator has no submission call),
while an uncatchable interruption leaves the marker to block the generated
submit helper. A successful materialization installs the scheduler-aware audit
and an empty headered repair ledger before removing the marker.

The eventual full-861 analyzer uses the same exchange and trapezoidal endpoint
weights (total weight 1600) for both `C_NN_full_861` and the explicitly named
`C_NN_full_quadrature_weighted_population_std` diagnostic. Its summary and
provenance outputs are add-only/idempotent: a byte-identical rerun is accepted,
whereas a differing pre-existing output is never overwritten. The dedicated
local finalizer independently validates and snapshots all 10,332 raw outputs.

Read-only certificate validation, with no source access or writes, is:

```bash
~/.venvs/myenv/bin/python \
  scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821/generate_batch.py \
  --verify-certificate --decision-certificate /absolute/path/decision.json
```

## Persistent tests

```bash
~/.venvs/myenv/bin/python -m unittest \
  internal_tests/test_fullobs_861expand_fig4_cnn.py
```

The tests cover exact cardinality, set reconstruction, collisions, deterministic
seeds, plan digest, pinned hashes, wrong/no-decision refusal, both quantitative
decision branches, symmetry-domain exits, GZ-RMSE decision invariance, default
no-write dry run, exact-calibration and coherent-certificate tampering,
manifest/template byte tampering, quadrature-weighted spread, and rendered
Bash/Python syntax. They also cover read-only certificate verification,
transaction cleanup after an injected materialization failure, incomplete-marker
submission refusal, interleaved cross-case selection, classified/action-bound
submission rows, exclusive fsynced 0444 artifacts, full three-phase policy
recomputation/receipt chaining, and the installed deep-audit hash.
`PACKAGE_SHA256SUMS` pins every reviewed package file except the ledger itself.
