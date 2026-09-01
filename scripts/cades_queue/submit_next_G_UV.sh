#!/bin/bash
set -euo pipefail

ACCOUNT="${1:-}"
if [[ -z "${ACCOUNT}" ]]; then
  echo "Usage: $0 <ccsd|cnms>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${TEMPLATE_DIR:-${SCRIPT_DIR}/templates}"
SUBMITTED_DIR="${SUBMITTED_DIR:-${SCRIPT_DIR}/submitted}"
LOG_FILE="${SCRIPT_DIR}/logs/submit_G_UV.log"
LOCK_FILE="${SCRIPT_DIR}/.queue_G_UV.lock"
JOB_TAG_REGEX="${JOB_TAG_REGEX:-GUV|G_UV|g_uv|guv}"
JOB_NAME="${JOB_NAME:-GUV}"
MAX_CCSD="${MAX_CCSD:-40}"
MAX_CNMS="${MAX_CNMS:-60}"

mkdir -p "${TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${SCRIPT_DIR}/logs"

cap_for_account() {
  case "$1" in
    ccsd) echo "${MAX_CCSD}" ;;
    cnms) echo "${MAX_CNMS}" ;;
    *) echo "Unknown account: $1" >&2; exit 1 ;;
  esac
}

count_guv_jobs_other_than_self() {
  local account="$1"
  local self_job_id="${SLURM_JOB_ID:-}"
  squeue -h -u "$USER" -A "$account" -o "%A|%j|%Z" \
    | awk -F'|' -v self="$self_job_id" -v re="$JOB_TAG_REGEX" \
        '$1 != self && ($2 ~ re || $3 ~ re) {n++} END {print n+0}'
}

render_job() {
  local template="$1"
  local account="$2"
  local output="$3"

  sed -E \
    -e "s/^#SBATCH[[:space:]]+-A[[:space:]]+.*/#SBATCH -A ${account}/" \
    -e "s/^#SBATCH[[:space:]]+-J[[:space:]]+.*/#SBATCH -J ${JOB_NAME}/" \
    "$template" > "$output"

  if ! grep -Eq '^#SBATCH[[:space:]]+-A[[:space:]]+' "$output"; then
    awk -v account="$account" 'NR==2{print "#SBATCH -A " account} {print}' "$output" > "${output}.tmp"
    mv "${output}.tmp" "$output"
  fi
  if ! grep -Eq '^#SBATCH[[:space:]]+-J[[:space:]]+' "$output"; then
    awk -v job_name="$JOB_NAME" 'NR==3{print "#SBATCH -J " job_name} {print}' "$output" > "${output}.tmp"
    mv "${output}.tmp" "$output"
  fi
}

exec 200>"${LOCK_FILE}"
flock -x 200

cap="$(cap_for_account "$ACCOUNT")"
# When called from a finishing Slurm job, exclude that current job from the count.
# This keeps the post-finish queue at or below the cap: ccsd<=40, cnms<=60.
current_other_count="$(count_guv_jobs_other_than_self "$ACCOUNT")"
if (( current_other_count >= cap )); then
  echo "$(date '+%F %T') [${ACCOUNT}] skip: ${current_other_count} other GUV jobs already >= cap ${cap}" >> "${LOG_FILE}"
  exit 0
fi

next_job="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job*.sh' | sort | head -n1 || true)"
if [[ -z "${next_job}" ]]; then
  echo "$(date '+%F %T') [${ACCOUNT}] no unsubmitted GUV jobs left" >> "${LOG_FILE}"
  exit 0
fi

base_name="$(basename "${next_job}")"
run_job="${SUBMITTED_DIR}/${base_name%.sh}_${ACCOUNT}.sh"

render_job "${next_job}" "${ACCOUNT}" "${run_job}"
chmod +x "${run_job}"

if sbatch_out="$(sbatch "${run_job}" 2>&1)"; then
  mv "${next_job}" "${SUBMITTED_DIR}/${base_name}.template"
  echo "$(date '+%F %T') [${ACCOUNT}] submitted ${run_job} -> ${sbatch_out}" >> "${LOG_FILE}"
else
  rm -f "${run_job}"
  echo "$(date '+%F %T') [${ACCOUNT}] FAILED to submit ${base_name}; sbatch output: ${sbatch_out}" >> "${LOG_FILE}"
  exit 1
fi
