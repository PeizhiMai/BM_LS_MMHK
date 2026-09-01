#!/usr/bin/env python3
"""Analyze the bond-resolved Mott and charge Green-function-zero theorem.

The script is the reusable replacement for the old t'=-0.25-only fitter.  It
extracts roots directly from raw Lanczos pairs for arbitrary (U,V,t'), fits
the complete model hierarchy in the 2026-07-31 plan, analyzes large-V
corrections, and produces the planned 2x3 main-text figure.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fit_tpn25_zero_dispersion import harmonics, linear_fit, solve_j1j2
from generate_eta005_other_parameter_colorplots import (
    ParameterGroup,
    compute_group,
)
from manuscript_figure_style import outside_panel_label
from reproduce_luttinger_figures import centers_to_edges, default_k_path, x_centers


RESULTS = ROOT / "results"
DATA_OUT = ROOT / "data/Gcalpath/bond_resolved_zero_eta0p05"
FIGURE = ROOT / "figures/prl_main/prl_fig6_bond_resolved_mott_charge"
METRICS_CSV = RESULTS / "bond_resolved_zero_theorem_eta0p05.csv"
CORRECTIONS_CSV = RESULTS / "vonly_large_v_corrections_eta0p05.csv"
ROOT_AUDIT_CSV = RESULTS / "bond_resolved_zero_root_audit_eta0p05.csv"
SUMMARY_JSON = RESULTS / "bond_resolved_zero_theorem_summary_eta0p05.json"

COMPARISON_GROUPS = [
    ParameterGroup(40.0, 0.0, 0.0),
    ParameterGroup(40.0, 0.0, -0.25),
    ParameterGroup(40.0, 0.0, -0.4),
    ParameterGroup(0.0, 8.0, 0.0),
    ParameterGroup(0.0, 8.0, -0.25),
    ParameterGroup(0.0, 8.0, -0.4),
]
LARGE_V = [2.0, 4.0, 5.0, 8.0, 12.0, 16.0, 20.0]


@dataclass
class GroupData:
    group: ParameterGroup
    omega: np.ndarray
    rho: np.ndarray
    re_g: np.ndarray
    roots: np.ndarray
    root_rows: list[dict]
    ylim: float
    root_window: float
    color_vmax: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data/Gcalpath/Lanczos_raw_data",
    )
    parser.add_argument("--eta", type=float, default=0.05)
    parser.add_argument("--omega-max", type=float, default=60.0)
    parser.add_argument("--omega-points", type=int, default=6001)
    parser.add_argument("--steps-max", type=int, default=1000)
    parser.add_argument("--coordination", type=int, default=4)
    parser.add_argument("--rho-clean-ratio", type=float, default=0.25)
    parser.add_argument("--max-continuity-jump", type=float, default=2.0)
    parser.add_argument("--min-continuous-segment", type=int, default=5)
    parser.add_argument(
        "--check-inputs",
        action="store_true",
        help="Only print raw-file coverage and exit.",
    )
    return parser.parse_args()


def value_label(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def expected_files(group: ParameterGroup, data_dir: Path) -> list[Path]:
    files = []
    seen = set()
    for kx, ky in default_k_path():
        if (kx, ky) in seen:
            continue
        seen.add((kx, ky))
        for kind in ("Gh", "Gp"):
            files.append(
                data_dir
                / (
                    f"L4x4Nup8Ndn8U{value_label(group.U)}V{value_label(group.V)}"
                    f"tp{value_label(group.tp)}f{kx}x{ky}Q0x0_{kind}.dat"
                )
            )
    return files


def inventory(data_dir: Path) -> list[dict]:
    groups = COMPARISON_GROUPS + [ParameterGroup(0.0, V, 0.0) for V in LARGE_V]
    unique = {(g.U, g.V, g.tp): g for g in groups}
    rows = []
    for group in unique.values():
        files = expected_files(group, data_dir)
        missing = [str(path) for path in files if not path.is_file()]
        rows.append(
            {
                "U": group.U,
                "V": group.V,
                "tp": group.tp,
                "expected_files": len(files),
                "present_files": len(files) - len(missing),
                "missing_files": len(missing),
                "missing_sample": missing[:4],
            }
        )
    return rows


def extract_group(group: ParameterGroup, args: argparse.Namespace, omega: np.ndarray) -> GroupData:
    rho, re_g, roots, root_rows, ylim, root_window, color_vmax = compute_group(
        args.data_dir,
        group,
        omega,
        args.eta,
        (0, 0),
        args.steps_max,
        args.coordination,
        args.rho_clean_ratio,
        args.max_continuity_jump,
        args.min_continuous_segment,
    )
    return GroupData(group, omega, rho, re_g, roots, root_rows, ylim, root_window, color_vmax)


def metrics_from_prediction(y: np.ndarray, prediction: np.ndarray, n_parameters: int) -> dict:
    mask = np.isfinite(y) & np.isfinite(prediction)
    residual = y[mask] - prediction[mask]
    rss = float(np.dot(residual, residual))
    n = int(mask.sum())
    rmse = float(np.sqrt(rss / n))
    tss = float(np.dot(y[mask] - np.mean(y[mask]), y[mask] - np.mean(y[mask])))
    aic = float(n * np.log(max(rss / n, 1e-300)) + 2 * n_parameters)
    aicc = float(aic + 2 * n_parameters * (n_parameters + 1) / (n - n_parameters - 1))
    return {
        "n": n,
        "p": n_parameters,
        "rmse": rmse,
        "mae": float(np.mean(np.abs(residual))),
        "max_abs_error": float(np.max(np.abs(residual))),
        "r2": float(1.0 - rss / tss),
        "aicc": aicc,
    }


def expected_coefficients(group: ParameterGroup) -> tuple[float, float, str]:
    if group.U > 0 and group.V == 0:
        spin = solve_j1j2(group.tp)
        return -4.0 * spin.c1, 4.0 * spin.c2, "4x4_J1J2_spin"
    if group.U == 0 and group.V > 0:
        return 8.0 / 7.0, 1.0, "checkerboard_defect"
    raise ValueError(group)


def fit_group(data: GroupData) -> tuple[list[dict], dict[str, np.ndarray]]:
    group = data.group
    k_path = np.asarray(default_k_path(), dtype=int)
    bands = harmonics(k_path, group.tp)
    y = data.roots
    unique = np.arange(120, dtype=int)
    expected_nn, expected_nnn, mechanism = expected_coefficients(group)
    analytic_shape = -expected_nn * bands["epsilon1"] + expected_nnn * bands["epsilon2"]

    models: list[tuple[str, dict[str, np.ndarray]]] = [
        ("bare_single_scale", {"s_bare": -bands["epsilon_bare"]}),
        ("bond_resolved", {"s_nn": -bands["epsilon1"]}),
        ("fixed_strong_coupling_ratio", {"gamma": analytic_shape}),
    ]
    if not np.allclose(bands["epsilon2"], 0.0):
        models[1] = (
            "bond_resolved",
            {"s_nn": -bands["epsilon1"], "s_nnn": bands["epsilon2"]},
        )
        models.append(
            (
                "bond_resolved_plus_chi21",
                {
                    "s_nn": -bands["epsilon1"],
                    "s_nnn": bands["epsilon2"],
                    "kappa21": bands["chi21"],
                },
            )
        )
    else:
        models.append(
            (
                "bond_resolved_plus_chi21",
                {"s_nn": -bands["epsilon1"], "kappa21": bands["chi21"]},
            )
        )

    rows = []
    predictions = {}
    for model, predictors in models:
        fit = linear_fit(y, predictors, unique)
        pred = np.asarray(fit["prediction"])
        predictions[model] = pred
        coeff = fit["coefficients"]
        row = {
            "eta": 0.05,
            "U": group.U,
            "V": group.V,
            "tprime": group.tp,
            "mechanism": mechanism,
            "sample": "unique_120",
            "model": model,
            "root_count_unique": int(np.isfinite(y[:120]).sum()),
            "root_count_plotted": int(np.isfinite(data.roots).sum()),
            "s_bare": coeff.get("s_bare", math.nan),
            "s_nn": coeff.get("s_nn", math.nan),
            "s_nn_signed": -coeff.get("s_nn", math.nan),
            "s_nnn": coeff.get("s_nnn", math.nan),
            "gamma": coeff.get("gamma", math.nan),
            "kappa21": coeff.get("kappa21", math.nan),
            "delta": fit["delta"],
            "expected_s_nn": expected_nn,
            "expected_s_nn_signed": -expected_nn,
            "expected_s_nnn": expected_nnn,
            "s_nn_relative_error_percent": (
                100.0 * abs(coeff["s_nn"] - expected_nn) / abs(expected_nn)
                if "s_nn" in coeff else math.nan
            ),
            "s_nnn_relative_error_percent": (
                100.0 * abs(coeff["s_nnn"] - expected_nnn) / abs(expected_nnn)
                if "s_nnn" in coeff and expected_nnn else math.nan
            ),
            "n": fit["n"],
            "p": fit["p"],
            "rmse": fit["rmse"],
            "mae": fit["mae"],
            "max_abs_error": fit["max_abs_error"],
            "r2": fit["r2"],
            "aicc": fit["aicc"],
            "condition_number": fit["condition_number"],
        }
        rows.append(row)

    mask = np.isfinite(y[:120])
    delta = float(np.mean(y[:120][mask] - analytic_shape[:120][mask]))
    prediction = analytic_shape + delta
    predictions["parameter_free_strong_coupling"] = prediction
    stats = metrics_from_prediction(y[:120], prediction[:120], 1)
    rows.append(
        {
            "eta": 0.05,
            "U": group.U,
            "V": group.V,
            "tprime": group.tp,
            "mechanism": mechanism,
            "sample": "unique_120",
            "model": "parameter_free_strong_coupling",
            "root_count_unique": int(mask.sum()),
            "root_count_plotted": int(np.isfinite(data.roots).sum()),
            "s_bare": math.nan,
            "s_nn": expected_nn,
            "s_nn_signed": -expected_nn,
            "s_nnn": expected_nnn,
            "gamma": 1.0,
            "kappa21": math.nan,
            "delta": delta,
            "expected_s_nn": expected_nn,
            "expected_s_nn_signed": -expected_nn,
            "expected_s_nnn": expected_nnn,
            "s_nn_relative_error_percent": 0.0,
            "s_nnn_relative_error_percent": 0.0,
            **stats,
            "condition_number": math.nan,
        }
    )
    return rows, predictions


def large_v_analysis(group_data: dict[tuple[float, float, float], GroupData]) -> tuple[pd.DataFrame, list[dict], str]:
    observed = []
    epsilon1 = harmonics(np.asarray(default_k_path(), dtype=int), 0.0)["epsilon1"]
    for V in LARGE_V:
        data = group_data[(0.0, V, 0.0)]
        fit = linear_fit(data.roots, {"s_nn": -epsilon1}, np.arange(120))
        observed.append({"V": V, "s_nn": float(fit["coefficients"]["s_nn"]), "delta": fit["delta"], "root_count": int(np.isfinite(data.roots[:120]).sum()), "root_rmse": fit["rmse"]})
    frame = pd.DataFrame(observed)
    train = frame["V"].to_numpy() >= 5.0
    holdout = ~train
    x = 1.0 / frame["V"].to_numpy(float)
    y = frame["s_nn"].to_numpy(float)
    asymptote = 8.0 / 7.0
    definitions = {
        "linear": np.column_stack([x]),
        "quadratic": np.column_stack([x**2]),
        "linear_plus_quadratic": np.column_stack([x, x**2]),
        "even_through_fourth": np.column_stack([x**2, x**4]),
    }
    summaries = []
    predictions = {}
    for name, design in definitions.items():
        coef = np.linalg.lstsq(design[train], y[train] - asymptote, rcond=None)[0]
        pred = asymptote + design @ coef
        predictions[name] = pred
        summaries.append(
            {
                "model": name,
                "parameters": int(len(coef)),
                "coefficients": coef.tolist(),
                "train_rmse": float(np.sqrt(np.mean((y[train] - pred[train]) ** 2))),
                "holdout_rmse": float(np.sqrt(np.mean((y[holdout] - pred[holdout]) ** 2))),
                "all_rmse": float(np.sqrt(np.mean((y - pred) ** 2))),
            }
        )
    minimum = min(item["holdout_rmse"] for item in summaries)
    eligible = [item for item in summaries if item["holdout_rmse"] <= 1.05 * minimum]
    selected = sorted(eligible, key=lambda item: (item["parameters"], item["holdout_rmse"], item["model"]))[0]["model"]
    for name, pred in predictions.items():
        frame[f"prediction_{name}"] = pred
        frame[f"residual_{name}"] = y - pred
    frame["fit_role"] = np.where(train, "train", "holdout")
    frame["selected_model"] = selected
    return frame, summaries, selected


def save_group_data(data: GroupData) -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    stem = f"U{value_label(data.group.U)}_V{value_label(data.group.V)}_tp{value_label(data.group.tp).replace('-', 'n').replace('.', 'p')}"
    np.savez_compressed(
        DATA_OUT / f"{stem}.npz",
        U=data.group.U,
        V=data.group.V,
        tp=data.group.tp,
        eta=0.05,
        omega=data.omega,
        x_path=x_centers(),
        k_path=np.asarray(default_k_path(), dtype=int),
        rho_G=data.rho,
        reG=data.re_g,
        omega_root=data.roots,
    )


def write_root_audit(group_data: dict[tuple[float, float, float], GroupData]) -> pd.DataFrame:
    rows = []
    path = default_k_path()
    xpos = x_centers()
    for data in group_data.values():
        for i, ((kx, ky), x, row) in enumerate(zip(path, xpos, data.root_rows)):
            rows.append(
                {
                    "U": data.group.U,
                    "V": data.group.V,
                    "tprime": data.group.tp,
                    "eta": 0.05,
                    "k_index": i,
                    "kx": kx,
                    "ky": ky,
                    "x_path": x,
                    **row,
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(ROOT_AUDIT_CSV, index=False)
    return frame


def decorate_path_axis(ax: plt.Axes) -> None:
    x = x_centers()
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.axvline(x[40], color="0.55", ls="--", lw=0.7)
    ax.axvline(x[80], color="0.55", ls="--", lw=0.7)


def spectrum_panel(ax: plt.Axes, data: GroupData, ylim: float) -> None:
    x = x_centers()
    mask = np.abs(data.omega) <= ylim
    cmap = plt.get_cmap("rainbow").copy()
    z = np.maximum(data.rho[:, mask], 0.0).T
    ax.pcolormesh(
        centers_to_edges(x),
        centers_to_edges(data.omega[mask]),
        z,
        shading="auto",
        cmap=cmap,
        vmin=0.0,
        vmax=data.color_vmax,
    )
    ax.plot(x, data.roots, color="white", lw=1.6)
    ax.axhline(0.0, color="black", ls="--", lw=0.8)
    ax.set_ylim(-ylim, ylim)
    decorate_path_axis(ax)
    ax.set_ylabel(r"$\omega/t$")


def plot_figure(group_data: dict[tuple[float, float, float], GroupData], metrics: pd.DataFrame, predictions: dict[tuple[float, float, float], dict[str, np.ndarray]], corrections: pd.DataFrame) -> tuple[Path, Path]:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9.0,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.4,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(12.4, 6.9))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.09, top=0.97, wspace=0.28, hspace=0.34)
    colors = {0.0: "#377eb8", -0.25: "#4daf4a", -0.4: "#e41a1c"}
    x = x_centers()

    mott04 = group_data[(40.0, 0.0, -0.4)]
    spectrum_panel(axes[0, 0], mott04, min(24.0, mott04.ylim))
    axes[0, 0].set_title(r"$U=40,\ V=0,\ t'=-0.4t$")

    key = (40.0, 0.0, -0.4)
    axes[0, 1].plot(x, mott04.roots, color="black", lw=2.0, label="extracted GZ")
    axes[0, 1].plot(x, predictions[key]["bare_single_scale"], color="0.55", ls="--", label="one scale")
    axes[0, 1].plot(x, predictions[key]["bond_resolved"], color="#984ea3", label="NN+NNN fit")
    axes[0, 1].plot(x, predictions[key]["parameter_free_strong_coupling"], color="#ff7f00", ls=":", lw=2.1, label="spin prediction")
    axes[0, 1].axhline(0.0, color="0.7", lw=0.6)
    decorate_path_axis(axes[0, 1])
    axes[0, 1].set_ylabel(r"$\omega_{\rm GZ}/t$")
    axes[0, 1].legend(frameon=False, ncol=2, loc="upper center")

    for tp in (0.0, -0.25, -0.4):
        subset = metrics[(metrics.U == 40) & (metrics.V == 0) & np.isclose(metrics.tprime, tp) & (metrics.model == "bond_resolved")]
        row = subset.iloc[0]
        axes[0, 2].scatter(tp, row.s_nn_signed, color=colors[tp], marker="o", s=34)
        if np.isfinite(row.s_nnn):
            axes[0, 2].scatter(tp, row.s_nnn, color=colors[tp], marker="s", s=34)
        spin = solve_j1j2(tp)
        axes[0, 2].scatter(tp, 4.0 * spin.c1, facecolors="none", edgecolors=colors[tp], marker="o", s=58)
        axes[0, 2].scatter(tp, 4.0 * spin.c2, facecolors="none", edgecolors=colors[tp], marker="s", s=58)
    axes[0, 2].plot([], [], "ko", label=r"fit $s_{\rm NN}$")
    axes[0, 2].plot([], [], "ks", label=r"fit $s_{\rm NNN}$")
    axes[0, 2].scatter([], [], facecolors="none", edgecolors="k", marker="o", label="spin prediction")
    axes[0, 2].set_xlabel(r"$t'/t$")
    axes[0, 2].set_ylabel("bond coefficient")
    axes[0, 2].legend(frameon=False, loc="best")

    charge04 = group_data[(0.0, 8.0, -0.4)]
    spectrum_panel(axes[1, 0], charge04, min(30.0, charge04.ylim))
    axes[1, 0].set_title(r"$U=0,\ V=8,\ t'=-0.4t$")

    for tp in (0.0, -0.25, -0.4):
        data = group_data[(0.0, 8.0, tp)]
        axes[1, 1].plot(x, data.roots, color=colors[tp], lw=1.8, label=rf"$t'={tp:g}t$")
        axes[1, 1].plot(x, predictions[(0.0, 8.0, tp)]["parameter_free_strong_coupling"], color=colors[tp], ls="--", lw=1.0)
    axes[1, 1].axhline(0.0, color="0.7", lw=0.6)
    decorate_path_axis(axes[1, 1])
    axes[1, 1].set_ylabel(r"$\omega_{\rm GZ}/t$")
    axes[1, 1].legend(frameon=False, ncol=3, loc="upper center")

    for tp in (0.0, -0.25, -0.4):
        subset = metrics[(metrics.U == 0) & (metrics.V == 8) & np.isclose(metrics.tprime, tp) & (metrics.model == "bond_resolved")]
        row = subset.iloc[0]
        axes[1, 2].scatter(tp, row.s_nn_signed, color=colors[tp], marker="o", s=34)
        if np.isfinite(row.s_nnn):
            axes[1, 2].scatter(tp, row.s_nnn, color=colors[tp], marker="s", s=34)
    axes[1, 2].axhline(-8.0 / 7.0, color="black", ls="--", lw=1.0, label=r"$-8/7$")
    axes[1, 2].axhline(1.0, color="0.45", ls=":", lw=1.0, label=r"NNN guide $1$")
    axes[1, 2].set_xlabel(r"$t'/t$")
    axes[1, 2].set_ylabel("charge-side coefficient")
    axes[1, 2].legend(frameon=False, loc="best")
    inset = axes[1, 2].inset_axes([0.12, 0.12, 0.42, 0.34])
    inset.plot(1.0 / corrections.V, -corrections.s_nn + 8.0 / 7.0, "o", ms=3, color="#377eb8")
    selected = corrections.selected_model.iloc[0]
    inset.plot(1.0 / corrections.V, -corrections[f"prediction_{selected}"] + 8.0 / 7.0, "-", lw=1, color="#e41a1c")
    inset.set_xlabel(r"$t/V$", fontsize=6)
    inset.set_ylabel(r"$s_{\rm NN}+8/7$", fontsize=6)
    inset.tick_params(labelsize=5.5)

    for label, ax in zip("ABCDEF", axes.ravel()):
        outside_panel_label(ax, label, x=-0.12, y=1.04)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    pdf = FIGURE.with_suffix(".pdf")
    png = FIGURE.with_suffix(".png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=280, bbox_inches="tight")
    plt.close(fig)
    if pdf.read_bytes()[:4] != b"%PDF":
        raise RuntimeError("Invalid PDF output")
    return pdf, png


def main() -> None:
    args = parse_args()
    args.data_dir = args.data_dir.resolve()
    coverage = inventory(args.data_dir)
    print(json.dumps({"coverage": coverage}, indent=2))
    if args.check_inputs:
        return
    missing = [row for row in coverage if row["missing_files"]]
    if missing:
        raise FileNotFoundError("Required raw-data groups are incomplete: " + json.dumps(missing, indent=2))
    if not np.isclose(args.eta, 0.05):
        raise ValueError("The planned analysis is fixed at eta=0.05")

    RESULTS.mkdir(parents=True, exist_ok=True)
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    omega = np.linspace(-args.omega_max, args.omega_max, args.omega_points)
    required = COMPARISON_GROUPS + [ParameterGroup(0.0, V, 0.0) for V in LARGE_V]
    unique_groups = {(g.U, g.V, g.tp): g for g in required}
    group_data = {}
    for key, group in unique_groups.items():
        print(f"Extracting U={group.U:g} V={group.V:g} tp={group.tp:g}", flush=True)
        data = extract_group(group, args, omega)
        group_data[key] = data
        save_group_data(data)

    root_audit = write_root_audit(group_data)
    metric_rows = []
    predictions = {}
    for group in COMPARISON_GROUPS:
        key = (group.U, group.V, group.tp)
        rows, pred = fit_group(group_data[key])
        metric_rows.extend(rows)
        predictions[key] = pred
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(METRICS_CSV, index=False)
    corrections, correction_models, selected_correction = large_v_analysis(group_data)
    corrections.to_csv(CORRECTIONS_CSV, index=False)
    pdf, png = plot_figure(group_data, metrics, predictions, corrections)

    def row(U, V, tp, model):
        return metrics[(metrics.U == U) & (metrics.V == V) & np.isclose(metrics.tprime, tp) & (metrics.model == model)].iloc[0]

    mott_bond = row(40.0, 0.0, -0.4, "bond_resolved")
    mott_bare = row(40.0, 0.0, -0.4, "bare_single_scale")
    charge_rows = [row(0.0, 8.0, tp, "bond_resolved") for tp in (-0.25, -0.4)]
    mott_accept = bool(
        mott_bond.rmse <= 0.75 * mott_bare.rmse
        and mott_bond.s_nn_relative_error_percent <= 5.0
        and mott_bond.s_nnn_relative_error_percent <= 5.0
    )
    charge_accept = bool(
        all(item.s_nn > 0 and item.s_nnn > 0 for item in charge_rows)
        and all(item.s_nn_relative_error_percent <= 15.0 for item in charge_rows)
        and all(item.s_nnn_relative_error_percent <= 15.0 for item in charge_rows)
    )
    root_completeness = {
        f"U{value_label(U)}_V{value_label(V)}_tp{value_label(tp)}": int(np.isfinite(data.roots).sum())
        for (U, V, tp), data in group_data.items()
    }
    summary = {
        "plan": "notes/2026-07-31_vonly_tprime_zero_dispersion_plan.md",
        "data_dir": str(args.data_dir),
        "eta": args.eta,
        "root_completeness": root_completeness,
        "mott_tpn04": {
            "bond_resolved_rmse": float(mott_bond.rmse),
            "one_scale_rmse": float(mott_bare.rmse),
            "rmse_reduction_percent": float(100.0 * (1.0 - mott_bond.rmse / mott_bare.rmse)),
            "s_nn": float(mott_bond.s_nn),
            "s_nn_signed": float(mott_bond.s_nn_signed),
            "s_nnn": float(mott_bond.s_nnn),
            "s_nn_expected": float(mott_bond.expected_s_nn),
            "s_nn_signed_expected": float(mott_bond.expected_s_nn_signed),
            "s_nnn_expected": float(mott_bond.expected_s_nnn),
            "s_nn_relative_error_percent": float(mott_bond.s_nn_relative_error_percent),
            "s_nnn_relative_error_percent": float(mott_bond.s_nnn_relative_error_percent),
            "accepted_within_5_percent_and_decisive_improvement": mott_accept,
        },
        "charge_v8": [
            {
                "tprime": float(item.tprime),
                "s_nn": float(item.s_nn),
                "s_nn_signed": float(item.s_nn_signed),
                "s_nnn": float(item.s_nnn),
                "s_nn_relative_error_percent": float(item.s_nn_relative_error_percent),
                "s_nnn_relative_error_percent": float(item.s_nnn_relative_error_percent),
                "rmse": float(item.rmse),
            }
            for item in charge_rows
        ],
        "charge_formula_accepted": charge_accept,
        "charge_follow_up": None if charge_accept else "Retain the finite-V deviation and recommend a later V=12 nonzero-tprime check.",
        "large_v_correction_models": correction_models,
        "selected_large_v_correction": selected_correction,
        "outputs": {
            "metrics_csv": str(METRICS_CSV.relative_to(ROOT)),
            "corrections_csv": str(CORRECTIONS_CSV.relative_to(ROOT)),
            "root_audit_csv": str(ROOT_AUDIT_CSV.relative_to(ROOT)),
            "figure_pdf": str(pdf.relative_to(ROOT)),
            "figure_png": str(png.relative_to(ROOT)),
        },
        "validation": {
            "all_new_groups_have_121_plotted_roots": all(root_completeness[f"U{value_label(g.U)}_V{value_label(g.V)}_tp{value_label(g.tp)}"] == 121 for g in COMPARISON_GROUPS),
            "root_audit_rows": int(len(root_audit)),
            "metrics_rows": int(len(metrics)),
            "correction_rows": int(len(corrections)),
            "pdf_header_valid": pdf.read_bytes()[:4] == b"%PDF",
            "png_nonempty": png.stat().st_size > 0,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
