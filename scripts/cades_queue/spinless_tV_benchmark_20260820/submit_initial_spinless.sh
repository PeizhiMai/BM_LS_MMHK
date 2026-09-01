#!/bin/bash
set -euo pipefail

ROOT="/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/spinless_tV_benchmark_20260820"
TEMPLATES="${ROOT}/templates"
SUBMITTED="${ROOT}/submitted"
LOG_FILE="${ROOT}/logs/submit.log"
LOCK_FILE="${ROOT}/state/queue.lock"
ACCOUNT="${1:-ccsd}"

case "${ACCOUNT}" in
    ccsd) CAP="${SLTV_CCSD_USER_CAP:-150}" ;;
    cnms) CAP="${SLTV_CNMS_USER_CAP:-150}" ;;
    *) echo "Usage: $0 [ccsd|cnms]" >&2; exit 1 ;;
esac

if [[ "${SLTV_CONFIRM_SUBMIT:-NO}" != "YES" ]]; then
    echo "Submission is disarmed; set SLTV_CONFIRM_SUBMIT=YES after approval." >&2
    exit 2
fi
[[ -x "${ROOT}/bin/Spinless_tV_sym_E0.x" ]] || { echo "Missing executable" >&2; exit 1; }
[[ ! "${ROOT}/source/Spinless_tV_sym_E0.cc" -nt "${ROOT}/bin/Spinless_tV_sym_E0.x" ]] || {
    echo "Source is newer than executable; rebuild first." >&2
    exit 1
}
[[ ! -e "${ROOT}/state/PAUSE" ]] || { echo "Submission paused." >&2; exit 3; }
mkdir -p "${TEMPLATES}" "${SUBMITTED}" "${ROOT}/logs" "${ROOT}/state"

count_account_jobs() {
    squeue -h -u "${USER}" -o '%A|%a' |
        awk -F'|' -v account="${ACCOUNT}" '$2 == account {count++} END {print count+0}'
}

submit_one() {
    local template="$1" base run_job output attempt
    base="$(basename "${template}")"
    run_job="${SUBMITTED}/${base%.sh}_${ACCOUNT}.sh"
    sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${ACCOUNT}/" "${template}" > "${run_job}"
    chmod +x "${run_job}"
    for attempt in 1 2 3 4 5; do
        if output="$(sbatch "${run_job}" 2>&1)"; then
            mv "${template}" "${SUBMITTED}/${base%.sh}.template"
            printf '%s [%s] %s -> %s\n' "$(date '+%F %T')" "${ACCOUNT}" "${run_job}" "${output}" >> "${LOG_FILE}"
            return 0
        fi
        sleep 5
    done
    rm -f "${run_job}"
    printf '%s [%s] FAILED %s: %s\n' "$(date '+%F %T')" "${ACCOUNT}" "${base}" "${output}" >> "${LOG_FILE}"
    return 1
}

exec 210>"${LOCK_FILE}"
flock -x 210
current="$(count_account_jobs)"
slots=$((CAP - current))
submitted=0
if (( slots > 0 )); then
    for ((index=0; index<slots; index++)); do
        next="$(find "${TEMPLATES}" -maxdepth 1 -type f -name 'job_sltv_*.sh' | sort | head -n 1 || true)"
        [[ -n "${next}" ]] || break
        submit_one "${next}" || break
        submitted=$((submitted + 1))
    done
fi
echo "${ACCOUNT}: user jobs before=${current}, cap=${CAP}, submitted=${submitted}."
