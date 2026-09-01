#!/usr/bin/env python3
"""Decompose the U-only Luttinger-surface scale into strong-coupling moment terms.

The script uses the first Lanczos coefficient of the Gh/Gp continued fractions to
form a two-pole/first-moment approximation.  It also diagonalizes the 4x4
Heisenberg model in Sz=0 to show that the asymptotic scale equals 4*C1, where
C1=<S_i.S_j> on a nearest-neighbor bond.
"""
from __future__ import annotations

from pathlib import Path
import itertools
import math
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
from reproduce_luttinger_figures import default_k_path, parse_green_file  # noqa: E402

DATA = ROOT / "data/Gcalpath/Lanczos_raw_data"
OUT = ROOT / "results/uonly_asymptotic_scale_decomposition.csv"


def eps0(kx_i: int, ky_i: int) -> float:
    d = math.pi / 40.0
    return -2.0 * (math.cos(kx_i * d) + math.cos(ky_i * d))


def fit_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    mask = np.isfinite(x) & np.isfinite(y) & (np.abs(x) > 1e-10)
    A = np.column_stack([x[mask], np.ones(mask.sum())])
    slope, offset = np.linalg.lstsq(A, y[mask], rcond=None)[0]
    pred = slope * x[mask] + offset
    return float(slope), float(offset), float(np.sqrt(np.mean((y[mask] - pred) ** 2)))


def heisenberg_4x4_c1() -> tuple[float, float, float]:
    L = 4
    N = L * L
    nup = N // 2
    basis = np.array([sum(1 << i for i in comb) for comb in itertools.combinations(range(N), nup)], dtype=np.uint32)
    index = {int(s): i for i, s in enumerate(basis)}
    bonds: list[tuple[int, int]] = []
    for x in range(L):
        for y in range(L):
            i = x + L * y
            bonds.append((i, ((x + 1) % L) + L * y))
            bonds.append((i, x + L * ((y + 1) % L)))
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    for col, state0 in enumerate(basis):
        state = int(state0)
        diag = 0.0
        for i, j in bonds:
            si = 1 if (state >> i) & 1 else -1
            sj = 1 if (state >> j) & 1 else -1
            diag += 0.25 * si * sj
            if si != sj:
                flipped = state ^ (1 << i) ^ (1 << j)
                rows.append(index[flipped])
                cols.append(col)
                vals.append(0.5)
        rows.append(col)
        cols.append(col)
        vals.append(diag)
    H = sp.csr_matrix((vals, (rows, cols)), shape=(len(basis), len(basis)))
    e0 = float(spla.eigsh(H, k=1, which="SA", tol=1e-12, return_eigenvectors=False)[0])
    c1 = e0 / len(bonds)
    return e0, e0 / N, c1


def main() -> None:
    rows = []
    k_path = default_k_path()
    eps = np.array([eps0(kx, ky) for kx, ky in k_path])
    root_npz = np.load(ROOT / "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz")
    roots_by_u = {int(U): root_npz["omega_root"][i] for i, U in enumerate(root_npz["U"])}
    for U in [8, 12, 20, 40]:
        delta = []
        center = []
        gap = []
        zero_first_moment = []
        for kx, ky in k_path:
            h = parse_green_file(DATA / f"L4x4Nup8Ndn8U{U}V0tp0f{kx}x{ky}Q0x0_Gh.dat", q_target=(0, 0))
            p = parse_green_file(DATA / f"L4x4Nup8Ndn8U{U}V0tp0f{kx}x{ky}Q0x0_Gp.dat", q_target=(0, 0))
            wh = h.nrm2**2
            wp = p.nrm2**2
            mu = U / 2.0
            eh = -mu + h.E0 - h.a[0]
            ep = -mu - h.E0 + p.a[0]
            delta.append(wh - 0.5)
            center.append(0.5 * (ep + eh))
            gap.append(ep - eh)
            zero_first_moment.append(wh * ep + wp * eh)
        delta = np.array(delta)
        center = np.array(center)
        gap = np.array(gap)
        zero_first_moment = np.array(zero_first_moment)
        actual_roots = roots_by_u[U]
        rows.append(
            {
                "U": U,
                "delta_slope_per_epsilon": fit_slope(eps, delta)[0],
                "spin_summed_nk_slope_per_epsilon": 2.0 * fit_slope(eps, delta)[0],
                "center_slope_per_epsilon": fit_slope(eps, center)[0],
                "delta_times_gap_slope_per_epsilon": fit_slope(eps, delta * gap)[0],
                "first_moment_zero_slope_per_epsilon": fit_slope(eps, zero_first_moment)[0],
                "actual_root_slope_per_epsilon": fit_slope(eps, actual_roots)[0],
                "first_moment_vs_actual_rms": float(np.sqrt(np.nanmean((zero_first_moment - actual_roots) ** 2))),
            }
        )
    e0, e_site, c1 = heisenberg_4x4_c1()
    df = pd.DataFrame(rows)
    df["heisenberg_4x4_E0"] = e0
    df["heisenberg_4x4_E_per_site"] = e_site
    df["heisenberg_4x4_C1"] = c1
    df["four_C1"] = 4.0 * c1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df.to_string(index=False))
    print(OUT)


if __name__ == "__main__":
    main()
