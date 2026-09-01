#!/usr/bin/env python3
"""Fourier-analyze the all-momentum U=40, V=0 occupation data.

The fullobs output stores the spin-summed occupation n(k) on the irreducible
0 <= kx <= ky <= pi wedge.  We restore the 80x80 periodic Brillouin-zone grid
using reflection and kx<->ky symmetry, then inverse Fourier transform it.  The
Fourier coefficient of spin-summed n(k) is twice the per-spin density matrix
g_r=<c^dagger_{i sigma} c_{i+r,sigma}>.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path("results/fullobs_U40_observable_rows_20260723_091307.csv.gz")
DEFAULT_OUTPUT = Path("results/u40v0_real_space_coherence_from_fullobs_nk.csv")
DISPLACEMENTS = [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (2, 2), (3, 2), (4, 1)]


def restore_grid(rows: pd.DataFrame, grid_size: int = 80) -> np.ndarray:
    lookup = {
        tuple(sorted((int(row.kx), int(row.ky)))): float(row.n_k)
        for row in rows.itertuples(index=False)
    }
    grid = np.empty((grid_size, grid_size), dtype=float)
    for ix in range(grid_size):
        ax = min(ix, grid_size - ix)
        for iy in range(grid_size):
            ay = min(iy, grid_size - iy)
            grid[iy, ix] = lookup[tuple(sorted((ax, ay)))]
    return grid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = pd.read_csv(args.input)
    rows = data[(data["U"] == 40.0) & (data["V"] == 0.0)]
    if len(rows) != 861:
        raise RuntimeError(f"Expected 861 irreducible-wedge rows, found {len(rows)}")

    grid = restore_grid(rows)
    size = grid.shape[0]
    momenta = 2.0 * np.pi * np.arange(size) / size
    output_rows = []
    for rx, ry in DISPLACEMENTS:
        phase = np.exp(
            1j * (momenta[None, :] * rx + momenta[:, None] * ry)
        )
        coefficient = np.mean(grid * phase)
        output_rows.append(
            {
                "U": 40.0,
                "V": 0.0,
                "rx": rx,
                "ry": ry,
                "manhattan_distance": abs(rx) + abs(ry),
                "same_sublattice": (rx + ry) % 2 == 0,
                "spin_summed_fourier_coefficient_real": coefficient.real,
                "spin_summed_fourier_coefficient_imag": coefficient.imag,
                "g_per_spin_real": coefficient.real / 2.0,
                "g_per_spin_imag": coefficient.imag / 2.0,
            }
        )

    output = pd.DataFrame(output_rows)
    g_nn = float(output.loc[(output.rx == 1) & (output.ry == 0), "g_per_spin_real"].iloc[0])
    output["abs_g_over_abs_g_NN"] = np.abs(output["g_per_spin_real"]) / abs(g_nn)
    output["source_file"] = str(args.input)
    output["restored_grid_size"] = size
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(output.to_string(index=False))
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
