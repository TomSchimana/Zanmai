[← Zanmai Documentation](index.md)

# Importing and filing material

Bringing a folder, an export or a pile of loose files into the vault and having it sorted.

## Getting material in

Drop it into `import`, or just say where it is. Dropping it is the instruction: at the next session start what is lying there gets opened, worked out and brought in, and you are told what it was and where it went. You do not have to ask for it a second time. Anything works: notes from another app, PDFs, screenshots, tickets, calendar files, a folder of mixed material from a project.

`import` is for material that still needs sorting out. If you already know it belongs to a piece of work you are on, it can go straight into that piece's own folder under `doing` instead, see [Folder architecture](folder-architecture.md).

Three things are asked before the work starts, as a short form rather than a conversation, because they change the outcome: whether Zanmai should apply its own conventions or keep the source structure as closely as possible, what exactly is in scope, and what to do when something already exists in the vault.

## What happens before anything moves

The scope is inspected first, so you can see what Zanmai looked at: which subfolders, how many files of which type, how many attachments. The vault index is rebuilt so existing themes are actually found rather than duplicated.

Then the structure is worked out from the content of the material, not from the folder names it arrived in. Several groupings are considered each time, by place, by time, by person or organisation, by project phase, by type of material, by how broad a topic is, and the one that matches how you will later look for it is chosen. Mirroring the source folders is treated as a failure, not a shortcut, because the way material was organised elsewhere is rarely the way you will search for it here. If you name a grouping yourself, that one wins.

Every single item gets its own classification into focus, doing, habits or knowledge, with a reason. A knowledge theme can contain one item that is active preparation and therefore focus. Nothing inherits its class from the folder it lands in.

Attachments that carry structured information are read rather than filed blindly. A photographed business card becomes fields in a contact, a booking confirmation becomes a note with the actual dates, a ticket becomes an entry. The original file stays in the same folder as what was written from it, and the two link to each other.

People and organisations found in the material get a short contact entry each, with a link back to the exact file they were mentioned in. That happens by default rather than by asking, because otherwise every import leaves a trail of names that link nowhere.

Filenames are cleaned on the way in: random ID suffixes dropped, dates that are already in the file's metadata dropped, typos in names fixed, everything in a consistent form. Tags are matched against what your vault already uses so you do not end up with three spellings of the same thing.

## The plan you approve

Before anything is written you get an overview in the chat, and it is as big as the job. When something new is built, an existing text rewritten, or material moved between themes: a tree of what lands where, one sentence on which grouping was chosen and which were rejected and why, the counts, and the notable items, meaning anything ambiguous, anything left out, and every renamed file. When something simply goes into a theme you already have: a dozen lines at most, what changes, in which file, and whatever turned up that changes what you were expecting. Nothing is created until you say go.

Mechanical detail does not clutter that overview, and neither does the rest of what was read. It goes into an operation report afterwards, kept as a log, so you can check exactly what happened without having to read it up front.

You are asked the questions the material actually leaves open, not a fixed set. Scope every time. How to file only when a new theme is being created, since an existing one already answers it. What to do about a name clash only when there is one.

## Your text stays your text

Imported files keep their body exactly as it was. Only the metadata at the top is brought in line with the vault's schema, and anything from the source that does not fit is preserved in the file rather than discarded. Templates apply to newly created themes, never to your existing content. It holds afterwards too: a sentence you wrote is not reworded or tidied up later, in an edit any more than in an import.

The `import` folder empties, but never before its content is somewhere in the vault. Once something has been filed, the original goes with what was made from it where it still carries something the result does not, a recording next to its transcript for instance, and to the trash where it does not. Throwing something away is throwing it away: the trash is swept, and a file in it is gone as far as your vault is concerned.

That is a condition on the command rather than a promise. Throwing a file away out of `import` has to name the place in the vault its content reached, or quote you saying it can go without one, and a summary in the conversation is neither: the conversation is gone tomorrow and the file is not. Your own words are the override, so nothing here can lock you out of your own vault. Moving something into the archive is not affected, because the archive is a place in the vault and what goes there stays findable. A file only stays lying there for a named reason, because otherwise every later session start reads it again.

## Saying what a sort of thing is, once

The first time something arrives that Zanmai has no rule for, you are asked what it is and where it belongs. The answer is written down, and the next one of its sort answers itself. The rules live in `zanmai/routing.json`, one line each, yours to change:

```
zanmai.py routing set "nightly backup report" journal/daily \
  --when-text "/mnt/backup" \
  --about "the homeserver's nightly status, one file a day" \
  --do "judge it, add one line to the day, say so where anything is irregular"
```

A rule keys on what something **is**, never on the file it arrived as. A file type tells you how to read something and nothing at all about what it is for: two `.txt` files are a shopping list and a server's nightly report, and a rule that caught one would catch the other. So the condition is a word in the content, or a pattern in the name where the name is genuinely part of what the thing is. The same report routes the same whether it arrives as text, as markdown or as a saved web page.

`zanmai.py routing show` prints what stands. `zanmai.py import scan` prints what is waiting, how each file will be read, and which rule covers it, so anything without one is visible before it is touched.

## Related

- [Folder architecture](folder-architecture.md), where things land and why
- [Contacts](contacts.md), how people and organisations are kept
- [Tags](tags.md), how tags are kept consistent

---

[← Back to the documentation index](index.md)
