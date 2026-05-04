#!/bin/bash
set -euo pipefail

file_counter=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMIT_NEXT_SCRIPT="${SCRIPT_DIR}/submit_next_job.sh"

mkdir -p "${TEMPLATE_DIR}" "${SCRIPT_DIR}/logs" "${SCRIPT_DIR}/submitted"

# Optional reset so regeneration starts clean.
rm -f "${TEMPLATE_DIR}"/job*.sh

job_header='#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J dqmc
#SBATCH --mem=100G
#SBATCH -t 8:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=cosdis123@gmail.com

cd /home/9pm/ED_qbasis/qbasis/bin/tp0U4
export OMP_NUM_THREADS=32
'

# Nup: 1..5, Ndn in {Nup, Nup+1}
for ((Nup = 1; Nup <= 5; Nup++)); do
  for ndn_offset in 0 1; do
    Ndn=$((Nup + ndn_offset))

    # i: 0..19, j: i..19
    for ((i = 0; i <= 19; i += 1)); do
      for ((j = i; j <= 19; j += 1)); do
        job_file="${TEMPLATE_DIR}/job$(printf '%06d' "${file_counter}").sh"

        {
          printf "%s\n" "${job_header}"
          echo "output_file=\"L4x4Nup${Nup}Ndn${Ndn}f${i}x${j}_gse.dat\""
          echo "if [[ -f \"\${output_file}\" ]]; then"
          echo "  echo \"Skipping existing \${output_file}\""
          echo "  job_rc=0"
          echo "else"
          # Keep original behavior: one command per job with k=j.
          echo "  time ./Hubbard_sym_test4x4gse_allq.x ${Nup} ${Ndn} ${i} ${j}"
          echo "  job_rc=\$?"
          echo "fi"
          echo "bash \"${SUBMIT_NEXT_SCRIPT}\" \"\${SLURM_JOB_ACCOUNT:-__ACCOUNT__}\""
          echo "exit \${job_rc}"
        } > "${job_file}"

        chmod +x "${job_file}"
        ((file_counter++))
      done
    done
  done
done

echo "Generated $((file_counter - 1)) template jobs in ${TEMPLATE_DIR}."
