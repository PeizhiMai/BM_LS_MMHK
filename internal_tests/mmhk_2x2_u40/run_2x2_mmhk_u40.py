#!/usr/bin/env python3
"""Internal 2x2-MMHK test at half filling, t'=V=0, and U=40t.

This is deliberately isolated from the manuscript workflow.  It performs
small-Hilbert-space exact diagonalization without qbasis, reproduces the
production MMHK hopping convention, evaluates the q=(0,0) Green function
directly from its Lehmann representation, measures equal-time observables on
the mixed-momentum grid, and tests

    omega_GZ(k) = s_NN epsilon(k),       s_NN ?= 4 <S_i.S_j>_NN.

The 2x2 Hilbert spaces have dimensions 36 (Nup=Ndn=2) and 24 in each
single-particle sector, so dense diagonalization is exact and inexpensive.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import brentq


NSITES = 4
LX = 2
LY = 2
T = 1.0
U = 40.0
V = 0.0
TP = 0.0
MU = U / 2.0
ETA = 0.05
F_OFFSET = 1.0e-5
GRID_DENOMINATOR = 40


@dataclass(frozen=True)
class Sector:
    nup: int
    ndn: int
    basis: tuple[int, ...]
    index: dict[int, int]


@dataclass
class GreenPoint:
    ix: int
    iy: int
    fx: float
    fy: float
    epsilon: float
    e0: float
    pole_h: np.ndarray
    weight_h: np.ndarray
    pole_p: np.ndarray
    weight_p: np.ndarray
    gap_lower: float
    gap_upper: float
    root: float
    rho_root: float
    candidate_count: int
    c_nn_x: float
    c_nn_y: float
    directional_prediction: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
    )
    parser.add_argument(
        "--stored-u2-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "2x2test"
        / "tp0U2"
        / "Nup2Ndn2",
        help="Stored qbasis U=2 outputs used only to validate conventions.",
    )
    parser.add_argument("--omega-min", type=float, default=-30.0)
    parser.add_argument("--omega-max", type=float, default=30.0)
    parser.add_argument("--omega-points", type=int, default=6001)
    return parser.parse_args()


def make_sector(nup: int, ndn: int) -> Sector:
    states: list[int] = []
    for occupied_up in combinations(range(NSITES), nup):
        up_bits = sum(1 << site for site in occupied_up)
        for occupied_dn in combinations(range(NSITES), ndn):
            dn_bits = sum(1 << (NSITES + site) for site in occupied_dn)
            states.append(up_bits | dn_bits)
    basis = tuple(states)
    return Sector(nup=nup, ndn=ndn, basis=basis, index={s: i for i, s in enumerate(basis)})


HALF = make_sector(2, 2)
PLUS_UP = make_sector(3, 2)
MINUS_UP = make_sector(1, 2)
MINUS_DN = make_sector(2, 1)


def annihilate(state: int, orbital: int) -> tuple[int, int] | None:
    if not ((state >> orbital) & 1):
        return None
    parity = (state & ((1 << orbital) - 1)).bit_count() & 1
    return state ^ (1 << orbital), -1 if parity else 1


def create(state: int, orbital: int) -> tuple[int, int] | None:
    if (state >> orbital) & 1:
        return None
    parity = (state & ((1 << orbital) - 1)).bit_count() & 1
    return state | (1 << orbital), -1 if parity else 1


def apply_hop(state: int, destination: int, source: int) -> tuple[int, int] | None:
    first = annihilate(state, source)
    if first is None:
        return None
    second = create(first[0], destination)
    if second is None:
        return None
    return second[0], first[1] * second[1]


def apply_right_to_left(
    state: int, operations: Sequence[tuple[str, int]]
) -> tuple[int, int] | None:
    coefficient = 1
    current = state
    for kind, orbital in operations:
        result = create(current, orbital) if kind == "create" else annihilate(current, orbital)
        if result is None:
            return None
        current, sign = result
        coefficient *= sign
    return current, coefficient


def site(x: int, y: int) -> int:
    return (x % LX) * LY + (y % LY)


def directed_nn_bonds() -> list[tuple[int, int, str]]:
    bonds: list[tuple[int, int, str]] = []
    for x in range(LX):
        for y in range(LY):
            i = site(x, y)
            bonds.append((i, site(x + 1, y), "x"))
            bonds.append((i, site(x, y + 1), "y"))
    return bonds


BONDS = directed_nn_bonds()


def f_value(index: int) -> float:
    return index * math.pi / GRID_DENOMINATOR + F_OFFSET


def bare_dispersion(fx: float, fy: float) -> float:
    return -2.0 * T * (math.cos(fx) + math.cos(fy))


def interaction_count(state: int) -> int:
    return sum(
        ((state >> i) & 1) * ((state >> (NSITES + i)) & 1)
        for i in range(NSITES)
    )


def build_hamiltonian(sector: Sector, interaction: float, fx: float, fy: float) -> np.ndarray:
    """Production MMHK Hamiltonian, including the L=2 bond aliasing exactly."""
    dim = len(sector.basis)
    ham = np.zeros((dim, dim), dtype=np.complex128)
    phases = {"x": fx, "y": fy}
    for col, state_value in enumerate(sector.basis):
        ham[col, col] += interaction * interaction_count(state_value)
        for i, j, direction in BONDS:
            phase = phases[direction]
            for spin_offset in (0, NSITES):
                terms = (
                    (i + spin_offset, j + spin_offset, -T * np.exp(-1j * phase)),
                    (j + spin_offset, i + spin_offset, -T * np.exp(+1j * phase)),
                )
                for destination, source, coefficient in terms:
                    result = apply_hop(state_value, destination, source)
                    if result is not None:
                        row = sector.index[result[0]]
                        ham[row, col] += coefficient * result[1]
    hermiticity_error = float(np.max(np.abs(ham - ham.conj().T)))
    if hermiticity_error > 2.0e-12:
        raise RuntimeError(f"Hamiltonian is not Hermitian: {hermiticity_error:g}")
    return ham


def diagonalize(sector: Sector, interaction: float, fx: float, fy: float) -> tuple[np.ndarray, np.ndarray]:
    return np.linalg.eigh(build_hamiltonian(sector, interaction, fx, fy))


def one_body_operator(
    source_sector: Sector,
    target_sector: Sector,
    spin: str,
    creation: bool,
    qx: float = 0.0,
    qy: float = 0.0,
) -> np.ndarray:
    matrix = np.zeros((len(target_sector.basis), len(source_sector.basis)), dtype=np.complex128)
    offset = 0 if spin == "up" else NSITES
    for col, state_value in enumerate(source_sector.basis):
        for x in range(LX):
            for y in range(LY):
                orbital = offset + site(x, y)
                if creation:
                    result = create(state_value, orbital)
                    phase = np.exp(-1j * (qx * x + qy * y)) / math.sqrt(NSITES)
                else:
                    result = annihilate(state_value, orbital)
                    phase = np.exp(+1j * (qx * x + qy * y)) / math.sqrt(NSITES)
                if result is not None:
                    matrix[target_sector.index[result[0]], col] += phase * result[1]
    return matrix


C_UP = one_body_operator(HALF, MINUS_UP, "up", creation=False)
CDAG_UP = one_body_operator(HALF, PLUS_UP, "up", creation=True)
C_DN = one_body_operator(HALF, MINUS_DN, "dn", creation=False)
NQ_UP = C_UP.conj().T @ C_UP
NQ_DN = C_DN.conj().T @ C_DN


def diagonal_expectation(psi: np.ndarray, values: np.ndarray) -> float:
    return float(np.real(np.vdot(psi, values * psi)))


DOUBLE_OCCUPANCY_COUNT = np.array([interaction_count(s) for s in HALF.basis], dtype=float)
NN_DENSITY_SUM = np.array(
    [
        sum(
            (((s >> i) & 1) + ((s >> (NSITES + i)) & 1))
            * (((s >> j) & 1) + ((s >> (NSITES + j)) & 1))
            for i, j, _ in BONDS
        )
        for s in HALF.basis
    ],
    dtype=float,
)
CHARGE_PIPI = np.array(
    [
        sum(
            ((-1.0) ** (x + y))
            * (((s >> site(x, y)) & 1) + ((s >> (NSITES + site(x, y))) & 1))
            for x in range(LX)
            for y in range(LY)
        )
        / math.sqrt(NSITES)
        for s in HALF.basis
    ],
    dtype=float,
)
SPIN_Z_PIPI = np.array(
    [
        sum(
            ((-1.0) ** (x + y))
            * 0.5
            * (((s >> site(x, y)) & 1) - ((s >> (NSITES + site(x, y))) & 1))
            for x in range(LX)
            for y in range(LY)
        )
        / math.sqrt(NSITES)
        for s in HALF.basis
    ],
    dtype=float,
)


def build_spin_nn_sum() -> np.ndarray:
    matrix = np.zeros((len(HALF.basis), len(HALF.basis)), dtype=np.complex128)
    for col, state_value in enumerate(HALF.basis):
        for i, j, _ in BONDS:
            sz_i = 0.5 * (((state_value >> i) & 1) - ((state_value >> (NSITES + i)) & 1))
            sz_j = 0.5 * (((state_value >> j) & 1) - ((state_value >> (NSITES + j)) & 1))
            matrix[col, col] += sz_i * sz_j

            # S_i^+ S_j^-: c^dagger_i,up c_i,dn c^dagger_j,dn c_j,up.
            result = apply_right_to_left(
                state_value,
                (
                    ("annihilate", j),
                    ("create", NSITES + j),
                    ("annihilate", NSITES + i),
                    ("create", i),
                ),
            )
            if result is not None:
                matrix[HALF.index[result[0]], col] += 0.5 * result[1]

            # S_i^- S_j^+: c^dagger_i,dn c_i,up c^dagger_j,up c_j,dn.
            result = apply_right_to_left(
                state_value,
                (
                    ("annihilate", NSITES + j),
                    ("create", j),
                    ("annihilate", i),
                    ("create", NSITES + i),
                ),
            )
            if result is not None:
                matrix[HALF.index[result[0]], col] += 0.5 * result[1]
    return matrix


SPIN_NN_SUM = build_spin_nn_sum()


def build_directional_spin_nn_sum(direction: str) -> np.ndarray:
    matrix = np.zeros((len(HALF.basis), len(HALF.basis)), dtype=np.complex128)
    for col, state_value in enumerate(HALF.basis):
        for i, j, bond_direction in BONDS:
            if bond_direction != direction:
                continue
            sz_i = 0.5 * (((state_value >> i) & 1) - ((state_value >> (NSITES + i)) & 1))
            sz_j = 0.5 * (((state_value >> j) & 1) - ((state_value >> (NSITES + j)) & 1))
            matrix[col, col] += sz_i * sz_j
            for operations in (
                (
                    ("annihilate", j),
                    ("create", NSITES + j),
                    ("annihilate", NSITES + i),
                    ("create", i),
                ),
                (
                    ("annihilate", NSITES + j),
                    ("create", j),
                    ("annihilate", i),
                    ("create", NSITES + i),
                ),
            ):
                result = apply_right_to_left(state_value, operations)
                if result is not None:
                    matrix[HALF.index[result[0]], col] += 0.5 * result[1]
    return matrix


SPIN_NN_X_SUM = build_directional_spin_nn_sum("x")
SPIN_NN_Y_SUM = build_directional_spin_nn_sum("y")
N_BONDS_X = sum(direction == "x" for _, _, direction in BONDS)
N_BONDS_Y = sum(direction == "y" for _, _, direction in BONDS)


def expectation(psi: np.ndarray, operator: np.ndarray) -> float:
    return float(np.real(np.vdot(psi, operator @ psi)))


def measure_observables(ix: int, iy: int, interaction: float = U) -> dict[str, float | int]:
    fx, fy = f_value(ix), f_value(iy)
    eigenvalues, eigenvectors = diagonalize(HALF, interaction, fx, fy)
    psi = eigenvectors[:, 0]
    d_sum = diagonal_expectation(psi, DOUBLE_OCCUPANCY_COUNT)
    n_up_q = expectation(psi, NQ_UP)
    n_dn_q = expectation(psi, NQ_DN)
    nq_up_nq_dn = float(np.real(np.vdot(psi, NQ_UP @ (NQ_DN @ psi))))
    return {
        "ix": ix,
        "iy": iy,
        "fx": fx,
        "fy": fy,
        "epsilon": bare_dispersion(fx, fy),
        "E0": float(eigenvalues[0]),
        "E0_per_site": float(eigenvalues[0] / NSITES),
        "double_occupancy": d_sum / NSITES,
        "kinetic_per_site": (float(eigenvalues[0]) - interaction * d_sum) / NSITES,
        "C_NN": expectation(psi, SPIN_NN_SUM) / len(BONDS),
        "C_NN_x": expectation(psi, SPIN_NN_X_SUM) / N_BONDS_X,
        "C_NN_y": expectation(psi, SPIN_NN_Y_SUM) / N_BONDS_Y,
        "nn_density_NN": diagonal_expectation(psi, NN_DENSITY_SUM) / len(BONDS),
        "Szz_pipi": diagonal_expectation(psi, SPIN_Z_PIPI**2),
        "Sc_pipi": diagonal_expectation(psi, CHARGE_PIPI**2),
        "nq_up": n_up_q,
        "nq_dn": n_dn_q,
        "nq": n_up_q + n_dn_q,
        "nq_up_nq_dn": nq_up_nq_dn,
    }


def green_point(ix: int, iy: int) -> GreenPoint:
    fx, fy = f_value(ix), f_value(iy)
    values_0, vectors_0 = diagonalize(HALF, U, fx, fy)
    values_p, vectors_p = diagonalize(PLUS_UP, U, fx, fy)
    values_h, vectors_h = diagonalize(MINUS_UP, U, fx, fy)
    e0 = float(values_0[0])
    psi = vectors_0[:, 0]

    amplitude_p = vectors_p.conj().T @ (CDAG_UP @ psi)
    amplitude_h = vectors_h.conj().T @ (C_UP @ psi)
    weight_p = np.abs(amplitude_p) ** 2
    weight_h = np.abs(amplitude_h) ** 2
    pole_p = values_p - e0 - MU
    pole_h = e0 - values_h - MU

    keep_p = weight_p > 1.0e-12
    keep_h = weight_h > 1.0e-12
    pole_p, weight_p = pole_p[keep_p], weight_p[keep_p]
    pole_h, weight_h = pole_h[keep_h], weight_h[keep_h]
    lower = float(np.max(pole_h))
    upper = float(np.min(pole_p))
    if not lower < upper:
        raise RuntimeError(f"No central gap at f=({ix},{iy}): [{lower}, {upper}]")

    def g_scalar(omega: float) -> complex:
        z = omega + 1j * ETA
        return complex(
            np.sum(weight_h / (z - pole_h)) + np.sum(weight_p / (z - pole_p))
        )

    margin = min(1.0e-5, 1.0e-4 * (upper - lower))
    scan = np.linspace(lower + margin, upper - margin, 4001)
    re_values = np.array([g_scalar(w).real for w in scan])
    candidates: list[float] = []
    for index in np.where(re_values[:-1] * re_values[1:] < 0.0)[0]:
        candidates.append(
            float(brentq(lambda w: g_scalar(w).real, scan[index], scan[index + 1], xtol=1.0e-13))
        )
    if not candidates:
        root = float("nan")
        rho_root = float("nan")
    else:
        spectral_values = [-g_scalar(root_value).imag / math.pi for root_value in candidates]
        selected = int(np.argmin(spectral_values))
        root = candidates[selected]
        rho_root = float(spectral_values[selected])

    c_nn_x = expectation(psi, SPIN_NN_X_SUM) / N_BONDS_X
    c_nn_y = expectation(psi, SPIN_NN_Y_SUM) / N_BONDS_Y
    epsilon_x = -2.0 * T * math.cos(fx)
    epsilon_y = -2.0 * T * math.cos(fy)
    directional_prediction = 4.0 * (c_nn_x * epsilon_x + c_nn_y * epsilon_y)

    return GreenPoint(
        ix=ix,
        iy=iy,
        fx=fx,
        fy=fy,
        epsilon=bare_dispersion(fx, fy),
        e0=e0,
        pole_h=pole_h,
        weight_h=weight_h,
        pole_p=pole_p,
        weight_p=weight_p,
        gap_lower=lower,
        gap_upper=upper,
        root=root,
        rho_root=rho_root,
        candidate_count=len(candidates),
        c_nn_x=c_nn_x,
        c_nn_y=c_nn_y,
        directional_prediction=directional_prediction,
    )


def evaluate_green(point: GreenPoint, omega: np.ndarray) -> np.ndarray:
    z = omega[:, None] + 1j * ETA
    gh = np.sum(point.weight_h[None, :] / (z - point.pole_h[None, :]), axis=1)
    gp = np.sum(point.weight_p[None, :] / (z - point.pole_p[None, :]), axis=1)
    return gh + gp


def default_path() -> list[tuple[int, int]]:
    return (
        [(i, 0) for i in range(40)]
        + [(40, i) for i in range(40)]
        + [(i, i) for i in range(40, -1, -1)]
    )


def unique_in_order(values: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    result: list[tuple[int, int]] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_against_stored_u2(stored_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    pattern = re.compile(r"f(?P<ix>\d+)x(?P<iy>\d+)Q0x0_obs\.dat$")
    for path in sorted(stored_dir.glob("L2x2Nup2Ndn2f*x*Q0x0_obs.dat")):
        match = pattern.search(path.name)
        if match is None:
            continue
        ix, iy = int(match.group("ix")), int(match.group("iy"))
        text = path.read_text()
        stored_e0 = float(re.search(r"^E0\s+(\S+)", text, re.MULTILINE).group(1))
        stored_d = float(re.search(r"^<ni_upni_dn>\s+(\S+)", text, re.MULTILINE).group(1))
        measured = measure_observables(ix, iy, interaction=2.0)
        rows.append(
            {
                "ix": ix,
                "iy": iy,
                "stored_E0": stored_e0,
                "local_E0": measured["E0"],
                "E0_abs_error": abs(float(measured["E0"]) - stored_e0),
                "stored_double_occupancy": stored_d,
                "local_double_occupancy": measured["double_occupancy"],
                "double_occupancy_abs_error": abs(float(measured["double_occupancy"]) - stored_d),
            }
        )
    if not rows:
        raise FileNotFoundError(f"No stored validation files found in {stored_dir}")
    summary = {
        "points": len(rows),
        "max_E0_abs_error": max(float(row["E0_abs_error"]) for row in rows),
        "max_double_occupancy_abs_error": max(
            float(row["double_occupancy_abs_error"]) for row in rows
        ),
    }
    return rows, summary


def weighted_obs_summary(rows: list[dict]) -> dict:
    integration_rows = rows
    keys = [
        "E0_per_site",
        "double_occupancy",
        "kinetic_per_site",
        "C_NN",
        "nn_density_NN",
        "Szz_pipi",
        "Sc_pipi",
        "nq",
        "nq_up_nq_dn",
    ]
    weights = np.array(
        [
            (1.0 if row["ix"] == row["iy"] else 2.0)
            * (0.5 if row["ix"] in (0, 40) else 1.0)
            * (0.5 if row["iy"] in (0, 40) else 1.0)
            for row in integration_rows
        ]
    )
    if not np.isclose(np.sum(weights), 1600.0):
        raise RuntimeError(f"Unexpected mixed-momentum quadrature weight {np.sum(weights)}")
    summary: dict[str, float | int | str] = {
        "stored_wedge_rows_including_endpoint": len(rows),
        "integration_wedge_rows": len(integration_rows),
        "integration_weight": float(np.sum(weights)),
        "grid": "41x41 endpoint representation of a 40x40 grid, with ix<->iy symmetry and trapezoidal endpoint weights",
    }
    for key in keys:
        values = np.array([float(row[key]) for row in integration_rows])
        mean = float(np.average(values, weights=weights))
        variance = float(np.average((values - mean) ** 2, weights=weights))
        summary[f"{key}_mean"] = mean
        summary[f"{key}_std"] = math.sqrt(max(variance, 0.0))

    # Under ix<->iy reflection, C_x and C_y exchange.  Reconstructing the
    # omitted half of the square therefore requires both directional values,
    # rather than simply doubling the stored wedge row.
    directional_values: list[float] = []
    directional_weights: list[float] = []
    for row in integration_rows:
        endpoint_weight = (
            (0.5 if row["ix"] in (0, 40) else 1.0)
            * (0.5 if row["iy"] in (0, 40) else 1.0)
        )
        directional_values.append(float(row["C_NN_x"]))
        directional_weights.append(endpoint_weight)
        if row["ix"] != row["iy"]:
            directional_values.append(float(row["C_NN_y"]))
            directional_weights.append(endpoint_weight)
    values_array = np.asarray(directional_values)
    weights_array = np.asarray(directional_weights)
    directional_mean = float(np.average(values_array, weights=weights_array))
    directional_variance = float(
        np.average((values_array - directional_mean) ** 2, weights=weights_array)
    )
    for key in ("C_NN_x", "C_NN_y"):
        summary[f"{key}_mean"] = directional_mean
        summary[f"{key}_std"] = math.sqrt(max(directional_variance, 0.0))
    return summary


def heisenberg_2x2_cnn() -> float:
    """Ground-state C_NN of the equal-J 2x2 spin model with production bonds."""
    spin_basis = tuple(sum(1 << i for i in occupied) for occupied in combinations(range(NSITES), 2))
    spin_index = {state: i for i, state in enumerate(spin_basis)}
    ham = np.zeros((len(spin_basis), len(spin_basis)), dtype=float)
    for col, state_value in enumerate(spin_basis):
        for i, j, _ in BONDS:
            up_i = (state_value >> i) & 1
            up_j = (state_value >> j) & 1
            ham[col, col] += (0.5 if up_i else -0.5) * (0.5 if up_j else -0.5)
            if up_i != up_j:
                flipped = state_value ^ (1 << i) ^ (1 << j)
                ham[spin_index[flipped], col] += 0.5
    return float(np.linalg.eigvalsh(ham)[0] / len(BONDS))


def fit_roots(path_points: list[GreenPoint], c_nn_mean: float, c_nn_heisenberg: float) -> dict:
    epsilon = np.array([point.epsilon for point in path_points])
    roots = np.array([point.root for point in path_points])
    directional_prediction = np.array([point.directional_prediction for point in path_points])
    valid = np.isfinite(roots)
    epsilon_valid = epsilon[valid]
    roots_valid = roots[valid]
    slope = float(np.dot(epsilon_valid, roots_valid) / np.dot(epsilon_valid, epsilon_valid))
    design = np.column_stack([epsilon_valid, np.ones_like(epsilon_valid)])
    affine_slope, affine_intercept = np.linalg.lstsq(design, roots_valid, rcond=None)[0]

    def metrics(prediction: np.ndarray) -> dict[str, float]:
        residual = roots_valid - prediction
        rmse = float(np.sqrt(np.mean(residual**2)))
        root_std = float(np.std(roots_valid))
        return {
            "rmse": rmse,
            "normalized_rmse_by_root_std": rmse / root_std if root_std > 0 else float("nan"),
            "max_abs_residual": float(np.max(np.abs(residual))),
        }

    fitted_metrics = metrics(slope * epsilon_valid)
    correlation_metrics = metrics((4.0 * c_nn_mean) * epsilon_valid)
    heisenberg_metrics = metrics((4.0 * c_nn_heisenberg) * epsilon_valid)
    directional_metrics = metrics(directional_prediction[valid])
    coefficient_difference = slope - 4.0 * c_nn_mean
    return {
        "path_rows": len(path_points),
        "valid_root_rows": int(np.sum(valid)),
        "s_NN_fit_zero_intercept": slope,
        "affine_slope": float(affine_slope),
        "affine_intercept": float(affine_intercept),
        "C_NN_grid_mean": c_nn_mean,
        "four_C_NN_grid_mean": 4.0 * c_nn_mean,
        "C_NN_2x2_Heisenberg": c_nn_heisenberg,
        "four_C_NN_2x2_Heisenberg": 4.0 * c_nn_heisenberg,
        "fit_minus_four_C_NN": coefficient_difference,
        "coefficient_relative_difference_percent": 100.0
        * abs(coefficient_difference)
        / abs(4.0 * c_nn_mean),
        "fit": fitted_metrics,
        "four_C_NN_prediction": correlation_metrics,
        "heisenberg_prediction": heisenberg_metrics,
        "direction_resolved_prediction": directional_metrics,
        "C_NN_x_path_min": float(min(point.c_nn_x for point in path_points)),
        "C_NN_x_path_max": float(max(point.c_nn_x for point in path_points)),
        "C_NN_y_path_min": float(min(point.c_nn_y for point in path_points)),
        "C_NN_y_path_max": float(max(point.c_nn_y for point in path_points)),
    }


def plot_results(
    output_dir: Path,
    omega: np.ndarray,
    rho: np.ndarray,
    path_points: list[GreenPoint],
    fit: dict,
) -> None:
    roots = np.array([point.root for point in path_points])
    epsilon = np.array([point.epsilon for point in path_points])
    x = np.arange(len(path_points))
    s_fit = float(fit["s_NN_fit_zero_intercept"])
    s_corr = float(fit["four_C_NN_grid_mean"])
    directional = np.array([point.directional_prediction for point in path_points])

    fig = plt.figure(figsize=(14.0, 4.0))
    grid = fig.add_gridspec(1, 3, width_ratios=(1.55, 1.0, 1.05), wspace=0.43)
    ax0 = fig.add_subplot(grid[0, 0])
    vmax = float(np.quantile(rho, 0.995))
    image = ax0.imshow(
        rho.T,
        origin="lower",
        aspect="auto",
        extent=(-0.5, len(path_points) - 0.5, omega[0], omega[-1]),
        cmap="magma",
        vmin=0.0,
        vmax=vmax,
        interpolation="bilinear",
        rasterized=True,
    )
    ax0.plot(x, roots, color="white", lw=1.7, label="exact GZ root")
    ax0.plot(
        x,
        directional,
        color="#4dd7ff",
        lw=1.25,
        ls="--",
        label=r"$4(C_x\varepsilon_x+C_y\varepsilon_y)$",
    )
    ax0.set_ylim(-27, 27)
    ax0.set_xticks([0, 40, 80, 120], [r"$\Gamma$", r"$X$", r"$M$", r"$\Gamma$"])
    ax0.set_ylabel(r"$\omega/t$")
    ax0.legend(loc="upper center", ncol=2, fontsize=8, frameon=False, labelcolor="white")
    colorbar = fig.colorbar(image, ax=ax0, pad=0.015, fraction=0.045)
    colorbar.set_label(r"$A(\mathbf{k},\omega)$")

    ax1 = fig.add_subplot(grid[0, 1])
    ax1.scatter(epsilon, roots, s=13, color="#5e3c99", alpha=0.75, label="GZ roots")
    eps_line = np.linspace(-4.05, 4.05, 300)
    ax1.plot(eps_line, s_fit * eps_line, color="#d73027", lw=1.8, label=rf"fit: $s_{{\rm NN}}={s_fit:.4f}$")
    ax1.plot(
        eps_line,
        s_corr * eps_line,
        color="#1f9e89",
        lw=1.6,
        ls="--",
        label=rf"$4C_{{\rm NN}}={s_corr:.4f}$",
    )
    ax1.axhline(0.0, color="0.75", lw=0.8)
    ax1.axvline(0.0, color="0.75", lw=0.8)
    ax1.set_xlabel(r"$\varepsilon(\mathbf{k})/t$")
    ax1.set_ylabel(r"$\omega_{\rm GZ}/t$")
    ax1.legend(loc="best", fontsize=8, frameon=False)
    ax1.text(
        0.03,
        0.03,
        "internal 2x2 test\n" + rf"$U/t=40$, $\eta/t={ETA:g}$",
        transform=ax1.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
    )

    ax2 = fig.add_subplot(grid[0, 2])
    ax2.plot(x, roots, color="#5e3c99", lw=2.0, label="exact GZ root")
    ax2.plot(x, s_fit * epsilon, color="#d73027", lw=1.4, label=r"best single $s_{\rm NN}\varepsilon$")
    ax2.plot(
        x,
        directional,
        color="#1f9e89",
        lw=1.6,
        ls="--",
        label=r"direction-resolved $4C\varepsilon$",
    )
    ax2.set_xticks([0, 40, 80, 120], [r"$\Gamma$", r"$X$", r"$M$", r"$\Gamma$"])
    ax2.set_ylabel(r"$\omega/t$")
    ax2.legend(loc="best", fontsize=7.5, frameon=False)
    fig.savefig(output_dir / "2x2_u40_gcalpath_relation.pdf", bbox_inches="tight")
    fig.savefig(output_dir / "2x2_u40_gcalpath_relation.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def report_text(validation: dict, obs: dict, fit: dict) -> str:
    coefficient_ok = float(fit["coefficient_relative_difference_percent"]) < 5.0
    shape_ok = float(fit["fit"]["normalized_rmse_by_root_std"]) < 0.05
    scalar_verdict = "passes" if coefficient_ok and shape_ok else "does not pass"
    directional_ok = float(fit["direction_resolved_prediction"]["normalized_rmse_by_root_std"]) < 0.05
    directional_verdict = "passes" if directional_ok else "does not pass"
    return f"""# Internal 2x2-MMHK U=40 test

