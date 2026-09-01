#!/usr/bin/env python3
"""Fit the half-filled U-only t'=-0.25 Green-function-zero dispersion.

The nearest-neighbour-only problem permits one band-scale parameter because
there is only one hopping harmonic.  Once t' is nonzero, the nearest- and
next-nearest-neighbour harmonics need not acquire the same many-body
renormalization.  This script therefore fits

    omega_GZ(k) = s_NN epsilon_1(k)
                  +s_NNN epsilon_2(k) + delta,

with the sign carried by each bond coefficient.  In particular,
s_NN<0 for the antiferromagnetic nearest-neighbour correlation,

where epsilon_1=-2t(cos kx+cos ky) and
epsilon_2=-4t' cos kx cos ky.  It also computes the parameter-free
strong-coupling prediction

    omega_GZ(k) = 4 C_NN epsilon_NN(k) + 4 C_NNN epsilon_NNN(k),

from the 4x4 J1-J2 Heisenberg ground state, with J2/J1=(t'/t)^2.

All fits use the stored eta=0.05 root curves generated from the raw Lanczos
continued fractions.  The repeated terminal Gamma point is retained for the
primary manuscript-convention fit; a 120-point unique-path fit is saved as an
endpoint-weighting audit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import eigsh

from manuscript_figure_style import outside_panel_label


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "data/Gcalpath/luttinger_surface_eta0p05"
    / "luttinger_tpn25_eta0p05_spectra_and_roots.npz"
)
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures/pnas_supplement"
MAIN_FIGURES = ROOT / "figures/prl_main"

METRICS_CSV = RESULTS / "tpn25_zero_dispersion_fit_metrics_eta0p05.csv"
CURVES_CSV = RESULTS / "tpn25_zero_dispersion_fit_curves_eta0p05.csv"
SPIN_CSV = RESULTS / "tpn25_j1j2_spin_correlations.csv"
SUMMARY_JSON = RESULTS / "tpn25_zero_dispersion_fit_summary_eta0p05.json"
FIGURE_STEM = MAIN_FIGURES / "prl_fig5_tprime_bond_resolved"
ANALYSIS_FIGURE_STEM = FIGURES / "tpn25_zero_dispersion_harmonic_fit_eta0p05"

STYLE = {
    "font.family": "Arial",
    "font.size": 10.5,
    "axes.labelsize": 11.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9.2,
    "axes.linewidth": 1.0,
    "lines.linewidth": 1.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


@dataclass(frozen=True)
class SpinResult:
    tprime: float
    j2_over_j1: float
    energy: float
    first_excited_energy: float
    finite_size_gap: float
    c1: float
    c2: float

    @property
    def s_nn(self) -> float:
        return 4.0 * self.c1

    @property
    def s_nnn(self) -> float:
        return 4.0 * self.c2

    @property
    def tprime_gz(self) -> float:
        """Effective t' in s_NN[-2(cos x+cos y)-4t'_GZ cos x cos y]."""
        if self.s_nn == 0.0:
            return math.nan
        return self.tprime * self.s_nnn / self.s_nn


def square_lattice_bonds(length: int = 4) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Return unique periodic NN and diagonal NNN bonds."""

    def site(x: int, y: int) -> int:
        return (x % length) + length * (y % length)

    nn: list[tuple[int, int]] = []
    nnn: list[tuple[int, int]] = []
    for y in range(length):
        for x in range(length):
            i = site(x, y)
            nn.extend([(i, site(x + 1, y)), (i, site(x, y + 1))])
            nnn.extend([(i, site(x + 1, y + 1)), (i, site(x + 1, y - 1))])

    # This catches accidental double counting if the lattice convention is
    # changed later.
    assert len(nn) == len({tuple(sorted(bond)) for bond in nn})
    assert len(nnn) == len({tuple(sorted(bond)) for bond in nnn})
    return nn, nnn


