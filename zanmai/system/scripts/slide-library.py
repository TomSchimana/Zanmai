#!/usr/bin/env python3
"""A brand's own slides as a library: harvest what exists, then fill copies of it.

The expensive way to make a deck is to compose every slide from scratch, and it
is also the way that drifts: the fourth slide invents what the first one already
solved. The cheap way is the one a designer uses, which is to take the slide that
already carries this shape of content and put the new content in it. Nothing is
drawn, so nothing can drift, and a slide costs seconds.

What this does not do is ship a fixed set of layouts. A brand's look is not ours
to prescribe, so the library is read out of the material the user already has,
their template and their approved decks, and it grows as they approve more.

    slide-library.py harvest <deck.pptx> --into <library-dir>
    slide-library.py build <plan.json> <out.pptx> --library <library-dir>
    slide-library.py show <library-dir> [--slide <id>]
    slide-library.py check <library-dir> --task <slug>
    slide-library.py nudge <deck.pptx> --shape <name> --dx <in> --dy <in> --into <out.pptx>
    slide-library.py overlap-check <deck.pptx> [--slide <n>]
    slide-library.py align-check <deck.pptx> [--slide <n>]

`harvest` writes `index.json` and a readable `index.md` describing each slide:
which master layout it uses, what its slots are, and how much text each slot
actually holds, measured from the box and the type size that is in it rather than
declared by anyone. That measurement is what lets a later build refuse content
that would overflow, instead of producing a slide nobody looks at twice.

`build` takes a plan naming a source slide per target slide plus the text per
slot, clones the source and swaps the text. `show` prints the library so an agent
can choose. `check` does the same and additionally records that the library was
looked at for a given piece of work (`--task`, the `doing/<slug>/` bundle this
deliverable belongs to): `library-check-guard` (PreToolUse Bash, see
`zanmai.py hook`) refuses to save a `.pptx` under that bundle until this has run
at least once, so composing from scratch is a choice made after looking, not
instead of it.

`nudge` and `overlap-check` are for the other kind of change: a correction, not a build. Found
2026-08-25 on a real Carol run: a text block sat over its card's background numeral, a fix any
person makes by dragging the box in PowerPoint in ten seconds, and it cost fifteen minutes because
the group-coordinate math, the "does the glyph paint past its box" check (`wrap="none"` at a large
point size does exactly that) and the pairwise overlap check were re-derived from nothing, in a
freshly written script that then needed its own debugging. `nudge` moves one shape by a delta and
sets all four xfrm values explicitly, `overlap-check` finds text-over-text pairs the same way, ink
rather than the box where `wrap="none"` makes the box lie. Both work on shapes nested in groups: a
group's own frame is grown to keep containing what moved, the way `gruppe_nachziehen` did by hand.

`align-check` is the same "box lies about the ink" pattern found a second time the same day, at the
other edge: a title and a body text sitting on the identical box-left value can still read as
mis-aligned, because a large bold face and a small regular face carry different left side bearings.
Both checks measure the real ink where they can, loading the actual font file (matched by name in the
standard font folders) and reading its own metrics, not a guess about where letters typically start.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.oxml.ns import qn
    from pptx.util import Emu
except ImportError:
    sys.exit("slide-library: python-pptx is missing. Provision it first (tools ensure python_pptx).")

EMU_PER_INCH = 914400
# Characters per square inch of text box at 12 pt, calibrated against the
# reference build so its own slides sit at roughly half their capacity: a card
# title box of 2.57 x 0.96 inch at 18 pt carries about 46 characters and holds 40
# today. Coarse on purpose, it only has to tell "fits" from "will overflow", and
# it is calibrated rather than guessed because a number nobody measured would let
# every overflow through.
CHAR_DENSITY = 42.0


def inches(value) -> float:
    return round((value or 0) / EMU_PER_INCH, 3)


def text_of(shape) -> str:
    return shape.text_frame.text.strip() if shape.has_text_frame else ""


def sizes_in(shape) -> list[float]:
    sizes = []
    if not shape.has_text_frame:
        return sizes
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.font.size is not None:
                sizes.append(run.font.size.pt)
    return sizes


def capacity(shape) -> int:
    """How many characters this box carries at the size its own text uses. A slot
    with no text yet falls back to the deck's body size, which is the honest
    answer rather than a guess dressed as a number."""
    size = max(sizes_in(shape) or [12.0])
    area = inches(shape.width) * inches(shape.height)
    return int(area * CHAR_DENSITY * (12.0 / size) ** 2)


def cell_sizes(cell) -> list[float]:
    sizes = []
    for paragraph in cell.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.font.size is not None:
                sizes.append(run.font.size.pt)
    return sizes


def cell_capacity(cell, width_emu, height_emu) -> int:
    """Same formula as `capacity()`, for a table cell rather than a shape: a cell has no
    `.width`/`.height` of its own, those live on the table's column and row."""
    size = max(cell_sizes(cell) or [12.0])
    area = inches(width_emu) * inches(height_emu)
    return int(area * CHAR_DENSITY * (12.0 / size) ** 2)


