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

**The medium is chosen by what gives the best result for this piece, never by what
is easiest to drive.** That is not a preference, it is the lesson from a 62-page
document that went to a browser because a browser is easy to script, and came out
with 22 pages half empty. So ask what the piece has to be able to do, and let the
answer pick:

- Anything paged, from a birthday card to a manual, is set with `typst`. Real flow
  across pages, a block that does not fit deferred instead of leaving a hole,
  hyphenation, folios, colour to the edge.
- **A single set surface goes to `powerpoint`, whatever its page size.** A one-page
  flyer, a one-pager, a poster, a card: A4 is a slide size like any other, and the PDF
  comes out of the same export. **The first reason belongs to the user: the file stays
  editable.** A PDF out of `typst` is finished, and a change means coming back here; a
  `.pptx` opens on their own machine and they change the word themselves. `affinity`
  would keep that property but cannot yet be driven to build a piece like this. The
  second reason is the measuring: `slide-library.py` checks overflow, overlap, alignment,
  broken references, type size and margins on the finished file, and no other medium here
  has any of that.
  **The line is not "flyer versus document", it is whether the layout is set or the text
  flows.** Set means every element has its place and the text is written to fit: that is
  this route. Flowing means the text decides where the breaks fall, which starts at about
  two pages and is `typst`'s job. Built as a one-page flyer in PowerPoint 2026-08-25 and
  delivered as a PDF, which is what raised the question.
- A piece a person will keep editing by hand, or a real press run with an exact
  colour profile and crop marks, goes to `affinity`; an editable presentation to
  `powerpoint`.
- `html` is for a deliverable that is itself a web page.

If the medium the piece needs is not on the machine, that is a prerequisite to
report, not a reason to quietly take the second best (operating-principles section
10). Taking the easier tool and working around what it cannot do is how a
workaround catalogue grows instead of a document getting better.

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
Design reads two files under `trusted/brands/<brand>/`: `design.md`, the durable
identity (colour, type, voice, imagery, shape tokens, the never-list; `design-brand`
template), and the per-format kit `<format>.md` (block geometry, page density and
the form ceiling; `design-kit` template). Load what exists and add only what the
newly given material adds; both accumulate, curated, never rebuilt from zero.

**Those two paths are the only place a kit lives.** A kit written next to the
deliverable on the desk is not a kit, it is a file that gets carried off with the
piece, and the next document starts from nothing again. So the kit is written under
`trusted/brands/<brand>/` before the piece is built, and the build reads it from
there.

**Between the brand's own pieces and composing from nothing there is a third source: the
neutral wireframe library** (`zanmai/system/templates/wireframes/`, 58 patterns). Greyscale
slides that use theme roles and theme fonts only, never a literal value, so taking one into a
brand is a theme swap rather than a rebuild: `slide-library.py migrate <deck> --slide N --into
<brand.pptx> --out <new.pptx>` puts the arrangement into a copy of the brand's own file, where
master, layouts, logo and theme come from. Each pattern carries what it is for in plain words
(`content_fit`), what may vary and within which bounds (`flex`), and a preview picture, so a
pattern is chosen by what the content is, not by what a name suggests.

**What `migrate` reports rather than silently fixing, all three measured 2026-08-26 on a real
brand:** literal colours that came across (only a person can say which role a `#2E86AB` stood
for); a change of body face, because a wider face means every slot holds less (Montserrat runs
16% wider than Arial, so a slot holds 13% less and text that fitted before does not); and two
theme roles carrying the same value, which silently removes a distinction the wireframe made.
After every migrate, run `overflow-check` and `layout-check` on the result.

**Where the brand already has finished pieces, they are part of the kit.** A template or an
approved deck is harvested into `trusted/brands/<brand>/slides/` (`slide-library.py harvest`),
which writes down per slide what it is, its text slots, and how much each slot measurably holds.
A new piece then starts by taking the one that already carries this shape of content and
swapping the text, and only composes where nothing fits. That is both the cheap path and the one
that cannot drift, and what gets approved joins the library, so it grows.

