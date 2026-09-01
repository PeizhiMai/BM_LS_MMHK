#!/bin/bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMITTED_DIR="${SCRIPT_DIR}/submitted"
RAW_LOG="${SCRIPT_DIR}/logs/submit.log"
TABLE_LOG="${SCRIPT_DIR}/submission.tsv"
LOCK_FILE="${SCRIPT_DIR}/.queue.lock"
MANIFEST="${SCRIPT_DIR}/manifest.tsv"
ACCOUNT="${1:-ccsd}"
case "${ACCOUNT}" in
  ccsd) CAP="${F4CNN25_CCSD_USER_CAP:-150}" ;;
  cnms) CAP="${F4CNN25_CNMS_USER_CAP:-150}" ;;
  *) echo "Unsupported account: ${ACCOUNT}" >&2; exit 1 ;;
esac
count_jobs_excluding_self() {
  local self="${SLURM_JOB_ID:-}"
  squeue -h -r -u "${USER}" -o '%i|%a' |
    awk -F'|' -v account="${ACCOUNT}" -v self="${self}" '$1 != self && $2 == account {n++} END {print n+0}'
}
submit_one() {
  local template="$1" base run sbout job_id idx row
  base="$(basename "${template}")"
  run="${SUBMITTED_DIR}/${base%.sh}_${ACCOUNT}.sh"
  sed "s/^#SBATCH -A __ACCOUNT__$/#SBATCH -A ${ACCOUNT}/" "${template}" > "${run}"
  chmod 700 "${run}"
  if sbout="$(sbatch "${run}" 2>&1)"; then
    job_id="$(awk '/Submitted batch job/ {print $4}' <<<"${sbout}")"
    [[ "${job_id}" =~ ^[0-9]+$ ]] || { echo "Could not parse sbatch output: ${sbout}" >&2; rm -f "${run}"; return 1; }
    idx="$(sed -n 's/^INDEX='"'"'\([0-9][0-9]*\)'"'"'$/\1/p' "${run}")"
    row="$(awk -F'\t' -v i="${idx}" 'NR>1 && $1==i {print $1"\t"$2"\t"$3"\t"$7"\t"$8; exit}' "${MANIFEST}")"
    [[ -n "${row}" ]] || { echo "Manifest lookup failed for index ${idx}" >&2; return 1; }
    mv "${template}" "${SUBMITTED_DIR}/${base%.sh}.template"
    printf '%s	%s	%s	%s
' "$(date '+%F %T')" "${ACCOUNT}" "${run}" "${sbout}" >> "${RAW_LOG}"
    printf '%s	%s	%s	%s	%s	%s
' "$(date --iso-8601=seconds)" "${ACCOUNT}" "${job_id}" "${row}" "${run}" "$(awk -F'\t' -v i="${idx}" 'NR>1 && $1==i {print $11; exit}' "${MANIFEST}")" >> "${TABLE_LOG}"
    return 0
  fi
  rm -f "${run}"
  printf '%s	%s	FAILED	%s	%s
' "$(date '+%F %T')" "${ACCOUNT}" "${base}" "${sbout}" >> "${RAW_LOG}"
  return 1
}
exec 211>"${LOCK_FILE}"
flock -x 211
current="$(count_jobs_excluding_self)"
(( current < CAP )) || exit 0
next="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_f4cnn25_*.sh' | LC_ALL=C sort | head -n 1 || true)"
[[ -n "${next}" ]] || exit 0
submit_one "${next}"
