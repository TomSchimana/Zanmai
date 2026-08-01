[← Zanmai Documentation](index.md)

# Snapshots and going back

The safety net before anything risky, and how to use it when something went wrong.

## What a snapshot is

A dated copy of your vault, kept inside it under `.zanmai/snapshots/`, named after the reason it was taken: before a particular import, before a bulk rename. It is not a backup system, it is a rollback point for the moment just before Zanmai changed many files at once.

## Why it exists

Some operations touch a lot of files: an import that files fifty things, a rename that rewrites links across the vault. If one of those goes sideways there is no undo in a folder of Markdown files, and reconstructing by hand is a bad alternative.

Version control would solve it if anyone reliably committed before every risky step, which nobody does. A snapshot is the same idea without the discipline requirement: Zanmai takes one at the moments that matter.

## When one is taken

You can ask for one at any time and it happens.

Otherwise Zanmai takes one by itself in three situations: before every update, regardless of any preference you set, because an update replaces its own files; before any repair that touches many files; and once a day at session start, quietly and without a chat line, unless you turned that off during setup.

## Going back

Restoring is deliberately not something every part of Zanmai can do. It sits with the house-keeping specialist, together with deleting snapshots, because both can lose material. Before a restore, a fresh snapshot of the current state is taken, so the restore itself stays reversible.

Every restore, deletion and update is recorded in `.zanmai/update-history.md`, which no update overwrites. That file is the audit trail when you want to know what happened and when.

Snapshots live inside the vault under `.zanmai/snapshots/`, so they travel with it and they are not a substitute for your own backup of the whole folder. A preview release is exactly the situation where you want both.

## When one is not taken

Not for a single edit you asked for directly, where the overhead buys nothing. Not for reading, since nothing changes. And not when you said you did not want one, in which case that choice is recorded rather than quietly overridden.

## They pile up, on purpose

Snapshots are not cleaned out automatically, because only you know which one still matters. The one from before an import is safe to remove once you have checked the result and moved on. Ask to have old ones deleted and the house-keeping specialist lists them first so you can see what you are about to lose.

They live inside the vault, so they travel with it. That also means they are not a backup of the vault: if you lose the folder, you lose the snapshots with it. Keep your own copy of the whole thing as well, which for a preview release is worth doing anyway. If that copy is a synced folder, the snapshots are the one part worth leaving out of it, see [backup and synced folders](backup.md).

---

[← Back to the documentation index](index.md)
