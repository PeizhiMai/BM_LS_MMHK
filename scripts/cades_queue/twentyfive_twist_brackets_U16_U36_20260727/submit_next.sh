#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/submit.log"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"
ACCOUNT="${1:-ccsd}"
case "${ACCOUNT}" in
  ccsd) CAP="${OBS25T_CCSD_USER_CAP:-150}" ;;
  cnms) CAP="${OBS25T_CNMS_USER_CAP:-150}" ;;
  *) exit 0 ;;
esac
count_jobs_excluding_self() {
  local self="${SLURM_JOB_ID:-}"
  squeue -h -u "${USER}" -o '%i|%a' | awk -F'|' -v account="${ACCOUNT}" -v self="${self}" '$1 != self && $2 == account {n++} END {print n+0}'
}
submit_one() {
  local template="$1" base run sbout
  base="$(basename "${template}")"
  run="${SUBMITTED_DIR}/${base%.sh}_${ACCOUNT}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${ACCOUNT}/" "${template}" > "${run}"
  chmod +x "${run}"
  if sbout="$(sbatch "${run}" 2>&1)"; then
    mv "${template}" "${SUBMITTED_DIR}/${base%.sh}.template"
    printf '%s	%s	%s	%s
' "$(date '+%F %T')" "${ACCOUNT}" "${run}" "${sbout}" >> "${LOG_FILE}"
    return 0
  fi
  rm -f "${run}"
  printf '%s	%s	FAILED	%s	%s
' "$(date '+%F %T')" "${ACCOUNT}" "${base}" "${sbout}" >> "${LOG_FILE}"
  return 1
}
exec 211>"${LOCK_FILE}"
flock -x 211
current="$(count_jobs_excluding_self)"
(( current < CAP )) || exit 0
next="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_obs25t_*.sh' | LC_ALL=C sort | head -n 1 || true)"
[[ -n "${next}" ]] || exit 0
submit_one "${next}"
