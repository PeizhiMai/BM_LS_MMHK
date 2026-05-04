#!/bin/bash
set -euo pipefail

ACCOUNT="${1:-}"
if [[ -z "${ACCOUNT}" ]]; then
  echo "Usage: $0 <account>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
LOG_FILE="${SCRIPT_DIR}/logs/submit.log"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"

mkdir -p "${TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${SCRIPT_DIR}/logs"

exec 200>"${LOCK_FILE}"
flock -x 200

next_job=$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job*.sh' | sort | head -n1 || true)
if [[ -z "${next_job}" ]]; then
  echo "$(date '+%F %T') [${ACCOUNT}] no unsubmitted jobs left" >> "${LOG_FILE}"
  exit 0
fi

base_name="$(basename "${next_job}")"
run_job="${SUBMITTED_DIR}/${base_name%.sh}_${ACCOUNT}.sh"

sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${ACCOUNT}/" "${next_job}" > "${run_job}"
chmod +x "${run_job}"

attempt=0
submitted=0
sbatch_out=""
while (( attempt < 5 )); do
  if sbatch_out=$(sbatch "${run_job}" 2>&1); then
    submitted=1
    break
  fi
  ((attempt++))
  sleep 10
done

if (( submitted == 1 )); then
  mv "${next_job}" "${SUBMITTED_DIR}/${base_name}.template"
  echo "$(date '+%F %T') [${ACCOUNT}] submitted ${run_job} -> ${sbatch_out}" >> "${LOG_FILE}"
else
  rm -f "${run_job}"
  echo "$(date '+%F %T') [${ACCOUNT}] FAILED to submit ${base_name}; sbatch output: ${sbatch_out}" >> "${LOG_FILE}"
  exit 1
fi
