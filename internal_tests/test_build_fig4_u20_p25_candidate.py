#!/usr/bin/env python3
"""Focused tests for the confined U=20 P25 Fig. 4 candidate builder."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_fig4_u20_p25_candidate as builder  # noqa: E402


def synthetic_output(V: float, kx: int, ky: int) -> str:
    phase = 0.17 * kx + 0.11 * ky
    C_NN = -0.331 + 8.0e-5 * math.sin(phase)
    D_site = 0.019 + 2.0e-5 * math.cos(phase)
    nn = 0.991 + 3.0e-5 * math.sin(phase)
    kinetic_nn = -0.515 + 2.0e-5 * math.cos(phase)
    kinetic_nnn = 0.0
    kinetic = kinetic_nn + kinetic_nnn
    E0 = 16.0 * (kinetic + 20.0 * D_site + 2.0 * V * nn)
    Sc = 0.048
    mcdw = Sc / 16.0
    return f"""Lx\t4
Ly\t4
tp\t0.000000000000000000e+00
U\t2.000000000000000000e+01
V\t{V:.18e}
E0\t{E0:.18e}
Gap\t0.000000000000000000e+00

<nn_NN> {nn:.18e}
<delta_n_delta_n_NN> {nn - 1.0:.18e}
<Kinetic_NN_per_site> {kinetic_nn:.18e}
<Kinetic_NNN_per_site> {kinetic_nnn:.18e}
<Kinetic_per_site> {kinetic:.18e}
<C1_NN> {C_NN:.18e}
Q\t0,0
<nq> 5.000000000000000000e-01
<nq_upnq_dn> 1.000000000000000000e-01
<ni_upni_dn> {D_site:.18e}
<Spipi> 1.200000000000000000e+00
<Sc_pipi> {Sc:.18e}
<mCDW2_pipi> {mcdw:.18e}
status\tCOMPLETE
"""


def write_raw_ledger(root: Path) -> None:
    manifest_path = root / "metadata" / "manifest.tsv"
    with manifest_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    fields = (
        "index",
        "U",
        "V",
        "kx",
        "ky",
        "filename",
        "size_bytes",
        "mtime_ns",
        "sha256",
    )
    with (root / "metadata" / "remote_results_sha256.tsv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            path = root / "raw" / Path(row["result"]).name
            writer.writerow(
                {
                    "index": row["index"],
                    "U": row["U"],
                    "V": row["V"],
                    "kx": row["kx"],
                    "ky": row["ky"],
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "mtime_ns": 0,
                    "sha256": builder.sha256(path),
                }
            )


def write_snapshot_ledger(root: Path) -> None:
    ledger = root / "metadata" / "snapshot_file_sha256.tsv"
    if ledger.exists():
        ledger.unlink()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    with ledger.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sha256", "size_bytes", "relative_path"])
        for path in files:
            writer.writerow(
                [
                    builder.sha256(path),
                    path.stat().st_size,
                    path.relative_to(root).as_posix(),
                ]
            )


def make_v5_snapshot(parent: Path) -> tuple[Path, builder.SourceContract]:
    root = parent / "fullobs_25twist_u20v5_fig4_cnn_20260821"
    metadata = root / "metadata"
    raw = root / "raw"
    metadata.mkdir(parents=True)
    raw.mkdir()
    shutil.copy2(
        builder.DEFAULT_U20_SOURCE / "metadata" / "twist_panel.tsv",
        metadata / "twist_panel.tsv",
    )

    manifest_rows: list[dict[str, object]] = []
    for index, (kx, ky) in enumerate(builder.TWISTS, 1):
        name = builder._expected_raw_name(5.0, kx, ky)
        result = f"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/{name}"
        manifest_rows.append(
            {
                "index": index,
                "U": 20,
                "V": 5,
                "V_over_U": 0.25,
                "expected_phase": "Mott",
                "twist_index": index,
                "kx": kx,
                "ky": ky,
                "seed": 1_000_000 + index,
                "job_name": "F4C20V5",
                "result": result,
                "state_at_generation": "template",
                "template": f"/remote/job_{index:04d}.sh",
            }
        )
        (raw / name).write_text(synthetic_output(5.0, kx, ky))
    manifest = metadata / "manifest.tsv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, delimiter="\t", fieldnames=builder.MANIFEST_FIELDS
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    provenance = {
        "aggregation": {
            "diagnostic_estimator": "exchange-symmetry-multiplicity-weighted panel mean",
            "primary_C_NN_estimator": (
                "unweighted arithmetic mean over deterministic 25-twist maximin panel"
            ),
            "twist_spread_is_not_standard_error": True,
        },
        "batch": "/remote/fullobs_25twist_u20v5_fig4_cnn_20260821",
        "created_at": "2026-08-21T00:00:00-04:00",
        "job_name": "F4C20V5",
        "solver_sha256": builder.PIN_SHA256["Hubbard_sym_testobs_UV.x"],
        "source_sha256": builder.PIN_SHA256["Hubbard_sym_testobs_UV.cc"],
        "qbasis_library_sha256": builder.PIN_SHA256["libqbasis.so"],
        "physics": {
            "Lx": 4,
            "Ly": 4,
            "Ndn": 8,
            "Nup": 8,
            "Qm": 0,
            "Qn": 0,
            "tp": 0,
        },
        "pairs": [{"U": 20, "V": "5", "V_over_U": 0.25}],
        "twists": [{"kx": kx, "ky": ky} for kx, ky in builder.TWISTS],
        "target_count": 25,
    }
    provenance_path = metadata / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    write_raw_ledger(root)
    write_snapshot_ledger(root)

    contract = replace(
        builder.SOURCE_CONTRACTS["u20v5"],
        manifest_sha256=builder.sha256(manifest),
        provenance_sha256=builder.sha256(provenance_path),
        require_pin_artifacts=False,
    )
    return root, contract


class U20P25CandidateBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fig4_u20_p25_test_")
        self.work = Path(self.temp.name)
        self.v5, self.v5_contract = make_v5_snapshot(self.work)
        self.outputs: list[Path] = []

    def tearDown(self) -> None:
        for output in self.outputs:
            shutil.rmtree(output, ignore_errors=True)
        self.temp.cleanup()

    def new_output(self, suffix: str) -> Path:
        output = builder.STAGING_ROOT / (
            f"fig4_u20_p25_test_{suffix}_{uuid.uuid4().hex}"
        )
        self.outputs.append(output)
        return output

    def patched_v5(self):
        return mock.patch.dict(builder.SOURCE_CONTRACTS, {"u20v5": self.v5_contract})

    def test_reviewed_existing_u20_source_is_exact_125(self) -> None:
        source = builder.validate_source(
            builder.DEFAULT_U20_SOURCE, builder.SOURCE_CONTRACTS["u20"]
        )
        self.assertEqual(len(source.rows), 125)
        self.assertEqual(
            source.rows.groupby("V").size().to_dict(),
            {
                0.0: 25,
                2.0: 25,
                3.0: 25,
                4.0: 25,
                4.5: 25,
            },
        )
        self.assertEqual(
            source.raw_digest_sha256,
            "a9c0c155c1b3cf9f073a58a9d30efae71e65ec67c11b82a1d5920af285191e7d",
        )
        self.assertLessEqual(
            float(source.rows["max_abs_identity_residual"].max()),
            builder.IDENTITY_TOLERANCE,
        )

    def test_end_to_end_exact_150_six_formula_and_no_active_changes(self) -> None:
        output = self.new_output("success")
        active_before = builder._active_artifact_state()
        with self.patched_v5():
            paths = builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
            )
        self.assertEqual(builder._active_artifact_state(), active_before)
        self.assertEqual(
            {path.name for path in output.iterdir()}, builder.OUTPUT_BASENAMES
        )
        raw = pd.read_csv(paths["raw_validation"])
        summary = pd.read_csv(paths["case_summary"])
        provenance = json.loads(paths["provenance"].read_text())
        self.assertEqual(len(raw), 150)
        self.assertEqual(raw["status"].value_counts().to_dict(), {"COMPLETE": 150})
        self.assertEqual(len(summary), 6)
        self.assertEqual(summary["complete_twists"].tolist(), [25] * 6)
        self.assertEqual(summary["V"].tolist(), list(builder.ALL_CASES))
        self.assertEqual(summary["analytic_phase"].tolist(), ["Mott"] * 6)
        v5 = summary[summary["V"].eq(5.0)].iloc[0]
        self.assertEqual(v5["legacy_source_branch"], "boundary")
        self.assertIn("5 < reviewed V_Mott=5.02", v5["analytic_phase_basis"])

        C0 = float(summary.iloc[0]["C_NN_P25_mean"])
        anchor_C = float(summary.iloc[0]["s_observed_U20_V0_signed"]) / 4.0
        for row in summary.itertuples(index=False):
            expected_C = anchor_C + float(row.C_NN_P25_mean) - C0
            expected_s = builder.eq10_signed(20.0, float(row.V), expected_C)
            self.assertAlmostEqual(
                float(row.C_NN_effective_axis_anchored_drift), expected_C, places=14
            )
            self.assertAlmostEqual(
                float(row.s_eq10_axis_anchored_measured_C_drift), expected_s, places=13
            )
        self.assertTrue(provenance["watermark_applied"])
        self.assertFalse(provenance["publication_candidate"])
        self.assertFalse(provenance["promotion_supported"])
        self.assertFalse(provenance["publication_artifacts_modified"])
        self.assertGreater(paths["figure_pdf"].stat().st_size, 10_000)
        self.assertGreater(paths["figure_png"].stat().st_size, 10_000)

    def test_missing_v5_refuses_without_creating_output(self) -> None:
        with (self.v5 / "metadata" / "manifest.tsv").open(newline="") as handle:
            first = next(csv.DictReader(handle, delimiter="\t"))
        (self.v5 / "raw" / Path(first["result"]).name).unlink()
        output = self.new_output("missing_v5")
        with self.patched_v5(), self.assertRaises(builder.CandidateBuildError):
            builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
            )
        self.assertFalse(output.exists())

    def test_four_identity_violation_refused_after_hash_ledgers_refresh(self) -> None:
        raw_path = sorted((self.v5 / "raw").iterdir())[0]
        text = raw_path.read_text()
        raw_path.write_text(
            text.replace(
                "<mCDW2_pipi> 3.000000000000000062e-03",
                "<mCDW2_pipi> 1.230000000000000000e-01",
            )
        )
        write_raw_ledger(self.v5)
        write_snapshot_ledger(self.v5)
        output = self.new_output("bad_identity")
        with (
            self.patched_v5(),
            self.assertRaisesRegex(
                builder.CandidateBuildError, "Four-identity tolerance exceeded"
            ),
        ):
            builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
            )
        self.assertFalse(output.exists())

    def test_v5_manifest_must_declare_mott_even_though_gz_branch_is_boundary(
        self,
    ) -> None:
        manifest = self.v5 / "metadata" / "manifest.tsv"
        with manifest.open(newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        rows[0]["expected_phase"] = "charge"
        with manifest.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle, delimiter="\t", fieldnames=builder.MANIFEST_FIELDS
            )
            writer.writeheader()
            writer.writerows(rows)
        write_snapshot_ledger(self.v5)
        contract = replace(self.v5_contract, manifest_sha256=builder.sha256(manifest))
        output = self.new_output("bad_phase")
        with (
            mock.patch.dict(builder.SOURCE_CONTRACTS, {"u20v5": contract}),
            self.assertRaisesRegex(
                builder.CandidateBuildError, "physics/order/phase/name contract"
            ),
        ):
            builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
            )
        self.assertFalse(output.exists())

    def test_v5_manifest_byte_drift_is_refused_before_output(self) -> None:
        manifest = self.v5 / "metadata" / "manifest.tsv"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        write_snapshot_ledger(self.v5)
        output = self.new_output("manifest_hash")
        with (
            self.patched_v5(),
            self.assertRaisesRegex(
                builder.CandidateBuildError, "manifest SHA-256 mismatch"
            ),
        ):
            builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
            )
        self.assertFalse(output.exists())

    def test_output_confinement_and_no_overwrite_apply_in_both_modes(self) -> None:
        outside = self.work / "fig4_u20_p25_escape"
        with self.assertRaises(builder.CandidateBuildError):
            builder.validate_output_directory(outside)
        nested = builder.STAGING_ROOT / "nested" / "fig4_u20_p25_escape"
        with self.assertRaises(builder.CandidateBuildError):
            builder.validate_output_directory(nested)
        existing = self.new_output("existing")
        existing.mkdir()
        with self.assertRaises(builder.CandidateBuildError):
            builder.validate_output_directory(existing)
        marker = existing / "keep.txt"
        marker.write_text("untouched\n")
        with self.patched_v5(), self.assertRaises(builder.CandidateBuildError):
            builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=existing,
                publication_candidate=True,
            )
        self.assertEqual(marker.read_text(), "untouched\n")

    def test_publication_candidate_only_removes_watermark_and_stays_in_tmp(
        self,
    ) -> None:
        output = self.new_output("publication_candidate")
        active_before = builder._active_artifact_state()
        with self.patched_v5():
            paths = builder.build_candidate(
                u20_source=builder.DEFAULT_U20_SOURCE,
                u20v5_source=self.v5,
                output_dir=output,
                publication_candidate=True,
            )
        provenance = json.loads(paths["provenance"].read_text())
        self.assertTrue(provenance["publication_candidate"])
        self.assertFalse(provenance["watermark_applied"])
        self.assertFalse(provenance["promotion_supported"])
        self.assertEqual(output.parent.resolve(), builder.STAGING_ROOT.resolve())
        self.assertEqual(builder._active_artifact_state(), active_before)

    def test_pin_artifacts_must_match_the_declared_reviewed_hashes(self) -> None:
        metadata = self.work / "pin_fixture"
        pinned = metadata / "pinned_solver"
        pinned.mkdir(parents=True)
        contents = {
            "Hubbard_sym_testobs_UV.x": b"solver fixture\n",
            "Hubbard_sym_testobs_UV.cc": b"source fixture\n",
            "libqbasis.so": b"library fixture\n",
        }
        pins = {}
        for name, payload in contents.items():
            path = pinned / name
            path.write_bytes(payload)
            pins[name] = hashlib.sha256(payload).hexdigest()
        (metadata / "PINNED_SHA256SUMS").write_text(
            "".join(f"{pins[name]}  pinned_solver/{name}\n" for name in contents)
        )
        contract = replace(
            self.v5_contract,
            pin_sha256=tuple(pins.items()),
            require_pin_artifacts=True,
        )
        builder._validate_pin_artifacts(metadata, contract)
        (pinned / "libqbasis.so").write_bytes(b"tampered\n")
        with self.assertRaisesRegex(builder.CandidateBuildError, "hash mismatch"):
            builder._validate_pin_artifacts(metadata, contract)

    def test_campaign_specific_hash_pins_are_not_placeholders(self) -> None:
        self.assertEqual(
            builder.SOURCE_CONTRACTS["u20"].manifest_sha256,
            "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5",
        )
        self.assertEqual(
            builder.SOURCE_CONTRACTS["u20v5"].manifest_sha256,
            "05d8ee7c0aef76beb1b86b82b4780a9e85fcce9df0c4b8da023d3b84f545943e",
        )
        self.assertEqual(
            builder.TWIST_PANEL_SHA256,
            builder.sha256(builder.DEFAULT_U20_SOURCE / "metadata" / "twist_panel.tsv"),
        )


if __name__ == "__main__":
    unittest.main()
