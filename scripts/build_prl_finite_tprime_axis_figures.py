#!/usr/bin/env python3
"""Build finite-t' analogues of the current PRL Figures 2 and 3.

Four non-destructive variants are produced: Mott-side (Fig. 2 grammar) and
CDW-side (Fig. 3 grammar) figures at t'=-0.25 and -0.4.  At finite t' the
one-scale model is replaced by the established bond-resolved form

    omega_GZ(k) = delta - s_NN epsilon_1(k) + s_NNN epsilon_2(k),

and panel (f) shows both coefficients approaching their corresponding
strong-coupling predictions.
"""

from __future__ import annotations

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

from manuscript_figure_style import ZERO_DISPERSION_AXIS_LABEL, outside_panel_label
from reproduce_luttinger_figures import centers_to_edges


DATE_TAG = "20260802"
DATA_DIR = (
    ROOT
    / "data/Gcalpath/luttinger_surface_eta0p05_uonly_vonly_finite_tprime_20260802"
)
METRICS_SOURCE = (
    ROOT
    / "results/uonly_vonly_finite_tprime_bond_resolved_eta0p05_20260802.csv"
)
OUT = ROOT / "figures/prl_main/finite_tprime_versions"
METRICS_OUT = ROOT / "results/prl_fig2_fig3_finite_tprime_metrics_eta0p05_20260802.csv"
MANIFEST = ROOT / "results/prl_fig2_fig3_finite_tprime_manifest_20260802.json"

U_VALUES = (8, 12, 20, 40)
V_VALUES = (2, 5, 8, 12)
TP_VALUES = (-0.25, -0.4)
U_YLIMS = {8: 12.0, 12: 15.0, 20: 20.0, 40: 30.0}
V_YLIMS = {2: 15.0, 5: 25.0, 8: 40.0, 12: 60.0}
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
COEFFICIENT_COLORS = {"s_nn": "#2d6f9f", "s_nnn": "#d17b25"}

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


@dataclass
class Spectrum:
    branch: str
    interaction: int
    tp: float
    omega: np.ndarray
    x: np.ndarray
    k_path: np.ndarray
    rho: np.ndarray
    root: np.ndarray
    source: Path


def tp_stem(tp: float) -> str:
    return str(tp).replace("-", "n").replace(".", "p")


def source_path(branch: str, interaction: int, tp: float) -> Path:
    U, V = (interaction, 0) if branch == "U-only" else (0, interaction)
    return DATA_DIR / (
        f"rhoG_LS_U{U}_V{V}_tp{tp_stem(tp)}_eta0p05_spectra_and_roots.npz"
    )


def load_spectrum(branch: str, interaction: int, tp: float) -> Spectrum:
    path = source_path(branch, interaction, tp)
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path) as data:
        eta = float(np.asarray(data["eta"]).item())
        U = float(np.asarray(data["U"]).item())
        V = float(np.asarray(data["V"]).item())
        stored_tp = float(np.asarray(data["tp"]).item())
        omega = np.asarray(data["omega"], dtype=float).copy()
        x = np.asarray(data["x_path"], dtype=float).copy()
        k_path = np.asarray(data["k_path"], dtype=int).copy()
        rho = np.asarray(data["rho_G"], dtype=float).copy()
        root = np.asarray(data["omega_root"], dtype=float).copy()
    expected_U, expected_V = (
        (float(interaction), 0.0) if branch == "U-only" else (0.0, float(interaction))
    )
    if not (
        np.isclose(eta, 0.05)
        and np.isclose(U, expected_U)
        and np.isclose(V, expected_V)
        and np.isclose(stored_tp, tp)
    ):
        raise ValueError(f"Metadata mismatch in {path}")
    if rho.shape != (121, omega.size) or x.shape != (121,) or k_path.shape != (121, 2):
        raise ValueError(f"Unexpected array shape in {path}")
    if root.shape != (121,) or not np.isfinite(root).all():
        raise ValueError(f"Incomplete root curve in {path}")
    return Spectrum(branch, interaction, tp, omega, x, k_path, rho, root, path)


