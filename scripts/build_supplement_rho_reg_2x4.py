#!/usr/bin/env python3
"""Build the complete Mott- and CDW-axis spectral/ReG supplements.

Each output is a 2 x 4 panel figure.  The upper row reproduces the four
eta=0.05 spectral maps used in the former full supplemental figures.  The
lower row displays the corresponding physical real part of the Green
function on the same momentum/frequency window.  The stored ``reG`` arrays
follow the legacy ``-2 Re G`` plotting convention, so they are multiplied by
``-1/2`` before display.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
import numpy as np

import build_prl_split_axis_figures as base


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures/supplement_reg_2x4"
MANUSCRIPT_OUT = ROOT / "manuscript/supp_figures"

MOTT_STEM = "supp_fig_mott_zero_mechanism_full"
CDW_STEM = "supp_fig_cdw_zero_mechanism_full"

# A common signed scale makes the Mott- and CDW-side ReG panels directly
# comparable while the symmetric-log central interval resolves the weak
# gap-interior sign change at the largest interaction strengths.
REG_VMAX = 6.0
REG_LINTHRESH = 0.01


def _parameter_panel_label(
    ax: plt.Axes,
    text: str,
    *,
    color: str = "white",
) -> None:
    ax.text(
        0.045,
        0.43,
        text,
        transform=ax.transAxes,
        color=color,
        ha="left",
        va="center",
        fontsize=9.0,
        fontweight="bold",
    )


def _format_k_axis(ax: plt.Axes) -> None:
    base._k_axis(ax)
    ax.tick_params(axis="both", which="major", pad=2.0)


def _spectral_panel(
    ax: plt.Axes,
    omega: np.ndarray,
    rho: np.ndarray,
    root: np.ndarray,
    *,
    ylim: float,
    parameter_text: str,
    vmax: float,
    show_ylabel: bool,
) -> plt.AxesImage:
    mask = np.abs(omega) <= ylim
    image = np.maximum(np.asarray(rho[:, mask], dtype=float), 0.0).T
    plotted = ax.imshow(
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
    ax.plot(np.arange(121), root, color="white", lw=1.35, zorder=4)
    ax.axhline(0.0, color="black", lw=0.65, ls="--", alpha=0.85, zorder=3)
    _format_k_axis(ax)
    ax.set_ylim(-ylim, ylim)
    if show_ylabel:
        ax.set_ylabel(r"$\omega/t$", labelpad=2.5)
    _parameter_panel_label(ax, parameter_text)
    return plotted


def _reg_panel(
    ax: plt.Axes,
    omega: np.ndarray,
    stored_reg: np.ndarray,
    root: np.ndarray,
    *,
    ylim: float,
    parameter_text: str,
    show_ylabel: bool,
) -> plt.AxesImage:
    mask = np.abs(omega) <= ylim
    # The analysis archive stores -2 Re G; display the physical Re G itself.
    reg = -0.5 * np.asarray(stored_reg[:, mask], dtype=float)
    plotted = ax.imshow(
        reg.T,
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
        extent=[0, 120, float(omega[mask][0]), float(omega[mask][-1])],
        cmap="RdBu_r",
        norm=SymLogNorm(
            linthresh=REG_LINTHRESH,
            linscale=0.82,
            vmin=-REG_VMAX,
            vmax=REG_VMAX,
            base=10,
        ),
        rasterized=True,
    )
    # A black overlay identifies the particular central-gap sign change that
    # is tracked as the GZ dispersion among all ReG=0 contours near poles.
    ax.plot(np.arange(121), root, color="black", lw=1.10, zorder=4)
    ax.axhline(0.0, color="0.15", lw=0.62, ls="--", alpha=0.82, zorder=3)
    _format_k_axis(ax)
    ax.set_ylim(-ylim, ylim)
    if show_ylabel:
        ax.set_ylabel(r"$\omega/t$", labelpad=2.5)
    _parameter_panel_label(ax, parameter_text, color="black")
    return plotted


def _horizontal_colorbar(
    fig: plt.Figure,
    axes: list[plt.Axes],
    image: plt.AxesImage,
    *,
    label: str,
    y_offset: float,
    signed: bool = False,
) -> None:
    first = axes[0].get_position()
    last = axes[-1].get_position()
    cax = fig.add_axes(
        [first.x0, first.y1 + y_offset, last.x1 - first.x0, 0.014]
    )
    colorbar = fig.colorbar(image, cax=cax, orientation="horizontal")
    colorbar.ax.xaxis.set_ticks_position("top")
    colorbar.ax.xaxis.set_label_position("top")
    colorbar.set_label(label, labelpad=0.5, fontsize=10.0)
    if signed:
        colorbar.set_ticks([-6, -1, -0.1, -0.01, 0, 0.01, 0.1, 1, 6])
        colorbar.set_ticklabels(
            [r"$-6$", r"$-1$", r"$-10^{-1}$", r"$-10^{-2}$", "0",
             r"$10^{-2}$", r"$10^{-1}$", "1", "6"]
        )
    colorbar.ax.tick_params(labelsize=8.2, length=3.6, width=0.85, pad=1)


def _figure_axes() -> tuple[plt.Figure, np.ndarray]:
    fig, axes = plt.subplots(2, 4, figsize=(7.70, 5.00), squeeze=False)
    fig.subplots_adjust(
        left=0.068,
        right=0.994,
        bottom=0.070,
        top=0.895,
        # Leave enough horizontal clearance for every outside panel label;
        # none of (b-d) or (f-h) should touch the preceding panel frame.
        wspace=0.400,
        hspace=0.485,
    )
    return fig, axes


def _decorate_panel_labels(axes: np.ndarray) -> None:
    for index, ax in enumerate(axes.flat):
        column = index % 4
        base._panel_label(
            ax,
            f"({chr(ord('a') + index)})",
            x=-0.195 if column == 0 else -0.180,
            y=0.985,
            fontsize=10.2,
        )


def _save(fig: plt.Figure, stem: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    manuscript_pdf = MANUSCRIPT_OUT / f"{stem}.pdf"
    shutil.copy2(pdf, manuscript_pdf)
    return manuscript_pdf


def build_mott() -> Path:
    source = np.load(base.U_SOURCE)
    u_values = [int(value) for value in source["U"]]
    fig, axes = _figure_axes()
    spectral_image = None
    reg_image = None
    for column, value in enumerate(base.U_MAP_VALUES):
        index = u_values.index(value)
        omega = np.asarray(source["omega"], dtype=float)
        root = np.asarray(source["omega_root"][index], dtype=float)
        spectral_image = _spectral_panel(
            axes[0, column],
            omega,
            np.asarray(source["rho_G"][index], dtype=float),
            root,
            ylim=base.U_YLIMS[value],
            parameter_text=rf"$U={value}$",
            vmax=1.5,
            show_ylabel=column == 0,
        )
        reg_image = _reg_panel(
            axes[1, column],
            omega,
            np.asarray(source["reG"][index], dtype=float),
            root,
            ylim=base.U_YLIMS[value],
            parameter_text=rf"$U={value}$",
            show_ylabel=column == 0,
        )
    _decorate_panel_labels(axes)
    assert spectral_image is not None and reg_image is not None
    _horizontal_colorbar(
        fig,
        list(axes[0]),
        spectral_image,
        label=r"$\rho_G(\mathbf{k},\omega)$",
        y_offset=0.014,
    )
    _horizontal_colorbar(
        fig,
        list(axes[1]),
        reg_image,
        label=r"$\mathrm{Re}\,G(\mathbf{k},\omega)$",
        y_offset=0.014,
        signed=True,
    )
    return _save(fig, MOTT_STEM)


def build_cdw() -> Path:
    records = {}
    for value in base.V_MAP_VALUES:
        path = (
            base.V_DIRECTORY
            / f"rhoG_LS_U0_V{value}_tp0_eta0p05_spectra_and_roots.npz"
        )
        records[value] = np.load(path)
    fig, axes = _figure_axes()
    spectral_image = None
    reg_image = None
    for column, value in enumerate(base.V_MAP_VALUES):
        source = records[value]
        omega = np.asarray(source["omega"], dtype=float)
        root = np.asarray(source["omega_root"], dtype=float)
        ylim = float(source["ylim"])
        spectral_image = _spectral_panel(
            axes[0, column],
            omega,
            np.asarray(source["rho_G"], dtype=float),
            root,
            ylim=ylim,
            parameter_text=rf"$V={value}$",
            vmax=2.5,
            show_ylabel=column == 0,
        )
        reg_image = _reg_panel(
            axes[1, column],
            omega,
            np.asarray(source["reG"], dtype=float),
            root,
            ylim=ylim,
            parameter_text=rf"$V={value}$",
            show_ylabel=column == 0,
        )
    _decorate_panel_labels(axes)
    assert spectral_image is not None and reg_image is not None
    _horizontal_colorbar(
        fig,
        list(axes[0]),
        spectral_image,
        label=r"$\rho_G(\mathbf{k},\omega)$",
        y_offset=0.014,
    )
    _horizontal_colorbar(
        fig,
        list(axes[1]),
        reg_image,
        label=r"$\mathrm{Re}\,G(\mathbf{k},\omega)$",
        y_offset=0.014,
        signed=True,
    )
    return _save(fig, CDW_STEM)


def main() -> None:
    with plt.rc_context(base.STYLE):
        mott = build_mott()
        cdw = build_cdw()
    print(mott)
    print(cdw)


if __name__ == "__main__":
    main()