def contains(outer, inner) -> bool:
    return (outer.left <= inner.left and outer.top <= inner.top
            and outer.left + outer.width >= inner.left + inner.width
            and outer.top + outer.height >= inner.top + inner.height)


def slot_names(slide) -> dict:
    """Name every text-bearing shape by the role its geometry gives it.

    The grouping is what makes a library usable: a card is a filled box with text
    boxes sitting inside it, so the boxes belong to that card and get its number,
    left to right. Within a group the largest type is the title and the rest is
    the body. No naming convention in the source file is required, which matters
    because the source is the user's own deck, not something we authored."""
    frames = [s for s in slide.shapes if s.has_text_frame and text_of(s)]
    containers = [s for s in slide.shapes if not s.has_text_frame or not text_of(s)]
    containers = [s for s in containers if s.width and s.height]

    groups: dict[int, list] = {}
    loose = []
    for frame in frames:
        holder = None
        for index, container in enumerate(containers):
            if contains(container, frame):
                if holder is None or (containers[holder].width * containers[holder].height
                                      > container.width * container.height):
                    holder = index
        if holder is None:
            loose.append(frame)
        else:
            groups.setdefault(holder, []).append(frame)

    slots: dict[str, dict] = {}

    def add(name, shape):
        slots[name] = {
            "text": text_of(shape),
            "capacity": capacity(shape),
            "lines": len([p for p in shape.text_frame.paragraphs if p.text.strip()]),
            "size_pt": max(sizes_in(shape) or [0]) or None,
            "box": [inches(shape.left), inches(shape.top), inches(shape.width), inches(shape.height)],
        }

    for shape in sorted(loose, key=lambda s: (s.top or 0, s.left or 0)):
        if shape.is_placeholder and shape.placeholder_format.idx == 0:
            add("title", shape)
        else:
            add(f"text{sum(1 for k in slots if k.startswith('text')) + 1}", shape)

    ordered = sorted(groups.items(), key=lambda kv: (containers[kv[0]].top or 0, containers[kv[0]].left or 0))
    rows: dict[float, list] = {}
    for holder, members in ordered:
        rows.setdefault(round(inches(containers[holder].top), 1), []).append((holder, members))
    for row_index, (top, entries) in enumerate(sorted(rows.items()), start=1):
        entries.sort(key=lambda kv: containers[kv[0]].left or 0)
        prefix = "hub" if len(entries) == 1 and row_index == 1 else "card"
        for column, (holder, members) in enumerate(entries, start=1):
            name = prefix if prefix == "hub" else f"{prefix}{column}"
            members.sort(key=lambda s: -(max(sizes_in(s) or [0])))
            for position, member in enumerate(members):
                add(f"{name}.title" if position == 0 else f"{name}.lines{position if position > 1 else ''}", member)

    # A template's rubrics are often laid out as a table rather than free text boxes; a table's
    # cells carry no `has_text_frame`, so they are invisible to everything above this point. Found
    # 2026-08-24: a real Battlecard template was entirely tables, and harvest reported only a title
    # and a bar, which read as "no placeholders here" and was wrong.
    table_index = 0
    for shape in slide.shapes:
        if not getattr(shape, "has_table", False):
            continue
        table_index += 1
        table = shape.table
        row_tops = []
        top = shape.top or 0
        for row in table.rows:
            row_tops.append(top)
            top += row.height or 0
        col_lefts = []
        left = shape.left or 0
        for column in table.columns:
            col_lefts.append(left)
            left += column.width or 0
        for r in range(len(table.rows)):
            for c in range(len(table.columns)):
                cell = table.cell(r, c)
                if cell.is_spanned or not cell.text_frame.text.strip():
                    continue
                width = table.columns[c].width or 0
                height = table.rows[r].height or 0
                slots[f"table{table_index}.r{r + 1}c{c + 1}"] = {
                    "text": cell.text_frame.text.strip(),
                    "capacity": cell_capacity(cell, width, height),
                    "lines": len([p for p in cell.text_frame.paragraphs if p.text.strip()]),
                    "size_pt": max(cell_sizes(cell) or [0]) or None,
                    "box": [inches(col_lefts[c]), inches(row_tops[r]), inches(width), inches(height)],
                }
    return slots


