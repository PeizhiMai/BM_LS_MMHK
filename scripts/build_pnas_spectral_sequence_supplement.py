#!/usr/bin/env python3
"""Build the occupied-band spectral figures retained in the SI.

The complete on-site-only and nearest-neighbor-only spectra now appear in
main-text Figs. 2 and 3 and are therefore not duplicated in the supplement.
The two retained figures show occupied-band crops.  The Mott-side figure uses
a common 10t vertical span, whereas the CDW-side figure uses a common 3t span
and an extended color range to resolve the narrow high-intensity ridge.  Each
absolute-energy window is centered on the significant lower-band weight.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from manuscript_figure_style import outside_panel_label


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Gcalpath"
OUT = ROOT / "figures" / "pnas_supplement"
RESULTS = ROOT / "results"

U_SOURCE = (
    DATA
    / "luttinger_surface_eta0p05"
    / "luttinger_tp0_eta0p05_spectra_and_roots.npz"
)
V_SOURCE_DIR = DATA / "luttinger_surface_eta0p05_U0_finiteV"
RAW_DATA = DATA / "Lanczos_raw_data"
U40_LOWER_EXTENSION = (
    DATA
    / "luttinger_surface_eta0p05"
    / "luttinger_tp0_U40_eta0p05_lower_frequency_extension.npz"
)

U_VALUES = (8, 12, 20, 40)
# V=12 is the requested representative point above V=8.
V_VALUES = (2, 5, 8, 12)
U_FULL_YLIM = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
U_VMAX = 1.5
V_VMAX = 2.5
U_LOWER_WINDOW_SPAN = 10.0
V_LOWER_WINDOW_SPAN = 3.0
V_LOWER_VMAX = 15.0
LOWER_SUPPORT_FRACTION = 0.01

STYLE = {
    "font.family": "Arial",
    "font.size": 10.5,
    "axes.labelsize": 12.5,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.linewidth": 1.05,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


@dataclass
class Spectrum:
    interaction_name: str
    interaction_value: int
    omega: np.ndarray
    rho: np.ndarray
    root: np.ndarray
    full_ylim: float
    source: Path
    auxiliary_source: Path | None = None


def _copy_array(data: np.lib.npyio.NpzFile, key: str) -> np.ndarray:
    return np.asarray(data[key], dtype=float).copy()


def _load_or_generate_u40_lower_extension(
    base_omega_min: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Extend S5(d) below the old grid edge so its band can be centered."""
    if U40_LOWER_EXTENSION.exists():
        with np.load(U40_LOWER_EXTENSION) as data:
            omega = _copy_array(data, "omega")
            rho = _copy_array(data, "rho_G")
            eta = float(np.asarray(data["eta"]).item())
        if (
            rho.shape == (121, omega.size)
            and omega.size > 0
            and float(omega[-1]) < base_omega_min
            and np.isclose(eta, 0.05)
        ):
            return omega, rho

    from reproduce_luttinger_figures import (
        continued_fraction_values,
        default_k_path,
        param_label,
        parse_green_file,
    )

    step = 0.01
    omega = np.arange(-26.0, base_omega_min, step, dtype=float)
    rho = np.zeros((121, omega.size), dtype=float)
    parse_cache = {}
    for k_idx, (kx, ky) in enumerate(default_k_path()):
        components = []
        for kind in ("Gh", "Gp"):
            path = RAW_DATA / (
                f"L4x4Nup8Ndn8U40V0tp0f{kx}x{ky}Q0x0_{kind}.dat"
            )
            if path not in parse_cache:
                parse_cache[path] = parse_green_file(path, q_target=(0, 0))
            components.append(
                continued_fraction_values(
                    parse_cache[path],
                    omega,
                    eta=0.05,
                    steps_max=1000,
                    coordination=4,
                )
            )
        rho[k_idx] = -2.0 * (components[0] + components[1]).imag

    U40_LOWER_EXTENSION.parent.mkdir(parents=True, exist_ok=True)
    temporary = U40_LOWER_EXTENSION.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        omega=omega,
        rho_G=rho,
        U=np.array(40),
        V=np.array(0),
        tp=np.array(0.0),
        eta=np.array(0.05),
        steps_max=np.array(1000),
        q=np.array((0, 0)),
        coordination=np.array(4),
    )
    temporary.replace(U40_LOWER_EXTENSION)
    return omega, rho


