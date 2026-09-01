#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
REPAIR_TEMPLATE_DIR="${SCRIPT_DIR}/repair_templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
REPAIR_SUBMITTED_DIR="${SCRIPT_DIR}/repair_submitted"
LOG_DIR="${SCRIPT_DIR}/logs"
LEDGER="${SCRIPT_DIR}/submission_ledger.tsv"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"
CCSD_CAP=${GAXR_CCSD_CAP:-990}
CNMS_CAP=${GAXR_CNMS_CAP:-330}
mkdir -p "${TEMPLATE_DIR}" "${REPAIR_TEMPLATE_DIR}" "${SUBMITTED_DIR}" "${REPAIR_SUBMITTED_DIR}" "${LOG_DIR}"

count_jobs() {
  local account="$1" self="${SLURM_JOB_ID:-}"
  squeue -h -u "${USER}" -o '%i|%j|%a|%Z' \
    | awk -F'|' -v account="${account}" -v target="${SCRIPT_DIR}" -v self="${self}" \
      '$1 != self && ($2 == "GAXR" || $2 == "GAXRR") && $3 == account && $4 == target {n++} END {print n+0}'
}

next_template() {
  local account="$1" item
  item="$(find "${REPAIR_TEMPLATE_DIR}" -maxdepth 1 -type f -name "repair_*_A${account}.sh" | LC_ALL=C sort | head -n1 || true)"
  if [[ -n "${item}" ]]; then printf 'repair|%s\n' "${item}"; return 0; fi
  item="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_gaxr_*.sh' | LC_ALL=C sort | head -n1 || true)"
  [[ -n "${item}" ]] && printf 'normal|%s\n' "${item}"
}

submit_one() {
  local template="$1" account="$2" kind="$3" base run out job_id task_index destination
  base="$(basename "${template}")"
  if [[ "${kind}" == repair ]]; then
    destination="${REPAIR_SUBMITTED_DIR}"
  else
    destination="${SUBMITTED_DIR}"
  fi
  run="${destination}/${base%.sh}_${account}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${account}/" "${template}" > "${run}"
  chmod +x "${run}"
  out="$(cd "${SCRIPT_DIR}" && sbatch "${run}" 2>&1)" || { rm -f "${run}"; return 1; }
  job_id="$(awk '/Submitted batch job/{print $4}' <<<"${out}")"
  [[ "${job_id}" =~ ^[0-9]+$ ]] || { rm -f "${run}"; return 1; }
  task_index="$(grep -E '^export GAXR_TASK_INDEX=' "${run}" | head -n1 | cut -d= -f2)"
  mv "${template}" "${destination}/${base%.sh}.template"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "${job_id}" "${account}" "${task_index}" "${kind}" "${run}" >> "${LEDGER}"
  echo "${out}"
}

[[ "${GAXR_CONFIRM_SUBMIT:-NO}" == YES ]] || { echo 'Submission disarmed; set GAXR_CONFIRM_SUBMIT=YES.' >&2; exit 2; }
[[ ! -e "${SCRIPT_DIR}/.priority_pause" ]] || { echo 'Batch is priority-paused.'; exit 0; }
ONLY="${1:-all}"
fill() {
  local account="$1" cap="$2" current slots submitted repairs normal record kind template
  repairs=0
  while true; do
    record="$(next_template "${account}" || true)"
    [[ -n "${record}" ]] || break
    kind="${record%%|*}"; template="${record#*|}"
    [[ "${kind}" == repair ]] || break
    submit_one "${template}" "${account}" "${kind}" || break
    repairs=$((repairs+1))
  done
  current="$(count_jobs "${account}")"; slots=$((cap-current)); normal=0
  (( slots < 0 )) && slots=0
  while (( normal < slots )); do
    record="$(next_template "${account}" || true)"
    [[ -n "${record}" ]] || break
    kind="${record%%|*}"; template="${record#*|}"
    submit_one "${template}" "${account}" "${kind}" || break
    normal=$((normal+1))
  done
  submitted=$((repairs+normal))
  echo "${account}: active after repair submission=${current}; ordinary quota=${cap}; repairs=${repairs}; ordinary=${normal}; total newly submitted=${submitted}."
}
exec 210>"${LOCK_FILE}"
flock -x 210
case "${ONLY}" in
  all) fill ccsd "${CCSD_CAP}"; fill cnms "${CNMS_CAP}" ;;
  ccsd) fill ccsd "${CCSD_CAP}" ;;
  cnms) fill cnms "${CNMS_CAP}" ;;
  *) exit 1 ;;
esac