def harvest(deck_path: Path, into: Path) -> int:
    deck = Presentation(str(deck_path))
    into.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, slide in enumerate(deck.slides, start=1):
        slots = slot_names(slide)
        fills = []
        for shape in slide.shapes:
            try:
                if shape.fill.type == 1:
                    value = str(shape.fill.fore_color.rgb).lower()
                    if value not in fills:
                        fills.append(value)
            except Exception:  # noqa: BLE001
                pass
        repeated = sorted({re.sub(r"\d+", "", k.split(".")[0]) for k in slots if "." in k})
        entries.append({
            "id": number,
            "layout": slide.slide_layout.name,
            "title": slots.get("title", {}).get("text", ""),
            "shapes": len(slide.shapes),
            "groups": {kind: len({k.split(".")[0] for k in slots if k.startswith(kind)}) for kind in repeated},
            "fills": fills,
            "slots": slots,
        })

    index = {"source": str(deck_path), "slides": entries}
    (into / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["# Slide library", "",
             f"Harvested from `{deck_path.name}`. Every slide here is one the user has approved, so a new",
             "piece starts by taking the one that already carries this shape of content, not by composing.",
             "The capacity per slot is measured from the box and the type size in it, so a slot that would",
             "overflow is refused at build time rather than delivered.", ""]
    for entry in entries:
        groups = ", ".join(f"{count}x {kind}" for kind, count in entry["groups"].items()) or "no repeated group"
        lines.append(f"## Slide {entry['id']}: {entry['title'] or '(no title)'}")
        lines.append(f"Layout `{entry['layout']}` · {entry['shapes']} shapes · {groups}")
        lines.append("")
        lines.append("| slot | holds | now | at |")
        lines.append("|---|---|---|---|")
        for name, slot in entry["slots"].items():
            lines.append(f"| `{name}` | {slot['capacity']} chars | {len(slot['text'])} chars, "
                         f"{slot['lines']} lines | {slot['size_pt'] or '-'} pt |")
        lines.append("")
    (into / "index.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"harvested {len(entries)} slides into {into}")
    for entry in entries:
        groups = ", ".join(f"{count}x {kind}" for kind, count in entry["groups"].items()) or "-"
        print(f"  {entry['id']:>3}  {entry['title'][:44]:<44} {groups}")
    return 0


def clone(deck, source):
    """A copy of one slide, shape for shape. Same layout, then every element of
    the source deep-copied in, so fills, connectors, pills and geometry come along
    exactly. Nothing is redrawn, which is the whole point."""
    new = deck.slides.add_slide(source.slide_layout)
    for shape in list(new.shapes):
        shape._element.getparent().remove(shape._element)
    for shape in source.shapes:
        new.shapes._spTree.append(copy.deepcopy(shape._element))
    return new


_TABLE_SLOT = re.compile(r"^table(\d+)\.r(\d+)c(\d+)$")


def _locate_slot_frame(slide, name: str, template_text: str):
    """The text frame a slot name resolves to in this (cloned) slide: a table cell, addressed by
    position since cell text need not be unique, or a shape, addressed by matching its current text
    against what harvest recorded, exactly as before tables were slots too."""
    table_match = _TABLE_SLOT.match(name)
    if table_match:
        wanted_table, row, col = (int(g) for g in table_match.groups())
        seen = 0
        for shape in slide.shapes:
            if not getattr(shape, "has_table", False):
                continue
            seen += 1
            if seen == wanted_table:
                return shape.table.cell(row - 1, col - 1).text_frame
        return None
    for shape in slide.shapes:
        if shape.has_text_frame and text_of(shape) == template_text:
            return shape.text_frame
    return None


def _fill_text_frame(frame, lines: list) -> str | None:
    """Replace a text frame's content with `lines`, one paragraph per line, keeping the template's
    own run formatting. Returns an error string, or None on success."""
    paragraphs = frame.paragraphs
    template_run = None
    for paragraph in paragraphs:
        if paragraph.runs:
            template_run = paragraph.runs[0]
            break
    if template_run is None:
        return "carries no styled run to follow"
    keep = copy.deepcopy(template_run._r)
    keep_paragraph = copy.deepcopy(paragraphs[0]._p)
    frame.clear()
    for index, line in enumerate(lines):
        if index == 0:
            paragraph = frame.paragraphs[0]
        else:
            new_p = copy.deepcopy(keep_paragraph)
            for run in new_p.findall(
                    "{http://schemas.openxmlformats.org/drawingml/2006/main}r"):
                new_p.remove(run)
            frame._txBody.append(new_p)
            paragraph = frame.paragraphs[-1]
        run_element = copy.deepcopy(keep)
        end_para_rpr = paragraph._p.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}endParaRPr")
        if end_para_rpr is not None:
            # A run appended after endParaRPr breaks the schema's element order; PowerPoint
            # then drops the run silently, no error, while a more tolerant renderer still
            # shows it. TextFrame.clear() keeps endParaRPr on the first paragraph, so this
            # is the common case, not the rare one.
            end_para_rpr.addprevious(run_element)
        else:
            paragraph._p.append(run_element)
        paragraph.runs[-1].text = str(line)
    return None


def fill_slots(slide, texts: dict, slots: dict, strict: bool) -> list[str]:
    """Put the new text in, addressed by slot name, and report what does not fit.
    Overflow is a refusal rather than a smaller type size: shrinking to fit is how
    a deck stops looking like the slide it was copied from."""
    problems = []
    live = slot_names(slide)
    for name, value in texts.items():
        if name not in live:
            problems.append(f"no slot '{name}' on this slide (has: {', '.join(sorted(live))})")
            continue
        lines = value if isinstance(value, list) else [value]
        room = slots.get(name, live[name])["capacity"]
        length = sum(len(str(line)) for line in lines)
        if length > room:
            problems.append(f"slot '{name}' holds {room} characters, the new text has {length}")
            if strict:
                continue
        frame = _locate_slot_frame(slide, name, live[name]["text"])
        if frame is None:
            problems.append(f"slot '{name}' could not be located in the copy")
            continue
        error = _fill_text_frame(frame, lines)
        if error:
            problems.append(f"slot '{name}' {error}")
    return problems


def build(plan_path: Path, out: Path, library: Path, strict: bool) -> int:
    index = json.loads((library / "index.json").read_text(encoding="utf-8"))
    source_deck = Path(index["source"])
    if not source_deck.is_file():
        print(f"slide-library: the harvested deck is gone from {source_deck}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    slides = plan.get("slides") or []
    if not slides:
        print("slide-library: the plan holds no slide", file=sys.stderr)
        return 2

    deck = Presentation(str(source_deck))
    sources = list(deck.slides)
    keep = set(plan.get("keep") or [])
    problems: list[str] = []

    for step, wanted in enumerate(slides, start=1):
        source_id = wanted.get("from")
        entry = next((e for e in index["slides"] if e["id"] == source_id), None)
        if entry is None:
            print(f"slide-library: plan step {step} names slide {source_id}, which is not in the library",
                  file=sys.stderr)
            return 2
        new = clone(deck, sources[source_id - 1])
        found = fill_slots(new, wanted.get("texts") or {}, entry["slots"], strict)
        problems += [f"step {step} ({wanted.get('name', 'unnamed')}): {p}" for p in found]

    # the harvested deck's own slides go, unless the plan keeps some
    xml_slides = deck.slides._sldIdLst
    for position, slide_id in enumerate(list(xml_slides)[:len(sources)], start=1):
        if position in keep:
            continue
        rId = slide_id.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        deck.part.drop_rel(rId)
        xml_slides.remove(slide_id)

    out.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(out))
    print(f"built {len(slides)} slides into {out}")
    if problems:
        print()
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"\n{len(problems)} open. Shorten the text or pick a slide that carries it.")
        return 1
    return 0