def heisenberg_bond_operator(
    states: np.ndarray,
    state_index: dict[int, int],
    bonds: Iterable[tuple[int, int]],
) -> csr_matrix:
    """Build sum_(ij) S_i.S_j in the fixed-Sz spin basis."""

    bond_list = list(bonds)
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    diagonal = np.zeros(len(states), dtype=float)

    for row, raw_state in enumerate(states):
        state = int(raw_state)
        diag = 0.0
        for i, j in bond_list:
            spin_i = (state >> i) & 1
            spin_j = (state >> j) & 1
            if spin_i == spin_j:
                diag += 0.25
            else:
                diag -= 0.25
                flipped = state ^ ((1 << i) | (1 << j))
                rows.append(row)
                cols.append(state_index[flipped])
                values.append(0.5)
        diagonal[row] = diag

    rows.extend(range(len(states)))
    cols.extend(range(len(states)))
    values.extend(diagonal.tolist())
    return coo_matrix(
        (values, (rows, cols)), shape=(len(states), len(states)), dtype=float
    ).tocsr()


def solve_j1j2(tprime: float, length: int = 4) -> SpinResult:
    """Exact fixed-Sz diagonalization of the leading strong-coupling spin model."""

    n_sites = length * length
    n_up = n_sites // 2
    states = np.asarray(
        [sum(1 << site for site in occupied) for occupied in combinations(range(n_sites), n_up)],
        dtype=np.uint32,
    )
    state_index = {int(state): index for index, state in enumerate(states)}
    nn_bonds, nnn_bonds = square_lattice_bonds(length)
    h1 = heisenberg_bond_operator(states, state_index, nn_bonds)
    h2 = heisenberg_bond_operator(states, state_index, nnn_bonds)

    ratio = float(tprime**2)
    hamiltonian = h1 + ratio * h2
    # A fixed starting vector makes reruns bitwise-stable up to the sparse
    # eigensolver's floating-point reduction order.
    v0 = np.linspace(1.0, 2.0, len(states), dtype=float)
    v0 /= np.linalg.norm(v0)
    eigenvalues, eigenvectors = eigsh(
        hamiltonian,
        k=2,
        which="SA",
        v0=v0,
        tol=1.0e-13,
        maxiter=100_000,
        ncv=50,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[order]
    ground_state = eigenvectors[:, order[0]]
    c1 = float(np.vdot(ground_state, h1 @ ground_state).real / len(nn_bonds))
    c2 = float(np.vdot(ground_state, h2 @ ground_state).real / len(nnn_bonds))
    return SpinResult(
        tprime=float(tprime),
        j2_over_j1=ratio,
        energy=float(eigenvalues[0]),
        first_excited_energy=float(eigenvalues[1]),
        finite_size_gap=float(eigenvalues[1] - eigenvalues[0]),
        c1=c1,
        c2=c2,
    )


def harmonics(k_path: np.ndarray, tprime: float) -> dict[str, np.ndarray]:
    momenta = np.asarray(k_path, dtype=float) * (np.pi / 40.0)
    kx = momenta[:, 0]
    ky = momenta[:, 1]
    cx = np.cos(kx)
    cy = np.cos(ky)
    epsilon1 = -2.0 * (cx + cy)
    epsilon2 = -4.0 * tprime * cx * cy
    # The leading additional square-lattice harmonic generated by mixed t-t'
    # paths at finite U.  Its fitted coefficient should vanish in the strict
    # strong-coupling limit.
    chi21 = -4.0 * (np.cos(2.0 * kx) * cy + cx * np.cos(2.0 * ky))
    return {
        "epsilon1": epsilon1,
        "epsilon2": epsilon2,
        "epsilon_bare": epsilon1 + epsilon2,
        "chi21": chi21,
    }


def linear_fit(
    y: np.ndarray,
    predictors: dict[str, np.ndarray],
    indices: np.ndarray,
) -> dict[str, object]:
    names = list(predictors)
    finite = np.isfinite(y[indices])
    for values in predictors.values():
        finite &= np.isfinite(values[indices])
    used = indices[finite]
    design = np.column_stack([predictors[name][used] for name in names] + [np.ones(len(used))])
    target = y[used]
    coefficients, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
    prediction_all = np.column_stack(
        [predictors[name] for name in names] + [np.ones(len(y))]
    ) @ coefficients
    residual = target - prediction_all[used]
    rss = float(np.dot(residual, residual))
    n = len(target)
    p = design.shape[1]
    rmse = float(np.sqrt(rss / n))
    mae = float(np.mean(np.abs(residual)))
    max_abs = float(np.max(np.abs(residual)))
    centered = target - np.mean(target)
    tss = float(np.dot(centered, centered))
    r2 = float(1.0 - rss / tss)
    aic = float(n * np.log(rss / n) + 2.0 * p)
    aicc = float(aic + 2.0 * p * (p + 1.0) / (n - p - 1.0))
    bic = float(n * np.log(rss / n) + p * np.log(n))

    sigma2 = rss / (n - p)
    covariance = sigma2 * np.linalg.inv(design.T @ design)
    standard_errors = np.sqrt(np.diag(covariance))
    coef_map = {name: float(value) for name, value in zip(names, coefficients[:-1])}
    se_map = {name: float(value) for name, value in zip(names, standard_errors[:-1])}
    return {
        "names": names,
        "coefficients": coef_map,
        "standard_errors": se_map,
        "delta": float(coefficients[-1]),
        "delta_se": float(standard_errors[-1]),
        "prediction": prediction_all,
        "used_indices": used,
        "n": n,
        "p": p,
        "rmse": rmse,
        "mae": mae,
        "max_abs_error": max_abs,
        "r2": r2,
        "aicc": aicc,
        "bic": bic,
        "condition_number": float(np.linalg.cond(design)),
    }


def path_block_cv_rmse(y: np.ndarray, predictors: dict[str, np.ndarray]) -> tuple[float, list[float]]:
    """Leave one of the three 40-point path blocks out at a time."""

    unique = np.arange(120, dtype=int)
    block_errors: list[float] = []
    for start in (0, 40, 80):
        test = np.arange(start, start + 40, dtype=int)
        train = np.setdiff1d(unique, test, assume_unique=True)
        fit = linear_fit(y, predictors, train)
        residual = y[test] - np.asarray(fit["prediction"])[test]
        block_errors.append(float(np.sqrt(np.nanmean(residual**2))))
    return float(np.sqrt(np.mean(np.square(block_errors)))), block_errors


def fit_models(
    roots: np.ndarray,
    bands: dict[str, np.ndarray],
    spin: SpinResult,
) -> tuple[pd.DataFrame, dict[tuple[int, str], np.ndarray]]:
    phi_spin = 4.0 * spin.c1 * bands["epsilon1"] + 4.0 * spin.c2 * bands["epsilon2"]
    model_predictors = {
        "bare_single_scale": {"s_bare": -bands["epsilon_bare"]},
        "nn_harmonic_only": {"s_nn": bands["epsilon1"]},
        "spin_ratio": {"gamma_spin": phi_spin},
        "two_bond": {
            "s_nn": bands["epsilon1"],
            "s_nnn": bands["epsilon2"],
        },
        "two_bond_plus_chi21": {
            "s_nn": bands["epsilon1"],
            "s_nnn": bands["epsilon2"],
            "kappa21": bands["chi21"],
        },
    }

    rows: list[dict[str, object]] = []
    predictions: dict[tuple[int, str], np.ndarray] = {}
    u_values = [8, 12, 20, 40]
    for U, y in zip(u_values, roots):
        for sample, indices in (
            ("path_121", np.arange(121, dtype=int)),
            ("unique_120", np.arange(120, dtype=int)),
        ):
            for model, predictors in model_predictors.items():
                fit = linear_fit(y, predictors, indices)
                cv_rmse, cv_blocks = path_block_cv_rmse(y, predictors)
                coefficients = fit["coefficients"]
                standard_errors = fit["standard_errors"]
                s_nn = float(coefficients.get("s_nn", math.nan))
                s_nnn = float(coefficients.get("s_nnn", math.nan))
                row = {
                    "eta": 0.05,
                    "tprime": -0.25,
                    "U": U,
                    "sample": sample,
                    "model": model,
                    "n": fit["n"],
                    "p": fit["p"],
                    "s_bare": coefficients.get("s_bare", math.nan),
                    "s_bare_se": standard_errors.get("s_bare", math.nan),
                    "s_nn": s_nn,
                    "s_nn_se": standard_errors.get("s_nn", math.nan),
                    "s_nnn": s_nnn,
                    "s_nnn_se": standard_errors.get("s_nnn", math.nan),
                    "gamma_spin": coefficients.get("gamma_spin", math.nan),
                    "gamma_spin_se": standard_errors.get("gamma_spin", math.nan),
                    "kappa21": coefficients.get("kappa21", math.nan),
                    "kappa21_se": standard_errors.get("kappa21", math.nan),
                    "delta": fit["delta"],
                    "delta_se": fit["delta_se"],
                    "effective_tprime_gz": (
                        spin.tprime * s_nnn / s_nn
                        if np.isfinite(s_nn) and np.isfinite(s_nnn) and s_nn != 0.0
                        else math.nan
                    ),
                    "s_nnn_over_s_nn": (
                        s_nnn / s_nn
                        if np.isfinite(s_nn) and np.isfinite(s_nnn) and s_nn != 0.0
                        else math.nan
                    ),
                    "rmse": fit["rmse"],
                    "mae": fit["mae"],
                    "max_abs_error": fit["max_abs_error"],
                    "r2": fit["r2"],
                    "aicc": fit["aicc"],
                    "bic": fit["bic"],
                    "condition_number": fit["condition_number"],
                    "path_block_cv_rmse": cv_rmse,
                    "cv_gamma_x_rmse": cv_blocks[0],
                    "cv_x_m_rmse": cv_blocks[1],
                    "cv_m_gamma_rmse": cv_blocks[2],
                }
                rows.append(row)
                if sample == "path_121":
                    predictions[(U, model)] = np.asarray(fit["prediction"], dtype=float)

    return pd.DataFrame(rows), predictions


def write_spin_table(spin_results: list[SpinResult]) -> pd.DataFrame:
    rows = []
    for result in spin_results:
        rows.append(
            {
                "resolution": "4x4",
                "tprime": result.tprime,
                "J2_over_J1": result.j2_over_j1,
                "E0_J1_units": result.energy,
                "E1_J1_units": result.first_excited_energy,
                "finite_size_spin_gap_J1_units": result.finite_size_gap,
                "C1_NN": result.c1,
                "C2_NNN": result.c2,
                "4C1": 4.0 * result.c1,
                "4C2": 4.0 * result.c2,
                "s_NN_asymptotic": result.s_nn,
                "s_NNN_asymptotic": result.s_nnn,
                "s_NNN_over_s_NN": result.s_nnn / result.s_nn,
                "effective_tprime_GZ_asymptotic": (
                    result.tprime_gz if result.tprime != 0.0 else math.nan
                ),
            }
        )
    frame = pd.DataFrame(rows)
    SPIN_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(SPIN_CSV, index=False)
    return frame


def write_curves(
    u_values: np.ndarray,
    k_path: np.ndarray,
    x_path: np.ndarray,
    roots: np.ndarray,
    bands: dict[str, np.ndarray],
    spin: SpinResult,
    predictions: dict[tuple[int, str], np.ndarray],
) -> pd.DataFrame:
    parameter_free = 4.0 * spin.c1 * bands["epsilon1"] + 4.0 * spin.c2 * bands["epsilon2"]
    rows: list[dict[str, object]] = []
    for u_index, U_raw in enumerate(u_values):
        U = int(U_raw)
        for k_index, ((kx, ky), xpos) in enumerate(zip(k_path, x_path)):
            rows.append(
                {
                    "eta": 0.05,
                    "tprime": -0.25,
                    "U": U,
                    "k_index": k_index,
                    "kx_index": int(kx),
                    "ky_index": int(ky),
                    "kx": float(kx * np.pi / 40.0),
                    "ky": float(ky * np.pi / 40.0),
                    "x_path": float(xpos),
                    "epsilon1": float(bands["epsilon1"][k_index]),
                    "epsilon2": float(bands["epsilon2"][k_index]),
                    "epsilon_bare": float(bands["epsilon_bare"][k_index]),
                    "chi21": float(bands["chi21"][k_index]),
                    "omega_GZ": float(roots[u_index, k_index]),
                    "omega_parameter_free_spin": float(parameter_free[k_index]),
                    "omega_bare_single_scale": float(
                        predictions[(U, "bare_single_scale")][k_index]
                    ),
                    "omega_spin_ratio_fit": float(predictions[(U, "spin_ratio")][k_index]),
                    "omega_two_bond_fit": float(predictions[(U, "two_bond")][k_index]),
                    "omega_two_bond_plus_chi21_fit": float(
                        predictions[(U, "two_bond_plus_chi21")][k_index]
                    ),
                }
            )
    frame = pd.DataFrame(rows)
    CURVES_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(CURVES_CSV, index=False)
    return frame


def plot_results(
    u_values: np.ndarray,
    x_path: np.ndarray,
    roots: np.ndarray,
    metrics: pd.DataFrame,
    spin: SpinResult,
    predictions: dict[tuple[int, str], np.ndarray],
) -> tuple[Path, Path]:
    colors = {
        "bare_single_scale": "#777777",
        "spin_ratio": "#d95f02",
        "two_bond": "#1b6ca8",
        "two_bond_plus_chi21": "#5e3c99",
    }
    primary = metrics[metrics["sample"] == "path_121"].copy()

    with plt.rc_context(STYLE):
        # Main-text panel: direct comparison between the extracted GZ and the
        # parameter-free bond-resolved spin prediction. The V-only companion
        # can later occupy the second panel of a two-panel layout.
        U = 40
        u_index = list(map(int, u_values)).index(U)
        parameter_free = predictions[(U, "spin_ratio")]
        spin_row = primary[(primary["U"] == U) & (primary["model"] == "spin_ratio")].iloc[0]
        # Remove the fitted finite-U gamma and offset to recover the genuine
        # parameter-free asymptotic spin expression.
        gamma = float(spin_row["gamma_spin"])
        delta = float(spin_row["delta"])
        parameter_free = (parameter_free - delta) / gamma

        fig, ax_curve = plt.subplots(figsize=(4.1, 2.85))
        ax_curve.plot(x_path, roots[u_index], color="black", lw=2.5, label="extracted GZ")
        ax_curve.plot(
            x_path,
            parameter_free,
            color=colors["spin_ratio"],
            ls=":",
            lw=2.4,
            label=(
                r"$4C_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}"
                r"+4C_{\mathrm{NNN}}\varepsilon_{\mathrm{NNN}}$"
            ),
        )
        ax_curve.axhline(0.0, color="0.75", lw=0.8)
        ax_curve.set_xlim(float(x_path[0]), float(x_path[-1]))
        ax_curve.set_xticks([x_path[0], x_path[40], x_path[80], x_path[120]])
        ax_curve.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
        ax_curve.set_ylabel(r"$E_{\rm GZ}(\mathbf{k})/t$")
        ax_curve.legend(frameon=False, loc="upper center", fontsize=8.8)
        fig.subplots_adjust(left=0.16, right=0.99, top=0.98, bottom=0.20)
        FIGURES.mkdir(parents=True, exist_ok=True)
        MAIN_FIGURES.mkdir(parents=True, exist_ok=True)
        pdf = FIGURE_STEM.with_suffix(".pdf")
        png = FIGURE_STEM.with_suffix(".png")
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=280, bbox_inches="tight")
        plt.close(fig)

        # Retain coefficient extraction and numerical fit diagnostics outside
        # the main figure.
        fig_diag = plt.figure(figsize=(9.1, 3.5))
        diag_grid = fig_diag.add_gridspec(1, 2, wspace=0.34)
        ax_coeff = fig_diag.add_subplot(diag_grid[0, 0])
        ax_rmse = fig_diag.add_subplot(diag_grid[0, 1])

        two_bond = primary[primary["model"] == "two_bond"].sort_values("U")
        x = 1.0 / two_bond["U"].to_numpy(float)
        ax_coeff.plot(x, two_bond["s_nn"], "o-", color="#1b6ca8", label=r"$s_{\rm NN}$")
        ax_coeff.plot(x, two_bond["s_nnn"], "s-", color="#d95f02", label=r"$s_{\rm NNN}$")
        ax_coeff.axhline(spin.s_nn, color="#1b6ca8", ls="--", lw=1.4)
        ax_coeff.axhline(spin.s_nnn, color="#d95f02", ls="--", lw=1.4)
        ax_coeff.set_xlim(0.0, 0.13)
        ax_coeff.set_xlabel(r"$t/U$")
        ax_coeff.set_ylabel("signed GZ coefficient")
        ax_coeff.legend(frameon=False, loc="center right", fontsize=8.7)

        model_order = [
            ("bare_single_scale", "one bare-band scale", "o"),
            ("nn_harmonic_only", "NN harmonic only", "v"),
            ("spin_ratio", "fixed spin ratio", "D"),
            ("two_bond", "two bond harmonics", "s"),
            ("two_bond_plus_chi21", r"two bonds + $\chi_{21}$", "^"),
        ]
        for model, label, marker in model_order:
            subset = primary[primary["model"] == model].sort_values("U")
            ax_rmse.plot(
                1.0 / subset["U"],
                subset["rmse"],
                marker=marker,
                ms=5,
                label=label,
            )
        ax_rmse.set_yscale("log")
        ax_rmse.set_xlim(0.0, 0.13)
        ax_rmse.set_xlabel(r"$t/U$")
        ax_rmse.set_ylabel("fit RMSE / $t$")
        ax_rmse.legend(frameon=False, loc="lower right", fontsize=8.2, handlelength=1.6)
        fig_diag.subplots_adjust(left=0.08, right=0.99, top=0.98, bottom=0.18)
        fig_diag.savefig(ANALYSIS_FIGURE_STEM.with_suffix(".pdf"), bbox_inches="tight")
        fig_diag.savefig(
            ANALYSIS_FIGURE_STEM.with_suffix(".png"), dpi=280, bbox_inches="tight"
        )
        plt.close(fig_diag)
    return pdf, png


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    source = np.load(SOURCE)
    eta = float(source["eta"])
    tprime = float(source["tp"])
    if not np.isclose(eta, 0.05):
        raise ValueError(f"Expected eta=0.05, found {eta}")
    if not np.isclose(tprime, -0.25):
        raise ValueError(f"Expected t'=-0.25, found {tprime}")
    u_values = np.asarray(source["U"], dtype=int)
    if list(u_values) != [8, 12, 20, 40]:
        raise ValueError(f"Unexpected U grid: {u_values.tolist()}")
    roots = np.asarray(source["omega_root"], dtype=float)
    if roots.shape != (4, 121) or not np.isfinite(roots).all():
        raise ValueError(f"Expected four complete 121-point curves, got {roots.shape}")

    # The t'=0 solution is a regression test: it must reproduce the C1 value
    # already used in the nearest-neighbour derivation.
    spin_tp0 = solve_j1j2(0.0)
    if not np.isclose(spin_tp0.c1, -0.3508901002634, atol=5.0e-12):
        raise RuntimeError(f"4x4 Heisenberg regression failed: C1={spin_tp0.c1}")
    spin = solve_j1j2(tprime)
    spin_table = write_spin_table([spin_tp0, spin])

    bands = harmonics(np.asarray(source["k_path"], dtype=int), tprime)
    metrics, predictions = fit_models(roots, bands, spin)
    RESULTS.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_CSV, index=False)
    curves = write_curves(
        u_values,
        np.asarray(source["k_path"], dtype=int),
        np.asarray(source["x_path"], dtype=float),
        roots,
        bands,
        spin,
        predictions,
    )
    pdf, png = plot_results(
        u_values,
        np.asarray(source["x_path"], dtype=float),
        roots,
        metrics,
        spin,
        predictions,
    )

    primary = metrics[metrics["sample"] == "path_121"]
    u40_two = primary[(primary["U"] == 40) & (primary["model"] == "two_bond")].iloc[0]
    u40_bare = primary[(primary["U"] == 40) & (primary["model"] == "bare_single_scale")].iloc[0]
    u40_spin = primary[(primary["U"] == 40) & (primary["model"] == "spin_ratio")].iloc[0]
    u40_higher = primary[
        (primary["U"] == 40) & (primary["model"] == "two_bond_plus_chi21")
    ].iloc[0]
    summary = {
        "source": str(SOURCE.relative_to(ROOT)),
        "eta": eta,
        "tprime": tprime,
        "u_values": u_values.tolist(),
        "root_completeness": {str(int(U)): int(np.isfinite(row).sum()) for U, row in zip(u_values, roots)},
        "strong_coupling": {
            "spin_model": "4x4 periodic J1-J2 Heisenberg model",
            "J2_over_J1": spin.j2_over_j1,
            "C1": spin.c1,
            "C2": spin.c2,
            "s_NN_equals_4_C1": spin.s_nn,
            "s_NNN_equals_4_C2": spin.s_nnn,
            "effective_tprime_GZ": spin.tprime_gz,
        },
        "U40_two_bond_fit": {
            "formula": "omega_GZ=s_NN*epsilon1+s_NNN*epsilon2+delta",
            "s_NN": float(u40_two["s_nn"]),
            "s_NNN": float(u40_two["s_nnn"]),
            "delta": float(u40_two["delta"]),
            "effective_tprime_GZ": float(u40_two["effective_tprime_gz"]),
            "rmse": float(u40_two["rmse"]),
            "r2": float(u40_two["r2"]),
            "s_NN_absolute_relative_difference_percent": float(
                100.0 * abs(float(u40_two["s_nn"]) - spin.s_nn) / abs(spin.s_nn)
            ),
            "s_NNN_absolute_relative_difference_percent": float(
                100.0 * abs(float(u40_two["s_nnn"]) - spin.s_nnn) / abs(spin.s_nnn)
            ),
        },
        "U40_model_comparison": {
            "bare_single_scale_rmse": float(u40_bare["rmse"]),
            "spin_ratio_fit_rmse": float(u40_spin["rmse"]),
            "spin_ratio_gamma": float(u40_spin["gamma_spin"]),
            "spin_ratio_delta": float(u40_spin["delta"]),
            "two_bond_rmse": float(u40_two["rmse"]),
            "two_bond_plus_chi21_rmse": float(u40_higher["rmse"]),
            "kappa21": float(u40_higher["kappa21"]),
            "bare_to_two_bond_rmse_reduction_percent": float(
                100.0 * (1.0 - float(u40_two["rmse"]) / float(u40_bare["rmse"]))
            ),
        },
        "interpretation": {
            "leading_parameters": ["s_NN", "s_NNN", "delta"],
            "asymptotic_relation": "s_NN=4C1<0 and s_NNN=4C2>0",
            "charge_role": (
                "No independent charge-correlation coefficient survives at leading order in the "
                "half-filled U-only projected manifold; charge fluctuations enter finite-U corrections."
            ),
            "optional_finite_U_term": "kappa21*chi21",
        },
        "outputs": {
            "metrics_csv": str(METRICS_CSV.relative_to(ROOT)),
            "curves_csv": str(CURVES_CSV.relative_to(ROOT)),
            "spin_csv": str(SPIN_CSV.relative_to(ROOT)),
            "figure_pdf": str(pdf.relative_to(ROOT)),
            "figure_png": str(png.relative_to(ROOT)),
        },
        "validation": {
            "curve_rows": int(len(curves)),
            "metrics_rows": int(len(metrics)),
            "spin_rows": int(len(spin_table)),
            "basis_condition_number_two_bond_path_121": float(u40_two["condition_number"]),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
