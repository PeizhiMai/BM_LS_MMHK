#!/usr/bin/env python3
"""Build supplemental figures that must not depend on legacy/manual artwork.

The figures in this module are reconstructed from machine-readable project
outputs:

* the strong-coupling asymptotic comparison moved from the former main
  Figure 1;
* the on-site-only and nearest-neighbor-only spectral sequences and their
  fixed-span occupied-band snapshots;
* the finite-interaction spectral sequence moved from the former main
  Figure 2 after the interaction-axis comparison was promoted;
* the one-page root-branch audit from stored root candidates and spectra;
* the frustrated-hopping robustness figure from the reproduced Lanczos NPZ.

The resulting files have distinct PNAS-supplement names so that the manuscript
cannot silently fall back to the early hand-assembled figures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from manuscript_figure_style import (
    ZERO_DISPERSION_AXIS_LABEL,
    outside_panel_label,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_zero_branch_tracking import AUDIT_CASES, audit_group, load_group  # noqa: E402


RESULTS = ROOT / "results"
DATA = ROOT / "data" / "Gcalpath"
OUT = ROOT / "figures" / "pnas_supplement"
OUT.mkdir(parents=True, exist_ok=True)

STYLE = {
    "font.family": "Arial",
    "font.size": 10.5,
    "axes.labelsize": 11.5,
    "axes.titlesize": 11.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "axes.linewidth": 1.0,
    "lines.linewidth": 1.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def save(
    fig: plt.Figure,
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
    return {
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
    }


def panel_label(
    ax: plt.Axes,
    label: str,
    *,
    color: str = "black",
    framed: bool = True,
    outside_top_tick: bool = False,
) -> None:
    # Preserve the old keyword arguments for caller compatibility while
    # enforcing one manuscript-wide placement rule.
    del framed, outside_top_tick
    outside_panel_label(ax, label, color=color, fontsize=11.5)


def asymptotic_mechanisms_figure() -> dict[str, str]:
    """Build the former main Figure 1 as supplemental Figure S1."""
    from build_pnas_manuscript_figures import asymptotic_mechanisms

    return asymptotic_mechanisms(
        output_dir=OUT,
        stem="supp_figS1_asymptotic_mechanisms",
    )


def root_audit_figure() -> dict[str, str]:
    """Place all six candidate-root audits on one reproducible page."""
    rows_out: list[pd.DataFrame] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(3, 2, figsize=(10.2, 10.2), squeeze=False)
        legend_handles = None
        legend_labels = None
        for idx, ((U, V), ax) in enumerate(zip(AUDIT_CASES, axes.ravel())):
            rows, branches, candidates = audit_group(float(U), float(V))
            df, _ = load_group(float(U), float(V))
            rows_out.append(rows)
            x = df["x_path"].to_numpy(float)
            for xpos, candidate_row in zip(x, candidates):
                if candidate_row:
                    ax.scatter(
                        [xpos] * len(candidate_row),
                        candidate_row,
                        s=4,
                        color="0.66",
                        alpha=0.52,
                        linewidths=0,
                        zorder=1,
                    )
            ax.plot(x, branches["current_csv"], color="white", lw=4.0, zorder=3)
            ax.plot(x, branches["current_csv"], color="black", lw=1.8,
                    label="production branch", zorder=4)
            ax.plot(x, branches["local_min_rho"], color="#2d6f9f", lw=1.0,
                    label=r"minimum-$\rho_G$")
            ax.plot(x, branches["local_nearest_reference"], color="#d17b25", lw=1.0,
                    label="nearest reference")
            ax.plot(x, branches["dp_smooth_1"], color="#3f8a55", lw=1.0,
                    label="smooth DP")
            ax.plot(x, branches["dp_reverse_smooth_1"], color="#b84846", lw=1.0,
                    ls="--", label="reverse path")
            ax.axhline(0.0, color="0.82", lw=0.7)
            ax.set_xlim(x[0], x[-1])
            ax.set_xticks([x[0], x[40], x[80], x[120]])
            ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
            ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
            ax.set_title(rf"$U={U:g},\ V={V:g}$")
            ax.grid(alpha=0.16)
            panel_label(ax, f"({chr(97 + idx)})")
            if legend_handles is None:
                legend_handles, legend_labels = ax.get_legend_handles_labels()
        if legend_handles:
            fig.legend(
                legend_handles,
                legend_labels,
                frameon=False,
                ncol=5,
                loc="upper center",
                bbox_to_anchor=(0.52, 1.01),
                fontsize=8.8,
            )
        fig.supxlabel(r"$\Gamma$--X--M--$\Gamma$ path")
        fig.subplots_adjust(left=0.085, right=0.99, bottom=0.07, top=0.94,
                            hspace=0.31, wspace=0.20)

        audit_csv = RESULTS / "pnas_supp_zero_branch_audit_eta0p05.csv"
        pd.concat(rows_out, ignore_index=True).to_csv(audit_csv, index=False)
        outputs = save(fig, "pnas_supp_figS8_zero_branch_candidate_audit_eta0p05")
        outputs["audit_csv"] = str(audit_csv.relative_to(ROOT))
        return outputs


def _spectral_map(
    ax: plt.Axes,
    omega: np.ndarray,
    rho: np.ndarray,
    roots: np.ndarray,
    ylim: float,
    label: str,
    *,
    vmax: float = 1.5,
    label_y: float = 0.08,
    label_framed: bool = True,
    label_fontsize: float = 10.5,
) -> plt.AxesImage:
    mask = np.abs(omega) <= ylim
    image = np.maximum(rho[:, mask], 0.0).T
    im = ax.imshow(
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
    ax.plot(np.arange(121), roots, color="white", lw=1.5)
    ax.axhline(0.0, color="black", lw=0.8, ls="--")
    for xpos in (40, 80):
        ax.axvline(xpos, color="black", lw=0.7, ls="--", alpha=0.7)
    ax.set_xlim(0, 120)
    ax.set_ylim(-ylim, ylim)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.set_ylabel(r"$\omega/t$")
    ax.text(
        0.035,
        label_y,
        label,
        transform=ax.transAxes,
        color="white",
        ha="left",
        va="bottom",
        fontsize=label_fontsize,
        fontweight="bold",
        bbox=(
            {"facecolor": "black", "edgecolor": "none", "alpha": 0.25, "pad": 2}
            if label_framed
            else None
        ),
    )
    return im


def interaction_axis_comparison_figure(
    *,
    output_dir: Path = ROOT / "figures" / "pnas_main",
    stem: str = "pnas_fig2_interaction_axis_comparison",
    metrics_path: Path | None = None,
) -> dict[str, str]:
    """Build main Figure 2 from the U-only and V-only sequences."""
    u_source = (
        DATA
        / "luttinger_surface_eta0p05"
        / "luttinger_tp0_eta0p05_spectra_and_roots.npz"
    )
    v_directory = DATA / "luttinger_surface_eta0p05_U0_finiteV"
    u_data = np.load(u_source)
    u_values = [int(value) for value in u_data["U"]]
    u_omega = np.asarray(u_data["omega"], dtype=float)
    u_rho = np.asarray(u_data["rho_G"], dtype=float)
    u_roots = np.asarray(u_data["omega_root"], dtype=float)
    k_path = np.asarray(u_data["k_path"], dtype=float)

    v_values = [2, 5, 8]
    v_data = {
        V: np.load(
            v_directory
            / f"rhoG_LS_U0_V{V}_tp0_eta0p05_spectra_and_roots.npz"
        )
        for V in v_values
    }
    for V, data in v_data.items():
        if not np.array_equal(np.asarray(data["k_path"], dtype=float), k_path):
            raise ValueError(f"U-only and V={V} paths do not match")

    kx = k_path[:, 0] * np.pi / 40.0
    ky = k_path[:, 1] * np.pi / 40.0
    epsilon1 = -2.0 * (np.cos(kx) + np.cos(ky))
    x = np.arange(len(epsilon1))

    def fit_scale(root: np.ndarray) -> tuple[float, float, np.ndarray]:
        finite = np.isfinite(root)
        alpha = -float(
            np.dot(epsilon1[finite], root[finite])
            / np.dot(epsilon1[finite], epsilon1[finite])
        )
        fitted = -alpha * epsilon1
        rmse = float(np.sqrt(np.mean((root[finite] - fitted[finite]) ** 2)))
        return alpha, rmse, fitted

    def diagnostic_unconstrained_offset(root: np.ndarray) -> float:
        finite = np.isfinite(root)
        design = np.column_stack([-epsilon1[finite], np.ones(finite.sum())])
        _, offset = np.linalg.lstsq(design, root[finite], rcond=None)[0]
        return float(offset)

    idx_u40 = u_values.index(40)
    alpha_u, rmse_u, fit_u = fit_scale(u_roots[idx_u40])
    diagnostic_offset_u = diagnostic_unconstrained_offset(u_roots[idx_u40])
    roots_v = {
        V: np.asarray(v_data[V]["omega_root"], dtype=float) for V in v_values
    }
    alpha_v, rmse_v, fit_v = fit_scale(roots_v[8])
    diagnostic_offset_v = diagnostic_unconstrained_offset(roots_v[8])

    metrics = pd.DataFrame(
        [
            {
                "axis": "U-only",
                "fit_interaction": 40,
                "alpha": alpha_u,
                "offset_in_model": False,
                "diagnostic_unconstrained_offset": diagnostic_offset_u,
                "rmse": rmse_u,
                "fit_form": "omega_GZ=-s*epsilon1",
                "source": str(u_source.relative_to(ROOT)),
            },
            {
                "axis": "V-only",
                "fit_interaction": 8,
                "alpha": alpha_v,
                "offset_in_model": False,
                "diagnostic_unconstrained_offset": diagnostic_offset_v,
                "rmse": rmse_v,
                "fit_form": "omega_GZ=-s*epsilon1",
                "source": str(
                    (
                        v_directory
                        / "rhoG_LS_U0_V8_tp0_eta0p05_spectra_and_roots.npz"
                    ).relative_to(ROOT)
                ),
            },
        ]
    )
    if metrics_path is None:
        metrics_path = RESULTS / "pnas_fig2_axis_fit_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    u_colors = {8: "#2d6f9f", 12: "#d17b25", 20: "#3f8a55", 40: "#c54d3f"}
    v_colors = {2: "#2d6f9f", 5: "#3f8a55", 8: "#c54d3f"}
    ylims_u = {8: 8.0, 20: 15.0}

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 3, figsize=(10.2, 6.65))
        fig.subplots_adjust(
            left=0.072,
            right=0.992,
            bottom=0.085,
            top=0.91,
            wspace=0.27,
            hspace=0.42,
        )

        idx_u8 = u_values.index(8)
        idx_u20 = u_values.index(20)
        im_u = _spectral_map(
            axes[0, 0],
            u_omega,
            u_rho[idx_u8],
            u_roots[idx_u8],
            ylims_u[8],
            r"$U=8,\ V=0$",
            vmax=1.5,
            label_y=0.40,
            label_framed=False,
        )
        _spectral_map(
            axes[0, 1],
            u_omega,
            u_rho[idx_u20],
            u_roots[idx_u20],
            ylims_u[20],
            r"$U=20,\ V=0$",
            vmax=1.5,
            label_y=0.40,
            label_framed=False,
        )
        axes[0, 1].set_ylabel("")

        for U in (8, 20, 40):
            idx = u_values.index(U)
            axes[0, 2].plot(
                x,
                u_roots[idx],
                color=u_colors[U],
                label=rf"$U={U}$",
                zorder=2,
            )
        axes[0, 2].plot(
            x,
            fit_u,
            color="black",
            ls="--",
            lw=1.6,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
            zorder=3,
        )

        im_v = _spectral_map(
            axes[1, 0],
            np.asarray(v_data[2]["omega"], dtype=float),
            np.asarray(v_data[2]["rho_G"], dtype=float),
            roots_v[2],
            float(v_data[2]["ylim"]),
            r"$U=0,\ V=2$",
            vmax=float(v_data[2]["color_vmax"]),
            label_y=0.40,
            label_framed=False,
        )
        _spectral_map(
            axes[1, 1],
            np.asarray(v_data[5]["omega"], dtype=float),
            np.asarray(v_data[5]["rho_G"], dtype=float),
            roots_v[5],
            float(v_data[5]["ylim"]),
            r"$U=0,\ V=5$",
            vmax=float(v_data[5]["color_vmax"]),
            label_y=0.40,
            label_framed=False,
        )
        axes[1, 1].set_ylabel("")

        for V in v_values:
            axes[1, 2].plot(
                x,
                roots_v[V],
                color=v_colors[V],
                label=rf"$V={V}$",
                zorder=2,
            )
        axes[1, 2].plot(
            x,
            fit_v,
            color="black",
            ls="--",
            lw=1.6,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
            zorder=3,
        )

        for row in range(2):
            line_ax = axes[row, 2]
            line_ax.axhline(0.0, color="0.55", lw=0.8)
            line_ax.set_xlim(0, 120)
            line_ax.set_ylim(-6.2, 6.2 if row == 0 else 6.2)
            line_ax.set_xticks([0, 40, 80, 120])
            line_ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
            line_ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
            line_ax.grid(alpha=0.18)
            line_ax.legend(
                frameon=False,
                ncol=1,
                loc="upper center",
                bbox_to_anchor=(0.52, 0.985),
                fontsize=11.55,
                handlelength=1.6,
                labelspacing=0.12,
                borderaxespad=0.15,
            )

        for idx, ax in enumerate(axes.ravel()):
            panel_label(
                ax,
                f"({chr(97 + idx)})",
                framed=False,
                outside_top_tick=True,
            )

        axes[0, 2].text(
            0.955,
            0.065,
            r"$V=0$",
            transform=axes[0, 2].transAxes,
            ha="right",
            va="bottom",
            fontsize=12.5,
            fontweight="bold",
        )
        axes[1, 2].text(
            0.955,
            0.065,
            r"$U=0$",
            transform=axes[1, 2].transAxes,
            ha="right",
            va="bottom",
            fontsize=12.5,
            fontweight="bold",
        )

        # Compact row-specific color bars preserve the display conventions of
        # the original U-only panel while retaining the wider V-only scale.
        pos_a = axes[0, 0].get_position()
        pos_b = axes[0, 1].get_position()
        pos_d = axes[1, 0].get_position()
        pos_e = axes[1, 1].get_position()
        cax_u = fig.add_axes([pos_a.x0, pos_a.y1 + 0.012, pos_b.x1 - pos_a.x0, 0.012])
        cax_v = fig.add_axes([pos_d.x0, pos_d.y1 + 0.012, pos_e.x1 - pos_d.x0, 0.012])
        cb_u = fig.colorbar(im_u, cax=cax_u, orientation="horizontal")
        cb_v = fig.colorbar(im_v, cax=cax_v, orientation="horizontal")
        for colorbar in (cb_u, cb_v):
            colorbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=1)
            colorbar.ax.xaxis.set_ticks_position("top")
            colorbar.ax.xaxis.set_label_position("top")
            colorbar.ax.tick_params(
                labelsize=14,
                length=7,
                width=1.5,
                pad=2,
            )
            colorbar.ax.xaxis.label.set_size(11.5)

        outputs = save(fig, stem, output_dir=output_dir)
        outputs["fit_metrics_csv"] = str(metrics_path.relative_to(ROOT))
        return outputs


def finite_uv_spectral_reorganization_figure() -> dict[str, str]:
    """Generate the expanded finite-interaction sequence as Fig. S6."""
    from build_pnas_manuscript_figures import (  # noqa: E402
        finite_uv_spectral_reorganization,
    )

    return finite_uv_spectral_reorganization(
        output_dir=OUT,
        stem="supp_figS6_finite_uv_spectral_reorganization",
    )


def tprime_figure() -> dict[str, str]:
    """Replot the reproduced t'=-0.25 data without any manual notebook figure."""
    from build_prl_split_axis_figures import (  # noqa: E402
        STYLE as SPLIT_AXIS_STYLE,
        _colorbar_above as split_colorbar_above,
        _panel_label as split_panel_label,
        _spectral_map as split_spectral_map,
        _zero_curve_axis as split_zero_curve_axis,
    )

    source = DATA / "luttinger_surface_eta0p05" / "luttinger_tpn25_eta0p05_spectra_and_roots.npz"
    z = np.load(source)
    omega = np.asarray(z["omega"], dtype=float)
    rho = np.asarray(z["rho_G"], dtype=float)
    roots = np.asarray(z["omega_root"], dtype=float)
    k_path = np.asarray(z["k_path"], dtype=float)
    u_values = [int(value) for value in z["U"]]
    ylims = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
    colors = {8: "#2d6f9f", 12: "#d17b25", 20: "#3f8a55", 40: "#c54d3f"}

    with plt.rc_context(SPLIT_AXIS_STYLE):
        # Match main-text Fig. 2 exactly: four spectral maps in a compact
        # 2x2 block and two vertically aligned analysis panels in column 3.
        fig = plt.figure(figsize=(7.15, 4.635))
        outer = fig.add_gridspec(
            1,
            2,
            width_ratios=[2.0, 1.08],
            wspace=0.22,
        )
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

        last_im = None
        map_values = [8, 12, 20, 40]
        for idx, (ax, U) in enumerate(zip(map_axes, map_values)):
            source_idx = u_values.index(U)
            last_im = split_spectral_map(
                ax,
                omega,
                rho[source_idx],
                roots[source_idx],
                ylim=ylims[U],
                text=rf"$U={U}$",
                vmax=1.5,
                show_ylabel=idx % 2 == 0,
            )
            split_panel_label(ax, f"({chr(97 + idx)})")
        if last_im is None:
            raise RuntimeError("No frustrated-hopping spectral maps were rendered")
        split_colorbar_above(fig, map_axes, last_im)

        x = np.arange(121)
        for U in map_values:
            source_idx = u_values.index(U)
            overlay_ax.plot(x, roots[source_idx], color=colors[U], label=rf"$U={U}$")
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

        idx40 = u_values.index(40)
        kx = k_path[:, 0] * np.pi / 40.0
        ky = k_path[:, 1] * np.pi / 40.0
        epsilon1 = -2.0 * (np.cos(kx) + np.cos(ky))
        epsilon2 = np.cos(kx) * np.cos(ky)  # -4t' cos(kx)cos(ky), t'=-0.25
        design = np.column_stack([epsilon1, epsilon2, np.ones(len(epsilon1))])
        s_nn, s_nnn, offset = np.linalg.lstsq(design, roots[idx40], rcond=None)[0]
        reference = design @ np.array([s_nn, s_nnn, offset])

        # Leading large-U spin model: J2/J1=(t'/t)^2=1/16.  Importing here
        # avoids making the rest of the supplemental builder depend on scipy.
        from fit_tpn25_zero_dispersion import solve_j1j2  # noqa: E402

        spin = solve_j1j2(-0.25)
        spin_reference = 4.0 * spin.c1 * epsilon1 + 4.0 * spin.c2 * epsilon2

        fit_ax.plot(x, roots[idx40], color=colors[40], label=r"$U=40$ GZ")
        fit_ax.plot(
            x,
            reference,
            color="#1b6ca8",
            ls="--",
            label=r"NN+NNN fit",
        )
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

        return save(fig, "supp_figS13_tpn25_reproduced")


def main() -> None:
    from build_pnas_spectral_sequence_supplement import build_all

    spectral_sequences = build_all()
    manifest = {
        "supplement_figure_S1": asymptotic_mechanisms_figure(),
        **spectral_sequences,
        "supplement_figure_S6": finite_uv_spectral_reorganization_figure(),
        "supplement_figure_S8": root_audit_figure(),
        "supplement_figure_S13": tprime_figure(),
    }
    output = RESULTS / "pnas_supplement_figure_manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
