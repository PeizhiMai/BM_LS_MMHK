#!/usr/bin/env python3
"""Archive the full interaction-axis figures and build compact main versions.

The Supplemental Material keeps the original six-panel Figures 2 and 3.
The main text uses four-panel, two-column layouts:

* Mott side: representative spectra at U/t=8 and 20, the four-U GZ overlay,
  and the interaction-axis coefficient estimate.
* CDW side: representative spectra at V/t=2 and 5, the four-V GZ overlay,
  and the interaction-axis coefficient estimate.

The full figures are regenerated first with the established plotting code, so
this script remains reproducible even after the canonical main-figure files
have been replaced by the compact versions.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import build_prl_split_axis_figures as base


ROOT = Path(__file__).resolve().parents[1]
MAIN_OUT = ROOT / "figures/prl_main"
FULL_OUT = MAIN_OUT / "full_supplement"
MANUSCRIPT_MAIN = ROOT / "manuscript/figures"
MANUSCRIPT_SUPP = ROOT / "manuscript/supp_figures"
MANIFEST = ROOT / "results/compact_main_axis_figures_manifest_20260820.json"

MOTT_MAP_VALUES = [8, 20]
CDW_MAP_VALUES = [2, 5]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_full_figure(stem: str) -> dict[str, str]:
    """Preserve a freshly regenerated six-panel figure for the supplement."""
    FULL_OUT.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_SUPP.mkdir(parents=True, exist_ok=True)
    source_pdf = MAIN_OUT / f"{stem}.pdf"
    source_png = MAIN_OUT / f"{stem}.png"
    full_pdf = FULL_OUT / f"{stem}_full.pdf"
    full_png = FULL_OUT / f"{stem}_full.png"
    supplement_pdf = MANUSCRIPT_SUPP / f"{stem}_full.pdf"
    shutil.copy2(source_pdf, full_pdf)
    shutil.copy2(source_png, full_png)
    shutil.copy2(source_pdf, supplement_pdf)
    return {
        "regenerated_source_at_copy_time": str(source_pdf.relative_to(ROOT)),
        "full_pdf": str(full_pdf.relative_to(ROOT)),
        "full_png": str(full_png.relative_to(ROOT)),
        "supplement_pdf": str(supplement_pdf.relative_to(ROOT)),
        "sha256": _sha256(source_pdf),
    }


def _compact_axes() -> tuple[
    plt.Figure, plt.Axes, plt.Axes, plt.Axes, plt.Axes
]:
    """Return a cropped 2x2 layout without enlarging the retained panels.

    The axes dimensions are copied from the former six-panel 7.15 x 4.635 in
    figure.  Removing one spectral-map column therefore reduces the canvas
    width rather than stretching the four retained panels.
    """
    width = 5.00
    height = 4.635
    fig = plt.figure(figsize=(width, height))

    map_x = 0.46475 / width
    map_width = 1.7232947232947236 / width
    analysis_x = 2.845 / width
    analysis_width = 2.0938030888030887 / width
    bottom_y = 0.085
    top_y = 0.5262790697674418
    panel_height = 0.38372093023255827

    map_top = fig.add_axes([map_x, top_y, map_width, panel_height])
    curve_ax = fig.add_axes([analysis_x, top_y, analysis_width, panel_height])
    map_bottom = fig.add_axes([map_x, bottom_y, map_width, panel_height])
    scale_ax = fig.add_axes(
        [analysis_x, bottom_y, analysis_width, panel_height]
    )
    return fig, map_top, curve_ax, map_bottom, scale_ax


def _format_curve_legend(ax: plt.Axes) -> None:
    handles, labels = ax.get_legend_handles_labels()
    order = [0, 2, 4, 1, 3]
    ax.legend(
        [handles[index] for index in order],
        [labels[index] for index in order],
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


def build_compact_mott(
    u_data,
    u_values: list[int],
    epsilon1: np.ndarray,
    metrics: pd.DataFrame,
) -> dict[str, str]:
    with plt.rc_context(base.STYLE):
        fig, map_top, curve_ax, map_bottom, scale_ax = _compact_axes()
        map_axes = [map_top, map_bottom]
        image = None
        for panel, (ax, value) in zip(["(a)", "(c)"], zip(map_axes, MOTT_MAP_VALUES)):
            source_index = u_values.index(value)
            image = base._spectral_map(
                ax,
                np.asarray(u_data["omega"], dtype=float),
                np.asarray(u_data["rho_G"][source_index], dtype=float),
                np.asarray(u_data["omega_root"][source_index], dtype=float),
                ylim=base.U_YLIMS[value],
                text=rf"$U={value}$",
                vmax=1.5,
                show_ylabel=True,
            )
            base._panel_label(ax, panel, x=-0.175)
        if image is None:
            raise RuntimeError("No Mott-side spectral maps were rendered")
        base._colorbar_above(fig, [map_top], image)

        x = np.arange(121)
        for value in base.U_MAP_VALUES:
            source_index = u_values.index(value)
            curve_ax.plot(
                x,
                np.asarray(u_data["omega_root"][source_index], dtype=float),
                color=base.U_COLORS[value],
                label=rf"$U={value}$",
            )
        s_u40 = float(
            metrics.loc[
                (metrics["axis"] == "Mott") & (metrics["U"] == 40),
                "s_zero_offset",
            ].iloc[0]
        )
        curve_ax.plot(
            x,
            s_u40 * epsilon1,
            color="black",
            ls="--",
            lw=1.05,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
        )
        base._zero_curve_axis(curve_ax)
        curve_ax.yaxis.set_label_coords(-0.10, 0.5)
        _format_curve_legend(curve_ax)
        base._panel_label(curve_ax, "(b)", x=-0.095)

        axis_scale = pd.read_csv(base.AXIS_SCALE_SOURCE)
        u_rows = axis_scale[(axis_scale["U"] > 0) & (axis_scale["V"] == 0)].copy()
        u_rows = u_rows.sort_values("U")
        scale_ax.plot(
            1.0 / u_rows["U"],
            -u_rows["s"],
            "o-",
            color="#c54d3f",
            markerfacecolor="white",
            markeredgewidth=1.5,
        )
        scale_ax.axhline(base.S_U_RESOLUTION, color="black", ls="--", lw=1.35)
        scale_ax.text(
            0.94,
            base.S_U_RESOLUTION + 0.0035,
            r"$4\langle\mathbf{S}_i\!\cdot\!\mathbf{S}_j"
            r"\rangle_{\rm NN,U\to\infty}$",
            transform=scale_ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=9.62,
            color="black",
        )
        scale_ax.set_xlabel(r"$t/U$")
        scale_ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(U,0)$")
        scale_ax.yaxis.set_label_coords(-0.22, 0.5)
        scale_ax.set_xlim(-0.004, 0.132)
        # The refined U=10 point reaches -1.2831.  Keep a small headroom so
        # the validated marker is never clipped by the top spine.
        scale_ax.set_ylim(-1.415, -1.278)
        scale_ax.set_yticks([-1.40, -1.38, -1.36, -1.34, -1.32, -1.30])
        scale_ax.grid(alpha=0.18)
        base._panel_label(scale_ax, "(d)", x=-0.095)
        return base._save(fig, "fig2_mott_zero_mechanism")


def build_compact_cdw(
    v_data: dict[int, np.lib.npyio.NpzFile],
    epsilon1: np.ndarray,
    metrics: pd.DataFrame,
) -> dict[str, str]:
    with plt.rc_context(base.STYLE):
        fig, map_top, curve_ax, map_bottom, scale_ax = _compact_axes()
        map_axes = [map_top, map_bottom]
        image = None
        for panel, (ax, value) in zip(["(a)", "(c)"], zip(map_axes, CDW_MAP_VALUES)):
            record = v_data[value]
            image = base._spectral_map(
                ax,
                np.asarray(record["omega"], dtype=float),
                np.asarray(record["rho_G"], dtype=float),
                np.asarray(record["omega_root"], dtype=float),
                ylim=float(record["ylim"]),
                text=rf"$V={value}$",
                vmax=2.5,
                show_ylabel=True,
            )
            base._panel_label(ax, panel, x=-0.175)
        if image is None:
            raise RuntimeError("No CDW-side spectral maps were rendered")
        base._colorbar_above(fig, [map_top], image)

        x = np.arange(121)
        for value in base.V_MAP_VALUES:
            curve_ax.plot(
                x,
                np.asarray(v_data[value]["omega_root"], dtype=float),
                color=base.V_COLORS[value],
                label=rf"$V={value}$",
            )
        s_v12 = float(
            metrics.loc[
                (metrics["axis"] == "CDW") & (metrics["V"] == 12),
                "s_zero_offset",
            ].iloc[0]
        )
        curve_ax.plot(
            x,
            s_v12 * epsilon1,
            color="black",
            ls="--",
            lw=1.05,
            label=r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}(\mathbf{k})$",
        )
        base._zero_curve_axis(curve_ax)
        curve_ax.yaxis.set_label_coords(-0.10, 0.5)
        _format_curve_legend(curve_ax)
        base._panel_label(curve_ax, "(b)", x=-0.095)

        axis_scale = pd.read_csv(base.AXIS_SCALE_SOURCE)
        v_rows = axis_scale[(axis_scale["U"] == 0) & (axis_scale["V"] > 0)].copy()
        extra_rows = metrics[
            (metrics["axis"] == "CDW") & (metrics["V"].isin([2, 5]))
        ][["V", "s_zero_offset"]].rename(columns={"s_zero_offset": "s"})
        v_rows["s"] = -v_rows["s"]
        v_rows = pd.concat([v_rows[["V", "s"]], extra_rows], ignore_index=True)
        v_rows = v_rows.drop_duplicates("V", keep="last").sort_values("V")
        scale_ax.plot(
            1.0 / v_rows["V"],
            v_rows["s"],
            "o-",
            color="#2d6f9f",
            markerfacecolor="white",
            markeredgewidth=1.5,
        )
        scale_ax.axhline(base.S_V, color="black", ls="--", lw=1.35)
        scale_ax.text(
            0.94,
            base.S_V + 0.00018,
            r"$-8/7$",
            transform=scale_ax.get_yaxis_transform(),
            ha="right",
            va="bottom",
            fontsize=10.27,
            color="black",
        )
        scale_ax.set_xlabel(r"$t/V$")
        scale_ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(0,V)$")
        scale_ax.yaxis.set_label_coords(-0.22, 0.5)
        scale_ax.set_xlim(-0.01, 0.52)
        scale_ax.set_ylim(-1.144, -1.135)
        scale_ax.set_yticks([-1.144, -1.142, -1.140, -1.138, -1.136])
        scale_ax.grid(alpha=0.18)
        base._panel_label(scale_ax, "(d)", x=-0.095)
        return base._save(fig, "fig3_cdw_zero_mechanism")


def main() -> None:
    u_data, u_values, v_data, epsilon1 = base._load_sources()
    metrics = base._axis_metrics(u_data, u_values, v_data, epsilon1)

    # Rebuild and preserve the exact six-panel scientific content first.
    base.build_mott_figure(u_data, u_values, epsilon1, metrics)
    full_mott = _copy_full_figure("fig2_mott_zero_mechanism")
    base.build_cdw_figure(v_data, epsilon1, metrics)
    full_cdw = _copy_full_figure("fig3_cdw_zero_mechanism")

    compact_mott = build_compact_mott(u_data, u_values, epsilon1, metrics)
    compact_cdw = build_compact_cdw(v_data, epsilon1, metrics)

    MANUSCRIPT_MAIN.mkdir(parents=True, exist_ok=True)
    for stem in ("fig2_mott_zero_mechanism", "fig3_cdw_zero_mechanism"):
        shutil.copy2(MAIN_OUT / f"{stem}.pdf", MANUSCRIPT_MAIN / f"{stem}.pdf")

    payload = {
        "main_panel_layout": {
            "figure_2": {
                "a": "U=8 spectral map",
                "b": "U=8,12,20,40 GZ overlay and U=40 reference",
                "c": "U=20 spectral map",
                "d": "estimated s_NN(U,0) versus t/U",
                "removed_original_panels": ["b (U=12 map)", "d (U=40 map)"],
            },
            "figure_3": {
                "a": "V=2 spectral map",
                "b": "V=2,5,8,12 GZ overlay and V=12 reference",
                "c": "V=5 spectral map",
                "d": "estimated s_NN(0,V) versus t/V",
                "removed_original_panels": ["c (V=8 map)", "d (V=12 map)"],
            },
        },
        "full_supplement_figures": {
            "figure_2": full_mott,
            "figure_3": full_cdw,
        },
        "compact_main_figures": {
            "figure_2": {
                **compact_mott,
                "sha256": _sha256(MAIN_OUT / "fig2_mott_zero_mechanism.pdf"),
            },
            "figure_3": {
                **compact_cdw,
                "sha256": _sha256(MAIN_OUT / "fig3_cdw_zero_mechanism.pdf"),
            },
        },
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Compact Fig. 2: {compact_mott['pdf']}")
    print(f"Compact Fig. 3: {compact_cdw['pdf']}")
    print(f"Manifest: {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
