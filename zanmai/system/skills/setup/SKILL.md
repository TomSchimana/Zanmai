---
name: setup
description: First-time vault setup. Runs when `zanmai/user.md` does not exist, or on any ask for an initial install or first run. Dialogue, then `zanmai.py setup init`.
---

# setup

First-time install. Steve runs this when the vault has no `zanmai/user.md`. The skill is invoked by reading this file and following the workflow below, it is not a slash command.

## Directive

This skill drives the dialogue. The deterministic state changes (folder creation, `zanmai/user.md` write) are done by `zanmai/system/scripts/zanmai.py setup init`. Do not write `zanmai/user.md` directly from the conversation. Use the script. The script is the single point of state change so future migrations can reason about what got written.

## When to use

- `zanmai/user.md` is missing.
- The user asks for an initial install or first run in their writing language.
- An older install needs to migrate to a new schema version, in which case the workflow calls `zanmai.py setup update`, not `init`.

## When not to use

- `zanmai/user.md` already exists and the schema is current. Refuse and tell the user.
- The user wants to add a single bundle. That is `import-bundle`, not setup.
- The user wants to rename folders. That is a manual operation, not in scope here.

## How to ask the user

Three modes:

- Structured choice with two to four options uses the `AskUserQuestion` form. Each option shows its own trade-off, the user picks one.
- Open text (name, email, free-form preference) uses an inline chat question.
- A trivial yes-or-no question with a sensible default does not get asked. Apply the default, mention it in one line if it might surprise the user, and let the user correct.

## The workflow

### Step 1: Detect

Check whether `zanmai/user.md` exists. If yes, stop. Report what is there, ask whether the user wants `update` (schema migration) or `validate` (structural check) instead.

If no, the vault is uninitialised: proceed to Step 1a and run the setup workflow now. A freshly copied vault holds only `zanmai/`, `CLAUDE.md` and `README.md`, no `.claude/` and no hooks yet; `setup init` creates `.claude/settings.json` at the end, and the safety hooks become live when the user reopens the vault after setup. This one setup dialogue therefore runs with no hook active, so hold the house voice by the canonical, em-dash-free text given in the steps below (operating-principles section 7), do not free-compose it.

### Step 1a: Opening

A short greeting in the user's writing language, addressing them personally rather than distantly where the language distinguishes the two. The user's name is not known yet (no `zanmai/user.md`), so the greeting must not address them by any name. Speak this canonical opening, translated to the user's writing language, and in the personal form of address where that language has one (never the distant form), rather than free-composing it: "Hello, I am Steve, your concierge for this vault. It is still empty, so let us set it up together. First I take a quick look at your system, then a few short questions." Mechanics (script names, `zanmai/user.md`, hooks, settings) do not belong here, they belong in Step 4 or in `zanmai/system/docs/setup.md`.

After the greeting, continue with Step 1b. The next visible chat output is the first question in Step 2, or a single one-liner from Step 1b when something genuinely needs the user's attention (Python not found).

### Step 1b: Environment check

There is one check. Zanmai needs nothing installed but Python: no editor, no companion app, no command-line helper. The vault is plain files and works with whatever the user already opens files in.

The check produces at most one short user-facing line in the user's writing language. No internal narration between tool calls, no "I'm probing the environment now" filler, no status reports.

**Check 0: Python interpreter available.**

Zanmai ships a Python CLI (`zanmai.py`) plus a handful of hooks. At least one of these invocations must work, tried in order:

1. `python3 --version`
2. `python --version` (accept only if it reports Python 3.x, on older Mac or Linux this can still be Python 2)
3. `py -3 --version` (Windows launcher)

Remember the first invocation that succeeded, call it `<python_cmd>`. Pass it to `zanmai.py setup init --python-cmd "<python_cmd>"` in Step 3. The script stores it in `zanmai/user.md` and uses it for hook registrations in `.claude/settings.json`. From then on, Steve substitutes `<python_cmd>` wherever skill files say `python3`.

If none of the invocations succeed, stop setup with a clear, OS-specific install hint, phrased in the user's writing language. The hint names that Zanmai needs Python 3.10 or newer, lists the standard install paths for macOS (Homebrew `brew install python`, or python.org), Windows (python.org or `winget install Python.Python.3`) and Linux (the platform package manager), and tells the user to start a new session and re-run setup after install. Nothing has been written yet at that point.