def show(library: Path, slide_id: int | None) -> int:
    index = json.loads((library / "index.json").read_text(encoding="utf-8"))
    for entry in index["slides"]:
        if slide_id and entry["id"] != slide_id:
            continue
        groups = ", ".join(f"{count}x {kind}" for kind, count in entry["groups"].items()) or "-"
        print(f"\nSlide {entry['id']}: {entry['title'] or '(no title)'}  [{entry['layout']}, {groups}]")
        for name, slot in entry["slots"].items():
            print(f"   {name:<16} holds ~{slot['capacity']:>4} chars   now {len(slot['text']):>4}   "
                  f"{slot['size_pt'] or '-'} pt")
    return 0


def check(library: Path, task: str, vault_root: Path) -> int:
    """Print the library, same as `show`, and record that it was looked at for `task`
    (a `doing/<slug>/` bundle). `library-check-guard` reads this record back, so what it
    proves is that a Compose build happened after a look at the library, not instead of
    one, and it does not judge whether Compose was the right call, only that the cheap
    tiers were on the table when it was made."""
    result = show(library, None)
    marker_dir = vault_root / "zanmai" / "temp" / task
    marker_dir.mkdir(parents=True, exist_ok=True)
    index = json.loads((library / "index.json").read_text(encoding="utf-8"))
    marker = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "library": str(library),
        "slides_seen": len(index["slides"]),
    }
    (marker_dir / "library-checked.json").write_text(
        json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nrecorded: {task} looked at {marker['slides_seen']} slide(s) in {library}")
    return result


def _shape_paths(shapes, prefix="", parents=()):
    """(path, shape, parents) for every shape in the tree, depth-first. `path` is the
    slash-joined chain of names down to this shape, which is what `--shape` accepts when
    a bare name repeats across sibling groups (a template's repeated cards do, verified on
    a real deck where every card's text box was named "Rectangle 63"). `parents` is the
    chain of enclosing group shapes, outermost first, which is what a caller needs to
    convert a slide-space distance into this shape's own coordinate units."""
    for sh in shapes:
        path = f"{prefix}/{sh.name}"
        yield path, sh, parents
        if sh.shape_type == 6:
            yield from _shape_paths(sh.shapes, path, parents + (sh,))


def _find_shape(deck, wanted: str, slide_no: int | None):
    """Every (slide_index, path, shape, parents) matching `wanted`, by full path first,
    then by bare name. Ambiguous or missing is the caller's problem to report, not a guess
    made here: picking the wrong one of several identically named cards is worse than an
    error that names every candidate."""
    slides = [(slide_no, deck.slides[slide_no - 1])] if slide_no else list(enumerate(deck.slides, start=1))
    hits = []
    for index, slide in slides:
        candidates = list(_shape_paths(slide.shapes))
        exact = [(index, p, sh, parents) for p, sh, parents in candidates if p in (wanted, "/" + wanted)]
        hits += exact or [(index, p, sh, parents) for p, sh, parents in candidates if sh.name == wanted]
    return hits


def _group_scale(group) -> tuple[float, float]:
    """(sx, sy): how one unit in this group's own child space maps to one unit in the
    space its own xfrm is expressed in (its parent group's child space, or slide space for
    a top-level group)."""
    xfrm = group._element.grpSpPr.xfrm
    ext, chExt = xfrm.find(qn("a:ext")), xfrm.find(qn("a:chExt"))
    cx, cy = int(chExt.get("cx")), int(chExt.get("cy"))
    return (int(ext.get("cx")) / cx if cx else 1.0,
            int(ext.get("cy")) / cy if cy else 1.0)


def _regroup(group) -> None:
    """After a descendant moved, keep this group's frame exactly containing its direct
    children: recompute chOff/chExt as their union in this group's own child space, and
    grow off/ext by the same amount so the scale to its own parent stays fixed. Without
    this a child that moved outside the old frame is silently clipped or rescaled by
    PowerPoint, which trusts chOff/chExt rather than re-measuring its children."""
    kids = [k for k in group.shapes if k.left is not None]
    if not kids:
        return
    new_x = min(k.left for k in kids)
    new_y = min(k.top for k in kids)
    new_w = max(k.left + k.width for k in kids) - new_x
    new_h = max(k.top + k.height for k in kids) - new_y

    xfrm = group._element.grpSpPr.xfrm
    off, ext = xfrm.find(qn("a:off")), xfrm.find(qn("a:ext"))
    chOff, chExt = xfrm.find(qn("a:chOff")), xfrm.find(qn("a:chExt"))
    sx, sy = _group_scale(group)

    off.set("x", str(int(off.get("x")) + round((new_x - int(chOff.get("x"))) * sx)))
    off.set("y", str(int(off.get("y")) + round((new_y - int(chOff.get("y"))) * sy)))
    ext.set("cx", str(round(new_w * sx)))
    ext.set("cy", str(round(new_h * sy)))
    chOff.set("x", str(new_x))
    chOff.set("y", str(new_y))
    chExt.set("cx", str(new_w))
    chExt.set("cy", str(new_h))


def nudge(deck_path: Path, wanted: str, dx_in: float, dy_in: float, slide_no: int | None, out: Path) -> int:
    deck = Presentation(str(deck_path))
    hits = _find_shape(deck, wanted, slide_no)
    if not hits:
        print(f"slide-library: no shape '{wanted}' on {'slide ' + str(slide_no) if slide_no else 'any slide'}",
              file=sys.stderr)
        return 2
    if len(hits) > 1:
        print(f"slide-library: '{wanted}' is not unique, qualify with its full path:", file=sys.stderr)
        for index, path, _, _ in hits:
            print(f"  slide {index}: {path}", file=sys.stderr)
        return 2

    index, path, shape, parents = hits[0]
    sx, sy = 1.0, 1.0
    for group in parents:
        gsx, gsy = _group_scale(group)
        sx *= gsx
        sy *= gsy
    dx_emu = round(dx_in * EMU_PER_INCH / sx)
    dy_emu = round(dy_in * EMU_PER_INCH / sy)

    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    shape.left, shape.top, shape.width, shape.height = left + dx_emu, top + dy_emu, width, height
    for group in reversed(parents):
        _regroup(group)

    out.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(out))
    print(f"slide {index}: moved {path} by {dx_in:+.3f}in / {dy_in:+.3f}in -> {out}")
    return 0


