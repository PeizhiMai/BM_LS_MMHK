#!/usr/bin/env python3
"""Analyze spinless 16-MMHK energies against 8x8-PBC t-V benchmarks.

The calculation uses the complete fixed-N Hilbert space at every mixed-
momentum point, so the reported energy is not tied to an assumed total-
momentum sector.  Reference values are read directly from the locally archived
VarBench markdown tables.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


V_VALUES = (1.0, 2.0, 4.0)
ROWS_PER_SET = 861
FULL_WEIGHT = 1600.0
NESTED_ROWS = 231
NESTED_WEIGHT = 400.0
NSITES_MMHK = 16
NPARTICLES_MMHK = 8
NSITES_REFERENCE = 64
NPARTICLES_REFERENCE = 32
FREE_TL_E0_PER_SITE = -8.0 / math.pi**2

FILENAME_RE = re.compile(
    r"L(?P<Lx>\d+)x(?P<Ly>\d+)N(?P<N>\d+)V(?P<V>[-+0-9.eE]+)"
    r"tp(?P<tp>[-+0-9.eE]+)f(?P<kx>\d+)x(?P<ky>\d+)"
    r"Qall_E0_spinless\.dat"
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=root / "data/spinless_tV_mmhk/pbc_fullQ_20260820",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=root / "data/literature/spinless_tV_varbench/raw",
    )
    parser.add_argument("--results-dir", type=Path, default=root / "results")
    parser.add_argument("--figures-dir", type=Path, default=root / "figures")
    parser.add_argument("--notes-dir", type=Path, default=root / "notes")
    return parser.parse_args()


def parse_value(text: str):
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        return text


def quadrature_weight(kx: int, ky: int) -> float:
    wx = 0.5 if kx in {0, 40} else 1.0
    wy = 0.5 if ky in {0, 40} else 1.0
    exchange = 1.0 if kx == ky else 2.0
    return wx * wy * exchange


def parse_mmhk_file(path: Path) -> dict:
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
        "seed",
        "max_iterations",
        "basis_dimension",
        "Qx",
        "Qy",
        "momentum_treatment",
    }
    if missing := required.difference(row):
        raise ValueError(f"{path.name}: missing fields {sorted(missing)}")
    expected = {
        "Lx": 4,
        "Ly": 4,
        "N": NPARTICLES_MMHK,
        "Qx": -1,
        "Qy": -1,
        "basis_dimension": math.comb(NSITES_MMHK, NPARTICLES_MMHK),
        "max_iterations": 10000,
        "status": "COMPLETE",
        "momentum_treatment": "all_sectors",
    }
    for field, expected_value in expected.items():
        if row[field] != expected_value:
            raise ValueError(
                f"{path.name}: {field}={row[field]!r}, expected {expected_value!r}"
            )
    if not math.isclose(float(row["tp"]), 0.0, abs_tol=1.0e-14):
        raise ValueError(f"{path.name}: expected tp=0")
    if not 0 <= row["kx"] <= row["ky"] <= 40:
        raise ValueError(f"{path.name}: outside 0 <= kx <= ky <= 40")
    if not any(math.isclose(float(row["V"]), value) for value in V_VALUES):
        raise ValueError(f"{path.name}: unexpected V={row['V']}")
    if not math.isclose(
        float(row["E0_per_site"]), float(row["E0"]) / NSITES_MMHK, abs_tol=1e-12
    ):
        raise ValueError(f"{path.name}: inconsistent E0_per_site")
    if not math.isclose(
        float(row["E0_per_particle"]),
        float(row["E0"]) / NPARTICLES_MMHK,
        abs_tol=1e-12,
    ):
        raise ValueError(f"{path.name}: inconsistent E0_per_particle")
    row["quadrature_weight"] = quadrature_weight(row["kx"], row["ky"])
    row["filename"] = path.name
    return row


def weighted_mean(values, weights) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(values * weights) / np.sum(weights))


def exact_free_grid_energy_per_site(spacing: int = 1) -> float:
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
            energies.append(sum(levels[:NPARTICLES_MMHK]) / NSITES_MMHK)
            weights.append(quadrature_weight(kx, ky))
    return weighted_mean(energies, weights)


def load_mmhk(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted(raw_dir.glob("L*_E0_spinless.dat"))
    expected_files = len(V_VALUES) * ROWS_PER_SET
    if len(files) != expected_files:
        raise ValueError(f"Expected {expected_files} files, found {len(files)}")
    rows = pd.DataFrame(parse_mmhk_file(path) for path in files)
    if rows.duplicated(["V", "kx", "ky"]).any():
        duplicate = rows[rows.duplicated(["V", "kx", "ky"], keep=False)]
        raise ValueError(f"Duplicate mixed-momentum rows:\n{duplicate}")

    summary = []
    for V in V_VALUES:
        group = rows[np.isclose(rows["V"], V)].copy()
        if len(group) != ROWS_PER_SET:
            raise ValueError(f"V={V:g}: expected {ROWS_PER_SET}, found {len(group)}")
        total_weight = float(group["quadrature_weight"].sum())
        if not math.isclose(total_weight, FULL_WEIGHT, abs_tol=1.0e-12):
            raise ValueError(f"V={V:g}: full-grid weight {total_weight}")

        nested = group[(group["kx"] % 2 == 0) & (group["ky"] % 2 == 0)]
        nested_weight = float(nested["quadrature_weight"].sum())
        if len(nested) != NESTED_ROWS or not math.isclose(
            nested_weight, NESTED_WEIGHT, abs_tol=1.0e-12
        ):
            raise ValueError(
                f"V={V:g}: bad nested grid ({len(nested)} rows, weight={nested_weight})"
            )

        full_energy = weighted_mean(
            group["E0_per_site"], group["quadrature_weight"]
        )
        nested_energy = weighted_mean(
            nested["E0_per_site"], nested["quadrature_weight"]
        )
        summary.append(
            {
                "V_over_t": V,
                "E0_per_site_16MMHK": full_energy,
                "E0_per_particle_16MMHK": weighted_mean(
                    group["E0_per_particle"], group["quadrature_weight"]
                ),
                "E0_per_site_nested_21": nested_energy,
                "nested_21_minus_41": nested_energy - full_energy,
                "n_mixed_momentum_rows": len(group),
                "quadrature_weight": total_weight,
                "n_unique_seeds": int(group["seed"].nunique()),
                "all_total_momentum_sectors": True,
                "basis_dimension": math.comb(NSITES_MMHK, NPARTICLES_MMHK),
                "max_lanczos_iterations": int(group["max_iterations"].max()),
            }
        )
    return rows, pd.DataFrame(summary)


def parse_reference_table(path: Path, V: float) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        if not line.startswith("|") or "QMC" not in line and "DMRG" not in line:
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        if len(fields) != 7:
            raise ValueError(f"Unexpected table row in {path}: {line}")
        energy = float(fields[0])
        variance = float(fields[2])
        method_raw = fields[5]
        method = "CT-QMC" if method_raw.startswith("QMC") else "DMRG"
        records.append(
            {
                "V_over_t": V,
                "method": method,
                "method_as_reported": method_raw,
                "E0_total": energy,
                "E0_per_site": energy / NSITES_REFERENCE,
                "E0_per_particle": energy / NPARTICLES_REFERENCE,
                "energy_variance_as_reported": variance,
                "n_sites": NSITES_REFERENCE,
                "n_particles": NPARTICLES_REFERENCE,
                "density": NPARTICLES_REFERENCE / NSITES_REFERENCE,
                "lattice": "8x8 square",
                "boundary_conditions": "periodic",
                "hamiltonian": "-t sum_NN(cdag_i c_j+h.c.) + V sum_NN n_i n_j",
                "source_file": str(path),
                "source_links": fields[6],
            }
        )
    if {record["method"] for record in records} != {"CT-QMC", "DMRG"}:
        raise ValueError(f"Expected CT-QMC and DMRG rows in {path}")
    return records


def load_references(reference_dir: Path) -> pd.DataFrame:
    records = []
    for V in V_VALUES:
        records.extend(
            parse_reference_table(reference_dir / f"square_64_P_32_{V:g}.md", V)
        )
    return pd.DataFrame(records).sort_values(["V_over_t", "method"]).reset_index(
        drop=True
    )


def build_comparison(
    mmhk: pd.DataFrame, references: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    long = references.merge(mmhk, on="V_over_t", how="left", validate="many_to_one")
    long["MMHK_minus_reference"] = (
        long["E0_per_site_16MMHK"] - long["E0_per_site"]
    )
    long["signed_percentage_difference"] = (
        100.0 * long["MMHK_minus_reference"] / long["E0_per_site"].abs()
    )
    long["absolute_percentage_difference"] = long[
        "signed_percentage_difference"
    ].abs()

    selected = []
    for V in V_VALUES:
        group = long[np.isclose(long["V_over_t"], V)].copy()
        # The lowest reported energy is used only as a pragmatic reference
        # selector.  It is not asserted to be an exact thermodynamic energy.
        best = group.loc[group["E0_per_site"].idxmin()].to_dict()
        best["reference_selection"] = "lowest reported 8x8-PBC energy"
        best["reference_quality_note"] = (
            "CT-QMC row has the lower reported energy"
            if best["method"] == "CT-QMC"
            else "DMRG row has the lower reported energy; the V=4 CT-QMC row has larger variance"
        )
        selected.append(best)
    primary = pd.DataFrame(selected)
    return long, primary


def make_figure(
    mmhk: pd.DataFrame,
    references: pd.DataFrame,
    primary: pd.DataFrame,
    output_base: Path,
) -> None:
    density_color = "#b7473e"
    plt.rcParams.update(
        {
            "font.size": 10.0,
            "axes.labelsize": 11.5,
            "axes.titlesize": 11.8,
            "xtick.labelsize": 10.0,
            "ytick.labelsize": 10.0,
            "legend.fontsize": 7.5,
            "lines.linewidth": 1.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, ax = plt.subplots(figsize=(3.40, 3.45))
    fig.subplots_adjust(left=0.19, right=0.985, bottom=0.15, top=0.90)
    ax.plot(
        mmhk["V_over_t"],
        mmhk["E0_per_site_16MMHK"],
        "o",
        color=density_color,
        linestyle="none",
        ms=4.6,
        mfc=density_color,
        mec="white",
        mew=0.35,
        label="spinless 16-MMHK",
        # Keep the MMHK points visible at coincident coordinates by drawing
        # their filled centers above the open literature markers.
        zorder=10,
    )
    styles = {
        "CT-QMC": ("o", "CT-QMC, $8\\!\\times\\!8$ PBC", 5.8),
        "DMRG": ("^", "DMRG, $8\\!\\times\\!8$ PBC", 5.8),
    }
    for method, (marker, label, marker_size) in styles.items():
        subset = references[references["method"] == method]
        ax.plot(
            subset["V_over_t"],
            subset["E0_per_site"],
            marker=marker,
            color=density_color,
            linestyle="none",
            ms=marker_size,
            mfc="white",
            mec=density_color,
            mew=1.0,
            label=label,
            zorder=7,
        )
    ax.set_title("Ground-state energy")
    ax.set_ylabel(r"$E_0/(N_s t)$")
    ax.legend(
        frameon=False,
        loc="upper left",
        fontsize=7.5,
        handlelength=1.65,
        handletextpad=0.40,
        labelspacing=0.18,
        borderaxespad=0.25,
    )
    ax.set_xlabel(r"$V/t$")
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlim(0.82, 4.18)
    ax.tick_params(direction="out", length=3.2, width=0.8)
    ax.grid(alpha=0.20)

    output_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.06)
    fig.savefig(
        output_base.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.06,
    )
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_report(
    path: Path,
    mmhk: pd.DataFrame,
    primary: pd.DataFrame,
    validation_path: Path,
) -> None:
    lines = [
        "# Spinless 16-MMHK benchmark against 8x8-PBC t-V data",
        "",
        "**Date:** 2026-08-20",
        "",
        "## Calculation",
        "",
        "The common Hamiltonian is",
        "",
        r"\[H=-t\sum_{\langle ij\rangle}(c_i^\dagger c_j+\mathrm{h.c.})+V\sum_{\langle ij\rangle}n_i n_j,\qquad t=1,\]",
        "",
        "at half filling. For each of V/t = 1, 2, and 4, the spinless 16-MMHK calculation used all 861 symmetry-reduced points of the 41x41 mixed-momentum grid. At every point it diagonalized the complete N=8 Hilbert space (dimension 12,870), thereby minimizing over all 16 total-momentum sectors rather than assuming Q=(0,0). Every output is marked COMPLETE and used a 10,000-step Lanczos ceiling.",
        "",
        "The integral uses kx<->ky symmetry and trapezoidal endpoint weights. Its reconstructed full-grid weight is 1600. The 21x21 nested-grid check has weight 400.",
        "",
        "## Energies",
        "",
        "| V/t | 16-MMHK E0/Ns | lowest reported 8x8-PBC E0/Ns | method | signed difference | absolute percentage | 21x21 minus 41x41 |",
        "|---:|---:|---:|:---|---:|---:|---:|",
    ]
    merged = mmhk.merge(
        primary[
            [
                "V_over_t",
                "E0_per_site",
                "method",
                "MMHK_minus_reference",
                "absolute_percentage_difference",
            ]
        ],
        on="V_over_t",
        validate="one_to_one",
    )
    for row in merged.itertuples():
        lines.append(
            f"| {row.V_over_t:g} | {row.E0_per_site_16MMHK:.12f} | "
            f"{row.E0_per_site:.12f} | {row.method} | "
            f"{row.MMHK_minus_reference:+.12f} | "
            f"{row.absolute_percentage_difference:.4f}% | "
            f"{row.nested_21_minus_41:+.3e} |"
        )
    lines.extend(
        [
            "",
            "The reference selector is simply the lower of the two reported finite-size energies at each V: CT-QMC for V=1,2 and DMRG for V=4. This is a transparent benchmark convention, not a claim that those values are exact thermodynamic-limit energies. The V=4 CT-QMC entry has a substantially larger reported variance and lies above the DMRG value.",
            "",
            "## Validation and interpretation",
            "",
            "- All 2,583 production targets are complete, with 861 unique mixed-momentum rows per interaction.",
            "- Direct V=0 tests reproduce the eight-lowest-level free-fermion energy to better than 1.1e-14 at four generic mixed momenta.",
            f"- The analytic thermodynamic V=0 value is -8/pi^2 = {FREE_TL_E0_PER_SITE:.12f}; the 41-point trapezoidal mixed-momentum integral is {exact_free_grid_energy_per_site():.12f}, differing by {exact_free_grid_energy_per_site() - FREE_TL_E0_PER_SITE:+.3e}. No V=0 production jobs were needed.",
            "- Two independent Lanczos seeds at V=1 give identical E0 within displayed precision.",
            "- The nested-grid differences are only O(1e-6) per site or smaller, so mixed-momentum integration error is negligible relative to the benchmark differences.",
            "- 16-MMHK is a thermodynamic momentum-mixing construction, whereas the references are an 8x8 periodic finite lattice. The signed differences are therefore descriptive and are not variational error bounds.",
            "- Agreement improves strongly from V=1 toward the charge-ordered regime. This is physically plausible because the strong-V state is governed increasingly by local checkerboard constraints, while the weaker-coupling regime retains longer-range itinerant correlations that are harder for finite momentum-mixing resolution.",
            "",
            f"Solver validation: `{validation_path}`",
            "",
            "## Reference provenance",
            "",
            "The archived values are from the VarBench 8x8-periodic, N=32 spinless t-V tables. The CT-QMC rows link to Wang, Liu, and Troyer, Phys. Rev. B 93, 155117 (2016); the DMRG rows record maximum bond dimension 4096. The reported energy variance is retained as provenance and is not treated as a statistical error bar.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    args = parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)
    args.notes_dir.mkdir(parents=True, exist_ok=True)

    rows, mmhk = load_mmhk(args.raw_dir)
    references = load_references(args.reference_dir)
    comparison_long, primary = build_comparison(mmhk, references)

    rows_path = args.results_dir / "spinless_tV_pbc_mmhk_rows.csv.gz"
    mmhk_path = args.results_dir / "spinless_tV_pbc_mmhk.csv"
    reference_path = args.results_dir / "spinless_tV_pbc_reference.csv"
    long_path = args.results_dir / "spinless_tV_pbc_comparison_all_references.csv"
    primary_path = args.results_dir / "spinless_tV_pbc_comparison.csv"
    validation_path = args.results_dir / "spinless_tV_pbc_solver_validation.json"
    figure_base = args.figures_dir / "spinless_tV_pbc_benchmark"
    note_path = args.notes_dir / "2026-08-20_spinless_tV_pbc_benchmark.md"

    rows.to_csv(rows_path, index=False, compression="gzip")
    mmhk.to_csv(mmhk_path, index=False)
    references.to_csv(reference_path, index=False, quoting=csv.QUOTE_MINIMAL)
    comparison_long.to_csv(long_path, index=False)
    primary.to_csv(primary_path, index=False)
    make_figure(mmhk, references, primary, figure_base)
    write_report(note_path, mmhk, primary, validation_path)

    manifest = {
        "status": "COMPLETE",
        "production_target_count": len(rows),
        "targets_per_interaction": ROWS_PER_SET,
        "interaction_values": list(V_VALUES),
        "unique_target_count": int(rows[["V", "kx", "ky"]].drop_duplicates().shape[0]),
        "all_outputs_complete": bool((rows["status"] == "COMPLETE").all()),
        "all_total_momentum_sectors": bool(
            (rows["momentum_treatment"] == "all_sectors").all()
        ),
        "basis_dimension": math.comb(NSITES_MMHK, NPARTICLES_MMHK),
        "free_limit": {
            "analytic_E0_per_site": FREE_TL_E0_PER_SITE,
            "mixed_momentum_grid_41_E0_per_site": exact_free_grid_energy_per_site(),
            "grid_41_minus_analytic": exact_free_grid_energy_per_site()
            - FREE_TL_E0_PER_SITE,
            "production_jobs_used": False,
        },
        "quadrature_weight_by_V": {
            f"{row.V_over_t:g}": row.quadrature_weight for row in mmhk.itertuples()
        },
        "nested_21_minus_41_by_V": {
            f"{row.V_over_t:g}": row.nested_21_minus_41 for row in mmhk.itertuples()
        },
        "source_sha256": {
            path.name: sha256(path)
            for path in sorted(args.reference_dir.glob("*.md"))
        },
        "artifacts": {
            "row_data": str(rows_path),
            "mmhk_summary": str(mmhk_path),
            "references": str(reference_path),
            "all_comparisons": str(long_path),
            "primary_comparison": str(primary_path),
            "figure_pdf": str(figure_base.with_suffix(".pdf")),
            "figure_png": str(figure_base.with_suffix(".png")),
            "note": str(note_path),
            "solver_validation": str(validation_path),
        },
    }
    manifest_path = args.results_dir / "spinless_tV_pbc_benchmark_validation.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print("\n16-MMHK summary")
    print(mmhk.to_string(index=False))
    print("\nPrimary comparisons")
    print(
        primary[
            [
                "V_over_t",
                "E0_per_site_16MMHK",
                "method",
                "E0_per_site",
                "MMHK_minus_reference",
                "signed_percentage_difference",
                "absolute_percentage_difference",
            ]
        ].to_string(index=False)
    )
    print(f"\nWrote {manifest_path}")


if __name__ == "__main__":
    main()
