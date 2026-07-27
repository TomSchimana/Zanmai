[← Zanmai Documentation](index.md)

# Skills and scripts

> The pages below use Zanmai's own vocabulary. If a word is new, [how the vault is organised](folder-architecture.md) defines them: theme and bundle, the note that carries a theme, the fields at the top of a note, links between notes, and slugs.

## What

Zanmai's operational layer is split into two kinds of artefact.

- Skills under `.zanmai/system/skills/<name>/SKILL.md`: markdown files with frontmatter (`name`, `description`), workflow steps, "Rationalizations to resist", "Red flags". Loaded into context when triggered.
- Scripts under `.zanmai/system/scripts/`: Python files that perform deterministic state changes (folder creation, file copy, validation).

Skills are the operational interface. Scripts are the mechanic the skills call.

## Why this split

Recurring discipline lives in skills because the skill file is in context at invocation. Critical mechanics live in scripts because scripts do not require AI discipline at all.

Putting discipline in general instruction files leads to it being forgotten across sessions. The fix is structural. Anything that needs to happen reliably becomes a skill or a script, not prose in a central document.

## How to use

When the user describes a recurring operation:

1. If a skill exists, invoke it. The skill carries its workflow plus the discipline.
2. If no skill exists and the operation is recurring, propose adding a skill rather than improvising prose.
3. If the operation must be deterministic (no AI judgement allowed), the right home is a script, not a skill. Snapshot is a script for this reason.

When writing a skill, the shape is:

- Frontmatter with `name` and a `description` that captures trigger phrasing.
- An iron-rule section with the non-negotiables.
- "When to use" and "When not to use".
- "The workflow", numbered steps.
- "Rationalizations to resist", a table of plausible-sounding shortcuts and why they are wrong.
- "Red flags, stop and recheck", signs that the skill is being misapplied.
- "Files", which other artefacts the skill touches.

## When not to use

- One-off operations (renaming a single file, answering a single question) do not become skills. They live in conversation.
- Implementation details (how to parse YAML frontmatter) live in scripts, not skills.
- User preferences are not skills, they live in `.zanmai/user.md`.

## The current set

The current distribution ships eighteen skills, two scripts (`zanmai.py` and a standalone `image-edit.py`), four hooks and seven subagents (plus Steve, the main-loop concierge).

Skills under `.zanmai/system/skills/<name>/SKILL.md`:

