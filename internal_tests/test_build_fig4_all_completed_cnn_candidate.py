#!/usr/bin/env python3
"""Contract tests for the all-completed, figure-only Fig. 4 candidate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_fig4_all_completed_cnn_candidate as builder  # noqa: E402


SNAPSHOT = ROOT / "results/staging/fig4_cnn_p25_13case_replica_resolved_20260822_103044"
AUDIT = (
    ROOT
    / "results/staging/fig4_cnn_p25_13case_replica_resolved_20260822_103044.deep_audit.json"
)


@unittest.skipUnless(
    SNAPSHOT.is_dir() and AUDIT.is_file(), "frozen Fig. 4 input absent"
)
class AllCompletedFig4CandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.p25, cls.raw, _, _ = builder.validate_p25_bundle(
            SNAPSHOT,
            snapshot_ledger_sha256=(
                "a5ee8e533b8bfc05d4fb671e456e941e3256541787ad0cd9e825904272fbacad"
            ),
            deep_audit=AUDIT,
            deep_audit_sha256=(
                "e31ab2c40b5e356da1b2926549091edd3c9f5cf01fc63d492402fad9eac01b54"
            ),
        )
        controls, calibration = builder.load_reviewed_u40_controls()
        cls.pointwise, cls.metrics = builder.assemble_pointwise(
            cls.p25, controls, calibration
        )

    def test_exact_inventory_and_one_replica_per_missing_twist(self) -> None:
        self.assertEqual(len(self.raw), 325)
        self.assertEqual(len(self.pointwise), 17)
        selected = self.raw[
            self.raw["source_role"].eq("D_selected_replica_for_missing_A")
        ]
        self.assertEqual(len(selected), 5)
        self.assertEqual(
            sorted(selected["source_job_id"].astype(int).tolist()),
            [5618538, 5618539, 5618540, 5618541, 5618547],
        )
        self.assertFalse(self.raw.duplicated(["U", "V", "kx", "ky"]).any())

    def test_matched_sampling_drift_and_axis_anchor(self) -> None:
        for U, group in self.pointwise.groupby("U", sort=True):
            anchor = group[group["V"].eq(0.0)].iloc[0]
            self.assertAlmostEqual(
                anchor["s_eq10_axis_anchored_C_NN_drift"],
                anchor["s_signed_observed"],
                places=13,
            )
        u40v6 = self.pointwise[
            self.pointwise["U"].eq(40.0) & self.pointwise["V"].eq(6.0)
        ].iloc[0]
        u40v4 = self.pointwise[
            self.pointwise["U"].eq(40.0) & self.pointwise["V"].eq(4.0)
        ].iloc[0]
        self.assertIn("P25 minus matched P25", u40v6["C_NN_reference_sampling"])
        self.assertEqual(
            u40v4["C_NN_reference_sampling"],
            "F861 minus F861 at U=40,V=0",
        )
        for U in (20.0, 40.0, 80.0):
            family = self.metrics[
                self.metrics["U"].eq(U) & self.metrics["scope"].eq("finite-V nodes")
            ].set_index("model")
            drift = family.loc[
                "axis-anchored Eq. (10) + measured matched-sampling C_NN drift",
                "rmse",
            ]
            no_drift = family.loc["V=0-axis anchor without measured C_NN drift", "rmse"]
            self.assertLess(drift, no_drift)

    def test_only_gz_data_have_markers(self) -> None:
        fig, ax = plt.subplots()
        try:
            builder.draw_scale_panel(
                ax, builder.legacy_fig4.load_scale_data(), self.pointwise
            )
            marker_lines = [
                line for line in ax.lines if line.get_marker() not in (None, "None", "")
            ]
            self.assertEqual(len(marker_lines), 3)
            self.assertEqual(
                {line.get_marker() for line in marker_lines}, {"s", "^", "D"}
            )
            self.assertTrue(
                all(np.isclose(line.get_linewidth(), 0.0) for line in marker_lines)
            )
            prediction_lines = [
                line
                for line in ax.lines
                if line.get_color() in set(builder.legacy_fig4.COLORS.values())
                and line.get_marker() in (None, "None", "")
            ]
            self.assertEqual(len(prediction_lines), 3)
            legend = ax.get_legend()
            self.assertIsNotNone(legend)
            self.assertEqual(
                [text.get_text() for text in legend.get_texts()],
                [r"$U=20$", r"$U=40$", r"$U=80$"],
            )
            self.assertEqual(
                [text.get_fontsize() for text in legend.get_texts()],
                [9.84, 9.84, 9.84],
            )
            self.assertNotIn(
                r"fullobs $C_{\rm NN}$ drifts: P25; $U=40$ controls F861",
                [text.get_text() for text in ax.texts],
            )
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
