#!/usr/bin/env python3
"""Overlay finite-(U,V) zero dispersions on U=0,V=12 and U=40,V=0 backgrounds."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
FINITE_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"
U0_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV"
V0_NPZ = ROOT / "data/Gcalpath/luttinger_surface_eta0p05/luttinger_tp0_eta0p05_spectra_and_roots.npz"
FIG_DIR = ROOT / "figures/luttinger_eta0p05_overlay_backgrounds"
OUT_CSV = ROOT / "results/finite_uv_luttinger_overlay_background_metrics.csv"
FIG_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

GROUPS = {
    8: [1, 2, 3, 4],
    20: [2, 4, 6, 8],
    40: [4, 8, 12, 16],
}


def load_root_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Ensure missing rows plot as gaps.
    df.loc[df["root_status"] == "missing_raw_data", "omega_root"] = np.nan
    return df


def compare(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return {"corr": np.nan, "rms": np.nan, "scale": np.nan, "offset": np.nan, "affine_rms": np.nan}
    corr = float(np.corrcoef(a[mask], b[mask])[0, 1])
    rms = float(np.sqrt(np.mean((a[mask] - b[mask]) ** 2)))
    A = np.column_stack([b[mask], np.ones(mask.sum())])
    scale, offset = np.linalg.lstsq(A, a[mask], rcond=None)[0]
    pred = scale * b[mask] + offset
    affine_rms = float(np.sqrt(np.mean((a[mask] - pred) ** 2)))
    return {"corr": corr, "rms": rms, "scale": float(scale), "offset": float(offset), "affine_rms": affine_rms}


def main() -> None:
    u0 = load_root_csv(U0_DIR / "rhoG_LS_U0_V12_tp0_eta0p05_roots.csv")
    x = u0["x_path"].to_numpy(float)
    bg_charge = u0["omega_root"].to_numpy(float)

    z = np.load(V0_NPZ)
    u_values = [int(u) for u in z["U"]]
    bg_mott = z["omega_root"][u_values.index(40)].astype(float)

    plt.rcParams.update({"font.size": 15, "axes.linewidth": 1.25})
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.6), sharex=True, sharey=True)
    cmap_by_u = {8: plt.cm.Blues, 20: plt.cm.Oranges, 40: plt.cm.Reds}
    metrics = []

    for ax, (U, Vs) in zip(axes, GROUPS.items()):
        ax.plot(x, bg_mott, color="0.15", lw=3.0, label=r"$U=40,V=0$ background")
        ax.plot(x, bg_charge, color="0.15", lw=3.0, ls="--", label=r"$U=0,V=12$ background")
        colors = cmap_by_u[U](np.linspace(0.45, 0.9, len(Vs)))
        for color, V in zip(colors, Vs):
            csv_path = FINITE_DIR / f"rhoG_LS_U{U}_V{V}_tp0_eta0p05_roots.csv"
            df = load_root_csv(csv_path)
            roots = df["omega_root"].to_numpy(float)
            vu = V / U
            ax.plot(x, roots, color=color, lw=2.2, alpha=0.92, label=rf"$V={V}$ ($V/U={vu:.2g}$)")
            row = {"U": U, "V": V, "V_over_U": vu, "accepted_root_count": int(np.isfinite(roots).sum())}
            for name, bg in [("vs_U40V0", bg_mott), ("vs_U0V12", bg_charge)]:
                vals = compare(roots, bg)
                row.update({f"{name}_{k}": v for k, v in vals.items()})
            metrics.append(row)
        ax.axhline(0.0, color="0.45", ls=":", lw=1.1)
        ax.axvline(x[40], color="0.45", ls=":", lw=1.1)
        ax.axvline(x[80], color="0.45", ls=":", lw=1.1)
        ax.set_title(rf"finite $U={U}$")
        ax.grid(alpha=0.15)
        ax.set_xlim(x[0], x[-1])
        ax.set_xticks([x[0], x[40], x[80], x[120]])
        ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
        ax.legend(frameon=False, fontsize=9, loc="lower left")
    axes[0].set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
    fig.suptitle(
        r"Finite-$(U,V)$ zero dispersions between spin-only and charge-only backgrounds",
        y=1.02,
        fontsize=17,
    )
    fig.tight_layout()
    pdf = FIG_DIR / "finite_uv_luttinger_with_U0V12_U40V0_backgrounds_eta0p05.pdf"
    png = FIG_DIR / "finite_uv_luttinger_with_U0V12_U40V0_backgrounds_eta0p05.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=180, bbox_inches="tight")

    # Also make a compact single-panel version colored by V/U.
    fig2, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.plot(x, bg_mott, color="k", lw=3.2, label=r"$U=40,V=0$")
    ax.plot(x, bg_charge, color="k", lw=3.2, ls="--", label=r"$U=0,V=12$")
    all_vu = [V / U for U, Vs in GROUPS.items() for V in Vs]
    norm = plt.Normalize(min(all_vu), max(all_vu))
    sm = plt.cm.ScalarMappable(norm=norm, cmap="viridis")
    for U, Vs in GROUPS.items():
        for V in Vs:
            csv_path = FINITE_DIR / f"rhoG_LS_U{U}_V{V}_tp0_eta0p05_roots.csv"
            roots = load_root_csv(csv_path)["omega_root"].to_numpy(float)
            ax.plot(x, roots, color=sm.to_rgba(V / U), lw=1.8, alpha=0.72)
    ax.axhline(0.0, color="0.45", ls=":", lw=1.1)
    ax.axvline(x[40], color="0.45", ls=":", lw=1.1)
    ax.axvline(x[80], color="0.45", ls=":", lw=1.1)
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
    ax.set_title(r"all finite-$(U,V)$ overlays, color = $V/U$")
    ax.grid(alpha=0.15)
    ax.legend(frameon=False, fontsize=11, loc="lower left")
    cbar = fig2.colorbar(sm, ax=ax, pad=0.02)
    cbar.set_label(r"$V/U$")
    fig2.tight_layout()
    pdf2 = FIG_DIR / "finite_uv_luttinger_all_with_backgrounds_eta0p05.pdf"
    png2 = FIG_DIR / "finite_uv_luttinger_all_with_backgrounds_eta0p05.png"
    fig2.savefig(pdf2, bbox_inches="tight")
    fig2.savefig(png2, dpi=180, bbox_inches="tight")

    pd.DataFrame(metrics).to_csv(OUT_CSV, index=False)
    print({"panel_pdf": str(pdf), "panel_png": str(png), "all_pdf": str(pdf2), "all_png": str(png2), "metrics": str(OUT_CSV)})


if __name__ == "__main__":
    main()
