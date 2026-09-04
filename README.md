# Zanmai

**Zanmai holds everything you would otherwise have to carry in your head, and an AI works with it
instead of just storing it.** What comes back is the thing you were actually after: an answer out of
your own things, a decision you can now make, a finished piece of work built from what you already
have.

It runs on your own computer, on ordinary files in ordinary folders, through
[Claude Code](https://claude.com/claude-code) (more AI tools to follow, local ones included).

## Install

You need Python 3.10 or newer, git, and Claude Code on the machine; the
[installation guide](zanmai/system/docs/install/index.md) has the one command per system for each.
Then clone Zanmai where your space should live and open a session in that folder. The downloaded
archive works too, and updates run either way.

```bash
git clone https://github.com/TomSchimana/Zanmai.git
cd Zanmai
claude
```

Say hello in your own language and setup starts: who you are, what the space is for, which areas to
begin with, and what to install for the things you want to do. When it finishes, close the session
and open a new one, which is when the guards load.

From then on you ask instead of reading. "Show me everything I can do with Zanmai" is a good first
line, and `/zanmai-close-session` at the end of the day is what lets the next one pick up where you
left off.

## What you can do with it

- **Throw things in and stop thinking about them.** A receipt, a rental contract, forty documents
  off an old laptop, a voice note from the car. You are told what each one was and where it went.
  [Importing and filing](zanmai/system/docs/importing.md)
- **Ask instead of remembering where you put it.** "Does the household insurance still run?" comes
  out of the matter itself, not out of twenty letters searched for the word "cancelled".
  [Finding things again](zanmai/system/docs/finding.md)
- **Speak instead of typing.** Transcribed on your own machine, nothing uploaded, your names spelled
  the way you write them. [Speaking instead of typing](zanmai/system/docs/voice.md)
- **Have a document written.** Minutes of a recorded conversation, a handover before you go on
  leave, written for the situation you will use it in rather than about a topic.
  [Documents written for you](zanmai/system/docs/writing.md)
- **Have it designed like the rest of your things.** Colour, type and tone read once out of a logo
  and a document you already have. [Designing documents](zanmai/system/docs/design.md) ·
  [your brand](zanmai/system/docs/brand.md)
- **Have something researched.** Real sources, cited only where they were read, with how sure each
  claim is and what was left out. [Research](zanmai/system/docs/research.md)
- **Turn footage into a finished cut.** Delete a sentence from the transcript and it leaves the
  video. [Editing video](zanmai/system/docs/video.md) ·
  [images and video](zanmai/system/docs/images.md)
- **Keep what has to be kept.** A date and a keeping reminder on every piece, so nothing needed
  disappears and nothing sits there for ever. [What you keep](zanmai/system/docs/archive.md)
- **Write down a day without filing it.** One entry per day, your words, unchanged, and nothing is
  ever taken back out. [The journal](zanmai/system/docs/daily-capture.md)
- **Get told what is waiting.** What falls due, what has sat on the desk untouched, what came in
  overnight. [A working session](zanmai/system/docs/sessions.md)

## Where your things live

Eight areas, and what decides which one is right is what happens to something next, not how
important it is. Importance changes without anyone noticing; what happens next you can answer
without judging yourself.

| | |
| --- | --- |
| `inbox` | it arrived and has not been sorted yet |
| `workbench` | you are working on it and it has an end |
| `life` | it is yours and matters now: the flat, the car, your health, your own role at work |
| `knowledge` | it would still be right for somebody else, so it can be looked up |
| `archive` | it is finished and kept, because you will take it out again |
| `journal` | it happened on a day |
| `contacts` | people and organisations, one note each |
| `zanmai` | the machine's own, and you never open it by hand |

Only the desk empties. Inside an area, everything you make is a bundle: one folder for one matter,
with the note, the PDF, the photo and the recording in it together. Any Markdown editor opens the
lot. [How the space is organised](zanmai/system/docs/folder-architecture.md) ·
[the idea behind it](zanmai/system/docs/philosophy.md) ·
[your editor](zanmai/system/docs/editors.md)

## Who does the work

You talk to one of them. He does the plain work himself and hands the rest to whoever owns it:
filing, keeping, writing, research, connections, brand, documents, images, video, and anything that
could lose something. Where a job fits none of them, a new one is built for it.
[Who does what](zanmai/system/docs/specialists.md) ·
[how Zanmai grows](zanmai/system/docs/growing.md)

## The name

三昧 (zanmai) is the Japanese word for being completely taken up by one thing, samadhi in Buddhism,
and in ordinary speech an ending hung on a word to say nothing but that. It only happens when the
other twenty things are not pulling at you, which is what the space is for.

## Documentation

You do not have to read any of it. The documentation ships inside Zanmai and asking is the intended
way in: "how do I import a folder", "what happens when I update". The answer comes from these same
pages, in your language and shaped to your space. It also reads fine here on GitHub.

→ **[Zanmai Documentation](zanmai/system/docs/index.md)**

## Licence

None yet, so all rights are reserved and redistributing or building on it is not permitted at this
stage; what Zanmai itself builds on is named in [credits](zanmai/system/docs/credits.md).
