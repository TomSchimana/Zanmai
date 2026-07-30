# Changelog

All notable changes to Zanmai. Format: <https://keepachangelog.com>. Versioning: semver. The 0.x series is pre-stable.

## [0.3.4] - 2026-07-30

### Changed

- **You decide what a new connection may do, not Zanmai.** Setting up access to an outside source silently limited it to reading, so asking for a connection you wanted to write with gave you one that could not, and nobody said so. Setting one up now asks in one menu whether it is for reading only or for reading and writing, and configures exactly that. Writing back to a source is still shown to you before it goes out, and nothing is mirrored continuously.

### Fixed

- **The ZenNotes command line acts on the vault you are in, not on another one.** Its helper keeps one vault of its own as the default and ignores which folder a command runs from, so archiving or trashing a file could quietly reach into a different vault. Every call now names this vault outright, and the helper is only used once ZenNotes has actually opened this vault, which is what makes it able to act on it. Until then, and whenever the helper is missing, the same operations run as ordinary file moves, which works but does not keep the restore path.
- **"The command line is available" now means available for this vault.** The setting recorded whether the helper was installed on the computer, which reads as usable and was not, so anything relying on it worked on the wrong material. It records usability for this vault instead, and the session-start check switches it on by itself the first time you open the vault in ZenNotes.

## [0.3.3] - 2026-07-29

### Fixed

- **Nothing is written into your files that you did not ask for.** Obligations worked out from a booking, a print-the-voucher, a decision still open in the terms, were entered into your own notes as open items. They now belong in the chat as a sentence: advising is the job, putting it in your file is your call. The same holds for a line you wrote yourself, which no longer gets reworded or tidied up while the file is updated around it, in a later edit as much as in an import.
- **A hand-over cannot switch off a house rule.** Each specialist follows rules that protect your material, and an instruction from the concierge was able to override them without anyone noticing, which is how those unasked items got written in the first place. A specialist now declines that part, finishes the rest of the job, and says what it refused and why. It also means nobody can order an extra section into a report that its own format does not have.
- **Corrections are kept as the rule they set, not as what you said.** Closing a session recorded your corrections word for word, including how they were phrased in the moment, and that ended up in a file in your vault. What gets written now is the concrete thing that was off and the rule that holds from here, precise and unsoftened, without quoting you. A chat message is fleeting, a file is not.
- **Taking a snapshot works the way every other command does.** Asking for a backup by hand failed with an argument error, because this one command still expected two paths spelled out while the rest simply act on the vault you are in. It now takes the current vault and a short reason, which is also the form the house-keeper was already documented to use before an update, so the safety copy before applying one no longer depends on getting an undocumented spelling right.
- **A vault refreshed without a fresh install is complete again.** Empty folders cannot travel in a repository, so a vault that had its files renewed rather than installed came out missing the drop folder for incoming material and two internal ones, and the structure check reported it as broken. The refresh now creates whatever the distribution requires.

### Changed

- **What you approve is as big as the job.** Filing four files into a theme you already have was presented like an import of dozens into a new structure: a tree with two branches, a grouping decision that decided nothing, and everything the sources gave up, so saying yes to something small cost minutes of reading. Building something new still gets the full picture. Anything landing in a theme that exists gets a dozen lines at most, what changes, in which file, and whatever turned up that changes what you expected. The rest of what was read goes into the log, where you can follow it if you want to.
- **You are only asked what the material actually leaves open.** Three questions ran every time, including the two the situation had already answered. Scope is still asked every time. How to file is asked when a new theme is being created, since an existing one already answers it. What to do about a name clash is asked when there is one. Whatever is settled by default is named in the approval instead.

## [0.3.2] - 2026-07-27

### Fixed

- **A job is thought through for its size before it is handed over.** A request such as "several places to stay, each with its rating, its number of reviews and what recent reviews say" quietly means one page looked up per candidate, which is where most of the time in a long research run went. The hand-over now puts the deciding criterion first, so the detailed look-up happens only for what passes it, and a confirmation says what the run actually covers, not just its topic.
- **A specialist's work no longer holds the conversation.** Handing over a long job, research across sources or a large import, kept the chat occupied until it finished, so anything written in the meantime sat unanswered for the whole run. Every hand-over now runs in the background: you hear in one line what is running, keep working, and the result comes back when it lands.

## [0.3.1] - 2026-07-26

The first release that arrives as an update rather than a download, which is also the point of it: the update path itself gets its first run against the real repository.

### Fixed

- **Commands no longer demand the vault path.** Twenty-four subcommands required the vault as an argument while ten took the current directory, with no rule to tell them apart. So a call like `memory briefing` failed with an argument error and had to be repeated with a path. All of them now default to the current directory, which is where they are documented to run.
- **The update check is mechanics again.** Asking for an update ran the full house-keeping workflow even when nothing was available: the check was re-verified with separate git calls, the changelog was opened for a version that did not exist, and a report with six headings came back to say nothing had happened. The check is now a single inline command, and the house-keeper is only involved when there is something to apply.

### Changed

- **The version check runs at every session start**, not once a day. It is one short request, so a schedule bought nothing; a session without network falls back to what the last one found.
- **Zanmai addresses you personally.** Where a language distinguishes a distant from a personal form of address, it takes the personal one. Asking someone for the name they want to be called by and then addressing them formally contradicted itself.

## [0.3.0] - 2026-07-26

