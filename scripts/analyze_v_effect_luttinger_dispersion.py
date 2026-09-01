#!/usr/bin/env python3
"""Quantify how finite nearest-neighbor V changes eta=0.05 LS dispersion."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reproduce_luttinger_figures import noninteracting_dispersion  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
V0_NPZ = ROOT / "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz"
FINITE_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"
FIG_DIR = ROOT / "figures/luttinger_eta0p05_other_parameter_sets"
OUT_DIR = FINITE_DIR


def load_data() -> tuple[np.lib.npyio.NpzFile, dict[int, np.ndarray], list[dict]]:
    z0 = np.load(V0_NPZ)
    roots0 = {int(U): z0["omega_root"][idx] for idx, U in enumerate(z0["U"])}
    rows = []
    for path in sorted(FINITE_DIR.glob("rhoG_LS_U*_V*_tp0_eta0p05_spectra_and_roots.npz")):
        z = np.load(path)
        U = int(float(z["U"]))
        V = float(z["V"])
        if U not in roots0:
            continue
        rows.append({"U": U, "V": V, "roots": z["omega_root"], "path": path})
    return z0, roots0, rows


def fit_affine(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    A = np.column_stack([x[mask], np.ones(int(mask.sum()))])
    scale, offset = np.linalg.lstsq(A, y[mask], rcond=None)[0]
    residual = y[mask] - (scale * x[mask] + offset)
    return (
        float(scale),
        float(offset),
        float(np.sqrt(np.mean(residual**2))),
        float(np.max(np.abs(residual))),
    )


def compute_metrics(z0: np.lib.npyio.NpzFile, roots0: dict[int, np.ndarray], rows: list[dict]) -> list[dict]:
    eps0 = noninteracting_dispersion([tuple(map(int, row)) for row in z0["k_path"]], tp=0.0)
    out: list[dict] = []
    # Include V=0 references in the band-fit part so the scale changes are directly visible.
    for U, root in roots0.items():
        mask = np.isfinite(root)
        band_scale, band_offset, band_rmse, band_max = fit_affine(eps0[mask], root[mask])
        out.append(
            {
                "U": U,
                "V": 0.0,
                "n": int(mask.sum()),
                "mean_shift_vs_V0": 0.0,
                "rms_shift_vs_V0": 0.0,
                "max_abs_shift_vs_V0": 0.0,
                "std_shift_vs_V0": 0.0,
                "scale_vs_V0": 1.0,
                "offset_vs_V0": 0.0,
                "shape_rmse_after_rescale_vs_V0": 0.0,
                "shape_max_after_rescale_vs_V0": 0.0,
                "corr_vs_V0": 1.0,
                "band_scale": band_scale,
                "band_offset": band_offset,
                "band_fit_rmse": band_rmse,
                "band_fit_max_abs": band_max,
                "bandwidth": float(np.nanmax(root) - np.nanmin(root)),
            }
        )
    for row in rows:
        U = row["U"]
        V = row["V"]
        root = row["roots"]
        ref = roots0[U]
        mask = np.isfinite(root) & np.isfinite(ref)
        diff = root[mask] - ref[mask]
        scale, offset, rmse_rescale, max_rescale = fit_affine(ref[mask], root[mask])
        band_scale, band_offset, band_rmse, band_max = fit_affine(eps0[mask], root[mask])
        out.append(
            {
                "U": U,
                "V": V,
                "n": int(mask.sum()),
                "mean_shift_vs_V0": float(np.mean(diff)),
                "rms_shift_vs_V0": float(np.sqrt(np.mean(diff**2))),
                "max_abs_shift_vs_V0": float(np.max(np.abs(diff))),
                "std_shift_vs_V0": float(np.std(diff)),
                "scale_vs_V0": scale,
                "offset_vs_V0": offset,
                "shape_rmse_after_rescale_vs_V0": rmse_rescale,
                "shape_max_after_rescale_vs_V0": max_rescale,
                "corr_vs_V0": float(np.corrcoef(ref[mask], root[mask])[0, 1]),
                "band_scale": band_scale,
                "band_offset": band_offset,
                "band_fit_rmse": band_rmse,
                "band_fit_max_abs": band_max,
                "bandwidth": float(np.nanmax(root) - np.nanmin(root)),
            }
        )
    return sorted(out, key=lambda item: (item["U"], item["V"]))


def save_metrics(metrics: list[dict]) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "eta0p05_V_effect_luttinger_dispersion_metrics.csv"
    json_path = OUT_DIR / "eta0p05_V_effect_luttinger_dispersion_metrics.json"
    fields = list(metrics[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(metrics)
    json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return csv_path, json_path


def plot_comparison(z0: np.lib.npyio.NpzFile, roots0: dict[int, np.ndarray], rows: list[dict]) -> tuple[Path, Path]:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    x = z0["x_path"]
    by_u: dict[int, list[dict]] = {}
    for row in rows:
        by_u.setdefault(row["U"], []).append(row)
    u_values = [U for U in (8, 20, 40) if U in by_u]
    colors = plt.cm.viridis(np.linspace(0.18, 0.86, 5))
    pdf = FIG_DIR / "eta0p05_V_effect_luttinger_dispersion_comparison.pdf"
    png = FIG_DIR / "eta0p05_V_effect_luttinger_dispersion_comparison.png"
    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 15,
            "axes.labelsize": 17,
            "xtick.labelsize": 15,
            "ytick.labelsize": 15,
            "legend.fontsize": 12,
            "axes.linewidth": 1.1,
        }
    ):
        fig, axes = plt.subplots(len(u_values), 2, figsize=(10.2, 3.1 * len(u_values)), squeeze=False)
        fig.subplots_adjust(left=0.08, right=0.99, top=0.97, bottom=0.07, wspace=0.22, hspace=0.36)
        for row_idx, U in enumerate(u_values):
            ax = axes[row_idx, 0]
            dax = axes[row_idx, 1]
            ref = roots0[U]
            ax.plot(x, ref, color="black", lw=2.4, label=r"$V=0$")
            dax.axhline(0, color="black", lw=1.2, ls="--")
            for idx, row in enumerate(sorted(by_u[U], key=lambda item: item["V"])):
                color = colors[idx % len(colors)]
                root = row["roots"]
                V = row["V"]
                ax.plot(x, root, lw=2.0, color=color, label=rf"$V={V:g}$")
                dax.plot(x, root - ref, lw=2.0, color=color, label=rf"$V={V:g}$")
            for target in (ax, dax):
                target.set_xlim(x[0], x[-1])
                target.set_xticks([x[0], x[40], x[80], x[120]])
                target.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
                target.axvline(x[40], color="0.78", lw=1.0)
                target.axvline(x[80], color="0.78", lw=1.0)
                target.grid(True, alpha=0.28)
            ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
            dax.set_ylabel(r"$\Delta\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
            ax.set_title(rf"$U={U}$: finite-$V$ zero dispersion")
            dax.set_title(rf"$U={U}$: shift relative to $V=0$")
            ax.legend(frameon=False, ncol=3, loc="upper center")
            dax.legend(frameon=False, ncol=3, loc="upper center")
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=220, bbox_inches="tight")
        plt.close(fig)
    return pdf, png


def main() -> None:
    z0, roots0, rows = load_data()
    metrics = compute_metrics(z0, roots0, rows)
    csv_path, json_path = save_metrics(metrics)
    pdf, png = plot_comparison(z0, roots0, rows)
    print(json.dumps({"csv": str(csv_path), "json": str(json_path), "pdf": str(pdf), "png": str(png)}, indent=2))


if __name__ == "__main__":
    main()
