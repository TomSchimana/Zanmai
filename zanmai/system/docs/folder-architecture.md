[← Zanmai Documentation](index.md)

# How the space is organised

**Read this when:** something has to be filed and it is not obvious where, or two areas fit at once.

Everything you keep sits in one of eight areas, and which one is right is decided by what happens to a thing next, never by how important it is. That is the whole cut, and it is why nothing has to be moved later.

## Space, area, bundle

Three words, and there are no others.

Your **space** is your Zanmai installation: the directory everything lives in. You can install
Zanmai more than once on a machine and have several spaces, if you want things kept apart. One for
work and one for private life, say. You can just as well put everything into one. That is your call,
not ours: two spaces know nothing of each other, so the only question is whether you want to look
into the same place in the evening as you do during the day.

Inside the space are eight **areas**. Inside an area, everything you make is a **bundle**: a folder
holding what belongs to one matter, with a note in it saying what the matter is. Bundles may sit
inside bundles, as deep as you find useful.

## The eight areas

An area is defined by what happens to what lies in it, not by what kind of thing that is. This is
the whole point of the cut. Sorting by importance goes wrong because importance changes without
anyone noticing: the trip is cancelled and the folder still says it is what you are working on,
because nothing is broken and nobody has a reason to tidy.

- **`inbox`** is where things arrive, however they got there: you put something in, a scanner drops
  a file, an import brings a pile. You do not decide where anything belongs at the moment you put it
  down. That happens later, in one pass. The inbox is a passage and it is meant to empty.
- **`workbench`** is your desk. This is where work happens and where something comes into being that
  was not there before. You put things down freely and move them around; the structure and the index
  are Zanmai's job. Everything belonging to one piece stays together: the drafts, the material, the
  correspondence.
- **`life`** is what is yours and matters to you now. Health, money, family, the flat, the car,
  hobbies, and at work your own role, the team, further training, a standing responsibility such as
  the website. Habits belong here too, and so does what you have set yourself. The difference to the
  workbench is the difference between building and building on: there you make the individual
  pieces, mostly from nothing; here stands what came of them.
- **`knowledge`** is what would still be right for somebody else, because it can be looked up or
  rebuilt from scratch. A write-up of your own machine does not belong here, a comparison of the
  best games for a C64 does. The research lives here; what you do with it lives in `life`.
- **`archive`** is your filing cabinet. An invoice, a policy, a certificate. Not "never needed
  again": it is kept precisely because you take it out again. You do not work on anything here and
  you change nothing, unless something is added or you find an error. Every piece carries a date and
  a keeping reminder, so that in five years you do not have to guess whether it still has to stay.
- **`journal`** is the time axis: one entry per day, filed under its year. What is on your mind goes
  into today, and what happened on a day belongs to that day. Nothing is ever taken out of an entry.
- **`contacts`** is people and organisations, split into `people` and `organisations`. A person is
  never a folder somewhere else; everything else points at them.
- **`zanmai`** is what the machine keeps for itself, and the only rule about it is that you never
  open it by hand.

Any Markdown editor opens this space, and none of the names depend on which one you use.

## Nothing has to move

There is no forced route. What is clear from the outset goes straight where it belongs. You take
the invoice out of the letterbox, see that it is the yearly one, and file it; it lands on the desk
only if you have to pay it first. The same here: research goes straight to `knowledge`, something
finished goes from the inbox straight into the archive. Only what is actually being worked on goes
across the workbench.

**Staying put is a valid end state.** In `knowledge` it is the normal case rather than a backlog you
owe someone. Something nobody ever looks at again has still ended up in the right place.

There is one exception, and it is deliberate: **the desk gets cleared.** A piece of work has an end,
so `workbench` is the one area that empties. You do not have to remember that either. Zanmai sees
that something has been sitting untouched, asks you about it, and on your word takes it further.
When you clear the desk there are four ways out: throw it away because the result does not matter;
take part of it out and drop the rest; keep the plan even when the result goes; or keep everything
and clear away only the working files. Whatever is thrown away goes to the trash. The rest has to go
somewhere, and the question for that is what it is.

## What happens by itself

Each area has its own pace, and that pace is its real definition: not why something lies there, but
what becomes of it.

The `inbox` is emptied daily. The `workbench` speaks up when nothing has happened to a piece for a
while. In `life` nothing ages by itself, but after a long quiet spell you are asked whether it still
holds. Knowledge is never tidied up; what ages there is the content, not the filing. A price
comparison from four years ago is wrong, a note about keyboard shortcuts stays right. The `archive`
grows without limit, and the term hangs on the individual piece rather than on the area.

You are always asked, and nothing is re-sorted behind your back. Nothing disappears by itself, with
one exception: what you throw away sits in the trash for thirty days and is then really deleted.

## Why the cut is made this way

You do not think in project stages, and a filing plan that asks you to decide the stage of every new
thing is a plan you stop keeping after a fortnight. The same trip would be a project, then a
recurring thing, then something past, and each of those would mean moving it.

