# Changelog

All notable changes to Zanmai. Format: <https://keepachangelog.com>. Versioning: semver. The 0.x
series is pre-stable, which means a folder name or a command can still change between versions, and
when it does, it will say so here.

## [0.4.1] - 2026-08-26

**Every dispatch to an expert was refused on the first try. `dispatch-guard` checks that a handover
carries two labelled blocks and looks for the heading `What the user said:` literally, but no skill
that dispatches ever said so, and neither did Steve's contract. The rule lived in one place nobody
reads at the moment of dispatch. Found in the field on the first real `/zanmai-update` after the
guard existed: the handover was a version pair, the guard turned it back, and the turn was spent
twice.**

### Fixed

- **The four skills that dispatch an expert now name the two blocks where the dispatch is
  described**, with the exact headings the guard checks for: `update`, `research`, `voice` and
  `manage-connections`. `update` carries the whole handover as a template, because there it is
  always the same two lines and there is nothing to interview about.
- **Steve's routing says the headings are literal**, not a matter of style. His contract described
  passing the user's ask in their own words, which is the right instruction and does not tell anyone
  that a specific wording is checked.

## [0.4.0] - 2026-08-26

**A deck was built by describing it, never by looking at it. That was not a habit but a rule: the
skill said no headless render is faithful, so nobody rendered, and faults that only a picture shows
went out unseen. This version turns that around. `render` writes a picture of every slide on any
platform, and the first time it ran against a freshly built set of 58 slides it found ten faults
that every existing check had reported clean. Alongside it comes a library of 58 neutral wireframes,
a way to put one of them into a brand's own deck, and three checks for faults that are about where
a shape sits rather than what is in it.**

### Added

- **A wireframe library: 58 neutral slide patterns** in `zanmai/system/templates/wireframes/`.
  Greyscale, built on theme roles and theme fonts only, never a literal colour or typeface, so
  taking one into a brand is a theme swap rather than a rebuild. Each pattern says in plain words
  what content it fits and what it is **not** for, what may vary and within which bounds, and comes
  with a preview picture. They cover what a master never provides: card rows, paths, chevrons,
  pyramids, funnels, matrices, status tables with timelines, charts with their reading beside them,
  and the plain ones every deck needs and nobody designs twice, from a title slide to an agenda to
  a bullet list.
- **`slide-library.py migrate`** puts one slide into another deck. `clone` copies inside one deck,
  where a colour difference would be a fault; this is the opposite case, where the slide arrives in
  a file that already carries a brand and adopts its master, layouts, theme, fonts and logo. It
  reports rather than silently fixing: literal colours that came across, a change of body face and
  what that costs in capacity, and theme roles the brand has collapsed onto one value.
- **`slide-library.py render`** writes one picture per slide, headless, no window, on macOS,
  Windows and Linux. 58 slides in about six seconds. Where the renderer is missing it names the one
  command that installs it, per platform, instead of leaving a deck unlooked-at.
- **`slide-library.py layout-check`** finds three faults no other check here can see, because they
  are about where a shape sits rather than what is in it: a shape past the slide edge, a shape
  under the margin, and type under a readable size. Its first run against a new library reported 440.

### Fixed

- **A cloned slide lost every picture.** `clone` copied the shape XML and left the image parts
  behind, so the new slide pointed at relationship ids it did not have. PowerPoint called such a
  file damaged and stripped the shape; LibreOffice rendered it silently without the image, which is
  why nothing caught it for so long. Found on a real customer deck.
- **A table cell's capacity ignored the typeface.** The count came from one density figure for every
  face, so it did not move when a brand's theme swapped the font, and a check that cannot see a
  theme swap is quiet exactly where a hand-over goes wrong. Measured: Montserrat runs 16% wider than
  Arial, so a cell that held 23 characters holds 20 after the swap and text that fitted overflows.
- **A soft line break came out as `_x000B_` on the slide.** U+000B has to be written as `<a:br/>`.
- **Files landed outside the vault when the host offered a scratch directory.** `zanmai/temp/` takes
  precedence: a file outside the vault is invisible to the vault's own tools, and a source that
  reads files refuses a path that leaves it.

### Changed

- **Writing into a system outside the vault is its own act.** It waits for an explicit yes in the
  same message, and `outward-guard` hands the decision back to the user on any outward write,
  recognised by the verb in the tool name rather than by a list of servers. A question asked in
  chat is answered in chat.
- **What was created unasked is taken back unasked.** Leaving the user to decide whether to delete
  something they never asked for puts the cleanup on them.
- **The cheapest route that does the job is a rule for every expert**, not one written into eleven
  contracts: a short search where a short search suffices, resizing an image rather than generating
  it again.
- **A set single-page piece goes to PowerPoint**, whatever its page size. A flyer, a one-pager, a
  poster: the file stays editable by the person who receives it, which a PDF does not, and it is
  the only medium here with checks that measure the finished file. The line is not flyer against
  document, it is whether the layout is set or the text flows.
