"""Focused tests for the dedicated add-only U=20,V=5 snapshot finalizer."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
FINALIZER_PATH = (
    REPO / "scripts" / "cades_queue" / "finalize_fullobs_25twist_u20v5_fig4_cnn.py"
)
EXPECTED_MANIFEST_SHA256 = (
    "05d8ee7c0aef76beb1b86b82b4780a9e85fcce9df0c4b8da023d3b84f545943e"
)
EXPECTED_PROVENANCE_SHA256 = (
    "ccf109a50ad2bf6d4f0abd2b1c0c2c0723354971c71b6fcdfd8815488484a51e"
)
EXPECTED_TWIST_PANEL_SHA256 = (
    "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
)


def load_finalizer():
    spec = importlib.util.spec_from_file_location(
        "u20v5_fullobs_finalizer_under_test", FINALIZER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load finalizer at {FINALIZER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def complete_report(finalizer) -> dict[str, object]:
    return {
        "batch": str(finalizer.REMOTE_BATCH),
        "total_targets": 25,
        "counts": {"COMPLETE": 25},
        "batch_active_queue_counts": {},
        "anomalies": {},
        "scheduler_errors": [],
        "warnings": [],
        "repair_candidates": [],
        "read_only": True,
        "pin_audit": [{"match": True} for _ in range(3)],
    }


def raw_output(*, energy_offset: float = 0.0) -> str:
    nn = 0.8
    delta_nn = nn - 1.0
    kinetic_nn = -0.3
    kinetic_nnn = -0.1
    kinetic = kinetic_nn + kinetic_nnn
    d_site = 0.1
    energy = 16.0 * (kinetic + 20.0 * d_site + 2.0 * 5.0 * nn)
    sc_pipi = 0.8
    return f"""Lx 4
