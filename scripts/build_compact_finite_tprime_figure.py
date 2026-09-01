#!/usr/bin/env python3
"""Build the compact main-text finite-t' figure at t'=-0.25t.

The former eight-panel Figure 5 compared t'=-0.25t and -0.4t side by side.
The main text now keeps one representative particle-hole-asymmetric case and
uses a two-row, two-column layout:

    (a) Mott-side spectrum,       (b) U-only GZ dispersions;
    (c) CDW-side spectrum,        (d) V-only GZ dispersions.

The complete checks for both hopping ratios remain in the Supplemental
Material, so this script changes only the main-text presentation.
"""
from __future__ import annotations

import hashlib
import json
import shutil
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
    save,
)
from manuscript_figure_style import (  # noqa: E402
    PANEL_LABEL_X,
    outside_panel_label,
)
from build_prl_4fig_finite_tprime_fig2 import (  # noqa: E402
    U_COLORS,
    U_VALUES,
    V_COLORS,
    V_VALUES,
    harmonics,
    load_group,
)
from build_prl_4fig_finite_tprime_fig2_combined import (  # noqa: E402
    SPIN_LIMIT_COEFFICIENTS,
    configure_curve_axis,
    curve_metrics,
    spin_limit_curve,
    universal_charge_curve,
)


TP = -0.25
OUT = ROOT / "figures/pnas_main/finite_tprime_versions"
STEM = "fig2_interaction_axis_finite_tprime_combined_2x4"
MANUSCRIPT_FIGURE = ROOT / "manuscript/figures" / f"{STEM}.pdf"
METRICS_OUT = ROOT / "results/fig5_finite_tprime_tpn25_metrics_eta0p05_20260820.csv"
MANIFEST_OUT = ROOT / "results/fig5_finite_tprime_tpn25_manifest_20260820.json"

LEFT_PANEL_LABEL_SHIFT = 0.035
ALL_PANEL_LABEL_LEFT_SHIFT = 0.020
MAIN_STYLE = dict(STYLE)
MAIN_STYLE.update(
    {
        "font.size": 14.0,
        "axes.labelsize": 15.5,
        "axes.titlesize": 15.5,
        "xtick.labelsize": 13.5,
        "ytick.labelsize": 13.5,
        "legend.fontsize": 12.5,
    }
)
LEGEND_FONTSIZE = 15.0
PANEL_D_FORMULA_FONTSIZE = 16.1
PANEL_LABEL_FONTSIZE = 15.5
SPECTRAL_TEXT_FONTSIZE = 13.5
COLORBAR_TICK_FONTSIZE = 13.5
COLORBAR_LABEL_FONTSIZE = 14.0
AXIS_NOTE_FONTSIZE = 13.5
PANEL_B_LEGEND_UPWARD_SHIFT = 0.015
CURVE_YLABEL_X = -0.18


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_colorbar_above(fig: plt.Figure, ax: plt.Axes, image) -> None:
    position = ax.get_position()
    colorbar_axis = fig.add_axes(
        [position.x0, position.y1 + 0.012, position.width, 0.013]
    )
    colorbar = fig.colorbar(image, cax=colorbar_axis, orientation="horizontal")
    colorbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=1)
    colorbar.ax.xaxis.set_ticks_position("top")
    colorbar.ax.xaxis.set_label_position("top")
    colorbar.ax.tick_params(
        labelsize=COLORBAR_TICK_FONTSIZE,
        length=5,
        width=1.1,
        pad=2,
    )
    colorbar.ax.xaxis.label.set_size(COLORBAR_LABEL_FONTSIZE)


def add_two_tier_legend(
    ax: plt.Axes,
    *,
    formula_fontsize: float,
    upward_shift: float = 0.0,
) -> None:
    """Place interaction values at the top and the formula below the curve."""
    handles, labels = ax.get_legend_handles_labels()
    formula_legend = ax.legend(
        [handles[3]],
        [labels[3]],
        frameon=False,
        ncol=1,
        loc="lower center",
        bbox_to_anchor=(0.51, -0.005 + upward_shift),
        fontsize=formula_fontsize,
        handlelength=0.80,
        labelspacing=0.08,
        borderaxespad=0.02,
    )
    ax.add_artist(formula_legend)
    ax.legend(
        handles[:3],
        labels[:3],
        frameon=False,
        ncol=1,
        loc="upper center",
        bbox_to_anchor=(0.50, 0.985 + upward_shift),
        fontsize=LEGEND_FONTSIZE,
        handlelength=0.80,
        labelspacing=0.08,
        borderaxespad=0.08,
    )


