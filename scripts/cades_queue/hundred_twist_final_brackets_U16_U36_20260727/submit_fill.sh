#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/submit.log"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"
ACCOUNT="${1:-ccsd}"
case "${ACCOUNT}" in
  ccsd) CAP="${OBS100_CCSD_USER_CAP:-150}" ;;
  cnms) CAP="${OBS100_CNMS_USER_CAP:-150}" ;;
  *) echo "Unsupported account: ${ACCOUNT}" >&2; exit 1 ;;
esac
[[ "${OBS100_CONFIRM_SUBMIT:-NO}" == YES ]] || { echo 'Submission disarmed; set OBS100_CONFIRM_SUBMIT=YES.' >&2; exit 2; }
[[ -x "${RUN_DIR}/Hubbard_sym_testobs_UV.x" ]] || { echo 'Missing observable executable.' >&2; exit 1; }
[[ ! "${RUN_DIR}/Hubbard_sym_testobs_UV.cc" -nt "${RUN_DIR}/Hubbard_sym_testobs_UV.x" ]] || { echo 'Source is newer than executable; rebuild first.' >&2; exit 1; }
mkdir -p "${TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${LOG_DIR}"
count_jobs() {
  squeue -h -u "${USER}" -o '%i|%a' | awk -F'|' -v account="${ACCOUNT}" '$2 == account {n++} END {print n+0}'
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
exec 210>"${LOCK_FILE}"
flock -x 210
before="$(count_jobs)"
slots=$((CAP-before))
submitted=0
while (( submitted < slots )); do
  next="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_obs100_*.sh' | LC_ALL=C sort | head -n 1 || true)"
  [[ -n "${next}" ]] || break
  submit_one "${next}" || break
  submitted=$((submitted+1))
done
echo "${ACCOUNT}: user jobs before=${before}; cap=${CAP}; newly submitted=${submitted}."
