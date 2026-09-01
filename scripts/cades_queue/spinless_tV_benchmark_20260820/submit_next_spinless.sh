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
    *) echo "Unsupported account: ${ACCOUNT}" >&2; exit 1 ;;
esac
if [[ "${SLTV_CONFIRM_SUBMIT:-NO}" != "YES" ]]; then
    echo "Submission is disarmed; set SLTV_CONFIRM_SUBMIT=YES after approval." >&2
    exit 2
fi
[[ ! -e "${ROOT}/state/PAUSE" ]] || exit 0

count_excluding_self() {
    local self="${SLURM_JOB_ID:-}"
    squeue -h -u "${USER}" -o '%A|%a' |
        awk -F'|' -v account="${ACCOUNT}" -v self="${self}" \
            '$1 != self && $2 == account {count++} END {print count+0}'
}

exec 211>"${LOCK_FILE}"
flock -x 211
current="$(count_excluding_self)"
(( current < CAP )) || exit 0
next="$(find "${TEMPLATES}" -maxdepth 1 -type f -name 'job_sltv_*.sh' | sort | head -n 1 || true)"
[[ -n "${next}" ]] || exit 0
base="$(basename "${next}")"
run_job="${SUBMITTED}/${base%.sh}_${ACCOUNT}.sh"
sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${ACCOUNT}/" "${next}" > "${run_job}"
chmod +x "${run_job}"
for attempt in 1 2 3 4 5; do
    if output="$(sbatch "${run_job}" 2>&1)"; then
        mv "${next}" "${SUBMITTED}/${base%.sh}.template"
        printf '%s [%s] %s -> %s\n' "$(date '+%F %T')" "${ACCOUNT}" "${run_job}" "${output}" >> "${LOG_FILE}"
        exit 0
    fi
    sleep 5
done
rm -f "${run_job}"
printf '%s [%s] FAILED %s: %s\n' "$(date '+%F %T')" "${ACCOUNT}" "${base}" "${output}" >> "${LOG_FILE}"
exit 1
