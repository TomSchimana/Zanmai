[← Zanmai Documentation](index.md)

# Snapshots and going back

**Read this when:** something is about to be overwritten, or a change has to be undone.

Zanmai takes a snapshot of the space before it changes many files at once. If something goes wrong, you go back to that state. Snapshots live inside the space and are gone when the space is gone. They do not replace a backup.

## When one is taken

- Before an update, a repair across many files, a rename that rewrites links, or a restore.
- Whenever you ask for one.

Not before adding something. An import creates new files and takes nothing away, so there is nothing to go back to. If nothing changed since the last one, no second is taken and you are told so.

## Going back

**One file.** Name the file and the snapshot, and it comes back. What was there goes to the trash first, so you can undo that too.

**The whole space.** One operation, for an update that went wrong: everything returns together instead of file by file. Before anything is touched, a snapshot of the current state is taken, and anything you made since then goes to the trash and is listed by name. So this step is undoable as well, and nothing of yours disappears without being named.

It stays a conversation with the house-keeping specialist, because going all the way back also undoes what you did since.

## How long they are kept

**Seven days, and the newest one always stays.** Whether an update went wrong shows within days. After that a snapshot only costs disk space: every changed video and slide file is carried along again.

If you have not worked in the space for weeks, the newest one is still there whatever its age, so you are never left without one.

The clearing runs at session start. It only touches what Zanmai put there, never what you filed.

## What this costs you in disk space

Each file is stored once by its content. A file that did not change between two snapshots is stored once and pointed at twice, so seven days of snapshots cost roughly your material plus what actually changed.

Large files are the exception. A video or a deck that changes is stored again in full, because there is no useful way to keep only the difference between two of them. That is the other reason the window is a week.

## What a snapshot is not

It is not a backup. Snapshots live under `zanmai/history/`, inside the space, so a dead disk takes the space and every snapshot in it at the same moment. Your own copy of the folder is a separate job and still worth doing: [backup and synced folders](backup.md) covers it.

Every restore and update is written to `zanmai/update-history.md`, which no update overwrites. That is where you look up what happened and when.

## Related

- [Backup and synced folders](backup.md), the copy that survives a dead disk
- [Keeping Zanmai up to date](updates.md), the operation a snapshot most often precedes

---

[← Back to the documentation index](index.md)
