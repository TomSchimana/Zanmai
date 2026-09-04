[← Zanmai Documentation](index.md)

# What runs automatically

**Read this when:** a guard fired, or the question is what runs automatically.

A handful of checks run on their own, before something is written or a job is sent off. Most of them you will never see. Two kinds exist: some refuse outright, the rest show you what they found and wait for your yes.

## What refuses, and why those

A refusal is right in exactly one case: where no later yes repairs the damage.

- **`permission-guard`** stops a write into Zanmai's own files, into the archive, or into the trash. Each of those has a command that does the job properly and reversibly.
- **`delete-guard`** stops any command that would remove or empty a file, and a hand-rolled move out of `inbox/` that skips the check that its content ever arrived in the space. Nothing in Zanmai deletes; things go to the trash and come back.
- **`outward-guard`** stops a write that leaves your space, a wiki page, a mail, a commit, and hands it to you as a decision. Inside your space an undo reaches everything. Outside it, other people have already seen it.
- **`kind-required`** refuses a note that is missing the fields every note carries. That is mechanically broken rather than a judgement call, and nobody can usefully be asked about it.
- **`park-guard`** stops a background job from settling into a wait loop. Such a run reaches nobody until it returns, so a question it stops on is a question nobody has been shown, and it would wait until it is killed. The question goes where you will find it instead.
- **`dispatch-guard`** turns away a job sent to a specialist without a proper handover, and puts a long-running one into the background so the conversation stays yours meanwhile. A specialist works with what it is handed and has nobody to ask, so a thin handover comes back as invented work.

## What asks

These catch a move that is usually wrong and now and then exactly right, and only you know which it is this time. Each shows what it found and waits.

- **`checkbox-guard`** asks about a task line appearing inside an ordinary edit. Ask for something to go on your list and it goes there; what this stops is a task arriving as a side effect, which is how reminders that were never yours used to end up on your list.
- **`prose-guard`** asks about a dash used as punctuation, a generic marketing phrase, or a leftover placeholder in text Zanmai wrote itself. Your own writing is never touched.
- **`library-check-guard`** asks before a finished deck is saved when your own existing slides were never looked at. Composing from scratch is sometimes right; not looking first is not.

## What runs quietly

- **`session-start`** prepares what the first reply needs: how to address you, what is open, what came in, and whether anything of Zanmai's own is out of step. It also keeps the search index current, so edits you made in your editor are found.
- **`session-end`** notices a session that ends without a proper close, so the next one can offer to write the missing hand-off.
- **`index-consistency`** points out a file written into a bundle without its line in that bundle's index.

## If one fires and you disagree

The move is to fix what it named, not to work around it. Every one of them names what to do instead, and each writes one line into the activity log, so what fired reaches the next session's briefing whichever way you answered.

A check this version does not have says nothing at all. That matters at one moment, a version change: a configuration naming a check the installed program lacks would otherwise refuse every command, including the one that finishes the change.

## Why these are mechanics rather than good intentions

Each of these was a written rule first, and each of them broke. A rule that has to be repeated is not a stronger rule, it is the same rule with more words. What has to hold reliably becomes a check or it stops being claimed.

## Related

- [When something does not work](troubleshooting.md), what to do when one of these stops you
- [Snapshots and going back](snapshots.md), the safety net behind the risky operations

---

[← Back to the documentation index](index.md)
