---
name: zanmai:journal
description: Capture freeform input into today's journal entry (or the week, month or year when named), and write the period rollups. Steve runs this skill inline, capture is lightweight and does not need a subagent. Triggered by `/zanmai-journal <text>`, by any equivalent "log this / trag das ein" intent, and at session start for a due rollup.
---

# journal

Capture into the periodic notes. Steve executes this directly, no dispatch, appending a line or a dump is cheap. The slash-command form is the strongest trigger; the user typed it, so there is no confirmation gate.

## Core principle

Capture first, structure later. The user's words go into the note the way the user wrote them, no marker vocabulary, no reshaping into buckets, no imposed sections. A voice memo turned into three paragraphs of stream-of-consciousness lands as three paragraphs. Only once the raw input is safely down does Steve look at what follows from it, and those follow-ups are frontmatter side effects and proposals, never edits to the body the user gave.

## Activation

The journal is always there, so there is nothing to check first. Capture happens only on an explicit trigger (a dump, a "log this", a request for a period). No unsolicited lines into an entry.

## Hard rules

0. **Every state change is a `zanmai.py journal` call.** The path, the bundle folder, whether a rollup is due, whether one already exists: all of that is worked out by the command, not by the AI. What is left to judgement is the wording of a summary, and nothing else.
1. **Append-only.** Past entries are never edited. A correction is a new entry that wikilinks back (`Correction to [[2026-06-22]]`). Today's daily grows through the day; each new input goes below what is already there.
2. **Verbatim capture.** The input enters the note unchanged in wording. No marker symbols, no reformatting into task/event/note categories, no forced headings. Preserve the paragraph and line breaks the input already carries; add no structure the user did not write.
3. **No silent overwrite.** If the target note already holds user content, append below it. If appending would clash with something the user looks to be mid-edit (one coherent prose block), name the situation to the user and let them pick append, hold, or replace-with-explicit-yes. Empty or template-shell-only notes may be filled.
4. **Follow-ups never touch the body.** After capture, mirror a mood signal into the note's frontmatter (`mood:`, plus `energy:` if named), write a habit completion as a wikilink pointer, and propose wikilinks, all without rewriting the captured text.
5. **Stub the obvious, propose the rest.** When the input clearly names a real, returnable person or organization (a full name with context, a named company), create the stub via `zanmai.py contact create` so the link resolves. When the name is a fragment, a one-off, or ambiguous, flag it as a proposal and create nothing. When in doubt, propose, a daily carries many transient names, and recurrence across days is the signal to promote one.
6. **Template-independent.** Require and write no template. If the entry already carries a shell the user's editor put there, append below whatever is there. Otherwise append into a plain note.
7. **No proactive mood.** Never invent a `mood:` value. Record mood only when the user gave a signal or asked to log one.
8. **Text only.** Audio (`mp3`, `wav`, `m4a`, voice memos) is transcribed by Reed first: Steve dispatches Reed, takes the transcript back, then runs this capture with the text. This skill handles no audio itself.

## Capture workflow

In order, every input.

1. **Resolve target.** Default today's daily. If the trigger names the weekly, the monthly, the yearly, or a specific past period, use that (past periods only on explicit request). Read the target entry and classify its state: missing, shell only, has user content.
2. **Append verbatim.** `zanmai.py journal append --kind <daily|weekly|monthly|yearly> --text "<the user's words>"`, unchanged. The command creates the bundle folder and the entry if they are not there, appends below whatever is already in it, and logs the write. Never assemble the path by hand: the ISO week is the trap, the week of 1 January belongs to the previous year more often than not.
3. **Mirror mood.** If the input carries a mood signal, stated ("müde", "on fire") or clearly implied, write it into the note's frontmatter via `Edit` on the frontmatter block, never into the body as a reshaped line.
4. **Habit side effects.** For an activity that matches an existing habit bundle in `habits/`, write `- [x] [[<habit-slug>]]` as a pointer and update the habit bundle's `last_done:` field. The bundle is the canonical completion record; the note holds the pointer.
5. **Entities.** For a clearly identified person or organization with no contact file, create the stub (Hard Rule 5). For entity-shaped but uncertain names, prepare a flag for the user. For entities that already have files, propose `[[wikilink]]`s. Read `zanmai/memory/patterns.json` once to match known slugs.
6. **Confirm to the user.** One short line naming what was captured, where, which wikilinks were proposed, which stubs were created, and what was flagged. No execute-question, the dispatch already happened by the user's trigger.

