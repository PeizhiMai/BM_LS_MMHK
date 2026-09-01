#!/bin/bash
#SBATCH -A ccsd
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J OBS1M32
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -o /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/one_twist_refine_U32_20260727/logs/%x-%j.out
#SBATCH -e /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/one_twist_refine_U32_20260727/logs/%x-%j.err

set -uo pipefail
cd /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED=3324284817
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}

result='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U32V8.015tp0f2x8Q0x0_obs.dat'
if [[ -s "${result}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${result}"; then
  echo 'OBS1M32_RESULT ALREADY_COMPLETE U=32 V=8.015 kx=2 ky=8'
  exit 0
fi

rm -f "${result}"
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 2 8 0 0 32 8.015 0
job_rc=$?
set -e

if (( job_rc == 0 )) && [[ -s "${result}" ]] && grep -Eq '^status[[:space:]]+COMPLETE[[:space:]]*$' "${result}"; then
  echo 'OBS1M32_RESULT COMPLETE U=32 V=8.015 kx=2 ky=8 seed=3324284817'
else
  echo 'OBS1M32_RESULT FAILED rc='"${job_rc}"' U=32 V=8.015 kx=2 ky=8 seed=3324284817' >&2
  (( job_rc == 0 )) && job_rc=90
fi
exit "${job_rc}"
