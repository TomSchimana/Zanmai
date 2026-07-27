[← Zanmai Documentation](index.md)

# Keeping Zanmai up to date

How Zanmai moves to a newer version without touching what is yours.

## The short version

Ask Zanmai to update, or wait until it mentions that a new version is out. It shows you what would change, takes a snapshot, and only then applies it. Your notes, your profile, your memory and your extensions are never part of an update. Only Zanmai's own files are replaced.

## Whichever way you got it

It makes no difference whether you cloned the repository or downloaded and unpacked an archive.

- **A clone** is updated through git, fast-forwarded from the same place you cloned it from. That keeps it a clean clone, so your own `git pull` keeps working afterwards.
- **An unpacked copy** has the new files fetched over HTTPS and written in place. No git, no remote, nothing to set up.

Either way only the files listed as distribution files in `.zanmai/system/manifest.yaml` are written, and the paths listed as user-immune are left alone.

## If you update by hand

You can run `git pull` yourself. Nothing breaks: the files that carry your content are excluded from version control, so they are invisible to git and cannot be overwritten or accidentally committed.

The one thing a manual pull cannot do is refresh the host-side configuration, the specialist adapters and the settings that Claude Code reads. Zanmai notices at the next session start that the version changed and does that itself, silently. So updating by hand, letting Zanmai do it, or mixing the two all end in the same place.

## When Zanmai asks

Once a day at most, at session start, Zanmai quietly checks whether a newer version exists. If so it offers the update once, in a single line, and drops the subject for that session if you decline. The check has a short timeout and never delays your session.

## If something goes wrong

The snapshot taken before the update is the way back. A failed check after applying triggers a restore from it, and every update, restore and deletion is recorded in `.zanmai/update-history.md`.

Two cases stop an update instead of forcing it. A clone with local edits to Zanmai's own files refuses to fast-forward, and you are told which files those are. And a vault that is ahead of the source is never rolled back to an older version.

---

[← Back to the documentation index](index.md)
