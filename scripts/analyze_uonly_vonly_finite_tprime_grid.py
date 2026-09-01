#!/usr/bin/env python3
"""Analyze the complete U-only/V-only finite-t' Gcalpath grid.

This is a non-manuscript analysis companion to
``analyze_bond_resolved_zero_theorem.py``.  It applies the established
eta=0.05 root tracker and bond-resolved model hierarchy to the 16 requested
sets

  * (U,V)=(8,0),(12,0),(20,0),(40,0), and
  * (U,V)=(0,2),(0,5),(0,8),(0,12),

at t'=-0.25 and -0.4.  The script writes a complete model table, a compact
one-row-per-set table, a root audit, a JSON summary, and a convergence figure.
It deliberately does not edit manuscript files.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_bond_resolved_zero_theorem as theorem
from analyze_bond_resolved_zero_theorem import GroupData, expected_files, fit_group
from fit_tpn25_zero_dispersion import harmonics, linear_fit
from generate_eta005_other_parameter_colorplots import ParameterGroup, compute_group
from reproduce_luttinger_figures import default_k_path, x_centers


U_VALUES = (8.0, 12.0, 20.0, 40.0)
V_VALUES = (2.0, 5.0, 8.0, 12.0)
TP_VALUES = (-0.25, -0.4)
GROUPS = (
    [ParameterGroup(U, 0.0, tp) for tp in TP_VALUES for U in U_VALUES]
    + [ParameterGroup(0.0, V, tp) for tp in TP_VALUES for V in V_VALUES]
)

RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
DATE_TAG = "20260802"
ALL_MODELS_CSV = RESULTS / f"uonly_vonly_finite_tprime_all_models_eta0p05_{DATE_TAG}.csv"
SUMMARY_CSV = RESULTS / f"uonly_vonly_finite_tprime_bond_resolved_eta0p05_{DATE_TAG}.csv"
ROOT_AUDIT_CSV = RESULTS / f"uonly_vonly_finite_tprime_root_audit_eta0p05_{DATE_TAG}.csv"
SUMMARY_JSON = RESULTS / f"uonly_vonly_finite_tprime_summary_eta0p05_{DATE_TAG}.json"
ROOTS_NPZ = ROOT / "data/Gcalpath" / f"uonly_vonly_finite_tprime_roots_eta0p05_{DATE_TAG}.npz"
FIGURE_STEM = FIGURES / f"uonly_vonly_finite_tprime_bond_coefficients_eta0p05_{DATE_TAG}"


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
    parser.add_argument("--check-inputs", action="store_true")
    return parser.parse_args()


def coverage_rows(data_dir: Path) -> list[dict]:
    rows = []
    for group in GROUPS:
        files = expected_files(group, data_dir)
        missing = [str(path) for path in files if not path.is_file()]
        rows.append(
            {
                "U": group.U,
                "V": group.V,
                "tprime": group.tp,
                "expected_files": len(files),
                "present_files": len(files) - len(missing),
                "missing_files": len(missing),
                "missing_sample": missing[:4],
            }
        )
    return rows


def extract(group: ParameterGroup, args: argparse.Namespace, omega: np.ndarray) -> GroupData:
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
    return GroupData(
        group=group,
        omega=omega,
        rho=rho,
        re_g=re_g,
        roots=roots,
        root_rows=root_rows,
        ylim=ylim,
        root_window=root_window,
        color_vmax=color_vmax,
    )


def root_audit_frame(group_data: dict[tuple[float, float, float], GroupData]) -> pd.DataFrame:
    rows = []
    for group in GROUPS:
        data = group_data[(group.U, group.V, group.tp)]
        for index, ((kx, ky), xpos, row) in enumerate(
            zip(default_k_path(), x_centers(), data.root_rows)
        ):
            rows.append(
                {
                    "branch": "U-only" if group.U > 0 else "V-only",
                    "U": group.U,
                    "V": group.V,
                    "tprime": group.tp,
                    "eta": 0.05,
                    "k_index": index,
                    "kx": kx,
                    "ky": ky,
                    "x_path": xpos,
                    **row,
                }
            )
    return pd.DataFrame(rows)


def compact_rows(
    all_models: pd.DataFrame,
    group_data: dict[tuple[float, float, float], GroupData],
) -> pd.DataFrame:
    rows = []
    for group in GROUPS:
        subset = all_models[
            (all_models.U == group.U)
            & (all_models.V == group.V)
            & np.isclose(all_models.tprime, group.tp)
        ]
        by_model = {row.model: row for row in subset.itertuples(index=False)}
        bond = by_model["bond_resolved"]
        bare = by_model["bare_single_scale"]
        extended = by_model["bond_resolved_plus_chi21"]
        parameter_free = by_model["parameter_free_strong_coupling"]

        data = group_data[(group.U, group.V, group.tp)]
        bands = harmonics(np.asarray(default_k_path(), dtype=int), group.tp)
        direct = linear_fit(
            data.roots,
            {"s_nn": -bands["epsilon1"], "s_nnn": bands["epsilon2"]},
            np.arange(120, dtype=int),
        )
        status_counts = pd.Series(
            [row["root_status"] for row in data.root_rows], dtype="object"
        ).value_counts()
        rows.append(
            {
                "branch": "U-only" if group.U > 0 else "V-only",
                "U": group.U,
                "V": group.V,
                "tprime": group.tp,
                "eta": 0.05,
                "root_count_unique": int(np.isfinite(data.roots[:120]).sum()),
                "root_count_plotted": int(np.isfinite(data.roots).sum()),
                "clean_root_count_plotted": int(status_counts.get("clean", 0)),
                "s_nn": bond.s_nn,
                "s_nn_se": direct["standard_errors"]["s_nn"],
                "expected_s_nn": bond.expected_s_nn,
                "s_nn_relative_error_percent": bond.s_nn_relative_error_percent,
                "s_nnn": bond.s_nnn,
                "s_nnn_se": direct["standard_errors"]["s_nnn"],
                "expected_s_nnn": bond.expected_s_nnn,
                "s_nnn_relative_error_percent": bond.s_nnn_relative_error_percent,
                "offset_delta": bond.delta,
                "offset_delta_se": direct["delta_se"],
                "bond_rmse": bond.rmse,
                "bond_mae": bond.mae,
                "bond_max_abs_error": bond.max_abs_error,
                "bond_r2": bond.r2,
                "bond_aicc": bond.aicc,
                "one_scale_rmse": bare.rmse,
                "one_scale_rmse_reduction_percent": 100.0 * (1.0 - bond.rmse / bare.rmse),
                "extended_chi21_rmse": extended.rmse,
                "extended_chi21_aicc": extended.aicc,
                "extended_minus_bond_aicc": extended.aicc - bond.aicc,
                "parameter_free_rmse": parameter_free.rmse,
                "parameter_free_to_bond_rmse_ratio": parameter_free.rmse / bond.rmse,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["branch", "tprime", "U", "V"],
        ascending=[True, False, True, True],
    )


def plot_coefficients(summary: pd.DataFrame) -> tuple[Path, Path]:
    colors = {-0.25: "#377eb8", -0.4: "#e41a1c"}
    labels = {-0.25: r"$t'=-0.25t$", -0.4: r"$t'=-0.4t$"}
    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 9.5,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.0,
            "ytick.labelsize": 9.0,
            "legend.fontsize": 8.0,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    ):
        fig, axes = plt.subplots(2, 2, figsize=(8.8, 6.5), constrained_layout=True)
        for col, coefficient in enumerate(("s_nn", "s_nnn")):
            expected_col = f"expected_{coefficient}"
            for tp in TP_VALUES:
                rows = summary[
                    (summary.branch == "U-only") & np.isclose(summary.tprime, tp)
                ].sort_values("U")
                axes[0, col].errorbar(
                    rows.U,
                    rows[coefficient],
                    yerr=rows[f"{coefficient}_se"],
                    marker="o",
                    ms=4.5,
                    lw=1.4,
                    capsize=2.2,
                    color=colors[tp],
                    label=labels[tp],
                )
                axes[0, col].axhline(
                    float(rows[expected_col].iloc[0]),
                    color=colors[tp],
                    ls="--",
                    lw=1.0,
                    alpha=0.8,
                )
                rows = summary[
                    (summary.branch == "V-only") & np.isclose(summary.tprime, tp)
                ].sort_values("V")
                axes[1, col].errorbar(
                    rows.V,
                    rows[coefficient],
                    yerr=rows[f"{coefficient}_se"],
                    marker="o",
                    ms=4.5,
                    lw=1.4,
                    capsize=2.2,
                    color=colors[tp],
                    label=labels[tp],
                )
            axes[1, col].axhline(
                float(rows[expected_col].iloc[0]),
                color="black",
                ls="--",
                lw=1.0,
                alpha=0.8,
            )

        axes[0, 0].set_title(r"U-only: NN coefficient")
        axes[0, 1].set_title(r"U-only: NNN coefficient")
        axes[1, 0].set_title(r"V-only: NN coefficient")
        axes[1, 1].set_title(r"V-only: NNN coefficient")
        axes[0, 0].set_ylabel(r"$s_{\rm NN}$")
        axes[1, 0].set_ylabel(r"$s_{\rm NN}$")
        axes[0, 1].set_ylabel(r"$s_{\rm NNN}$")
        axes[1, 1].set_ylabel(r"$s_{\rm NNN}$")
        axes[0, 0].set_xlabel(r"$U/t$")
        axes[0, 1].set_xlabel(r"$U/t$")
        axes[1, 0].set_xlabel(r"$V/t$")
        axes[1, 1].set_xlabel(r"$V/t$")
        for ax in axes.ravel():
            ax.grid(alpha=0.22, lw=0.6)
        axes[0, 0].legend(frameon=False, loc="best")
        axes[1, 0].legend(frameon=False, loc="best")

        FIGURE_STEM.parent.mkdir(parents=True, exist_ok=True)
        pdf = FIGURE_STEM.with_suffix(".pdf")
        png = FIGURE_STEM.with_suffix(".png")
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=280, bbox_inches="tight")
        plt.close(fig)
    if pdf.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Invalid PDF output: {pdf}")
    if png.stat().st_size == 0:
        raise RuntimeError(f"Empty PNG output: {png}")
    return pdf, png


def finite_or_none(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def main() -> None:
    args = parse_args()
    args.data_dir = args.data_dir.resolve()
    if not np.isclose(args.eta, 0.05):
        raise ValueError("This established root analysis is fixed at eta=0.05")
    coverage = coverage_rows(args.data_dir)
    print(json.dumps({"coverage": coverage}, indent=2), flush=True)
    missing = [row for row in coverage if row["missing_files"]]
    if missing:
        raise FileNotFoundError(json.dumps(missing, indent=2))
    if args.check_inputs:
        return

    # The spin prediction depends only on t', not on U.  Cache the exact 4x4
    # diagonalization so the eight U-only fits require only two solves.
    theorem.solve_j1j2 = functools.lru_cache(maxsize=None)(theorem.solve_j1j2)

    RESULTS.mkdir(parents=True, exist_ok=True)
    ROOTS_NPZ.parent.mkdir(parents=True, exist_ok=True)
    omega = np.linspace(-args.omega_max, args.omega_max, args.omega_points)
    group_data: dict[tuple[float, float, float], GroupData] = {}
    model_rows: list[dict] = []
    roots_stack = []
    k_path = np.asarray(default_k_path(), dtype=int)

    for index, group in enumerate(GROUPS, start=1):
        print(
            f"[{index:02d}/{len(GROUPS)}] extracting U={group.U:g} "
            f"V={group.V:g} t'={group.tp:g}",
            flush=True,
        )
        data = extract(group, args, omega)
        group_data[(group.U, group.V, group.tp)] = data
        rows, _ = fit_group(data)
        model_rows.extend(rows)
        roots_stack.append(data.roots)

    all_models = pd.DataFrame(model_rows)
    all_models.insert(
        0,
        "branch",
        np.where(all_models.U > 0, "U-only", "V-only"),
    )
    all_models.to_csv(ALL_MODELS_CSV, index=False)

    root_audit = root_audit_frame(group_data)
    root_audit.to_csv(ROOT_AUDIT_CSV, index=False)
    summary = compact_rows(all_models, group_data)
    summary.to_csv(SUMMARY_CSV, index=False)

    np.savez_compressed(
        ROOTS_NPZ,
        U=np.asarray([group.U for group in GROUPS]),
        V=np.asarray([group.V for group in GROUPS]),
        tprime=np.asarray([group.tp for group in GROUPS]),
        eta=np.asarray(args.eta),
        k_path=k_path,
        x_path=x_centers(),
        omega_root=np.asarray(roots_stack),
    )
    pdf, png = plot_coefficients(summary)

    records = []
    for row in summary.itertuples(index=False):
        records.append(
            {
                key: finite_or_none(value) if isinstance(value, (float, np.floating)) else value
                for key, value in row._asdict().items()
            }
        )
    clean_count = int((root_audit.root_status == "clean").sum())
    result = {
        "analysis": "complete U-only/V-only finite-tprime bond-resolved GZ grid",
        "date_tag": DATE_TAG,
        "data_dir": str(args.data_dir),
        "eta": args.eta,
        "model_convention": "omega_GZ(k)=delta-s_nn*epsilon1(k)+s_nnn*epsilon2(k)",
        "groups": len(GROUPS),
        "unique_roots_expected": 16 * 120,
        "plotted_roots_expected": 16 * 121,
        "unique_roots_valid": int(summary.root_count_unique.sum()),
        "plotted_roots_valid": int(summary.root_count_plotted.sum()),
        "clean_plotted_roots": clean_count,
        "all_groups_120_unique_121_plotted": bool(
            (summary.root_count_unique == 120).all()
            and (summary.root_count_plotted == 121).all()
        ),
        "all_plotted_roots_clean": clean_count == 16 * 121,
        "records": records,
        "outputs": {
            "all_models_csv": str(ALL_MODELS_CSV.relative_to(ROOT)),
            "summary_csv": str(SUMMARY_CSV.relative_to(ROOT)),
            "root_audit_csv": str(ROOT_AUDIT_CSV.relative_to(ROOT)),
            "roots_npz": str(ROOTS_NPZ.relative_to(ROOT)),
            "figure_pdf": str(pdf.relative_to(ROOT)),
            "figure_png": str(png.relative_to(ROOT)),
        },
        "validation": {
            "all_input_files_present": all(row["missing_files"] == 0 for row in coverage),
            "all_numeric_summary_values_finite": bool(
                np.isfinite(
                    summary.select_dtypes(include=[np.number]).to_numpy(dtype=float)
                ).all()
            ),
            "pdf_header_valid": pdf.read_bytes()[:4] == b"%PDF",
            "png_nonempty": png.stat().st_size > 0,
            "summary_rows": int(len(summary)),
            "all_model_rows": int(len(all_models)),
            "root_audit_rows": int(len(root_audit)),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
