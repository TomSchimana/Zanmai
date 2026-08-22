[← Zanmai Documentation](index.md)

# When something does not work

The failures that actually happen, and what each one means.

## Ask first

Before working through anything below, describe the problem to Zanmai. It can read its own state, check what your machine has, and usually name the cause faster than you can look it up. That is what it is for.

## Nothing happens on the first start

If the greeting looks generic and no setup ran, the session did not recognise the vault. Say "run setup" and it starts. This is the one moment Zanmai has no safety net yet, because the guards it installs during setup only take effect once a session begins.

After setup, close that session and open a new one. Until you do, the guards are written but not loaded.

## Python is missing or the wrong one

Zanmai names the exact problem rather than failing quietly, including the case where a system pretends to have Python but does not, which happens on Windows. Follow the path it gives you, then say you are done and it continues.

Version 3.10 or newer is required. Some systems have several Pythons installed, which is why the invocation is stored during setup instead of guessed each time.

## Too many approval prompts

Zanmai runs its own engine for almost everything it files, indexes and checks, so in the strictest permission mode a session interrupts you a lot. Setup therefore writes `defaultMode: auto` into this vault's `.claude/settings.json`, which lets Claude Code judge commands itself instead of asking you each time. It applies to this folder only and leaves your global Claude Code settings untouched. The status line shows which mode is active, for example `⏵⏵ auto mode on`.

If you still get a prompt at every step, the setting has not taken effect yet. A mode is read when a session starts, so the setup session itself still runs in whatever mode you opened it with, and not every plan offers auto mode. Press `Shift+Tab` to cycle the mode by hand and pick accept edits if auto is not in the list. The same key is also the way back if you would rather approve each step yourself.

Two things are worth knowing. Zanmai's own protections do not depend on the mode, because they are checks that run on every write rather than questions put to you: a note without its required fields is still refused, the system folder still cannot be overwritten, and a snapshot is still taken before anything risky. And bypass mode is a different matter, it switches off far more than the prompts, so leave it alone unless you are working in a throwaway environment.

## A job stops and asks for a tool

This is intended. Prerequisites are checked before a specialist starts, so you find out at the beginning rather than halfway through a document. You get told what is missing, what it does for this particular job, and the one command that installs it.

Small helper libraries can be fetched on your go, into Zanmai's own corner of the vault, never into your system Python. Heavier programs are yours to install; Zanmai will not silently work around a missing one with a worse method.

## A document cannot be rendered

A set document needs a typesetting engine, which Zanmai fetches itself at first use, one self-contained file into its own working folder, and checks on a test document before it is used on yours. Nothing to install by hand. A web-page deliverable needs a Chromium-based browser, any of Chrome, Edge, Brave or Chromium itself; on a machine with only Safari you are told to install one, and Windows normally has Edge already.

An exact colour profile, bleed and crop marks for a commercial press run are not produced this way, and are named as a boundary rather than approximated.

## An update refuses to apply

Two cases stop on purpose. If your vault is a clone and Zanmai's own files were edited locally, the update refuses instead of overwriting those edits, and tells you which files. Either revert them or move what you want to keep into `zanmai/extensions`, which no update touches.

And a vault already ahead of the published version is never rolled back to an older one.

If an update applied but something is off afterwards, the snapshot taken beforehand is the way back, and every update is recorded in `zanmai/update-history.md`.

## A connected source is not reachable

A source only works on a machine where you configured it. On a different computer it is simply absent, and you are told that plainly rather than getting an invented answer. Secrets are never stored in the vault, so moving your notes to another machine never carries credentials with it, by design.

## An image or video looks wrong

Say so, and be specific about what is off. A rendered result is judged before delivery, but the taste call is yours. For a person, insist on seeing the reference frames before a paid render: a drifting face halfway through a clip is almost always a missing identity anchor rather than a bad prompt.

## Something was filed in the wrong place

Say where it should be. Moving material is a normal operation, links are updated with it, and a snapshot is taken first. Nothing about the original text changes.

## Related

- [Requirements and installation](install/index.md)
- [Keeping Zanmai up to date](updates.md)
- [Snapshots](snapshots.md)

---

[← Back to the documentation index](index.md)
