#!/usr/bin/env python3
import argparse
import csv
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
# Figure-level legend anchor in figure coordinates.
# Adjust these two numbers to move legend around.
LEGEND_X = 0.15
LEGEND_Y = 0.95
DOPED_LEGEND_X = 0.23
DOPED_LEGEND_Y = 0.32
LEGEND_FONTSIZE = 14
FRAME_LABEL_FONTSIZE = 14
TICK_FONTSIZE = 15
XTICKS = [2, 4, 6, 8, 10, 12]
TARGET_DENSITIES = [1.0, 0.875, 0.8]
TARGET_US = [2, 4, 6, 8, 10, 12]


@dataclass
class MeasuredValue:
    value: float
    sigma: float | None
    raw: str


def _parse_measured(text: str) -> MeasuredValue | None:
    s = (text or "").strip()
    if not s:
        return None
    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\((\d+)\)\s*$", s)
    if m:
        base = m.group(1)
        err_digits = m.group(2)
        value = float(base)
        if "." in base:
            decimals = len(base.split(".")[1].split("E")[0].split("e")[0])
            sigma = int(err_digits) * (10 ** (-decimals))
        else:
            sigma = float(err_digits)
        return MeasuredValue(value=value, sigma=sigma, raw=s)
    try:
        return MeasuredValue(value=float(s), sigma=None, raw=s)
    except ValueError:
        return None


