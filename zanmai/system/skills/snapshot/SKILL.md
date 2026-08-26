---
name: zanmai:snapshot
description: Record the vault before a risky write, and restore from an earlier record. Triggers before bulk imports, cross-bundle moves, body rewrites, or `/zanmai-snapshot`.
---

# snapshot

Make a rollback point. Always before risky writes, on demand otherwise.

## Directive

A snapshot exists as an entry in the history, written by the script. A conversational claim of having "taken a snapshot in memory" is not a snapshot. Run the script.

It is not a copy of the vault. Every file is stored once by its content, so an unchanged file costs nothing on the second snapshot and a changed line costs the line. That is why taking one is never the expensive choice and why nothing has to be cleaned out afterwards. If nothing changed since the last one, none is taken and the script says so.

The single config flag `auto_snapshots` in `zanmai/user.md` is the master switch. `zanmai.py snapshot create` reads it every time and exits with `skip: auto_snapshots disabled` when set to `false`, including invocations of this skill. When the user has their own backup discipline they flip it via `zanmai.py snapshot disable` (and `enable` to turn back on). The script is what counts, no separate disable list.

## When to use

Four cases, and they share one shape: Zanmai is about to overwrite material that already exists, in a
way it cannot undo one file at a time.

- Before a distribution update.
- Before a bulk repair, one pattern applied across many files.
- Before a rename that rewrites links throughout the vault.
- Before restoring from an earlier snapshot, since that overwrites the current state.

Plus the one case that is not a rule: the user asks for a rollback point in their own words.

## When not to use

The count of files is not the test, and neither is the calendar. What matters is whether anything the
user already had is being replaced.

- Adding: an import, a filed document, a generated deliverable. New files take nothing away, so there
  is nothing to roll back to. This used to be a trigger at "more than five files".
- The start of a session, or a new day. Nothing has changed yet, and a snapshot per working day is a
  backup schedule, not a safety net. The user's own backup covers that case and covers it better.
- Right after setup. The vault is an empty skeleton, and its state is already the first entry in the
  history.
- Single-file edits, reads, and anything the user waived.

## The workflow

### Step 1: pick the reason

One to three kebab-case words saying why this snapshot exists, for example `pre-<theme>-import`, `pre-bulk-rename` or `pre-template-migration`. It is the only thing that will identify it in a list a year from now.

Avoid generic words like `snapshot`, `backup` or `tmp`. They tell future readers nothing.

### Step 2: call the script

From the vault root:

```
<python_cmd> zanmai/system/scripts/zanmai.py snapshot create --reason <reason-slug>
```

It prints the snapshot's short name and exits 0. If nothing has changed since the last one it says so and takes none, which is also a 0: the previous one still covers the state. On a non-zero exit, stop and report; nothing has been changed.

### Step 3: tell the user

One sentence in the user's writing language: what was recorded and the operation it precedes.

If the user asked for a snapshot on its own (not as a prelude to another operation), stop here.

## Sounds sensible, is wrong

| Rationalization | Reality |
|---|---|
| "The operation is small, a snapshot is overkill." | If you have to argue with yourself, snapshot. The 200ms cost is worth the rollback path. |
| "I'll snapshot after, not before." | After is too late. The operation is what you might want to roll back. |
| "I already snapshotted this session." | A new risky operation gets a new snapshot. The previous one is for the previous operation, and if nothing changed in between the script takes none anyway. |
| "I'll use a generic slug and figure it out later." | Future readers cannot tell five generic snapshots apart. Name what it is. |

## Stop and look again

- About to write to more than five files without having called the script in this turn.
- The snapshot script exited non-zero and the operation proceeded anyway.
- The slug is generic (`backup`, `snapshot`, `tmp`, `test`).
- About to write to the history folder by hand. Only `zanmai.py snapshot` writes there.

## Managing existing snapshots

The script ships the rest of the surface. None of it removes vault content.

- `zanmai.py snapshot list`, the snapshots newest first and what they occupy together.
- `zanmai.py snapshot show --snapshot <name>`, what that one changed. With `--path`, one file as it was.
- `zanmai.py snapshot restore --snapshot <name> --path <path>`, put one file back. The version that is there now goes to the trash first, so the restore is itself undoable.
- `zanmai.py snapshot compact`, let git pack the history down. Loses no snapshot.

There is no delete subcommand and nothing to prune. Snapshots are not copies piling up with time, so age costs nothing.

## Putting something back

**One file the user named.** Run `snapshot restore`. It is reversible by construction, so it does not need a consultation: state which file, from which snapshot, and that the current version goes to the trash.

**The whole vault.** Still a guided conversation, and still Pepper's. Rolling everything back also rolls back what the user did since, and that is a judgement about their work, not a flag.

1. **Never restore on a vague complaint.** "Something is broken" is not a restore trigger. Establish what is actually wrong, and whether a restore is the right tool at all.
2. **Name the artefacts.** Which files, from which snapshot, in the user's words.
3. **Take a fresh snapshot of the current state** before anything is overwritten: `zanmai.py snapshot create --reason pre-restore-<short-reason>`. Non-negotiable. State it in one line.
4. **File by file, not wholesale.** Copying a whole snapshot over the vault re-introduces every other change made since.
5. **Confirm at every step.** Which source goes over which target, what the user loses from the current version, and where that version now lives.

## Files

- `zanmai/system/scripts/zanmai.py` (`snapshot create`, `list`, `show`, `restore`, `compact`, `enable`, `disable`): the actual mechanic.
- `zanmai/history/`: destination.
