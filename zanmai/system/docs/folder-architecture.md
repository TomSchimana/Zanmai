[← Zanmai Documentation](index.md)

# How the vault is organised

Which folder holds what, why it is sorted that way, and the few words worth knowing.

## What you see

At the top level of your vault, with nothing above them, in the order things travel through: where
it turns up, where it takes shape, where it gathers, where it settles.

- **`journal`** is the time axis: a bundle per day, week, month and year. What is on your mind goes into the day, and so does what happened that day, photos and recordings included.
- **`focus`** is what you want to reach and what you are looking at.
- **`doing`** is your desk: work that has an end, one folder per piece with every draft of it together.
- **`habits`** is what has a beat.
- **`knowledge`** is everything you have gathered, with nothing ranked and nothing decided.
- **`trusted`** is the small set of things you have settled on.
- **`archive`** is what is finished and kept: the document from outside, and your own completed piece.
- **`records`** is what has to be kept, or is worth keeping: contracts, policies, tax papers, certificates, receipts you would need if something broke.
- **`contacts`** is people and organisations, split into `people` and `organisations`.
- **`import`** is where you drop things. It empties itself.
- **`zanmai`** is Zanmai's own area, and the only rule about it is that you never open it by hand.

Any Markdown editor opens this vault, Obsidian included, and none of the folder names depend on
which one you use.

### Why records is not a folder inside the archive

The two look alike from outside: both hold things that are done with. The difference is what you
are allowed to do with them, and it runs the other way round from what the names suggest.

The archive holds what answers no question any more. You may clear it out, and one day you will.
`records` holds what a law, a contract or a later need says has to stay: the tax papers for as long
as the tax office may ask, the policy for as long as a claim can be made on it, the certificate for
good. Each piece carries a term, and throwing one away is a decision with a date attached rather
than tidying up.

Putting `records` inside `archive` would inherit exactly the wrong permission. Anything that clears
out the archive would reach into it, and the folder that must not be cleared out would sit inside
the one that may. So it is a root of its own, beside the archive rather than under it.

The other difference is pace. In the rest of the vault something happens every day. Here a document
arrives, and then nothing happens to it for years. What moves it is a term running out, not a
change of mind.

### Nothing has to move

The order above is a direction, not a duty. **Everything may stay where it is**, and in `knowledge`
that is the normal case rather than a backlog you owe someone. Something nobody ever looks at again
has still ended up in the right place.

There is one exception, and it is deliberate: **the desk gets cleared.** A piece of work has an end,
so `doing` is the one folder that empties. You do not have to remember that either. Zanmai sees from
the file dates that something has been sitting untouched for weeks, asks you about it, and on your
word moves the whole thing to one of five places: the archive, your knowledge, your trusted set, the
trash, or out of the vault entirely.

## Why these names and not projects

The common approach sorts by lifecycle: projects, areas, resources, archive. In practice that forces
a decision on every new item, and the decision keeps changing. A trip is a project, then it recurs
and becomes an area, then it is over and becomes a resource. The same material moves three times and
you have to think about it each time. Worse, it only works as long as you keep doing the moving, and
nobody does.

You do not think in projects anyway. You think in what you want to reach. So the folders are named
after states of a head rather than stages of a filing system, and they line up with the way memory
is actually separated:

| folder | in your head |
|---|---|
| `focus` | attention, what you are looking at |
| `doing` | working memory, what is on the desk right now |
| `habits` | what you can do without thinking about it |
| `knowledge` | facts, out of their original context |
| `journal` | what happened to you, and when |
| `trusted` | the best answer you have, until a better one turns up |

Two families of words, and they never mix: behaviour (`focus`, `doing`, `habits`, `knowledge`,
`trusted`, `archive`) and machinery (`zanmai`, `import`), with `journal` and `contacts` beside them
as time and people. A name that falls between two families is the wrong name.

### Gathered, settled, finished

Three of them are easy to confuse, so here is the line between them.

