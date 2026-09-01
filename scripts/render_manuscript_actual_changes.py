#!/usr/bin/env python3
"""Render a manuscript diff with moved/unchanged text suppressed.

Long LaTeX paragraphs make a line-level unified diff look more extensive than
the underlying edit.  This renderer pairs similar deleted/added lines, applies
word-level highlighting, collapses long unchanged spans, and lists pure moves
separately.  The complete source diff remains available in a collapsible HTML
appendix but is excluded from the print/PDF view.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import html
import re
from dataclasses import dataclass
from pathlib import Path


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
TOKEN_RE = re.compile(r"\s+|\\[A-Za-z@]+|[A-Za-z0-9_]+|.", re.DOTALL)


@dataclass(frozen=True)
class ChangedLine:
    side: str
    line: int
    text: str


def changed_lines(diff_text: str) -> tuple[list[ChangedLine], list[ChangedLine]]:
    removed: list[ChangedLine] = []
    added: list[ChangedLine] = []
    old_line = new_line = 0
    for line in diff_text.splitlines()[2:]:
        match = HUNK_RE.match(line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            continue
        if line.startswith("-"):
            text = line[1:]
            if text.strip():
                removed.append(ChangedLine("old", old_line, text))
            old_line += 1
        elif line.startswith("+"):
            text = line[1:]
            if text.strip():
                added.append(ChangedLine("new", new_line, text))
            new_line += 1
        elif line.startswith(" "):
            old_line += 1
            new_line += 1
    return removed, added


def pair_lines(
    removed: list[ChangedLine], added: list[ChangedLine], threshold: float = 0.35
) -> tuple[list[tuple[float, ChangedLine, ChangedLine]], list[ChangedLine], list[ChangedLine]]:
    candidates: list[tuple[float, int, int]] = []
    for i, old in enumerate(removed):
        for j, new in enumerate(added):
            score = difflib.SequenceMatcher(None, old.text, new.text, autojunk=False).ratio()
            if score >= threshold:
                candidates.append((score, i, j))
    used_old: set[int] = set()
    used_new: set[int] = set()
    pairs: list[tuple[float, ChangedLine, ChangedLine]] = []
    for score, i, j in sorted(candidates, reverse=True):
        if i in used_old or j in used_new:
            continue
        used_old.add(i)
        used_new.add(j)
        pairs.append((score, removed[i], added[j]))
    pairs.sort(key=lambda item: item[1].line)
    old_only = [line for i, line in enumerate(removed) if i not in used_old]
    new_only = [line for j, line in enumerate(added) if j not in used_new]
    return pairs, old_only, new_only


def shortened_equal(tokens: list[str], position: str) -> str:
    visible = [token for token in tokens if not token.isspace()]
    if len(visible) <= 24:
        return html.escape("".join(tokens))

    def keep_nonspace_from_start(count: int) -> str:
        seen = 0
        out: list[str] = []
        for token in tokens:
            out.append(token)
            if not token.isspace():
                seen += 1
            if seen >= count:
                break
        return "".join(out).rstrip()

    def keep_nonspace_from_end(count: int) -> str:
        seen = 0
        out: list[str] = []
        for token in reversed(tokens):
            out.append(token)
            if not token.isspace():
                seen += 1
            if seen >= count:
                break
        return "".join(reversed(out)).lstrip()

    if position == "start":
        return '<span class="ellipsis">…</span> ' + html.escape(keep_nonspace_from_end(15))
    if position == "end":
        return html.escape(keep_nonspace_from_start(15)) + ' <span class="ellipsis">…</span>'
    return (
        html.escape(keep_nonspace_from_start(8))
        + ' <span class="ellipsis">… unchanged …</span> '
        + html.escape(keep_nonspace_from_end(8))
    )


def word_highlight(old: str, new: str) -> tuple[str, str]:
    old_tokens = TOKEN_RE.findall(old)
    new_tokens = TOKEN_RE.findall(new)
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    opcodes = matcher.get_opcodes()
    old_html: list[str] = []
    new_html: list[str] = []
    for index, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag == "equal":
            if index == 0:
                position = "end"
            elif index == len(opcodes) - 1:
                position = "start"
            else:
                position = "middle"
            fragment = shortened_equal(old_tokens[i1:i2], position)
            old_html.append(fragment)
            new_html.append(fragment)
        else:
            if tag in {"replace", "delete"}:
                old_html.append(f'<mark class="word-old">{html.escape("".join(old_tokens[i1:i2]))}</mark>')
            if tag in {"replace", "insert"}:
                new_html.append(f'<mark class="word-new">{html.escape("".join(new_tokens[j1:j2]))}</mark>')
    return "".join(old_html), "".join(new_html)


def edit_label(old: str, new: str) -> str:
    text = old + " " + new
    labels = [
        ("\\subsection", "Subsection claim"),
        ("With the static benchmarks", "Dynamical-results opening"),
        ("Mott-side GZ dispersion", "Figure 2 caption"),
        ("CDW-side GZ dispersion", "Figure 3 caption"),
        ("In either correlated insulator", "Why the gap-interior zero exists"),
        ("we use the same signed", "Coefficient definition and analytical setup"),
        ("Inside a large gap", "Moment-expansion wording"),
        ("where $w_{h,p}", "Physical interpretation of the moment identity"),
        ("For $U\\gg t$", "Mott-limit derivation"),
        ("Because the bond is antiferromagnetic", "Mott limit: prediction before test"),
        ("At $\\tp=0$, the leading", "New NN-scale analytical setup"),
        ("\\Figdisp{fig:mott-axis} tests", "New Mott numerical-test paragraph"),
        ("\\Figdisp{fig:cdw-axis} provides", "New CDW numerical-test paragraph"),
        ("For $V\\gg t$", "CDW-limit derivation"),
        ("At $t'", "CDW leading-order argument"),
        ("\\Figdisp{fig:cdw-axis}", "CDW limit: prediction before test"),
    ]
    for needle, label in labels:
        if needle in text:
            return label
    return "Wording change"


def full_source_table(diff_text: str) -> str:
    rows: list[str] = []
    old_line = new_line = 0
    for line in diff_text.splitlines()[2:]:
        match = HUNK_RE.match(line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            rows.append(f'<tr class="range"><td colspan="4">{html.escape(line)}</td></tr>')
            continue
        if line.startswith("-"):
            rows.append(f'<tr class="removed"><td>{old_line}</td><td></td><td>−</td><td><code>{html.escape(line[1:])}</code></td></tr>')
            old_line += 1
        elif line.startswith("+"):
            rows.append(f'<tr class="added"><td></td><td>{new_line}</td><td>+</td><td><code>{html.escape(line[1:])}</code></td></tr>')
            new_line += 1
        elif line.startswith(" "):
            rows.append(f'<tr><td>{old_line}</td><td>{new_line}</td><td></td><td><code>{html.escape(line[1:])}</code></td></tr>')
            old_line += 1
            new_line += 1
    return "".join(rows)


def render(diff_path: Path, output_path: Path) -> None:
    source = diff_path.read_text()
    removed, added = changed_lines(source)
    pairs, old_only, new_only = pair_lines(removed, added)
    exact_moves = [(score, old, new) for score, old, new in pairs if score == 1.0]
    edits = [(score, old, new) for score, old, new in pairs if score < 1.0]

    edit_cards: list[str] = []
    for index, (_, old, new) in enumerate(edits, start=1):
        old_markup, new_markup = word_highlight(old.text, new.text)
        edit_cards.append(
            f"""
            <article class="edit-card">
              <header><div><span class="edit-number">EDIT {index}</span><h3>{html.escape(edit_label(old.text, new.text))}</h3></div><span class="lines">OLD {old.line} → CUR {new.line}</span></header>
              <div class="compare">
                <div class="version old"><span class="version-label">Earlier Results order</span><code>{old_markup}</code></div>
                <div class="version new"><span class="version-label">Current manuscript</span><code>{new_markup}</code></div>
              </div>
            </article>
            """
        )

    removed_cards = "".join(
        f'<article class="single old"><header><span>Removed/recast standalone passage</span><span class="lines">OLD {line.line}</span></header><code>{html.escape(line.text)}</code></article>'
        for line in old_only
    )
    added_cards = "".join(
        f'<article class="single new"><header><span>{html.escape(edit_label("", line.text)) if edit_label("", line.text) != "Wording change" else "New current-manuscript passage"}</span><span class="lines">CUR {line.line}</span></header><code>{html.escape(line.text)}</code></article>'
        for line in new_only
    )

    generated = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Actual manuscript changes</title>
<style>
:root{{--ink:#182238;--muted:#68748b;--line:#d9dfeb;--canvas:#edf2f7;--paper:#fff;--blue:#2055a6;--blue-soft:#eaf1ff;--red:#a31f34;--red-soft:#fff2f4;--green:#14663a;--green-soft:#ebf8ef;--amber:#9a6100;--amber-soft:#fff7df}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--canvas);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}} main{{width:min(1280px,calc(100% - 32px));margin:28px auto 60px}}
.hero,.section{{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 28px rgba(28,45,75,.06)}} .hero{{padding:28px 32px;border-top:5px solid var(--blue)}}
.eyebrow,.edit-number{{font-size:11px;font-weight:800;letter-spacing:.09em;text-transform:uppercase;color:var(--blue)}} h1{{font-size:29px;margin:6px 0 10px}} h2{{font-size:20px;margin:0}} h3{{font-size:15px;margin:3px 0 0}} p{{line-height:1.55}} .subtitle{{color:var(--muted);max-width:950px;margin:0}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:20px}} .metric{{padding:12px 14px;background:#f8fafd;border:1px solid var(--line);border-radius:9px}} .metric b{{display:block;font-size:20px}} .metric span{{font-size:11px;color:var(--muted)}}
.scope{{margin-top:15px;padding:11px 14px;background:var(--blue-soft);border-radius:8px;color:#284b75;font-size:13px;line-height:1.5}} .section{{margin-top:20px;padding:22px 24px}} .section-intro{{color:var(--muted);font-size:13px;margin:6px 0 17px}}
.flow{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:center;gap:10px;margin-top:17px}} .flow div{{padding:13px;border:1px solid var(--line);border-radius:9px;background:#fafbfd;text-align:center;font-size:13px;font-weight:650}} .flow .arrow{{color:var(--blue);font-weight:900}}
.move-list{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}} .move{{padding:13px 15px;background:var(--amber-soft);border:1px solid #f1d993;border-radius:9px}} .move b{{display:block;color:var(--amber);margin-bottom:4px}} .move span{{font-size:12px;line-height:1.45;color:#5f5746}}
.edit-card{{border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-top:13px}} .edit-card>header,.single>header{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:11px 14px;background:#f7f9fc;border-bottom:1px solid var(--line)}} .lines{{color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap}}
.compare{{display:grid;grid-template-columns:1fr 1fr}} .version{{padding:13px 15px;min-width:0}} .version.old{{background:var(--red-soft);border-right:1px solid var(--line)}} .version.new{{background:var(--green-soft)}} .version-label{{display:block;font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px}} .old .version-label{{color:var(--red)}} .new .version-label{{color:var(--green)}}
code{{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#596277}} mark{{padding:1px 2px;border-radius:3px;font-weight:750;color:#172033}} mark.word-old{{background:#ffc8cf;text-decoration:line-through;text-decoration-color:var(--red)}} mark.word-new{{background:#bdebc9;border-bottom:2px solid var(--green)}} .ellipsis{{color:#9aa3b2;font-style:italic}}
.single{{border:1px solid var(--line);border-radius:9px;overflow:hidden;margin-top:12px}} .single code{{display:block;padding:13px 15px}} .single.old code{{background:var(--red-soft)}} .single.new code{{background:var(--green-soft)}}
details{{margin-top:20px}} summary{{cursor:pointer;font-weight:750;color:var(--blue);padding:12px 0}} .full-table{{width:100%;border-collapse:collapse;table-layout:fixed}} .full-table td{{padding:4px;border-bottom:1px solid #e7ebf2;vertical-align:top;font:9px/1.35 ui-monospace,monospace}} .full-table td:nth-child(1),.full-table td:nth-child(2){{width:35px;text-align:right;color:#8b95a8}} .full-table td:nth-child(3){{width:20px;text-align:center}} .full-table code{{font-size:9px}} .full-table tr.removed td{{background:var(--red-soft)}} .full-table tr.added td{{background:var(--green-soft)}} .full-table tr.range td{{background:#eef3fb;color:var(--blue);font-weight:700}}
footer{{text-align:center;color:var(--muted);font-size:10px;margin-top:18px}}
@media(max-width:760px){{main{{width:calc(100% - 14px);margin-top:7px}}.hero,.section{{padding:18px 15px}}.metrics{{grid-template-columns:1fr 1fr}}.compare,.move-list{{grid-template-columns:1fr}}.version.old{{border-right:0;border-bottom:1px solid var(--line)}}.flow{{grid-template-columns:1fr}}.flow .arrow{{transform:rotate(90deg)}}}}
@page{{size:Letter landscape;margin:.30in}} @media print{{body{{background:#fff}}main{{width:100%;margin:0}}.hero,.section{{box-shadow:none;border-radius:0}}.hero{{padding:14px 16px}}h1{{font-size:21px}}.metrics{{margin-top:8px}}.metric{{padding:6px 8px}}.metric b{{font-size:14px}}.scope{{margin-top:7px;padding:6px 8px}}.section{{margin-top:8px;padding:11px 13px}}.section-intro{{margin:4px 0 10px}}.flow{{grid-template-columns:1fr auto 1fr auto 1fr;margin-top:7px}}.flow .arrow{{transform:none}}.move-list{{grid-template-columns:1fr 1fr;margin-top:7px}}.move{{padding:6px 8px}}.edit-card{{margin-top:6px;break-inside:avoid}}.edit-card>header,.single>header{{padding:4px 7px;break-after:avoid}}.compare{{grid-template-columns:1fr 1fr}}.version{{padding:5px 7px}}.version.old{{border-right:1px solid var(--line);border-bottom:0}}code{{font-size:7.5px;line-height:1.28}}.single{{break-inside:avoid;margin-top:7px}}.single code{{padding:7px 9px}}details{{display:none}}footer{{display:none}}}}
</style></head><body><main>
<section class="hero"><span class="eyebrow">Actual-change view</span><h1>What changed in the Results organization?</h1><p class="subtitle">This historical comparison records how the current manuscript reorganized the central Results narrative. Unchanged and merely relocated LaTeX is suppressed; within paired passages, only genuinely changed words are emphasized.</p>
<div class="metrics"><div class="metric"><b>{len(edits)}</b><span>word-level edits</span></div><div class="metric"><b>{len(new_only)}</b><span>new passages</span></div><div class="metric"><b>{len(old_only)}</b><span>removed/recast passage</span></div><div class="metric"><b>2</b><span>figure blocks relocated</span></div></div>
<div class="scope"><strong>Scope:</strong> Philip's Introduction is byte-identical in both versions. All differences below belong to the Results reorganization that has now been promoted to the current manuscript.</div></section>

<section class="section"><span class="eyebrow">Core structural change</span><h2>Analytical predictions now precede their numerical tests</h2><p class="section-intro">The science is unchanged; the evidentiary order is reversed so the dashed limits read as prior predictions rather than retrospective fits.</p>
<div class="flow"><div>Spectral phenomenon and existence of a zero</div><span class="arrow">→</span><div>Two-sector identity and U- and V-only predictions</div><span class="arrow">→</span><div>Figures 2 and 3 as finite-coupling tests</div></div>
<div class="move-list"><div class="move"><b>Figure 2 moved</b><span>The unchanged Mott figure wrapper and graphic move from before the derivation to immediately after the 4C<sub>NN</sub> prediction. Its caption receives a small wording change.</span></div><div class="move"><b>Figure 3 moved</b><span>The unchanged CDW figure wrapper and graphic move from the section opening to immediately after the −8/7 prediction. Its caption receives a small wording change.</span></div></div></section>

<section class="section"><span class="eyebrow">Word-level comparison</span><h2>Actual wording edits</h2><p class="section-intro">Gray text is unchanged context. Dark red strikeouts and dark green underlines identify the exact altered fragments.</p>{''.join(edit_cards)}</section>

<section class="section"><span class="eyebrow">Passage-level changes</span><h2>Text removed, recast, or newly added</h2><p class="section-intro">These passages have no sufficiently close one-line counterpart and therefore represent the substantive narrative redistribution.</p>{removed_cards}{added_cards}</section>

<section class="section full-source-section"><details><summary>Show the complete source-level diff</summary><table class="full-table"><tbody>{full_source_table(source)}</tbody></table></details></section>
<footer>Generated {html.escape(generated)} from {html.escape(diff_path.name)}; {len(exact_moves)} exact moved/scaffolding lines suppressed.</footer>
</main></body></html>"""
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
