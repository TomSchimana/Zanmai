---
name: zanmai:powerpoint
description: Native PowerPoint handling, fill a template or create new slides, fully headless (no app, no MCP). A .pptx is a ZIP of XML edited locally. Carol runs this to produce or fill decks. Native objects only; the CI lives in the master and layouts, not the theme alone.
---

# powerpoint

Handle PowerPoint natively and headless. A `.pptx` is a ZIP of XML: `ppt/theme/theme1.xml`, `ppt/slideMasters/`, `ppt/slideLayouts/`, `ppt/slides/` plus each slide's `_rels`. Work on a copy, never the original.

## CI truth: the layouts, not the theme alone

The theme can be default Office (Calibri, Office palette) while the brand lives in the master and the custom layouts: placeholder styles, background graphic, logo, set colors and fonts. Read the layouts; do not trust `theme1.xml` alone as CI. What the layouts also miss comes from the brand pack.

## The library first, composing last

A deck built slide by slide from scratch is the slow way and the drifting way at once: measured on a real run, three slides cost half an hour, and the fourth slide invented what the first had already solved. So the order is fixed, and composing is the exception.

**Harvest once.** `slide-library.py harvest <deck.pptx> --into trusted/brands/<brand>/slides/` reads a template or an approved deck and writes down, per slide, which master layout it uses, what its text slots are, and how much text each slot measurably holds (from the box and the type size in it, not from anyone's estimate). This runs when a brand's kit is first built and again whenever a deck is approved. The library is the user's own material, never a set of layouts we invented. A slide's rubrics are often laid out as a table rather than free text boxes; harvest reads a table's cells as slots too (`table1.r2c3`), not just text frames, so a template built entirely from tables still shows its real placeholders instead of reading as empty.

**Then build in three tiers, in this order.**

1. **Match.** Read the library, take the slide that already carries this shape of content, clone it, swap the text. `slide-library.py build <plan.json> <out.pptx> --library <dir>` does exactly that and refuses text that would overflow a slot rather than shrinking type to fit. Seconds per slide, and the look cannot drift because nothing is drawn. **The fastest form of Match does not even deep-copy: work on the copy of the source deck, delete every slide except the one that already carries the shape, keep that slide's own XML untouched, and only swap its text.** Verified on a real deck, 7 minutes start to finished: this skipped all position work and font-size search entirely, because the geometry stayed byte-identical to the original rather than being reconstructed by a shape-copy. The slowest part of that run was finding the right exemplar among 41 slides by eye (under two minutes); a harvested library removes that lookup, so this path gets faster still once harvest has run once.
2. **Adapt.** Nothing fits exactly: clone the closest slide, then multiply or remove an **existing** group inside it. A row of a measures band is its own four shapes; a further row is a copy of those four moved by the step two existing rows already have, measured from the file. A card too many is a deletion. Values that a source slide already carries are looked up, never chosen: the priority colours, for instance, are in that slide's own legend.
3. **Compose.** Only when nothing in the library carries it. This is the expensive tier, so it is named before the work starts, not discovered afterwards, and whatever comes out and is approved is harvested back into the library so tier one grows and tier three gets rarer.

Cloning is a deep copy of every shape element into a new slide on the same layout, so fills, connectors, pills and geometry come along exactly. Verified on a real deck: 22 shapes stay 22, with the colour rotation intact.

**A spacing constant is measured, not eyeballed or invented, and one sample is not enough.** When several existing slides share a layout, read the same corner or edge position off all of them and take the median, not the value from whichever one was opened first: a single slide can carry a one-off nudge that is not the family's real grid. This turns a guessed margin into one line of arithmetic and is the same "measured from the file" standard the library harvest already applies to text slots, extended to geometry.

## Fill

Unpack the template copy, set text in the placeholders of `slideN.xml` at run level, pack back against the original so master, theme, layouts and fonts survive. No direct formatting that overrides inherited layout values.

## Create

When tier three is the honest answer, **derive from a copy of a real deck that already carries the brand, never from an empty `Presentation()`.** Open the copy, drop the slides you don't need, and add the new one from that file's own `prs.slide_layouts`, the layout object, not a redrawn look-alike. Master, layouts, theme and fonts come along because nothing was rebuilt. Pick the layout whose purpose and placeholder set fit the content, rather than building free on a blank. What a browser-shaped instinct would draw as a table is usually already a form in the library.

Building a fresh, empty presentation and copying the CI (theme XML, measured positions) into it by hand is a fallback for when no real deck exists at all, not a shortcut when one does. It only *looks* equivalent: positions are re-measured and typed in rather than inherited, so a coordinate can be close but wrong (a placeholder and the fixed logo element next to it are easy to swap), and nothing catches that a value was read from the wrong shape. Verified on a real deck: this technique's own excuse, "the original file's unused media stay attached, bloating the copy," does not hold either. `python-pptx` only serialises parts the surviving tree still references; removing unused slides and layouts drops their exclusive media on save (measured: 486 parts down to 33, 10.4 MB down to 36 kB). There is no real cost trade-off left in favour of the transplant path.

**Check the theme fonts before trusting anything.** A master can carry a theme face the machine does not have, and then every inheriting placeholder is silently swapped: verified on a real customer template whose theme was Calibri Light and Calibri, neither installed, which is why its previews came out in a serif nobody chose. Fix the theme in the template once; until then pin the brand face per run.

**The theme is not always where the brand lives, and then hard values are correct.** Verified on a real corporate deck: `theme1.xml` was a generic Office stock design (unrelated name, Office palette, Aptos) and `theme2.xml` was blank default Office: neither carried the brand at all. The actual brand colour and face sat hard-coded in the run properties of every real slide, hundreds of times over. Reading the theme first is still right, but when the theme itself turns out to be a placeholder nobody set up, follow what the real slides actually do (hard values matching the brand pack) rather than a theme reference that would silently render Office defaults.

## Rules

- The master is never modified. Never clone a finished slide (it corrupts the file); one layout per look, add from it, fill. Derived layouts with a `1_` prefix are the copy-and-modify artifact.
- A new slide is never built in an empty `Presentation()` while a real deck carrying the brand is available. Derive from a copy of that deck, see Create.
- **Repositioning an inherited placeholder sets all four of `left`, `top`, `width`, `height`, plus `text_frame.vertical_anchor`, together, never just the values that seem to need changing.** Verified on a real deck: setting only `left` and `width` on a placeholder still inheriting its position from the layout left `top`/`height` implicit, and python-pptx wrote an `xfrm` with `off y="0" ext cy="0"`, and the title rendered pinned to the slide's top edge. There is no partial-override state that is safe to leave implicit.
- **A gap between two elements is closed by measuring, the same way a spacing constant is:** step the variable dimension (usually the type size of what sits above the gap) in small increments (0.5pt worked on a real deck) until the box's measured extent fills the space, rather than picking a plausible-looking value.
- Diagrams are native chart objects with data, never an image. Real photos are images. No imported SVG or EMF for vector content.
- Animation is not covered by this toolchain, name it, never promise it silently.

## The deck is read, not photographed

Only PowerPoint itself renders a `.pptx` faithfully; every other engine lays it out again, so a picture taken from one of those reports faults that are not there and passes ones that are. And PowerPoint's own automation needs the running app, which is the user's screen, not ours (operating-principles section 11). So there is no faithful headless render of a deck, and the measurable check does not need one: a `.pptx` is a file, and the questions worth asking are answered by reading it.

`python3 zanmai/system/scripts/design-check.py --pptx <deck.pptx> --tokens <palette.css>` reads the file and reports numbers: how many slides use a real master layout instead of a blank, empty placeholders left standing, runs that override the layout with their own face, size or colour, colours outside the palette, and whether a diagram is a chart object or a flattened picture. Red means not finished.

There is a way to see one slide without PowerPoint, and it still costs the user something, so it is not a free pass. On macOS `qlmanage -t -s 1600 -o <dir> <deck.pptx>` writes a PNG of the **first** slide in a fraction of a second, with the real fonts and exact colours. But `qlmanage` puts itself in the dock while it runs, observed, so it is visible activity on someone else's machine and falls under the same rule as an application: asked for once, with the reason, or not used (operating-principles section 11). Default is not to use it. When it is agreed: to see slide N, copy the deck, reduce the copy to that slide and render the copy, never the deliverable, and never `qlmanage -p`, which opens a window outright. Outside macOS there is no equivalent at all, and then there is no visual check to be had: say so rather than reaching for an application.

`qlmanage` is also not a complete renderer: verified on a real deck, it drew neither a shape inherited from the slide's layout nor an `outerShdw` shadow, both present and correct in the actual file and visible in LibreOffice. A slide that looks like it is missing its logo or a card's drop shadow in the preview can be complete in the file: check the XML for the inherited shape before "fixing" a preview gap by drawing a new object on top of it, which would break the inheritance that was already correct. On a large deck (real case: 7 MB) `qlmanage` can take minutes and blocks further calls to it meanwhile; budget for that or work on a slide-reduced copy as above.

**A structural check passing (renderer, XML diff, `design-check.py`) is not proof PowerPoint will open the file cleanly.** Verified on a real deck: a file that passed all three still triggered PowerPoint's own repair dialog on open. None of the headless checks model everything PowerPoint's loader validates. When a repair dialog fires: let PowerPoint repair and save the result, then diff the repaired file's XML against the pre-repair copy part by part. The diff names the exact invalid element; guessing at the cause from the outside does not.

Two confirmed causes of that same repair dialog, both worth checking directly rather than waiting for the diff: an inherited placeholder repositioned with only some of `left`/`top`/`width`/`height` set (see Create), and a shape whose hyperlink or other relationship points at a `.rels` entry that no longer exists on a deck with slides removed: the relationship, not the visible content, is what PowerPoint's loader rejects. When slides are deleted from a copy, check that no remaining shape's `_rels` reference a target that went with them.

**A clean `qlmanage` preview does not prove the deck is right.** Found on a real deck: a run inserted
after a paragraph's `a:endParaRPr` breaks the schema's element order, and PowerPoint drops that run
silently, no error, while `qlmanage` and other renderers are more tolerant and still show it. A slide
can look complete in the preview and lose half its text in PowerPoint. `slide-library.py`'s `fill`
guards against the one case this surfaced on (`TextFrame.clear()` keeps `endParaRPr`, a new run goes
in before it, never after); any other place that inserts an `a:r` by hand needs the same care.

Verified, and worth knowing before trusting a preview: a face the machine does not have is swapped for another one silently, so the render can look wrong for a reason that has nothing to do with the deck. That is why the check reports which referenced faces are actually installed.

**A text frame set to auto-fit (`spAutoFit`) can grow past the shape it sits in when PowerPoint actually renders it, and python-pptx does not notice**: it has no layout engine, so nothing at write time flags the overflow. Verified on a real deck. Before writing text into a fixed-size card or box, measure each line with the actual font and size (Pillow's `ImageFont`/`getlength` reads real metrics) and fail or shrink before writing, rather than trusting `spAutoFit` to catch it later.

The look itself goes to the user, in real PowerPoint. That is not a gap, it is the same split as everywhere: the countable part here, the taste with fresh eyes, and this deliverable is editable precisely so it opens in their own application.

## Combining several decks into one

When several files genuinely share the same master, layouts and theme (built from the same source, not just visually similar), combine them at the package level: copy each deck's own `ppt/slides/slideN.xml` and its rels into the target's ZIP and register it, rather than `python-pptx` shape-copying slides across `Presentation` objects into a common blank layout. Verified on a real case, six slides from four separately-built files: byte-identical to the originals, none of the shape-copy failure modes a blank-layout `add_slide()` would carry (it defaults to a white background that shape-copying does not restore). Confirm the shared foundation first: if the decks do not actually share master/layout/theme, this is the wrong technique and a per-slide rebuild against one chosen master is the honest path instead.

## Toolchain

Native and headless, no app in the loop: `python-pptx` for reading and for writing placeholders, layouts, tables and charts, and ooxml unpack/edit/pack where it does not reach. The real CI fonts come from the brand assets. Output goes to `doing/`.

## Learn

What a run teaches, a working idiom, an OOXML gotcha, goes into `zanmai/memory/technique/powerpoint.md`, dated and curated.