- **Changing the wording of a finished deck is not a build and never a script.** `slots` prints
  every fillable place with what it holds; `fill` writes new wording into them without redrawing
  anything.

## [0.3.7] - 2026-08-26

**A vault that cannot tell you what happened yesterday is a vault with no memory, whatever else it
does. The handover between sessions ran through a skill someone had to invoke, and on a live vault
after four weeks not one session had ever been closed that way: every morning opened on the state of
whichever afternoon someone last remembered to run it. That now happens on its own. Six further
defects came out of one morning of real use, all of them in code that seven green check runs and 391
passing checks had never walked.**

### Fixed

- **The next session no longer opens on a stale day.** A `SessionEnd` hook rebuilds the briefing
  whenever a session ends, and the briefing now opens with what happened after the last clean close,
  read from the activity log, which is written while the work happens rather than at the end. Found
  on a live vault: `briefing.md` stood at 15:13 while the log carried entries up to 16:24, and an
  escalation, a correction and the reasoning behind both were invisible the next morning. The hook
  does not mark a session closed. It has no model, so it can record what happened but not what it
  meant, and only a real close advances that marker.
- **`work show` exists.** `list` prints a short id and every other command takes one, and there was
  no way to read what one stood for. The only route to the content was the page folder and its full
  uuid, which is the machine's own filing.
- **Every `work` command takes its subject the way a person types it.** `work open "a title"` used to
  fail with "the following arguments are required: --title", naming a flag the user had not used,
  because an optional `vault` positional that nothing in the product ever passed ate the argument
  first. The same happened to `work log <id>`. The vault is a flag now, the subject is a positional
  or a flag, and `--agent` is accepted where `--owner` was the only spelling.
- **`work` writes to the vault root from wherever it is called.** Called from inside a bundle it used
  to create a second database there, and an object written into it would never have appeared in any
  later `work list`.
- **A dash against a quote mark is a dash.** In a build command the text sits inside string literals,
  so the dash that carries the sentence ends one of them and stands against the closing quote, where
  neither a space nor a line end closes it. That is the same construction 0.3.6 fixed at a line end
  and missed here.
- **`prose-guard` and `library-check-guard` read the shell's working directory, not their own.** A
  hook process runs from the project root, so the branch meant to catch a dropped `cd` could never
  match. It was dead code from the day it was written, which is why working inside a bundle got past
  both guards.

### Changed

- The check run grew by 20 checks, one per defect above and one per case that has to keep passing.
  Each was verified to fail with the fix removed and pass with it in place, because a check that was
  never seen red is a check nobody has tested.

## [0.3.6] - 2026-08-25

**Guards were bound to the tool the AI usually reaches for rather than to the moment the decision is
made, so they were silent exactly where they mattered, and the one procedure that asks the user
anything before expensive work had never run at all. Both now hang at the decision. Two guards
written the same day were measured against a live vault, failed, and were removed rather than
shipped: the count goes down, not up.**

### Fixed

- **`prose-guard` could not see a dash sentence on its way into a finished piece.** It required a
  markdown file, written through Write or Edit, carrying frontmatter that said the AI wrote it, and
  all three had to hold at once. A finished slide went out reading "Heute sinnvoll entscheiden –
  ohne die Optionen von morgen zu verbauen": the text came from a JSON content file, which is not
  markdown and cannot carry frontmatter, and reached the deck through a Python build script, which
  is Bash and not Write. Any one of the three conditions was enough to make the check silent. It now
  binds on every content file type, requires frontmatter only where a file can carry it, exempts
  `import/` so the user's own material is still untouched, and reads a build command running against
  a `doing/<slug>/` bundle as what it is, a write. A JSON file is scanned by its actual string values
  rather than its raw lines, because the quoting around every value would otherwise hide the prose
  inside it. The pattern itself was wrong too, and this only showed up against the real file: it
  required whitespace on both sides of the dash, and a slide's text is split across several strings,
  so the one that mattered ended on it. Whitespace or a line boundary counts now. A number range still
  keeps its dash, because it carries no spaces at all.
- **`library-check-guard` refused runs that had done the check.** It looked for the record at
  `Path.cwd()`, the shell's working directory, while `slide-library.py check` writes it at the vault
  root. Working from inside the bundle, which is the natural place to work from, meant the hook
  looked under `doing/<slug>/zanmai/temp/<slug>/`, a path that cannot exist. The run was refused
  although it had done everything right, and went looking for a way around a guard that was correct
  in principle. The record is now resolved against the vault root. The same fix closes the gap on the
  other side: with the shell inside the bundle and every path relative, the bundle's name never
  appeared in the command and the guard did not fire at all. It now reads the working directory too.

