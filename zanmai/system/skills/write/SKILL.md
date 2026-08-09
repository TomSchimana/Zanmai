---
name: write
description: Write a document for the user, anything longer than a line that is not a filing operation, a design piece or a research report. Meeting summaries, notes from a recording, an overview of material already in the vault, a handover, a letter. Sets the four things a document needs before the first sentence exists, and proposes them in one line instead of asking. Triggers on `/zanmai-write`, and on any ask whose answer is a document; every expert who writes pulls it, Hank, Reed, Carol and Steve.
model: opus
---

# write

A model asked to write with no further instruction does not write nothing. It writes the average of everything it has seen under that word, and for a word like "summary" that average is journalism: a narrative arc, named people cast against each other, a strongest quote, a turning point. Nobody asked for that and it reads as an accusation when the people in it work at the same company as the reader.

The fix is not a warning. It is that four things are settled before the first sentence, and that the user sees them in one line and can stop it there.

## The four, before anything is written

| | The question | What goes wrong without it |
|---|---|---|
| Source | What is the one valid source, and what is out of scope? | Training knowledge leaks in as if it came from the material |
| Purpose and readers | What is this for, who reads it, who appears in it by name? | A document written for nobody, and people described who never agreed to be |
| Frame and bans | Length, form of address, what must not appear | Length, tone and invented facts all decided by the writer alone |
| Format | Where it lands and in what shape | The user rebuilds it by hand afterwards |

None of these is asked as a question. They are answered from the brief, from the material and from the vault, and whatever is left over goes into the proposal line below as a decision already taken.

## Look at a comparable document first

Before proposing anything, `zanmai.py index find` with the tokens of the job. If the vault already holds a document of the same kind, read it and take its structure and its voice. That is a better answer than any preference invented on the spot, and it is the difference between a house style and a fresh guess every time. The proposal then says "shaped like `<slug>`" rather than naming three attributes.

Only when nothing comparable exists is the shape derived from the material, and the proposal says so.

## Propose in one line, do not ask

The user is the one who says stop or go, not the one who fills in a form. So the last step before writing is a single line naming what will be written, followed by at most three bullets where a real choice was made. Not a menu, not a question, not a list of options with trade-offs.

> Handover for the people who were not there, grouped by topic, opinions only as quotes with the name behind them, no timestamps.

That is the whole gate. The user answers go, or changes one word in it. A proposal that takes longer to read than the decision it carries has failed at its job; if it runs past a sentence and three bullets, cut it rather than explain it.

With nobody in the chat the same line goes on the work object and the run proceeds, because a document is a file and rewriting it later costs a sentence.

## Documents in which other people appear

The sharp case, and the reason this skill sets a model. A text that names colleagues, is read by those colleagues, and describes what they said is not a style question: an assessment of a person is a statement about that person, and it stays in the vault and in whatever system it is published to.

Four constructions carry the damage, and they are recognisable by shape rather than by adjective:

- **Verbs that judge the speaking.** Someone said, described, asked, proposed. They did not counter, insist, admit, concede, relativise, stress or hold their ground. The neutral verb is almost always the accurate one, because what was actually observed is that a sentence was spoken.
- **Rankings nobody asked for.** The sharpest point, the most concrete proposal, the only real disagreement, the longest thread. These are the writer's opinion wearing the clothes of a fact.
- **Narrative about the conversation.** The real break in the discussion, the turning point, the thing everybody was circling. The reader wanted to know what was discussed, not how it felt to watch.
- **The document talking about itself.** "This note covers only this meeting", "it should be noted that". A document describes its subject, not its own existence.

Opinions are not the problem and they do not get filtered out. They get attributed: as a quote with the name behind it, or with the fact that it is one opinion stated plainly. That is how a strong sentence survives without the writer taking sides.

Timestamps per statement are never written unless the brief asked for them. A reference to a place in the source belongs at the section level, once, when the reader might want to look something up.

## Where this runs, and when it goes to Hank

The skill is the same wherever it is pulled, and so is the result. The only question is who runs it, and the answer is how long the user would sit and wait.

Swapping two words, replacing a name, rewriting a paragraph the user pointed at: done in the conversation. There is nothing to delegate and the round trip would cost more than the edit.

A document that takes minutes to write goes to Hank via the `Agent` tool with `run_in_background: true`, and the reason is not that Hank is better at it. It is that the conversation stays free while it runs and that a subagent starts on the material rather than on fifty turns of chat history. Say in one line what is running.

Reed writes its own research report and Carol writes the copy for its own piece; both pull this skill rather than handing text to someone else, because separating the words from the work that produced them costs more than it saves.

## Sounds sensible, is wrong

| Sounds reasonable | Why it is wrong |
|---|---|
| "It is obviously a summary, I know what that looks like." | That is exactly the average this skill exists to interrupt. Obvious is where the journalism comes from. |
| "I will write it and ask for feedback on the draft." | Then the user reads a whole document to discover a decision that fitted in one line. The gate is before, not after. |
| "I will ask what tone they want." | The user hired a writer, not a form. A proposal they can veto is worth more than a question they have to answer. |
| "The transcript really does say she disagreed." | The transcript says what she said. "Disagreed" is the reading, and the reading is the writer's, not the record's. |
| "I will note in the document that opinions are the speakers' own." | That is the document talking about itself. Attribute the opinion where it appears instead. |
| "Timestamps make it verifiable." | They make a summary into an evidence file. Nobody asked for one, and the source is already in the vault. |
| "It is only a short note, the four do not apply." | They cost one line. A short note that goes out wrong costs the afternoon. |

## Stop and look again

- About to write a document without a comparable one having been looked for.
- About to write a person's name next to a verb that characterises how they spoke.
- About to produce more than a sentence and three bullets as the proposal.
- About to publish into a system outside the vault before the user has seen the text.
- About to write a document longer than a page in the conversation instead of handing it to Hank.

## Files

- `zanmai.py index find`, the search for the comparable document
- `zanmai/system/experts/hank/hank.md`, who writes it when it runs long
- `zanmai/system/operating-principles.md` §7, the human-voice discipline every produced surface follows
