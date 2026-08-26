---
name: zanmai:create-launcher
description: Build a double-clickable starter for this vault. Triggers on any ask for an icon, app, launcher or shortcut to start Zanmai, and once as an optional step after setup.
---

# create-launcher

Not opening a terminal, finding the right folder, and knowing to type `claude` is a real barrier for
someone who did not set the vault up themselves. This turns that into one click.

## Directive

The script does the mechanics: detecting terminals, building the icon, writing the app or shortcut.
The conversation resolves the two choices a person actually has an opinion about, which terminal and
what to call it. Do not build the icon by hand, and do not skip the script's terminal detection and
guess what is installed.

## When to use

- The user asks, in their own words, for an icon, an app, a launcher, a shortcut, or "something to
  click" that starts Zanmai. This is the direct trigger and works at any point in a session.
- Offered once, as an optional last step of the `setup` skill (its Step 3d), after the vault is fully
  set up. A "no" there is not final: the user can ask for this anytime afterward the same way.

## When not to use

- The vault is not set up yet (no `zanmai/user.md`). Run `setup` first.
- The user wants to change vault folders or rename things. That is a manual operation, unrelated to
  this skill.

## The workflow

### Step 1: find out what is installed

Run `zanmai.py launcher detect-terminals` from the vault root. It prints `id<TAB>name` pairs, one per
line, and it is the only source of truth for what to offer; do not guess what terminal apps exist.

- **Exactly one result** (always the case on Windows, and on a macOS machine with nothing but Terminal):
  no question. Use it, and mention which one in the confirmation at the end so it does not look silent.
- **More than one result** (macOS with something else installed too): ask via the `AskUserQuestion`
  form, one option per detected terminal, each with a one-line note if there is something worth saying
  about it (already tested and proven vs. not yet tried, for example). Terminal itself is always the
  first option, it is the one every macOS install has.

### Step 2: name it

The default is always the vault folder's own name, read from the path, for example `Zanmai-dev` or
`Second Brain`, never a fixed product name. State the default in one line and ask whether that is fine
or whether the user wants a different name; a free name is always allowed. This is the inline-question
mode from the `setup` skill's "How to ask the user" section, not a menu, there is nothing to choose
between beyond default vs. override.

### Step 3: build it

```
<python_cmd> zanmai/system/scripts/zanmai.py launcher create <vault_root> --name "<name>" --terminal <id>
```

On success it prints the path the starter was written to. On failure (a name already taken under
`/Applications`, a missing shipped icon, a platform this has no mechanic for) it exits non-zero with the
reason on stderr; relay that reason, do not retry silently with a different name.

### Step 4: tell the user

One sentence, in the user's writing language: what was created, where, and which terminal it opens.
On macOS that is an app under `/Applications`, reachable from Spotlight, Launchpad, or dragged to the
Dock from there. On Windows it is a shortcut on the Desktop. No further onboarding text, this is a
small, self-explanatory result.

## Sounds sensible, is wrong

| Rationalization | Reality |
|---|---|
| "The user already said no once during setup, I will not offer this again." | A "no" during setup is about that moment, not a standing refusal. Build it the moment they ask. |
| "I know this machine has Ghostty from earlier in the conversation, I can skip detection." | Run detection every time. What was installed five minutes ago is not guaranteed to still be, and a stale assumption produces an icon for an app that is not there. |
| "The vault is called `Zanmai-dev`, but the product is `Zanmai`, I will suggest the product name." | The default is the folder's own name, always. A hardcoded product name is wrong the moment two vaults exist on one machine (a private one and a work one, for example) and both get the same suggested name. |
| "Only Terminal is installed, I will still ask which terminal, options can't hurt." | A one-item list is not a choice. Use it and say so in the confirmation, do not ask. |

## Files

- `zanmai/system/scripts/zanmai.py` (`launcher detect-terminals`, `launcher create`): the mechanic.
- `zanmai/system/icons/app-icon.png`, `zanmai/system/icons/app-icon.ico`: the shipped icon source, macOS
  builds an `.icns` from the PNG at create-time via `sips`/`iconutil`, Windows uses the `.ico` directly.
- `zanmai/system/skills/setup/SKILL.md`: Step 3d offers this skill once, at the end of first-time setup.
