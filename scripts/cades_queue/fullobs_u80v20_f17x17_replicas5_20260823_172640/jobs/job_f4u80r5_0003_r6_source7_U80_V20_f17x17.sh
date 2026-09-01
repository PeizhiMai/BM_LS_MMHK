#!/bin/bash
#SBATCH -A ccsd
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J F4U80R5
#SBATCH --mem=100G
#SBATCH -t 47:00:00
#SBATCH --signal=B:TERM@300
#SBATCH -o /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/logs/%x-%j.out
#SBATCH -e /home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/logs/%x-%j.err
set -Eeuo pipefail
umask 077
BATCH='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640'
SOLVER="${BATCH}/pinned_solver/Hubbard_sym_testobs_UV.x"
PINNED_SOURCE="${BATCH}/pinned_solver/Hubbard_sym_testobs_UV.cc"
PINNED_LIBQBASIS="${BATCH}/pinned_solver/libqbasis.so"
BUILT_PIN_LEDGER="${BATCH}/BUILT_PIN_SHA256SUMS"
REPLICA_INDEX='3'; REPLICA_ORDINAL='6'; SOURCE_INDEX='7'; SOURCE_JOB_ID='5619905'
U='80'; V='20'; KX='17'; KY='17'; SEED='3952085789'; MAXIT='50000'
CANONICAL='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
RESULT='/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/results/replica_0003_r6_source7_L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
RESULT_NAME='L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat'
WORK="${BATCH}/work/replica_${REPLICA_INDEX}_${SLURM_JOB_ID:-manual}"
LOCK="${BATCH}/locks/replica_${REPLICA_INDEX}.lock"
INSTALL_TMP="${RESULT}.install.${SLURM_JOB_ID:-manual}.tmp"
cleanup() { unlink "${INSTALL_TMP}" 2>/dev/null || true; }
trap 'cleanup; exit 143' TERM INT
trap cleanup EXIT
canonical_state() {
 if [[ ! -e "${CANONICAL}" && ! -L "${CANONICAL}" ]]; then echo absent; return; fi
 if [[ -f "${CANONICAL}" && ! -L "${CANONICAL}" && -s "${CANONICAL}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${CANONICAL}"; then echo complete; else echo conflict; fi
}
pin_hash() { awk -v rel="$1" '$2==rel {n++;h=$1} END{if(n!=1)exit 2;print h}' "${BUILT_PIN_LEDGER}"; }
[[ -f "${BUILT_PIN_LEDGER}" && ! -L "${BUILT_PIN_LEDGER}" ]] || exit 99
EXPECTED_SOLVER_SHA256="$(pin_hash pinned_solver/Hubbard_sym_testobs_UV.x)"
EXPECTED_SOURCE_SHA256="$(pin_hash pinned_solver/Hubbard_sym_testobs_UV.cc)"
EXPECTED_QBASIS_SHA256="$(pin_hash pinned_solver/libqbasis.so)"
[[ "${EXPECTED_SOURCE_SHA256}" == 'fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b' ]] || exit 95
[[ -d "${BATCH}/results" && ! -L "${BATCH}/results" && -d "${BATCH}/work" && ! -L "${BATCH}/work" && -d "${BATCH}/locks" && ! -L "${BATCH}/locks" ]] || { echo 'batch-local directories missing/unsafe' >&2; exit 91; }
mkdir -p "${WORK}"
exec 9>"${LOCK}"; flock -x 9
if [[ -e "${RESULT}" || -L "${RESULT}" ]]; then
 if [[ -f "${RESULT}" && ! -L "${RESULT}" ]] && "${BATCH}/validate_output.sh" "${RESULT}" "${U}" "${V}"; then echo 'replica already complete and valid'; exit 0; fi
 echo 'incomplete/invalid replica result conflict' >&2; exit 92
fi
case "$(canonical_state)" in complete) echo 'canonical became complete; replica skipped'; exit 0;; conflict) echo 'canonical path exists but is not a safe complete regular file; replica refused' >&2; exit 94;; esac
for spec in "${SOLVER}:${EXPECTED_SOLVER_SHA256}:96" "${PINNED_SOURCE}:${EXPECTED_SOURCE_SHA256}:95" "${PINNED_LIBQBASIS}:${EXPECTED_QBASIS_SHA256}:97"; do
 IFS=: read -r pinned expected code <<<"${spec}"
 [[ -f "${pinned}" && ! -L "${pinned}" ]] || exit "${code}"
 [[ "$(sha256sum "${pinned}" | awk '{print $1}')" == "${expected}" ]] || exit "${code}"