CHAR_WIDTH_EM = 0.52
# Average glyph advance as a fraction of point size, calibrated against the reference
# build's bold numerals, the case that actually painted past its own box. Coarse like
# CHAR_DENSITY above, and for the same reason: it only has to tell "still fits" from
# "paints past its box", not predict a layout engine exactly. Used only where the real
# font file below cannot be found -- a fallback, not the primary measurement.


def _painted_width(char_count: int, size_pt: float, bold: bool) -> int:
    per_char = (size_pt / 72.0) * EMU_PER_INCH * (CHAR_WIDTH_EM + (0.05 if bold else 0.0))
    return round(char_count * per_char)


def _font_file(family: str, bold: bool) -> Path | None:
    """A real font file for `family`, matched by filename in the standard font folders
    (same list `installed_font_families()` in design-check.py scans, one level further:
    a file, not just a name), closest weight to `bold` preferred. None means no match on
    this machine; callers fall back to the calibrated estimate rather than fail."""
    roots = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts",
             Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts"]
    fam_key = re.sub(r"[^a-z0-9]", "", family.lower()) if family else ""
    if not fam_key:
        return None
    candidates = []
    for root in roots:
        if not root.is_dir():
            continue
        for file in root.rglob("*"):
            if file.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            if re.sub(r"[^a-z0-9]", "", file.stem.lower()).startswith(fam_key):
                candidates.append(file)
    if not candidates:
        return None
    variant_markers = ("italic", "narrow", "condensed", "rounded", "unicode", "oblique")
    plain = [f for f in candidates if not any(m in f.stem.lower() for m in variant_markers)] or candidates
    if bold:
        # A literal "bold" not preceded by "extra"/"semi" is the correct match for a plain bold
        # request. "Black" is not: on this machine "Arial Black" is a distinct shipped family,
        # not a weight of "Arial", so treating a name match on "black" as "Arial, but bold" picked
        # the wrong file entirely -- found while building this function, not assumed away.
        exact = [f for f in plain if re.search(r"(?<!extra)(?<!semi)bold", f.stem.lower())]
        if exact:
            return min(exact, key=lambda f: len(f.stem))
        for keyword in ("black", "heavy", "extrabold", "semibold"):
            matches = [f for f in plain if keyword in f.stem.lower()]
            if matches:
                return min(matches, key=lambda f: len(f.stem))
    weight_markers = ("bold", "black", "light", "thin", "medium", "semibold", "extrabold", "heavy")
    unweighted = [f for f in plain if not any(m in f.stem.lower() for m in weight_markers)]
    return min(unweighted or plain, key=lambda f: len(f.stem))


