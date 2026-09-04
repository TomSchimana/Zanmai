[← Zanmai Documentation](index.md)

# Speaking instead of typing

**Read this when:** something was spoken instead of typed.

Record a voice note, drop it in `inbox/`, and it gets read. A thought on the way to the car, a journal entry at the end of the day, an instruction you would rather say than type. The folder is created for you the first time.

## How it goes

You do one thing: put the file there. Any format a phone produces works, m4a, aac, mp3, ogg, wav.

The next time you open Zanmai, the start-up says how many recordings are waiting and gets on with it in the background, so you can carry on working. When it is done you get a short report: how many notes, what each one turned out to be, and where it went. If something genuinely needs you, you get one question. If not, the report is the whole thing.

Several notes recorded in a row are read together and in order, because the third one is often correcting the first, and five recorded between sets at the gym are one training session rather than five entries. The order is the order you spoke them, taken from each recording's own date; when a file has no usable date, a timestamp or number in its name stands in, and if the two ever disagree Zanmai says so rather than presenting a sequence as certain. When a note arrives is not something you control, and a recording made with no signal syncs whenever it syncs.

**It can also run while you are away.** Started on a schedule, it reads whatever is waiting, decides where each note goes and files it, and closes the session itself. The next time you open Zanmai, the first line says what happened and what is still waiting on you. Nothing is left hanging on a question nobody was there to answer: it decides, and it tells you where each thing went, so moving one afterwards is a sentence. Only two things wait for you, money you did not ask to spend, and a correction that would change what you said.

## Why the transcript is right

The hard part of speech to text is never the ordinary words. It is the names, and the names are what the note is about. A general transcriber has never heard of the people you work with.

Reading it is what makes it right, and that is the normal path. A word that is nearly a name is that name, the way a typo resolves: the sentence says what it must be. Most names in the world are known anyway, the space supplies the ones only you have, and a subject too new for either is worth one quick look on the web. **How a name is written is settled here too**, because a recogniser applies its own capitalisation and cannot be talked out of it: a company always spelled in lower case comes back capitalised no matter what, and the space's own spelling wins.

**When a name will not come out, the space's own list of names goes to the recogniser and the recording is read again.** That is the one step that hears the audio a second time, which is why it is the one that can recover a name that was misheard rather than mistyped. It is a second attempt rather than the standard route, and it earns its cost only where full names were spoken: in a conversation between people who know each other, what gets said is first names, and a recogniser already knows those.

**Corrections are written down, not read out.** Putting a mangled word right is the job, and a list of every fix would only give you something to check. What each change was, and on what grounds, goes into the run's log, so you can look if a note ever seems off. The one correction you do hear about is the one that would change what you meant, and that comes as a question before anything is changed. "Vertrag" and "Vortrag" are one letter apart.

Filler and false starts stay in a journal entry. That is how people talk, and editing your own voice is not the job.

## Where a note ends up

Depending on what it turns out to be: a journal entry goes into the note for the day you spoke it, not the day it happens to be read, an instruction is carried out the way it would be if you had typed it, an idea goes to the bundle it belongs to, and something about work already running goes onto that work. One note can be more than one of these, and gets split.

**The recording itself is kept**, in the day you spoke it, beside whatever came out of it. It moves out of the import folder so it cannot be read twice, and it is not deleted: it is yours, a transcript is a reading of it, and keeping the original next to the reading is what makes a garbled word repairable years later.

## Letting it run while you are away

Zanmai does not set up a schedule for you; you decide when it should run, with whatever your computer already uses for that (`launchd` or `cron` on a Mac, Task Scheduler on Windows). What it needs to run is one line, from the space folder:

```
claude -p "/zanmai-voice nobody is at the keyboard, this is a scheduled run" --permission-mode dontAsk
```

`dontAsk` is what makes it honest: no question can be put to an empty room, so anything that would have been a question is written down for you instead. Zanmai reads what is waiting, files it, closes the session, and leaves the open points where you will see them next time.

## What it needs, once

Three things, and Zanmai tells you which are missing rather than guessing:

- **ffmpeg**, to turn what your phone recorded into what the recogniser reads.
- **whisper-cli**, the recogniser itself.
- **A model file**, about 1.6 GB, fetched once. Nothing transcribes without it.

Zanmai fetches the model itself when you say go. It lives in the machine-local part of the space, so it never travels in a backup.

**Nothing is uploaded.** A spoken journal entry is the most private thing in the space, so it is transcribed on this machine, with no account and no service. It also means it works on a train.

## Asking again

`/zanmai-voice` reads whatever is waiting right now. You do not need it for the normal case, which happens by itself, but it is there for when you dropped something mid-session.

## Related

- [The journal](daily-capture.md), where a spoken journal entry lands
- [Work that outlives one sitting](work.md), how a question about a note reaches you
- [Backup and synced folders](backup.md), why the model file stays out of the copy
