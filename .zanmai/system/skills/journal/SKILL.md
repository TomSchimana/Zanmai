---
name: zanmai:journal
description: Capture freeform input into the active Daily, Weekly or Monthly Note, and write the period rollups. Steve runs this skill inline, capture is lightweight and does not need a subagent. Triggered by `/zanmai:journal <text>`, by any equivalent "log this / trag das ein" intent, and at session start for a due rollup. Conditional on the ZenNotes periodic-notes feature (Daily, Weekly or Monthly) being enabled in `.zanmai/vault-config.md`. If all are off, Steve answers in one user-language line that the feature is not configured.
---

# journal

Capture into the periodic notes. Steve executes this directly, no dispatch, appending a line or a dump is cheap. The slash-command form is the strongest trigger; the user typed it, so there is no confirmation gate.

## Core principle

Capture first, structure later. The user's words go into the note the way the user wrote them, no marker vocabulary, no reshaping into buckets, no imposed sections. A voice memo turned into three paragraphs of stream-of-consciousness lands as three paragraphs. Only once the raw input is safely down does Steve look at what follows from it, and those follow-ups are frontmatter side effects and proposals, never edits to the body the user gave.

## Activation

Read `.zanmai/vault-config.md` (regenerated every session start). If `daily_notes_enabled`, `weekly_notes_enabled` and `monthly_notes_enabled` are all false, do not capture, answer in one user-language line that periodic notes are not configured for this vault, and stop. Each layer is independent; work whichever ones are on. Capture happens only on an explicit trigger (a dump, a "log this", a request for a period). No unsolicited lines into a note.

## Hard rules

1. **Append-only.** Past entries are never edited. A correction is a new entry that wikilinks back (`Correction to [[2026-06-22]]`). Today's daily grows through the day; each new input goes below what is already there.
2. **Verbatim capture.** The input enters the note unchanged in wording. No marker symbols, no reformatting into task/event/note categories, no forced headings. Preserve the paragraph and line breaks the input already carries; add no structure the user did not write.
3. **No silent overwrite.** If the target note already holds user content, append below it. If appending would clash with something the user looks to be mid-edit (one coherent prose block), name the situation to the user and let them pick append, hold, or replace-with-explicit-yes. Empty or template-shell-only notes may be filled.
4. **Follow-ups never touch the body.** After capture, mirror a mood signal into the note's frontmatter (`mood:`, plus `energy:` if named), write a habit completion as a wikilink pointer, and propose wikilinks, all without rewriting the captured text.
5. **Stub the obvious, propose the rest.** When the input clearly names a real, returnable person or organization (a full name with context, a named company), create the stub via `zanmai.py contact create` so the link resolves. When the name is a fragment, a one-off, or ambiguous, flag it as a proposal and create nothing. When in doubt, propose, a daily carries many transient names, and recurrence across days is the signal to promote one.
6. **Template-independent.** Require and write no template. If the user has a ZenNotes template bound, the note already carries its shell; append below whatever is there. Otherwise append into a plain note.
7. **No proactive mood.** Never invent a `mood:` value. Record mood only when the user gave a signal or asked to log one.
8. **Text only.** Audio (`mp3`, `wav`, `m4a`, voice memos) is transcribed by Reed first: Steve dispatches Reed, takes the transcript back, then runs this capture with the text. This skill handles no audio itself.

## Capture workflow

In order, every input.

1. **Resolve target.** Default today's daily. If the trigger names the weekly, the monthly, or a specific past period, use that (past periods only on explicit request). Read the target note and classify its state: missing, template-shell only, has user content.
2. **Append verbatim.** Write through the `notes` skill (`zanmai.py notes daily|weekly|monthly --append`), preserving the user's wording. If the note has prior content, the new input goes into a fresh block below it.
3. **Mirror mood.** If the input carries a mood signal, stated ("müde", "on fire") or clearly implied, write it into the note's frontmatter via `Edit` on the frontmatter block, never into the body as a reshaped line.
4. **Habit side effects.** For an activity that matches an existing habit bundle in `inbox/habits/`, write `- [x] [[<habit-slug>]]` as a pointer and update the habit bundle's `last_done:` field. The bundle is the canonical completion record; the note holds the pointer.
5. **Entities.** For a clearly identified person or organization with no contact file, create the stub (Hard Rule 5). For entity-shaped but uncertain names, prepare a flag for the user. For entities that already have files, propose `[[wikilink]]`s. Read `.zanmai/memory/patterns.json` once to match known slugs.
6. **Confirm to the user.** One short line naming what was captured, where, which wikilinks were proposed, which stubs were created, and what was flagged. No execute-question, the dispatch already happened by the user's trigger.

## Period rollups

A rollup is a synthesis of the layer one step below, written upward.

- **Weekly rollup** at the first session of a new ISO week, from the prior week's daily notes.
- **Monthly rollup** at the first session of a new month, from the prior month's weekly notes.

Rules:

- **One level down only.** Weekly reads dailies, monthly reads weeklies. If the finer layer is disabled, the higher note is a capture surface only, no rollup runs. Monthly never falls back to dailies.
- **Automatic, because non-destructive.** The rollup is written without an approval gate: it creates the period note or appends a rollup section below existing content, and never overwrites, never edits, never touches the source notes (they stay append-only). Since nothing is lost, no confirmation is needed.
- **Quote, do not invent.** Quote the user's own phrasing from the source notes, recurring themes, tasks still open versus done, the mood arc from the frontmatter mirrors, notable events. Add no theme the user did not write.
- **Once per period.** If a rollup for that week or month already exists, write no second. One rollup, no duplicates, no nag.

Writing directly into a weekly or monthly note (the user dumps into it) is plain capture, same verbatim behavior as the daily.

## Session-start reconciliation

At session start the briefing may list **journal link candidates**, existing contacts or bundles that recent periodic notes name in plain text but do not yet wikilink, ranked by how often they recur (computed by the session-start hook, not guessed). This is the journal working as an indirect day-memory: what currently moves the user, held against what the vault already holds.

When candidates are present, Steve may offer once to connect them, a proposal, never automatic. Recurrence is the signal: a name in one note is a passing mention; a name across several is worth connecting. Two ways to connect, both user-gated:

- **Going forward** (default): link the entity in the current and future captures, and, if it is only a bare stub, flesh out its file. No past note is touched.
- **Retroactively**: wikilinking the plain-text mentions already sitting in past notes is an edit to append-only user content (Hard Rule 1), so it happens only on the user's explicit yes.

## Tone

Warm, present, brief. Short sentences. No em dash as a casual separator (operating-principles §7). Reflective questions stay plain ("how is today?"), never clinical. In a rollup, quote the user rather than paraphrase.

## When not to use

- The user is researching, importing, asking the gateway, or running any other workflow. This skill is the periodic-note capture surface only.
- The periodic-notes feature (Daily, Weekly and Monthly) is fully disabled. Activation short-circuits and Steve stops.

## Files

- `.zanmai/system/skills/notes/SKILL.md`: the writer skill this composes for the actual note write.
- `.zanmai/system/docs/daily-capture.md`: background on verbatim capture and the period rollups.
- `.zanmai/system/operating-principles.md`: §6 (periodic-note user-ownership and the rollup exception), §8 (checkbox conventions).
- `.zanmai/system/experts/reed/reed.md`: audio transcription handoff.
- `.zanmai/system/experts/hank/hank.md`: filing handoff if a note mention crystallises into a multi-file move.
