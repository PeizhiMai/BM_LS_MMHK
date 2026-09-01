#!/usr/bin/env python3
"""Render a staging-only diagnostic from the validated Fig. 4 C_NN table.

The script intentionally reads only two analytical inputs: the validated
16-row pointwise CSV emitted by ``analyze_fig4_cnn_full861_campaign.py`` and that
analyzer's provenance JSON.  It verifies their hash/content contract before
plotting and never edits manuscript, figure-source, or published-result files.

The three panels show (a) independent all-F861 C_NN inputs, (b) signed GZ
slopes with the pointwise Eq. (10) and old V=0-axis-anchor predictions, and
(c) observed-minus-predicted residuals. The quadrature-weighted grid spread is
retained in the machine-readable table but is not plotted as an uncertainty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from fig4_cnn_prediction_input import (
    C_NN_OBSERVABLE,
    DATA_PRODUCT,
    EXPECTED_EXPANSION_CASES,
    EXPECTED_POINTWISE_CASES,
    FULL861_CONTROL_SOURCE,
    FULL861_EXPANSION_SOURCE,
    FULL861_FIDELITY,
    FULL861_SAMPLING,
    POINTWISE_BASENAME,
    PROVENANCE_BASENAME,
    REVIEWED_FULL861_PINS,
    SCHEMA_VERSION,
    PointwisePredictionError,
    load_validated_fullobs_eq10_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
PNG_BASENAME = "fig4_cnn_staging_diagnostic.png"
PDF_BASENAME = "fig4_cnn_staging_diagnostic.pdf"
QA_BASENAME = "fig4_cnn_staging_diagnostic_qa.json"

EXPECTED_CASES = set(EXPECTED_POINTWISE_CASES)

REQUIRED_COLUMNS = {
    "U",
    "V",
    "r",
    "C_NN",
    "C_NN_spread",
    "C_NN_population_std_diagnostic",
    "C_NN_source",
    "C_NN_sampling",
    "C_NN_fidelity",
    "C_NN_full_wedge_rows",
    "C_NN_quadrature_weight",
    "C_NN_full_quadrature_weighted_population_std",
    "twist_spread_is_standard_error",
    "s_signed_observed",
    "s_u0_signed",
    "eq10_factor",
    "s_eq10_signed",
    "s_axis_anchor_signed",
    "eq10_residual_observed_minus_prediction",
    "axis_anchor_residual_observed_minus_prediction",
    "eq10_convention",
    "residual_convention",
}

COLORS = {20.0: "#D07A16", 40.0: "#B13C45", 80.0: "#6654A3"}
MARKERS = {20.0: "s", 40.0: "^", 80.0: "D"}
INK = "#222222"
GRID = "#D8D8D8"


class ValidationError(RuntimeError):
    """Raised when the pointwise/provenance plotting contract is violated."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointwise", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Fresh staging directory; existing diagnostic outputs are never replaced.",
    )
    parser.add_argument("--dpi", type=int, default=240)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_case(U: object, V: object) -> tuple[float, float]:
    return (round(float(U), 10), round(float(V), 10))


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValidationError(f"Missing {label}: {path}")
    return path


def validate_output_dir(path: Path) -> None:
    resolved = path.expanduser().resolve()
    for protected in (ROOT / "manuscript", ROOT / "figures", ROOT / "results"):
        try:
            resolved.relative_to(protected.resolve())
        except ValueError:
            continue
        raise ValidationError(f"Refusing staging diagnostic output under {protected}")
    collisions = [
        resolved / name
        for name in (PNG_BASENAME, PDF_BASENAME, QA_BASENAME)
        if (resolved / name).exists()
    ]
    if collisions:
        raise ValidationError(
            "Diagnostic output already exists; choose a fresh staging directory: "
            + ", ".join(str(path) for path in collisions)
        )


def bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype(bool)
    lowered = values.astype(str).str.strip().str.lower()
    if not lowered.isin(["true", "false"]).all():
        raise ValidationError("twist_spread_is_standard_error is not Boolean")
    return lowered.eq("true")


