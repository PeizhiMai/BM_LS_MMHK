#!/usr/bin/env python3
"""Compare a future manuscript source tree with the frozen pre-Philip baseline.

The input may be an Overleaf source ZIP or an unpacked source directory.  The
script writes a human-readable Markdown report, a machine-readable JSON report,
and unified diffs for changed text files.  It never modifies either source tree.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_POINTER = PROJECT_ROOT / "manuscript" / "archive" / "PRE_PHILIP_BASELINE.json"
TEXT_SUFFIXES = {".tex", ".bib", ".md", ".txt", ".sty", ".cls"}
FIGURE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"}
IGNORED_NAMES = {
    ".DS_Store",
    "main.aux",
    "main.bbl",
    "main.blg",
    "main.fdb_latexmk",
    "main.fls",
    "main.log",
    "main.out",
    "main.synctex.gz",
    "supplement.aux",
    "supplement.bbl",
    "supplement.blg",
    "supplement.fdb_latexmk",
    "supplement.fls",
    "supplement.log",
    "supplement.out",
    "supplement.synctex.gz",
    "supplement.toc",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def locate_source_root(root: Path) -> Path:
    """Return the shallowest directory containing main.tex."""
    if (root / "main.tex").is_file():
        return root
    candidates = sorted(
        (path.parent for path in root.rglob("main.tex")),
        key=lambda path: (len(path.relative_to(root).parts), str(path)),
    )
    if not candidates:
        raise FileNotFoundError(f"No main.tex found under {root}")
    return candidates[0]


def materialize_source(path: Path, temporary_root: Path) -> Path:
    if path.is_dir():
        return locate_source_root(path.resolve())
    if path.suffix.lower() != ".zip":
        raise ValueError("Final source must be a directory or an Overleaf source ZIP")
    extracted = temporary_root / "final_source"
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(extracted)
    return locate_source_root(extracted)


def inventory(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        relative = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in Path(relative).parts):
            continue
        result[relative] = {
            "path": path,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "kind": (
                "text"
                if path.suffix.lower() in TEXT_SUFFIXES
                else "figure"
                if path.suffix.lower() in FIGURE_SUFFIXES
                else "other"
            ),
        }
    return result


def strip_latex_for_word_count(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", " ", text)
    text = re.sub(r"\\(?:cite|ref|eqref|figdisp|refdisp|label)\*?(?:\[[^]]*\])?\{[^}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
    text = re.sub(r"[{}$&_^~\\]", " ", text)
    return text


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", strip_latex_for_word_count(text)))


def extract_sections(text: str) -> list[str]:
    pattern = re.compile(r"\\(?:section|subsection|subsubsection)\*?\s*\{([^{}]*)\}")
    return [re.sub(r"\s+", " ", title).strip() for title in pattern.findall(text)]


def extract_labels(text: str) -> list[str]:
    return re.findall(r"\\label\s*\{([^}]+)\}", text)


def extract_bib_keys(text: str) -> list[str]:
    return re.findall(r"@\w+\s*\{\s*([^,\s]+)", text)


def added_removed(before: Iterable[str], after: Iterable[str]) -> dict[str, list[str]]:
    before_counter = Counter(before)
    after_counter = Counter(after)
    return {
        "added": sorted((after_counter - before_counter).elements()),
        "removed": sorted((before_counter - after_counter).elements()),
    }


def line_change_counts(diff_lines: list[str]) -> tuple[int, int]:
    additions = sum(line.startswith("+") and not line.startswith("+++") for line in diff_lines)
    deletions = sum(line.startswith("-") and not line.startswith("---") for line in diff_lines)
    return additions, deletions


def compare_trees(baseline_root: Path, final_root: Path, output_dir: Path) -> dict[str, Any]:
    baseline = inventory(baseline_root)
    final = inventory(final_root)
    baseline_names = set(baseline)
    final_names = set(final)

    added = sorted(final_names - baseline_names)
    removed = sorted(baseline_names - final_names)
    common = sorted(baseline_names & final_names)
    changed = [name for name in common if baseline[name]["sha256"] != final[name]["sha256"]]
    unchanged = [name for name in common if baseline[name]["sha256"] == final[name]["sha256"]]

    diffs_dir = output_dir / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)
    text_changes: dict[str, Any] = {}
    for name in changed:
        if baseline[name]["kind"] != "text" or final[name]["kind"] != "text":
            continue
        before = read_text(baseline[name]["path"])
        after = read_text(final[name]["path"])
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"pre-Philip/{name}",
                tofile=f"final/{name}",
                n=3,
            )
        )
        additions, deletions = line_change_counts(diff_lines)
        diff_path = diffs_dir / f"{name}.diff"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text("".join(diff_lines), encoding="utf-8")
        text_changes[name] = {
            "added_lines": additions,
            "deleted_lines": deletions,
            "baseline_words": word_count(before),
            "final_words": word_count(after),
            "word_change": word_count(after) - word_count(before),
            "diff": str(diff_path.relative_to(output_dir)),
        }

    core_files: dict[str, Any] = {}
    for name in ("main.tex", "supplement.tex", "significance_statement.tex", "references.bib"):
        if name not in baseline and name not in final:
            continue
        before = read_text(baseline[name]["path"]) if name in baseline else ""
        after = read_text(final[name]["path"]) if name in final else ""
        core: dict[str, Any] = {
            "baseline_words": word_count(before),
            "final_words": word_count(after),
            "word_change": word_count(after) - word_count(before),
        }
        if name.endswith(".tex"):
            core["sections"] = added_removed(extract_sections(before), extract_sections(after))
            core["labels"] = added_removed(extract_labels(before), extract_labels(after))
        if name == "references.bib":
            core["bibliography_keys"] = added_removed(extract_bib_keys(before), extract_bib_keys(after))
        core_files[name] = core

    figure_names = sorted(
        name
        for name in baseline_names | final_names
        if (baseline.get(name) or final.get(name))["kind"] == "figure"
    )
    figure_changes = {
        "added": [name for name in figure_names if name in added],
        "removed": [name for name in figure_names if name in removed],
        "changed": [name for name in figure_names if name in changed],
        "unchanged": [name for name in figure_names if name in unchanged],
    }

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "baseline_source": str(baseline_root),
        "final_source": str(final_root),
        "summary": {
            "baseline_files": len(baseline),
            "final_files": len(final),
            "added_files": len(added),
            "removed_files": len(removed),
            "changed_files": len(changed),
            "unchanged_files": len(unchanged),
        },
        "files": {
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
        },
        "text_changes": text_changes,
        "core_files": core_files,
        "figures": figure_changes,
    }


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- `{item}`" for item in items) if items else "- None"


def render_markdown(report: dict[str, Any], baseline_label: str) -> str:
    summary = report["summary"]
    lines = [
        "# Manuscript comparison: pre-Philip baseline to final version",
        "",
        f"- **Baseline:** {baseline_label}",
        f"- **Compared at (UTC):** {report['generated_utc']}",
        f"- **Final source:** `{report['final_source']}`",
        "",
        "## Executive inventory",
        "",
        f"- Files: {summary['baseline_files']} baseline, {summary['final_files']} final",
        f"- Added: {summary['added_files']}",
        f"- Removed: {summary['removed_files']}",
        f"- Changed: {summary['changed_files']}",
        f"- Unchanged: {summary['unchanged_files']}",
        "",
        "## Core manuscript changes",
        "",
        "| File | Baseline words | Final words | Change | Added lines | Deleted lines |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, core in report["core_files"].items():
        change = report["text_changes"].get(name, {})
        lines.append(
            f"| `{name}` | {core['baseline_words']} | {core['final_words']} | "
            f"{core['word_change']:+d} | {change.get('added_lines', 0)} | "
            f"{change.get('deleted_lines', 0)} |"
        )

    for name, core in report["core_files"].items():
        if "sections" in core and (core["sections"]["added"] or core["sections"]["removed"]):
            lines.extend(
                [
                    "",
                    f"### Section-title changes in `{name}`",
                    "",
                    "**Added**",
                    bullet_list(core["sections"]["added"]),
                    "",
                    "**Removed**",
                    bullet_list(core["sections"]["removed"]),
                ]
            )
        if "labels" in core and (core["labels"]["added"] or core["labels"]["removed"]):
            lines.extend(
                [
                    "",
                    f"### Label changes in `{name}`",
                    "",
                    "**Added**",
                    bullet_list(core["labels"]["added"]),
                    "",
                    "**Removed**",
                    bullet_list(core["labels"]["removed"]),
                ]
            )

    bib = report["core_files"].get("references.bib", {}).get("bibliography_keys")
    if bib:
        lines.extend(
            [
                "",
                "## Bibliography-key changes",
                "",
                "**Added**",
                bullet_list(bib["added"]),
                "",
                "**Removed**",
                bullet_list(bib["removed"]),
            ]
        )

    lines.extend(
        [
            "",
            "## Figure-file changes",
            "",
            "### Added",
            bullet_list(report["figures"]["added"]),
            "",
            "### Removed",
            bullet_list(report["figures"]["removed"]),
            "",
            "### Changed in place",
            bullet_list(report["figures"]["changed"]),
            "",
            "## All changed files",
            "",
            bullet_list(report["files"]["changed"]),
            "",
            "Unified text diffs are stored under `diffs/`; `comparison.json` contains the complete machine-readable inventory.",
            "",
            "> This report identifies changes relative to the timestamped baseline. It does not infer authorship of individual edits after that baseline.",
            "",
        ]
    )
    return "\n".join(lines)


def load_pointer() -> dict[str, Any]:
    if not BASELINE_POINTER.is_file():
        raise FileNotFoundError(f"Missing baseline pointer: {BASELINE_POINTER}")
    return json.loads(BASELINE_POINTER.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_source", type=Path, help="Final Overleaf source ZIP or unpacked source directory")
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Override the frozen baseline source directory (normally read from PRE_PHILIP_BASELINE.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "manuscript_comparison_pre_philip_to_final",
        help="Directory for comparison.md, comparison.json, and unified diffs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pointer = load_pointer()
    baseline_root = (
        args.baseline.resolve()
        if args.baseline
        else (PROJECT_ROOT / pointer["source_path"]).resolve()
    )
    if not baseline_root.is_dir():
        raise FileNotFoundError(f"Baseline source directory does not exist: {baseline_root}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="manuscript_compare_") as temporary:
        final_root = materialize_source(args.final_source.resolve(), Path(temporary))
        report = compare_trees(baseline_root, final_root, output_dir)

    report["baseline"] = pointer
    (output_dir / "comparison.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "comparison.md").write_text(
        render_markdown(report, pointer["label"]), encoding="utf-8"
    )
    print(output_dir / "comparison.md")
    print(output_dir / "comparison.json")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
