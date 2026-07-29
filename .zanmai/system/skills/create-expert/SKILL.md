---
name: zanmai:create-expert
description: Procedure for adding a new expert to the vault without drift, research the role first so the spec is not generic, draft a role-specific contract, place it update-safe under extensions, and wire every registration point in lockstep. Stan runs this; any agent can follow it.
---

# create-expert

Add an expert so the roster stays consistent and the spec is not a generic stub. Two things have broken this before: a spec drafted from model knowledge that reads like every other AI agent, and a contract added to one list but not the others so the next setup crashes or the expert dispatches nowhere. This procedure closes both.

This is the one way an expert is built, whether Stan adds it for the user or it ships with Zanmai. Same procedure, same shape, same budget. That shared discipline is what lets Zanmai grow itself without bloating: an expert added the disciplined way stays lean by construction.

## When to use

- The user needs a capability no current expert covers, and Steve could name it in one sentence.
- Not for a one-off task an existing expert can do. Not for renaming or removing an expert.

## The procedure

### 1. Name the need
One sentence: what this expert does that no current expert does. Steve settles it with the user before dispatch. If the sentence cannot be finished, the role is not defined yet.

### 2. Research the role (before any drafting)
Steve dispatches Reed for a role-research pass: how an excellent version of this role operates day to day, its core competencies, the anti-patterns a mediocre version falls into, the real deliverables, the boundaries it holds, and name candidates. This is the step that prevents a generic spec, a contract written from model knowledge alone mirrors every other AI agent. Stan drafts from this research, not from memory.

### 3. Snapshot
`python3 .zanmai/system/scripts/zanmai.py snapshot create --reason add-expert-<name>` before any write.

### 4. Draft the contract, role-specific
Match the shape of the shipped experts (identity and why-it-exists, how-you-work steps, a few hard rails, a return format, pointers). The contract is the spec: the research stays as reference, it is not pasted in. Write it in the contract voice (instructions to the model), not as prose about the expert.

**The contract is thin, a pointer, not a manual.** It points at the skills that hold the depth; the procedure lives in the skill, read when it runs, never copied into the contract. Define the role by what it does (positive), with a few surgical rails, not a wall of prohibitions, which only dilutes the positive rules around it. A contract that runs long or fills with "never" is the signal to reformulate or move depth to a skill, not to ship, the same bar at runtime as at build time.

### 5. Place it update-safe
A user-grown expert lives at `.zanmai/extensions/experts/<name>/<name>.md`. `.zanmai/extensions/` is update-immune, a distribution update never touches it. (An expert that ships with Zanmai is the exception: it lives in the distribution tree at `.zanmai/system/experts/<name>/` and is added to the manifest.)

### 6. Wire every registration point, the checklist
An expert is not real until all of these are in lockstep. Miss one and it crashes or dispatches nowhere.

**Every expert:**
- Contract file written (step 5).
- Host adapter `.claude/agents/<name>.md`: the contract's frontmatter plus a one-line body pointing at the contract path. This is what makes the expert discoverable and dispatchable.
- Memory: `.zanmai/memory/agents/<name>/lessons.md` created (empty is fine) so the expert can learn.

**A core (distribution) expert, additionally, all hand-maintained lists, they drift if you touch one and forget another:**
- `zanmai.py` `_ROSTER`, one entry `(name, adapter, memory)`; `_AGENT_NAMES`, the memory folders and both lessons loops all derive from it, so this single edit wires them together.
- `manifest.yaml` `distribution_paths`, the contract path (and any new skill).
- `steve.md`, one row in the Routing table so Steve routes the right intent to the expert (a row, not a section: the depth is the expert's own contract).
- `CLAUDE.md` pointer list and `docs/skills-and-scripts.md`.

**Then grep-sweep the whole tree for the new name** and confirm every reference agrees. An identifier change ends with a full-tree grep and a verify grep, never a single representative edit, that rule exists because this exact drift has bitten before.

### 7. Verify
`python3 .zanmai/system/scripts/zanmai.py setup validate .`, green, or the expert is not shipped. Validate checks that adapters match the roster and no registration is dangling.

### 8. Report
Stan returns the contract path, the adapter, what the research surfaced, the registration points wired, the validate result, and anything open. For a core expert the draft is shown for approval before it ships.

## Common failures this procedure prevents

- **Generic spec**, skipping the research pass; the contract reads like every other AI agent.
- **The ghost**, a contract with no adapter or no roster entry; it exists on disk and dispatches nowhere.
- **The drift**, added to one list, missed in another; the next setup crashes on the missing piece.
- **The wipe**, a runtime-created expert placed in the distribution tree; the next update deletes it.
