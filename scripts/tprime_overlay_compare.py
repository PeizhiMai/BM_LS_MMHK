#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


LEGEND_X = 0.10
LEGEND_Y = 0.92
DENSITY_LEGEND_X = 0.52
DENSITY_LEGEND_Y = 0.92
LEGEND_FONTSIZE = 14
FRAME_LABEL_FONTSIZE = 14
TICK_FONTSIZE = 15

TARGET_DENSITIES = [1.0, 0.875, 0.8]
TPRIME_CONFIGS = [
    {"prefix": "tp0", "label": "t'=0", "linestyle": "-", "u_tag": "tp0U"},
    {"prefix": "tpn25", "label": "t'=-0.25", "linestyle": "--", "u_tag": "tpn25U"},
]
DENSITY_STYLES = {
    1.0: {"marker": "s", "color": "#d62728", "label": "n=1"},
    0.875: {"marker": "d", "color": "#8c564b", "label": "n=0.875"},
    0.8: {"marker": "o", "color": "#9467bd", "label": "n=0.8"},
}


def _extract_rows(data_root: Path, u_values: list[int], div: int):
    observable_script_dir = Path(__file__).resolve().parents[1] / "observable" / "scripts"
    sys.path.insert(0, str(observable_script_dir))
    from find_observables_doped_clean import find_observables_at_density

    rows = []
    for cfg in TPRIME_CONFIGS:
        for u in u_values:
            u_dir = f"{cfg['u_tag']}{u}"
            for n_target in TARGET_DENSITIES:
                mu, n_actual, e0, sp, doi, doq = find_observables_at_density(
                    target_density=n_target,
                    div=div,
                    data_root=data_root,
                    u_dir=u_dir,
                )
                rows.append(
                    {
                        "tprime_label": cfg["label"],
                        "tprime_prefix": cfg["prefix"],
                        "U": float(u),
                        "n_target": n_target,
                        "n_actual": n_actual,
                        "mu": mu,
                        "ground_state_energy": e0,
                        "double_occupancy_i": doi,
                        "magnetization": sp,
                        "double_occupancy_q": doq,
                    }
                )
    return rows


def _write_csv(rows, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tprime_overlay_observables.csv"
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "tprime_label",
                "tprime_prefix",
                "U",
                "n_target",
                "n_actual",
                "mu",
                "ground_state_energy",
                "double_occupancy_i",
                "magnetization",
                "double_occupancy_q",
            ]
        )
        for row in sorted(rows, key=lambda item: (item["n_target"], item["tprime_prefix"], item["U"])):
            w.writerow(
                [
                    row["tprime_label"],
                    row["tprime_prefix"],
                    row["U"],
                    row["n_target"],
                    row["n_actual"],
                    row["mu"],
                    row["ground_state_energy"],
                    row["double_occupancy_i"],
                    row["magnetization"],
                    row["double_occupancy_q"],
                ]
            )
    return out_path


def _plot(rows, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    props = [
        ("ground_state_energy", "Ground State Energy"),
        ("double_occupancy_i", "Double Occupancy"),
        ("magnetization", "Magnetization"),
    ]
    xticks = sorted({int(row["U"]) for row in rows})

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), dpi=200, constrained_layout=True)
    for ax, (key, title) in zip(axes, props):
        for cfg in TPRIME_CONFIGS:
            for n_target in TARGET_DENSITIES:
                pts = sorted(
                    [
                        (row["U"], row[key])
                        for row in rows
                        if row["tprime_prefix"] == cfg["prefix"] and abs(row["n_target"] - n_target) < 1e-12
                    ],
                    key=lambda item: item[0],
                )
                dstyle = DENSITY_STYLES[n_target]
                ax.plot(
                    [p[0] for p in pts],
                    [p[1] for p in pts],
                    linestyle=cfg["linestyle"],
                    marker=dstyle["marker"],
                    color=dstyle["color"],
                    linewidth=2,
                    label=f"{cfg['label']}, {dstyle['label']}",
                )
        ax.set_title(title)
        ax.set_xlabel("U/t", fontsize=FRAME_LABEL_FONTSIZE)
        ax.set_xticks(xticks)
        ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
        ax.grid(alpha=0.25)

    axes[0].set_ylabel("Value", fontsize=FRAME_LABEL_FONTSIZE)

    tprime_handles = [
        Line2D([0], [0], color="black", linestyle=cfg["linestyle"], linewidth=2, label=cfg["label"])
        for cfg in TPRIME_CONFIGS
    ]
    density_handles = [
        Line2D(
            [0],
            [0],
            color=DENSITY_STYLES[n]["color"],
            marker=DENSITY_STYLES[n]["marker"],
            linestyle="None",
            markersize=7,
            label=DENSITY_STYLES[n]["label"],
        )
        for n in TARGET_DENSITIES
    ]

    tprime_legend = fig.legend(
        tprime_handles,
        [h.get_label() for h in tprime_handles],
        loc="upper center",
        bbox_to_anchor=(LEGEND_X, LEGEND_Y),
        ncol=1,
        fontsize=LEGEND_FONTSIZE,
        frameon=False,
    )
    fig.add_artist(tprime_legend)
    fig.legend(
        density_handles,
        [h.get_label() for h in density_handles],
        loc="upper center",
        bbox_to_anchor=(DENSITY_LEGEND_X, DENSITY_LEGEND_Y),
        ncol=1,
        fontsize=LEGEND_FONTSIZE,
        frameon=False,
    )

    out_path = out_dir / "tprime_overlay_comparison.pdf"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Overlay MMHK observables for t'=0 and t'=-0.25.")
    parser.add_argument("--data-root", default="observable/data", help="Observable data root.")
    parser.add_argument("--out-dir", default="results", help="Output directory.")
    parser.add_argument("--div", type=int, default=1, help="Sampling stride.")
    parser.add_argument(
        "--u-values",
        nargs="+",
        type=int,
        default=[6, 8, 10, 12],
        help="U values to include.",
    )
    args = parser.parse_args()

    rows = _extract_rows(Path(args.data_root), args.u_values, args.div)
    csv_path = _write_csv(rows, Path(args.out_dir))
    plot_path = _plot(rows, Path(args.out_dir))
    print(f"Wrote {csv_path}")
    print(f"Wrote {plot_path}")


if __name__ == "__main__":
    main()
