#!/usr/bin/env python3
"""Synthetic end-to-end test for the Fig. 4 C_NN campaign analyzer."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_fig4_cnn_campaign.py"
BATCH_TEMPLATE = ROOT / "scripts" / "cades_queue" / "fullobs_25twist_fig4_cnn_20260820"
U40_SUMMARY = (
    ROOT / "results" / "fullobs_U40_observable_summary_by_V_20260723_091307.csv"
)
U40_ROWS = ROOT / "results" / "fullobs_U40_observable_rows_20260723_091307.csv.gz"
GZ_POINTS = ROOT / "results" / "pnas_scale_rule_points_eta0p05.csv"
REVIEWED_MANIFEST_SHA256 = (
    "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
)


def synthetic_output(U: float, V: float, kx: int, ky: int) -> str:
    phase = 0.17 * kx + 0.11 * ky
    C = -0.34 + 7.0e-6 * math.sin(phase) + 1.5e-4 * (V / U)
    D = 0.008 + 2.0e-5 * (1.0 + math.cos(phase))
    nn = 0.985 + 3.0e-5 * math.sin(phase)
    kinetic_nn = -0.24 + 2.0e-5 * math.cos(phase)
    kinetic_nnn = 0.0
    kinetic = kinetic_nn + kinetic_nnn
    E0 = 16.0 * (kinetic + U * D + 2.0 * V * nn)
    Sc = 0.032
    mcdw = Sc / 16.0
    return f"""Lx\t4
Ly\t4
tp\t0.000000000000000000e+00
U\t{U:.18e}
V\t{V:.18e}
E0\t{E0:.18e}
Gap\t0.000000000000000000e+00

