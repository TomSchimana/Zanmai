# Design Kit, <brand> · <format>

The build layer for one format of one brand: block geometry and page density, the
part that genuinely changes between a flyer, a deck, a trade-show wall. Values, not
adjectives. Produced by the decompose step, consumed at build time, refined on
session close, curated (stale patterns removed, not appended around). One file per
brand × format. Store: `.zanmai/design/<brand>/<format>.md`.

Colour, type, voice, imagery, shape tokens and the never-list are **not** here, 
they are brand-durable and live once in `brand.md` (`design-brand` template). This
file reads them from there and holds only what is specific to this format.

Source templates: <files this format was read from>
Last refined: <date>, <one line: what changed and why>

## Page (this format)
- size: <A4 / A3 / custom mm>  (derived from the piece; see the render medium's notes)
- page margin: <pt>  (equal on all sides unless a template proves otherwise)
- inner-group gap: <pt>  (smaller than the page margin)
- density budget: <how much this one surface carries before it must split to a second>

## Blocks (the inventory)
Per block: where it sits, its box + padding, which type levels it uses (from
`brand.md`), colour roles, icon slot, and what is fixed vs. what varies. These are
the Lego pieces for this format.
- header: <logo file, position, size; background shape + colour role>
- title zone / hero: <eyebrow? headline level; subline level; accent use>
- benefit-card: <box W×H or auto; padding; title + body level; icon slot y/n; base vs. accent card>
- stats-bar: <box; how many figures; number level + label level; colour role>
- contact-block: <box; what it always contains: CTA, channels; levels>
- footer: <…>

## Reinterpretation notes
When a need has no matching block, build a sibling from the brand values so it reads
as one of the family. Solve a new constraint inside the brand, type over a new
full-bleed ground → a brand colour that stays legible; a wide list → two columns in
the same card look, never by dropping content or leaving the CI.
