# Brand, <brand>

The durable identity of one brand, read out of its own material and kept as the single home for everything that does not change from piece to piece: how it speaks, who it speaks to, its colour and type, how it looks in images. Format-specific build values (block geometry, page density) live in the per-format kit beside this file; this file is what every format shares. Values, not adjectives. Curated overriding, a corrected value replaces the old one, it does not accrete beside it. Empty beats guessed: an unfilled field reads as "not yet pinned", never as a default to invent.

Store: `zanmai/design/<brand>/brand.md` · format kits: `zanmai/design/<brand>/<format>.md`
The kit path is fixed, so this file never points somewhere else for one. A kit that
sits next to a delivered piece leaves with it, and the next document starts from zero.
Read from: <the templates or CI document this was taken from>
Last refined: <date>, <one line: what changed and why>

## Voice
- Tone: <three to five descriptors that actually narrow it, "calm but direct", not "professional">
- Audience: <one sentence, a person in a situation, not a demographic>
- Samples (the reference for any copy written for this brand):
  1. <a real sentence in the brand's voice>
  2. <a second>

## Colour
Each colour: value + the job it does + confidence. Confidence is `binding` (read exactly from a vector source, a logo SVG, a brand spec PDF) or `approx` (estimated from a render, to refine when a binding source appears). A colour with no job does not belong here.
- base: `#RRGGBB`, <calm ground>, binding|approx
- structure: `#RRGGBB`, <blocks, headers>, binding|approx
- accent: `#RRGGBB`, <the few places it is earned: eyebrow, one anchor word, CTA>, binding|approx

## Type
Pinned, so no run re-guesses. Family + weights + where each is used; confidence as above.
- heading: <font> <weights>, <display, section heads>, binding|approx
- body: <font> <weights>, <copy, labels>, binding|approx

## Shape (brand-level)
- spacing unit: <pt>  (per-format margins and density live in the format kit)
- corner radius: <mm> / <fraction 0–1 for a native SDK>
- line weight: <pt>

## Imagery
- photography: <editorial / studio / candid / none>, <the look>
- illustration: <line / flat / painted / none>, <the look>
- icons: <line / filled / two-tone / none>, one family pinned: <family>

## Never (read out, not decreed)
What the brand's own material demonstrably never does, held as its rule until a new source proves otherwise. Read from the templates, not invented; the user may override any of it.
- <e.g. no decorative rule above a heading>
- <e.g. no dash used as a sentence splitter>

## Reference pieces
A few exemplar files (paths) that show the brand at its best, the bar a new piece is measured against.
- <path or name>