def axis_anchor_law(r: np.ndarray, s0: np.ndarray) -> np.ndarray:
    return (s0 - 0.5 * (s0 + 1.0) * r) / (1.0 - r)


def load_validated_inputs(
    pointwise_path: Path, provenance_path: Path
) -> tuple[pd.DataFrame, dict]:
    pointwise_path = require_file(pointwise_path, "pointwise CSV").resolve()
    provenance_path = require_file(provenance_path, "analysis provenance").resolve()
    if pointwise_path.name != POINTWISE_BASENAME:
        raise ValidationError(
            f"Pointwise CSV must retain analyzer basename {POINTWISE_BASENAME}"
        )
    if provenance_path.name != PROVENANCE_BASENAME:
        raise ValidationError(
            f"Analysis provenance must retain analyzer basename {PROVENANCE_BASENAME}"
        )
    if pointwise_path.parent != provenance_path.parent:
        raise ValidationError("Pointwise CSV and provenance must be an inseparable sibling bundle")
    try:
        bundle = load_validated_fullobs_eq10_bundle(
            pointwise_path.parent,
            allow_fixture=False,
            scale_points_path=ROOT / "results/pnas_scale_rule_points_eta0p05.csv",
        )
    except PointwisePredictionError as exc:
        raise ValidationError(str(exc)) from exc
    frame = bundle.rows.copy()
    provenance = bundle.provenance
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValidationError(f"Pointwise CSV is missing columns: {missing}")
    if len(frame) != 16:
        raise ValidationError(f"Expected exactly 16 pointwise rows, found {len(frame)}")
    if frame.duplicated(["U", "V"]).any():
        raise ValidationError("Pointwise CSV contains duplicate (U,V) rows")
    observed_cases = {canonical_case(row.U, row.V) for row in frame.itertuples()}
    if observed_cases != EXPECTED_CASES:
        raise ValidationError(
            f"Pointwise case inventory mismatch; missing={sorted(EXPECTED_CASES - observed_cases)}, "
            f"extra={sorted(observed_cases - EXPECTED_CASES)}"
        )

    numeric_columns = [
        "U",
        "V",
        "r",
        "C_NN",
        "s_signed_observed",
        "s_u0_signed",
        "eq10_factor",
        "s_eq10_signed",
        "s_axis_anchor_signed",
        "eq10_residual_observed_minus_prediction",
        "axis_anchor_residual_observed_minus_prediction",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[numeric_columns].to_numpy(dtype=float)).all():
        raise ValidationError("Pointwise CSV contains non-finite required values")
    if not np.allclose(frame["r"], frame["V"] / frame["U"], atol=1e-13, rtol=0):
        raise ValidationError("Pointwise r is inconsistent with U and V")
    if not (frame["C_NN"] < 0.0).all() or not (frame["s_signed_observed"] < 0.0).all():
        raise ValidationError(
            "Pointwise C_NN/signed-observed sign convention is inconsistent"
        )
    if bool_series(frame["twist_spread_is_standard_error"]).any():
        raise ValidationError(
            "At least one point incorrectly labels twist spread as a standard error"
        )

    expansion_mask = frame.apply(
        lambda row: canonical_case(row["U"], row["V"])
        in set(EXPECTED_EXPANSION_CASES),
        axis=1,
    )
    control_mask = ~expansion_mask
    if not (
        frame["C_NN_sampling"].eq(FULL861_SAMPLING).all()
        and frame["C_NN_fidelity"].eq(FULL861_FIDELITY).all()
        and frame.loc[expansion_mask, "C_NN_source"]
        .eq(FULL861_EXPANSION_SOURCE)
        .all()
        and frame.loc[control_mask, "C_NN_source"]
        .eq(FULL861_CONTROL_SOURCE)
        .all()
    ):
        raise ValidationError(
            "C_NN source/sampling labels do not match the reviewed all-F861 12+4 merge"
        )
    population_spread = pd.to_numeric(
        frame["C_NN_full_quadrature_weighted_population_std"], errors="raise"
    )
    if not np.isfinite(population_spread).all() or (population_spread < 0.0).any():
        raise ValidationError(
            "F861 quadrature-weighted population-spread diagnostics are missing or negative"
        )
    if "C_NN_spread" in frame and frame["C_NN_spread"].notna().any():
        raise ValidationError(
            "All-F861 rows must not masquerade grid variation as P25 panel spread"
        )

    U = frame["U"].to_numpy(dtype=float)
    V = frame["V"].to_numpy(dtype=float)
    C = frame["C_NN"].to_numpy(dtype=float)
    factor = (2.0 * U - V) / (U - V)
    eq10 = 1.0 + factor * (2.0 * C - 0.5)
    anchor = axis_anchor_law(
        frame["r"].to_numpy(dtype=float),
        frame["s_u0_signed"].to_numpy(dtype=float),
    )
    eq_residual = frame["s_signed_observed"].to_numpy(dtype=float) - eq10
    anchor_residual = frame["s_signed_observed"].to_numpy(dtype=float) - anchor
    checks = {
        "eq10_factor": (frame["eq10_factor"].to_numpy(dtype=float), factor),
        "s_eq10_signed": (frame["s_eq10_signed"].to_numpy(dtype=float), eq10),
        "s_axis_anchor_signed": (
            frame["s_axis_anchor_signed"].to_numpy(dtype=float),
            anchor,
        ),
        "eq10_residual": (
            frame["eq10_residual_observed_minus_prediction"].to_numpy(dtype=float),
            eq_residual,
        ),
        "axis_anchor_residual": (
            frame["axis_anchor_residual_observed_minus_prediction"].to_numpy(
                dtype=float
            ),
            anchor_residual,
        ),
    }
    for label, (stored, recomputed) in checks.items():
        if not np.allclose(stored, recomputed, atol=5e-13, rtol=0):
            raise ValidationError(
                f"Stored {label} disagrees with an independent recomputation"
            )
    if set(frame["eq10_convention"].astype(str)) != {
        "signed s_NN in omega_GZ=s_NN epsilon_NN"
    } or set(frame["residual_convention"].astype(str)) != {"observed minus prediction"}:
        raise ValidationError(
            "Row-level equation/residual convention labels are inconsistent"
        )

    return frame.sort_values(["U", "V"]).reset_index(drop=True), provenance


