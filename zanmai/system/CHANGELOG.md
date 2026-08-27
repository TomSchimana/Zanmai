# Changelog

All notable changes to Zanmai. Versions follow semver; the 0.x series is pre-stable, so a folder
name or a command can still change between versions.

## [0.4.9] - 2026-08-27

- Changed the changelog to one line per change, and dropped the reasoning from it
- Removed internal notes, dates and measurements from the shipped files

## [0.4.8] - 2026-08-27

- Added `structure-check`: reported a slide that lost part of the pattern it was built from
- Added `schema-check`: reported shapes PowerPoint would not draw
- Added `leftover-check`: reported comments, speaker notes, animations and authors left in a file
- Added `suggest`: a shortlist of the patterns that fit a shape of content
- Added `keep`: put an approved slide into the brand's library
- Added `extract`: lifted whole slides out of a deck, links into the rest cut
- Added `swap-image`: replaced a picture and kept the target's position and crop
- Added `tools list`: every tool Zanmai can use, with its purpose, its size and who installs it
- Added `gaps`: what the experts noted about the tooling while they worked
- Added `housekeeping`: cleared the trash, the scratch area and the snapshots
- Added `tools ensure-all --only`, to fetch a selection instead of the whole group
- Added LibreOffice to the tool register, installed by you when a job first needs it
- Changed the wireframes: every pattern shares one frame now, a kicker over the title, the title, an optional claim and an optional intro
- Changed the wireframe count to 57; `cards-row-kicker` went, because every pattern carries a kicker slot
- Changed `statement-tiles`: a tile is one surface carrying its marker, heading and text
- Changed `migrate`: it appends to the target deck instead of replacing it, and `--brand-from` carries the brand's corner shape, fill and formatting across
- Changed `slots` and `fill`: they reach shapes inside groups
- Changed snapshots: kept seven days, the newest one always
- Changed setup: it names every tool with its size before anything is fetched
- Removed the preview note from the README
- Fixed two runs on one deck overwriting each other silently
- Fixed a resumed session being greeted as if it were new
- Fixed a file whose name ends in a date losing its name in the greeting
- Fixed `align-check` missing the left inset and `overflow-check` measuring the wrong type size

## [0.4.7] - 2026-08-26

- Fixed an empty session-start payload passing unmentioned

## [0.4.6] - 2026-08-26

- Changed the greet to name the model by its display name rather than its id
- Fixed the session-start hook waiting forever on input that never closed
- Fixed the index rebuild running inside the session-start hook

## [0.4.5] - 2026-08-26

- Added a line to the greet naming which model is running
- Fixed the session-start hook waiting for input that never came

## [0.4.4] - 2026-08-26

- Fixed a work object waiting on you being left out of the greet when it carried no date

## [0.4.3] - 2026-08-26

- Changed the update to run as two steps with you in between, so nothing is applied before your yes
- Changed expert descriptions to a budget, like the skill descriptions

## [0.4.2] - 2026-08-26

- Added a wireframe library of neutral slide patterns
- Changed the greet into a skill of its own
- Changed the session-start hook to name the briefing and the greet instead of pasting them
- Changed skill descriptions back into triggers, with a budget on what they may cost
- Changed an expert's adapter into a reading list
- Fixed fifteen skills having no adapter, which made them invisible

## [0.4.1] - 2026-08-26

- Changed the four skills that dispatch an expert to name where the dispatch is described

## [0.4.0] - 2026-08-26

- Added `migrate`: one slide into another deck, adopting that deck's master, theme and logo
- Added `render`: a picture of every slide, on any platform
- Added `layout-check`: shapes off the slide, under the margin or set too small to read
- Changed a set single-page piece to go to PowerPoint, so the file stays editable
- Changed wording changes on a finished deck into an edit rather than a rebuild
- Fixed a cloned slide losing every picture
- Fixed a table cell's capacity ignoring the typeface
- Fixed a soft line break coming out as a stray code on the slide
- Fixed files landing outside the vault when the host offered a scratch directory

## [0.3.7] - 2026-08-26

- Added `work show`
- Fixed the next session opening on a stale day
- Fixed `work` writing its database wherever it was called instead of the vault root
- Fixed `work` commands demanding a flag for what you had already typed
- Fixed a dash against a quote mark passing as punctuation
- Fixed two guards reading the shell's working directory instead of their own

## [0.3.6] - 2026-08-25

- Added `link-guard` and `provenance-guard`
- Fixed a dash sentence reaching a finished piece unseen
- Fixed a guard refusing runs that had done their check

## [0.3.5] - 2026-08-25

- Added `image-edit.py palette`
- Added a check for generic AI-marketing phrasing and leftover placeholders
- Fixed a guard missing any deck produced by a separate build script

## [0.3.4] - 2026-08-25

- Added `nudge`: move one shape by a distance without redrawing it
- Added `overlap-check`: text sitting on other text
- Added `align-check`: two text frames sharing a box edge but not where the ink starts

## [0.3.3] - 2026-08-25

- Added `check` for a slide library, and a guard that holds a save until it has run

## [0.3.2] - 2026-08-24

- Added a check for AI-written prose before it is written, not only after
- Changed `slide-library.py` to see a table's cells as slots
- Fixed `fill` silently dropping text it had just written
- Fixed a dash inside quote marks being reported as punctuation
- Fixed an index warning firing on almost every write
- Fixed a theme font reference being reported as a missing font

## [0.3.1] - 2026-08-22

- Changed Office files to be read directly
- Changed dispatch: a specialist is called only where the step needs one
- Fixed the morning greeting losing and misnumbering items
- Fixed your own material and Zanmai's working files going down the same delete path

## [0.3.0] - 2026-08-12

- Added `prose-guard`
- Added dated filenames to what the session start surfaces
- Changed the session start into a walk over what is open
- Changed a page you hand over to be read directly instead of dispatched
- Changed a piece of work to get its object at the dispatch
- Fixed checkboxes being reported instead of taken

## [0.2.6] - 2026-08-12

- Changed the first message after setup to say what Zanmai does and who does the work
- Changed an answer from the documentation to name a real alternative where one exists

## [0.2.5] - 2026-08-12

- Added a double-clickable starter icon

## [0.2.4] - 2026-08-12

- Added `/zanmai-grill-me`, which questions a raw idea before anything is dispatched
- Fixed an update reporting a new version and then refusing to show what changed

## [0.2.3] - 2026-08-11

- Changed a dispatch to hand over what you said and what Zanmai concluded as two separate blocks

## [0.2.2] - 2026-08-11

- Added Ben, the writer
- Changed documents to be written for what you use them for
- Changed the model for a job to be decided when the job is handed over
- Removed advice from documents that were only asked to report

## [0.2.1] - 2026-08-10

- Changed setup to ask once whether to fetch the tools Zanmai can fetch itself
- Fixed motion graphics being impossible to install
- Fixed a specialist's job showing a red error before it started

## [0.2.0] - 2026-08-10

- Added Luis, who edits video
- Added Shuri, who owns your brand at `trusted/brands/<brand>/design.md`
- Changed a search to be sized to the question
- Changed deadlines to be found wherever they sit
- Fixed a video in the import folder being taken for a voice note
- Fixed the desk not being filed onto
- Fixed generated images not coming out on brand
- Fixed looking at the trash being taken for emptying it
- Fixed captions breaking at character counts instead of at meaning

## [0.1.0] - 2026-08-09

- Added the vault: plain files in folders named after what is going on, not what stage a file is at
- Added the specialists for filing, research, design, images and housekeeping
