#!/usr/bin/env python3
"""Build finite-t' versions of Figure 2 from the preserved four-figure paper.

The four-figure manuscript (``manuscript/main_prl_style.tex``) uses the
six-panel interaction-axis comparison

    figures/pnas_main/pnas_fig2_interaction_axis_comparison.pdf

as its Figure 2.  This script preserves that panel grammar:

* U-only spectra at U=8 and 20, followed by U=8,20,40 zero curves;
* V-only spectra at V=2 and 5, followed by V=2,5,8 zero curves.

At finite t' the one-scale dashed curve is replaced by the validated
bond-resolved fit

    omega_GZ(k) = s_NN epsilon_1(k) + s_NNN epsilon_2(k),

where epsilon_1=-2(cos kx+cos ky) and
epsilon_2=-4t' cos(kx)cos(ky).  Fits use 120 unique momenta; the terminal
Gamma point is repeated only for plotting.  The original t'=0 artifact is
never overwritten.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_pnas_supplement_figures import (  # noqa: E402
    STYLE,
    _spectral_map,
    panel_label,
    save,
)
from manuscript_figure_style import ZERO_DISPERSION_AXIS_LABEL  # noqa: E402


DATE_TAG = "20260802"
DATA_DIR = (
    ROOT
    / "data/Gcalpath/luttinger_surface_eta0p05_uonly_vonly_finite_tprime_20260802"
)
SOURCE_METRICS = (
    ROOT
    / "results/uonly_vonly_finite_tprime_bond_resolved_eta0p05_20260802.csv"
)
OUT = ROOT / "figures/pnas_main/finite_tprime_versions"
METRICS_OUT = (
    ROOT
    / "results/pnas_fig2_interaction_axis_finite_tprime_metrics_eta0p05_20260802.csv"
)
MANIFEST_OUT = (
    ROOT
    / "results/pnas_fig2_interaction_axis_finite_tprime_manifest_20260802.json"
)

TP_VALUES = (-0.25, -0.4)
U_VALUES = (8, 20, 40)
V_VALUES = (2, 5, 8)
U_COLORS = {8: "#2d6f9f", 20: "#3f8a55", 40: "#c54d3f"}
V_COLORS = {2: "#2d6f9f", 5: "#3f8a55", 8: "#c54d3f"}


def tp_token(tp: float) -> str:
    return str(tp).replace("-", "n").replace(".", "p")


def source_path(U: int, V: int, tp: float) -> Path:
    return DATA_DIR / (
        f"rhoG_LS_U{U}_V{V}_tp{tp_token(tp)}_eta0p05_spectra_and_roots.npz"
    )


def load_group(U: int, V: int, tp: float) -> dict[str, np.ndarray | float | Path]:
    path = source_path(U, V, tp)
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path) as raw:
        group = {
            "omega": np.asarray(raw["omega"], dtype=float).copy(),
            "x": np.asarray(raw["x_path"], dtype=float).copy(),
            "k_path": np.asarray(raw["k_path"], dtype=int).copy(),
            "rho": np.asarray(raw["rho_G"], dtype=float).copy(),
            "root": np.asarray(raw["omega_root"], dtype=float).copy(),
            "U": float(np.asarray(raw["U"]).item()),
            "V": float(np.asarray(raw["V"]).item()),
            "tp": float(np.asarray(raw["tp"]).item()),
            "eta": float(np.asarray(raw["eta"]).item()),
            "path": path,
        }
    if not (
        math.isclose(group["U"], U, abs_tol=1.0e-12)
        and math.isclose(group["V"], V, abs_tol=1.0e-12)
        and math.isclose(group["tp"], tp, abs_tol=1.0e-12)
        and math.isclose(group["eta"], 0.05, abs_tol=1.0e-12)
    ):
        raise ValueError(f"Metadata mismatch in {path}")
    omega = group["omega"]
    rho = group["rho"]
    root = group["root"]
    x = group["x"]
    k_path = group["k_path"]
    if not (
        isinstance(omega, np.ndarray)
        and isinstance(rho, np.ndarray)
        and isinstance(root, np.ndarray)
        and isinstance(x, np.ndarray)
        and isinstance(k_path, np.ndarray)
        and rho.shape == (121, omega.size)
        and root.shape == (121,)
        and x.shape == (121,)
        and k_path.shape == (121, 2)
        and np.isfinite(root).all()
        and np.array_equal(k_path[0], k_path[-1])
        and np.isclose(root[0], root[-1], atol=1.0e-12)
    ):
        raise ValueError(f"Invalid 120-unique/121-plotted dataset in {path}")
    return group


def harmonics(k_path: np.ndarray, tp: float) -> tuple[np.ndarray, np.ndarray]:
    momenta = np.asarray(k_path, dtype=float) * (np.pi / 40.0)
    kx, ky = momenta[:, 0], momenta[:, 1]
    epsilon1 = -2.0 * (np.cos(kx) + np.cos(ky))
    epsilon2 = -4.0 * tp * np.cos(kx) * np.cos(ky)
    return epsilon1, epsilon2


def metrics_row(
    metrics: pd.DataFrame,
    *,
    branch: str,
    interaction: int,
    tp: float,
) -> pd.Series:
    mask = (metrics["branch"] == branch) & np.isclose(metrics["tprime"], tp)
    if branch == "U-only":
        mask &= np.isclose(metrics["U"], interaction) & np.isclose(metrics["V"], 0)
    else:
        mask &= np.isclose(metrics["U"], 0) & np.isclose(metrics["V"], interaction)
    rows = metrics.loc[mask]
    if len(rows) != 1:
        raise ValueError(
            f"Expected one metrics row for {branch}, {interaction}, t'={tp}; "
            f"found {len(rows)}"
        )
    row = rows.iloc[0]
    if not (
        int(row["root_count_unique"]) == 120
        and int(row["root_count_plotted"]) == 121
        and int(row["clean_root_count_plotted"]) == 121
    ):
        raise ValueError(f"Incomplete root audit for {branch}, {interaction}, t'={tp}")
    return row


def fitted_curve(
    group: dict,
    row: pd.Series,
    tp: float,
) -> tuple[np.ndarray, dict[str, float]]:
    """Return a zero-offset NN+NNN fit and its diagnostics."""
    epsilon1, epsilon2 = harmonics(group["k_path"], tp)
    root = np.asarray(group["root"], dtype=float)
    design_unique = np.column_stack([epsilon1[:120], epsilon2[:120]])
    coefficients, _, _, _ = np.linalg.lstsq(
        design_unique,
        root[:120],
        rcond=None,
    )
    prediction = np.column_stack([epsilon1, epsilon2]) @ coefficients
    residual = root[:120] - prediction[:120]
    rmse_unique = float(np.sqrt(np.mean(residual**2)))
    centered = root[:120] - np.mean(root[:120])
    r2 = float(1.0 - np.dot(residual, residual) / np.dot(centered, centered))
    diagnostics = {
        "s_nn": float(coefficients[0]),
        "s_nnn": float(coefficients[1]),
        "delta": 0.0,
        "rmse": rmse_unique,
        "r2": r2,
        "diagnostic_unconstrained_delta": float(row["offset_delta"]),
        "diagnostic_unconstrained_rmse": float(row["bond_rmse"]),
    }
    return prediction, diagnostics


def format_tp(tp: float) -> str:
    return rf"$t'={tp:g}t$"


def build_figure(tp: float, metrics: pd.DataFrame) -> tuple[dict[str, str], list[dict]]:
    u_data = {U: load_group(U, 0, tp) for U in U_VALUES}
    v_data = {V: load_group(0, V, tp) for V in V_VALUES}
    reference_path = np.asarray(u_data[8]["k_path"], dtype=int)
    for group in [*u_data.values(), *v_data.values()]:
        if not np.array_equal(np.asarray(group["k_path"], dtype=int), reference_path):
            raise ValueError("The U-only and V-only momentum paths do not match")

    u_fit_row = metrics_row(metrics, branch="U-only", interaction=40, tp=tp)
    v_fit_row = metrics_row(metrics, branch="V-only", interaction=8, tp=tp)
    u_fit, u_fit_metrics = fitted_curve(u_data[40], u_fit_row, tp)
    v_fit, v_fit_metrics = fitted_curve(v_data[8], v_fit_row, tp)
    # Match the original four-figure Fig. 2 coordinate convention exactly:
    # the three 40-point path segments occupy indices 0--120.  ``x_path`` is
    # a cumulative Euclidean-distance coordinate and therefore must not be
    # combined with the original 0,40,80,120 ticks.
    x = np.arange(121, dtype=float)

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

        im_u = _spectral_map(
            axes[0, 0],
            np.asarray(u_data[8]["omega"], dtype=float),
            np.asarray(u_data[8]["rho"], dtype=float),
            np.asarray(u_data[8]["root"], dtype=float),
            10.0,
            r"$U=8,\ V=0$",
            vmax=1.5,
            label_y=0.40,
            label_framed=False,
        )
        _spectral_map(
            axes[0, 1],
            np.asarray(u_data[20]["omega"], dtype=float),
            np.asarray(u_data[20]["rho"], dtype=float),
            np.asarray(u_data[20]["root"], dtype=float),
            15.0,
            r"$U=20,\ V=0$",
            vmax=1.5,
            label_y=0.40,
            label_framed=False,
        )
        axes[0, 1].set_ylabel("")

        for U in U_VALUES:
            axes[0, 2].plot(
                x,
                np.asarray(u_data[U]["root"], dtype=float),
                color=U_COLORS[U],
                label=rf"$U={U}$",
                zorder=2,
            )
        axes[0, 2].plot(
            x,
            u_fit,
            color="black",
            ls="--",
            lw=1.6,
            label=(
                r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}"
                r"+s_{\mathrm{NNN}}\varepsilon_{\mathrm{NNN}}$"
            ),
            zorder=3,
        )

        im_v = _spectral_map(
            axes[1, 0],
            np.asarray(v_data[2]["omega"], dtype=float),
            np.asarray(v_data[2]["rho"], dtype=float),
            np.asarray(v_data[2]["root"], dtype=float),
            11.5,
            r"$U=0,\ V=2$",
            vmax=2.5,
            label_y=0.40,
            label_framed=False,
        )
        _spectral_map(
            axes[1, 1],
            np.asarray(v_data[5]["omega"], dtype=float),
            np.asarray(v_data[5]["rho"], dtype=float),
            np.asarray(v_data[5]["root"], dtype=float),
            25.0,
            r"$U=0,\ V=5$",
            vmax=2.5,
            label_y=0.40,
            label_framed=False,
        )
        axes[1, 1].set_ylabel("")

        for V in V_VALUES:
            axes[1, 2].plot(
                x,
                np.asarray(v_data[V]["root"], dtype=float),
                color=V_COLORS[V],
                label=rf"$V={V}$",
                zorder=2,
            )
        axes[1, 2].plot(
            x,
            v_fit,
            color="black",
            ls="--",
            lw=1.6,
            label=(
                r"$s_{\mathrm{NN}}\varepsilon_{\mathrm{NN}}"
                r"+s_{\mathrm{NNN}}\varepsilon_{\mathrm{NNN}}$"
            ),
            zorder=3,
        )

        for row_index in range(2):
            line_ax = axes[row_index, 2]
            line_ax.axhline(0.0, color="0.55", lw=0.8)
            line_ax.set_xlim(0, 120)
            line_ax.set_ylim(-7.2, 7.2)
            line_ax.set_xticks([0, 40, 80, 120])
            line_ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
            line_ax.set_ylabel(ZERO_DISPERSION_AXIS_LABEL)
            line_ax.grid(alpha=0.18)
            line_ax.legend(
                frameon=False,
                ncol=1,
                loc="upper center",
                # The original anchor was x=0.52.  Moving to x=0.55 is the
                # nearest rightward shift for which the full equation legend
                # does not intersect any of the four plotted curves in either
                # panel, for either finite-t' dataset.
                bbox_to_anchor=(0.55, 0.985),
                fontsize=9.1,
                handlelength=1.6,
                labelspacing=0.12,
                borderaxespad=0.15,
            )

        for index, ax in enumerate(axes.ravel()):
            panel_label(ax, f"({chr(97 + index)})", framed=False, outside_top_tick=True)

        axes[0, 2].text(
            0.955,
            0.065,
            rf"$V=0,\quad t'={tp:g}t$",
            transform=axes[0, 2].transAxes,
            ha="right",
            va="bottom",
            fontsize=11.7,
            fontweight="bold",
        )
        axes[1, 2].text(
            0.955,
            0.065,
            rf"$U=0,\quad t'={tp:g}t$",
            transform=axes[1, 2].transAxes,
            ha="right",
            va="bottom",
            fontsize=11.7,
            fontweight="bold",
        )

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
            colorbar.ax.tick_params(labelsize=14, length=7, width=1.5, pad=2)
            colorbar.ax.xaxis.label.set_size(11.5)

        stem = f"pnas_fig2_interaction_axis_comparison_tp{tp_token(tp)}"
        outputs = save(fig, stem, output_dir=OUT)

    metric_records = []
    for branch, interaction, fit_metrics in (
        ("U-only", 40, u_fit_metrics),
        ("V-only", 8, v_fit_metrics),
    ):
        metric_records.append(
            {
                "tprime": tp,
                "axis": branch,
                "fit_interaction": interaction,
                **fit_metrics,
                "unique_fit_points": 120,
                "plotted_points": 121,
                "fit_form": "omega_GZ=s_nn*epsilon1+s_nnn*epsilon2",
                "figure_pdf": outputs["pdf"],
            }
        )
    return outputs, metric_records


def main() -> None:
    if not SOURCE_METRICS.is_file():
        raise FileNotFoundError(SOURCE_METRICS)
    metrics = pd.read_csv(SOURCE_METRICS)
    required_columns = {
        "branch",
        "U",
        "V",
        "tprime",
        "root_count_unique",
        "root_count_plotted",
        "clean_root_count_plotted",
        "s_nn",
        "s_nnn",
        "offset_delta",
        "bond_rmse",
        "bond_r2",
    }
    missing = required_columns - set(metrics.columns)
    if missing:
        raise ValueError(f"Missing source metrics columns: {sorted(missing)}")

    outputs_by_tp: dict[str, dict[str, str]] = {}
    metric_records: list[dict] = []
    for tp in TP_VALUES:
        outputs, records = build_figure(tp, metrics)
        outputs_by_tp[str(tp)] = outputs
        metric_records.extend(records)

    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metric_records).to_csv(METRICS_OUT, index=False)

    captions = {
        str(tp): (
            "Approach to the two interaction-axis limits at "
            f"t'={tp:g}t. (A,B) U-only spectral maps at U=8 and 20; "
            "white curves are gap-interior Green-function zeros. (C) "
            "U=8,20,40 zero dispersions and the zero-offset NN+NNN fit "
            "to U=40. (D,E) V-only spectra at V=2 and 5. (F) V=2,5,8 "
            "zero dispersions and the zero-offset NN+NNN fit to V=8. "
            "Fits use 120 unique momenta; the terminal Gamma point is "
            "repeated only for plotting. Color scales are fixed within each row."
        )
        for tp in TP_VALUES
    }
    manifest = {
        "date_tag": DATE_TAG,
        "purpose": "finite-tprime variants of Figure 2 in the preserved four-figure paper",
        "source_figure": "figures/pnas_main/pnas_fig2_interaction_axis_comparison.pdf",
        "source_manuscript": "manuscript/main_prl_style.tex",
        "source_metrics": str(SOURCE_METRICS.relative_to(ROOT)),
        "model_convention": "omega_GZ(k)=s_nn*epsilon1(k)+s_nnn*epsilon2(k)",
        "epsilon1": "-2*(cos(kx)+cos(ky))",
        "epsilon2": "-4*tprime*cos(kx)*cos(ky)",
        "fit_points_unique": 120,
        "plot_points_with_repeated_terminal_gamma": 121,
        "spectral_windows_omega_over_t": {
            "panel_a_U8": [-10.0, 10.0],
            "panel_b_U20": [-15.0, 15.0],
            "panel_d_V2": [-11.5, 11.5],
            "panel_e_V5": [-25.0, 25.0],
        },
        "outputs": outputs_by_tp,
        "metrics_csv": str(METRICS_OUT.relative_to(ROOT)),
        "suggested_captions": captions,
        "original_overwritten": False,
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n")

    for output in outputs_by_tp.values():
        pdf = ROOT / output["pdf"]
        png = ROOT / output["png"]
        if pdf.read_bytes()[:4] != b"%PDF" or png.stat().st_size == 0:
            raise RuntimeError(f"Invalid output pair: {pdf}, {png}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