def harmonics(k_path: np.ndarray, tp: float) -> tuple[np.ndarray, np.ndarray]:
    momenta = np.asarray(k_path, dtype=float) * (np.pi / 40.0)
    kx, ky = momenta[:, 0], momenta[:, 1]
    epsilon1 = -2.0 * (np.cos(kx) + np.cos(ky))
    epsilon2 = -4.0 * tp * np.cos(kx) * np.cos(ky)
    return epsilon1, epsilon2


def k_axis(ax: plt.Axes, x: np.ndarray) -> None:
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    for xpos in (x[40], x[80]):
        ax.axvline(xpos, color="black", lw=0.5, ls="--", alpha=0.72)


def panel_label(ax: plt.Axes, text: str, *, x: float = -0.13, y: float = 0.985) -> None:
    outside_panel_label(ax, text, fontsize=10.0, x=x, y=y)


def spectral_map(
    ax: plt.Axes,
    spectrum: Spectrum,
    *,
    ylim: float,
    text: str,
    show_ylabel: bool,
) -> plt.cm.ScalarMappable:
    mask = np.abs(spectrum.omega) <= ylim
    image = ax.pcolormesh(
        centers_to_edges(spectrum.x),
        centers_to_edges(spectrum.omega[mask]),
        np.maximum(spectrum.rho[:, mask], 0.0).T,
        shading="auto",
        cmap="rainbow",
        vmin=0.0,
        vmax=2.5,
        rasterized=True,
    )
    ax.plot(spectrum.x, spectrum.root, color="white", lw=1.45)
    ax.axhline(0.0, color="black", lw=0.7, ls="--", alpha=0.85)
    k_axis(ax, spectrum.x)
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
        fontsize=8.7,
        fontweight="bold",
    )
    return image


def colorbar_above(fig: plt.Figure, axes: list[plt.Axes], image) -> None:
    first, last = axes[0].get_position(), axes[-1].get_position()
    cax = fig.add_axes([first.x0, first.y1 + 0.016, last.x1 - first.x0, 0.018])
    cbar = fig.colorbar(image, cax=cax, orientation="horizontal")
    cbar.ax.xaxis.set_ticks_position("top")
    cbar.ax.xaxis.set_label_position("top")
    cbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=1, fontsize=10.0)
    cbar.ax.tick_params(labelsize=8.5, length=4.0, width=0.9, pad=1)


def zero_curve_axis(ax: plt.Axes, x: np.ndarray) -> None:
    ax.axhline(0.0, color="0.55", lw=0.55)
    k_axis(ax, x)
    ax.set_ylim(-7.1, 7.1)
    ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
    ax.grid(alpha=0.18)


def metric_row(metrics: pd.DataFrame, branch: str, interaction: int, tp: float) -> pd.Series:
    mask = (metrics.branch == branch) & np.isclose(metrics.tprime, tp)
    mask &= metrics.U == interaction if branch == "U-only" else metrics.V == interaction
    rows = metrics[mask]
    if len(rows) != 1:
        raise ValueError(f"Expected one metrics row for {branch}, {interaction}, {tp}")
    return rows.iloc[0]


def save(fig: plt.Figure, stem: str) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=260, bbox_inches="tight")
    plt.close(fig)
    if pdf.read_bytes()[:4] != b"%PDF" or png.stat().st_size == 0:
        raise RuntimeError(f"Invalid figure outputs for {stem}")
    return {"pdf": str(pdf.relative_to(ROOT)), "png": str(png.relative_to(ROOT))}


