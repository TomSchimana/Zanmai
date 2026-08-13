# Zanmai

**Zanmai** (三昧) is Japanese for being completely absorbed in one thing. You never get there while
part of you is holding twenty others in place.

**A folder on your machine that AI can actually work in.** You throw things in, it files them. You
ask in your own words, it answers from your own material. It builds new things out of what is
already there.

Everything in it opens in any editor, with or without this. The AI is Claude, through
[Claude Code](https://claude.com/claude-code).

> **Developer preview, 0.3.0.** Filing, search and the journal are in daily use; design and image
> generation work but are still being sharpened. A new version can change how things behave, so keep
> your own backups and read the [changelog](zanmai/system/CHANGELOG.md) before you update.

## What it does, and where things land

The folders are named after what is going on rather than what stage a file is at, so the right one is
obvious and nothing has to move later. Everything about one matter stays together in it, whatever the
file type, because sorting by type would cut apart the very thing you were keeping.
[How the vault is organised](zanmai/system/docs/folder-architecture.md) ·
[why it is built this way](zanmai/system/docs/philosophy.md).

**What comes out**

- **[Documents in your own design](zanmai/system/docs/design.md)**: it measures the templates you already use and builds in that language. Print-ready PDF, or PowerPoint and Affinity to keep editing.
- **[Text written for its purpose](zanmai/system/docs/writing.md)**: minutes from a recording, a handover, copy for a page. It settles what the document is used for before the first sentence, asks if that is not findable, and gives you the points without a frame, a derivation or advice on how to run your own meeting.
- **[A finished cut](zanmai/system/docs/video.md)**: footage and your notes in, a video out, with captions and levelled sound. Delete a paragraph from the transcript and exactly that leaves the video.
- **[A summary of a video](zanmai/system/docs/research.md)**: it reads the picture as well, so what is only on a slide still lands in the text.
- **[Research you can check](zanmai/system/docs/research.md)**: real sources, cited only where it actually read them.
- **[Images](zanmai/system/docs/images.md)**: generated through Higgsfield or Magnific, or edited on your own machine for free.

**What it does with what you have**

- **[Anything you drop in gets filed](zanmai/system/docs/importing.md)**, in whatever state it arrives.
- **A photo of a business card becomes [a contact](zanmai/system/docs/contacts.md)**, a booking confirmation a note with the real dates in it.
- **[Speak instead of typing](zanmai/system/docs/voice.md)**: turned into text on your own machine, nothing uploaded.
- **[Ask instead of remembering](zanmai/system/docs/finding.md)**: it searches everything, including inside files your editor cannot open.
- **[One matter stays in one folder](zanmai/system/docs/folder-architecture.md)**: note, PDF, photo and recording together.
- **[Your brand comes out of your own material](zanmai/system/docs/brand.md)**: colour, type and tone read off a logo and an old document, kept in one file, so a document, an image and a video look like the same company.
- **[Specialists](zanmai/system/docs/specialists.md)** instead of one model for everything, each on a model you pick.
- **[It tells you what is waiting](zanmai/system/docs/sessions.md)** without being asked: what came in, what has sat on your desk for weeks.
- **[Nothing is ever deleted](zanmai/system/docs/snapshots.md)**, and you can pull a single file out of an earlier state of the vault.
- **[Reaches what is outside](zanmai/system/docs/connections.md)**: the sources you hooked up yourself.
- **[Updates](zanmai/system/docs/updates.md) never touch your own material.**

## Requirements

Three things, with a command for each. Homebrew comes from [brew.sh](https://brew.sh); `winget`
ships with Windows 10 and 11 already, or get it from the [Microsoft
Store](https://apps.microsoft.com/detail/9nblggh4nns1) if it is missing.

| what you need | macOS | Windows (PowerShell) |
| --- | --- | --- |
| **Python** 3.10 or newer | `brew install python` | `winget install Python.Python.3.12` |
| **Git** | `brew install git` | `winget install Git.Git` |
| **Claude Code** | `brew install --cask claude-code` | `winget install Anthropic.ClaudeCode` |

On Linux, install Python and git with your package manager and Claude Code with
`curl -fsSL https://claude.ai/install.sh | bash`, which also works on macOS. Without Homebrew or
winget, take Python from [python.org](https://www.python.org/downloads/), ticking "Add python.exe to
PATH" on Windows, and install Claude Code with `irm https://claude.ai/install.ps1 | iex` there.

Optional: **Node.js** for connected features such as image generation. Anything else a job needs,
Zanmai names and installs on your go. [Requirements and installation](zanmai/system/docs/install/index.md).

## Install

Clone it where your vault should live, then start a session in that folder. The archive works too,
and updates run either way.

```bash
git clone https://github.com/TomSchimana/Zanmai.git
cd Zanmai
claude
```

Say hello in your own language and setup starts. When it finishes, close the session and open a new
one: that is when the guards load.

From then on you ask instead of reading. "Show me everything I can do with Zanmai" is a good first
line. End the day with `/zanmai-close-session` so the next one picks up where you left off.

If the approval prompts get tiring, press `Shift+Tab` and pick auto mode. Zanmai's own guards keep
working, so [nothing gets less safe](zanmai/system/docs/troubleshooting.md).

## Documentation

You do not have to read any of it. The documentation ships inside Zanmai and asking is the intended
way in: "how do I import a folder", "what happens when I update". The answer comes from these same
pages, in your language and shaped to your vault. It also reads fine here on GitHub.

→ **[Zanmai Documentation](zanmai/system/docs/index.md)**

## Licence

None yet, so all rights are reserved and redistributing or building on it is not permitted at this
stage; what Zanmai itself builds on is named in [credits](zanmai/system/docs/credits.md).
