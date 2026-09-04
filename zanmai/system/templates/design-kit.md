# Design Kit, <brand> · <format>

The build layer for one format of one brand: block geometry and page density, the
part that genuinely changes between a flyer, a deck, a trade-show wall. Values, not
adjectives. Produced by the decompose step, consumed at build time, refined on
session close, curated (stale patterns removed, not appended around). One file per
brand × format. Store: `zanmai/design/<brand>/<format>.md`.

Colour, type, voice, imagery, shape tokens and the never-list are **not** here, 
they are brand-durable and live once in `design.md` (`design-brand` template). This
file reads them from there and holds only what is specific to this format.

Source templates: <files this format was read from>
Last refined: <date>, <one line: what changed and why>

## Page (this format), as parameters

The knobs, and only the knobs. Everything that follows from them is computed by
`document.py resolve <this file>`, which prints the text area, the column measure,
the type scale, the leading and the lines per column, and says so when the numbers
do not work: a measure too short to read, a gutter narrower than a line, more type
steps than a scale has. That is what makes a second format cheap, because A6
landscape is these few numbers changed rather than a kit written again, and every
derived value moves with them instead of being re-decided.

`--emit-typst` writes the same values as a module the build imports, so the setting
reads one source and nothing is typed twice.

```zanmai-parameters
page_width_mm: <210>
page_height_mm: <297>
margin_mm: <22>              # equal on all sides unless a template proves otherwise
margin_top_mm: <optional, when the head needs more room than the foot>
margin_bottom_mm: <optional>
columns: <1>                 # per surface type; an opening surface is rarely the body
gutter_mm: <6>
base_size_pt: <8.6>
scale_ratio: <1.25>          # each step up from the base
scale_steps: <4>
leading_ratio: <1.45>        # times the base size
spacing_unit_pt: <optional, defaults to one line of leading>
radius_mm: <2>               # from design.md, restated here so the build reads one file
```

- density budget: <how much this one surface carries before it must split to a second>
- what a number here may not be: an average of two surface types. An opening surface
  with its own column count is its own entry, not a compromise in this one.

## Blocks (the inventory)
Per block: where it sits, its box + padding, which type levels it uses (from
`design.md`), colour roles, icon slot, and what is fixed vs. what varies. These are
the Lego pieces for this format.

A single-surface piece (flyer, one-pager, poster):
- header: <logo file, position, size; background shape + colour role>
- title zone / hero: <eyebrow? headline level; subline level; accent use>
- benefit-card: <box W×H or auto; padding; title + body level; icon slot y/n; base vs. accent card>
- stats-bar: <box; how many figures; number level + label level; colour role>
- contact-block: <box; what it always contains: CTA, channels; levels>
- footer: <…>

A multi-surface document (report, guide, manual):
- cover: <how the title, subject and logo sit; column count of its own>
- section opener: <one form, carried through; label, headline, no rule unless the brand has one>
- running text: <column measure in pt or mm; paragraph spacing; how a heading meets its text>
- quote: <the forms and what picks between them>
- table: <the forms; header treatment; how a wide one is handled>
- code or fixed-width surface: <ground, width, how it differs without a second typeface>
- figure: <width options; caption level and position; radius and frame per `design.md`>
- page furniture: <folio position, running head, where they stop>

## Form ceiling (binding)
The number of forms each component may have in this format. A reader recognises
structure by repetition, so this is the line that keeps a document readable. A case
that fits none of them widens an existing form for every instance, or takes the
closest fit; a genuinely new form replaces one and the count stays.
- quote: <n>  · table: <n>  · code surface: <n>  · opener: <n>  · figure: <n>

## Set for this format, pending decision
Values this format needed that the brand has not settled. Neither invented nor
ignored: written here, used consistently, and put to the user to decide or drop.
- <value, where it is used, date set>

## Measured cost
What a run of this format actually costs, so the next one is quoted rather than
guessed. Overwritten with the latest measurement, not appended.
- per surface: <tokens>, <wall time>  · measured on <date>, <n surfaces>

## Reinterpretation notes
When a need has no matching block, build a sibling from the brand values so it reads
as one of the family. Solve a new constraint inside the brand, type over a new
full-bleed ground → a brand colour that stays legible; a wide list → two columns in
the same card look, never by dropping content or leaving the CI.