This calculation is an internal resolution test and is not part of the manuscript.

## Setup

- 2x2 momentum-mixing resolution, half filling (`Nup=Ndn=2`)
- `t=1`, `t'=0`, `U=40`, `V=0`, `mu=U/2`
- production mixed-momentum phase convention `f_i=i*pi/40+1e-5`
- exact dense diagonalization and exact Lehmann Green function
- displayed/evaluated spectrum broadening `eta=0.05`
- 121-row Gamma-X-M-Gamma path (120 unique momenta)
- observables integrated with the production 41-point endpoint/trapezoid convention (effective 40x40 grid) and `kx<->ky` symmetry

## Convention validation

The local implementation was checked against all {validation['points']} stored qbasis 2x2, U=2 observable files.
The maximum absolute errors are {validation['max_E0_abs_error']:.3e} in E0 and
{validation['max_double_occupancy_abs_error']:.3e} in double occupancy.

## Mott-side relation test

- zero-intercept GZ fit: `s_NN = {fit['s_NN_fit_zero_intercept']:.8f}`
- affine check: slope `{fit['affine_slope']:.8f}`, intercept `{fit['affine_intercept']:.3e}`
- measured grid-averaged `C_NN = {fit['C_NN_grid_mean']:.8f}`
- correlation prediction: `4 C_NN = {fit['four_C_NN_grid_mean']:.8f}`
- coefficient mismatch: `{fit['coefficient_relative_difference_percent']:.3f}%`
- fitted-line normalized RMSE: `{fit['fit']['normalized_rmse_by_root_std']:.5f}`
- direct `4 C_NN epsilon` normalized RMSE: `{fit['four_C_NN_prediction']['normalized_rmse_by_root_std']:.5f}`
- direction-resolved `4(C_x epsilon_x+C_y epsilon_y)` normalized RMSE: `{fit['direction_resolved_prediction']['normalized_rmse_by_root_std']:.5f}`
- valid gap-interior roots: `{fit['valid_root_rows']}/{fit['path_rows']}`

