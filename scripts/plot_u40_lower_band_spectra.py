#!/usr/bin/env python3
"""Show only the occupied/lower spectral band for every available U=40 V.

Each panel uses an independently selected energy zoom around the significant
negative-frequency spectral weight.  The rho_G color normalization is shared,
so the evolution from the multi-branch Mott spectrum to the sharp charge-side
atomic line remains an intensity-faithful comparison.
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
    FINITE_DIR,
    ROOT,
    STYLE,
    TP,
    U,
    V_VALUES,
    VMAX,
    Spectrum,
    interpolate_missing_rows,
    load_finite_v,
    value_label,
)


OUT_DIR = ROOT / "figures/luttinger_eta0p05_U40_allV"
MAX_OMEGA_PIXELS = 1800
X_PIXELS = 601


def lower_band_window(record: Spectrum) -> tuple[float, float]:
    """Find a stable display window around the principal occupied band."""
    negative = record.omega < 0.0
    omega = record.omega[negative]
    rho = np.nan_to_num(np.maximum(record.rho[:, negative], 0.0), nan=0.0)
    profile = np.mean(rho, axis=0)
    if not np.isfinite(profile).any() or float(np.max(profile)) <= 0.0:
        raise ValueError(f"No negative-frequency spectral weight for V={record.V:g}")
    significant = profile >= 0.01 * float(np.max(profile))
    low = float(omega[significant][0])
    high = float(omega[significant][-1])
    margin = max(0.35, 0.08 * (high - low))
    # Half-tick rounding gives readable, reproducible panel limits.
    low = math.floor(2.0 * (low - margin)) / 2.0
    high = math.ceil(2.0 * (high + margin)) / 2.0
    return low, high


def resample_window(
    record: Spectrum, window: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    rho, missing_rows = interpolate_missing_rows(record.rho, record.x_path)
    low, high = window
    mask = (record.omega >= low) & (record.omega <= high)
    indices = np.where(mask)[0]
    if indices.size < 2:
        raise ValueError(f"Lower-band window {window} is outside the grid for V={record.V:g}")
    stride = max(1, math.ceil(indices.size / MAX_OMEGA_PIXELS))
    indices = indices[::stride]
    final_idx = int(np.where(mask)[0][-1])
    if int(indices[-1]) != final_idx:
        indices = np.append(indices, final_idx)

    omega_plot = record.omega[indices]
    rho_plot = np.maximum(rho[:, indices], 0.0)
    x_uniform = np.linspace(record.x_path[0], record.x_path[-1], X_PIXELS)
    left = np.searchsorted(record.x_path, x_uniform, side="right") - 1
    left = np.clip(left, 0, record.x_path.size - 2)
    right = left + 1
    weight = (x_uniform - record.x_path[left]) / (record.x_path[right] - record.x_path[left])
    rho_uniform = (1.0 - weight[:, None]) * rho_plot[left] + weight[:, None] * rho_plot[right]
    return x_uniform, omega_plot, rho_uniform.T, missing_rows


def decorate_axis(ax: plt.Axes, x: np.ndarray, window: tuple[float, float]) -> None:
    ticks = [x[0], x[40], x[80], x[120]]
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(*window)
    ax.set_xticks(ticks)
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    for xpos in ticks[1:3]:
        ax.axvline(xpos, color="black", lw=0.9, ls="--", alpha=0.75)


def main() -> None:
    # The dedicated V=0 file has the wider omega range needed to avoid
    # clipping the low-energy edge of the Mott lower Hubbard band.
    v0_path = FINITE_DIR / "rhoG_LS_U40_V0_tp0_eta0p05_spectra_and_roots.npz"
    if not v0_path.exists():
        raise FileNotFoundError(
            f"Missing wide-range V=0 source {v0_path}; generate it with "
            "generate_eta005_other_parameter_colorplots.py --groups 40,0,0."
        )
    records = [load_finite_v(V) for V in V_VALUES]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = OUT_DIR / "rhoG_U40_all_V_eta0p05_lower_band_imshow.pdf"
    png = OUT_DIR / "rhoG_U40_all_V_eta0p05_lower_band_imshow.png"
    summary_path = OUT_DIR / "rhoG_U40_all_V_eta0p05_lower_band_imshow_summary.json"

    summary_rows: list[dict] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(4, 3, figsize=(12.2, 12.0), squeeze=False)
        fig.subplots_adjust(left=0.075, right=0.985, top=0.985, bottom=0.055,
                            wspace=0.20, hspace=0.31)
        cmap = plt.get_cmap("rainbow").copy()
        last_image = None

        for panel_idx, (ax, record) in enumerate(zip(axes.ravel(), records)):
            window = lower_band_window(record)
            x_uniform, omega_plot, image, missing_rows = resample_window(record, window)
            last_image = ax.imshow(
                image,
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                extent=[x_uniform[0], x_uniform[-1], omega_plot[0], omega_plot[-1]],
                cmap=cmap,
                vmin=0.0,
                vmax=VMAX,
                rasterized=True,
            )
            decorate_axis(ax, record.x_path, window)
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
                    "tp": TP,
                    "eta": ETA,
                    "omega_window": list(window),
                    "source": str(record.source.relative_to(ROOT)),
                    "missing_display_rows_interpolated": missing_rows,
                }
            )

        utility_ax = axes.ravel()[-1]
        utility_ax.axis("off")
        utility_ax.text(0.5, 0.81, r"$U=40,\quad t'=0$", ha="center", va="center",
                        fontsize=14, transform=utility_ax.transAxes)
        utility_ax.text(0.5, 0.66, "lower band only", ha="center", va="center",
                        fontsize=11.5, transform=utility_ax.transAxes)
        utility_ax.text(0.5, 0.57, r"independent $\omega$ zoom in each panel", ha="center",
                        va="center", fontsize=10.5, transform=utility_ax.transAxes)
        cax = utility_ax.inset_axes([0.09, 0.36, 0.82, 0.095])
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
        "description": "Occupied/lower-band-only spectral maps for all U=40, t'=0 eta=0.05 sets",
        "window_rule": "mean negative-frequency rho_G >= 1% of its maximum, plus rounded margin",
        "shared_color_range": [0.0, VMAX],
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
        "parameter_sets": summary_rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pdf": str(pdf), "png": str(png), "summary": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