def _col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def _read_sheet_rows(path: Path) -> dict[int, dict[str, str]]:
    if path.suffix.lower() == ".csv":
        rows: dict[int, dict[str, str]] = {}
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for i, rec in enumerate(reader, start=2):  # line 1 is CSV header
                rows[i] = {k: (v or "") for k, v in rec.items()}
        return rows

    with zipfile.ZipFile(path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall("a:si", NS):
                text = "".join((t.text or "") for t in si.findall(".//a:t", NS))
                shared_strings.append(text)

        sheet_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows: dict[int, dict[str, str]] = {}
        for row in sheet_root.findall(".//a:sheetData/a:row", NS):
            r = int(row.attrib["r"])
            rows[r] = {}
            for c in row.findall("a:c", NS):
                ref = c.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                t = c.attrib.get("t")
                v = c.find("a:v", NS)
                if v is None:
                    value = ""
                else:
                    raw = v.text or ""
                    if t == "s" and raw.isdigit():
                        value = shared_strings[int(raw)]
                    else:
                        value = raw
                rows[r][col] = value
        return rows


def _extract_half_filling(rows: dict[int, dict[str, str]]):
    header_row = None
    u_start_col = None
    for r, cells in rows.items():
        ordered = sorted(cells.keys(), key=_col_to_idx)
        for i, col in enumerate(ordered[:-1]):
            nxt = ordered[i + 1]
            if cells.get(col, "").strip() == "t'=0" and cells.get(nxt, "").strip() == "U":
                header_row = r
                u_start_col = ordered[i + 2] if i + 2 < len(ordered) else None
                break
        if header_row is not None:
            break
    if header_row is None:
        raise RuntimeError("Could not find half-filling AFQMC/MMHK header row.")
    if u_start_col is None:
        raise RuntimeError("Could not determine first U column.")

    u_cols = []
    for col in sorted(rows[header_row].keys(), key=_col_to_idx):
        if _col_to_idx(col) < _col_to_idx(u_start_col):
            continue
        token = rows[header_row].get(col, "").strip()
        if not token:
            continue
        try:
            float(token)
            u_cols.append(col)
        except ValueError:
            pass
    if not u_cols:
        raise RuntimeError("No U values found in half-filling header row.")

    properties = [
        ("Ground State Energy", header_row + 1, header_row + 2),
        ("Double Occupancy", header_row + 3, header_row + 4),
        ("Magnetization", header_row + 5, header_row + 6),
    ]

    data = []
    for prop, afqmc_row, mmhk_row in properties:
        for col in u_cols:
            u_val = float(rows[header_row][col])
            afqmc = _parse_measured(rows.get(afqmc_row, {}).get(col, ""))
            mmhk = _parse_measured(rows.get(mmhk_row, {}).get(col, ""))
            data.append(
                {
                    "property": prop,
                    "U": u_val,
                    "AFQMC": afqmc,
                    "MMHK": mmhk,
                }
            )
    return data


def _attach_dmet_from_prx(data):
    # Extracted from Phys. Rev. X 5, 041041 (2015), Tables II, III, and VI.
    dmet = {
        "Ground State Energy": {
            2.0: MeasuredValue(-1.1764, 0.0003, "-1.1764(3)"),
            4.0: MeasuredValue(-0.8604, 0.0003, "-0.8604(3)"),
            6.0: MeasuredValue(-0.6562, 0.0005, "-0.6562(5)"),
            8.0: MeasuredValue(-0.5234, 0.0010, "-0.5234(10)"),
            12.0: MeasuredValue(-0.3685, 0.0010, "-0.3685(10)"),
        },
        "Double Occupancy": {
            2.0: MeasuredValue(0.1913, 0.0004, "0.1913(4)"),
            4.0: MeasuredValue(0.1261, 0.0001, "0.1261(1)"),
            6.0: MeasuredValue(0.08095, 0.00004, "0.08095(4)"),
            8.0: MeasuredValue(0.05398, 0.00007, "0.05398(7)"),
            12.0: MeasuredValue(0.02780, 0.00003, "0.02780(3)"),
        },
        "Magnetization": {
            2.0: MeasuredValue(0.133, 0.005, "0.133(5)"),
            4.0: MeasuredValue(0.252, 0.009, "0.252(9)"),
            6.0: MeasuredValue(0.299, 0.012, "0.299(12)"),
            8.0: MeasuredValue(0.318, 0.013, "0.318(13)"),
        },
    }
    for row in data:
        row["DMET"] = dmet.get(row["property"], {}).get(row["U"])
    return data


def _build_mmhk_from_observable_data(data_root: Path, div: int):
    observable_script_dir = Path(__file__).resolve().parents[1] / "observable" / "scripts"
    sys.path.insert(0, str(observable_script_dir))
    from find_observables_doped_clean import find_observables_at_density

    table = []
    for n_target in TARGET_DENSITIES:
        for u in TARGET_US:
            mu_star, density_star, e0_avg, sp, doi, doq = find_observables_at_density(
                target_density=n_target,
                div=div,
                data_root=data_root,
                u_dir=f"tp0U{u}",
            )
            table.append(
                {
                    "n_target": n_target,
                    "n_actual": density_star,
                    "U": float(u),
                    "mu": mu_star,
                    "Ground State Energy": e0_avg,
                    "Double Occupancy": doi,
                    "Magnetization": sp,
                    "Double Occupancy q": doq,
                }
            )
    return table


def _merge_half_filling_mmhk(data, mmhk_table):
    half_filling = {
        (row["U"], prop): row[prop]
        for row in mmhk_table
        if math.isclose(row["n_target"], 1.0)
        for prop in ("Ground State Energy", "Double Occupancy", "Magnetization")
    }
    for row in data:
        key = (row["U"], row["property"])
        if key in half_filling:
            value = half_filling[key]
            row["MMHK"] = MeasuredValue(value=value, sigma=None, raw=f"{value:.10f}")
    return data


def _mmhk_series(mmhk_table):
    series: dict[str, dict[float, list[tuple[float, float]]]] = {
        "Ground State Energy": {},
        "Double Occupancy": {},
        "Magnetization": {},
    }
    for prop in series:
        for n_target in TARGET_DENSITIES:
            pts = []
            for row in mmhk_table:
                if math.isclose(row["n_target"], n_target):
                    pts.append((row["U"], row[prop]))
            series[prop][n_target] = sorted(pts, key=lambda t: t[0])
    return series


def _write_csvs(data, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    methods_path = out_dir / "half_filling_methods.csv"
    delta_path = out_dir / "half_filling_deltas.csv"

    with methods_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["property", "U", "method", "value", "sigma", "raw"])
        for row in data:
            for method in ("AFQMC", "DMET", "MMHK"):
                mv = row[method]
                if mv is None:
                    continue
                w.writerow(
                    [
                        row["property"],
                        row["U"],
                        method,
                        mv.value,
                        "" if mv.sigma is None else mv.sigma,
                        mv.raw,
                    ]
                )

    with delta_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "property",
                "U",
                "mmhk_minus_afqmc",
                "abs_mmhk_minus_afqmc",
                "rel_mmhk_minus_afqmc_percent",
                "mmhk_minus_dmet",
                "abs_mmhk_minus_dmet",
                "rel_mmhk_minus_dmet_percent",
            ]
        )
        for row in data:
            afqmc = row["AFQMC"]
            dmet = row["DMET"]
            mmhk = row["MMHK"]
            delta_af = abs_af = rel_af = math.nan
            delta_dm = abs_dm = rel_dm = math.nan
            if afqmc is not None and mmhk is not None:
                delta_af = mmhk.value - afqmc.value
                abs_af = abs(delta_af)
                rel_af = math.nan if afqmc.value == 0 else (delta_af / afqmc.value) * 100.0
            if dmet is not None and mmhk is not None:
                delta_dm = mmhk.value - dmet.value
                abs_dm = abs(delta_dm)
                rel_dm = math.nan if dmet.value == 0 else (delta_dm / dmet.value) * 100.0
            w.writerow([row["property"], row["U"], delta_af, abs_af, rel_af, delta_dm, abs_dm, rel_dm])


def _write_mmhk_observables_csv(mmhk_table, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mmhk_observables_all_cases.csv"
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "n_target",
                "n_actual",
                "U",
                "mu",
                "ground_state_energy",
                "double_occupancy_i",
                "magnetization",
                "double_occupancy_q",
            ]
        )
        for row in sorted(mmhk_table, key=lambda item: (item["n_target"], item["U"])):
            w.writerow(
                [
                    row["n_target"],
                    row["n_actual"],
                    row["U"],
                    row["mu"],
                    row["Ground State Energy"],
                    row["Double Occupancy"],
                    row["Magnetization"],
                    row["Double Occupancy q"],
                ]
            )


