#!/usr/bin/env python3
"""Plot every available U=40, t'=0 spectrum with its Re G=0 branch.

The plot uses the manuscript's eta=0.05, Arial/rainbow/white-curve style and
``imshow``.  Before rasterization the 121 momentum rows are linearly resampled
onto a uniform physical Gamma-X-M-Gamma distance grid, so the longer M-Gamma
leg is displayed with its correct sqrt(2) metric rather than as an equal-width
index interval.

Rows missing from the three retained >99%-complete production sets are
interpolated only in the displayed raster/curve.  The source arrays and the
root-completeness counts written to the JSON summary remain unchanged.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/Gcalpath"
UONLY_NPZ = DATA / "luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz"
FINITE_DIR = DATA / "luttinger_surface_eta0p05_other_parameter_sets"
OUT_DIR = ROOT / "figures/luttinger_eta0p05_U40_allV"

U = 40.0
TP = 0.0
ETA = 0.05
V_VALUES = [0.0, 4.0, 6.0, 8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 20.0]
VMAX = 2.5
MAX_OMEGA_PIXELS = 2800
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


@dataclass
class Spectrum:
    V: float
    omega: np.ndarray
    x_path: np.ndarray
    rho: np.ndarray
    root: np.ndarray
    ylim: float
    source: Path


def value_label(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def default_x_path(nn: int = 40) -> np.ndarray:
    """Physical path coordinate used by the original Lanczos notebook."""
    x = np.zeros(3 * nn + 1, dtype=float)
    for idx in range(x.size):
        if idx < 2 * nn:
            x[idx] = idx + 1.0
        else:
            x[idx] = x[2 * nn - 1] + 1.0 + (idx - 2 * nn) * math.sqrt(2.0)
    return x


def load_u_only() -> Spectrum:
    with np.load(UONLY_NPZ) as z:
        u_values = np.asarray(z["U"], dtype=float)
        matches = np.where(np.isclose(u_values, U))[0]
        if matches.size != 1:
            raise ValueError(f"Expected one U={U:g} row in {UONLY_NPZ}, found {matches.size}")
        idx = int(matches[0])
        x_path = np.asarray(z["x_path"], dtype=float) if "x_path" in z.files else default_x_path()
        return Spectrum(
            V=0.0,
            omega=np.asarray(z["omega"], dtype=float),
            x_path=x_path,
            rho=np.asarray(z["rho_G"][idx], dtype=float),
            root=np.asarray(z["omega_root"][idx], dtype=float),
            ylim=24.0,
            source=UONLY_NPZ,
        )


def load_finite_v(V: float) -> Spectrum:
    path = FINITE_DIR / (
        f"rhoG_LS_U{value_label(U)}_V{value_label(V)}_tp0_eta0p05_spectra_and_roots.npz"
    )
    if not path.exists():
        raise FileNotFoundError(f"Missing processed spectrum for U={U:g}, V={V:g}: {path}")
    with np.load(path) as z:
        eta = float(np.asarray(z["eta"]).item())
        if not np.isclose(eta, ETA):
            raise ValueError(f"Expected eta={ETA:g} in {path}, found {eta:g}")
        x_path = np.asarray(z["x_path"], dtype=float) if "x_path" in z.files else default_x_path()
        return Spectrum(
            V=V,
            omega=np.asarray(z["omega"], dtype=float),
            x_path=x_path,
            rho=np.asarray(z["rho_G"], dtype=float),
            root=np.asarray(z["omega_root"], dtype=float),
            ylim=float(np.asarray(z["ylim"]).item()),
            source=path,
        )


def interpolate_missing_rows(values: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Interpolate absent momentum rows for display only."""
    out = np.asarray(values, dtype=float).copy()
    if out.ndim == 1:
        good = np.isfinite(out)
    else:
        good = np.isfinite(out).all(axis=tuple(range(1, out.ndim)))
    missing = np.where(~good)[0].tolist()
    good_indices = np.where(good)[0]
    if not missing:
        return out, missing
    if good_indices.size < 2:
        raise ValueError("Cannot interpolate display rows with fewer than two finite rows")
    for idx in missing:
        left = good_indices[good_indices < idx]
        right = good_indices[good_indices > idx]
        if left.size and right.size:
            i0, i1 = int(left[-1]), int(right[0])
            weight = (x[idx] - x[i0]) / (x[i1] - x[i0])
            out[idx] = (1.0 - weight) * out[i0] + weight * out[i1]
        elif right.size:
            out[idx] = out[int(right[0])]
        else:
            out[idx] = out[int(left[-1])]
    return out, missing


