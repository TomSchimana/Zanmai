[← Zanmai Documentation](index.md)

# How the vault is organised

Which folder holds what, why it is sorted that way, and the few words worth knowing.

## What you see

At the top level of your vault:

- **`inbox`** holds everything you keep. Your editor opens here, and new notes land here.
- **`_import`** is where you drop material to be taken in. It empties itself once the material is filed.
- **`_export`** is where finished work lands, ready for you to pull out.
- **`assets`** holds every file that is not a note: PDFs, images, calendar files, audio, video.
- **`quick`** is your own scratch area. Zanmai writes there only if you ask.
- **`archive`** and **`trash`** work the way your editor expects them to.
- **`.zanmai`** is Zanmai's own area. The leading dot hides it from Finder, most Linux file managers and your editor. Nothing of yours is in there.

Inside `inbox`, four folders:

- **`focus`**, what you are working on now.
- **`habits`**, what comes back regularly.
- **`knowledge`**, what stays available for later.
- **`contacts`**, people and organisations, split into `people` and `organizations`.

Daily, weekly and monthly notes live wherever your editor puts them; Zanmai reads that from the editor's own settings rather than deciding for you. Any Markdown editor opens this vault, Obsidian included. ZenNotes is the one we recommend, being leaner and faster, and the one Zanmai works with most closely, which is why the folder names follow its conventions. See [your editor](editors.md) for what that integration covers.

## Why sorted by attention, not by type

The common approach sorts by lifecycle: projects, areas, resources, archive. In practice that forces a decision on every new item, and the decision keeps changing. A trip is a project, then it recurs and becomes an area, then it is over and becomes a resource. The same material moves three times and you have to think about it each time.

Zanmai sorts by how much attention something needs, which is far more stable:

- **focus** is active attention. You are working on it. Narrow set, high signal.
- **habits** is middling attention. It reminds you without demanding the foreground.
- **knowledge** is low attention. Reachable when you want it, not in your face. This is also the default for anything unclear, which is the point: no agonising.

Moving something from focus to knowledge when it goes quiet is the normal course of things, not a filing mistake. And when you say "project", that usually means focus.

Contacts sit apart because a person is not a topic. Everything else points at them.

The themes inside those folders exist for you, not for the assistant. It does not need them to find anything, it follows the links. You need them, because a structure you can see is what makes a growing vault feel manageable instead of endless.

And everything is linked, the way one thought reaches another. An invoice is not a lonely file in a folder, it hangs off the insurance it belongs to, which hangs off the company, which hangs off the person you dealt with. That is why you can ask a question in your own words instead of remembering which folder you picked two years ago, and why hundreds or thousands of documents stay workable rather than becoming a heap.

The whole reasoning behind this is in [the idea behind Zanmai](philosophy.md).

## Themes, and the words for them

A **theme** is a subject you keep material about, and it gets its own folder inside `focus`, `habits` or `knowledge`. Everything about that subject lives in there together. In the rest of this documentation and in Zanmai's own files, such a folder is called a **bundle**, so: a bundle is a theme's folder with its material inside.

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

Everything that is not Markdown lives in the single `assets` folder at the vault root: PDFs, images, calendar files, audio, transcripts. Notes reference them by embedding, and the filename carries the owning theme or contact as a prefix so two attachments called `scan.pdf` cannot collide.

The exception is your editor's database folders, which end in `.base` and contain a table, its column definitions and one page per row. Those belong to the editor entirely. Zanmai reads nothing inside them, writes nothing inside them, and leaves them out of every scan. You create and edit them in the app; they can live wherever you put them.

## Coming in, going out, and unsure

- **`_import`** is transit. You drop material there, ask for it to be imported, and it is empty again afterwards. Nothing should link to files sitting there, since they are not filed yet.
- **`_export`** is the mirror: finished flyers, decks, documents, one folder per piece with its files kept local so you can pull the whole thing out. Nothing produced goes into `inbox`. Once you have taken a piece, it can move to an archive folder inside `_export` to keep the surface tidy without deleting anything.
- **`inbox/review`** holds a briefing written for one decision, something to read once rather than keep. It sits inside `inbox` deliberately, so you see it in your editor and can open it directly. When you are done, it moves into the logs. Plans for larger operations do not go here; those are shown to you in the chat and recorded afterwards.

The distinction the folders enforce: unsure where something belongs and you decide, versus finished and yours to take.

## The system folder

`.zanmai/` holds everything Zanmai needs for itself. Two halves matter, because updates treat them differently:

- **Replaced on update:** `.zanmai/system/`, the distribution itself. Editing anything in there is pointless, the next version overwrites it.
- **Never touched by an update:** your profile (`user.md`), `extensions/` for anything grown specifically for this vault including new specialists, `connections/` recording what has been wired to outside sources with references only and never secrets, `memory/` for what carries across sessions, `design/` for brand values, `logs/`, `snapshots/`, plus two machine-local folders: `work/` for scratch and hand-off between specialists, and `runtime/` for what was provisioned on this particular machine.

That split is what makes an update safe: one half is replaced wholesale, the other is left alone. Machine-local means `runtime/` is not meant to travel to another computer.

## The briefing

`.zanmai/memory/briefing.md` is the current picture of what is going on in the vault: what is active, what is open, and where links point nowhere. It is rebuilt whole rather than patched, at every session close, after any larger operation, or on request.

It has three parts, always present even when empty: the current state with active focus themes, the open items drawn from recent notes, and the gaps worth noticing. The session-start hook reads it and hands it to the first reply, which is why the greeting is fast and already knows what you were doing.

It is written by Zanmai, not by you, and manual edits are overwritten at the next rebuild.

---

[← Back to the documentation index](index.md)