## Period rollups

A rollup is a synthesis of the layer one step below, written upward.

- **Weekly rollup** at the first session of a new ISO week, from the prior week's daily entries.
- **Monthly rollup** at the first session of a new month, from the prior month's weekly entries.
- **Yearly rollup** at the first session of a new year, from the prior year's monthly entries.

Rules:

- **One level down only.** Weekly reads dailies, monthly reads weeklies, yearly reads monthlies. If the finer layer holds nothing for that period, no rollup runs; monthly never falls back to dailies.
- **The decision is not yours to make.** `zanmai.py journal rollup-due` says which rollups are due and names the entries each one reads. It checks whether the period entry already carries a rollup and whether the layer below holds anything at all. Do not work that out from dates in your head.
- **Automatic, because non-destructive.** `zanmai.py journal rollup --kind <kind> --text "<summary>"` writes it without an approval gate: it appends below existing content, never overwrites, never edits, never touches the source entries. Since nothing is lost, no confirmation is needed.
- **Quote, do not invent.** Quote the user's own phrasing from the source entries, recurring themes, tasks still open versus done, the mood arc from the frontmatter mirrors, notable events. Add no theme the user did not write.
- **Once per period.** The command refuses a second rollup for the same period, so this cannot double up even if the skill is run twice.

Writing directly into a weekly or monthly note (the user dumps into it) is plain capture, same verbatim behavior as the daily.

## Session-start reconciliation

At session start the briefing may list **journal link candidates**, existing contacts or bundles that recent entries name in plain text but do not yet wikilink, ranked by how often they recur (computed by the session-start hook, not guessed). This is the journal working as an indirect day-memory: what currently moves the user, held against what the vault already holds.

When candidates are present, Steve may offer once to connect them, a proposal, never automatic. Recurrence is the signal: a name in one note is a passing mention; a name across several is worth connecting. Two ways to connect, both user-gated:

- **Going forward** (default): link the entity in the current and future captures, and, if it is only a bare stub, flesh out its file. No past note is touched.
- **Retroactively**: wikilinking the plain-text mentions already sitting in past notes is an edit to append-only user content (Hard Rule 1), so it happens only on the user's explicit yes.

## Tone

Warm, present, brief. Short sentences. No em dash as a casual separator (operating-principles §7). Reflective questions stay plain ("how is today?"), never clinical. In a rollup, quote the user rather than paraphrase.

## The commands, all of them

Everything the journal does is a subcommand, and nothing about it is left to be worked out at the moment of use.

```
zanmai.py journal path       --kind <kind> [--date YYYY-MM-DD]   where the entry is, creates nothing
zanmai.py journal ensure     --kind <kind> [--date]              create the entry and its bundle
zanmai.py journal append     --kind <kind> [--date] --text "…"   the user's words, verbatim, below
zanmai.py journal read       --kind <kind> [--date]              print it, or say it holds nothing
zanmai.py journal list       --kind <kind> [--limit N]           what exists, with bundle contents
zanmai.py journal rollup-due [--date]                            which rollups are due, and from what
zanmai.py journal rollup     --kind <kind> --text "…"            write it, once per period
```

`<kind>` is `daily`, `weekly`, `monthly` or `yearly`. Use `Edit` on an entry only for something no
subcommand covers, and only on the user's instruction.

## When not to use

- The user is researching, importing, asking the gateway, or running any other workflow. This skill is the journal capture surface only.

## Files

- `zanmai/system/scripts/zanmai.py`: the `journal` subcommands, the whole surface.
- `zanmai/system/docs/daily-capture.md`: background on verbatim capture and the period rollups.
- `zanmai/system/operating-principles.md`: §6 (the journal is the user's, and the rollup exception), §8 (checkboxes are the user's).
- `zanmai/system/experts/reed/reed.md`: audio transcription handoff.
- `zanmai/system/experts/hank/hank.md`: filing handoff if a note mention crystallises into a multi-file move.