def resample_for_imshow(record: Spectrum) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[int]]:
    """Return a compact uniform-distance raster and display-only root curve."""
    rho, missing_rows = interpolate_missing_rows(record.rho, record.x_path)
    root, _ = interpolate_missing_rows(record.root, record.x_path)

    omega_mask = np.abs(record.omega) <= record.ylim + 1.0e-12
    omega_indices = np.where(omega_mask)[0]
    if omega_indices.size < 2:
        raise ValueError(f"No usable omega grid for V={record.V:g}")
    stride = max(1, math.ceil(omega_indices.size / MAX_OMEGA_PIXELS))
    omega_indices = omega_indices[::stride]
    final_idx = int(np.where(omega_mask)[0][-1])
    if int(omega_indices[-1]) != final_idx:
        omega_indices = np.append(omega_indices, final_idx)
    omega_plot = record.omega[omega_indices]
    rho_plot = np.maximum(rho[:, omega_indices], 0.0)

    x_uniform = np.linspace(record.x_path[0], record.x_path[-1], X_PIXELS)
    left = np.searchsorted(record.x_path, x_uniform, side="right") - 1
    left = np.clip(left, 0, record.x_path.size - 2)
    right = left + 1
    denom = record.x_path[right] - record.x_path[left]
    weight = (x_uniform - record.x_path[left]) / denom
    rho_uniform = (1.0 - weight[:, None]) * rho_plot[left] + weight[:, None] * rho_plot[right]
    return x_uniform, omega_plot, rho_uniform.T, root, missing_rows


def decorate_axis(ax: plt.Axes, x: np.ndarray, ylim: float) -> None:
    ticks = [x[0], x[40], x[80], x[120]]
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(-ylim, ylim)
    ax.set_xticks(ticks)
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.axhline(0.0, color="black", lw=0.9, ls="--", alpha=0.8)
    for xpos in ticks[1:3]:
        ax.axvline(xpos, color="black", lw=0.9, ls="--", alpha=0.75)


def plot(records: list[Spectrum]) -> tuple[Path, Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = OUT_DIR / "rhoG_LS_U40_all_V_eta0p05_imshow.pdf"
    png = OUT_DIR / "rhoG_LS_U40_all_V_eta0p05_imshow.png"
    summary_path = OUT_DIR / "rhoG_LS_U40_all_V_eta0p05_imshow_summary.json"

    summary_rows: list[dict] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(4, 3, figsize=(12.2, 12.4), squeeze=False)
        fig.subplots_adjust(left=0.075, right=0.985, top=0.985, bottom=0.055,
                            wspace=0.20, hspace=0.29)
        cmap = plt.get_cmap("rainbow").copy()
        last_image = None

        for panel_idx, (ax, record) in enumerate(zip(axes.ravel(), records)):
            x_uniform, omega_plot, image, display_root, missing_rows = resample_for_imshow(record)
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
            ax.plot(record.x_path, display_root, color="white", lw=1.8,
                    solid_capstyle="round", zorder=4)
            decorate_axis(ax, record.x_path, record.ylim)
            if panel_idx % 3 == 0:
                ax.set_ylabel(r"$\omega/t$")
            label = f"({chr(97 + panel_idx)})"
            ax.text(0.018, 0.965, label, transform=ax.transAxes, ha="left", va="top",
                    fontsize=12.5, fontweight="bold", color="black",
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
                    "source": str(record.source.relative_to(ROOT)),
                    "omega_min": float(record.omega[0]),
                    "omega_max": float(record.omega[-1]),
                    "plot_ylim": record.ylim,
                    "source_path_rows": int(record.rho.shape[0]),
                    "finite_root_rows": int(np.isfinite(record.root).sum()),
                    "missing_display_rows_interpolated": missing_rows,
                }
            )

        utility_ax = axes.ravel()[-1]
        utility_ax.axis("off")
        utility_ax.text(0.5, 0.81, r"$U=40,\quad t'=0$", ha="center", va="center",
                        fontsize=14, transform=utility_ax.transAxes)
        utility_ax.text(0.5, 0.66, r"white curve: $\mathrm{Re}\,G=0$", ha="center", va="center",
                        fontsize=11.5, transform=utility_ax.transAxes)
        cax = utility_ax.inset_axes([0.09, 0.40, 0.82, 0.095])
        if last_image is None:
            raise RuntimeError("No spectral panels were plotted")
        cbar = fig.colorbar(last_image, cax=cax, orientation="horizontal")
        cbar.set_ticks(np.arange(0.0, VMAX + 0.001, 0.5))
        cbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)
        cbar.ax.tick_params(labelsize=10, pad=2)

        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=260, bbox_inches="tight")
        plt.close(fig)

    if pdf.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Rendered file is not a PDF: {pdf}")
    summary = {
        "description": "All locally available U=40, t'=0 eta=0.05 spectral maps with white ReG=0 curves",
        "plot_renderer": "imshow after linear resampling to uniform physical path distance",
        "colormap": "rainbow",
        "color_range": [0.0, VMAX],
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
        "parameter_sets": summary_rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return pdf, png, summary_path


def main() -> None:
    records = [load_u_only()]
    records.extend(load_finite_v(V) for V in V_VALUES if V != 0.0)
    if [record.V for record in records] != V_VALUES:
        raise RuntimeError("Loaded V grid does not match the requested ordered grid")
    pdf, png, summary = plot(records)
    print(json.dumps({"pdf": str(pdf), "png": str(png), "summary": str(summary)}, indent=2))


if __name__ == "__main__":
    main()
