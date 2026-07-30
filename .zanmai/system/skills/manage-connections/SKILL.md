---
name: zanmai:connection
description: Overview and use of connections to sources outside the vault, whatever the host machine already exposes (an MCP server, a local CLI), plus setting one up where it is needed. Connections are Wong's domain: Steve dispatches Wong, which drives it as a conversation and guards its security. The user never types subcommands or slugs, they say what they want, Wong uses what the host exposes.
---

# connection

A connection is this vault reaching one source outside it, an MCP server or a local CLI. Where the host already exposes and authenticates the source, Zanmai just uses it; where a source must be set up, Wong establishes it and guards the security. Because the host exposes a source only once the user configured it there, that host configuration is the opt-in, no second gate. This skill is Wong's manual; Wong is gateway and security in one role.

## Who runs this, and how

`/zanmai:connection` (with or without extra words) reaches Steve, as does any natural request that needs an outside source ("what's in my calendar", "pull that wiki page"). The outside boundary is Wong's, so Steve dispatches Wong via the `Agent` tool with `subagent_type: "wong"`. Wong drives it as a conversation, the user speaks plainly, Wong translates; the user never types `scan` or a slug.

## Using a host source

1. **Vault first.** If the answer is inside, point there and stop.
2. If the host exposes the source, **use it** and answer in the user's language, no activation ceremony, the host configuration is the opt-in. A subagent reaches host MCP tools through the granted interface.
3. If the host does not expose it, say so plainly and set it up only when the task needs it, see credentials below. Wong cannot conjure a source the machine does not provide. An MCP is always registered project-locally for the current working directory, never globally and never inside the vault (wong.md hard rule 5), so it loads only for the session that needs it.

A read that should become a vault file goes back to Steve, who dispatches Hank; Wong writes no vault files. Setting one up includes one menu, read only or read and write; Wong configures what the user chose, never a level it picked for them, and puts every outgoing write to them first (wong.md hard rule 4).

## Credentials and security (Wong's second half)

Wong decides per connection: **(a)** if the source keeps its secret safely in its own config, it stays there and Wong holds nothing; **(b)** only if it cannot, Wong stores the secret in the OS keychain or an `.env` outside the vault (gitignored, `chmod 600`, masked). A secret never enters the vault, a commit or the chat, the vault holds a reference at most. Wong reviews each new connection for credential hygiene and least privilege.

## The engine (under the hood, never shown to the user)

`zanmai.py connection scan`, discovery of what the host exposes. That is the one command. Reading a source is a normal call to its MCP tool or CLI, listed or not. None of these words, paths or slugs appear in what the user sees.

## Plain language

Everything the user sees is their-language prose: no paths, file names, tool or server names, commands or state words. "Your calendar isn't set up on your machine yet, want me to help add it?", not a slug, not a command.

## Pointers

- `.zanmai/system/experts/wong/wong.md`: Wong's contract.
- `.zanmai/system/experts/steve/steve.md`: when Steve dispatches Wong.
- `.zanmai/system/operating-principles.md`: vault-first principle and the external boundary.
