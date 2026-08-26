---
name: write
description: Write any document longer than a line that is not filing, design or research: notes, summary, overview, handover, letter, page copy. Triggers on `/zanmai-write`.
---

# write

Asked to write with no further instruction, a model writes the average of everything it has seen under that word. The four steps below replace that average with this job.

## The question this file cannot answer for you

Before every word, sentence, paragraph and formatting choice: what is this here to do? Answer that and most of what follows takes care of itself. Skip it, and no amount of rules will save the text.

This matters most where the rules look like they have already decided. Bold is not a habit to break, it is a tool: a term the reader will look for again earns it, and it earns nothing at the head of every paragraph, where it stops marking anything. Same for a bulleted list, which is right when the items are genuinely parallel and wrong when it chops up an argument that needed to flow. Same for plain prose, which is not the safe default; it is the wrong choice for six things of the same kind.

So the answer to a habit is never its opposite. Told that a bold lead-in is a tell, the reflex is to ban bold and write everything flat, and flat-everywhere is the same mistake facing the other way: a form applied without asking what it is for. Decide per element, and decide again inside a document where a section genuinely needs something different, as long as the reader is not made to learn two systems.

Underneath is one idea. Simplicity is not the absence of things. Stripping until nothing is left produces something dried out and lifeless, not something clear. It is saying exactly what the thing is for and what part it plays, and the leanness that follows is a result of having got that right, never the goal itself.

## 1. Settle what it is for

One sentence naming the situation the document gets used in, not its topic. "Notes read on a phone during a one-to-one on Thursday" decides the form. "Preparation for the meeting" decides nothing.

Work it out from the ask, the material and the vault. Where it is genuinely not there, ask, once, in the user's language. That is the one question worth interrupting for; a document written for a purpose nobody settled is thrown away whole rather than corrected.

## 2. Take the level from something that works

Find a document of the same kind with `zanmai.py index find` and read it. Where the piece carries a brand outward, its voice section (`trusted/brands/<brand>/design.md`) is the source and is binding. Otherwise the user's own template or earlier piece.

This step matters more than every rule in this file, and here is why. Writing well is a question of how much: how warm, how short, how direct, how much context. No list can carry an amount, and a rule pushed to its end always lands at the opposite failure, a telegram instead of a brochure. A document already in the vault is a measured amount. Copy the level, not the words.

Where nothing comparable exists, say so in the proposal and take the level from the purpose: how much does this reader, in this situation, actually need.

## 3. Write what this reader needs

Every line earns its place by what the named reader would miss if it were gone. Correct is not the test, needed is. What they already know stays out, however true it is. Material that came with the ask, a screenshot, a file, a link, tells you what the job is about; it is not a list of fields to transcribe.

Say what you have to say and stop. The target is not a polished text, it is the text a competent colleague in a hurry would have written: it repeats a word instead of hunting for a synonym, it has corners, and it ends when the subject ends.

Before writing, one line to the user naming what will be written, plus at most three bullets where a real choice was made. They answer go, or change a word. With nobody in the chat that line goes on the work object and the run proceeds.

Where the file's `source` will be `ai-generated` or `collaborative`, run `zanmai.py prose check --text <draft>` on the draft before the Write call and fix whatever it names. It is the same dash-as-punctuation scan the `prose-guard` hook runs on the write itself; running it on the draft first means the hook has nothing left to refuse.

## 4. Know what gives it away

Human editors catalogued these across thousands of machine-written texts. They are shapes rather than words, so they hold in any language. Read them as things to steer off, not as dials at zero.

The big one is the urge to be right: hedging, qualifying, citing sources for material the user handed over themselves. Write the finding and stand behind it. A reference is for a reader who will look it up.

Then the visible ones. A bullet or a numbered item that opens with bold words and a colon, which is the most recognisable machine habit there is. A closing summary of what stands directly above it. Claimed significance in place of content, a pivotal moment, a broader trend. A participle hung off a fact to fake analysis. The plain verb avoided, so nothing is anything any more but serves as, functions as, boasts. Framing by negation, not just X but Y. Everything in threes. A synonym where the same word belonged. Headings by template, outlook, challenges, recognition. Officialese, which every language keeps for forms and ministries: stacked nouns, the passive where somebody acted, a long word for a short one.

Two more that are not about wording. Altitude: a text can break no rule and still float, true in every sentence and useful in none, because it talks around the subject instead of naming the thing, the date, the number, the decision. And cutting: told a text is too long, a machine compresses everything instead of removing whole parts. Cut sections, not sentences. What stays keeps its normal shape.

## Who writes it, and what happens after

The user's word decides it. Failing that, whoever already has the material: substance from this conversation is written here, material sitting in unread files goes to Ben in the background via the `Agent` tool with `run_in_background: true`. Reed and Carol write their own text.

Nothing checks the document afterwards. A text judged by the same kind of thing that wrote it gets the same blind spots twice, and a green verdict on a bad document is worse than none, because it ends the matter. The reader is the check.

## Sounds sensible, is wrong

| Sounds reasonable | Why it is wrong |
|---|---|
| "The purpose is clear enough from the topic." | A topic is not a situation. Ask, it costs a line. |
| "They sent the screenshot, so they want what is in it." | They sent it so you know what this is about. |
| "They asked how to approach it, so I will advise throughout." | One question, one answer, one place. |
| "It is written the way we write internally." | There is no internal register, only right and wrong for the situation. |
| "I should cite that, to be safe." | Safe for whom? |
| "No comparable document, so I will pick a style." | Then take the level from the purpose and say so. A picked style is a guess with confidence. |

## Files

- `zanmai.py index find`, the search for the comparable document
- `zanmai/system/experts/ben/ben.md`, who writes it when the material has to be read first
- `zanmai/system/operating-principles.md` §7, how anything user-facing reads
