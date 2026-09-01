#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J __JOB_NAME__
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -D /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827
#SBATCH -o /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827/logs/%x-%j.out
#SBATCH -e /home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827/logs/%x-%j.err

set -uo pipefail
BATCH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/Gcalpath_axis_refinement_UV_20260827
RAW="${BATCH}/raw"
export GAXR_TASK_INDEX=__TASK_INDEX__
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED=__SEED__
export LD_LIBRARY_PATH=/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}
refilled=0
refill() {
  if (( refilled == 0 )); then
    refilled=1
    bash "${BATCH}/submit_next.sh" "${SLURM_JOB_ACCOUNT:-ccsd}" || true
  fi
}
trap refill EXIT
trap 'exit 143' TERM INT

gp="${RAW}/__GP__"
gh="${RAW}/__GH__"
if /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/validate_pair.py" --gp "${gp}" --gh "${gh}" --U __U__ --V __V__ --tp __TP__; then
  echo "GAXR_RESULT ALREADY_VALID task=${GAXR_TASK_INDEX}"
  exit 0
fi

work='__WORK__'
rm -rf "${work}"
mkdir -p "${work}"
cd "${work}"
set +e
time "${BATCH}/Square_Hubbard_tbc_G_calculation_UV.x" 8 8 __KX__ __KY__ 0 0 __U__ __V__ __TP__
rc=$?
set -e
if (( rc == 0 )); then
  /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/install_pair.py" --gp "${work}/__GP__" --gh "${work}/__GH__" \
    --dest "${RAW}" --U __U__ --V __V__ --tp __TP__ || rc=$?
fi
if (( rc == 0 )) && /sw/cades-open/python/3.10.14/bin/python3 "${BATCH}/validate_pair.py" --gp "${gp}" --gh "${gh}" --U __U__ --V __V__ --tp __TP__; then
  echo "GAXR_RESULT COMPLETE task=${GAXR_TASK_INDEX} U=__U__ V=__V__ tp=__TP__ kx=__KX__ ky=__KY__ seed=__SEED__"
else
  echo "GAXR_RESULT FAILED rc=${rc} task=${GAXR_TASK_INDEX} U=__U__ V=__V__ tp=__TP__ kx=__KX__ ky=__KY__ seed=__SEED__" >&2
  (( rc == 0 )) && rc=90
fi
exit "${rc}"