A workplace asks a different question, and it is one you can answer without judging yourself: what
happens to this next. Something arriving lands in the inbox. Something you are building sits on the
desk. Something that is yours and current lives in `life`. Something anybody could look up is
knowledge. Something finished but kept goes into the cabinet. Two of those empty themselves, three
of them do not, and that is knowable rather than a matter of taste.

Two families of words, and they never mix: the workplace (`inbox`, `workbench`, `life`, `knowledge`,
`archive`) and the machinery (`zanmai`), with `journal` and `contacts` beside them as time and
people. A name that falls between two families is the wrong name.

An area is the wrong area when its question does not fit. Where two questions fit, it is two things: split it. `workbench/` is the only area that empties; in `knowledge/` staying put is the normal case. The line between `life` and `knowledge` is whose it is: the research belongs to knowledge, what the user does with it belongs to their life. The line between `life` and `archive` is whether they still act on it.

## Bundles

A **bundle** is a folder holding everything about one matter. `life/health/` is one,
`life/health/back-training/` sits inside it. The words are yours; nothing below an area ships with
the space.

Each bundle holds a main note carrying the matter itself, its description and what belongs to it.
Internally that one is called the **truth file**, because it is the single place the matter's own
facts live rather than being repeated across the files around it. Beside it sits an `INDEX.md`
listing what is in the folder.

Three more words you will meet:

- The fields at the top of every note, between `---` lines, are its **frontmatter**. They hold the
  structured facts: what class it is, when it was created, where it came from.
- A link from one note to another is written `[[like-this]]` and called a **wikilink**. It uses only
  the file's name, not its path, so moving a folder does not break links.
- The short, lowercase, dash-separated form of a name used in filenames is the **slug**.
  "Kundentermin Meyer" becomes `kundentermin-meyer`.

A bundle is the normal case, not the exception. A single loose file is for material that genuinely
stands alone.

### The bundle is the broad matter, never the single item

This is the rule that goes wrong most often, so it gets its own section.

You think from general to specific, so the folder is the general subject and the specific things
live inside it. A place name, a product model, a medication, an appliance: none of those is a bundle
of its own. "Travel" is a bundle and one trip is a note inside it. "Health" is a bundle and one
medication is a note inside it.

A specific item can sit on the workbench while you are actively dealing with it, but its long-term
home is inside the broader bundle, as a flat note in that folder rather than as a folder of its own.

### When the bundle does not exist yet

For the first item in a new subject, Zanmai proposes a name and asks you once, in your language,
whether to create it or use a different name. Bundles are cheap; naming them right is the only cost,
which is what the question is for.

For a genuinely one-off item, or when you are unsure, the note lands flat in `knowledge` as a
temporary state and is surfaced in a later briefing as something still to file. When a second,
related item arrives, Zanmai proposes making a bundle out of both.

If material arrives for a bundle that already exists, that bundle is reused. A second folder for the
same subject is not created.

### Bundles inside bundles

A bundle can contain further bundles, but only when that actually helps. The test is whether the
narrower subject has enough identity and material to stand as its own thing; if not, loose notes in
the parent are clearer. When in doubt: fewer folders, more notes per folder. Empty drawers are the
failure mode.

Two shapes exist side by side:

- One with **its own identity** gets its own main note carrying a link back to the parent.
- One that just **groups narrow material** inside the parent, for instance loose clippings, has no
  main note; the parent carries the matter.

Both get their own `INDEX.md`. Because links use file names rather than paths, nesting never breaks
a reference.

Restructuring later is always possible. When new material would sit better with existing material
rearranged, Zanmai proposes the move as part of its plan rather than doing it silently.

## Everything is linked

An invoice is not a lonely file in a folder. It hangs off the insurance it belongs to, which hangs
off the company, which hangs off the person you dealt with. That is why you can ask a question in
your own words instead of remembering which folder you picked two years ago, and why hundreds or
thousands of documents stay workable rather than becoming a heap.

A whole matter stays in one place. The current policy, the one it replaced, the correspondence and
the invoices belong in one folder, the way they would sit in one hanging file. Which version applies
is written on the paper and gets read; a folder does not get to claim it. Splitting a matter across
two areas is the mistake, not the tidy-up.

The bundles inside an area exist for you, not for the assistant. It does not need them to find
anything, it follows the links. You need them, because a structure you can see is what makes a
growing space feel manageable instead of endless.

The whole reasoning behind this is in [the idea behind Zanmai](philosophy.md).

## How wide a bundle should be

A bundle is where things collect, not a label on one thing. Its name says the subject, and the subject has to be
wide enough that the second and the tenth thing still belong there. `ai` is a subject, `travel` is a
subject. `ai-coding-workflows` is the occasion that produced the first file, and a name that narrow
only ever fits that file.

The file itself can be as specific as you like, and it should be. A file is about one thing, a folder
is about a subject.

Zanmai holds the line for you: a bundle name of more than two words is refused, with the subject it
heard named back to you. Where the narrow cut really is what you want, it is one word away. The other
end of the same mistake gets reported too, because `housekeeping` names any bundle holding nothing
but its own page, and that is usually one that was cut too tight months earlier.

