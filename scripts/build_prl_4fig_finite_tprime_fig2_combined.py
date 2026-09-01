#!/usr/bin/env python3
"""Combine finite-t' four-figure-paper Fig. 2 panels into a 2x4 figure.

The retained source panels are (b,c,e,f) from each of the t'=-0.25t and
t'=-0.4t variants.  For direct comparison, each row places the two spectral
maps first and the two zero-dispersion panels second:

    top:    U=20 spectra, then U=8,20,40 zero curves;
    bottom: V=5 spectra, then V=2,5,8 zero curves.

The U-only dashed curves are parameter-free U->infinity spin-correlation
references, 4 C_NN epsilon_NN + 4 C_NNN epsilon_NNN, evaluated separately
for each t'.  The V-only dashed curves are parameter-free charge-side
references with the universal signed coefficients (s_NN,s_NNN)=(-8/7,1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_pnas_supplement_figures import (  # noqa: E402
    STYLE,
    _spectral_map,
    panel_label,
    save,
)
from build_prl_4fig_finite_tprime_fig2 import (  # noqa: E402
    SOURCE_METRICS,
    TP_VALUES,
    U_COLORS,
    U_VALUES,
    V_COLORS,
    V_VALUES,
    harmonics,
    load_group,
)
from manuscript_figure_style import ZERO_DISPERSION_AXIS_LABEL  # noqa: E402


OUT = ROOT / "figures/pnas_main/finite_tprime_versions"
STEM = "fig2_interaction_axis_finite_tprime_combined_2x4"
METRICS_OUT = (
    ROOT
    / "results/fig2_interaction_axis_finite_tprime_combined_2x4_metrics_eta0p05_20260802.csv"
)
MANIFEST_OUT = (
    ROOT
    / "results/fig2_interaction_axis_finite_tprime_combined_2x4_manifest_20260802.json"
)

# Exact-diagonalization spin correlations of the corresponding 4x4 J1--J2
# model at the present momentum-mixing resolution.  The entries are the
# signed coefficients (4 C_NN, 4 C_NNN), not fits to a finite-U GZ curve.
SPIN_LIMIT_COEFFICIENTS = {
    -0.25: (-1.4029276100, 0.8354855142),
    -0.4: (-1.3982754762773109, 0.7947635647849522),
}


def configure_curve_axis(ax: plt.Axes) -> None:
    ax.axhline(0.0, color="0.55", lw=0.8)
    ax.set_xlim(0, 120)
    ax.set_ylim(-7.2, 7.2)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
    ax.grid(alpha=0.18)


def add_row_colorbar(
    fig: plt.Figure,
    axes: tuple[plt.Axes, plt.Axes],
    image,
) -> None:
    first = axes[0].get_position()
    second = axes[1].get_position()
    cax = fig.add_axes(
        [first.x0, first.y1 + 0.012, second.x1 - first.x0, 0.012]
    )
    colorbar = fig.colorbar(image, cax=cax, orientation="horizontal")
    colorbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=1)
    colorbar.ax.xaxis.set_ticks_position("top")
    colorbar.ax.xaxis.set_label_position("top")
    colorbar.ax.tick_params(labelsize=12.5, length=6, width=1.3, pad=2)
    colorbar.ax.xaxis.label.set_size(11.0)


def universal_charge_curve(k_path: np.ndarray, tp: float) -> np.ndarray:
    epsilon1, epsilon2 = harmonics(k_path, tp)
    return -(8.0 / 7.0) * epsilon1 + epsilon2


def spin_limit_curve(k_path: np.ndarray, tp: float) -> tuple[np.ndarray, float, float]:
    """Return the parameter-free U->infinity spin-correlation reference."""
    epsilon1, epsilon2 = harmonics(k_path, tp)
    s_nn, s_nnn = SPIN_LIMIT_COEFFICIENTS[tp]
    return s_nn * epsilon1 + s_nnn * epsilon2, s_nn, s_nnn


def curve_metrics(root: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    residual = root[:120] - prediction[:120]
    rmse = float(np.sqrt(np.mean(residual**2)))
    centered = root[:120] - np.mean(root[:120])
    r2 = float(1.0 - np.dot(residual, residual) / np.dot(centered, centered))
    return rmse, r2


def build() -> tuple[dict[str, str], pd.DataFrame]:
    # Retain the source-metrics existence check as part of the figure-data
    # provenance audit, although the Mott-side reference is no longer fitted.
    pd.read_csv(SOURCE_METRICS)
    data: dict[float, dict[str, dict[int, dict]]] = {}
    for tp in TP_VALUES:
        data[tp] = {
            "U": {U: load_group(U, 0, tp) for U in U_VALUES},
            "V": {V: load_group(0, V, tp) for V in V_VALUES},
        }

    x = np.arange(121, dtype=float)
    metric_records: list[dict] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 4, figsize=(13.4, 6.65))
        fig.subplots_adjust(
            left=0.052,
            right=0.993,
            bottom=0.085,
            top=0.91,
            wspace=0.25,
            hspace=0.42,
        )

        top_images = []
        bottom_images = []
        for column, tp in enumerate(TP_VALUES):
            u20 = data[tp]["U"][20]
            top_images.append(
                _spectral_map(
                    axes[0, column],
                    np.asarray(u20["omega"], dtype=float),
                    np.asarray(u20["rho"], dtype=float),
                    np.asarray(u20["root"], dtype=float),
                    15.0,
                    rf"$U=20,\ V=0$" + "\n" + rf"$t'={tp:g}t$",
                    vmax=1.5,
                    label_y=0.29,
                    label_framed=False,
                )
            )
            if column == 1:
                axes[0, column].set_ylabel("")

            v5 = data[tp]["V"][5]
            bottom_images.append(
                _spectral_map(
                    axes[1, column],
                    np.asarray(v5["omega"], dtype=float),
                    np.asarray(v5["rho"], dtype=float),
                    np.asarray(v5["root"], dtype=float),
                    25.0,
                    rf"$U=0,\ V=5$" + "\n" + rf"$t'={tp:g}t$",
                    vmax=2.5,
                    label_y=0.29,
                    label_framed=False,
                )
            )
            if column == 1:
                axes[1, column].set_ylabel("")

        for offset, tp in enumerate(TP_VALUES):
            column = 2 + offset
            u_axis = axes[0, column]
            for U in U_VALUES:
                u_axis.plot(
                    x,
                    np.asarray(data[tp]["U"][U]["root"], dtype=float),
                    color=U_COLORS[U],
                    label=rf"$U={U}$",
                    zorder=2,
                )
            u_reference, s_nn, s_nnn = spin_limit_curve(
                np.asarray(data[tp]["U"][40]["k_path"], dtype=int),
                tp,
            )
            u_axis.plot(
                x,
                u_reference,
                color="black",
                ls="--",
                lw=1.6,
                label=(
                    r"$4C_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}"
                    r"+4C_{\mathrm{NNN}}\varepsilon_{\mathrm{NNN}}$"
                ),
                zorder=3,
            )
            configure_curve_axis(u_axis)
            u_axis.legend(
                frameon=False,
                ncol=1,
                loc="upper center",
                bbox_to_anchor=(0.55, 0.985),
                fontsize=11.088,
                handlelength=1.5,
                labelspacing=0.10,
                borderaxespad=0.12,
            )
            u_axis.text(
                0.96,
                0.055,
                rf"$V=0,\quad t'={tp:g}t$",
                transform=u_axis.transAxes,
                ha="right",
                va="bottom",
                fontsize=10.7,
                fontweight="bold",
            )
            u_root = np.asarray(data[tp]["U"][40]["root"], dtype=float)
            u_rmse, u_r2 = curve_metrics(u_root, u_reference)
            metric_records.append(
                {
                    "tprime": tp,
                    "axis": "U-only",
                    "reference_interaction": np.inf,
                    "reference_type": "parameter_free_spin_limit",
                    "s_nn": s_nn,
                    "s_nnn": s_nnn,
                    "delta": 0.0,
                    "rmse": u_rmse,
                    "r2": u_r2,
                    "diagnostic_unconstrained_delta": np.nan,
                    "diagnostic_unconstrained_rmse": np.nan,
                }
            )

            v_axis = axes[1, column]
            for V in V_VALUES:
                v_axis.plot(
                    x,
                    np.asarray(data[tp]["V"][V]["root"], dtype=float),
                    color=V_COLORS[V],
                    label=rf"$V={V}$",
                    zorder=2,
                )
            universal = universal_charge_curve(
                np.asarray(data[tp]["V"][8]["k_path"], dtype=int),
                tp,
            )
            v_axis.plot(
                x,
                universal,
                color="black",
                ls="--",
                lw=1.6,
                label=(
                    r"$-\frac{8}{7}\varepsilon_{\mathrm{NN}}"
                    r"+\varepsilon_{\mathrm{NNN}}$"
                ),
                zorder=3,
            )
            configure_curve_axis(v_axis)
            v_axis.legend(
                frameon=False,
                ncol=1,
                loc="upper center",
                bbox_to_anchor=(0.55, 0.985),
                fontsize=12.384,
                handlelength=1.5,
                labelspacing=0.10,
                borderaxespad=0.12,
            )
            v_axis.text(
                0.96,
                0.055,
                rf"$U=0,\quad t'={tp:g}t$",
                transform=v_axis.transAxes,
                ha="right",
                va="bottom",
                fontsize=10.7,
                fontweight="bold",
            )
            v_root = np.asarray(data[tp]["V"][8]["root"], dtype=float)
            v_rmse, v_r2 = curve_metrics(v_root, universal)
            metric_records.append(
                {
                    "tprime": tp,
                    "axis": "V-only",
                    "reference_interaction": 8,
                    "reference_type": "universal_charge_rule",
                    "s_nn": -8.0 / 7.0,
                    "s_nnn": 1.0,
                    "delta": 0.0,
                    "rmse": v_rmse,
                    "r2": v_r2,
                    "diagnostic_unconstrained_delta": np.nan,
                    "diagnostic_unconstrained_rmse": np.nan,
                }
            )

        for index, ax in enumerate(axes.ravel()):
            panel_label(ax, f"({chr(97 + index)})", framed=False, outside_top_tick=True)

        add_row_colorbar(fig, (axes[0, 0], axes[0, 1]), top_images[0])
        add_row_colorbar(fig, (axes[1, 0], axes[1, 1]), bottom_images[0])
        outputs = save(fig, STEM, output_dir=OUT)

    metric_frame = pd.DataFrame(metric_records)
    metric_frame["unique_comparison_points"] = 120
    metric_frame["plotted_points"] = 121
    metric_frame["figure_pdf"] = outputs["pdf"]
    return outputs, metric_frame


def main() -> None:
    outputs, metrics = build()
    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_OUT, index=False)
    manifest = {
        "purpose": "combined 2x4 finite-tprime version of four-figure-paper Fig. 2",
        "retained_source_panels": ["b", "c", "e", "f"],
        "layout": {
            "top_row": [
                "b: U=20 spectrum, tprime=-0.25",
                "b: U=20 spectrum, tprime=-0.4",
                "c: U-only zero curves, tprime=-0.25",
                "c: U-only zero curves, tprime=-0.4",
            ],
            "bottom_row": [
                "e: V=5 spectrum, tprime=-0.25",
                "e: V=5 spectrum, tprime=-0.4",
                "f: V-only zero curves, tprime=-0.25",
                "f: V-only zero curves, tprime=-0.4",
            ],
        },
        "u_side_reference": {
            "type": "parameter-free U->infinity spin-correlation rule",
            "formula": "omega_GZ=4*C_NN*epsilon_NN+4*C_NNN*epsilon_NNN",
            "coefficients": {
                str(tp): {
                    "s_nn": SPIN_LIMIT_COEFFICIENTS[tp][0],
                    "s_nnn": SPIN_LIMIT_COEFFICIENTS[tp][1],
                }
                for tp in TP_VALUES
            },
        },
        "v_side_reference": {
            "type": "universal charge rule",
            "s_nn": "-8/7",
            "s_nnn": 1,
            "formula": "omega_GZ=-(8/7)*epsilon1+epsilon2",
        },
        "fit_points_unique": 120,
        "plot_points_with_repeated_terminal_gamma": 121,
        "outputs": outputs,
        "metrics_csv": str(METRICS_OUT.relative_to(ROOT)),
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n")
    pdf = ROOT / outputs["pdf"]
    png = ROOT / outputs["png"]
    if pdf.read_bytes()[:4] != b"%PDF" or png.stat().st_size == 0:
        raise RuntimeError("Invalid combined figure outputs")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
