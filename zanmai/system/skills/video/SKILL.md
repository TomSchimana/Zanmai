---
name: video
description: Luis's method for turning footage into a finished cut: transcription with word timing, the rough cut decided by reading, hiding the seams a cut leaves, captions in two classes, sound, reframing to another format, and one file per purpose at the end. The judgment layer; the mechanics are `zanmai.py video`.
---

# video

The job is the shortest cut that still delivers the point, and every stage below can run alone. Run only the ones the job asked for.

## First: what is this video for

Before any stage runs, one question is settled with the user, and it is not a formality: **what is this video supposed to do, and for whom.** The answer decides how much treatment the piece gets, and the honest answer is usually "less than the tool can do".

Three levels, and most work lands in the first:

- **A plain cut.** Trim, tighten, level the sound, done. No captions unless asked, no graphics, no generated material. A recorded walkthrough, an internal explanation, a customer message: these are finished at this level, and anything added makes them worse.
- **A cut with reading support.** Captions, a logo, chapter marks. For anything watched without sound or scrubbed through.
- **A produced piece.** Graphics, generated material, music, effects. For something that competes for attention, and only there.

**Restraint is the default, not a setting.** Every insert has to earn its place by helping the viewer understand something, and the burden of proof lies on adding, never on leaving out. Material and animation that exist to show what the tool can do are the failure mode of AI editing, plainly visible in the genre, and they cost the viewer attention while giving nothing back. A quiet cut with a face and a clear sentence beats a busy one.

Where the brief is silent, ask once, in a line, and propose the lower level. Where the user asked for one thing ("captions on this clip"), that is the whole job: do it and stop.

## Second: propose before you build

Transcription is cheap and it is the only thing that runs before the user has agreed to anything. From the transcript, write a proposal in plain prose, not a form:

- how long the piece is, what kind of piece it is, and how it reads
- **how tight the cut should be**, proposed as a number and not as a default: how much silence
  counts as a pause worth removing, roughly how many cuts that makes per minute, and whether the
  seams get covered. A calm explanation wants long pauses left standing and reads as chopped at
  fifteen cuts a minute; a clip for social wants the opposite. This is a decision about the piece,
  and it is settled here rather than discovered in the render.
- what treatment you recommend at which level, and what you would deliberately leave untouched
- every place you would add something: where, what kind, and why that one belongs there
- for anything that would be generated, a description of the shot before it exists
- what it will cost in time, and in money where a paid render is involved

Then wait. A video is an expensive document and a weak one wastes everyone who watches it, so the ten minutes of agreement here are worth more than any later correction. Nobody should meet a decision for the first time in a finished render.

## The order, and why it is this order

Transcribe, decide the cut, cut, hide the seams, set the format, then captions and graphics, then sound, then export. Two of those placements are not arbitrary. **Format comes before captions and graphics**, because it decides safe areas, type size and how the frame is divided; a caption laid out for wide and then cropped to upright is a rebuild, not a tweak. **Sound comes after the picture is locked**, because music and effects are placed against final timings.

Where two formats are wanted, they share everything up to the cut and split at the format. The expensive part runs once.

## Transcription, once per source

`zanmai.py video transcribe` writes word timings beside the job and re-running reads that file. This is the slowest step and it runs exactly once per source, ever. Transcribe supporting footage too, not only the main take: people narrate their own intentions inside a screen recording ("this bit is for the pricing part"), and that direction exists nowhere else.

After the cut, the transcript is **remapped** onto the new timeline and written out again. Everything downstream reads the remapped file. Nothing re-transcribes.

## The rough cut, decided by reading

Read the transcript and write a cut sheet: an ordered list of what stays, each entry naming its source file, where it starts, where it ends, and what is said in it. That last column is why the file exists: the whole cut can be checked by reading it, with nothing playing.

Out by default: false starts and stutters, filler that carries no rhythm, tangents that do not serve the opening, throat-clearing, and everything before the hook lands. **How much silence goes with them is not a default, it is the number agreed in the proposal.** Around a second suits a spoken explanation; a few tenths belongs to fast-cut short form and turns a calm piece into something chopped. Where a line was recorded several times, the **last** take wins; it is the warmest and comparing them costs an hour.

Keep the cadence. Removing every single "like" and "so" leaves speech that reads correct and sounds like a machine.

