#!/usr/bin/env python3
"""Tests for the immutable all-F861 analysis-release freeze step."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_fig4_cnn_full861_release as freezer  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Full861ReleaseFreezeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fig4_full861_freeze_test_")
        self.work = Path(self.temp.name)
        self.tmp = self.work / "tmp"
        self.results = self.work / "results"
        self.tmp.mkdir()
        self.results.mkdir()
        self.candidate = (
            self.tmp / f"{freezer.CANDIDATE_PREFIX}synthetic-contract-test"
        )
        self.candidate.mkdir()
        for index, basename in enumerate(freezer.ANALYZER_OUTPUT_BASENAMES):
            (self.candidate / basename).write_text(f"synthetic analyzer output {index}\n")
        output_hashes = {
            basename: sha256(self.candidate / basename)
            for basename in freezer.ANALYZER_OUTPUT_BASENAMES
        }
        self.provenance = {
            "analyzer_sha256": "a" * 64,
            "snapshot_root": "/immutable/synthetic/snapshot",
            "decision_certificate_sha256": "b" * 64,
            "decision_gate_algorithm": freezer.DECISION_GATE_ALGORITHM,
            "output_files": output_hashes,
        }
        (self.candidate / freezer.PROVENANCE_BASENAME).write_text(
            json.dumps(self.provenance, indent=2, sort_keys=True) + "\n"
        )

    def tearDown(self) -> None:
        for path in self.work.rglob("*"):
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.temp.cleanup()

    def patch_roots_and_loader(self):
        return (
            mock.patch.object(freezer, "TMP_ROOT", self.tmp),
            mock.patch.object(freezer, "RESULTS_ROOT", self.results),
            mock.patch.object(
                freezer,
                "load_validated_fullobs_eq10_bundle",
                return_value=SimpleNamespace(provenance=self.provenance),
            ),
        )

    def freeze_release(self, suffix: str) -> Path:
        release = self.results / f"{freezer.RELEASE_PREFIX}{suffix}"
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with root_patch, results_patch, loader_patch:
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        return release

    @staticmethod
    def rewrite_manifest(release: Path, payload: dict[str, object]) -> None:
        path = release / freezer.RELEASE_MANIFEST_BASENAME
        path.chmod(0o600)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        path.chmod(0o444)

    def test_exact_bundle_is_hash_verified_and_atomically_frozen(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}20260821_testhash"
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with root_patch, results_patch, loader_patch as loader:
            installed = freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        self.assertEqual(installed, release.resolve())
        loader.assert_called_once_with(
            self.candidate.resolve(),
            allow_fixture=False,
            scale_points_path=self.work / "scale.csv",
        )
        self.assertEqual(
            {path.name for path in release.iterdir()},
            {*freezer.ANALYSIS_BASENAMES, freezer.RELEASE_MANIFEST_BASENAME},
        )
        self.assertEqual(stat.S_IMODE(release.stat().st_mode), 0o555)
        for basename in freezer.ANALYSIS_BASENAMES:
            self.assertEqual(
                (release / basename).read_bytes(),
                (self.candidate / basename).read_bytes(),
            )
            self.assertEqual(
                stat.S_IMODE((release / basename).stat().st_mode),
                0o444,
            )
        self.assertEqual(
            stat.S_IMODE(
                (release / freezer.RELEASE_MANIFEST_BASENAME).stat().st_mode
            ),
            0o444,
        )
        manifest = json.loads(
            (release / freezer.RELEASE_MANIFEST_BASENAME).read_text()
        )
        self.assertEqual(manifest["row_count"], 16)
        self.assertTrue(manifest["immutable_no_overwrite"])
        self.assertEqual(
            manifest["decision_certificate_sha256"],
            self.provenance["decision_certificate_sha256"],
        )
        self.assertEqual(
            manifest["analysis_files_sha256"],
            {
                basename: sha256(self.candidate / basename)
                for basename in freezer.ANALYSIS_BASENAMES
            },
        )
        self.assertFalse(
            list(self.results.glob(f".{release.name}.freeze-*")),
            "Atomic freeze must not leave a hidden staging directory",
        )

    def test_exported_validator_accepts_exact_frozen_release(self) -> None:
        release = self.freeze_release("validator_accepts")
        expected = json.loads(
            (release / freezer.RELEASE_MANIFEST_BASENAME).read_text()
        )

        validated = freezer.validate_frozen_full861_release(
            release,
            results_root=self.results,
        )

        self.assertEqual(validated, expected)

    def test_exported_validator_rejects_wrong_direct_child_path(self) -> None:
        nested = self.results / "nested" / f"{freezer.RELEASE_PREFIX}not_direct"
        nested.mkdir(parents=True)
        nested.chmod(0o555)

        with self.assertRaisesRegex(freezer.FreezeRefusal, "direct child"):
            freezer.validate_frozen_full861_release(
                nested,
                results_root=self.results,
            )

    def test_exported_validator_rejects_inventory_and_mode_changes(self) -> None:
        release = self.freeze_release("validator_inventory_modes")

        release.chmod(0o755)
        unexpected = release / "unexpected.txt"
        unexpected.write_text("not part of the frozen release\n")
        unexpected.chmod(0o444)
        release.chmod(0o555)
        with self.assertRaisesRegex(freezer.FreezeRefusal, "exact seven-file"):
            freezer.validate_frozen_full861_release(
                release,
                results_root=self.results,
            )
        release.chmod(0o755)
        unexpected.unlink()
        release.chmod(0o555)

        release.chmod(0o755)
        with self.assertRaisesRegex(freezer.FreezeRefusal, "mode must be exactly 0555"):
            freezer.validate_frozen_full861_release(
                release,
                results_root=self.results,
            )
        release.chmod(0o555)

        analysis_file = release / freezer.ANALYSIS_BASENAMES[0]
        analysis_file.chmod(0o644)
        with self.assertRaisesRegex(freezer.FreezeRefusal, "writable file"):
            freezer.validate_frozen_full861_release(
                release,
                results_root=self.results,
            )
        analysis_file.chmod(0o444)

    def test_exported_validator_rejects_manifest_schema_and_products(self) -> None:
        release = self.freeze_release("validator_manifest_contract")
        manifest_path = release / freezer.RELEASE_MANIFEST_BASENAME
        original = json.loads(manifest_path.read_text())

        tampered = dict(original)
        tampered["unexpected_key"] = "not in the exact schema"
        self.rewrite_manifest(release, tampered)
        with self.assertRaisesRegex(freezer.FreezeRefusal, "wrong exact schema"):
            freezer.validate_frozen_full861_release(
                release,
                results_root=self.results,
            )

        for key in ("data_product", "analysis_data_product"):
            with self.subTest(key=key):
                tampered = dict(original)
                tampered[key] = "tampered_data_product"
                self.rewrite_manifest(release, tampered)
                with self.assertRaisesRegex(
                    freezer.FreezeRefusal,
                    "manifest contract is inconsistent",
                ):
                    freezer.validate_frozen_full861_release(
                        release,
                        results_root=self.results,
                    )

    def test_exported_validator_rejects_analysis_file_byte_tampering(self) -> None:
        release = self.freeze_release("validator_file_hash")
        analysis_file = release / freezer.ANALYSIS_BASENAMES[0]
        analysis_file.chmod(0o600)
        analysis_file.write_text("tampered analysis bytes\n")
        analysis_file.chmod(0o444)

        with self.assertRaisesRegex(freezer.FreezeRefusal, "analysis-file hashes"):
            freezer.validate_frozen_full861_release(
                release,
                results_root=self.results,
            )

    def test_exported_validator_rejects_manifest_hash_and_digest_tampering(self) -> None:
        release = self.freeze_release("validator_manifest_hashes")
        manifest_path = release / freezer.RELEASE_MANIFEST_BASENAME
        original = json.loads(manifest_path.read_text())
        first_analysis = freezer.ANALYSIS_BASENAMES[0]
        cases = (
            (
                "analysis_files_sha256",
                lambda manifest: manifest["analysis_files_sha256"].__setitem__(
                    first_analysis, "0" * 64
                ),
                "analysis-file hashes",
            ),
            (
                "analysis_bundle_sha256",
                lambda manifest: manifest.__setitem__(
                    "analysis_bundle_sha256", "0" * 64
                ),
                "analysis-bundle digest",
            ),
            (
                "pointwise_csv_sha256",
                lambda manifest: manifest.__setitem__(
                    "pointwise_csv_sha256", "0" * 64
                ),
                "pointwise CSV hash",
            ),
            (
                "analysis_provenance_sha256",
                lambda manifest: manifest.__setitem__(
                    "analysis_provenance_sha256", "0" * 64
                ),
                "analysis-provenance hash",
            ),
            (
                "analyzer_sha256",
                lambda manifest: manifest.__setitem__("analyzer_sha256", "0" * 64),
                "not bound to its analysis provenance",
            ),
            (
                "decision_certificate_sha256",
                lambda manifest: manifest.__setitem__(
                    "decision_certificate_sha256", "0" * 64
                ),
                "not bound to its analysis provenance",
            ),
        )
        for label, mutate, message in cases:
            with self.subTest(field=label):
                tampered = json.loads(json.dumps(original))
                mutate(tampered)
                self.rewrite_manifest(release, tampered)
                with self.assertRaisesRegex(freezer.FreezeRefusal, message):
                    freezer.validate_frozen_full861_release(
                        release,
                        results_root=self.results,
                    )

    def test_copy_failure_leaves_no_release_or_partial_stage(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}copy_failure"
        real_copy = shutil.copy2
        copy_count = 0

        def fail_second_copy(source, destination, *args, **kwargs):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("injected freeze copy failure")
            return real_copy(source, destination, *args, **kwargs)

        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch,
            mock.patch.object(freezer.shutil, "copy2", side_effect=fail_second_copy),
            self.assertRaisesRegex(OSError, "injected freeze copy failure"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        self.assertFalse(release.exists())
        self.assertFalse(list(self.results.glob(f".{release.name}.freeze-*")))

    def test_rename_failure_after_permission_freeze_cleans_read_only_stage(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}rename_failure"
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch,
            mock.patch.object(
                freezer,
                "_rename_directory_no_replace",
                side_effect=OSError("injected atomic rename failure"),
            ),
            self.assertRaisesRegex(OSError, "injected atomic rename failure"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        self.assertFalse(release.exists())
        self.assertFalse(
            list(self.results.glob(f".{release.name}.freeze-*")),
            "A failed rename must restore permissions and remove its read-only stage",
        )

    def test_atomic_rename_refuses_racing_empty_destination(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}racing_destination"
        real_rename = freezer._rename_directory_no_replace

        def create_empty_destination_then_rename(source: Path, destination: Path):
            destination.mkdir()
            return real_rename(source, destination)

        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch,
            mock.patch.object(
                freezer,
                "_rename_directory_no_replace",
                side_effect=create_empty_destination_then_rename,
            ),
            self.assertRaises(FileExistsError),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        self.assertTrue(release.is_dir())
        self.assertEqual(list(release.iterdir()), [])
        self.assertFalse(list(self.results.glob(f".{release.name}.freeze-*")))

    def test_post_install_hash_mismatch_rolls_back_owned_release(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}post_install_mismatch"
        resolved_release = release.resolve()
        real_sha256 = freezer._sha256
        target = freezer.ANALYSIS_BASENAMES[0]

        def mismatch_after_install(path: Path) -> str:
            candidate = Path(path)
            if candidate.parent == resolved_release and candidate.name == target:
                return "0" * 64
            return real_sha256(candidate)

        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch,
            mock.patch.object(freezer, "_sha256", side_effect=mismatch_after_install),
            self.assertRaisesRegex(freezer.FreezeRefusal, "hash/mode mismatch"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
                scale_points_path=self.work / "scale.csv",
            )
        self.assertFalse(release.exists())
        self.assertFalse(list(self.results.glob(f".{release.name}.freeze-*")))

    def test_refuses_transient_and_durable_path_contract_violations(self) -> None:
        wrong_candidate = self.work / "outside_tmp" / self.candidate.name
        wrong_candidate.parent.mkdir()
        release = self.results / f"{freezer.RELEASE_PREFIX}bad_source"
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch as loader,
            self.assertRaisesRegex(freezer.FreezeRefusal, "direct child"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=wrong_candidate,
                release_dir=release,
            )
        loader.assert_not_called()

        wrong_release = self.work / "outside_results" / (
            f"{freezer.RELEASE_PREFIX}bad_destination"
        )
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch as loader,
            self.assertRaisesRegex(freezer.FreezeRefusal, "direct child"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=wrong_release,
            )
        loader.assert_not_called()

    def test_existing_release_is_never_replaced(self) -> None:
        release = self.results / f"{freezer.RELEASE_PREFIX}already_frozen"
        release.mkdir()
        sentinel = release / "sentinel"
        sentinel.write_bytes(b"keep me")
        root_patch, results_patch, loader_patch = self.patch_roots_and_loader()
        with (
            root_patch,
            results_patch,
            loader_patch as loader,
            self.assertRaisesRegex(freezer.FreezeRefusal, "will not be replaced"),
        ):
            freezer.freeze_full861_publication_bundle(
                candidate_dir=self.candidate,
                release_dir=release,
            )
        loader.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"keep me")


if __name__ == "__main__":
    unittest.main()
