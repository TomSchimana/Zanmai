---
name: setup
description: First-time Zanmai vault setup. Used when `.zanmai/user.md` does not exist, or when the user asks for an initial install or first run. Drives an interactive dialogue, then calls `.zanmai/system/scripts/zanmai.py setup init` to create folders and `.zanmai/user.md`.
---

# setup

First-time install. Steve runs this when the vault has no `.zanmai/user.md`. The skill is invoked by reading this file and following the workflow below, it is not a slash command.

## Directive

This skill drives the dialogue. The deterministic state changes (folder creation, `.zanmai/user.md` write) are done by `.zanmai/system/scripts/zanmai.py setup init`. Do not write `.zanmai/user.md` directly from the conversation. Use the script. The script is the single point of state change so future migrations can reason about what got written.

## When to use

- `.zanmai/user.md` is missing.
- The user asks for an initial install or first run in their writing language.
- An older install needs to migrate to a new schema version, in which case the workflow calls `zanmai.py setup update`, not `init`.

## When not to use

- `.zanmai/user.md` already exists and the schema is current. Refuse and tell the user.
- The user wants to add a single bundle. That is `import-bundle`, not setup.
- The user wants to rename folders. That is a manual operation, not in scope here.

## How to ask the user

Three modes:

- Structured choice with two to four options uses the `AskUserQuestion` form. Each option shows its own trade-off, the user picks one.
- Open text (name, email, free-form preference) uses an inline chat question.
- A trivial yes-or-no question with a sensible default does not get asked. Apply the default, mention it in one line if it might surprise the user, and let the user correct.

## The workflow

### Step 1: Detect

Check whether `.zanmai/user.md` exists. If yes, stop. Report what is there, ask whether the user wants `update` (schema migration) or `validate` (structural check) instead.

If no, the vault is uninitialised: proceed to Step 1a and run the setup workflow now. A freshly copied vault holds only `.zanmai/`, `CLAUDE.md` and `README.md`, no `.claude/` and no hooks yet; `setup init` creates `.claude/settings.json` at the end, and the safety hooks become live when the user reopens the vault after setup. This one setup dialogue therefore runs with no hook active, so hold the house voice by the canonical, em-dash-free text given in the steps below (operating-principles section 7), do not free-compose it.

### Step 1a: Opening

A short greeting in the user's writing language, addressing them personally rather than distantly where the language distinguishes the two. The user's name is not known yet (no `.zanmai/user.md`), so the greeting must not address them by any name. Speak this canonical opening, translated to the user's writing language, and in the personal form of address where that language has one (never the distant form), rather than free-composing it: "Hello, I am Steve, your concierge for this vault. It is still empty, so let us set it up together. First I take a quick look at your system, then a few short questions." Mechanics (script names, `.zanmai/user.md`, hooks, settings) do not belong here, they belong in Step 4 or in `.zanmai/system/docs/setup.md`.

After the greeting, continue with Step 1b. The next visible chat output is the first question in Step 2, or a single one-liner from Step 1b when something genuinely needs the user's attention (ZenNotes app detected but vault not yet opened, missing zn CLI, Python not found).

### Step 1b: Environment check

Run the checks in this order. Each check produces at most one short user-facing line in the user's writing language, then continues. No internal narration between tool calls, no "I'm probing the environment now" filler, no "ZenNotes integration active, zn CLI looks fine" status reports. The check either says what was found, asks a question if one is needed, or stays silent.

Python is checked first because the entire script layer depends on it. Without Python, setup cannot continue.

**Check 0: Python interpreter available.**

Zanmai ships a Python CLI (`zanmai.py`) plus a handful of hooks. At least one of these invocations must work, tried in order:

1. `python3 --version`
2. `python --version` (accept only if it reports Python 3.x, on older Mac or Linux this can still be Python 2)
3. `py -3 --version` (Windows launcher)