- **The brief now actually happens, because `dispatch-guard` asks for it.** A handover with no
  `What the user said:` block is refused at the moment of dispatch, with the route named. The `brief`
  skill has described that interview since it was written, two labelled blocks and one numbered round
  of questions with a recommended answer each, plus the rule that a fact sitting in the vault is
  fetched rather than asked about, because what belongs to the user is decisions and not retrieval.
  Measured across two live vaults, 3123 and 744 lines of activity log: **it had never run, not once.**
  It was reached by a sentence asking the reply to notice by itself that its inputs were incomplete,
  and nothing that is never performed can visibly fail. Meanwhile the questions the user did get were
  the ad-hoc ones, at the wrong moment, about things the vault could have answered. This is the only
  change here that adds work to a run rather than removing it, and it is the front of the job, not
  the back: the interview happens while the user is still in the chat, which is the one moment it can.
  Unlike the background-flag correction in the same hook, it cannot be fixed up on the way through,
  because the two blocks are content and only the turn that just read the user's words knows them.

### Removed

- **`link-guard` and `provenance-guard`, both shipped-never.** Written earlier the same day against
  two real incidents, and both dropped before release after being measured against a real vault
  rather than a scratch one. `link-guard` was to demand a `[[link]]` where a bundle was named as plain
  text; it built its word index from folder names, and against the live vault the two words it existed
  for were not in it. It found 44 words and none of the ones that mattered. `provenance-guard` was to
  refuse a commitment field that did not record whether the user or the AI chose the value; it was a
  wall with no door, demanding a declaration no command could write, which is the shape a run works
  around rather than follows. The defects both were aimed at are real and stay open as tasks. Hook
  count is back to 9 from 11.

## [0.3.5] - 2026-08-25

**`library-check-guard` now actually sees a build script, not only an inline save call, and two
skills point at the tools that already existed instead of leaving them to be reinvented.**

### Fixed

- **`library-check-guard` missed any `.pptx` produced by a separate build script.** The hook only
  matched a literal `.save("x.pptx")` written directly in the Bash command; a script file invocation
  (`python3 build.py ...`) calls `.save()` inside that file, invisible to the check. A real build went
  straight through with no library-first record at all. The hook now binds to any Python run that
  resolves into a `doing/<slug>/` path, not only a visible save literal. Found and fixed alongside it:
  the path-matching regex searched only the already-isolated save argument, not the full command, and
  missed a path embedded in quotes or following `cd`.

### Added

- **`image-edit.py palette`.** Dominant colours of a reference image, measured by Pillow's own
  quantiser, plus WCAG 2 contrast against a given colour. Where a brand's colours had to be read off a
  raster mockup with no vector source, this replaces an eyeballed estimate with a real measurement.
- **`prose check` / `prose-guard` catch generic AI-marketing phrasing and a leftover placeholder**
  ("[Your Company]", "Musterfirma", "Lorem ipsum"), in prose the AI wrote itself, the same way the
  hook already caught a dash used as sentence punctuation. Deliberately not extended to invented
  numbers: a script cannot tell a real figure from a fabricated one without knowing the domain.

### Changed

- **`powerpoint/SKILL.md` now names `nudge`, `overlap-check` and `align-check`** as the way to move a
  shape or find a text-over-text or misaligned pair, instead of leaving a correction to be worked out
  from scratch each time.
- **`designer/SKILL.md` now requires a hand-correction to the delivered file to be ported back into
  whatever produced it** before the piece counts as done. A fix that lives only in the delivered copy
  is not fixed: the next build from the same generator brings the old mistake back.

## [0.3.4] - 2026-08-25

**A geometry correction on a PowerPoint slide is now one command, not fifteen minutes of freshly
written Python.**

### Added

- **`slide-library.py nudge`.** Moves one named shape by a distance and sets all four position values
  explicitly, growing every enclosing group's frame to keep containing what moved. A correction that
  used to mean re-deriving group coordinate math from scratch on every run is now one call.
- **`slide-library.py overlap-check`.** Finds text sitting on top of other text, measured against the
  ink actually painted rather than the saved box: a box with `wrap="none"` at a large point size paints
  past its own edge, and the saved box alone misses that.
- **`slide-library.py align-check`.** Two text frames sitting on the same left edge can still read as
  mis-aligned, because a large bold face and a small regular face rarely share the same left side
  bearing. Checks where the ink actually starts, not where the box says it does.
- Both checks measure from the real font file on the machine, matched by name in the standard font
  folders, where one can be found, and fall back to a calibrated estimate only where it cannot.

## [0.3.3] - 2026-08-25

**"Library first" is now a hook, not a sentence.**

### Added

- **`slide-library.py check <library> --task <slug>` and the `library-check-guard` hook.** The
  `powerpoint` skill's order, match or adapt a slide from the brand's own material before composing
  one from scratch, lived only as prose, and a live build skipped straight to the expensive tier
  twice in one afternoon before anyone checked. `check` prints the library and records that it was
  looked at for a `doing/<slug>/` bundle; the hook (PreToolUse Bash, wired alongside `delete-guard`)
  refuses to save a `.pptx` into that bundle until the record exists. It never picks the tier, it
  only proves the library was on the table when the choice was made.

## [0.3.2] - 2026-08-24