<nn_NN> {nn:.18e}
<delta_n_delta_n_NN> {nn - 1.0:.18e}
<Kinetic_NN_per_site> {kinetic_nn:.18e}
<Kinetic_NNN_per_site> {kinetic_nnn:.18e}
<Kinetic_per_site> {kinetic:.18e}
<C1_NN> {C:.18e}
Q\t0,0
<nq> 1.000000000000000000e+00
<nq_upnq_dn> 2.500000000000000000e-01
<ni_upni_dn> {D:.18e}
<Spipi> 1.000000000000000000e+00
<Sc_pipi> {Sc:.18e}
<mCDW2_pipi> {mcdw:.18e}
status\tCOMPLETE
"""


class Fig4CnnAnalyzerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fig4_cnn_analyzer_test_")
        self.work = Path(self.temp.name)
        self.campaign = self.work / "campaign"
        self.raw = self.campaign / "raw"
        self.raw.mkdir(parents=True)
        for name in ("manifest.tsv", "provenance.json", "twist_panel.tsv"):
            shutil.copy2(BATCH_TEMPLATE / name, self.campaign / name)
        manifest = pd.read_csv(self.campaign / "manifest.tsv", sep="\t")
        for row in manifest.itertuples(index=False):
            name = Path(str(row.result)).name
            (self.raw / name).write_text(
                synthetic_output(float(row.U), float(row.V), int(row.kx), int(row.ky))
            )
        self.manifest = manifest

    def tearDown(self) -> None:
        self.temp.cleanup()

    def command(self, output: Path) -> list[str]:
        return [
            sys.executable,
            str(SCRIPT),
            "--campaign-root",
            str(self.campaign),
            "--output-dir",
            str(output),
            "--u40-summary",
            str(U40_SUMMARY),
            "--u40-rows",
            str(U40_ROWS),
            "--gz-points",
            str(GZ_POINTS),
        ]

    def test_end_to_end_and_incomplete_gate(self) -> None:
        output = self.work / "analysis_success"
        result = subprocess.run(
            self.command(output),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Validated campaign outputs: 300/300 COMPLETE", result.stdout)

        raw = pd.read_csv(output / "fig4_cnn_campaign_raw_validation.csv")
        panel = pd.read_csv(output / "fig4_cnn_campaign_panel_summary.csv")
        calibration = pd.read_csv(output / "fig4_cnn_u40_panel_calibration.csv")
        pointwise = pd.read_csv(output / "fig4_cnn_pointwise_eq10.csv")
        families = pd.read_csv(output / "fig4_cnn_pointwise_family_summary.csv")
        provenance = json.loads(
            (output / "fig4_cnn_analysis_provenance.json").read_text()
        )

        self.assertEqual(len(raw), 300)
        self.assertEqual(len(panel), 12)
        self.assertEqual(len(calibration), 4)
        self.assertEqual(len(pointwise), 16)
        self.assertEqual(len(families), 8)
        self.assertLess(calibration["abs_panel_minus_full"].max(), 1.0e-6)
        self.assertEqual(
            pointwise["C_NN_sampling"].value_counts().to_dict(),
            {
                "deterministic_25_panel_unweighted_arithmetic_mean": 12,
                "full_861_wedge_trapezoidal_weight_1600": 4,
            },
        )

        check = pointwise[(pointwise["U"] == 20.0) & (pointwise["V"] == 2.0)].iloc[0]
        expected = 1.0 + ((2.0 * 20.0 - 2.0) / (20.0 - 2.0)) * (
            2.0 * check["C_NN"] - 0.5
        )
        self.assertAlmostEqual(check["s_eq10_signed"], expected, places=13)
        u40_v8 = pointwise[(pointwise["U"] == 40.0) & (pointwise["V"] == 8.0)].iloc[0]
        self.assertAlmostEqual(u40_v8["s_eq10_signed"], -1.681755579831535, places=13)
        self.assertEqual(
            u40_v8["C_NN_sampling"],
            "full_861_wedge_trapezoidal_weight_1600",
        )
        self.assertEqual(
            u40_v8["C_NN_source"],
            "existing U=40 all-twist fullobs control",
        )
        anchors = pointwise[pointwise["V"] == 0.0]
        self.assertTrue(
            (anchors["s_signed_observed"] - anchors["s_axis_anchor_signed"])
            .abs()
            .lt(1.0e-13)
            .all()
        )
        self.assertEqual(provenance["raw_output_inventory"]["count"], 300)
        self.assertEqual(provenance["schema_version"], 1)
        self.assertEqual(
            provenance["data_product"],
            "fig4_pointwise_direct_fullobs_C_NN_eq10",
        )
        self.assertEqual(provenance["C_NN_observable"], "<C1_NN>")
        self.assertEqual(
            provenance["reviewed_manifest_sha256"], REVIEWED_MANIFEST_SHA256
        )
        self.assertEqual(
            provenance["input_files"]["manifest"]["sha256"],
            REVIEWED_MANIFEST_SHA256,
        )
        self.assertFalse(provenance["publication_artifacts_modified"])
        self.assertTrue(
            provenance["pointwise"]["all_C_NN_inputs_independent_of_GZ_slope"]
        )

        unexpected = self.raw / "unexpected_control_obs.dat"
        unexpected.write_text("status\tCOMPLETE\n")
        extra_failed = subprocess.run(
            self.command(self.work / "analysis_unexpected"),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(extra_failed.returncode, 0)
        self.assertIn(
            "Raw directory contains 1 unexpected *_obs.dat files",
            extra_failed.stdout + extra_failed.stderr,
        )
        unexpected.unlink()

        manifest_path = self.campaign / "manifest.tsv"
        reviewed_manifest = manifest_path.read_bytes()
        manifest_path.write_bytes(reviewed_manifest + b"\n")
        manifest_failed = subprocess.run(
            self.command(self.work / "analysis_manifest_hash_mismatch"),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        manifest_path.write_bytes(reviewed_manifest)
        self.assertNotEqual(manifest_failed.returncode, 0)
        self.assertIn(
            "Manifest SHA-256 does not match the reviewed campaign manifest",
            manifest_failed.stdout + manifest_failed.stderr,
        )

        missing_name = Path(str(self.manifest.iloc[0]["result"])).name
        (self.raw / missing_name).unlink()
        failed = subprocess.run(
            self.command(self.work / "analysis_missing"),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Missing 1 of 300 raw outputs", failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()
