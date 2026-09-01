#!/usr/bin/env python3
"""Summarize noninteracting-dispersion fits to extracted Luttinger-surface roots."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "Gcalpath"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
RESULTS.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)


def eps_from_k_path(k_path: np.ndarray, tp: float) -> np.ndarray:
    delta = np.pi / 40.0
    kx = k_path[:, 0] * delta
    ky = k_path[:, 1] * delta
    return -2.0 * (np.cos(kx) + np.cos(ky)) - 4.0 * tp * np.cos(kx) * np.cos(ky)


def fit_linear(eps: np.ndarray, roots: np.ndarray) -> tuple[float, float, float, float]:
    mask = np.isfinite(eps) & np.isfinite(roots)
    A = np.column_stack([eps[mask], np.ones(mask.sum())])
    scale, offset = np.linalg.lstsq(A, roots[mask], rcond=None)[0]
    pred = scale * eps[mask] + offset
    resid = roots[mask] - pred
    return float(scale), float(offset), float(np.sqrt(np.mean(resid**2))), float(np.max(np.abs(resid)))


def main() -> None:
    rows: list[dict[str, object]] = []
    for path in sorted(DATA_ROOT.glob("luttinger_surface_eta*/luttinger_*_spectra_and_roots.npz")):
        data = np.load(path)
        tp = float(data["tp"])
        eta = float(data["eta"])
        k_path = data["k_path"]
        roots_all = data["omega_root"]
        U_all = data["U"]
        eps_fixed = eps_from_k_path(k_path, tp)
        for idx, U in enumerate(U_all):
            roots = roots_all[idx]
            scale, offset, rmse, maxerr = fit_linear(eps_fixed, roots)
            rows.append(
                {
                    "eta": eta,
                    "tp": tp,
                    "U": int(U),
                    "scale_fixed_tp": scale,
                    "offset_fixed_tp": offset,
                    "rmse_fixed_tp": rmse,
                    "max_abs_error_fixed_tp": maxerr,
                    "finite_root_count": int(np.isfinite(roots).sum()),
                    "source_npz": str(path.relative_to(ROOT)),
                }
            )
    out_csv = RESULTS / "ls_noninteracting_scale_summary.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plt.rcParams.update({"font.size": 18, "axes.linewidth": 1.4})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), sharey=True)
    colors = {0.05: "tab:blue", 0.1: "tab:orange", 0.2: "tab:green"}
    for ax, tp in zip(axes, [0.0, -0.25]):
        for eta in [0.05, 0.1, 0.2]:
            subset = [r for r in rows if abs(float(r["tp"]) - tp) < 1e-12 and abs(float(r["eta"]) - eta) < 1e-12]
            subset.sort(key=lambda r: int(r["U"]))
            ax.plot(
                [r["U"] for r in subset],
                [r["scale_fixed_tp"] for r in subset],
                marker="o",
                lw=2.2,
                color=colors[eta],
                label=rf"$\eta={eta:g}$",
            )
        ax.axhline(-1.4, color="0.35", ls="--", lw=1.5, label=r"$-1.4$" if tp == 0.0 else None)
        ax.set_title(rf"$t'={tp:g}$")
        ax.set_xlabel(r"$U/t$")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel(r"fit scale $a$ in $\omega_{\mathrm{GZ}}=a\,\epsilon_0+b$")
    axes[0].legend(frameon=False, fontsize=13)
    fig.tight_layout()
    out_pdf = FIGURES / "ls_scale_vs_u_eta_robustness.pdf"
    out_png = FIGURES / "ls_scale_vs_u_eta_robustness.png"
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    print({"csv": str(out_csv), "pdf": str(out_pdf), "png": str(out_png)})


if __name__ == "__main__":
    main()