Remember the first invocation that succeeded, call it `<python_cmd>`. Pass it to `zanmai.py setup init --python-cmd "<python_cmd>"` in Step 3. The script stores it in `.zanmai/user.md` and uses it for hook registrations in `.claude/settings.json`. From then on, Steve substitutes `<python_cmd>` wherever skill files say `python3`.

If none of the invocations succeed, stop setup with a clear, OS-specific install hint, phrased in the user's writing language. The hint names that Zanmai needs Python 3.10 or newer, lists the standard install paths for macOS (Homebrew `brew install python`, or python.org), Windows (python.org or `winget install Python.Python.3`) and Linux (the platform package manager), and tells the user to start a new session and re-run setup after install. Nothing has been written yet at that point.

Do not invent alternative install paths. Do not try to download Python.

**Check 1: ZenNotes installed and intended for this vault.**

Tools-existence is not usage-intent (operating-principles section 9). A user can have ZenNotes installed for another vault and want this one without it. Whichever they choose, the vault always stores plain Markdown that any Markdown editor can open, with or without ZenNotes; ZenNotes is only an optional companion editor, never what makes the vault Markdown. So the choice is never framed as Markdown versus something else, and Markdown is never named as a benefit of one side. Setup distinguishes three cases, each gets one short line in the user's writing language.

- Case A, `.zennotes/` folder exists at the vault root. ZenNotes already opened this vault as a vault, the intent is unambiguous. Set `zennotes_installed: true`, tell the user in one line that ZenNotes is the editor set for this vault, and that the notes stay plain Markdown any editor can open. Daily, Weekly and Monthly Notes state (enabled, folder name, location) is not persisted in user.md, it lives in `.zennotes/vault.json` and is read live by the session-start hook into `.zanmai/vault-config.md` for the AI. Then proceed to Check 2.
- Case B, the `.zennotes/` folder does not exist but the ZenNotes app does. Detect the macOS app via `[ -d "/Applications/ZenNotes.app" ]` (other platforms skip the check). Existence of the app does not mean usage-intent, the user might keep this vault out of ZenNotes intentionally. Ask via the `AskUserQuestion` form in the user's writing language, with two options. The yes option sets `zennotes_installed: true` and proceeds to Check 2. The no option sets `zennotes_installed: false` and `zen_cli_installed: false` (skip Check 2, without ZenNotes-usage the CLI semantics do not apply, even if the binary is in PATH), and continues. Its one short follow-up line does not mention Markdown or editors, that is the common ground for both answers, never a consequence of declining ZenNotes; it simply notes that Zanmai carries on without ZenNotes.
- Case C, neither `.zennotes/` nor the ZenNotes app exist. Lead with the fact that no ZenNotes was found, kept calm, not framed as a lack. A few plain, human sentences, one thought each, no parentheses. Canonical, translated to the user's language: "I did not find ZenNotes on your computer. Your notes are plain Markdown and open in any editor, and ZenNotes is simply the editor we offer with Zanmai, which adds an inbox and daily and weekly notes." Then ask via the `AskUserQuestion` form, translated to the user's writing language. Use this canonical menu verbatim, do not free-compose it. Question: "Do you want to use ZenNotes for this vault?" First option label "Use ZenNotes", description "I show you where to get it. Zanmai picks it up once it is installed." Second option label "Do not use ZenNotes", description "You keep working in your own editor. Nothing to set up." Never put "Markdown" in a label or a description as if it set the options apart: the notes are plain Markdown in both cases, so Markdown is the ground both options stand on, never one side of the choice. The options differ only in whether ZenNotes is used. Either way setup continues as a plain Markdown vault now: Check 2 is skipped, the Daily, Weekly and Monthly Notes folders are left out (ZenNotes creates those itself if it is added later), and the `zennotes_installed` / `zen_cli_installed` flags come from live detection by `setup init`, not from a guess here.