def _real_ink_bbox(text: str, family: str | None, size_pt: float, bold: bool):
    """(left_bearing_in, width_in) of `text` set in this exact font file at this exact
    size, not an average -- the same "measured, not eyeballed" standard `capacity()`
    already applies to a slot's character count, extended to where the ink itself sits.
    None if Pillow is missing, the family cannot be resolved to a file, or the file
    fails to parse: an unmeasured run is left to the calibrated fallback, never guessed
    into a false positive or a false clean."""
    if not family or not text:
        return None
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    path = _font_file(family, bold)
    if path is None:
        return None
    try:
        font = ImageFont.truetype(str(path), size=max(1, round(size_pt)))
        left, _top, right, _bottom = font.getbbox(text)
    except Exception:  # noqa: BLE001 -- a font file that fails to parse falls back, it does not crash the check
        return None
    return left / 72.0, (right - left) / 72.0


def _leaf_rects(shapes, tf=(1.0, 0.0, 1.0, 0.0)):
    """(shape, (left, top, width, height) in slide EMU) for every text-bearing leaf, groups
    resolved through their own scale and offset so a card's children compare against a
    sibling card's in one shared coordinate space, not each in its own group's raw units."""
    ax, bx, ay, by = tf
    out = []
    for sh in shapes:
        if sh.shape_type == 6:
            sx, sy = _group_scale(sh)
            xfrm = sh._element.grpSpPr.xfrm
            off, chOff = xfrm.find(qn("a:off")), xfrm.find(qn("a:chOff"))
            nested = (ax * sx, ax * (int(off.get("x")) - int(chOff.get("x")) * sx) + bx,
                      ay * sy, ay * (int(off.get("y")) - int(chOff.get("y")) * sy) + by)
            out += _leaf_rects(sh.shapes, nested)
            continue
        if sh.left is None or not sh.has_text_frame or not text_of(sh):
            continue
        out.append((sh, (ax * sh.left + bx, ay * sh.top + by, ax * sh.width, ay * sh.height)))
    return out


