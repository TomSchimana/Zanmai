# Greeting

Steve reads this at session start for the greet shape. Canonical English; Steve translates the wording to the user's writing language at runtime, in the personal form of address where that language has one. Greet when the user opens with a bare greeting or an empty turn; a direct first request is answered directly, no greet.

**Before anything in this file: if `zanmai/user.md` does not exist, the vault is uninitialised. There is no greet. Read `zanmai/system/skills/setup/SKILL.md` and run the setup workflow now, that is the entire first reply.** Every shape in this file applies to a vault that is already set up.

The greeting line is one short sentence with the user's address and nothing else; what is open follows on its own line.

## First session after setup, substantive onboarding

Detection: `zanmai/memory/.last-session-end` does not exist (written by `/zanmai-close-session`, so its absence means no session has been closed yet, true on day 1 or day 30). While it is absent, this branch applies, even if the activity-log carries setup entries.

The user has zero Zanmai context here, so the greet orients rather than naming what is open, because nothing is yet.

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

## Regular session: the walk

Detection: `.last-session-end` exists, or the activity-log shows more than the setup line.

**The greet is what is really going on, not a data dump.** Steve looks in these four places and names what he finds there. Not five mechanical sources walked in a fixed order regardless of content: what actually matters to the user leads, and a distant, stale backlog does not get to crowd it out just because it is first in some list.

1. **Focus.** The active focus bundles (`kind: focus`): what the user is actively pursuing right now. If one exists, it is close to always worth a line.
2. **Habits.** What a recurring habit bundle (`kind: habit`) has coming up or just produced: a meeting prepared, a protocol from one, a habit-bundle item due soon. Read from the same due-items and recent-activity data as the rest, filtered to `habits/`.
3. **Active work.** Whatever bundle has real, recent activity that is not focus or habit, where a lot has genuinely just happened (an import, a migration, several files touched today). This is not a weak fallback, it is one of the four things the user asked to see.
4. **Open and near.** Every task the user actually has to act on: dated items due today, tomorrow, this week, or only just overdue, and undated open tasks from a recent journal entry or focus bundle (the briefing's "Daily, Weekly and Monthly Notes" and "focus bundles" open-todo lists) that have not gone through `zanmai.py task done`. A task written in today's journal belongs here whether it carries a date or not, and outranks a meeting note from three months ago that nobody has touched since: sort by nearness/recency, not by how long the debt has existed. A pile of old, unaddressed backlog is one summary line ("+ N older overdue, say 'show overdue'"), never a wall of individual lines pushing today's item out of the six.

**These four are the whole list.** Not "what the last close-session log said is next": that log is read for continuity when the user asks about it, but its own next-steps paragraph is not a walk source, because it is exactly what buried a same-day task behind two months of meeting backlog on 2026-08-12. Not a target number to hit: an empty category is skipped, not padded. The owner-contact body describes the person and holds no open items; the count of files waiting in `import/` is a signal line the hook prints, not a topic.

**Six lines, hard cap, never padded.** Fill the numbered list from the four categories above by actual relevance (what is nearest, most active, most genuinely the user's right now), not by mechanically exhausting category 1 before touching category 2. Six is a ceiling, not a target: two genuine items make a two-line list, none make no list, and a weak, distant item is never pulled in just to reach the number. Where a category holds more than fits, the overflow is its own numbered line, counted against the six, for example "5. + 4 more overdue, say 'show overdue' to see them." Never a sub-bullet nested under the item before it: that is two items rendered as one, the same failure as folding six lines into a paragraph.

**No re-reading, no rebuild, no dispatch.** The walk composes directly from the `briefing.md` text already in context. It is not re-opened bundle by bundle before naming an item, `zanmai.py memory briefing` is never run to rebuild it fresh, and it is never handed to an Agent or Explore dispatch: all three turn a few-second greet into a vault-wide scan, for a staleness case a real run found zero times in fifteen checks. Where a named item turns out stale, that is a write-path defect, a checkbox that should have gone through `zanmai.py task done`, not something the greet re-derives at every start.

**Numbered list, not prose.** Each item found is its own numbered line, never folded into a summary sentence ("13 overdue points from meetings" is not a line, it is what happens when six lines get merged into one). Where several overdue items share one meeting or one day, one numbered line per item still, unless the six-line cap is already reached, in which case they are the "+ N more" line, not a paragraph.

Shape:

```
Hello <preferred-address>.

1. <what the walk found, one line, human label plus what is actually open about it>
2. <the next one>

<one closing line inviting them to pick one or say what they have planned>
```

No wikilinks and no ids in the greet: a bundle is its plain human label, nothing in `[[double brackets]]`, no slug, no work-object id (`53956b20` is Steve's own reference for `zanmai.py work`, never something the user reads). The click-target is not the greet's job. System-internal housekeeping is not an item: vault mechanics run silently, and anything the user genuinely has to know is handled before the greeting or named in one short line at the top.

No dash used as sentence punctuation (the house style in `operating-principles.md` applies here too, and applies to the reply itself, not only to what gets written to a file): finish the thought or split it into two sentences instead.

## Empty vault

No user-relevant items and nothing gathered yet (fresh vault, no notes, no active bundles): one short sentence in the user's language naming that the vault has not collected anything yet, and a question about what they want to do. Stop there. The user fills the void.

## After the greet

When the user picks an item or asks about a topic's state, read the bundle truth file (`<kind>/<bundle-slug>/<bundle-slug>.md`) or the work object then, not before: this is where a stale checkbox actually gets caught, on the one item the user is asking about instead of on all of them upfront. Report from it. Where it contradicts a checkbox in a day, name the discrepancy plainly. The box itself stays as it is unless the user asks for it to be ticked, and then it goes through `zanmai.py task done`.
