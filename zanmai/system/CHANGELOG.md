# Changelog

All notable changes to Zanmai. Versions follow semver; the 0.x series is pre-stable, so a folder
name or a command can still change between versions.

## [0.6.0] - 2026-09-04

- Changed the space to eight areas: inbox, workbench, life, knowledge, archive, journal, contacts, zanmai
- Changed what decides where something goes, from how important it is to what happens to it next
- Changed `focus`, `habits` and `trusted` into one area, `life`, for what is yours and matters now
- Changed `records` and `archive` into one area, `archive`, with a date and a keeping reminder on every piece
- Changed `knowledge` to hold what would still be right for someone else, not everything gathered
- Changed `import` to `inbox` and `doing` to `workbench`
- Changed the word for your installation from vault to space
- Changed the `records` command family to `archive`, and `--area` to `--into`
- Removed the level between an area and a bundle: everything inside an area is a bundle, and bundles may hold bundles
- Added a migration that moves an existing space to the new areas on update, keeping every file
- Changed the documentation on how the space is organised and on the idea behind it
- Added `setup upgrade --from <path or URL>`, which updates from a source you name instead of from the published release
- Fixed the archive index losing its content when the `records` command family became `archive`: the file is renamed with it
- Fixed the paths inside the archive index still naming the old areas, so every hit led nowhere
- Fixed paths written into notes still naming the old areas, where the file is at the new one
- Fixed the searchable text in the archive index still naming the old area, so a search answered the wrong way round
- Changed `setup validate` to report a file under the system folder that no version ships any more
- Fixed the renamed archive documentation page and the wireframe library never arriving in an updated space
- Added a step that takes documentation and templates an earlier version shipped out of the system folder
- Changed every structural step to carry a revision, so a corrected one reaches a space that already ran the old version
- Changed an area rename into one mechanism that covers folders, kinds, routing, the search index, its searchable text and notes
- Fixed a whole-space restore leaving behind empty folders the snapshot never had
- Changed a whole-space restore to name at the end what a keeping rule of yours protected, instead of as a failure line at the start
- Fixed an area rename splitting a bundle in two when the same name existed on both sides, leaving half of it empty
- Fixed a folder holding nothing but empty folders counting as occupied during a rename
- Fixed a second discard of the same file on the same day failing instead of standing beside the first
- Fixed a required folder staying gone when a rename emptied it
- Added a check that refuses to write a command into a standing rule when the command does not exist
- Fixed the archive index keeping the text of a document as it was before an update rewrote the file
- Changed a failed check after an update to trigger a rollback only where the update caused it
- Added a step that takes the machine's own files out of the space root, where older versions kept them
- Changed that step to keep a copy at the old place that is newer than the one in use, and to say so
- Added a step that takes keeping terms out of use that still carry a legal category per country, so the current three buckets apply
- Added a check that reports a bundle holding nothing but its own page, which is a single item given a folder
- Changed the documentation to be for the person who owns the space, with a specialist's own method moved to the specialist
- Changed the tag synonyms into a file you can read and change, instead of a table inside a documentation page
- Changed filing to take the original out of the inbox once its content is in the space, unless a rule of yours says it stays
- Changed a dated task to stand in the journal day it is due, instead of the day it was asked for
- Added `task add --every weekly|monthly|quarterly|yearly`, which writes the next occurrence when you tick one off
- Changed the keeping terms in a space to hold your decision and your changes, instead of a copy of the periods that could not be improved
- Changed `housekeeping` to report a bundle that holds nothing but its own page, and to list the bundles of every area side by side
- Changed `bundle create` to list what already exists in every area, so a new bundle is not made beside a home that is already there
- Changed a search that finds nothing to say whether the index is empty or simply lacks the word
- Changed the update history to be written by the update itself, with the source it came from, instead of by the specialist who ran it
- Added `snapshot restore --all`, which puts the whole space back as it was in one snapshot, as the way back from an update
- Changed three guards from refusing to asking, so you decide: the dash, task-line and slide-library checks now show what they found and wait for your yes
- Added a check at session start for sessions that were never closed, with an offer to write the hand-off for them now
- Added `session digest`, which reads what was said, asked and went wrong out of the conversation your program recorded, so a hand-off can be written after the fact
- Fixed a bundle rename leaving the folder under its old name, so the rename had to be finished by hand
- Changed a rename to print the command that undoes it, and to name any running text that still says the old name
- Changed the summary before a change to be sized by whether a command takes it back, not by how many files it touches
- Removed the snapshot before a rename, which its own command reverses
- Added a check that refuses a bundle name of more than two words, since one cut to fit a single file holds a single file for ever
- Added `/zanmai-housekeeping`, and a weekly surfacing of the same shape findings in the greet
- Fixed a never-do write guard matching the script's own invocation path instead of the write target, refusing an ordinary write for naming the script that ran it
- Changed `general.md` and an expert's own lessons file to write without asking first, replaced by a periodic critical read in the background, in the same weekly moment as housekeeping
- Added a hard refusal for a `general.md` write naming a specific date or a specific running instance, ahead of the periodic read
- Added `file status --set --check`: reports a status change's own open task lines and every linked file's, so a person can see what a cancellation touches before anything is written
- Fixed `index find` reporting a missing pattern index instead of naming a bad `--tokens` value, when tokens ran together without a comma
- Fixed `index search` only taking `--root`, where every other `index`/`archive` command reading a subfolder takes `--scope`
- Fixed housekeeping's shape findings being relayed as a plain list, with nobody asked to connect what belongs together across areas by matter rather than by name
- Changed setup into four blocks: who you are, what the space is for, how it is laid out, and what it should be able to do
- Added a short table of the areas during setup, with one example of what lands where
- Added a starting structure at setup: each area, project or goal you name becomes its own bundle under its own name
- Added a capability overview at setup, with the programs needed for what you pick offered by name and size
- Added a catch-up at session start for a space older than the current setup questions: it asks only what is missing, once
- Fixed the space index reporting life, knowledge and archive as empty while they held bundles
- Added a closing note at setup that a missing capability can be built as an expert for your own case
- Added the three habits at the end of setup: starting with a hello, closing a session with one command, dropping things in as they arrive
- Fixed a file your routing rule pins in the inbox being counted as waiting at every session start
- Changed the routing table into the only place that decides what happens to incoming material, with an instruction found elsewhere turned into a rule instead of followed
- Fixed work dated months or years ahead being read out as an open task at every session start, now left out until its date comes closer
- Fixed the write guard refusing a command because the text it wrote merely mentioned the archive or the trash
- Fixed the search guard refusing a command that only filtered another command's output
- Fixed `update_check: false` promising to stop the daily version check while nothing read it, and it now also works in your own profile, where no update can reset it
- Added `setup upgrade --force`, which applies the files again when the version says there is nothing to do
- Added `life/task.md`: one plain list for what has to be done and belongs to no particular matter
- Changed a dated task to stay on that list instead of creating a journal entry in a year nobody has reached yet
- Changed calling something off to first show what hangs off it, in both directions and two steps out, with one question about each
- Added a directory to the documentation: every page says the situation it settles, and the table is generated from those lines
- Changed the file read at every session start to hold only what would go wrong unnoticed, with the rest reachable through that directory
- Fixed Zanmai translating its own folder names when answering in another language, so a reply named a folder nobody has
- Changed the question about what your machine still needs into what is actually missing and what it costs, instead of a table of everyone's job
- Changed that question to group by what you would use it for, instead of naming single libraries nobody can judge
- Fixed an update taking two snapshots of the same state, one from the specialist and one from the command itself
- Fixed an update reporting the replaced files before the snapshot it had already taken, which read as if the copy came second
- Fixed the rule for building file names being applied to the text as well, so a piece of work was called `Ersatz fuer Ollama`
- Fixed German text losing its umlauts on its way into a task or a piece of work, where you read it back at every session start
- Fixed a read being refused as a write because a greater-than sign stood inside quotes, as in an awk program
- Removed two fields on a life bundle that promised to track a rhythm and were read by nothing
- Changed a specialist's instructions never to send anyone into your documentation, which is written for you and not for them
- Changed closing a matter to stop once until that list has been put to you, instead of setting the field and moving on
- Fixed work whose result is already in the space being read out at session start as still waiting on you
- Fixed a deadline in a file nobody had opened for weeks dropping out of the open items entirely
- Added `/zanmai-show-welcome`, which shows the list the session opened with, rebuilt as things stand, for when the greet has scrolled away
- Changed the catch-up to also cover the capability overview for a space that never saw it
- Fixed a plain search of your own notes coming back empty: the rules that keep your material out of the update repository were being read as search rules too
- Added `.ignore` at the top of your space, so a search reaches your material and leaves out the snapshots, the trash and the generated index
- Changed both ignore lists to be rewritten at every session start, so a renamed area cannot leave one of them behind
- Removed the ability of a rule to keep a file in `inbox`, which made the one area that empties into a place things live
- Added `routing set --keep`, which says once per sort of material whether the file itself is still wanted after its content is filed
- Added `routing set --by`, so a sort of material goes straight to the specialist who handles it
- Fixed a file whose content was filed staying in `inbox` when the filing step had not copied it, instead of moving to where its result is
- Added a rule writing down by itself what happened to the file, where it had no answer for that yet, and saying so with the command that changes it
- Fixed a command changing a file on another machine being stopped as a write into your space
- Fixed text inside a here-document being read as a write target where it is only being written down as content
- Changed a handover sent off without a brief to be turned away as a plain note instead of an error block, and shortened it
- Changed the README to say what you get in two sentences, then what you can do with it, with the installation right after
- Changed the documentation on connections and on setup to say what you get out of them, instead of how they are built
- Changed the pages on what runs automatically and on commands to a tenth of their length, keeping every check, command and specialist they name
- Fixed the page on work that outlives a sitting describing a table and a format that no version writes any more
- Fixed the same page promising that an answer written into the file is picked up, which nothing reads
- Fixed the journal page promising that a routine you track is updated from an entry, which no version does
- Fixed the installation guide never naming Claude Code, without which nothing runs
- Added the missing links between documentation pages, so no page is reachable only through the index
- Fixed a search reaching inside an editor's database folder, which everything else in the space leaves alone
- Fixed the page on memory naming four things that survive a session where there are five
- Fixed the page on contacts claiming a link between a person and an organisation is enforced, which nothing does
- Changed the pages on research and on speech to state what holds generally, instead of what one run measured

