#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LEGEND_FONTSIZE = 14
FRAME_LABEL_FONTSIZE = 14
TICK_FONTSIZE = 15

TARGET_DENSITIES = [round(0.7 + 0.025 * i, 3) for i in range(13)]
TPRIME_CONFIGS = [
    {"prefix": "tp0", "label": "t'=0", "u_tag": "tp0U"},
    {"prefix": "tpn25", "label": "t'=-0.25", "u_tag": "tpn25U"},
]
_MARKERS = ["o", "v", "^", "<", "d", "P", "X", "h", ">", "s", "*", "p", "8"]
_COLORS = [
    "#2f4b8f",
    "#3b5ba9",
    "#4770c1",
    "#5685d0",
    "#3b5ba9",
    "#4f74c8",
    "#6690d8",
    "#7ca9cf",
    "#5f9f80",
    "#78a95c",
    "#b49b45",
    "#c7773c",
    "#b2473e",
]
DENSITY_STYLES = {
    density: {
        "marker": _MARKERS[i],
        "color": _COLORS[i],
        "label": f"n={density:.3f}",
    }
    for i, density in enumerate(TARGET_DENSITIES)
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
    out_path = out_dir / "magnetization_tprime_panels.csv"
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
                "magnetization",
            ]
        )
        for row in sorted(rows, key=lambda item: (item["tprime_prefix"], item["n_target"], item["U"])):
            w.writerow(
                [
                    row["tprime_label"],
                    row["tprime_prefix"],
                    row["U"],
                    row["n_target"],
                    row["n_actual"],
                    row["mu"],
                    row["magnetization"],
                ]
            )
    return out_path


def _plot(rows, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    xticks = sorted({int(row["U"]) for row in rows})

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), dpi=200, constrained_layout=True)
    for ax, cfg in zip(axes, TPRIME_CONFIGS):
        for n_target in TARGET_DENSITIES:
            pts = sorted(
                [
                    (row["U"], row["magnetization"])
                    for row in rows
                    if row["tprime_prefix"] == cfg["prefix"] and abs(row["n_target"] - n_target) < 1e-12
                ],
                key=lambda item: item[0],
            )
            dstyle = DENSITY_STYLES[round(n_target, 3)]
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                marker=dstyle["marker"],
                color=dstyle["color"],
                linewidth=2,
                label=dstyle["label"],
            )
        ax.set_title(cfg["label"])
        ax.set_xlabel("U/t", fontsize=FRAME_LABEL_FONTSIZE)
        ax.set_xticks(xticks)
        ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
        ax.grid(alpha=0.25)
        if cfg["prefix"] == "tpn25":
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                fontsize=LEGEND_FONTSIZE,
                frameon=False,
                ncol=1,
            )

    axes[0].set_ylabel("Magnetization", fontsize=FRAME_LABEL_FONTSIZE)

    out_path = out_dir / "magnetization_tprime_panels.pdf"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Magnetization panels for t'=0 and t'=-0.25.")
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