- **`knowledge`** is gathered. Nothing here is decided, two notes are allowed to contradict each other, and that is fine. Most of your material lives here and stays.
- **`trusted`** answers a question you actually ask, **and only when the answer cannot be worked out from the files themselves**: which of your many training plans is the one you follow, which corporate design applies, which draft is the finished one. It is the best available assumption, not the truth. Trust can be withdrawn; truth cannot. That is why it is not called `truth`.
- **`archive`** is finished and kept, and answers no question any more. The policy, the invoice, the contract, the notice, and your own completed pieces.

A whole matter stays in one place. The current policy, the one it replaced, the correspondence and
the invoices belong in one folder, the way they would sit in one hanging file. Which version applies
is written on the paper and gets read; a folder does not get to claim it. That is why **nothing ever
moves between `trusted` and `archive`**, and why splitting a matter across the two would be the
mistake rather than the tidy-up.

Contacts sit apart because a person is not a topic. Everything else points at them.

The themes inside those folders exist for you, not for the assistant. It does not need them to find anything, it follows the links. You need them, because a structure you can see is what makes a growing vault feel manageable instead of endless.

And everything is linked, the way one thought reaches another. An invoice is not a lonely file in a folder, it hangs off the insurance it belongs to, which hangs off the company, which hangs off the person you dealt with. That is why you can ask a question in your own words instead of remembering which folder you picked two years ago, and why hundreds or thousands of documents stay workable rather than becoming a heap.

The whole reasoning behind this is in [the idea behind Zanmai](philosophy.md).

## Themes, and the words for them

A **theme** is a subject you keep material about, and it gets its own folder inside `focus`, `doing`, `habits` or `knowledge`. Everything about that subject lives in there together. In the rest of this documentation and in Zanmai's own files, such a folder is called a **bundle**, so: a bundle is a theme's folder with its material inside.

Each theme folder holds a main note carrying the theme itself, its description and what belongs to it. Internally that one is called the **truth file**, because it is the single place the theme's own facts live rather than being repeated across members. Alongside it sits an `INDEX.md` listing what is in the folder.

Three more words you will meet:

- The fields at the top of every note, between `---` lines, are its **frontmatter**. They hold the structured facts: what class it is, when it was created, where it came from.
- A link from one note to another is written `[[like-this]]` and called a **wikilink**. It uses only the file's name, not its path, so moving a folder does not break links.
- The short, lowercase, dash-separated form of a name used in filenames is the **slug**. "Kundentermin Meyer" becomes `kundentermin-meyer`.

A bundle is the normal case, not the exception. A single loose file is for material that genuinely stands alone.

## The theme is the broad subject, never the single item

This is the rule that goes wrong most often, so it gets its own section.

You think from general to specific, so the folder is the general subject and the specific things live inside it. A place name, a product model, a medication, an appliance: none of those is a theme. "Travel" is a theme and one trip is a note inside it. "Health" is a theme and one medication is a note inside it.

A specific item can sit in `focus` while you are actively dealing with it, but its long-term home is inside the broader theme, as a flat note in that folder rather than as a folder of its own.

## When the theme does not exist yet

For the first item in a new theme, Zanmai proposes a name and asks you once, in your language, whether to create it or use a different name. Theme folders are cheap; naming them right is the only cost, which is what the question is for.

For a genuinely themeless one-off, or when you are unsure, the note lands flat in `knowledge` as a temporary state and is surfaced in a later briefing as something still to file. When a second, related item arrives, Zanmai proposes making a theme out of both.

If material arrives for a theme that already exists, that theme is reused. A second folder for the same subject is not created.

## Sub-themes

A theme folder can contain further folders, but only when that actually helps. The test is whether the sub-subject has enough identity and material to stand as its own thing; if not, loose notes in the parent are clearer. When in doubt: fewer folders, more notes per folder. Empty drawers are the failure mode.

Two shapes exist side by side:

- A **thematic sub-theme** has its own identity, so it gets its own main note carrying a link back to the parent.
- An **organisational sub-folder** just groups narrow material inside the parent, for instance loose clippings. No main note, the parent carries the theme.

Both get their own `INDEX.md`. Because links use file names rather than paths, nesting never breaks a reference.

