# Changelog

All notable changes to Zanmai. Format: <https://keepachangelog.com>. Versioning: semver. The 0.x
series is pre-stable, which means a folder name or a command can still change between versions, and
when it does, it will say so here.

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