- `setup`: first-time install, invoked by Steve when `.zanmai/user.md` is missing. No slash command (too risky to trigger by accident, invoked by reading the SKILL.md and following the workflow). A freshly copied vault ships no `.claude/`: it holds only `.zanmai/`, `CLAUDE.md` and `README.md`. `init` creates `user.md`, the folder skeleton and `.claude/settings.json` at the end of the guided dialogue, with the hook script path rooted at `$CLAUDE_PROJECT_DIR` so it survives the vault being moved. The safety hooks become live when the user reopens the vault after setup, so the one setup dialogue before `init` runs with no hook active and relies on the canonical, em-dash-free text for its voice.
- `snapshot`: slash command `/zanmai:snapshot`.
- `close-session`: slash command `/zanmai:close-session`.
- `import-bundle`: slash command `/zanmai:import` (short user-facing name, the folder keeps the longer descriptive name internally).
- `classify-note`: internal helper invoked by `import-bundle`. No slash command (too abstract for direct user trigger).
- `research`: slash command `/zanmai:research` (alias `/zanmai:recherche`). Explicit Reed-trigger that removes the natural-language guesswork. Steve runs the pre-dispatch brief mandatorily per CLAUDE.md Hard Rule 9, then dispatches Reed via the `Agent` tool.
- `journal`: slash command `/zanmai:journal <text>`. Captures the text after the command verbatim into today's Daily Note (or this week's Weekly or this month's Monthly when named). Steve runs the skill inline, capture is lightweight, no subagent, no confirmation gate. Also writes the automatic period rollups (weekly from the week's dailies, monthly from the month's weeklies). Conditional on the ZenNotes periodic-notes feature being enabled.
- `notes`: internal, Daily/Weekly/Monthly Notes operations on direct user instruction, capture a dictated line, append a named todo, toggle a pointed-at checkbox, read a specific period's note. State changes go through `zanmai.py notes daily|weekly|monthly`, which resolves the path from `.zennotes/vault.json` deterministically. No slash command (the `journal` command covers the common capture path).
- `media`: internal, run by Loki. His method for image and video generation, backend routing, the swappable model registry, prompt craft, the quality axes, cost control and lawful marking. The judgment layer; the runnable generate and labeling clients are provisioned when a backend is wired. No slash command.
- `image-edit`: internal, run by Loki. The local pixel workbench through `image-edit.py`, convert (incl. WebP), resize, rotate, crop, grayscale, composite, optimize and batch a folder on Pillow alone, plus colour grading (a `.cube` LUT or a reference match) and RAW develop where the host has the libraries. Deterministic, no model, no cost; preferred over regenerating when the pixels already exist. No slash command.
- `update`: slash command `/zanmai:update`. Explicit Pepper-trigger for a distribution update. Steve dispatches Pepper, who checks for a newer version with `zanmai.py setup upgrade --check`, returns a TL;DR preview of the changes, snapshots before apply on user yes, applies with `zanmai.py setup upgrade` (git fast-forward for a cloned vault, HTTPS file fetch for any other, host config refreshed in the same run), verifies via `zanmai.py setup validate`, rolls back from the pre-update snapshot on failure.
- `manage-connections`: slash command `/zanmai:connection`. Wong's manual for host sources outside the vault. Wong drives it as a conversation: vault-first, and if the host exposes the source it reads it directly, the host configuration is the opt-in, so no activation gate. No credentials, no read-write, no sync (use-not-own). Recording a connection is optional curation for the user's overview. Steve dispatches Wong, which runs the `connection` subcommand group (scan, activate, deactivate, list) under the hood, the user never types them.
- `content-brief`: internal, run by Carol (or Steve inline) before any document production. Turns a solution's raw source material into a neutral, source-grounded content substrate persisted as reusable product knowledge. No slash command.
- `designer`: internal, Carol's design method, settle the mode (clone / compose), shape the piece from the content (structure and block count follow the content, split before cramming), decompose the templates into a concrete building-block kit (values not adjectives; stored per brand × format), compose from it, and a fresh-eyes check against a hard checklist (a separate pass seeing only render + templates + kit, briefed to find fault; any single hard fail, dead space, orphaned element, run-on heading, claim/structure mismatch, hollowed slot, fails the piece) as the delivery gate the builder cannot self-certify. No slash command.
- `affinity`: internal, run by Carol. Field notes for building natively in Affinity fast, the pre-flight ladder (start the app, repair a wedged session), Desktop-only staging, verified fill/compose idioms and stumble warnings, export presets. Accelerators, not the boundary of what is allowed. No slash command.
- `powerpoint`: internal, run by Carol. Native, headless PowerPoint handling, fill a template copy or create slides from its layouts by editing the OOXML directly. No slash command.
- `html`: internal, run by Carol. Turning a design into a handoff-ready file through HTML, format from context via CSS `@page`, fonts embedded (verified with `pdffonts`), a cheap PNG seeing-loop, delivery to `_export/`; the RGB/native-tool boundaries for true press are named, not improvised. No slash command.
- `create-expert`: internal, run by Stan. The procedure for adding a new expert without drift, research the role first so the spec is not generic, draft a role-specific contract, place it update-safe under `.zanmai/extensions/`, and wire every registration point (adapter, memory, and for a core expert the roster lists, manifest, routing, docs) in lockstep, then validate. No slash command.

