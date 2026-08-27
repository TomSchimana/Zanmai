---
name: zanmai:powerpoint
description: Native PowerPoint, fully headless: fill a template or build new slides. Triggers on any deck, slide or `.pptx` work. The CI lives in master and layouts.
---

# powerpoint

Handle PowerPoint natively and headless. A `.pptx` is a ZIP of XML: `ppt/theme/theme1.xml`, `ppt/slideMasters/`, `ppt/slideLayouts/`, `ppt/slides/` plus each slide's `_rels`. Work on a copy, never the original.

## CI truth: the layouts, not the theme alone

The theme can be default Office (Calibri, Office palette) while the brand lives in the master and the custom layouts: placeholder styles, background graphic, logo, set colors and fonts. Read the layouts; do not trust `theme1.xml` alone as CI. What the layouts also miss comes from the brand pack.

## The library first, composing last

A deck built slide by slide from scratch is the slow way and the drifting way at once: three slides cost half an hour, and the fourth slide invented what the first had already solved. So the order is fixed, and composing is the exception.

**Every other check asks whether what is there is right. This one asks whether something is missing.** `slide-library.py structure-check <deck> --slide N --against <pattern deck>:<slide>` counts shapes, filled areas and text places against the pattern and reports **any** difference, with no tolerance: a hub without its centre still holds six of eight areas, and the missing one is what all four lines point at. **A difference is not a fault** where it was chosen; `--intended "<why>"` records that and passes. What this catches is the shape that fell out unnoticed. Run it after every migrate and after any hand editing that follows one.

**Two checks that only look at the finished file.** `slide-library.py refs-check <deck.pptx>` reports any relationship id a slide points at that its own rels cannot resolve: that is what makes PowerPoint call a file damaged and strip the shape, while LibreOffice renders it silently without the image, so neither a render nor any other check here would show it. `slide-library.py overflow-check <deck.pptx>` reports text that wraps to a line the box has no room for, measured in the deck's own typeface at its own size, insets included. `overlap-check` cannot see that case: it compares the boxes two shapes declare, and a wrapped line lands on the shape below while the declared boxes still say the two do not touch. `overflow-check` reads table cells too, because a cell that outgrows its row pushes the rows under it down and covers their headings. Both run on the deck as written, after every build and every fill. **Both take `--baseline <original.pptx>`**, and on a Match they should: a template's own bands often overlap on purpose, and without a baseline those findings read as the build's.

**A picture is never replaced by swapping its image source.** Every `p:pic` carries its own `a:srcRect`, a crop cut for its own artwork, and icons sharing a viewBox hold different amounts of whitespace inside it. The old crop on new artwork slides the icon out of its field, visible in a render and invisible to every check, because the box never changed. `slide-library.py swap-image <deck> --shape <name> --from <deck>:<slide>:<shape> --out <new>` brings the whole picture across, crop included, and sets only the placement. The source slide has to still be in the file: once dropped, its image parts are gone. Order is swap, then drop, then fill.

