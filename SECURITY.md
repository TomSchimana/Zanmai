# Security

## Reporting something

Use **GitHub's private vulnerability reporting** on this repository: Security → Report a vulnerability. That is the only channel, and no email address is published on purpose. Anything else that could be used as a support address is not access-controlled, and a working exploit is the last thing that should land there.

If private reporting is unavailable to you, open a public issue saying only that you have a security finding and asking for a private channel. Do not put the finding in it.

## What to expect

These are targets a small team works to, not a response guarantee.

- Acknowledgement within five working days.
- An assessment, with our view of severity and a rough fix window, within ten.
- Disclosure coordinated with you, and we aim to be public within ninety days of the report.

If it goes quiet for more than two weeks, ping the report thread. A published guarantee nobody is staffed to meet is worse than an honest target, so this file states the target.

## Supported versions

The `0.x` series is a developer preview. Only the newest published version is supported; the fix ships in a new version rather than as a patch to an older one.

## What Zanmai does over the network

Worth knowing before you look for something, because the surface is small on purpose.

- **A version check.** One HTTPS request per session to the repository named in `manifest.yaml` under `update_source`, fetching one version string. It sends nothing about you or your vault, fails silently offline, and prints a line only when something newer exists. Turn it off with `update_check: false` in that file.
- **An update, only when you ask for it.** `setup upgrade` fetches the release over HTTPS and replaces distribution files. It never writes to your notes, your profile, your extensions, your memory, your logs or your snapshots. Paths come out of the downloaded manifest, so they are treated as input: anything that does not resolve inside your vault aborts the whole update rather than being skipped quietly.
- **Nothing else, unless you wired it.** Research and outside sources reach the network only through a connection you set up yourself, per source, and only when a task needs it. There is no telemetry and no analytics.

## In scope

- Anything that lets a downloaded update, an extension or an imported file write outside the vault or into your own material.
- Anything that puts a credential into the vault, into a log, into a snapshot or into a chat reply.
- A check or a guard that reports success without having done its work. We treat that as a security bug rather than a cosmetic one, because a guarantee nobody can rely on is worse than none.

## Out of scope

- The machine's own security. Zanmai runs with your user's rights and does not sandbox itself.
- Tools you have installed and configured yourself, and services you have connected. Their security is theirs.
- Putting your vault in a shared or synced folder. That is supported and normal, and what it means is described in the documentation, but who can read that folder is your decision.

## Standing rules that block a release

- No credential in the repository, in a shipped file, or in an example.
- Secrets by reference only: the vault may hold the name of a keychain entry, never a value.
- Every release is verifiable: the version in the manifest matches the tag, and the file list matches what is on disk in both directions.

## Good-faith research

Test against a vault you own, with material you own. Do not touch anyone else's data, and give us a chance to fix something before you publish it. Work along those lines is welcome, and we will not come after you for it.
