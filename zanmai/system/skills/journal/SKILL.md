---
name: zanmai:journal
description: Capture freeform input into today's journal entry, verbatim. Triggers on `/zanmai-journal` and on any "log this" intent.
---

# journal

Capture into the periodic notes. Steve executes this directly, no dispatch, appending a line or a dump is cheap. The slash-command form is the strongest trigger; the user typed it, so there is no confirmation gate.

## Core principle

Capture first, structure later. The user's words go into the note the way the user wrote them, no marker vocabulary, no reshaping into buckets, no imposed sections. A voice memo turned into three paragraphs of stream-of-consciousness lands as three paragraphs. Only once the raw input is safely down does Steve look at what follows from it, and those follow-ups are frontmatter side effects and proposals, never edits to the body the user gave.

## Activation

The journal is always there, so there is nothing to check first. Capture happens only on an explicit trigger (a dump, a "log this", a request for a period). No unsolicited lines into an entry.

## Hard rules

0. **Every state change is a `zanmai.py journal` call.** The path, whether one already exists: all of that is worked out by the command, not by the AI. What is left to judgement is the wording of a summary, and nothing else.
1. **Append-only.** Past entries are never edited. A correction is a new entry that wikilinks back (`Correction to [[2026-06-22]]`). Today's daily grows through the day; each new input goes below what is already there.
2. **Verbatim capture.** The input enters the note unchanged in wording. No marker symbols, no reformatting into task/event/note categories, no forced headings. Preserve the paragraph and line breaks the input already carries; add no structure the user did not write.
3. **No silent overwrite.** If the target note already holds user content, append below it. If appending would clash with something the user looks to be mid-edit (one coherent prose block), name the situation to the user and let them pick append, hold, or replace-with-explicit-yes. Empty or template-shell-only notes may be filled.
4. **Follow-ups never touch the body.** After capture, mirror a mood signal into the note's frontmatter (`mood:`, plus `energy:` if named), write a habit completion as a wikilink pointer, and propose wikilinks, all without rewriting the captured text.
5. **Stub the obvious, propose the rest.** When the input clearly names a real, returnable person or organization (a full name with context, a named company), create the stub via `zanmai.py contact create` so the link resolves. When the name is a fragment, a one-off, or ambiguous, flag it as a proposal and create nothing. When in doubt, propose, a daily carries many transient names, and recurrence across days is the signal to promote one.
6. **Template-independent.** Require and write no template. If the entry already carries a shell the user's editor put there, append below whatever is there. Otherwise append into a plain note.
7. **No proactive mood.** Never invent a `mood:` value. Record mood only when the user gave a signal or asked to log one.
8. **Text only.** Audio (`mp3`, `wav`, `m4a`, voice memos) is transcribed by Reed first: Steve dispatches Reed, takes the transcript back, then runs this capture with the text. This skill handles no audio itself. Where that text is bound for the daily, the day is the recording's own day, not today (Hard Rule 1's own logic, applied backward): use `zanmai.py voice journal-append` instead of `journal append` for that one case.

## Capture workflow

In order, every input. Each step says whether it is mechanics or judgement. **[SCRIPT]** means the step has one defined outcome and a command that produces it, so nothing here is decided by the run. **[JUDGEMENT]** means the outcome depends on reading the situation. A step marked [SCRIPT] that names no command is a rule sitting in prose, and prose at that position does not hold.

1. [JUDGEMENT] **Resolve target.** Today's entry, today meaning the day the words were said or written, not the day they are read. That is the same day for a live chat dump, so the default holds for the normal case without anyone thinking about it. If the trigger names a past day, use that day instead, and only when it was asked for. Read the target entry and classify its state: missing, or holding something already.
2. [SCRIPT] **Append verbatim.** `zanmai.py journal append --text "<the user's words>"`, unchanged. The command creates the entry if it is not there, appends below whatever is already in it, and logs the write. A day exists as a file only once something has been written into it, so nothing creates an empty one. Never assemble the path by hand. Text read off a voice recording is the one case where the day of writing and the day of speaking can genuinely differ: use `zanmai.py voice journal-append` instead (`voice` skill Step 5), it derives the target day from the recording rather than defaulting to today.
3. [JUDGEMENT] **Mirror mood.** If the input carries a mood signal, stated ("müde", "on fire") or clearly implied, write it into the note's frontmatter via `Edit` on the frontmatter block, never into the body as a reshaped line.
4. [JUDGEMENT] **Habit side effects.** For an activity that matches an existing bundle in `life/`, write `- [x] [[<habit-slug>]]` in the day's entry as a pointer to it. The day is the record: it happened on that day and stays there. Nothing is written into the bundle for it, and no field there tracks when it last happened.
5. [JUDGEMENT] **Entities.** For a clearly identified person or organization with no contact file, create the stub (Hard Rule 4). For entity-shaped but uncertain names, prepare a flag for the user. For entities that already have files, propose `[[wikilink]]`s. Read `zanmai/memory/patterns.json` once to match known slugs.
6. [JUDGEMENT] **Confirm to the user.** One short line naming what was captured, where, which wikilinks were proposed, which stubs were created, and what was flagged. No execute-question, the dispatch already happened by the user's trigger.

## Session-start reconciliation

At session start the briefing may list **journal link candidates**, existing contacts or bundles that recent entries name in plain text but do not yet wikilink, ranked by how often they recur (computed by the session-start hook, not guessed). This is the journal working as an indirect day-memory: what currently moves the user, held against what the space already holds.

When candidates are present, Steve may offer once to connect them, a proposal, never automatic. Recurrence is the signal: a name in one note is a passing mention; a name across several is worth connecting. Two ways to connect, both user-gated:

- **Going forward** (default): link the entity in the current and future captures, and, if it is only a bare stub, flesh out its file. No past note is touched.
- **Retroactively**: wikilinking the plain-text mentions already sitting in past notes is an edit to append-only user content (Hard Rule 1), so it happens only on the user's explicit yes.

## Tone

Warm, present, brief. Short sentences. No em dash as a casual separator (operating-principles principle:surfaces). Reflective questions stay plain ("how is today?"), never clinical. Quote the user rather than paraphrase.

## The commands, all of them

Everything the journal does is a subcommand, and nothing about it is left to be worked out at the moment of use.

```
zanmai.py journal path       [--date YYYY-MM-DD]   where the entry is, creates nothing
zanmai.py journal append     [--date] --text "…"   the user's words, verbatim, below
zanmai.py journal read       [--date]              print it, or say it holds nothing
zanmai.py journal list       [--limit N]           what exists
zanmai.py voice journal-append --file <recording> --text "…"     voice-derived only, dates by the recording
```

One entry per day, named by its date, under its year. Use `Edit` on an entry only for something no
subcommand covers, and only on the user's instruction.

## When not to use

- The user is researching, importing, asking the gateway, or running any other workflow. This skill is the journal capture surface only.

## Files

- `zanmai/system/scripts/zanmai.py`: the `journal` subcommands, the whole surface.
- `zanmai/system/operating-principles.md`: principle:journal (the journal is the user'sn), principle:tasks (checkboxes are the user's).
- `zanmai/system/experts/reed/reed.md`: audio transcription handoff.
- `zanmai/system/experts/hank/hank.md`: filing handoff if a note mention crystallises into a multi-file move.
