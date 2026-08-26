---
name: zanmai:voice
description: Turn spoken notes in `import/` into what they were meant to be. Triggers on `/zanmai-voice`, on the hook reporting recordings, or on "I recorded something".
---

# voice

Speaking is the cheapest way to get something into a vault, and the transcript is the expensive part. The words that carry the meaning are the names, and names are what speech recognition mangles. Putting them right is reading, not machinery: a garbled word resolves from the sense of the sentence the way a typo does, and most of the world's names are already known to whoever is reading. That is the default path, and for most notes it is the only one.

Two things are worth knowing about the rest.

**A word only the vault could know needs the vault.** A colleague's surname, a company spelled a particular way, a term nobody outside this vault uses. `zanmai.py voice lexicon` collects those and hands them to the recogniser as its initial prompt, which is the one thing that can recover a misheard name, because it is the only step that hears the audio again. It is reached for when reading does not get there, not run as a matter of course.

**Rewriting a transcript has a documented failure mode: over-correction.** A model asked to fix a transcript reliably invents names that were never spoken, because a plausible name is exactly what it is good at producing. Hence the two rules that bound the reading: knowing is allowed and guessing is not, and what stays unresolved stays as it was, marked.

**Who runs which leg.** A recording is a source to read, which is Reed's own ground (`reed-source-pipelines.md` covers voice memos), so Steve dispatches Reed in the background for steps 1 to 4: transcribe, correct against the vault, and say for each note what it appears to ask for. Reed returns that and stops there, because acting on an instruction is not research. Steps 5 and 6 are Steve's: routing each part to whoever owns it, filing through Hank where material is being filed, capturing through the `journal` skill where it is a journal entry, and the one question that is left. No new expert exists for this; every leg has an owner already, and a procedure whose owner is not named is a procedure nobody runs.

## The workflow

### 1. Take all of them, oldest first

`zanmai.py voice scan` lists what is waiting. Read them as a set, in the order they were recorded: several notes made in a row are usually one train of thought, and the third one often corrects the first. Deciding they are separate items is a judgement, and it is made after reading, not before.

**The order comes from the file date, the file name only as a fallback**, and the scan says which it used for each one. The date is when the recording was made, written by the recorder against the local clock; when a note arrives is not something the speaker decides, since one spoken in a dead spot or at the gym syncs whenever it syncs. Where a file carries no usable date, a timestamp or running number in its name stands in. The scan also compares the two and says so when they disagree: that means one of them was rewritten on the way, and the sequence is then read out of the notes themselves rather than assumed. Say that in the return as well, rather than presenting a sequence as if it were certain.

Open a work object for the run (`zanmai.py work open --title "voice notes <date>" --owner steve`), because this is exactly the shape of work that outlives the turn: something arrives, some of it can be settled and some of it needs the user (operating-principles §13).

### 2. Check the prerequisites, and stop rather than improvise

Transcription needs `ffmpeg`, `whisper-cli` and a model file. `zanmai.py voice transcribe` reports precisely which of the three is missing and does not guess. The model is a one-time fetch of about 1.6 GB, so it is asked for once, with the reason: without it a recording cannot be read at all on this machine. Nothing about a voice note is sent anywhere; it is transcribed locally, because a spoken journal entry is the most private material the vault holds.

### 3. Transcribe

```
zanmai.py voice transcribe --file import/<name>
```

The language is detected, not assumed, and the transcript stays in the language it was spoken in. A note that switches language mid-sentence is transcribed as spoken.

### 4. Read it and put it right

Most of the work is here, and it is reading rather than machinery. A garbled word resolves from the sense of the sentence, the way a typo does: given that the note is about an island, a mangled town name is that town; given a colleague called Pat, "pad" is Pat. Nothing needs to be consulted for that.

**First, what is this note about?** One line. It is what makes a wrong word visible as a wrong word.

**Where the subject itself is not recognisable, one look at the web.** Something hyped for two weeks is newer than what you know, and a name you have never met reads exactly like a mangled word. One lookup, because once the subject is clear most of the vocabulary around it falls into place at once.

**Then fix what you can see is wrong**, and settle how each name is written. For a name the vault holds, the file that owns it is the authority, in full: case, hyphens, spacing. A recogniser applies its own capitalisation and cannot be talked out of it, so this part is never the recogniser's to decide.

**Where you are stuck on a name, then reach for the vault's list and run it again.** Not before: most notes never need it.

```
zanmai.py voice lexicon --out zanmai/temp/voice/lexicon.txt
zanmai.py voice transcribe --file <same file> --lexicon zanmai/temp/voice/lexicon.txt
```

This is the only step that can hear the audio again, which is why it is the one that can actually recover a misheard surname, and it costs one cheap run. Measured both ways: on a note where full names were spoken it fixed all five of them; across ten minutes of a real meeting it changed almost nothing, because what people say in a room is first names and a recogniser knows those. Rarely decisive, worth having when nothing else gets there.

