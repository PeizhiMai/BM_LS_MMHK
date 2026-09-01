#!/usr/bin/env python3
"""Render reproduced U-only zero-dispersion figure using imshow.

This uses the same eta=0.05 reproduced spectra and zero curves as
figures/luttinger_tp0_eta0p05.pdf, but renders the spectral maps with imshow
on the 121-point path-index grid for a sharper display in the manuscript.
"""
from __future__ import annotations

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NPZ = ROOT / "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz"
FIG_PDF = ROOT / "figures/luttinger_tp0_eta0p05_imshow.pdf"
FIG_PNG = ROOT / "figures/luttinger_tp0_eta0p05_imshow.png"


def decorate_k_axis(ax):
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])


def main() -> None:
    z = np.load(NPZ)
    omega = z["omega"]
    k_path = np.asarray(z["k_path"], dtype=float)
    U_values = [int(u) for u in z["U"]]
    rho = np.asarray(z["rho_G"], dtype=float)
    roots = np.asarray(z["omega_root"], dtype=float)
    xidx = np.arange(rho.shape[1])
    panels = ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"]
    map_ylims = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
    line_colors = {8: "#1f77b4", 12: "#ff7f0e", 20: "#2ca02c", 40: "#d62728"}
    intensity_vmax = 1.5

    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 18,
            "axes.labelsize": 22,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "legend.fontsize": 16,
            "axes.linewidth": 1.2,
        }
    ):
        fig = plt.figure(figsize=(10.05, 11.8), constrained_layout=False)
        gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.95], wspace=0.18, hspace=0.34)
        map_axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
        line_ax = fig.add_subplot(gs[2, 0])
        ref_ax = fig.add_subplot(gs[2, 1])
        fig.subplots_adjust(left=0.09, right=0.985, top=0.985, bottom=0.07)

        last_im = None
        for i, (ax, U, panel) in enumerate(zip(map_axes, U_values, panels[:4])):
            ylim = map_ylims[U]
            mask = np.abs(omega) <= ylim
            omega_plot = omega[mask]
            zmap = np.maximum(rho[i][:, mask], 0.0).T
            last_im = ax.imshow(
                zmap,
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                extent=[0, 120, float(omega_plot[0]), float(omega_plot[-1])],
                cmap="rainbow",
                vmin=0.0,
                vmax=intensity_vmax,
                rasterized=True,
            )
            ax.plot(xidx, roots[i], color="white", lw=1.8, solid_capstyle="round")
            ax.axhline(0.0, color="black", ls="--", lw=1.4)
            ax.axvline(40, color="black", ls="--", lw=1.4)
            ax.axvline(80, color="black", ls="--", lw=1.4)
            decorate_k_axis(ax)
            ax.set_ylim(-ylim, ylim)
            if i in (0, 2):
                ax.set_ylabel(r"$\omega/t$")
            ax.text(-0.20, 1.03, panel, transform=ax.transAxes, ha="left", va="top", color="black", fontsize=20)
            ax.text(0.03, 0.46, rf"$U={U}$", transform=ax.transAxes, ha="left", va="center", color="white", fontsize=18, fontstyle="italic")

        for cax_source in (map_axes[2], map_axes[3]):
            cbar = fig.colorbar(last_im, ax=cax_source, orientation="horizontal", fraction=0.08, pad=0.16)
            cbar.set_ticks([0.0, 0.4, 0.8, 1.2])
            cbar.ax.tick_params(labelsize=18, pad=2)

        for i, U in enumerate(U_values):
            line_ax.plot(xidx, roots[i], lw=2.8, color=line_colors[U], label=rf"$U={U}$" if U in (8, 12) else rf"${U}$")
        decorate_k_axis(line_ax)
        line_ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
        line_ax.grid(True, alpha=0.35)
        line_ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.52, 0.98))
        line_ax.text(-0.20, 1.03, panels[4], transform=line_ax.transAxes, ha="left", va="top", fontsize=20)
        line_ax.set_ylim(-6.2, 6.2)

        eps0 = -2 * (np.cos(k_path[:, 0] * np.pi / 40) + np.cos(k_path[:, 1] * np.pi / 40))
        ref = -1.4 * eps0
        idx40 = U_values.index(40)
        ref_ax.plot(xidx, roots[idx40], lw=2.8, color=line_colors[40], label=r"$U=40$")
        ref_ax.plot(xidx, ref, color="black", lw=2.6, ls=":", label=rf"$-1.4*\epsilon_{{0,\mathbf{{k}}}}(t'=0)$")
        decorate_k_axis(ref_ax)
        ref_ax.grid(True, alpha=0.35)
        ref_ax.legend(frameon=False, loc="upper center")
        ref_ax.text(-0.20, 1.03, panels[5], transform=ref_ax.transAxes, ha="left", va="top", fontsize=20)
        ref_ax.set_ylim(-6.2, 6.2)

        FIG_PDF.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG_PDF, bbox_inches="tight")
        fig.savefig(FIG_PNG, dpi=260, bbox_inches="tight")
        plt.close(fig)

    print(json.dumps({"pdf": str(FIG_PDF), "png": str(FIG_PNG)}, indent=2))


if __name__ == "__main__":
    main()
