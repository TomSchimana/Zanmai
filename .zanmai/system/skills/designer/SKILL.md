---
name: zanmai:designer
description: Method for designing a branded piece, let the structure follow the content, decompose the brand's templates into a concrete building-block kit, compose the new piece from that kit, and pass a fresh-eyes check against a hard checklist before delivery. Not taste written as prose; a procedure that makes the model's taste actually bind.
---

# designer

The taste is already in the model, it has seen more good and bad design than any
rulebook holds. What failed before was not missing knowledge; it was knowledge
that sat in the context as prose and never ran as a step, so the build optimized
for "done" and shipped hollow work. This file is steps, not reminders. Each step
produces or checks a concrete artifact.

## 0. Mode first, ask, do not assume
One design work-order is settled before building (Steve raises it in the dialog,
the way content facts are raised, a substance question, not a consent ritual):

- **Clone**, rebuild one template 1:1, swap only the content. Use when the user
  says copy / identical / clone / "same as this".
- **Compose**, build a new piece in the brand's language from the kit. The
  default for "make a flyer about X".

Also settle, in the same dialog: audience, purpose, and what matters to the user
for this piece. Thin answers are a real problem to name, not to pad around.

## 1. Shape the piece from the content
Before any template is opened, the structure of the piece is decided by the
**shape of the content**, not by a template's boxes. A template that was built for
other content, filled with new content, leaves boxes two-thirds empty and icons
stranded, the exact failure this step exists to prevent.

Read the content and let its shape name the structure:

- Several things measured on the same attributes → a table or aligned columns.
- Repeated items of the same internal shape (label + a line or two) → a grid of
  equal blocks, count set by the *number of items*, not by a template's slot count.
- An ordered sequence → a flow.
- Two axes → a quadrant. Events over time → a timeline. One central thing with
  satellites → a hub.

If two structures fit, take the simpler one. A grid that is really a list should
be a list.

**Density budget, split before you cram.** A single surface holds only so much
before it stops reading; a card holds one clear point, not three. When the content
exceeds what the surface carries, the answer is a second surface (a second page,
a second card row), never smaller type and tighter gaps until it fits. Two clean
pieces beat one crammed one. If the content cannot fill the surfaces the format
implies, that is a content problem to raise, not blank space to leave standing.

The output of this step is a block plan: how many blocks, of what kind, in what
structure, derived from the content, ready to carry the kit's values.

## 2. Decompose to concrete values, brand, then format
Design reads two files under `.zanmai/design/<brand>/`: `brand.md`, the durable
identity (colour, type, voice, imagery, shape tokens, the never-list; `design-brand`
template), and the per-format kit `<format>.md` (block geometry and page density;
`design-kit` template). Load what exists and add only what the newly given material
adds; both accumulate, curated, never rebuilt from zero.

If a file does not exist, build it: open every given template or CI reference (as
copies, via the render medium's field notes) and read the brand out as **concrete
values**, hex, pt, mm, never adjectives, each colour and font tagged `binding`
(read from a vector source) or `approx` (from a render, to refine later). What
repeats across the material is a brand invariant → `brand.md`; what is specific to
this format → the kit. No template and no CI reference means no brand, stop and
ask for one.

The point is fixed values, not description. "Card = 2 mm radius, #e6e6f0, title
11 pt" cannot drift mid-build the way "rounded lavender cards" can.

## 3. Compose from the kit
Build the block plan from step 1 using the kit's values from step 2.

- **Clone mode:** fill the chosen template, swap content, done.
- **Compose mode:** build from the blocks.
  - Reuse a block as-is where it fits.
  - **Reinterpret** a block when the need is new: a wide list → two columns in
    the same card look; a hero that must go full-bleed → check the kit's palette
    so the type stays legible on the new ground. Solve the new problem *inside*
    the brand, never by leaving content out or ignoring the CI.
  - New need, no block → build a new block from the kit's values so it reads as a
    sibling, and add it to the kit.
- Block count and size follow the content plan, not an inherited slot count. Every
  value comes from the kit; nothing approximated from memory. An element the
  content does not need (a leftover icon, a template's decoration) is removed, not
  left floating. Medium mechanics live in the render medium's field notes (`html`, `affinity`, `powerpoint`).

## 4. Check each render, measurable by you, taste by fresh eyes
Two different things get checked, and conflating them is what shipped bad work. The
**measurable** ones you check yourself, on the pixels of every render, this is not
the self-flattery trap, because each point is a concrete pass/fail on what is
visible, not a feeling. The **taste** ones you cannot judge for your own work (whoever
built the piece grades it too kindly, "looks 70% full" when it is 40%), so they go to
fresh eyes: the user, on a preview, early rather than at the very end.

**Measurable, you check every render; any one open fails the piece:**
- **Dead space**, a card or block more than roughly half empty.
- **Orphaned element**, an icon, marker, rule or graphic not aligned to its block,
  or present with no job (e.g. icons in one row of cards and none in the others).
- **Run-on heading**, body text jammed onto the same line as its heading.
- **Claim/structure mismatch**, a heading that names a count or shape the layout
  contradicts ("four pillars" over seven cards).
- **Hollowed slot**, a box whose content was cut to a stub to hide a fit problem.
- **Kit honoured**, equal margins, gaps on the unit, the type levels present,
  radius right, accent only where its job allows, the *never*-list respected,
  contrast legible.

Every point is pass or fail against what is on screen; "looks fine" is not a
verdict. Any fail goes back to step 3 and re-renders. A render with an open fail is
never delivered.

**Taste, fresh eyes, not yours.** Does it read as the same house as the template
renders, is the whitespace intentional and the density right for *this* format,
does it earn its restraint? This is exactly where self-grading fails, so it is not
self-certified: put an early preview in front of the user and let their reaction
steer, rather than polishing to a finish first.

## Ground floor (checked in step 4, never merely recited)
Whitespace exists · one spacing unit, equal margins · three size tiers read ·
one type system · accent has a job · brand CI outranks every rule · trends are
not taste.

## On session close
What this run taught about the brand goes back into the **kit** as updated values
or a new block, scoped to this brand × format, not as growing rule-prose.
Stale patterns the user flags as no-longer-valid are removed, not appended around.
The kit stays curated, not just larger.