**First public release, and a developer preview.** Everything below is what Zanmai is, not a list of changes: earlier versions were never published, so there is nothing to compare against. It is a preview for people who want to see how it is built, not a finished product, and a new version can still change how things behave.

### The vault

Plain Markdown files in a folder you own, opened in any editor you like, Obsidian included. The recommended one is ZenNotes, leaner and faster, and the one Zanmai integrates with closely, so the layout follows its conventions. Everything kept lives under `inbox`, sorted by the attention it needs rather than by what kind of thing it is: `focus` for what is current, `habits` for what recurs, `knowledge` for what stays available, and `contacts` for people and organisations. Deliberately no projects folder, because lifecycle categories force a decision that keeps changing. Material on the way in or out sits outside `inbox`, in `_import` and `_export`, and every non-text file lives in one shared `assets` folder.

A theme groups related material into one bundle, with the broad subject as its name and specific items as members. Frontmatter follows a shipped schema and is enforced when a file is written. One fact lives in one place; everything else links to it.

### Working with it

- **Capture.** What you write lands in today's, this week's or this month's note unchanged, with mood and links handled around your words rather than inside them. Which periodic notes exist comes from your ZenNotes settings, and rollups from one layer to the next are written automatically.
- **Import.** A folder of mixed material is read in full, grouped along an axis derived from the content, and proposed to you as a plan before anything moves. People and organisations found in the material become contacts. Filenames are cleaned, tags consolidated, and your body text is never rewritten.
- **Search.** A vault index that refreshes itself at session start, so edits made directly in your editor are picked up. Answers come from the vault, and going to the internet takes an explicit research request.
- **Research.** Multiple sources, cross-checked, returned as a cited write-up filed where it belongs. Video and repository sources run through their own pipeline with transcription.
- **Design.** Flyers, decks and one-pagers composed in your own visual language, read out of your existing templates as concrete values rather than descriptions. A rendered page is the default medium, as a screen file or a print-ready PDF with fonts embedded and verified. Affinity and PowerPoint are there for when you need a native editable file.
- **Images and video.** Generated through image and video services you have connected, with prompt craft and identity anchoring rather than a bare call, and a cost gate before anything is spent. Existing pixels are edited locally with no model involved. Results carry the official EU disclosure icon and a machine-readable C2PA credential where disclosure applies, and an existing credential from the generating platform is preserved rather than stripped.
- **Contacts, plans and housekeeping.** Bundle renames, broken-link repair, structure checks and snapshot management, each behind a preview and a confirmation.

### How it behaves

- **Specialists rather than one assistant.** A concierge takes the request and hands it to whoever's job it is: filing, research, connections, design, imagery, expert-building, housekeeping. Each has its own rules and its own bar for finished work. The concierge owns every conversation with you; the specialists never interrupt mid-run.
- **Nothing happens unannounced.** Anything touching many files is shown as a plan first, a snapshot precedes risky writes, and a costly or hard-to-reverse job is described and confirmed before it starts.
- **It stops instead of improvising.** A missing tool is named with the one step to enable it, and the job halts there rather than being assembled from whatever happens to be installed.
- **It remembers across sessions.** Decisions, corrections and per-tool findings carry over, so the same ground is not re-covered.
- **It writes like a person.** Produced text takes its tone from the source it is written for, and the constructions that read as machine-made are kept out.
- **It can grow.** When no existing specialist covers a need, a new one is researched, written and wired in, in a place that survives updates.

### Setup, tools and updates

- **Setup** is a conversation on first start: it checks what your machine has, asks what it needs to know, and lays out the vault. Nothing is guessed from your system.
- **Tools are detected, never assumed.** A shipped register lists every external tool Zanmai can invoke, per operating system, with what it is for. Presence, version and identity are verified on the machine, because a name does not guarantee the program behind it. Small Python libraries install into a managed runtime environment, never into the system Python, and only when a job needs them.
- **Prerequisites are checked before a specialist starts**, so no job fails halfway for a missing renderer or library.
- **Updates work whichever way you got Zanmai.** A cloned vault is fast-forwarded through git and stays a clean clone, so your own `git pull` keeps working; any other copy has the new files fetched over HTTPS. Only the files the manifest calls distribution are replaced, and the paths it calls user-immune are never touched. Your content is kept out of version control, so it can neither be overwritten nor committed by accident. Zanmai checks for a new version at most once a day and offers it once. A version that arrived some other way is noticed at the next session start, and the host-side configuration is brought in line by itself.
- **Guards run at the tool layer**, not on good intentions: required frontmatter, permission boundaries, index consistency, and the session-start briefing.

### Documentation

Documentation ships with the system, readable in the vault and on GitHub, including installation guides written for a non-technical reader and a credits page naming what Zanmai builds on. It is the same material Zanmai answers from, so asking it how something works produces an answer from these pages.

### Known limits

Design, image and video generation work but are still being sharpened. Windows is tested for setup and the core, while the heavier media paths are still being hardened there. Vector graphics and video editing are not in yet.

## [0.2.0] - 2026-07-12

Not published. Periodic notes gained a monthly layer with automatic rollups, capture became verbatim, the index learned to refresh itself at session start, and connections to sources outside the vault became usable rather than merely catalogued.

## [0.1.0] - 2026-06-22

Not published. The first working version: a concierge dispatching specialists for filing, research, connections, capture and housekeeping, the command-line engine behind them, and the first deterministic guards against destructive writes.
