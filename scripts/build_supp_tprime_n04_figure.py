#!/usr/bin/env python3
"""Build the t'=-0.4 counterpart of the existing supplemental t'=-0.25 figure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_prl_split_axis_figures import (  # noqa: E402
    STYLE as SPLIT_AXIS_STYLE,
    _colorbar_above as split_colorbar_above,
    _panel_label as split_panel_label,
    _spectral_map as split_spectral_map,
    _zero_curve_axis as split_zero_curve_axis,
)
from fit_tpn25_zero_dispersion import solve_j1j2  # noqa: E402


DATA = (
    ROOT
    / "data"
    / "Gcalpath"
    / "luttinger_surface_eta0p05_uonly_vonly_finite_tprime_20260802"
)
OUT = ROOT / "figures" / "pnas_supplement"
RESULTS = ROOT / "results"
TP = -0.4
U_VALUES = (8, 12, 20, 40)


def load_axis() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    omega_ref: np.ndarray | None = None
    k_path_ref: np.ndarray | None = None
    rho_rows: list[np.ndarray] = []
    root_rows: list[np.ndarray] = []
    for U in U_VALUES:
        source = DATA / f"rhoG_LS_U{U}_V0_tpn0p4_eta0p05_spectra_and_roots.npz"
        with np.load(source) as z:
            omega = np.asarray(z["omega"], dtype=float)
            k_path = np.asarray(z["k_path"], dtype=float)
            rho = np.asarray(z["rho_G"], dtype=float)
            roots = np.asarray(z["omega_root"], dtype=float)
        if omega_ref is None:
            omega_ref = omega
            k_path_ref = k_path
        else:
            if not np.array_equal(omega_ref, omega):
                raise ValueError(f"Inconsistent omega grid in {source}")
            if not np.array_equal(k_path_ref, k_path):
                raise ValueError(f"Inconsistent momentum path in {source}")
        rho_rows.append(rho)
        root_rows.append(roots)
    assert omega_ref is not None and k_path_ref is not None
    return omega_ref, np.stack(rho_rows), np.stack(root_rows), k_path_ref


def build() -> dict[str, object]:
    omega, rho, roots, k_path = load_axis()
    ylims = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
    colors = {8: "#2d6f9f", 12: "#d17b25", 20: "#3f8a55", 40: "#c54d3f"}

    with plt.rc_context(SPLIT_AXIS_STYLE):
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
        overlay_ax = fig.add_subplot(analysis_grid[0, 0])
        fit_ax = fig.add_subplot(analysis_grid[1, 0])
        fig.subplots_adjust(left=0.065, right=0.992, bottom=0.085, top=0.91)

        image = None
        for idx, (ax, U) in enumerate(zip(map_axes, U_VALUES)):
            image = split_spectral_map(
                ax,
                omega,
                rho[idx],
                roots[idx],
                ylim=ylims[U],
                text=rf"$U={U}$",
                vmax=1.5,
                show_ylabel=idx % 2 == 0,
            )
            split_panel_label(ax, f"({chr(97 + idx)})")
        if image is None:
            raise RuntimeError("No spectral maps were rendered")
        split_colorbar_above(fig, map_axes, image)

        x = np.arange(121)
        for idx, U in enumerate(U_VALUES):
            overlay_ax.plot(x, roots[idx], color=colors[U], label=rf"$U={U}$")
        split_zero_curve_axis(overlay_ax)
        overlay_ax.set_ylim(-5.4, 6.9)
        overlay_ax.yaxis.set_label_coords(-0.12, 0.5)
        overlay_ax.legend(
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
        split_panel_label(overlay_ax, "(e)", x=-0.075)

        kx = k_path[:, 0] * np.pi / 40.0
        ky = k_path[:, 1] * np.pi / 40.0
        epsilon_nn = -2.0 * (np.cos(kx) + np.cos(ky))
        epsilon_nnn = -4.0 * TP * np.cos(kx) * np.cos(ky)
        design = np.column_stack([epsilon_nn, epsilon_nnn])
        coefficients = np.linalg.lstsq(design, roots[-1], rcond=None)[0]
        fitted_reference = design @ coefficients

        spin = solve_j1j2(TP)
        spin_coefficients = np.asarray([4.0 * spin.c1, 4.0 * spin.c2])
        spin_reference = design @ spin_coefficients

        fit_ax.plot(x, roots[-1], color=colors[40], label=r"$U=40$ GZ")
        fit_ax.plot(x, fitted_reference, color="#1b6ca8", ls="--", label=r"NN+NNN fit")
        fit_ax.plot(
            x,
            spin_reference,
            color="black",
            ls=":",
            lw=2.1,
            label=(
                r"$4C_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}"
                r"+4C_{\mathrm{NNN}}\varepsilon_{\mathrm{NNN}}$"
            ),
        )
        split_zero_curve_axis(fit_ax)
        fit_ax.set_ylim(-5.4, 6.9)
        fit_ax.yaxis.set_label_coords(-0.12, 0.5)
        fit_ax.legend(
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.50, 0.99),
            fontsize=7.8,
            handlelength=1.25,
            labelspacing=0.12,
            borderaxespad=0.10,
        )
        split_panel_label(fit_ax, "(f)", x=-0.075)

        OUT.mkdir(parents=True, exist_ok=True)
        stem = "supp_fig_tpn0p4_reproduced"
        pdf = OUT / f"{stem}.pdf"
        png = OUT / f"{stem}.png"
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=260, bbox_inches="tight")
        plt.close(fig)

    metrics = {
        "tprime": TP,
        "U_fit": 40,
        "s_NN_fit": float(coefficients[0]),
        "s_NNN_fit": float(coefficients[1]),
        "fit_rmse": float(np.sqrt(np.mean((roots[-1] - fitted_reference) ** 2))),
        "C_NN_infinite_U": float(spin.c1),
        "C_NNN_infinite_U": float(spin.c2),
        "s_NN_infinite_U": float(spin_coefficients[0]),
        "s_NNN_infinite_U": float(spin_coefficients[1]),
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    metrics_path = RESULTS / "supp_tpn0p4_bond_coefficients.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    metrics["metrics"] = str(metrics_path.relative_to(ROOT))
    return metrics


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
