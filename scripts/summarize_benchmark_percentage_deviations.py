#!/usr/bin/env python3
"""Summarize the reference deviations of the data displayed in main Fig. 1.

The source-selection rules are implemented by
``plot_combined_density_benchmark.py``.  This script deliberately consumes
its selected-reference tables so the numerical summary and the plotted open
markers cannot silently diverge.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MMHK_SOURCE = RESULTS / "mmhk_observables_all_cases.csv"
HALF_REFERENCE_SOURCE = RESULTS / "figS2_selected_half_filling_references.csv"
DOPED_REFERENCE_SOURCE = RESULTS / "figS2_selected_comparison_data.csv"

POINTWISE_OUTPUT = RESULTS / "benchmark_pointwise_percentage_deviations.csv"
SUMMARY_OUTPUT = RESULTS / "benchmark_percentage_deviations_by_density.csv"
METHOD_OUTPUT = RESULTS / "benchmark_percentage_deviations_by_density_method.csv"
STRONG_COUPLING_OUTPUT = (
    RESULTS / "benchmark_percentage_deviations_by_density_Uge4.csv"
)

MMHK_COLUMNS = {
    "Ground-state energy": "ground_state_energy",
    "Double occupancy": "double_occupancy_i",
    "Magnetization": "magnetization",
}
HALF_QUANTITY_NAMES = {
    "Ground State Energy": "Ground-state energy",
    "Double Occupancy": "Double occupancy",
    "Magnetization": "Magnetization",
}
DOPED_QUANTITY_NAMES = {
    "energy": "Ground-state energy",
    "double_occupancy": "Double occupancy",
}


def _mmhk_value(
    mmhk: pd.DataFrame, density: float, interaction: float, quantity: str
) -> float:
    rows = mmhk[
        np.isclose(mmhk["n_target"], density)
        & np.isclose(mmhk["U"], interaction)
    ]
    if len(rows) != 1:
        raise ValueError(
            f"Expected one MMHK row at n={density}, U={interaction}; "
            f"found {len(rows)}"
        )
    return float(rows.iloc[0][MMHK_COLUMNS[quantity]])


def build_pointwise_table() -> pd.DataFrame:
    mmhk = pd.read_csv(MMHK_SOURCE)
    half = pd.read_csv(HALF_REFERENCE_SOURCE)
    doped = pd.read_csv(DOPED_REFERENCE_SOURCE)
    records: list[dict[str, object]] = []

    for row in half.itertuples(index=False):
        quantity = HALF_QUANTITY_NAMES[str(row.property)]
        mmhk_value = _mmhk_value(mmhk, 1.0, float(row.U), quantity)
        reference = float(row.value)
        records.append(
            {
                "density": 1.0,
                "U": float(row.U),
                "quantity": quantity,
                "reference_method": str(row.method),
                "reference_value": reference,
                "mmhk_value": mmhk_value,
                "mmhk_minus_reference": mmhk_value - reference,
                "signed_percentage_deviation": (
                    100.0 * (mmhk_value - reference) / abs(reference)
                ),
                "absolute_percentage_deviation": (
                    100.0 * abs(mmhk_value - reference) / abs(reference)
                ),
            }
        )

    selected_doped = doped[~doped["method"].eq("MMHK")]
    for row in selected_doped.itertuples(index=False):
        quantity = DOPED_QUANTITY_NAMES[str(row.observable)]
        reference = float(row.value)
        mmhk_value = float(row.mmhk_value)
        records.append(
            {
                "density": float(row.density),
                "U": float(row.U),
                "quantity": quantity,
                "reference_method": str(row.method),
                "reference_value": reference,
                "mmhk_value": mmhk_value,
                "mmhk_minus_reference": mmhk_value - reference,
                "signed_percentage_deviation": (
                    100.0 * (mmhk_value - reference) / abs(reference)
                ),
                "absolute_percentage_deviation": (
                    100.0 * abs(mmhk_value - reference) / abs(reference)
                ),
            }
        )

    pointwise = pd.DataFrame.from_records(records)
    return pointwise.sort_values(
        ["density", "quantity", "U", "reference_method"], kind="stable"
    ).reset_index(drop=True)


def _join_unique(values: pd.Series) -> str:
    return ",".join(sorted({str(value) for value in values}))


def _join_interactions(values: pd.Series) -> str:
    return ",".join(f"{float(value):g}" for value in sorted(set(values)))


def summarize(pointwise: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    return (
        pointwise.groupby(group_columns, sort=True, dropna=False)
        .agg(
            matched_reference_points=("absolute_percentage_deviation", "size"),
            U_values=("U", _join_interactions),
            reference_methods=("reference_method", _join_unique),
            mean_absolute_percentage_deviation=(
                "absolute_percentage_deviation",
                "mean",
            ),
            median_absolute_percentage_deviation=(
                "absolute_percentage_deviation",
                "median",
            ),
            minimum_absolute_percentage_deviation=(
                "absolute_percentage_deviation",
                "min",
            ),
            maximum_absolute_percentage_deviation=(
                "absolute_percentage_deviation",
                "max",
            ),
            mean_signed_percentage_deviation=(
                "signed_percentage_deviation",
                "mean",
            ),
        )
        .reset_index()
    )


def main() -> None:
    pointwise = build_pointwise_table()
    summary = summarize(pointwise, ["density", "quantity"])
    by_method = summarize(
        pointwise, ["density", "quantity", "reference_method"]
    )
    strong_coupling = summarize(
        pointwise[pointwise["U"].ge(4.0)], ["density", "quantity"]
    )

    pointwise.to_csv(POINTWISE_OUTPUT, index=False, float_format="%.10g")
    summary.to_csv(SUMMARY_OUTPUT, index=False, float_format="%.10g")
    by_method.to_csv(METHOD_OUTPUT, index=False, float_format="%.10g")
    strong_coupling.to_csv(
        STRONG_COUPLING_OUTPUT, index=False, float_format="%.10g"
    )

    print(f"Wrote {POINTWISE_OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {METHOD_OUTPUT.relative_to(ROOT)}")
    print(f"Wrote {STRONG_COUPLING_OUTPUT.relative_to(ROOT)}")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
