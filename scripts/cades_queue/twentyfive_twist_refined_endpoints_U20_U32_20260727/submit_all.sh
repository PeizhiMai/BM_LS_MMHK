#!/bin/bash
set -euo pipefail
BATCH='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/twentyfive_twist_refined_endpoints_U20_U32_20260727'
LOG="$BATCH/submission.tsv"
if [[ ! -s "$LOG" ]]; then
  printf 'job_id\taccount\tscript\n' > "$LOG"
fi
shopt -s nullglob
for script in "$BATCH"/templates/*.sh; do
  account=$(awk '$1=="#SBATCH" && $2=="-A" {print $3; exit}' "$script")
  output=$(sbatch "$script")
  job_id=${output##* }
  printf '%s\t%s\t%s\n' "$job_id" "$account" "$script" >> "$LOG"
  mv "$script" "$BATCH/submitted/"
done
