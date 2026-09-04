---
name: zanmai:housekeeping
description: Check the space's keeping times and its shape, run by Pepper. Triggers on `/zanmai-housekeeping` and any ask to run housekeeping or tidy up the space.
---

# housekeeping

Explicit housekeeping trigger. The user typed the command or asked for it in their own words, and
wants a report on where the space stands.

## Directive

The slash-command form is the strongest possible trigger. Steve dispatches Pepper via the `Agent`
tool with `subagent_type: pepper` and `run_in_background: true`, in the same turn, no confirmation
question at the dispatch level; `dispatch-guard` corrects it to the background regardless, so a
foreground call is never live even where this is missed. Report only: nothing this skill runs
writes or moves anything but what is already past its keeping time, which the command sweeps on
its own. The user does not wait on this: report whatever Pepper finds when she returns.

## What Pepper does

1. [SCRIPT] Run `zanmai.py housekeeping` from the space root. It does three things in one pass:
   sweeps trash, scratch space and snapshots older than their keeping time; reports bundles that
   hold nothing but their own page, a single item given a folder; lists the bundles of every area
   side by side, so a matter split across two areas or a duplicate name is visible at a glance.
2. [JUDGEMENT] Read every rule in `zanmai/memory/general.md` against its own purpose, the same
   check the `pepper.md` housekeeping workflow describes: a lasting principle, not a single case,
   and not an instruction about what happens to an incoming file, which belongs in the routing
   table and is reported with the `routing set` line that would replace it.
3. [JUDGEMENT] Read the shape findings as raw material, not a report: the thin-bundle list and
   every area's bundles side by side. Connect what belongs together by matter, not by name: a
   trip sitting in `workbench/` and trips sitting in `life/` are one shape even where no word
   matches, the same name in two areas is one matter split. Return to Steve: what the sweep
   cleared, the thin bundles, the connections found with a one-line reason each, and the
   general.md findings with their reason. Nothing here is applied. Where a section is empty, say
   so plainly rather than listing nothing.

Steve relays the report in the user's writing language and asks what, if anything, the user wants
fixed. **The report is not the end of the job, only its first half.** On a yes, Steve dispatches
Hank via the `Agent` tool with the finding(s) as the brief: for a bundle holding nothing but its
own page, Hank applies his own rule that a bundle is the broad matter, never the single item
(`hank.md`, filing heuristic 4), proposes where it belongs and, on approval, runs `bundle add-file`
into the target and retires the thin one. For an area whose shape looks split or duplicated, Hank
proposes the merge the same way. A command that only ever reports and never finishes the job on the
user's go is not worth running twice.

## When to use

- The user types `/zanmai-housekeeping`.
- Steve may invoke this skill on the natural-language equivalent ("housekeeping", "tidy up",
  "check the shape of the space") if the intent is unambiguous.
- The session-start hook already surfaces the same shape findings once a week on its own; this
  skill is the on-demand path for whenever the user wants a look sooner.

## When not to use

- The user wants a snapshot, a restore, a distribution update, or a bulk repair touching more
  than one file's content. Those are also Pepper's domain but go through their own paths.

## Files

- `zanmai/system/experts/pepper/pepper.md`: the executor Steve dispatches.
- `zanmai/system/scripts/zanmai.py` (`housekeeping`): the actual mechanic, and the one it shares
  with the weekly automatic surfacing in the session-start hook.
