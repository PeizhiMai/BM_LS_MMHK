#!/usr/bin/env python3
"""Validate the lean 16-MMHK E0/D executable against production observables."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-dir",
        type=Path,
        default=root / "data/zeroT_D_E_mmhk/solver_validation_20260819",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=root / "data/zeroT_D_E_mmhk/fullobs_reference_20260819",
    )
    parser.add_argument("--results-dir", type=Path, default=root / "results")
    return parser.parse_args()


def parse(path: Path) -> dict:
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split(None, 1)
        if len(fields) != 2:
            continue
        key, value = fields
        try:
            values[key] = float(value)
        except ValueError:
            values[key] = value
    return values


def find_one(directory: Path, pattern: str) -> Path:
    matches = list(directory.rglob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one {pattern!r} under {directory}, found {len(matches)}")
    return matches[0]


def lean_path(directory: Path, U: str, V: str, kx: int, ky: int) -> Path:
    return find_one(directory, f"L4x4Nup8Ndn8U{U}V{V}tp0f{kx}x{ky}Q0x0_E0D.dat")


def main() -> None:
    args = parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    # The production full-observable files evaluate the same Hamiltonian and
    # the same real-space double-occupancy estimator.
    for U, V in [("2", "0.5"), ("4", "1")]:
        lean_file = lean_path(args.validation_dir, U, V, 0, 0)
        reference_file = find_one(
            args.reference_dir,
            f"L4x4Nup8Ndn8U{U}V{V}tp0f0x0Q0x0_obs.dat",
        )
        lean = parse(lean_file)
        reference = parse(reference_file)
        e_diff = float(lean["E0"] - reference["E0"])
        d_diff = float(lean["D"] - reference["<ni_upni_dn>"])
        rows.extend(
            [
                {
                    "test": "lean_vs_fullobs_E0",
                    "U": float(U),
                    "V": float(V),
                    "kx": 0,
                    "ky": 0,
                    "lean_value": lean["E0"],
                    "reference_value": reference["E0"],
                    "difference": e_diff,
                    "tolerance": 1e-8,
                    "passed": abs(e_diff) <= 1e-8,
                },
                {
                    "test": "lean_vs_fullobs_D",
                    "U": float(U),
                    "V": float(V),
                    "kx": 0,
                    "ky": 0,
                    "lean_value": lean["D"],
                    "reference_value": reference["<ni_upni_dn>"],
                    "difference": d_diff,
                    "tolerance": 1e-8,
                    "passed": abs(d_diff) <= 1e-8,
                },
            ]
        )

    # Hellmann--Feynman check: D=(1/N)dE0/dU at fixed V and mixed momentum.
    delta = 0.001
    for kx, ky in [(0, 0), (20, 20)]:
        lower = parse(lean_path(args.validation_dir, "3.999", "1", kx, ky))
        upper = parse(lean_path(args.validation_dir, "4.001", "1", kx, ky))
        center = parse(lean_path(args.validation_dir, "4", "1", kx, ky))
        derivative_per_site = (upper["E0"] - lower["E0"]) / (2.0 * delta * 16.0)
        difference = derivative_per_site - center["D"]
        rows.append(
            {
                "test": "Hellmann_Feynman_D",
                "U": 4.0,
                "V": 1.0,
                "kx": kx,
                "ky": ky,
                "lean_value": center["D"],
                "reference_value": derivative_per_site,
                "difference": difference,
                "tolerance": 5e-5,
                "passed": abs(difference) <= 5e-5,
            }
        )

    free = parse(lean_path(args.validation_dir, "0", "0", 0, 0))
    difference = float(free["D"] - 0.25)
    rows.append(
        {
            "test": "free_point_D",
            "U": 0.0,
            "V": 0.0,
            "kx": 0,
            "ky": 0,
            "lean_value": free["D"],
            "reference_value": 0.25,
            "difference": difference,
            "tolerance": 1e-8,
            "passed": abs(difference) <= 1e-8,
        }
    )

    output = pd.DataFrame(rows)
    output.to_csv(args.results_dir / "zeroT_D_E_solver_validation.csv", index=False)
    report = {
        "all_passed": bool(output["passed"].all()),
        "tests": int(len(output)),
        "max_lean_fullobs_absolute_difference": float(
            output[output["test"].str.startswith("lean_vs_fullobs")]["difference"].abs().max()
        ),
        "max_Hellmann_Feynman_absolute_difference": float(
            output[output["test"] == "Hellmann_Feynman_D"]["difference"].abs().max()
        ),
    }
    (args.results_dir / "zeroT_D_E_solver_validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(output.to_string(index=False))
    if not report["all_passed"]:
        raise SystemExit("One or more lean-solver validation tests failed")


if __name__ == "__main__":
    main()
