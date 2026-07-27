[← Zanmai Documentation](index.md)

# Importing and filing material

Bringing a folder, an export or a pile of loose files into the vault and having it sorted.

## Getting material in

Drop it into `_import`, or just say where it is. Then ask for it to be imported. Anything works: notes from another app, PDFs, screenshots, tickets, calendar files, a folder of mixed material from a project.

Three things are asked before the work starts, as a short form rather than a conversation, because they change the outcome: whether Zanmai should apply its own conventions or keep the source structure as closely as possible, what exactly is in scope, and what to do when something already exists in the vault.

## What happens before anything moves

The scope is inspected first, so you can see what Zanmai looked at: which subfolders, how many files of which type, how many attachments. The vault index is rebuilt so existing themes are actually found rather than duplicated.

Then the structure is worked out from the content of the material, not from the folder names it arrived in. Several groupings are considered each time, by place, by time, by person or organisation, by project phase, by type of material, by how broad a topic is, and the one that matches how you will later look for it is chosen. Mirroring the source folders is treated as a failure, not a shortcut, because the way material was organised elsewhere is rarely the way you will search for it here. If you name a grouping yourself, that one wins.

Every single item gets its own classification into focus, habits or knowledge, with a reason. A knowledge theme can contain one item that is active preparation and therefore focus. Nothing inherits its class from the folder it lands in.

Attachments that carry structured information are read rather than filed blindly. A photographed business card becomes fields in a contact, a booking confirmation becomes a note with the actual dates, a ticket becomes an entry. The original file goes into the shared `assets` folder and the two link to each other.

People and organisations found in the material get a short contact entry each, with a link back to the exact file they were mentioned in. That happens by default rather than by asking, because otherwise every import leaves a trail of names that link nowhere.

Filenames are cleaned on the way in: random ID suffixes dropped, dates that are already in the file's metadata dropped, typos in names fixed, everything in a consistent form. Tags are matched against what your vault already uses so you do not end up with three spellings of the same thing.

## The plan you approve

Before anything is written you get a short overview in the chat: a tree of what lands where, one sentence on which grouping was chosen and which were rejected and why, the counts, and the notable items, meaning anything ambiguous, anything left out, and every renamed file. Nothing is created until you say go.

Mechanical detail does not clutter that overview. It goes into an operation report afterwards, kept as a log, so you can check exactly what happened without having to read it up front.

## Your text stays your text

Imported files keep their body exactly as it was. Only the metadata at the top is brought in line with the vault's schema, and anything from the source that does not fit is preserved in the file rather than discarded. Templates apply to newly created themes, never to your existing content.

At the end you are asked once whether the source files in `_import` should be moved to trash or left where they are. Leaving them is the default.

## Related

- [Folder architecture](folder-architecture.md), where things land and why
- [Contacts](contacts.md), how people and organisations are kept
- [Tags](tags.md), how tags are kept consistent

---

[← Back to the documentation index](index.md)
