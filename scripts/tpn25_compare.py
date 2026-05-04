#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LEGEND_X = 0.18
LEGEND_Y = 0.93
LEGEND_FONTSIZE = 14
FRAME_LABEL_FONTSIZE = 14
TICK_FONTSIZE = 15

TARGET_DENSITIES = [1.0, 0.875, 0.8]


def _extract_tpn25(data_root: Path, u_values: list[int], div: int):
    observable_script_dir = Path(__file__).resolve().parents[1] / "observable" / "scripts"
    sys.path.insert(0, str(observable_script_dir))
    from find_observables_doped_clean import find_observables_at_density

    rows = []
    for u in u_values:
        u_dir = f"tpn25U{u}"
        for n_target in TARGET_DENSITIES:
            mu, n_actual, e0, sp, doi, doq = find_observables_at_density(
                target_density=n_target,
                div=div,
                data_root=data_root,
                u_dir=u_dir,
            )
            rows.append(
                {
                    "u_dir": u_dir,
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
    out_path = out_dir / "tpn25_observables.csv"
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "u_dir",
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
        for row in sorted(rows, key=lambda item: (item["n_target"], item["U"])):
            w.writerow(
                [
                    row["u_dir"],
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
    styles = {
        1.0: {"fmt": "--s", "color": "#d62728", "label": "4x4-MMHK (n=1)"},
        0.875: {"fmt": "--d", "color": "#8c564b", "label": "4x4-MMHK (n=0.875)"},
        0.8: {"fmt": "--o", "color": "#9467bd", "label": "4x4-MMHK (n=0.8)"},
    }

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), dpi=200, constrained_layout=True)
    for ax, (key, title) in zip(axes, props):
        for n_target in TARGET_DENSITIES:
            pts = sorted(
                [(row["U"], row[key]) for row in rows if abs(row["n_target"] - n_target) < 1e-12],
                key=lambda item: item[0],
            )
            style = styles[n_target]
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                style["fmt"],
                color=style["color"],
                label=style["label"],
            )
        ax.set_title(title)
        ax.set_xlabel("U/t", fontsize=FRAME_LABEL_FONTSIZE)
        ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
        ax.grid(alpha=0.25)

    axes[0].set_ylabel("Value", fontsize=FRAME_LABEL_FONTSIZE)
    axes[0].set_xticks(sorted({int(row["U"]) for row in rows}))
    axes[1].set_xticks(sorted({int(row["U"]) for row in rows}))
    axes[2].set_xticks(sorted({int(row["U"]) for row in rows}))

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(LEGEND_X, LEGEND_Y),
        ncol=1,
        fontsize=LEGEND_FONTSIZE,
        frameon=False,
    )

    out_path = out_dir / "tpn25_comparison.pdf"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Plot MMHK observables for t'=-0.25.")
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

    rows = _extract_tpn25(Path(args.data_root), args.u_values, args.div)
    csv_path = _write_csv(rows, Path(args.out_dir))
    plot_path = _plot(rows, Path(args.out_dir))
    print(f"Wrote {csv_path}")
    print(f"Wrote {plot_path}")


if __name__ == "__main__":
    main()
