---
name: zanmai:update
description: Bring the space's distribution to the published version, run by Pepper. Triggers on `/zanmai-update` and any ask to update Zanmai.
---

# update

Explicit distribution-update trigger. The user typed the command, the user wants the update. Steve does not second-guess.

## Directive

The slash-command form is the strongest possible trigger. Steve dispatches Pepper via the `Agent` tool with `subagent_type: pepper` in the same turn, no confirmation question at the dispatch level. The user already approved by typing the command. Pepper's own TL;DR-preview gate (Hard Rule 6 in `pepper.md`) is where the user confirms or refuses the actual apply.

## Workflow

Each step says whether it is mechanics or judgement. **[SCRIPT]** has one defined outcome and a command that produces it. **[JUDGEMENT]** depends on reading the situation. A step marked [SCRIPT] that names no command is a rule sitting in prose.

1. [SCRIPT] **Check it yourself first, it takes a second.** Steve runs `zanmai.py setup upgrade. --check` inline. This is mechanics, not expert work: the command resolves where this space gets updates, compares versions and prints the answer.

2. [JUDGEMENT] **Nothing newer: one line, no dispatch.** Say the version they are on and that it is current, in their language, and stop. No expert is dispatched, no CHANGELOG is opened, nothing is verified a second time. A report with headings about an update that does not exist is noise.

3. [JUDGEMENT] **Something newer: dispatch Pepper** via the `Agent` tool with `subagent_type: pepper`, passing the version pair the check reported. **The prompt needs the two labelled blocks** (`brief`), and here they are short and always the same shape, so there is nothing to interview about:

   ```
   What the user said: /zanmai-update
   What I concluded: bring this space from <old> to <new>, the published release. Nothing else.
   ```

   Without the first heading, `dispatch-guard` refuses the dispatch. Seen on the
   first real `/zanmai-update` after the guard existed: the handover was the version pair alone, the
   guard turned it back, and the turn was spent twice.

   Pepper reads the CHANGELOG and returns the preview. **She changes nothing in this run.** Steve
   relays the preview verbatim and asks for the go.

4. [JUDGEMENT] **On the user's yes: dispatch Pepper a second time**, same two blocks, and the second one carries
   `mode: apply` plus the version pair. Only now does she apply, verify, roll back on failure and
   write the history line.

   **She does not take a snapshot of her own.** `setup upgrade` takes one itself, before it replaces
   anything, and a second beside it is not twice as safe: it is the same state stored twice, one copy
   named after whoever triggered it. Where the upgrade path reports no snapshot, that is a fault to
   report, not a gap to fill in by hand.

   **Two dispatches, not one, and this is the whole point of the step.** A subagent runs start to
   finish and cannot wait mid-run for an answer that is not in its context, so "apply after the user
   says yes" inside one dispatch is an instruction nobody can carry out. On 2026-08-26 that is exactly
   what happened in a space in daily use: the preview came back reading "ready to apply on your yes", and the
   space was already on the new version when it was read. The gate belongs to Steve, in the chat,
   between two dispatches. Nowhere else can hold it.

## When to use

- The user types `/zanmai-update`.
- Steve may invoke this skill on the natural-language equivalent if the intent is unambiguous, but the slash-command form is the canonical strongest trigger.

## Channel

By default a space tracks the published release. `zanmai.py setup upgrade. --channel <name>` (for
example `beta`) switches which branch it tracks and remembers the choice in `zanmai/user.md`, so it
survives every later update; `--channel release` switches back. Steve only runs this on an explicit
user request naming the channel, never on his own judgement, since a beta channel by definition carries
material that has not gone through the normal release check.

## A source the user names

An update normally comes from the published release. When the user names a source instead, a folder,
an archive or a URL, the same workflow runs with `--from <source>` throughout, Step 1 included:
`zanmai.py setup upgrade . --check --from <source>` reads the version out of the source and reports
the comparison without applying anything, and the apply step is the same call without `--check`.
Everything else is unchanged, the snapshot included.

Steve does this only when the user names the source. A source outside the release has not been
through the release check, which is why it is the user who decides that it is the one to take.

## When not to use

- The user wants a snapshot, a restore, a structure check, or a bulk repair. Those are also Pepper's domain but go through their own paths (slash-commands or natural-language triggers), not through this skill.

## Files

- `zanmai/system/experts/pepper/pepper.md`: the executor Steve dispatches and the full workflow definition.
- `zanmai/system/CHANGELOG.md`: per-version release notes that Pepper reads to compose the TL;DR.
- `zanmai/update-history.md`: local audit trail. The update writes its own line, with the source it came from; Pepper adds one for a rollback.
