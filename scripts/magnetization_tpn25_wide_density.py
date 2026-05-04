#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LEGEND_FONTSIZE = 13
FRAME_LABEL_FONTSIZE = 14
TICK_FONTSIZE = 15

TARGET_DENSITIES = [round(0.8 + 0.05 * i, 3) for i in range(9)]
_MARKERS = ["o", "v", "^", "d", "P", "X", "h", ">", "s"]
_COLORS = [
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
        "label": f"n={density:.2f}",
    }
    for i, density in enumerate(TARGET_DENSITIES)
}


def _extract_rows(data_root: Path, u_values: list[int], div: int):
    observable_script_dir = Path(__file__).resolve().parents[1] / "observable" / "scripts"
    sys.path.insert(0, str(observable_script_dir))
    from find_observables_doped_clean import find_ave_n_E, find_observables_at_density

    rows = []

    def _solve_with_local_bracket(u: int, n_target: float):
        u_dir = f"tpn25U{u}"
        if not (u == 12 and n_target > 1.0):
            return find_observables_at_density(
                target_density=n_target,
                div=div,
                data_root=data_root,
                u_dir=u_dir,
            )

        # For tpn25U12 above half-filling, the relevant branch lives in a very narrow
        # chemical-potential window. Find it first, then hand a tight bracket to the
        # existing bisection routine.
        coarse_mus = [6.0 + 0.01 * i for i in range(301)]
        prev_mu = coarse_mus[0]
        prev_n, _, _ = find_ave_n_E(prev_mu, div, data_root, u_dir)
        jump_window = None
        for mu in coarse_mus[1:]:
            n_now, _, _ = find_ave_n_E(mu, div, data_root, u_dir)
            if prev_n <= 1.0 and n_now > 1.0:
                jump_window = (prev_mu, mu)
                break
            prev_mu = mu
            prev_n = n_now
        if jump_window is None:
            raise RuntimeError(f"Could not find upper-filling mu window for {u_dir}")

        fine_mus = [jump_window[0] + 0.001 * i for i in range(int(round((jump_window[1] - jump_window[0]) / 0.001)) + 1)]
        fine_data = []
        for mu in fine_mus:
            n_now, _, _ = find_ave_n_E(mu, div, data_root, u_dir)
            fine_data.append((mu, n_now))

        bracket = None
        for (mu_a, n_a), (mu_b, n_b) in zip(fine_data, fine_data[1:]):
            if (n_a <= n_target <= n_b) or (n_b <= n_target <= n_a):
                bracket = (mu_a, mu_b)
                break
        if bracket is None:
            raise RuntimeError(f"Could not bracket density {n_target} in local mu window for {u_dir}")

        return find_observables_at_density(
            target_density=n_target,
            div=div,
            data_root=data_root,
            u_dir=u_dir,
            mu_low=bracket[0],
            mu_high=bracket[1],
            mu_tol=1e-6,
            max_iter=300,
        )

    for u in u_values:
        for n_target in TARGET_DENSITIES:
            mu, n_actual, e0, sp, doi, doq = _solve_with_local_bracket(u, n_target)
            rows.append(
                {
                    "U": float(u),
                    "n_target": n_target,
                    "n_actual": n_actual,
                    "mu": mu,
                    "magnetization": sp,
                }
            )
    return rows


def _write_csv(rows, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "magnetization_tpn25_wide_density.csv"
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["U", "n_target", "n_actual", "mu", "magnetization"])
        for row in sorted(rows, key=lambda item: (item["n_target"], item["U"])):
            w.writerow([row["U"], row["n_target"], row["n_actual"], row["mu"], row["magnetization"]])
    return out_path


def _plot(rows, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    xticks = sorted({int(row["U"]) for row in rows})

    fig, ax = plt.subplots(1, 1, figsize=(6.8, 4.8), dpi=200, constrained_layout=True)
    for n_target in TARGET_DENSITIES:
        pts = sorted(
            [(row["U"], row["magnetization"]) for row in rows if abs(row["n_target"] - n_target) < 1e-12],
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

    ax.set_title("t'=-0.25")
    ax.set_xlabel("U/t", fontsize=FRAME_LABEL_FONTSIZE)
    ax.set_ylabel("Magnetization", fontsize=FRAME_LABEL_FONTSIZE)
    ax.set_xticks(xticks)
    ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
    ax.grid(alpha=0.25)
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=LEGEND_FONTSIZE,
        frameon=False,
        ncol=1,
    )

    out_path = out_dir / "magnetization_tpn25_wide_density.pdf"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="t'=-0.25 magnetization plot on a wide density grid.")
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
