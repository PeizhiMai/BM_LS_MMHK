#!/usr/bin/env python3
"""Build Supplemental Fig. S1 from the 1D and 2D spinless t--V tests."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "results/mmhk_tV1_ground_state_convergence_drop_inv_n_0p25_points.csv"
FITS = ROOT / "results/mmhk_tV1_ground_state_convergence_drop_inv_n_0p25_fits.csv"
TWO_D = ROOT / "results/spinless_tV_pbc_comparison_all_references.csv"
OUTPUT = ROOT / "manuscript/supp_figures/supp_figS1_spinless_tV_benchmarks"
VALIDATION = ROOT / "results/supp_figS1_spinless_tV_benchmarks.json"


def style_axis(ax: plt.Axes) -> None:
    ax.minorticks_on()
    ax.tick_params(which="major", direction="in", length=4.0, width=0.9, top=True, right=True)
    ax.tick_params(which="minor", direction="in", length=2.2, width=0.7, top=True, right=True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)


def main() -> None:
    points = pd.read_csv(POINTS)
    fits = pd.read_csv(FITS)
    two_d = pd.read_csv(TWO_D)

    required_v = {4.0, 6.0, 8.0}
    if set(points["V"].unique()) != required_v or set(fits["V"].unique()) != required_v:
        raise ValueError("The 1D inputs must contain exactly V/t=4,6,8")
    if set(points["n"].unique()) != set(range(6, 21, 2)):
        raise ValueError("Panel (a) must use the even-n sequence n=6,...,20")
    if set(two_d["V_over_t"].unique()) != {1.0, 2.0, 4.0}:
        raise ValueError("The 2D input must contain V/t=1,2,4")

    plt.rcParams.update(
        {
            "font.size": 10.0,
            "axes.labelsize": 12.0,
            "xtick.labelsize": 10.0,
            "ytick.labelsize": 10.0,
            "legend.fontsize": 9.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.25, 3.35))
    fig.subplots_adjust(left=0.105, right=0.985, bottom=0.19, top=0.965, wspace=0.33)

    # (a) One-dimensional n_mix-MMHK convergence.
    colors = {4.0: "#5AA0C8", 6.0: "#F2A900", 8.0: "#A75B9E"}
    x_data_max = float((1.0 / points["n"]).max())
    xfit = np.linspace(0.0, 1.035 * x_data_max, 500)
    for V in (4.0, 6.0, 8.0):
        group = points[np.isclose(points["V"], V)].sort_values("n")
        fit = fits[np.isclose(fits["V"], V)].iloc[0]
        color = colors[V]
        ax_a.plot(
            1.0 / group["n"],
            group["delta_e"],
            "o",
            ms=5.6,
            color=color,
            mfc=color,
            mec="white",
            mew=0.4,
            linestyle="none",
            zorder=4,
            label=rf"$V/t={V:g}$",
        )
        ax_a.plot(
            xfit,
            fit["power_offset"]
            + fit["power_amplitude"] * np.power(xfit, fit["power_exponent"]),
            color=color,
            lw=1.55,
            linestyle=(0, (2.0, 2.0)),
            zorder=2,
        )

    r_text = "\n".join(
        rf"$V/t={row.V:g}:\ r_V={row.power_exponent:.2f}$" for row in fits.itertuples()
    )
    ax_a.text(0.055, 0.825, r_text, transform=ax_a.transAxes, ha="left", va="top", fontsize=10.2)
    ax_a.legend(
        loc="upper left",
        frameon=False,
        ncol=3,
        columnspacing=0.55,
        handletextpad=0.20,
        borderaxespad=0.35,
    )
    ax_a.set_xlabel(r"$1/n_{\mathrm{mix}}$")
    ax_a.set_ylabel(r"$E_{t\mathrm{-}V}^{\infty}-E_{\mathrm{MMHK}}^{(n_{\mathrm{mix}})}$")
    ax_a.set_xlim(-0.025 * x_data_max, 1.055 * x_data_max)
    ymax = 1.08 * float(points["delta_e"].max())
    ax_a.set_ylim(-0.075 * ymax, ymax)
    style_axis(ax_a)

    # (b) Two-dimensional square-lattice benchmark.
    benchmark_color = "#b7473e"
    styles = {
        "CT-QMC": ("o", r"CT-QMC, $8\!\times\!8$ PBC", 6.2),
        "DMRG": ("^", r"DMRG, $8\!\times\!8$ PBC", 6.2),
    }
    for method, (marker, label, marker_size) in styles.items():
        subset = two_d[two_d["method"] == method]
        ax_b.plot(
            subset["V_over_t"],
            subset["E0_per_site"],
            marker=marker,
            color=benchmark_color,
            linestyle="none",
            ms=marker_size,
            mfc="white",
            mec=benchmark_color,
            mew=1.05,
            label=label,
            zorder=7,
        )
    mmhk = two_d.drop_duplicates("V_over_t").sort_values("V_over_t")
    ax_b.plot(
        mmhk["V_over_t"],
        mmhk["E0_per_site_16MMHK"],
        "o",
        color=benchmark_color,
        linestyle="none",
        ms=4.9,
        mfc=benchmark_color,
        mec="white",
        mew=0.35,
        label="spinless 16-MMHK",
        zorder=10,
    )
    # Put the MMHK legend entry first without changing the requested draw order.
    handles, labels = ax_b.get_legend_handles_labels()
    order = [2, 0, 1]
    ax_b.legend(
        [handles[i] for i in order],
        [labels[i] for i in order],
        loc="upper left",
        frameon=False,
        fontsize=8.4,
        handlelength=1.55,
        handletextpad=0.35,
        labelspacing=0.18,
        borderaxespad=0.28,
    )
    ax_b.set_xlabel(r"$V/t$")
    ax_b.set_ylabel(r"$E_0/(N_s t)$")
    ax_b.set_xticks([1, 2, 3, 4])
    ax_b.set_xlim(0.82, 4.18)
    ax_b.grid(alpha=0.18)
    style_axis(ax_b)

    for label, ax in (("(a)", ax_a), ("(b)", ax_b)):
        ax.text(
            -0.18,
            0.965,
            label,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=12,
            fontweight="bold",
            clip_on=False,
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.05)
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    validation = {
        "status": "COMPLETE",
        "panel_a": {
            "dimension": "1D",
            "n_mix": list(range(6, 21, 2)),
            "V_over_t": [4, 6, 8],
            "fit": "Delta E=c_V+A_V*(1/n_mix)^r_V",
            "parameters": [
                {
                    "V_over_t": float(row.V),
                    "c_V": float(row.power_offset),
                    "A_V": float(row.power_amplitude),
                    "r_V": float(row.power_exponent),
                }
                for row in fits.itertuples()
            ],
        },
        "panel_b": {
            "dimension": "2D square lattice",
            "V_over_t": [1, 2, 4],
            "methods": ["spinless 16-MMHK", "CT-QMC 8x8 PBC", "DMRG 8x8 PBC"],
        },
        "artifacts": [str(OUTPUT.with_suffix(".pdf")), str(OUTPUT.with_suffix(".png"))],
    }
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n")
    print(f"Wrote {OUTPUT.with_suffix('.pdf')}")
    print(f"Wrote {VALIDATION}")


if __name__ == "__main__":
    main()