**PowerPoint builds from a real master now, not a redrawn copy, and a repair dialog has a way to be
diagnosed instead of guessed at.**

### Added

- **A precheck for AI-written prose before it is written, not just after.** `zanmai.py prose check
  --text <draft>` runs the same dash-as-punctuation scan the `prose-guard` hook runs on the write
  itself, on the draft, first. The `write` skill now calls it on every AI-authored draft, so the write
  is normally never refused in the first place.
- **`slide-library.py` now sees a table's cells as slots.** A template whose rubrics are laid out as
  a table rather than text boxes used to harvest as empty: `has_text_frame` is false for a table
  cell. Cells are named `table1.r2c3`, measured for capacity from their own column width and row
  height, and fillable the same way a text-box slot is.
- **`prose-guard` (and `prose check`) exempt a dash reproduced inside quote marks.** A verbatim quote,
  a source's own title or a claim quoted exactly, no longer has to be rewritten to pass; only a dash
  outside any quoted span still counts as the AI's own sentence punctuation.

### Changed

- **`powerpoint/SKILL.md`'s "Create" section now states the master-derivation build as the only normal
  path, not one of two roughly equal options.** Building a fresh, empty presentation and transplanting
  the CI in by hand is named as a fallback for when no real deck exists at all. Its usual justification,
  that unused media stay attached to a master-derived copy and bloat it, does not hold: `python-pptx`
  only serialises reachable parts, so removing unused slides and layouts drops their exclusive media on
  save (measured on a real deck: 486 parts down to 33, 10.4 MB down to 36 kB). Also added: a real theme
  can itself be an unset stock design (an unrelated name, Office palette and faces) with the brand
  living hard-coded in every run instead, in which case hard values are the correct read, not a theme
  reference; `qlmanage` does not render a shape inherited from the slide's layout or an `outerShdw`
  shadow, so a preview can look like it is missing an element that the file already has correct; a
  passing renderer, XML diff and `design-check.py` do not prove PowerPoint will open the file without a
  repair dialog, and the way to find what's actually wrong is to let PowerPoint repair, save, and diff
  the repaired XML against the original rather than guess; and a spacing constant read off a slide
  family should be the median of several same-layout slides, not one sample. All found on real decks
  during a live build.
- **Two more `powerpoint/SKILL.md` rules, from the same live build's actual repair-dialog root cause and
  a layout-gap fix.** Repositioning an inherited placeholder by setting only some of `left`/`top`/
  `width`/`height` leaves the rest implicit; python-pptx then writes an `xfrm` with a zeroed offset or
  extent, which is what triggered PowerPoint's repair dialog on this deck: all four values plus
  `vertical_anchor` are now set together, never partially. And a gap between two elements is closed by
  stepping the variable dimension in small increments until the measured extent fills it, the same
  "measured, not guessed" standard as a spacing constant.
- **`powerpoint/SKILL.md`'s Match tier now names its fastest form: don't deep-copy the exemplar slide
  into a new one, delete every other slide from the copy and keep the exemplar's own XML untouched,
  swapping only its text.** Verified on a real deck, 7 minutes start to finished with no repair
  dialog: geometry stayed byte-identical to the source, skipping all position work and font-size
  search that a shape-copy would have needed. Two more confirmed repair-dialog causes and one more
  overflow trap from the same run: a shape's hyperlink or relationship pointing at a `.rels` target
  removed along with a deleted slide; and `spAutoFit` text frames that grow past their shape in real
  PowerPoint without python-pptx ever noticing, now caught by measuring each line with Pillow before
  writing it.
- **`powerpoint/SKILL.md` documents a package-level way to combine several decks into one file.** When
  the source decks genuinely share the same master, layouts and theme, copying each deck's own slide
  XML and rels into the target's ZIP directly gives byte-identical slides with none of the shape-copy
  failure modes. Verified on a real case, six slides from four separately-built files, 58 checks
  passed, all five source files left untouched.

### Fixed

- **`slide-library.py fill` could silently drop the text it had just written.** `TextFrame.clear()`
  keeps a paragraph's `a:endParaRPr` and only removes its runs; appending the new run put it after
  `endParaRPr`, which breaks the schema's element order. PowerPoint drops such a run with no error, a
  more tolerant renderer like `qlmanage` still shows it, so a clean preview did not catch it. Found on
  a real deck. The new run now always goes in before `endParaRPr`.
- **`index-consistency` false-alarmed on almost every write in a working session.** It took a written
  file's immediate parent as the bundle directory, right only when the file sits straight in the
  bundle root; a file nested under a working subfolder (`arbeit/recherche/…`) read as one level too
  deep, so the bundle's real `INDEX.md` looked missing on every write under that subfolder. It also
  matched a wikilink case-sensitively, so `STAND.md` linked as `[[stand]]` read as unreferenced. Both
  fixed: the bundle directory is found by walking up to the slug level, and the wikilink match is
  case-insensitive.
