#!/usr/bin/env python3
"""Analyze even-n convergence of 1D spinless t-V n-MMHK energies.

The input is a pandas pickle supplied by the user.  It is loaded through a
strict global whitelist rather than through ``pandas.read_pickle`` because
ordinary pickle loading can execute arbitrary code.

For V/t > 2, the thermodynamic grand-canonical energy per site follows from
the Bethe-ansatz ground-state energy of the antiferromagnetic XXZ chain,

    Delta = V/(2t) = cosh(eta),
    e_XXZ/J = Delta/4 - sinh(eta) [1/2 + 2 sum_{m>=1} 1/(1+exp(2m eta))],

with J=2t.  The chemical-potential convention mu=V adds the constant -V/4,
so e_infinity = e_XXZ - V/4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from numpy.core.multiarray import _reconstruct
from numpy.core.numeric import _frombuffer
from pandas._libs.internals import _unpickle_block
from pandas.core.frame import DataFrame
from pandas.core.indexes.base import Index, _new_Index
from pandas.core.indexes.range import RangeIndex
from pandas.core.internals.managers import BlockManager


DEFAULT_INPUT = Path("/Users/cosdis/Downloads/mmhk_tV1_ground_state_energies.pkl")
DEFAULT_V = (4.0, 6.0, 8.0)


_SAFE_GLOBALS = {
    ("pandas.core.frame", "DataFrame"): DataFrame,
    ("pandas.core.internals.managers", "BlockManager"): BlockManager,
    ("pandas._libs.internals", "_unpickle_block"): _unpickle_block,
    # NumPy 2 writes numpy._core paths; map them to the NumPy 1.26 symbols in
    # the project virtual environment.
    ("numpy._core.numeric", "_frombuffer"): _frombuffer,
    ("numpy", "dtype"): np.dtype,
    ("builtins", "slice"): slice,
    ("pandas.core.indexes.base", "_new_Index"): _new_Index,
    ("pandas.core.indexes.base", "Index"): Index,
    ("numpy._core.multiarray", "_reconstruct"): _reconstruct,
    ("numpy", "ndarray"): np.ndarray,
    ("pandas.core.indexes.range", "RangeIndex"): RangeIndex,
}


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):  # type: ignore[override]
        try:
            return _SAFE_GLOBALS[(module, name)]
        except KeyError as exc:
            raise pickle.UnpicklingError(
                f"Blocked non-data pickle global: {module}.{name}"
            ) from exc


def load_dataframe(path: Path) -> pd.DataFrame:
    with path.open("rb") as handle:
        obj = _RestrictedUnpickler(handle).load()
    if not isinstance(obj, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, received {type(obj)!r}")
    required = {"n", "V", "energy", "density"}
    if set(obj.columns) != required:
        raise ValueError(f"Unexpected columns {list(obj.columns)!r}; expected {sorted(required)}")
    out = obj.copy()
    if out.duplicated(["n", "V"]).any():
        raise ValueError("Duplicate (n,V) rows are present")
    if not np.allclose(out["density"], 0.5, atol=1e-12, rtol=0):
        raise ValueError("The supplied data are not uniformly at half filling")
    out["e_per_site"] = out["energy"] / out["n"]
    return out


def bethe_grand_energy_per_site(V: float, t: float = 1.0) -> float:
    """Thermodynamic half-filled grand-potential density for V/t > 2."""

    delta = V / (2.0 * t)
    if delta <= 1.0:
        raise ValueError("The hyperbolic XXZ series used here requires V/t > 2")
    eta = math.acosh(delta)
    series = 0.0
    for m in range(1, 100_000):
        # This form avoids overflow for large m*eta.
        q = math.exp(-2.0 * m * eta)
        term = q / (1.0 + q)
        series += term
        if term < 1e-16:
            break
    else:
        raise RuntimeError("Bethe-ansatz series did not converge")
    j = 2.0 * t
    e_xxz = j * (delta / 4.0 - math.sinh(eta) * (0.5 + 2.0 * series))
    return e_xxz - V / 4.0


def linear_fit_with_covariance(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ beta
    dof = len(y) - X.shape[1]
    sigma2 = float(residual @ residual / dof) if dof > 0 else float("nan")
    covariance = sigma2 * np.linalg.inv(X.T @ X)
    return beta, covariance


def fit_models(n: np.ndarray, error: np.ndarray) -> dict[str, float]:
    if np.any(error <= 0):
        raise ValueError("All convergence errors must be positive for logarithmic fits")
    log_error = np.log(error)

    # Log-space estimate used to initialize the nonlinear fit robustly even
    # when the last few deterministic errors are many orders of magnitude
    # smaller than the first.
    Xp = np.column_stack([np.ones_like(n), -np.log(n)])
    bp, cp = linear_fit_with_covariance(Xp, log_error)

    # First retain the zero-intercept power law as a diagnostic.
    def zero_offset_power_model(
        n_value: np.ndarray, amplitude: float, exponent: float
    ) -> np.ndarray:
        return amplitude * np.power(n_value, -exponent)

    error_scale = float(error.max())
    zero_parameters_scaled, zero_covariance_scaled = curve_fit(
        zero_offset_power_model,
        n,
        error / error_scale,
        p0=(math.exp(bp[0]) / error_scale, bp[1]),
        bounds=((0.0, 0.0), (np.inf, np.inf)),
        maxfev=100_000,
        ftol=1e-14,
        xtol=1e-14,
        gtol=1e-14,
    )
    zero_parameters = np.array(
        [zero_parameters_scaled[0] * error_scale, zero_parameters_scaled[1]]
    )
    zero_covariance = zero_covariance_scaled.copy()
    zero_covariance[0, :] *= error_scale
    zero_covariance[:, 0] *= error_scale
    zero_prediction_linear = zero_offset_power_model(n, *zero_parameters)
    zero_residual_linear = error - zero_prediction_linear
    zero_rss_linear = float(zero_residual_linear @ zero_residual_linear)

    # Displayed fit: error = c + A n^{-r}.  The fitted c is allowed to float
    # because a short finite-n window need not extrapolate exactly through the
    # known Bethe-limit intercept.  It is a finite-window correction, not a
    # redefinition of the exact thermodynamic energy.
    def power_model(
        n_value: np.ndarray, offset: float, amplitude: float, exponent: float
    ) -> np.ndarray:
        return offset + amplitude * np.power(n_value, -exponent)

    power_parameters_scaled, power_covariance_scaled = curve_fit(
        power_model,
        n,
        error / error_scale,
        p0=(0.0, zero_parameters_scaled[0], zero_parameters_scaled[1]),
        bounds=((-np.inf, 0.0, 0.0), (np.inf, np.inf, np.inf)),
        maxfev=100_000,
        ftol=1e-14,
        xtol=1e-14,
        gtol=1e-14,
    )
    power_parameters = np.array(
        [
            power_parameters_scaled[0] * error_scale,
            power_parameters_scaled[1] * error_scale,
            power_parameters_scaled[2],
        ]
    )
    power_covariance = power_covariance_scaled.copy()
    for index in (0, 1):
        power_covariance[index, :] *= error_scale
        power_covariance[:, index] *= error_scale
    power_prediction_linear = power_model(n, *power_parameters)
    power_residual_linear = error - power_prediction_linear
    power_rss_linear = float(power_residual_linear @ power_residual_linear)
    power_tss_linear = float(((error - error.mean()) ** 2).sum())

    # A log-space power fit is retained as a sensitivity diagnostic because it
    # weights the smallest errors more strongly.
    pred_p = Xp @ bp
    p = float(bp[1])

    # Exponential: log(error) = log(B) - n/xi.
    Xe = np.column_stack([np.ones_like(n), -n])
    be, ce = linear_fit_with_covariance(Xe, log_error)
    pred_e = Xe @ be
    inv_xi = float(be[1])

    def metrics(pred: np.ndarray) -> tuple[float, float, float]:
        residual = log_error - pred
        rss = float(residual @ residual)
        rmse = math.sqrt(rss / len(n))
        tss = float(((log_error - log_error.mean()) ** 2).sum())
        r2 = 1.0 - rss / tss
        aic = len(n) * math.log(rss / len(n)) + 2.0 * 2
        return rmse, r2, aic

    prmse, pr2, paic = metrics(pred_p)
    ermse, er2, eaic = metrics(pred_e)
    return {
        "power_offset": float(power_parameters[0]),
        "power_offset_fit_se": float(math.sqrt(power_covariance[0, 0])),
        "power_amplitude": float(power_parameters[1]),
        "power_amplitude_fit_se": float(math.sqrt(power_covariance[1, 1])),
        "power_exponent": float(power_parameters[2]),
        "power_exponent_fit_se": float(math.sqrt(power_covariance[2, 2])),
        "power_linear_rmse": math.sqrt(power_rss_linear / len(n)),
        "power_linear_r2": 1.0 - power_rss_linear / power_tss_linear,
        "zero_offset_power_amplitude": float(zero_parameters[0]),
        "zero_offset_power_exponent": float(zero_parameters[1]),
        "zero_offset_power_exponent_fit_se": float(
            math.sqrt(zero_covariance[1, 1])
        ),
        "zero_offset_power_linear_rmse": math.sqrt(zero_rss_linear / len(n)),
        "power_log_amplitude": float(math.exp(bp[0])),
        "power_log_exponent": p,
        "power_log_exponent_fit_se": float(math.sqrt(cp[1, 1])),
        "power_log_rmse": prmse,
        "power_log_r2": pr2,
        "power_log_aic": paic,
        "exponential_amplitude": float(math.exp(be[0])),
        "exponential_xi": float(1.0 / inv_xi),
        "exponential_xi_fit_se": float(
            math.sqrt(ce[1, 1]) / (inv_xi * inv_xi)
        ),
        "exponential_log_rmse": ermse,
        "exponential_log_r2": er2,
        "exponential_log_aic": eaic,
    }


def plot_convergence(points: pd.DataFrame, fits: pd.DataFrame, output_base: Path) -> None:
    colors = {4.0: "#5AA0C8", 6.0: "#F2A900", 8.0: "#A75B9E"}
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 10.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, ax = plt.subplots(figsize=(4.55, 3.70))
    fig.subplots_adjust(left=0.19, right=0.98, bottom=0.19, top=0.96)

    x_data_max = float((1.0 / points["n"]).max())
    xfit = np.linspace(0.0, 1.035 * x_data_max, 500)
    for V in DEFAULT_V:
        group = points[np.isclose(points["V"], V)].sort_values("n")
        fit = fits[np.isclose(fits["V"], V)].iloc[0]
        color = colors[V]
        ax.plot(
            1.0 / group["n"],
            group["delta_e"],
            "o",
            ms=6.3,
            color=color,
            mfc=color,
            mec="white",
            mew=0.45,
            linestyle="none",
            zorder=4,
            label=rf"$V/t={V:g}$",
        )
        yfit = (
            fit["power_offset"]
            + fit["power_amplitude"] * np.power(xfit, fit["power_exponent"])
        )
        ax.plot(
            xfit,
            yfit,
            color=color,
            lw=1.65,
            linestyle=(0, (2.0, 2.0)),
            zorder=2,
        )

    ax.text(
        -0.15,
        0.965,
        "(a)",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=15,
        fontweight="bold",
        clip_on=False,
    )
    exponent_text = "\n".join(
        rf"$V/t={row.V:g}:\ r={row.power_exponent:.2f}$"
        for row in fits.itertuples()
    )
    ax.text(
        0.05,
        0.835,
        exponent_text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10.2,
        color="#222222",
    )
    ax.legend(
        loc="upper left",
        frameon=False,
        ncol=3,
        columnspacing=0.75,
        handletextpad=0.25,
        borderaxespad=0.45,
    )
    ax.set_xlabel(r"$1/n$")
    ax.set_ylabel(r"$E_{t\mathrm{-}V}^{\infty}-E_{\mathrm{MMHK}}^{(n)}$")
    ax.set_xlim(-0.025 * x_data_max, 1.055 * x_data_max)
    ymax = 1.08 * points["delta_e"].max()
    # Keep zero visibly above the lower frame so markers at very small error
    # remain fully visible rather than being clipped by the bottom spine.
    ax.set_ylim(-0.075 * ymax, ymax)
    ax.minorticks_on()
    ax.tick_params(which="major", direction="in", length=4.0, width=0.9, top=True, right=True)
    ax.tick_params(which="minor", direction="in", length=2.2, width=0.7, top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)

    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--n-min", type=int, default=4)
    parser.add_argument("--n-max", type=int, default=20)
    parser.add_argument(
        "--output-base",
        type=Path,
        default=Path("figures/mmhk_tV1_ground_state_convergence"),
    )
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results")
    )
    args = parser.parse_args()

    data = load_dataframe(args.input)
    selected = data[
        data["V"].isin(DEFAULT_V)
        & (data["n"] % 2 == 0)
        & (data["n"] >= args.n_min)
        & (data["n"] <= args.n_max)
    ].copy()
    expected = len(DEFAULT_V) * len(range(args.n_min, args.n_max + 1, 2))
    if len(selected) != expected:
        raise ValueError(f"Expected {expected} selected rows, found {len(selected)}")

    fit_rows: list[dict[str, float | int | str]] = []
    for V in DEFAULT_V:
        group = selected[np.isclose(selected["V"], V)].sort_values("n").copy()
        e_inf = bethe_grand_energy_per_site(V)
        selected.loc[group.index, "e_infinity_bethe"] = e_inf
        selected.loc[group.index, "delta_e"] = e_inf - group["e_per_site"]
        error = (e_inf - group["e_per_site"]).to_numpy(float)
        model = fit_models(group["n"].to_numpy(float), error)

        # Window sensitivity is more meaningful than a statistical confidence
        # interval for these deterministic data.
        sensitivity_minima = (args.n_min, args.n_min + 2, args.n_min + 4)
        exponents = []
        for n_min_sensitivity in sensitivity_minima:
            mask = group["n"].to_numpy(float) >= n_min_sensitivity
            exponents.append(
                fit_models(group.loc[mask, "n"].to_numpy(float), error[mask])[
                    "power_exponent"
                ]
            )
        fit_rows.append(
            {
                "V": V,
                "n_min": args.n_min,
                "n_max": args.n_max,
                "n_points": len(group),
                "e_infinity_bethe": e_inf,
                **model,
                **{
                    f"power_exponent_nmin{n_min_value}": exponent
                    for n_min_value, exponent in zip(sensitivity_minima, exponents)
                },
                "preferred_in_log_space": (
                    "power"
                    if model["power_log_aic"] < model["exponential_log_aic"]
                    else "exponential"
                ),
            }
        )

    fits = pd.DataFrame(fit_rows)
    selected = selected.sort_values(["V", "n"]).reset_index(drop=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    result_stem = args.output_base.name
    points_path = args.results_dir / f"{result_stem}_points.csv"
    fits_path = args.results_dir / f"{result_stem}_fits.csv"
    summary_path = args.results_dir / f"{result_stem}_summary.json"
    selected.to_csv(points_path, index=False)
    fits.to_csv(fits_path, index=False)
    plot_convergence(selected, fits, args.output_base)

    summary = {
        "status": "COMPLETE",
        "input": str(args.input),
        "input_sha256": sha256(args.input),
        "input_shape": list(data.shape),
        "input_columns": list(data.columns),
        "input_attrs": data.attrs,
        "selection": {
            "V_over_t": list(DEFAULT_V),
            "parity": "even n only",
            "n_min": args.n_min,
            "n_max": args.n_max,
        },
        "fit_definition": (
            "delta_e=c+A*n^(-r), unweighted nonlinear least squares in delta_e"
        ),
        "fit_sensitivity": (
            "The CSV also gives the previous zero-offset power fit, a log-space "
            "power fit, an exponential fit, and offset-power exponents after "
            "raising n_min by two and four."
        ),
        "delta_e_definition": "e_infinity_Bethe - energy/n",
        "interpretation": (
            "The quoted r values and offsets are finite-window effective fit "
            "parameters; the exact Bethe-limit intercept remains zero. "
            "Because V/t>2 is gapped, convergence is ultimately expected to be "
            "exponential; the increasing r with V and n_min diagnoses that crossover."
        ),
        "artifacts": {
            "points_csv": str(points_path),
            "fits_csv": str(fits_path),
            "figure_pdf": str(args.output_base.with_suffix(".pdf")),
            "figure_png": str(args.output_base.with_suffix(".png")),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(fits.to_string(index=False))
    print(f"\nWrote {args.output_base.with_suffix('.pdf')}")
    print(f"Wrote {fits_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
