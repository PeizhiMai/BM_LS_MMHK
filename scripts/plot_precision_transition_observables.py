#!/usr/bin/env python3
"""Plot observables across the refined MMHK Mott/CDW brackets."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "precision_transition_observables.csv"
SUMMARY = ROOT / "results" / "precision_transition_bracket_changes.csv"
OUT_PDF = ROOT / "figures" / "precision_transition_observables.pdf"
OUT_PNG = ROOT / "figures" / "precision_transition_observables.png"

BRACKETS = {
    12: (3.032, 3.034),
    8: (2.038, 2.040),
    4: (1.029, 1.030),
    2: (0.511, 0.512),
}

METRICS = {
    "double_occupancy": r"$D=\langle n_{i\uparrow}n_{i\downarrow}\rangle$",
    "mCDW2_pipi": r"$m_{\rm CDW}^2=S_c(\pi,\pi)/N$",
    "C1_NN": r"$C_{\mathrm{NN}}=\langle\mathbf{S}_i\!\cdot\!\mathbf{S}_j\rangle_{\rm NN}$",
    "nn_NN": r"$\langle n_i n_j\rangle_{\rm NN}$",
}

COLORS = {12: "#1f4e79", 8: "#d97706", 4: "#7b2cbf", 2: "#5f6f52"}
MARKERS = {12: "o", 8: "s", 4: "^", 2: "D"}


def main() -> None:
    df = pd.read_csv(DATA)
    if len(df) != 68 or not (df["status"] == "COMPLETE").all():
        raise RuntimeError("Expected 68 COMPLETE precision-scout rows.")
    if df.duplicated(["U", "V", "kx", "ky"]).any():
        raise RuntimeError("Duplicate precision-scout rows found.")

    metric_names = list(METRICS)
    spread = (
        df.groupby(["U", "V"])[metric_names].agg(lambda x: x.max() - x.min()).max()
    )
    twist_max_difference = float(spread.max())

    averaged = (
        df.groupby(["U", "V"], as_index=False)[metric_names]
        .mean()
        .sort_values(["U", "V"])
    )
    averaged["V_over_U"] = averaged["V"] / averaged["U"]

    summary_rows = []
    for u, (v_lo, v_hi) in BRACKETS.items():
        group = averaged[averaged["U"] == u].set_index("V")
        lo = group.loc[v_lo]
        hi = group.loc[v_hi]
        row = {
            "U": u,
            "V_lower": v_lo,
            "V_upper": v_hi,
            "V_c_midpoint": 0.5 * (v_lo + v_hi),
            "V_c_halfwidth": 0.5 * (v_hi - v_lo),
            "V_c_over_U": 0.5 * (v_lo + v_hi) / u,
        }
        for metric in metric_names:
            row[f"{metric}_lower"] = lo[metric]
            row[f"{metric}_upper"] = hi[metric]
            row[f"{metric}_change"] = hi[metric] - lo[metric]
        summary_rows.append(row)
    pd.DataFrame(summary_rows).sort_values("U", ascending=False).to_csv(
        SUMMARY, index=False
    )

    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.5), constrained_layout=True)
    axes = axes.ravel()

    handles = []
    labels = []
    for ax, (metric, ylabel) in zip(axes, METRICS.items()):
        for u in (12, 8, 4, 2):
            group = averaged[averaged["U"] == u]
            (line,) = ax.plot(
                group["V_over_U"],
                group[metric],
                color=COLORS[u],
                marker=MARKERS[u],
                markersize=4.2,
                markerfacecolor="white",
                markeredgewidth=0.9,
                linewidth=1.6,
                label=rf"$U={u}$",
            )
            if metric == "double_occupancy":
                handles.append(line)
                labels.append(rf"$U={u}$")
        ax.axvline(0.25, color="#555555", linestyle="--", linewidth=1.0, zorder=0)
        ax.set_xlabel(r"$V/U$")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="#d9d9d9", linewidth=0.55)
        ax.tick_params(direction="out", length=3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.025),
        ncol=4,
        frameon=False,
        handlelength=2.2,
    )
    fig.text(
        0.5,
        -0.012,
        (
            r"Dashed line: $V/U=1/4$. "
            rf"The $(0,0)$ and $(40,40)$ results overlap; maximum difference "
            rf"$< {max(twist_max_difference, 1e-15):.1e}$."
        ),
        ha="center",
        va="bottom",
        fontsize=8,
    )

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