- **`design-check.py` flagged a theme font reference as a missing font.** `+mn-lt` / `+mj-lt` mean a
  run explicitly asks for the theme's minor/major face instead of inheriting it silently, which is
  correct, not an override. The master-level check already excluded `+`-prefixed values; the
  run-level check did not, so it reported the correct choice as a face to fix.

## [0.3.1] - 2026-08-22

**Steve now does the small stuff himself, and the morning greeting stopped losing items.**

### Added

- **Office files are read directly.** Word, Excel and PowerPoint files show their text, their tables
  row by row, and their images as separate files with a marker at the spot they belong, instead of
  being containers nothing could open.

### Changed

- **A specialist is dispatched only where the step genuinely needs one.** Reading a quick fact with an
  obvious source, a source you already have access to (a passwordless machine, a mail account you
  already set up), or a small edit to a file that already exists, Steve now does directly instead of
  sending Reed or Wong off on a full run for it. Reed and Wong still take over research that weighs
  sources against each other, and any connection setup or credential or security choice.

### Fixed

- **The morning greeting stopped losing or misnumbering items.** A backlog item could push out
  today's actual task, an internal work-object ID leaked into what you read, and an overflow line
  broke the numbering. All three are fixed and locked in as test cases.
- **Deleting no longer sends your own material and Zanmai's own working files down the same path.**
  What you throw away goes to the trash; what Zanmai discards from its own temp folder does not.

## [0.3.0] - 2026-08-12

**The rule set is smaller, and the rules that kept failing are checks now.** A session start named four
topics, none of which mattered, and left out a meeting the next day that stood in its own briefing.
Looking for the cause turned up the shape behind it: a refusal that names no alternative produces a
report about the refusal instead of the work. Across the fourteen files that govern behaviour there
were 499 sentences carrying a prohibition, 274 of them with no route named. This release takes the
three files the main loop actually runs on down to 363 and 206, and turns the two worst-behaved rules
into machinery. Nothing was dropped, and the ten specialist contracts were read line by line and left
alone: their prohibitions already name where the work goes instead.

### Added

- **`prose-guard`**, a check that refuses a dash used as sentence punctuation in prose Zanmai wrote
  itself. That construction was banned in five files of the distribution and a produced document still
  went out carrying 21 of them, on a page other people read. Your own writing is untouched: it binds
  only where the frontmatter says the AI produced the content, and it compares the lines before and
  after, so moving, importing or re-saving your material passes. Compound words and number ranges keep
  their dash. Nine cases in the self-test.
- **Files whose name carries a date from today onward are found and surfaced.** The briefing used to
  see a date in three places only, all of them places Zanmai keeps itself: a task line it wrote, a
  bundle's `due` field, a work object. A meeting prepared yesterday for tomorrow sits in none of them.
  It is now read straight off the filename, anywhere in your own folders, with the journal and the
  system folder skipped because a daily entry named by its date is the calendar, not something coming
  up.
- **The briefing checks itself.** A rebuild that lost a section used to look exactly like a full one,
  and the greet then read from a source that had gone quiet. A missing section is now named and the
  command exits non-zero.

### Changed

- **The session start is a walk over what is open, not a composed list of topics.** The instruction
  used to ask for three to five items and to fill up from whatever was reachable, which is how a line
  from a contact file describing what you do became a "topic" and how tomorrow's meeting did not
  appear. There are now five sources in a fixed order: what the last close left as next, work waiting
  on you, anything due or overdue, files dated from today onward, and bundles touched in the last two
  days. Nothing else is a source. There is no target number, so one open thing is one line and a quiet
  vault gets no list at all. Every line is checked against its truth file before it is written rather
  than after you pick it.
- **A page you hand over is read by Steve, not dispatched.** URLs or paths you pass in are his own
  plain work, however many there are and whether or not the answer compares them; the researcher is
  for finding sources you have not named. Three places used to disagree about this and the loudest one
  won, so four catalogue pages and a plain question turned into a background job.
- **A piece of work gets its object at the dispatch**, rather than when someone judges it will outlive
  the turn. That judgement was made in the same breath as the work and always came out the same way,
  which is why the list of open work stayed empty while open points were written as prose into logs.
  The session close now writes each open point onto its object before it writes the log.
- **`operating-principles.md` rewritten**: 5389 words to 3381, prohibitions 115 to 49, of which 76
  named no alternative before and 34 do now. Every rule is still there; the reasoning behind them moved
  to the background page that already existed for it, and each remaining refusal says what to do
  instead.
- **Checkboxes: the one route is taken rather than reported.** Asked to add items to a file that
  already holds checkboxes, the run makes the `task add` calls and finishes. Handing the work back with
  the name of the guard on it is a defect.
- **A rule that has not held twice is built as a check or deleted**, never sharpened and never repeated
  in a second file.

## [0.2.6] - 2026-08-12

### Changed

- **The first message after setup now says what Zanmai actually does, and who does the work.**
  Until now it named practical next steps (close a session, the slash commands) without saying what
  the specialists are for, so a first-time user saw names like Carol or Loki with nothing attached to
  them. It now lists what each one is for, its name in parentheses, and ends by asking what you are
  actually trying to get done instead of a generic "what would you like to start with".
