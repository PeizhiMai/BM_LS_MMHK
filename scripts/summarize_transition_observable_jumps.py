#!/usr/bin/env python3
"""Summarize observable changes across the final transition brackets.

The table distinguishes the fixed-twist steepest-change criterion used for
U=2,4,8,12 from the unambiguous double-occupancy branch classifier used in
the strong-coupling representative/full-twist scans.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
BRACKETS = RESULTS / "transition_brackets_combined_U2_U40.csv"
OUT = RESULTS / "transition_observable_jumps_all_U.csv"

METRICS = {
    "double_occupancy": "D",
    "mCDW2_pipi": "mCDW2",
    "C1_NN": "C1",
    "nn_NN": "nn",
    "kinetic_per_site": "kinetic",
}


def endpoint_stats(
    data: pd.DataFrame,
    *,
    U: int,
    V: float,
    sampling: str,
    weight_column: str | None = None,
) -> dict[str, float | int | str]:
    """Return means and ranges for one endpoint."""

    if data.empty:
        raise RuntimeError(f"No observable rows for U={U}, V={V:g}.")
    result: dict[str, float | int | str] = {
        "U": U,
        "V": V,
        "n_twists": len(data),
        "sampling_detail": sampling,
    }
    if weight_column is None:
        weights = np.ones(len(data), dtype=float)
    else:
        weights = data[weight_column].to_numpy(dtype=float)
    weights = weights / weights.sum()

    for source, short in METRICS.items():
        values = data[source].to_numpy(dtype=float)
        result[f"{short}_mean"] = float(np.sum(weights * values))
        result[f"{short}_min"] = float(np.min(values))
        result[f"{short}_max"] = float(np.max(values))
    return result


def select(data: pd.DataFrame, U: int, V: float) -> pd.DataFrame:
    return data.loc[
        data["U"].astype(int).eq(U)
        & np.isclose(data["V"].astype(float), V, atol=5e-10)
    ].copy()


def main() -> None:
    brackets = pd.read_csv(BRACKETS).set_index("U")
    endpoint_rows: list[dict[str, float | int | str]] = []

    # Weak/intermediate coupling: the original refinement used the fixed
    # (0,0) twist.  (40,40) is the repeated periodic endpoint, so retain only
    # one physical twist rather than double-counting it.
    precision = pd.read_csv(RESULTS / "precision_transition_observables.csv")
    precision = precision.loc[precision["kx"].eq(0) & precision["ky"].eq(0)]
    for U in (2, 4, 8, 12):
        for side, column in (("lower", "V_Mott"), ("upper", "V_charge")):
            V = float(brackets.loc[U, column])
            row = endpoint_stats(
                select(precision, U, V),
                U=U,
                V=V,
                sampling="fixed twist (0,0)",
            )
            row["side"] = side
            endpoint_rows.append(row)

    # Strong coupling endpoints validated on 25 representative twists.
    validation = pd.read_csv(
        RESULTS / "twentyfive_twist_bracket_observables_U16_U36.csv"
    )
    for U in (16, 32, 36):
        for side, column in (("lower", "V_Mott"), ("upper", "V_charge")):
            V = float(brackets.loc[U, column])
            row = endpoint_stats(
                select(validation, U, V),
                U=U,
                V=V,
                sampling="25 representative twists",
            )
            row["side"] = side
            endpoint_rows.append(row)

    # U=20 uses the same five representative twists on both refined sides.
    u20_lower = pd.read_csv(
        RESULTS / "five_twist_U20_lower_endpoint_observables.csv"
    )
    u20_upper = pd.read_csv(RESULTS / "five_twist_U20_refinement_observables.csv")
    for side, data, column in (
        ("lower", u20_lower, "V_Mott"),
        ("upper", u20_upper, "V_charge"),
    ):
        V = float(brackets.loc[20, column])
        row = endpoint_stats(
            select(data, 20, V),
            U=20,
            V=V,
            sampling="5 matched representative twists",
        )
        row["side"] = side
        endpoint_rows.append(row)

    # U=24 and U=28 have one refined midpoint side and one original scan side.
    original_five = pd.read_csv(
        RESULTS / "five_twist_transition_observables_U16_U36.csv"
    )
    refined_five = pd.read_csv(
        RESULTS / "five_twist_U24_U28_refinement_observables.csv"
    )
    for U in (24, 28):
        for side, column in (("lower", "V_Mott"), ("upper", "V_charge")):
            V = float(brackets.loc[U, column])
            candidates = pd.concat(
                [select(original_five, U, V), select(refined_five, U, V)],
                ignore_index=True,
            ).drop_duplicates(["U", "V", "kx", "ky"])
            row = endpoint_stats(
                candidates,
                U=U,
                V=V,
                sampling="5 matched representative twists",
            )
            row["side"] = side
            endpoint_rows.append(row)

    # U=40 has the complete symmetry wedge; use quadrature-weighted means and
    # retain the raw 861-point ranges.
    u40_path = sorted(RESULTS.glob("fullobs_U40_observable_rows_*.csv.gz"))[-1]
    u40 = pd.read_csv(u40_path).rename(
        columns={"D_site": "double_occupancy"}
    )
    for side, column in (("lower", "V_Mott"), ("upper", "V_charge")):
        V = float(brackets.loc[40, column])
        row = endpoint_stats(
            select(u40, 40, V),
            U=40,
            V=V,
            sampling="861-twist symmetry wedge",
            weight_column="quadrature_weight",
        )
        row["side"] = side
        endpoint_rows.append(row)

    endpoints = pd.DataFrame(endpoint_rows)
    rows: list[dict[str, float | int | str]] = []
    for U, group in endpoints.groupby("U", sort=True):
        lower = group.loc[group["side"].eq("lower")].iloc[0]
        upper = group.loc[group["side"].eq("upper")].iloc[0]
        row: dict[str, float | int | str] = {
            "U": int(U),
            "V_lower": lower["V"],
            "V_upper": upper["V"],
            "n_twists_lower": int(lower["n_twists"]),
            "n_twists_upper": int(upper["n_twists"]),
            "sampling_detail": lower["sampling_detail"],
            "decision_basis": (
                "largest adjacent joint observable change at fixed twist"
                if U <= 12
                else "unanimous branch separation using D=0.25 separator"
            ),
        }
        for short in METRICS.values():
            for stat in ("mean", "min", "max"):
                row[f"{short}_lower_{stat}"] = lower[f"{short}_{stat}"]
                row[f"{short}_upper_{stat}"] = upper[f"{short}_{stat}"]
            row[f"delta_{short}_mean"] = (
                upper[f"{short}_mean"] - lower[f"{short}_mean"]
            )
        rows.append(row)

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT, index=False)
    print(summary.to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
