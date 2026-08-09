[← Zanmai Documentation](index.md)

# Snapshots and going back

The safety net before anything risky, and how to use it when something went wrong.

## What a snapshot is

A record of your whole vault as it was at one moment, named after the reason it was taken: before a particular import, before a bulk rename. It is not a backup of the folder, it is a way back to the state just before Zanmai changed many files at once.

The record lives inside the vault, under `zanmai/history/`. You never open that folder; you ask for a list, and you ask for something back.

## Why it costs almost nothing

Every file is stored once by its content. A file that did not change between two snapshots is not stored twice, it is the same file pointed at again. So the cost is what you own, once, plus the changes you actually made.

This replaced complete copies, and the numbers are why. Measured in a real vault: two copies, thirteen gigabytes, for three gigabytes of material, because each copy also copied the copies before it. The same vault with a history holds every snapshot it has ever taken for roughly what the material itself takes.

That changes what a snapshot is for. Copies had to be rationed and cleaned out; a snapshot now costs so little that taking one is never the expensive choice.

## When one is taken

You can ask for one at any time and it happens.

Otherwise Zanmai takes one by itself before it replaces material that already exists and could not put back file by file: an update, a repair across many files, a rename that rewrites links across the vault, a restore. Not before adding things. An import or a filed document creates new files and takes nothing away, so there is nothing to go back to.

If nothing has changed since the last one, no second is taken. You are told that the last one still covers you.

## Going back

Two ways, and both are undoable.

**One file.** Ask for a file as it was, name the snapshot, and it comes back. The version that was there goes to the trash first, so if the old one turns out to be the wrong one, that is one more step back rather than a loss.

**The whole vault.** This stays with the house-keeping specialist and stays a conversation, because rolling everything back also rolls back what you did since. A fresh snapshot of the current state is taken before anything is touched.

Every restore and update is recorded in `zanmai/update-history.md`, which no update overwrites. That file is the audit trail when you want to know what happened and when.

## They are not cleaned out

They do not need to be. The history is not a pile of copies growing with time, so there is no thirty-day rule on it and nothing to prune. Everything Zanmai ever recorded about your vault stays available.

If the history ever feels large after a lot of churn, it can be packed down without losing a single snapshot.

## Still not a backup

The history lives inside the vault, so it travels with the vault, and it disappears with it. If you lose the folder you lose the history too. Keep your own copy of the whole thing as well, which for a preview release is worth doing anyway. See [backup and synced folders](backup.md).

---

[← Back to the documentation index](index.md)