done
cd "${WORK}"; ln -sfn "${SOLVER}" ./Hubbard_sym_testobs_UV.x
export OMP_NUM_THREADS=32 MKL_NUM_THREADS=32 OMP_PROC_BIND=close OMP_PLACES=cores QBASIS_LANCZOS_SEED="${SEED}"
export LD_LIBRARY_PATH=/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_u80v20_f17x17_replicas5_20260823_172640/pinned_solver:/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}
resolved_qbasis="$(ldd "${SOLVER}" | awk '$1=="libqbasis.so" {print $3}')"
[[ -n "${resolved_qbasis}" && "$(readlink -f "${resolved_qbasis}")" == "$(readlink -f "${PINNED_LIBQBASIS}")" ]] || exit 98
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
seed_mechanism QBASIS_LANCZOS_SEED_strict_uint32
maxit ${MAXIT}
solver_sha256 ${EXPECTED_SOLVER_SHA256}
source_sha256 ${EXPECTED_SOURCE_SHA256}
qbasis_sha256 ${EXPECTED_QBASIS_SHA256}
original_solver_sha256 b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b
original_source_sha256 f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73
original_qbasis_sha256 be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85
slurm_job_id ${SLURM_JOB_ID:-manual}
slurm_account ${SLURM_JOB_ACCOUNT:-unknown}
hostname $(hostname)
started_at $(date --iso-8601=seconds)
EOF
set +e
/usr/bin/time -v stdbuf -oL -eL ./Hubbard_sym_testobs_UV.x 8 8 "${KX}" "${KY}" 0 0 "${U}" "${V}" 0 2>&1 | tee solver.combined.log
rc=${PIPESTATUS[0]}
set -e
if [[ "$(grep -Fxc "QBASIS_LANCZOS_SEED = ${SEED}" solver.combined.log || true)" != 1 ]]; then echo 'effective-seed proof missing/nonunique' >&2; exit 89; fi
LOCAL_RESULT="${WORK}/${RESULT_NAME}"
if ((rc!=0)) || [[ ! -s "${LOCAL_RESULT}" ]]; then echo "replica solver failed rc=${rc}" >&2; ((rc==0)) && rc=90; exit "${rc}"; fi
"${BATCH}/validate_output.sh" "${LOCAL_RESULT}" "${U}" "${V}"
case "$(canonical_state)" in complete) echo 'canonical completed during replica; validated work result retained without result install'; exit 0;; conflict) echo 'canonical path appeared during replica; validated work result retained without result install' >&2; exit 94;; esac
if [[ -e "${RESULT}" || -L "${RESULT}" ]]; then echo 'replica install conflict' >&2; exit 93; fi
cp -p -- "${LOCAL_RESULT}" "${INSTALL_TMP}"; "${BATCH}/validate_output.sh" "${INSTALL_TMP}" "${U}" "${V}"; mv -- "${INSTALL_TMP}" "${RESULT}"; chmod 0444 "${RESULT}"
echo "finished_at $(date --iso-8601=seconds)" >> run_metadata.txt; chmod 0444 run_metadata.txt solver.combined.log
echo "F4U80R5_RESULT COMPLETE replica_index=${REPLICA_INDEX} replica_ordinal=${REPLICA_ORDINAL} seed=${SEED} source_index=${SOURCE_INDEX} maxit=${MAXIT}"
