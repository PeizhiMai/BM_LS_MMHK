#!/usr/bin/env python3
"""Plot only the occupied (lower) spectral band for the U=40 V scan.

Every panel has the same vertical span (10t).  Charge-side panels are centered
on the atomic removal energy -(4V-U/2), allowing their residual dispersion to
be compared without the increasing charge gap changing the panel magnification.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_u40_all_v_spectral_luttinger import (
    ETA,
    ROOT,
    U,
    VMAX,
    V_VALUES,
    interpolate_missing_rows,
    load_finite_v,
    load_u_only,
    value_label,
)


OUT_DIR = ROOT / "figures/luttinger_eta0p05_U40_allV"
WINDOW_SPAN = 10.0
HALF_WINDOW = WINDOW_SPAN / 2.0
MAX_OMEGA_PIXELS = 1800
X_PIXELS = 601

STYLE = {
    "font.family": "Arial",
    "font.size": 11,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.linewidth": 1.1,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def lower_band_window(V: float, omega: np.ndarray) -> tuple[float, float, float]:
    """Return a fixed-width absolute-energy window and its atomic center."""
    if V <= U / 4.0:
        atomic_center = -U / 2.0
    else:
        atomic_center = -(4.0 * V - U / 2.0)
    ymin = atomic_center - HALF_WINDOW
    ymax = atomic_center + HALF_WINDOW
    # The legacy V=0 spectrum ends at -24t.  Shift, rather than shrink, its
    # window so all panels retain the requested identical 10t span.
    if ymin < float(omega[0]):
        shift = float(omega[0]) - ymin
        ymin += shift
        ymax += shift
    if ymax > float(omega[-1]):
        shift = ymax - float(omega[-1])
        ymin -= shift
        ymax -= shift
    return ymin, ymax, atomic_center


def prepare_raster(record, ymin: float, ymax: float):
    rho, missing_rows = interpolate_missing_rows(record.rho, record.x_path)
    mask = (record.omega >= ymin - 1.0e-12) & (record.omega <= ymax + 1.0e-12)
    indices = np.where(mask)[0]
    if indices.size < 2:
        raise ValueError(f"No omega points in [{ymin:g},{ymax:g}] for V={record.V:g}")
    stride = max(1, math.ceil(indices.size / MAX_OMEGA_PIXELS))
    indices = indices[::stride]
    final = int(np.where(mask)[0][-1])
    if int(indices[-1]) != final:
        indices = np.append(indices, final)
    omega = record.omega[indices]
    rho = np.maximum(rho[:, indices], 0.0)

    x_uniform = np.linspace(record.x_path[0], record.x_path[-1], X_PIXELS)
    left = np.searchsorted(record.x_path, x_uniform, side="right") - 1
    left = np.clip(left, 0, record.x_path.size - 2)
    right = left + 1
    weight = (x_uniform - record.x_path[left]) / (record.x_path[right] - record.x_path[left])
    image = ((1.0 - weight[:, None]) * rho[left] + weight[:, None] * rho[right]).T
    return x_uniform, omega, image, missing_rows


def main() -> None:
    records = [load_u_only()]
    records.extend(load_finite_v(V) for V in V_VALUES if V != 0.0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = OUT_DIR / "rhoG_lower_band_U40_all_V_fixed10t_eta0p05_imshow.pdf"
    png = OUT_DIR / "rhoG_lower_band_U40_all_V_fixed10t_eta0p05_imshow.png"
    summary_path = OUT_DIR / "rhoG_lower_band_U40_all_V_fixed10t_eta0p05_imshow_summary.json"
    summary_rows = []

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(4, 3, figsize=(12.2, 12.4), squeeze=False)
        fig.subplots_adjust(left=0.075, right=0.985, top=0.985, bottom=0.055,
                            wspace=0.20, hspace=0.29)
        cmap = plt.get_cmap("rainbow").copy()
        last_image = None

        for panel_idx, (ax, record) in enumerate(zip(axes.ravel(), records)):
            ymin, ymax, atomic_center = lower_band_window(record.V, record.omega)
            x_uniform, omega, image, missing_rows = prepare_raster(record, ymin, ymax)
            last_image = ax.imshow(
                image,
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                extent=[x_uniform[0], x_uniform[-1], omega[0], omega[-1]],
                cmap=cmap,
                vmin=0.0,
                vmax=VMAX,
                rasterized=True,
            )
            ticks = [record.x_path[0], record.x_path[40], record.x_path[80], record.x_path[120]]
            ax.set_xlim(ticks[0], ticks[-1])
            ax.set_ylim(ymin, ymax)
            ax.set_xticks(ticks)
            ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
            for xpos in ticks[1:3]:
                ax.axvline(xpos, color="black", lw=0.9, ls="--", alpha=0.75)
            if panel_idx % 3 == 0:
                ax.set_ylabel(r"$\omega/t$")
            ax.text(0.018, 0.965, f"({chr(97 + panel_idx)})", transform=ax.transAxes,
                    ha="left", va="top", fontsize=12.5, fontweight="bold", color="black",
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.80, "pad": 1.2})
            ax.text(0.035, 0.075, rf"$V={value_label(record.V)}$", transform=ax.transAxes,
                    color="white", ha="left", va="bottom", fontsize=12, fontweight="bold",
                    bbox={"facecolor": "black", "edgecolor": "none", "alpha": 0.25, "pad": 2})
            summary_rows.append(
                {
                    "U": U,
                    "V": record.V,
                    "eta": ETA,
                    "ymin": ymin,
                    "ymax": ymax,
                    "y_span": ymax - ymin,
                    "atomic_lower_band_center": atomic_center,
                    "missing_display_rows_interpolated": missing_rows,
                    "source": str(record.source.relative_to(ROOT)),
                }
            )

        utility_ax = axes.ravel()[-1]
        utility_ax.axis("off")
        utility_ax.text(0.5, 0.82, r"$U=40,\quad t'=0$", ha="center", va="center",
                        fontsize=14, transform=utility_ax.transAxes)
        utility_ax.text(0.5, 0.66, r"identical vertical span: $10t$", ha="center", va="center",
                        fontsize=11.5, transform=utility_ax.transAxes)
        cax = utility_ax.inset_axes([0.09, 0.40, 0.82, 0.095])
        if last_image is None:
            raise RuntimeError("No lower-band panels were plotted")
        cbar = fig.colorbar(last_image, cax=cax, orientation="horizontal")
        cbar.set_ticks(np.arange(0.0, VMAX + 0.001, 0.5))
        cbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)
        cbar.ax.tick_params(labelsize=10, pad=2)

        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=260, bbox_inches="tight")
        plt.close(fig)

    summary = {
        "description": "Occupied spectral band for all U=40 V values, with a fixed 10t vertical span",
        "colormap": "rainbow",
        "color_range": [0.0, VMAX],
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
        "parameter_sets": summary_rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "png": str(png), "summary": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
