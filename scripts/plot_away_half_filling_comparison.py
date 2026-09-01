#!/usr/bin/env python3
"""Plot doped MMHK observables against published CP-AFQMC and DMET data.

The four panels separate density and observable so that unlike magnetic-order
definitions do not enter the comparison.  Filled symbols denote compact
thermodynamic benchmark estimates.  Small open symbols expose the underlying
stripe-state/system spread from Zheng et al. (2017), rather than converting
that spread into an artificial statistical error bar.
"""
from __future__ import annotations

from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from manuscript_figure_style import outside_panel_label


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LITERATURE = ROOT / "data" / "literature" / "doped_hubbard_benchmarks"
OUT = ROOT / "figures" / "pnas_supplement"

MMHK_SOURCE = RESULTS / "mmhk_observables_all_cases.csv"
DMET_TDL_SOURCE = LITERATURE / "zheng_chan_2016_TDL.csv"
DMET_4X4_SOURCE = LITERATURE / "leblanc2015_dmet_4x4.csv"
STRIPE_SOURCES = {
    U: LITERATURE / f"zheng_et_al_2017_U{U}_summary.csv"
    for U in (6, 8, 12)
}

LEBLANC_URL = "https://doi.org/10.1103/PhysRevX.5.041041"
QIN_URL = "https://doi.org/10.1103/PhysRevB.94.085103"
ZHENG_CHAN_URL = "https://authors.library.caltech.edu/records/z3ca4-4t019"
STRIPE_URL = "https://github.com/zhengbx/stripe_data"

COLORS = {
    "MMHK": "#b7473e",
    "CP-AFQMC": "#2d6f9f",
    "DMET": "#3f8a55",
}

