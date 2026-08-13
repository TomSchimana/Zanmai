---
name: zanmai:update
description: Explicit update trigger for Pepper. The user invoked `/zanmai-update` to bring the vault's distribution to the current published version. The slash-command form is the strongest possible trigger; Steve dispatches Pepper in the same turn. Steve checks the version inline first and only dispatches Pepper when there is something to apply; Pepper then builds the update TL;DR for the user to approve, snapshots, applies, verifies, and rolls back on failure. The full workflow lives in Pepper's contract.
---

# update

Explicit distribution-update trigger. The user typed the command, the user wants the update. Steve does not second-guess.

## Directive

The slash-command form is the strongest possible trigger. Steve dispatches Pepper via the `Agent` tool with `subagent_type: pepper` in the same turn, no confirmation question at the dispatch level. The user already approved by typing the command. Pepper's own TL;DR-preview gate (Hard Rule 7 in `pepper.md`) is where the user confirms or refuses the actual apply.

## Workflow

1. **Check it yourself first, it takes a second.** Steve runs `zanmai.py setup upgrade . --check` inline. This is mechanics, not expert work: the command resolves where this vault gets updates, compares versions and prints the answer.

2. **Nothing newer: one line, no dispatch.** Say the version they are on and that it is current, in their language, and stop. No expert is dispatched, no CHANGELOG is opened, nothing is verified a second time. A report with headings about an update that does not exist is noise.

3. **Something newer: dispatch Pepper** via the `Agent` tool with `subagent_type: pepper`, passing the version pair the check reported. Pepper reads the CHANGELOG for what changed, snapshots, applies, verifies, and rolls back on failure. Steve relays her preview verbatim and asks for the go; the apply happens after the user's yes.

## When to use

- The user types `/zanmai-update`.
- Steve may invoke this skill on the natural-language equivalent if the intent is unambiguous, but the slash-command form is the canonical strongest trigger.

## Channel

By default a vault tracks the published release. `zanmai.py setup upgrade . --channel <name>` (for
example `beta`) switches which branch it tracks and remembers the choice in `zanmai/user.md`, so it
survives every later update; `--channel release` switches back. Steve only runs this on an explicit
user request naming the channel, never on his own judgement, since a beta channel by definition carries
material that has not gone through the normal release check.

## When not to use

- The user wants a snapshot, a restore, a structure check, or a bulk repair. Those are also Pepper's domain but go through their own paths (slash-commands or natural-language triggers), not through this skill.

## Files

- `zanmai/system/experts/pepper/pepper.md`: the executor Steve dispatches and the full workflow definition.
- `zanmai/system/CHANGELOG.md`: per-version release notes that Pepper reads to compose the TL;DR.
- `zanmai/update-history.md`: local audit trail Pepper writes to after each successful or rolled-back update.
