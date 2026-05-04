#!/usr/bin/env python3
import argparse
import base64
import json
import re
from pathlib import Path


def _find_image_cell(nb: dict):
    for i, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if "imshow(spectralfunc" not in src:
            continue
        for out in cell.get("outputs", []):
            data = out.get("data", {})
            if "image/png" in data:
                return i, cell, out
    raise RuntimeError("No spectral image cell found in notebook.")


def _parse_mu_and_nden(prev_cell: dict):
    src = "".join(prev_cell.get("source", []))
    mu_match = re.search(r"\bmu\s*=\s*([+-]?\d+(?:\.\d+)?)", src)
    mu_val = float(mu_match.group(1)) if mu_match else None

    nden_val = None
    for out in prev_cell.get("outputs", []):
        text = "".join(out.get("text", []))
        m = re.search(r"([+-]?\d+(?:\.\d+)?)", text)
        if m:
            nden_val = float(m.group(1))
            break
    return mu_val, nden_val


def main():
    parser = argparse.ArgumentParser(description="Extract spectral image from notebook output.")
    parser.add_argument(
        "--notebook",
        default="old/ground_state_energy/find_gse_tp0_4x4.ipynb",
        help="Notebook file to parse.",
    )
    parser.add_argument(
        "--out-image",
        default="results/spectral_function_from_notebook.png",
        help="Output PNG path.",
    )
    parser.add_argument(
        "--out-meta",
        default="results/spectral_function_metadata.txt",
        help="Output metadata path.",
    )
    args = parser.parse_args()

    nb_path = Path(args.notebook)
    if not nb_path.exists():
        candidates = [
            Path("ground_state_energy/find_gse_tp0_4x4.ipynb"),
            Path("old/ground_state_energy/find_gse_tp0_4x4.ipynb"),
        ]
        for c in candidates:
            if c.exists():
                nb_path = c
                break
        else:
            raise FileNotFoundError(
                f"Notebook not found: {args.notebook}. Checked fallback candidates too."
            )
    nb = json.loads(nb_path.read_text())
    idx, _, img_out = _find_image_cell(nb)
    prev = nb["cells"][idx - 1] if idx > 0 else {}
    mu_val, nden_val = _parse_mu_and_nden(prev)

    png_b64 = img_out["data"]["image/png"]
    out_img = Path(args.out_image)
    out_img.parent.mkdir(parents=True, exist_ok=True)
    out_img.write_bytes(base64.b64decode(png_b64))

    out_meta = Path(args.out_meta)
    out_meta.parent.mkdir(parents=True, exist_ok=True)
    out_meta.write_text(
        "\n".join(
            [
                f"notebook: {nb_path}",
                f"image_cell_index: {idx}",
                f"mu_from_previous_cell: {mu_val}",
                f"printed_nden_from_previous_cell: {nden_val}",
                "note: extracted from stored notebook output; verify half-filling condition before publication.",
            ]
        )
        + "\n"
    )
    print(f"Wrote {out_img.resolve()}")
    print(f"Wrote {out_meta.resolve()}")


if __name__ == "__main__":
    main()
