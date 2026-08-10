[← Zanmai Documentation](index.md)

# Tools Zanmai uses

What outside programs Zanmai relies on, and how they get onto your computer.

## Two kinds

One thing has to be there before Zanmai can start: Python, since Zanmai runs on it. If it is missing, Zanmai tells you plainly and points you to the [installation guide](install/index.md). It never installs it silently.

Your notes are plain Markdown, so they open in any editor and you need nothing special to read or write them. The folder names, the journal and the trash are Zanmai's own, so they work the same whichever editor you use.

Everything else, a feature needs only when you use it: small helper libraries for images, tools for video, and so on. Zanmai fetches those itself the first time, keeps them in its own corner of the vault so your system stays untouched, and asks first when something bigger is involved.

## Good to know

Zanmai never assumes a tool is present. It checks, on your computer, what is really there. The same program can even have a different name on macOS, Windows, or Linux, so it looks properly and works with what it finds, or helps you get the rest.

## Three kinds of dependency

- **Prerequisites** you bring: Python, git, and Claude Code itself. Named plainly if missing, never installed silently.
- **Fetched on demand** by Zanmai when a job needs it: small Python libraries for images and signing, media tools for video work. Python libraries go into Zanmai's own environment inside the vault, so your system Python stays untouched.
- **Recommended, never required**: a package manager makes installing easier, but the on-demand path works without one.

## Everything at once, offered at setup

At the end of setup you are asked once whether the tools Zanmai can fetch itself should be fetched now. You see how many are already there and what the rest are for, and you say yes or later. Whatever needs you, a package manager command, an account, money, is listed separately with the one command that does it, and is never installed behind your back.

This exists so a missing tool is not met for the first time in the middle of a job that is already running. You can ask for the same overview at any point later; the answer is the same list, minus whatever has arrived since.

## Before a job starts

When a task needs one of those on-demand tools, Zanmai checks the prerequisites are in place before it begins, not halfway through. If something is missing it tells you what, why it is needed for this particular job, and the simplest way to get it. So a job never stalls partway for a tool it could have named at the start. To keep this quick, it remembers what it already found on your machine and only looks again when something changed.

---

[← Back to the documentation index](index.md)