Using the explicit internal thresholds (coefficient mismatch <5% and fitted-line normalized
RMSE <5%), the 2x2 result **{scalar_verdict}** the isotropic, single-coefficient version of
the Mott-side relation.  The more fundamental direction-resolved form
`omega_GZ=4(C_x epsilon_x+C_y epsilon_y)` **{directional_verdict}** the 5% shape criterion.

This distinction is a genuine 2x2-resolution effect.  On a two-site periodic direction,
the + and - hopping paths connect the same pair of sites and interfere.  The effective
exchange is consequently strongly direction- and mixed-momentum-dependent, with
`C_x` and `C_y` ranging from nearly zero to about -0.743 along the path.  The compact
2x2 construction therefore retains the bond-resolved strong-coupling mechanism, but it
is too coarse to collapse the entire path onto one momentum-independent `s_NN`.

## Selected equal-time observables

- `E0/N = {obs['E0_per_site_mean']:.8f}`
- double occupancy `D = {obs['double_occupancy_mean']:.8f}`
- kinetic energy per site `K/N = {obs['kinetic_per_site_mean']:.8f}`
- `C_NN = {obs['C_NN_mean']:.8f}`
- `Szz(pi,pi) = {obs['Szz_pipi_mean']:.8f}`
- `Sc(pi,pi) = {obs['Sc_pipi_mean']:.8f}`