def build_axis_figure(
    branch: str,
    tp: float,
    spectra: dict[int, Spectrum],
    metrics: pd.DataFrame,
) -> dict[str, object]:
    values = U_VALUES if branch == "U-only" else V_VALUES
    ylims = U_YLIMS if branch == "U-only" else V_YLIMS
    interaction_colors = U_COLORS if branch == "U-only" else V_COLORS
    symbol = "U" if branch == "U-only" else "V"
    strongest = values[-1]
    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(7.15, 4.635))
        outer = fig.add_gridspec(1, 2, width_ratios=[2.0, 1.08], wspace=0.22)
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
        for index, (ax, value) in enumerate(zip(map_axes, values)):
            image = spectral_map(
                ax,
                spectra[value],
                ylim=ylims[value],
                text=rf"${symbol}={value}$",
                show_ylabel=index % 2 == 0,
            )
            panel_label(ax, f"({chr(97 + index)})")
        if image is None:
            raise RuntimeError("No spectral maps rendered")
        colorbar_above(fig, map_axes, image)

        reference = spectra[strongest]
        epsilon1, epsilon2 = harmonics(reference.k_path, tp)
        for value in values:
            curve_ax.plot(
                spectra[value].x,
                spectra[value].root,
                color=interaction_colors[value],
                label=rf"${symbol}={value}$",
            )
        strongest_metrics = metric_row(metrics, branch, strongest, tp)
        prediction = (
            -float(strongest_metrics.s_nn) * epsilon1
            + float(strongest_metrics.s_nnn) * epsilon2
            + float(strongest_metrics.offset_delta)
        )
        curve_ax.plot(
            reference.x,
            prediction,
            color="black",
            ls="--",
            lw=1.1,
            label="NN+NNN fit",
        )
        zero_curve_axis(curve_ax, reference.x)
        curve_ax.yaxis.set_label_coords(-0.10, 0.5)
        curve_ax.set_title(rf"$t'={tp:g}t$", pad=2, fontsize=10.0)
        handles, labels = curve_ax.get_legend_handles_labels()
        order = [0, 2, 4, 1, 3]
        curve_ax.legend(
            [handles[i] for i in order],
            [labels[i] for i in order],
            frameon=False,
            ncol=2,
            loc="upper center",
            bbox_to_anchor=(0.52, 0.95),
            fontsize=8.0,
            handlelength=1.20,
            columnspacing=0.65,
            labelspacing=0.08,
            borderaxespad=0.10,
        )
        panel_label(curve_ax, "(e)", x=-0.075)

        rows = pd.DataFrame(
            [metric_row(metrics, branch, value, tp) for value in values]
        ).sort_values(symbol)
        coupling = rows[symbol].to_numpy(dtype=float)
        x_inverse = 1.0 / coupling
        scale_ax.errorbar(
            x_inverse,
            rows.s_nn,
            yerr=rows.s_nn_se,
            marker="o",
            color=COEFFICIENT_COLORS["s_nn"],
            markerfacecolor="white",
            markeredgewidth=1.35,
            capsize=2.0,
            label=r"$s_{\rm NN}$",
        )
        scale_ax.errorbar(
            x_inverse,
            rows.s_nnn,
            yerr=rows.s_nnn_se,
            marker="s",
            color=COEFFICIENT_COLORS["s_nnn"],
            markerfacecolor="white",
            markeredgewidth=1.35,
            capsize=2.0,
            label=r"$s_{\rm NNN}$",
        )
        expected_nn = float(rows.expected_s_nn.iloc[0])
        expected_nnn = float(rows.expected_s_nnn.iloc[0])
        scale_ax.axhline(
            expected_nn,
            color=COEFFICIENT_COLORS["s_nn"],
            ls="--",
            lw=1.15,
            label=r"NN prediction",
        )
        scale_ax.axhline(
            expected_nnn,
            color=COEFFICIENT_COLORS["s_nnn"],
            ls=":",
            lw=1.35,
            label=r"NNN prediction",
        )
        scale_ax.set_xlabel(rf"$t/{symbol}$")
        scale_ax.set_ylabel("bond coefficient")
        scale_ax.yaxis.set_label_coords(-0.19, 0.5)
        if branch == "U-only":
            scale_ax.set_xlim(-0.004, 0.132)
            scale_ax.set_ylim(0.73, 1.46)
        else:
            scale_ax.set_xlim(-0.01, 0.52)
            scale_ax.set_ylim(0.975, 1.165)
        scale_ax.grid(alpha=0.18)
        scale_ax.legend(
            frameon=False,
            ncol=2,
            loc="best",
            fontsize=7.2,
            handlelength=1.20,
            columnspacing=0.55,
            labelspacing=0.10,
            borderaxespad=0.20,
        )
        panel_label(scale_ax, "(f)", x=-0.075)

        base = "fig2_mott_zero_mechanism" if branch == "U-only" else "fig3_cdw_zero_mechanism"
        output = save(fig, f"{base}_tp{tp_stem(tp)}")
    return {
        "branch": branch,
        "tprime": tp,
        "strongest_interaction": strongest,
        "strongest_fit": {
            "s_nn": float(strongest_metrics.s_nn),
            "s_nnn": float(strongest_metrics.s_nnn),
            "offset_delta": float(strongest_metrics.offset_delta),
            "rmse": float(strongest_metrics.bond_rmse),
        },
        "expected_s_nn": expected_nn,
        "expected_s_nnn": expected_nnn,
        **output,
    }


