#!/usr/bin/env python3
"""Build the four data-backed figures for the PNAS-level manuscript revision."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

from manuscript_figure_style import (
    ZERO_DISPERSION_AXIS_LABEL,
    ZERO_DISPERSION_SCALE_AXIS_LABEL,
    outside_panel_label,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/Gcalpath"
RESULTS = ROOT / "results"
OUT = ROOT / "figures/pnas_main"
OUT.mkdir(parents=True, exist_ok=True)

UONLY_NPZ = DATA / "luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz"
U0V12_NPZ = DATA / "luttinger_surface_eta0p05_U0_finiteV/rhoG_LS_U0_V12_tp0_eta0p05_spectra_and_roots.npz"
FINITE = DATA / "luttinger_surface_eta0p05_other_parameter_sets"

COLORS = {20.0: "#e68613", 40.0: "#c63b32", 80.0: "#7556a5"}
MARKERS = {20.0: "s", 40.0: "^", 80.0: "D"}
RAINBOW = "rainbow"
S_U_RESOLUTION = 1.4035604012
S_U_THERMO = 1.338883714
S_V = 8.0 / 7.0
R_BOUNDARY = 0.25
U_FIXED = 40.0
FULLOBS_TAG = "20260723_091307"
FULLOBS_SUMMARY = RESULTS / f"fullobs_U40_observable_summary_by_V_{FULLOBS_TAG}.csv"
FULLOBS_ROWS = RESULTS / f"fullobs_U40_observable_rows_{FULLOBS_TAG}.csv.gz"
FULLOBS_QUALITY = RESULTS / f"fullobs_U40_data_quality_{FULLOBS_TAG}.json"


STYLE = {
    "font.family": "Arial",
    "font.size": 11,
    "axes.labelsize": 13,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 10.5,
    "axes.linewidth": 1.1,
    "lines.linewidth": 2.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def k_axis(ax) -> None:
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    for xpos in (40, 80):
        ax.axvline(xpos, color="black", lw=0.9, ls="--", alpha=0.75)


def panel_label(
    ax,
    label: str,
    color: str = "black",
    *,
    x: float = -0.105,
) -> None:
    outside_panel_label(ax, label, color=color, fontsize=12.5, x=x)


def save(
    fig,
    stem: str,
    *,
    output_dir: Path = OUT,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf = output_dir / f"{stem}.pdf"
    png = output_dir / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return {"pdf": str(pdf.relative_to(ROOT)), "png": str(png.relative_to(ROOT))}


def extract_uonly(U: int) -> dict[str, np.ndarray]:
    z = np.load(UONLY_NPZ)
    uvals = [int(v) for v in z["U"]]
    idx = uvals.index(U)
    return {
        "omega": z["omega"],
        "rho": z["rho_G"][idx],
        "root": z["omega_root"][idx],
        "k_path": z["k_path"],
    }


def load_single(path: Path) -> dict[str, np.ndarray]:
    z = np.load(path)
    return {
        "omega": z["omega"],
        "rho": z["rho_G"],
        "root": z["omega_root"],
        "k_path": z["k_path"],
        "ylim": np.asarray(z["ylim"]).item() if "ylim" in z.files else None,
    }


def spectral_map(
    ax,
    record: dict[str, np.ndarray],
    ylim: float,
    label: str,
    show_ylabel: bool = True,
    vmax: float = 2.5,
    *,
    label_x: float = 0.035,
    label_y: float = 0.08,
    label_va: str = "bottom",
    label_framed: bool = True,
):
    omega = record["omega"]
    mask = np.abs(omega) <= ylim
    rho = np.asarray(record["rho"][:, mask], dtype=float).copy()
    # A few retained production sets have one absent momentum row.  Interpolate
    # that row only for the raster display; all fits and completeness metrics
    # continue to exclude it and are reported in Fig. 4d and the source CSV.
    missing = np.where(~np.isfinite(rho).all(axis=1))[0]
    for idx in missing:
        if 0 < idx < len(rho) - 1:
            rho[idx] = 0.5 * (rho[idx - 1] + rho[idx + 1])
        elif idx == 0:
            rho[idx] = rho[idx + 1]
        else:
            rho[idx] = rho[idx - 1]
    root = np.asarray(record["root"], dtype=float).copy()
    for idx in np.where(~np.isfinite(root))[0]:
        if 0 < idx < len(root) - 1:
            root[idx] = 0.5 * (root[idx - 1] + root[idx + 1])
        elif idx == 0:
            root[idx] = root[idx + 1]
        else:
            root[idx] = root[idx - 1]
    image = np.maximum(rho, 0.0).T
    im = ax.imshow(
        image,
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
        extent=[0, 120, float(omega[mask][0]), float(omega[mask][-1])],
        cmap=RAINBOW,
        vmin=0,
        vmax=vmax,
        rasterized=True,
    )
    ax.plot(np.arange(121), root, color="white", lw=1.8,
            solid_capstyle="round")
    ax.axhline(0, color="black", lw=0.9, ls="--", alpha=0.8)
    k_axis(ax)
    ax.set_ylim(-ylim, ylim)
    if show_ylabel:
        ax.set_ylabel(r"$\omega/t$")
    ax.text(
        label_x,
        label_y,
        label,
        transform=ax.transAxes,
        color="white",
        ha="left",
        va=label_va,
        fontsize=12,
        fontweight="bold",
        bbox=(
            {
                "facecolor": "black",
                "edgecolor": "none",
                "alpha": 0.25,
                "pad": 2,
            }
            if label_framed
            else None
        ),
    )
    return im


def supplement_panel_label(ax, label: str) -> None:
    """Apply the common unframed, outside-frame panel-label rule."""
    outside_panel_label(ax, label, fontsize=12)


def asymptotic_mechanisms(
    *,
    output_dir: Path = ROOT / "figures" / "pnas_supplement",
    stem: str = "supp_figS1_asymptotic_mechanisms",
) -> dict[str, str]:
    """Build the direct strong-coupling comparison now used as Fig. S1."""
    u40 = extract_uonly(40)
    v12 = load_single(U0V12_NPZ)
    scale = pd.read_csv(RESULTS / "additional2_zero_dispersion_scale_fits_eta0p05.csv")

    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(10.1, 8.0))
        gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 0.9], hspace=0.33, wspace=0.25)
        axa = fig.add_subplot(gs[0, 0])
        axb = fig.add_subplot(gs[0, 1])
        axc = fig.add_subplot(gs[1, 0])
        axd = fig.add_subplot(gs[1, 1])

        ima = spectral_map(axa, u40, 24, r"$U=40,\ V=0$")
        spectral_map(axb, v12, 56, r"$U=0,\ V=12$", show_ylabel=True)
        panel_label(axa, "(a)")
        panel_label(axb, "(b)")
        cbar = fig.colorbar(ima, ax=[axa, axb], orientation="horizontal",
                           fraction=0.055, pad=0.13, aspect=45)
        cbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)

        epsilon1 = -2.0 * (
            np.cos(u40["k_path"][:, 0] * np.pi / 40.0)
            + np.cos(u40["k_path"][:, 1] * np.pi / 40.0)
        )
        x = np.arange(121)
        axc.plot(x, u40["root"], color="#c63b32", label=r"$U=40,V=0$")
        s_u_resolution = -S_U_RESOLUTION
        s_u_thermo = -S_U_THERMO
        s_v = -S_V
        axc.plot(x, s_u_resolution * epsilon1, color="#c63b32", ls="--",
                 label=r"$4C_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$")
        axc.plot(x, v12["root"], color="#2767a5", label=r"$U=0,V=12$")
        axc.plot(x, s_v * epsilon1, color="#2767a5", ls=":",
                 label=r"$-(8/7)\varepsilon_{\mathrm{NN}}(\mathbf{k})$")
        axc.axhline(0, color="0.5", lw=0.8)
        k_axis(axc)
        axc.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
        axc.set_ylim(-6.1, 6.1)
        axc.legend(frameon=False, ncol=1, loc="upper center")
        panel_label(axc, "(c)")

        urows = scale[(scale["U"] > 0) & (scale["V"] == 0)].sort_values("U")
        vrows = scale[(scale["U"] == 0) & (scale["V"] > 0)].sort_values("V")
        axd.plot(1.0 / urows["U"], -urows["s"], marker="s", color="#c63b32",
                 label=r"$U$-only: $t/U$")
        axd.plot(1.0 / vrows["V"], -vrows["s"], marker="o", color="#2767a5",
                 label=r"$V$-only: $t/V$")
        axd.axhline(s_u_resolution, color="#c63b32", ls="--", lw=1.3)
        axd.axhline(s_u_thermo, color="#c63b32", ls=":", lw=1.0, alpha=0.75)
        axd.axhline(s_v, color="#2767a5", ls="--", lw=1.3)
        axd.text(0.248, s_u_resolution - 0.012, r"$4C_{\mathrm{NN}}$", color="#9a2d27",
                 ha="right", va="top")
        axd.text(0.248, s_v - 0.012, r"$-8/7$", color="#1d527f",
                 ha="right", va="top")
        axd.set_xlabel("inverse interaction")
        axd.set_ylabel(ZERO_DISPERSION_SCALE_AXIS_LABEL)
        axd.set_xlim(-0.005, 0.255)
        axd.set_ylim(-1.45, -1.10)
        axd.grid(alpha=0.2)
        axd.legend(frameon=False, loc="center right")
        panel_label(axd, "(d)")
        fig.subplots_adjust(left=0.09, right=0.985, top=0.98, bottom=0.08)
        return save(fig, stem, output_dir=output_dir)


def figure1() -> dict[str, str]:
    """Build the condensed density benchmark promoted to main Figure 1."""
    from plot_combined_density_benchmark import build_condensed_density_benchmark

    return build_condensed_density_benchmark(
        stem="fig1_multidensity_benchmark",
        output_dir=OUT,
    )


def finite_uv_spectral_reorganization(
    *,
    output_dir: Path = ROOT / "figures" / "pnas_supplement",
    stem: str = "supp_figS6_finite_uv_spectral_reorganization",
) -> dict[str, str]:
    """Build the six-panel finite-U,V spectral sequence used as Fig. S6."""
    records = {
        0: extract_uonly(40),
        4: load_single(FINITE / "rhoG_LS_U40_V4_tp0_eta0p05_spectra_and_roots.npz"),
        8: load_single(FINITE / "rhoG_LS_U40_V8_tp0_eta0p05_spectra_and_roots.npz"),
        12: load_single(FINITE / "rhoG_LS_U40_V12_tp0_eta0p05_spectra_and_roots.npz"),
        16: load_single(FINITE / "rhoG_LS_U40_V16_tp0_eta0p05_spectra_and_roots.npz"),
        20: load_single(FINITE / "rhoG_LS_U40_V20_tp0_eta0p05_spectra_and_roots.npz"),
    }
    v_values = [0, 4, 8, 12, 16, 20]
    ylims = {0: 24.0, 4: 30.0, 8: 30.0, 12: 40.0, 16: 50.0, 20: 70.0}
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(3, 2, figsize=(9.8, 10.4))
        last = None
        for i, (ax, V) in enumerate(zip(axes.ravel(), v_values)):
            last = spectral_map(
                ax,
                records[V],
                ylims[V],
                rf"$U=40,\ V={V}$",
                show_ylabel=i % 2 == 0,
                label_x=0.035,
                label_y=0.46,
                label_va="center",
                label_framed=False,
            )
            supplement_panel_label(ax, f"({chr(97+i)})")
        cax = fig.add_axes([0.26, 0.045, 0.48, 0.024])
        cbar = fig.colorbar(last, cax=cax, orientation="horizontal")
        cbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)
        fig.subplots_adjust(
            left=0.09,
            right=0.985,
            top=0.99,
            bottom=0.11,
            hspace=0.30,
            wspace=0.22,
        )
        return save(fig, stem, output_dir=output_dir)


def figure2() -> dict[str, str]:
    """Promote the former Fig. S4 interaction-axis comparison to Fig. 2."""
    from build_pnas_supplement_figures import (  # noqa: E402
        interaction_axis_comparison_figure,
    )

    return interaction_axis_comparison_figure(
        output_dir=OUT,
        stem="pnas_fig2_interaction_axis_comparison",
        metrics_path=RESULTS / "pnas_fig2_axis_fit_metrics.csv",
    )


def figure3_scale_only() -> dict[str, str]:
    """Build the former one-panel Figure 3 for archival comparison."""
    points = pd.read_csv(RESULTS / "pnas_scale_rule_points_eta0p05.csv")
    summary = json.loads((RESULTS / "pnas_scale_rule_summary_eta0p05.json").read_text())
    lam = summary["mott_parameters"]["lambda"]
    beta = summary["charge_parameters"]["beta"]
    lam_lo, lam_hi = summary["mott_95pct_stratified_bootstrap_ci"]["lambda"]
    beta_lo, beta_hi = summary["charge_95pct_stratified_bootstrap_ci"]["beta"]

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(7.4, 4.8))
        ax.axvspan(0.0, R_BOUNDARY, color="#3b78a8", alpha=0.055, zorder=0)
        ax.axvspan(R_BOUNDARY, 0.53, color="#b64a42", alpha=0.05, zorder=0)
        for U in [20.0, 40.0, 80.0]:
            g = points[points["U"] == U].sort_values("r")
            ax.plot(g["r"], g["s"], marker=MARKERS[U], color=COLORS[U], lw=0,
                    ms=6.5, label=rf"$U={U:g}$", zorder=4)
            s0 = float(g.loc[g["V"] == 0, "s_u0"].iloc[0])
            r = np.linspace(0.0, 0.245, 220)
            ax.plot(r, s0 / (1.0 - lam * r), color=COLORS[U], lw=1.55, alpha=0.8)
            ax.fill_between(r, s0 / (1.0 - lam_lo * r), s0 / (1.0 - lam_hi * r),
                            color=COLORS[U], alpha=0.07, linewidth=0)
        r = np.linspace(0.255, 0.52, 240)
        x = 1.0 / (4.0 * r)
        charge = S_V + beta * x**2
        ax.plot(r, charge, color="black", ls="-.", lw=2.0)
        ax.fill_between(r, S_V + beta_lo * x**2, S_V + beta_hi * x**2,
                        color="black", alpha=0.08, linewidth=0)
        ax.axvline(R_BOUNDARY, color="0.35", lw=1.0, ls=":")
        ax.hlines(S_U_RESOLUTION, 0.0, R_BOUNDARY, color="0.45", ls="--", lw=1.0)
        ax.hlines(S_V, R_BOUNDARY, 0.53, color="0.15", ls="--", lw=1.1)
        ax.text(0.125, S_U_RESOLUTION - 0.018, r"$U\to\infty,\ 4C_{\mathrm{NN}}$",
                ha="center", va="top", color="0.38")
        ax.text(0.515, S_V - 0.014, r"$V$-only $8/7$", ha="right", va="top",
                color="0.1")
        ax.text(0.105, 1.09, "Mott / spin side", color="#1f5278", ha="center")
        ax.text(0.39, 1.09, "CDW / charge side", color="#8d2d28", ha="center")
        ax.set_xlabel(r"$V/U$", labelpad=1)
        ax.set_ylabel(ZERO_DISPERSION_SCALE_AXIS_LABEL)
        ax.set_xlim(-0.01, 0.53)
        ax.set_ylim(1.06, 1.84)
        ax.grid(alpha=0.18)
        ax.legend(frameon=False, ncol=1, loc="upper left")
        fig.subplots_adjust(left=0.13, right=0.985, top=0.98, bottom=0.15)
        return save(fig, "pnas_fig3_scale_across_interaction_plane")


def figure3() -> dict[str, str]:
    """Build the canonical two-panel scale and transition-boundary figure."""
    from build_scale_and_transition_figure import (
        OUT_PDF,
        OUT_PNG,
        build_figure,
    )

    build_figure()
    return {
        "pdf": str(OUT_PDF.relative_to(ROOT)),
        "png": str(OUT_PNG.relative_to(ROOT)),
    }


def figure4() -> dict[str, str]:
    """Energy, order diagnostics, and interacting/free n(k) maps."""
    from analyze_fullobs_u40_scan import full_map, noninteracting_nk_map

    obs = pd.read_csv(FULLOBS_SUMMARY)
    rows = pd.read_csv(FULLOBS_ROWS)
    quality = json.loads(FULLOBS_QUALITY.read_text())
    crossing = quality["branch_switch_estimate"]
    last_mott_v = float(crossing["last_mott_V"])
    first_charge_v = float(crossing["first_charge_V"])
    x = obs["V_over_U"].to_numpy(dtype=float)

    def phase_guides(ax) -> None:
        ax.axvspan(0.0, R_BOUNDARY, color="#3b78a8", alpha=0.055, zorder=-10)
        ax.axvspan(R_BOUNDARY, 0.52, color="#b64a42", alpha=0.05, zorder=-10)
        ax.axvline(R_BOUNDARY, color="0.35", lw=1.0, ls=":", zorder=-5)
        ax.axvspan(
            last_mott_v / U_FIXED,
            first_charge_v / U_FIXED,
            color="#d39a2c",
            alpha=0.16,
            lw=0,
            zorder=-4,
        )
        ax.set_xlim(-0.01, 0.51)
        ax.set_xlabel(r"$V/U$")
        ax.grid(alpha=0.18, lw=0.7)

    map_arrays = {
        float(V): full_map(rows[np.isclose(rows["V"], V)], "n_k")
        for V in [0.0, 20.0]
    }
    map_finite = np.concatenate(
        [array[np.isfinite(array)] for array in map_arrays.values()]
    )
    map_radius = max(
        abs(float(np.min(map_finite)) - 1.0),
        abs(float(np.max(map_finite)) - 1.0),
    )
    interacting_norm = TwoSlopeNorm(
        vmin=1.0 - map_radius,
        vcenter=1.0,
        vmax=1.0 + map_radius,
    )
    # The analytic reference is evaluated on a much denser grid than the
    # interacting calculation so its Fermi line remains smooth when rendered.
    free_map = noninteracting_nk_map(points=1001)
    free_norm = TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=2.0)
    map_cmap = plt.get_cmap("RdBu_r").copy()
    map_cmap.set_bad("#d9d9d9")

    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(10.6, 7.6))
        grid = fig.add_gridspec(
            2,
            3,
            height_ratios=[0.88, 1.0],
            hspace=0.18,
            wspace=0.24,
        )
        axa = fig.add_subplot(grid[0, 0])
        axb = fig.add_subplot(grid[0, 1])
        axc = fig.add_subplot(grid[0, 2])
        axd = fig.add_subplot(grid[1, 0])
        axe = fig.add_subplot(grid[1, 1])
        axf = fig.add_subplot(grid[1, 2])

        mott = obs[obs["branch"].eq("Mott")]
        charge = obs[obs["branch"].eq("charge")]
        axa.plot(
            mott["V_over_U"],
            mott["E0_per_site_mean"],
            "o-",
            color="#335f8d",
            label="Mott",
        )
        axa.plot(
            charge["V_over_U"],
            charge["E0_per_site_mean"],
            "s-",
            color="#c56f2d",
            label="CDW",
        )
        axa.plot(
            [mott["V_over_U"].iloc[-1], charge["V_over_U"].iloc[0]],
            [mott["E0_per_site_mean"].iloc[-1], charge["E0_per_site_mean"].iloc[0]],
            color="0.35",
            lw=1.0,
            zorder=1,
        )
        axa.set_ylabel(r"$E_0/(Nt)$")
        axa.legend(
            frameon=False,
            fontsize=12.9,
            loc="upper left",
            bbox_to_anchor=(0.015, 0.94),
            borderaxespad=0.0,
            handlelength=1.6,
            handletextpad=0.55,
            labelspacing=0.45,
        )
        phase_guides(axa)
        panel_label(axa, "(a)", x=-0.14)

        axb.plot(x, obs["D_site_mean"], "o-", color="#335f8d",
                 label=r"$D_i$")
        axb.plot(x, obs["mCDW2_pipi_mean"], "s-", color="#c56f2d",
                 label=r"$m_{\rm CDW}^2$")
        axb.plot(x, obs["nn_NN_mean"], "^-", color="#4b7f52",
                 label=r"$\langle n_i n_j\rangle_{\rm NN}$")
        axb.set_ylabel("charge diagnostics")
        axb.set_ylim(-0.035, 1.055)
        axb.legend(
            frameon=False,
            fontsize=12.45,
            loc="upper left",
            bbox_to_anchor=(0.015, 0.94),
        )
        phase_guides(axb)
        panel_label(axb, "(b)", x=-0.14)

        axc.plot(x, obs["Szz_pipi_mean"], "o-", color="#7a5c91",
                 label=r"$S^{zz}(\pi,\pi)$")
        axc.plot(x, -obs["C1_NN_mean"], "s-", color="#335f8d",
                 label=r"$-\langle\mathbf{S}_i\!\cdot\!\mathbf{S}_j\rangle_{\rm NN}$")
        axc.set_ylabel("spin diagnostics")
        axc.set_ylim(-0.045, 1.55)
        axc.legend(
            frameon=False,
            fontsize=11.9,
            loc="upper right",
            bbox_to_anchor=(1.015, 0.94),
            handlelength=1.4,
        )
        phase_guides(axc)
        panel_label(axc, "(c)", x=-0.14)

        interacting_image = None
        for ax, array, title, label in [
            (axd, map_arrays[0.0], r"$V/U=0$", "(d)"),
            (axe, map_arrays[20.0], r"$V/U=0.5$", "(e)"),
        ]:
            interacting_image = ax.imshow(
                array,
                origin="lower",
                extent=(0, 1, 0, 1),
                interpolation="nearest",
                aspect="equal",
                cmap=map_cmap,
                norm=interacting_norm,
                rasterized=True,
            )
            ax.set_title(title, fontsize=10.0, pad=1.0)
            ax.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
            ax.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
            ax.set_xlabel(r"$k_x$")
            ax.tick_params(labelsize=12.9, length=3)
            panel_label(ax, label)

        free_image = axf.imshow(
            free_map,
            origin="lower",
            extent=(0, 1, 0, 1),
            interpolation="nearest",
            aspect="equal",
            cmap=map_cmap,
            norm=free_norm,
            rasterized=True,
        )
        axf.set_title(r"noninteracting $U=V=0$", fontsize=10.0, pad=1.0)
        axf.set_xticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        axf.set_yticks([0, 0.5, 1], [r"$0$", r"$\pi/2$", r"$\pi$"])
        axf.set_xlabel(r"$k_x$")
        axf.tick_params(labelsize=12.9, length=3)
        panel_label(axf, "(f)")

        axd.set_ylabel(r"$k_y$")
        axe.tick_params(labelleft=False)
        axf.tick_params(labelleft=False)

        if interacting_image is None:
            raise RuntimeError("Figure 4 momentum maps were not rendered")

        fig.subplots_adjust(
            left=0.09,
            right=0.99,
            top=0.985,
            bottom=0.17,
        )

        # Place both bars just below, but clear of, the x-axis labels.
        # Panels (d,e) share the interaction-resolved scale, while panel (f)
        # retains the full
        # noninteracting 0--2 occupation range.
        pos_d = axd.get_position()
        pos_e = axe.get_position()
        pos_f = axf.get_position()
        colorbar_y = pos_d.y0 - 0.088
        cax_interacting = fig.add_axes(
            [pos_d.x0, colorbar_y, pos_e.x1 - pos_d.x0, 0.016]
        )
        cax_free = fig.add_axes(
            [pos_f.x0, colorbar_y, pos_f.width, 0.016]
        )
        interacting_colorbar = fig.colorbar(
            interacting_image,
            cax=cax_interacting,
            orientation="horizontal",
        )
        free_colorbar = fig.colorbar(
            free_image,
            cax=cax_free,
            orientation="horizontal",
            ticks=[0.0, 1.0, 2.0],
        )
        interacting_colorbar.set_label(r"$n(\mathbf{k})$", labelpad=2)
        free_colorbar.set_label(r"$n_0(\mathbf{k})$", labelpad=2)
        for colorbar in (interacting_colorbar, free_colorbar):
            colorbar.ax.tick_params(labelsize=12.9, pad=2)

        return save(fig, "pnas_fig4_static_branch_crossing")


def figure_s_extraction_robustness() -> dict[str, str]:
    """Preserve the former main-text extraction audit as an SI figure."""
    nk = pd.read_csv(RESULTS / "nk_metrics.csv")
    nk = nk[(nk["tp"] == 0) & (nk["U"].isin([20, 40]))].copy()
    nk["r"] = nk["V"] / nk["U"]
    robust = pd.read_csv(RESULTS / "zero_branch_robustness_eta0p05.csv")
    robust = robust.copy()
    spread = robust.groupby(["U", "V", "V_over_U"], as_index=False).agg(
        scale_min=("scale_s_positive", "min"),
        scale_max=("scale_s_positive", "max"),
        scale_current=("scale_s_positive", "first"),
    )
    points = pd.read_csv(RESULTS / "pnas_scale_rule_points_eta0p05.csv")

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 2, figsize=(9.8, 7.2))
        axa, axb, axc, axd = axes.ravel()

        for U in [20.0, 40.0]:
            g = nk[nk["U"] == U].sort_values("r")
            axa.plot(g["r"], g["variance_nk_path"], marker=MARKERS[U],
                     color=COLORS[U], label=rf"$U={U:g}$")
        axa.axvline(R_BOUNDARY, color="0.4", ls=":", lw=1.0)
        axa.set_xlabel(r"$V/U$")
        axa.set_ylabel(r"path variance of $n(\mathbf{k})$")
        axa.legend(frameon=False)
        axa.grid(alpha=0.2)
        panel_label(axa, "(a)")

        spread["relative_spread_pct"] = 100.0 * (
            spread["scale_max"] - spread["scale_min"]
        ) / spread["scale_current"]
        spread["case"] = [rf"$({int(U)},{int(V)})$" for U, V in zip(spread["U"], spread["V"])]
        xpos = np.arange(len(spread))
        bar_colors = ["#6387a8" if U == 8 else "#b6b6b6" for U in spread["U"]]
        axb.bar(xpos, spread["relative_spread_pct"], color=bar_colors,
                edgecolor="0.25", linewidth=0.7)
        axb.set_xticks(xpos)
        axb.set_xticklabels(spread["case"], rotation=35, ha="right")
        axb.text(0.98, 0.94, "seven root-selection rules", transform=axb.transAxes,
                 ha="right", va="top", fontsize=9.5)
        axb.set_xlabel(r"$(U,V)$")
        axb.set_ylabel(r"branch-scale spread (\%)")
        axb.grid(alpha=0.2)
        panel_label(axb, "(b)")

        fit_rows = points[np.isfinite(points["fit_residual"])]
        for U in [20.0, 40.0, 80.0]:
            g = fit_rows[fit_rows["U"] == U].sort_values("r")
            axc.plot(g["r"], g["fit_residual"], marker=MARKERS[U], lw=0,
                     color=COLORS[U], ms=6, label=rf"$U={U:g}$")
        axc.axhline(0, color="0.25", lw=1.0)
        axc.axvline(R_BOUNDARY, color="0.4", ls=":", lw=1.0)
        axc.set_xlabel(r"$V/U$")
        axc.set_ylabel("fit residual in $s$")
        axc.grid(alpha=0.2)
        axc.legend(frameon=False, ncol=1)
        panel_label(axc, "(c)")

        for U in [20.0, 40.0, 80.0]:
            g = points[points["U"] == U].sort_values("r")
            axd.plot(g["r"], 100.0 * g["accepted_fraction"], marker=MARKERS[U],
                     color=COLORS[U], label=rf"$U={U:g}$")
        axd.axhline(90, color="0.5", ls="--", lw=1.0)
        axd.axvline(R_BOUNDARY, color="0.4", ls=":", lw=1.0)
        axd.set_xlabel(r"$V/U$")
        axd.set_ylabel(r"accepted path points (\%)")
        axd.set_ylim(89, 101)
        axd.grid(alpha=0.2)
        panel_label(axd, "(d)")

        fig.subplots_adjust(left=0.11, right=0.985, top=0.98, bottom=0.09,
                            hspace=0.32, wspace=0.28)
        return save(fig, "pnas_supp_extraction_robustness")


def main() -> None:
    outputs = {
        "figure_1": figure1(),
        "figure_2": figure2(),
        "figure_3": figure3(),
        "figure_4": figure4(),
        "supplement_figure_S6": finite_uv_spectral_reorganization(),
        "supplement_extraction_robustness": figure_s_extraction_robustness(),
    }
    (RESULTS / "pnas_main_figure_manifest.json").write_text(
        json.dumps(outputs, indent=2) + "\n"
    )
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
