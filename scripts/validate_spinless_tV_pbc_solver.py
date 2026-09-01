#!/usr/bin/env python3
"""Validate the full-momentum spinless 16-MMHK ground-state solver."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


CASES = ((0, 0), (7, 13), (20, 20), (0, 40))


def parse(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2:
            result[fields[0]] = fields[1]
    return result


def exact_free_energy(kx: int, ky: int) -> float:
    fx = kx * math.pi / 40.0 + 0.00001
    fy = ky * math.pi / 40.0 + 0.00001
    levels = sorted(
        -2.0
        * (
            math.cos(2.0 * math.pi * nx / 4.0 + fx)
            + math.cos(2.0 * math.pi * ny / 4.0 + fy)
        )
        for nx in range(4)
        for ny in range(4)
    )
    return sum(levels[:8])


def run(
    binary: Path,
    output_dir: Path,
    V: float,
    kx: int,
    ky: int,
    q: int,
    seed: int,
    subdir: str = "default",
):
    qlabel = "Qall" if q == -1 else f"Q{q}x{q}"
    filename = f"L4x4N8V{V:g}tp0f{kx}x{ky}{qlabel}_E0_spinless.dat"
    destination_dir = output_dir / subdir
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    if destination.is_file() and "status\tCOMPLETE" in destination.read_text():
        return destination
    env = os.environ.copy()
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "MKL_DYNAMIC": "FALSE",
            "OMP_DYNAMIC": "FALSE",
            "DYLD_LIBRARY_PATH": (
                "/Users/cosdis/Downloads/ED/ED_Zhentao/installs/lib:"
                "/opt/intel/oneapi/mkl/latest/lib:"
                "/opt/intel/oneapi/tbb/latest/lib:"
                + env.get("DYLD_LIBRARY_PATH", "")
            ),
        }
    )
    with tempfile.TemporaryDirectory(prefix="spinless_validate_") as temporary:
        completed = subprocess.run(
            [
                str(binary),
                "8",
                str(kx),
                str(ky),
                str(q),
                str(q),
                f"{V:g}",
                "0",
                str(seed),
            ],
            cwd=temporary,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        source = Path(temporary) / filename
        if completed.returncode != 0 or not source.is_file():
            raise RuntimeError(completed.stdout[-12000:])
        shutil.copy2(source, destination)
    return destination


def main():
    root = Path(__file__).resolve().parents[1]
    binary = (root / ".codex_tmp/spinless_local/bin/Spinless_tV_sym_E0.x").resolve()
    output_dir = root / "data/spinless_tV_mmhk/pbc_validation_20260820"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not binary.is_file():
        raise FileNotFoundError(binary)

    free_checks = []
    for index, (kx, ky) in enumerate(CASES, start=1):
        path = run(
            binary,
            output_dir,
            0.0,
            kx,
            ky,
            -1,
            320_000_000 + index,
            subdir="free",
        )
        row = parse(path)
        solver = float(row["E0"])
        exact = exact_free_energy(kx, ky)
        free_checks.append(
            {
                "kx": kx,
                "ky": ky,
                "solver_E0": solver,
                "exact_E0": exact,
                "absolute_error": abs(solver - exact),
                "passed": abs(solver - exact) < 1.0e-10,
            }
        )

    all_q_a = parse(
        run(
            binary,
            output_dir,
            1.0,
            7,
            13,
            -1,
            320_000_101,
            subdir="seed_a",
        )
    )
    all_q_b = parse(
        run(
            binary,
            output_dir,
            1.0,
            7,
            13,
            -1,
            320_000_102,
            subdir="seed_b",
        )
    )
    fixed_q = parse(
        run(
            binary,
            output_dir,
            1.0,
            7,
            13,
            0,
            320_000_103,
            subdir="fixed_q00",
        )
    )
    ea = float(all_q_a["E0"])
    eb = float(all_q_b["E0"])
    efixed = float(fixed_q["E0"])

    report = {
        "solver": "spinless 16-MMHK t-V, N=8 on 16 mixing orbitals",
        "hamiltonian": "-t sum_NN(cdag_i c_j+h.c.) + V sum_NN n_i n_j",
        "momentum_treatment": "complete fixed-N basis; minimizes all 16 total-momentum sectors",
        "basis_dimension": int(all_q_a["basis_dimension"]),
        "free_checks": free_checks,
        "all_free_checks_passed": all(row["passed"] for row in free_checks),
        "seed_repeat": {
            "E0_seed_a": ea,
            "E0_seed_b": eb,
            "absolute_difference": abs(ea - eb),
            "passed": abs(ea - eb) < 1.0e-10,
        },
        "fixed_sector_audit": {
            "V": 1.0,
            "kx": 7,
            "ky": 13,
            "E0_all_momentum_sectors": ea,
            "E0_fixed_Q00": efixed,
            "all_minus_fixed": ea - efixed,
            "passed_variational_order": ea <= efixed + 1.0e-12,
        },
    }
    output = root / "results/spinless_tV_pbc_solver_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    if not (
        report["all_free_checks_passed"]
        and report["seed_repeat"]["passed"]
        and report["fixed_sector_audit"]["passed_variational_order"]
    ):
        raise SystemExit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