def _painted_rect(shape, rect):
    """Widen `rect` to the glyph's real ink where `wrap="none"` lets the run paint past its
    own box. Verified on a real deck: an 80pt digit box sized for two characters still
    painted a three-character run, and the saved bounding box said nothing overlapped."""
    body_pr = shape.text_frame._txBody.find(qn("a:bodyPr"))
    if body_pr is None or body_pr.get("wrap") != "none":
        return rect
    left, top, width, height = rect
    widest = width
    for paragraph in shape.text_frame.paragraphs:
        length = sum(len(r.text) for r in paragraph.runs)
        if not length:
            continue
        size = max((r.font.size.pt for r in paragraph.runs if r.font.size), default=12.0)
        bold = any(r.font.bold for r in paragraph.runs)
        family = next((r.font.name for r in paragraph.runs if r.font.name), None)
        run_text = "".join(r.text for r in paragraph.runs)
        real = _real_ink_bbox(run_text, family, size, bold)
        if real is not None:
            widest = max(widest, round(real[1] * EMU_PER_INCH))
        else:
            widest = max(widest, _painted_width(length, size, bold))
    return (left, top, widest, height)


def _ink_left_offset(shape) -> int | None:
    """How far this shape's first line actually starts painting from its own box's
    left edge, in EMU. None where that cannot be measured (no run, no named font, no
    matching file on this machine) -- such a shape is left out of `align_check` rather
    than assumed aligned or assumed not."""
    for paragraph in shape.text_frame.paragraphs:
        if not paragraph.runs:
            continue
        run = paragraph.runs[0]
        if not run.text.strip() or not run.font.size:
            return None
        real = _real_ink_bbox(run.text, run.font.name, run.font.size.pt, bool(run.font.bold))
        if real is None:
            return None
        return round(real[0] * EMU_PER_INCH)
    return None


def align_check(deck_path: Path, slide_no: int | None) -> int:
    """Two text frames whose boxes sit on the same left edge can still read as
    misaligned: a large bold face and a small regular face rarely share the same left
    side bearing, so their ink starts at different points even though the boxes agree
    exactly (found on a real deck, a title and its body text). Boxes within 0.02in are
    treated as "meant to align"; among those, ink-left positions more than 0.02in apart
    are reported. A shape whose ink cannot be measured is left out of its group, never
    silently counted as aligned."""
    deck = Presentation(str(deck_path))
    slides = [(slide_no, deck.slides[slide_no - 1])] if slide_no else list(enumerate(deck.slides, start=1))
    tolerance = round(0.02 * EMU_PER_INCH)
    problems = []
    groups_checked = 0
    for index, slide in slides:
        leaves = _leaf_rects(slide.shapes)
        leaves = sorted(leaves, key=lambda pair: pair[1][0])
        groups: list[list] = []
        for sh, rect in leaves:
            for group in groups:
                if abs(group[0][1][0] - rect[0]) <= tolerance:
                    group.append((sh, rect))
                    break
            else:
                groups.append([(sh, rect)])
        for group in groups:
            if len(group) < 2:
                continue
            measured = [(sh, rect[0] + offset) for sh, rect in group
                        if (offset := _ink_left_offset(sh)) is not None]
            if len(measured) < 2:
                continue
            groups_checked += 1
            for i in range(len(measured)):
                sh_a, left_a = measured[i]
                for j in range(i + 1, len(measured)):
                    sh_b, left_b = measured[j]
                    if abs(left_a - left_b) > tolerance:
                        problems.append(
                            "slide %d: '%s' and '%s' share a box-left edge but their ink starts "
                            "%.3f inch apart"
                            % (index, text_of(sh_a)[:20], text_of(sh_b)[:20], Emu(abs(left_a - left_b)).inches))
    for problem in problems:
        print(f"FAIL: {problem}")
    print(f"{groups_checked} shared-edge group(s) checked, {len(problems)} misalignment(s)")
    return 1 if problems else 0