All machine-readable outputs are in this directory.  No manuscript or Overleaf file was modified.
"""


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    validation_rows, validation_summary = validate_against_stored_u2(args.stored_u2_dir)
    write_csv(output_dir / "validation_against_stored_qbasis_u2.csv", validation_rows)

    observable_rows = [measure_observables(ix, iy) for ix in range(41) for iy in range(ix, 41)]
    write_csv(output_dir / "obs_all_mixed_momenta.csv", observable_rows)
    obs_summary = weighted_obs_summary(observable_rows)

    path = default_path()
    green_by_key = {key: green_point(*key) for key in unique_in_order(path)}
    path_points = [green_by_key[key] for key in path]
    omega = np.linspace(args.omega_min, args.omega_max, args.omega_points)
    green_values = np.vstack([evaluate_green(point, omega) for point in path_points])
    rho = -green_values.imag / math.pi
    re_g = green_values.real

    root_rows: list[dict] = []
    for path_index, point in enumerate(path_points):
        root_rows.append(
            {
                "path_index": path_index,
                "ix": point.ix,
                "iy": point.iy,
                "fx": point.fx,
                "fy": point.fy,
                "epsilon": point.epsilon,
                "omega_GZ": point.root,
                "rho_at_root": point.rho_root,
                "gap_lower": point.gap_lower,
                "gap_upper": point.gap_upper,
                "gap_width": point.gap_upper - point.gap_lower,
                "root_candidate_count": point.candidate_count,
                "C_NN_x": point.c_nn_x,
                "C_NN_y": point.c_nn_y,
                "direction_resolved_prediction": point.directional_prediction,
                "direction_resolved_residual": point.root - point.directional_prediction,
                "status": "clean" if np.isfinite(point.root) else "missing",
            }
        )
    write_csv(output_dir / "gcalpath_gz_roots.csv", root_rows)

    pole_rows: list[dict] = []
    for point in green_by_key.values():
        for branch, poles, weights in (
            ("removal", point.pole_h, point.weight_h),
            ("addition", point.pole_p, point.weight_p),
        ):
            for pole_index, (pole, weight) in enumerate(zip(poles, weights, strict=True)):
                pole_rows.append(
                    {
                        "ix": point.ix,
                        "iy": point.iy,
                        "branch": branch,
                        "pole_index": pole_index,
                        "omega_pole": float(pole),
                        "weight": float(weight),
                    }
                )
    write_csv(output_dir / "gcalpath_exact_lehmann_poles.csv", pole_rows)
    np.savez_compressed(
        output_dir / "gcalpath_eta0p05.npz",
        omega=omega,
        rho=rho,
        re_g=re_g,
        ix=np.array([point.ix for point in path_points]),
        iy=np.array([point.iy for point in path_points]),
        fx=np.array([point.fx for point in path_points]),
        fy=np.array([point.fy for point in path_points]),
        epsilon=np.array([point.epsilon for point in path_points]),
        omega_gz=np.array([point.root for point in path_points]),
        c_nn_x=np.array([point.c_nn_x for point in path_points]),
        c_nn_y=np.array([point.c_nn_y for point in path_points]),
        direction_resolved_prediction=np.array(
            [point.directional_prediction for point in path_points]
        ),
        eta=np.array(ETA),
        U=np.array(U),
        V=np.array(V),
        tp=np.array(TP),
    )

    c_nn_heisenberg = heisenberg_2x2_cnn()
    fit_summary = fit_roots(path_points, float(obs_summary["C_NN_mean"]), c_nn_heisenberg)
    summary = {
        "purpose": "internal_only_not_for_manuscript",
        "parameters": {
            "Lx": LX,
            "Ly": LY,
            "Nup": 2,
            "Ndn": 2,
            "t": T,
            "tp": TP,
            "U": U,
            "V": V,
            "mu": MU,
            "eta": ETA,
            "f_offset": F_OFFSET,
        },
        "validation": validation_summary,
        "observables": obs_summary,
        "gz_relation": fit_summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    plot_results(output_dir, omega, rho, path_points, fit_summary)
    report = report_text(validation_summary, obs_summary, fit_summary)
    (output_dir / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