def load_u_records() -> list[Spectrum]:
    with np.load(U_SOURCE) as data:
        stored_u = np.asarray(data["U"], dtype=int)
        omega = _copy_array(data, "omega")
        rho = _copy_array(data, "rho_G")
        roots = _copy_array(data, "omega_root")
    records: list[Spectrum] = []
    for U in U_VALUES:
        matches = np.where(stored_u == U)[0]
        if matches.size != 1:
            raise ValueError(f"Expected one U={U} row in {U_SOURCE}")
        idx = int(matches[0])
        record_omega = omega
        record_rho = rho[idx]
        auxiliary_source = None
        if U == 40:
            extension_omega, extension_rho = (
                _load_or_generate_u40_lower_extension(float(omega[0]))
            )
            record_omega = np.concatenate((extension_omega, omega))
            record_rho = np.concatenate((extension_rho, rho[idx]), axis=1)
            auxiliary_source = U40_LOWER_EXTENSION
        records.append(
            Spectrum(
                interaction_name="U",
                interaction_value=U,
                omega=record_omega,
                rho=record_rho,
                root=roots[idx],
                full_ylim=U_FULL_YLIM[U],
                source=U_SOURCE,
                auxiliary_source=auxiliary_source,
            )
        )
    return records


def load_v_records() -> list[Spectrum]:
    records: list[Spectrum] = []
    for V in V_VALUES:
        source = (
            V_SOURCE_DIR
            / f"rhoG_LS_U0_V{V}_tp0_eta0p05_spectra_and_roots.npz"
        )
        if not source.exists():
            raise FileNotFoundError(source)
        with np.load(source) as data:
            eta = float(np.asarray(data["eta"]).item())
            if not np.isclose(eta, 0.05):
                raise ValueError(f"Expected eta=0.05 in {source}, found {eta}")
            records.append(
                Spectrum(
                    interaction_name="V",
                    interaction_value=V,
                    omega=_copy_array(data, "omega"),
                    rho=_copy_array(data, "rho_G"),
                    root=_copy_array(data, "omega_root"),
                    full_ylim=float(np.asarray(data["ylim"]).item()),
                    source=source,
                )
            )
    return records