Scripts under `.zanmai/system/scripts/`: `zanmai.py` (the vault CLI with all subcommands, setup, snapshot, bundle, asset, contact, notes, file, plan, review, update, index, memory, connection, media, tools) and `image-edit.py` (a standalone pixel-editing tool Loki's `image-edit` skill drives, convert, resize, rotate, crop, grayscale, composite, optimize, batch, grade, raw; kept separate from `zanmai.py` because it is a workbench, not vault mechanics).

External-tool register: `.zanmai/system/tool-register.json` is a static, distribution-shipped, user-immune catalogue of every external tool Zanmai invokes, per-OS invocation, tier, which agent needs it, how to detect and provision it. `zanmai.py tools` (doctor / check / ensure / preflight) reads it. **Maintenance rule (§3): introducing a new external tool REQUIRES an entry here in lockstep**, like manifest.yaml. Presence is detected live per machine, never stored in this static file; detection results are cached machine-locally in `.zanmai/runtime/tool-cache.json` (writable, update-immune) so a check is a quick look, not a rescan, and a change re-registers there.

Hooks are subcommands of `zanmai.py hook`, wired into Claude Code via `.claude/settings.json`. The four hooks: `kind-required` (PreToolUse Write|Edit), `permission-guard` (PreToolUse Write|Edit), `index-consistency` (PostToolUse Write|Edit), `session-start` (SessionStart). There is no gate on external (MCP) tool calls, the host configuration is the opt-in (LD6).

Subagents under `.zanmai/system/experts/<name>/<name>.md`, registered via a thin `.claude/agents/<name>.md` adapter stub (the contract's frontmatter plus a pointer to it, a real file, not a symlink):

- `hank`: filing expert. Steve dispatches via the `Agent` tool for any operation that produces more than a single line written into the vault. Hank runs the `import-bundle` skill, classifies per topic, stubs entities, calls `zanmai.py` for state changes.
- `reed`: research expert with `WebFetch` and `WebSearch` tools. Steve dispatches via the `Agent` tool. Output is a markdown file with citations, confidence levels, methodology and limitations.
- `wong`: gateway to host sources outside the vault. Steve dispatches via the `Agent` tool when a request touches an outside source, an MCP server or a local CLI the host already exposes. Wong's first reflex is vault-first. When an outside source is needed and the host exposes it, Wong reads it and returns prose; if the host does not expose it, Wong says so plainly and offers to help set it up at the host. A host-exposed source is available for use, the host configuration is the opt-in, so no activation gate. Wong uses the host's already-authenticated interfaces, holds no credentials, and cannot write vault files or the source, reads that become notes go to Hank.
- `pepper`: house-keeper for distribution updates, snapshot delete and restore, structure checks across the vault, and bulk repairs. Steve dispatches via the `Agent` tool for any operation that can lose state if mishandled, updates, restores, multi-file edits, structure audits. Pepper holds the discipline for pre-snapshot, TL;DR preview before apply, post-apply verification, automatic rollback on failure. Other agents do not perform these operations.
- `carol`: marketing document designer. Steve dispatches via the `Agent` tool when the user wants a marketing artifact (flyer, one-pager, deck) from a solution's material, after gathering her required inputs in conversation (audience, purpose, format, all CI templates, image and logo sources). Carol learns the design language from all templates, composes the piece on a copy of the best structural base, judges every render like a critic (designer skill), runs a final per-slot sweep, and writes the finished bundle to `_export/`; she checks the measurable points on every render herself, and the taste call goes to the user's fresh eyes on the render rather than a self sign-off. Runs the `content-brief`, `designer`, `html`, `affinity` and `powerpoint` skills; her contract grants the Affinity MCP tools.
- `loki`: image and video generation expert. Steve, or another expert whose piece needs generated visuals, dispatches him via the `Agent` tool to turn a brief into a still, a short clip, or an upscale. Loki directs the model: a refined prompt, service and model choice with a reason from a swappable registry, reference and identity handling, cost-aware video, a judgment of the render against explicit axes (regenerate vs. fix in place), and lawful marking (machine-readable credential always, a visible label on the deep-fake trigger). He reads the active style profile for on-brand prompts and renders through a configured backend Wong set up, never wiring one himself. The mechanics live in the `media` skill.
- `stan`: expert builder. Steve dispatches him (via the `Agent` tool) when the user needs a capability no current expert covers, after settling the one-sentence need and a Reed role-research pass. Stan drafts a role-specific contract from the research (never from model knowledge), places it update-safe under `.zanmai/extensions/experts/`, wires every registration point consistently, validates, and returns the draft for approval. Runs the `create-expert` skill.

Slash-command discovery works via thin adapter stubs the migration places at install time:

- `.claude/skills/zanmai-close-session/SKILL.md` to `.zanmai/system/skills/close-session/SKILL.md`.
- `.claude/skills/zanmai-import/SKILL.md` to `.zanmai/system/skills/import-bundle/SKILL.md`.
- `.claude/skills/zanmai-snapshot/SKILL.md` to `.zanmai/system/skills/snapshot/SKILL.md`.
- `.claude/skills/zanmai-research/SKILL.md` to `.zanmai/system/skills/research/SKILL.md`.
- `.claude/skills/zanmai-connection/SKILL.md` to `.zanmai/system/skills/manage-connections/SKILL.md`.
- `.claude/agents/hank.md` to `.zanmai/system/experts/hank/hank.md`.
- `.claude/agents/reed.md` to `.zanmai/system/experts/reed/reed.md`.
- `.claude/agents/wong.md` to `.zanmai/system/experts/wong/wong.md`.
- `.claude/agents/pepper.md` to `.zanmai/system/experts/pepper/pepper.md`.
- `.claude/agents/carol.md` to `.zanmai/system/experts/carol/carol.md`.

The SKILL.md frontmatter `name:` field carries the user-visible slash command (`zanmai:close-session`, `zanmai:import`, `zanmai:snapshot`, `zanmai:research`). The adapter stub carries that frontmatter and points at the source procedure under `.zanmai/system/`, so distribution updates touch only the source file and the stub stays valid. Real files, not symlinks, portable and copy/sync-safe; the canonical procedure stays in the AI-neutral `.zanmai/system/` tree, so another host only needs its own thin adapter, not a rewrite.

### `zanmai.py` subcommands

`zanmai.py` is the executor for all bundle state changes. Skills call it, the AI does not write directly into `inbox/`. Subcommands:

- `index inspect`: user-visible plain-text scan of an import scope. Lists subfolders, file counts per extension, folder-name token candidates, embed reference counts. Run before `index find` so the user sees what was looked at and folder-tokens enter the token query.- `bundle create`: new bundle folder, truth file, `INDEX.md`, master-INDEX refresh. Refuses contact kinds (use `contact create` instead). The slug may contain `/` for sub-bundles. Only called after the user approves the plan.
- `bundle add-file`: copy a markdown file into a bundle. Body verbatim. Non-schema frontmatter fields go to a body section. Honours `--overwrite`, default behaviour appends `-imported` to avoid clobber.
- `asset add`: copy a non-markdown file into the shared vault-root `assets/` folder. `--target-name` lets the caller rename to avoid basename collisions; renames are recorded in `.zanmai/memory/.embed-rename-map.json` so `update embeds` can resolve plan-driven renames automatically.
- `update master-index`: regenerate the vault-root `INDEX.md` from existing bundles plus the contacts folders.
- `update wikilinks`: rename `[[old-slug]]` to `[[new-slug]]` across markdown bodies. Honours `|display` variants. Scope defaults to `inbox/` (the live user vault); pass `--scope <path>` to override. System paths (`.zanmai/system/`, `.zanmai/snapshots/`, `.zanmai/logs/`, `.zanmai/memory/activity-log.md`, `_import/`, `trash/`, `archive/`) are hard-excluded regardless of scope so historical and immutable content stays verbatim.
- `bundle rename`: atomic slug rename. Renames the markdown file, updates the frontmatter `slug:` field, rewrites vault-wide wikilinks (with the `update wikilinks` scope and hard-exclude rules), refreshes the master `INDEX.md`, and writes one activity-log line. Replaces the multi-step manual workaround that risked `source_detail` corruption.- `bundle add-truth`: write a truth file for an existing sub-bundle, with a "Part of [[parent]]" wikilink derived from the folder path. `bundle create` deliberately omits a truth file for sub-bundles; this command adds one when the sub-bundle is meant as a thematic node with body and parent-link.- `plan clear-section`: remove the `## Plan` section from a bundle's truth file after filing has executed. Idempotent.
- `contact create`: create a `contact/person` or `contact/organization` file under `inbox/contacts/<sub>/`. Single file, no bundle. Schema-strict frontmatter.
- `file trash` and `file archive`: move via `zn` if installed, `mv` fallback otherwise.
- `reindex`, `patterns`, `index find`: pattern engine (per-file metadata layer, aggregated themes layer, query interface).
- `memory report`: operation report at `.zanmai/logs/<YYYY>/<MM>/<date-op-slug>.md`. Captures the activity-log window of the operation plus a skill-provided summary. Gives future Steve sessions a per-operation memory beyond the one-liner activity log. Triggers an automatic `briefing` rebuild after writing the report.
- `briefing`: atomic rebuild of `.zanmai/memory/briefing.md`. Three sections (current state, open items, gaps and hints) synthesised from active focus bundles, the latest operation report, open `- [ ]` lines in Daily, Weekly and focus files, and broken wikilinks via the vault index. Atomic full rebuild on every call, no incremental drift. Triggered by `/zanmai:close-session` Step 6, by `memory report` automatically, and on demand via this subcommand. The `session-start.py` hook reads the file and inlines it into Steve's context, so the greet needs no extra tool-reads.

- `setup upgrade`: fetches the newest published version and replaces the distribution files. A cloned vault is fast-forwarded through git so it stays a clean clone and a manual `git pull` keeps working; any other vault has the new files fetched over HTTPS. Only the manifest's distribution paths are written, user-immune paths never, and files a new version withdraws are removed. Refreshes the host config in the same run and records which version that config was built for, so a version arriving by hand is noticed at the next session start. `--check` reports without applying, and a vault ahead of the source is never downgraded.
- `tools`: reads `tool-register.json` and works the external-tool layer. `doctor` detects every registered tool on this machine (per-OS invocation, presence, version, identity, never assumed); `check <id>` reports one; `ensure <id>` provisions an on-demand tool at first use, Python libraries install into a managed runtime venv at `.zanmai/runtime/venv` (built with `uv` if present, else stdlib `venv`, so the externally-managed system Python is never touched), standalone binaries are reported with their recipe (auto-fetch is a later step), the self-managed C2PA signer is established on demand (`media signer ensure`, cryptography into the same venv), prerequisites return the user-facing install hint. `preflight <expert>` (optionally `--capability <path>`) resolves everything that expert needs, cache-backed, and returns `ready` plus, for each gap, the why (what the tool does for the job) and the install hint, so Steve gates a dispatch before it starts: auto-provision a small library, ask for a heavy one, or stop with a clear message. No expert meets a missing tool mid-run (a subagent cannot ask the user, operating-principles §10).

The skills compose these subcommands. The discipline lives in the skill, the mechanics live in the script.

---

[← Back to the documentation index](index.md)