STYLE = {
    "font.family": "Arial",
    "font.size": 10.5,
    "axes.labelsize": 12.0,
    "axes.titlesize": 12.0,
    "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5,
    "legend.fontsize": 9.2,
    "axes.linewidth": 1.0,
    "lines.linewidth": 1.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def mmhk_rows() -> pd.DataFrame:
    """Return the two doped MMHK sequences in long format."""
    source = pd.read_csv(MMHK_SOURCE)
    source = source[source["n_target"].isin([0.8, 0.875])].copy()
    expected_u = {2.0, 4.0, 6.0, 8.0, 10.0, 12.0}
    for density in (0.8, 0.875):
        found = set(source.loc[np.isclose(source["n_target"], density), "U"])
        if found != expected_u:
            raise ValueError(
                f"Incomplete MMHK grid at n={density}: found U={sorted(found)}"
            )

    records: list[dict[str, object]] = []
    observable_columns = {
        "energy": "ground_state_energy",
        "double_occupancy": "double_occupancy_i",
    }
    for observable, column in observable_columns.items():
        for row in source.itertuples(index=False):
            records.append(
                {
                    "density": float(row.n_target),
                    "U": float(row.U),
                    "observable": observable,
                    "method": "MMHK",
                    "study": "present work",
                    "value": float(getattr(row, column)),
                    "sigma": np.nan,
                    "record_type": "model_result",
                    "quality_flag": "complete_mmhk_sequence",
                    "system": "4x4 momentum-mixing resolution",
                    "boundary": "",
                    "state": "",
                    "source_url": "",
                    "source_local": str(MMHK_SOURCE.relative_to(ROOT)),
                }
            )
    return pd.DataFrame.from_records(records)


def compact_cp_afqmc_rows() -> pd.DataFrame:
    """Published constrained-path AFQMC values at the two target densities."""
    # LeBlanc et al. PRX 5, 041041 (2015), Tables IV-V, and
    # Qin, Shi, Zhang PRB 94, 085103 (2016), Sec. IV B.
    values = [
        # density, U, observable, value, sigma
        (0.8, 2.0, "energy", -1.306, 0.002),
        (0.8, 4.0, "energy", -1.110, 0.003),
        (0.875, 4.0, "energy", -1.026, 0.001),
        (0.875, 8.0, "energy", -0.766, 0.001),
        (0.875, 4.0, "double_occupancy", 0.0940, 0.0003),
        (0.875, 8.0, "double_occupancy", 0.0403, 0.0002),
    ]
    return pd.DataFrame(
        [
            {
                "density": density,
                "U": U,
                "observable": observable,
                "method": "CP-AFQMC",
                "study": "LeBlanc et al. 2015; Qin et al. 2016",
                "value": value,
                "sigma": sigma,
                "record_type": "benchmark_tdl",
                "quality_flag": "published_constrained_path_estimate",
                "system": "thermodynamic estimate",
                "boundary": "twist averaged",
                "state": "",
                "source_url": f"{LEBLANC_URL}; {QIN_URL}",
                "source_local": "",
            }
            for density, U, observable, value, sigma in values
        ]
    )


def dmet_tdl_rows() -> pd.DataFrame:
    """Read the published DMET thermodynamic-limit table."""
    source = pd.read_csv(DMET_TDL_SOURCE)
    source = source[
        np.isclose(source["tprime"], 0.0)
        & source["n"].isin([0.8, 0.875])
        & source["U"].isin([2.0, 4.0, 6.0, 8.0])
    ].copy()

    records: list[dict[str, object]] = []
    for row in source.itertuples(index=False):
        comment = "" if pd.isna(row.comment) else str(row.comment)
        quality = (
            "published_tdl"
            if not comment
            else "flagged_cluster_or_inhomogeneity_sensitive"
        )
        for observable, value, sigma in (
            ("energy", row.E, row.eE),
            ("double_occupancy", row.DoubleOcc, row.eDoubleOcc),
        ):
            if pd.isna(value):
                continue
            records.append(
                {
                    "density": float(row.n),
                    "U": float(row.U),
                    "observable": observable,
                    "method": "DMET",
                    "study": "Zheng and Chan 2016",
                    "value": float(value),
                    "sigma": np.nan if pd.isna(sigma) else float(sigma),
                    "record_type": "benchmark_tdl",
                    "quality_flag": quality,
                    "system": "thermodynamic extrapolation",
                    "boundary": "",
                    "state": comment,
                    "source_url": ZHENG_CHAN_URL,
                    "source_local": str(DMET_TDL_SOURCE.relative_to(ROOT)),
                }
            )
    return pd.DataFrame.from_records(records)


def dmet_embedding_double_occupancy_rows() -> pd.DataFrame:
    """Finite-embedding DMET D values at n=0.875, U=8 from LeBlanc data."""
    values = [
        ("2x2", 0.0446281336, 0.0),
        ("4x2", 0.04249, 0.00004),
        ("4x4", 0.0414, 0.0003),
        ("8x2", 0.04333, 0.0004),
    ]
    return pd.DataFrame(
        [
            {
                "density": 0.875,
                "U": 8.0,
                "observable": "double_occupancy",
                "method": "DMET",
                "study": "LeBlanc et al. 2015 ancillary data",
                "value": value,
                "sigma": sigma,
                "record_type": "finite_embedding",
                "quality_flag": "not_tdl_extrapolated",
                "system": system,
                "boundary": "",
                "state": "",
                "source_url": LEBLANC_URL,
                "source_local": "",
            }
            for system, value, sigma in values
        ]
    )


def dmet_4x4_rows() -> pd.DataFrame:
    """Read unextrapolated 4x4 DMET values from the LeBlanc ancillary data."""
    source = pd.read_csv(DMET_4X4_SOURCE)
    expected_columns = {
        "density",
        "U",
        "observable",
        "value",
        "sigma",
        "system",
        "original_ancillary_file",
    }
    if set(source.columns) != expected_columns:
        raise ValueError(
            f"Unexpected columns in {DMET_4X4_SOURCE}: {list(source.columns)}"
        )
    if not source["system"].astype(str).eq("4x4").all():
        raise ValueError("The curated DMET source contains a non-4x4 row")
    if source.duplicated(["density", "U", "observable"]).any():
        raise ValueError("Duplicate 4x4 DMET observable rows")

    records: list[dict[str, object]] = []
    for row in source.itertuples(index=False):
        records.append(
            {
                "density": float(row.density),
                "U": float(row.U),
                "observable": str(row.observable),
                "method": "DMET",
                "study": "LeBlanc et al. 2015 ancillary data",
                "value": float(row.value),
                "sigma": float(row.sigma),
                "record_type": "finite_embedding",
                "quality_flag": "unextrapolated_4x4_embedding",
                "system": "4x4",
                "boundary": "",
                "state": "",
                "source_url": LEBLANC_URL,
                "source_local": str(DMET_4X4_SOURCE.relative_to(ROOT)),
                "original_source_local": str(row.original_ancillary_file),
            }
        )
    return pd.DataFrame.from_records(records)


def stripe_energy_rows() -> pd.DataFrame:
    """Load every published AFQMC/DMET stripe-summary energy row."""
    records: list[dict[str, object]] = []
    for U, path in STRIPE_SOURCES.items():
        source = pd.read_csv(path, skipinitialspace=True)
        source["method"] = source["method"].astype(str).str.strip()
        source = source[source["method"].isin(["AFQMC", "DMET"])]
        for row in source.itertuples(index=False):
            method = "CP-AFQMC" if row.method == "AFQMC" else "DMET"
            records.append(
                {
                    "density": 0.875,
                    "U": float(U),
                    "observable": "energy",
                    "method": method,
                    "study": "Zheng et al. 2017",
                    "value": float(row.energy),
                    "sigma": float(row.error),
                    "record_type": "stripe_resolved",
                    "quality_flag": "geometry_and_state_resolved_not_single_tdl_value",
                    "system": str(row.system).strip(),
                    "boundary": str(row.boundary).strip(),
                    "state": str(row.state).strip(),
                    "source_url": STRIPE_URL,
                    "source_local": str(path.relative_to(ROOT)),
                }
            )
    return pd.DataFrame.from_records(records)


def _add_mmhk_deltas(data: pd.DataFrame) -> pd.DataFrame:
    """Attach like-density MMHK differences to a comparison table."""
    data = data.sort_values(
        ["density", "observable", "U", "record_type", "method", "system"],
        kind="stable",
    ).reset_index(drop=True)
    mmhk_lookup = (
        data[data["method"].eq("MMHK")]
        .set_index(["density", "U", "observable"])["value"]
        .to_dict()
    )
    data["mmhk_value"] = [
        mmhk_lookup.get((row.density, row.U, row.observable), np.nan)
        for row in data.itertuples(index=False)
    ]
    data["mmhk_minus_reference"] = data["mmhk_value"] - data["value"]
    data["relative_delta_percent"] = (
        100.0 * data["mmhk_minus_reference"] / data["value"]
    )
    data.loc[
        data["method"].eq("MMHK"),
        ["mmhk_minus_reference", "relative_delta_percent"],
    ] = 0.0
    return data


def build_figs2_strict_dataset() -> pd.DataFrame:
    """Build the deliberately finite, nonextrapolated doped comparison.

    The doped literature points used in main-text Fig. 1 obey three source-selection
    rules: CP-AFQMC rows must be explicit TABC calculations, BCS-state rows
    are excluded, and DMET rows must be unextrapolated 4x4 embeddings.
    Thermodynamic-limit extrapolations are not included.
    """
    tabc = stripe_energy_rows()
    tabc = tabc[
        tabc["method"].eq("CP-AFQMC")
        & tabc["boundary"].astype(str).str.upper().eq("TABC")
        & ~tabc["state"].astype(str).str.contains(
            "BCS", case=False, na=False
        )
    ].copy()
    tabc["record_type"] = "tabc_resolved"
    tabc["quality_flag"] = "finite_tabc_state_resolved"

    data = pd.concat(
        [mmhk_rows(), tabc, dmet_4x4_rows()],
        ignore_index=True,
        sort=False,
    )

    external = data[~data["method"].eq("MMHK")]
    if external["record_type"].eq("benchmark_tdl").any():
        raise ValueError("Figure 1 strict data unexpectedly contain a TDL row")
    if external["state"].astype(str).str.contains(
        "BCS", case=False, na=False
    ).any():
        raise ValueError("Figure 1 strict data unexpectedly contain a BCS row")
    cp_rows = external[external["method"].eq("CP-AFQMC")]
    if not cp_rows["boundary"].astype(str).str.upper().eq("TABC").all():
        raise ValueError("Figure 1 contains a non-TABC CP-AFQMC row")
    dmet_rows = external[external["method"].eq("DMET")]
    if not dmet_rows["system"].astype(str).eq("4x4").all():
        raise ValueError("Figure 1 contains a non-4x4 DMET row")

    return _add_mmhk_deltas(data)


def _finite_system_sites(system: object) -> int:
    """Return the site count encoded by a finite ``LxW`` system label."""
    match = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", str(system))
    if match is None:
        raise ValueError(f"Cannot parse finite system size: {system!r}")
    return int(match.group(1)) * int(match.group(2))


def select_figs2_doped_references(data: pd.DataFrame) -> pd.DataFrame:
    """Select one energy and a paired/closest D for each doped parameter set.

    Selection order:

    1. Within CP-AFQMC at fixed (n,U), retain the largest finite TABC system;
       if that size has several states, retain the lowest energy.
    2. Across the retained CP-AFQMC and 4x4 DMET candidates at fixed (n,U),
       retain the lowest energy.
    3. For double occupancy, use the same method and system as the selected
       energy when available. Otherwise use a retained D at the same (n,U),
       preferring the same method. No D is borrowed across U or density.
    """
    mmhk = data[data["method"].eq("MMHK")].copy()
    external = data[~data["method"].eq("MMHK")].copy()

    cp = external[
        external["method"].eq("CP-AFQMC")
        & external["observable"].eq("energy")
    ].copy()
    cp["system_sites"] = cp["system"].map(_finite_system_sites)
    retained_cp: list[pd.DataFrame] = []
    for (_, _), rows in cp.groupby(["density", "U"], sort=True):
        largest = rows[rows["system_sites"].eq(rows["system_sites"].max())]
        retained_cp.append(largest.nsmallest(1, "value"))
    cp_largest = (
        pd.concat(retained_cp, ignore_index=True)
        if retained_cp
        else cp.iloc[0:0].copy()
    )
    cp_largest["candidate_selection"] = (
        "largest_finite_tabc_system_then_lowest_energy"
    )

    dmet = external[external["method"].eq("DMET")].copy()
    dmet["candidate_selection"] = "unextrapolated_4x4_embedding"
    candidate_pool = pd.concat([cp_largest, dmet], ignore_index=True, sort=False)

    energy_candidates = candidate_pool[
        candidate_pool["observable"].eq("energy")
    ].copy()
    selected_energy_rows: list[pd.Series] = []
    for (_, _), rows in energy_candidates.groupby(["density", "U"], sort=True):
        selected = rows.loc[rows["value"].idxmin()].copy()
        selected["selection_reason"] = (
            "lowest_energy_after_largest_system_filter"
            if len(rows) > 1
            else "only_retained_energy"
        )
        selected["paired_energy_method"] = selected["method"]
        selected["paired_energy_system"] = selected["system"]
        selected["paired_energy_value"] = selected["value"]
        selected_energy_rows.append(selected)
    selected_energy = pd.DataFrame(selected_energy_rows)

    d_candidates = candidate_pool[
        candidate_pool["observable"].eq("double_occupancy")
    ].copy()
    selected_d_rows: list[pd.Series] = []
    for energy in selected_energy.itertuples(index=False):
        same_parameter = d_candidates[
            np.isclose(d_candidates["density"], float(energy.density))
            & np.isclose(d_candidates["U"], float(energy.U))
        ].copy()
        if same_parameter.empty:
            continue

        exact = same_parameter[
            same_parameter["method"].eq(energy.method)
            & same_parameter["system"].astype(str).eq(str(energy.system))
        ]
        if not exact.empty:
            chosen = exact.iloc[0].copy()
            pairing = "corresponding_method_and_system"
        else:
            same_method = same_parameter[
                same_parameter["method"].eq(energy.method)
            ]
            if not same_method.empty:
                chosen = same_method.sort_values("system").iloc[-1].copy()
                pairing = "closest_same_method_same_parameter"
            else:
                # The fallback remains at exactly the same (n,U); borrowing a
                # D from another interaction would falsely move an observable.
                chosen = same_parameter.sort_values(
                    ["method", "system"], kind="stable"
                ).iloc[0].copy()
                pairing = "closest_same_parameter_other_method"

        chosen["selection_reason"] = pairing
        chosen["paired_energy_method"] = energy.method
        chosen["paired_energy_system"] = energy.system
        chosen["paired_energy_value"] = energy.value
        selected_d_rows.append(chosen)

    selected_d = (
        pd.DataFrame(selected_d_rows)
        if selected_d_rows
        else d_candidates.iloc[0:0].copy()
    )
    selected_external = pd.concat(
        [selected_energy, selected_d],
        ignore_index=True,
        sort=False,
    )

    if selected_energy.duplicated(["density", "U"]).any():
        raise ValueError("More than one selected doped energy at fixed (n,U)")
    if selected_d.duplicated(["density", "U"]).any():
        raise ValueError("More than one selected doped D at fixed (n,U)")
    selected_cp = selected_external[
        selected_external["method"].eq("CP-AFQMC")
    ]
    if not selected_cp["system"].astype(str).eq("20x8").all():
        raise ValueError("A selected CP-AFQMC row is not the largest 20x8 TABC system")

    return _add_mmhk_deltas(
        pd.concat([mmhk, selected_external], ignore_index=True, sort=False)
    )


def build_dataset() -> pd.DataFrame:
    frames = [
        mmhk_rows(),
        compact_cp_afqmc_rows(),
        dmet_tdl_rows(),
        dmet_embedding_double_occupancy_rows(),
        stripe_energy_rows(),
    ]
    return _add_mmhk_deltas(pd.concat(frames, ignore_index=True))


def deterministic_jitter(count: int, half_width: float) -> np.ndarray:
    if count <= 1:
        return np.zeros(count)
    return np.linspace(-half_width, half_width, count)


def panel_label(ax: plt.Axes, label: str) -> None:
    outside_panel_label(ax, label, fontsize=11.5)


def plot(
    data: pd.DataFrame, *, simplified_legend: bool = False
) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    stem = (
        "pnas_supp_away_half_filling_comparison_simple_legend"
        if simplified_legend
        else "pnas_supp_away_half_filling_comparison"
    )
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"

    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.65), sharex=True)

        panel_specs = [
            (0.8, "energy", r"Ground-state energy", r"$E_0/(Nt)$"),
            (
                0.8,
                "double_occupancy",
                r"Double occupancy",
                r"$D=\langle n_{i\uparrow}n_{i\downarrow}\rangle$",
            ),
            (0.875, "energy", r"Ground-state energy", r"$E_0/(Nt)$"),
            (
                0.875,
                "double_occupancy",
                r"Double occupancy",
                r"$D=\langle n_{i\uparrow}n_{i\downarrow}\rangle$",
            ),
        ]

        for idx, (ax, (density, observable, title, ylabel)) in enumerate(
            zip(axes.ravel(), panel_specs)
        ):
            group = data[
                np.isclose(data["density"], density)
                & data["observable"].eq(observable)
            ]

            mmhk = group[group["method"].eq("MMHK")].sort_values("U")
            ax.plot(
                mmhk["U"],
                mmhk["value"],
                color=COLORS["MMHK"],
                marker="s",
                ms=5.3,
                label=r"$4\times4$ MMHK",
                zorder=3,
            )

            for method, marker in (("CP-AFQMC", "o"), ("DMET", "^")):
                method_offset = -0.085 if method == "CP-AFQMC" else 0.085
                benchmark = group[
                    group["method"].eq(method)
                    & group["record_type"].eq("benchmark_tdl")
                ]
                regular = benchmark[
                    ~benchmark["quality_flag"].str.startswith("flagged")
                ].sort_values("U")
                if not regular.empty:
                    ax.errorbar(
                        regular["U"] + method_offset,
                        regular["value"],
                        yerr=regular["sigma"].fillna(0.0),
                        fmt=marker,
                        ms=6.0,
                        capsize=2.4,
                        color=COLORS[method],
                        mec="white",
                        mew=0.45,
                        linestyle="none",
                        zorder=6,
                    )

                flagged = benchmark[
                    benchmark["quality_flag"].str.startswith("flagged")
                ].sort_values("U")
                if not flagged.empty:
                    ax.errorbar(
                        flagged["U"] + method_offset,
                        flagged["value"],
                        yerr=flagged["sigma"].fillna(0.0),
                        fmt=marker if simplified_legend else "X",
                        ms=6.2,
                        capsize=2.4,
                        color=COLORS[method],
                        mfc="white",
                        mew=1.15,
                        linestyle="none",
                        alpha=0.88,
                        zorder=5,
                    )

            stripe = group[group["record_type"].eq("stripe_resolved")]
            for method, marker, x_center in (
                ("CP-AFQMC", "o", -0.16),
                ("DMET", "^", 0.16),
            ):
                method_rows = stripe[stripe["method"].eq(method)]
                for U, rows in method_rows.groupby("U", sort=True):
                    rows = rows.sort_values(["system", "boundary", "state"])
                    x = (
                        float(U)
                        + x_center
                        + deterministic_jitter(len(rows), 0.075)
                    )
                    ax.scatter(
                        x,
                        rows["value"],
                        marker=marker,
                        s=20,
                        facecolors="none",
                        edgecolors=COLORS[method],
                        linewidths=0.85,
                        alpha=0.50,
                        zorder=2,
                    )

            embeddings = group[group["record_type"].eq("finite_embedding")]
            if not embeddings.empty:
                embeddings = embeddings.sort_values("system")
                x = 8.12 + deterministic_jitter(len(embeddings), 0.12)
                ax.errorbar(
                    x,
                    embeddings["value"],
                    yerr=embeddings["sigma"].fillna(0.0),
                    fmt="^" if simplified_legend else "D",
                    ms=4.6,
                    mfc="white",
                    mec=COLORS["DMET"],
                    ecolor=COLORS["DMET"],
                    mew=1.0,
                    capsize=1.8,
                    linestyle="none",
                    alpha=0.82,
                    zorder=5,
                )

            density_x = 0.035 if observable == "energy" else 0.965
            density_ha = "left" if observable == "energy" else "right"
            ax.text(
                density_x,
                0.945,
                rf"$n={density:g}$",
                transform=ax.transAxes,
                ha=density_ha,
                va="top",
                fontsize=11.2,
                fontweight="bold",
            )
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.set_xlim(1.45, 12.55)
            ax.set_xticks([2, 4, 6, 8, 10, 12])
            ax.grid(alpha=0.20)
            panel_label(ax, f"({chr(97 + idx)})")

        axes[1, 0].set_xlabel(r"$U/t$")
        axes[1, 1].set_xlabel(r"$U/t$")

        if simplified_legend:
            legend_handles = [
                Line2D(
                    [0], [0], color="none", marker="o", ms=6.2,
                    mfc=COLORS["CP-AFQMC"], mec="white", mew=0.45,
                    label="CP-AFQMC",
                ),
                Line2D(
                    [0], [0], color="none", marker="^", ms=6.5,
                    mfc=COLORS["DMET"], mec="white", mew=0.45,
                    label="DMET",
                ),
            ]
            legend_columns = 2
            footnote = (
                r"Red lines with squares: $4\times4$ MMHK. Filled symbols: compact "
                "benchmarks; open symbols: flagged or resolved values. "
                "Offsets are visual only; AFQMC is constrained-path."
            )
        else:
            legend_handles = [
                Line2D(
                    [0], [0], color=COLORS["MMHK"], marker="s", ms=5.3,
                    label=r"$4\times4$ MMHK"
                ),
                Line2D(
                    [0], [0], color="none", marker="o", ms=6.2,
                    mfc=COLORS["CP-AFQMC"], mec="white", mew=0.45,
                    label="CP-AFQMC benchmark"
                ),
                Line2D(
                    [0], [0], color="none", marker="^", ms=6.5,
                    mfc=COLORS["DMET"], mec="white", mew=0.45,
                    label="DMET TDL estimate"
                ),
                Line2D(
                    [0], [0], color="none", marker="X", ms=6.2,
                    mfc="white", mec=COLORS["DMET"], mew=1.15,
                    label="flagged DMET extrapolation"
                ),
                Line2D(
                    [0], [0], color="none", marker="o", ms=5.0,
                    mfc="none", mec=COLORS["CP-AFQMC"], alpha=0.55,
                    label="CP-AFQMC stripe-resolved"
                ),
                Line2D(
                    [0], [0], color="none", marker="^", ms=5.2,
                    mfc="none", mec=COLORS["DMET"], alpha=0.55,
                    label="DMET stripe-resolved"
                ),
                Line2D(
                    [0], [0], color="none", marker="D", ms=4.6,
                    mfc="white", mec=COLORS["DMET"],
                    label="DMET finite embedding"
                ),
            ]
            legend_columns = 4
            footnote = (
                "Open small symbols show individual stripe-state/system or "
                "embedding results; horizontal offsets and jitter are visual "
                "only. Away-from-half-filling AFQMC is constrained-path."
            )
        fig.legend(
            handles=legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.52, 0.995),
            ncol=legend_columns,
            frameon=False,
            handletextpad=0.5,
            columnspacing=1.25,
        )
        fig.text(
            0.50,
            0.018,
            footnote,
            ha="center",
            va="bottom",
            fontsize=8.7,
            color="0.30",
        )
        fig.subplots_adjust(
            left=0.09,
            right=0.99,
            bottom=0.12,
            top=0.86,
            hspace=0.30,
            wspace=0.25,
        )
        fig.savefig(pdf, bbox_inches="tight")
        fig.savefig(png, dpi=260, bbox_inches="tight")
        plt.close(fig)
    return pdf, png


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    data = build_dataset()
    combined_path = RESULTS / "away_half_filling_comparison_data.csv"
    data.to_csv(combined_path, index=False)

    deltas = data[
        data["record_type"].eq("benchmark_tdl")
        & data["mmhk_value"].notna()
    ].copy()
    deltas_path = RESULTS / "away_half_filling_benchmark_deltas.csv"
    deltas.to_csv(deltas_path, index=False)

    pdf, png = plot(data)
    simple_pdf, simple_png = plot(data, simplified_legend=True)
    print(f"Wrote {combined_path.relative_to(ROOT)} ({len(data)} rows)")
    print(f"Wrote {deltas_path.relative_to(ROOT)} ({len(deltas)} rows)")
    print(f"Wrote {pdf.relative_to(ROOT)}")
    print(f"Wrote {png.relative_to(ROOT)}")
    print(f"Wrote {simple_pdf.relative_to(ROOT)}")
    print(f"Wrote {simple_png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
