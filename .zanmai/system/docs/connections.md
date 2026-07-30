[← Zanmai Documentation](index.md)

# Connections

## What

A connection is this vault reaching one source outside it, an MCP server or a local CLI. Connections are how Wong, the connections and security expert, reaches beyond the vault boundary.

The guiding principle: **Zanmai uses interfaces, it does not own heavy integrations.** Where the host already exposes and authenticates a source (its MCP configuration, the user's shell login), Zanmai just calls it, no key held, no OAuth run, no webhook received. Where a source must be set up and cannot keep its own secret safely, Wong establishes it and stores the secret only in the OS keychain or an `.env` outside the vault, never in the vault, a commit or the chat. Because the host exposes a source only once the user configured it, that host configuration is the opt-in: no second consent gate. Where Wong does set one up, the user picks the access level in one menu, read only or read and write.

## Why

Keeping Zanmai thin and safe. Owning heavy integrations would mean owning token refresh, retries and a permanent security surface, a different, much heavier product. By preferring host-authenticated interfaces, and holding a secret only when a source cannot itself and only outside the vault, the burden stays minimal and Zanmai stays environment-agnostic: every user brings their own MCP servers and CLIs. Wong is gateway and security in one role, so every new connection gets a credential-hygiene and least-privilege check as it is made.

## How to use

You do not type commands. You say what you want, "what's in my calendar this week", "use my wiki", and Wong drives it: if the host exposes that source, Wong uses it and answers; if not, Wong says so and sets it up only when the task needs it. A discovery scan lets Wong show you what the machine exposes.

Reading is the everyday case: a connection reads the source and answers in chat, nothing is copied into your files by Wong. A read that should become a note goes to Hank. If you chose read and write when it was set up, Zanmai can also write back, and every write is shown to you before it goes out. Continuous sync is out of scope; that would be a separate extension, not the core.

Connections work the same on macOS, Linux and Windows. A source not reachable on the current machine says so plainly instead of failing.

## When not to use

If the answer is already in the vault, no connection is involved, Wong points at the note. And a connection is not storage: it is using a host source, not a copy of its content.

## Files

- `.zanmai/connections/`: update-immune home for anything Wong records about an established connection (a reference, never a secret).
- `.zanmai/system/skills/manage-connections/SKILL.md`: the workflow Wong follows.
- `.zanmai/system/experts/wong/wong.md`: Wong's contract.
- `.zanmai/system/scripts/zanmai.py` (`connection scan`): the discovery command Wong runs under the hood.

---

[← Back to the documentation index](index.md)
