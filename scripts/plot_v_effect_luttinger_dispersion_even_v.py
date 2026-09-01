#!/usr/bin/env python3
"""Plot eta=0.05 finite-V zero-dispersion comparison using only even-integer V."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analyze_v_effect_luttinger_dispersion import load_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures/luttinger_eta0p05_other_parameter_sets"


def is_even_integer_v(v: float) -> bool:
    return abs(v - round(v)) < 1e-9 and int(round(v)) % 2 == 0


def plot_even_v() -> dict[str, str]:
    z0, roots0, rows = load_data()
    rows = [
        row
        for row in rows
        if float(row["V"]) > 0
        and is_even_integer_v(float(row["V"]))
        and (
            int(row["U"]) != 40
            or int(round(float(row["V"]))) % 4 == 0
        )
    ]
    x = z0["x_path"]
    by_u: dict[int, list[dict]] = {}
    for row in rows:
        by_u.setdefault(int(row["U"]), []).append(row)
    u_values = [U for U in (8, 20, 40) if U in by_u]

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    pdf = FIG_DIR / "eta0p05_V_effect_luttinger_dispersion_comparison_evenV.pdf"
    png = FIG_DIR / "eta0p05_V_effect_luttinger_dispersion_comparison_evenV.png"

    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 15,
            "axes.labelsize": 17,
            "xtick.labelsize": 15,
            "ytick.labelsize": 15,
            "legend.fontsize": 11,
            "axes.linewidth": 1.1,
        }
    ):
        fig, axes = plt.subplots(len(u_values), 2, figsize=(10.2, 3.05 * len(u_values)), squeeze=False)
        fig.subplots_adjust(left=0.08, right=0.99, top=0.965, bottom=0.07, wspace=0.22, hspace=0.36)
        for row_idx, U in enumerate(u_values):
            ax = axes[row_idx, 0]
            dax = axes[row_idx, 1]
            ref = roots0[U]
            filtered = sorted(by_u[U], key=lambda item: float(item["V"]))
            colors = plt.cm.viridis(np.linspace(0.18, 0.86, max(2, len(filtered))))

            ax.plot(x, ref, color="black", lw=2.4, label=r"$V=0$")
            dax.axhline(0, color="black", lw=1.2, ls="--")
            for color, row in zip(colors, filtered):
                root = row["roots"]
                V = float(row["V"])
                label = rf"$V={V:g}$"
                ax.plot(x, root, lw=2.0, color=color, label=label)
                dax.plot(x, root - ref, lw=2.0, color=color, label=label)

            for target in (ax, dax):
                target.set_xlim(x[0], x[-1])
                target.set_xticks([x[0], x[40], x[80], x[120]])
                target.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])
                target.axvline(x[40], color="0.78", lw=1.0)
                target.axvline(x[80], color="0.78", lw=1.0)
                target.grid(True, alpha=0.28)
            ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
            dax.set_ylabel(r"$\Delta\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
            ax.set_title(rf"$U={U}$: finite-$V$ zero dispersion")
            dax.set_title(rf"$U={U}$: shift relative to $V=0$")
            ax.legend(frameon=False, ncol=3, loc="upper center")
            dax.legend(frameon=False, ncol=3, loc="upper center")
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=220, bbox_inches="tight")
        plt.close(fig)
    return {"pdf": str(pdf), "png": str(png), "included_V": {str(U): [float(row["V"]) for row in sorted(by_u[U], key=lambda item: float(item["V"]))] for U in u_values}}


if __name__ == "__main__":
    print(json.dumps(plot_even_v(), indent=2))
