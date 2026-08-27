[← Zanmai Documentation](index.md)

# Snapshots and going back

The moment captured before anything risky, and how to use it when something went wrong.

## What a snapshot is, and what it is not

A snapshot is a picture of your whole vault as it was at one moment, named after the reason it was taken: before an update, before a bulk rename. Its whole purpose is to give you a point to jump back to when Zanmai changed many files at once and got it wrong.

**It is not a backup.** It lives inside the vault, under `zanmai/history/`, so it travels with the vault and it disappears with it. A dead disk takes the vault and every snapshot in it at the same moment. Keeping your own copy of the whole folder is a separate job and still worth doing; [backup and synced folders](backup.md) covers it.

You never open that folder. You ask for a list, and you ask for something back.

## When one is taken

You can ask for one at any time and it happens.

Otherwise Zanmai takes one by itself before it replaces material that already exists and could not put back file by file: an update, a repair across many files, a rename that rewrites links across the vault, a restore. Not before adding things. An import or a filed document creates new files and takes nothing away, so there is nothing to go back to.

If nothing has changed since the last one, no second is taken. You are told that the last one still covers you.

## Going back

Two ways, and both are undoable.

**One file.** Ask for a file as it was, name the snapshot, and it comes back. The version that was there goes to the trash first, so if the old one turns out to be the wrong one, that is one more step back rather than a loss.

**The whole vault.** This stays with the house-keeping specialist and stays a conversation, because rolling everything back also rolls back what you did since. A snapshot of the current state is taken before anything is touched.

Every restore and update is recorded in `zanmai/update-history.md`, which no update overwrites. That file is the audit trail when you want to know what happened and when.

## How long they are kept

**Seven days, and the newest one always stays.** Whether an update or a large edit went wrong is something you find out within days, not within months. After that the snapshot has done its job, and keeping it turns a safety line into a pile: measured in one real vault, twenty-five snapshots held 2.6 GB, nearly all of it video and slide files carried along a second time.

The clearing runs by itself at session start, alongside the trash and the scratch area. It only ever reaches what Zanmai put there. Nothing you filed is in scope.

If you have not worked in the vault for weeks, the newest snapshot is still there whatever its age, because a vault with no jump-back point at all is the one state this mechanism exists to prevent.

## What it costs

Every file is stored once by its content, so a file that did not change between two snapshots is stored once and pointed at twice. Within the keeping window the cost is roughly your material plus what actually changed.

Large binary files are the exception worth knowing about. A video or a deck that changes gets stored again in full, because there is no useful way to store the difference between two of them. That is the other reason the window is short.

---

[← Back to the documentation index](index.md)