## [0.5.2] - 2026-08-31

- Changed a write into a file that stays true after the session to ask you first, showing what would be written
- Fixed the guard on those files only watching two tools, so a shell command wrote them unasked
- Added the count of standing rules to that question, with any rule that grew past one entry named
- Fixed a hook wired in the host config that this version does not implement going unreported
- Fixed six of the twelve experts never being told where the script lives, which cost them their first commands looking for it
- Changed the journal to one entry per day, filed under its year, so a month is thirty files you can read
- Removed the weekly, monthly and yearly notes, and with them the rollup that wrote into your own text unasked
- Removed `journal ensure`, which created an empty entry for a day nothing had happened on
- Added a migration that an update runs itself: your existing entries move to the new shape, nothing is dropped
- Fixed that migration moving hidden system files along, which left a folder named for a year they do not have
- Fixed that guard holding a read for a write when the command silenced its errors, so opening a session asked for permission

## [0.5.1] - 2026-08-30

- Added `records rename` and `records move`: a kept document or a whole section gets a better name or a new place, and the search index follows
- Added `--scope` to `records survey`, so it reports the folder that was just read in instead of the whole archive
- Fixed `records file --area health/x-rays` collapsing a section inside a section into one folder
- Fixed `bundle index-entry` refusing to write the line for a member that had none, which left a hand-edit of the index as the only way
- Added `--truth` to `bundle create`, so a sub-bundle with a theme of its own gets its main file in the same call
- Fixed the line describing a bundle's main file staying English in an index whose headings were translated
- Added the resolution of `zanmai.py <subcommand>` to the session briefing, so a run does not look for a file that is not at the space root

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
- Fixed any write path built from data being able to create a folder the space does not have
- Changed contacts on the records path to follow a matter rather than every sender on every document
- Added `records file`: a whole pile of documents into the records area at once, read as they land
- Fixed documents being skipped by the index because of their file name, by reading what a file is from the file
- Fixed a search for a date, an amount or a case number failing instead of answering
- Fixed the index still answering for documents that had been moved or deleted
- Fixed a document being unfindable by the name it carries, by searching the name along with the text
- Added hanging a whole folder of documents on a matter, with dates, amounts and counterparties taken from what was read
- Fixed a matter note being written with English headings in a space kept in another language
- Fixed the records area missing from the master index
- Changed routing rules to key on what something is rather than on its file type, so the same report routes the same however it arrives
- Fixed a file being thrown away out of `import/` while its content had reached nowhere in the space
- Fixed that check being avoidable by moving the file out of `import/` by hand
- Changed the work objects to one JSON file in `zanmai/open/`, replacing a table format no editor here draws any more
- Fixed the page listing what ships: it named a command that does not exist and left out twelve that do, two skills, a specialist and two hooks
- Changed the slash-command menu to hold only what you would ask for by name, so a specialist's working method is reached through that specialist instead of sitting in your list
- Removed fifteen entries from that menu that nobody types, which also gives every session start less to carry
- Fixed two pieces of work opened under the same name in the same minute sharing one id, which made the second unreachable and closed the wrong one
- Fixed a version change being able to lock the space out of itself, where a guard the installed version does not have refused every command
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
- Fixed files landing outside the space when the host offered a scratch directory

## [0.3.7] - 2026-08-26

- Added `work show`
- Fixed the next session opening on a stale day
- Fixed `work` writing its database wherever it was called instead of the space root
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

- Added the space: plain files in folders named after what is going on, not what stage a file is at
- Added the specialists for filing, research, design, images and housekeeping
