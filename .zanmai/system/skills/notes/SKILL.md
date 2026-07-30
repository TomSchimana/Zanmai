---
name: notes
description: Daily, Weekly and Monthly Notes operations on direct user instruction, capture a line the user dictated, append a todo the user named, toggle a checkbox the user pointed at, read a specific period's note for the user. Triggers when the user explicitly tells the AI to do something in or with a daily, weekly or monthly note. State changes go through `zanmai.py notes daily|weekly|monthly` so the path is resolved from `.zennotes/vault.json` deterministically and the AI never has to translate `titlePattern` itself.
---

# notes

Operations on Daily, Weekly and Monthly Notes. The vault layout (folder name, location, titlePattern, enabled flags) is the user's ZenNotes configuration, not Zanmai's choice. This skill reads that configuration and acts on what the user instructed. The three note kinds share one command shape, `notes daily`, `notes weekly`, `notes monthly`, with identical flags; pick the subcommand matching the period the user named.

## Directives

1. Read `.zanmai/vault-config.md` before any operation. If the note kind the user named is disabled, or ZenNotes is not configured for this vault, reply once in the user's writing language that the feature is off in their ZenNotes settings, then stop. Do not create folders, do not invent paths, do not propose alternatives.
2. The AI never initiates a note write on its own judgement. Daily, Weekly and Monthly Notes are the user's writing space. The AI writes there only when the user directly instructed it ("trag das ein", "schreib das in heute", "hak das ab"), or when the `journal` skill writes an automatic period rollup, the one non-destructive exception defined in operating-principles §6. No unsolicited cleanups, no augmentation surveys, no "I noticed a typo, shall I…" proposals.
3. Path resolution goes through `zanmai.py notes <kind> --print-path` (or `--ensure` / `--append`). Never compute a note filename by translating `titlePattern` in the AI head. The script honours `primaryNotesLocation` and the chosen kind's `directory` and `titlePattern` from `.zennotes/vault.json`.
4. Writes go through `zanmai.py notes <kind> --append` or `--ensure`. Use `Edit` only for in-place edits the script does not cover (toggling an existing checkbox via `zn task toggle`, multi-line restructuring on user instruction).
5. Zanmai never writes `.zennotes/vault.json`. That file is ZenNotes' own settings store. The skill reads it via `zanmai.py`, never edits it.

## When to use

- The user says "trag das ins Daily", "schreib das in heute", "add this to today's note" or equivalent.
- The user asks to toggle or strike a specific checkbox in a daily note.
- The user asks to read a specific period's daily, weekly or monthly note.
- The user references the weekly or monthly note for a similar operation.

## When not to use

- The AI noticed something in a daily note and wants to act on it. The trigger is the user, not the AI.
- Operations on bundle truth files, INDEX.md or other vault content, those belong to other skills or direct `zanmai.py` subcommands.
- Imports from `_import/`, that is `import-bundle`.

## The workflow

### Step 1: confirm the feature is on

Read the first lines of `.zanmai/vault-config.md`. If it says ZenNotes is not configured, or that Daily Notes are disabled, reply once in the user's writing language (one short sentence) and stop. No further steps run.

### Step 2: resolve the path

```
<python_cmd> .zanmai/system/scripts/zanmai.py notes daily <vault> [--date YYYY-MM-DD] --print-path
```

The script prints the path relative to the vault root, or exits with code 2 when the feature is off. Exit code 2 means the Step-1 check missed something, stop and re-read `vault-config.md`.

### Step 3: execute the user-instructed change

The user already said what they want. Translate that into a single `zanmai.py notes daily` call and run it. No proposal step, no "shall I write X?" approval loop, the instruction is the approval.

For an append:

```
<python_cmd> .zanmai/system/scripts/zanmai.py notes daily <vault> --append "<exact line>"
```

The script creates the note file if it does not exist (with the right path and any subfolders the `titlePattern` requires), appends the line, and writes one activity-log entry.

For toggling an existing checkbox, use `zn task toggle <id> --vault <vault path>` when `zen_cli_installed: true` (per the tool-hierarchy in `operating-principles.md`). Otherwise an in-place `Edit`.

If the user's instruction is genuinely ambiguous (no wording for the line they want, no clear target date), ask one short clarifying question, then act. Not a propose-and-approve loop, a one-shot clarification.

### Step 4: confirm to the user

One short line in the user's writing language naming what was done. Offer to open the note via `zn open <path>` if the user has the zn CLI, otherwise the platform default. Never open without a yes.

## Rationalizations to resist

| Rationalization | Reality |
|---|---|
| "I can compute today's date and the path myself, it's simpler." | The titlePattern can be `yyyy-MM-dd-EEE` or `yyyy/MM-MMM/yyyy-MM-dd-EEE`, subfolder components, locale-sensitive month/weekday names. The script handles all that, the AI rates these wrong. Always go through the script. |
| "Notes are off in vault-config but the user clearly wants this captured somewhere." | Off means off. Do not silently re-route to an alternative location. One sentence stating the feature is off, then stop. The user can switch it on in ZenNotes settings if they want it. |
| "The user mentioned the daily note in passing, I'll write that line for them as a courtesy." | The trigger is direct instruction, not passing mention. "Ich war heute beim Sport" in a chat is conversation, not a write-instruction. Without a clear "trag das ein", nothing happens. |
| "I'll add the line directly via Edit, faster than calling the script." | The script is authoritative for the path. Direct Edit risks landing in the wrong folder when `primaryNotesLocation` or `directory` changes, the script reads vault.json every time, Edit relies on the AI's memory of the path. |
| "The user said 'schreib das ein' but I'll show a proposal first to be safe." | No proposal step. The instruction is the approval. Show a proposal only when the wording or target is genuinely ambiguous, one clarifying question, then act. |

## Red flags, stop and recheck

- The proposed path does not match what `zanmai.py notes daily --print-path` returns. Re-resolve, never override.
- About to write into a daily note without a direct user instruction in the current turn. Stop. Capture acts on a direct instruction only.
- vault-config.md says Daily off but the AI is about to run `zanmai.py notes daily`. Stop. Step 1 was skipped.

## Files

- `.zanmai/system/scripts/zanmai.py`, `notes daily` subcommand.
- `.zanmai/vault-config.md`, current Daily/Weekly enabled state, folder paths, titlePattern (regenerated by `session-start.py` on every session).
- `.zanmai/system/operating-principles.md`, section 6, the principle that AI never initiates a note write.
