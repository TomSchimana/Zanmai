---
version: alpha
name: <brand>
description: <one line: what this brand is and what it is for>
colors:
  # `primary` is the one that must exist. The rest are the conventional roles; keep the ones the
  # brand actually has. Any CSS colour is valid (hex, rgb(), hsl(), oklch()); hex is the default.
  primary: "<#RRGGBB>"
  secondary: "<#RRGGBB>"
  tertiary: "<#RRGGBB>"
  neutral: "<#RRGGBB>"
  surface: "<#RRGGBB>"
  on-surface: "<#RRGGBB>"
  error: "<#RRGGBB>"
typography:
  # Most brands need nine to fifteen levels, not two. A level nobody pinned is a level somebody
  # invents at build time, differently each time. fontSize and lineHeight are what make a level a
  # level; letterSpacing where the brand actually sets it.
  headline-display:
    fontFamily: <family>
    fontSize: <48px>
    fontWeight: <700>
    lineHeight: <1.1>
    letterSpacing: <-0.02em>
  headline-lg:
    fontFamily: <family>
    fontSize: <32px>
    fontWeight: <700>
    lineHeight: <1.2>
  headline-md:
    fontFamily: <family>
    fontSize: <24px>
    fontWeight: <600>
    lineHeight: <1.25>
  body-lg:
    fontFamily: <family>
    fontSize: <18px>
    fontWeight: <400>
    lineHeight: <1.6>
  body-md:
    fontFamily: <family>
    fontSize: <16px>
    fontWeight: <400>
    lineHeight: <1.6>
  body-sm:
    fontFamily: <family>
    fontSize: <14px>
    fontWeight: <400>
    lineHeight: <1.5>
  label-lg:
    fontFamily: <family>
    fontSize: <14px>
    fontWeight: <600>
    lineHeight: <1.2>
  label-md:
    fontFamily: <family>
    fontSize: <12px>
    fontWeight: <600>
    lineHeight: <1.2>
    letterSpacing: <0.05em>
  caption:
    fontFamily: <family>
    fontSize: <12px>
    fontWeight: <400>
    lineHeight: <1.4>
spacing:
  # The whitespace scale, and it is not an afterthought: it is what makes a page look composed
  # rather than assembled. One base step, the scale built off it, plus the two values a layout
  # actually needs, the gap between columns and the margin around the block.
  base: <16px>
  xs: <4px>
  sm: <8px>
  md: <16px>
  lg: <32px>
  xl: <64px>
  gutter: <24px>
  margin: <32px>
rounded:
  none: <0px>
  sm: <4px>
  md: <8px>
  lg: <16px>
  full: <9999px>
components:
  # Values may reference the tokens above as `"{colors.primary}"`, so a corrected colour corrects
  # every component at once. Variants are their own key: `button-primary-hover`, `-active`.
  button-primary:
    backgroundColor: "<{colors.primary}>"
    textColor: "<{colors.on-surface}>"
    typography: "<{typography.label-lg}>"
    rounded: "<{rounded.sm}>"
    padding: <12px>
omitted: []
---

# Brand, <brand>

The durable identity of one brand, read out of its own material and kept as the single home for everything that does not change from piece to piece: how it speaks, who it speaks to, its colour and type, its whitespace, how it looks in images. Format-specific build values (block geometry, page density) live in the per-format kit beside this file; this file is what every format shares. Values, not adjectives. Curated overriding, a corrected value replaces the old one, it does not accrete beside it.

**The aim is a complete system, not a legal minimum.** Only `name` and a primary colour are strictly required, and a brand that stops there is one that gets invented at build time, differently in every piece. Empty beats guessed, so an unfilled field stays unfilled rather than being defaulted, but an unfilled field is also a job, not a resting state. Where a section genuinely does not apply, it goes in `omitted` **with a reason**, which is a decision on the record and reads differently from silence.

The block above carries the machine-readable values in the shape a coding agent expects, so a colour or a spacing step can be handed to a stylesheet without being retyped. The sections below carry what a token cannot hold: what each value is for, where it was read from, how binding that reading is, and what the brand never does.

