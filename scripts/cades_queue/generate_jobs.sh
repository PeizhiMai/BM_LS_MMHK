#!/bin/bash
set -euo pipefail

file_counter=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
SUBMIT_NEXT_SCRIPT="${SCRIPT_DIR}/submit_next_job.sh"
mkdir -p "${TEMPLATE_DIR}" "${SCRIPT_DIR}/logs" "${SCRIPT_DIR}/submitted"

job_header='#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J dqmc
#SBATCH --mem=100G
#SBATCH -t 2:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=cosdis123@gmail.com

cd /home/9pm/ED_qbasis/qbasis/bin/tp0U4/Spipit0
export OMP_NUM_THREADS=32
'

for ((Nupi = 1; Nupi <= 7; Nupi++)); do
  Nup=${Nupi}

  for ndn_offset in 0 1; do
    Ndn=$((Nupi + ndn_offset))

    for ((i = 0; i <= 40; i += 1)); do
      for ((j = i; j <= 40; j += 1)); do
        data_file="./Qmins_sym/Nup${Nup}Ndn${Ndn}_Qmins_sym.dat"

        if [[ -f "${data_file}" ]]; then
          q_lines=$(awk "/f${i}x${j}:/{flag=1; next} /^f[0-9]+x[0-9]+:/{flag=0} flag && /Q =/" "${data_file}")

          if [[ -n "${q_lines}" ]]; then
            while IFS= read -r q_line; do
              qx=$(echo "${q_line}" | sed -E 's/.*\(([0-9]+),[[:space:]]*([0-9]+)\).*/\1/')
              qy=$(echo "${q_line}" | sed -E 's/.*\(([0-9]+),[[:space:]]*([0-9]+)\).*/\2/')

              result_file="./L4x4Nup${Nup}Ndn${Ndn}f${i}x${j}Q${qx}x${qy}_SpiSpi.dat"
              if [[ ! -f "${result_file}" ]]; then
                job_file="${TEMPLATE_DIR}/job$(printf '%06d' "${file_counter}").sh"
                {
                  printf "%s\n" "${job_header}"
                  echo "time ./Hubbard_sym_testSpipit0.x ${Nup} ${Ndn} ${i} ${j} ${qx} ${qy}"
                  echo "job_rc=\$?"
                  echo "bash \"${SUBMIT_NEXT_SCRIPT}\" \"\${SLURM_JOB_ACCOUNT:-__ACCOUNT__}\""
                  echo "exit \${job_rc}"
                } > "${job_file}"

                chmod +x "${job_file}"
                ((file_counter++))
              else
                echo "Skipping: Nup=${Nup}, Ndn=${Ndn}, i=${i}, j=${j}, qx=${qx}, qy=${qy} (result exists)."
              fi
            done <<< "${q_lines}"
          else
            echo "Warning: No Q values for f${i}x${j} in ${data_file}. Using Q=(0,0)."
            job_file="${TEMPLATE_DIR}/job$(printf '%06d' "${file_counter}").sh"
            {
              printf "%s\n" "${job_header}"
              echo "time ./Hubbard_sym_testSpipit0.x ${Nup} ${Ndn} ${i} ${j} 0 0"
              echo "job_rc=\$?"
              echo "bash \"${SUBMIT_NEXT_SCRIPT}\" \"\${SLURM_JOB_ACCOUNT:-__ACCOUNT__}\""
              echo "exit \${job_rc}"
            } > "${job_file}"

            chmod +x "${job_file}"
            ((file_counter++))
          fi
        else
          echo "Warning: Missing data file ${data_file}. Using Q=(0,0)."
          job_file="${TEMPLATE_DIR}/job$(printf '%06d' "${file_counter}").sh"
          {
            printf "%s\n" "${job_header}"
            echo "time ./Hubbard_sym_testSpipit0.x ${Nup} ${Ndn} ${i} ${j} 0 0"
            echo "job_rc=\$?"
            echo "bash \"${SUBMIT_NEXT_SCRIPT}\" \"\${SLURM_JOB_ACCOUNT:-__ACCOUNT__}\""
            echo "exit \${job_rc}"
          } > "${job_file}"

          chmod +x "${job_file}"
          ((file_counter++))
        fi
      done
    done
  done
done

echo "Generated $((file_counter - 1)) template jobs in ${TEMPLATE_DIR}."