- **An answer drawn from one page of the documentation now says when a real alternative exists**,
  instead of answering as if that page were the whole picture. Asking where files go used to come back
  as "into `import`" only; it now also names that material you already recognise can go straight into
  its own `doing` folder, and invites the follow-up question rather than stopping there.
- **`/zanmai-grill-me` and the question rounds behind a dispatch interview more rigorously.** The
  mechanic (frontier, rounds, numbered questions with a recommendation each) was already faithful to
  where it came from, but the questions themselves had drifted toward "what does this need to start"
  and away from actually pressing on an idea's weak points before you build it.

## [0.2.5] - 2026-08-12

### Added

- **A double-clickable starter icon, so opening a terminal and typing a command is no longer the price
  of entry.** At the end of first-time setup, or anytime afterward by simply asking for an icon, an
  app, or a shortcut, Zanmai builds one: on macOS an app under `/Applications`, reachable from
  Spotlight, Launchpad or the Dock; on Windows a Desktop shortcut. It detects what terminal apps are
  actually installed and asks which to use when there is a real choice, and it suggests the vault
  folder's own name, never a fixed product name, so a private vault and a work vault on the same
  machine get two distinct, correctly labelled icons. The Windows path is written against documented
  behaviour and not yet run on real Windows hardware, the same status as the rest of Zanmai's Windows
  support.
  → [Setup](docs/setup.md)

## [0.2.4] - 2026-08-12

### Added

- **`/zanmai-grill-me` questions a raw idea before anything is dispatched.** Until now the question
  rounds only ran when Steve decided on his own that a job was too thin to hand to a specialist. You
  can trigger them yourself on an idea that has no specialist yet: one round of numbered questions
  with a recommended answer each, the open decisions recomputed after every round, done when nothing
  is left to settle. The questions come from what the idea itself needs, not a fixed checklist.

### Fixed

- **A distribution update could report a new version and then refuse to show what changed in it.**
  The update preview read the release notes from the file already on disk, which at that point still
  held the old version, so an update sitting more than one release behind aborted before ever asking
  you. The preview now reads the new release notes from the update source itself, before anything is
  applied.

## [0.2.3] - 2026-08-11

### Changed

- **What you said and what Zanmai concluded are handed to a specialist as two separate blocks.** They
  used to arrive as one, which is how a screenshot you attached for context ended up transcribed into
  a document as content, and how a conclusion of its own got quoted back to you afterwards as your
  instruction. The specialist now sees which is which, and nothing enters your document from the
  second block. Where the first block does not cover what the job needs, you get asked instead of
  guessed at: one round of numbered questions in the chat, each with a recommended answer you can
  wave through, and anything findable in your vault looked up rather than asked. Most jobs need no
  round at all.
  → [Who does what](docs/specialists.md)

## [0.2.2] - 2026-08-11

### Changed

- **The habits that make text read as machine-written are named and avoided while writing.** Not a
  filter afterwards: the shapes go into the writing rules, so they never get produced. They come
  from a catalogue human editors built across thousands of machine-written texts, and they are
  described as shapes rather than words, so they hold in whatever language you write in. The
  strongest is the urge to prove itself right, hedging and citing and qualifying where somebody with
  a spine would write the finding and stand behind it. Then the bullet that opens with bold words
  and a colon, claimed significance in place of content, the plain verb avoided, framing by
  negation, everything in threes, headings that arrive by template, and the officialese every
  language keeps for forms and ministries.
- **Documents are written for what you use them for, not for the topic.** Before the first sentence,
  the situation the document gets used in is settled, and where that cannot be found in your ask, in
  the material or in your vault, you are asked once. A note you read on your phone during a meeting
  and a handover for someone who was not there are now different documents. There is no internal
  version and no external one: plain language is the constant, and what changes with the reader is
  only how much goes in.
  → [Documents written for you](docs/writing.md)
- **No document tells you what to do any more.** "Suggested approach", "you should", a ranking of
  your own topics by importance: banned outright, and enforced on the finished file rather than
  asked for. Ask for a recommendation and you get one, in its own section; asking once no longer
  switches the whole document into advice mode. A screenshot or file you send along is context for
  the job now, not a list of fields to copy in, so your colleague's reporting line stops turning up
  in your meeting notes.
- **Which model runs a job is decided at the moment the job is handed over.** Each specialist still
  has a default you can override in your profile, and on top of that Steve can raise or lower it for
  one particular job: up for a long chain of tool calls or a mistake that would be expensive to
  undo, down for bounded, mechanical work. A raise spends your money, so it is said out loud in the
  line that announces the work. No skill carries a model of its own any more, which used to let a
  procedure quietly overrule both the specialist's default and your own setting. Writing runs on
  Sonnet now: measured across model tiers, having a voice to write against changes the result more
  than a heavier model does, so the effort goes into reading your brand and a comparable document.
