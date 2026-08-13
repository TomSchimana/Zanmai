---
name: zanmai:connection
description: Overview and use of connections to sources outside the vault, whatever the host machine already exposes (an MCP server, a local CLI), plus setting one up where it is needed. Connections are Wong's domain: Steve dispatches Wong, which drives it as a conversation and guards its security. The user never types subcommands or slugs, they say what they want, Wong uses what the host exposes.
---

# connection

A connection is this vault reaching one source outside it, an MCP server or a local CLI. Where the host already exposes and authenticates the source, Zanmai just uses it; where a source must be set up, Wong establishes it and guards the security. Because the host exposes a source only once the user configured it there, that host configuration is the opt-in, no second gate. This skill is Wong's manual; Wong is gateway and security in one role.

## Who runs this, and how

`/zanmai-connection` (with or without extra words) reaches Steve, as does any natural request that needs an outside source ("what's in my calendar", "pull that wiki page"). The outside boundary is Wong's, so Steve dispatches Wong via the `Agent` tool with `subagent_type: "wong"`. Wong drives it as a conversation, the user speaks plainly, Wong translates; the user never types `scan` or a slug.

## Using a host source

1. **Vault first.** If the answer is inside, point there and stop.
2. If the host exposes the source, **use it** and answer in the user's language, no activation ceremony, the host configuration is the opt-in. A subagent reaches host MCP tools through the granted interface.
3. If the host does not expose it here, say so plainly and set it up only when the task needs it, see credentials below. A source the scan reports as configured for another folder is an access the user already has and that works: reuse that configuration for this vault instead of establishing a second one. Wong cannot conjure a source the machine does not provide. An MCP is always registered project-locally for the current working directory, never globally and never inside the vault (wong.md hard rule 5), so it loads only for the session that needs it, and it takes effect in a new session, so the restart is named and nothing is reported as connected before it.

A read that should become a vault file goes back to Steve, who dispatches Hank; Wong writes no vault files. Setting one up includes one menu, read only or read and write; Wong configures what the user chose, never a level it picked for them, and puts every outgoing write to them first (wong.md hard rule 4).

## A browser OAuth round trip never goes through a dispatched agent

Some sources authorise this way: an authorise call returns a login URL, the user signs in and confirms
in their browser, and a callback URL comes back with a code Wong or Loki completes the login with.
That pending login is bound to the live connection instance on the source's own server, not durably to
the code or state alone, so it dies the moment the agent that started it ends, whether or not the
answer is relayed back later. This holds even for a run parked the proper way (operating-principles
§12): a parked run is still its own process, separate from the connection the pending login is bound
to, so parking does not rescue it either. The only path that keeps the same connection alive across the
wait for the user's reply is one with no dispatch boundary in it at all: Steve makes both calls itself,
in its own ongoing conversation with the user, never handed to Wong or any other expert as a background
agent for this specific exchange. Establishing the connection (registration, scope, credential storage)
stays Wong's as usual; only this one authorise-then-complete pair, when it needs the user's browser, is
kept out of dispatch.

## Credentials and security (Wong's second half)

Wong decides per connection: **(a)** if the source keeps its secret safely in its own config, it stays there and Wong holds nothing; **(b)** only if it cannot, Wong stores the secret in the OS keychain or an `.env` outside the vault (gitignored, `chmod 600`, masked). A secret never enters the vault, a commit or the chat, the vault holds a reference at most. Wong reviews each new connection for credential hygiene and least privilege.

## The engine (under the hood, never shown to the user)

`zanmai.py connection scan`, discovery of what the host exposes. That is the one command. Reading a source is a normal call to its MCP tool or CLI, listed or not. None of these words, paths or slugs appear in what the user sees.

## Plain language

Everything the user sees is their-language prose: no paths, file names, tool or server names, commands or state words. "Your calendar isn't set up on your machine yet, want me to help add it?", not a slug, not a command.

## Pointers

- `zanmai/system/experts/wong/wong.md`: Wong's contract.
- `zanmai/system/experts/steve/steve.md`: when Steve dispatches Wong.
- `zanmai/system/operating-principles.md`: vault-first principle and the external boundary.
