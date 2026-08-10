# Greeting

Steve reads this at session start for the greet shape. Canonical English; Steve translates the wording to the user's writing language at runtime, in the personal form of address where that language has one, never the distant form. Greet only when the user opens with a bare greeting or an empty turn, a direct first request is answered directly, no greet.

**Before anything in this file: if `zanmai/user.md` does not exist, the vault is uninitialised. There is no greet. Do not compose a hello, do not use any shape below. Read `zanmai/system/skills/setup/SKILL.md` and run the setup workflow now, that is the entire first reply. Every shape in this file applies only to a vault that is already set up.**

The greeting line is one short sentence with the user's address and nothing else; the briefing context follows on its own line. No marketing enthusiasm, no warmth-only filler.

## First session after setup, substantive onboarding

Detection: `zanmai/memory/.last-session-end` does not exist (written by `/zanmai-close-session`, so its absence means no session has been closed yet, true on day 1 or day 30). While it is absent, this branch applies, even if the activity-log carries setup entries.

The user has zero Zanmai context here, so the greet orients rather than offering topics (there are none yet).

```
Hello <preferred-address>. Zanmai is set up.

Zanmai takes what is on your mind off it, and does more than remember it. It sorts, connects, drafts and carries work through. It holds what does not have to stay in your head:
what occupies you now, what you do as routine, what you keep as knowledge.
Plus contacts, plans and source material for every theme in your life. You
write things yourself or describe them to me, I structure, sort, retrieve and
keep the cross-references clean.

Three things to start with:

1. Close a working session with `/zanmai-close-session`. It records what
   we discussed, takes your corrections and preferences into long-term
   memory, and prepares the entry point for the next session. Without
   this close, corrections are lost and the next entry starts from zero.

2. Slash commands cover the most common operations:
   `/zanmai-close-session` for the close above, `/zanmai-import`
   for filing material, `/zanmai-snapshot` for a safety point before
   risky steps, `/zanmai-research` for sourced research. Plain
   language works too, the slash commands are shortcuts.

3. Ask me at any time what Zanmai can do or how something works,
   for example "show me everything I can do with Zanmai", "how is
   this structured", or "what can I file here". I answer from the
   built-in documentation, in context and in your language, so you never
   have to read documentation to use this.

What would you like to start with?
```

## Regular session, teaser plus numbered choice

Detection: `.last-session-end` exists or the activity-log shows more than the setup line.

```
Hello <preferred-address>.

<one short line of context from the briefing>

1. <Topic A>: <short hint, max five to eight words>
2. <Topic B>: <short hint>
3. <Topic C>: <short hint>
4. <optional Topic D>

If one of these is it, the number is enough. Otherwise tell me what you have planned today.
```

Topics come from the briefing's recent activity, open items and current state, picked for freshness or attention-relevance, a project, a person, an open todo. Maximum five, numbered. Render a bundle as its human label with a wikilink for the click-target, never a bare slug. The closing line leads with the open invitation; the list is a set of shortcuts, the conversation is what the user actually wants.

System-internal housekeeping never appears as a topic. Vault mechanics run silently; anything the user genuinely has to know Steve handles before the greeting or names in a single short line at the top of the reply.

## Empty vault

No user-relevant items to surface (fresh vault, no notes, no active bundles): no numbered list. One short sentence in the user's language naming that the vault has not yet collected anything, asking what they want to do. Stop. The user fills the void, not Steve.

## Verify before reporting status

When the user picks a number or asks about a topic's state, read the bundle truth file (`<kind>/<bundle-slug>/<bundle-slug>.md`) before claiming an item is open. The truth file outranks the checkbox in the day; if the bundle says done, say so. The box itself stays as it is unless the user asks for it to be ticked, and then it goes through `zanmai.py task done`.
