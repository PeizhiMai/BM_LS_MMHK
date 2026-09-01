#!/usr/bin/env python3
"""Synthetic end-to-end tests for the staging Fig. 4 C_NN diagnostic."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

from internal_tests.test_fig4_cnn_prediction_input import (
    production_provenance,
    table_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fig4_cnn_prediction_input as prediction_input  # noqa: E402
import plot_fig4_cnn_diagnostic as plotter  # noqa: E402


POINTWISE_NAME = "fig4_cnn_pointwise_eq10.csv"
PROVENANCE_NAME = "fig4_cnn_analysis_provenance.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Fig4CnnDiagnosticPlotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fig4_cnn_plot_test_")
        self.work = Path(self.temp.name)
        self.analysis = self.work / "analysis"
        self.analysis.mkdir()
        pointwise = self.analysis / POINTWISE_NAME
        table_fixture().to_csv(pointwise, index=False)
        (self.analysis / PROVENANCE_NAME).write_text(
            json.dumps(production_provenance(pointwise), indent=2) + "\n"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_plot(
        self, pointwise: Path, provenance: Path, output: Path
    ) -> SimpleNamespace:
        argv = [
            str(plotter.__file__),
            "--pointwise",
            str(pointwise),
            "--provenance",
            str(provenance),
            "--output-dir",
            str(output),
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()
        returncode = 0
        try:
            with (
                mock.patch.object(sys, "argv", argv),
                # This test targets plot layout and plot-level gates. The
                # strict immutable-snapshot replay is covered end-to-end by
                # test_analyze_fig4_cnn_full861_campaign.
                mock.patch.object(
                    prediction_input,
                    "_bind_and_replay_reviewed_analyzer",
                    return_value=None,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                plotter.main()
        except Exception as exc:
            returncode = 1
            stderr.write(str(exc))
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    def write_mutated_contract(
        self, directory: Path, frame: pd.DataFrame
    ) -> tuple[Path, Path]:
        directory.mkdir(parents=True)
        pointwise = directory / POINTWISE_NAME
        provenance = directory / PROVENANCE_NAME
        frame.to_csv(pointwise, index=False)
        payload = json.loads((self.analysis / PROVENANCE_NAME).read_text())
        payload["output_files"][POINTWISE_NAME] = file_hash(pointwise)
        provenance.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return pointwise, provenance

    def test_render_and_rejection_gates(self) -> None:
        pointwise = self.analysis / POINTWISE_NAME
        provenance = self.analysis / PROVENANCE_NAME
        preview = self.work / "preview"
        success = self.run_plot(pointwise, provenance, preview)
        self.assertEqual(success.returncode, 0, msg=success.stdout + success.stderr)
        self.assertIn("Validated pointwise input: 16/16 unique rows", success.stdout)
        self.assertIn("All 16 C_NN inputs: F861", success.stdout)
        png = preview / "fig4_cnn_staging_diagnostic.png"
        pdf = preview / "fig4_cnn_staging_diagnostic.pdf"
        qa_path = preview / "fig4_cnn_staging_diagnostic_qa.json"
        self.assertTrue(png.is_file() and png.stat().st_size > 100_000)
        self.assertTrue(pdf.is_file() and pdf.stat().st_size > 10_000)
        qa = json.loads(qa_path.read_text())
        self.assertEqual(qa["validation"]["schema_version"], 3)
        self.assertEqual(
            qa["validation"]["data_product"],
            "fig4_pointwise_full861_direct_fullobs_C_NN_eq10",
        )
        self.assertEqual(qa["validation"]["C_NN_observable"], "<C1_NN>")
        self.assertEqual(qa["validation"]["C_NN_fidelity"], "F861")
        self.assertEqual(qa["validation"]["pointwise_rows"], 16)
        self.assertEqual(qa["validation"]["expansion_full861_rows"], 12)
        self.assertEqual(qa["validation"]["existing_u40_full861_rows"], 4)
        self.assertEqual(qa["validation"]["all_full861_rows"], 16)
        self.assertFalse(qa["validation"]["twist_spread_is_standard_error"])
        self.assertGreater(
            qa["outputs"]["fig4_cnn_staging_diagnostic.png"]["width_px"], 2000
        )
        for protected in (
            ROOT / "results/diagnostic_should_be_rejected",
            ROOT / "figures/diagnostic_should_be_rejected",
            ROOT / "manuscript/diagnostic_should_be_rejected",
        ):
            with self.subTest(protected=protected):
                with self.assertRaisesRegex(
                    plotter.ValidationError,
                    "Refusing staging diagnostic output",
                ):
                    plotter.validate_output_dir(protected)

        original = pd.read_csv(pointwise)
        incomplete, incomplete_provenance = self.write_mutated_contract(
            self.work / "incomplete_contract", original.iloc[:-1].copy()
        )
        incomplete_run = self.run_plot(
            incomplete,
            incomplete_provenance,
            self.work / "incomplete_plot",
        )
        self.assertNotEqual(incomplete_run.returncode, 0)
        self.assertIn(
            "must contain exactly 16 rows; found 15",
            incomplete_run.stdout + incomplete_run.stderr,
        )

        duplicate_frame = original.copy()
        duplicate_frame.iloc[-1] = duplicate_frame.iloc[0]
        duplicate, duplicate_provenance = self.write_mutated_contract(
            self.work / "duplicate_contract", duplicate_frame
        )
        duplicate_run = self.run_plot(
            duplicate,
            duplicate_provenance,
            self.work / "duplicate_plot",
        )
        self.assertNotEqual(duplicate_run.returncode, 0)
        self.assertIn(
            "Duplicate pointwise C_NN cases",
            duplicate_run.stdout + duplicate_run.stderr,
        )

        bad_pointwise, bad_provenance_path = self.write_mutated_contract(
            self.work / "bad_provenance_bundle", original
        )
        bad_provenance = json.loads(bad_provenance_path.read_text())
        bad_provenance["pointwise"]["existing_u40_full861_C_NN_points"] = 3
        bad_provenance_path.write_text(json.dumps(bad_provenance) + "\n")
        provenance_run = self.run_plot(
            bad_pointwise,
            bad_provenance_path,
            self.work / "bad_provenance_plot",
        )
        self.assertNotEqual(provenance_run.returncode, 0)
        self.assertIn(
            "16 independent all-F861",
            provenance_run.stdout + provenance_run.stderr,
        )

        bad_contract_pointwise, bad_contract_path = self.write_mutated_contract(
            self.work / "bad_data_product_bundle", original
        )
        bad_contract = json.loads(bad_contract_path.read_text())
        bad_contract["data_product"] = "unreviewed_product"
        bad_contract_path.write_text(json.dumps(bad_contract) + "\n")
        contract_run = self.run_plot(
            bad_contract_pointwise,
            bad_contract_path,
            self.work / "bad_data_product_plot",
        )
        self.assertNotEqual(contract_run.returncode, 0)
        self.assertIn(
            "data_product must be",
            contract_run.stdout + contract_run.stderr,
        )


if __name__ == "__main__":
    unittest.main()
