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

`harvest` writes `index.json` and a readable `index.md` describing each slide:
which master layout it uses, what its slots are, and how much text each slot
actually holds, measured from the box and the type size that is in it rather than
declared by anyone. That measurement is what lets a later build refuse content
that would overflow, instead of producing a slide nobody looks at twice.

`build` takes a plan naming a source slide per target slide plus the text per
slot, clones the source and swaps the text. `show` prints the library so an agent
can choose.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

try:
    from pptx import Presentation
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
        target = None
        for shape in slide.shapes:
            if shape.has_text_frame and text_of(shape) == live[name]["text"]:
                target = shape
                break
        if target is None:
            problems.append(f"slot '{name}' could not be located in the copy")
            continue
        paragraphs = target.text_frame.paragraphs
        template_run = None
        for paragraph in paragraphs:
            if paragraph.runs:
                template_run = paragraph.runs[0]
                break
        if template_run is None:
            problems.append(f"slot '{name}' carries no styled run to follow")
            continue
        keep = copy.deepcopy(template_run._r)
        keep_paragraph = copy.deepcopy(paragraphs[0]._p)
        frame = target.text_frame
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
            paragraph._p.append(run_element)
            paragraph.runs[-1].text = str(line)
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

    args = ap.parse_args(argv[1:])
    if args.command == "harvest":
        if not args.deck.is_file():
            print(f"slide-library: no deck at {args.deck}", file=sys.stderr)
            return 2
        return harvest(args.deck, args.into)
    if args.command == "build":
        return build(args.plan, args.out, args.library, strict=not args.loose)
    return show(args.library, args.slide)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
