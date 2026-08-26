---
name: zanmai:research
description: Sourced research with citations, run by Reed. Triggers on `/zanmai-research`, "find out", "what is out there", "what does it cost".
---

# research

Explicit research trigger. The user invoked `/zanmai-research`. The slash-command form means this is a Reed job, no ambiguity. Steve does not decide whether to dispatch, the slash command already decided.

## Directive

The slash-command form is the strongest possible trigger. Steve does not second-guess whether the topic actually needs Reed, does not offer to answer from model knowledge instead. The user typed the command, the user wants Reed. The only conversation step before dispatch is the pre-dispatch brief (CLAUDE.md Hard Rule 9). Never a "should I dispatch" question.

## Workflow

1. Read the trigger payload. The user invoked the command with a topic after it. The topic is the raw research question.

2. Pre-dispatch brief, mandatory, never skipped per Hard Rule 9. Steve states the planned brief in one chat turn with the seven load-bearing items:
   - Question (from the trigger payload, verbatim or lightly paraphrased).
   - Use case (what the user will do with the answer, Steve infers from context, asks once if unclear).
   - Stakes (high, medium or low, defaults to medium unless health, legal, financial or safety stakes are obvious, never silently low).
   - Audience (beginner, standard, expert or Reed-chooses, Steve reads the owner-contact's lessons-Steve-learned and domain-expertise sections, asks once if unclear).
   - Filing target (kind: reference default or read-once explicit, path: general-to-specific theme-bundle per Hard Rule 9, `knowledge/<theme>/<topic-slug>.md` for reference, `doing/<slug>/` for a read-once briefing).
   - Deliverable shape (list, table, report or comparison matrix, length sketch).
   - Constraints (language, source preferences, exclusions, time window like "twelve months or younger").

   The brief is plain prose in the user's writing language, two to four sentences. It ends with a confirmation question in the same language. Wait for user confirmation. No dispatch before yes.

3. Dispatch Reed via the `Agent` tool with `subagent_type: "reed"`. Reed gets the brief verbatim plus any clarifications from the confirmation turn.

**The prompt carries the two labelled blocks** (`brief`), headed exactly `What the user said:` and `What I concluded:`. `dispatch-guard` checks for the first heading literally and refuses the dispatch without it.

4. Reed runs the five-step research protocol independently in its own context (see `zanmai/system/experts/reed/reed.md`). Steve waits.

5. Reed returns with the deliverable path, the TL;DR and any source material that is worth preserving (transcript, repo snippets, domain pages).

6. Steve synthesises for the user per CLAUDE.md Hard Rule 10: a one-paragraph summary (five to eight lines, the key findings or comparisons), the path, an explicit offer to open phrased in the user's writing language. If Reed flagged source material worth preserving, Steve adds a second one-line offer asking whether to attach the preserved material to the bundle.

7. On the user's yes to the open offer, the file opens with the platform default.

## What this skill does not do

- It does not bypass the pre-dispatch brief. The brief is mandatory per Hard Rule 9.
- It does not change Reed's behaviour. Same five-step protocol, same source types, same return format.

## Trigger surface

The skill is registered as a slash command.

- `/zanmai-research`: canonical English.

The natural-language Reed-trigger pattern in the Steve contract still works without the slash command. The slash command is the explicit form for when the user wants to remove all guesswork.
