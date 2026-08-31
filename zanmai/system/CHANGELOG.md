# Changelog

All notable changes to Zanmai. Versions follow semver; the 0.x series is pre-stable, so a folder
name or a command can still change between versions.

## [0.5.1] - 2026-08-30

- Added `records rename` and `records move`: a kept document or a whole section gets a better name or a new place, and the search index follows
- Added `--scope` to `records survey`, so it reports the folder that was just read in instead of the whole archive
- Fixed `records file --area health/x-rays` collapsing a section inside a section into one folder
- Fixed `bundle index-entry` refusing to write the line for a member that had none, which left a hand-edit of the index as the only way
- Added `--truth` to `bundle create`, so a sub-bundle with a theme of its own gets its main file in the same call
- Fixed the line describing a bundle's main file staying English in an index whose headings were translated
- Added the resolution of `zanmai.py <subcommand>` to the session briefing, so a run does not look for a file that is not at the vault root

## [0.5.0] - 2026-08-29

- Added `records/`, a root of its own for what has to be kept, with a term on each piece and no sweep that reaches it
- Added Marcus, the curator: files what is kept, says whether a contract still runs, assembles a matter, proposes what may go
- Added `records index` and `records search`: every kept document readable in seconds, scans included, without a note per document
- Added `routing`: what a sort of incoming material is and where it goes, as a file you can open and change
- Added `retention`: keeping terms as suggestions with their source, confirmed once and then yours
- Added the `record` kind, with its states, terms and the ways one document relates to another
- Added `records matter`: the thing documents belong to, with its history, and a document is hung on it in both directions at once
- Added `records who`: one name per counterparty however many ways it was written, and never merged without asking
- Changed the import to read your routing table and follow it, instead of asking again what you already decided
- Added `survey`: what a pile of files is, established by machine, so a run reads short lines instead of whole documents
- Fixed the records area being filed into before it was set up, by settling it in the conversation instead of expecting a background run to ask
- Changed keeping terms to three buckets, four years, ten years and for good, with no legal area attached to them
- Fixed a matter being created in a folder next to the records area instead of inside it
- Fixed any write path built from data being able to create a folder the vault does not have
- Changed contacts on the records path to follow a matter rather than every sender on every document
- Added `records file`: a whole pile of documents into the records area at once, read as they land
- Fixed documents being skipped by the index because of their file name, by reading what a file is from the file
- Fixed a search for a date, an amount or a case number failing instead of answering
- Fixed the index still answering for documents that had been moved or deleted
- Fixed a document being unfindable by the name it carries, by searching the name along with the text
- Added hanging a whole folder of documents on a matter, with dates, amounts and counterparties taken from what was read
- Fixed a matter note being written with English headings in a vault kept in another language
- Fixed the records area missing from the master index
- Changed routing rules to key on what something is rather than on its file type, so the same report routes the same however it arrives
- Fixed a file being thrown away out of `import/` while its content had reached nowhere in the vault
- Fixed that check being avoidable by moving the file out of `import/` by hand
- Changed the work objects to one JSON file in `zanmai/open/`, replacing a table format no editor here draws any more
- Fixed the page listing what ships: it named a command that does not exist and left out twelve that do, two skills, a specialist and two hooks
- Changed the slash-command menu to hold only what you would ask for by name, so a specialist's working method is reached through that specialist instead of sitting in your list
- Removed fifteen entries from that menu that nobody types, which also gives every session start less to carry
- Fixed two pieces of work opened under the same name in the same minute sharing one id, which made the second unreachable and closed the wrong one
- Fixed a version change being able to lock the vault out of itself, where a guard the installed version does not have refused every command
- Added `setup upgrade --to <version>`: go to a named published version, backwards included, with a snapshot taken first
- Changed filing and research to survey a pile first and open only what the survey could not answer
- Fixed a word wider than its column counting as one line, so text that wrapped into the paragraph below passed every check
- Fixed `fill-check` counting a card's padding as missing content, which reported every small card as two thirds full

