#!/usr/bin/env python3
"""Plot observable distributions for the 25-twist transition brackets."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "twentyfive_twist_bracket_observables_U16_U36.csv"
SUMMARY = ROOT / "results" / "twentyfive_twist_bracket_validation_U16_U36.csv"
OUT_PDF = ROOT / "figures" / "twentyfive_twist_bracket_validation_U16_U36.pdf"
OUT_PNG = ROOT / "figures" / "twentyfive_twist_bracket_validation_U16_U36.png"

EXPECTED_U = [16, 24, 28, 32, 36]
PHASE_STYLE = {
    "Mott": {"color": "#355c7d", "marker": "o", "offset": -0.18},
    "charge": {"color": "#b23a48", "marker": "s", "offset": 0.18},
}


def validate() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(DATA)
    summary = pd.read_csv(SUMMARY)
    if len(data) != 250 or not data["status"].eq("COMPLETE").all():
        raise RuntimeError("Expected 250 COMPLETE endpoint outputs.")
    if data.duplicated(["U", "V", "kx", "ky"]).any():
        raise RuntimeError("Duplicate endpoint-twist outputs found.")
    group_sizes = data.groupby(["U", "V"]).size()
    if len(group_sizes) != 10 or not group_sizes.eq(25).all():
        raise RuntimeError("Expected ten groups containing 25 twists each.")
    if set(data["U"].astype(int)) != set(EXPECTED_U):
        raise RuntimeError("Unexpected U values in the endpoint data.")
    if not data["phase_matches_expected"].astype(bool).all():
        bad = data.loc[
            ~data["phase_matches_expected"].astype(bool),
            ["U", "V", "kx", "ky", "phase", "expected_phase"],
        ]
        raise RuntimeError(f"Endpoint phase disagreement:\n{bad}")
    if len(summary) != 10 or not summary["unanimous_expected_phase"].astype(bool).all():
        raise RuntimeError("The ten endpoint summaries are not unanimously validated.")
    return data, summary


def main() -> None:
    data, _ = validate()
    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "axes.linewidth": 0.8,
        }
    )
    metrics = [
        ("double_occupancy", r"$D=\langle n_{i\uparrow}n_{i\downarrow}\rangle$"),
        ("mCDW2_pipi", r"$m_{\mathrm{CDW}}^2=S_c(\pi,\pi)/N$"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.05), constrained_layout=True)

    legend_handles = []
    legend_labels = []
    for ax, (metric, ylabel) in zip(axes, metrics):
        for phase in ("Mott", "charge"):
            style = PHASE_STYLE[phase]
            for U in EXPECTED_U:
                group = (
                    data.loc[
                        data["U"].eq(U) & data["expected_phase"].eq(phase)
                    ]
                    .sort_values(["ky", "kx"])
                    .reset_index(drop=True)
                )
                values = group[metric].to_numpy()
                jitter = np.linspace(-0.11, 0.11, len(group))
                x_center = U + style["offset"]
                ax.scatter(
                    x_center + jitter,
                    values,
                    s=10,
                    color=style["color"],
                    alpha=0.35,
                    linewidths=0,
                    zorder=2,
                )
                mean = float(values.mean())
                low = mean - float(values.min())
                high = float(values.max()) - mean
                handle = ax.errorbar(
                    x_center,
                    mean,
                    yerr=np.array([[low], [high]]),
                    fmt=style["marker"],
                    markersize=5.0,
                    markerfacecolor="white",
                    markeredgecolor=style["color"],
                    markeredgewidth=1.1,
                    color=style["color"],
                    ecolor=style["color"],
                    elinewidth=1.0,
                    capsize=2.3,
                    zorder=3,
                )
                if metric == "double_occupancy" and U == EXPECTED_U[0]:
                    legend_handles.append(handle)
                    legend_labels.append(
                        "lower (Mott)" if phase == "Mott" else "upper (charge)"
                    )

        ax.set_xlabel(r"$U/t$")
        ax.set_ylabel(ylabel)
        ax.set_xticks(EXPECTED_U)
        ax.grid(axis="y", color="#dddddd", linewidth=0.55)
        ax.tick_params(direction="out", length=3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].axhline(0.25, color="#777777", linestyle="--", linewidth=0.9, zorder=1)
    axes[0].set_ylim(-0.02, 0.52)
    axes[1].set_ylim(-0.04, 1.04)
    axes[0].legend(
        legend_handles,
        legend_labels,
        frameon=False,
        loc="center right",
    )

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(OUT_PDF)
    print(OUT_PNG)


if __name__ == "__main__":
    main()