def _plot(data, mmhk_series, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    props = ["Ground State Energy", "Double Occupancy", "Magnetization"]
    density_styles = {
        1.0: {"fmt": "--s", "color": "#d62728", "label": "4x4-MMHK (n=1)"},
        0.875: {"fmt": "--d", "color": "#8c564b", "label": "4x4-MMHK (n=0.875)"},
        0.8: {"fmt": "--o", "color": "#9467bd", "label": "4x4-MMHK (n=0.8)"},
    }
    secondary_labels = {
        density_styles[0.875]["label"],
        density_styles[0.8]["label"],
    }

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), dpi=200, constrained_layout=True)
    for ax, prop in zip(axes, props):
        rows = sorted([r for r in data if r["property"] == prop], key=lambda x: x["U"])

        xs_af = [r["U"] for r in rows if r["AFQMC"] is not None]
        ys_af = [r["AFQMC"].value for r in rows if r["AFQMC"] is not None]
        yerr_af = [
            0.0 if r["AFQMC"].sigma is None else r["AFQMC"].sigma
            for r in rows
            if r["AFQMC"] is not None
        ]
        xs_dm = [r["U"] for r in rows if r["DMET"] is not None]
        ys_dm = [r["DMET"].value for r in rows if r["DMET"] is not None]
        yerr_dm = [
            0.0 if r["DMET"].sigma is None else r["DMET"].sigma
            for r in rows
            if r["DMET"] is not None
        ]

        if xs_af:
            ax.errorbar(
                xs_af,
                ys_af,
                yerr=yerr_af,
                fmt="o",
                capsize=3,
                label="AFQMC (n=1)",
                color="#1f77b4",
            )
        if xs_dm:
            ax.errorbar(
                xs_dm,
                ys_dm,
                yerr=yerr_dm,
                fmt="^",
                capsize=3,
                label="DMET (n=1)",
                color="#2ca02c",
            )
        for n_target in TARGET_DENSITIES:
            pts = mmhk_series.get(prop, {}).get(n_target, [])
            if not pts:
                continue
            style = density_styles[n_target]
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                style["fmt"],
                color=style["color"],
                label=style["label"],
            )

        if prop == "Magnetization":
            # Sandvik (Phys. Rev. B 56, 11678): 2D Heisenberg staggered magnetization.
            ax.axhline(
                0.307,
                color="#7f7f7f",
                linestyle="--",
                linewidth=1.5,
            )
            ax.text(
                8.6,
                0.309,
                "Heisenberg limit",
                color="#7f7f7f",
                fontsize=12,
                ha="left",
                va="bottom",
            )

        ax.set_title(prop)
        ax.set_xlabel("U/t", fontsize=FRAME_LABEL_FONTSIZE)
        ax.set_xticks(XTICKS)
        ax.tick_params(axis="both", labelsize=TICK_FONTSIZE)
        ax.grid(alpha=0.25)

    axes[0].set_ylabel("Value", fontsize=FRAME_LABEL_FONTSIZE)
    legend_entries: dict[str, object] = {}
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            legend_entries.setdefault(label, handle)

    primary_labels = [label for label in legend_entries if label not in secondary_labels]
    if primary_labels:
        primary_legend = fig.legend(
            [legend_entries[label] for label in primary_labels],
            primary_labels,
            loc="upper center",
            bbox_to_anchor=(LEGEND_X, LEGEND_Y),
            ncol=1,
            fontsize=LEGEND_FONTSIZE,
            frameon=False,
        )
        fig.add_artist(primary_legend)

    density_labels = [label for label in legend_entries if label in secondary_labels]
    if density_labels:
        fig.legend(
            [legend_entries[label] for label in density_labels],
            density_labels,
            loc="upper center",
            bbox_to_anchor=(DOPED_LEGEND_X, DOPED_LEGEND_Y),
            ncol=1,
            fontsize=LEGEND_FONTSIZE,
            frameon=False,
        )

    out_path = out_dir / "comparison.pdf"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare MMHK vs AFQMC from benchmark.xlsx.")
    parser.add_argument(
        "--xlsx",
        default="results/benchmark_backup_filled_EFG.csv",
        help="Input workbook path (.xlsx or .csv).",
    )
    parser.add_argument(
        "--data-root",
        default="observable/data",
        help="MMHK observable data root.",
    )
    parser.add_argument(
        "--div",
        type=int,
        default=1,
        help="Sampling stride used in observable extraction.",
    )
    parser.add_argument("--out-dir", default="results", help="Output directory.")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    rows = _read_sheet_rows(xlsx_path)
    data = _extract_half_filling(rows)
    data = _attach_dmet_from_prx(data)
    mmhk_table = _build_mmhk_from_observable_data(data_root=data_root, div=args.div)
    data = _merge_half_filling_mmhk(data, mmhk_table)
    mmhk_series = _mmhk_series(mmhk_table)
    _write_csvs(data, out_dir)
    _write_mmhk_observables_csv(mmhk_table, out_dir)
    _plot(data, mmhk_series, out_dir)
    print(f"Wrote comparison outputs to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
