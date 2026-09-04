[← Zanmai Documentation](index.md)

# Setup

**Read this when:** a space is set up for the first time, or an update added questions it never answered.

Setup is one conversation the first time you open a fresh space. You say hello, and it asks what it needs to know, lays out the space with the areas you name, and settles what has to be on the machine for the things you want to do. It runs once.

## What it asks

**Who you are.** How you want to be addressed, your name, your language, and an email if you want one on file. The name matters because you are a contact in your own space like everybody else, and because everything after this is written to you rather than to a user.

**What the space is for.** Private life, work, one particular project, or all of it in one place. "Not sure yet" is a real answer. This is not a label for its own sake: it decides what the next question suggests.

**How it should be laid out.** You see the eight areas and one plain example of what lands where, then you name the broad areas you already have, and the projects or goals you are on. Each name becomes an empty bundle: something with an end goes to the desk, something that runs on goes to `life`. Nothing is created that you did not name.

**What it should be able to do.** A short table of what the specialists can do and which of those need a program on your machine. You say what you already know you will want, and exactly those are offered, by name and size, before anything is fetched. Skipping is free: a missing program is fetched at the moment a job first needs it.

That table is not the limit, and the last thing setup says is why: where something you need is not on it, say so and it gets built for your case.

## What happens after

Close the session and open a new one. That is when the guards take effect, and until then the space is running without them.

The last question is optional and easy to say no to: a double-clickable icon that opens this space, so getting in never means finding a folder and typing a command. You can ask for it any time later.

Three habits are worth the sentence they take:

- **Starting is just saying hello.** The space reads its own state and tells you what is waiting.
- **Ending is one command**, `/zanmai-close-session`, which writes the hand-off the next session starts from.
- **Things go into `inbox/`** in whatever state they arrive, rather than being filed by hand.

Everything else you learn when it comes up, by asking.

## What has to be there before it starts

One thing: Python 3.10 or newer. Zanmai looks for it before the first question, remembers which one it found, and stops with a plain instruction if there is none. Nothing has been written at that point, so you install it and start again.

No editor, no companion app, nothing else. [Requirements and installation](install/index.md) has the command per system.

## When a later version asks something new

Setup grows. A space set up months ago has answered fewer questions than one set up today, and there has to be a way to close that gap without reinstalling.

So a session opens with the missing questions and only those. What already stands in your profile and what already sits in your areas is read first, so nothing you have answered or built is asked about again, and the question does not come back afterwards, whether you answered it or said "not now".

## When it does not run

Setup refuses to run a second time on a space that is already set up. If you want to change your name or your language afterwards, that is an edit to your profile rather than another setup.

## Related

- [How the space is organised](folder-architecture.md), the areas you see during setup
- [Tools Zanmai uses](tools.md), what the last block offers to fetch
- [A working session](sessions.md), what the three habits above look like in practice

---

[← Back to the documentation index](index.md)
