#!/usr/bin/env python3
"""Build a non-publication Fig. 4 pointwise-C_NN integration preview.

The fixture exercises the complete 16-case table contract and bundle plumbing
before the real 10,332-output F861 snapshot is available. Every row and the rendered
figure are explicitly marked as synthetic/fixture-only.  Nothing below
``figures/``, ``results/``, or ``manuscript/`` is touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from build_scale_and_transition_figure import ROOT, build_figure
from fig4_cnn_prediction_input import (
    EQ10_CONVENTION,
    EXPECTED_EXPANSION_CASES,
    EXPECTED_POINTWISE_CASES,
    FIXTURE_DATA_PRODUCT,
    FULL861_CONTROL_SOURCE,
    FULL861_EXPANSION_SOURCE,
    FULL861_FIDELITY,
    FULL861_SAMPLING,
    POINTWISE_BASENAME,
    PROVENANCE_BASENAME,
    eq10_signed,
)


PREVIEW_DIR = ROOT / "tmp" / "fig4_cnn_pointwise_preview_20260821"
BUNDLE_DIR = PREVIEW_DIR / "analysis_bundle"
FIXTURE_LABEL = (
    "synthetic 16-case C_NN contract fixture; not production fullobs data"
)
U40_SUMMARY = (
    ROOT / "results" / "fullobs_U40_observable_summary_by_V_20260723_091307.csv"
)
GZ_POINTS = ROOT / "results" / "pnas_scale_rule_points_eta0p05.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_fixture() -> pd.DataFrame:
    """Return a visibly marked contract fixture, never a production estimate."""
    gz = pd.read_csv(GZ_POINTS)
    gz = gz[gz["branch"].isin(["U-only", "Mott/spin"])].copy()
    gz = gz[gz["U"].isin([20.0, 40.0, 80.0])]
    if len(gz) != 16:
        raise RuntimeError("Current GZ table no longer has the expected 16 cases")

    # Four U=40 values are copied from the already audited full-861 summary.
    # All other numbers below are deliberately synthetic and only exercise the
    # plotting interface; they must never be interpreted as campaign results.
    u40 = pd.read_csv(U40_SUMMARY).set_index("V")["C1_NN_mean"]
    c_fixture = {
        (20.0, 0.0): -0.34065,
        (20.0, 2.0): -0.34030,
        (20.0, 3.0): -0.33990,
        (20.0, 4.0): -0.33950,
        (20.0, 4.5): -0.33920,
        (40.0, 0.0): float(u40.loc[0.0]),
        (40.0, 4.0): float(u40.loc[4.0]),
        (40.0, 6.0): 0.5 * float(u40.loc[4.0] + u40.loc[8.0]),
        (40.0, 8.0): float(u40.loc[8.0]),
        (40.0, 9.0): float(u40.loc[9.0]),
        (80.0, 0.0): -0.35090,
        (80.0, 4.0): -0.35070,
        (80.0, 8.0): -0.35040,
        (80.0, 12.0): -0.35010,
        (80.0, 16.0): -0.34980,
        (80.0, 18.0): -0.34960,
    }
    if set(c_fixture) != set(EXPECTED_POINTWISE_CASES):
        raise RuntimeError("Synthetic fixture inventory drifted from the contract")

    rows = []
    campaign_cases = set(EXPECTED_EXPANSION_CASES)
    for row in gz.sort_values(["U", "V"]).itertuples(index=False):
        case = (float(row.U), float(row.V))
        c_value = c_fixture[case]
        if case in campaign_cases:
            source = FULL861_EXPANSION_SOURCE
        else:
            source = FULL861_CONTROL_SOURCE
        factor = (2.0 * row.U - row.V) / (row.U - row.V)
        rows.append(
            {
                "U": float(row.U),
                "V": float(row.V),
                "r": float(row.r),
                "branch": str(row.branch),
                "C_NN": c_value,
                "C_NN_source": source,
                "C_NN_sampling": FULL861_SAMPLING,
                "C_NN_fidelity": FULL861_FIDELITY,
                "C_NN_full_wedge_rows": 861,
                "C_NN_quadrature_weight": 1600.0,
                "C_NN_full_quadrature_weighted_population_std": 1.0e-5,
                "twist_spread_is_standard_error": False,
                "eq10_factor": factor,
                "s_eq10_signed": float(eq10_signed(row.U, row.V, c_value)),
                "eq10_convention": EQ10_CONVENTION,
                "fixture_only": True,
                "fixture_label": FIXTURE_LABEL,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    pointwise_path = BUNDLE_DIR / POINTWISE_BASENAME
    fixture = build_fixture()
    fixture.to_csv(pointwise_path, index=False)
    provenance = {
        "fixture_only": True,
        "fixture_label": FIXTURE_LABEL,
        "data_product": FIXTURE_DATA_PRODUCT,
        "purpose": "staging-only integration preview",
        "output_files": {POINTWISE_BASENAME: sha256(pointwise_path)},
        "publication_artifacts_modified": False,
    }
    (BUNDLE_DIR / PROVENANCE_BASENAME).write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )

    out_pdf = PREVIEW_DIR / "fig4_pointwise_eq10_STAGING.pdf"
    out_png = PREVIEW_DIR / "fig4_pointwise_eq10_STAGING.png"
    analytic_csv = PREVIEW_DIR / "finite_uv_validation_STAGING.csv"
    analytic_json = PREVIEW_DIR / "finite_uv_validation_STAGING.json"
    boundary_csv = PREVIEW_DIR / "transition_boundary_STAGING.csv"
    build_figure(
        out_pdf=out_pdf,
        out_png=out_png,
        fullobs_analysis_dir=BUNDLE_DIR,
        staging_preview=True,
        allow_fixture=True,
        analytic_points_path=analytic_csv,
        analytic_summary_path=analytic_json,
        boundary_filtered_path=boundary_csv,
    )
    print(f"Fixture bundle: {BUNDLE_DIR}")
    print(f"Staging PDF: {out_pdf}")
    print(f"Staging PNG: {out_png}")
    print(f"Staging analytic CSV: {analytic_csv}")
    print(f"Staging analytic JSON: {analytic_json}")
    print("Publication artifacts modified: False")


if __name__ == "__main__":
    main()
