#!/usr/bin/env python3
"""Condense the density-resolved Hubbard benchmark into three panels.

The main-text layout places energy and double occupancy in the first row and
centers magnetization in the second row.  Each axes frame retains the physical
width, height, and aspect ratio of the earlier one-row version.

Energy and double occupancy combine the n=1, 0.875, and 0.8 MMHK sequences
with a deliberately strict doped comparison.  At fixed (n,U), CP-AFQMC is
first reduced to its largest finite TABC system, after which the lowest
energy among the retained CP-AFQMC and unextrapolated 4x4 DMET calculations
is selected.  Double occupancy follows that energy calculation whenever
available; otherwise it uses the closest same-parameter result.  No
observable is borrowed across U or density.  Thermodynamic extrapolations
and BCS-state rows are excluded.  Magnetization is restricted to half
filling because no like-for-like doped magnetic benchmark series matches
the finite-resolution MMHK estimator.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manuscript_figure_style import outside_panel_label  # noqa: E402
from plot_away_half_filling_comparison import (  # noqa: E402
    MMHK_SOURCE,
    RESULTS,
    STYLE,
    build_figs2_strict_dataset,
    select_figs2_doped_references,
)


HALF_METHODS_SOURCE = RESULTS / "half_filling_methods.csv"
OUT = ROOT / "figures" / "pnas_main"

DENSITY_STYLES = {
    1.0: {
        "color": "#b7473e",
        "label": r"MMHK, $n=1$",
    },
    0.875: {
        "color": "#2d6f9f",
        "label": r"MMHK, $n=0.875$",
    },
    0.8: {
        "color": "#8060b0",
        "label": r"MMHK, $n=0.8$",
    },
}
METHOD_STYLES = {
    "CP-AFQMC": {
        "marker": "o",
        "label": "(CP)-AFQMC",
    },
    "DMET": {
        "marker": "^",
        "label": "DMET",
    },
}


PANEL_LABEL_FONTSIZE = 15.5
LEGEND_FONTSIZE = 11.5
ANNOTATION_FONTSIZE = 13.5
HEISENBERG_TEXT_FONTSIZE = 11.5
BENCHMARK_LEGEND_X = 0.005
MMHK_LEGEND_HANDLE_LENGTH = 1.05


def panel_label(ax: plt.Axes, label: str, *, x: float = -0.105) -> None:
    outside_panel_label(
        ax,
        label,
        x=x,
        fontsize=PANEL_LABEL_FONTSIZE,
    )


def plot_mmhk_density_lines(
    ax: plt.Axes,
    mmhk: pd.DataFrame,
    column: str,
    *,
    densities: tuple[float, ...] = (1.0, 0.875, 0.8),
) -> None:
    for density in densities:
        rows = mmhk[np.isclose(mmhk["n_target"], density)].sort_values("U")
        style = DENSITY_STYLES[density]
        ax.plot(
            rows["U"],
            rows[column],
            color=style["color"],
            marker="o",
            ms=4.6,
            mfc=style["color"],
            mec="white",
            mew=0.35,
            lw=1.8,
            zorder=3,
        )


def plot_half_filling_references(
    ax: plt.Axes,
    methods: pd.DataFrame,
    property_name: str,
) -> None:
    references = methods[methods["property"].eq(property_name)]
    for method, source_method in (
        ("CP-AFQMC", "AFQMC"),
        ("DMET", "DMET"),
    ):
        rows = references[references["method"].eq(source_method)].sort_values("U")
        style = METHOD_STYLES[method]
        density_color = DENSITY_STYLES[1.0]["color"]
        ax.errorbar(
            rows["U"],
            rows["value"],
            yerr=rows["sigma"].fillna(0.0),
            fmt=style["marker"],
            ms=5.8,
            capsize=2.2,
            color=density_color,
            mfc="white",
            mec=density_color,
            mew=1.0,
            linestyle="none",
            zorder=7,
        )


def select_half_filling_reference_rows(methods: pd.DataFrame) -> pd.DataFrame:
    """Select the lowest-energy method and its corresponding D at each U."""
    external = methods[methods["method"].isin(["AFQMC", "DMET"])].copy()
    energy = external[external["property"].eq("Ground State Energy")]
    selected_energy_rows: list[pd.Series] = []
    selected_d_rows: list[pd.Series] = []

    for U, rows in energy.groupby("U", sort=True):
        selected_energy = rows.loc[rows["value"].idxmin()].copy()
        selected_energy["selection_reason"] = "lowest_energy_at_fixed_U"
        selected_energy["paired_energy_method"] = selected_energy["method"]
        selected_energy["paired_energy_value"] = selected_energy["value"]
        selected_energy_rows.append(selected_energy)

        d_candidates = external[
            external["property"].eq("Double Occupancy")
            & np.isclose(external["U"], float(U))
        ]
        same_method = d_candidates[
            d_candidates["method"].eq(selected_energy["method"])
        ]
        if not same_method.empty:
            selected_d = same_method.iloc[0].copy()
            pairing = "corresponding_lowest_energy_method"
        elif not d_candidates.empty:
            # Never borrow D from a different U. If the selected method has no
            # D, use the same-U method whose energy is closest to the minimum.
            candidate_energy = energy[
                np.isclose(energy["U"], float(U))
                & energy["method"].isin(d_candidates["method"])
            ].set_index("method")["value"]
            distances = d_candidates["method"].map(
                lambda method: abs(
                    float(candidate_energy.loc[method])
                    - float(selected_energy["value"])
                )
            )
            selected_d = d_candidates.loc[distances.idxmin()].copy()
            pairing = "closest_energy_method_same_parameter"
        else:
            continue
        selected_d["selection_reason"] = pairing
        selected_d["paired_energy_method"] = selected_energy["method"]
        selected_d["paired_energy_value"] = selected_energy["value"]
        selected_d_rows.append(selected_d)

    # Magnetization is not the U derivative paired to the selected energy, so
    # retain both directly reported half-filled magnetic estimates.
    magnetization = external[
        external["property"].eq("Magnetization")
    ].copy()
    magnetization["selection_reason"] = "all_direct_magnetization_references"
    magnetization["paired_energy_method"] = ""
    magnetization["paired_energy_value"] = np.nan

    selected = pd.concat(
        [
            pd.DataFrame(selected_energy_rows),
            pd.DataFrame(selected_d_rows),
            magnetization,
        ],
        ignore_index=True,
        sort=False,
    )
    if selected[
        selected["property"].eq("Ground State Energy")
    ].duplicated("U").any():
        raise ValueError("Duplicate selected half-filled energy")
    if selected[
        selected["property"].eq("Double Occupancy")
    ].duplicated("U").any():
        raise ValueError("Duplicate selected half-filled double occupancy")
    return selected


def plot_doped_references(
    ax: plt.Axes,
    data: pd.DataFrame,
    observable: str,
) -> None:
    """Overlay only finite TABC CP-AFQMC and 4x4 DMET references."""
    group = data[
        data["density"].isin([0.8, 0.875])
        & data["observable"].eq(observable)
    ]

    tabc = group[
        group["method"].eq("CP-AFQMC")
        & group["record_type"].eq("tabc_resolved")
    ]
    style = METHOD_STYLES["CP-AFQMC"]
    for row in tabc.itertuples(index=False):
        color = DENSITY_STYLES[float(row.density)]["color"]
        ax.errorbar(
            float(row.U),
            float(row.value),
            yerr=0.0 if pd.isna(row.sigma) else float(row.sigma),
            fmt=style["marker"],
            ms=4.5,
            mfc="white",
            mec=color,
            ecolor=color,
            mew=0.85,
            capsize=1.4,
            linestyle="none",
            alpha=0.90,
            zorder=5,
        )

    embeddings = group[
        group["method"].eq("DMET")
        & group["record_type"].eq("finite_embedding")
        & group["system"].astype(str).eq("4x4")
    ]
    style = METHOD_STYLES["DMET"]
    for row in embeddings.itertuples(index=False):
        color = DENSITY_STYLES[float(row.density)]["color"]
        ax.errorbar(
            float(row.U),
            float(row.value),
            yerr=0.0 if pd.isna(row.sigma) else float(row.sigma),
            fmt=style["marker"],
            ms=4.4,
            mfc="white",
            mec=color,
            ecolor=color,
            mew=0.95,
            capsize=1.7,
            linestyle="none",
            alpha=0.90,
            zorder=5,
        )


def method_and_density_legend(ax: plt.Axes) -> None:
    """Use color for density and open-marker shape for reference method."""
    density_handles: list[Line2D] = []
    for density in (1.0, 0.875, 0.8):
        style = DENSITY_STYLES[density]
        density_handles.append(
            Line2D(
                [0],
                [0],
                color=style["color"],
                marker="o",
                ms=4.8,
                mfc=style["color"],
                mec="white",
                mew=0.35,
                lw=1.8,
                label=style["label"],
            )
        )
    method_handles = [
        Line2D(
            [0],
            [0],
            color="none",
            marker="o",
            ms=5.7,
            mfc="white",
            mec="0.18",
            mew=1.0,
            label="(CP)-AFQMC",
        ),
        Line2D(
            [0],
            [0],
            color="none",
            marker="^",
            ms=5.8,
            mfc="white",
            mec="0.18",
            mew=1.0,
            label="DMET",
        ),
    ]
    # Keep the complete key in one reading-order column.
    handles = density_handles + method_handles
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(BENCHMARK_LEGEND_X, 1.0),
        ncol=1,
        frameon=False,
        fontsize=LEGEND_FONTSIZE,
        # Only the MMHK entries contain line segments; shortening the common
        # handle therefore shortens those samples without changing the open
        # AFQMC/DMET marker symbols.
        handlelength=MMHK_LEGEND_HANDLE_LENGTH,
        handletextpad=0.40,
        labelspacing=0.12,
        borderaxespad=0.10,
    )


def write_open_marker_inventory(data: pd.DataFrame) -> Path:
    """Record every retained finite doped reference and plotted position."""
    selected = data[
        data["record_type"].isin(["tabc_resolved", "finite_embedding"])
    ].copy()
    selected["open_marker_category"] = ""
    selected.loc[
        selected["record_type"].eq("tabc_resolved"),
        "open_marker_category",
    ] = "largest-system finite TABC CP-AFQMC calculation"
    selected.loc[
        selected["record_type"].eq("finite_embedding"),
        "open_marker_category",
    ] = "unextrapolated 4x4 DMET embedding"
    selected["figure_panel"] = np.where(
        selected["observable"].eq("energy"),
        "(a) ground-state energy",
        "(b) double occupancy",
    )
    selected["marker_description"] = np.where(
        selected["method"].eq("DMET"),
        "open triangle; edge color encodes density",
        "open circle; edge color encodes density",
    )
    selected["density_color_hex"] = selected["density"].map(
        lambda density: DENSITY_STYLES[float(density)]["color"]
    )
    selected["plotted_x"] = np.nan

    # Every benchmark marker is plotted at its physical interaction value.
    # Marker shape, fill, and color—not horizontal jitter—distinguish sources.
    selected["plotted_x"] = selected["U"].astype(float)

    columns = [
        "figure_panel",
        "open_marker_category",
        "marker_description",
        "density_color_hex",
        "plotted_x",
        "density",
        "observable",
        "method",
        "U",
        "value",
        "sigma",
        "system",
        "boundary",
        "state",
        "candidate_selection",
        "selection_reason",
        "paired_energy_method",
        "paired_energy_system",
        "paired_energy_value",
        "quality_flag",
        "study",
        "source_url",
        "source_local",
    ]
    output = RESULTS / "figS2_open_marker_inventory.csv"
    selected[columns].sort_values(
        [
            "figure_panel",
            "open_marker_category",
            "method",
            "U",
            "plotted_x",
        ],
        kind="stable",
    ).to_csv(output, index=False)
    return output


def write_source_filter_audit(
    candidates: pd.DataFrame,
    selected: pd.DataFrame,
    selected_half: pd.DataFrame,
) -> Path:
    """Write machine-readable evidence that all selection rules hold."""
    candidate_external = candidates[~candidates["method"].eq("MMHK")].copy()
    external = selected[~selected["method"].eq("MMHK")].copy()
    selected_energy = external[external["observable"].eq("energy")]
    selected_d = external[external["observable"].eq("double_occupancy")]
    selected_cp = selected_energy[selected_energy["method"].eq("CP-AFQMC")]
    selected_dmet_energy = selected_energy[selected_energy["method"].eq("DMET")]
    selected_dmet_d = selected_d[selected_d["method"].eq("DMET")]
    half_energy = selected_half[
        selected_half["property"].eq("Ground State Energy")
    ]
    half_d = selected_half[
        selected_half["property"].eq("Double Occupancy")
    ]

    audit = {
        "scope": "external comparison in main-text Fig. 1",
        "candidate_external_rows": int(len(candidate_external)),
        "candidate_cp_afqmc_tabc_rows": int(
            (
                candidate_external["method"].eq("CP-AFQMC")
                & candidate_external["boundary"]
                .astype(str)
                .str.upper()
                .eq("TABC")
            ).sum()
        ),
        "candidate_dmet_4x4_rows": int(
            (
                candidate_external["method"].eq("DMET")
                & candidate_external["system"].astype(str).eq("4x4")
            ).sum()
        ),
        "selected_external_rows": int(len(external)),
        "selected_energy_rows": int(len(selected_energy)),
        "selected_cp_afqmc_energy_rows": int(len(selected_cp)),
        "selected_cp_afqmc_systems": sorted(
            selected_cp["system"].astype(str).unique().tolist()
        ),
        "selected_dmet_energy_rows": int(len(selected_dmet_energy)),
        "selected_dmet_double_occupancy_rows": int(len(selected_dmet_d)),
        "selected_corresponding_do_rows": int(
            selected_d["selection_reason"]
            .astype(str)
            .eq("corresponding_method_and_system")
            .sum()
        ),
        "selected_same_parameter_fallback_do_rows": int(
            selected_d["selection_reason"]
            .astype(str)
            .eq("closest_same_parameter_other_method")
            .sum()
        ),
        "selected_energy_duplicate_parameter_sets": int(
            selected_energy.duplicated(["density", "U"]).sum()
        ),
        "selected_do_duplicate_parameter_sets": int(
            selected_d.duplicated(["density", "U"]).sum()
        ),
        "thermodynamic_extrapolation_rows": int(
            external["record_type"].eq("benchmark_tdl").sum()
        ),
        "bcs_state_rows": int(
            external["state"]
            .astype(str)
            .str.contains("BCS", case=False, na=False)
            .sum()
        ),
        "non_tabc_cp_afqmc_rows": int(
            (
                external["method"].eq("CP-AFQMC")
                & ~external["boundary"].astype(str).str.upper().eq("TABC")
            ).sum()
        ),
        "non_4x4_dmet_rows": int(
            (
                external["method"].eq("DMET")
                & ~external["system"].astype(str).eq("4x4")
            ).sum()
        ),
        "half_filling_selected_energy_rows": int(len(half_energy)),
        "half_filling_selected_do_rows": int(len(half_d)),
        "half_filling_corresponding_do_rows": int(
            half_d["selection_reason"]
            .astype(str)
            .eq("corresponding_lowest_energy_method")
            .sum()
        ),
        "half_filling_selected_energy_methods_by_U": {
            f"{float(row.U):g}": str(row.method)
            for row in half_energy.sort_values("U").itertuples(index=False)
        },
        "visual_encoding": {
            "density": "color",
            "MMHK": "colored line with filled circular markers",
            "AFQMC_or_CP_AFQMC": "open circles",
            "DMET": "open triangles",
            "legend": "single column at upper left of panel a",
            "x_coordinate": "exact U/t for every method; no horizontal offsets",
        },
    }
    output = RESULTS / "figS2_source_filter_audit.json"
    output.write_text(json.dumps(audit, indent=2) + "\n")
    return output


def build_condensed_density_benchmark(
    stem: str = "pnas_supp_combined_density_benchmark",
    *,
    output_dir: Path = OUT,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = build_figs2_strict_dataset()
    doped = select_figs2_doped_references(candidates)
    candidates.to_csv(
        RESULTS / "figS2_filtered_candidate_data.csv", index=False
    )
    doped.to_csv(
        RESULTS / "figS2_filtered_comparison_data.csv", index=False
    )
    doped.to_csv(
        RESULTS / "figS2_selected_comparison_data.csv", index=False
    )
    write_open_marker_inventory(doped)
    mmhk = pd.read_csv(MMHK_SOURCE)
    methods_all = pd.read_csv(HALF_METHODS_SOURCE)
    methods = select_half_filling_reference_rows(methods_all)
    methods.to_csv(
        RESULTS / "figS2_selected_half_filling_references.csv",
        index=False,
    )
    write_source_filter_audit(candidates, doped, methods)

    expected_densities = {0.8, 0.875, 1.0}
    expected_u = {2.0, 4.0, 6.0, 8.0, 10.0, 12.0}
    if (
        set(mmhk["n_target"].astype(float)) != expected_densities
        or set(mmhk["U"].astype(float)) != expected_u
        or len(mmhk) != len(expected_densities) * len(expected_u)
    ):
        raise ValueError("The MMHK multi-density source is not a complete 3x6 grid")

    condensed_style = dict(STYLE)
    condensed_style.update(
        {
            "font.size": 13.5,
            "axes.labelsize": 15.5,
            "axes.titlesize": 15.5,
            "xtick.labelsize": 13.5,
            "ytick.labelsize": 13.5,
            "lines.linewidth": 1.8,
        }
    )

    with plt.rc_context(condensed_style):
        # Preserve the axes-frame dimensions of the former 1x3 layout exactly:
        #   width  = (0.994 - 0.072) * 10.2 / (3 + 2 * 0.27)
        #   height = (0.90  - 0.15)  * 3.45
        # Keeping the 10.2-inch canvas width also preserves the panel size when
        # the PDF is included at the same width in the manuscript.
        fig_width = 10.2
        fig_height = 6.675
        panel_width = (0.994 - 0.072) * 10.2 / (3.0 + 2.0 * 0.27)
        panel_height = (0.90 - 0.15) * 3.45
        # Keep both axes frames unchanged while giving the enlarged labels a
        # little more breathing room between the two top-row panels.
        column_gap = 0.34 * panel_width
        row_gap = 0.70
        bottom = 0.65

        top_group_width = 2.0 * panel_width + column_gap
        top_left = 0.5 * (fig_width - top_group_width)
        lower_left = 0.5 * (fig_width - panel_width)
        top_bottom = bottom + panel_height + row_gap

        fig = plt.figure(figsize=(fig_width, fig_height))

        def add_panel(left_in: float, bottom_in: float) -> plt.Axes:
            return fig.add_axes(
                [
                    left_in / fig_width,
                    bottom_in / fig_height,
                    panel_width / fig_width,
                    panel_height / fig_height,
                ]
            )

        energy_ax = add_panel(top_left, top_bottom)
        double_ax = add_panel(top_left + panel_width + column_gap, top_bottom)
        magnetization_ax = add_panel(lower_left, bottom)
        axes = np.asarray([energy_ax, double_ax, magnetization_ax])

        plot_mmhk_density_lines(
            energy_ax, mmhk, "ground_state_energy"
        )
        plot_half_filling_references(
            energy_ax, methods, "Ground State Energy"
        )
        plot_doped_references(energy_ax, doped, "energy")

        plot_mmhk_density_lines(
            double_ax, mmhk, "double_occupancy_i"
        )
        plot_half_filling_references(
            double_ax, methods, "Double Occupancy"
        )
        plot_doped_references(double_ax, doped, "double_occupancy")

        # The magnetic panel is deliberately restricted to half filling:
        # doped literature primarily reports incommensurate stripe profiles or
        # broken-symmetry order parameters, not this same scalar estimator.
        plot_mmhk_density_lines(
            magnetization_ax,
            mmhk,
            "magnetization",
            densities=(1.0,),
        )
        plot_half_filling_references(
            magnetization_ax, methods, "Magnetization"
        )
        magnetization_ax.axhline(0.307, color="0.42", ls="--", lw=1.1)
        magnetization_ax.text(
            0.035,
            0.945,
            "Heisenberg limit",
            transform=magnetization_ax.transAxes,
            color="0.38",
            ha="left",
            va="top",
            fontsize=HEISENBERG_TEXT_FONTSIZE,
        )
        magnetization_ax.text(
            0.965,
            0.055,
            r"$n=1$",
            transform=magnetization_ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=ANNOTATION_FONTSIZE,
            fontweight="bold",
        )

        ylabels = (r"$E_0/(Nt)$", r"$D$", r"$m$")
        ylimits = ((-1.34, -0.31), (0.012, 0.202), (0.085, 0.34))
        for idx, (ax, ylabel, ylim) in enumerate(
            zip(axes, ylabels, ylimits)
        ):
            ax.set_xlabel(r"$U/t$")
            ax.set_ylabel(ylabel)
            ax.set_xlim(1.45, 12.55)
            ax.set_ylim(*ylim)
            ax.set_xticks([2, 4, 6, 8, 10, 12])
            ax.grid(alpha=0.20)
            panel_label(
                ax,
                f"({chr(97 + idx)})",
                x=-0.20 if idx == 1 else -0.18,
            )

        method_and_density_legend(energy_ax)

        pdf = output_dir / f"{stem}.pdf"
        png = output_dir / f"{stem}.png"
        # Crop away the deliberately unused canvas columns after arranging the
        # three fixed-size panels.  A very small pad protects the outside panel
        # labels while keeping the left/right margins visually minimal.
        fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
        fig.savefig(png, dpi=260, bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)

    return {
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
    }


def main() -> None:
    outputs = build_condensed_density_benchmark()
    print(f"Wrote {outputs['pdf']}")
    print(f"Wrote {outputs['png']}")


if __name__ == "__main__":
    main()