Ly 4
tp 0
U 20
V 5
E0 {energy + energy_offset:.18e}
<nn_NN> {nn:.18e}
<delta_n_delta_n_NN> {delta_nn:.18e}
<Kinetic_NN_per_site> {kinetic_nn:.18e}
<Kinetic_NNN_per_site> {kinetic_nnn:.18e}
<Kinetic_per_site> {kinetic:.18e}
<C1_NN> -3.500000000000000000e-01
Q 0,0
<ni_upni_dn> {d_site:.18e}
<Sc_pipi> {sc_pipi:.18e}
<mCDW2_pipi> {sc_pipi / 16.0:.18e}
status COMPLETE
"""


def write_remote_manifest(finalizer, path: Path) -> None:
    fields = (
        "index",
        "U",
        "V",
        "V_over_U",
        "expected_phase",
        "twist_index",
        "kx",
        "ky",
        "seed",
        "job_name",
        "result",
        "state_at_generation",
        "template",
    )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for index, (kx, ky) in enumerate(finalizer.TWISTS, 1):
            name = finalizer.expected_raw_name(kx, ky)
            writer.writerow(
                {
                    "index": index,
                    "U": 20,
                    "V": 5,
                    "V_over_U": 0.25,
                    "expected_phase": "Mott",
                    "twist_index": index,
                    "kx": kx,
                    "ky": ky,
                    "seed": 10_000 + index,
                    "job_name": "F4C20V5",
                    "result": str(finalizer.REMOTE_BASE / name),
                    "state_at_generation": "template",
                    "template": f"{finalizer.REMOTE_BATCH}/templates/job_{index:04d}.sh",
                }
            )


def make_analysis_fixture(finalizer, parent: Path) -> tuple[Path, Path]:
    metadata = parent / "metadata"
    raw = parent / "raw"
    metadata.mkdir()
    raw.mkdir()
    write_remote_manifest(finalizer, metadata / "manifest.tsv")
    finalizer.make_local_manifest(
        metadata / "manifest.tsv", metadata / "manifest_local.tsv"
    )
    for kx, ky in finalizer.TWISTS:
        (raw / finalizer.expected_raw_name(kx, ky)).write_text(raw_output())
    return metadata, raw


def make_minimal_snapshot_staging(finalizer, root: Path, name: str) -> Path:
    staging = root / name
    staging.mkdir(mode=0o700)
    executable = staging / "metadata/tools/finalizer.py"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/usr/bin/python3.11\n")
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


def inventory_fixture(finalizer) -> dict[str, object]:
    results = []
    for index, (kx, ky) in enumerate(finalizer.TWISTS, 1):
        name = finalizer.expected_raw_name(kx, ky)
        results.append(
            {
                "index": index,
                "U": "20",
                "V": "5",
                "kx": kx,
                "ky": ky,
                "filename": name,
                "path": str(finalizer.REMOTE_BASE / name),
                "size_bytes": 1,
                "mtime_ns": 1,
                "sha256": "a" * 64,
            }
        )
    pin_file_hash = finalizer.hashlib.sha256(
        finalizer.expected_pin_file_text().encode()
    ).hexdigest()
    core = {
        "manifest.tsv": finalizer.EXPECTED_MANIFEST_SHA256,
        "provenance.json": finalizer.EXPECTED_PROVENANCE_SHA256,
        "twist_panel.tsv": finalizer.EXPECTED_TWIST_PANEL_SHA256,
        "PINNED_SHA256SUMS": pin_file_hash,
        **{
            f"pinned_solver/{name}": digest
            for name, digest in finalizer.EXPECTED_PIN_SHA256.items()
        },
    }
    metadata = [
        {
            "relative_path": relative,
            "size_bytes": 1,
            "mtime_ns": 1,
            "sha256": digest,
        }
        for relative, digest in core.items()
    ]
    return {
        "schema_version": 1,
        "batch": str(finalizer.REMOTE_BATCH),
        "base": str(finalizer.REMOTE_BASE),
        "manifest_sha256": finalizer.EXPECTED_MANIFEST_SHA256,
        "provenance_sha256": finalizer.EXPECTED_PROVENANCE_SHA256,
        "twist_panel_sha256": finalizer.EXPECTED_TWIST_PANEL_SHA256,
        "pin_file_sha256": pin_file_hash,
        "target_count": 25,
        "submission_count": 25,
        "results": results,
        "metadata": metadata,
    }


def make_downloaded_metadata_fixture(finalizer, metadata: Path) -> dict[str, str]:
    metadata.mkdir()
    write_remote_manifest(finalizer, metadata / "manifest.tsv")
    with (metadata / "twist_panel.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "twist_index",
                "kx",
                "ky",
                "diagonal",
                "symmetry_multiplicity",
            ]
        )
        for index, (kx, ky) in enumerate(finalizer.TWISTS, 1):
            writer.writerow([index, kx, ky, kx == ky, 1 if kx == ky else 2])

    pinned = metadata / "pinned_solver"
    pinned.mkdir()
    pin_hashes: dict[str, str] = {}
    for name in finalizer.EXPECTED_PIN_SHA256:
        path = pinned / name
        path.write_bytes(("fixture-" + name).encode())
        pin_hashes[name] = finalizer.sha256(path)
    pin_text = "".join(
        f"{digest}  pinned_solver/{name}\n" for name, digest in pin_hashes.items()
    )
    (metadata / "PINNED_SHA256SUMS").write_text(pin_text)
    provenance = {
        "batch": str(finalizer.REMOTE_BATCH),
        "job_name": "F4C20V5",
        "target_count": 25,
        "physics": {
            "Lx": 4,
            "Ly": 4,
            "Ndn": 8,
            "Nup": 8,
            "Qm": 0,
            "Qn": 0,
            "tp": 0,
        },
        "twists": [{"kx": kx, "ky": ky} for kx, ky in finalizer.TWISTS],
        "pairs": [{"U": 20, "V": "5", "V_over_U": 0.25}],
        "solver_sha256": pin_hashes["Hubbard_sym_testobs_UV.x"],
        "source_sha256": pin_hashes["Hubbard_sym_testobs_UV.cc"],
        "qbasis_library_sha256": pin_hashes["libqbasis.so"],
        "aggregation": {
            "primary_C_NN_estimator": (
                "unweighted arithmetic mean over deterministic 25-twist maximin panel"
            ),
            "twist_spread_is_not_standard_error": True,
        },
    }
    (metadata / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    return pin_hashes


class U20V5FinalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finalizer = load_finalizer()

    def test_campaign_identity_and_candidate_layout_are_exact(self) -> None:
        f = self.finalizer
        self.assertEqual(f.EXPECTED_MANIFEST_SHA256, EXPECTED_MANIFEST_SHA256)
        self.assertEqual(f.EXPECTED_PROVENANCE_SHA256, EXPECTED_PROVENANCE_SHA256)
        self.assertEqual(f.EXPECTED_TWIST_PANEL_SHA256, EXPECTED_TWIST_PANEL_SHA256)
        self.assertEqual(f.EXPECTED_TARGETS, 25)
        self.assertEqual(f.EXPECTED_PER_CASE, 25)
        self.assertEqual(f.EXPECTED_JOB_NAMES, ("F4C20V5", "F4C20V5R"))
        self.assertEqual(f.SNAPSHOT_NAME, "fullobs_25twist_u20v5_fig4_cnn_20260821")
        self.assertEqual(f.REMOTE_BATCH.name, "fullobs_25twist_u20v5_fig4_cnn_20260821")
        self.assertEqual(
            f.SNAPSHOT_ROOT_DEFAULT / f.SNAPSHOT_NAME,
            REPO / "data" / "fullobs" / "fullobs_25twist_u20v5_fig4_cnn_20260821",
        )
        self.assertIn(
            "metadata/remote_results_sha256.tsv", f.snapshot_readme(Path("x"))
        )
        self.assertIn("metadata/snapshot_file_sha256.tsv", f.snapshot_readme(Path("x")))

    def test_wrong_manifest_provenance_or_twist_hash_is_refused(self) -> None:
        valid = inventory_fixture(self.finalizer)
        for field in (
            "manifest_sha256",
            "provenance_sha256",
            "twist_panel_sha256",
            "pin_file_sha256",
        ):
            with self.subTest(field=field):
                altered = dict(valid)
                altered[field] = "0" * 64
                with self.assertRaises(self.finalizer.Refusal):
                    self.finalizer.require_source_hashes(altered, "test")

    def test_inventory_is_exactly_bound_to_reviewed_panel_and_pins(self) -> None:
        inventory = inventory_fixture(self.finalizer)
        self.finalizer.require_source_hashes(inventory, "test")
        self.finalizer.validate_inventory_contract(inventory)
        inventory["results"][4]["filename"] = "wrong.dat"
        with self.assertRaises(self.finalizer.Refusal):
            self.finalizer.validate_inventory_contract(inventory)

    def test_downloaded_candidate_layout_checks_original_metadata_and_pins(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_metadata_") as temporary:
            metadata = Path(temporary) / "metadata"
            pin_hashes = make_downloaded_metadata_fixture(self.finalizer, metadata)
            with (
                mock.patch.object(
                    self.finalizer,
                    "EXPECTED_MANIFEST_SHA256",
                    self.finalizer.sha256(metadata / "manifest.tsv"),
                ),
                mock.patch.object(
                    self.finalizer,
                    "EXPECTED_PROVENANCE_SHA256",
                    self.finalizer.sha256(metadata / "provenance.json"),
                ),
                mock.patch.object(
                    self.finalizer,
                    "EXPECTED_TWIST_PANEL_SHA256",
                    self.finalizer.sha256(metadata / "twist_panel.tsv"),
                ),
                mock.patch.object(self.finalizer, "EXPECTED_PIN_SHA256", pin_hashes),
            ):
                self.finalizer.validate_downloaded_campaign_metadata(metadata)
                (metadata / "pinned_solver/libqbasis.so").write_bytes(b"tampered")
                with self.assertRaises(self.finalizer.Refusal):
                    self.finalizer.validate_downloaded_campaign_metadata(metadata)

    def test_incomplete_or_active_audit_refuses(self) -> None:
        incomplete = complete_report(self.finalizer)
        incomplete["counts"] = {"COMPLETE": 24, "RUNNING": 1}
        with self.assertRaises(self.finalizer.Refusal):
            self.finalizer.gate_report(incomplete, "test incomplete")

        active = complete_report(self.finalizer)
        active["batch_active_queue_counts"] = {"RUNNING": 1}
        with self.assertRaises(self.finalizer.Refusal):
            self.finalizer.gate_report(active, "test active")

    def test_unsafe_option_like_ssh_host_refuses_before_remote_access(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_unsafe_host_") as temporary:
            with mock.patch.object(self.finalizer, "remote_audit") as audit:
                with self.assertRaises(self.finalizer.Refusal):
                    self.finalizer.finalize(
                        "-bad",
                        Path(temporary),
                        check_only=True,
                    )
            audit.assert_not_called()

    def test_finalize_incomplete_refusal_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_incomplete_") as temporary:
            snapshot_root = Path(temporary) / "snapshots"
            report = complete_report(self.finalizer)
            report["counts"] = {"COMPLETE": 24, "RUNNING": 1}
            with (
                mock.patch.object(self.finalizer, "remote_audit", return_value=report),
                mock.patch.object(self.finalizer, "remote_inventory") as inventory,
            ):
                with self.assertRaises(self.finalizer.Refusal):
                    self.finalizer.finalize("cades", snapshot_root, check_only=False)
            inventory.assert_not_called()
            self.assertFalse(snapshot_root.exists())

    def test_check_only_success_still_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_check_only_") as temporary:
            snapshot_root = Path(temporary) / "snapshots"
            with (
                mock.patch.object(
                    self.finalizer,
                    "remote_audit",
                    return_value=complete_report(self.finalizer),
                ),
                mock.patch.object(
                    self.finalizer,
                    "remote_inventory",
                    return_value=inventory_fixture(self.finalizer),
                ),
            ):
                destination = self.finalizer.finalize(
                    "cades", snapshot_root, check_only=True
                )
            self.assertEqual(destination, snapshot_root / self.finalizer.SNAPSHOT_NAME)
            self.assertFalse(snapshot_root.exists())

    def test_analysis_validates_exact_25_raw_files_and_four_identities(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_analysis_") as temporary:
            root = Path(temporary)
            metadata, raw = make_analysis_fixture(self.finalizer, root)
            analysis = root / "analysis"
            self.finalizer.generate_analysis(metadata, raw, analysis)
            with (analysis / "fig4_cnn_25twist_observables.csv").open(
                newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            with (analysis / "fig4_cnn_25twist_summary.csv").open(newline="") as handle:
                summary = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 25)
            self.assertEqual(len(summary), 1)
            self.assertTrue(all(row["status"] == "COMPLETE" for row in rows))
            self.assertTrue(
                all(
                    float(row["max_abs_identity_residual"])
                    <= self.finalizer.IDENTITY_TOLERANCE
                    for row in rows
                )
            )

    def test_analysis_refuses_identity_violation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_identity_") as temporary:
            root = Path(temporary)
            metadata, raw = make_analysis_fixture(self.finalizer, root)
            kx, ky = self.finalizer.TWISTS[0]
            (raw / self.finalizer.expected_raw_name(kx, ky)).write_text(
                raw_output(energy_offset=1.0e-3)
            )
            with self.assertRaisesRegex(RuntimeError, "Four-identity tolerance"):
                self.finalizer.generate_analysis(metadata, raw, root / "analysis")

    @unittest.skipUnless(sys.platform == "darwin", "exercises macOS renamex_np")
    def test_real_macos_no_replace_rename_freezes_all_files_0444(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_snapshot_install_") as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(
                self.finalizer, root, ".snapshot.staging"
            )
            destination = root / "snapshot"
            observed_source_modes: list[int] = []
            real_rename = self.finalizer._rename_directory_no_replace

            def checked_real_rename(source: Path, target: Path) -> None:
                observed_source_modes.append(stat.S_IMODE(source.stat().st_mode))
                real_rename(source, target)

            with mock.patch.object(
                self.finalizer,
                "_rename_directory_no_replace",
                side_effect=checked_real_rename,
            ):
                self.finalizer.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertEqual(observed_source_modes, [0o700])
            self.assertFalse(os.path.lexists(staging))
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o555)
            for path in destination.rglob("*"):
                expected_mode = 0o555 if path.is_dir() else 0o444
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected_mode)

            ledger = destination / "metadata/snapshot_file_sha256.tsv"
            with ledger.open(newline="") as handle:
                ledger_rows = list(csv.DictReader(handle, delimiter="\t"))
            actual_files = {
                path.relative_to(destination).as_posix()
                for path in destination.rglob("*")
                if path.is_file() and path != ledger
            }
            self.assertEqual(
                {row["relative_path"] for row in ledger_rows}, actual_files
            )
            identity = self.finalizer._directory_identity(destination)
            self.finalizer._remove_owned_snapshot_tree(destination, identity)

    def test_post_install_failure_rolls_back_owned_destination(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="u20v5_snapshot_rollback_"
        ) as temporary:
            root = Path(temporary)
            staging = make_minimal_snapshot_staging(
                self.finalizer, root, ".snapshot.staging"
            )
            destination = root / "snapshot"
            real_verify = self.finalizer._verify_snapshot_install_contract

            def fail_after_rename(
                path: Path, contract: dict, *, root_mode: int
            ) -> None:
                real_verify(path, contract, root_mode=root_mode)
                if root_mode == 0o555:
                    raise self.finalizer.Refusal("synthetic post-install failure")

            with (
                mock.patch.object(
                    self.finalizer,
                    "_verify_snapshot_install_contract",
                    side_effect=fail_after_rename,
                ),
                self.assertRaises(self.finalizer.Refusal),
            ):
                self.finalizer.install_read_only_snapshot(
                    staging, destination, expected_raw_count=1
                )
            self.assertFalse(os.path.lexists(staging))
            self.assertFalse(os.path.lexists(destination))

    def test_existing_destination_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="u20v5_snapshot_no_replace_"
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

    def test_top_level_existing_snapshot_refuses_before_remote_access(self) -> None:
        with tempfile.TemporaryDirectory(prefix="u20v5_existing_release_") as temporary:
            root = Path(temporary)
            destination = root / self.finalizer.SNAPSHOT_NAME
            destination.mkdir()
            marker = destination / "immutable.txt"
            marker.write_text("preserve\n")
            with mock.patch.object(self.finalizer, "remote_audit") as audit:
                with self.assertRaises(self.finalizer.Refusal):
                    self.finalizer.finalize("cades", root, check_only=False)
            audit.assert_not_called()
            self.assertEqual(marker.read_text(), "preserve\n")

    def test_cli_has_no_force_overwrite_or_destination_override(self) -> None:
        for arguments in (
            ["--force"],
            ["--overwrite"],
            ["--snapshot-root", "/tmp/not-the-fixed-destination"],
        ):
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", [str(FINALIZER_PATH), *arguments]),
            ):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    self.finalizer.parse_args()


if __name__ == "__main__":
    unittest.main()