**And then stop.** What is still unresolved stays as the recogniser wrote it, marked as unresolved. Not corrected to the nearest plausible thing: that is over-correction, the documented failure of letting a model rewrite a transcript, and a plausible wrong name is worse than an obviously garbled one because the garbled one gets noticed. Every change goes into the run's log on the work object, from what to what and on whose authority, and stays out of the report: fixing a mangled word is the job, and a list of fixes reads as homework for the user. Only one correction is ever said out loud, the one that would change what a sentence means, and that one is a question before it is made.

### 5. Work out what each note is, then do it

Read all of them first, then decide, then file. What a note is comes from what it says and from the vault it landed in, not from a list of types: how the day went belongs in the periodic note as spoken, an instruction is carried out as if it had been typed, four sets of squats belong wherever this person's training already lives, an errand belongs where their errands are, and an idea belongs to the theme it is about. None of that is recognisable from the wording, all of it from the context, which is why there is no table here.

**The day it belongs to is the day it was spoken, not the day this step runs.** A recording read three days after it was made still speaks from that day: "heute war kein guter Tag" said on Monday and read on Thursday belongs in Monday's entry, not Thursday's. `zanmai.py voice journal-append --file <recording> --text "…"` writes it there directly, it derives the date from the recording itself (Step 1's dating) the same way `voice archive` already does for the audio file, so this is never worked out by hand and never defaults to today. Everything else the note becomes (an instruction, an idea, material to file) is unaffected, only the journal placement follows the recording's own date.

Two things follow. A note can hold more than one thing: split it and treat each part on its own merits rather than filing the whole under the loudest sentence. And a run of notes is usually one thing, not several, because a set is spoken one recording at a time; where an entry for it already exists, this goes into that one rather than beside it.

Say in the report where each part went and why. That sentence is what makes "move it to X" cheap, and it is the reason a decision taken without the user is safe to take.

### 6. Keep the recording, then report

`zanmai.py voice archive --file <name>` moves the audio out of the import folder into the day it was spoken on and keeps it. Out of the drop folder so it cannot be transcribed twice; kept because it is the user's own recording and a transcript is a reading of it, not a replacement.

The report is short and has three parts: how many notes and how long, what each turned out to be and where it went, and what is waiting on the user. Nothing else, and no list of corrected words: they are in the log for anyone who doubts a note later. If nothing needs the user, the report is the whole interaction.

## What runs automatically, and what does not

The session-start hook says how many recordings are waiting; it does not transcribe, because a hook that takes a minute is a session that starts in a minute. On the next turn Steve dispatches Reed in the background (`subagent_type: reed`, `run_in_background: true`) for the reading legs, so the user can carry on while it runs, and acts on what comes back.

**The prompt carries the two labelled blocks** (`brief`), headed exactly `What the user said:` and `What I concluded:`. `dispatch-guard` checks for the first heading literally and refuses the dispatch without it.

Everything up to the report happens without asking: transcribing, correcting, filing a journal entry, carrying out an instruction that was actually given. What waits is money nobody asked for, a missing tool or model to fetch, and a correction that changes what a sentence means.

**When nobody is at the keyboard.** The run can be started on a schedule, and then the invocation says so. Nothing about the reading changes; three things about the ending do. Open points go to `zanmai.py work ask` instead of a question, because a question asked into an empty room stops the run for a day. The run does not park (operating-principles §12): nobody is there to wake it. And it closes itself through the `close-session` skill, which writes the log with `session_type: unattended`, so the next real session is told in one line what happened and what is waiting. Decisions are taken rather than deferred, in the knowledge that the report makes them easy to undo.

## Sounds sensible, is wrong

| Sounds reasonable | Why it is wrong |
|---|---|
| "The vault does not have it, so it cannot be resolved." | Most of what a note names is not vault material at all. You know most of it, and the web has the rest. The vault is for what only this person could have. |
| "It is probably that town, I will write it." | Probably is guessing. Knowing is allowed, guessing is not; if you are unsure you are not sure, and it goes to a source. |
| "The subject is unfamiliar, so I will research it properly first." | A spoken note is not a research brief. Two lookups, one attempt each, then mark what is left and move on. Effort stays in proportion to a note somebody spoke in half a minute. |
| "While I am here I will write up what I found." | One line in the right theme, so the next note is free. A write-up is a different job and nobody asked for it. |
| "It is obviously an instruction, I will just do it." | Obvious in the transcript, and the transcript may be wrong. Unambiguous means unambiguous after step 4. |
| "Nobody is there, so I will leave the decision for later." | Later is tomorrow at best. Decide, file, and say where it went. |
| "No model, so I will use an online service." | A voice note is private material. Missing tools are a stop, not a detour (operating-principles §10). |

## Stop and look again

- About to file a note under a name that is not in the vault and was not looked up.
- About to change a word without writing the change into the log.
- About to ask the user more than one question about one recording.
- About to delete a recording rather than keep it.
- About to transcribe again a file that already sits in a journal day.

## Files

- `zanmai.py voice scan | lexicon | transcribe | archive | journal-append`
- `zanmai.py work open | log | ask | done`, the run's own object
- `zanmai/system/skills/journal/SKILL.md`, where a spoken journal entry goes
- `zanmai/system/tool-register.json`, entries `ffmpeg`, `whisper`, `whisper-model`
