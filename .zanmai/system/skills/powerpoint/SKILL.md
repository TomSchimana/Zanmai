---
name: zanmai:powerpoint
description: Native PowerPoint handling, fill a template or create new slides, fully headless (no app, no MCP). A .pptx is a ZIP of XML edited locally. Carol runs this to produce or fill decks. Native objects only; the CI lives in the master and layouts, not the theme alone.
---

# powerpoint

Handle PowerPoint natively and headless. A `.pptx` is a ZIP of XML: `ppt/theme/theme1.xml`, `ppt/slideMasters/`, `ppt/slideLayouts/`, `ppt/slides/` plus each slide's `_rels`. Work on a copy, never the original.

## CI truth: the layouts, not the theme alone

The theme can be default Office (Calibri, Office palette) while the brand lives in the master and the custom layouts: placeholder styles, background graphic, logo, set colors and fonts. Read the layouts; do not trust `theme1.xml` alone as CI. What the layouts also miss comes from the brand pack.

## Fill

Unpack the template copy, set text in the placeholders of `slideN.xml` at run level, pack back against the original so master, theme, layouts and fonts survive. No direct formatting that overrides inherited layout values.

## Create

Add new slides from the matching master layout, then fill placeholders. New native objects (charts with data, tables, shapes, text) are created programmatically and fed with the template's theme and layout values. Pick the layout whose purpose and placeholder set fit the content, rather than building free on a blank.

## Rules

- The master is never modified. Never clone a finished slide (it corrupts the file); one layout per look, add from it, fill. Derived layouts with a `1_` prefix are the copy-and-modify artifact.
- Diagrams are native chart objects with data, never an image. Real photos are images. No imported SVG or EMF for vector content.
- Review the render against the `designer` skill. Animation is not covered by this toolchain, name it, never promise it silently.

## Toolchain

Technique adopted natively, no third-party skill installed: native object creation for create mode, ooxml unpack/edit/pack for fill mode. Node and a headless renderer plus the real CI fonts are provisioned by the environment. Output goes to `_export/`.

## Learn

What a run teaches, a working idiom, an OOXML gotcha, goes into `.zanmai/memory/technique/powerpoint.md`, dated and curated.
