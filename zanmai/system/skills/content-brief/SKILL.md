---
name: zanmai:content-brief
description: Turn raw material into an audience-neutral content substrate every later artifact draws from. Carol runs it before producing any document. Not finished copy.
---

# content-brief

Make the neutral content substrate. Read the source, sort it by meaning, record every statement with its source and confidence. No document, no audience tailoring, no invention.

## Boundaries

- No finished document and no format, the format skills do that.
- No audience tailoring, that happens in Carol's produce step. The substrate stays neutral.
- Source templates are read only.
- Nothing invented: an empty field beats a placeholder; verbatim beats paraphrase where a statement carries weight.

## Steps

| Step | What happens |
|---|---|
| Clarify | Which solution, which material, what purpose. Ask if unclear, never guess. |
| Read | Read each source by type. Use the form to extract, then discard it, the angle comes from content, not container. |
| Map | Sort every piece by meaning (taxonomy below). What fits no meaning goes to `Raw / unmapped` with a flag, never a new category. |
| Draft | Fill the substrate (schema below). Each statement carries source and confidence; contradictions stand side by side; empty stays empty. |
| Approve | Only when a live user dialog exists (Steve running this inline): show the draft as a plan, write after OK. Inside a dispatched production run (Carol) there is no mid-run chat, the dispatch brief is the approval; note the substrate in the return TL;DR instead. |
| Write | To `knowledge/<product>/` as reusable product knowledge; source kept by reference; only the allowed fields. Never hand-write into a bundle, draft the substrate in the task's work area, then persist via the CLI: `zanmai.py bundle create` (kind `knowledge`) when the product bundle does not exist yet, `zanmai.py bundle add-file` for the substrate note. The script carries the schema frontmatter and the index duties. |

`zanmai.py <subcommand>` is shorthand for `<python_cmd> zanmai/system/scripts/zanmai.py <subcommand>` run from the vault root, with `<python_cmd>` read from `zanmai/user.md`.

## Substrate, the only legal write form

Typed facts (neutral): name, category, status, sources (references, not content), date.

Meaning sections (fixed): Problem/pain · What it is · Value · Differentiation · Proof points · Objections · Audience candidates · Key messages · Tone samples (verbatim quotes) · Raw/unmapped.

Each statement carries `, [source: <ref> · High|Med|Low]`. Additions from outside the given material are marked `[source: web/own-knowledge · <ref>]`, so nothing unmarked slips in.

## Meaning taxonomy (the angle)

Sort by the question a piece answers: a problem or need → Problem; what the solution is → What it is; a concrete benefit → Value; a comparison to alternatives → Differentiation; evidence → Proof; a counter-argument → Objections; an addressee → Audience candidates. Unresolvable → Raw/unmapped with a flag. Never invent a category; if one is truly needed, change the schema first.

## Writing baseline (all produced copy follows this)

Produced copy follows the human-voice discipline in `operating-principles.md` §7 (constructions, not one glyph). Its voice target is the brand's samples (`design.md`) and the source's tone samples captured in the substrate above, never an invented voice.