If the user later asks what ZenNotes is, Steve answers from `.zanmai/system/docs/setup.md` in one paragraph plus the link. The setup turn itself does not volunteer that explainer.

**Check 1b: Daily, Weekly and Monthly Notes orientation.**

Only run when Check 1 set `zennotes_installed: true` and `.zennotes/vault.json` is readable.

Daily, Weekly and Monthly Notes are quick places to jot what is on the user's mind, and Zanmai reads the recent ones into the next session's briefing. Which of them are on is set in ZenNotes, so Zanmai follows that switch and never flips it itself.

Zanmai reads the current state live from `.zennotes/vault.json` on every session start and surfaces it in `.zanmai/vault-config.md`. Setup does not persist Daily/Weekly/Monthly state in `.zanmai/user.md`.

If any of Daily, Weekly or Monthly is currently off in `vault.json`, one short orientation line in the user's writing language explains the value of having them on, and one short line tells the user where to flip the switch in ZenNotes (Settings, Vault, Periodic Notes). No `AskUserQuestion`, no persistence, the ZenNotes switch is the actual feature and Zanmai never writes `vault.json` from outside.

**Check 2: zn CLI in PATH.**

Only run if Check 1 set `zennotes_installed: true` (Cases A or B-yes).

`command -v zn` returns 0 if installed.

If found, stay silent and set `zen_cli_installed: true` in user.md.

If not found, tell the user in their writing language, in one or two short lines, that ZenNotes is here but its command-line helper is not set up yet, that it is optional and Zanmai works fine without it, and that they can add it later from the ZenNotes settings. Continue setup. Set `zen_cli_installed: false` in user.md.

Do not ask the user to install anything mid-setup. Inform once and continue. The user can re-run setup later when the toolchain is complete.

### Step 2: Explain, then ask, one at a time

Before each question, one or two sentences of context in the user's writing language. The user did not read the docs, they should know why each answer matters. Then the question. One at a time. Do not batch.

Both the context and the question are spoken to the user. A bare question without context reads as rude and unclear. The shape: short context sentence(s) explaining why the answer matters, then the question itself, in the user's writing language.

If the user volunteered information in earlier turns (they typed it in this conversation), reuse it. Inferences from how the user wrote get a one-line confirm-and-correct, state what was inferred and how the user can change it, never a silent apply. Blindly re-asking data the user already gave is skipped. The list below is the field inventory, not a mandatory question script.

The identity fields (preferred address, real first name, last name, email) are always asked, one plain open-text question per turn. Steve never reads or guesses them from the system account, the git config, an existing email address, or any other environment signal, and never folds two fields into a single yes-or-no confirmation. Reading a machine email to guess the name, and bundling the two into one confirmation, is exactly what leaves the user unsure which field they are answering. Ask, do not detect.

All questions are asked in the user's writing language at runtime (Steve detects the language from how they write and translates the prompts). Translate into the personal form of address where the language has one. Asking someone for the name they want to be called by while addressing them formally contradicts itself, so the whole setup speaks to them personally. The labels below are the canonical English phrasing. Do not write any other language version into this file.

1. Preferred address. Context: how should I address you, this is the name I will use in every reply, it can differ from your real first name, many people prefer a nickname or a short form, or a different name entirely. Question: how should I address you? Do not list real-name examples in the question, the question is generic enough on its own.
2. First name (real). Context: your real first name is separate, it becomes part of your owner-contact's slug (filename) and is used wherever the system needs your full identity, if your preferred address is also your real first name, just repeat it here. Question: and your real first name?
3. Last name. Context: a last name makes the slug unique, if you ever file another contact with the same first name, there is no collision. Question: last name?
4. Email (optional). Context: an email goes into your owner-contact, useful later when material arrives addressed to you so I can correlate, skip if you prefer, you can add it via the checklist in your contact file. Question: email, or skip?
5. Language. Context: I detect language from how you write, this stores the preference explicitly so I do not second-guess on short messages. Question: I will reply in the detected language, OK, or pick another code (`en`, `de`, `es`)?

