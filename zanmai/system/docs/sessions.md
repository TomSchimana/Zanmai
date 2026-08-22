[← Zanmai Documentation](index.md)

# A working session, start to close

What happens when you open a session, and why closing it properly matters.

## When a session starts

Before the first word reaches you, Zanmai reads its own state: your profile, your own contact entry, when the last session ended, and the current layout of your vault. It also compares the vault against its index and rebuilds it if anything changed, which is how edits you made directly in your editor are picked up rather than missed.

Out of that comes a short briefing: how to address you, what is currently open, what happened recently, and any hints worth surfacing. That briefing is for Zanmai, not a wall of text for you. What you see is a greeting naming what is actually open, or a direct answer if you started with a question.

The list in that greeting is not written freehand. It is assembled by the script from your dated tasks, the work objects, files whose name carries a date, and undated items from a journal entry or focus bundle touched in the last few days. What waits on you comes first, then whatever is nearest in time. It is grouped so you can see at a glance what falls today, what falls tomorrow and what is already past, and it is six lines at most: whatever does not fit becomes the last line as a count, for example "+ 5 more within the next 7 days, 15 older overdue". So a routine item due today can never be pushed out by a backlog that has been sitting there for two months, and one open thing is one line. A quiet vault gets no list at all.

If the vault has nothing in it yet, you get one sentence and a question instead of a made-up list.

## During the session

Work that belongs to a specialist is handed over with the context to do it well, and anything that touches more than one file is shown to you as a plan before it happens. The hand-over does not take the conversation with it: you are told in one line what is running, and you can keep going in the meantime, the result is brought back to you when it is finished.

When a specialist comes back with something you need to decide, a design round, reference frames to approve, a follow-up question, it stays available rather than being thrown away. Your answer continues that same piece of work with its context intact, instead of starting it over from a fresh brief. That is why a second round on a document is quick and does not lose what was already agreed.

## Closing it

End with `/zanmai-close-session`, or just say you are done for the day.

Closing writes a hand-off in four parts, and only those four: what was actually done, meaning things that exist now and did not before; what comes next; the intent behind it, so the reason survives; and any realignments, meaning what your corrections established, written as the rule that now holds rather than as a quote of what you said. Insights worth keeping beyond this session graduate into long-term memory, and the briefing for next time is rebuilt on the spot.

That is the difference between picking up tomorrow where you left off and re-explaining yourself.

One thing worth knowing about work that is still waiting on you. A specialist who needs your answer does not finish; it waits, holding everything it worked out, so your answer carries on the same run instead of starting a new one. That waiting ends when the session does. What survives is the note it keeps while it works: where the material is, what it decided, what is still open. So closing with something unsettled costs the run, not the work, and the next session picks up from that note rather than from nothing. Settling it before you close is still cheaper.

## Related

- [Memory](memory.md), what carries across sessions and where it lives
- [Snapshots](snapshots.md), the safety net before risky writes

---

[← Back to the documentation index](index.md)
