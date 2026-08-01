---
name: zanmai:close-session
description: Write the session hand-off when the user wraps a session. Triggers when the user asks to close, wrap or end the session in their writing language, or via `/zanmai:close-session`. Writes a hand-off log to `.zanmai/logs/YYYY/MM/<timestamp>-<slug>.md` with four sections (Done, Next, Intent, Realignments) and graduates durable insights to `.zanmai/memory/general.md`. Closes with a briefing rebuild so the next session starts ready.
---

# close-session

Persistent hand-off at session close. Four sections, no more.

## Directive

Four sections, in this order, every time: Done, Next, Intent, Realignments. Adding a fifth section is out of scope for a session close. If a piece of content does not fit one of the four, ask whether it belongs in `.zanmai/memory/general.md` instead.

## When to use

- The user signals end-of-session in their writing language (close session, wrap up, we are done, end for today).
- The user invokes `/zanmai:close-session`.
- Steve detects the session is winding down and offers to close.

## When not to use

- Mid-session note taking. Use the bundle's own file for that.
- Capturing a single fact. Use the bundle or `.zanmai/memory/general.md`.
- The user wants a status report mid-session. That is a manual ask, not a session close.

## The four sections

### Done

What was actually accomplished. Concrete artefacts (files written, decisions taken, imports completed). Not "we discussed". Not "we considered". Things that exist after the session that did not exist before.

### Next

The single most important next step for the next session. Plus one backup item if there is a natural follow-up. One or two items, not a backlog. The full backlog lives elsewhere, this is the entry point for the next session.

Read it off `zanmai.py work list`, do not compose it from memory of the conversation. Anything still waiting on the user is named here with its short id, because that is the one class of open item the next session cannot work out for itself: the work is done as far as it can go and stopped on a decision. A specialist parked on such a decision does not survive the close (operating-principles §12), so the object and its workshop are what the next session picks up from.

### Intent

What the user wants in the medium term. The framing the next session should pick up. One paragraph. If the intent did not change this session, write "unchanged" and reference the previous session's intent.

### Realignments

What the user's corrections established, in the user's writing language: the concrete thing that was off, and the rule now in force. Precise and unsoftened, never their wording, a chat message is transient and a file is not. This section is the team memory, and the rule is what has to survive intact across sessions.

## The workflow

### Step 1: compose silently

Draft the four sections internally from the session history. Do not show the draft to the user, do not ask for confirmation. The user invoked the close, they want it done, not previewed. Steve writes the file in Step 2 and reports the result in Step 4. If the user wants to edit afterwards, they open the log file and edit, that is cheap.

This rule exists because close-session is a wrap-up, not a planning step. A draft-then-confirm dance turns a 5-second close into a 60-second back-and-forth and trains the assistant to over-ask. The contract is: invoke close, get a closed session.

The only exception. If a realignment from this session is genuinely ambiguous (the user gave contradicting feedback), Steve writes the log without the contested item and notes in the confirmation that one item was left out because of ambiguity, asking the user (in their writing language) to say so if it should be added.

### Step 2: write the log file

Path: `.zanmai/logs/YYYY/MM/YYYY-MM-DD-HHMM-<slug>.md`. The slug is one to three kebab-case words capturing the session theme.

Frontmatter:

```yaml
---
kind: knowledge
slug: <slug>
created: YYYY-MM-DD
session_type: close-session
---
```

Then four `## Section` headings with the content, in the user's writing language.

Create the `YYYY/MM/` folder if missing.

### Step 3: graduate insights (optional)

If a realignment is a permanent rule, not a one-off correction, append a bullet to `.zanmai/memory/general.md` under the appropriate section (`## Preferences`, `## Lessons`, `## Decisions`). Link back to the session log with a wikilink.

**Then keep those files to their rules.** Anything appended to memory is read at the start of a later run, so its size is paid for on every dispatch: on a real vault after three days, one specialist's lessons had reached 678 lines and all of it went into that specialist's context each time. So the close runs `zanmai.py memory curate --file <the file just written to>`, which moves struck entries and long reasoning into a dated archive beside the file and leaves the rule and its bounds in place. What it cannot decide it reports: an entry still marked provisional from an earlier month is put to the user, because dropping a lesson nobody ever checked would lose exactly the ones that were never checked. A standing rule is never rotated out by date; a rule has no expiry, and "do not suggest that again" retired after two months means it gets suggested again.

The chronological log is the other case and takes the other treatment: `zanmai.py memory rotate` moves its older months into an archive beside it, leaving one index line. It is searched, not read, so nothing is lost by moving it.