**Validate the cut sheet before anything renders**: fields present, in before out, sorted, and no passage starting before the previous one ended, which would use the same moment twice and stutter at the join. A gap between passages is not a fault here, it is the material being dropped. (The rule about neighbouring entries either meeting exactly or staying a second apart belongs to graphics, where a gap exposes untreated picture. Applying it to a cut sheet reports every removed pause as an error, which is what happened the first time it was written.)

## Cutting, and the traps in it

- **Do not stream-copy at arbitrary points.** Copying the stream desynchronises picture and sound; re-encode each piece, hardware-accelerated where available.
- **Never encode audio per piece.** Carry it through the cut untouched and level the assembled track once, otherwise every join clicks.
- **Do not snap cuts to detected silence.** Word-level timing is the whole advantage; silence detection drags a deliberate boundary into the nearest pause.
- **Watch the tail of a retake.** Where a speaker talks over the end of their own previous attempt, the kept word gets clipped. Extend slightly into the stumble and fade that piece's audio out over its last fraction of a second, so the word rings out instead of being chopped.
- **A word span far longer than the word can be is a signal, not a fact.** A stumble and its retake sometimes merge into one span; measure that stretch before cutting inside it.
- **Check a line against the audio before dropping it.** One word heard wrong is enough to make a sentence that was fine read as nonsense.
- **Correcting a transcript is reading, and it has a documented failure mode.** The discipline is already written down in the `voice` skill and it holds here unchanged: a garbled word resolves from the sense of the sentence the way a typo does; knowing is allowed and guessing is not; what stays unresolved stays as it was, marked. A model asked to tidy a transcript reliably invents names that were never spoken, because a plausible name is exactly what it is good at producing. For a name the vault holds, the file that owns it decides how it is written. **One rule is specific to video**: the word count must not change, so only whole single words are ever swapped. Two words merged into one shifts every timing after it, and the cut drifts with them. `video correct` enforces that and reports the words the recogniser was least sure about, which is where the proper nouns sit.
- **Names come back wrong, and the fix belongs in a list rather than in a correction each time.** Compare every word of the transcript against an ordinary dictionary and look only at what is neither a normal word nor already known: that short list is where the product names, the people and the company sit. A name that recurs goes into a permanent list that biases every future transcription; a one-off goes into a list for this piece alone. **Only ever swap single whole words automatically.** A fix that turns two words into one changes the word count, and every timing after it belongs to the wrong word.
- **The last word of the piece is reported too late, by up to a second.** A recogniser reading a whole file counts the breath after the final word as part of it. Trusting that number leaves the recording visibly running after the speaker has finished. Transcribe the last few seconds again on their own and take the end from that, then add the tail.
- **Padding is not one number, it depends on where the cut falls.** Inside a sentence, where the passage ends on a comma, roughly a tenth of a second after and a little less before. At a sentence boundary, about twice that. At the very end of the piece, two thirds of a second, so the last word rings out. One value for all three produces either a clipped word or a video that seems to keep running.
- **A screen recording sometimes carries chapter data.** The reported length then comes out too long and the file ends on black. Read the metadata first and drop it while re-encoding.

## Hiding the seam

A removed pause leaves a visible jump. Cover it in this order: switch to the second camera where one exists; otherwise change the framing slightly at the cut; otherwise place material that belongs there anyway. Only where the jump actually shows, and never twice in a row with the same device, or the video zooms its way through the whole runtime.

## Editing through the text

`video text --write` hands the transcript over as plain paragraphs, without timings in the way; `--read` takes the edited file back and writes the cut sheet. A word-by-word comparison against the original says which spans disappear. Two consequences worth knowing: a **correction to the wording** changes the captions, not the cut, and a deletion that lands mid-sentence is not refused, it is cut and the seam is hidden. Reordering paragraphs is not supported.

## Format

Reframing loses picture: a quarter of the width going from wide to 4:3, roughly two thirds going to upright. Decide the crop **per scene**, never per frame (it shakes) and never blindly centred. Check each decision against what fell outside: a face, a caption, a logo, the thing the sentence is about. Where too much would be lost, keep the whole picture, place it smaller in the new frame and fill the rest with a blurred enlargement of itself.

Upright has bands top and bottom that belong to the platform's own controls; nothing that must be read goes there. Wide keeps a margin all round, and the closing seconds keep one side clear where end cards appear.

