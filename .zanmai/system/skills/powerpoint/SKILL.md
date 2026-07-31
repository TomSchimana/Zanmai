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

**Harvest once.** `slide-library.py harvest <deck.pptx> --into .zanmai/design/<brand>/slides/` reads a template or an approved deck and writes down, per slide, which master layout it uses, what its text slots are, and how much text each slot measurably holds (from the box and the type size in it, not from anyone's estimate). This runs when a brand's kit is first built and again whenever a deck is approved. The library is the user's own material, never a set of layouts we invented.

**Then build in three tiers, in this order.**

1. **Match.** Read the library, take the slide that already carries this shape of content, clone it, swap the text. `slide-library.py build <plan.json> <out.pptx> --library <dir>` does exactly that and refuses text that would overflow a slot rather than shrinking type to fit. Seconds per slide, and the look cannot drift because nothing is drawn.
2. **Adapt.** Nothing fits exactly: clone the closest slide, then multiply or remove an **existing** group inside it. A row of a measures band is its own four shapes; a further row is a copy of those four moved by the step two existing rows already have, measured from the file. A card too many is a deletion. Values that a source slide already carries are looked up, never chosen: the priority colours, for instance, are in that slide's own legend.
3. **Compose.** Only when nothing in the library carries it. This is the expensive tier, so it is named before the work starts, not discovered afterwards, and whatever comes out and is approved is harvested back into the library so tier one grows and tier three gets rarer.

Cloning is a deep copy of every shape element into a new slide on the same layout, so fills, connectors, pills and geometry come along exactly. Verified on a real deck: 22 shapes stay 22, with the colour rotation intact.

## Fill

Unpack the template copy, set text in the placeholders of `slideN.xml` at run level, pack back against the original so master, theme, layouts and fonts survive. No direct formatting that overrides inherited layout values.

## Create

When tier three is the honest answer, add slides from the matching master layout and fill placeholders. New native objects (charts with data, tables, shapes, text) are created programmatically and fed with the template's theme and layout values. Pick the layout whose purpose and placeholder set fit the content, rather than building free on a blank. What a browser-shaped instinct would draw as a table is usually already a form in the library.

**Check the theme fonts before trusting anything.** A master can carry a theme face the machine does not have, and then every inheriting placeholder is silently swapped: verified on a real teccle template whose theme is Calibri Light and Calibri, neither installed, which is why its previews came out in a serif nobody chose. Fix the theme in the template once; until then pin the brand face per run.

## Rules

- The master is never modified. Never clone a finished slide (it corrupts the file); one layout per look, add from it, fill. Derived layouts with a `1_` prefix are the copy-and-modify artifact.
- Diagrams are native chart objects with data, never an image. Real photos are images. No imported SVG or EMF for vector content.
- Animation is not covered by this toolchain, name it, never promise it silently.

## The deck is read, not photographed

Only PowerPoint itself renders a `.pptx` faithfully; every other engine lays it out again, so a picture taken from one of those reports faults that are not there and passes ones that are. And PowerPoint's own automation needs the running app, which is the user's screen, not ours (operating-principles section 11). So there is no faithful headless render of a deck, and the measurable check does not need one: a `.pptx` is a file, and the questions worth asking are answered by reading it.

`python3 .zanmai/system/scripts/design-check.py --pptx <deck.pptx> --tokens <palette.css>` reads the file and reports numbers: how many slides use a real master layout instead of a blank, empty placeholders left standing, runs that override the layout with their own face, size or colour, colours outside the palette, and whether a diagram is a chart object or a flattened picture. Red means not finished.

There is a way to see one slide without PowerPoint, and it still costs the user something, so it is not a free pass. On macOS `qlmanage -t -s 1600 -o <dir> <deck.pptx>` writes a PNG of the **first** slide in a fraction of a second, with the real fonts and exact colours. But `qlmanage` puts itself in the dock while it runs, observed, so it is visible activity on someone else's machine and falls under the same rule as an application: asked for once, with the reason, or not used (operating-principles section 11). Default is not to use it. When it is agreed: to see slide N, copy the deck, reduce the copy to that slide and render the copy, never the deliverable, and never `qlmanage -p`, which opens a window outright. Outside macOS there is no equivalent at all, and then there is no visual check to be had: say so rather than reaching for an application.

Verified, and worth knowing before trusting a preview: a face the machine does not have is swapped for another one silently, so the render can look wrong for a reason that has nothing to do with the deck. That is why the check reports which referenced faces are actually installed.

The look itself goes to the user, in real PowerPoint. That is not a gap, it is the same split as everywhere: the countable part here, the taste with fresh eyes, and this deliverable is editable precisely so it opens in their own application.

## Toolchain

Native and headless, no app in the loop: `python-pptx` for reading and for writing placeholders, layouts, tables and charts, and ooxml unpack/edit/pack where it does not reach. The real CI fonts come from the brand assets. Output goes to `_export/`.

## Learn

What a run teaches, a working idiom, an OOXML gotcha, goes into `.zanmai/memory/technique/powerpoint.md`, dated and curated.
