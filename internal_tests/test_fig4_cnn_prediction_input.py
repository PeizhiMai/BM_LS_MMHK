#!/usr/bin/env python3
"""Contract and staging-safety tests for Fig. 4 pointwise C_NN curves."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_scale_and_transition_figure as figure_builder  # noqa: E402
import freeze_fig4_cnn_full861_release as release_freezer  # noqa: E402
from fig4_cnn_prediction_input import (  # noqa: E402
    C_NN_OBSERVABLE,
    DATA_PRODUCT,
    DECISION_GATE_ALGORITHM,
    EQ10_CONVENTION,
    EXPECTED_EXPANSION_CASES,
    EXPECTED_POINTWISE_CASES,
    FIXTURE_DATA_PRODUCT,
    FULL861_CONTROL_SOURCE,
    FULL861_EXPANSION_SOURCE,
    FULL861_FIDELITY,
    FULL861_SAMPLING,
    FullobsEq10Bundle,
    POINTWISE_BASENAME,
    PROVENANCE_BASENAME,
    REVIEWED_FULL861_PINS,
    REVIEWED_FULL861_ANALYZER_SHA256,
    SCHEMA_VERSION,
    PointwisePredictionError,
    eq10_signed,
    load_validated_fullobs_eq10_bundle,
    validate_pointwise_eq10_predictions,
)


ACTIVE_DEFAULT_SHA256 = {
    "pdf": "3c828ae4a52fa5fac164f0a6e5380d97cf152d24a0a7cfff9d486859d8ec8382",
    "png": "a29f2d8bd147868896bc9018fd5f9b06f4ba7e627db051c7b75f0e175de7f3b8",
    "analytic_csv": "dd3ad76001021a300a54b03b25505b8d7d1b3be6315734d3c697d462ee039cd0",
    "analytic_json": "8cf1bc6564b17ae09e52c54b98361e9e69c01b05a7f31284b79bcb6b0b669fdb",
    "boundary_csv": "cca126f57425b3a52b6c3aa87b490ffb262cce1597ced0bb8db50e9371c6596e",
    "prl_pdf": "5c18e1a87300ab55d2280c3bfc4a41734996f41d8e1807dd647245ce6b9b93b2",
    "prl_png": "ddc6fff11c048fdbb101d71b81e701dc40947d184c0dbc8186d714986c1ef0df",
    "manuscript_pdf": "5c18e1a87300ab55d2280c3bfc4a41734996f41d8e1807dd647245ce6b9b93b2",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def table_fixture(*, fixture_only: bool = False) -> pd.DataFrame:
    campaign = set(EXPECTED_EXPANSION_CASES)
    gz = pd.read_csv(figure_builder.SCALE_POINTS)
    gz_lookup = gz.set_index(["U", "V"])
    rows: list[dict[str, object]] = []
    for U, V in EXPECTED_POINTWISE_CASES:
        source = (
            FULL861_EXPANSION_SOURCE
            if (U, V) in campaign
            else FULL861_CONTROL_SOURCE
        )
        c_value = -0.34
        if (U, V) == (40.0, 8.0):
            # Exact full-861 regression value from the audited U=40 control.
            c_value = -0.3459456844070078
        factor = (2.0 * U - V) / (U - V)
        gz_row = gz_lookup.loc[(U, V)]
        signed_observed = -float(gz_row["s"])
        s_u0_signed = -float(gz_row["s_u0"])
        r = V / U
        axis_anchor = (s_u0_signed - 0.5 * (s_u0_signed + 1.0) * r) / (
            1.0 - r
        )
        predicted = float(eq10_signed(U, V, c_value))
        row: dict[str, object] = {
            "U": U,
            "V": V,
            "r": V / U,
            "branch": "U-only" if V == 0.0 else "Mott/spin",
            "C_NN": c_value,
            "C_NN_source": source,
            "C_NN_sampling": FULL861_SAMPLING,
            "C_NN_fidelity": FULL861_FIDELITY,
            "C_NN_full_wedge_rows": 861,
            "C_NN_quadrature_weight": 1600.0,
            "C_NN_full_quadrature_weighted_population_std": 1.0e-5,
            "C_NN_population_std_diagnostic": 1.0e-5,
            "C_NN_spread": float("nan"),
            "twist_spread_is_standard_error": False,
            "eq10_factor": factor,
            "s_eq10_signed": predicted,
            "eq10_convention": EQ10_CONVENTION,
            "s_signed_observed": signed_observed,
            "s_u0_signed": s_u0_signed,
            "s_axis_anchor_signed": axis_anchor,
            "eq10_residual_observed_minus_prediction": signed_observed - predicted,
            "axis_anchor_residual_observed_minus_prediction": (
                signed_observed - axis_anchor
            ),
            "residual_convention": "observed minus prediction",
        }
        if fixture_only:
            row["fixture_only"] = True
            row["fixture_label"] = "synthetic test fixture; not production"
        rows.append(row)
    return pd.DataFrame(rows)


def production_provenance(csv_path: Path) -> dict:
    decision_certificate_sha256 = "d" * 64
    return {
        "schema_version": SCHEMA_VERSION,
        "data_product": DATA_PRODUCT,
        "C_NN_observable": C_NN_OBSERVABLE,
        "C_NN_fidelity": FULL861_FIDELITY,
        "analyzer_sha256": REVIEWED_FULL861_ANALYZER_SHA256,
        "decision_certificate_sha256": decision_certificate_sha256,
        "decision_gate_algorithm": DECISION_GATE_ALGORITHM,
        "reviewed_inputs": dict(REVIEWED_FULL861_PINS),
        "input_files": {
            "expansion_manifest": {
                "sha256": REVIEWED_FULL861_PINS["expansion_manifest_sha256"]
            },
            "source_25_manifest": {
                "sha256": REVIEWED_FULL861_PINS["source_25_manifest_sha256"]
            },
            "decision_certificate": {"sha256": decision_certificate_sha256},
            "decision_verifier": {
                "sha256": REVIEWED_FULL861_PINS["expansion_generator_sha256"]
            },
            "u40_summary": {
                "sha256": REVIEWED_FULL861_PINS["u40_summary_sha256"]
            },
            "u40_rows": {"sha256": REVIEWED_FULL861_PINS["u40_rows_sha256"]},
            "gz_points": {"sha256": REVIEWED_FULL861_PINS["gz_points_sha256"]},
        },
        "output_files": {POINTWISE_BASENAME: sha256(csv_path)},
        "campaign_pinned_solver": {
            label: REVIEWED_FULL861_PINS[label]
            for label in (
                "solver_sha256",
                "source_sha256",
                "qbasis_library_sha256",
            )
        },
        "raw_output_inventory": {
            "count": 10_332,
            "expansion_count": 10_032,
            "reused_25_count": 300,
            "all_status_complete": True,
            "all_sha256_match": True,
            "max_abs_identity_residual": 1.0e-12,
            "identity_tolerance": 1.0e-8,
        },
        "aggregation": {
            "C_NN_estimator": "861-point wedge with exchange and trapezoidal endpoint weights (weight 1600)",
            "twist_spread_is_standard_error": False,
            "campaign_case_count": 12,
            "full_wedge_coordinates_per_case": 861,
            "quadrature_weight_per_case": 1600.0,
            "pointwise_full861_count": 16,
        },
        "snapshot": {
            "immutable_add_only": True,
            "combined_targets": 10_332,
            "full_wedges_verified": True,
            "remote_local_analysis_agreement": True,
        },
        "expansion_decision": {
            "decision": "APPROVE_EXPANSION",
            "approved": True,
            "gate_algorithm": DECISION_GATE_ALGORITHM,
            "decision_certificate_sha256": decision_certificate_sha256,
            "decision_verifier_sha256": REVIEWED_FULL861_PINS[
                "expansion_generator_sha256"
            ],
            "case_count": 12,
            "source_decision_inputs_sha256": "e" * 64,
            "all_decision_driving_target_metrics_match_source_bytes": True,
        },
        "u40_controls": {
            "count": 4,
            "raw_wedge_rows": 3_444,
            "coordinates_per_case": 861,
            "quadrature_weight_per_case": 1600.0,
            "all_status_complete": True,
            "max_abs_identity_residual": 1.0e-12,
            "identity_tolerance": 1.0e-8,
            "summary_sha256": REVIEWED_FULL861_PINS["u40_summary_sha256"],
            "rows_sha256": REVIEWED_FULL861_PINS["u40_rows_sha256"],
        },
        "pointwise": {
            "count": 16,
            "expansion_full861_C_NN_points": 12,
            "existing_u40_full861_C_NN_points": 4,
            "full861_C_NN_points": 16,
            "all_rows_labeled_F861": True,
            "all_C_NN_inputs_independent_of_GZ_slope": True,
        },
        "equations": {
            "signed_convention": "omega_GZ(k)=s_NN epsilon_NN(k)",
            "eq10": "s_NN=1+[(2U-V)/(U-V)](2C_NN-1/2)",
        },
        "publication_artifacts_modified": False,
    }


def write_bundle(directory: Path, table: pd.DataFrame, *, fixture: bool) -> None:
    directory.mkdir(parents=True)
    csv_path = directory / POINTWISE_BASENAME
    table.to_csv(csv_path, index=False)
    if fixture:
        label = str(table["fixture_label"].iloc[0])
        provenance = {
            "fixture_only": True,
            "fixture_label": label,
            "data_product": FIXTURE_DATA_PRODUCT,
            "output_files": {POINTWISE_BASENAME: sha256(csv_path)},
            "publication_artifacts_modified": False,
        }
    else:
        provenance = production_provenance(csv_path)
    (directory / PROVENANCE_BASENAME).write_text(
        json.dumps(provenance, indent=2) + "\n"
    )


def write_frozen_release(
    results_root: Path,
    version: str,
    table: pd.DataFrame,
) -> Path:
    """Create a structurally real frozen release for downstream transaction tests."""

    release = results_root / f"{release_freezer.RELEASE_PREFIX}{version}"
    results_root.mkdir(parents=True, exist_ok=True)
    write_bundle(release, table, fixture=False)
    for index, basename in enumerate(release_freezer.ANALYZER_OUTPUT_BASENAMES):
        path = release / basename
        if not path.exists():
            path.write_text(f"synthetic analyzer output {index}\n")
    provenance = json.loads((release / PROVENANCE_BASENAME).read_text())
    file_hashes = {
        basename: sha256(release / basename)
        for basename in release_freezer.ANALYSIS_BASENAMES
    }
    manifest = release_freezer._release_manifest(
        file_hashes=file_hashes,
        provenance=provenance,
    )
    (release / release_freezer.RELEASE_MANIFEST_BASENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    for path in release.iterdir():
        path.chmod(0o444)
    release.chmod(0o555)
    release_freezer.validate_frozen_full861_release(
        release,
        results_root=results_root,
    )
    return release


def trusted_bundle_stub(directory: Path) -> FullobsEq10Bundle:
    """Downstream transaction stub; strict production binding is tested separately."""
    csv_path = directory / POINTWISE_BASENAME
    rows = validate_pointwise_eq10_predictions(pd.read_csv(csv_path))
    return FullobsEq10Bundle(rows, production_provenance(csv_path), directory.resolve())


class PointwiseContractTest(unittest.TestCase):
    def test_valid_exact_inventory_and_signed_eq10(self) -> None:
        validated = validate_pointwise_eq10_predictions(table_fixture())
        self.assertEqual(len(validated), 16)
        self.assertEqual(
            validated.groupby("U").size().to_dict(),
            {20.0: 5, 40.0: 5, 80.0: 6},
        )
        row = validated[(validated["U"] == 20.0) & (validated["V"] == 2.0)].iloc[0]
        signed = 1.0 + ((40.0 - 2.0) / (20.0 - 2.0)) * (2.0 * -0.34 - 0.5)
        self.assertAlmostEqual(row["s_eq10_signed"], signed, places=14)
        self.assertLess(row["s_eq10_signed"], 0.0)
        u40_v8 = validated[(validated["U"] == 40.0) & (validated["V"] == 8.0)].iloc[0]
        self.assertAlmostEqual(u40_v8["s_eq10_signed"], -1.681755579831535, places=13)

    def test_missing_and_duplicate_rejected(self) -> None:
        with self.assertRaisesRegex(PointwisePredictionError, "exactly 16"):
            validate_pointwise_eq10_predictions(table_fixture().iloc[:-1])
        duplicate = table_fixture()
        duplicate.iloc[-1] = duplicate.iloc[0]
        with self.assertRaisesRegex(PointwisePredictionError, "Duplicate"):
            validate_pointwise_eq10_predictions(duplicate)

    def test_non_fullobs_and_wrong_sampling_rejected(self) -> None:
        non_fullobs = table_fixture()
        non_fullobs.loc[0, "C_NN_source"] = "axis-anchor inferred from GZ slope"
        with self.assertRaisesRegex(PointwisePredictionError, "Wrong F861 source"):
            validate_pointwise_eq10_predictions(non_fullobs)
        wrong_sampling = table_fixture()
        wrong_sampling.loc[0, "C_NN_sampling"] = "single common C_NN"
        with self.assertRaisesRegex(PointwisePredictionError, "must be F861"):
            validate_pointwise_eq10_predictions(wrong_sampling)
        pilot = table_fixture()
        pilot.loc[0, "C_NN_sampling"] = (
            "deterministic_25_panel_unweighted_arithmetic_mean"
        )
        pilot.loc[0, "C_NN_fidelity"] = "P25"
        with self.assertRaisesRegex(PointwisePredictionError, "P25 inputs are rejected"):
            validate_pointwise_eq10_predictions(pilot)

    def test_unsigned_and_formula_tampering_rejected(self) -> None:
        unsigned = table_fixture()
        unsigned.loc[0, "s_eq10_signed"] *= -1.0
        with self.assertRaisesRegex(PointwisePredictionError, "signed Eq"):
            validate_pointwise_eq10_predictions(unsigned)
        factor = table_fixture()
        factor.loc[0, "eq10_factor"] += 0.01
        with self.assertRaisesRegex(PointwisePredictionError, "eq10_factor"):
            validate_pointwise_eq10_predictions(factor)

    def test_fixture_requires_explicit_opt_in(self) -> None:
        fixture = table_fixture(fixture_only=True)
        with self.assertRaisesRegex(PointwisePredictionError, "fixture table rejected"):
            validate_pointwise_eq10_predictions(fixture)
        validated = validate_pointwise_eq10_predictions(fixture, allow_fixture=True)
        self.assertTrue(validated["fixture_only"].all())


class BundleAndBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            prefix="fig4_cnn_builder_test_", dir=ROOT / "tmp"
        )
        self.work = Path(self.temp.name)

    def tearDown(self) -> None:
        for path in self.work.rglob("*"):
            if not path.is_symlink():
                path.chmod(0o700 if path.is_dir() else 0o600)
        self.temp.cleanup()

    def test_production_bundle_hash_and_independence_gates(self) -> None:
        bundle_dir = self.work / "valid_bundle"
        write_bundle(bundle_dir, table_fixture(), fixture=False)
        with self.assertRaisesRegex(
            PointwisePredictionError, "lacks the reviewed analyzer path"
        ):
            load_validated_fullobs_eq10_bundle(
                bundle_dir, scale_points_path=figure_builder.SCALE_POINTS
            )

        provenance_path = bundle_dir / PROVENANCE_BASENAME
        provenance = json.loads(provenance_path.read_text())
        provenance["pointwise"]["all_C_NN_inputs_independent_of_GZ_slope"] = False
        provenance_path.write_text(json.dumps(provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "independent all-F861"):
            load_validated_fullobs_eq10_bundle(
                bundle_dir, scale_points_path=figure_builder.SCALE_POINTS
            )

        analyzer_bundle = self.work / "wrong_analyzer_bundle"
        write_bundle(analyzer_bundle, table_fixture(), fixture=False)
        analyzer_path = analyzer_bundle / PROVENANCE_BASENAME
        analyzer_provenance = json.loads(analyzer_path.read_text())
        analyzer_provenance["analyzer_sha256"] = "0" * 64
        analyzer_path.write_text(json.dumps(analyzer_provenance) + "\n")
        with self.assertRaisesRegex(
            PointwisePredictionError, "reviewed all-F861 analyzer"
        ):
            load_validated_fullobs_eq10_bundle(
                analyzer_bundle, scale_points_path=figure_builder.SCALE_POINTS
            )

        write_bundle(self.work / "hash_bundle", table_fixture(), fixture=False)
        hash_bundle = self.work / "hash_bundle"
        with (hash_bundle / POINTWISE_BASENAME).open("a") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(PointwisePredictionError, "SHA-256"):
            load_validated_fullobs_eq10_bundle(
                hash_bundle, scale_points_path=figure_builder.SCALE_POINTS
            )

        tolerance_bundle = self.work / "inflated_tolerance_bundle"
        write_bundle(tolerance_bundle, table_fixture(), fixture=False)
        tolerance_path = tolerance_bundle / PROVENANCE_BASENAME
        tolerance_provenance = json.loads(tolerance_path.read_text())
        tolerance_provenance["raw_output_inventory"]["identity_tolerance"] = 1.0e-7
        tolerance_path.write_text(json.dumps(tolerance_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "reviewed 1e-8"):
            load_validated_fullobs_eq10_bundle(
                tolerance_bundle, scale_points_path=figure_builder.SCALE_POINTS
            )

        stricter_tolerance_bundle = self.work / "stricter_tolerance_bundle"
        write_bundle(stricter_tolerance_bundle, table_fixture(), fixture=False)
        stricter_path = stricter_tolerance_bundle / PROVENANCE_BASENAME
        stricter_provenance = json.loads(stricter_path.read_text())
        stricter_provenance["raw_output_inventory"]["identity_tolerance"] = 1.0e-9
        stricter_path.write_text(json.dumps(stricter_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "exact reviewed 1e-8"):
            load_validated_fullobs_eq10_bundle(
                stricter_tolerance_bundle,
                scale_points_path=figure_builder.SCALE_POINTS,
            )

        count_bundle = self.work / "wrong_raw_count_bundle"
        write_bundle(count_bundle, table_fixture(), fixture=False)
        count_path = count_bundle / PROVENANCE_BASENAME
        count_provenance = json.loads(count_path.read_text())
        count_provenance["raw_output_inventory"]["count"] = 300
        count_path.write_text(json.dumps(count_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "10,332-row F861"):
            load_validated_fullobs_eq10_bundle(
                count_bundle, scale_points_path=figure_builder.SCALE_POINTS
            )

        wedge_bundle = self.work / "wrong_wedge_bundle"
        write_bundle(wedge_bundle, table_fixture(), fixture=False)
        wedge_path = wedge_bundle / PROVENANCE_BASENAME
        wedge_provenance = json.loads(wedge_path.read_text())
        wedge_provenance["aggregation"]["full_wedge_coordinates_per_case"] = 25
        wedge_path.write_text(json.dumps(wedge_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "all-F861 aggregation"):
            load_validated_fullobs_eq10_bundle(
                wedge_bundle,
                scale_points_path=figure_builder.SCALE_POINTS,
            )

        controls_bundle = self.work / "wrong_u40_controls_bundle"
        write_bundle(controls_bundle, table_fixture(), fixture=False)
        controls_path = controls_bundle / PROVENANCE_BASENAME
        controls_provenance = json.loads(controls_path.read_text())
        controls_provenance["u40_controls"]["count"] = 3
        controls_path.write_text(json.dumps(controls_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "four complete hash-pinned"):
            load_validated_fullobs_eq10_bundle(
                controls_bundle,
                scale_points_path=figure_builder.SCALE_POINTS,
            )

        control_hash_bundle = self.work / "wrong_u40_hash_bundle"
        write_bundle(control_hash_bundle, table_fixture(), fixture=False)
        control_hash_path = control_hash_bundle / PROVENANCE_BASENAME
        control_hash_provenance = json.loads(control_hash_path.read_text())
        control_hash_provenance["u40_controls"]["rows_sha256"] = "0" * 64
        control_hash_path.write_text(json.dumps(control_hash_provenance) + "\n")
        with self.assertRaisesRegex(PointwisePredictionError, "four complete hash-pinned"):
            load_validated_fullobs_eq10_bundle(
                control_hash_bundle,
                scale_points_path=figure_builder.SCALE_POINTS,
            )

    def test_staging_build_redirects_all_outputs_and_preserves_active(self) -> None:
        bundle_dir = self.work / "fixture_bundle"
        write_bundle(bundle_dir, table_fixture(fixture_only=True), fixture=True)
        active = (
            figure_builder.OUT_PDF,
            figure_builder.OUT_PNG,
            figure_builder.ANALYTIC_POINTS,
            figure_builder.ANALYTIC_SUMMARY,
            figure_builder.BOUNDARY_FILTERED,
        )
        before = {path: sha256(path) for path in active}
        stage = self.work / "rendered"
        destinations = {
            "out_pdf": stage / "preview.pdf",
            "out_png": stage / "preview.png",
            "analytic_points_path": stage / "validation.csv",
            "analytic_summary_path": stage / "validation.json",
            "boundary_filtered_path": stage / "boundary.csv",
        }
        figure_builder.build_figure(
            **destinations,
            fullobs_analysis_dir=bundle_dir,
            staging_preview=True,
            allow_fixture=True,
        )
        self.assertTrue(all(path.is_file() for path in destinations.values()))
        self.assertEqual(before, {path: sha256(path) for path in active})

        validation = pd.read_csv(destinations["analytic_points_path"])
        self.assertTrue(
            {
                "C_NN_pointwise",
                "C_NN_source",
                "C_NN_sampling",
                "C_NN_fidelity",
                "C_NN_full_wedge_rows",
                "C_NN_quadrature_weight",
                "s_pointwise_eq10_signed",
                "diagnostic_s_axis_anchor_signed",
                "diagnostic_axis_anchor_residual_observed_minus_prediction",
                "strong_coupling_model",
                "fixture_only",
                "fixture_label",
            }.issubset(validation.columns)
        )
        summary = json.loads(destinations["analytic_summary_path"].read_text())
        self.assertIn("not production", summary["mott_curve_source"])
        self.assertTrue(summary["pointwise_bundle"]["fixture_only"])

    def test_production_promotion_path_is_explicit_and_staged(self) -> None:
        release_root = self.work / "release_results"
        bundle_dir = write_frozen_release(
            release_root,
            "production_bundle",
            table_fixture(),
        )
        reviewed_legacy_csv = figure_builder.ANALYTIC_POINTS.read_bytes()
        reviewed_legacy_json = figure_builder.ANALYTIC_SUMMARY.read_bytes()
        targets = self.work / "mock_active"
        out_pdf = targets / "figure.pdf"
        out_png = targets / "figure.png"
        analytic_csv = targets / "validation.csv"
        analytic_json = targets / "validation.json"
        boundary_csv = targets / "boundary.csv"
        prl_pdf = targets / "vertical.pdf"
        prl_png = targets / "vertical.png"
        manuscript_pdf = targets / "manuscript_fig4.pdf"
        promotion_tmp = self.work / "promotion_tmp"
        active_pointer = targets / "active_bundle.json"
        legacy_archive = targets / "legacy_archive"
        targets.mkdir(parents=True)
        analytic_csv.write_bytes(reviewed_legacy_csv)
        analytic_json.write_bytes(reviewed_legacy_json)
        with (
            mock.patch.multiple(
                figure_builder,
                OUT_PDF=out_pdf,
                OUT_PNG=out_png,
                ANALYTIC_POINTS=analytic_csv,
                ANALYTIC_SUMMARY=analytic_json,
                BOUNDARY_FILTERED=boundary_csv,
                PRL_VERTICAL_OUT_PDF=prl_pdf,
                PRL_VERTICAL_OUT_PNG=prl_png,
                MANUSCRIPT_FIG4_OUT_PDF=manuscript_pdf,
                STAGING_ROOT=promotion_tmp,
                ACTIVE_BUNDLE_POINTER=active_pointer,
                LEGACY_ANALYTIC_ARCHIVE_DIR=legacy_archive,
                RESULTS=release_root,
            ),
            mock.patch.object(
                figure_builder,
                "load_validated_fullobs_eq10_bundle",
                return_value=trusted_bundle_stub(bundle_dir),
            ),
        ):
            figure_builder.build_figure(
                out_pdf=out_pdf,
                out_png=out_png,
                analytic_points_path=analytic_csv,
                analytic_summary_path=analytic_json,
                boundary_filtered_path=boundary_csv,
                fullobs_analysis_dir=bundle_dir,
                production_promotion=True,
            )
            # Once promotion writes the active-bundle pointer, a default
            # rebuild must use the validated pointwise bundle, never silently
            # fall back to the legacy axis-anchor curve.
            figure_builder.build_figure(
                out_pdf=out_pdf,
                out_png=out_png,
                analytic_points_path=analytic_csv,
                analytic_summary_path=analytic_json,
                boundary_filtered_path=boundary_csv,
            )
            figure_builder.build_figure(
                out_pdf=prl_pdf,
                out_png=prl_png,
                fullobs_analysis_dir=bundle_dir,
                production_promotion=True,
                vertical=True,
                axis_text_scale=1.4,
                write_derived_tables=False,
            )
            valid_pointer_text = active_pointer.read_text()
            stale_pointer = json.loads(valid_pointer_text)
            stale_pointer["analysis_bundle_sha256"] = "0" * 64
            active_pointer.write_text(json.dumps(stale_pointer) + "\n")
            with self.assertRaisesRegex(
                RuntimeError,
                "stale against its frozen release manifest",
            ):
                figure_builder.build_figure(
                    out_pdf=out_pdf,
                    out_png=out_png,
                    analytic_points_path=analytic_csv,
                    analytic_summary_path=analytic_json,
                    boundary_filtered_path=boundary_csv,
                )
            active_pointer.write_text(valid_pointer_text)
            stale_decision_pointer = json.loads(valid_pointer_text)
            stale_decision_pointer["decision_certificate_sha256"] = "0" * 64
            active_pointer.write_text(json.dumps(stale_decision_pointer) + "\n")
            with self.assertRaisesRegex(
                RuntimeError,
                "stale against its frozen release manifest",
            ):
                figure_builder.build_figure(
                    out_pdf=out_pdf,
                    out_png=out_png,
                    analytic_points_path=analytic_csv,
                    analytic_summary_path=analytic_json,
                    boundary_filtered_path=boundary_csv,
                )
            active_pointer.write_text(valid_pointer_text)
            valid_manuscript_bytes = manuscript_pdf.read_bytes()
            manuscript_pdf.write_bytes(b"not the staged PRL PDF\n")
            nonidentical_pointer = json.loads(valid_pointer_text)
            nonidentical_pointer["release_artifacts_sha256"]["manuscript_pdf"] = (
                sha256(manuscript_pdf)
            )
            active_pointer.write_text(json.dumps(nonidentical_pointer) + "\n")
            with self.assertRaisesRegex(
                RuntimeError,
                "not byte-identical to the PRL vertical PDF",
            ):
                figure_builder.build_figure(
                    out_pdf=out_pdf,
                    out_png=out_png,
                    analytic_points_path=analytic_csv,
                    analytic_summary_path=analytic_json,
                    boundary_filtered_path=boundary_csv,
                )
            manuscript_pdf.write_bytes(valid_manuscript_bytes)
            active_pointer.write_text(valid_pointer_text)
        promoted = [
            out_pdf,
            out_png,
            prl_pdf,
            prl_png,
            manuscript_pdf,
            analytic_csv,
            analytic_json,
            boundary_csv,
        ]
        self.assertTrue(
            all(path.is_file() and path.stat().st_size > 0 for path in promoted)
        )
        self.assertTrue(prl_pdf.is_file() and prl_png.is_file())
        self.assertEqual(manuscript_pdf.read_bytes(), prl_pdf.read_bytes())
        self.assertFalse(
            promotion_tmp.exists() and any(promotion_tmp.iterdir()),
            "Atomic-promotion staging directory must be empty after success",
        )
        self.assertTrue(active_pointer.is_file())
        pointer = json.loads(active_pointer.read_text())
        self.assertEqual(pointer["analysis_dir"], str(bundle_dir.resolve()))
        release_manifest_path = (
            bundle_dir / release_freezer.RELEASE_MANIFEST_BASENAME
        )
        release_manifest = json.loads(release_manifest_path.read_text())
        self.assertEqual(
            pointer["analysis_release_manifest_sha256"],
            sha256(release_manifest_path),
        )
        self.assertEqual(
            pointer["analysis_bundle_sha256"],
            release_manifest["analysis_bundle_sha256"],
        )
        self.assertEqual(
            pointer["decision_certificate_sha256"],
            release_manifest["decision_certificate_sha256"],
        )
        self.assertEqual(
            pointer["decision_gate_algorithm"],
            release_manifest["decision_gate_algorithm"],
        )
        release_paths = {
            "pnas_pdf": out_pdf,
            "pnas_png": out_png,
            "prl_pdf": prl_pdf,
            "prl_png": prl_png,
            "manuscript_pdf": manuscript_pdf,
            "analytic_csv": analytic_csv,
            "analytic_json": analytic_json,
            "boundary_csv": boundary_csv,
        }
        self.assertEqual(
            pointer["release_artifacts_sha256"],
            {role: sha256(path) for role, path in release_paths.items()},
        )
        self.assertEqual(
            (legacy_archive / analytic_csv.name).read_bytes(),
            reviewed_legacy_csv,
        )
        self.assertEqual(
            (legacy_archive / analytic_json.name).read_bytes(),
            reviewed_legacy_json,
        )
        summary = json.loads(analytic_json.read_text())
        self.assertEqual(
            summary["mott_curve_source"],
            "pointwise independent fullobs F861 C_NN",
        )
        self.assertFalse(summary["pointwise_bundle"]["fixture_only"])
        self.assertEqual(
            summary["validation_exclusions"], ["V=0 points", "boundary points"]
        )
        self.assertEqual(
            summary["axis_anchor_role"], "diagnostic comparison only; not plotted"
        )
        mott_families = {
            float(item["U"]): item
            for item in summary["families"]
            if item["branch"] == "Mott/spin"
        }
        self.assertEqual(
            {U: item["point_count"] for U, item in mott_families.items()},
            {20.0: 4, 40.0: 4, 80.0: 5},
            "Production Mott RMSE must exclude the three V=0 points",
        )
        validation = pd.read_csv(analytic_csv)
        mott = validation[validation["branch"].isin(["U-only", "Mott/spin"])]
        self.assertEqual(len(mott), 16)
        self.assertTrue(mott["s_pointwise_eq10_signed"].lt(0.0).all())

    def test_vertical_staging_writes_only_the_prl_figure_pair(self) -> None:
        bundle_dir = self.work / "vertical_fixture_bundle"
        write_bundle(bundle_dir, table_fixture(fixture_only=True), fixture=True)
        active = (
            figure_builder.ANALYTIC_POINTS,
            figure_builder.ANALYTIC_SUMMARY,
            figure_builder.BOUNDARY_FILTERED,
        )
        before = {path: sha256(path) for path in active}
        stage = self.work / "vertical"
        figure_builder.build_figure(
            out_pdf=stage / "vertical.pdf",
            out_png=stage / "vertical.png",
            fullobs_analysis_dir=bundle_dir,
            staging_preview=True,
            allow_fixture=True,
            vertical=True,
            axis_text_scale=1.4,
            write_derived_tables=False,
        )
        self.assertTrue((stage / "vertical.pdf").is_file())
        self.assertTrue((stage / "vertical.png").is_file())
        self.assertEqual(
            sorted(path.name for path in stage.iterdir()),
            ["vertical.pdf", "vertical.png"],
        )
        self.assertEqual(before, {path: sha256(path) for path in active})

    def test_prl_vertical_invocation_suppresses_pnas_derived_writes(self) -> None:
        import build_prl_split_axis_figures as prl_builder

        with mock.patch.object(prl_builder, "build_scale_figure") as mocked:
            pdf, png = prl_builder.build_scale_boundary_figure()
        self.assertEqual(pdf, figure_builder.PRL_VERTICAL_OUT_PDF)
        self.assertEqual(png, figure_builder.PRL_VERTICAL_OUT_PNG)
        kwargs = mocked.call_args.kwargs
        self.assertTrue(kwargs["vertical"])
        self.assertFalse(kwargs["write_derived_tables"])
        self.assertIsNone(kwargs["fullobs_analysis_dir"])
        self.assertFalse(kwargs["production_promotion"])

        bundle = self.work / "durable_production_bundle"
        with mock.patch.object(prl_builder, "build_scale_figure") as mocked:
            prl_builder.build_scale_boundary_figure(
                fullobs_analysis_dir=bundle,
                production_promotion=True,
            )
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["fullobs_analysis_dir"], bundle)
        self.assertTrue(kwargs["production_promotion"])
        self.assertTrue(kwargs["vertical"])
        self.assertFalse(kwargs["write_derived_tables"])

    def test_active_default_artifact_hashes_and_derived_bytes_are_frozen(self) -> None:
        active = {
            "pdf": figure_builder.OUT_PDF,
            "png": figure_builder.OUT_PNG,
            "analytic_csv": figure_builder.ANALYTIC_POINTS,
            "analytic_json": figure_builder.ANALYTIC_SUMMARY,
            "boundary_csv": figure_builder.BOUNDARY_FILTERED,
            "prl_pdf": figure_builder.PRL_VERTICAL_OUT_PDF,
            "prl_png": figure_builder.PRL_VERTICAL_OUT_PNG,
            "manuscript_pdf": figure_builder.MANUSCRIPT_FIG4_OUT_PDF,
        }
        self.assertEqual(
            {label: sha256(path) for label, path in active.items()},
            ACTIVE_DEFAULT_SHA256,
        )

        generated = self.work / "default_derived"
        generated.mkdir()
        figure_builder.write_analytic_validation(
            figure_builder.load_scale_data(),
            analytic_points_path=generated / "validation.csv",
            analytic_summary_path=generated / "validation.json",
        )
        figure_builder.load_boundary_data(
            write_filtered=True, filtered_path=generated / "boundary.csv"
        )
        self.assertEqual(
            (generated / "validation.csv").read_bytes(),
            figure_builder.ANALYTIC_POINTS.read_bytes(),
        )
        self.assertEqual(
            (generated / "validation.json").read_bytes(),
            figure_builder.ANALYTIC_SUMMARY.read_bytes(),
        )
        self.assertEqual(
            (generated / "boundary.csv").read_bytes(),
            figure_builder.BOUNDARY_FILTERED.read_bytes(),
        )

    def test_builder_cli_is_read_only_even_for_help_or_no_arguments(self) -> None:
        active = (
            figure_builder.OUT_PDF,
            figure_builder.OUT_PNG,
            figure_builder.ANALYTIC_POINTS,
            figure_builder.ANALYTIC_SUMMARY,
            figure_builder.BOUNDARY_FILTERED,
            figure_builder.PRL_VERTICAL_OUT_PDF,
            figure_builder.PRL_VERTICAL_OUT_PNG,
            figure_builder.MANUSCRIPT_FIG4_OUT_PDF,
        )
        before = {path: sha256(path) for path in active}
        script = ROOT / "scripts" / "build_scale_and_transition_figure.py"

        help_run = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("Direct figure writes are disabled", help_run.stdout)

        refused = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("Direct figure writes are disabled", refused.stderr)
        self.assertEqual(before, {path: sha256(path) for path in active})

    def test_failed_bundle_creates_no_partial_outputs(self) -> None:
        bundle_dir = self.work / "bad_bundle"
        bad = table_fixture(fixture_only=True).iloc[:-1]
        write_bundle(bundle_dir, bad, fixture=True)
        stage = self.work / "must_not_exist"
        outputs = [
            stage / "preview.pdf",
            stage / "preview.png",
            stage / "validation.csv",
            stage / "validation.json",
            stage / "boundary.csv",
        ]
        with self.assertRaises(PointwisePredictionError):
            figure_builder.build_figure(
                out_pdf=outputs[0],
                out_png=outputs[1],
                analytic_points_path=outputs[2],
                analytic_summary_path=outputs[3],
                boundary_filtered_path=outputs[4],
                fullobs_analysis_dir=bundle_dir,
                staging_preview=True,
                allow_fixture=True,
            )
        self.assertFalse(stage.exists())

    def test_failed_production_gate_touches_no_active_destination(self) -> None:
        release_root = self.work / "invalid_release_results"
        bundle_dir = write_frozen_release(
            release_root,
            "bad_production_bundle",
            table_fixture().iloc[:-1],
        )
        targets = self.work / "untouched_active"
        out_pdf = targets / "figure.pdf"
        out_png = targets / "figure.png"
        analytic_csv = targets / "validation.csv"
        analytic_json = targets / "validation.json"
        boundary_csv = targets / "boundary.csv"
        promotion_tmp = self.work / "should_not_be_created"
        with mock.patch.multiple(
            figure_builder,
            OUT_PDF=out_pdf,
            OUT_PNG=out_png,
            ANALYTIC_POINTS=analytic_csv,
            ANALYTIC_SUMMARY=analytic_json,
            BOUNDARY_FILTERED=boundary_csv,
            STAGING_ROOT=promotion_tmp,
            RESULTS=release_root,
        ):
            with self.assertRaises(PointwisePredictionError):
                figure_builder.build_figure(
                    out_pdf=out_pdf,
                    out_png=out_png,
                    analytic_points_path=analytic_csv,
                    analytic_summary_path=analytic_json,
                    boundary_filtered_path=boundary_csv,
                    fullobs_analysis_dir=bundle_dir,
                    production_promotion=True,
                )
        self.assertFalse(targets.exists())
        self.assertFalse(promotion_tmp.exists())

    def test_production_rejects_unfrozen_arbitrary_durable_bundle(self) -> None:
        bundle_dir = self.work / "arbitrary_durable_analysis"
        write_bundle(bundle_dir, table_fixture(), fixture=False)
        release_root = self.work / "empty_release_results"
        release_root.mkdir()
        promotion_tmp = self.work / "unfrozen_rejection_stage"
        with (
            mock.patch.multiple(
                figure_builder,
                RESULTS=release_root,
                STAGING_ROOT=promotion_tmp,
            ),
            mock.patch.object(
                figure_builder,
                "load_validated_fullobs_eq10_bundle",
            ) as loader,
            self.assertRaisesRegex(
                RuntimeError,
                "validated frozen full-861 release",
            ),
        ):
            figure_builder.promote_pointwise_publication_release(
                fullobs_analysis_dir=bundle_dir
            )
        loader.assert_not_called()
        self.assertFalse(promotion_tmp.exists())

    def test_invalid_active_pointer_never_falls_back_to_anchor(self) -> None:
        pointer_states = {
            "directory": self.work / "pointer_directory",
            "malformed_json": self.work / "pointer_malformed.json",
            "broken_symlink": self.work / "pointer_broken_link.json",
        }
        pointer_states["directory"].mkdir()
        pointer_states["malformed_json"].write_text("not JSON\n")
        pointer_states["broken_symlink"].symlink_to(
            self.work / "pointer_missing_target.json"
        )

        for state, pointer in pointer_states.items():
            with self.subTest(state=state):
                with (
                    mock.patch.object(figure_builder, "ACTIVE_BUNDLE_POINTER", pointer),
                    mock.patch.object(figure_builder, "load_scale_data") as loader,
                ):
                    with self.assertRaises(RuntimeError):
                        figure_builder.build_figure()
                loader.assert_not_called()

    def test_mid_commit_failure_restores_complete_active_artifact_set(self) -> None:
        release_root = self.work / "rollback_release_results"
        bundle_dir = write_frozen_release(
            release_root,
            "production_bundle_for_rollback",
            table_fixture(),
        )
        reviewed_legacy_csv = figure_builder.ANALYTIC_POINTS.read_bytes()
        reviewed_legacy_json = figure_builder.ANALYTIC_SUMMARY.read_bytes()
        targets = self.work / "mock_active_rollback"
        targets.mkdir()
        out_pdf = targets / "figure.pdf"
        out_png = targets / "figure.png"
        analytic_csv = targets / "validation.csv"
        analytic_json = targets / "validation.json"
        boundary_csv = targets / "boundary.csv"
        prl_pdf = targets / "vertical.pdf"
        prl_png = targets / "vertical.png"
        manuscript_pdf = targets / "manuscript_fig4.pdf"
        active_pointer = targets / "active_bundle.json"
        active_paths = (
            out_pdf,
            out_png,
            prl_pdf,
            prl_png,
            manuscript_pdf,
            analytic_csv,
            analytic_json,
            boundary_csv,
        )
        for index, path in enumerate(active_paths):
            path.write_bytes(f"old-active-byte-sequence-{index}\n".encode())
        analytic_csv.write_bytes(reviewed_legacy_csv)
        analytic_json.write_bytes(reviewed_legacy_json)
        before = {path: path.read_bytes() for path in active_paths}
        transaction_destinations = set(active_paths) | {active_pointer}
        promotion_tmp = self.work / "rollback_promotion_tmp"
        legacy_archive = targets / "legacy_archive"
        real_replace = figure_builder.os.replace
        commit_count = 0

        def fail_pointer_candidate_replace(source, destination):
            nonlocal commit_count
            source_path = Path(source)
            destination_path = Path(destination)
            if (
                ".fullobs-candidate-" in source_path.name
                and destination_path in transaction_destinations
            ):
                commit_count += 1
                if commit_count == 9:
                    raise OSError("injected pointer commit failure")
            return real_replace(source, destination)

        with (
            mock.patch.multiple(
                figure_builder,
                OUT_PDF=out_pdf,
                OUT_PNG=out_png,
                ANALYTIC_POINTS=analytic_csv,
                ANALYTIC_SUMMARY=analytic_json,
                BOUNDARY_FILTERED=boundary_csv,
                PRL_VERTICAL_OUT_PDF=prl_pdf,
                PRL_VERTICAL_OUT_PNG=prl_png,
                MANUSCRIPT_FIG4_OUT_PDF=manuscript_pdf,
                STAGING_ROOT=promotion_tmp,
                ACTIVE_BUNDLE_POINTER=active_pointer,
                LEGACY_ANALYTIC_ARCHIVE_DIR=legacy_archive,
                RESULTS=release_root,
            ),
            mock.patch.object(
                figure_builder,
                "load_validated_fullobs_eq10_bundle",
                return_value=trusted_bundle_stub(bundle_dir),
            ),
        ):
            with mock.patch.object(
                figure_builder.os,
                "replace",
                side_effect=fail_pointer_candidate_replace,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "all active destinations were restored"
                ):
                    figure_builder.build_figure(
                        out_pdf=out_pdf,
                        out_png=out_png,
                        analytic_points_path=analytic_csv,
                        analytic_summary_path=analytic_json,
                        boundary_filtered_path=boundary_csv,
                        fullobs_analysis_dir=bundle_dir,
                        production_promotion=True,
                    )

        self.assertEqual(commit_count, 9)
        self.assertEqual(before, {path: path.read_bytes() for path in active_paths})
        self.assertFalse(active_pointer.exists())
        self.assertFalse(
            legacy_archive.exists(),
            "A newly prepared legacy archive is rolled back with a failed first release",
        )
        self.assertFalse(
            list(targets.glob(".*.fullobs-candidate-*.tmp"))
            or list(targets.glob(".*.fullobs-backup-*.tmp"))
        )
        self.assertFalse(
            promotion_tmp.exists() and any(promotion_tmp.iterdir()),
            "Failed promotion must remove its central staging directory",
        )

    def test_failed_update_preserves_preexisting_release_and_archive(self) -> None:
        release_root = self.work / "update_release_results"
        bundle_a = write_frozen_release(
            release_root,
            "production_bundle_a",
            table_fixture(),
        )
        changed = table_fixture()
        changed["C_NN"] = changed["C_NN"].astype(float) + 0.002
        changed["s_eq10_signed"] = eq10_signed(
            changed["U"], changed["V"], changed["C_NN"]
        )
        bundle_b = write_frozen_release(
            release_root,
            "production_bundle_b",
            changed,
        )

        targets = self.work / "mock_active_update_rollback"
        targets.mkdir()
        paths = {
            "pnas_pdf": targets / "horizontal.pdf",
            "pnas_png": targets / "horizontal.png",
            "prl_pdf": targets / "vertical.pdf",
            "prl_png": targets / "vertical.png",
            "manuscript_pdf": targets / "manuscript_fig4.pdf",
            "analytic_csv": targets / "validation.csv",
            "analytic_json": targets / "validation.json",
            "boundary_csv": targets / "boundary.csv",
            "pointer": targets / "active_bundle.json",
        }
        paths["analytic_csv"].write_bytes(figure_builder.ANALYTIC_POINTS.read_bytes())
        paths["analytic_json"].write_bytes(figure_builder.ANALYTIC_SUMMARY.read_bytes())
        legacy_archive = targets / "legacy_archive"
        promotion_tmp = self.work / "update_rollback_tmp"
        render_generation = 0

        def fake_render(**kwargs):
            orientation = "vertical" if kwargs["vertical"] else "horizontal"
            kwargs["out_pdf"].write_bytes(
                f"generation={render_generation};{orientation};pdf\n".encode()
            )
            kwargs["out_png"].write_bytes(
                f"generation={render_generation};{orientation};png\n".encode()
            )

        with (
            mock.patch.multiple(
                figure_builder,
                OUT_PDF=paths["pnas_pdf"],
                OUT_PNG=paths["pnas_png"],
                PRL_VERTICAL_OUT_PDF=paths["prl_pdf"],
                PRL_VERTICAL_OUT_PNG=paths["prl_png"],
                MANUSCRIPT_FIG4_OUT_PDF=paths["manuscript_pdf"],
                ANALYTIC_POINTS=paths["analytic_csv"],
                ANALYTIC_SUMMARY=paths["analytic_json"],
                BOUNDARY_FILTERED=paths["boundary_csv"],
                ACTIVE_BUNDLE_POINTER=paths["pointer"],
                LEGACY_ANALYTIC_ARCHIVE_DIR=legacy_archive,
                STAGING_ROOT=promotion_tmp,
                RESULTS=release_root,
            ),
            mock.patch.object(
                figure_builder, "_render_combined_figure", side_effect=fake_render
            ),
            mock.patch.object(
                figure_builder,
                "load_validated_fullobs_eq10_bundle",
                side_effect=lambda directory, **_: trusted_bundle_stub(Path(directory)),
            ),
        ):
            figure_builder.promote_pointwise_publication_release(
                fullobs_analysis_dir=bundle_a
            )
            generation_a = {role: path.read_bytes() for role, path in paths.items()}
            archive_a = {
                path.name: path.read_bytes()
                for path in legacy_archive.iterdir()
                if path.is_file()
            }

            render_generation = 1
            real_replace = figure_builder.os.replace
            commit_count = 0

            def fail_pointer_update(source, destination):
                nonlocal commit_count
                source_path = Path(source)
                destination_path = Path(destination)
                if (
                    ".fullobs-candidate-" in source_path.name
                    and destination_path in set(paths.values())
                ):
                    commit_count += 1
                    if commit_count == 9:
                        raise OSError("injected generation-B pointer failure")
                return real_replace(source, destination)

            with mock.patch.object(
                figure_builder.os,
                "replace",
                side_effect=fail_pointer_update,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "all active destinations were restored"
                ):
                    figure_builder.promote_pointwise_publication_release(
                        fullobs_analysis_dir=bundle_b
                    )

        self.assertEqual(commit_count, 9)
        self.assertEqual(
            generation_a,
            {role: path.read_bytes() for role, path in paths.items()},
        )
        self.assertEqual(
            archive_a,
            {
                path.name: path.read_bytes()
                for path in legacy_archive.iterdir()
                if path.is_file()
            },
            "A failed update must not remove or rewrite the preexisting archive",
        )
        self.assertFalse(
            list(targets.glob(".*.fullobs-candidate-*.tmp"))
            or list(targets.glob(".*.fullobs-backup-*.tmp"))
        )
        self.assertFalse(
            promotion_tmp.exists() and any(promotion_tmp.iterdir()),
            "Failed update must remove its central staging directory",
        )

    def test_legacy_archive_copy_failure_never_installs_partial_archive(self) -> None:
        analytic_csv = self.work / "legacy_validation.csv"
        analytic_json = self.work / "legacy_validation.json"
        analytic_csv.write_text("legacy csv\n")
        analytic_json.write_text('{"legacy": true}\n')
        archive = self.work / "legacy_archive_atomic"
        real_copy2 = figure_builder.shutil.copy2
        archive_copy_count = 0

        def fail_second_archive_copy(source, destination, *args, **kwargs):
            nonlocal archive_copy_count
            destination_path = Path(destination)
            if destination_path.parent.name.startswith(f".{archive.name}.staging-"):
                archive_copy_count += 1
                if archive_copy_count == 2:
                    raise OSError("injected archive copy failure")
            return real_copy2(source, destination, *args, **kwargs)

        with mock.patch.object(
            figure_builder.shutil,
            "copy2",
            side_effect=fail_second_archive_copy,
        ):
            with self.assertRaisesRegex(OSError, "injected archive copy failure"):
                figure_builder._archive_legacy_analytic_outputs(
                    analytic_csv=analytic_csv,
                    analytic_json=analytic_json,
                    archive_dir=archive,
                )

        self.assertEqual(archive_copy_count, 2)
        self.assertFalse(archive.exists())
        self.assertFalse(
            any(
                path.name.startswith(f".{archive.name}.staging-")
                for path in self.work.iterdir()
            )
        )

    def test_unreviewed_legacy_outputs_are_not_archived(self) -> None:
        analytic_csv = self.work / "unreviewed_legacy.csv"
        analytic_json = self.work / "unreviewed_legacy.json"
        analytic_csv.write_text("not the reviewed legacy table\n")
        analytic_json.write_text('{"not": "the reviewed legacy summary"}\n')
        archive = self.work / "must_not_be_labeled_legacy"
        with self.assertRaisesRegex(RuntimeError, "unreviewed legacy"):
            figure_builder._archive_legacy_analytic_outputs(
                analytic_csv=analytic_csv,
                analytic_json=analytic_json,
                archive_dir=archive,
                expected_sha256=figure_builder.REVIEWED_LEGACY_ANALYTIC_SHA256,
            )
        self.assertFalse(archive.exists())

    def test_explicit_legacy_diagnostic_retains_axis_anchor_curves(self) -> None:
        points = figure_builder.load_scale_data()
        fig, ax = plt.subplots()
        figure_builder.draw_scale_panel(ax, points)
        line_lengths = [len(line.get_xdata()) for line in ax.lines]
        plt.close(fig)
        self.assertEqual(line_lengths.count(220), 3)

    def test_pointwise_panel_uses_only_open_measured_nodes(self) -> None:
        points = figure_builder.load_scale_data()
        predictions = validate_pointwise_eq10_predictions(
            table_fixture(fixture_only=True), allow_fixture=True
        )
        fig, ax = plt.subplots()
        figure_builder.draw_scale_panel(ax, points, cnn_predictions=predictions)
        theory_lines = [
            line
            for line in ax.lines
            if line.get_markerfacecolor() == "white"
            and line.get_color() in figure_builder.COLORS.values()
        ]
        plt.close(fig)
        self.assertEqual(
            sorted(len(line.get_xdata()) for line in theory_lines), [5, 5, 6]
        )
        self.assertTrue(
            all(
                max(float(x) for x in line.get_xdata()) <= 0.225
                for line in theory_lines
            )
        )


if __name__ == "__main__":
    unittest.main()