## Captions, two classes

**Short pieces** get the designed treatment: each word drawn, the current one inverted, the box in the brand's colours. At a minute or two this is a few hundred states and it renders.

**Long pieces** get a subtitle track, either kept separate or drawn in as one calm two-line band: two lines, calm, scaling to any length. Continuous word-by-word highlighting over twenty minutes exhausts the eye, and the file that carries a thousand separately drawn states does not render in reasonable time.

The line runs on purpose, not on minutes, and the user can override it. The two classes also group differently, and that matters more than it sounds: word-by-word captions stay under four words and break at **every** comma, because they are short by design; a subtitle track follows the broadcast convention of around forty characters and breaks at a comma only once the line has some length, because breaking at every one leaves fragments. `video caption --style karaoke|subtitle` carries both sets. Either way: never caption a file that is already captioned, and offer the separate subtitle file as well, because platforms prefer their own rendering and a burned-in line clutters a wide frame.

## Sound

Denoise first, then level, then bed, then effects, in that order, each working on what the previous produced.

Level to a target rather than by ear, and use the same target every time; two recordings in one piece must match. A music bed sits well below speech, with no ducking and no fade in, and a short fade at the tail. Effects are sparse, a handful in a whole piece, from real samples; a synthesised tone is instantly recognisable as not a sound effect, so where there is no sample the step is skipped rather than faked.

Music and effects are audio-only passes: copy the picture, never re-encode it. Write the plan out, so a later change to the picture re-applies the same placements instead of re-deciding them.

## Looking at a piece: one picture, not a folder of frames

`zanmai.py video timeline` draws the whole runtime as a single image: a filmstrip across the top,
the loudness underneath, the words along the bottom, with a time ruler. That one picture answers
where the scenes change, where it goes quiet, where somebody is talking and roughly about what.

Read it first, always. Pull an individual frame only where the strip raises a question, and name
the second it sits at. Twenty-four separate frames cost more than the edit they were meant to
inform; this costs one.

## Before anything reads a video frame by frame

A cut made at an arbitrary moment lands on the nearest key frame, not on the moment asked for, and
with normal encoding those sit seconds apart. Anything that steps through a piece frame by frame
therefore works on a copy encoded so that every frame is a key frame. The copy is several times
larger and that is the price; without it the picture appears to freeze while the sound continues,
and the cause is invisible in every measurement.

## What it costs, so nobody is surprised

Rough numbers from real runs, worth saying in the proposal rather than discovering afterwards.
Transcription runs at roughly thirty times real time, so an hour of recording is two minutes.
Cutting is fast, seconds per minute of output. Drawing captions into a piece re-encodes the whole
picture, so it costs about as long as the piece itself. Generated material is the only part that
costs money rather than time, and it is charged per second of output.

The shape of the result is worth stating too: a recorded talk of twenty-five minutes usually
becomes eleven or twelve once the pauses and the false starts are gone. Somebody expecting twenty
minutes of video out of twenty-five minutes of material is expecting the wrong thing.

## Export

By the end the folder holds the plain cut, the version with graphics, the version with captions and a couple of attempts, and a week later nobody can say which one went out. Export promotes the newest real render to one clearly named file per purpose: the master to keep, a smaller one for internal use, one shaped for the platform. **The master is never overwritten**; the others sit beside it with the purpose in the name.

What stays with the job so it can be reopened: the transcript, the cut sheet, the graphics source. What can be discarded: render scratch and cached intermediates, and only those, never source footage and never a finished file. Print what would go before anything goes.

## Mechanics

`zanmai.py video` carries every state change: `probe` (what a file measurably is), `transcribe` (words with start and end, once per source), `propose` (a first cut sheet with the silence gone), `cutsheet` (checks one, and says whether a word would be cut through), `cut`, `caption` (a subtitle file, and drawing them in), `reframe`, `mix`, `frames`, `check` (the measurable half of a review), `brand` (opening, closing, a logo held throughout), `chapters`, `thumbnail`, `text` (out for editing, and back as a cut), `sync` and `export`. Judgement lives here in the skill, the state changes live there. Never assemble a shell line by hand where a subcommand exists, and never build a command as one string: a bracket in a filename and a time-range condition in the same line destroy each other's quoting.
