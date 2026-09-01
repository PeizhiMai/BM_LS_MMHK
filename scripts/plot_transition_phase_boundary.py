#!/usr/bin/env python3
"""Combine and plot the full-861 Mott--charge transition audit.

All final endpoints for U=4,8,...,40 have 861 valid twist outputs.  The
eleven endpoints added for U=16--36 (including the U=20 upper endpoint)
are unanimous in their expected phases.  The pre-existing U=4,8,12
endpoints are retained numerically, but mixed-phase endpoint audits are
marked explicitly rather than being presented as unanimous brackets.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results" / "transition_brackets_reference_U2_U40.csv"
NEW = ROOT / "results" / "five_twist_transition_brackets_U16_U36.csv"
VALIDATION_25 = (
    ROOT / "results" / "twentyfive_twist_bracket_validation_U16_U36.csv"
)
REFINEMENT_24_28 = (
    ROOT / "results" / "five_twist_U24_U28_refined_brackets.csv"
)
REFINEMENT_32 = (
    ROOT / "results" / "twentyfive_twist_U32_refined_bracket.csv"
)
VALIDATION_861 = (
    ROOT / "results" / "full_861_twist_final_bracket_validation.csv"
)
PREEXISTING_861 = (
    ROOT / "results" / "preexisting_full_861_endpoint_validation.csv"
)
COMBINED = ROOT / "results" / "transition_brackets_combined_U2_U40.csv"
OUT_PDF = ROOT / "figures" / "transition_phase_boundary_U2_U40.pdf"
OUT_PNG = ROOT / "figures" / "transition_phase_boundary_U2_U40.png"

EXPECTED_NEW_U = {16, 24, 28, 32, 36}
FULL_861_SOURCE = "full_861_twist_final_brackets_U16_U36_20260729"
PREEXISTING_AUDIT_SOURCE = "preexisting_full_861_endpoint_audit_20260801"
EXPECTED_861_ENDPOINTS = {
    (16, 4.025): "Mott",
    (16, 4.030): "charge",
    (20, 5.025): "charge",
    (24, 6.020): "Mott",
    (24, 6.025): "charge",
    (28, 7.015): "Mott",
    (28, 7.020): "charge",
    (32, 8.015): "Mott",
    (32, 8.020): "charge",
    (36, 9.010): "Mott",
    (36, 9.020): "charge",
}


def append_source(value: str, source: str) -> str:
    """Append a provenance token once."""
    tokens = str(value).split("+")
    return str(value) if source in tokens else f"{value}+{source}"


def load_full_861_validation() -> pd.DataFrame:
    """Require unanimous 861/861 validation for the eleven new groups."""
    if not VALIDATION_861.is_file():
        raise RuntimeError(f"Missing final endpoint validation: {VALIDATION_861}")
    validation = pd.read_csv(VALIDATION_861)
    observed = {
        (int(row.U), round(float(row.V), 6)): str(row.expected_phase)
        for row in validation.itertuples(index=False)
    }
    expected = {
        (U, round(V, 6)): phase
        for (U, V), phase in EXPECTED_861_ENDPOINTS.items()
    }
    unanimous = (
        validation["unanimous_expected_phase"]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    if (
        observed != expected
        or not validation["complete_twists"].eq(861).all()
        or not validation["matching_twists"].eq(861).all()
        or not unanimous.all()
    ):
        raise RuntimeError(
            "The final 861-twist endpoint validation is incomplete or "
            "contains a phase disagreement."
        )
    return validation


def load_preexisting_861_audit() -> pd.DataFrame:
    """Load the nine pre-existing 861-twist endpoint audits.

    Completeness is mandatory.  Unanimity is deliberately not required:
    mixed endpoints are retained and visibly flagged in the output figure.
    """
    if not PREEXISTING_861.is_file():
        raise RuntimeError(f"Missing pre-existing endpoint audit: {PREEXISTING_861}")
    audit = pd.read_csv(PREEXISTING_861)
    expected = {
        (4, 1.029): "Mott",
        (4, 1.030): "charge",
        (8, 2.038): "Mott",
        (8, 2.040): "charge",
        (12, 3.032): "Mott",
        (12, 3.034): "charge",
        (20, 5.020): "Mott",
        (40, 10.010): "Mott",
        (40, 10.020): "charge",
    }
    observed = {
        (int(row.U), round(float(row.V), 6)): str(row.expected_phase)
        for row in audit.itertuples(index=False)
    }
    expected = {
        (U, round(V, 6)): phase for (U, V), phase in expected.items()
    }
    if observed != expected or not audit["complete_twists"].eq(861).all():
        raise RuntimeError("The pre-existing full-861 endpoint audit is incomplete.")
    return audit


def load_data() -> pd.DataFrame:
    reference = pd.read_csv(REFERENCE)
    new = pd.read_csv(NEW)
    load_full_861_validation()
    preexisting_audit = load_preexisting_861_audit()

    if set(new["U"].astype(int)) != EXPECTED_NEW_U:
        raise RuntimeError(
            f"Expected new U values {sorted(EXPECTED_NEW_U)}, "
            f"found {sorted(set(new['U'].astype(int)))}."
        )
    if not (new["status"] == "bracketed").all():
        bad = new.loc[new["status"] != "bracketed", ["U", "status"]]
        raise RuntimeError(f"Unresolved transition brackets:\n{bad}")
    if not new["all_five_twists_agree"].astype(bool).all():
        bad = new.loc[
            ~new["all_five_twists_agree"].astype(bool),
            ["U", "V_Mott", "V_charge"],
        ]
        raise RuntimeError(f"Five-twist phase disagreement remains:\n{bad}")

    new = new.copy()
    refined_us: set[int] = set()
    refinement_sources: dict[int, str] = {}
    if REFINEMENT_24_28.is_file():
        refinement = pd.read_csv(REFINEMENT_24_28)
        if (
            set(refinement["U"].astype(int)) != {24, 28}
            or not refinement["status"].eq("bracketed").all()
            or not refinement["all_five_twists_agree"].astype(bool).all()
        ):
            raise RuntimeError("Invalid U=24,28 midpoint-refinement table.")
        update_columns = [
            "V_Mott",
            "V_charge",
            "V_c_midpoint",
            "V_c_halfwidth",
            "V_c_over_U",
            "V_c_over_U_halfwidth",
            "bracket_width",
        ]
        for _, row in refinement.iterrows():
            U = int(row["U"])
            mask = new["U"].eq(U)
            if mask.sum() != 1:
                raise RuntimeError(f"Cannot apply midpoint refinement for U={U}.")
            for column in update_columns:
                new.loc[mask, column] = float(row[column])
            refined_us.add(U)
            refinement_sources[U] = "five_twist_refine_U24_U28_20260727"

    if REFINEMENT_32.is_file():
        refinement = pd.read_csv(REFINEMENT_32)
        if (
            set(refinement["U"].astype(int)) != {32}
            or not refinement["status"].eq("bracketed").all()
            or not refinement["twists_at_midpoint"].eq(25).all()
        ):
            raise RuntimeError("Invalid 25-twist U=32 midpoint-refinement table.")
        update_columns = [
            "V_Mott",
            "V_charge",
            "V_c_midpoint",
            "V_c_halfwidth",
            "V_c_over_U",
            "V_c_over_U_halfwidth",
            "bracket_width",
        ]
        row = refinement.iloc[0]
        U = 32
        mask = new["U"].eq(U)
        if mask.sum() != 1:
            raise RuntimeError("Cannot apply midpoint refinement for U=32.")
        for column in update_columns:
            new.loc[mask, column] = float(row[column])
        refined_us.add(U)
        refinement_sources[U] = (
            "twentyfive_twist_refined_endpoints_U20_U32_20260727"
        )

    if VALIDATION_25.is_file():
        validation = pd.read_csv(VALIDATION_25)
        validated = (
            len(validation) == 10
            and set(validation["U"].astype(int)) == EXPECTED_NEW_U
            and validation["complete_twists"].eq(25).all()
            and validation["matching_twists"].eq(25).all()
            and validation["unanimous_expected_phase"].astype(bool).all()
        )
    else:
        validated = False
    if validated:
        new["sampling"] = "twentyfive_representative_twists"
        new["source"] = (
            "five_twist_U16_U36_20260726"
            "+twentyfive_twist_brackets_U16_U36_20260727"
        )
    else:
        new["sampling"] = "five_representative_twists"
        new["source"] = "five_twist_U16_U36_20260726"
    if refined_us:
        for U in sorted(refined_us):
            mask = new["U"].eq(U)
            new.loc[mask, "sampling"] = (
                "twentyfive_twist_midpoint_refinement"
                if validated
                else "representative_twist_midpoint_refinement"
            )
            new.loc[mask, "source"] = (
                new.loc[mask, "source"] + "+" + refinement_sources[U]
            )

    # Every final endpoint for U=16,24,28,32,36 now has unanimous
    # 861/861 validation.  U=20 combines two independently audited
    # full-861 endpoints.
    for U in sorted(EXPECTED_NEW_U):
        mask = new["U"].eq(U)
        new.loc[mask, "sampling"] = "full_861_twist_grid_unanimous_endpoints"
        new.loc[mask, "source"] = new.loc[mask, "source"].map(
            lambda value: append_source(value, FULL_861_SOURCE)
        )
    mask20 = reference["U"].eq(20)
    if mask20.sum() != 1:
        raise RuntimeError("Expected exactly one U=20 reference row.")
    reference.loc[mask20, "sampling"] = "full_861_twist_grid_unanimous_endpoints"
    reference.loc[mask20, "source"] = reference.loc[mask20, "source"].map(
        lambda value: append_source(
            append_source(value, PREEXISTING_AUDIT_SOURCE), FULL_861_SOURCE
        )
    )

    audit_unanimous = (
        preexisting_audit["unanimous_expected_phase"]
        .astype(str)
        .str.lower()
        .eq("true")
    )
    mixed_us = set(
        preexisting_audit.loc[~audit_unanimous, "U"].astype(int)
    )
    for U in sorted(mixed_us):
        mask = reference["U"].eq(U)
        if mask.sum() != 1:
            raise RuntimeError(f"Expected exactly one U={U} reference row.")
        reference.loc[mask, "sampling"] = "full_861_twist_grid_mixed_phase"
        reference.loc[mask, "source"] = reference.loc[mask, "source"].map(
            lambda value: append_source(value, PREEXISTING_AUDIT_SOURCE)
        )
    mask40 = reference["U"].eq(40)
    if mask40.sum() != 1:
        raise RuntimeError("Expected exactly one U=40 reference row.")
    reference.loc[mask40, "sampling"] = "full_861_twist_grid_unanimous_endpoints"
    reference.loc[mask40, "source"] = reference.loc[mask40, "source"].map(
        lambda value: append_source(value, PREEXISTING_AUDIT_SOURCE)
    )

    columns = [
        "U",
        "V_Mott",
        "V_charge",
        "V_c_midpoint",
        "V_c_halfwidth",
        "V_c_over_U",
        "V_c_over_U_halfwidth",
        "bracket_width",
        "sampling",
        "source",
    ]
    combined = (
        pd.concat([reference[columns], new[columns]], ignore_index=True)
        .sort_values("U")
        .reset_index(drop=True)
    )
    if combined["U"].duplicated().any():
        raise RuntimeError("Duplicate U values in the combined transition table.")
    combined.to_csv(COMBINED, index=False)
    return combined


def make_figure(data: pd.DataFrame) -> None:
    mixed_mask = data["sampling"].eq("full_861_twist_grid_mixed_phase")
    unanimous_mask = data["sampling"].eq(
        "full_861_twist_grid_unanimous_endpoints"
    )
    retained = data.loc[~mixed_mask & ~unanimous_mask]
    unanimous = data.loc[unanimous_mask]
    mixed = data.loc[mixed_mask]

    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "axes.linewidth": 0.8,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.05), constrained_layout=True)

    uline = pd.Series([0.0, max(42.0, 1.05 * data["U"].max())])
    axes[0].plot(
        uline,
        uline / 4.0,
        color="#666666",
        linestyle="--",
        linewidth=1.1,
        label=r"$V=U/4$",
        zorder=1,
    )
    for subset, label, color, marker, face in [
        (retained, "retained 861-twist bracket", "#5f6f52", "o", "white"),
        (unanimous, "861-twist unanimous endpoints", "#b23a48", "s", "#b23a48"),
        (mixed, "861 twists; endpoint phases mixed", "#d17c16", "D", "white"),
    ]:
        axes[0].errorbar(
            subset["U"],
            subset["V_c_midpoint"],
            yerr=subset["V_c_halfwidth"],
            fmt=marker,
            markersize=5.0,
            markerfacecolor=face,
            markeredgecolor=color,
            markeredgewidth=1.0,
            ecolor=color,
            elinewidth=1.0,
            capsize=2.4,
            color=color,
            linestyle="none",
            label=label,
            zorder=3,
        )
    axes[0].set_xlabel(r"$U/t$")
    axes[0].set_ylabel(r"$V_c/t$")
    axes[0].legend(frameon=False, loc="upper left")

    axes[1].axhline(
        0.25,
        color="#666666",
        linestyle="--",
        linewidth=1.1,
        zorder=1,
    )
    for subset, color, marker, face in [
        (retained, "#5f6f52", "o", "white"),
        (unanimous, "#b23a48", "s", "#b23a48"),
        (mixed, "#d17c16", "D", "white"),
    ]:
        axes[1].errorbar(
            subset["U"],
            subset["V_c_over_U"],
            yerr=subset["V_c_over_U_halfwidth"],
            fmt=marker,
            markersize=5.0,
            markerfacecolor=face,
            markeredgecolor=color,
            markeredgewidth=1.0,
            ecolor=color,
            elinewidth=1.0,
            capsize=2.4,
            color=color,
            linestyle="none",
            zorder=3,
        )
    axes[1].set_xlabel(r"$U/t$")
    axes[1].set_ylabel(r"$(V/U)_c$")

    for ax in axes:
        ax.grid(axis="y", color="#dddddd", linewidth=0.55)
        ax.tick_params(direction="out", length=3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data = load_data()
    make_figure(data)
    print(COMBINED)
    print(OUT_PDF)
    print(OUT_PNG)


if __name__ == "__main__":
    main()
