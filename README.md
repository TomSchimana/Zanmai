# Zanmai

**Your head is for thinking, not for keeping track.**

Zanmai (三昧) is the Japanese word for being completely taken up by one thing, samadhi in Buddhism. A brain kept busy remembering never gets there. So the AI does the remembering: everything you would otherwise hold in your head lives in local files on your own machine, and one thing can have all of you.

Keeping the files is the easy half. You write something down yourself, or hand it over and let the AI file it, in plain Markdown that any editor opens. The other half is what a brain is really for, and that is where the help counts: making something out of it. A question researched across sources. A decision thought through. A document or an image built from material you already gathered. [Why it is built this way](.zanmai/system/docs/philosophy.md).

It is for people whose material arrives from all directions and who regularly have to hand something over. The AI is Claude, through [Claude Code](https://claude.com/claude-code), and your notes stay readable without either of them.

> **Developer preview, 0.3.5.** Parts are still being reworked and a new version can change how things behave. Keep your own backups.

## What it does

- **Captures** what you throw at it, in your words, into today's [note](.zanmai/system/docs/daily-capture.md).
- **Sorts a pile of mixed material** into themes, and shows you the plan before it moves anything. [Importing](.zanmai/system/docs/importing.md).
- **Answers from your own notes** rather than from the internet.
- **Keeps its own overviews.** Every theme gets an index note and the vault a master index, kept current as material lands instead of when you remember to.
- **Researches a question** across sources and files a [write-up with citations](.zanmai/system/docs/research.md).
- **Watches a video**, not only its transcript. A diagram on a slide or code on screen lands in the summary too, because it looked at the frames.
- **Designs documents**, flyers, decks and one-pagers in your own [visual language](.zanmai/system/docs/design.md), measured out of your existing templates. Out comes a print-ready PDF, or a native Affinity or PowerPoint file when you want to keep editing.
- **Generates images and short video** through [services you connected](.zanmai/system/docs/images.md), edits images you already have without spending anything, and marks the results where the law asks for it.
- **Reads sources outside the vault** that you [connected](.zanmai/system/docs/connections.md) yourself.
- **Builds a capability it lacks**, [shaped to fit](.zanmai/system/docs/skills-and-scripts.md) the rest.
- **Works in whatever editor you like**, Obsidian included. We recommend [ZenNotes](https://github.com/ZenNotes/zennotes), leaner and faster, and the one Zanmai [works with most closely](.zanmai/system/docs/editors.md).

## Requirements

Three things, with a command for each.

| | macOS | Windows (PowerShell) |
| --- | --- | --- |
| **Python** 3.10 or newer | `brew install python` | `winget install Python.Python.3.12` |
| **Git** | `brew install git` | `winget install Git.Git` |
| **Claude Code** | `brew install --cask claude-code` | `winget install Anthropic.ClaudeCode` |

On Linux, install Python and git with your package manager and Claude Code with `curl -fsSL https://claude.ai/install.sh | bash`, which also works on macOS. Without Homebrew or winget, take Python from [python.org](https://www.python.org/downloads/), ticking "Add python.exe to PATH" on Windows, and install Claude Code with `irm https://claude.ai/install.ps1 | iex` there.

Optional: **ZenNotes** for the inbox, the periodic notes and fast search, and **Node.js** for connected features such as image generation. Anything else a job needs, Zanmai names and installs on your go. Detail in [requirements and installation](.zanmai/system/docs/install/index.md).

## Install Zanmai

Clone it where your vault should live, then start a session in that folder. Downloading the archive works too, updates run either way.

```bash
git clone https://github.com/TomSchimana/Zanmai.git
cd Zanmai
claude
```

Say hello in your own language and setup starts, asking your name, how you want to be addressed and whether you use ZenNotes. When it finishes, close the session and open a new one. That is when the guards load.

Using ZenNotes? Open it once beforehand and switch on the daily, weekly or monthly notes you want to keep. Zanmai follows those settings, and [does a few more things](.zanmai/system/docs/editors.md) with the app.

From then on you ask instead of reading. "Show me everything I can do with Zanmai" is a good first line.

If the approval prompts get tiring, press `Shift+Tab` and pick auto mode. Zanmai's own guards keep working, so [nothing gets less safe](.zanmai/system/docs/troubleshooting.md).

End the day with `/zanmai:close-session`, so the next session picks up where you left off.

## Where things go

Those three modes are the only folders you deal with. **Knowledge** takes anything you want to keep, with as little deciding as possible. **Habits** is what repeats, sport once it is running, the weekly review. **Focus** is what occupies you at the moment, sometimes a real project, usually not.

Anything unclear goes to knowledge. Related things gather into themes so you can see a shape when you look, and links run across all of it, so an invoice is not a lonely file but hangs off the insurance it belongs to, which hangs off the company.

All of that lives in your inbox. Material on its way in or out stays outside it, so your view holds only what you keep. Zanmai's own files sit in a hidden folder you never need to open.

## How it works

**You see it coming.** Before fifty files get sorted into themes, you get the list of what lands where and say go. Before anything risky, a copy of the vault is put aside.

**A program touches your files, not the model.** Creating, moving, renaming and indexing all run through the tool that ships with Zanmai. That is why the same job twice gives the same result twice.

**One place per fact.** Your customer's address lives in their contact entry, and the notes that need it link there. When it changes, you change it once.

**Each specialist has its own standard.** Research may not cite anything it has not actually read. Design looks at the rendered page before handing it over. Filing never rewrites a word you wrote.

**It learns your corrections.** Tell it once that invoices belong with your receipts and it stays that way, without you repeating it every session.

**You can walk away.** Delete Zanmai and you still have readable text files in folders whose names make sense.

## Staying up to date

Ask Zanmai to update, or wait until it offers. You see what would change, it snapshots, then it applies. Your notes and settings are never part of it.

Cloned or unpacked makes no difference, and your own `git pull` works too. Detail in [updating](.zanmai/system/docs/updates.md).

## Documentation

You do not have to read any of this. The documentation ships inside Zanmai, and asking is the intended way in: "how do I import a folder", "what happens when I update", "show me everything I can do". The answer comes from these same pages, in your language and shaped to your vault. It is also plain Markdown, so you can read it here on GitHub if you prefer.

→ **[Zanmai Documentation](.zanmai/system/docs/index.md)**

## Status

Early. Capture, filing, search, contacts and updates are in daily use. Design, image and video generation work but are still being sharpened. Windows is tested for setup and the core, while the heavier media paths are still being hardened there. Read the [changelog](.zanmai/system/CHANGELOG.md) before you update.

## Credits and licence

The projects, standards and tools Zanmai builds on, and the licences that apply to them, are named in [credits](.zanmai/system/docs/credits.md).

Zanmai itself carries no licence yet, so all rights are reserved. Redistributing it or building on it is not permitted at this stage.
