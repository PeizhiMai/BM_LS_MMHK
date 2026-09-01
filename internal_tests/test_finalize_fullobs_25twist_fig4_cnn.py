"""Focused provenance-gate tests for the add-only fullobs finalizer."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
FINALIZER_PATH = (
    REPO / "scripts" / "cades_queue" / "finalize_fullobs_25twist_fig4_cnn.py"
)
EXPECTED_MANIFEST_SHA256 = (
    "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
)


def load_finalizer():
    spec = importlib.util.spec_from_file_location("fullobs_finalizer_under_test", FINALIZER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load finalizer at {FINALIZER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_minimal_snapshot_staging(finalizer, root: Path, name: str) -> Path:
    staging = root / name
    staging.mkdir(mode=0o700)
    executable = staging / "metadata/tools/monitor.py"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/usr/bin/env python3\n")
    executable.chmod(0o755)
    provenance = staging / "metadata/provenance.json"
    provenance.write_text('{"schema_version": 1}\n')
    raw = staging / "raw/result_00001.dat"
    raw.parent.mkdir()
    raw.write_text("status COMPLETE\n<C1_NN> -0.35\n")
    finalizer.write_snapshot_hashes(
        staging, staging / "metadata/snapshot_file_sha256.tsv"
    )
    return staging


class ManifestProvenanceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finalizer = load_finalizer()

    def test_expected_manifest_hash_is_campaign_specific(self) -> None:
        self.assertEqual(
            self.finalizer.EXPECTED_MANIFEST_SHA256,
            EXPECTED_MANIFEST_SHA256,
        )
        self.finalizer.require_manifest_hash(
            EXPECTED_MANIFEST_SHA256,
            "test inventory",
        )

    def test_wrong_manifest_hash_is_refused(self) -> None:
        wrong_hash = "0" * 64
        with self.assertRaises(self.finalizer.Refusal) as raised:
            self.finalizer.require_manifest_hash(wrong_hash, "test inventory")
        message = str(raised.exception)
        self.assertIn("test inventory manifest SHA-256 mismatch", message)
        self.assertIn(wrong_hash, message)
        self.assertIn(EXPECTED_MANIFEST_SHA256, message)

    def test_remote_inventory_refuses_wrong_manifest_hash(self) -> None:
        inventory = {
            "target_count": 300,
            "submission_count": 300,
            "results": [{} for _ in range(300)],
            "manifest_sha256": "f" * 64,
        }
        with mock.patch.object(
            self.finalizer,
            "remote_python",
            return_value=json.dumps(inventory),
        ):
            with self.assertRaises(self.finalizer.Refusal) as raised:
                self.finalizer.remote_inventory("unused-test-host")
        self.assertIn("remote inventory manifest SHA-256 mismatch", str(raised.exception))

    def test_real_filesystem_install_renames_0700_then_freezes_root(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn25_snapshot_install_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(
                self.finalizer, root, ".snapshot.staging"
            )
            destination = root / "snapshot"
            observed_source_modes: list[int] = []
            real_rename = self.finalizer._rename_directory_no_replace

            def checked_rename(source: Path, target: Path) -> None:
                observed_source_modes.append(stat.S_IMODE(source.stat().st_mode))
                real_rename(source, target)

            with mock.patch.object(
                self.finalizer,
                "_rename_directory_no_replace",
                side_effect=checked_rename,
            ):
                self.finalizer.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertEqual(observed_source_modes, [0o700])
            self.assertFalse(os.path.lexists(staging))
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o555)
            self.assertEqual(
                stat.S_IMODE(
                    (destination / "metadata/tools/monitor.py").stat().st_mode
                ),
                0o555,
            )
            self.assertEqual(
                stat.S_IMODE(
                    (destination / "metadata/provenance.json").stat().st_mode
                ),
                0o444,
            )
            for path in destination.rglob("*"):
                if path.is_dir():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o555)
            identity = self.finalizer._directory_identity(destination)
            self.finalizer._remove_owned_snapshot_tree(destination, identity)

    def test_post_install_verification_failure_removes_owned_release(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn25_snapshot_rollback_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(
                self.finalizer, root, ".snapshot.staging"
            )
            destination = root / "snapshot"
            real_verify = self.finalizer._verify_snapshot_install_contract

            def fail_installed_verification(
                path: Path, contract: dict, *, root_mode: int
            ) -> None:
                real_verify(path, contract, root_mode=root_mode)
                if root_mode == 0o555:
                    raise self.finalizer.Refusal("synthetic post-install failure")

            with mock.patch.object(
                self.finalizer,
                "_verify_snapshot_install_contract",
                side_effect=fail_installed_verification,
            ), self.assertRaises(self.finalizer.Refusal):
                self.finalizer.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertFalse(os.path.lexists(staging))
            self.assertFalse(os.path.lexists(destination))

    def test_existing_destination_is_untouched_and_owned_stage_removed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="f4cnn25_snapshot_no_replace_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(
                self.finalizer, root, ".snapshot.staging"
            )
            destination = root / "snapshot"
            destination.mkdir()
            marker = destination / "preexisting.txt"
            marker.write_text("do not replace\n")
            with self.assertRaises(self.finalizer.Refusal):
                self.finalizer.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertFalse(os.path.lexists(staging))
            self.assertEqual(marker.read_text(), "do not replace\n")


if __name__ == "__main__":
    unittest.main()