- **Writing has its own specialist, Ben.** It used to sit with the filing expert, handed over
  whenever a document would take a few minutes, which is a fact about waiting time and not about who
  should write. Ben settles the purpose, finds the voice himself (your brand where the piece carries
  it outward, otherwise a comparable document or your own templates) and reads the finished file
  back against its purpose before you see it. Hank files and no longer writes.
  → [The specialists](docs/specialists.md)
- **Who writes now follows where the material is.** Points you dictated, or substance gathered in
  the conversation you are in, get written right there instead of being handed to a background run
  that would need re-briefing. Only material nobody has read yet, a transcript, a bundle of forty
  documents, goes to the background. Saying who should write it overrides all of that.

## [0.2.1] - 2026-08-10

### Added

- **Setup asks once whether to fetch the tools Zanmai can fetch itself.** You see how many are
  already there and what the rest are for, and you say yes or later; what needs you, an account or
  money is listed separately with the one command that does it. Until now a missing tool turned up
  for the first time in the middle of a job that was already running.
  → [Tools Zanmai uses](docs/tools.md)

### Fixed

- **Motion graphics could not be installed by anybody.** The renderer was listed as fetched on
  demand, but nothing knew how to fetch that kind of tool, so the request answered "no provisioner"
  and did nothing. It now installs into the vault's own runtime, pinned to one version, and it has
  been run end to end: a ten-second composition rendered in six seconds. A check now fails the build
  if any tool promises a way to install itself that does not exist.
- **A specialist's job no longer shows you a red error before it starts.** Handing work to a
  specialist in the mode that would freeze the conversation used to be rejected, which worked and
  which you saw every single time. It is corrected on the way through instead.
  → [Hooks](docs/hooks.md)

## [0.2.0] - 2026-08-10

### Added

- **Luis edits video.** Footage and your notes in, a finished cut out: the rough cut decided from the
  transcript, captions, sound, other formats, and he watches his own render before you do. You can
  also edit by editing the transcript, delete a paragraph and exactly that leaves the video.
  → [Editing video](docs/video.md)
- **Shuri owns your brand.** Colour, type, voice, whitespace and imagery, read out of your own
  material into one file that every other specialist builds from, in a format a coding agent reads
  directly. She judges finished work against it, and she tells you what is still missing rather than
  waiting to be asked: a type scale of two levels, no spacing rhythm, or a button whose text sits
  below readable contrast. Nothing on-brand gets produced without a brand: the job stops and asks,
  and you can still say build it anyway.
  → [Your brand](docs/brand.md)
- **Ask for something to go on your list and it goes on your list.** Into today's entry, or into a
  file you name; ticking off works the same way. Zanmai still never invents a task of its own.
  → [Daily, weekly and monthly notes](docs/daily-capture.md)
- **Deadlines are found wherever they sit.** A task can carry a date, and whatever falls due in the
  next two weeks is named at the start of a session, overdue first, `archive/` included.
  → [Daily, weekly and monthly notes](docs/daily-capture.md)

### Changed

- **A search is sized to the question.** A price or a version number gets one to three sources and a
  straight answer; a real comparison gets the full method; money, law or health gets the deep run.
  Where the right size is unclear you are asked before anything is spent.
  → [Research](docs/research.md)
- **Your brand lives at `trusted/brands/<brand>/design.md`.** It used to sit in the system folder,
  which is the part of the vault you never open by hand, and a brand is not that.
  → [Your brand](docs/brand.md)
- **Looking at material is a sample, not a full pass, and a self-check stops after two rounds.**
  Reading something before working on it exists to spend less, not more, and "until it passes" is an
  open budget. What two rounds did not fix comes back to you named.
  → [Operating principles](docs/operating-principles.md)

### Fixed

- **A video dropped into the import folder could be taken for a voice note** and read out as if
  someone had spoken it. What a file is now comes from the file, not from its extension.
- **The desk could not be filed onto.** `doing/` existed as a folder but not as a kind of bundle, so
  nine commands refused it and anything written there landed unchecked.
- **Generated images could not come out on brand**, because image generation read a folder no other
  part of Zanmai ever wrote to.
- **Looking at the trash was mistaken for emptying it**, so listing that folder and even discarding a
  file were refused. Removal is still refused on the verb alone.
- **Captions broke at character counts instead of at meaning**, and cutting between two cameras of
  different sizes failed outright.

## [0.1.0] - 2026-08-09

The first release. There is nothing before it, so this entry describes what Zanmai is rather than
what changed.

### The vault