**Harvest once.** `slide-library.py harvest <deck.pptx> --into trusted/brands/<brand>/slides/` reads a template or an approved deck and writes down, per slide, which master layout it uses, what its text slots are, and how much text each slot measurably holds (from the box and the type size in it, not from anyone's estimate). This runs when a brand's kit is first built and again whenever a deck is approved. The library is the user's own material, never a set of layouts we invented. A slide's rubrics are often laid out as a table rather than free text boxes; harvest reads a table's cells as slots too (`table1.r2c3`), not just text frames, so a template built entirely from tables still shows its real placeholders instead of reading as empty.

**First decide what shape this content needs, then pick a route to it.** How many things are there
and how do they stand to each other: one thing and what it brings, several of equal rank, a sequence,
a comparison, a claim and its evidence. That question is answered from the content, never from what
happens to be lying around. **The tiers below are routes to a shape already decided, not a way of
deciding it.** Read the other way round they turn into "take whatever is cheapest to reach", and a
bundle of twenty pieces then comes out as the same two patterns twenty times.

**Then build in three tiers, in this order.**

0. **Look in the brand's own library first**, `trusted/brands/<brand>/slides/`, and read its
   `INDEX.md`. Every slide there is one the user approved, so taking one and swapping its text is
   the cheapest route and the only one where the look cannot drift. Two commands, `extract` then
   `fill`, and nothing is redrawn. **What the user approves goes back in**:
   `slide-library.py keep <deck> --slide N --brand-dir trusted/brands/<brand> --as <shape-name>`
   writes the slide plus a note of its fillable places. Approval is the trigger, never the build.
   **A kept slide answers one shape of content, it is not a default.** Where the content needs a
   different shape, the library is the wrong place to look, and the cost of the right route is not
   an argument against it.

0b. **Reuse what is already in this deck.** Before the library is even opened: does a slide in the file being built already carry this shape of content? Then clone that one and swap its text. A deck of thirty battlecards is one built slide and twenty-nine copies of it, not thirty builds. This tier is new and it is the cheapest of all, because the geometry is not just approved, it is the geometry of this very deck. It also grows while the work runs: a slide composed at tier three becomes tier zero for every slide after it. Asked for one more slide after slide 10 in a deck that already holds fifty, the answer is almost never a build.

1. **Match.** Read the library, take the slide that already carries this shape of content, clone it, swap the text. `slide-library.py build <plan.json> <out.pptx> --library <dir>` does exactly that and refuses text that would overflow a slot rather than shrinking type to fit. Seconds per slide, and the look cannot drift because nothing is drawn. **The fastest form of Match does not even deep-copy: `slide-library.py extract <deck> --slides 34,14 --out <new>` lifts the slides that carry the shape out of the source deck, keeps their own XML untouched, and cuts every link into slides that did not come along.** That last part is why it is a command and not three steps by hand: deleting a navigation button's shape leaves its relationship behind, and that one link holds every part of the foreign slide alive (9.9 MB against 4.0 on a real deck, and PowerPoint calls a reference into nothing damage). Nothing is repositioned and no font size is searched, because the geometry stays byte-identical. Finding the right exemplar by eye is then the slow part, which a harvested library removes.
2. **Adapt.** Nothing fits exactly: clone the closest slide, then multiply or remove an **existing** group inside it. A row of a measures band is its own four shapes; a further row is a copy of those four moved by the step two existing rows already have, measured from the file. A card too many is a deletion. Values that a source slide already carries are looked up, never chosen: the priority colours, for instance, are in that slide's own legend.
3. **Wireframe.** The brand has nothing like it, but the neutral library does:
   `zanmai/system/templates/wireframes/` holds 57 patterns in greyscale, built on theme roles and
   theme fonts only. **A wireframe is a starting point, not a template to copy.** What it gives is a
   fast start on an arrangement, and it may be changed freely: leave parts out, add parts, rebuild
   it around the content. Using one unchanged is fine where it fits; what is not fine is treating
   what it happens to contain as settled, because then it would be a copy template and not a
   wireframe.
   **An element may be built differently where the brand takes its function away**, not only
   recoloured and rounded. A tab docked flush to a panel's top edge reads as a label pinned to it
   while the edge is straight; in a brand that rounds its corners the rounding runs underneath and
   it reads as a box stuck askew on a corner, so it becomes a free-standing centred label instead.
   What counts is what the slide says, not how
   closely it still resembles the pattern. The content is never bent to fit a pattern; the pattern
   is bent to fit the brand.
   **Every pattern carries the same frame**: a kicker over the title, the title, an optional
   emphasised claim line and an optional intro, each in the same place on all 57. The pattern
   fills only the content area under it. So slides built from different patterns line up, and the
   kicker is a slot to fill rather than something to remember. A line inside a pattern is there
   because it carries a relation, an axis, a connector, a boundary: what only marked something was
   taken out so a line that comes across in a migrate is one the arrangement needs.
   It still draws aids to show where things go, ticks, spacers, boxes standing in for a picture,
   and `migrate` brings the arrangement across including them. What comes from the wireframe is where
   things sit and in what hierarchy; what a piece is made of comes from the brand. Migrate lists the
   textless bars and markers it carried over, and each one is kept only where the brand itself uses
   that element in that role. In practice: nine 0.04 inch rules ended up in
   front of every text block in a brand whose own 74 vertical rules only ever sit between an icon
   and its text column. Formally right, wrong in its role, invisible to every geometry check.
   **`--brand-from <deck>` is where a thin or empty target gets its brand measured** (a deck built set by set starts empty, so everything measured in the target finds
   nothing and says nothing). The slide is **appended** to the target, so several patterns can be migrated
   into one deck in a row; `--replace` empties the target first, which is what this used to do
   unconditionally and what has cost a built file before. Where the target's own slides paint in
   colours its theme palette does not hold, migrate says so: mapping onto theme roles then does not
   adopt that brand, it replaces it with whatever the theme carries.
   `slide-library.py migrate <wireframes.pptx> --slide N --into <brand deck>
   --out <new>` puts the arrangement into a copy of the brand's own file, so master, layouts, logo
   and colours come from there. Minutes, not an hour, and the geometry is one that has already
   been rendered and looked at. `library.json` says per pattern what content it fits, what may
   vary and within which bounds; the preview pictures are what to show the user before building.
   **After a migrate, always `overflow-check` and `layout-check`**: a change of typeface changes
   how much every slot holds, and the target brand may have collapsed two theme roles into one
   value.
4. **Compose.** Only when nothing in the library and nothing in the wireframes carries it. This is the expensive tier, so it is named before the work starts, not discovered afterwards, and whatever comes out and is approved is harvested back into the library so tier one grows and tier three gets rarer.

**Changing the wording of a deck that already exists is not a build at all, and never a script.** `slide-library.py slots <deck.pptx>` prints every fillable place in a finished file, by the role its geometry gives it (`hub.lines2`, `card1.title`, `table1.r2c3`), with what stands there now and how much each holds. `slide-library.py fill <deck.pptx> --texts <texts.json> --out <new.pptx>` writes the new wording into those places and refuses text that does not fit rather than shrinking type. The texts file is `{"1": {"hub.lines": "..."}}` by slide number, flat for a one-slide deck. A table cell is a place like any other, addressed as `table1.r2c3`. A value can be one string, a list of strings for several paragraphs, or a list of `{"text": "...", "bold": true}` pieces for one paragraph made of several runs, which is how a rubric carries a bold objection and its plain answer together. Nothing is redrawn and nothing is cloned, so the geometry stays byte-identical. This exists because the alternative kept happening: a wording change on a finished deck was written as a purpose-built python-pptx script, twice in one bundle, and each of those is a new place for the layout to drift and a new thing to maintain. A one-off script for filling text is now a sign that the wrong route was taken.

**When the user hands over content and asks what to make of it, the shape of the content picks
the pattern, not the topic.** The question is never "what is this slide about", it is "how many
things are there and how do they relate":

- several things of the same rank → a card row; with a list each → cards with bullets
- things in an order → a path, a chevron row or a staircase, depending on whether they build
- one thing and its parts → a hub, or a claim with what carries it
- two things weighed → columns compared row by row, or a butterfly of bars
- measured values → a chart with the reading beside it, never a chart alone
- things with a state and a duration → a status table with a timeline
- one sentence that has to land → a statement slide, and nothing else on it
- real prose → two columns of text, and accept that it will be read, not presented

Each pattern in `library.json` states this in its own words under `content_fit`, including what it
is **not** for. Read that field rather than guessing from the name, show the preview, and let the
user say yes before the build. Content that fits no pattern is the honest case for Compose.

**A copied slide brings its whole history, and no geometry check sees it.** Cloning keeps the geometry, which is the point, and it also keeps the source's hard formatting, its comments, its speaker notes and its animations. Where the job is to bring content into a brand, that works against it: a copied deck can carry over a thousand hard colour values and as many hard font settings the master never asked for, and a comment written during review can reach a finished slide that way. `slide-library.py leftover-check <deck.pptx>` reports what a file carries beyond its content, and it removes nothing, because which of it belongs in a handover is a person's call.

**Where the user has named the route, that decides, not the tier order.** The order below is about cost, and cost never outranks an instruction. Asked for a pattern taken out of the neutral library and put into the brand's master, that is the job even where cloning a finished slide would be faster: the two do not produce the same thing.

**The tier is chosen per slide, never once for the job.** A set of pages is not one decision repeated. Page one may be composed, page two cloned from page one, page three migrated out of the neutral library and recoloured, page four cloned again from page two. Picking one tier at the start and holding it for twenty pages is what makes a run expensive, and it is the failure this list exists to prevent. The question is asked again at every page: what is the cheapest route to this one.

**This order is enforced, not just stated.** `slide-library.py check <library> --task <slug> --shape <pattern> --why "<one sentence>"` prints the library, lists the brand's approved slides, and records both the look and the shape decision for the `doing/<slug>/` bundle a deck belongs to. **Reusing a pattern already used in this bundle is reported, not refused**: fine where the content has the same shape, worth a second look where it does not. Several pieces of a product family legitimately look alike. Both directions have been seen: first a second piece silently took the first one's shape, then a rule against repeating sent a run looking for a different pattern for every piece whether or not it carried the content; `library-check-guard` (`zanmai.py hook`, PreToolUse Bash) refuses to save a `.pptx` into that bundle until the record exists. In practice: this exact order was skipped twice in one afternoon, straight to Compose, before anyone checked, which is where that run's whole cost went. Running the check is cheap even when Compose turns out to be the right call; the guard only proves the library was looked at, it never picks the tier.

Cloning is a deep copy of every shape element into a new slide on the same layout, so fills, connectors, pills and geometry come along exactly. In practice: 22 shapes stay 22, with the colour rotation intact.

**A spacing constant is measured, not eyeballed or invented, and one sample is not enough.** When several existing slides share a layout, read the same corner or edge position off all of them and take the median, not the value from whichever one was opened first: a single slide can carry a one-off nudge that is not the family's real grid. This turns a guessed margin into one line of arithmetic and is the same "measured from the file" standard the library harvest already applies to text slots, extended to geometry.

**A geometry correction is a call, not a rewrite.** Text sitting on other text, or two frames misaligned even though their boxes agree, is not a fresh problem each time: `slide-library.py overlap-check <deck.pptx>` and `align-check <deck.pptx>` find both, measured against the real ink (a real font file's own metrics where one can be found, not a guess), and `nudge <deck.pptx> --shape <name> --dx <in> --dy <in> --into <out.pptx>` moves one shape by a distance with all four position values set explicitly, groups regrown around it. In practice: the same correction, worked out from scratch (group-coordinate math, an "is the glyph painting past its box" check, a hand-written overlap scan with its own bugs to find), cost fifteen to nineteen minutes; called through these three, it is one command each. Deriving the geometry math again by hand is the failure this section exists to prevent, not a valid alternative when the deck already exists on disk.

## Fill

Unpack the template copy, set text in the placeholders of `slideN.xml` at run level, pack back against the original so master, theme, layouts and fonts survive. No direct formatting that overrides inherited layout values.

## Create

When tier three is the honest answer, **derive from a copy of a real deck that already carries the brand, never from an empty `Presentation()`.** Open the copy, drop the slides you don't need, and add the new one from that file's own `prs.slide_layouts`, the layout object, not a redrawn look-alike. Master, layouts, theme and fonts come along because nothing was rebuilt. Pick the layout whose purpose and placeholder set fit the content, rather than building free on a blank. What a browser-shaped instinct would draw as a table is usually already a form in the library.

Building a fresh, empty presentation and copying the CI (theme XML, measured positions) into it by hand is a fallback for when no real deck exists at all, not a shortcut when one does. It only *looks* equivalent: positions are re-measured and typed in rather than inherited, so a coordinate can be close but wrong (a placeholder and the fixed logo element next to it are easy to swap), and nothing catches that a value was read from the wrong shape. In practice: this technique's own excuse, "the original file's unused media stay attached, bloating the copy," does not hold either. `python-pptx` only serialises parts the surviving tree still references; removing unused slides and layouts drops their exclusive media on save (measured: 486 parts down to 33, 10.4 MB down to 36 kB). There is no real cost trade-off left in favour of the transplant path.

**Check the theme fonts before trusting anything.** A master can carry a theme face the machine does not have, and then every inheriting placeholder is silently swapped: verified on a real customer template whose theme was Calibri Light and Calibri, neither installed, which is why its previews came out in a serif nobody chose. Fix the theme in the template once; until then pin the brand face per run.

**The theme is not always where the brand lives, and then hard values are correct.** Verified on a real corporate deck: `theme1.xml` was a generic Office stock design (unrelated name, Office palette, Aptos) and `theme2.xml` was blank default Office: neither carried the brand at all. The actual brand colour and face sat hard-coded in the run properties of every real slide, hundreds of times over. Reading the theme first is still right, but when the theme itself turns out to be a placeholder nobody set up, follow what the real slides actually do (hard values matching the brand pack) rather than a theme reference that would silently render Office defaults.

## Rules

- The master is never modified. Never clone a finished slide (it corrupts the file); one layout per look, add from it, fill. Derived layouts with a `1_` prefix are the copy-and-modify artifact.
- A new slide is never built in an empty `Presentation()` **while a real deck carrying the brand is available**. Derive from a copy of that deck, see Create. Where there is no brand deck at all (a neutral wireframe, a first template for a vault that has none), the empty presentation is the correct start, and this rule does not apply. Stated because it was read as absolute once and cost a question that had an obvious answer.
- **Repositioning an inherited placeholder sets all four of `left`, `top`, `width`, `height`, plus `text_frame.vertical_anchor`, together, never just the values that seem to need changing.** In practice: setting only `left` and `width` on a placeholder still inheriting its position from the layout left `top`/`height` implicit, and python-pptx wrote an `xfrm` with `off y="0" ext cy="0"`, and the title rendered pinned to the slide's top edge. There is no partial-override state that is safe to leave implicit.
- **A gap between two elements is closed by measuring, the same way a spacing constant is:** step the variable dimension (usually the type size of what sits above the gap) in small increments (0.5pt worked on a real deck) until the box's measured extent fills the space, rather than picking a plausible-looking value.
- Diagrams are native chart objects with data, never an image. Real photos are images. No imported SVG or EMF for vector content.
- Animation is not covered by this toolchain, name it, never promise it silently.

## Look at the deck, and read it too

Only PowerPoint itself renders a `.pptx` exactly. That was long taken to mean there is no
useful headless render at all, and the consequence was that a deck went out having been
described rather than seen. **That consequence was wrong, and it cost the most **,
when ten faults in a freshly built library were found by looking and by nothing else: shapes
sitting on each other, a two-digit marker breaking over two lines, banding that was white on
white because the brand had put the same value on two theme roles. None of those wrap, none is
a broken reference, and none looks unusual in the XML.

`python3 zanmai/system/scripts/slide-library.py render <deck.pptx> --into <dir>` writes one
picture per slide, headless, no window, on macOS, Windows and Linux. Measured: 57 slides in
about six seconds. **Look at every slide you built, before you report it done.**

**What it answers and what it does not.** LibreOffice lays the deck out again instead of
reproducing PowerPoint, so this tells you whether the arrangement works, whether text sits in
its box and whether anything covers anything else. It does not tell you the file is
pixel-identical to what the customer will see, and three gaps are verified: a shape inherited
from the layout and an `outerShdw` can render differently, and **a font installed only for the
user is not found at all**. On macOS, LibreOffice does not read `~/Library/Fonts`: a test slide
set hard to Montserrat, Arial and Helvetica came out with Arial correct and the other two both
in a fallback serif, while `fc-match` resolved all three. So the render carries arrangement,
alignment, colour and shapes covering each other, and it carries nothing about typeface, letter
widths or where a line breaks. `overflow-check` measures the real TTF through Pillow and stays
right where the render is wrong. Neither gap weakens the questions above.

**Hidden slides are skipped by the export unless it is told otherwise, and nothing says so.**
Measured on a deck of 27 slides where 16 were hidden and 11 came out. `render` passes the
flag; anyone exporting by hand has to.

If LibreOffice is not on the machine, `render` says so and names the one command that installs
it, per platform. That is a prerequisite to report, never a reason to deliver unseen
(operating-principles section 10).

`qlmanage` on macOS remains as a second opinion for a single slide, and its limits are
unchanged: first slide only, it puts itself in the dock while it runs, so it is asked for once
with a reason or not used, and on a large deck it takes minutes.

The countable part is still read, not looked at: `refs-check`, `overflow-check`,
`overlap-check`, `align-check`, `layout-check` and `schema-check` all read the file, and a render
does not replace any of them. The render catches the class none of them can: what the arrangement
looks like once it is painted.

**And one class the render actively hides.** `slide-library.py schema-check <deck.pptx>` reports a
shape PowerPoint will not draw: `a:spPr` whose children are out of schema order, or a shape with no
position at all. PowerPoint holds a file to that order and answers a breach by dropping the
position and drawing nothing; LibreOffice is tolerant and draws it anyway. On 2026-08-27 six slides
of a finished deck were empty in PowerPoint and complete in every render and every other check.
Run it on the deck as written, before anything is handed over.

`python3 zanmai/system/scripts/design-check.py --pptx <deck.pptx> --tokens <palette.css>` reads
the file and reports numbers: how many slides use a real master layout instead of a blank,
empty placeholders left standing, runs that override the layout with their own face, size or
colour, colours outside the palette, and whether a diagram is a chart object or a flattened
picture. Red means not finished.

**A structural check passing (renderer, XML diff, `design-check.py`) is not proof PowerPoint will open the file cleanly.** In practice: a file that passed all three still triggered PowerPoint's own repair dialog on open. None of the headless checks model everything PowerPoint's loader validates. When a repair dialog fires: let PowerPoint repair and save the result, then diff the repaired file's XML against the pre-repair copy part by part. The diff names the exact invalid element; guessing at the cause from the outside does not.

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
