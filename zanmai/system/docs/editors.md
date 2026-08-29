[← Zanmai Documentation](index.md)

# Your editor

Use whatever you like. Obsidian, VS Code, a plain text editor: your vault is a folder of ordinary files with links written `[[like this]]`, so anything that reads Markdown reads it. Zanmai depends on none of them, and there is no editor to install and no setting to point at during setup.

Two things are worth knowing before you point an app at the folder.

## The folders are Zanmai's, so leave them where they are

The layout is what Zanmai works with. Where the daily entry lives, what the trash means, which folder holds a theme: renaming or relocating any of that in your editor's settings does not move it for Zanmai, it just means the two of you are looking at different places.

So: point your editor at the vault, and leave the folder structure alone. Make new folders wherever you like for your own things. Do not repurpose the ones that are already there.

## Set your tool up so it does not collide

Most editors want to put a few things somewhere the moment you use them, and left on their defaults they will put them in the middle of your vault. Worth a minute in the settings:

- **Attachments.** An editor that asks where to save a pasted image usually defaults to one shared folder for the whole vault. Set it to save next to the note instead. In Zanmai a picture belongs in the folder of the thing it is about, not in a pile with every other picture.
- **Daily notes.** If your editor has its own daily-note feature, switch it off. Zanmai keeps the journal under `journal/`, one folder per day, and a second daily note somewhere else just means half your days are in one place and half in another.
- **Trash and archive.** If your editor has its own, it will not be the one Zanmai restores from. Throw things away with Zanmai (`file trash`), which keeps the original path and lets `file restore` put it back exactly where it was.
- **Sync and cache folders.** Anything an app writes for itself is its own business, and Zanmai leaves it alone. Just keep it out of the folders that hold your material.

None of this is a requirement. Get it wrong and nothing breaks; you just end up with two half-filled versions of the same thing.

## Database folders stay yours

Some editors keep a table or a board as a folder ending in `.base`, holding the columns and one page per row. Every one you build is untouched: nothing read, nothing written, left out of every scan, wherever you put it.

There is no exception any more: every folder ending in `.base` is yours. Zanmai's own list of what it still owes you lives in `zanmai/open/`, one JSON file and one Markdown page per piece of work, inside the system folder where the things you never touch by hand belong.

## Why it is built this way

An editor Zanmai depended on would decide things Zanmai should decide: whether a daily entry exists at all, where it lives, what happens when you throw something away. Each of those is part of how the vault works, and none should change because you tried a different app.

It also settles a bigger one. An editor built around Markdown treats every other file as an attachment to a note, and a life is not shaped like that. A PDF, a photo, a video and a scan are the thing itself as often as a note is. Here they all sit together in the folder for the thing they belong to.

## Related

- [How the vault is organised](folder-architecture.md)
- [Daily, weekly and monthly notes](daily-capture.md), what capture does with them

---

[← Back to the documentation index](index.md)
