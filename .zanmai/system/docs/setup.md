[← Zanmai Documentation](index.md)

# Setup

## What setup is

The one conversation that happens when you open a fresh vault for the first time. It asks a handful of things, looks at what your machine has, and lays out the folders. After that it never runs again.

Underneath, the conversation collects the answers and one command writes them out. When it is done, close the session and open a new one: the guards Zanmai installs only take effect when a session starts.

Setup asks five things.

1. Preferred address (how Steve addresses the user in every reply, a nickname or short form, when the user does not want to be addressed by the real first name). Stored as `preferred_address` in `.zanmai/user.md` and as `nickname` on the owner-contact. Empty if equal to the first name.
2. First name (the real first name, for the owner-contact slug and any place the system needs full identity).
3. Last name (for slug uniqueness, the first name alone collides with the next contact carrying the same first name).
4. Email (optional, can be skipped, goes into the owner-contact, also useful for filing material addressed to the user).
5. Language preference (`de`, `en`, etc., confirms the auto-detection from the conversation).

The split between preferred address and first name exists because many people prefer a nickname or short form over their full name. The same split applies to other contacts the user later files. Nicknames are a normal contact attribute, not a special case.

That is the entire dialogue. Setup does not ask birthday, address, organisation, role, phone or website. Those are optional profile fields the user adds when they mention them or when a concrete trigger appears (a booking needs a phone number, a contact links to an organisation). Setup writes a single-line reminder into `.zanmai/memory/general.md` under "Open threads" so the option stays present across sessions without a user-visible task list.

## Why

Four mandatory questions, not more, because:

- Slug uniqueness needs first plus last name. A first-name-only slug collides the first time the user files another contact with the same first name. Zanmai enforces unique slugs per folder.
- Email is the only piece of structured data setup needs upfront. It is the most common identifier and the most awkward to dig out of a separate dialog later. Still optional, the user can skip and add it later by mentioning it.
- Language is asked explicitly even though Steve auto-detects. The auto-detection looks at how the user writes. Setup-time detection might mis-call if the user's first message is short. Asking once removes ambiguity.
- All other fields stay out of the setup dialogue: birthday, address, organisation, role, phone, website. Adding them would balloon first install. Instead, the AI carries a one-line reminder in `.zanmai/memory/general.md` Open Threads, the option is not forgotten across sessions, but the user is not nagged from a task list. The user mentions the value when it matters; the AI adds it to the owner-contact frontmatter at that moment.

Why not zero questions and full automation? Because Steve needs to address the user by name from the first reply, and that name has to be persistent across sessions. Asking once is cleaner than guessing.

## What is checked before you are asked anything

Before the first question, Zanmai looks at your machine. The order matters, because each check decides whether the next one is even relevant.

1. Python interpreter. Try `python3`, `python`, `py -3`. The first invocation that reports a Python 3.x version wins and gets remembered as `python_cmd` in `.zanmai/user.md`. The hook commands in `.claude/settings.json` use this invocation. Setup stops with a clear install hint (specific to macOS, Linux or Windows) if none works. Nothing has been written at that point. The user installs Python and re-runs setup.
2. ZenNotes app, three-case logic per operating-principles section 9 ("tools-existence is not usage-intent"). Each case gets one short user-facing line in the user's writing language so the user reads what was found, not a silent state change. The toggle `zennotes_installed` in `user.md` distinguishes installation from intent.
    - Case A: `.zennotes/` exists at the vault root. ZenNotes already opened this vault, the intent is unambiguous. `zennotes_installed: true`. One short line in the user's writing language stating that ZenNotes is being used for this vault.
    - Case B: `.zennotes/` missing but the ZenNotes app present. One short line in the user's writing language asking whether to configure this vault for ZenNotes. On yes, `zennotes_installed: true`. On no, both `zennotes_installed: false` and `zen_cli_installed: false` (skip the CLI check entirely, without ZenNotes usage the CLI semantics do not apply).
    - Case C: neither folder nor app. `zennotes_installed: false`. Lead with a short line that no ZenNotes was found, then the plain framing: the notes are plain Markdown and open in any editor, ZenNotes is the editor Zanmai offers. Then an `AskUserQuestion` with two equal options labelled exactly "Use ZenNotes" and "Do not use ZenNotes". Markdown appears in neither the labels nor the descriptions: the notes are plain Markdown in both cases, so it is the ground both options stand on, never one side of the choice, and the options differ only in whether ZenNotes is used. Either way the CLI check is skipped and setup continues as a plain Markdown vault now.