That is the minimum for v1.0. Birthday, phone, address, organisation, role, and website are surfaced as a checklist in the owner-contact body after setup. The user fills them at their own pace.

If preferred-address equals first-name, the owner-contact stores them once (no duplicate `nickname` field). If they differ, the owner-contact's frontmatter carries both: `first_name` and `last_name` for identity, `nickname` for address. Steve uses `nickname` for greetings and falls back to `first_name` only if `nickname` is empty.

### Step 3: Call the script

Run the script without prefacing it with a status line. The Bash invocation is sufficient signal, another sentence on top is filler. The next visible chat output is the Step 4 confirmation after the script returns.

Run from the vault root, substituting `<python_cmd>` with the invocation that worked in Step 1b Check 0 (often `python3`, on Windows `py -3` or `python`):

```
<python_cmd> .zanmai/system/scripts/zanmai.py setup init . --first-name "<first>" --last-name "<last>" --language "<lang>" --python-cmd "<python_cmd>" [--email "<email>"] [--preferred-address "<nickname>"]
```

Pass `--preferred-address` only if the user gave a value different from `--first-name`. Same value is fine to omit.

`--python-cmd` carries the detected invocation forward so the migration writes it into `.zanmai/user.md` and the hook commands in `.claude/settings.json` use it instead of a hardcoded `python3`.

The script creates the folder skeleton plus:

- `.zanmai/user.md` with `first_name`, `last_name`, `language`, `owner_contact` pointer, `auto_snapshots: true` (single master switch for every automatic snapshot, turn off via `zanmai.py snapshot disable` when the user has their own backup discipline).
- `inbox/contacts/people/<slug>.md` as the owner-contact (slug derived from first plus last name, kebab-case ASCII).
- `INDEX.md` at the vault root (master index, Steve maintains it as bundles are added).
- `.zanmai/memory/general.md`, `.zanmai/memory/activity-log.md`, `.zanmai/memory/agents/{steve,hank}/lessons.md`.
- `.claude/settings.json` with `autoMemoryEnabled: false`, the `kind-required` and `permission-guard` PreToolUse hooks, the `index-consistency` PostToolUse hook, and the `session-start` SessionStart hook. No MCP consent gate: a host-exposed MCP is available for use (LD6).
- `.claude/settings.local.json` with Bash allow-rules for the Zanmai scripts so the user is not prompted on every invocation.

### Step 3b: Localize the owner-contact body

Init writes the owner-contact at `inbox/contacts/people/<slug>.md` with an English body. If the user's writing language is not English, Steve reads the file, translates every line from `# <Full Name>` onwards into the user's writing language, and writes it back. The frontmatter block between the two `---` lines stays English, those labels are machine-readable. Code identifiers in backticks (`nickname`, `owner_contact`, `.zanmai/user.md`, `close-session`) stay verbatim. Section headings, prose, sub-category bullets and `(empty)` placeholders all translate. If the user's writing language is English, skip this step.

### Step 4: First snapshot, then confirm

Take the first snapshot silently using the detected `<python_cmd>`:

```
<python_cmd> .zanmai/system/scripts/zanmai.py snapshot create . .zanmai/snapshots/ post-init
```

Then tell the user, in their writing language, that setup is done. The confirmation has three parts: a substantive Zanmai-identity paragraph (not just a place to remember but a system that orders, thinks, creates and does, sorted by the three attention layers), the collaboration model in one sentence, and the instruction to open a fresh session. Tone: written prose, not chat. No em-dashes as stylistic markers. No casual filler.

Canonical English template, runtime-translates to the user's writing language:

