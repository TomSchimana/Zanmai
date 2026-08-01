#!/usr/bin/env python3
"""Page geometry from parameters, and honest measurements of a render.

Two halves of the same job.

`resolve` reads a format kit's parameters and works out what follows from them.
Most of a layout is arithmetic: the column measure follows from the page size, the
margins, the column count and the gutter; the type scale follows from a base size
and a ratio; the vertical rhythm follows from one unit. Writing those out by hand
per format is how a brand ends up with four one-off sizes that each got a class
name. Computed, a new format is a handful of parameters and everything else falls
out, which is the difference between "another A4 guide" and "the same brand on A6
landscape" costing the same.

It also states the one thing arithmetic can settle about taste: a line that is far
too short or far too long to read. Two columns on a small page is not a preference,
it is a measure of forty characters, and that is worth saying before anything is
built rather than after it is looked at.

`measure` reads a rendered PDF and reports coverage per column rather than per
page, because the average of a full column and an empty one is a number that hides
exactly what a reader sees first. It also checks whether a full-bleed page really
reaches all four edges, allowing for the rasteriser rounding a page up to whole
pixels, and writes a contact sheet.

`words` compares the source text against what the PDF actually contains, so "the
text is all in there" is a measurement instead of an assumption.

Nothing here decides anything about design. It computes, measures, and reports.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MM_PER_PT = 25.4 / 72.0
PT_PER_MM = 72.0 / 25.4

# 45 to 75 characters is the long-standing range for body text. The floor is the one
# a column can simply fail: below it a line is hard to read whatever the design
# intends. The ceiling sits a little above the range, because a wide measure is a
# judgement call rather than a fault.
MEASURE_MIN_CHARS = 45
MEASURE_MAX_CHARS = 90

PARAM_BLOCK = re.compile(r"```zanmai-parameters\s*\n(.*?)```", re.DOTALL)
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def read_parameters(kit: Path) -> dict:
    """Read the fenced `zanmai-parameters` block out of a kit file.

    Plain `key: value` lines so it needs no YAML library and stays readable to a
    person editing the kit. A missing block is an error rather than a default,
    because guessing a page size is how a document silently comes out wrong.
    """
    text = kit.read_text(encoding="utf-8")
    match = PARAM_BLOCK.search(text)
    if not match:
        raise SystemExit(
            f"document: no ```zanmai-parameters block in {kit}. A kit without parameters "
            "is a description, and a description cannot be built from."
        )
    params: dict = {}
    for line in match.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key, raw = key.strip(), raw.strip()
        if NUMBER.match(raw):
            params[key] = float(raw) if "." in raw else int(raw)
        elif raw.lower() in ("true", "false"):
            params[key] = raw.lower() == "true"
        else:
            params[key] = raw
    return params


REQUIRED = ("page_width_mm", "page_height_mm", "margin_mm", "columns", "base_size_pt")


def derive(params: dict) -> tuple[dict, list[str]]:
    """Everything that follows from the parameters, plus what does not add up."""
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        raise SystemExit(f"document: kit is missing {', '.join(missing)}")

    notes: list[str] = []
    width = float(params["page_width_mm"])
    height = float(params["page_height_mm"])
    margin = float(params["margin_mm"])
    margin_top = float(params.get("margin_top_mm", margin))
    margin_bottom = float(params.get("margin_bottom_mm", margin))
    columns = int(params["columns"])
    gutter = float(params.get("gutter_mm", 5))
    base = float(params["base_size_pt"])
    ratio = float(params.get("scale_ratio", 1.25))
    steps = int(params.get("scale_steps", 4))
    leading_ratio = float(params.get("leading_ratio", 1.45))
    unit = float(params.get("spacing_unit_pt", round(base * leading_ratio, 2)))

    text_width = width - 2 * margin
    text_height = height - margin_top - margin_bottom
    if text_width <= 0 or text_height <= 0:
        raise SystemExit("document: the margins leave no text area on this page size")
    column_width = (text_width - (columns - 1) * gutter) / columns

    # Characters per line, from the average advance width of a proportional face at
    # this size. 0.5 em is the usual rule of thumb and close enough to tell a
    # readable measure from an unreadable one, which is all this is for.
    chars = column_width / (base * 0.5 * MM_PER_PT)

    scale = [round(base * (ratio ** i), 2) for i in range(steps)]
    lines_per_column = int(text_height / (base * leading_ratio * MM_PER_PT))

    derived = {
        "text_width_mm": round(text_width, 2),
        "text_height_mm": round(text_height, 2),
        "column_width_mm": round(column_width, 2),
        "characters_per_line": round(chars, 1),
        "type_scale_pt": scale,
        "leading_pt": round(base * leading_ratio, 2),
        "spacing_unit_pt": unit,
        "lines_per_column": lines_per_column,
        "columns": columns,
        "gutter_mm": gutter,
    }

    if chars < MEASURE_MIN_CHARS:
        best = max(1, int(text_width / (MEASURE_MIN_CHARS * base * 0.5 * MM_PER_PT)))
        notes.append(
            f"{chars:.0f} characters per line is too short to read at {columns} column(s) on "
            f"{width:.0f} by {height:.0f} mm. At this page size and type size, {best} column(s) "
            f"is the most that reads. This is arithmetic, not taste."
        )
    elif chars > MEASURE_MAX_CHARS:
        notes.append(
            f"{chars:.0f} characters per line is a long measure. Either a second column or a "
            f"wider margin, or a larger base size."
        )
    if columns > 1 and gutter < base * MM_PER_PT:
        notes.append(
            f"the gutter ({gutter} mm) is narrower than one line of type, so the columns will "
            "read as one block of text"
        )
    if steps > 6:
        notes.append(f"{steps} type steps is not a scale any more, it is a list of sizes")
    return derived, notes


def cmd_resolve(args: argparse.Namespace) -> int:
    params = read_parameters(args.kit)
    derived, notes = derive(params)
    print(f"kit: {args.kit}")
    for key, value in params.items():
        print(f"  given    {key}: {value}")
    for key, value in derived.items():
        print(f"  derived  {key}: {value}")
    print(f"checked: {len(REQUIRED)} required parameters present, "
          f"{len(derived)} value(s) derived, {len(notes)} note(s)")
    for note in notes:
        print(f"NOTE: {note}")
    if args.emit_typst:
        lines = [
            "// Written by document.py resolve. Do not edit: change the kit's parameters",
            "// and run resolve again, so every format of this brand stays in step.",
            "#let kit = (",
        ]
        for key, value in {**params, **derived}.items():
            if isinstance(value, list):
                lines.append(f"  {key}: ({', '.join(str(v) + 'pt' for v in value)}),")
            elif isinstance(value, bool):
                lines.append(f"  {key}: {str(value).lower()},")
            elif isinstance(value, (int, float)):
                suffix = "mm" if key.endswith("_mm") else ("pt" if key.endswith("_pt") else "")
                lines.append(f"  {key}: {value}{suffix},")
            else:
                lines.append(f'  {key}: "{value}",')
        lines.append(")\n")
        args.emit_typst.write_text("\n".join(lines), encoding="utf-8")
        print(f"ok: wrote {args.emit_typst}")
    return 1 if notes and args.strict else 0


def _load_pillow():
    try:
        from PIL import Image  # noqa: PLC0415
        return Image
    except ImportError:
        raise SystemExit(
            "document: this needs Pillow, which is not in the interpreter running this script. "
            "Provision it with `zanmai.py tools ensure pillow`, then run again. Measuring nothing "
            "and reporting a pass is not an option."
        )


def _render_pages(pdf: Path, dpi: int, out_dir: Path) -> list[Path]:
    tool = shutil.which("pdftoppm")
    if not tool:
        raise SystemExit(
            "document: this needs pdftoppm (poppler) to turn the render into pixels, and it is "
            "not on this machine. Install poppler, then run again."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([tool, "-r", str(dpi), "-png", str(pdf), str(out_dir / "page")],
                   check=True, capture_output=True)
    return sorted(out_dir.glob("page-*.png"))


def _column_coverage(image, columns: int, margin_px: int, ink_threshold: int = 245):
    """How much of each column is used, and whether the page is a colour surface.

    Used, not inked. A fully set text column is only twenty to thirty percent dark
    pixels, because most of a line is the space between letters, so measuring ink
    would call every finished page empty. What a reader sees as a hole is the part of
    the column no content reaches, so the measure is the share of *lines* that carry
    anything at all. A column filled to the foot scores near a hundred whatever its
    type size, and one that stops halfway scores fifty.

    Per column rather than per page, because the mean of a full column and an empty
    one is a number that hides exactly what is noticed first: 98 and 18 average to 58
    and read as a hole.

    A page covered edge to edge is a colour surface, where the number says nothing,
    so it is reported and skipped rather than counted as a triumph.
    """
    grey = image.convert("L")
    w, h = grey.size
    pixels = grey.load()
    inner = (margin_px, margin_px, w - margin_px, h - margin_px)
    bands = []
    dark_px = 0
    all_px = 0
    band_w = (inner[2] - inner[0]) / columns
    for c in range(columns):
        x0 = int(inner[0] + c * band_w)
        x1 = int(inner[0] + (c + 1) * band_w)
        rows_total = 0
        rows_used = 0
        for y in range(inner[1], inner[3]):
            rows_total += 1
            used = False
            for x in range(x0, x1, 2):
                all_px += 1
                if pixels[x, y] < ink_threshold:
                    dark_px += 1
                    used = True
            if used:
                rows_used += 1
        bands.append(100.0 * rows_used / rows_total if rows_total else 0.0)
    flood = (100.0 * dark_px / all_px) > 90.0 if all_px else False
    return bands, flood


def cmd_measure(args: argparse.Namespace) -> int:
    Image = _load_pillow()
    work = args.work or args.pdf.parent / "measured"
    pages = _render_pages(args.pdf, args.dpi, work)
    if not pages:
        raise SystemExit("document: the render produced no pages, nothing was measured")
    margin_px = int(args.margin_mm / MM_PER_PT * (args.dpi / 72.0))
    rows = []
    failures = []
    for n, page in enumerate(pages, 1):
        with Image.open(page) as img:
            bands, flood = _column_coverage(img, args.columns, margin_px)
        mean = sum(bands) / len(bands)
        spread = max(bands) - min(bands)
        rows.append({"page": n, "columns": [round(b, 1) for b in bands],
                     "coverage": round(mean, 1), "spread": round(spread, 1),
                     "colour_surface": flood})
        if flood:
            continue
        if mean < args.fill:
            failures.append(f"page {n}: {mean:.0f} percent covered, below {args.fill:.0f}")
        if spread > args.spread:
            failures.append(
                f"page {n}: columns {', '.join(f'{b:.0f}' for b in bands)} percent, "
                f"{spread:.0f} points apart, which reads as a hole"
            )
    measured = [r for r in rows if not r["colour_surface"]]
    print(f"checked: {len(rows)} page(s) rendered at {args.dpi} dpi, {len(measured)} measured, "
          f"{len(rows) - len(measured)} colour surface(s) skipped, {args.columns} column(s) per page")
    if measured:
        worst = min(measured, key=lambda r: r["coverage"])
        avg = sum(r["coverage"] for r in measured) / len(measured)
        print(f"    mean coverage {avg:.1f} percent, worst page {worst['page']} at "
              f"{worst['coverage']:.1f} percent")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"    numbers per page written to {args.json}")
    if args.contact_sheet:
        _contact_sheet(Image, pages, args.contact_sheet)
        print(f"    contact sheet at {args.contact_sheet}")
    if not measured:
        print(f"FAIL: all {len(rows)} page(s) read as colour surfaces, so coverage was measured "
              "on none of them. Either the pages really are all colour, in which case this check "
              "has nothing to say about them, or the margin given here is wrong and the whole "
              "page is being read as content.")
        return 1
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        print(f"\n{len(failures)} open, the piece is not finished.")
        return 1
    print("\nevery page above passes.")
    return 0


def _contact_sheet(Image, pages: list[Path], out: Path, per_row: int = 6, thumb_w: int = 240) -> None:
    thumbs = []
    for page in pages:
        with Image.open(page) as img:
            ratio = thumb_w / img.width
            thumbs.append(img.resize((thumb_w, int(img.height * ratio))).convert("RGB"))
    if not thumbs:
        return
    tw, th = thumbs[0].size
    rows = (len(thumbs) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (tw + 8) + 8, rows * (th + 8) + 8), "white")
    for i, thumb in enumerate(thumbs):
        x = 8 + (i % per_row) * (tw + 8)
        y = 8 + (i // per_row) * (th + 8)
        sheet.paste(thumb, (x, y))
    sheet.save(out)


def cmd_bleed(args: argparse.Namespace) -> int:
    """Does a full-bleed page really reach all four edges?

    With one correction that matters: a rasteriser rounds a page up to whole pixels,
    so the outermost row or column is fill and reads as white whatever the PDF says.
    Reading the four corners blind therefore reports a false white edge on one side or
    another depending on resolution. So both are measured: the colour one row inside
    the edge, and how many unbroken white pixels lie between the edge and the colour.
    One pixel is the rounding; more than that is a white border in the document.
    """
    Image = _load_pillow()
    work = args.work or args.pdf.parent / "measured"
    pages = _render_pages(args.pdf, args.dpi, work)
    wanted = {int(n) for n in re.findall(r"\d+", args.pages)} or set(range(1, len(pages) + 1))
    failures = []
    checked = 0
    for n, page in enumerate(pages, 1):
        if n not in wanted:
            continue
        checked += 1
        with Image.open(page) as img:
            rgb = img.convert("RGB")
            w, h = rgb.size
            px = rgb.load()
            for name, (x, y) in (("top left", (1, 1)), ("top right", (w - 2, 1)),
                                 ("bottom left", (1, h - 2)), ("bottom right", (w - 2, h - 2))):
                r, g, b = px[x, y]
                if r > 245 and g > 245 and b > 245:
                    failures.append(f"page {n}: {name} corner is white, so it does not bleed")
            # Walk far enough in to report the real width of a white edge rather than
            # the width of the window. A margin is tens of pixels; capping the walk at
            # a handful would report "6" for every one of them and read like a
            # measurement.
            reach = max(8, min(w, h) // 4)
            for name, at in (("left", lambda i: (i, h // 2)),
                             ("right", lambda i: (w - 1 - i, h // 2)),
                             ("top", lambda i: (w // 2, i)),
                             ("bottom", lambda i: (w // 2, h - 1 - i))):
                white = 0
                for i in range(reach):
                    r, g, b = px[at(i)]
                    if r > 245 and g > 245 and b > 245:
                        white += 1
                    else:
                        break
                if white > 1:
                    where = "the whole way in" if white >= reach else f"{white} pixel(s) in"
                    failures.append(
                        f"page {n}: white {where} from the {name} edge, which is a border in "
                        "the document rather than the rasteriser rounding up"
                    )
    print(f"checked: {checked} of {len(pages)} page(s) for bleed at {args.dpi} dpi, "
          f"4 corners and 4 edges each")
    if checked == 0:
        print(f"FAIL: no page matched --pages '{args.pages}' out of {len(pages)}, so nothing was "
              "checked. A run that measured nothing is not a run that passed.")
        return 1
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        return 1
    print("\nevery page above bleeds to all four edges.")
    return 0


def cmd_words(args: argparse.Namespace) -> int:
    """Is the source text complete and unchanged in the render?

    Word by word, source with its markup stripped against what pdftotext pulls back
    out. Hyphenation at a line end is undone, quotes are normalised on both sides and
    case is ignored, because a label set in capitals is not a changed word. What is
    left is named: in the source and not in the PDF is a loss, in the PDF and not in
    the source is an addition. Both belong in the report rather than a footnote.
    """
    tool = shutil.which("pdftotext")
    if not tool:
        raise SystemExit("document: this needs pdftotext (poppler), which is not on this machine.")
    out = subprocess.run([tool, "-layout", str(args.pdf), "-"],
                         check=True, capture_output=True, text=True).stdout
    src = args.source.read_text(encoding="utf-8")
    src = re.sub(r"^---\n.*?\n---\n", "", src, flags=re.DOTALL)
    src = re.sub(r"!\[[^\]]*\]\([^)]*\)|!\[\[[^\]]*\]\]", " ", src)
    src = re.sub(r"`{1,3}[^`]*`{1,3}", " ", src)
    src = re.sub(r"[#*_>|\[\]()~]", " ", src)

    def words(text: str) -> list[str]:
        text = text.replace("­", "").replace("-\n", "")
        text = re.sub(r"[‘’‚‛]", "'", text)
        text = re.sub(r"[“”„‟]", '"', text)
        return [w for w in re.findall(r"[^\s]+", text.lower()) if any(c.isalnum() for c in w)]

    from collections import Counter
    src_words, pdf_words = Counter(words(src)), Counter(words(out))
    lost = src_words - pdf_words
    added = pdf_words - src_words
    print(f"checked: {sum(src_words.values())} word(s) in the source against "
          f"{sum(pdf_words.values())} in the render")
    if lost:
        print(f"    {sum(lost.values())} missing from the render:")
        for word, count in lost.most_common(args.show):
            print(f"      {word} ({count}x)")
    if added:
        print(f"    {sum(added.values())} present in the render and not the source:")
        for word, count in added.most_common(args.show):
            print(f"      {word} ({count}x)")
    if not lost and not added:
        print("\nthe text arrived complete and unchanged.")
        return 0
    print("\nevery difference above needs an explanation before this ships.")
    return 1 if lost and not args.tolerate_loss else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="document", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="Work out the geometry a kit's parameters imply.")
    r.add_argument("kit", type=Path)
    r.add_argument("--emit-typst", type=Path, dest="emit_typst",
                   help="Write the given and derived values as a Typst module the build imports.")
    r.add_argument("--strict", action="store_true", help="Exit non-zero when there are notes.")
    r.set_defaults(func=cmd_resolve)

    m = sub.add_parser("measure", help="Coverage per column, per page, from the render.")
    m.add_argument("--pdf", type=Path, required=True)
    m.add_argument("--columns", type=int, default=1)
    m.add_argument("--margin-mm", type=float, default=20.0, dest="margin_mm")
    m.add_argument("--fill", type=float, default=70.0, help="Minimum coverage in percent.")
    m.add_argument("--spread", type=float, default=15.0,
                   help="Largest acceptable gap between columns, in points of percent.")
    m.add_argument("--dpi", type=int, default=72)
    m.add_argument("--json", type=Path, help="Write the numbers per page here.")
    m.add_argument("--contact-sheet", type=Path, dest="contact_sheet")
    m.add_argument("--work", type=Path, help="Where to put the rendered pages.")
    m.set_defaults(func=cmd_measure)

    b = sub.add_parser("bleed", help="Does a colour page reach all four edges?")
    b.add_argument("--pdf", type=Path, required=True)
    b.add_argument("--pages", default="", help="Page numbers to check. Default: all.")
    b.add_argument("--dpi", type=int, default=72)
    b.add_argument("--work", type=Path)
    b.set_defaults(func=cmd_bleed)

    w = sub.add_parser("words", help="Is the source text complete and unchanged in the render?")
    w.add_argument("--source", type=Path, required=True)
    w.add_argument("--pdf", type=Path, required=True)
    w.add_argument("--show", type=int, default=25)
    w.add_argument("--tolerate-loss", action="store_true", dest="tolerate_loss",
                   help="Report losses without failing. For a piece that deliberately excerpts.")
    w.set_defaults(func=cmd_words)

    args = ap.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
