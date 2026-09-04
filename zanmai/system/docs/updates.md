[← Zanmai Documentation](index.md)

# Keeping Zanmai up to date

**Read this when:** a new version exists, or an update has to be applied, checked or undone.

Ask Zanmai to update, or wait until it says a new version is out. It shows you what would change, takes a snapshot, and only then replaces its own files. Everything you made stays untouched.

## The short version

Ask Zanmai to update, or wait until it mentions that a new version is out. It shows you what would change, takes a snapshot, and only then applies it. Your notes, your profile, your memory and your extensions are never part of an update. Only Zanmai's own files are replaced.

## Whichever way you got it

It makes no difference whether you cloned the repository or downloaded and unpacked an archive.

- **A clone** is updated through git, fast-forwarded from the same place you cloned it from. That keeps it a clean clone, so your own `git pull` keeps working afterwards.
- **An unpacked copy** has the new files fetched over HTTPS and written in place. No git, no remote, nothing to set up.

Either way only Zanmai's own files are written. Which ones those are is fixed in the version you are installing, not worked out at the time, and everything else is left alone.

## If you update by hand

You can run `git pull` yourself. Nothing breaks: the files that carry your content are excluded from version control, so they are invisible to git and cannot be overwritten or accidentally committed.

The one thing a manual pull cannot do is refresh the host-side configuration, the specialist adapters and the settings that Claude Code reads. Zanmai notices at the next session start that the version changed and does that itself, silently. So updating by hand, letting Zanmai do it, or mixing the two all end in the same place.

## When an update changes the shape of your space

Until version 1.0 the areas can still change: a folder can be renamed, two can become one. An
update that does this brings the move with it and runs it on your space, so that after the update
you are in the new shape and not in a half-old one. Your files go with it, and nothing is thrown
away. Where a name exists on both sides, the two folders are joined; where two files carry one
name, the arriving one stands beside the other under a counter rather than over it.

A move reaches everything that points at a path, not only the folders: the search index, the
routing table, the sentences in your notes that name a place. One thing it deliberately leaves
alone is any record of what happened. The activity log, the operation reports and your journal say
what was true on a day, and on that day the folder really was called what it was called.

Each of these steps is recorded with a revision. If a step turns out to have been wrong, the
correction carries a higher revision and runs again on every space, including the ones that already
took the faulty version. That is why a step is written so that running it twice changes nothing.

## When the new version actually takes effect

The files are in place as soon as the update is applied, and most of it works immediately. The specialists are the exception: Claude Code reads their instructions when a session opens, so anything an update changed about how a specialist works applies from your next session, not from your next sentence. That is worth knowing when an update says it fixed something and the very next run still behaves the old way. Close the session and open a new one.

## When Zanmai asks

Once a day at most, at session start, Zanmai quietly checks whether a newer version exists. If so it offers the update once, in a single line, and drops the subject for that session if you decline. The check has a short timeout and never delays your session.

**Turning it off.** Put `update_check: false` into `zanmai/user.md` and nothing reaches the network on its own any more. That file is yours and no update touches it, so the decision holds from then on. Switching the check off does not lock you out of updating: ask for one and it runs.

## Updating when the version says there is nothing to do

Two situations look like "you are current" and are not: a release re-cut under the same number carries different files, and an update that broke halfway leaves a space whose version claims more than its files hold. For both, say you want it applied again anyway: the files are fetched and written a second time instead of the comparison deciding there is nothing to do. A snapshot is taken first, like every other update.

## If something goes wrong

The snapshot taken before the update is the way back. A failed check after applying triggers a restore from it, and every update, restore and deletion is recorded in `zanmai/update-history.md`.

Two cases stop an update instead of forcing it. A clone with local edits to Zanmai's own files refuses to fast-forward, and you are told which files those are. And a space that is ahead of the source is never *offered* an older version.

## Going to a particular version

Never offered is not the same as impossible. When a version turns out to be wrong for you, say which one you want and it goes there whether that is forwards or backwards, takes a snapshot first, and says out loud when it is going back. The version you are leaving is reachable the same way, so this is a step you can undo. The automatic offer keeps its rule and never moves you backwards on its own.

## Updating from a source you name

An update normally comes from the published release. It can also come from a folder, an archive or a URL you name:

```
zanmai.py setup upgrade --from <path or URL>
```

Two situations call for it. A version that is not published yet has to be tried in a real space before it goes out, and a fix sometimes has to reach a space before there is a release to carry it. Both used to mean copying files in by hand, which proves that the copy worked and nothing about the update.

The source has to carry a `zanmai/system/VERSION` and a manifest; the version is read from there, not from what you type. A snapshot is taken every time, forwards or backwards, because a source you name carries no promise about what is in it. Everything else is the ordinary update: the same files are replaced, the same ones are withdrawn, your own material is untouched.

Nothing about a version change can leave the space unable to help you with it. A guard named in the host config but missing from the version now installed is treated as silence rather than as a refusal, and what gets wired in is read from what the installed script can actually run. Without that pair, a step backwards would refuse every command, including the one that would undo it.

## Related

- [Snapshots and going back](snapshots.md), the way back from an update
- [How Zanmai grows](growing.md), what an update replaces and what it leaves alone

---

[← Back to the documentation index](index.md)