> Hello <preferred-address>. Zanmai is set up.
>
> Zanmai takes what does not have to stay in your head, and does more than remember it: it orders, thinks, creates and gets things done. It holds what occupies you now, what recurs as routine, what you keep as knowledge, plus contacts, plans and source material for every theme in your life. You write things yourself or describe them to me; I structure, sort, retrieve and keep the cross-references clean, and the capabilities built on top act for you.
>
> Close this session and open a new one on this vault. From then on, Zanmai takes over and I walk you through the first steps.

The confirmation follows the global communication rule (see `.zanmai/system/operating-principles.md` section 7): solution-focused, plain language, no assumed knowledge of Zanmai's scripts, paths or internal terminology. No capability claims for anything that is not in the vault. The user asked for setup, not an architecture manual or a usage tour.

The detailed onboarding (slash commands, close-session discipline, ask-anytime) happens in the first real session after the new session is opened, not here. Steve's contract has the first-session onboarding template in `Session start, first session after setup`. Setup's job ends at that instruction.

If the user explicitly asked during setup about something specific, answer that one thing in one sentence and stop.

### Step 5: The closing line

The confirmation in Step 4 already ends with the close-session instruction as its final line, and that is the last thing setup says. It is not repeated as a separate line. Phrase it as closing this session and opening a new one, not as quitting and relaunching the app. In the desktop app a relaunch can drop the user back into the same session, where the freshly written settings have not loaded yet. No mention of which settings change, no list of hooks. The user does not need to debug what the new session does, they only need to know a new session is required.

## Rationalizations to resist

| Rationalization | Reality |
|---|---|
| "I'll ask everything in one message to save round-trips." | Setup is four questions maximum. One at a time produces cleaner answers. |
| "I can write `.zanmai/user.md` directly with the user's answers." | The script is the only writer. Bypassing it breaks future migrations. |
| "The user did not give a last name, I'll just use the first name as the contact slug." | A first-name-only slug collides with the first additional contact added later. Ask. |
| "The user did not give a language, I'll pick English." | Ask. Defaults the user did not pick erode trust. |
| "I'll add timezone, working hours, birthday and integrations so it feels complete." | The current setup asks four questions. Anything else goes onto a separate addition path, not into setup. |
| "The user said `setup` but `.zanmai/user.md` already exists, I'll just rerun." | Refuse and ask whether the user wants `update` or `validate`. Idempotent does not mean silently overwrite. |
| "I'll mention that auto-memory is now off, the hook is wired, permissions are set, the user should know." | The user was not asked about any of that. They asked for setup. They got setup. Background mechanics belong in docs, not in the confirmation. |
| "Preferred address and first name are the same field with two labels." | They are not. Preferred address is how to call the person (a nickname or short form), first name is the real name on the contact (the full given name). Two fields, two values, often equal but not always. Ask both. |
| "The Step 4 confirmation should list all the features so the user knows what is possible." | The confirmation is identity sentence plus collaboration sentence plus two or three entry verbs. Not a feature tour. Further detail comes when the user asks. |
| "I'll list external integrations (calendar, mail, fitness, project-management) in the confirmation so the user knows the full scope." | Zanmai is the vault. External tools are not in the vault. They are not listed as Zanmai capabilities, not hinted at as future capabilities, not mentioned at all. |

## Red flags, stop and recheck

Stop if any of the following happens:

- Writing to `.zanmai/user.md` from the conversation (Step 3 is the only write path).
- Skipping the language confirmation because the language seems obvious.
- Creating folders the user did not name and the manifest does not list.
- Renaming the script's outputs.
- Adding placeholder content to `.zanmai/user.md` that the user did not provide.
- Producing a feature menu in Step 4 instead of identity plus collaboration plus two or three entry verbs.
- Listing capabilities Zanmai does not own in the Step 4 confirmation.

If any of these, re-read this skill file and rerun the workflow from Step 1.

## Files

- `.zanmai/system/scripts/zanmai.py` (`setup init` subcommand): the single CLI; the deterministic state change for first-time install.
- `.zanmai/system/manifest.yaml`: canonical list of folders and distribution files.