## Files that are not notes

**There is no folder for them.** A PDF, an image, a calendar file, an audio recording, a transcript:
each one lies flat inside the bundle it belongs to, next to the notes about it. Markdown is one
format among several here, not the content with everything else hanging off it as an attachment.

The reason is the same one that makes bundles worth having. A folder that sorts by file type cuts
apart exactly what the bundle exists to hold together: the recording, the transcript, the scan and
the note about them are one matter. That is why there is no shared attachment folder, and no
`files/` inside a bundle either, which would be the same mistake one level down.

**What keeps a full bundle readable is its `INDEX.md`, not a sub-folder.** Every file gets a line
there. A sub-folder is made only when it is a nameable thing in its own right, and the test is
simple: can you name it without using the words attachment, files or assets? If yes, it is a bundle
of its own with an index. If no, everything stays flat. Two things reliably pass that test, and both
can be filled by machine: time, and where something came from.

Where a file lies and where it appears are two different questions. Embedding works on the file
name, not the path, so a note shows its picture wherever the picture sits.

The one exception to all of this is your editor's database folders, which end in `.base` and contain
a table, its column definitions and one page per row. Those belong to the editor entirely. Zanmai
reads nothing inside them, writes nothing inside them, and leaves them out of every scan. You create
and edit them in the app; they can live wherever you put them.

## Coming in and going out

- **`inbox`** is deliberately a heap: throw things in however they land, and Zanmai takes them up by
  itself. **The folder is the automation**, so it has no sub-folders for purposes: what kind of file
  something is decides what happens to it, not where you put it. The one exception is an automatic
  feeder that needs a fixed target path, such as a scanner watch folder. Everything is read
  oldest-first and in full before any of it is acted on, because a later item can withdraw an
  earlier one. Nothing links to files sitting there, since they are not filed yet, and nothing in
  there is ever the only copy.
- **`workbench`** is both the way in and the way out. Work you are on, and work Zanmai produced for
  you, sit in the same place: one folder per piece with its files kept local, so you can pull the
  whole thing out. There is no separate export folder, because a finished piece and the drafts that
  led to it are the same matter and a second folder would only cut them apart.

Briefings written for a single decision land on the desk too, rather than in a review area of their
own: you see them in your editor and open them directly, and when you are done they move into the
logs. Plans for larger operations do not become files at all; they are shown to you in the chat and
recorded afterwards.

## The system area

`zanmai/` holds everything Zanmai needs for itself. The test for what belongs in there is not "what
you do not need" but **"what you never touch by hand"**. It has no leading dot and is therefore
plainly visible, which is on purpose: an area that runs your space should not be hidden from you.

Two halves matter, because updates treat them differently:

- **Replaced on update:** `zanmai/system/`, the distribution itself. Editing anything in there is
  pointless, the next version overwrites it.
- **Never touched by an update:** your profile (`user.md`), `extensions/` for anything grown
  specifically for this space including new specialists, `connections/` recording what has been
  wired to outside sources with references only and never secrets, `memory/` for what carries across
  sessions, `design/` for brand values, `logs/`, `history/` for the snapshots, `trash/` and `temp/`,
  plus `runtime/` for what was provisioned on this particular machine.

That split is what makes an update safe: one half is replaced wholesale, the other is left alone.
Machine-local means `runtime/` is not meant to travel to another computer.

Three of those clear themselves out. What differs is how long each one waits, and each number comes
from what the folder is actually for:

- **`trash/`** holds what was thrown away, for **30 days**. It exists because Zanmai deletes things
  and that has to be reversible; until the 30 days are up, anything in there can be put back exactly
  where it came from. It is your own change of mind, so it gets the long window.
- **`temp/`** is where Zanmai puts things down mid-job: a render preview, an unpacked archive, a
  download before it is read. It is cleared after **7 days**. Anything still sitting there is a
  fault rather than rubbish, so it is deleted **and said out loud**.

- **`history/`** keeps the snapshots, for **7 days**, and the newest one always stays whatever its
  age. A snapshot is a point to jump back to after an update or a large edit, not a backup, and
  whether one of those went wrong is known within days. Every version of every file is stored once
  by its content, but a changed video or deck is stored again in full, which is the other reason the
  window is short.

## The briefing

`zanmai/memory/briefing.md` is the current picture of what is going on in the space: what is active,
what is open, and where links point nowhere. It is rebuilt whole rather than patched, at every
session close, after any larger operation, or on request.

It has three parts, always present even when empty: the current state, the open items drawn from
recent notes, and the gaps worth noticing. The session-start hook reads it and hands it to the first
reply, which is why the greeting is fast and already knows what you were doing.

It is written by Zanmai, not by you, and manual edits are overwritten at the next rebuild.

## Related

- [The idea behind Zanmai](philosophy.md), why the cut is made this way
- [What you keep](archive.md), the one area that grows without limit
- [Finding things again](finding.md), how anything in here is found

---

[← Back to the documentation index](index.md)
