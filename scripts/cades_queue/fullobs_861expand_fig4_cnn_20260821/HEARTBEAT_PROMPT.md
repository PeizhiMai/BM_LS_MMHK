# Dedicated two-hour expansion heartbeat prompt

The user's active parent goal supplies standing authorization to submit the
missing full-observable jobs, conditional on a valid real `APPROVE_EXPANSION`
certificate. No additional user confirmation is needed. Keep this prompt
paused before materialization. The existing automation may switch to it only
after remote certificate revalidation, clean materialization, the first
authorized `ccsd` fill, the one-time +10/+20-minute rebalance cycle, and a
verified terminal `rebalance_20m` receipt from `handoff_receipt.py`. Schedule:
every two hours. Do not keep the 25-panel prompt active after this one takes
ownership of expansion monitoring.

---

Monitor only the authorized CADES Fig. 4 full-observable 25→861 complement
campaign. Before acting, read
`/Users/cosdis/.codex/skills/cades-account-rebalance/SKILL.md` and the pinned
handoff at
`/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821/HANDOFF.md`.
Use lowercase SSH host `cades`, remote `/usr/bin/python3.11`, and local
`~/.venvs/myenv/bin/python`. Touch no unrelated jobs or canonical results.
At the first expansion wake, read the exact terminal receipt path recorded by
the transition turn (never select one by an ambiguous wildcard), run
`handoff_receipt.py --verify-receipt PATH`, and require
`eligible_for_two_hour_expansion_heartbeat=true` and
`rebalance_cycle_complete=true`. Verification must recursively pass schema 2,
all six regular non-symlink 0444 policy-state/receipt artifacts, exclusive
no-overwrite predecessor hashes, the recomputed `P,Q,B,Rc,Rn`, capacity,
`counts_changed`, requested/effective `N`, bound append-only ledger deltas,
interleaved selected manifest indices/Slurm job IDs, and explicit
`allowed_refill_accounts`. Thereafter preserve that immutable chain and report
its terminal SHA-256/state digest and allowed-account list in every update.

Remote batch `B` is exactly:
`/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_861expand_fig4_cnn_20260821`.
Normal/repair job names are exactly `F4CNN861X`/`F4CNN861R`. Scope is exactly
10,032 new targets = 12 cases × 836 complement coordinates, plus 300 immutable
reused outputs, giving 10,332 combined outputs. Require semantic plan SHA
`368caa133e96fe10b453968fa6f00eab96b0e862d6013b8b79df70212f7cec9e`
and manifest SHA
`53fc88369d637916e5f33a0511f45ddeb97e60e72ed3a0a173bde03b5edc0b31`.
Pinned solver/source/libqbasis hashes must remain 3/3 matching.

At every wake first refuse all mutations if `B/MATERIALIZATION_INCOMPLETE` or
any `submitted/*.claim` exists. Verify the manifest hash and run:

```text
/usr/bin/python3.11 $B/audit_status.py --batch $B \
 --job-name F4CNN861X --job-name F4CNN861R \
 --pin-file PINNED_SHA256SUMS --require-pins \
 --submission-log repair_submission.tsv --since 2026-08-21 \
 --expect-targets 10032 --expect-per-case 836 \
 --expect-account ccsd --expect-account cnms \
 --expect-partition burst --expect-cpus 32 --expect-nodes 1 \
 --expect-memory 100G --expect-time-limit 08:00:00 \
 --write-report $B/analysis/latest_monitor.json
```

Report valid COMPLETE/10032, RUNNING, PENDING, UNSUBMITTED, FAILED, INVALID,
INCOMPLETE, and UNKNOWN by `(U,V)`; template/archive/claim counts; exact-name
account/state counts; pins; anomalies; scheduler errors; and repair candidates.
UNSUBMITTED is normal while self-refilling work is active.

Never submit, cancel, or repair if scheduler access fails, a pin/manifest/
resource/identity/cardinality anomaly exists, an exact-name active job is
unmapped, a target has any RUNNING/COMPLETING/PENDING job, or an incomplete
canonical result exists. Never delete or overwrite a canonical result. Never
cancel RUNNING, COMPLETING, or COMPLETED work. Never bypass an ambiguous claim.

Normal jobs self-refill under the total-user cap of 150/account. If and only if
the exact campaign has zero active jobs, pending templates remain, there are no
claims/anomalies/failures, and every target is either valid COMPLETE or
UNSUBMITTED, prove no target/lock conflict and refill `ccsd` once with:

```text
F4CNN861X_CONFIRM_SUBMIT=YES F4CNN861X_CHAIN_SUBMIT=YES \
F4CNN861X_CCSD_USER_CAP=150 \
 /usr/bin/python3.11 $B/submit_fill.py --submit --account ccsd \
 --submission-kind heartbeat_refill \
 --action-id heartbeat-$(date -u +%Y%m%dT%H%M%SZ)-$$
```

Then immediately re-audit. Do not start a duplicate wave. Honor the one-time
+10/+20-minute account-rebalance record made at launch.  That launch rule is an
add-only adaptation for the per-template self-refilling architecture: it uses
the backlog `B=PENDING+UNSUBMITTED`, may seed at most 10 deterministic
still-unsubmitted templates on `cnms` only while `ccsd` is already running,
and never cancels/moves a submitted `PENDING` job or reuses an archived
template. Do not recompute or churn the account split on later heartbeats.
Refill only an account explicitly named by the verified terminal receipt's
`allowed_refill_accounts`. If it contains `cnms`, a later zero-activity refill
may use the same classified `heartbeat_refill` command with
`--account cnms`, a fresh action ID, and `F4CNN861X_CNMS_USER_CAP=150`;
otherwise keep primary-account refill only. Never infer account permission
from `submission_accounts` or a later mutable scheduler snapshot.

For a terminal failure inspect exact `sacct`, stdout, stderr, result path,
locks, and every submission ledger record. Auto-repair at most once and only
for an unambiguous transient infrastructure terminal state such as NODE_FAIL,
BOOT_FAIL, PREEMPTED, or REVOKED; require canonical result absent, zero active
jobs for the target, a fresh unused uint32 seed, identical pinned runtime,
physics/resources, isolated work path, job name `F4CNN861R`, and an atomic
headered `repair_submission.tsv` record mapping old/new job IDs and result.
Do not auto-repair TIMEOUT, OUT_OF_MEMORY, numerical/Lanczos failure, identity
failure, hash/provenance failure, cancellation of unclear origin, or
COMPLETED-without-valid-output. Report these for diagnosis. Never auto-repeat a
repair and never launch repair pairs.

At 10,032/10,032 valid expansion COMPLETE, require zero exact-name activity,
zero anomalies/warnings/repairs/claims, then run `$B/preflight.py` and the
idempotent `$B/analyze.py`. Require 12 rows, 861 coordinates and quadrature
weight 1600 per case, and its provenance JSON. Run the local immutable
finalizer first with `--check-only`, then without it. Require the read-only
snapshot
`/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/data/fullobs/fullobs_861twist_fig4_cnn_20260821`,
10,332 hash-verified raw outputs, remote/local summary agreement, and exact
runtime/manifest/plan pins. Never overwrite or use force; if a staging path
already exists, stop for manual inspection.

After successful finalization report all 12 full-861 `C_NN(U,V)` and signed
Eq. (10) predictions, their quadrature-spread diagnostics (never SEM), exact
snapshot/analysis/provenance paths, and pause this heartbeat. Do not edit Fig.
4, manuscript text, or Overleaf from the heartbeat; those require the separate
fresh-Overleaf synchronization and release workflow in the parent task.
