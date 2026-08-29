[← Zanmai Documentation](index.md)

# Keeping Zanmai up to date

How Zanmai moves to a newer version without touching what is yours.

## The short version

Ask Zanmai to update, or wait until it mentions that a new version is out. It shows you what would change, takes a snapshot, and only then applies it. Your notes, your profile, your memory and your extensions are never part of an update. Only Zanmai's own files are replaced.

## Whichever way you got it

It makes no difference whether you cloned the repository or downloaded and unpacked an archive.

- **A clone** is updated through git, fast-forwarded from the same place you cloned it from. That keeps it a clean clone, so your own `git pull` keeps working afterwards.
- **An unpacked copy** has the new files fetched over HTTPS and written in place. No git, no remote, nothing to set up.

Either way only the files listed as distribution files in `zanmai/system/manifest.yaml` are written, and the paths listed as user-immune are left alone.

## If you update by hand

You can run `git pull` yourself. Nothing breaks: the files that carry your content are excluded from version control, so they are invisible to git and cannot be overwritten or accidentally committed.

The one thing a manual pull cannot do is refresh the host-side configuration, the specialist adapters and the settings that Claude Code reads. Zanmai notices at the next session start that the version changed and does that itself, silently. So updating by hand, letting Zanmai do it, or mixing the two all end in the same place.

## When the new version actually takes effect

The files are in place as soon as the update is applied, and most of it works immediately. The specialists are the exception: Claude Code reads their instructions when a session opens, so anything an update changed about how a specialist works applies from your next session, not from your next sentence. That is worth knowing when an update says it fixed something and the very next run still behaves the old way. Close the session and open a new one.

## When Zanmai asks

Once a day at most, at session start, Zanmai quietly checks whether a newer version exists. If so it offers the update once, in a single line, and drops the subject for that session if you decline. The check has a short timeout and never delays your session.

## If something goes wrong

The snapshot taken before the update is the way back. A failed check after applying triggers a restore from it, and every update, restore and deletion is recorded in `zanmai/update-history.md`.

Two cases stop an update instead of forcing it. A clone with local edits to Zanmai's own files refuses to fast-forward, and you are told which files those are. And a vault that is ahead of the source is never *offered* an older version.

## Going to a particular version

Never offered is not the same as impossible. When a version turns out to be wrong for you, say which one you want:

```
zanmai.py setup upgrade --to <version>
```

It goes there whether that is forwards or backwards, takes a snapshot first, and says out loud when it is going back. The version you are leaving is reachable the same way, so this is a step you can undo. The automatic offer keeps its rule and never moves you backwards on its own.

Nothing about a version change can leave the vault unable to help you with it. A guard named in the host config but missing from the version now installed is treated as silence rather than as a refusal, and what gets wired in is read from what the installed script can actually run. Without that pair, a step backwards would refuse every command, including the one that would undo it.

---

[← Back to the documentation index](index.md)