Do not invent alternative install paths. Do not try to download Python.

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
<python_cmd> zanmai/system/scripts/zanmai.py setup init . --first-name "<first>" --last-name "<last>" --language "<lang>" --python-cmd "<python_cmd>" [--email "<email>"] [--preferred-address "<nickname>"]
```

Pass `--preferred-address` only if the user gave a value different from `--first-name`. Same value is fine to omit.

`--python-cmd` carries the detected invocation forward so the migration writes it into `zanmai/user.md` and the hook commands in `.claude/settings.json` use it instead of a hardcoded `python3`.

The script creates the folder skeleton plus:

- `zanmai/user.md` with `first_name`, `last_name`, `language`, `owner_contact` pointer, `auto_snapshots: true` (single master switch for every automatic snapshot, turn off via `zanmai.py snapshot disable` when the user has their own backup discipline).
- `contacts/people/<slug>.md` as the owner-contact (slug derived from first plus last name, kebab-case ASCII).
- `INDEX.md` at the vault root (master index, Steve maintains it as bundles are added).
- `zanmai/memory/general.md`, `zanmai/memory/activity-log.md`, `zanmai/memory/agents/{steve,hank}/lessons.md`.
- `.claude/settings.json` with `autoMemoryEnabled: false`, the `kind-required` and `permission-guard` PreToolUse hooks, the `index-consistency` PostToolUse hook, and the `session-start` SessionStart hook. No MCP consent gate: a host-exposed MCP is available for use (LD6).
- `.claude/settings.local.json` with Bash allow-rules for the Zanmai scripts so the user is not prompted on every invocation.

### Step 3b: Localize the owner-contact body

Init writes the owner-contact at `contacts/people/<slug>.md` with an English body. If the user's writing language is not English, Steve reads the file, translates every line from `# <Full Name>` onwards into the user's writing language, and writes it back. The frontmatter block between the two `---` lines stays English, those labels are machine-readable. Code identifiers in backticks (`nickname`, `owner_contact`, `zanmai/user.md`, `close-session`) stay verbatim. Section headings, prose, sub-category bullets and `(empty)` placeholders all translate. If the user's writing language is English, skip this step.

### Step 3c: Offer to fetch the prerequisites, once

Run `zanmai.py tools ensure-all <vault>` and read what it prints. It reports three groups: what is
already here, what Zanmai can fetch by itself, and what the user installs with one command each.

Put the first group in front of them in their own language, in a few lines: how many are already
there, what the fetchable ones are for (their purpose, never their package names), and the question
whether to fetch them now. On a yes, run the same command with `--yes` and report per item what came
of it. On a no or a later, say nothing further about it; the offer is not repeated.

The ones they install themselves are named afterwards, each with the one command that does it, as
information rather than as a task. Anything host-configured is not mentioned at all here.

Why this sits in setup: without it, a missing prerequisite is met for the first time in the middle
of a job that is already running, which is where it is most expensive and least welcome. Asking once,
at the only moment nothing is running, is the cheap version of the same conversation.

### Step 3d: Offer a launcher icon

Ask, via the `AskUserQuestion` form (two options, one sentence each): build a one-click starter now, or
skip it. There is no sensible default to apply silently here, people genuinely differ on whether they
want an icon, so this is asked rather than assumed.

On yes, run the `create-launcher` skill's workflow (detect installed terminals, ask the name, build it,
confirm) inline, then continue to Step 4. On no, say nothing further about it and continue to Step 4:
a "no" here is about this moment, not a standing refusal, the user can ask for it anytime later the
same way `create-launcher` describes.

### Step 4: Confirm

No snapshot here. A snapshot exists to undo a change, and a vault that was just set up holds nothing
to undo: the copy would be of an empty skeleton. The first one is taken before the first import, where
there is finally something to lose.

Tell the user, in their writing language, that setup is done. The confirmation has three parts: a substantive Zanmai-identity paragraph (not just a place to remember but a system that sorts, connects, drafts and carries work through, with folders named after what is going on rather than what stage a file is at, and nothing obliged to move between them), the collaboration model in one sentence, and the instruction to open a fresh session. Tone: written prose, not chat. No em-dashes as stylistic markers. No casual filler.

Canonical English template, runtime-translates to the user's writing language:

> Hello <preferred-address>. Zanmai is set up.
>
> Zanmai takes what does not have to stay in your head, and does more than remember it: it sorts, connects, drafts and carries work through. It holds what occupies you now, what recurs as routine, what you keep as knowledge, plus contacts, plans and source material for every theme in your life. You write things yourself or describe them to me; I structure, sort, retrieve and keep the cross-references clean, and the capabilities built on top act for you.
>
> Close this session and open a new one on this vault. From then on, Zanmai takes over and I walk you through the first steps.

The confirmation follows the global communication rule (see `zanmai/system/operating-principles.md` section 7): solution-focused, plain language, no assumed knowledge of Zanmai's scripts, paths or internal terminology. No capability claims for anything that is not in the vault. The user asked for setup, not an architecture manual or a usage tour.

The detailed onboarding (slash commands, close-session discipline, ask-anytime) happens in the first real session after the new session is opened, not here. Steve's contract has the first-session onboarding template in `Session start, first session after setup`. Setup's job ends at that instruction.

If the user explicitly asked during setup about something specific, answer that one thing in one sentence and stop.

### Step 5: The closing line

The confirmation in Step 4 already ends with the close-session instruction as its final line, and that is the last thing setup says. It is not repeated as a separate line. Phrase it as closing this session and opening a new one, not as quitting and relaunching the app. In the desktop app a relaunch can drop the user back into the same session, where the freshly written settings have not loaded yet. No mention of which settings change, no list of hooks. The user does not need to debug what the new session does, they only need to know a new session is required.

## Sounds sensible, is wrong

| Rationalization | Reality |
|---|---|
| "I'll ask everything in one message to save round-trips." | Setup is four questions maximum. One at a time produces cleaner answers. |
| "I can write `zanmai/user.md` directly with the user's answers." | The script is the only writer. Bypassing it breaks future migrations. |
| "The user did not give a last name, I'll just use the first name as the contact slug." | A first-name-only slug collides with the first additional contact added later. Ask. |
| "The user did not give a language, I'll pick English." | Ask. Defaults the user did not pick erode trust. |
| "I'll add timezone, working hours, birthday and integrations so it feels complete." | The current setup asks four questions. Anything else goes onto a separate addition path, not into setup. |
| "The user said `setup` but `zanmai/user.md` already exists, I'll just rerun." | Refuse and ask whether the user wants `update` or `validate`. Idempotent does not mean silently overwrite. |
| "I'll mention that auto-memory is now off, the hook is wired, permissions are set, the user should know." | The user was not asked about any of that. They asked for setup. They got setup. Background mechanics belong in docs, not in the confirmation. |
| "Preferred address and first name are the same field with two labels." | They are not. Preferred address is how to call the person (a nickname or short form), first name is the real name on the contact (the full given name). Two fields, two values, often equal but not always. Ask both. |
| "The Step 4 confirmation should list all the features so the user knows what is possible." | The confirmation is identity sentence plus collaboration sentence plus two or three entry verbs. Not a feature tour. Further detail comes when the user asks. |
| "I'll list external integrations (calendar, mail, fitness, project-management) in the confirmation so the user knows the full scope." | Zanmai is the vault. External tools are not in the vault. They are not listed as Zanmai capabilities, not hinted at as future capabilities, not mentioned at all. |

## Stop and look again

Stop if any of the following happens:

- Writing to `zanmai/user.md` from the conversation (Step 3 is the only write path).
- Skipping the language confirmation because the language seems obvious.
- Creating folders the user did not name and the manifest does not list.
- Renaming the script's outputs.
- Adding placeholder content to `zanmai/user.md` that the user did not provide.
- Producing a feature menu in Step 4 instead of identity plus collaboration plus two or three entry verbs.
- Listing capabilities Zanmai does not own in the Step 4 confirmation.

If any of these, re-read this skill file and rerun the workflow from Step 1.

## Files

- `zanmai/system/scripts/zanmai.py` (`setup init` subcommand): the single CLI; the deterministic state change for first-time install.
- `zanmai/system/manifest.yaml`: canonical list of folders and distribution files.
- `zanmai/system/skills/create-launcher/SKILL.md`: Step 3d's optional offer, and the same skill the
  user can invoke directly, anytime, by asking for an icon, an app or a shortcut.
