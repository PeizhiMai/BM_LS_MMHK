#!/bin/bash
#SBATCH -A ccsd
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J F4U80R3
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -o /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/logs/%x-%j.out
#SBATCH -e /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/logs/%x-%j.err
set -Eeuo pipefail
umask 077
BATCH='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730'
SOLVER='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/pinned_solver/Hubbard_sym_testobs_UV.x'
PINNED_SOURCE='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/pinned_solver/Hubbard_sym_testobs_UV.cc'
PINNED_LIBQBASIS='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/pinned_solver/libqbasis.so'
EXPECTED_SOLVER_SHA256='b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b'
EXPECTED_SOURCE_SHA256='f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73'
EXPECTED_QBASIS_SHA256='be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85'
REPLICA_INDEX='2'
REPLICA_ORDINAL='2'
SOURCE_INDEX='7'
SOURCE_JOB_ID='5619905'
U='80'; V='20'; KX='17'; KY='17'; SEED='3887639161'
CANONICAL='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
RESULT='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/results/replica_0002_r2_source7_L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
RESULT_NAME='L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
WORK="${BATCH}/work/replica_${REPLICA_INDEX}_${SLURM_JOB_ID:-manual}"
LOCK="${BATCH}/locks/replica_${REPLICA_INDEX}.lock"
INSTALL_TMP="${RESULT}.install.${SLURM_JOB_ID:-manual}.tmp"
cleanup() { unlink "${INSTALL_TMP}" 2>/dev/null || true; }
trap 'cleanup; exit 143' TERM INT
trap cleanup EXIT
mkdir -p "${WORK}"
exec 9>"${LOCK}"; flock -x 9
if [[ -s "${RESULT}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${RESULT}"; then echo 'replica already complete'; exit 0; fi
if [[ -e "${RESULT}" || -L "${RESULT}" ]]; then echo 'incomplete replica result conflict' >&2; exit 92; fi
if [[ -s "${CANONICAL}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${CANONICAL}"; then echo 'canonical became complete; replica skipped'; exit 0; fi
[[ "$(sha256sum "${SOLVER}" | awk '{print $1}')" == "${EXPECTED_SOLVER_SHA256}" ]] || exit 96
[[ "$(sha256sum "${PINNED_SOURCE}" | awk '{print $1}')" == "${EXPECTED_SOURCE_SHA256}" ]] || exit 95
[[ "$(sha256sum "${PINNED_LIBQBASIS}" | awk '{print $1}')" == "${EXPECTED_QBASIS_SHA256}" ]] || exit 97
cd "${WORK}"; ln -sfn "${SOLVER}" ./Hubbard_sym_testobs_UV.x
export OMP_NUM_THREADS=32 MKL_NUM_THREADS=32 QBASIS_LANCZOS_SEED="${SEED}"
export LD_LIBRARY_PATH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas3_20260823_002730/pinned_solver:/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}
resolved_qbasis="$(ldd "${SOLVER}" | awk '$1=="libqbasis.so" {print $3}')"
[[ "$(readlink -f "${resolved_qbasis}")" == "$(readlink -f "${PINNED_LIBQBASIS}")" ]] || exit 98
cat > run_metadata.txt <<EOF
replica_index ${REPLICA_INDEX}
replica_ordinal ${REPLICA_ORDINAL}
source_index ${SOURCE_INDEX}
source_job_id ${SOURCE_JOB_ID}
U ${U}
V ${V}
kx ${KX}
ky ${KY}
seed ${SEED}
solver_sha256 ${EXPECTED_SOLVER_SHA256}
source_sha256 ${EXPECTED_SOURCE_SHA256}
qbasis_sha256 ${EXPECTED_QBASIS_SHA256}
slurm_job_id ${SLURM_JOB_ID:-manual}
slurm_account ${SLURM_JOB_ACCOUNT:-unknown}
hostname $(hostname)
started_at $(date --iso-8601=seconds)
EOF
set +e
time ./Hubbard_sym_testobs_UV.x 8 8 "${KX}" "${KY}" 0 0 "${U}" "${V}" 0
rc=$?
set -e
LOCAL_RESULT="${WORK}/${RESULT_NAME}"
if ((rc!=0)) || [[ ! -s "${LOCAL_RESULT}" ]]; then echo "replica solver failed rc=${rc}" >&2; ((rc==0)) && rc=90; exit "${rc}"; fi
"${BATCH}/validate_output.sh" "${LOCAL_RESULT}" "${U}" "${V}"
if [[ -e "${RESULT}" || -L "${RESULT}" ]]; then echo 'replica install conflict' >&2; exit 93; fi
cp -p "${LOCAL_RESULT}" "${INSTALL_TMP}"; "${BATCH}/validate_output.sh" "${INSTALL_TMP}" "${U}" "${V}"; mv "${INSTALL_TMP}" "${RESULT}"; chmod 0444 "${RESULT}"
echo "finished_at $(date --iso-8601=seconds)" >> run_metadata.txt
echo "F4U80R3_RESULT COMPLETE replica_index=${REPLICA_INDEX} seed=${SEED} source_index=${SOURCE_INDEX}"