def add_panel_label(ax: plt.Axes, label: str) -> None:
    """Apply the approved extra left shift to left-column panel labels."""
    x = (
        PANEL_LABEL_X - ALL_PANEL_LABEL_LEFT_SHIFT - LEFT_PANEL_LABEL_SHIFT
        if label in {"(a)", "(c)"}
        else PANEL_LABEL_X - ALL_PANEL_LABEL_LEFT_SHIFT
    )
    outside_panel_label(ax, label, fontsize=PANEL_LABEL_FONTSIZE, x=x)


def build() -> tuple[dict[str, str], pd.DataFrame]:
    data = {
        "U": {value: load_group(value, 0, TP) for value in U_VALUES},
        "V": {value: load_group(0, value, TP) for value in V_VALUES},
    }
    x = np.arange(121, dtype=float)
    records: list[dict[str, float | str]] = []

    with plt.rc_context(MAIN_STYLE):
        # Preserve the exact axes dimensions of the former 13.4 x 6.65 in
        # 2x4 figure.  The reduced canvas removes the t'=-0.4 columns without
        # stretching the retained panels.  The wider center gutter leaves
        # room for the enlarged single-column y labels.
        column_gap = 0.72
        width = 6.82
        height = 6.65
        fig = plt.figure(figsize=(width, height))
        left_x = 0.6968 / width
        panel_width = 2.6546105263157895 / width
        right_x = (0.6968 + 2.6546105263157895 + column_gap) / width
        bottom_y = 0.085
        top_y = 0.5690909090909091
        panel_height = 0.34090909090909094
        axes = np.array(
            [
                [
                    fig.add_axes(
                        [left_x, top_y, panel_width, panel_height]
                    ),
                    fig.add_axes(
                        [right_x, top_y, panel_width, panel_height]
                    ),
                ],
                [
                    fig.add_axes(
                        [left_x, bottom_y, panel_width, panel_height]
                    ),
                    fig.add_axes(
                        [right_x, bottom_y, panel_width, panel_height]
                    ),
                ],
            ]
        )

        u20 = data["U"][20]
        top_image = _spectral_map(
            axes[0, 0],
            np.asarray(u20["omega"], dtype=float),
            np.asarray(u20["rho"], dtype=float),
            np.asarray(u20["root"], dtype=float),
            15.0,
            r"$U=20,\ V=0$",
            vmax=1.5,
            label_y=0.29,
            label_framed=False,
            label_fontsize=SPECTRAL_TEXT_FONTSIZE,
        )

        u_axis = axes[0, 1]
        for value in U_VALUES:
            u_axis.plot(
                x,
                np.asarray(data["U"][value]["root"], dtype=float),
                color=U_COLORS[value],
                label=rf"$U={value}$",
                zorder=2,
            )
        u_reference, s_nn, s_nnn = spin_limit_curve(
            np.asarray(data["U"][40]["k_path"], dtype=int), TP
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
        u_axis.yaxis.set_label_coords(CURVE_YLABEL_X, 0.5)
        add_two_tier_legend(
            u_axis,
            formula_fontsize=LEGEND_FONTSIZE,
            upward_shift=PANEL_B_LEGEND_UPWARD_SHIFT,
        )
        u_axis.text(
            0.06,
            0.20,
            r"$V=0$",
            transform=u_axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=AXIS_NOTE_FONTSIZE,
            fontweight="bold",
        )
        u_rmse, u_r2 = curve_metrics(
            np.asarray(data["U"][40]["root"], dtype=float), u_reference
        )
        records.append(
            {
                "tprime": TP,
                "axis": "U-only",
                "reference_interaction": "infinity",
                "reference_type": "parameter_free_spin_limit",
                "s_nn": s_nn,
                "s_nnn": s_nnn,
                "rmse": u_rmse,
                "r2": u_r2,
            }
        )

        v5 = data["V"][5]
        bottom_image = _spectral_map(
            axes[1, 0],
            np.asarray(v5["omega"], dtype=float),
            np.asarray(v5["rho"], dtype=float),
            np.asarray(v5["root"], dtype=float),
            25.0,
            r"$U=0,\ V=5$",
            vmax=2.5,
            label_y=0.29,
            label_framed=False,
            label_fontsize=SPECTRAL_TEXT_FONTSIZE,
        )

        v_axis = axes[1, 1]
        for value in V_VALUES:
            v_axis.plot(
                x,
                np.asarray(data["V"][value]["root"], dtype=float),
                color=V_COLORS[value],
                label=rf"$V={value}$",
                zorder=2,
            )
        universal = universal_charge_curve(
            np.asarray(data["V"][8]["k_path"], dtype=int), TP
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
        v_axis.yaxis.set_label_coords(CURVE_YLABEL_X, 0.5)
        add_two_tier_legend(
            v_axis,
            formula_fontsize=PANEL_D_FORMULA_FONTSIZE,
        )
        v_axis.text(
            0.06,
            0.20,
            r"$U=0$",
            transform=v_axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=AXIS_NOTE_FONTSIZE,
            fontweight="bold",
        )
        v_rmse, v_r2 = curve_metrics(
            np.asarray(data["V"][8]["root"], dtype=float), universal
        )
        records.append(
            {
                "tprime": TP,
                "axis": "V-only",
                "reference_interaction": 8,
                "reference_type": "universal_charge_rule",
                "s_nn": -8.0 / 7.0,
                "s_nnn": 1.0,
                "rmse": v_rmse,
                "r2": v_r2,
            }
        )

        for index, axis in enumerate(axes.ravel()):
            add_panel_label(axis, f"({chr(97 + index)})")

        add_colorbar_above(fig, axes[0, 0], top_image)
        add_colorbar_above(fig, axes[1, 0], bottom_image)
        outputs = save(fig, STEM, output_dir=OUT)

    metrics = pd.DataFrame(records)
    metrics["unique_comparison_points"] = 120
    metrics["plotted_points"] = 121
    metrics["figure_pdf"] = outputs["pdf"]
    return outputs, metrics


def main() -> None:
    outputs, metrics = build()
    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_OUT, index=False)

    figure_pdf = ROOT / outputs["pdf"]
    figure_png = ROOT / outputs["png"]
    MANUSCRIPT_FIGURE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(figure_pdf, MANUSCRIPT_FIGURE)

    manifest = {
        "purpose": "compact main-text finite-tprime Figure 5",
        "hopping_ratio": TP,
        "layout": {
            "a": "Mott-side spectrum at U=20, V=0",
            "b": "U-only GZ curves and spin-correlation reference",
            "c": "CDW-side spectrum at U=0, V=5",
            "d": "V-only GZ curves and charge-defect reference",
        },
        "removed_former_panels": [
            "b: Mott spectrum at tprime=-0.4",
            "d: U-only curves at tprime=-0.4",
            "f: CDW spectrum at tprime=-0.4",
            "h: V-only curves at tprime=-0.4",
        ],
        "supplemental_coverage": "Both tprime=-0.25 and -0.4 remain in Supplemental Figs. S10 and S11.",
        "spin_limit_coefficients": {
            "s_nn": SPIN_LIMIT_COEFFICIENTS[TP][0],
            "s_nnn": SPIN_LIMIT_COEFFICIENTS[TP][1],
        },
        "outputs": outputs,
        "manuscript_pdf": str(MANUSCRIPT_FIGURE.relative_to(ROOT)),
        "metrics_csv": str(METRICS_OUT.relative_to(ROOT)),
        "sha256": sha256(figure_pdf),
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if figure_pdf.read_bytes()[:4] != b"%PDF" or figure_png.stat().st_size == 0:
        raise RuntimeError("Invalid compact Figure 5 outputs")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