Do not promote everything, this is the high-signal layer.

### Step 3a: hold the feedback against the lessons already there

Appending is the easy half. Where an expert did work this session and the user said something about the result, read that expert's `.zanmai/memory/agents/<name>/lessons.md` and check the standing entries against what the user actually said, before writing anything new.

- Feedback that contradicts an entry adds a **Disproven:** line to it, with the date and what the feedback showed. The entry stays where it is and stops applying. Never delete it silently and never write a second lesson beside it: two entries pointing opposite ways leave the next run free to pick the flattering one.
- An entry marked `provisional` that this session's feedback bears out becomes `confirmed`. One the user has now contradicted is struck as above.
- A new lesson from work the user has not seen or judged is written `provisional`, whatever the run looked like from the inside.

The cost of skipping this is not a missing note, it is a wrong instruction that gets more authoritative every session. An agent's own account of its work is the weakest evidence in the vault; the user's reaction to the result is the strongest, and this is the one step where the two meet.

### Step 4: confirm

One sentence in the user's writing language confirming the close and naming the one-line Next item for the next session. No internal file paths in the reply, the log lives under `.zanmai/logs/`, the user does not navigate there. The Next item is the substance the user actually wants to hear: what the next session will pick up.

**A session nobody attended closes the same way, into the file rather than the chat.** Its frontmatter carries `session_type: unattended`, which is what makes the next real session mention it. Done and Next are written as always, from what ran and from `zanmai.py work list`. Intent is "unchanged". Realignments is empty, since nobody corrected anything, and an empty section is the honest answer rather than a paragraph invented to fill it.

### Step 5: mark session end

Write the current timestamp to `.zanmai/memory/.last-session-end` so Steve's next session knows where to draw the "what happened since I was last here" line. Single line, ISO 8601 with seconds:

```
date -u +"%Y-%m-%dT%H:%M:%SZ" > .zanmai/memory/.last-session-end
```

This is silent infrastructure, the user sees nothing about it. If close-session was not invoked (the user just stops), the marker stays at the previous close. Steve falls back to a "last three days minus today" window.

### Step 6: rebuild the briefing

The briefing file (`.zanmai/memory/briefing.md`) is Steve's session-start context for the next session. Close-session is one of two atomic triggers (the other is `zanmai.py memory report`). Rebuild it now from current vault state:

```
<python_cmd> .zanmai/system/scripts/zanmai.py memory briefing <vault>
```

Atomic rebuild, around 30 lines, three sections: current state, open items, gaps and hints. No human input needed, the script reads vault state and synthesises. If this step is skipped, the next session's greet falls back to whatever briefing was there last, possibly outdated.

The transient workspace `.zanmai/work/` is not cleared here, the session-start hook prunes it (age-based, keeping recent unfinished work). One rule, one place.

## Rationalizations to resist

| Rationalization | Reality |
|---|---|
| "I'll quote the correction so it keeps its force." | Never a quote. Write the rule that follows from it. Force comes from precision, not from the user's words. |
| "Five sections would capture more." | The format is four. Roadmap-style extras live elsewhere. |
| "Done was empty, I'll skip the section." | Write that nothing was completed and what was explored instead. An empty Done is informative. |
| "I'll add an extra Insights or Notes section." | If the content cannot tie to one of the four, propose `.zanmai/memory/general.md` instead. |
| "I'll auto-promote every realignment to memory." | Only durable rules graduate. One-off corrections stay in the log. |
| "I'll show the draft to the user and let them edit before I write." | No. The user invoked close to close, not to review a draft. Write the file in Step 2, report in Step 4. Edits happen afterwards, by opening the file. |
| "I'll ask whether to write the file before saving." | Never. Close-session is the most auto-complete-able skill in the system. The user typed the close trigger, that is the green light. Asking again is anti-pattern. |

## Red flags, stop and recheck

- About to write to `.zanmai/memory/general.md` without consulting the user.
- The realignments section is empty when the user clearly redirected at least once during the session.
- The slug is generic (`session-1`, `close`, `wrap`).
- The log path is missing the `YYYY/MM/` nesting.
- More than four `## Section` headings in the file.
- About to show the four-section draft in chat and ask whether to save. The user triggered the close, the file gets written directly.
- Step 5 (the `.last-session-end` marker) or Step 6 (briefing rebuild) was skipped. Both are silent infrastructure, skipping them means the next session's greet is broken. Run them every time.

## Files

- `.zanmai/logs/YYYY/MM/`: destination.
- `.zanmai/memory/general.md`: graduation target.
- `.zanmai/system/templates/session-log.md`: template to start from if useful (optional).
