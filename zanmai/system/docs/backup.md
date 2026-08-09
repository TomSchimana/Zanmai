[← Zanmai Documentation](index.md)

# Backup, and keeping the vault in a synced folder

Your vault is a folder. Putting it inside iCloud Drive, OneDrive, Dropbox, Nextcloud or Google Drive is the simplest backup there is, and it is a normal way to run Zanmai. Nothing here argues against it. Three things are worth setting up once.

## One: keep three things out of the copy

Most of the vault should travel. Three parts should not.

- **`runtime`**, inside the system folder. This is a Python environment Zanmai installs on demand, plus a record of which tools this particular computer has. Copied to a second machine it claims tools that are not installed there, and restored onto a different platform it is an environment built for the wrong one.
- **`work`**, also inside the system folder. Scratch space for a job in progress. It belongs to the machine doing the job.
- **`history`**. The record of every snapshot ever taken. It is a repository, and a repository being written by two machines through a sync client is a known way to break one. It is also the one part of the vault that can be rebuilt from nothing, so leaving it out of the sync costs you the old states and no current material.

Everything else, your notes, your profile, your memory, your design values, your logs, is worth having in the copy.

How you exclude them depends on the service, and only two of the five let you do it with a file:

| Service | How |
|---|---|
| Dropbox | add the paths to a `.dropboxignore` file at the top of your Dropbox folder |
| iCloud Drive | rename the folder so it ends in `.nosync`, or keep the vault outside iCloud |
| OneDrive | Settings → Account → Choose folders, and untick them |
| Nextcloud | Settings → General → Edit ignored files |
| Google Drive | Preferences, and untick the folders |

`setup validate` tells you which service it found and which of the three paths currently exist, so you can go and exclude exactly those.

## Two: conflict copies

When two things write the same file at once, every sync client makes a second file with something like *(conflicted copy)* in the name. That can happen even with one computer, because building a document writes hundreds of files while the client is still uploading the last batch.

A duplicate like that inside your notes is a real problem: Zanmai's first rule is that a fact exists once and everything else links to it. Two files, one of them stale, breaks the thing links are for. `setup validate` looks for them and fails if it finds any in your notes, so you can delete the loser rather than discovering it months later.

## Three: what a backup is not

A synced folder protects you from a dead disk. It does not protect you from a bad edit, because that syncs too, immediately.

That is what snapshots are for, and it is why the history is worth keeping out of the sync: a record taken before anything risky, sitting on the machine, restorable one file at a time. [Snapshots and going back](snapshots.md) covers them.

## And who can read it

A synced folder is as private as the account behind it. In a company cloud, that usually includes whoever administers the tenant. Nothing in Zanmai leaves your machine on its own, but a folder you have deliberately put in a shared service is shared, and that includes your session logs and your contacts. Worth a moment's thought about which vault lives where. It is your decision, and Zanmai does not make it for you.

## Related

- [Snapshots and going back](snapshots.md)
- [Folder architecture](folder-architecture.md), what each folder is for
- [Your editor](editors.md), reading the same vault on a phone
