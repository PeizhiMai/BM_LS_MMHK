#!/usr/bin/env python3
"""Analyze the U=40 all-twist full-observable scan.

The input is a frozen CADES download snapshot containing one COMPLETE
``*_obs.dat`` file per available (V,kx,ky) row and a SHA-256 manifest.
The script validates the download, parses every measured quantity, performs
symmetry/trapezoidal momentum averaging, tests exact output identities, and
generates machine-readable summaries plus publication-quality figures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

from manuscript_figure_style import outside_panel_label


VS = [0, 4, 8, 9, 10, 10.01, 10.02, 10.1, 10.2, 10.4, 11, 12, 16, 20]
# Keep the dense two-dimensional map figures compact; the added boundary
# refinements enter all scalar/transition plots and machine-readable tables.
MAP_VS = [0, 4, 8, 9, 10, 11, 12, 16, 20]
# The V/U=1/4 point is intentionally omitted from phase-labelled n(k) maps:
# it sits at the atomic crossing and should not be assigned to either row.
NK_MOTT_VS = [0, 4, 8, 9]
NK_CHARGE_VS = [11, 12, 16, 20]
NK_DISPLAY_VS = NK_MOTT_VS + NK_CHARGE_VS
U_FIXED = 40.0
NSITES = 16.0
GRID_MAX = 40
EXPECTED_WEDGE_ROWS = 861
EXPECTED_QUADRATURE_WEIGHT = 1600.0

FILENAME_RE = re.compile(
    r"L(?P<Lx>\d+)x(?P<Ly>\d+)Nup(?P<Nup>\d+)Ndn(?P<Ndn>\d+)"
    r"U(?P<U>[-+0-9.eE]+)V(?P<V>[-+0-9.eE]+)tp(?P<tp>[-+0-9.eE]+)"
    r"f(?P<kx>\d+)x(?P<ky>\d+)Q(?P<Qm>\d+)x(?P<Qn>\d+)_obs\.dat"
)

RAW_TO_COLUMN = {
    "<nn_NN>": "nn_NN",
    "<delta_n_delta_n_NN>": "delta_n_delta_n_NN",
    "<Kinetic_NN_per_site>": "kinetic_NN_per_site",
    "<Kinetic_NNN_per_site>": "kinetic_NNN_per_site",
    "<Kinetic_per_site>": "kinetic_per_site",
    "<C1_NN>": "C1_NN",
    "<nq>": "n_k",
    "<nq_upnq_dn>": "D_k",
    "<ni_upni_dn>": "D_site",
    "<Spipi>": "Szz_pipi",
    "<Sc_pipi>": "Sc_pipi",
    "<mCDW2_pipi>": "mCDW2_pipi",
}

MEASURED_COLUMNS = [
    "E0",
    "Gap",
    "nn_NN",
    "delta_n_delta_n_NN",
    "kinetic_NN_per_site",
    "kinetic_NNN_per_site",
    "kinetic_per_site",
    "C1_NN",
    "n_k",
    "D_k",
    "D_site",
    "Szz_pipi",
    "Sc_pipi",
    "mCDW2_pipi",
]

ANALYSIS_COLUMNS = [
    "E0_per_site",
    "nn_NN",
    "delta_n_delta_n_NN",
    "kinetic_NN_per_site",
    "kinetic_NNN_per_site",
    "kinetic_per_site",
    "C1_NN",
    "n_k",
    "D_k",
    "D_site",
    "Szz_pipi",
    "Sc_pipi",
    "mCDW2_pipi",
    "var_n_k",
    "cov_nup_ndn_k",
]

DISPLAY = {
    "E0_per_site": r"$E_0/N$",
    "nn_NN": r"$\langle n_i n_j\rangle_{\rm NN}$",
    "delta_n_delta_n_NN": r"$\langle\delta n_i\delta n_j\rangle_{\rm NN}$",
    "kinetic_NN_per_site": r"$K_{\rm NN}/N$",
    "kinetic_NNN_per_site": r"$K_{\rm NNN}/N$",
    "kinetic_per_site": r"$K/N$",
    "C1_NN": r"$C_{\mathrm{NN}}=\langle\mathbf{S}_i\cdot\mathbf{S}_j\rangle_{\mathrm{NN}}$",
    "n_k": r"$n(\mathbf{k})$",
    "D_k": r"$\langle n_{\mathbf{k}\uparrow}n_{\mathbf{k}\downarrow}\rangle$",
    "D_site": r"$\langle n_{i\uparrow}n_{i\downarrow}\rangle$",
    "Szz_pipi": r"$S^{zz}(\pi,\pi)$",
    "Sc_pipi": r"$S_c(\pi,\pi)$",
    "mCDW2_pipi": r"$m_{\rm CDW}^2=S_c/N$",
    "var_n_k": r"$\mathrm{Var}(n_{\mathbf{k}})$",
    "cov_nup_ndn_k": r"$\mathrm{Cov}(n_{\mathbf{k}\uparrow},n_{\mathbf{k}\downarrow})$",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_scalar(value: str):
    try:
        return float(value)
    except ValueError:
        return value.strip()


def parse_file(path: Path) -> dict:
    match = FILENAME_RE.fullmatch(path.name)
    if not match:
        raise ValueError(f"Unexpected fullobs filename: {path.name}")
    row = {}
    for key, value in match.groupdict().items():
        if key in {"U", "V", "tp"}:
            row[f"filename_{key}"] = float(value)
        else:
            row[f"filename_{key}"] = int(value)

    for line in path.read_text(errors="replace").splitlines():
        fields = line.split(None, 1)
        if len(fields) != 2:
            continue
        key, value = fields
        key = RAW_TO_COLUMN.get(key, key)
        row[key] = parse_scalar(value)
    row["filename"] = path.name
    row["size_bytes"] = path.stat().st_size
    return row


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(weights * values) / np.sum(weights))


def weighted_std(values: Iterable[float], weights: Iterable[float]) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mean = weighted_mean(values, weights)
    return float(np.sqrt(np.sum(weights * (values - mean) ** 2) / np.sum(weights)))


def weighted_quantile(values, weights, quantiles):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    quantiles = np.asarray(quantiles, dtype=float)
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights) - 0.5 * weights
    cumulative /= np.sum(weights)
    return np.interp(quantiles, cumulative, values)


def add_region_guides(ax):
    ax.axvspan(0.0, 0.25, color="#dce8f2", alpha=0.42, zorder=-10)
    ax.axvspan(0.25, 0.52, color="#f4e2cf", alpha=0.42, zorder=-10)
    ax.axvline(0.25, color="0.25", lw=1.0, ls="--", zorder=-5)
    ax.set_xlim(-0.01, 0.51)
    ax.set_xlabel(r"$V/U$")
    ax.grid(alpha=0.18, lw=0.6)


def save_figure(fig, output_base: Path):
    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.16)
    fig.savefig(output_base.with_suffix(".png"), dpi=240, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)


def full_map(group: pd.DataFrame, column: str) -> np.ndarray:
    array = np.full((GRID_MAX + 1, GRID_MAX + 1), np.nan)
    for row in group.itertuples(index=False):
        kx, ky = int(row.kx), int(row.ky)
        value = float(getattr(row, column))
        array[ky, kx] = value
        array[kx, ky] = value
    return array


def style_axes(axes):
    for ax in np.ravel(axes):
        ax.tick_params(direction="out", length=3, width=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)


def make_static_scan_figure(summary: pd.DataFrame, outdir: Path):
    x = summary["V_over_U"].to_numpy()
    colors = {"blue": "#335f8d", "orange": "#c56f2d", "green": "#4b7f52", "purple": "#7a5c91"}
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 6.4), constrained_layout=True)
    ax = axes[0, 0]
    ax.plot(x, summary["D_site_mean"], "o-", color=colors["blue"], label=r"$D_i$")
    ax.plot(x, summary["mCDW2_pipi_mean"], "s-", color=colors["orange"], label=r"$m_{\rm CDW}^2$")
    ax.plot(x, summary["nn_NN_mean"], "^-", color=colors["green"], label=r"$\langle n_i n_j\rangle_{\rm NN}$")
    ax.set_ylabel("charge observables")
    ax.set_ylim(-0.03, 1.05)
    ax.legend(frameon=False, fontsize=8, loc="center left")
    add_region_guides(ax)

    ax = axes[0, 1]
    ax.plot(
        x,
        -summary["C1_NN_mean"],
        "o-",
        color=colors["blue"],
        label=r"$-C_{\mathrm{NN}}$",
    )
    ax.plot(x, summary["Szz_pipi_mean"], "s-", color=colors["purple"], label=r"$S^{zz}(\pi,\pi)$")
    ax.set_ylabel("spin correlations")
    ax.set_ylim(-0.03, 1.55)
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    ax = axes[1, 0]
    ax.plot(x, -summary["kinetic_per_site_mean"], "o-", color=colors["blue"], label=r"$-K/N$")
    ax.plot(x, summary["n_k_std"], "s-", color=colors["orange"], label=r"$\sigma_{\mathbf{k}}[n]$")
    ax.plot(x, summary["n_k_band_contrast"] / 4.0, "^-", color=colors["green"], label=r"$[n(0)-n(\pi,\pi)]/4$")
    ax.set_ylabel("one-body response")
    ax.set_ylim(0.0, 0.34)
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    ax = axes[1, 1]
    ax.plot(x, summary["D_k_mean"], "o-", color=colors["blue"], label=r"$D_{\mathbf{k}}$")
    ax.plot(x, summary["var_n_k_mean"], "s-", color=colors["orange"], label=r"$\langle\mathrm{Var}(n_{\mathbf{k}})\rangle_{\mathbf{k}}$")
    ax.plot(x, summary["cov_nup_ndn_k_mean"], "^-", color=colors["purple"], label=r"$\langle\mathrm{Cov}_{\uparrow\downarrow}\rangle_{\mathbf{k}}$")
    ax.set_ylabel("momentum-orbital fluctuations")
    ax.set_ylim(-0.02, 0.60)
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    for label, ax in zip("abcd", axes.ravel()):
        outside_panel_label(ax, f"({label})", fontsize=11.5)
    style_axes(axes)
    save_figure(fig, outdir / "fullobs_static_scan_U40")


def make_strong_coupling_figure(summary: pd.DataFrame, outdir: Path):
    x = summary["V_over_U"].to_numpy()
    mott = summary[summary["branch"] == "Mott"]
    charge = summary[summary["branch"] == "charge"]
    blue, orange, ink = "#335f8d", "#c56f2d", "#222222"
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 6.4), constrained_layout=True)

    ax = axes[0, 0]
    ax.plot(x, summary["E0_per_site_mean"], "o", color=ink, label="measured")
    grid = np.linspace(0, 0.5, 300)
    ax.plot(grid, np.minimum(2 * U_FIXED * grid, U_FIXED / 2), ls=":", color="0.45", label="atomic envelope")
    ax.plot(mott["V_over_U"], mott["E0_per_site_pred"], "-", color=blue, label=r"Mott $\Delta_M=U-V$")
    ax.plot(charge["V_over_U"], charge["E0_per_site_pred"], "-", color=orange, label=r"CDW $\Delta_C=7V-U$")
    ax.set_ylabel(r"$E_0/N$")
    ax.legend(frameon=False, fontsize=7.8, loc="lower right")
    add_region_guides(ax)

    ax = axes[0, 1]
    ax.plot(x, -summary["n_epsilon_slope"], "o", color=ink, label="measured")
    ax.plot(mott["V_over_U"], -mott["n_epsilon_slope_pred"], "-", color=blue, label="Mott rule")
    ax.plot(charge["V_over_U"], -charge["n_epsilon_slope_pred"], "-", color=orange, label="CDW rule")
    ax.set_ylabel(r"$-a$ in $n(\mathbf{k})=1+a\varepsilon_{\mathbf{k}}$")
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    ax = axes[1, 0]
    ax.plot(x, -summary["kinetic_per_site_mean"], "o", color=ink, label="measured")
    ax.plot(mott["V_over_U"], -mott["kinetic_per_site_pred"], "-", color=blue, label="Mott rule")
    ax.plot(charge["V_over_U"], -charge["kinetic_per_site_pred"], "-", color=orange, label="CDW rule")
    ax.set_ylabel(r"$-K/N$")
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    ax = axes[1, 1]
    ax.plot(x, summary["D_site_mean"], "o", color=blue, label=r"$D_i$ measured")
    ax.plot(x, summary["nn_NN_mean"], "s", color=orange, label=r"$\langle n_i n_j\rangle$ measured")
    ax.plot(mott["V_over_U"], mott["D_site_pred"], "-", color=blue)
    ax.plot(charge["V_over_U"], charge["D_site_pred"], "-", color=blue)
    ax.plot(mott["V_over_U"], mott["nn_NN_pred"], "-", color=orange)
    ax.plot(charge["V_over_U"], charge["nn_NN_pred"], "-", color=orange)
    ax.set_ylabel("local charge probabilities")
    ax.set_ylim(-0.03, 1.05)
    ax.legend(frameon=False, fontsize=7.8, loc="center left")
    add_region_guides(ax)

    for label, ax in zip("abcd", axes.ravel()):
        outside_panel_label(ax, f"({label})", fontsize=11.5)
    style_axes(axes)
    save_figure(fig, outdir / "fullobs_strong_coupling_validation_U40")


def make_map_figure(df: pd.DataFrame, column: str, outdir: Path, cmap_name: str, center=None):
    maps = [full_map(df[df["V"] == V], column) for V in MAP_VS]
    finite = np.concatenate([array[np.isfinite(array)] for array in maps])
    if center is None:
        vmin, vmax = float(np.min(finite)), float(np.max(finite))
        norm = None
    else:
        radius = max(abs(float(np.min(finite)) - center), abs(float(np.max(finite)) - center))
        vmin, vmax = center - radius, center + radius
        norm = TwoSlopeNorm(vmin=vmin, vcenter=center, vmax=vmax)
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad("#d9d9d9")
    fig, axes = plt.subplots(3, 3, figsize=(8.2, 7.3), constrained_layout=True)
    im = None
    for ax, V, array in zip(axes.ravel(), MAP_VS, maps):
        im = ax.imshow(
            array,
            origin="lower",
            extent=(0, 1, 0, 1),
            interpolation="nearest",
            aspect="equal",
            cmap=cmap,
            vmin=None if norm else vmin,
            vmax=None if norm else vmax,
            norm=norm,
            rasterized=True,
        )
        ax.set_title(rf"$V/U={V / U_FIXED:.3g}$", fontsize=9)
        ax.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        ax.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        ax.set_xlabel(r"$k_x$")
        ax.set_ylabel(r"$k_y$")
        ax.tick_params(labelsize=7, length=2)
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.82, pad=0.02)
    cbar.set_label(DISPLAY[column])
    safe = {"n_k": "nk", "D_k": "Dk", "var_n_k": "varnk"}[column]
    save_figure(fig, outdir / f"fullobs_{safe}_maps_U40")


def ratio_filename(value: float) -> str:
    """Return a stable, filesystem-safe interaction-ratio tag."""
    return f"{value:.3f}".replace(".", "p")


def noninteracting_nk_map(points: int = GRID_MAX + 1) -> np.ndarray:
    """Zero-temperature, half-filled spin-summed square-lattice n_0(k)."""
    k = np.linspace(0.0, np.pi, points)
    kx, ky = np.meshgrid(k, k, indexing="xy")
    epsilon = -2.0 * (np.cos(kx) + np.cos(ky))
    # The value on the Fermi line is set to one, the particle-hole-symmetric
    # convention for a zero-temperature step sampled exactly at epsilon=0.
    return np.where(epsilon < -1.0e-12, 2.0, np.where(epsilon > 1.0e-12, 0.0, 1.0))


def make_grouped_nk_figure(df: pd.DataFrame, summary: pd.DataFrame, outdir: Path):
    """Show Mott and CDW n(k) maps, a free reference, and n_Gamma(V/U)."""
    maps = {V: full_map(df[df["V"] == V], "n_k") for V in NK_DISPLAY_VS}
    finite = np.concatenate([array[np.isfinite(array)] for array in maps.values()])
    radius = max(abs(float(np.min(finite)) - 1.0), abs(float(np.max(finite)) - 1.0))
    interacting_norm = TwoSlopeNorm(vmin=1.0 - radius, vcenter=1.0, vmax=1.0 + radius)
    free_norm = TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=2.0)
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#d9d9d9")

    fig = plt.figure(figsize=(11.1, 8.35), constrained_layout=True)
    grid = fig.add_gridspec(3, 4, height_ratios=[1.0, 1.0, 1.08])
    map_axes = []
    interacting_image = None
    for row_index, values in enumerate([NK_MOTT_VS, NK_CHARGE_VS]):
        for column_index, V in enumerate(values):
            ax = fig.add_subplot(grid[row_index, column_index])
            map_axes.append(ax)
            interacting_image = ax.imshow(
                maps[V],
                origin="lower",
                extent=(0, 1, 0, 1),
                interpolation="nearest",
                aspect="equal",
                cmap=cmap,
                norm=interacting_norm,
                rasterized=True,
            )
            ax.set_title(rf"$V/U={V/U_FIXED:.3g}$", fontsize=9.5)
            ax.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
            ax.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
            ax.set_xlabel(r"$k_x$")
            if column_index == 0:
                ax.set_ylabel(r"$k_y$")
            else:
                ax.tick_params(labelleft=False)
            ax.tick_params(labelsize=7.5, length=2)

    map_axes[0].text(
        -0.34,
        0.5,
        "Mott insulator",
        transform=map_axes[0].transAxes,
        rotation=90,
        va="center",
        ha="center",
        fontweight="bold",
        fontsize=9.5,
    )
    map_axes[4].text(
        -0.34,
        0.5,
        "CDW insulator",
        transform=map_axes[4].transAxes,
        rotation=90,
        va="center",
        ha="center",
        fontweight="bold",
        fontsize=9.5,
    )
    cbar = fig.colorbar(interacting_image, ax=map_axes, shrink=0.84, pad=0.012)
    cbar.set_label(r"interacting $n(\mathbf{k})$")

    # Third row: a free-electron benchmark with its physically distinct 0--2
    # color scale, followed by the measured Gamma-point evolution.
    ax_free = fig.add_subplot(grid[2, 0])
    free_image = ax_free.imshow(
        noninteracting_nk_map(points=1001),
        origin="lower",
        extent=(0, 1, 0, 1),
        interpolation="nearest",
        aspect="equal",
        cmap=cmap,
        norm=free_norm,
        rasterized=True,
    )
    ax_free.set_title(r"Noninteracting $U=V=0$", fontsize=9.5)
    ax_free.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
    ax_free.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
    ax_free.set_xlabel(r"$k_x$")
    ax_free.set_ylabel(r"$k_y$")
    ax_free.tick_params(labelsize=7.5, length=2)
    free_cbar = fig.colorbar(free_image, ax=ax_free, shrink=0.78, pad=0.035, ticks=[0, 1, 2])
    free_cbar.set_label(r"$n_0(\mathbf{k})$")

    ax_gamma = fig.add_subplot(grid[2, 1:])
    shown = summary[summary["V"].isin(NK_DISPLAY_VS)].copy()
    mott = shown[shown["V"].isin(NK_MOTT_VS)]
    charge = shown[shown["V"].isin(NK_CHARGE_VS)]
    ax_gamma.plot(
        mott["V_over_U"], mott["n_k_gamma"], "o-", color="#335f8d", label="Mott insulator"
    )
    ax_gamma.plot(
        charge["V_over_U"], charge["n_k_gamma"], "s-", color="#c56f2d", label="CDW insulator"
    )
    ax_gamma.axvline(0.25, color="0.25", lw=1.0, ls="--")
    ax_gamma.axhline(1.0, color="0.55", lw=0.9, ls=":")
    ax_gamma.text(0.252, 1.338, r"$V/U=1/4$", va="top", ha="left", fontsize=8)
    ax_gamma.text(
        0.99,
        0.08,
        r"noninteracting: $n_0(\Gamma)=2$ (off scale)",
        transform=ax_gamma.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="0.30",
    )
    ax_gamma.set_xlim(-0.01, 0.51)
    ax_gamma.set_ylim(1.045, 1.345)
    ax_gamma.set_xlabel(r"$V/U$")
    ax_gamma.set_ylabel(r"$n_{\Gamma}=n(0,0)$")
    ax_gamma.set_title(r"Interaction-driven momentum redistribution", fontsize=9.5)
    ax_gamma.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    ax_gamma.grid(alpha=0.18, lw=0.6)
    style_axes([ax_gamma])

    save_figure(fig, outdir / "fullobs_nk_maps_U40")

    # Also export the reference and Gamma trend as standalone assets.
    fig_ref, ax_ref = plt.subplots(figsize=(4.45, 3.95), constrained_layout=True)
    im_ref = ax_ref.imshow(
        noninteracting_nk_map(points=1001),
        origin="lower",
        extent=(0, 1, 0, 1),
        interpolation="nearest",
        aspect="equal",
        cmap=cmap,
        norm=free_norm,
        rasterized=True,
    )
    ax_ref.set_title(r"Noninteracting $n_0(\mathbf{k})$ at half filling")
    ax_ref.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
    ax_ref.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
    ax_ref.set_xlabel(r"$k_x$")
    ax_ref.set_ylabel(r"$k_y$")
    fig_ref.colorbar(im_ref, ax=ax_ref, shrink=0.85, pad=0.035, ticks=[0, 1, 2], label=r"$n_0(\mathbf{k})$")
    save_figure(fig_ref, outdir / "fullobs_nk_noninteracting_reference")

    gamma_columns = ["U", "V", "V_over_U", "n_k_gamma", "n_k_M", "n_k_band_contrast"]
    summary[gamma_columns].to_csv(outdir / "fullobs_nk_gamma_vs_VU_U40.csv", index=False)


def make_individual_nk_figures(df: pd.DataFrame, outdir: Path) -> pd.DataFrame:
    """Export one consistently scaled two-dimensional n(k) map per V/U.

    All panels use the same color normalization, so colors can be compared
    directly across files.  The upper-triangular input wedge is reflected
    under kx <-> ky by :func:`full_map`; unavailable input rows remain gray.
    """
    target = outdir / "nk_individual"
    target.mkdir(parents=True, exist_ok=True)

    maps = {V: full_map(df[df["V"] == V], "n_k") for V in NK_DISPLAY_VS}
    finite = np.concatenate([array[np.isfinite(array)] for array in maps.values()])
    radius = max(abs(float(np.min(finite)) - 1.0), abs(float(np.max(finite)) - 1.0))
    vmin, vmax = 1.0 - radius, 1.0 + radius
    norm = TwoSlopeNorm(vmin=vmin, vcenter=1.0, vmax=vmax)
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#d9d9d9")

    index_rows = []
    # Remove the formerly indexed V/U=0.25 files so the exported list matches
    # the requested phase-separated selection.
    for suffix in ["png", "pdf"]:
        stale = target / f"fullobs_nk_U40_V10_ratio0p250.{suffix}"
        if stale.exists():
            stale.unlink()

    for V, array in maps.items():
        ratio = V / U_FIXED
        group = df[df["V"] == V]
        fig, ax = plt.subplots(figsize=(4.65, 4.05), constrained_layout=True)
        im = ax.imshow(
            array,
            origin="lower",
            extent=(0, 1, 0, 1),
            interpolation="nearest",
            aspect="equal",
            cmap=cmap,
            norm=norm,
            rasterized=True,
        )
        ax.set_title(
            rf"Momentum occupation $n(\mathbf{{k}})$"
            + "\n"
            + rf"$U={U_FIXED:g},\ V={V:g},\ V/U={ratio:.3g}$",
            fontsize=10,
        )
        ax.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        ax.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        ax.set_xlabel(r"$k_x$")
        ax.set_ylabel(r"$k_y$")
        ax.tick_params(direction="out", length=3, width=0.8)
        cbar = fig.colorbar(im, ax=ax, shrink=0.88, pad=0.035)
        cbar.set_label(r"$n(\mathbf{k})$")

        stem = f"fullobs_nk_U40_V{V:g}_ratio{ratio_filename(ratio)}"
        save_figure(fig, target / stem)
        observed_weight = float(group["quadrature_weight"].sum())
        index_rows.append(
            {
                "U": U_FIXED,
                "V": V,
                "V_over_U": ratio,
                "phase_row": "Mott insulator" if V in NK_MOTT_VS else "CDW insulator",
                "wedge_rows": int(len(group)),
                "wedge_completion_fraction": len(group) / EXPECTED_WEDGE_ROWS,
                "quadrature_completion_fraction": observed_weight / EXPECTED_QUADRATURE_WEIGHT,
                "color_vmin": vmin,
                "color_vcenter": 1.0,
                "color_vmax": vmax,
                "png": str((target / stem).with_suffix(".png").resolve()),
                "pdf": str((target / stem).with_suffix(".pdf").resolve()),
            }
        )

    index = pd.DataFrame(index_rows)
    index.to_csv(target / "nk_plot_index.csv", index=False)
    markdown = [
        "# U=40 two-dimensional n(k) maps",
        "",
        (
            "All maps share the same color scale "
            f"[{vmin:.6f}, {vmax:.6f}], centered at n(k)=1. "
            "Gray cells denote unavailable raw rows."
        ),
        "",
        "The V/U=0.25 map is omitted because it lies at the atomic crossing and is not assigned to either phase row.",
        "",
        "| phase row | V/U | V | wedge rows | quadrature completion | PNG | PDF |",
        "|:---|---:|---:|---:|---:|:---|:---|",
    ]
    for row in index.itertuples(index=False):
        png_name = Path(row.png).name
        pdf_name = Path(row.pdf).name
        markdown.append(
            f"| {row.phase_row} | {row.V_over_U:g} | {row.V:g} | {row.wedge_rows}/861 | "
            f"{100 * row.quadrature_completion_fraction:.3f}% | "
            f"[{png_name}]({png_name}) | [{pdf_name}]({pdf_name}) |"
        )
    markdown.extend(
        [
            "",
            "## Noninteracting reference",
            "",
            "- [PNG](../fullobs_nk_noninteracting_reference.png)",
            "- [PDF](../fullobs_nk_noninteracting_reference.pdf)",
        ]
    )
    (target / "README.md").write_text("\n".join(markdown) + "\n")
    return index


def make_n_epsilon_figure(df: pd.DataFrame, summary: pd.DataFrame, outdir: Path):
    fig, axes = plt.subplots(3, 3, figsize=(8.2, 7.3), sharex=True, sharey=True, constrained_layout=True)
    eps_grid = np.linspace(-4, 4, 200)
    for ax, V in zip(axes.ravel(), MAP_VS):
        group = df[df["V"] == V]
        row = summary[summary["V"] == V].iloc[0]
        ax.scatter(group["epsilon_k"], group["n_k"], s=4, alpha=0.28, color="#335f8d", edgecolors="none")
        ax.plot(eps_grid, 1 + row["n_epsilon_slope"] * eps_grid, color="#c56f2d", lw=1.4)
        ax.axhline(1, color="0.65", lw=0.6)
        ax.axvline(0, color="0.65", lw=0.6)
        ax.set_title(rf"$V/U={V/U_FIXED:.3g}$", fontsize=9)
        ax.text(
            0.04,
            0.08,
            rf"$a={row['n_epsilon_slope']:.4f}$" + "\n" + rf"$R^2={row['n_epsilon_R2']:.5f}$",
            transform=ax.transAxes,
            fontsize=7,
        )
        ax.grid(alpha=0.12, lw=0.5)
    for ax in axes[-1, :]:
        ax.set_xlabel(r"$\varepsilon_{\mathbf{k}}=-2(\cos k_x+\cos k_y)$")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$n(\mathbf{k})$")
    axes[0, 0].set_xlim(-4.15, 4.15)
    axes[0, 0].set_ylim(0.67, 1.33)
    style_axes(axes)
    save_figure(fig, outdir / "fullobs_nk_vs_epsilon_U40")


def make_transition_figure(summary: pd.DataFrame, outdir: Path):
    x = summary["V_over_U"].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.3), constrained_layout=True)
    ax = axes[0]
    ax.plot(x, summary["energy_dE_dV_numeric"], "o-", color="#222222", label=r"secant $\Delta(E/N)/\Delta V$")
    ax.plot(x, 2 * summary["nn_NN_mean"], "s-", color="#335f8d", label=r"Hellmann--Feynman $2\langle n_i n_j\rangle$")
    ax.set_ylabel(r"$\partial(E/N)/\partial V$")
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)

    ax = axes[1]
    fields = [
        ("mCDW2_pipi_mean", r"$m_{\rm CDW}^2$", "#c56f2d"),
        ("D_site_mean", r"$D_i$", "#335f8d"),
        ("Szz_pipi_mean", r"$S^{zz}(\pi,\pi)$", "#7a5c91"),
    ]
    for field, label, color in fields:
        ax.plot(x, summary[field], "o-", label=label, color=color)
    ax.set_yscale("log")
    ax.set_ylim(5e-4, 2.0)
    ax.set_ylabel("order diagnostics (log scale)")
    ax.legend(frameon=False, fontsize=8)
    add_region_guides(ax)
    style_axes(axes)
    save_figure(fig, outdir / "fullobs_transition_diagnostics_U40")


def build_dictionary() -> pd.DataFrame:
    rows = [
        ("E0", "measured", "Lowest energy of the fixed Nup=Ndn=8, Q=(0,0) block", "total energy"),
        ("Gap", "metadata-only", "qbasis energy_gap output; zero because only one eigenpair was requested", "not interpreted"),
        ("nn_NN", "measured", "Nearest-neighbor density product averaged over the 32 bonds", "per bond"),
        ("delta_n_delta_n_NN", "measured", "Connected nearest-neighbor density correlation; at half filling nn_NN-1", "per bond"),
        ("kinetic_NN_per_site", "measured", "Nearest-neighbor hopping expectation", "per site"),
        ("kinetic_NNN_per_site", "measured", "Next-nearest-neighbor hopping expectation", "per site; identically zero for tp=0"),
        ("kinetic_per_site", "measured", "Total hopping expectation", "per site"),
        ("C1_NN", "measured", "Nearest-neighbor spin dot product", "per bond"),
        ("n_k", "measured", "Spin-summed occupation of q=(0,0) in the f-twisted block, identified with physical k=f", "0 to 2"),
        ("D_k", "measured", "Momentum-orbital double occupation <n_k_up n_k_down>", "0 to 1"),
        ("D_site", "measured", "Real-space on-site double occupation", "per site"),
        ("Szz_pipi", "measured", "Longitudinal staggered spin structure factor", "1/N normalization"),
        ("Sc_pipi", "measured", "Staggered charge structure factor", "1/N normalization"),
        ("mCDW2_pipi", "measured", "Squared checkerboard order proxy Sc(pi,pi)/N", "dimensionless"),
        ("var_n_k", "derived", "n_k + 2 D_k - n_k^2", "intrinsic momentum-orbital number variance"),
        ("cov_nup_ndn_k", "derived", "D_k - (n_k/2)^2 using spin symmetry", "momentum spin covariance"),
        ("n_k_std", "derived", "Momentum-grid standard deviation of n(k)", "momentum differentiation, not statistical error"),
        ("n_epsilon_slope", "derived", "Weighted zero-intercept fit of n(k)-1 to epsilon_k", "coefficient a"),
    ]
    return pd.DataFrame(rows, columns=["field", "kind", "definition", "normalization_or_role"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/fullobs/U40_all_twist_20260717_123231"),
        help="Downloaded snapshot directory containing raw/ and metadata/",
    )
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--figures", type=Path, default=Path("figures/fullobs"))
    parser.add_argument("--tag", default="20260717_123231")
    args = parser.parse_args()

    raw_dir = args.input / "raw"
    metadata_dir = args.input / "metadata"
    manifest_path = metadata_dir / "complete_manifest.tsv"
    manifest = pd.read_csv(manifest_path, sep="\t", dtype={"sha256": str})
    manifest_by_name = manifest.set_index("filename")
    paths = sorted(raw_dir.glob("*_obs.dat"))

    hash_mismatches = []
    unexpected_files = []
    parsed = []
    for path in paths:
        if path.name not in manifest_by_name.index:
            unexpected_files.append(path.name)
            continue
        expected_hash = manifest_by_name.at[path.name, "sha256"]
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            hash_mismatches.append({"filename": path.name, "expected": expected_hash, "actual": actual_hash})
        parsed.append(parse_file(path))

    df = pd.DataFrame(parsed)
    rename = {
        "filename_Lx": "file_Lx",
        "filename_Ly": "file_Ly",
        "filename_Nup": "Nup",
        "filename_Ndn": "Ndn",
        "filename_U": "file_U",
        "filename_V": "file_V",
        "filename_tp": "file_tp",
        "filename_kx": "kx",
        "filename_ky": "ky",
        "filename_Qm": "Qm",
        "filename_Qn": "Qn",
    }
    df = df.rename(columns=rename)
    numeric_fields = ["Lx", "Ly", "tp", "U", "V", "E0", "Gap"] + list(RAW_TO_COLUMN.values())
    for column in numeric_fields:
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["symmetry_weight"] = np.where(df["kx"] == df["ky"], 1.0, 2.0)
    df["endpoint_weight"] = (
        np.where(df["kx"].isin([0, GRID_MAX]), 0.5, 1.0)
        * np.where(df["ky"].isin([0, GRID_MAX]), 0.5, 1.0)
    )
    df["quadrature_weight"] = df["symmetry_weight"] * df["endpoint_weight"]
    df["V_over_U"] = df["V"] / df["U"]
    df["kx_radian"] = df["kx"] * np.pi / GRID_MAX + 1.0e-5
    df["ky_radian"] = df["ky"] * np.pi / GRID_MAX + 1.0e-5
    df["epsilon_k"] = -2.0 * (np.cos(df["kx_radian"]) + np.cos(df["ky_radian"]))
    df["E0_per_site"] = df["E0"] / NSITES
    df["var_n_k"] = df["n_k"] + 2.0 * df["D_k"] - df["n_k"] ** 2
    df["cov_nup_ndn_k"] = df["D_k"] - (df["n_k"] / 2.0) ** 2
    df["energy_reconstructed_per_site"] = (
        df["kinetic_per_site"] + df["U"] * df["D_site"] + 2.0 * df["V"] * df["nn_NN"]
    )
    df["energy_identity_residual"] = df["E0_per_site"] - df["energy_reconstructed_per_site"]
    df["connected_density_identity_residual"] = df["delta_n_delta_n_NN"] - (df["nn_NN"] - 1.0)
    df["kinetic_identity_residual"] = df["kinetic_per_site"] - (
        df["kinetic_NN_per_site"] + df["kinetic_NNN_per_site"]
    )
    df["charge_identity_residual"] = df["mCDW2_pipi"] - df["Sc_pipi"] / NSITES

    duplicate_keys = int(df.duplicated(["U", "V", "kx", "ky"]).sum())
    required_columns = set(MEASURED_COLUMNS + ["status", "Q"])
    missing_columns = sorted(required_columns - set(df.columns))

    long_stats = []
    summary_rows = []
    for V in VS:
        group = df[df["V"] == V].copy()
        weights = group["quadrature_weight"].to_numpy()
        observed_weight = float(np.sum(weights))
        missing_weight = EXPECTED_QUADRATURE_WEIGHT - observed_weight
        row = {
            "U": U_FIXED,
            "V": V,
            "V_over_U": V / U_FIXED,
            "wedge_rows": len(group),
            "wedge_completion_fraction": len(group) / EXPECTED_WEDGE_ROWS,
            "quadrature_weight_observed": observed_weight,
            "quadrature_completion_fraction": observed_weight / EXPECTED_QUADRATURE_WEIGHT,
        }
        for column in ANALYSIS_COLUMNS:
            values = group[column].to_numpy(dtype=float)
            q05, q50, q95 = weighted_quantile(values, weights, [0.05, 0.50, 0.95])
            mean = weighted_mean(values, weights)
            std = weighted_std(values, weights)
            vmin, vmax = float(np.min(values)), float(np.max(values))
            denominator = EXPECTED_QUADRATURE_WEIGHT
            lower = (mean * observed_weight + vmin * missing_weight) / denominator
            upper = (mean * observed_weight + vmax * missing_weight) / denominator
            long_stats.append(
                {
                    "U": U_FIXED,
                    "V": V,
                    "V_over_U": V / U_FIXED,
                    "observable": column,
                    "display_name": DISPLAY[column],
                    "mean": mean,
                    "std_over_momentum_grid": std,
                    "min": vmin,
                    "q05": q05,
                    "median": q50,
                    "q95": q95,
                    "max": vmax,
                    "observed_range_missing_lower_bound": lower,
                    "observed_range_missing_upper_bound": upper,
                }
            )
            row[f"{column}_mean"] = mean
            row[f"{column}_std"] = std

        # Momentum diagnostics.
        x = group["epsilon_k"].to_numpy(dtype=float)
        y = group["n_k"].to_numpy(dtype=float) - 1.0
        slope = float(np.sum(weights * x * y) / np.sum(weights * x * x))
        prediction = slope * x
        sse = float(np.sum(weights * (y - prediction) ** 2))
        ybar = weighted_mean(y, weights)
        sst = float(np.sum(weights * (y - ybar) ** 2))
        row["n_epsilon_slope"] = slope
        row["n_epsilon_R2"] = 1.0 - sse / sst
        row["n_k_std"] = weighted_std(group["n_k"], weights)
        lookup = group.set_index(["kx", "ky"])
        row["n_k_gamma"] = float(lookup.loc[(0, 0), "n_k"])
        row["n_k_M"] = float(lookup.loc[(40, 40), "n_k"])
        row["n_k_band_contrast"] = row["n_k_gamma"] - row["n_k_M"]
        row["n_k_weighted_mean_minus_one"] = weighted_mean(group["n_k"], weights) - 1.0

        # Particle-hole check n(k)+n(pi-k)-2 on available pairs.
        map_n = {(int(r.kx), int(r.ky)): float(r.n_k) for r in group.itertuples()}
        ph_residuals = []
        for (kx, ky), value in map_n.items():
            partner = tuple(sorted((GRID_MAX - kx, GRID_MAX - ky)))
            if partner in map_n:
                ph_residuals.append(value + map_n[partner] - 2.0)
        row["particle_hole_mean_abs_residual"] = float(np.mean(np.abs(ph_residuals)))
        row["particle_hole_max_abs_residual"] = float(np.max(np.abs(ph_residuals)))
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    summary["branch"] = np.where(summary["D_site_mean"] < 0.25, "Mott", "charge")

    # Strong-coupling formulas, evaluated only on their corresponding branch.
    summary["Delta_M"] = U_FIXED - summary["V"]
    summary["Delta_C"] = 7.0 * summary["V"] - U_FIXED
    summary["E0_per_site_pred"] = np.nan
    summary["kinetic_per_site_pred"] = np.nan
    summary["n_epsilon_slope_pred"] = np.nan
    summary["D_site_pred"] = np.nan
    summary["nn_NN_pred"] = np.nan
    mott_mask = summary["branch"] == "Mott"
    charge_mask = summary["branch"] == "charge"
    spin_factor = 0.25 - summary.loc[mott_mask, "C1_NN_mean"]
    dm = summary.loc[mott_mask, "Delta_M"]
    summary.loc[mott_mask, "E0_per_site_pred"] = 2 * summary.loc[mott_mask, "V"] - 8 * spin_factor / dm
    summary.loc[mott_mask, "kinetic_per_site_pred"] = -16 * spin_factor / dm
    summary.loc[mott_mask, "n_epsilon_slope_pred"] = -4 * spin_factor / dm
    summary.loc[mott_mask, "D_site_pred"] = 8 * spin_factor / dm**2
    summary.loc[mott_mask, "nn_NN_pred"] = 1 - 4 * spin_factor / dm**2
    dc = summary.loc[charge_mask, "Delta_C"]
    summary.loc[charge_mask, "E0_per_site_pred"] = U_FIXED / 2 - 4 / dc
    summary.loc[charge_mask, "kinetic_per_site_pred"] = -8 / dc
    summary.loc[charge_mask, "n_epsilon_slope_pred"] = -2 / dc
    summary.loc[charge_mask, "D_site_pred"] = 0.5 - 4 / dc**2
    summary.loc[charge_mask, "nn_NN_pred"] = 14 / dc**2
    for field in ["E0_per_site", "kinetic_per_site", "n_epsilon_slope", "D_site", "nn_NN"]:
        measured = summary[f"{field}_mean"] if f"{field}_mean" in summary else summary[field]
        predicted = summary[f"{field}_pred"]
        summary[f"{field}_formula_residual"] = measured - predicted
        summary[f"{field}_formula_relative_error_percent"] = 100 * (measured / predicted - 1)

    # Numerical secants align with the right endpoint; first entry is NaN.
    summary["energy_dE_dV_numeric"] = np.nan
    e = summary["E0_per_site_mean"].to_numpy()
    vv = summary["V"].to_numpy(dtype=float)
    summary.loc[1:, "energy_dE_dV_numeric"] = np.diff(e) / np.diff(vv)

    # Piecewise-linear Hellmann--Feynman branch intersection from the nearest
    # directly sampled point on each side.
    r_mott = summary.loc[summary["branch"] == "Mott"].sort_values("V").iloc[-1]
    r_charge = summary.loc[summary["branch"] == "charge"].sort_values("V").iloc[0]
    v_mott = float(r_mott["V"])
    v_charge = float(r_charge["V"])
    slope_m = 2.0 * r_mott["nn_NN_mean"]
    slope_c = 2.0 * r_charge["nn_NN_mean"]
    e_m = float(r_mott["E0_per_site_mean"])
    e_c = float(r_charge["E0_per_site_mean"])
    crossing_v = (e_c - e_m + slope_m * v_mott - slope_c * v_charge) / (slope_m - slope_c)

    # Quality and physics validation.
    hash_manifest_names = set(manifest["filename"])
    local_names = {path.name for path in paths}
    quality = {
        "input_snapshot": str(args.input.resolve()),
        "manifest_rows": int(len(manifest)),
        "local_raw_files": int(len(paths)),
        "parsed_rows": int(len(df)),
        "manifest_missing_locally": sorted(hash_manifest_names - local_names),
        "unexpected_local_files": unexpected_files,
        "sha256_mismatches": hash_mismatches,
        "duplicate_parameter_keys": duplicate_keys,
        "missing_required_columns": missing_columns,
        "status_values": sorted(map(str, df["status"].unique())),
        "Q_values": sorted(map(str, df["Q"].unique())),
        "fixed_metadata": {
            "Lx": sorted(map(float, df["Lx"].unique())),
            "Ly": sorted(map(float, df["Ly"].unique())),
            "U": sorted(map(float, df["U"].unique())),
            "tp": sorted(map(float, df["tp"].unique())),
            "Gap": sorted(map(float, df["Gap"].unique())),
        },
        "max_abs_identity_residuals": {
            "energy_per_site": float(df["energy_identity_residual"].abs().max()),
            "connected_density": float(df["connected_density_identity_residual"].abs().max()),
            "kinetic_sum": float(df["kinetic_identity_residual"].abs().max()),
            "Sc_over_N": float(df["charge_identity_residual"].abs().max()),
        },
        "physical_range_checks": {
            "n_k_in_0_2": bool(df["n_k"].between(-1e-10, 2 + 1e-10).all()),
            "D_k_in_0_1": bool(df["D_k"].between(-1e-10, 1 + 1e-10).all()),
            "D_site_in_0_half": bool(df["D_site"].between(-1e-10, 0.5 + 1e-10).all()),
            "mCDW2_in_0_1": bool(df["mCDW2_pipi"].between(-1e-10, 1 + 1e-10).all()),
            "var_n_k_nonnegative": bool((df["var_n_k"] >= -1e-10).all()),
        },
        "completeness_by_V": summary[
            ["V", "wedge_rows", "wedge_completion_fraction", "quadrature_completion_fraction"]
        ].to_dict(orient="records"),
        "branch_switch_estimate": {
            "method": "piecewise-linear integration of d(E/N)/dV=2<ni nj> using nearest sampled points on each branch",
            "V_c": crossing_v,
            "V_c_over_U": crossing_v / U_FIXED,
            "last_mott_V": v_mott,
            "first_charge_V": v_charge,
            "Mott_side_slope": slope_m,
            "charge_side_slope": slope_c,
        },
    }

    args.results.mkdir(parents=True, exist_ok=True)
    args.figures.mkdir(parents=True, exist_ok=True)
    rows_path = args.results / f"fullobs_U40_observable_rows_{args.tag}.csv.gz"
    long_path = args.results / f"fullobs_U40_observable_stats_long_{args.tag}.csv"
    summary_path = args.results / f"fullobs_U40_observable_summary_by_V_{args.tag}.csv"
    dictionary_path = args.results / f"fullobs_U40_observable_dictionary_{args.tag}.csv"
    quality_path = args.results / f"fullobs_U40_data_quality_{args.tag}.json"
    df.sort_values(["V", "ky", "kx"]).to_csv(rows_path, index=False, compression="gzip")
    pd.DataFrame(long_stats).to_csv(long_path, index=False)
    summary.to_csv(summary_path, index=False)
    build_dictionary().to_csv(dictionary_path, index=False)
    quality_path.write_text(json.dumps(quality, indent=2) + "\n")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.labelsize": 9.5,
            "axes.titlesize": 10,
            "legend.fontsize": 8.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.5,
            "lines.markersize": 4.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )
    make_static_scan_figure(summary, args.figures)
    make_strong_coupling_figure(summary, args.figures)
    make_grouped_nk_figure(df, summary, args.figures)
    nk_plot_index = make_individual_nk_figures(df, args.figures)
    make_map_figure(df, "D_k", args.figures, "viridis")
    make_map_figure(df, "var_n_k", args.figures, "magma")
    make_n_epsilon_figure(df, summary, args.figures)
    make_transition_figure(summary, args.figures)

    receipt = {
        "rows": len(df),
        "V_values": VS,
        "summary_csv": str(summary_path.resolve()),
        "long_stats_csv": str(long_path.resolve()),
        "quality_json": str(quality_path.resolve()),
        "figure_directory": str(args.figures.resolve()),
        "individual_nk_plot_index": str((args.figures / "nk_individual" / "nk_plot_index.csv").resolve()),
        "individual_nk_plot_count": int(len(nk_plot_index)),
        "branch_switch_Vc": crossing_v,
        "branch_switch_Vc_over_U": crossing_v / U_FIXED,
    }
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