Restructuring later is always possible. When new material would sit better with existing material rearranged, Zanmai proposes the move as part of its plan rather than doing it silently.

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
simple: can you name it without using the words attachment, files or assets? If yes, it is a
sub-bundle with an index of its own. If no, everything stays flat. Two things reliably pass that
test, and both can be filled by machine: time, and where something came from.

Where a file lies and where it appears are two different questions. Embedding works on the file
name, not the path, so a note shows its picture wherever the picture sits.

The one exception to all of this is your editor's database folders, which end in `.base` and contain
a table, its column definitions and one page per row. Those belong to the editor entirely. Zanmai
reads nothing inside them, writes nothing inside them, and leaves them out of every scan. You create
and edit them in the app; they can live wherever you put them.

## Coming in and going out

- **`import`** is where you drop things, and it is deliberately a heap: throw it in however it lands, and Zanmai takes it up by itself. **The folder is the automation**, so it has no sub-folders for purposes: what kind of file it is decides what happens to it, not where you put it. Everything in there is read oldest-first and in full before any of it is acted on, because the later item can withdraw the earlier one. Nothing links to files sitting there, since they are not filed yet, and nothing in there is ever the only copy.
- **`doing`** is both the way in and the way out. Work you are on, and work Zanmai produced for you, sit in the same place: one folder per piece with its files kept local, so you can pull the whole thing out. There is no separate export folder, because a finished piece and the drafts that led to it are the same matter and a second folder would only cut them apart.

Briefings written for a single decision land on the desk too, rather than in a review area of their
own: you see them in your editor and open them directly, and when you are done they move into the
logs. Plans for larger operations do not become files at all; they are shown to you in the chat and
recorded afterwards.

## The system folder

`zanmai/` holds everything Zanmai needs for itself. The test for what belongs in there is not "what
you do not need" but **"what you never touch by hand"**. It has no leading dot and is therefore
plainly visible, which is on purpose: a folder that runs your vault should not be hidden from you.

Two halves matter, because updates treat them differently:

- **Replaced on update:** `zanmai/system/`, the distribution itself. Editing anything in there is pointless, the next version overwrites it.
- **Never touched by an update:** your profile (`user.md`), `extensions/` for anything grown specifically for this vault including new specialists, `connections/` recording what has been wired to outside sources with references only and never secrets, `memory/` for what carries across sessions, `design/` for brand values, `logs/`, `history/` for the snapshots, `trash/` and `temp/`, plus `runtime/` for what was provisioned on this particular machine.

That split is what makes an update safe: one half is replaced wholesale, the other is left alone.
Machine-local means `runtime/` is not meant to travel to another computer.

Three of those clear themselves out by themselves. What differs is how long each one waits, and each
number comes from what the folder is actually for:

- **`trash/`** holds what was thrown away, for **30 days**. It exists because Zanmai deletes things and that has to be reversible; until the 30 days are up, anything in there can be put back exactly where it came from. It is the user's own change of mind, so it gets the long window.
- **`temp/`** is where Zanmai puts things down mid-job: a render preview, an unpacked archive, a download before it is read. It is cleared after **7 days**. Anything still sitting there is a fault rather than rubbish, so it is deleted **and said out loud**.
- **`history/`** keeps the snapshots, for **7 days**, and the newest one always stays whatever its age. A snapshot is a point to jump back to after an update or a large edit, not a backup, and whether one of those went wrong is known within days. Every version of every file is stored once by its content, but a changed video or deck is stored again in full, which is the other reason the window is short.

## The briefing

`zanmai/memory/briefing.md` is the current picture of what is going on in the vault: what is active, what is open, and where links point nowhere. It is rebuilt whole rather than patched, at every session close, after any larger operation, or on request.

It has three parts, always present even when empty: the current state with active focus themes, the open items drawn from recent notes, and the gaps worth noticing. The session-start hook reads it and hands it to the first reply, which is why the greeting is fast and already knows what you were doing.

It is written by Zanmai, not by you, and manual edits are overwritten at the next rebuild.

---

[← Back to the documentation index](index.md)