def style_axis(ax: plt.Axes) -> None:
    ax.grid(axis="y", color=GRID, lw=0.65, alpha=0.75)
    ax.tick_params(direction="out", length=3.2, width=0.8, colors=INK)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#777777")
    ax.spines["bottom"].set_color("#777777")


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.13,
        1.045,
        label,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="bottom",
        color=INK,
    )


def render(frame: pd.DataFrame, output_dir: Path, dpi: int) -> tuple[Path, Path]:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9.5,
            "axes.labelsize": 10.5,
            "axes.titlesize": 11.0,
            "legend.fontsize": 8.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(14.1, 4.45), constrained_layout=False)
    fig.subplots_adjust(left=0.064, right=0.985, bottom=0.19, top=0.80, wspace=0.31)

    ax = axes[0]
    for U in (20.0, 40.0, 80.0):
        group = frame[frame["U"].eq(U)].sort_values("r")
        ax.plot(
            group["r"],
            group["C_NN"],
            color=COLORS[U],
            marker=MARKERS[U],
            ms=5.5,
            lw=1.35,
            mec=COLORS[U],
            mfc=COLORS[U],
            zorder=3,
        )
    full = frame
    ax.scatter(
        full["r"],
        full["C_NN"],
        s=58,
        facecolors="none",
        edgecolors=INK,
        linewidths=0.85,
        zorder=4,
        label="F861 input",
    )
    ax.set_title(r"Independent $C_{\mathrm{NN}}(U,V)$ inputs")
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel(r"$C_{\mathrm{NN}}$")
    ax.set_xlim(-0.012, 0.238)
    style_axis(ax)
    panel_label(ax, "a")
    # The shared legend keys the three U families; the local key certifies the
    # common full-wedge resolution of every source.
    ax.legend(frameon=False, loc="center left", handlelength=1.8)
    ax.text(
        0.99,
        0.025,
        "All inputs: 861-point wedge, weight 1600"
        "\n(grid spread retained in data; not SEM)",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.5,
        color="#555555",
    )

    ax = axes[1]
    for U in (20.0, 40.0, 80.0):
        group = frame[frame["U"].eq(U)].sort_values("r")
        color = COLORS[U]
        marker = MARKERS[U]
        ax.plot(
            group["r"],
            group["s_signed_observed"],
            color=color,
            marker=marker,
            ms=5.3,
            lw=0,
            mfc=color,
            mec=color,
            zorder=5,
        )
        ax.plot(
            group["r"],
            group["s_eq10_signed"],
            color=color,
            marker=marker,
            ms=5.3,
            lw=1.45,
            mfc="white",
            mec=color,
            mew=1.1,
            zorder=4,
        )
        ax.plot(
            group["r"],
            group["s_axis_anchor_signed"],
            color=color,
            lw=1.1,
            ls="--",
            alpha=0.7,
            zorder=2,
        )
    ax.set_title("Signed GZ coefficient comparison")
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel(r"signed $s_{\mathrm{NN}}$")
    ax.set_xlim(-0.012, 0.238)
    style_axis(ax)
    panel_label(ax, "b")
    method_handles = [
        Line2D([], [], marker="o", ls="none", color=INK, mfc=INK, label="observed GZ"),
        Line2D(
            [],
            [],
            marker="o",
            ls="-",
            color=INK,
            mfc="white",
            label=r"Eq. 10 from $C_{\mathrm{NN}}$",
        ),
        Line2D([], [], ls="--", color=INK, label=r"$V=0$-axis anchor"),
    ]
    ax.legend(handles=method_handles, frameon=False, loc="lower left")

    ax = axes[2]
    for U in (20.0, 40.0, 80.0):
        group = frame[frame["U"].eq(U)].sort_values("r")
        color = COLORS[U]
        marker = MARKERS[U]
        ax.plot(
            group["r"],
            group["eq10_residual_observed_minus_prediction"],
            color=color,
            marker=marker,
            ms=5.2,
            lw=1.35,
            mfc=color,
            mec=color,
        )
        ax.plot(
            group["r"],
            group["axis_anchor_residual_observed_minus_prediction"],
            color=color,
            marker=marker,
            ms=5.0,
            lw=1.0,
            ls="--",
            mfc="white",
            mec=color,
            alpha=0.8,
        )
    ax.axhline(0.0, color="#666666", lw=0.9, zorder=0)
    ax.set_title("Pointwise residuals")
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel("observed $-$ prediction")
    ax.set_xlim(-0.012, 0.238)
    style_axis(ax)
    panel_label(ax, "c")
    residual_handles = [
        Line2D([], [], marker="o", ls="-", color=INK, mfc=INK, label="Eq. 10"),
        Line2D(
            [],
            [],
            marker="o",
            ls="--",
            color=INK,
            mfc="white",
            label="axis anchor",
        ),
    ]
    ax.legend(handles=residual_handles, frameon=False, loc="best")

    family_handles = [
        Line2D(
            [],
            [],
            marker=MARKERS[U],
            color=COLORS[U],
            lw=1.4,
            mfc=COLORS[U],
            label=rf"$U/t={U:g}$",
        )
        for U in (20.0, 40.0, 80.0)
    ]
    fig.legend(
        handles=family_handles,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.895),
        ncol=3,
        handlelength=2.0,
        columnspacing=2.2,
    )
    fig.suptitle(
        r"Fig. 4 $C_{\mathrm{NN}}$ pointwise diagnostic (staging only)",
        x=0.5,
        y=0.97,
        fontsize=13.0,
        color=INK,
    )
    fig.text(
        0.5,
        0.035,
        "Independent equal-time inputs; residual = observed − prediction. "
        "All equal-time inputs use the full 861-point wedge; grid variation is diagnostic, not a SEM.",
        ha="center",
        va="bottom",
        fontsize=8.2,
        color="#4A4A4A",
    )

    png = output_dir / PNG_BASENAME
    pdf = output_dir / PDF_BASENAME
    fig.savefig(png, dpi=dpi, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return png, pdf


def atomic_write_json(payload: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def main() -> None:
    args = parse_args()
    if args.dpi < 120:
        raise ValidationError("DPI must be at least 120 for visual QA")
    pointwise_path = args.pointwise.expanduser().resolve()
    provenance_path = args.provenance.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    validate_output_dir(output_dir)
    frame, provenance = load_validated_inputs(pointwise_path, provenance_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    png, pdf = render(frame, output_dir, args.dpi)
    image = plt.imread(png)
    if image.ndim < 2 or image.shape[0] < 700 or image.shape[1] < 2000:
        raise ValidationError(
            f"Rendered PNG is unexpectedly small: shape={image.shape}"
        )

    expansion = frame[frame["C_NN_source"].eq(FULL861_EXPANSION_SOURCE)]
    controls = frame[frame["C_NN_source"].eq(FULL861_CONTROL_SOURCE)]
    qa = {
        "created_at": datetime.now().astimezone().isoformat(),
        "purpose": "staging-only diagnostic; not a manuscript or active figure artifact",
        "plotter": str(Path(__file__).resolve()),
        "plotter_sha256": sha256(Path(__file__).resolve()),
        "inputs": {
            "pointwise": {
                "path": str(pointwise_path),
                "sha256": sha256(pointwise_path),
            },
            "analysis_provenance": {
                "path": str(provenance_path),
                "sha256": sha256(provenance_path),
            },
            "analyzer_sha256": provenance.get("analyzer_sha256"),
        },
        "validation": {
            "schema_version": SCHEMA_VERSION,
            "data_product": DATA_PRODUCT,
            "C_NN_observable": C_NN_OBSERVABLE,
            "C_NN_fidelity": FULL861_FIDELITY,
            "reviewed_inputs": REVIEWED_FULL861_PINS,
            "pointwise_rows": len(frame),
            "unique_UV_rows": int(frame[["U", "V"]].drop_duplicates().shape[0]),
            "expansion_full861_rows": len(expansion),
            "existing_u40_full861_rows": len(controls),
            "all_full861_rows": len(frame),
            "equations_independently_recomputed": True,
            "pointwise_hash_matches_provenance": True,
            "twist_spread_is_standard_error": False,
            "uncertainty_whiskers_plotted": False,
            "population_spread_role": "quadrature-grid variation diagnostic; not SEM or confidence interval",
            "publication_artifacts_modified": False,
        },
        "panels": [
            "C_NN vs V/U by U, with full-861 inputs ringed",
            "signed observed GZ vs pointwise Eq.10 and V=0-axis-anchor predictions",
            "observed-minus-predicted residuals for Eq.10 and axis anchor",
        ],
        "outputs": {
            png.name: {
                "sha256": sha256(png),
                "width_px": int(image.shape[1]),
                "height_px": int(image.shape[0]),
            },
            pdf.name: {"sha256": sha256(pdf)},
        },
    }
    qa_path = output_dir / QA_BASENAME
    atomic_write_json(qa, qa_path)
    print("Validated pointwise input: 16/16 unique rows")
    print("C_NN sources: 12 expansion F861 + 4 existing U=40 F861")
    print("Equation/residual recomputation: PASS")
    print("All 16 C_NN inputs: F861; grid spread diagnostic only, not SEM")
    print(f"PNG: {png}")
    print(f"PDF: {pdf}")
    print(f"QA: {qa_path}")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        raise SystemExit(f"VALIDATION FAILED: {exc}") from exc