- **Folders at the top, and nothing above them.** `journal` for the time axis, `focus` for what you want to reach, `doing` for the desk, `habits` for what has a beat, `knowledge` for everything gathered, `trusted` for the small set you have settled on, `archive` for what is finished and kept, `contacts` for people and organisations, `import` for whatever you drop in, and `zanmai` for the system's own files.
- **Named after states of a head, not stages of a filing system.** The common approach sorts by lifecycle, which forces a decision on every new item and then keeps changing it: a trip is a project, then it recurs, then it is over, and the same material moves three times. Worse, it only works while you keep doing the moving. Here nothing has to move at all. In `knowledge` staying put is the normal case rather than a backlog you owe someone.
- **One exception, on purpose: the desk gets cleared.** Work has an end, so `doing` empties. You do not have to remember that either. Zanmai sees from the file dates that something has sat untouched for weeks, asks, and on your word moves the whole thing to the archive, your knowledge, your trusted set, the trash, or out of the vault.
- **Everything about one matter stays together.** A bundle holds the note, the PDF, the photo, the recording and the transcript side by side, because a folder that sorts by file type cuts apart the very thing you were keeping. There is no shared attachment folder. What keeps a full bundle readable is its own index, not a sub-folder, and a sub-folder is only made when it is a nameable thing in its own right.
- **No subject headings ship with it.** The areas inside `knowledge`, `trusted` and `archive` come from your words, never guessed and never supplied as examples. The vault you already have is the list.

### What it does

- **The journal is a destination, not a hallway.** Daily, weekly, monthly and yearly entries, each one a folder, the path following from the date so there is nothing to configure. What happened on a day belongs to that day, photos and recordings included, and **nothing is ever taken out of an entry**. Anything worked out from a day is an addition that points back at it; where the two disagree, the day wins. The week is filed by its ISO year, so the week spanning New Year stays in one piece. Rollups are written a level at a time, once per period, and said out loud at the next session start.
- **The import folder takes things up by itself.** Drop anything in, however it lands. The folder is the automation, so there are no sub-folders for purposes: what kind of file it is decides its route. Everything is read oldest-first and in full before any of it is acted on, because the later item can withdraw the earlier one. Recordings are read out without asking, everything else asks, and an unknown type is named rather than quietly left lying.
- **Spoken notes get read properly.** Transcribed locally, with no key and nothing uploaded, then read against the vault, which is where a garbled word and the spelling of a name are settled. The recording is kept in the day you spoke it, beside whatever came out of it, so a transcription error stays repairable years later.
- **Nothing deletes.** The assistant is refused outright when a command would remove something, with no exception for "this is obviously junk". Everything discarded goes to the trash and can be brought back exactly where it came from; the path under the trash is the record, so there is no second list to drift out of step. The only thing that truly deletes is one sweep at session start clearing what has sat for more than thirty days in the trash or the scratch area. One number for both, because two numbers would be two things to remember.
- **Snapshots cost what changed, not a copy of everything.** Every version of every file is stored once by its content, so an unchanged file costs nothing the second time. One is taken when Zanmai is about to overwrite material that already exists and cannot take it back file by file: an update, a bulk repair, a vault-wide rename, a restore. Not for adding, because filing new documents takes nothing away. You can also ask for a single file back, with the version that was there moved to the trash so the restore itself is undoable.
- **It works with any Markdown editor.** The folder names, the trash, the archive and the journal are Zanmai's own and behave the same everywhere, Obsidian or a plain text editor included. Your notes are plain files; nothing needs an app to be readable.

### How it works with you

- **Approval before writing, sized to the operation.** A run that builds bundles or rewrites something you wrote shows you a tree of where things would land, the axis it chose and the ones it rejected, the counts and the notable items. A run that only adds to a bundle that exists gets twelve lines at most. The proposal lives in the chat, not as a file in your vault, and the record afterwards is the operation report.
- **A cost you asked for is already approved; one nobody asked for waits.** Research that spends minutes fetching sources, an import that rewrites many files, an image generation that spends credits: those get a brief of two to four sentences and wait for your word. Asking again about something you did ask for is a permission ritual, not care.
- **Work that outlives a sitting has somewhere to live.** One object per piece: what it is, who is on it, where the material and the result are, what waits on you, what you decided, the log and the cost. It sits on Zanmai's own side rather than in your folders, because it is the machine's list of what it still owes you.
- **Specialists, each on a model that fits its work.** Filing, research, design, image generation, housekeeping, gateway, expert-building. Each ships with a default and the reason next to it, and you can override any of them in your profile. That choice is yours: an update replaces the contracts and leaves it alone. No run raises its own model quietly; where a job needs more, it says so and waits.
- **A document is agreed in one line before it is written.** What the valid source is, what it is for and who reads it, what must not appear, and the format. None of it arrives as a question: it is answered from the brief and from your vault, and whatever is genuinely left over is proposed in a single line you can stop or change.

### What it will not do

- **It does not touch your checkboxes.** Not one, in no file. It reads them and answers from them, and it writes none, ticks none, deletes none, not even a list you asked it for. This is not a promise in a document, it is a check that runs before every write and refuses the ones that would break it. Something it still owes you goes on its own list instead, where you can see it without it being in your way.
- It does not move what you wrote yourself. A tidy-up is an offer, never an act.
- It does not invent a subject heading, a source, or a folder for something it could not place. It says so instead.
