# Changelog

All notable changes to Zanmai. Format: <https://keepachangelog.com>. Versioning: semver. The 0.x
series is pre-stable, which means a folder name or a command can still change between versions, and
when it does, it will say so here.

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
