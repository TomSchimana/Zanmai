---
name: zanmai:welcome
description: Show what is currently waiting and open, the same list a session opens with, rebuilt as things stand. Triggers on `/zanmai-show-welcome` and on a clear ask for what is open right now.
---

# welcome

The list the session opened with, shown again mid-session. It exists because the greet scrolls away:
an hour and a dozen operations later it is somewhere far above, and the way back to it used to be
starting a new session, which is an absurd price for reading nine lines.

## Run this

```
<python_cmd> zanmai/system/scripts/zanmai.py welcome
```

Render exactly what it prints, under the rules in `zanmai/system/skills/greeting/SKILL.md`: the
lines are already selected, sorted, capped and numbered, and nothing is added to them. Translate the
headings and the wording into the user's writing language, keep each item's own words.

No greeting in front of it. The user is already in the session and asked to see the list, not to be
welcomed again. No closing question either unless they asked one; if the list is empty, say that in
one sentence rather than composing something to fill it.

## What it is not

- **Not a rebuild of anything.** It reads the space as it stands and prints. Nothing is written.
- **Not the same list as before.** What was dealt with since the greet is gone from it, what arrived
  since is in it. That is the point of running it rather than scrolling up.
- **Not everything open.** Work dated further out than the next week is counted, not listed, the
  same rule the greet follows: a date in the future is a plan, not something waiting today.

## Sounds sensible, is wrong

| Rationalization | Reality |
|---|---|
| "The user said list, they probably mean the open items." | Only where they clearly asked for what is open or waiting. Any other list in the conversation is a different list, and answering with this one loses whatever they were actually looking at. |
| "I still have the greet in context, I can repeat it from there." | Then it is stale by exactly the work done since. Run the command. |
| "The list is empty, I'll pull in something else so the answer is not blank." | An empty list is an answer, and a good one. |
