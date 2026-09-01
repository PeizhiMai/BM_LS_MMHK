from __future__ import annotations

import csv
import importlib
import importlib.util
import json
import math
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
GENERATOR_PATH = (
    REPO / "scripts/cades_queue/fullobs_861expand_fig4_cnn_20260821/generate_batch.py"
)
FINALIZER_PATH = REPO / "scripts/cades_queue/finalize_fullobs_861expand_fig4_cnn.py"
SCRIPTS = REPO / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module("f4cnn861x_generator_finalizer_test", GENERATOR_PATH)
FINALIZER = load_module("f4cnn861x_finalizer_test", FINALIZER_PATH)
sys.path.insert(0, str(SCRIPTS))
LOADER = importlib.import_module("fig4_cnn_prediction_input")


def make_minimal_snapshot_staging(root: Path, name: str) -> Path:
    staging = root / name
    staging.mkdir(mode=0o700)
    for relative in FINALIZER.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS:
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env python3\n")
        path.chmod(0o755)
    raw = staging / "raw/result_00001.dat"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("status COMPLETE\n<C1_NN> -0.35\n")
    provenance = staging / "metadata/snapshot_provenance.json"
    provenance.write_text('{"schema_version": 1}\n')
    FINALIZER.CORE.write_snapshot_hashes(
        staging, staging / "metadata/snapshot_file_sha256.tsv"
    )
    return staging