def main() -> None:
    if not METRICS_SOURCE.is_file():
        raise FileNotFoundError(METRICS_SOURCE)
    metrics = pd.read_csv(METRICS_SOURCE)
    if len(metrics) != 16 or metrics.duplicated(["U", "V", "tprime"]).any():
        raise ValueError("Finite-tprime metrics table must contain 16 unique groups")
    if not (
        (metrics.root_count_unique == 120).all()
        and (metrics.root_count_plotted == 121).all()
        and (metrics.clean_root_count_plotted == 121).all()
    ):
        raise ValueError("Metrics contain incomplete or non-clean root groups")

    spectra: dict[tuple[str, float, int], Spectrum] = {}
    for tp in TP_VALUES:
        for U in U_VALUES:
            spectra[("U-only", tp, U)] = load_spectrum("U-only", U, tp)
        for V in V_VALUES:
            spectra[("V-only", tp, V)] = load_spectrum("V-only", V, tp)

    outputs = []
    for tp in TP_VALUES:
        outputs.append(
            build_axis_figure(
                "U-only",
                tp,
                {U: spectra[("U-only", tp, U)] for U in U_VALUES},
                metrics,
            )
        )
        outputs.append(
            build_axis_figure(
                "V-only",
                tp,
                {V: spectra[("V-only", tp, V)] for V in V_VALUES},
                metrics,
            )
        )

    metrics_output = metrics.copy()
    metrics_output.insert(
        0,
        "figure_variant",
        np.where(metrics_output.branch == "U-only", "Fig2", "Fig3"),
    )
    metrics_output.to_csv(METRICS_OUT, index=False)

    manifest = {
        "date_tag": DATE_TAG,
        "eta": 0.05,
        "description": "Finite-tprime analogues of current PRL Figures 2 and 3",
        "model": "omega_GZ=delta-s_NN*epsilon1+s_NNN*epsilon2",
        "source_metrics": str(METRICS_SOURCE.relative_to(ROOT)),
        "output_metrics": str(METRICS_OUT.relative_to(ROOT)),
        "source_data_dir": str(DATA_DIR.relative_to(ROOT)),
        "figures": outputs,
        "validation": {
            "figure_count": len(outputs),
            "source_group_count": len(spectra),
            "all_sources_have_121_roots": all(
                np.isfinite(record.root).sum() == 121 for record in spectra.values()
            ),
            "all_pdf_headers_valid": all(
                (ROOT / item["pdf"]).read_bytes()[:4] == b"%PDF" for item in outputs
            ),
            "all_pngs_nonempty": all(
                (ROOT / item["png"]).stat().st_size > 0 for item in outputs
            ),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