Store: `trusted/brands/<brand>/design.md` · format kits: `trusted/brands/<brand>/<format>.md`
The kit path is fixed, so this file never points somewhere else for one. A kit that
sits next to a delivered piece leaves with it, and the next document starts from zero.
Read from: <the templates or CI document this was taken from>
Last refined: <date>, <one line: what changed and why>

## Overview
<Two or three sentences: what the brand is, the impression it should leave, whether it feels dense or spacious, plain or expressive. This is what an agent falls back on where no token answers the question.>

### Voice
- Tone: <three to five descriptors that actually narrow it, "calm but direct", not "professional">
- Audience: <one sentence, a person in a situation, not a demographic>
- Samples (the reference for any copy written for this brand):
  1. <a real sentence in the brand's voice>
  2. <a second>

## Colors
Each colour: the job it does + where it was read from + how binding that is. Confidence is `binding` (read exactly from a vector source, a logo SVG, a brand spec PDF) or `approx` (measured off a render, to be replaced when a binding source appears). A colour with no job does not belong here.
- **primary** `<#RRGGBB>`: <the signature colour and where it is earned>, read from <source>, binding|approx
- **secondary** `<#RRGGBB>`: <the quiet counterpart: headings, dark surfaces>, read from <source>, binding|approx
- **tertiary** `<#RRGGBB>`: <the accent, and how sparingly it is used>, read from <source>, binding|approx
- **neutral** `<#RRGGBB>`: <page ground>, read from <source>, binding|approx
- **surface / on-surface**: <what sits on what, and which text colour goes on each ground>
- **error**: <only where the brand actually has UI states; otherwise omit rather than repurposing the accent>

## Typography
Which family carries which role, and why. The numbers are in the block above; this is what a build cannot read off them.
- **Headlines**: <family and weight>, <the voice it gives>, read from <source>, binding|approx
- **Body**: <family and weight>, <readability intent, the measure it wants>, read from <source>, binding|approx
- **Labels**: <family>, <casing and letter spacing, where they appear>
- Where the brand's own font is not embeddable or not licensed for a medium, the substitute is named here, as a substitute.

## Layout
- **Grid**: <fluid or fixed, the maximum width text may run to>
- **Rhythm**: <the base step above, what it governs, and the half-step if one exists>
- **Density**: <generous or tight, and where that changes: cards, tables, covers>
- **Safe areas**: <what must stay clear, and what may never be placed there>

## Elevation & Depth
<How hierarchy is conveyed: shadows with their spread, blur and colour, or tonal layers, or borders alone. Where the brand is deliberately flat, say so here and say what carries the hierarchy instead. If the brand has no position on it at all, put it in `omitted` with a reason rather than leaving this section empty.>

## Shapes
- **Corner radius**: <which of the values above applies to what, and where sharp is deliberate>
- **Line weight**: <pt or px, and what draws a line at all>
- **Motifs**: <recurring geometry the brand actually uses, if any>

## Components
What recurs is built the same way every time; the values sit in the block above.
- **Buttons**: <primary, secondary, and what a hover or pressed state changes>
- **Cards / lists**: <padding, divider, what a card is for>
- **Inputs**: <label, helper text, error state, where the brand has forms>
- **Quotes, callouts, chips**: <the forms the brand's own material actually shows>
- A component the brand has never shown is not invented here; it is a question.

## Do's and Don'ts
What the brand's own material demonstrably always and never does, held as its rule until a new source proves otherwise. Read from the templates, not invented; the user may override any of it.
- Do: <e.g. one accent per surface, and it is earned>
- Do: <e.g. keep body text at 4.5:1 contrast or better against its ground>
- Don't: <e.g. no decorative rule above a heading>
- Don't: <e.g. no dash used as a sentence splitter>

## Reference pieces
A few exemplar files (paths) that show the brand at its best, the bar a new piece is measured against.
- <path or name>