**The kit is the truth; the build file is one realization of it.** `<format>.md`
holds values and forms, which belong to no medium. Beside it sits what the chosen
medium actually reads, `<format>.css` for a browser, `<format>.typ` for Typst. So a
brand is not married to the tool its first piece happened to use: a second
realization is a translation of the same truth, and both are checked by the same
script. No kit for this brand and format yet means building one is the first step of
the job, not an optional extra; a piece set without one is the failure this step
exists to prevent.

If a file does not exist, build it: open every given template or CI reference (as
copies, via the render medium's field notes) and read the brand out as **concrete
values**, hex, pt, mm, never adjectives, each colour and font tagged `binding`
(read from a vector source) or `approx` (from a render, to refine later). What
repeats across the material is a brand invariant → `design.md`; what is specific to
this format → the kit. No template and no CI reference means no brand, stop and
ask for one.

The point is fixed values, not description. "Card = 2 mm radius, #e6e6f0, title
11 pt" cannot drift mid-build the way "rounded lavender cards" can.

**Most of a layout is arithmetic, so it is computed and not decided.** The kit holds
the knobs, page size, margins, column count, gutter, base size, scale ratio, leading,
radius, in one `zanmai-parameters` block. `document.py resolve <kit>` works out what
follows: text area, column measure, type scale, leading, lines per column, and it
says so when the numbers cannot work, a measure too short to read, a gutter narrower
than a line, more steps than a scale has. Run it before building, not after: two
columns on a small page is a forty-character line, which is arithmetic rather than
taste, and the cheapest place to learn that is before the first render. `--emit-typst`
hands the same values to the setting, so nothing is typed twice.

This is also what makes the second format cheap. A6 landscape is these few numbers
changed and everything derived moving with them, not a kit written again. What is
genuinely not computable, whether a radius carries at a small size, where a caption
sits, stays a judgement: take the computed value as the default, and where you
override it, say why in the kit.

**The form ceiling is part of the kit, and it binds.** Each component (quote, table,
code surface, opener, figure) carries a fixed number of forms, and the kit names it.
Sorting content across many forms by an explicit rule feels like craftsmanship and
reads as arbitrariness: a reader recognises structure by repetition, so five kinds of
quote in one document means there is no quote form at all. When a case fits none of
the existing forms, widen a form so every existing instance moves with it, or take
the closest fit. A new form enters the kit only in place of another, and the count
stays where the kit put it. Where the kit has a machine-readable CSS form, the
ceiling is declared in it as one comment line, so `design-check.py` can hold the
build to it:
`/* zanmai-kit: quote=q- 2, table=t- 2 */` plus `/* zanmai-sizes: 4 */`.

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

## 4. Prove the look, then spend the effort
A piece of more than a handful of surfaces is not finished in one go. A designer
shows a few surfaces, gets a decision, and only then does the rest of the work.
Which surfaces those are depends on whether they stand alone, and getting that
wrong makes the whole step incoherent.

**Surfaces that stand alone** (a flyer, a deck, a card series): pick five at most,
the ones that decide the look rather than the prettiest. The opening surface, a
plain one carrying ordinary content, and the two or three hardest cases this content
brings (the widest table, the longest quote, an image that must run full width).
Build those and stop.

**A continuous document** (a guide, a report, a manual) cannot be proved that way,
and pretending otherwise wastes the step. Page breaks are global: what sits on page
27 follows from everything before it, so five hand-picked pages are either not real
pages, or everything ahead of them had to be built anyway. What is expensive here is
also not the building and not the rendering, which is seconds for sixty pages. It is
the polishing loop afterwards. So: build the whole thing once, deliberately
unpolished, render all of it, run the check, and stop there. The user then sees real
pages out of the real flow, with their real numbers, and a contact sheet of every
page so the shape of the whole is visible rather than five excerpts. Their answer
changes the kit, and re-rendering everything is one command.

The mistake to avoid is not "built too much", it is "polished before anyone looked".

The return is the gate. It carries the proof renders (for a continuous document the
contact sheet as well), the check output as it came, not as a summary of it, what the
kit now fixes, the cost figures the build itself can see (surfaces done, wall time,
what is left), and one question: does this look carry the rest? What a run has spent in
tokens is not visible from inside it, it is reported to whoever dispatched the run,
so the estimate for the remaining surfaces is theirs to do, and the number comes back
with the go, to be written into the kit then. A subagent cannot ask the user mid-run,
and it does not need to; the open point rides up in the return and the run is
continued on the answer, with the kit and the decisions still in context (Steve keeps
the dispatch warm). What comes back as "almost, but" is answered by changing the kit,
not by hand-tuning the surface it was noticed on.

Whoever ordered the piece owns the go. Setting the remaining surfaces before it
arrives is the same mistake as skipping the proof.

## 5. Check each render, measurable by you, taste by fresh eyes
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
- **Surface filled or deliberately open**, a page that runs out of content halfway
  is a fault, not a measurement. Say what fills it (an image the material already
  holds, a surface fewer) rather than reporting a percentage.
- **Nothing split that reads as one thing**, a box, quote or figure that begins in
  one column and ends in the next.
- **Everything the file needs travels inside it**, every face embedded, every image
  placed rather than linked. A document that only names its font is right on the
  machine it was built on and wrong in the hands it was made for, and nothing about
  that is visible from here. A piece that cannot be handed on is not a deliverable.

The ones a script can decide are decided by a script, not by looking. Four
measurements on the render, each answering a question a look cannot:

- `document.py measure --pdf <render> --columns <n>`: coverage **per column**, not per
  page. The mean over a page cannot see an empty column, and a page that is 98 percent
  full on the left and 18 on the right measures 58 and reads as a hole. It reports the
  worst page, skips colour surfaces where the number means nothing, and writes a
  contact sheet of every page.
- `document.py words --source <md> --pdf <render>`: is the text complete and unchanged?
  Word by word against what the PDF actually contains, hyphenation undone and case
  ignored. Every difference gets named rather than assumed away.
- `document.py bleed --pdf <render> --pages <n,n>`: does a colour page really reach all
  four edges? Measured one row inside the edge as well as at it, because a rasteriser
  rounds a page up to whole pixels and the outermost line is fill, so reading the
  corners blind reports a false white edge.
- `design-check.py <kit> --tokens <palette> --pdf <render>`
counts the forms per component against the kit's ceiling, finds colour and size
values that are in neither the brand file nor the kit, verifies that every font is
embedded, flags container forms with no break-inside guard, and measures how much of
each rendered page is covered. It takes the kit as CSS or as Typst. Run it on the
proof and again before delivery, and read its numbers: a check that could not run
says so instead of passing. Red means not finished, whatever the piece looks like.

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
**A hand-correction to the delivered file is ported back into whatever produced it**
before the piece counts as done: the build script, the template, the kit value it
should have read. A fix that lives only in the delivered copy is not a fix, it is one
correct file sitting next to a generator that still makes the old mistake, and the
next run from that generator brings the mistake back. Verified failure: a user's own
correction to a rendered deck (wrong type size, a line that would not go away) never
reached the script that built it; the next build from that script, on the user's own
explicit instruction to rebuild, silently reintroduced both.

What this run taught about the brand goes back into the **kit** as updated values
or a new block, scoped to this brand × format, not as growing rule-prose.
Stale patterns the user flags as no-longer-valid are removed, not appended around.
The kit stays curated, not just larger. The measured cost per surface is written
there too, so the next piece of this kind is quoted from a number instead of a guess.

A value the piece needed and the brand had not decided is a third state, neither
settled nor open: it is recorded in the kit as set for this format and pending the
user's decision, and it goes into the return so they can settle it. Left only in the
piece, the same question gets answered differently every time.
