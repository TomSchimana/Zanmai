---
name: zanmai:snapshot
description: Create a timestamped copy of a vault folder before risky writes. Used before bulk imports, moves across many bundles, body rewrites, or when the user asks for a backup or snapshot in their writing language, or via `/zanmai:snapshot`. Wraps `.zanmai/system/scripts/zanmai.py snapshot create`.
---

# snapshot

Make a rollback point. Always before risky writes, on demand otherwise.

## Directive

A snapshot exists as a timestamped folder on disk, written by the script. A conversational claim of having "taken a snapshot in memory" is not a snapshot. Run the script.

The single config flag `auto_snapshots` in `.zanmai/user.md` is the master switch. `zanmai.py snapshot create` reads it every time and exits with `skip: auto_snapshots disabled` when set to `false`, including invocations of this skill. When the user has their own backup discipline they flip it via `zanmai.py snapshot disable` (and `enable` to turn back on). The script is what counts, no separate disable list.

## When to use

- Before any operation that touches more than five files at once.
- Before any write that rewrites body text (frontmatter migration alone does not count).
- Before any move across bundles.
- Before the first import in a fresh vault.
- When the user asks for a backup or rollback point in their writing language.

## When not to use

- Single-file edits in response to a direct user instruction.
- Reading files (snapshot offers no read protection).
- Operations the user explicitly waived.

## The workflow

### Step 1: pick source and reason slug

Source is usually the vault root (`.`). The reason slug is one to three kebab-case words describing why the snapshot exists, for example `pre-<theme>-import`, `pre-bulk-rename` or `pre-template-migration`.

Avoid generic slugs like `snapshot`, `backup` or `tmp`. They tell future readers nothing.

### Step 2: call the script

From the vault root:

```
<python_cmd> .zanmai/system/scripts/zanmai.py snapshot create . .zanmai/snapshots/ <reason-slug>
```

The script creates `.zanmai/snapshots/YYYY-MM-DD-HHMM-<reason-slug>/` and exits 0 on success. On non-zero exit, stop and report.

### Step 3: tell the user

One sentence in the user's writing language: the snapshot path and the operation it precedes.

If the user asked for a snapshot on its own (not as a prelude to another operation), stop here.

## Rationalizations to resist

| Rationalization | Reality |
|---|---|
| "The operation is small, a snapshot is overkill." | If you have to argue with yourself, snapshot. The 200ms cost is worth the rollback path. |
| "I'll snapshot after, not before." | After is too late. The operation is what you might want to roll back. |
| "I already snapshotted this session." | A new risky operation gets a new snapshot. The previous one is for the previous operation. |
| "I'll use a generic slug and figure it out later." | Future readers cannot tell five generic snapshots apart. Name what it is. |

## Red flags, stop and recheck

- About to write to more than five files without having called the script in this turn.
- The snapshot script exited non-zero and the operation proceeded anyway.
- The slug is generic (`backup`, `snapshot`, `tmp`, `test`).
- About to snapshot `.zanmai/snapshots/` itself.

## Managing existing snapshots

The script ships three management subcommands. None of them remove or rewrite vault content, they only touch the snapshot folders themselves.

- `zanmai.py snapshot list`, list all snapshots in `.zanmai/snapshots/` newest first, with date and reason slug. Read-only.
- `zanmai.py snapshot delete --name <folder>`, delete the named snapshot folder. No confirmation prompt because the caller typed the exact name.
- `zanmai.py snapshot delete --older-than <days>`, bulk delete snapshots older than N days. **Dry-run by default**: prints what would go, exits without touching disk. Add `--yes` to actually delete.

When the user asks "clean up old snapshots", Steve runs `snapshot delete --older-than <N>` without `--yes` first, shows the list to the user, and waits for the user to confirm before the second call with `--yes`.

## Recovery from a snapshot, AI consultation, never reflex

There is **no `snapshot restore` CLI subcommand on purpose**. Restoring is the highest-risk operation against the vault, the surface area for "AI guessed wrong and overwrote my work" is large, and a single typed wrong reason-slug at the source can wipe the recent state. So restore is not a one-shot tool, it is a guided conversation.

When the user says they lost something, want an older version back, want to roll back a change, or anything that implies pulling content out of a snapshot back into the live vault, Steve runs the following consultation. Every step is dialogue, not action.

1. **Ask what is being recovered.** A specific file, a folder, a single body section, a deleted entity. Steve needs to know which artefact, at file-level granularity, not just a topic name. One question, no list of options yet.
2. **Ask which state / which time window.** Different recovery descriptions point at different snapshots. Steve restates the time-window assumption explicitly and waits for the user to confirm before listing candidates.
3. **List candidate snapshots.** Run `zanmai.py snapshot list` and show only snapshots that bracket the user's described time window. Read the relevant artefact in two or three candidates and show short excerpts so the user can identify the right snapshot. Never assume the most recent matching slug is correct.
4. **Take a fresh snapshot of the current state.** Before any file is overwritten, `zanmai.py snapshot create . .zanmai/snapshots/ pre-restore-<short-reason>`. Non-negotiable, restoring without a fresh baseline trades one loss for another. State to the user that this just happened, in one line.
5. **Restore surgically, not wholesale.** Copy back only the artefacts the user identified. Never `cp -R` the whole snapshot folder over the vault, that re-introduces every other change since the snapshot was taken. One artefact at a time.
6. **Confirm at every step.** Before the copy, Steve states exactly which source file goes over which target file, what the user will lose from the current version (it lives in the pre-restore snapshot), and waits for the user's yes. After the copy, Steve names what was restored and the pre-restore snapshot, and asks whether further recovery is needed.
7. **Stop when the user says stop.** No silent additional restores. Each restored artefact is its own confirmed turn.

The pre-restore snapshot from step 4 is the user's undo button. If the user is unhappy with the restored state, point them at it. Recovery from the pre-restore snapshot uses this same flow recursively (and another fresh snapshot before the second restore).

## Files

- `.zanmai/system/scripts/zanmai.py` (`snapshot create`, `list`, `delete`, `enable`, `disable` subcommands): the actual mechanic. No `restore` subcommand on purpose, recovery is the consultation above, not a one-shot CLI call.
- `.zanmai/snapshots/`: destination.
