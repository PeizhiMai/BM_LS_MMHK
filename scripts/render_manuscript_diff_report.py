#!/usr/bin/env python3
"""Render a unified manuscript diff as a readable HTML report.

The output is self-contained and print-optimized.  A browser can export it to
PDF without external stylesheets or JavaScript.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
from dataclasses import dataclass
from pathlib import Path


HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:\s*(.*))?$"
)


@dataclass
class DiffRow:
    kind: str
    old_line: int | None
    new_line: int | None
    text: str


@dataclass
class Hunk:
    header: str
    old_start: int
    new_start: int
    rows: list[DiffRow]


def parse_unified_diff(text: str) -> tuple[str, str, list[Hunk]]:
    lines = text.splitlines()
    old_name = lines[0][4:] if lines and lines[0].startswith("--- ") else "old"
    new_name = lines[1][4:] if len(lines) > 1 and lines[1].startswith("+++ ") else "new"
    hunks: list[Hunk] = []
    current: Hunk | None = None
    old_line = new_line = 0

    for line in lines[2:]:
        match = HUNK_RE.match(line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            current = Hunk(line, old_line, new_line, [])
            hunks.append(current)
            continue
        if current is None:
            continue
        if line.startswith("-"):
            current.rows.append(DiffRow("removed", old_line, None, line[1:]))
            old_line += 1
        elif line.startswith("+"):
            current.rows.append(DiffRow("added", None, new_line, line[1:]))
            new_line += 1
        elif line.startswith(" "):
            current.rows.append(DiffRow("context", old_line, new_line, line[1:]))
            old_line += 1
            new_line += 1
        elif line.startswith("\\"):
            current.rows.append(DiffRow("meta", None, None, line))
    return old_name, new_name, hunks


def render(diff_path: Path, output_path: Path) -> None:
    source = diff_path.read_text()
    old_name, new_name, hunks = parse_unified_diff(source)
    additions = sum(row.kind == "added" for hunk in hunks for row in hunk.rows)
    deletions = sum(row.kind == "removed" for hunk in hunks for row in hunk.rows)
    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    hunk_titles = [
        "Results opening: establish the phenomenon, then derive the prediction",
        "Strong-coupling limits: predictions precede their numerical tests",
    ]

    sections: list[str] = []
    for index, hunk in enumerate(hunks, start=1):
        rows: list[str] = []
        for row in hunk.rows:
            sign = {"added": "+", "removed": "−", "context": "", "meta": ""}[row.kind]
            old_line = "" if row.old_line is None else str(row.old_line)
            new_line = "" if row.new_line is None else str(row.new_line)
            rows.append(
                f'<tr class="{row.kind}">'
                f'<td class="line old">{old_line}</td>'
                f'<td class="line new">{new_line}</td>'
                f'<td class="sign">{sign}</td>'
                f'<td class="code"><code>{html.escape(row.text)}</code></td>'
                "</tr>"
            )
        title = hunk_titles[index - 1] if index <= len(hunk_titles) else f"Changed block {index}"
        sections.append(
            f"""
            <section class="hunk {'page-break' if index > 1 else ''}">
              <div class="hunk-heading">
                <div>
                  <span class="eyebrow">Changed block {index} of {len(hunks)}</span>
                  <h2>{html.escape(title)}</h2>
                </div>
                <code class="hunk-range">{html.escape(hunk.header)}</code>
              </div>
              <table class="diff-table">
                <thead><tr><th>OLD</th><th>CUR</th><th></th><th>LaTeX source</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
              </table>
            </section>
            """
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Results-organization manuscript diff</title>
<style>
  :root {{
    --ink: #172033;
    --muted: #657089;
    --line: #d9dfeb;
    --paper: #ffffff;
    --canvas: #eef2f7;
    --blue: #2155a6;
    --blue-soft: #eaf1ff;
    --red: #9d1c2d;
    --red-soft: #fff0f2;
    --green: #17663a;
    --green-soft: #eaf8ef;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--canvas); color: var(--ink); font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  main {{ width: min(1500px, calc(100% - 36px)); margin: 30px auto 60px; }}
  .hero, .hunk {{ background: var(--paper); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 8px 30px rgba(26, 42, 70, .07); }}
  .hero {{ padding: 30px 34px; margin-bottom: 22px; border-top: 5px solid var(--blue); }}
  .eyebrow {{ display: block; color: var(--blue); font-size: 12px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 7px; }}
  h1 {{ font-size: 30px; line-height: 1.15; margin: 0 0 10px; }}
  h2 {{ font-size: 18px; line-height: 1.25; margin: 2px 0 0; }}
  .subtitle {{ color: var(--muted); font-size: 15px; line-height: 1.55; max-width: 960px; margin: 0; }}
  .summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-top: 22px; }}
  .card {{ padding: 14px 16px; border: 1px solid var(--line); border-radius: 10px; background: #f9fbfe; }}
  .card .value {{ display: block; font-size: 20px; font-weight: 760; margin-bottom: 3px; }}
  .card .label {{ color: var(--muted); font-size: 12px; }}
  .scope {{ margin-top: 18px; padding: 12px 15px; border-radius: 9px; background: var(--blue-soft); color: #254466; font-size: 13px; line-height: 1.5; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 15px; font-size: 12px; color: var(--muted); }}
  .swatch {{ display: inline-block; width: 12px; height: 12px; margin-right: 6px; border-radius: 3px; vertical-align: -2px; border: 1px solid rgba(0,0,0,.08); }}
  .swatch.red {{ background: var(--red-soft); }} .swatch.green {{ background: var(--green-soft); }}
  .hunk {{ margin-top: 22px; overflow: hidden; }}
  .hunk-heading {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 20px 24px 17px; border-bottom: 1px solid var(--line); }}
  .hunk-range {{ color: var(--muted); background: #f4f6fa; border: 1px solid var(--line); border-radius: 7px; padding: 7px 9px; white-space: nowrap; font-size: 11px; }}
  .diff-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  .diff-table thead {{ display: table-header-group; }}
  .diff-table th {{ position: sticky; top: 0; z-index: 1; padding: 8px 7px; text-align: left; color: var(--muted); background: #f4f6fa; border-bottom: 1px solid var(--line); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }}
  .diff-table th:nth-child(1), .diff-table th:nth-child(2), .diff-table td.line {{ width: 42px; text-align: right; }}
  .diff-table th:nth-child(3), .diff-table td.sign {{ width: 27px; text-align: center; }}
  .diff-table td {{ border-bottom: 1px solid #e9edf4; vertical-align: top; }}
  .diff-table td.line {{ color: #8b94a7; background: rgba(246,248,251,.72); border-right: 1px solid #e3e8f0; padding: 6px 6px 6px 3px; font: 10px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; user-select: none; }}
  .diff-table td.sign {{ padding: 6px 2px; font: 700 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .diff-table td.code {{ padding: 6px 10px; }}
  .diff-table code {{ display: block; white-space: pre-wrap; overflow-wrap: anywhere; font: 11px/1.48 ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}
  tr.removed td {{ background: var(--red-soft); }} tr.removed td.sign {{ color: var(--red); }}
  tr.added td {{ background: var(--green-soft); }} tr.added td.sign {{ color: var(--green); }}
  tr.context td.code {{ color: #526078; background: #fff; }}
  tr.meta td {{ color: var(--muted); background: #f7f8fb; }}
  footer {{ color: var(--muted); text-align: center; font-size: 11px; padding: 20px 0 0; }}
  @media (max-width: 760px) {{
    main {{ width: calc(100% - 16px); margin-top: 8px; }}
    .hero {{ padding: 22px 18px; }} .summary {{ grid-template-columns: repeat(2, 1fr); }}
    .hunk-heading {{ display: block; padding: 16px; }} .hunk-range {{ display: inline-block; margin-top: 10px; }}
    .diff-table code {{ font-size: 9.5px; }}
  }}
  @page {{ size: Letter landscape; margin: 0.30in; }}
  @media print {{
    body {{ background: #fff; }} main {{ width: 100%; margin: 0; }}
    .hero, .hunk {{ box-shadow: none; border-radius: 0; }}
    .hero {{ padding: 18px 20px; margin-bottom: 12px; }} h1 {{ font-size: 23px; }}
    .summary {{ margin-top: 12px; gap: 8px; }} .card {{ padding: 8px 10px; }} .card .value {{ font-size: 15px; }}
    .scope {{ margin-top: 10px; padding: 8px 10px; }} .legend {{ margin-top: 9px; }}
    .hunk {{ margin-top: 10px; }} .hunk-heading {{ padding: 9px 12px 7px; }}
    .diff-table th {{ position: static; padding: 3px 4px; }}
    .diff-table td.line {{ padding: 2px 3px; font-size: 6.7px; width: 30px; }}
    .diff-table td.sign {{ padding: 2px 1px; width: 18px; font-size: 7.4px; }}
    .diff-table td.code {{ padding: 2px 5px; }} .diff-table code {{ font-size: 7.0px; line-height: 1.24; }}
    .page-break {{ break-before: auto; }} footer {{ display: none; }}
  }}
</style>
</head>
<body>
<main>
  <section class="hero">
    <span class="eyebrow">Manuscript comparison</span>
    <h1>Current manuscript versus the earlier Results organization</h1>
    <p class="subtitle">A complete, line-numbered rendering of the source diff. Red rows belong to the earlier numerical-first organization; green rows belong to the current manuscript.</p>
    <div class="summary">
      <div class="card"><span class="value">{len(hunks)}</span><span class="label">changed blocks</span></div>
      <div class="card"><span class="value" style="color:var(--green)">+{additions}</span><span class="label">current-manuscript lines</span></div>
      <div class="card"><span class="value" style="color:var(--red)">−{deletions}</span><span class="label">earlier lines replaced</span></div>
      <div class="card"><span class="value">1</span><span class="label">Results subsection affected</span></div>
    </div>
    <div class="scope"><strong>Scope check:</strong> Philip's current Introduction is byte-identical in both files. Everything before and after the reorganized Results block is also identical; only the presentation order of the two strong-coupling mechanisms and their numerical tests changes.</div>
    <div class="legend"><span><i class="swatch red"></i>Earlier Results order ({html.escape(old_name)})</span><span><i class="swatch green"></i>Current manuscript ({html.escape(new_name)})</span><span>OLD = earlier line; CUR = current line</span></div>
  </section>
  {''.join(sections)}
  <footer>Generated {html.escape(generated)} from {html.escape(diff_path.name)}</footer>
</main>
</body>
</html>
"""
    output_path.write_text(document)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("diff", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render(args.diff, args.output)


if __name__ == "__main__":
    main()
