[← Zanmai Documentation](index.md)

# Your editor

Any Markdown editor works. ZenNotes is the one we recommend, and the one Zanmai goes further with.

## Any editor, including Obsidian

Your vault is a folder of ordinary Markdown files with links written `[[like this]]`. Nothing about it is proprietary, so open it in whatever you already use. Obsidian works, so does anything else that reads Markdown, and so does a plain text editor.

Nothing breaks if you switch editors, or use two at once. Zanmai notices files you changed elsewhere at the next session start and updates its own index, so editing directly in the app is expected rather than tolerated.

## Why we recommend ZenNotes

[ZenNotes](https://github.com/ZenNotes/zennotes) is leaner and faster than Obsidian, and it is the editor Zanmai integrates with rather than merely coexists with. That integration is the reason for the recommendation, not loyalty to an app.

## What is actually integrated

Four concrete things, all of them reading the app's own configuration rather than imposing something on it.

**Periodic notes.** Which of the daily, weekly and monthly notes exist, where they live and what they are called comes from your ZenNotes settings. Zanmai reads that at every session start, so switching one on or off in the app is enough; nothing has to be configured twice. Capture then writes into exactly those notes, and the weekly and monthly reviews are built from the layer below.

**The inbox.** ZenNotes treats `inbox` as the primary place notes live, and Zanmai files into it, so new material appears where you already look instead of somewhere you have to go find.

**Opening and tidying.** Notes open in the app through its command line helper, and moving something to archive or trash goes through the app as well, so its own bookkeeping stays intact rather than being bypassed by a plain file move. Its search is also used as one route when looking things up.

**Databases: yours stay yours, and Zanmai keeps exactly one of its own.** ZenNotes stores a database as a folder ending in `.base`, holding the table, its columns and one page per row. Every database you build is untouched: nothing read, nothing written, left out of every scan, wherever you put it. The single exception is Zanmai's own, `inbox/review/work.base/`, which is where work that outlives one sitting is tracked. The line runs by who owns the folder, not by the file type, because a rule that stops at the file type would either lock Zanmai out of its own bookkeeping or let it into yours. That one folder is also why the view works on your phone: it is the same table and board you see on the desktop, and the underlying rows are plain CSV, so nothing about it needs this app.

On top of that, the folder names Zanmai uses follow the app's lowercase convention, so the vault does not look like two systems stapled together.

## What to set up, once

Before you start Zanmai for the first time, open ZenNotes and do two things.

1. **Point it at the vault folder.** That is what creates its settings inside the vault, which is what Zanmai reads.
2. **Switch on the periodic notes you actually want.** If you keep a journal, enable daily, and weekly or monthly if you want the reviews built from it. If you do not, leave them off and Zanmai will not use them.

Worth pointing the inbox at the vault's `inbox` folder as well, since the layout is built around it: everything you keep sits inside `inbox`, and everything that is only coming in or going out stays outside it.

The command line helper that comes with ZenNotes is optional. Without it, opening and archiving fall back to ordinary file operations, which works but does not tell the app what happened.

## Using Obsidian instead

Everything central works: your notes, the folder structure, links, filing, importing, search, research, documents, images. It is the same Markdown either way.

What you do not get is the part that reads the app's configuration. Obsidian's own daily notes are not picked up, so Zanmai treats the periodic notes as switched off and captures into your themes instead of into a daily note. Opening a file goes through the operating system rather than the app, and there are no database folders to leave alone.

None of that stops you. It is the difference between an editor Zanmai reads and an editor that just shows the same files.

## Related

- [How the vault is organised](folder-architecture.md), the layout the integration follows
- [Daily, weekly and monthly notes](daily-capture.md), what capture does with them
- [Installing ZenNotes](install/zennotes.md)

---

[← Back to the documentation index](index.md)
