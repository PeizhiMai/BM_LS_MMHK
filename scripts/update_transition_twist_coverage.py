#!/usr/bin/env python3
"""Build the final full-861 twist and phase-audit coverage table."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
BRACKETS = RESULTS / "transition_brackets_combined_U2_U40.csv"
PREVIOUS = RESULTS / "transition_bracket_twist_coverage_20260727.csv"
VALIDATION_861 = RESULTS / "full_861_twist_final_bracket_validation.csv"
PREEXISTING_861 = RESULTS / "preexisting_full_861_endpoint_validation.csv"
OUTPUT = RESULTS / "transition_bracket_twist_coverage_20260727.csv"

FULL_861_SOURCE = "full_861_twist_final_brackets_U16_U36_20260729"
PREEXISTING_SOURCE = "preexisting_full_861_endpoint_audit_20260801"
REQUIRED_U = set(range(4, 41, 4))


def key(U: float, V: float) -> tuple[int, float]:
    return int(U), round(float(V), 6)


def main() -> None:
    brackets = pd.read_csv(BRACKETS)
    previous = pd.read_csv(PREVIOUS) if PREVIOUS.is_file() else pd.DataFrame()
    validation = pd.read_csv(VALIDATION_861)
    preexisting = pd.read_csv(PREEXISTING_861)

    unanimous = (
        validation["unanimous_expected_phase"]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    if (
        len(validation) != 11
        or not validation["complete_twists"].eq(861).all()
        or not validation["matching_twists"].eq(861).all()
        or not unanimous.all()
    ):
        raise RuntimeError("Invalid final full-861 validation table.")
    if len(preexisting) != 9 or not preexisting["complete_twists"].eq(861).all():
        raise RuntimeError("Invalid pre-existing full-861 endpoint audit.")

    old_counts: dict[tuple[int, float], int] = {}
    if not previous.empty:
        for row in previous.itertuples(index=False):
            old_counts[key(row.U, row.V)] = int(row.valid_unique_twists)
    audit_rows: dict[tuple[int, float], dict[str, object]] = {}
    for source, table in [
        (FULL_861_SOURCE, validation),
        (PREEXISTING_SOURCE, preexisting),
    ]:
        for row in table.itertuples(index=False):
            audit_rows[key(row.U, row.V)] = {
                "expected_phase": str(row.expected_phase),
                "matching_expected_twists": int(row.matching_twists),
                "unanimous_expected_phase": str(
                    row.unanimous_expected_phase
                ).lower() == "true",
                "source": source,
            }

    rows: list[dict[str, object]] = []
    for row in brackets.sort_values("U").itertuples(index=False):
        endpoints = (float(row.V_Mott), float(row.V_charge))
        for V in endpoints:
            endpoint = key(row.U, V)
            retained = old_counts.get(endpoint, 0)
            expected_phase = "Mott" if V == endpoints[0] else "charge"
            if endpoint in audit_rows:
                audit = audit_rows[endpoint]
                count = 861
                matching = int(audit["matching_expected_twists"])
                unanimous_endpoint = bool(audit["unanimous_expected_phase"])
                endpoint_sampling = (
                    "full_861_twist_grid_unanimous_endpoint"
                    if unanimous_endpoint
                    else "full_861_twist_grid_mixed_phase"
                )
                endpoint_source = str(audit["source"])
                phase_status = "unanimous_expected" if unanimous_endpoint else "mixed"
                if str(audit["expected_phase"]) != expected_phase:
                    raise RuntimeError(
                        f"Phase-label mismatch for U={int(row.U)}, V={V}."
                    )
            elif retained >= 861:
                count = retained
                matching = pd.NA
                unanimous_endpoint = pd.NA
                endpoint_sampling = "full_861_twist_grid"
                endpoint_source = (
                    "fullobs_U40_20260723"
                    if int(row.U) == 40
                    else "full_grid_selected_20260723"
                )
                phase_status = "not_reaudited_20260801"
            else:
                raise RuntimeError(
                    f"No full-861 evidence for endpoint U={int(row.U)}, V={V}."
                )
            rows.append(
                {
                    "U": int(row.U),
                    "V": V,
                    "valid_unique_twists": count,
                    "invalid_files": 0,
                    "at_least_5": count >= 5,
                    "at_least_100": count >= 100,
                    "at_least_400": count >= 400,
                    "at_least_861": count >= 861,
                    "expected_phase": expected_phase,
                    "matching_expected_twists": matching,
                    "unanimous_expected_phase": unanimous_endpoint,
                    "phase_validation_status": phase_status,
                    "sampling": endpoint_sampling,
                    "source": endpoint_source,
                }
            )

    coverage = pd.DataFrame(rows).sort_values(["U", "V"]).reset_index(drop=True)
    coverage["matching_expected_twists"] = coverage[
        "matching_expected_twists"
    ].astype("Int64")
    coverage["unanimous_expected_phase"] = coverage[
        "unanimous_expected_phase"
    ].astype("boolean")
    required = coverage.loc[coverage["U"].isin(REQUIRED_U)]
    if (
        set(required["U"]) != REQUIRED_U
        or required.groupby("U").size().ne(2).any()
        or not required["at_least_861"].all()
    ):
        raise RuntimeError("Not every final U=4,8,...,40 bracket has two full-861 endpoints.")

    coverage.to_csv(OUTPUT, index=False)
    print(OUTPUT)
    print(
        required.groupby("U")["valid_unique_twists"]
        .agg(["min", "max"])
        .to_string()
    )
    mixed = required.loc[required["phase_validation_status"].eq("mixed")]
    if not mixed.empty:
        print("\nMixed-phase endpoint audits retained without bracket changes:")
        print(
            mixed[["U", "V", "expected_phase", "matching_expected_twists"]]
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
