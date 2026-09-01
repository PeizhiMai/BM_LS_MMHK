#!/usr/bin/env python3
"""Build separate Mott- and CDW-axis figures for the current PRL-style paper.

The preserved four-figure PRL and PNAS figures are intentionally left
unchanged. Each current figure uses four spectral snapshots, a common
zero-dispersion comparison, and an interaction-axis convergence panel so that
it makes a self-contained microscopic argument.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from manuscript_figure_style import (
    ZERO_DISPERSION_AXIS_LABEL,
    outside_panel_label,
)
from build_scale_and_transition_figure import build_figure as build_scale_figure


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/Gcalpath"
RESULTS = ROOT / "results"
OUT = ROOT / "figures/prl_main"
OUT.mkdir(parents=True, exist_ok=True)

U_SOURCE = (
    DATA / "luttinger_surface_eta0p05" / "luttinger_tp0_eta0p05_spectra_and_roots.npz"
)
V_DIRECTORY = DATA / "luttinger_surface_eta0p05_U0_finiteV"
AXIS_SCALE_SOURCE = RESULTS / "additional2_zero_dispersion_scale_fits_eta0p05.csv"
METRICS_OUT = RESULTS / "prl_split_axis_figure_metrics.csv"

U_MAP_VALUES = [8, 12, 20, 40]
V_MAP_VALUES = [2, 5, 8, 12]
U_YLIMS = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
U_COLORS = {
    8: "#2d6f9f",
    12: "#d17b25",
    20: "#3f8a55",
    40: "#c54d3f",
}
V_COLORS = {
    2: "#2d6f9f",
    5: "#d17b25",
    8: "#3f8a55",
    12: "#c54d3f",
}

S_U_RESOLUTION = -1.4035604012
S_V = -8.0 / 7.0

STYLE = {
    "font.family": "Arial",
    "font.size": 9.0,
    "axes.labelsize": 10.0,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.0,
    "axes.linewidth": 0.9,
    "lines.linewidth": 1.4,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def _fit_scale(epsilon1: np.ndarray, root: np.ndarray) -> dict[str, float]:
    finite = np.isfinite(root)
    if finite.sum() < 2:
        raise ValueError("Too few finite roots for a scale fit")
    x = epsilon1[finite]
    y = root[finite]
    scale = float(np.dot(x, y) / np.dot(x, x))
    fitted = scale * x
    rmse = float(np.sqrt(np.mean((y - fitted) ** 2)))
    design = np.column_stack([x, np.ones_like(x)])
    scale_with_offset, offset = np.linalg.lstsq(design, y, rcond=None)[0]
    return {
        "s_zero_offset": scale,
        "rmse_zero_offset": rmse,
        "s_with_offset": float(scale_with_offset),
        "diagnostic_offset": float(offset),
        "accepted_root_count": int(finite.sum()),
    }


def _k_axis(ax: plt.Axes) -> None:
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    for xpos in (40, 80):
        ax.axvline(xpos, color="black", lw=0.5, ls="--", alpha=0.72)


def _panel_label(
    ax: plt.Axes,
    text: str,
    *,
    x: float = -0.13,
    y: float = 0.985,
    fontsize: float = 10.0,
) -> None:
    outside_panel_label(ax, text, fontsize=fontsize, x=x, y=y)


def _spectral_map(
    ax: plt.Axes,
    omega: np.ndarray,
    rho: np.ndarray,
    roots: np.ndarray,
    *,
    ylim: float,
    text: str,
    vmax: float,
    show_ylabel: bool,
    annotation_fontsize: float = 8.7,
) -> plt.AxesImage:
    mask = np.abs(omega) <= ylim
    image = np.maximum(np.asarray(rho[:, mask], dtype=float), 0.0).T
    im = ax.imshow(
        image,
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
        extent=[0, 120, float(omega[mask][0]), float(omega[mask][-1])],
        cmap="rainbow",
        vmin=0.0,
        vmax=vmax,
        rasterized=True,
    )
    ax.plot(np.arange(121), roots, color="white", lw=1.45)
    ax.axhline(0.0, color="black", lw=0.7, ls="--", alpha=0.85)
    _k_axis(ax)
    ax.set_ylim(-ylim, ylim)
    if show_ylabel:
        ax.set_ylabel(r"$\omega/t$")
    ax.text(
        0.04,
        0.43,
        text,
        transform=ax.transAxes,
        color="white",
        ha="left",
        va="center",
        fontsize=annotation_fontsize,
        fontweight="bold",
    )
    return im


def _zero_curve_axis(ax: plt.Axes) -> None:
    ax.axhline(0.0, color="0.55", lw=0.55)
    _k_axis(ax)
    ax.set_ylim(-6.2, 6.2)
    ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
    ax.grid(alpha=0.18)


def _colorbar_above(
    fig: plt.Figure,
    axes: list[plt.Axes],
    image: plt.AxesImage,
    *,
    label_fontsize: float = 10.0,
    tick_fontsize: float = 8.5,
) -> None:
    first = axes[0].get_position()
    last = axes[-1].get_position()
    cax = fig.add_axes([first.x0, first.y1 + 0.016, last.x1 - first.x0, 0.018])
    cbar = fig.colorbar(image, cax=cax, orientation="horizontal")
    cbar.ax.xaxis.set_ticks_position("top")
    cbar.ax.xaxis.set_label_position("top")
    cbar.set_label(
        r"$\rho_G(\mathbf{k},\omega)$",
        labelpad=1,
        fontsize=label_fontsize,
    )
    cbar.ax.tick_params(
        labelsize=tick_fontsize,
        length=4.0,
        width=0.9,
        pad=1,
    )


def _save(fig: plt.Figure, stem: str) -> dict[str, str]:
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return {
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
    }


def _load_sources():
    u_data = np.load(U_SOURCE)
    u_values = [int(value) for value in u_data["U"]]
    k_path = np.asarray(u_data["k_path"], dtype=float)
    kx = k_path[:, 0] * np.pi / 40.0
    ky = k_path[:, 1] * np.pi / 40.0
    epsilon1 = -2.0 * (np.cos(kx) + np.cos(ky))

    v_data = {}
    for value in V_MAP_VALUES:
        path = V_DIRECTORY / f"rhoG_LS_U0_V{value}_tp0_eta0p05_spectra_and_roots.npz"
        record = np.load(path)
        if not np.array_equal(np.asarray(record["k_path"], dtype=float), k_path):
            raise ValueError(f"Momentum path mismatch for V={value}")
        v_data[value] = record
    return u_data, u_values, v_data, epsilon1


def _axis_metrics(
    u_data,
    u_values: list[int],
    v_data: dict[int, np.lib.npyio.NpzFile],
    epsilon1: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for value in U_MAP_VALUES:
        index = u_values.index(value)
        metrics = _fit_scale(epsilon1, np.asarray(u_data["omega_root"][index]))
        rows.append(
            {
                "axis": "Mott",
                "U": value,
                "V": 0,
                "shown_as_spectrum": True,
                "source": str(U_SOURCE.relative_to(ROOT)),
                **metrics,
            }
        )
    for value in V_MAP_VALUES:
        path = V_DIRECTORY / f"rhoG_LS_U0_V{value}_tp0_eta0p05_spectra_and_roots.npz"
        metrics = _fit_scale(
            epsilon1, np.asarray(v_data[value]["omega_root"], dtype=float)
        )
        rows.append(
            {
                "axis": "CDW",
                "U": 0,
                "V": value,
                "shown_as_spectrum": True,
                "source": str(path.relative_to(ROOT)),
                **metrics,
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(METRICS_OUT, index=False)
    return result


def build_mott_figure(
    u_data,
    u_values: list[int],
    epsilon1: np.ndarray,
    metrics: pd.DataFrame,
) -> dict[str, str]:
    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(7.15, 4.635))
        outer = fig.add_gridspec(
            1,
            2,
            width_ratios=[2.0, 1.08],
            wspace=0.22,
        )
        maps_grid = outer[0, 0].subgridspec(2, 2, hspace=0.15, wspace=0.25)
        analysis_grid = outer[0, 1].subgridspec(2, 1, hspace=0.15)
        map_axes = [
            fig.add_subplot(maps_grid[0, 0]),
            fig.add_subplot(maps_grid[0, 1]),
            fig.add_subplot(maps_grid[1, 0]),
            fig.add_subplot(maps_grid[1, 1]),
        ]
        curve_ax = fig.add_subplot(analysis_grid[0, 0])
        scale_ax = fig.add_subplot(analysis_grid[1, 0])
        fig.subplots_adjust(left=0.065, right=0.992, bottom=0.085, top=0.91)

        image = None
        for index, (ax, value) in enumerate(zip(map_axes, U_MAP_VALUES)):
            source_index = u_values.index(value)
            image = _spectral_map(
                ax,
                np.asarray(u_data["omega"], dtype=float),
                np.asarray(u_data["rho_G"][source_index], dtype=float),
                np.asarray(u_data["omega_root"][source_index], dtype=float),
                ylim=U_YLIMS[value],
                text=rf"$U={value}$",
                vmax=1.5,
                show_ylabel=index % 2 == 0,
            )
            _panel_label(
                ax,
                f"({chr(97 + index)})",
                x=-0.15 if index in (0, 2) else -0.13,
            )
        if image is None:
            raise RuntimeError("No Mott-side spectral maps were rendered")
        _colorbar_above(fig, map_axes, image)

        x = np.arange(121)
        for value in U_MAP_VALUES:
            source_index = u_values.index(value)
            curve_ax.plot(
                x,
                np.asarray(u_data["omega_root"][source_index], dtype=float),
                color=U_COLORS[value],
                label=rf"$U={value}$",
            )
        s_u40 = float(
            metrics.loc[
                (metrics["axis"] == "Mott") & (metrics["U"] == 40),
                "s_zero_offset",
            ].iloc[0]
        )
        curve_ax.plot(
            x,
            s_u40 * epsilon1,
            color="black",
            ls="--",
            lw=1.05,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
        )
        _zero_curve_axis(curve_ax)
        curve_ax.yaxis.set_label_coords(-0.10, 0.5)
        curve_handles, curve_labels = curve_ax.get_legend_handles_labels()
        curve_legend_order = [0, 2, 4, 1, 3]
        curve_ax.legend(
            [curve_handles[i] for i in curve_legend_order],
            [curve_labels[i] for i in curve_legend_order],
            frameon=False,
            ncol=2,
            loc="upper center",
            bbox_to_anchor=(0.52, 0.99),
            fontsize=8.2,
            handlelength=1.15,
            columnspacing=0.70,
            labelspacing=0.10,
            borderaxespad=0.10,
        )
        _panel_label(curve_ax, "(e)", x=-0.075)

        axis_scale = pd.read_csv(AXIS_SCALE_SOURCE)
        u_rows = axis_scale[(axis_scale["U"] > 0) & (axis_scale["V"] == 0)].copy()
        u_rows = u_rows.sort_values("U")
        scale_ax.plot(
            1.0 / u_rows["U"],
            -u_rows["s"],
            "o-",
            color="#c54d3f",
            markerfacecolor="white",
            markeredgewidth=1.5,
        )
        scale_ax.axhline(
            S_U_RESOLUTION,
            color="black",
            ls="--",
            lw=1.35,
        )
        scale_ax.text(
            0.94,
            S_U_RESOLUTION + 0.0035,
            r"$4\langle\mathbf{S}_i\!\cdot\!\mathbf{S}_j"
            r"\rangle_{\rm NN,U\to\infty}$",
            transform=scale_ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=9.62,
            color="black",
        )
        scale_ax.set_xlabel(r"$t/U$")
        scale_ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(U,0)$")
        scale_ax.yaxis.set_label_coords(-0.22, 0.5)
        scale_ax.set_xlim(-0.004, 0.132)
        # The refined U=10 point reaches -1.2831.  Keep a small headroom so
        # the validated marker is never clipped by the top spine.
        scale_ax.set_ylim(-1.415, -1.278)
        scale_ax.set_yticks([-1.40, -1.38, -1.36, -1.34, -1.32, -1.30])
        scale_ax.grid(alpha=0.18)
        _panel_label(scale_ax, "(f)", x=-0.075)
        return _save(fig, "fig2_mott_zero_mechanism")


def build_cdw_figure(
    v_data: dict[int, np.lib.npyio.NpzFile],
    epsilon1: np.ndarray,
    metrics: pd.DataFrame,
) -> dict[str, str]:
    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(7.15, 4.635))
        outer = fig.add_gridspec(
            1,
            2,
            width_ratios=[2.0, 1.08],
            wspace=0.22,
        )
        maps_grid = outer[0, 0].subgridspec(2, 2, hspace=0.15, wspace=0.25)
        analysis_grid = outer[0, 1].subgridspec(2, 1, hspace=0.15)
        map_axes = [
            fig.add_subplot(maps_grid[0, 0]),
            fig.add_subplot(maps_grid[0, 1]),
            fig.add_subplot(maps_grid[1, 0]),
            fig.add_subplot(maps_grid[1, 1]),
        ]
        curve_ax = fig.add_subplot(analysis_grid[0, 0])
        scale_ax = fig.add_subplot(analysis_grid[1, 0])
        fig.subplots_adjust(left=0.065, right=0.992, bottom=0.085, top=0.91)

        image = None
        for index, (ax, value) in enumerate(zip(map_axes, V_MAP_VALUES)):
            record = v_data[value]
            image = _spectral_map(
                ax,
                np.asarray(record["omega"], dtype=float),
                np.asarray(record["rho_G"], dtype=float),
                np.asarray(record["omega_root"], dtype=float),
                ylim=float(record["ylim"]),
                text=rf"$V={value}$",
                vmax=2.5,
                show_ylabel=index % 2 == 0,
            )
            _panel_label(
                ax,
                f"({chr(97 + index)})",
                x=-0.15 if index in (0, 2) else -0.13,
            )
        if image is None:
            raise RuntimeError("No CDW-side spectral maps were rendered")
        _colorbar_above(fig, map_axes, image)

        x = np.arange(121)
        for value in V_MAP_VALUES:
            curve_ax.plot(
                x,
                np.asarray(v_data[value]["omega_root"], dtype=float),
                color=V_COLORS[value],
                label=rf"$V={value}$",
            )
        s_v12 = float(
            metrics.loc[
                (metrics["axis"] == "CDW") & (metrics["V"] == 12),
                "s_zero_offset",
            ].iloc[0]
        )
        curve_ax.plot(
            x,
            s_v12 * epsilon1,
            color="black",
            ls="--",
            lw=1.05,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
        )
        _zero_curve_axis(curve_ax)
        curve_ax.yaxis.set_label_coords(-0.10, 0.5)
        curve_handles, curve_labels = curve_ax.get_legend_handles_labels()
        curve_legend_order = [0, 2, 4, 1, 3]
        curve_ax.legend(
            [curve_handles[i] for i in curve_legend_order],
            [curve_labels[i] for i in curve_legend_order],
            frameon=False,
            ncol=2,
            loc="upper center",
            bbox_to_anchor=(0.52, 0.99),
            fontsize=8.2,
            handlelength=1.15,
            columnspacing=0.70,
            labelspacing=0.10,
            borderaxespad=0.10,
        )
        _panel_label(curve_ax, "(e)", x=-0.075)

        axis_scale = pd.read_csv(AXIS_SCALE_SOURCE)
        v_rows = axis_scale[(axis_scale["U"] == 0) & (axis_scale["V"] > 0)].copy()
        extra_rows = metrics[(metrics["axis"] == "CDW") & (metrics["V"].isin([2, 5]))][
            ["V", "s_zero_offset"]
        ].rename(columns={"s_zero_offset": "s"})
        v_rows["s"] = -v_rows["s"]
        v_rows = pd.concat([v_rows[["V", "s"]], extra_rows], ignore_index=True)
        v_rows = v_rows.drop_duplicates("V", keep="last").sort_values("V")
        scale_ax.plot(
            1.0 / v_rows["V"],
            v_rows["s"],
            "o-",
            color="#2d6f9f",
            markerfacecolor="white",
            markeredgewidth=1.5,
        )
        scale_ax.axhline(
            S_V,
            color="black",
            ls="--",
            lw=1.35,
        )
        scale_ax.text(
            0.94,
            S_V + 0.00018,
            r"$-8/7$",
            transform=scale_ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=10.27,
            color="black",
        )
        scale_ax.set_xlabel(r"$t/V$")
        scale_ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(0,V)$")
        scale_ax.yaxis.set_label_coords(-0.22, 0.5)
        scale_ax.set_xlim(-0.01, 0.52)
        scale_ax.set_ylim(-1.144, -1.135)
        scale_ax.set_yticks([-1.144, -1.142, -1.140, -1.138, -1.136])
        scale_ax.grid(alpha=0.18)
        _panel_label(scale_ax, "(f)", x=-0.075, y=0.985)
        return _save(fig, "fig3_cdw_zero_mechanism")


def build_scale_boundary_figure(
    *,
    fullobs_analysis_dir: Path | None = None,
    production_promotion: bool = False,
) -> tuple[Path, Path]:
    """Build the PRL vertical scale panel without rewriting PNAS tables.

    The optional production route is deliberately explicit and inherits the
    complete non-fixture bundle gate from ``build_scale_figure``.  Production
    delegates to the unified release orchestrator, so the horizontal PNAS
    layout, this vertical PRL layout, derived tables, and pointer commit as one
    generation rather than promoting this pair alone.
    """
    scale_pdf = OUT / "fig4_scale_and_transition_boundary.pdf"
    scale_png = OUT / "fig4_scale_and_transition_boundary.png"
    build_scale_figure(
        out_pdf=scale_pdf,
        out_png=scale_png,
        mixed_momentum_terms=True,
        vertical=True,
        axis_text_scale=1.4,
        fullobs_analysis_dir=fullobs_analysis_dir,
        production_promotion=production_promotion,
        # This secondary vertical rendering must not overwrite the canonical
        # PNAS analytic-validation or filtered-boundary result tables.
        write_derived_tables=False,
    )
    return scale_pdf, scale_png


def main() -> None:
    u_data, u_values, v_data, epsilon1 = _load_sources()
    metrics = _axis_metrics(u_data, u_values, v_data, epsilon1)
    mott = build_mott_figure(u_data, u_values, epsilon1, metrics)
    cdw = build_cdw_figure(v_data, epsilon1, metrics)
    scale_pdf, scale_png = build_scale_boundary_figure()
    print(f"Mott figure: {mott['pdf']}")
    print(f"CDW figure: {cdw['pdf']}")
    print(f"Scale/boundary figure: {scale_pdf.relative_to(ROOT)}")
    print(f"Metrics: {METRICS_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
