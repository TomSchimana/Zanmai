[← Zanmai Documentation](index.md)

# Importing and filing material

**Read this when:** material arrives and has to be read, sorted and filed.

Put material into `inbox/` and it gets read, sorted and filed, and you are told what it was and where it went. Nothing leaves the inbox before its content is somewhere in the space.

## Getting material in

Drop it into `inbox`, or just say where it is. Dropping it is the instruction: at the next session start what is lying there gets opened, worked out and brought in, and you are told what it was and where it went. You do not have to ask for it a second time. Anything works: notes from another app, PDFs, screenshots, tickets, calendar files, a folder of mixed material from a project.

`inbox` is for material that still needs sorting out. If you already know it belongs to a piece of work you are on, it can go straight into that piece's own folder under `workbench` instead, see [Folder architecture](folder-architecture.md).

Three things are asked before the work starts, as a short form rather than a conversation, because they change the outcome: whether Zanmai should apply its own conventions or keep the source structure as closely as possible, what exactly is in scope, and what to do when something already exists in the space.

## What happens before anything moves

The scope is inspected first, so you can see what Zanmai looked at: which subfolders, how many files of which type, how many attachments. The space index is rebuilt so existing bundles are actually found rather than duplicated.

Then the structure is worked out from the content of the material, not from the folder names it arrived in. Several groupings are considered each time, by place, by time, by person or organisation, by project phase, by type of material, by how broad a topic is, and the one that matches how you will later look for it is chosen. Mirroring the source folders is treated as a failure, not a shortcut, because the way material was organised elsewhere is rarely the way you will search for it here. If you name a grouping yourself, that one wins.

Every single item gets its own classification into workbench, life, knowledge or archive, with a reason. A knowledge bundle can contain one item that is the user's own and therefore life. Nothing inherits its class from the folder it lands in.

Attachments that carry structured information are read rather than filed blindly. A photographed business card becomes fields in a contact, a booking confirmation becomes a note with the actual dates, a ticket becomes an entry. The original file stays in the same folder as what was written from it, and the two link to each other.

People and organisations found in the material get a short contact entry each, with a link back to the exact file they were mentioned in. That happens by default rather than by asking, because otherwise every import leaves a trail of names that link nowhere.

Filenames are cleaned on the way in: random ID suffixes dropped, dates that are already in the file's metadata dropped, typos in names fixed, everything in a consistent form. Tags are matched against what your space already uses so you do not end up with three spellings of the same thing.

## The plan you approve

Before anything is written you get an overview in the chat, and it is as big as the job. When something new is built, an existing text rewritten, or material moved between bundles: a tree of what lands where, one sentence on which grouping was chosen and which were rejected and why, the counts, and the notable items, meaning anything ambiguous, anything left out, and every renamed file. When something simply goes into a bundle you already have: a dozen lines at most, what changes, in which file, and whatever turned up that changes what you were expecting. Nothing is created until you say go.

Mechanical detail does not clutter that overview, and neither does the rest of what was read. It goes into an operation report afterwards, kept as a log, so you can check exactly what happened without having to read it up front.

You are asked the questions the material actually leaves open, not a fixed set. Scope every time. How to file only when a new bundle is being created, since an existing one already answers it. What to do about a name clash only when there is one.

## Your text stays your text

Imported files keep their body exactly as it was. Only the metadata at the top is brought in line with the space's schema, and anything from the source that does not fit is preserved in the file rather than discarded. Templates apply to newly created bundles, never to your existing content. It holds afterwards too: a sentence you wrote is not reworded or tidied up later, in an edit any more than in an import.

The `inbox` empties, but never before its content is somewhere in the space. Once something has been filed, the original goes with what was made from it where it still carries something the result does not, a recording next to its transcript for instance, and to the trash where it does not. Throwing something away is throwing it away: the trash is swept, and a file in it is gone as far as your space is concerned.

That is a condition on the command rather than a promise. Throwing a file away out of `inbox` has to name the place in the space its content reached, and a summary in the conversation is not a place: the conversation is gone tomorrow and the file is not. Moving something into the archive is not affected, because the archive is a place in the space and what goes there stays findable.

**Nothing stays in `inbox`, and no rule can say otherwise.** For a while one could, and it was wrong in a way worth naming: a file left there is read again at every session start, cannot be told apart from one that arrived this morning, and the one area that exists to empty becomes a place things live. Which of the two exits a file takes is the only question, and it is about the file rather than about tidiness.

## Saying what a sort of thing is, once

The first time something arrives that Zanmai has no rule for, you are asked what it is and where it belongs. You answer in your own words; what gets written down is a rule, and the next one of its sort answers itself. The rules live in `zanmai/routing.json`, yours to read and change, and one of them looks like this:

```
zanmai.py routing set "nightly backup report" journal \
  --when-text "/mnt/backup" \
  --about "the homeserver's nightly status, one file a day" \
  --do "judge it, add one line to the day, say so where anything is irregular" \
  --keep discard
```

Two parts of it answer questions that would otherwise come back every time you drop one of these in. **What happens to the file itself** once its content is in the space: kept beside what was made from it where it still carries something the result does not, a scan or a recording; thrown away where it does not, like the report above, whose one line in the day says everything the file said. And **who does the work**, so a kind of material that belongs in the archive goes straight to the one who curates it.

A rule keys on what something **is**, never on the file it arrived as. A file type tells you how to read something and nothing at all about what it is for: two `.txt` files are a shopping list and a server's nightly report, and a rule that caught one would catch the other. So the condition is a word in the content, or a pattern in the name where the name is genuinely part of what the thing is. The same report routes the same whether it arrives as text, as markdown or as a saved web page.

Ask what rules stand and you get the list. Ask what is waiting and you get each file, how it will be read, and which rule covers it, so anything without one is visible before it is touched.

## Related

- [Folder architecture](folder-architecture.md), where things land and why
- [Contacts](contacts.md), how people and organisations are kept
- [Tags](tags.md), how tags are kept consistent
- [What you keep](archive.md), where a document that has to stay ends up

---

[← Back to the documentation index](index.md)
