#!/bin/bash
# Read-only target/scheduler audit.  The sole write is atomic replacement of
# analysis/latest_monitor.json with the audit report.
set -Eeuo pipefail
BATCH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_u20v5_fig4_cnn_20260821
exec /usr/bin/python3.11 "$BATCH/audit_status.py" \
  --batch "$BATCH" \
  --job-name F4C20V5 \
  --job-name F4C20V5R \
  --pin-file PINNED_SHA256SUMS \
  --submission-log repair_submission.tsv \
  --require-pins \
  --since 2026-08-21 \
  --expect-targets 25 \
  --expect-per-case 25 \
  --expect-account ccsd \
  --expect-partition burst \
  --expect-cpus 32 \
  --expect-nodes 1 \
  --expect-memory 100G \
  --expect-time-limit 08:00:00 \
  --write-report "$BATCH/analysis/latest_monitor.json"
