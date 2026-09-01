#!/usr/bin/env python3
"""Generate eta=0.05 rho_G colorplots with Luttinger-surface overlays.

This companion script scans the available ML_MMHK-style raw Lanczos data and
renders all complete parameter groups that are not already part of the V=0
Fig. 3/4 eta=0.05 set.  Each plot uses rho_G as the color map and overlays the
continuous low-spectral-weight ReG=0 branch as a white Luttinger-surface curve.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reproduce_luttinger_figures import (  # noqa: E402
    centers_to_edges,
    choose_continuous_roots,
    continued_fraction_values,
    default_k_path,
    eta_label,
    param_label,
    parse_green_file,
    parse_q,
    unique_k_path,
    x_centers,
)

NUMBER_RE = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
FILE_RE = re.compile(
    rf"L4x4Nup8Ndn8U(?P<U>{NUMBER_RE})V(?P<V>{NUMBER_RE})"
    rf"tp(?P<tp>{NUMBER_RE})f(?P<kx>\d+)x(?P<ky>\d+)Q0x0_(?P<kind>G[hp])\.dat$"
)

MAIN_FIG34_GROUPS = {
    (8.0, 0.0, 0.0),
    (12.0, 0.0, 0.0),
    (20.0, 0.0, 0.0),
    (40.0, 0.0, 0.0),
    (8.0, 0.0, -0.25),
    (12.0, 0.0, -0.25),
    (20.0, 0.0, -0.25),
    (40.0, 0.0, -0.25),
}


@dataclass(frozen=True)
class ParameterGroup:
    U: float
    V: float
    tp: float

    @property
    def stem(self) -> str:
        return (
            f"U{param_label(self.U)}_V{param_label(self.V)}_"
            f"tp{param_label(self.tp).replace('-', 'n').replace('.', 'p')}"
        )

    @property
    def title(self) -> str:
        return rf"$U={param_label(self.U)},\ V={param_label(self.V)},\ t'={param_label(self.tp)}$"

    @property
    def sort_key(self) -> tuple[float, float, float]:
        return (self.U, self.tp, self.V)


@dataclass
class PlotResult:
    group: ParameterGroup
    rho: np.ndarray
    re_g: np.ndarray
    roots: np.ndarray
    root_rows: list[dict]
    ylim: float
    root_window: float
    color_vmax: float
    pdf: Path
    png: Path
    csv: Path
    npz: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot eta=0.05 rho_G and ReG=0 Luttinger surfaces for all other complete parameter sets."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data/Gcalpath/Lanczos_raw_data"))
    parser.add_argument("--fig-dir", type=Path, default=Path("figures/luttinger_eta0p05_other_parameter_sets"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"))
    parser.add_argument("--eta", type=float, default=0.05)
    parser.add_argument("--omega-max", type=float, default=60.0)
    parser.add_argument(
        "--omega-points",
        type=int,
        default=6001,
        help="Use 0.02 spacing by default over [-60, 60], sufficient for adaptive plotting ranges.",
    )
    parser.add_argument("--steps-max", type=int, default=1000)
    parser.add_argument("--coordination", type=int, default=4)
    parser.add_argument("--q", default="0,0")
    parser.add_argument("--rho-clean-ratio", type=float, default=0.25)
    parser.add_argument("--max-continuity-jump", type=float, default=2.0)
    parser.add_argument("--min-continuous-segment", type=int, default=5)
    parser.add_argument(
        "--groups",
        nargs="*",
        default=None,
        help="Optional explicit groups as U,V,tp triples, e.g. 40,12,0 40,16,0.",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Allow groups with missing raw rows; missing rows are flagged and plotted as gaps.",
    )
    parser.add_argument(
        "--max-missing-files",
        type=int,
        default=0,
        help="Maximum missing Gh/Gp files allowed per incomplete group when --include-incomplete is used.",
    )
    parser.add_argument(
        "--include-main-fig34",
        action="store_true",
        help="Also plot the existing V=0 Fig.3/4 groups. Default is to plot only the other groups.",
    )
    return parser.parse_args()


def scan_groups(data_dir: Path) -> tuple[list[ParameterGroup], list[dict]]:
    seen: set[tuple[float, float, float]] = set()
    for path in data_dir.glob("L*.dat"):
        match = FILE_RE.match(path.name)
        if match:
            seen.add((float(match["U"]), float(match["V"]), float(match["tp"])))

    expected = unique_k_path()
    complete: list[ParameterGroup] = []
    incomplete: list[dict] = []
    for U, V, tp in sorted(seen):
        missing: list[str] = []
        for kx, ky in expected:
            for kind in ("Gh", "Gp"):
                name = (
                    f"L4x4Nup8Ndn8U{param_label(U)}V{param_label(V)}"
                    f"tp{param_label(tp)}f{kx}x{ky}Q0x0_{kind}.dat"
                )
                if not (data_dir / name).exists():
                    missing.append(name)
        if missing:
            incomplete.append(
                {
                    "U": U,
                    "V": V,
                    "tp": tp,
                    "missing_file_count": len(missing),
                    "missing_files_sample": missing[:12],
                }
            )
        else:
            complete.append(ParameterGroup(U=U, V=V, tp=tp))
    return complete, incomplete


def parse_group_spec(text: str) -> ParameterGroup:
    parts = text.split(",")
    if len(parts) != 3:
        raise ValueError(f"Expected group as U,V,tp, got {text!r}")
    return ParameterGroup(U=float(parts[0]), V=float(parts[1]), tp=float(parts[2]))


def nice_limit(value: float) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        return 10.0
    value *= 1.08
    if value <= 12:
        step = 2.0
    elif value <= 30:
        step = 5.0
    else:
        step = 10.0
    return step * math.ceil(value / step)


def adaptive_omega_limit(omega: np.ndarray, rho: np.ndarray, roots: np.ndarray | None = None) -> float:
    """Choose a symmetric plot window that contains most visible spectral weight."""
    rho_pos = np.maximum(rho, 0.0)
    avg = np.nanmean(rho_pos, axis=0)
    finite = np.isfinite(avg) & (avg > 0)
    candidates = [8.0]
    if finite.any():
        total = float(np.sum(avg[finite]))
        if total > 0:
            order = np.argsort(np.abs(omega[finite]))
            omega_f = omega[finite]
            avg_f = avg[finite]
            cdf = np.cumsum(avg_f[order]) / total
            candidates.append(float(abs(omega_f[order[min(np.searchsorted(cdf, 0.992), order.size - 1)]])))
        threshold = 0.0125 * float(np.nanmax(avg[finite]))
        mask = finite & (avg >= threshold)
        if mask.any():
            candidates.append(float(np.nanpercentile(np.abs(omega[mask]), 99.0)))
    if roots is not None and np.isfinite(roots).any():
        candidates.append(float(1.15 * np.nanmax(np.abs(roots))))
    return min(float(np.nanmax(np.abs(omega))), nice_limit(max(candidates)))


def adaptive_color_vmax(rho: np.ndarray) -> float:
    rho_pos = np.maximum(rho, 0.0)
    values = rho_pos[np.isfinite(rho_pos) & (rho_pos > 0)]
    if values.size == 0:
        return 1.5
    # Keep the Fig.3/4 saturation style but allow finite-V scans to rescale if
    # the high-intensity peaks differ substantially.
    return float(np.clip(np.nanpercentile(values, 99.7), 0.8, 2.5))


def compute_group(
    data_dir: Path,
    group: ParameterGroup,
    omega: np.ndarray,
    eta: float,
    q_target: tuple[int, int],
    steps_max: int,
    coordination: int,
    clean_ratio: float,
    max_continuity_jump: float,
    min_continuous_segment: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict], float, float, float]:
    k_path = default_k_path()
    rho = np.full((len(k_path), omega.size), np.nan, dtype=np.float64)
    re_g = np.full_like(rho, np.nan)
    available = np.zeros(len(k_path), dtype=bool)
    parse_cache = {}
    for k_idx, (kx, ky) in enumerate(k_path):
        values = []
        paths = [
            data_dir
            / (
                f"L4x4Nup8Ndn8U{param_label(group.U)}V{param_label(group.V)}"
                f"tp{param_label(group.tp)}f{kx}x{ky}Q0x0_{kind}.dat"
            )
            for kind in ("Gh", "Gp")
        ]
        if not all(path.exists() for path in paths):
            continue
        for kind in ("Gh", "Gp"):
            path = data_dir / (
                f"L4x4Nup8Ndn8U{param_label(group.U)}V{param_label(group.V)}"
                f"tp{param_label(group.tp)}f{kx}x{ky}Q0x0_{kind}.dat"
            )
            if path not in parse_cache:
                parse_cache[path] = parse_green_file(path, q_target=q_target)
            values.append(
                continued_fraction_values(
                    parse_cache[path],
                    omega,
                    eta,
                    steps_max=steps_max,
                    coordination=coordination,
                )
            )
        total = values[0] + values[1]
        rho[k_idx] = -2.0 * total.imag
        re_g[k_idx] = -2.0 * total.real
        available[k_idx] = True

    preliminary_ylim = adaptive_omega_limit(omega, rho, roots=None)
    root_window = min(float(np.nanmax(np.abs(omega))), max(20.0, preliminary_ylim))
    roots = np.full(len(k_path), np.nan, dtype=float)
    root_rows = [
        {
            "omega_root": np.nan,
            "rho_at_root": np.nan,
            "rho_ratio_at_root": np.nan,
            "raw_omega_root": np.nan,
            "raw_rho_at_root": np.nan,
            "raw_rho_ratio_at_root": np.nan,
            "abs_reG_at_root": np.nan,
            "root_status": "missing_raw_data",
            "candidate_roots": 0,
            "clean_candidate_roots": 0,
            "candidate_omega_roots": "",
            "clean_candidate_omega_roots": "",
            "chosen_candidate_index": -1,
        }
        for _ in k_path
    ]
    idx = 0
    while idx < len(k_path):
        if not available[idx]:
            idx += 1
            continue
        start = idx
        while idx + 1 < len(k_path) and available[idx + 1]:
            idx += 1
        end = idx + 1
        seg_roots, seg_rows = choose_continuous_roots(
            omega,
            rho[start:end],
            re_g[start:end],
            plot_omega_limit=root_window,
            clean_ratio=clean_ratio,
            max_continuity_jump=max_continuity_jump,
            min_continuous_segment=min(min_continuous_segment, end - start),
        )
        roots[start:end] = seg_roots
        root_rows[start:end] = seg_rows
        idx = end
    ylim = adaptive_omega_limit(omega, rho, roots=roots)
    root_window = max(root_window, 1.05 * float(np.nanmax(np.abs(roots))) if np.isfinite(roots).any() else root_window)
    color_vmax = adaptive_color_vmax(rho[:, np.abs(omega) <= ylim])
    return rho, re_g, roots, root_rows, ylim, root_window, color_vmax


def decorate_axis(ax: plt.Axes, x: np.ndarray) -> None:
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])


def plot_single(
    pdf: Path,
    png: Path,
    group: ParameterGroup,
    omega: np.ndarray,
    x: np.ndarray,
    rho: np.ndarray,
    roots: np.ndarray,
    ylim: float,
    color_vmax: float,
) -> None:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    x_edges = centers_to_edges(x)
    mask = np.abs(omega) <= ylim
    omega_plot = omega[mask]
    omega_edges = centers_to_edges(omega_plot)
    z = np.maximum(rho[:, mask], 0.0).T
    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 18,
            "axes.labelsize": 22,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "axes.linewidth": 1.2,
        }
    ):
        fig, ax = plt.subplots(figsize=(8.2, 5.8), constrained_layout=False)
        fig.subplots_adjust(left=0.13, right=0.98, top=0.88, bottom=0.19)
        cmap = plt.get_cmap("rainbow").copy()
        cmap.set_bad(color="0.35", alpha=0.45)
        im = ax.pcolormesh(
            x_edges,
            omega_edges,
            z,
            shading="auto",
            cmap=cmap,
            vmin=0.0,
            vmax=color_vmax,
        )
        ax.plot(x, roots, color="white", lw=2.2, solid_capstyle="round")
        ax.axhline(0.0, color="black", ls="--", lw=1.4)
        ax.axvline(x[40], color="black", ls="--", lw=1.4)
        ax.axvline(x[80], color="black", ls="--", lw=1.4)
        decorate_axis(ax, x)
        ax.set_ylim(-ylim, ylim)
        ax.set_ylabel(r"$\omega/t$")
        ax.set_title(group.title, pad=8)
        cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.08, pad=0.20)
        cbar.set_ticks(np.linspace(0.0, color_vmax, 5))
        cbar.ax.tick_params(labelsize=16, pad=2)
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=220, bbox_inches="tight")
        plt.close(fig)
    if pdf.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Rendered PDF lacks a PDF header: {pdf}")


def plot_overview(path_pdf: Path, path_png: Path, results: list[PlotResult], omega: np.ndarray, x: np.ndarray) -> None:
    if not results:
        return
    path_pdf.parent.mkdir(parents=True, exist_ok=True)
    ncols = 2
    nrows = math.ceil(len(results) / ncols)
    x_edges = centers_to_edges(x)
    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 14,
            "axes.labelsize": 16,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "axes.linewidth": 1.0,
        }
    ):
        fig, axes = plt.subplots(nrows, ncols, figsize=(10.1, 3.15 * nrows), squeeze=False)
        fig.subplots_adjust(left=0.08, right=0.985, top=0.965, bottom=0.045, wspace=0.18, hspace=0.45)
        for ax in axes.ravel()[len(results) :]:
            ax.axis("off")
        for ax, result in zip(axes.ravel(), results):
            mask = np.abs(omega) <= result.ylim
            omega_plot = omega[mask]
            omega_edges = centers_to_edges(omega_plot)
            cmap = plt.get_cmap("rainbow").copy()
            cmap.set_bad(color="0.35", alpha=0.45)
            im = ax.pcolormesh(
                x_edges,
                omega_edges,
                np.maximum(result.rho[:, mask], 0.0).T,
                shading="auto",
                cmap=cmap,
                vmin=0.0,
                vmax=result.color_vmax,
            )
            ax.plot(x, result.roots, color="white", lw=1.6)
            ax.axhline(0.0, color="black", ls="--", lw=1.0)
            ax.axvline(x[40], color="black", ls="--", lw=1.0)
            ax.axvline(x[80], color="black", ls="--", lw=1.0)
            decorate_axis(ax, x)
            ax.set_ylim(-result.ylim, result.ylim)
            ax.set_title(result.group.title, pad=5)
            if ax.get_subplotspec().colspan.start == 0:
                ax.set_ylabel(r"$\omega/t$")
            cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.07, pad=0.13)
            cbar.ax.tick_params(labelsize=11, pad=1)
        fig.savefig(path_pdf, bbox_inches="tight")
        fig.savefig(path_png, dpi=180, bbox_inches="tight")
        plt.close(fig)


def write_root_csv(path: Path, result: PlotResult, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    k_path = default_k_path()
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "U",
            "V",
            "tp",
            "eta",
            "k_index",
            "kx",
            "ky",
            "x_path",
            "omega_root",
            "rho_at_root",
            "rho_ratio_at_root",
            "raw_omega_root",
            "raw_rho_at_root",
            "raw_rho_ratio_at_root",
            "abs_reG_at_root",
            "root_status",
            "candidate_roots",
            "clean_candidate_roots",
            "candidate_omega_roots",
            "clean_candidate_omega_roots",
            "chosen_candidate_index",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for k_idx, ((kx, ky), x_path, row) in enumerate(zip(k_path, x, result.root_rows)):
            writer.writerow(
                {
                    "U": result.group.U,
                    "V": result.group.V,
                    "tp": result.group.tp,
                    "eta": 0.05,
                    "k_index": k_idx,
                    "kx": kx,
                    "ky": ky,
                    "x_path": x_path,
                    **row,
                }
            )


def status_counts(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[row["root_status"]] = out.get(row["root_status"], 0) + 1
    return out


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    fig_dir = args.fig_dir.resolve()
    out_dir = args.out_dir.resolve()
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    complete, incomplete = scan_groups(data_dir)
    complete_keys = {(group.U, group.V, group.tp) for group in complete}
    incomplete_by_key = {(item["U"], item["V"], item["tp"]): item for item in incomplete}
    if args.groups:
        groups = [parse_group_spec(text) for text in args.groups]
        not_allowed = []
        for group in groups:
            key = (group.U, group.V, group.tp)
            missing_info = incomplete_by_key.get(key)
            if key not in complete_keys and (
                not args.include_incomplete
                or missing_info is None
                or missing_info["missing_file_count"] > args.max_missing_files
            ):
                not_allowed.append({"U": group.U, "V": group.V, "tp": group.tp, "missing_info": missing_info})
        if not_allowed:
            raise FileNotFoundError(
                "Requested groups are incomplete or absent. Use --include-incomplete "
                "--max-missing-files N if the missing rows should be flagged. "
                + json.dumps(not_allowed, indent=2)
            )
    elif not args.include_main_fig34:
        groups = [group for group in complete if (group.U, group.V, group.tp) not in MAIN_FIG34_GROUPS]
        if args.include_incomplete:
            groups.extend(
                ParameterGroup(U=item["U"], V=item["V"], tp=item["tp"])
                for item in incomplete
                if item["missing_file_count"] <= args.max_missing_files
                and (item["U"], item["V"], item["tp"]) not in MAIN_FIG34_GROUPS
            )
    else:
        groups = list(complete)
        if args.include_incomplete:
            groups.extend(
                ParameterGroup(U=item["U"], V=item["V"], tp=item["tp"])
                for item in incomplete
                if item["missing_file_count"] <= args.max_missing_files
            )
    groups = sorted(groups, key=lambda group: group.sort_key)

    omega = np.linspace(-args.omega_max, args.omega_max, args.omega_points)
    x = x_centers()
    q_target = parse_q(args.q)
    e_label = eta_label(args.eta)
    results: list[PlotResult] = []

    for group in groups:
        print(f"Computing eta={args.eta:g}, U={group.U:g}, V={group.V:g}, tp={group.tp:g} ...", flush=True)
        rho, re_g, roots, root_rows, ylim, root_window, color_vmax = compute_group(
            data_dir=data_dir,
            group=group,
            omega=omega,
            eta=args.eta,
            q_target=q_target,
            steps_max=args.steps_max,
            coordination=args.coordination,
            clean_ratio=args.rho_clean_ratio,
            max_continuity_jump=args.max_continuity_jump,
            min_continuous_segment=args.min_continuous_segment,
        )
        pdf = fig_dir / f"rhoG_LS_{group.stem}_{e_label}.pdf"
        png = fig_dir / f"rhoG_LS_{group.stem}_{e_label}.png"
        csv_path = out_dir / f"rhoG_LS_{group.stem}_{e_label}_roots.csv"
        npz_path = out_dir / f"rhoG_LS_{group.stem}_{e_label}_spectra_and_roots.npz"
        result = PlotResult(
            group=group,
            rho=rho,
            re_g=re_g,
            roots=roots,
            root_rows=root_rows,
            ylim=ylim,
            root_window=root_window,
            color_vmax=color_vmax,
            pdf=pdf,
            png=png,
            csv=csv_path,
            npz=npz_path,
        )
        plot_single(pdf, png, group, omega, x, rho, roots, ylim, color_vmax)
        write_root_csv(csv_path, result, x)
        np.savez_compressed(
            npz_path,
            omega=omega,
            x_path=x,
            k_path=np.array(default_k_path(), dtype=int),
            U=np.array(group.U),
            V=np.array(group.V),
            tp=np.array(group.tp),
            eta=np.array(args.eta),
            rho_G=rho,
            reG=re_g,
            omega_root=roots,
            ylim=np.array(ylim),
            root_window=np.array(root_window),
            color_vmax=np.array(color_vmax),
        )
        results.append(result)

    # An explicit --groups repair/recompute must not overwrite the canonical
    # all-parameter overview and summary with a one-group subset.
    if args.groups:
        selection = "__".join(result.group.stem for result in results)
        overview_stem = f"rhoG_LS_selected_{selection}_{e_label}"
    else:
        overview_stem = f"rhoG_LS_all_other_parameter_sets_{e_label}"
    overview_pdf = fig_dir / f"{overview_stem}.pdf"
    overview_png = fig_dir / f"{overview_stem}.png"
    plot_overview(overview_pdf, overview_png, results, omega, x)

    summary = {
        "data_dir": str(data_dir),
        "fig_dir": str(fig_dir),
        "out_dir": str(out_dir),
        "eta": args.eta,
        "omega_max": args.omega_max,
        "omega_points": args.omega_points,
        "steps_max": args.steps_max,
        "plotted_group_count": len(results),
        "plotted_groups": [
            {
                "U": result.group.U,
                "V": result.group.V,
                "tp": result.group.tp,
                "ylim": result.ylim,
                "root_window": result.root_window,
                "color_vmax": result.color_vmax,
                "accepted_root_count": int(np.isfinite(result.roots).sum()),
                "rejected_root_count": int(result.roots.size - np.isfinite(result.roots).sum()),
                "root_status_counts": status_counts(result.root_rows),
                "pdf": str(result.pdf),
                "png": str(result.png),
                "csv": str(result.csv),
                "npz": str(result.npz),
            }
            for result in results
        ],
        "overview_pdf": str(overview_pdf),
        "overview_png": str(overview_png),
        "skipped_incomplete_groups": incomplete,
        "excluded_main_fig34_groups": [] if args.include_main_fig34 else sorted([list(item) for item in MAIN_FIG34_GROUPS]),
    }
    summary_path = out_dir / f"{overview_stem}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), "overview_pdf": str(overview_pdf), "overview_png": str(overview_png)}, indent=2))


if __name__ == "__main__":
    main()
