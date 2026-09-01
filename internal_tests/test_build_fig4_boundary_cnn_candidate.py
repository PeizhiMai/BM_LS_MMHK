#!/usr/bin/env python3
"""Contract tests for the staging-only Fig. 4 boundary-endpoint builder."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_fig4_boundary_cnn_candidate as builder  # noqa: E402


BASE_SNAPSHOT = (
    ROOT / "results/staging/fig4_cnn_p25_13case_replica_resolved_20260822_103044"
)
BASE_AUDIT = ROOT / (
    "results/staging/"
    "fig4_cnn_p25_13case_replica_resolved_20260822_103044.deep_audit.json"
)


@unittest.skipUnless(
    BASE_SNAPSHOT.is_dir() and BASE_AUDIT.is_file(),
    "frozen 13-case Fig. 4 input absent",
)
class BoundaryCandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        builder._validate_base_builder_identity()
        cls.p25, cls.raw, _, _ = builder.base.validate_p25_bundle(
            BASE_SNAPSHOT,
            snapshot_ledger_sha256=(
                "a5ee8e533b8bfc05d4fb671e456e941e3256541787ad0cd9e825904272fbacad"
            ),
            deep_audit=BASE_AUDIT,
            deep_audit_sha256=(
                "e31ab2c40b5e356da1b2926549091edd3c9f5cf01fc63d492402fad9eac01b54"
            ),
        )
        controls, calibration = builder.base.load_reviewed_u40_controls()
        u40v10, u40v10_calibration = builder.load_u40_v10_endpoint()
        addon = pd.DataFrame(
            [
                {
                    "U": 80.0,
                    "V": 20.0,
                    "r": 0.25,
                    "complete_twists": 25,
                    "C_NN": builder.EXPECTED_U80V20_C_NN_MEAN,
                    "C_NN_min": -0.3494613620759718,
                    "C_NN_max": -0.3494565324548047,
                    "C_NN_spread": 4.8296211671017275e-6,
                    "C_NN_population_std_diagnostic": 1.4332088442441903e-6,
                    "C_NN_source": "replica-resolved fullobs P25",
                    "C_NN_sampling": "25-twist unweighted arithmetic mean",
                    "C_NN_fidelity": "P25",
                }
            ]
        )
        cls.pointwise, cls.metrics, cls.calibration = (
            builder.assemble_final_pointwise(
                cls.p25,
                controls,
                calibration,
                addon,
                u40v10,
                u40v10_calibration,
            )
        )

    def test_base_contract_remains_frozen(self) -> None:
        self.assertEqual(len(builder.FROZEN_P25_CASES_13), 13)
        self.assertEqual(len(builder.FROZEN_U40_CONTROLS_4), 4)
        self.assertEqual(len(builder.FROZEN_POINTWISE_CASES_17), 17)
        self.assertEqual(len(self.raw), 325)

    def test_final_exact_inventory(self) -> None:
        self.assertEqual(len(self.pointwise), 19)
        self.assertEqual(
            self.pointwise.groupby("U").size().to_dict(),
            {20.0: 6, 40.0: 6, 80.0: 7},
        )
        self.assertEqual(len(self.calibration), 5)
        self.assertEqual(
            set(self.calibration["V"].astype(float)), {0.0, 4.0, 8.0, 9.0, 10.0}
        )
        self.assertLessEqual(
            float(self.calibration["abs_panel_minus_full"].max()), 1.0e-6
        )

    def test_boundary_endpoint_values(self) -> None:
        expected = {
            (40.0, 10.0): {
                "C_NN": -0.3452846751419901,
                "anchored": -1.7804958019128034,
                "direct": -1.7779951506626208,
                "observed": -1.7767186641372603,
            },
            (80.0, 20.0): {
                "C_NN": -0.3494588373529676,
                "anchored": -1.7980709458743802,
                "direct": -1.7974745743138492,
                "observed": -1.7970513860920925,
            },
        }
        for (U, V), values in expected.items():
            row = self.pointwise[
                self.pointwise["U"].eq(U) & self.pointwise["V"].eq(V)
            ].iloc[0]
            self.assertAlmostEqual(row["C_NN"], values["C_NN"], places=13)
            self.assertAlmostEqual(
                row["s_eq10_axis_anchored_C_NN_drift"],
                values["anchored"],
                places=13,
            )
            self.assertAlmostEqual(
                row["s_eq10_direct_fullobs_C_NN"], values["direct"], places=13
            )
            self.assertAlmostEqual(
                row["s_signed_observed"], values["observed"], places=13
            )

    def test_prediction_lines_reach_boundary(self) -> None:
        for U in (20.0, 40.0, 80.0):
            family = self.pointwise[self.pointwise["U"].eq(U)]
            self.assertTrue(np.isclose(family["r"].max(), 0.25))
        self.assertEqual(len(self.metrics), 12)


if __name__ == "__main__":
    unittest.main()
