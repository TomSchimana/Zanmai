[← Zanmai Documentation](index.md)

# Operating principles (background)

This is the rationale layer for `.zanmai/system/operating-principles.md` (the principle layer). Use this doc when the user asks why something works the way it does.

> The pages below use Zanmai's own vocabulary. If a word is new, [how the vault is organised](folder-architecture.md) defines them: theme and bundle, the note that carries a theme, the fields at the top of a note, links between notes, and slugs.

## The principles at a glance

The principle layer currently lists ten numbered principles.

1. **TL;DR before write.** For multi-file operations, return a TL;DR to the user in chat (structure tree, axis decision, counts, notable items), wait for approval, then execute.
2. **Source files are sacred.** Body verbatim, frontmatter migrates.
3. **Skills carry their own discipline.** Rules live in the skill file because that file is in context at invocation.
4. **Mechanic over memory.** Critical rules become scripts or hooks, not prose.
5. **Index and log everything written.** INDEX append plus activity-log append on every bundle write.
6. **Daily, Weekly and Monthly Notes.** Read freely, write only on the user's direct instruction.
7. **User-facing surfaces stay user-facing.** Distribution stays English, user-facing replies follow the user's language and address them personally rather than distantly, mechanics terminology does not leak.
8. **Checkbox conventions.** `- [ ]` is a user tool. The AI writes `- [ ]` only when the user's request directly calls for one (an actionable list, a concrete information gap). AI sets `@waiting` for non-today items, never sets priority markers. `due:` is set without confirmation when the user named a concrete date directly; fuzzy or implicit timing still goes through propose-then-confirm. AI-internal cross-session reminders live in `.zanmai/memory/general.md` Open Threads as plain bullets.
9. **Tools-existence is not usage-intent.** For ambiguous tool detection, ask once and persist the user's intent flag.
10. **Only tools that are present and agreed.** A missing capability is named with the one step that enables it, and the job stops there. No substitute assembled from whatever happens to be installed.

Principles 1 to 4 are the original foundation, each written after a concrete failure. Principles 5 to 10 layer on top: 5 covers index hygiene, 6 note-edit semantics, 7 language and surface boundaries, 8 task-marker conventions, 9 tool-detection semantics, 10 what happens when a tool is absent.

## Why each principle exists

### TL;DR before write

LLM agents routinely lose work when they start writing before confirming intent. An unprompted bulk write can wipe carefully-built user content with no rollback path. The TL;DR returned to the user in chat (structure tree showing where things would land, axis decision, counts, notable items) forces an explicit user yes before any destructive operation. The trade-off vs the older plan-file-in-vault approach: less ceremony, no `inbox/review/` file to read, but the proposal lives in the chat buffer rather than markdown. The audit trail after execute is the operation report under `.zanmai/logs/`, which is persistent regardless of chat compaction.

### Source files are sacred

The directive. A filing agent that applies a bundle template on top of an existing user file overwrites body text the user had written. Templates are for new bundles. Existing user-authored body is content the user owns. Only frontmatter may migrate to the current schema.

This rule is not enforced mechanically by hooks (a hook would have to know user-authored versus template-generated, which is harder than it sounds). It is enforced by skills (`import-bundle` Directive 4) and by definition-of-done checks.

### Skills carry their own discipline

Across stable AI-assisted PKM systems, the same pattern recurs: discipline lives in skill files (loaded into context at invocation), not in central instruction documents (which get forgotten).

The mechanic. A skill file is read into context at the moment it runs. General principles in a separate file are not. Putting the discipline in the skill means the discipline is visible exactly when it matters.

### Mechanic over memory

When a rule keeps failing despite being written down, it is a signal to move it into deterministic code. The `kind-required` hook refuses writes that lack required frontmatter. The hook does not require AI discipline. Prose did, and prose failed across multiple sessions. Snapshot is a script because the snapshot rule kept being skipped. Frontmatter validation is a hook. The next rule to mechanise is whichever one keeps failing.

### Index and log everything written

Two things must happen on every bundle write to keep the vault navigable across sessions. The bundle's `INDEX.md` gets a wikilink to the new file. `.zanmai/memory/activity-log.md` gets a one-line append. Without the INDEX, files become unreachable from the bundle truth file. Without the activity log, cross-session memory of what happened is lost.

### Daily, Weekly and Monthly Notes

These are the user's writing space when ZenNotes is configured to use them. Operations live in the `notes` skill, which checks `.zanmai/vault-config.md` first and routes writes through `zanmai.py notes daily`. The AI reads daily and weekly entries for context but never writes without an explicit per-edit yes. The privacy boundary is firm. Content does not graduate to `.zanmai/memory/general.md` or agent lessons unless the user explicitly says so.

### User-facing surfaces stay user-facing

The distribution ships in English (skill files, contracts, hooks, scripts). User-facing output (chat replies, generated content in `inbox/`) follows the user's language as set in `.zanmai/user.md`. Mechanics terminology does not leak into replies unless the user asked about it.

### ZenNotes checkbox conventions

`- [ ]` and `- [x]` are Markdown standard, editor-neutral. When the user is on ZenNotes, the Task view aggregates them by inline markers (`@waiting`, `due:`, `!priority`, `#tag`); other editors may handle markers differently. `- [ ]` is a user tool. The AI writes `- [ ]` only when the user's request directly calls for one (an actionable list to tick through, a concrete information gap with a user-driven trigger). The default in any AI output is not `- [ ]`. Agent-neutral rule: Reed, Hank, Wong and Steve all follow it. On AI-written checkboxes, `@waiting` keeps non-today items out of the ZenNotes Today bucket; priority markers are never set by AI; `due:`-dates only after explicit user confirmation. AI-internal cross-session reminders go into `.zanmai/memory/general.md` under "Open threads" as plain bullets.

### Tools-existence is not usage-intent

Detecting that a tool is installed does not mean the user wants it active for this vault. Setup distinguishes binary-on-disk from intended-for-this-vault by asking once when the signal is ambiguous, and persisting the answer as a flag in `.zanmai/user.md`. Subsequent runs read the flag, not the binary.

### Only tools that are present and agreed

The failure this prevents is the helpful-looking workaround. A job that needs a renderer, a media tool or a connected source and does not find it used to improvise: a hand-assembled PDF, a different app pressed into service, a plausible answer with no source behind it. That produces work the user cannot trust and cannot tell apart from the real thing.

So the rule is a stop, not a fallback. The capability is named in plain language, with what it does for this particular job and the one step that enables it, and the job halts there. Zanmai is allowed to say no. Paired with the prerequisite check before dispatch, this means a job either runs properly or does not start.

## When not to apply them

The principles bias toward caution. For trivial operations (single-line edit in response to a direct user instruction, reading a file, opening a file in ZenNotes via `zn open <path>`), they do not all apply. Plan-before-write does not apply to trivial writes. Source-files-sacred always applies. Skills-carry-discipline is irrelevant when no skill exists. Mechanic-over-memory is a design observation, not a per-operation rule.

---

[← Back to the documentation index](index.md)