def _interpolate_missing_rows(values: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Interpolate absent path rows for raster display only."""
    output = np.asarray(values, dtype=float).copy()
    missing = np.where(~np.isfinite(output).all(axis=1))[0].tolist()
    for idx in missing:
        if 0 < idx < output.shape[0] - 1:
            output[idx] = 0.5 * (output[idx - 1] + output[idx + 1])
        elif idx == 0:
            output[idx] = output[idx + 1]
        else:
            output[idx] = output[idx - 1]
    return output, missing


def _interpolate_root(root: np.ndarray) -> np.ndarray:
    output = np.asarray(root, dtype=float).copy()
    missing = np.where(~np.isfinite(output))[0]
    finite = np.where(np.isfinite(output))[0]
    if missing.size and finite.size:
        output[missing] = np.interp(missing, finite, output[finite])
    return output


def _decorate_path_axis(ax: plt.Axes) -> None:
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 40, 80, 120])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    for xpos in (40, 80):
        ax.axvline(xpos, color="black", lw=0.85, ls="--", alpha=0.72)


def _panel_label(ax: plt.Axes, panel_index: int) -> None:
    outside_panel_label(
        ax,
        f"({chr(97 + panel_index)})",
        fontsize=12,
    )


def _save(fig: plt.Figure, stem: str) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return {
        "pdf": str(pdf.relative_to(ROOT)),
        "png": str(png.relative_to(ROOT)),
    }


def _full_sequence(
    records: list[Spectrum],
    *,
    fixed_zero_interaction: str,
    vmax: float,
    stem: str,
) -> tuple[dict[str, str], list[dict]]:
    metadata: list[dict] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.9))
        fig.subplots_adjust(
            left=0.085,
            right=0.992,
            bottom=0.145,
            top=0.985,
            wspace=0.22,
            hspace=0.30,
        )
        last_image = None
        for idx, (ax, record) in enumerate(zip(axes.ravel(), records)):
            ylim = record.full_ylim
            mask = np.abs(record.omega) <= ylim + 1.0e-12
            rho, missing_rows = _interpolate_missing_rows(record.rho)
            image = np.maximum(rho[:, mask], 0.0).T
            omega = record.omega[mask]
            last_image = ax.imshow(
                image,
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                extent=[0, 120, float(omega[0]), float(omega[-1])],
                cmap="rainbow",
                vmin=0.0,
                vmax=vmax,
                rasterized=True,
            )
            ax.plot(
                np.arange(121),
                _interpolate_root(record.root),
                color="white",
                lw=1.75,
                solid_capstyle="round",
            )
            ax.axhline(0.0, color="black", lw=0.9, ls="--", alpha=0.80)
            _decorate_path_axis(ax)
            ax.set_ylim(-ylim, ylim)
            if idx % 2 == 0:
                ax.set_ylabel(r"$\omega/t$")
            _panel_label(ax, idx)
            ax.text(
                0.035,
                0.46,
                rf"${record.interaction_name}={record.interaction_value},\ "
                rf"{fixed_zero_interaction}=0$",
                transform=ax.transAxes,
                ha="left",
                va="center",
                color="white",
                fontsize=11.5,
                fontweight="bold",
            )
            metadata.append(
                {
                    "interaction": record.interaction_name,
                    "value": record.interaction_value,
                    "omega_window": [-ylim, ylim],
                    "y_span": 2.0 * ylim,
                    "color_range": [0.0, vmax],
                    "source": str(record.source.relative_to(ROOT)),
                    "missing_display_rows_interpolated": missing_rows,
                    "accepted_root_count": int(np.isfinite(record.root).sum()),
                }
            )
        if last_image is None:
            raise RuntimeError("No full-spectrum panel was rendered")
        cax = fig.add_axes([0.28, 0.055, 0.44, 0.026])
        colorbar = fig.colorbar(last_image, cax=cax, orientation="horizontal")
        colorbar.set_ticks(np.linspace(0.0, vmax, 6 if vmax == 2.5 else 4))
        colorbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)
        colorbar.ax.tick_params(labelsize=10.5, pad=2)
        output = _save(fig, stem)
    return output, metadata


def lower_band_window(
    record: Spectrum,
    window_span: float,
) -> tuple[float, float, tuple[float, float]]:
    """Return a fixed-span window centered on significant occupied weight."""
    negative = record.omega < 0.0
    omega = record.omega[negative]
    rho = np.nan_to_num(
        np.maximum(record.rho[:, negative], 0.0),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )
    profile = np.mean(rho, axis=0)
    if profile.size == 0 or float(np.max(profile)) <= 0.0:
        raise ValueError(
            f"No lower-band spectral weight for "
            f"{record.interaction_name}={record.interaction_value}"
        )
    significant = profile >= LOWER_SUPPORT_FRACTION * float(np.max(profile))
    support = (float(omega[significant][0]), float(omega[significant][-1]))
    center = 0.5 * (support[0] + support[1])
    low = center - 0.5 * window_span
    high = center + 0.5 * window_span
    if low < float(record.omega[0]):
        shift = float(record.omega[0]) - low
        low += shift
        high += shift
    if high > float(record.omega[-1]):
        shift = high - float(record.omega[-1])
        low -= shift
        high -= shift
    if not np.isclose(high - low, window_span):
        raise RuntimeError("Lower-band window lost its fixed vertical span")
    return low, high, support


def _lower_sequence(
    records: list[Spectrum],
    *,
    fixed_zero_interaction: str,
    vmax: float,
    window_span: float,
    stem: str,
) -> tuple[dict[str, str], list[dict]]:
    metadata: list[dict] = []
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 2, figsize=(9.4, 6.9))
        fig.subplots_adjust(
            left=0.085,
            right=0.992,
            bottom=0.145,
            top=0.985,
            wspace=0.22,
            hspace=0.30,
        )
        last_image = None
        for idx, (ax, record) in enumerate(zip(axes.ravel(), records)):
            low, high, support = lower_band_window(record, window_span)
            mask = (
                (record.omega >= low - 1.0e-12)
                & (record.omega <= high + 1.0e-12)
            )
            rho, missing_rows = _interpolate_missing_rows(record.rho)
            image = np.maximum(rho[:, mask], 0.0).T
            omega = record.omega[mask]
            last_image = ax.imshow(
                image,
                origin="lower",
                aspect="auto",
                interpolation="bilinear",
                extent=[0, 120, float(omega[0]), float(omega[-1])],
                cmap="rainbow",
                vmin=0.0,
                vmax=vmax,
                rasterized=True,
            )
            _decorate_path_axis(ax)
            ax.set_ylim(low, high)
            if idx % 2 == 0:
                ax.set_ylabel(r"$\omega/t$")
            _panel_label(ax, idx)
            ax.text(
                0.018,
                0.965,
                rf"${record.interaction_name}={record.interaction_value},\ "
                rf"{fixed_zero_interaction}=0$",
                transform=ax.transAxes,
                ha="left",
                va="top",
                color="white",
                fontsize=11.5,
                fontweight="bold",
            )
            metadata.append(
                {
                    "interaction": record.interaction_name,
                    "value": record.interaction_value,
                    "omega_window": [low, high],
                    "y_span": high - low,
                    "one_percent_mean_spectral_support": list(support),
                    "support_centered_then_grid_limited": True,
                    "color_range": [0.0, vmax],
                    "source": str(record.source.relative_to(ROOT)),
                    "auxiliary_source": (
                        str(record.auxiliary_source.relative_to(ROOT))
                        if record.auxiliary_source is not None
                        else None
                    ),
                    "missing_display_rows_interpolated": missing_rows,
                }
            )
        if last_image is None:
            raise RuntimeError("No lower-band panel was rendered")
        cax = fig.add_axes([0.28, 0.055, 0.44, 0.026])
        colorbar = fig.colorbar(last_image, cax=cax, orientation="horizontal")
        colorbar.set_ticks(np.linspace(0.0, vmax, 6 if vmax == 2.5 else 4))
        colorbar.set_label(r"$\rho_G(\mathbf{k},\omega)$", labelpad=2)
        colorbar.ax.tick_params(labelsize=10.5, pad=2)
        output = _save(fig, stem)
    return output, metadata


def build_all() -> dict[str, dict[str, str]]:
    u_records = load_u_records()
    v_records = load_v_records()
    s1, s1_meta = _lower_sequence(
        u_records,
        fixed_zero_interaction="V",
        vmax=U_VMAX,
        window_span=U_LOWER_WINDOW_SPAN,
        stem="supp_figS3_uonly_lower_band_snapshots",
    )
    s2, s2_meta = _lower_sequence(
        v_records,
        fixed_zero_interaction="U",
        vmax=V_LOWER_VMAX,
        window_span=V_LOWER_WINDOW_SPAN,
        stem="supp_figS5_vonly_lower_band_snapshots",
    )
    outputs = {
        "supplement_figure_S1": s1,
        "supplement_figure_S2": s2,
    }
    summary = {
        "description": "SI occupied-band snapshots",
        "eta": 0.05,
        "v_greater_than_8_choice": 12,
        "lower_band_window_rule": (
            "figure-specific fixed span centered on the support of the "
            "path-averaged negative-frequency spectrum above 1% of its "
            "maximum; shifted without resizing only when required by the "
            "stored omega grid"
        ),
        "lower_band_window_spans": {
            "S1": U_LOWER_WINDOW_SPAN,
            "S2": V_LOWER_WINDOW_SPAN,
        },
        "lower_band_color_upper_bounds": {
            "S1": U_VMAX,
            "S2": V_LOWER_VMAX,
        },
        "figures": {
            "S1": {"output": s1, "panels": s1_meta},
            "S2": {"output": s2, "panels": s2_meta},
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary_path = RESULTS / "pnas_supp_spectral_sequence_windows.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    outputs["window_summary"] = {
        "json": str(summary_path.relative_to(ROOT))
    }
    return outputs


def main() -> None:
    print(json.dumps(build_all(), indent=2))


if __name__ == "__main__":
    main()
