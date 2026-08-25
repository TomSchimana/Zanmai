[← Zanmai Documentation](index.md)

# Hooks

> The pages below use Zanmai's own vocabulary. If a word is new, [how the vault is organised](folder-architecture.md) defines them: theme and bundle, the note that carries a theme, the fields at the top of a note, links between notes, and slugs.

## What

Zanmai wires eight Claude Code hooks via `.claude/settings.json`. Each hook is a subcommand of the single CLI: `zanmai.py hook <name>`. They are deterministic gates that run on tool calls or on conversation events.

- `zanmai.py hook checkbox-guard` (PreToolUse Write|Edit): refuses a task line that turns up inside an ordinary write. Ask for something to go on a list and it is written, through the one command meant for it (`task add`, `task done`); what this hook stops is a box arriving as a side effect of editing a file, which is how Zanmai's own reminders used to end up on your lists. It compares the task lines before and after the write and refuses anything that changes them, so editing the prose next to a task list is normal work.
- `zanmai.py hook prose-guard` (PreToolUse Write|Edit): refuses a dash used as sentence punctuation in prose Zanmai wrote itself. It is the most recognisable machine-made construction and the house style bans it first; the rule stood in five files of the distribution and a produced document still went out with 21 of them. Your own writing is never touched: the hook binds only where the file's frontmatter says the AI produced the content, and it compares the lines before and after, so moving, importing or re-saving your material passes untouched. A hyphen inside a compound word and a number range keep their dash. The refusal names the lines and says what to do instead, which is to finish the thought or split it into two sentences. `zanmai.py prose check --text <draft>` runs the identical scan on a draft before the write, always exit 0; the `write` skill calls it on every AI-authored draft, so the hook itself has nothing left to refuse in normal use.
- `zanmai.py hook delete-guard` (PreToolUse Bash): refuses a command that would remove or empty a file. Nothing is deleted, it goes to the trash and comes back.
- `zanmai.py hook library-check-guard` (PreToolUse Bash): refuses to save a `.pptx` into a `doing/<slug>/` bundle until `slide-library.py check <library> --task <slug>` has run for that bundle at least once. The `powerpoint` skill's rule that a slide is matched or adapted from the brand's own material before it is composed from scratch lived only as prose, and a live build skipped it twice in one afternoon before it was caught by hand, which is where that run's whole cost went. The check does not judge whether composing was the right call, it only proves the library was looked at first.
- `zanmai.py hook kind-required` (PreToolUse Write|Edit): refuses bundle writes that lack valid `kind:` and `slug:` frontmatter.
- `zanmai.py hook permission-guard` (PreToolUse Write|Edit): refuses writes to never-do paths (`zanmai/system/`, `zanmai/user.md`, `archive/`, `trash/`, `zanmai/history/`).
- `zanmai.py hook dispatch-guard` (PreToolUse Agent): puts a specialist's job into the background when it was about to run in the mode that holds the whole conversation until the job is finished. A specialist's work runs for many minutes, and in that mode nothing you write gets an answer for the duration. It corrects the call rather than rejecting it, so you never see an error for something that is simply put right on the way through. A specialist that pulls in a second one is exempt, because it does need that answer inside its own step.
- `zanmai.py hook index-consistency` (PostToolUse Write|Edit): emits a stderr warning when a new bundle file is not referenced by the bundle's `INDEX.md`.
- `zanmai.py hook session-start` (SessionStart): prepares the briefing context for Steve's first reply (preferred address, language, last-session-end marker, recent journal entries within a fixed window, theme signals, inline briefing) so the greet needs zero further tool calls. It also builds the greet list itself: the open items, chosen by urgency, grouped by time, numbered and capped at six lines with the remainder as a count. That selection is done here rather than left to the reply, because the rules for it were written out plainly three times and broke in a live session each time. It also keeps the search index current: it compares the vault against the index by path and modification time and rebuilds if anything changed, including edits the user made in their editor, so a fresh session always searches on an up-to-date index. On an uninitialised vault (system tree present, no `user.md`) it instead injects a hard directive to read the setup skill and run it before any greeting, so a fresh session drives setup rather than sliding into a generic reply. Two more things happen here: if the distribution files carry a version the host config was not built for, for example because the user pulled the repository by hand, the adapters and settings are quietly brought in line; and at most once a day the update source is asked whether a newer version exists, with a short timeout and the answer cached, so the offer can be made without ever delaying a session.

## Why

Operating principles are advisory, hooks are deterministic. These guard failure modes that are either destructive, corrupting, or a repeat offender against a standing rule: a task appearing on one of your lists that you never asked for, something being deleted, invalid frontmatter, writes into the distribution area, bundle drift (files written without INDEX update), a job that silently locks the conversation for an hour, a cold greet without loaded context, and a deck composed from scratch without a check against the brand's own material first. Each is cheap and deterministic, a rule that does not need to be remembered.

The last one on that list is the reason the checkbox rule became a hook rather than a sentence: it had been a sentence, in six places at once, and it did not hold. A rule written down again after it failed is not a stronger rule, it is the same rule with more words. When one keeps failing, it moves into machinery or it stops being claimed.

There is deliberately no gate on external (MCP) tool calls. The host only exposes a server as a tool once the user has configured it there, that host configuration is the opt-in, so a second consent gate would be redundant.

Cosmetic or self-correcting conventions (path phrasing in chat, which app opens a note) are left to the contracts and the model, not to a hook, a hook that forces an extra turn to fix a low-harm slip costs more than the slip. A markdown task is not in that group and has a hook of its own: a task you never asked for, read back to you a week later as your own open point, is not a slip that corrects itself.

## How to use

The hooks are wired automatically by `zanmai.py setup init`. The user does not invoke them, Claude Code does. From the user's perspective: malformed writes get refused, system paths cannot be overwritten by accident, missing INDEX entries get surfaced as a console hint, and the greet starts with the right name and context already loaded.

If a hook fires and the user disagrees with the verdict, the right move is to fix the underlying issue (add frontmatter, write to a different path, append to INDEX), not to bypass the hook. Bypassing requires editing `.claude/settings.json` and removing the hook entry, which is allowed but should be a deliberate user choice.

## When not to use

The Write and Edit hooks do not run on Read. A determined user can write to `zanmai/system/` via Bash, sidestepping `permission-guard`. The hooks are guardrails against AI accidents, not against deliberate user action.

## Files

- `zanmai/system/scripts/zanmai.py` (`hook` subcommand group): every hook is a subcommand of the single CLI.
- `.claude/settings.json`: hook wiring, plus `autoMemoryEnabled: false` and `permissions.defaultMode: auto` for this vault (generated by `zanmai.py setup init`). The permission mode is a comfort setting and no part of the guards; see [troubleshooting](troubleshooting.md).

---

[← Back to the documentation index](index.md)
