#!/usr/bin/env python3
"""Analyze the spinless 16-MMHK t-V benchmark against Zhou et al."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


V_VALUES = [0.45, 1.0, 2.0]
EXPECTED_ROWS = 861
EXPECTED_WEIGHT = 1600.0
NSITES = 16
NPARTICLES = 8
FREE_TL_E0_PER_SITE = -8.0 / math.pi**2
FILENAME_RE = re.compile(
    r"L(?P<Lx>\d+)x(?P<Ly>\d+)N(?P<N>\d+)V(?P<V>[-+0-9.eE]+)"
    r"tp(?P<tp>[-+0-9.eE]+)f(?P<kx>\d+)x(?P<ky>\d+)"
    r"Q(?P<Qx>\d+)x(?P<Qy>\d+)_E0_spinless\.dat"
)


def parse_args():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=root / "data/spinless_tV_mmhk/raw_20260820",
    )
    parser.add_argument(
        "--literature-csv",
        type=Path,
        default=root
        / "data/literature/zeroT_extended_hubbard_benchmarks/zeroT_D_E_literature.csv",
    )
    parser.add_argument("--results-dir", type=Path, default=root / "results")
    parser.add_argument("--figures-dir", type=Path, default=root / "figures")
    return parser.parse_args()


def parse_value(text):
    try:
        return float(text)
    except ValueError:
        return text.strip()


def parse_file(path: Path) -> dict:
    match = FILENAME_RE.fullmatch(path.name)
    if not match:
        raise ValueError(f"Unexpected filename: {path.name}")
    row = {
        key: (float(value) if key in {"V", "tp"} else int(value))
        for key, value in match.groupdict().items()
    }
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2:
            row[fields[0]] = parse_value(fields[1])
    required = {
        "E0",
        "E0_per_site",
        "E0_per_particle",
        "status",
        "max_iterations",
        "seed",
    }
    if missing := required.difference(row):
        raise ValueError(f"{path.name}: missing fields {sorted(missing)}")
    if row["status"] != "COMPLETE" or int(row["max_iterations"]) != 10000:
        raise ValueError(f"{path.name}: incomplete or wrong Lanczos ceiling")
    if (row["Lx"], row["Ly"], row["N"], row["Qx"], row["Qy"]) != (
        4,
        4,
        8,
        0,
        0,
    ):
        raise ValueError(f"{path.name}: unexpected lattice, filling, or Q sector")
    if not math.isclose(float(row["tp"]), 0.0, abs_tol=1e-14):
        raise ValueError(f"{path.name}: expected tp=0")
    if not (0 <= row["kx"] <= row["ky"] <= 40):
        raise ValueError(f"{path.name}: outside the symmetry wedge")
    if not math.isclose(row["E0_per_site"], row["E0"] / NSITES, abs_tol=1e-12):
        raise ValueError(f"{path.name}: inconsistent energy per site")
    if not math.isclose(
        row["E0_per_particle"], row["E0"] / NPARTICLES, abs_tol=1e-12
    ):
        raise ValueError(f"{path.name}: inconsistent energy per particle")
    wx = 0.5 if row["kx"] in {0, 40} else 1.0
    wy = 0.5 if row["ky"] in {0, 40} else 1.0
    row["quadrature_weight"] = wx * wy * (1.0 if row["kx"] == row["ky"] else 2.0)
    row["filename"] = path.name
    return row


def weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(values * weights) / np.sum(weights))


def exact_free_grid_energy_per_site(spacing=1):
    energies = []
    weights = []
    for kx in range(0, 41, spacing):
        for ky in range(kx, 41, spacing):
            fx = kx * math.pi / 40.0 + 0.00001
            fy = ky * math.pi / 40.0 + 0.00001
            levels = sorted(
                -2.0
                * (
                    math.cos(2.0 * math.pi * nx / 4.0 + fx)
                    + math.cos(2.0 * math.pi * ny / 4.0 + fy)
                )
                for nx in range(4)
                for ny in range(4)
            )
            energies.append(sum(levels[:NPARTICLES]) / NSITES)
            wx = 0.5 if kx in {0, 40} else 1.0
            wy = 0.5 if ky in {0, 40} else 1.0
            weights.append(wx * wy * (1.0 if kx == ky else 2.0))
    return weighted_mean(energies, weights)


def load_and_summarize(raw_dir: Path):
    files = sorted(raw_dir.glob("*_E0_spinless.dat"))
    if len(files) != len(V_VALUES) * EXPECTED_ROWS:
        raise ValueError(
            f"Expected {len(V_VALUES)*EXPECTED_ROWS} files, found {len(files)}"
        )
    frame = pd.DataFrame(parse_file(path) for path in files)
    if frame.duplicated(["V", "kx", "ky"]).any():
        raise ValueError("Duplicate (V,kx,ky) rows")
    records = []
    for V in V_VALUES:
        group = frame[np.isclose(frame["V"], V)].copy()
        if len(group) != EXPECTED_ROWS:
            raise ValueError(f"V={V:g}: expected 861 rows, found {len(group)}")
        weight = float(group["quadrature_weight"].sum())
        if not math.isclose(weight, EXPECTED_WEIGHT, abs_tol=1e-12):
            raise ValueError(f"V={V:g}: quadrature weight is {weight}")
        nested = group[(group["kx"] % 2 == 0) & (group["ky"] % 2 == 0)]
        nested_weight = float(nested["quadrature_weight"].sum())
        if len(nested) != 231 or not math.isclose(nested_weight, 400.0):
            raise ValueError(
                f"V={V:g}: invalid nested 21-point grid "
                f"({len(nested)} rows, weight {nested_weight})"
            )
        full_energy = weighted_mean(
            group["E0_per_site"], group["quadrature_weight"]
        )
        nested_energy = weighted_mean(
            nested["E0_per_site"], nested["quadrature_weight"]
        )
        records.append(
            {
                "V_over_t": V,
                "n_rows": len(group),
                "quadrature_weight": weight,
                "E0_per_site_mmhk": full_energy,
                "E0_per_particle_mmhk": weighted_mean(
                    group["E0_per_particle"], group["quadrature_weight"]
                ),
                "E0_per_site_nested_21": nested_energy,
                "nested_21_minus_41": nested_energy - full_energy,
                "unique_seeds": int(group["seed"].nunique()),
                "iterations_min": int(group["max_iterations"].min()),
                "iterations_max": int(group["max_iterations"].max()),
            }
        )
    free = {
        "V_over_t": 0.0,
        "n_rows": 0,
        "quadrature_weight": EXPECTED_WEIGHT,
        # MMHK is exactly noninteracting at V=0.  Use the analytic
        # thermodynamic integral rather than its finite 41-point quadrature.
        "E0_per_site_mmhk": FREE_TL_E0_PER_SITE,
        "E0_per_particle_mmhk": 2.0 * FREE_TL_E0_PER_SITE,
        "E0_per_site_nested_21": np.nan,
        "nested_21_minus_41": np.nan,
        "unique_seeds": 0,
        "iterations_min": 0,
        "iterations_max": 0,
    }
    summary = pd.concat([pd.DataFrame([free]), pd.DataFrame(records)], ignore_index=True)
    return frame, summary


def build_comparison(summary: pd.DataFrame, literature: pd.DataFrame):
    p1 = literature[
        literature["reference"].str.startswith("Zhou et al.")
        & (literature["series"] == "p=1 backflow")
    ][["V_over_t", "value"]].rename(columns={"value": "E0_per_site_zhou_p1"})
    fpeps = literature[
        literature["reference"].str.startswith("Zhou et al.")
        & (literature["series"] == "fPEPS")
    ][["V_over_t", "value"]].rename(columns={"value": "E0_per_site_zhou_fPEPS"})
    v0 = literature[
        literature["record_id"] == "exact_spinless_10x10_obc_E_V0"
    ][["V_over_t", "value"]].rename(columns={"value": "E0_per_site_zhou_p1"})
    p1 = pd.concat([v0, p1], ignore_index=True)
    comparison = summary.merge(p1, on="V_over_t", how="inner").merge(
        fpeps, on="V_over_t", how="left"
    )
    comparison["mmhk_minus_zhou_p1"] = (
        comparison["E0_per_site_mmhk"] - comparison["E0_per_site_zhou_p1"]
    )
    comparison["absolute_percentage_difference"] = 100.0 * (
        comparison["mmhk_minus_zhou_p1"].abs()
        / comparison["E0_per_site_zhou_p1"].abs()
    )
    # The V=0 Zhou baseline is an independently calculated 10x10-OBC value,
    # not a same-boundary MMHK benchmark.  Do not report it as an accuracy
    # deviation.
    comparison.loc[
        np.isclose(comparison["V_over_t"], 0.0),
        "absolute_percentage_difference",
    ] = np.nan
    comparison["mmhk_delta_from_V0"] = (
        comparison["E0_per_site_mmhk"] - comparison.iloc[0]["E0_per_site_mmhk"]
    )
    comparison["zhou_delta_from_V0"] = (
        comparison["E0_per_site_zhou_p1"]
        - comparison.iloc[0]["E0_per_site_zhou_p1"]
    )
    comparison["delta_mmhk_minus_zhou"] = (
        comparison["mmhk_delta_from_V0"] - comparison["zhou_delta_from_V0"]
    )
    comparison["delta_percentage_difference"] = np.where(
        comparison["V_over_t"] > 0,
        100.0
        * comparison["delta_mmhk_minus_zhou"].abs()
        / comparison["zhou_delta_from_V0"].abs(),
        np.nan,
    )
    return comparison


def make_figure(comparison: pd.DataFrame, output_base: Path):
    blue = "#2f5d8a"
    orange = "#c66a2b"
    purple = "#76558b"
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    fig.subplots_adjust(left=0.095, right=0.985, bottom=0.19, top=0.96, wspace=0.34)

    ax = axes[0]
    ax.plot(
        comparison["V_over_t"],
        comparison["E0_per_site_mmhk"],
        "o-",
        color=blue,
        lw=1.6,
        ms=5,
        label="spinless 16-MMHK",
    )
    zhou_finite = comparison[comparison["V_over_t"] > 0]
    ax.plot(
        zhou_finite["V_over_t"],
        zhou_finite["E0_per_site_zhou_p1"],
        "^--",
        color=orange,
        lw=1.35,
        ms=5,
        label=r"Zhou $10\!\times\!10$ OBC, $p=1$",
    )
    zhou_v0 = comparison[np.isclose(comparison["V_over_t"], 0.0)].iloc[0]
    ax.plot(
        [zhou_v0["V_over_t"]],
        [zhou_v0["E0_per_site_zhou_p1"]],
        "^",
        mfc="none",
        mec=orange,
        mew=1.2,
        ms=5.5,
        linestyle="none",
        label=r"exact $10\!\times\!10$ OBC, $V=0$",
    )
    finite = comparison[comparison["E0_per_site_zhou_fPEPS"].notna()]
    ax.plot(
        finite["V_over_t"],
        finite["E0_per_site_zhou_fPEPS"],
        "D",
        mfc="none",
        mec=purple,
        ms=4.2,
        linestyle="none",
        label="Zhou fPEPS",
    )
    ax.set_ylabel(r"$E_0/N_s$")
    ax.legend(frameon=False, fontsize=8, loc="lower right")

    ax = axes[1]
    ax.plot(
        comparison["V_over_t"],
        comparison["mmhk_delta_from_V0"],
        "o-",
        color=blue,
        lw=1.6,
        ms=5,
        label="spinless 16-MMHK",
    )
    ax.plot(
        comparison["V_over_t"],
        comparison["zhou_delta_from_V0"],
        "^--",
        color=orange,
        lw=1.35,
        ms=5,
        label="Zhou $p=1$",
    )
    ax.set_ylabel(r"$[E_0(V)-E_0(0)]/N_s$")

    for index, ax in enumerate(axes):
        ax.set_xlabel(r"$V/t$")
        ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0])
        ax.tick_params(direction="out", length=3, width=0.8, labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(alpha=0.15, lw=0.55)
        ax.text(-0.18, 1.01, "ab"[index], transform=ax.transAxes, fontweight="bold", va="top")

    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.08)
    fig.savefig(output_base.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def main():
    args = parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=True)
    frame, summary = load_and_summarize(args.raw_dir)
    literature = pd.read_csv(args.literature_csv)
    comparison = build_comparison(summary, literature)
    frame.to_csv(args.results_dir / "spinless_tV_mmhk_rows.csv.gz", index=False)
    summary.to_csv(args.results_dir / "spinless_tV_mmhk.csv", index=False)
    comparison.to_csv(args.results_dir / "spinless_tV_benchmark_comparison.csv", index=False)
    manifest = {
        "raw_file_count": len(frame),
        "interaction_sets": V_VALUES,
        "rows_per_set": EXPECTED_ROWS,
        "quadrature_weight_per_set": EXPECTED_WEIGHT,
        "all_complete": True,
        "energy_normalization": "energy per lattice site",
        "free_16mmhk_exact_E0_per_site": FREE_TL_E0_PER_SITE,
        "free_16mmhk_41_grid_estimate_E0_per_site": exact_free_grid_energy_per_site(),
        "free_41_grid_minus_exact": exact_free_grid_energy_per_site()
        - FREE_TL_E0_PER_SITE,
        "free_16mmhk_21_grid_estimate_E0_per_site": exact_free_grid_energy_per_site(
            spacing=2
        ),
        "zhou_V0_baseline": "exact spinless 10x10 open-boundary energy",
        "V0_cross_method_accuracy_deviation_reported": False,
        "nested_21_minus_41_by_V": {
            f"{row.V_over_t:g}": (
                None
                if pd.isna(row.nested_21_minus_41)
                else row.nested_21_minus_41
            )
            for row in summary.itertuples()
        },
    }
    (args.results_dir / "spinless_tV_benchmark_validation.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    make_figure(comparison, args.figures_dir / "spinless_tV_mmhk_benchmark")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
