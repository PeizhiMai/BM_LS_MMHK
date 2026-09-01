#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBMIT_NEXT="${SCRIPT_DIR}/submit_next_G_UV.sh"
JOB_TAG_REGEX="${JOB_TAG_REGEX:-GUV|G_UV|g_uv|guv}"
MAX_CCSD="${MAX_CCSD:-40}"
MAX_CNMS="${MAX_CNMS:-60}"
export JOB_TAG_REGEX MAX_CCSD MAX_CNMS

count_guv_jobs() {
  local account="$1"
  squeue -h -u "$USER" -A "$account" -o "%A|%j|%Z" \
    | awk -F'|' -v re="$JOB_TAG_REGEX" '($2 ~ re || $3 ~ re) {n++} END {print n+0}'
}

fill_account() {
  local account="$1"
  local cap="$2"
  local current slots submitted
  current="$(count_guv_jobs "$account")"
  slots=$((cap - current))
  submitted=0

  if (( slots <= 0 )); then
    echo "${account}: already has ${current} GUV jobs, cap=${cap}; submitting 0."
    return 0
  fi

  for ((i = 1; i <= slots; i++)); do
    bash "${SUBMIT_NEXT}" "${account}"
    submitted=$((submitted + 1))
  done

  echo "${account}: had ${current}, submitted ${submitted}, cap=${cap}."
}

fill_account ccsd "${MAX_CCSD}"
fill_account cnms "${MAX_CNMS}"

echo "Initial G-UV submission capped at: ${MAX_CCSD} to ccsd and ${MAX_CNMS} to cnms."
