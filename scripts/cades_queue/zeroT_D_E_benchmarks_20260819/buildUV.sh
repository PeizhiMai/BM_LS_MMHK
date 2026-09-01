#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd)"
if [[ "$(hostname -f)" == *ornl.gov ]]; then
    ROOT="/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/literature_benchmarks_20260819"
fi
TMPDIR="${ROOT}/.tmp_build"
mkdir -p "${TMPDIR}" "${ROOT}/bin"
export TMPDIR

CXX="${CXX:-/sw/cades-open/gcc/12.2.0/bin/g++}"
CXXFLAGS="-std=c++17 -Wall -Wextra -O3 -funroll-loops -m64 -DMKL_ILP64 -march=native"
INCLUDES="-I/home/9pm/installs/include -I/home/9pm/intel/oneapi/mkl/2024.2/include"
LIBDIRS="-L/home/9pm/installs/lib -L/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64 -L/home/9pm/intel/oneapi/tbb/latest/lib"
LIBS="-lqbasis -larpackILP64 -Wl,--no-as-needed -lmkl_intel_ilp64 -lmkl_tbb_thread -lmkl_core -lpthread -ltbb -lm -ldl"

SRC="${ROOT}/source/Hubbard_sym_E0_D_UV.cc"
OUT="${ROOT}/bin/Hubbard_sym_E0_D_UV.x"
echo "Compiling ${SRC} -> ${OUT}"
${CXX} ${CXXFLAGS} ${INCLUDES} "${SRC}" ${LIBDIRS} ${LIBS} -o "${OUT}"
echo "Build finished: ${OUT}"
