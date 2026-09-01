#!/usr/bin/env python3
"""Summarize and overlay U=0 finite-V Luttinger-surface root CSVs."""
from __future__ import annotations

from pathlib import Path
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root-dir", type=Path, default=ROOT / "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV")
    p.add_argument("--fig-dir", type=Path, default=ROOT / "figures/luttinger_eta0p05_U0_finiteV")
    p.add_argument("--metrics", type=Path, default=ROOT / "results/u0_finite_v_luttinger_surface_metrics.csv")
    p.add_argument("--eta-label", default="eta0p05")
    p.add_argument("--eta", type=float, default=0.05)
    p.add_argument("--V", type=float, nargs="*", default=[4, 8, 12])
    return p.parse_args()


def v_label(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v).replace(".", "p")


def main() -> None:
    args = parse_args()
    args.fig_dir.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    plt.rcParams.update({"font.size": 18, "axes.linewidth": 1.3})
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    colors = plt.cm.viridis(np.linspace(0.15, 0.75, len(args.V)))
    last_df = None
    for color, V in zip(colors, args.V):
        csv_path = args.root_dir / f"rhoG_LS_U0_V{v_label(V)}_tp0_{args.eta_label}_roots.csv"
        df = pd.read_csv(csv_path)
        last_df = df
        roots = df["omega_root"].to_numpy(float)
        finite = np.isfinite(roots)
        x_path = df["x_path"].to_numpy(float)
        ax.plot(x_path, roots, lw=2.4, color=color, label=rf"$V={V:g}$")
        finite_roots = roots[finite]
        jumps = np.abs(np.diff(finite_roots)) if finite_roots.size > 1 else np.array([])
        rows.append(
            {
                "U": 0,
                "V": V,
                "tp": 0,
                "eta": args.eta,
                "accepted_root_count": int(finite.sum()),
                "missing_raw_rows": int((df["root_status"] == "missing_raw_data").sum()),
                "root_min": float(np.nanmin(roots)),
                "root_max": float(np.nanmax(roots)),
                "bandwidth": float(np.nanmax(roots) - np.nanmin(roots)),
                "mean_abs_root": float(np.nanmean(np.abs(roots))),
                "max_neighbor_jump": float(np.nanmax(jumps)) if jumps.size else np.nan,
                "max_candidate_roots": int(df["candidate_roots"].max()),
                "mean_candidate_roots": float(df["candidate_roots"].mean()),
                "status_counts": str(df["root_status"].value_counts().to_dict()),
                "source_csv": str(csv_path.relative_to(ROOT)),
            }
        )
    if last_df is None:
        raise SystemExit("No root CSVs read")
    x = last_df["x_path"].to_numpy(float)
    ax.axhline(0, color="0.35", ls="--", lw=1.1)
    ax.axvline(x[40], color="0.35", ls=":", lw=1.1)
    ax.axvline(x[80], color="0.35", ls=":", lw=1.1)
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
    ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
    ax.set_title(r"$U=0$, finite-$V$ zero dispersion")
    ax.legend(frameon=False, ncol=len(args.V), fontsize=14)
    ax.grid(alpha=0.18)
    fig.tight_layout()
    pdf = args.fig_dir / f"u0_v_luttinger_surface_overlay_{args.eta_label}.pdf"
    png = args.fig_dir / f"u0_v_luttinger_surface_overlay_{args.eta_label}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=180, bbox_inches="tight")
    pd.DataFrame(rows).to_csv(args.metrics, index=False)
    print({"metrics": str(args.metrics), "pdf": str(pdf), "png": str(png)})


if __name__ == "__main__":
    main()
