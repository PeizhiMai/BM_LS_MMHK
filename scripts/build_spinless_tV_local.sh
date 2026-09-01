#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/.codex_tmp/spinless_local/bin/Spinless_tV_sym_E0.x"
QBASIS_ROOT="/Users/cosdis/Downloads/ED/ED_Zhentao/installs"
MKL_ROOT="/opt/intel/oneapi/mkl/latest"
TBB_ROOT="/opt/intel/oneapi/tbb/latest"

mkdir -p "$(dirname "${OUT}")"
/usr/local/bin/g++ -std=c++17 -Wall -O3 -funroll-loops -m64 \
  -DMKL_ILP64 -fopenmp \
  -I"${QBASIS_ROOT}/include" -I"${MKL_ROOT}/include" -I/usr/local/include \
  "${ROOT}/code/Spinless_tV_sym_E0.cc" \
  -L"${QBASIS_ROOT}/lib" -lqbasis -larpackILP64 -fopenmp \
  -L"${MKL_ROOT}/lib" -lmkl_intel_ilp64 -lmkl_tbb_thread -lmkl_core \
  -L"${TBB_ROOT}/lib" -lpthread -ltbb -lm -ldl \
  -Wl,-rpath,"${QBAS_ROOT:-${QBASIS_ROOT}}/lib" \
  -Wl,-rpath,"${MKL_ROOT}/lib" -Wl,-rpath,"${TBB_ROOT}/lib" \
  -o "${OUT}"

# The locally installed qbasis library has a relative install name.  Replace it
# in this executable so Rosetta can resolve it without relying on shell state.
install_name_tool -change libqbasis.so "${QBASIS_ROOT}/lib/libqbasis.so" "${OUT}"
echo "Built ${OUT}"

