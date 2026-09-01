#!/usr/bin/env python3
"""Combine the compiled PNAS-style manuscript artifacts into review packets."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript"
OUTPUT = ROOT / "output" / "pdf"
TAG = date.today().strftime("%Y%m%d")


def merge(inputs: list[Path], output: Path) -> dict[str, object]:
    writer = PdfWriter()
    input_pages = {}
    for path in inputs:
        reader = PdfReader(path)
        input_pages[path.name] = len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)
    pages = len(PdfReader(output).pages)
    return {
        "output": str(output.resolve()),
        "pages": pages,
        "size_bytes": output.stat().st_size,
        "input_pages": input_pages,
    }


def main() -> None:
    main_pdf = MANUSCRIPT / "main_pnas_style.pdf"
    significance_pdf = MANUSCRIPT / "significance_statement_pnas_style.pdf"
    supplement_pdf = MANUSCRIPT / "supplement_pnas_style.pdf"
    for path in [main_pdf, significance_pdf, supplement_pdf]:
        if not path.exists() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Compile before combining: {path}")

    combined = MANUSCRIPT / "MMHK_PNAS_current_with_supplement.pdf"
    packet = MANUSCRIPT / "MMHK_PNAS_current_full_submission_packet.pdf"
    receipt = {
        "main_plus_supplement": merge([main_pdf, supplement_pdf], combined),
        "full_packet": merge([significance_pdf, main_pdf, supplement_pdf], packet),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    dated_combined = OUTPUT / f"MMHK_PNAS_current_{TAG}_main_and_SI.pdf"
    dated_packet = OUTPUT / f"MMHK_PNAS_current_{TAG}_full_packet.pdf"
    stable_combined = OUTPUT / "MMHK_PNAS_current_main_and_SI.pdf"
    stable_packet = OUTPUT / "MMHK_PNAS_current_full_packet.pdf"
    shutil.copy2(combined, dated_combined)
    shutil.copy2(packet, dated_packet)
    shutil.copy2(combined, stable_combined)
    shutil.copy2(packet, stable_packet)
    receipt["dated_outputs"] = [str(dated_combined.resolve()), str(dated_packet.resolve())]
    receipt["stable_outputs"] = [str(stable_combined.resolve()), str(stable_packet.resolve())]

    receipt_path = ROOT / "results" / f"pnas_submission_packet_{TAG}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