- Added `file status`: a file can record that it is done or cancelled, and its open points and dates stop being offered
- Changed the session-start list to two blocks, what carries a day and what does not, ten lines each at most and numbered straight through
- Changed the open-task list to reach every folder, not only the journal and the focus bundles
- Fixed a due date written without brackets not being read as a date
- Changed `tools ensure`: it reports what a download or install would cost and fetches only with `--yes`
- Changed the session start: what lies in `import` is read straight away in the background, and the questions come after the reading
- Changed `import` to empty: the original follows what was made from it or goes to the trash, and stays lying only for a named reason
- Changed the session-start list to fold several loose ends from one bundle into a single line, named as the bundle names itself
- Added `park-guard`: a background run cannot wait for an answer where nobody can see the question
- Fixed `layout-check` holding a printed page to the type size a slide needs, which made every ordinary caption a fault
- Fixed `align-check` reading no side bearing at all, so text that visibly started at different points was reported as level
- Changed `align-check` to name the shape to move and how far, and to measure a printed page more finely than a slide
- Added `furniture-check`: a footer, logo or page number that sits somewhere else on the next page, which no single-page check could see
- Fixed a session picked up again running its session start a second time, which read material the first run was still working on
- Fixed `furniture-check` reporting a sentence repeated in the middle of a page as furniture that had moved
- Changed a blocked command: it is tried before it is reported, and a line for you to type is a last resort rather than a working method
- Changed filing: material that a synced folder keeps putting back is settled at its source instead of left lying
- Added `rasterise`: an SVG or a PDF page becomes pixels at the size it will be used at, transparency kept
- Added a renderer for vector files to the tool register, so icons no longer need a workaround per piece
- Added `fact`: what a run established about this machine, install or piece of work, so the next one does not establish it again
- Changed the readiness checks before building a deck to read what was already established instead of measuring it afresh
- Added a sentence at session start about what has been sitting on the desk untouched for more than two weeks
- Added `waiting` as a status: a piece parked on something outside stays quiet until the date it comes back
- Fixed the library check refusing any command that merely mentioned a piece of work, down to ticking a task off in a text file
- Fixed a headless render setting a deck in the wrong typeface where the right one was installed for you alone
- Added `--font-dir` to the render, for a typeface that lives with the brand instead of on the machine
- Changed the rule on driving a visible application: it opens a window on your screen, so it is the last resort and never the method
- Changed a task line: it stays one line and carries `--see` to where the detail lives, rather than repeating it or cutting it away
- Changed the checks to say when they compared nothing at all, so an empty run no longer reads like a pass
- Changed `furniture-check` to name what it paired across pages instead of only counting it
- Changed an instruction to report: it ends with the reporting and carries no permission to change what was reported
- Added `media-check`: a picture the file points at that is empty or is not the format it claims, which only opening the file used to reveal
- Added `fill-check`: a card holding far less than it has room for, measured from whatever stands inside it
- Fixed `layout-check` never seeing a shape without text, so a card hanging over the page edge passed as clean
- Fixed `furniture-check` never seeing a logo, which carries no text and is the thing most likely to wander between pages
- Changed `furniture-check` to recognise a slot by its height in the zone as well, so a kicker whose wording differs per page is still checked
- Fixed `furniture-check` comparing shortened labels, so two wordings sharing their first characters counted as one
- Fixed the library check reading prose inside a heredoc as a command, which blocked writing a report about the check itself
- Changed the `work` commands to take the same flags throughout, with `--text` accepted for `--note`
- Fixed an interrupted model download starting over instead of continuing where it stopped
- Fixed a handover being refused for carrying its two labelled blocks in the user's own language
- Fixed a command being refused for tidying up `.DS_Store` alongside what it created
- Fixed the memory curation not seeing rules written as bullets, which is most of them
- Changed the session close: a rule is only written down if it still holds in three months, and one that refines an earlier rule replaces it

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