def overlap_check(deck_path: Path, slide_no: int | None) -> int:
    deck = Presentation(str(deck_path))
    slides = [(slide_no, deck.slides[slide_no - 1])] if slide_no else list(enumerate(deck.slides, start=1))
    problems = []
    pairs = 0
    for index, slide in slides:
        leaves = [(sh, _painted_rect(sh, rect)) for sh, rect in _leaf_rects(slide.shapes)]
        for i in range(len(leaves)):
            sh_a, (la, ta, wa, ha) = leaves[i]
            for j in range(i + 1, len(leaves)):
                sh_b, (lb, tb, wb, hb) = leaves[j]
                pairs += 1
                ox = min(la + wa, lb + wb) - max(la, lb)
                oy = min(ta + ha, tb + hb) - max(ta, tb)
                if ox > 0 and oy > 0:
                    problems.append(
                        "slide %d: '%s' over '%s', %.3f x %.3f inch"
                        % (index, text_of(sh_a)[:24], text_of(sh_b)[:24], Emu(ox).inches, Emu(oy).inches))
    for problem in problems:
        print(f"FAIL: {problem}")
    print(f"{pairs} pair(s) checked on {len(slides)} slide(s), {len(problems)} overlap(s)")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Harvest a brand's own slides, then fill copies of them.")
    sub = ap.add_subparsers(dest="command", required=True)

    ph = sub.add_parser("harvest", help="read a deck and write the library index")
    ph.add_argument("deck", type=Path)
    ph.add_argument("--into", type=Path, required=True)

    pb = sub.add_parser("build", help="clone slides from the library and fill them")
    pb.add_argument("plan", type=Path)
    pb.add_argument("out", type=Path)
    pb.add_argument("--library", type=Path, required=True)
    pb.add_argument("--loose", action="store_true",
                    help="write text that exceeds a slot's capacity anyway, still reported")

    ps = sub.add_parser("show", help="print the library so a slide can be chosen")
    ps.add_argument("library", type=Path)
    ps.add_argument("--slide", type=int)

    pc = sub.add_parser("check", help="print the library and record that it was looked at for a task")
    pc.add_argument("library", type=Path)
    pc.add_argument("--task", required=True,
                     help="the doing/<slug>/ bundle this deliverable belongs to")
    pc.add_argument("--vault", type=Path, default=Path.cwd(),
                     help="vault root the task's zanmai/temp/ lives under (default: cwd)")

    pn = sub.add_parser("nudge", help="move one shape by a delta, all four xfrm values set explicitly")
    pn.add_argument("deck", type=Path)
    pn.add_argument("--shape", required=True, help="shape name, or full slash path when the name repeats")
    pn.add_argument("--dx", type=float, default=0.0, help="inches, positive is right")
    pn.add_argument("--dy", type=float, default=0.0, help="inches, positive is down")
    pn.add_argument("--slide", type=int, help="1-based; default searches every slide, errors if ambiguous")
    pn.add_argument("--into", type=Path, required=True)

    po = sub.add_parser("overlap-check", help="pairwise text-over-text check, ink-aware for wrap=none")
    po.add_argument("deck", type=Path)
    po.add_argument("--slide", type=int, help="1-based; default checks every slide")

    pa = sub.add_parser("align-check", help="ink-left alignment between text frames sharing a box-left edge")
    pa.add_argument("deck", type=Path)
    pa.add_argument("--slide", type=int, help="1-based; default checks every slide")

    args = ap.parse_args(argv[1:])
    if args.command == "harvest":
        if not args.deck.is_file():
            print(f"slide-library: no deck at {args.deck}", file=sys.stderr)
            return 2
        return harvest(args.deck, args.into)
    if args.command == "build":
        return build(args.plan, args.out, args.library, strict=not args.loose)
    if args.command == "check":
        return check(args.library, args.task, args.vault)
    if args.command in ("nudge", "overlap-check", "align-check") and not args.deck.is_file():
        print(f"slide-library: no deck at {args.deck}", file=sys.stderr)
        return 2
    if args.command == "nudge":
        return nudge(args.deck, args.shape, args.dx, args.dy, args.slide, args.into)
    if args.command == "overlap-check":
        return overlap_check(args.deck, args.slide)
    if args.command == "align-check":
        return align_check(args.deck, args.slide)
    return show(args.library, args.slide)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
