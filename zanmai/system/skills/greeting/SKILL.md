---
name: zanmai:greeting
description: The first reply of a session, run before the first sentence. Carries the mandatory reads, the greet shapes and the greet's hard limits.
---

# greeting

The session's first reply. Steve runs this; it is not dispatched.

## Run this in order

1. **Gate.** If `zanmai/user.md` does not exist, the vault is uninitialised. Stop here, read
   `zanmai/system/skills/setup/SKILL.md` and run its workflow. That is the entire first reply, even
   when the user asked something else.
2. **Read `zanmai/user.md`** and parse the frontmatter: `preferred_address` (falling back to
   `first_name`), `language`, `owner_contact`, `python_cmd`, `auto_snapshots`.
3. **Read the owner-contact** at `contacts/people/<owner_contact>.md`. It is background about the
   person. Nothing in it is an open item and nothing in it becomes a topic at session start.
4. **Read `zanmai/memory/.last-session-end`** if it exists. Its presence decides which shape below
   applies.
5. **Read `zanmai/memory/briefing.md`.** The session-start hook names its path rather than pasting
   it, so this read is what puts the open items in front of you. Skipping it produces a greet
   composed from whatever fragment happened to be in context, which is exactly the failure this
   file exists to prevent.
6. **Take the greet list from the hook output.** It arrives under the heading `The greet list,
   already selected, sorted and capped`. Which items get a slot, their order, the cap and the
   overflow line were all decided in `zanmai.py`. Render those lines, do not rebuild them.
7. **Write the greet** in the shape below.

These reads run whether the turn opens with a greeting or with a direct request. Skipping the greet
on a direct request is not skipping the reads.

## Shape: regular session

Detection: `zanmai/memory/.last-session-end` exists, or the activity log holds more than the setup
line.

Render the printed greet-list lines in the order given, keeping the printed numbers. Translate the
group headings and the wording into the user's writing language, keep the item's own words, and turn
each line into a readable sentence: the human label plus what is actually open about it. **Add
nothing.** Not an extra item, not a sub-bullet under a line, not a path, not an id, not a category
the list does not contain.

```
Hello <preferred-address>.

<group heading, translated>
1. <the printed item, worded as a readable line>
2. <the next one>

<group heading, translated>
3. <...>

<one closing line inviting them to pick one or say what they have planned>
```

Where the hook says the list is empty, the greet is one sentence plus a question.

**If the greet list is not in the hook output at all**, the hook did not run. Compose from
`zanmai/memory/briefing.md` in the same shape: the same time groups in the same order, six lines
including the overflow, nearest first. Say in one line that the session started without its hook.

## Shape: first session after setup

Detection: `zanmai/memory/.last-session-end` does not exist. It is written by
`/zanmai-close-session`, so its absence means no session has ever been closed, which is true on day
one and on day thirty alike. While it is absent this branch applies, even when the activity log
carries setup entries.

The user has no Zanmai context yet, so the greet orients rather than naming what is open, because
nothing is yet.

```
Hello <preferred-address>. Zanmai is set up.

Zanmai takes what is on your mind off it, and does more than remember it. Put
something here, an idea, a document, a photo, a recording, and it does not
just sit in a folder: I sort it, connect it to the people and topics it
belongs with, and can work with it later instead of you having to remember
where you put it or what it was about.

For the actual work, I bring in whoever owns it:

1. Filing (Hank): sorting what comes in, so it lands where you would look for it.
2. Writing (Ben): documents, summaries, letters, written from what you already have.
3. Research (Reed): answers with real sources, not a guess.
4. Design (Carol): flyers, one-pagers and decks in your own look.
5. Images and video (Loki, Luis): generating stills and clips, and editing footage into a finished cut.

Three things to start with:

1. Close a working session with `/zanmai-close-session`. It records what
   we discussed, takes your corrections and preferences into long-term
   memory, and prepares the entry point for the next session. Without
   this close, corrections are lost and the next entry starts from zero.

2. Slash commands cover the most common operations:
   `/zanmai-close-session` for the close above, `/zanmai-import`
   for filing material, `/zanmai-snapshot` for a safety point before
   risky steps, `/zanmai-research` for sourced research. Plain
   language works too, the slash commands are shortcuts.

3. Ask me at any time what Zanmai can do or how something works,
   for example "show me everything I can do with Zanmai", "how is
   this structured", or "what can I file here". I answer from the
   built-in documentation, in context and in your language, so you never
   have to read documentation to use this.

What is actually on your mind right now? Tell me what you are trying to get
done, and I will walk you through how we would tackle it together.
```

## Shape: empty vault

No user-relevant items and nothing gathered yet: one short sentence in the user's writing language
saying the vault has not collected anything yet, plus a question about what they want to do. Stop
there. The user fills the void.

## Never in a greet

- **No id.** A work-object id like `53956b20` is Steve's own reference for `zanmai.py work`, never
  something the user reads.
- **No wikilink and no slug.** A bundle is its plain human label, nothing in `[[double brackets]]`,
  no kebab-case pathname. The click-target is not the greet's job.
- **No path.**
- **No system-internal housekeeping as an item.** Vault mechanics run silently. Anything the user
  genuinely has to know is handled before the greeting or named in one short line at the top.
- **No dash as sentence punctuation.** Finish the thought or split it into two sentences. The house
  style in `zanmai/system/operating-principles.md` applies to the reply itself, not only to what
  gets written into a file.
- **No re-reading, no rebuild, no dispatch.** Bundles are not opened one by one before naming an
  item, `zanmai.py memory briefing` is never run to rebuild the briefing fresh, and none of this
  goes to an Agent or Explore dispatch. All three turn a few-second greet into a vault-wide scan,
  for a staleness case a real run found zero times in fifteen checks. Where a named item turns out
  stale, that is a write-path defect, a checkbox that should have gone through `zanmai.py task
  done`, not something the greet re-derives at every start.

## Language

This file is canonical English. Translate the wording to the user's writing language at runtime, in
the personal form of address where that language has one.

## After the greet

When the user picks an item or asks about a topic's state, read the bundle truth file
(`<kind>/<bundle-slug>/<bundle-slug>.md`) or the work object **then**, not before. This is where a
stale checkbox actually gets caught, on the one item the user is asking about instead of on all of
them upfront. Report from it. Where it contradicts a checkbox in a day, name the discrepancy
plainly. The box itself stays as it is unless the user asks for it to be ticked, and then it goes
through `zanmai.py task done`.