class FinalizerContractTests(unittest.TestCase):
    def test_manifest_and_support_tool_hash_contracts(self) -> None:
        source = GENERATOR.load_source_manifest(
            GENERATOR.PACKAGE / "reviewed_inputs/source_25_manifest.tsv"
        )
        _, complement = GENERATOR.load_coordinate_contracts()
        plan = GENERATOR.build_plan(GENERATOR.BASE_DEFAULT, source, complement)
        for row in plan:
            row["template"] = str(
                GENERATOR.BATCH_DEFAULT
                / "templates"
                / (
                    f"{GENERATOR.TEMPLATE_PREFIX}{row['index']:05d}_U{row['U']}_"
                    f"V{GENERATOR.decimal_tag(row['V'])}_f{row['kx']}x{row['ky']}.sh"
                )
            )
        with tempfile.TemporaryDirectory(
            prefix="f4cnn861x_manifest_hash_"
        ) as temporary:
            path = Path(temporary) / "manifest.tsv"
            GENERATOR.write_tsv(path, plan, list(plan[0]))
            self.assertEqual(GENERATOR.sha256(path), FINALIZER.EXPECTED_MANIFEST_SHA256)
        self.assertEqual(GENERATOR.plan_digest(plan), FINALIZER.EXPECTED_PLAN_SHA256)
        self.assertEqual(
            FINALIZER.sha256(FINALIZER.MONITOR), FINALIZER.EXPECTED_MONITOR_SHA256
        )
        self.assertEqual(
            FINALIZER.sha256(FINALIZER.CORE_PATH),
            FINALIZER.EXPECTED_CORE_FINALIZER_SHA256,
        )
        self.assertEqual(
            FINALIZER.sha256(FINALIZER_PATH), LOADER.REVIEWED_FINALIZER_SHA256
        )
        self.assertEqual(
            FINALIZER.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS,
            LOADER.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS,
        )

    def test_real_filesystem_install_renames_0700_then_freezes_root(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn861x_snapshot_install_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(root, ".snapshot.staging")
            destination = root / "snapshot"
            observed_source_modes: list[int] = []
            real_rename = FINALIZER._rename_directory_no_replace

            def checked_rename(source: Path, target: Path) -> None:
                observed_source_modes.append(stat.S_IMODE(source.stat().st_mode))
                real_rename(source, target)

            with mock.patch.object(
                FINALIZER,
                "_rename_directory_no_replace",
                side_effect=checked_rename,
            ):
                FINALIZER.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertEqual(observed_source_modes, [0o700])
            self.assertFalse(os.path.lexists(staging))
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o555)
            for path in destination.rglob("*"):
                relative = path.relative_to(destination).as_posix()
                expected_mode = (
                    0o555
                    if path.is_dir()
                    or relative in FINALIZER.SNAPSHOT_EXECUTABLE_RELATIVE_PATHS
                    else 0o444
                )
                self.assertEqual(
                    stat.S_IMODE(path.stat().st_mode),
                    expected_mode,
                    relative,
                )
            identity = FINALIZER._directory_identity(destination)
            FINALIZER._remove_owned_snapshot_tree(destination, identity)

    def test_post_install_verification_failure_removes_owned_release(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn861x_snapshot_rollback_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(root, ".snapshot.staging")
            destination = root / "snapshot"
            real_verify = FINALIZER._verify_snapshot_install_contract

            def fail_installed_verification(
                path: Path, contract: dict, *, root_mode: int
            ) -> None:
                real_verify(path, contract, root_mode=root_mode)
                if root_mode == 0o555:
                    raise FINALIZER.Refusal("synthetic post-install failure")

            with mock.patch.object(
                FINALIZER,
                "_verify_snapshot_install_contract",
                side_effect=fail_installed_verification,
            ), self.assertRaises(FINALIZER.Refusal):
                FINALIZER.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertFalse(os.path.lexists(staging))
            self.assertFalse(os.path.lexists(destination))

    def test_existing_destination_is_untouched_and_owned_stage_removed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn861x_snapshot_no_replace_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(root, ".snapshot.staging")
            destination = root / "snapshot"
            destination.mkdir()
            marker = destination / "preexisting.txt"
            marker.write_text("do not replace\n")
            with self.assertRaises(FINALIZER.Refusal):
                FINALIZER.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertFalse(os.path.lexists(staging))
            self.assertEqual(marker.read_text(), "do not replace\n")

    def test_completion_gate_is_exact(self) -> None:
        report = {
            "total_targets": FINALIZER.EXPECTED_EXPANSION,
            "counts": {"COMPLETE": FINALIZER.EXPECTED_EXPANSION},
            "batch_active_queue_counts": {},
            "scheduler_errors": [],
            "warnings": [],
            "repair_candidates": [],
            "anomalies": {"unmapped_active_matching_jobs": []},
            "pin_audit": [{"match": True}] * 3,
        }
        FINALIZER.gate_report(report, combined=False, label="test")
        report["counts"] = {
            "COMPLETE": FINALIZER.EXPECTED_EXPANSION - 1,
            "PENDING": 1,
        }
        with self.assertRaises(FINALIZER.Refusal):
            FINALIZER.gate_report(report, combined=False, label="test")

    def test_remote_inventory_program_requires_combined_wedges(self) -> None:
        self.assertIn("need(len(exp)==10032", FINALIZER.REMOTE_INVENTORY_PROGRAM)
        self.assertIn("need(len(reused)==300", FINALIZER.REMOTE_INVENTORY_PROGRAM)
        self.assertIn("set(counts.values())=={861}", FINALIZER.REMOTE_INVENTORY_PROGRAM)
        self.assertIn(
            FINALIZER.EXPECTED_MANIFEST_SHA256,
            FINALIZER.REMOTE_INVENTORY_PROGRAM,
        )

    def test_remote_quiescence_requires_no_claims_or_exact_name_activity(self) -> None:
        clean = {"claims": [], "exact_name_activity": []}
        with mock.patch.object(
            FINALIZER.CORE, "remote_python", return_value=json.dumps(clean)
        ) as remote_python:
            self.assertEqual(
                FINALIZER.remote_quiescence("test-host", label="test"), clean
            )
        arguments = remote_python.call_args.args[2]
        self.assertEqual(arguments[0], str(FINALIZER.REMOTE_BATCH))
        self.assertEqual(tuple(arguments[1:]), FINALIZER.EXPECTED_JOB_NAMES)
        self.assertIn('glob("*.claim")', FINALIZER.REMOTE_QUIESCENCE_PROGRAM)

        for payload in (
            {"claims": ["job.claim"], "exact_name_activity": []},
            {
                "claims": [],
                "exact_name_activity": [
                    {"job_id": "1", "job_name": "F4CNN861X", "state": "RUNNING"}
                ],
            },
        ):
            with self.subTest(payload=payload), mock.patch.object(
                FINALIZER.CORE, "remote_python", return_value=json.dumps(payload)
            ), self.assertRaises(FINALIZER.Refusal):
                FINALIZER.remote_quiescence("test-host", label="test")


class Full861LocalAnalysisTests(unittest.TestCase):
    def test_independent_local_summary_matches_remote_fixture(self) -> None:
        pairs = (
            (20, 0.0),
            (20, 2.0),
            (20, 3.0),
            (20, 4.0),
            (20, 4.5),
            (40, 6.0),
            (80, 0.0),
            (80, 4.0),
            (80, 8.0),
            (80, 12.0),
            (80, 16.0),
            (80, 18.0),
        )
        with tempfile.TemporaryDirectory(
            prefix="f4cnn861x_local_analysis_"
        ) as temporary:
            root = Path(temporary)
            metadata = root / "metadata"
            raw = root / "raw"
            (metadata / "analysis").mkdir(parents=True)
            raw.mkdir()
            manifest_rows = []
            expected_rows = []
            index = 0
            for U, V in pairs:
                weighted = []
                for ky in range(41):
                    for kx in range(ky + 1):
                        index += 1
                        value = -0.34 + 1.0e-6 * (kx + 2 * ky) + 2.0e-5 * V / U
                        filename = f"result_{index:05d}.dat"
                        (raw / filename).write_text(f"<C1_NN> {value:.18e}\n")
                        manifest_rows.append(
                            {
                                "index": index,
                                "source_campaign": "synthetic",
                                "U": U,
                                "V": V,
                                "expected_phase": "Mott",
                                "kx": kx,
                                "ky": ky,
                                "seed": index,
                                "job_name": "",
                                "result": str((raw / filename).resolve()),
                                "remote_result": f"/remote/{filename}",
                                "snapshot_result": f"../raw/{filename}",
                                "template": "",
                            }
                        )
                        weight = (
                            (1 if kx == ky else 2)
                            * (0.5 if kx in (0, 40) else 1.0)
                            * (0.5 if ky in (0, 40) else 1.0)
                        )
                        weighted.append((weight, value))
                total = sum(weight for weight, _ in weighted)
                mean = sum(weight * value for weight, value in weighted) / total
                spread = math.sqrt(
                    sum(weight * (value - mean) ** 2 for weight, value in weighted)
                    / total
                )
                factor = (2 * U - V) / (U - V)
                expected_rows.append(
                    {
                        "U": U,
                        "V": V,
                        "C_NN_full_861": mean,
                        "C_NN_full_quadrature_weighted_population_std": spread,
                        "s_eq10_signed": 1 + factor * (2 * mean - 0.5),
                    }
                )
            with (metadata / "manifest_local.tsv").open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle, delimiter="\t", fieldnames=list(manifest_rows[0])
                )
                writer.writeheader()
                writer.writerows(manifest_rows)
            with (metadata / "analysis/fig4_cnn_full861_summary.csv").open(
                "w", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=list(expected_rows[0]))
                writer.writeheader()
                writer.writerows(expected_rows)

            output = root / "local_analysis"
            FINALIZER.generate_analysis(metadata, raw, output)
            with (output / "fig4_cnn_full861_summary.csv").open(newline="") as handle:
                observed = list(csv.DictReader(handle))
            with (output / "fig4_cnn_full861_raw_validation.csv").open() as handle:
                raw_row_count = sum(1 for _ in handle) - 1
            self.assertEqual(len(observed), 12)
            self.assertEqual(raw_row_count, FINALIZER.EXPECTED_COMBINED)
            self.assertTrue(
                all(
                    row["twist_spread_is_standard_error"] == "False" for row in observed
                )
            )


if __name__ == "__main__":
    unittest.main()
