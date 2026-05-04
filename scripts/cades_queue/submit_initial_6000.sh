#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
LOG_FILE="${SCRIPT_DIR}/logs/submit.log"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"

mkdir -p "${TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${SCRIPT_DIR}/logs"

exec 200>"${LOCK_FILE}"
flock -x 200

# Reset queue state on each run:
# 1) move archived templates back to template pool
# 2) remove old account-specific rendered scripts
shopt -s nullglob
for archived_template in "${SUBMITTED_DIR}"/job*.template; do
  base_name="$(basename "${archived_template}" .template)"
  mv "${archived_template}" "${TEMPLATE_DIR}/${base_name}.sh"
done
rm -f "${SUBMITTED_DIR}"/job*_{ccsd,cnms}.sh
shopt -u nullglob

mapfile -t all_templates < <(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job*.sh' | sort)
total_templates=${#all_templates[@]}

if (( total_templates == 0 )); then
  echo "No templates found in ${TEMPLATE_DIR}. Run generate_jobs.sh first."
  exit 1
fi

ccsd_count=$(( total_templates < 3000 ? total_templates : 3000 ))
remaining=$(( total_templates - ccsd_count ))
cnms_count=$(( remaining < 3000 ? remaining : 3000 ))

submit_one() {
  local template="$1"
  local account="$2"
  local base_name run_job sbatch_out

  base_name="$(basename "${template}")"
  run_job="${SUBMITTED_DIR}/${base_name%.sh}_${account}.sh"

  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${account}/" "${template}" > "${run_job}"
  chmod +x "${run_job}"

  if sbatch_out=$(sbatch "${run_job}" 2>&1); then
    mv "${template}" "${SUBMITTED_DIR}/${base_name}.template"
    echo "$(date '+%F %T') [${account}] submitted ${run_job} -> ${sbatch_out}" >> "${LOG_FILE}"
    return 0
  fi

  rm -f "${run_job}"
  echo "$(date '+%F %T') [${account}] FAILED to submit ${base_name}; sbatch output: ${sbatch_out}" >> "${LOG_FILE}"
  return 1
}

submitted_ccsd=0
for ((idx = 0; idx < ccsd_count; idx++)); do
  if ! submit_one "${all_templates[idx]}" ccsd; then
    echo "Stopped on ccsd failure at index ${idx}."
    break
  fi
  submitted_ccsd=$((submitted_ccsd + 1))
  if (( submitted_ccsd % 200 == 0 )); then
    echo "Submitted ${submitted_ccsd}/${ccsd_count} to ccsd"
  fi
done

submitted_cnms=0
for ((idx = ccsd_count; idx < ccsd_count + cnms_count; idx++)); do
  if ! submit_one "${all_templates[idx]}" cnms; then
    echo "Stopped on cnms failure at index ${idx}."
    break
  fi
  submitted_cnms=$((submitted_cnms + 1))
  if (( submitted_cnms % 200 == 0 )); then
    echo "Submitted ${submitted_cnms}/${cnms_count} to cnms"
  fi
done

echo "Initial submission complete: ${submitted_ccsd} to ccsd and ${submitted_cnms} to cnms."
