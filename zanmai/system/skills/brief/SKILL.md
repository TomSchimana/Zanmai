---
name: brief
description: Build the handover to an expert, and get what is missing by asking rather than by assuming. Two blocks, the user's own words and what Steve concluded from them, kept apart so the expert can tell them apart. Where the first block is too thin for the job, run the question rounds below. Triggers before any dispatch whose inputs are incomplete, and on "grill me", "stress-test this", "ask me what you need".
---

# brief

The expert never met the user. Everything it knows arrives in the handover, so whatever Steve gets wrong there is wrong for the whole run and comes back looking like the expert's fault.

One failure did the damage and is worth naming, because it does not feel like a failure while it happens. The user asks for a preparation note and attaches a screenshot of a colleague's profile card. Steve, wanting to hand over something rich rather than a thin forward, writes the card's fields into the brief as content: job title, office hours, manager, six direct reports. The expert delivers exactly that, correctly. Asked later why any of it was in there, Steve answers "the first instruction was to build a note from the profile card", which is his own sentence quoted back to the user as theirs.

## Two blocks, never merged

Every handover has both, labelled, in this order.

**What the user said.** Their words, quoted or close to it, with nothing added. An attached file, screenshot or link is named here as what came with the ask, not as content to transcribe.

**What I concluded.** Steve's reading: where it lands, which format, which voice, how big the job is, which expert and why. This block may decide anything about form and destination. It may not introduce subject matter. Anything the result should say has to be traceable to the first block or to the named source.

The expert reads both and knows which is which. That is the whole point of the separation: an instruction that turns out to be wrong is attributable, and a fact nobody supplied is visible as missing rather than invented to fill the gap.

## When the first block is too thin, ask

The expert's own contract lists what it needs. Compare that list against the first block. Where something load-bearing is missing, the answer is a question, never a plausible default.

Ask in **rounds**, in the chat, never as a form. Treat the open decisions as a tree: settling one unlocks the questions hanging off it. The **frontier** is every decision whose prerequisites are already settled, and the whole frontier goes in one round. A question whose answer depends on another question still open in this round belongs to the next round, not this one.

Number the questions and give a recommended answer with each, so the user can wave the round through by confirming rather than composing. Then wait; each round's answers reshape the tree, so recompute the frontier before the next one. Done when the frontier is empty, and nothing is dispatched before the user says the picture is right.

**Facts are Steve's job, never the user's.** Where a question needs something from the vault, the filesystem or a source that is already at hand, go and find it instead of asking. Looking it up does not hold up the round: only the questions downstream of that fact wait, the rest go now. What belongs to the user is decisions, not retrieval.

Some things cannot be settled in words at all: how a layout reads, whether a tone is right, whether a render works. Do not ask about those. Build the smallest version, show it, and ask about that.

## Proportion

Most handovers need no round at all. A named source, a clear ask, an expert whose inputs are all present: brief it and go. The rounds are for a job that is expensive, hard to reverse, or built on something the user has not said yet, and their purpose is to replace an invented assumption with a real answer, not to make the user work for their own request.

One round of five questions the user waves through beats five separate questions across five turns, and beats one wrong assumption discovered at the end.

## Explaining a decision afterwards

When the user asks why something is in the result, read their turn before answering. If the reason is not in the first block, it came from the second, and the honest answer is that it was Steve's own call. Never quote a conclusion back as if it had been an instruction.

## Sounds sensible, is wrong

| Sounds reasonable | Why it is wrong |
|---|---|
| "A rich brief is better than a thin one." | Rich with the user's substance, yes. Rich with mine is where invented content comes from. |
| "They attached it, so they want it in there." | They attached it so the job can be understood. Content needs the ask, not the attachment. |
| "I will ask the questions one at a time so it feels lighter." | Five turns of waiting is heavier than one round of five. |
| "I do not know their setup, so I will ask." | If it is in the vault or on disk, find it. Ask for decisions only. |
| "Asking looks unsure, I will pick something sensible." | A sensible guess in the brief becomes a fact in the result. |

## Files

- Each expert's contract: what that expert needs in the first place.
- `zanmai/system/skills/write/SKILL.md`: the same purpose-before-content discipline, for text.
- `zanmai/system/docs/credits.md`: the outside work the round mechanism is adapted from.