3. Daily, weekly and monthly notes. Only runs when ZenNotes is intended for this vault. Zanmai reads `dailyNotes` and `weeklyNotes` live from `.zennotes/vault.json` on every session start via the `session-start.py` hook and surfaces the current state in `.zanmai/vault-config.md` for the AI. Nothing is persisted in `.zanmai/user.md` about Daily/Weekly state. If either is off at setup, the dialogue explains in one short line what Zanmai uses them for and tells the user where to flip the switch in ZenNotes settings. Zanmai never writes `vault.json`, that file is ZenNotes' own settings store.
4. `zn` CLI. Only checked if Case A or Case-B-yes (ZenNotes is intended for this vault). Optional. Without it, `zanmai.py` falls back to Unix `mv` for trash and archive (loses the ZenNotes-restore-path semantics).

Then the dialogue starts.

## How to use

The user invokes setup through Steve when `.zanmai/user.md` is missing, or asks for an initial install in their writing language. Steve checks whether `.zanmai/user.md` exists. If no, the `setup` skill triggers. The skill runs the environment cascade above, then asks the five questions one at a time, then calls the script:

```
<python_cmd> .zanmai/system/scripts/zanmai.py setup init . --first-name "<first>" --last-name "<last>" --language "<lang>" --python-cmd "<python_cmd>" [--email "<email>"] [--preferred-address "<nickname>"]
```

The script creates the folder skeleton, writes `.zanmai/user.md`, creates the owner-contact under `inbox/contacts/people/<slug>.md`, writes `INDEX.md` at the vault root, generates `.claude/settings.json` with `autoMemoryEnabled: false` and the four hooks wired, and writes `.claude/settings.local.json` with the Bash allow-rules. The first snapshot is taken automatically.

Then Claude Code restart. The user closes the current session and re-opens the vault. From the next session on, the hooks are active and auto-memory is off.

## When not to use

Setup runs once. Re-running with an existing `.zanmai/user.md` is refused. The hint points to `update` (when implemented) or to editing `.zanmai/user.md` directly.

If the user wants to change their name or language after setup, the path for now is a direct edit of `.zanmai/user.md` plus a manual rename of the owner-contact file. A `zanmai.py setup update` subcommand that does per-field edits is a future addition.

## Version

`.zanmai/system/VERSION` is a plain `key: value` file holding the current Zanmai distribution version:

```
distribution_version: <version>
phase: <phase>
schema_version: <schema version>
released: <release date>
```

The user can read it any time via `cat .zanmai/system/VERSION` or by asking Steve which version is running. `.zanmai/user.md` carries `zanmai_version_installed` and `zanmai_phase_installed` recording what was active at setup. If a future `zanmai.py setup update` runs, the user.md fields stay, the VERSION file moves with the distribution. Drift between the two is the trigger for an update prompt.

## Files

- `.zanmai/system/scripts/zanmai.py` (`setup init` subcommand): the single CLI; deterministic state change for first-time install. The first-run migration is an internal function in zanmai.py.
- `.zanmai/system/skills/setup/SKILL.md`: the dialogue.
- `.zanmai/system/VERSION`: distribution version.
- `.zanmai/user.md`: output, the user profile (carries `zanmai_version_installed`).
- `inbox/contacts/people/<slug>.md`: owner-contact, also output.
- `.claude/settings.json` and `.claude/settings.local.json`: output.

---

[← Back to the documentation index](index.md)
