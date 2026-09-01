#!/bin/bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs'
PINNED_SOLVER='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.x'
PINNED_SOURCE='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.cc'
PINNED_QBASIS='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/libqbasis.so'
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
[[ "${F4CNN25_CONFIRM_SUBMIT:-NO}" == YES ]] || { echo 'Submission disarmed; set F4CNN25_CONFIRM_SUBMIT=YES.' >&2; exit 2; }
[[ -x "${PINNED_SOLVER}" ]] || { echo 'Missing pinned observable executable.' >&2; exit 1; }
[[ -f "${PINNED_SOURCE}" ]] || { echo 'Missing pinned observable source.' >&2; exit 1; }
[[ "$(sha256sum "${PINNED_SOLVER}" | awk '{print $1}')" == 'b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b' ]] || { echo 'Pinned solver hash mismatch.' >&2; exit 1; }
[[ "$(sha256sum "${PINNED_SOURCE}" | awk '{print $1}')" == 'f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73' ]] || { echo 'Pinned source hash mismatch.' >&2; exit 1; }
[[ "$(sha256sum "${PINNED_QBASIS}" | awk '{print $1}')" == 'be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85' ]] || { echo 'Pinned qbasis library hash mismatch.' >&2; exit 1; }
count_jobs() {
  squeue -h -r -u "${USER}" -o '%a' | awk -v account="${ACCOUNT}" '$1 == account {n++} END {print n+0}'
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
exec 210>"${LOCK_FILE}"
flock -x 210
before="$(count_jobs)"
slots=$((CAP-before))
(( slots > 0 )) || { echo "${ACCOUNT}: user jobs=${before} already meet/exceed cap=${CAP}; submitted=0."; exit 0; }
submitted=0
while (( submitted < slots )); do
  next="$(find "${TEMPLATE_DIR}" -maxdepth 1 -type f -name 'job_f4cnn25_*.sh' | LC_ALL=C sort | head -n 1 || true)"
  [[ -n "${next}" ]] || break
  submit_one "${next}" || break
  submitted=$((submitted+1))
done
echo "${ACCOUNT}: user jobs before=${before}; cap=${CAP}; newly submitted=${submitted}."
