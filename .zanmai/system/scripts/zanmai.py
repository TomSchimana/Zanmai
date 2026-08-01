#!/usr/bin/env python3
"""zanmai.py: the single CLI for Zanmai vault operations.

Replaces AI-tool-call sequences (Write+Edit+Write+...) with deterministic
state-changes. AI decides (classification, plan); script executes.

Subcommand groups:
    setup, first-time install and validation (init/validate/update)
    snapshot, vault snapshots (create)
    bundle, bundle operations (create, add-file, add-truth, rename)
    asset, non-markdown files in the shared assets/ folder (add)
    contact, person and organisation contacts (create)
    notes, daily, weekly and monthly notes (daily, weekly, monthly)
    file, file moves to system folders (trash, archive)
    plan, plan-section maintenance on bundle truth files (clear-section)
    review, read-once briefings in inbox/review/ (archive)
    update, bundle-level index touches (wikilinks, embeds, master-index)
    index, vault-index and pattern queries (rebuild, patterns, find, inspect)
    memory, briefing and operation reports (briefing, report)

Conventions:
    - `created` is always today (the day the file is written), not the source date.
    - `source: organic` for body-verbatim user content.
    - `source: ai-generated` for files the script generates (INDEX.md, etc.).
    - Schema is strict: non-schema frontmatter keys go into the body, not the YAML.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Schema-required and -optional fields per kind. Sync with schema/frontmatter-v1.yaml.
COMMON_REQUIRED = ("kind", "slug", "created")
COMMON_OPTIONAL = ("updated", "source", "source_detail", "tags", "mentioned_in")
KIND_FIELDS = {
    "focus": {"required": ("goal", "status"), "optional": ("due",)},
    "habit": {"required": ("cadence",), "optional": ("last_done",)},
    "knowledge": {"required": (), "optional": ("topic", "status")},
    "contact/person": {"required": (), "optional": ("nickname", "role", "org", "email", "phone", "birthday", "address", "website")},
    "contact/organization": {"required": (), "optional": ("kind_of", "website")},
}

ATTACHMENT_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ics", ".heic", ".mp4", ".mov")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _timestamp_log() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


_UMLAUT_MAP = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}


def _slugify(value: str) -> str:
    # Pre-replace German umlauts and eszett before NFKD-decompose, so 'ä' becomes
    # 'ae' (semantic) instead of 'a' (lossy via diacritic-strip).
    for char, replacement in _UMLAUT_MAP.items():
        value = value.replace(char, replacement)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "untitled"


def _slugify_bundle_path(value: str) -> tuple[list[str], str]:
    """Bundle slugs may contain '/' for sub-bundles (e.g. 'computer/clippings').

    Returns (path-segments, leaf-slug). Empty segments are dropped; each
    segment is slugified independently.
    """
    raw = [seg for seg in value.split("/") if seg.strip()]
    segments = [_slugify(seg) for seg in raw]
    if not segments:
        return [], "untitled"
    return segments, segments[-1]


def _resolve_bundle_dir(vault: Path, bundle_slug: str, bundle_kind: str | None) -> tuple[Path | None, str | None, str]:
    """Find the bundle directory for a (possibly sub-pathed) slug.

    Returns (bundle_dir, bundle_kind, leaf_slug). bundle_dir is None when no
    matching folder exists.
    """
    segments, leaf = _slugify_bundle_path(bundle_slug)
    if not segments:
        return None, None, leaf

    if bundle_kind:
        candidate = vault / "inbox" / bundle_kind / Path(*segments)
        return (candidate if candidate.is_dir() else None), bundle_kind, leaf

    for k in ("focus", "habit", "knowledge"):
        candidate = vault / "inbox" / k / Path(*segments)
        if candidate.is_dir():
            return candidate, k, leaf
    return None, None, leaf


def _allowed_keys_for_kind(kind: str) -> set[str]:
    fields = KIND_FIELDS.get(kind, {"required": (), "optional": ()})
    return set(COMMON_REQUIRED) | set(COMMON_OPTIONAL) | set(fields["required"]) | set(fields["optional"])


def _split_frontmatter(content: str) -> tuple[dict, list[str], str]:
    """Return (frontmatter-dict, order-of-keys, body)."""
    if not content.startswith("---"):
        return {}, [], content
    end = content.find("\n---", 4)
    if end == -1:
        return {}, [], content
    block = content[3:end].strip("\n")
    body = content[end + 4:]
    if body.startswith("\n"):
        body = body[1:]
    fm: dict[str, str | list[str]] = {}
    order: list[str] = []
    current_key: str | None = None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            value = line[4:].strip().strip('"').strip("'")
            if not isinstance(fm[current_key], list):
                fm[current_key] = [fm[current_key]] if fm[current_key] else []
            fm[current_key].append(value)
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            key, raw = m.group(1), m.group(2).strip()
            if key not in fm:
                order.append(key)
            # An inline flow sequence is a list, not a string. Read as a string it
            # survives one round-trip as `key: "[a, b, c]"`, which is a single
            # nonsense value where five tags used to be.
            if raw.startswith("[") and raw.endswith("]"):
                items = [i.strip().strip('"').strip("'") for i in raw[1:-1].split(",")]
                fm[key] = [i for i in items if i]
            else:
                value = raw.strip('"').strip("'")
                fm[key] = value if value else ""
            current_key = key
    return fm, order, body


def _render_frontmatter(fm: dict, order: list[str]) -> str:
    lines = ["---"]
    for key in order:
        if key not in fm:
            continue
        value = fm[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif value == "":
            lines.append(f'{key}: ""')
        else:
            if isinstance(value, str) and any(c in value for c in " :,"):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
    lines.append("---\n")
    return "\n".join(lines)


def _migrate_frontmatter(source_fm: dict, source_order: list[str], *, kind: str, slug: str,
                          additions: dict, overrides: dict | None = None) -> tuple[dict, list[str], dict]:
    """Build target frontmatter from what the source carries, filled up where it is silent.

    Three classes, and the order between them is the whole point:
    `overrides` win over the source (where the file lands defines `kind` and `slug`,
    and a value the user typed on the command line beats a stale one in the file),
    the source comes next, and `additions` are defaults that only apply where the
    source says nothing. The other way round, a default overwrote a field the file
    already had correct: an AI-written research note arrived declaring
    `source: organic`, which claims the user wrote it themselves. Nobody notices
    that, and provenance is exactly the field where nobody noticing is the damage.

    Returns (target_fm, target_order, leftover-non-schema-fields).
    Non-schema keys are filtered out and returned as leftover so the caller can
    append them to the body under `## Original metadata`.
    """
    allowed = _allowed_keys_for_kind(kind)
    overrides = dict(overrides or {})
    overrides.setdefault("kind", kind)
    overrides.setdefault("slug", slug)
    target_fm: dict = {}
    target_order: list[str] = []
    leftover: dict = {}

    # Required fields first, in canonical order.
    canonical_order = list(COMMON_REQUIRED)
    fields = KIND_FIELDS.get(kind, {"required": (), "optional": ()})
    canonical_order += list(fields["required"])
    canonical_order += list(COMMON_OPTIONAL)
    canonical_order += list(fields["optional"])

    # Overrides first, then what the source carries, then defaults for what is missing.
    for key in canonical_order:
        if key in overrides:
            target_fm[key] = overrides[key]
        elif key in source_fm and key in allowed and source_fm[key] not in ("", [], None):
            target_fm[key] = source_fm[key]
        elif key in additions:
            target_fm[key] = additions[key]
        else:
            continue
        target_order.append(key)

    # Source fields that are not in the schema go to leftover.
    for key in source_order:
        if key not in allowed:
            leftover[key] = source_fm[key]

    return target_fm, target_order, leftover


def _work_is_open(work_task_dir: Path) -> bool:
    """Does this workshop declare itself open, in `status.md` frontmatter `state:`?

    Read leniently on purpose: only an explicit `state: done` (or `closed`) marks a
    workshop finished. An unreadable or `state:`-less status file counts as open, so
    a malformed line can cost disk but never the work.
    """
    status = work_task_dir / "status.md"
    if not status.is_file():
        return False
    try:
        fm, _, _ = _split_frontmatter(status.read_text(encoding="utf-8"))
    except OSError:
        return True
    state = str(fm.get("state", "")).strip().lower()
    return state not in ("done", "closed")


def _render_original_metadata_block(leftover: dict) -> str:
    if not leftover:
        return ""
    lines = ["\n## Original metadata\n",
             "Preserved from the source frontmatter (not in Zanmai schema):\n"]
    for key, value in leftover.items():
        if isinstance(value, list):
            lines.append(f"- **{key}**: {', '.join(value)}")
        else:
            lines.append(f"- **{key}**: {value}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _append_activity_log(vault: Path, agent: str, what: str) -> None:
    log = vault / ".zanmai" / "memory" / "activity-log.md"
    if not log.exists():
        return
    line = f"\n## [{_timestamp_log()}] - {agent} - {what}\n"
    with log.open("a", encoding="utf-8") as f:
        f.write(line)


def _append_index(index_path: Path, slug: str, summary: str = "") -> None:
    if not index_path.exists():
        return
    text = index_path.read_text(encoding="utf-8")
    suffix = f" - {summary}" if summary else ""
    wikilink_line = f"- [[{slug}]]{suffix}\n"
    if f"[[{slug}]]" in text:
        return
    # Append under the members heading. The known English wordings come first, then
    # whatever the file's own first `##` heading is, because a bundle index written in
    # the user's language carries that heading in their words and the members list is
    # the first section either way. Without that second pass the link landed at the
    # end of the file, below the activity log.
    candidates = ["## Files in this bundle", "## Knowledge", "## Focus", "## Habits"]
    first = re.search(r"^## .+$", text, re.MULTILINE)
    if first:
        candidates.append(first.group(0))
    for header in candidates:
        idx = text.find(header)
        if idx == -1:
            continue
        end = text.find("\n##", idx + len(header))
        section = text[idx:end] if end != -1 else text[idx:]
        # Remove "(empty...)"-stubs.
        section_new = re.sub(r"\n\(empty[^)]*\)\n", "\n", section)
        if section_new.rstrip().endswith(header):
            section_new = section_new + "\n" + wikilink_line
        else:
            section_new = section_new.rstrip("\n") + "\n" + wikilink_line + "\n"
        text = text[:idx] + section_new + (text[end:] if end != -1 else "")
        index_path.write_text(text, encoding="utf-8")
        return
    # Fallback: append at end.
    with index_path.open("a", encoding="utf-8") as f:
        f.write("\n" + wikilink_line)


def _render_truth_file(*, kind: str, slug: str, additions: dict) -> str:
    title = additions.get("_title", slug.replace("-", " ").title())
    fm: dict = {
        "kind": kind,
        "slug": slug,
        "created": _today(),
        "source": additions.get("source", "ai-generated"),
    }
    fields = KIND_FIELDS.get(kind, {"required": (), "optional": ()})
    # COMMON_OPTIONAL belongs in this pickup too. Without it, `source_detail` and
    # `tags` were accepted on the command line and silently dropped on the way in.
    for key in tuple(COMMON_OPTIONAL) + fields["required"] + fields["optional"]:
        if key in additions:
            fm[key] = additions[key]
    order: list[str] = []
    for key in (list(COMMON_REQUIRED) + ["source"] + list(COMMON_OPTIONAL)
                + list(fields["required"]) + list(fields["optional"])):
        if key in fm and key not in order:
            order.append(key)
    fm_text = _render_frontmatter(fm, order)
    return f"{fm_text}\n# {title}\n\n(Content to follow.)\n"


INDEX_HEADING_FILES = "Files in this bundle"
INDEX_HEADING_ACTIVITY = "Recent activity"


def _render_bundle_index(*, slug: str, title: str, bundle_kind: str = "knowledge",
                         is_sub_bundle: bool = False,
                         heading_files: str = INDEX_HEADING_FILES,
                         heading_activity: str = INDEX_HEADING_ACTIVITY) -> str:
    # INDEX inherits the bundle's kind so it stays consistent with the path.
    # The schema does not require goal or status on INDEX files. The
    # kind-required hook exempts INDEX.md from the required-field check.
    #
    # The two headings are passed in because this file is the user's, and a vault
    # written in one language does not want two English headings in the middle of it.
    # The script cannot know the language, and a table of translations here would grow
    # with every language Zanmai meets, so the caller supplies the words; English is
    # the default for a caller that has nothing better.
    fm = {"kind": bundle_kind, "slug": "index", "created": _today(), "source": "ai-generated"}
    if is_sub_bundle:
        # No claim here about whether a truth file exists. It used to say there was
        # none, which `bundle add-truth` then made false without correcting it, and
        # that is the documented path for a sub-bundle with its own theme.
        return _render_frontmatter(fm, list(fm.keys())) + (
            f"\n# {title}, index\n\n"
            f"## {heading_files}\n\n"
            f"## {heading_activity}\n\n"
        )
    return _render_frontmatter(fm, list(fm.keys())) + (
        f"\n# {title}, index\n\n"
        f"## {heading_files}\n\n"
        f"- [[{slug}]]: the bundle's main file\n\n"
        f"## {heading_activity}\n\n"
    )


def cmd_create_bundle(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    kind = args.kind
    if kind in ("contact/person", "contact/organization"):
        print(
            f"fail: contacts are single files, not bundles. "
            f"Use 'contact create --kind {'person' if kind == 'contact/person' else 'organization'} --slug ...' instead.",
            file=sys.stderr,
        )
        return 2
    if kind not in KIND_FIELDS:
        print(f"fail: unknown kind {kind}", file=sys.stderr)
        return 1
    # Sub-bundle slugs are allowed via "/" (e.g. "computer/clippings"). Each
    # path segment is slugified independently; the last segment is the bundle slug.
    segments, slug = _slugify_bundle_path(args.slug)
    if not segments:
        print(f"fail: empty slug", file=sys.stderr)
        return 1
    bundle_dir = vault / "inbox" / kind / Path(*segments)
    if bundle_dir.exists():
        print(f"fail: bundle already exists: {bundle_dir}", file=sys.stderr)
        return 1
    bundle_dir.mkdir(parents=True)
    bundle_rel = f"inbox/{kind}/{'/'.join(segments)}"
    is_sub_bundle = len(segments) > 1

    additions: dict = {"_title": args.title or slug.replace("-", " ").title()}
    for key in ("source", "source_detail", "goal", "status", "cadence", "due", "topic", "last_done"):
        v = getattr(args, key, None)
        if v:
            additions[key] = v

    # Sub-bundles get no truth file from this command by default. Two shapes
    # coexist:
    #   - Organisational sub-folder: container for loose items of a narrow
    #     shape inside the parent theme. The parent's truth carries the
    #     theme; the sub-folder is just a grouping. Stays as-is (no truth).
    #   - Thematic sub-bundle: the sub-theme has its own identity. Add the
    #     truth file with a "Part of [[parent]]" wikilink afterwards via
    #     `zanmai.py bundle add-truth`. Kept as a separate command so
    #     the caller decides shape per bundle, not by name convention.
    if not is_sub_bundle:
        truth = bundle_dir / f"{slug}.md"
        truth.write_text(_render_truth_file(kind=kind, slug=slug, additions=additions), encoding="utf-8")

    bundle_index = bundle_dir / "INDEX.md"
    bundle_index.write_text(
        _render_bundle_index(
            slug=slug, title=additions["_title"], bundle_kind=kind, is_sub_bundle=is_sub_bundle,
            heading_files=(getattr(args, "heading_files", None) or INDEX_HEADING_FILES),
            heading_activity=(getattr(args, "heading_activity", None) or INDEX_HEADING_ACTIVITY),
        ),
        encoding="utf-8",
    )

    _append_activity_log(vault, "zanmai.py", f"created bundle {bundle_rel}/")
    _update_master_index(vault)

    print(f"ok: bundle created at {bundle_rel}/")
    return 0


def cmd_copy_into_bundle(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        print(f"fail: source not a file: {source}", file=sys.stderr)
        return 1

    bundle_dir, bundle_kind, leaf_slug = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found under inbox/", file=sys.stderr)
        return 1

    target_name = args.target_name or source.stem
    # Strip a trailing .md from caller-supplied target_name so we don't slugify
    # the extension dot into '-md'.
    if target_name.lower().endswith(".md"):
        target_name = target_name[:-3]
    target_slug = _slugify(target_name)
    target = bundle_dir / f"{target_slug}.md"
    if target.exists() and not args.overwrite:
        target = bundle_dir / f"{target_slug}-imported.md"

    content = source.read_text(encoding="utf-8")
    source_fm, source_order, body = _split_frontmatter(content)

    target_kind = args.target_kind or bundle_kind
    # Where the file lands decides these two; everything else fills gaps only.
    overrides = {"kind": target_kind, "slug": target_slug}
    # Provenance stated on the command line is an override, because the caller knows
    # something the file does not say about itself. Without it the default below
    # applies, and it only applies to a file that declares no source of its own: a
    # research note that says it was AI-written keeps saying so.
    if getattr(args, "source_class", None):
        overrides["source"] = args.source_class
    if getattr(args, "source_detail", None):
        overrides["source_detail"] = args.source_detail
    additions = {
        "created": _today(),
        "source": "organic",
        "source_detail": f"import:{source.name}",
    }

    target_fm, target_order, leftover = _migrate_frontmatter(
        source_fm, source_order, kind=target_kind, slug=target_slug,
        additions=additions, overrides=overrides,
    )

    fm_text = _render_frontmatter(target_fm, target_order)
    leftover_block = _render_original_metadata_block(leftover)
    target.write_text(f"{fm_text}\n{body.rstrip()}\n{leftover_block}", encoding="utf-8")

    bundle_rel = target.parent.relative_to(vault).as_posix()
    # The index line describes the member, so it takes the file's own topic or title
    # where it has one. The bare source stem told the reader nothing the wikilink did
    # not already say, and had to be replaced by hand afterwards.
    summary = (getattr(args, "summary", None) or "").strip()
    if not summary:
        for key in ("topic", "goal", "_title", "title"):
            value = target_fm.get(key)
            if isinstance(value, str) and value.strip():
                summary = value.strip()
                break
    _append_index(bundle_dir / "INDEX.md", target_slug, summary=summary or source.stem)
    _append_activity_log(
        vault, "zanmai.py",
        f"copied {source.name} into {bundle_rel}/ (body verbatim, "
        f"frontmatter migrated, {len(leftover)} non-schema field(s) moved to body)"
    )

    print(f"ok: copied to {target.relative_to(vault)}")
    return 0


def cmd_copy_attachment(args: argparse.Namespace) -> int:
    """Copy a non-markdown file into the shared vault-root `assets/` folder.

    Target shape: `assets/<basename>` at the vault root. All non-markdown
    files in the vault live in this one shared folder regardless of which
    bundle, contact or topic they belong to. The owning file (bundle truth
    file, topic file, contact file) is not required to exist for the copy
    itself, `--bundle-slug` and `--bundle-kind` are accepted for symmetry
    with other subcommands and for plan dialogue, but do not affect the
    target path.

    `--target-name` lets the caller rename on copy to avoid basename
    collisions in the shared folder. `--overwrite` allows replacement of
    an existing target; otherwise the new name gets `-imported` suffix.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.source).resolve()

    assets_dir = vault / "assets"
    assets_dir.mkdir(exist_ok=True)
    target_name = args.target_name or source.name
    target = assets_dir / target_name
    if target.exists() and not args.overwrite:
        stem, dot, ext = target.name.rpartition(".")
        target = assets_dir / (f"{stem}-imported.{ext}" if dot else f"{target.name}-imported")
    shutil.copy2(source, target)

    # Record any rename (original -> final) so `update embeds` can resolve
    # plan-driven attachment renames automatically. Stable across import waves
    # until cleared via `update embeds --clear-rename-map`.
    if target.name != source.name:
        _record_rename(vault, source.name, target.name)

    _append_activity_log(
        vault, "zanmai.py",
        f"attachment {target.name} -> assets/"
    )
    print(f"ok: attachment at {target.relative_to(vault)}")
    return 0


def _update_master_index(vault: Path) -> None:
    """Regenerate vault-root INDEX.md from existing bundles."""
    master = vault / "INDEX.md"
    if not master.exists():
        return
    text = master.read_text(encoding="utf-8")

    def list_bundles(kind: str) -> list[str]:
        kind_dir = vault / "inbox" / kind
        if not kind_dir.is_dir():
            return []
        bundles = sorted(p.name for p in kind_dir.iterdir() if p.is_dir())
        return bundles

    def list_single_notes(kind: str) -> list[str]:
        kind_dir = vault / "inbox" / kind
        if not kind_dir.is_dir():
            return []
        return sorted(p.stem for p in kind_dir.iterdir() if p.is_file() and p.suffix == ".md")

    def list_contacts(sub: str) -> list[str]:
        contacts_dir = vault / "inbox" / "contacts" / sub
        if not contacts_dir.is_dir():
            return []
        return sorted(p.stem for p in contacts_dir.iterdir() if p.is_file() and p.suffix == ".md")

    def render_section(header: str, kind: str, intro: str) -> str:
        bundles = list_bundles(kind)
        singles = list_single_notes(kind)
        lines = [f"## {header}", "", intro, ""]
        if not bundles and not singles:
            lines.append("(empty)")
        else:
            for b in bundles:
                lines.append(f"- [[{b}]]")
            for s in singles:
                lines.append(f"- [[{s}]]")
        return "\n".join(lines) + "\n"

    def render_contacts() -> str:
        people = list_contacts("people")
        orgs = list_contacts("organizations")
        lines = ["## Contacts", "",
                 "Single files per person and organisation.", "",
                 "### People (`inbox/contacts/people/`)", ""]
        if people:
            for p in people:
                lines.append(f"- [[{p}]]")
        else:
            lines.append("(empty)")
        lines += ["", "### Organisations (`inbox/contacts/organizations/`)", ""]
        if orgs:
            for o in orgs:
                lines.append(f"- [[{o}]]")
        else:
            lines.append("(empty)")
        return "\n".join(lines) + "\n"

    def render_review() -> str:
        review_dir = vault / "inbox" / "review"
        plans = sorted(p.stem for p in review_dir.iterdir() if p.is_file() and p.suffix == ".md") if review_dir.is_dir() else []
        lines = [
            "## Review",
            "",
            "`inbox/review/` - read-once briefings the AI produced for a specific decision. "
            "Read, then archive via `review archive` to keep this area clean. Multi-file "
            "operations approve via chat (TL;DR + tree-sketch), not via files here.",
            "",
        ]
        if plans:
            for p in plans:
                lines.append(f"- [[{p}]]")
        else:
            lines.append("(empty)")
        return "\n".join(lines) + "\n"

    new_focus = render_section("Focus", "focus", "Active attention bundles live here. See `inbox/focus/`.")
    new_habits = render_section("Habits", "habit", "Recurring routines live here. See `inbox/habits/`.")
    new_knowledge = render_section(
        "Knowledge", "knowledge",
        "Persistent reference material. Default class for anything that does not clearly belong in focus or habits. See `inbox/knowledge/`."
    )
    new_contacts = render_contacts()
    new_review = render_review()

    text = re.sub(r"## Focus\n.*?(?=\n## Habits)", new_focus + "\n", text, flags=re.DOTALL)
    text = re.sub(r"## Habits\n.*?(?=\n## Knowledge)", new_habits + "\n", text, flags=re.DOTALL)
    text = re.sub(r"## Knowledge\n.*?(?=\n## Contacts)", new_knowledge + "\n", text, flags=re.DOTALL)
    text = re.sub(r"## Contacts\n.*?(?=\n## Review)", new_contacts + "\n", text, flags=re.DOTALL)
    text = re.sub(r"## Review\n.*?(?=\n## Daily and Weekly notes)", new_review + "\n", text, flags=re.DOTALL)

    master.write_text(text, encoding="utf-8")


def cmd_update_master_index(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    _update_master_index(vault)
    _append_activity_log(vault, "zanmai.py", "master INDEX.md regenerated from existing bundles")
    print("ok: master INDEX updated")
    return 0


# Hard-exclude paths for all wikilink operations (write-time sweep AND
# read-time aggregation). These paths hold content that must not be mutated
# retroactively (sweeps) and must not surface as user-vault "issues"
# (aggregations like broken-wikilinks reporting):
#   - `.zanmai/system/`: distribution material, replaced on update.
#   - `.zanmai/snapshots/`: immutable rollback points, must stay bit-identical.
#   - `.zanmai/logs/`: append-only history (operation reports, plans, gap logs).
#     Old slug names appear here as historical record, by design.
#   - `.zanmai/memory/activity-log.md`: append-only activity history. Same
#     reason as `.zanmai/logs/`.
#   - `_import/`: source material stays verbatim until the user's trash
#     question at the end of an import run is answered.
#   - `trash/`: trashed files keep the wikilinks they had when trashed,
#     so a future restore lands in a coherent state.
#   - `archive/`: archived files keep their state at the time of archiving.
_WIKILINK_OPS_EXCLUDED_PREFIXES = (
    ".zanmai/system/",
    ".zanmai/snapshots/",
    ".zanmai/logs/",
    "_import/",
    "trash/",
    "archive/",
)
_WIKILINK_OPS_EXCLUDED_FILES = (
    ".zanmai/memory/activity-log.md",
)


def _is_excluded_from_wikilink_ops(rel_path: str) -> bool:
    """True if a vault-relative path must not be touched by wikilink sweeps
    and must not be counted by wikilink aggregations (e.g. broken-wikilinks
    reporting in briefing.md)."""
    rel = rel_path.replace("\\", "/")
    for prefix in _WIKILINK_OPS_EXCLUDED_PREFIXES:
        if rel.startswith(prefix):
            return True
    return rel in _WIKILINK_OPS_EXCLUDED_FILES


def cmd_update_wikilinks(args: argparse.Namespace) -> int:
    """Replace `[[old-slug]]` with `[[new-slug]]` across markdown files.

    Honors the `|display` variant: `[[old-slug|Display Text]]` becomes
    `[[new-slug|Display Text]]`. Does not touch embed-paths or non-link
    occurrences.

    Scope: defaults to `inbox/` (the live user vault). Pass `--scope <path>`
    to override. Hard-excluded paths (see `_WIKILINK_OPS_EXCLUDED_PREFIXES`
    and `_WIKILINK_OPS_EXCLUDED_FILES`) are never rewritten regardless of
    the requested scope: snapshots, logs, the activity log, trash, archive
    and the import drop area must stay verbatim.
    """
    vault = Path(args.vault).resolve()
    old_slug = args.old.strip()
    new_slug = args.new.strip()
    if not old_slug or not new_slug:
        print("fail: --old and --new must both be non-empty", file=sys.stderr)
        return 1
    if old_slug == new_slug:
        print("ok: nothing to do (old == new)")
        return 0

    scope_root = vault / args.scope if args.scope else vault / "inbox"
    if not scope_root.exists():
        print(f"fail: scope does not exist: {scope_root}", file=sys.stderr)
        return 1

    pattern = re.compile(r"\[\[" + re.escape(old_slug) + r"(\|[^\]]*)?\]\]")
    files_touched: list[str] = []
    occurrences = 0

    for md in scope_root.rglob("*.md"):
        rel = md.relative_to(vault).as_posix()
        if _is_excluded_from_wikilink_ops(rel):
            continue
        text = md.read_text(encoding="utf-8")
        replaced, count = pattern.subn(
            lambda m: f"[[{new_slug}{m.group(1) or ''}]]", text
        )
        if count > 0:
            md.write_text(replaced, encoding="utf-8")
            files_touched.append(rel)
            occurrences += count

    _append_activity_log(
        vault, "zanmai.py",
        f"wikilink rename [[{old_slug}]] -> [[{new_slug}]] "
        f"({occurrences} occurrence(s) in {len(files_touched)} file(s))"
    )
    if files_touched:
        for f in files_touched:
            print(f"  {f}")
    print(f"ok: {occurrences} occurrence(s) rewritten in {len(files_touched)} file(s)")
    return 0


# ---------------------------------------------------------------------------
# Changing what already exists.
#
# The tool could create and not change, so every correction went out through raw
# file writes: past the frontmatter guard, past the index update, past the log.
# Twenty-seven gap entries across ten runs, always the same shape. These are the
# four operations those entries asked for.
# ---------------------------------------------------------------------------


def _edit_frontmatter_in_place(path: Path, sets: dict, removes: list[str]) -> tuple[int, list[str]]:
    """Set or remove frontmatter fields, leaving the body byte-for-byte alone.

    Returns (number of fields changed, notes). A field not in the schema for this
    file's kind is refused rather than written, because the hook would refuse the
    file afterwards and the caller would be left with a file it cannot save.
    """
    text = path.read_text(encoding="utf-8")
    fm, order, body = _split_frontmatter(text)
    if not fm:
        return 0, ["file has no frontmatter block"]
    allowed = _allowed_keys_for_kind(str(fm.get("kind", "")))
    changed = 0
    notes: list[str] = []
    for key, value in sets.items():
        if allowed and key not in allowed:
            notes.append(f"refused '{key}': not in the schema for kind '{fm.get('kind')}'")
            continue
        new_value: str | list[str] = value
        if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            new_value = [i.strip() for i in value[1:-1].split(",") if i.strip()]
        if fm.get(key) == new_value:
            continue
        if key not in fm:
            order.append(key)
        fm[key] = new_value
        changed += 1
    for key in removes:
        if key in fm:
            fm.pop(key)
            order = [k for k in order if k != key]
            changed += 1
    if changed:
        path.write_text(_render_frontmatter(fm, order) + body, encoding="utf-8")
    return changed, notes


def _parse_set_pairs(pairs: list[str]) -> dict:
    out: dict = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--set expects key=value, got '{pair}'")
        key, value = pair.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def cmd_bundle_set_body(args: argparse.Namespace) -> int:
    """Replace the body of a file in a bundle. Frontmatter is untouched.

    Refuses to overwrite a body that already has content unless --replace is given,
    because the body is where the user's own writing lives (operating-principles
    section 2) and a silent overwrite is the one mistake this whole tool exists to
    prevent.
    """
    vault = Path(args.vault).resolve()
    target = _resolve_vault_file(vault, args.file)
    if target is None:
        print(f"fail: no such file in the vault: {args.file}", file=sys.stderr)
        return 1
    new_body = (Path(args.body_file).read_text(encoding="utf-8")
                if args.body_file else sys.stdin.read())
    text = target.read_text(encoding="utf-8")
    fm, order, old_body = _split_frontmatter(text)
    if not fm:
        print(f"fail: {target.relative_to(vault)} has no frontmatter; refusing to write a body into it",
              file=sys.stderr)
        return 1
    meaningful = [ln for ln in old_body.splitlines() if ln.strip() and not ln.startswith("#")]
    if meaningful and not args.replace:
        print(f"fail: {target.relative_to(vault)} already has {len(meaningful)} line(s) of body. "
              f"Pass --replace to overwrite, and be sure it is not the user's own writing.",
              file=sys.stderr)
        return 1
    if not new_body.startswith("\n"):
        new_body = "\n" + new_body
    target.write_text(_render_frontmatter(fm, order) + new_body.rstrip() + "\n", encoding="utf-8")
    _append_activity_log(vault, args.agent or "zanmai.py",
                         f"wrote body of {target.relative_to(vault)} "
                         f"({len(meaningful)} line(s) replaced, {len(new_body.splitlines())} written)")
    print(f"ok: body written to {target.relative_to(vault)} "
          f"({len(meaningful)} line(s) replaced, {len(new_body.splitlines())} written)")
    return 0


def cmd_bundle_edit_file(args: argparse.Namespace) -> int:
    """Correct frontmatter fields of an existing file in place. Body untouched."""
    vault = Path(args.vault).resolve()
    target = _resolve_vault_file(vault, args.file)
    if target is None:
        print(f"fail: no such file in the vault: {args.file}", file=sys.stderr)
        return 1
    try:
        sets = _parse_set_pairs(args.set)
    except ValueError as exc:
        print(f"fail: {exc}", file=sys.stderr)
        return 1
    changed, notes = _edit_frontmatter_in_place(target, sets, args.remove or [])
    for note in notes:
        print(f"  {note}")
    if changed:
        _append_activity_log(vault, args.agent or "zanmai.py",
                             f"edited frontmatter of {target.relative_to(vault)} ({changed} field(s))")
    print(f"ok: {changed} of {len(sets) + len(args.remove or [])} requested field(s) changed "
          f"in {target.relative_to(vault)}")
    return 1 if notes and not changed else 0


def cmd_contact_update(args: argparse.Namespace) -> int:
    """Enrich an existing contact: set frontmatter fields, optionally append body lines.

    The path a stub takes from auto-created to filled in. Appending never rewrites
    what is already in the body.
    """
    vault = Path(args.vault).resolve()
    candidates = [vault / "inbox" / "contacts" / sub / f"{args.slug}.md"
                  for sub in ("people", "organizations")]
    target = next((c for c in candidates if c.is_file()), None)
    if target is None:
        print(f"fail: no contact '{args.slug}' under inbox/contacts/", file=sys.stderr)
        return 1
    try:
        sets = _parse_set_pairs(args.set)
    except ValueError as exc:
        print(f"fail: {exc}", file=sys.stderr)
        return 1
    changed, notes = _edit_frontmatter_in_place(target, sets, args.remove or [])
    for note in notes:
        print(f"  {note}")
    appended = 0
    if args.append:
        text = target.read_text(encoding="utf-8")
        addition = "\n".join(args.append)
        target.write_text(text.rstrip() + "\n\n" + addition + "\n", encoding="utf-8")
        appended = len(args.append)
    if changed or appended:
        _append_activity_log(vault, args.agent or "zanmai.py",
                             f"updated contact {args.slug} ({changed} field(s), {appended} line(s) appended)")
    print(f"ok: contact {args.slug}: {changed} of {len(sets) + len(args.remove or [])} "
          f"field(s) changed, {appended} line(s) appended")
    return 0


# ---------------------------------------------------------------------------
# Keeping memory readable: rotate the record, curate the rules.
#
# Two different problems that look like one. A chronological record (the activity
# log) only ever grows and is read by grep, so it wants rotating by month and never
# reading whole. A rules file (an agent's lessons, the general memory) is read at the
# start of every run, so its size is paid for on every dispatch: measured on a real
# vault after three days of use, one agent's lessons had reached 48 KB across 42
# entries, and that whole file went into the run's context each time.
#
# The move that works on the rules file is NOT rotating by date. A standing rule has
# no expiry, and "do not suggest that tool again" rotated out in September means it
# gets suggested again in September. What rotates is the *why*: the headline and the
# bounds are what a run needs to apply a rule, the paragraph explaining how it was
# learned is what a person needs when they doubt it. So the rule stays and the
# reasoning moves, leaving a pointer. A struck entry leaves altogether, because its
# whole content is that it no longer applies.
# ---------------------------------------------------------------------------

# The status field is optional, and that is not a detail: entries written without one
# did not match a stricter pattern, were swallowed into the entry above them, and got
# archived along with its reasoning. A rule silently disappearing is the worst thing
# this command could do, so the headline is what is required and everything else is
# read only when it is there.
LESSON_HEAD = re.compile(r"^##\s+\[(\d{4}-\d{2})-\d{2}\]\s*(.+)$")
STATUS_WORDS = ("provisional", "confirmed", "standing", "struck", "disproven",
                "withdrawn", "retracted", "partly")


def _split_status(remainder: str) -> tuple[str, str]:
    """Pull a leading status off a headline, only where one is actually there.

    Splitting on the first dash would turn a headline that happens to contain one
    into a status, so the part before it has to look like a status to count as one.
    """
    for sep in (" \u2014 ", " - "):
        if sep in remainder:
            head, rest = remainder.split(sep, 1)
            if any(word in head.lower() for word in STATUS_WORDS):
                return head.strip(), rest.strip()
    return "", remainder.strip()
WHY_LINE = re.compile(r"^\s*-\s+\*\*Why:\*\*")
STRUCK_MARKERS = ("struck", "disproven", "withdrawn", "retracted")


def _archive_dir(source: Path) -> Path:
    return source.parent / f"{source.stem}-archive"


def _split_lesson_entries(text: str) -> tuple[str, list[tuple[str, str, str, list[str]]]]:
    """(preamble, [(month, status, headline, body-lines)]) for a lessons file."""
    lines = text.split("\n")
    # Every `## ` line is a boundary, whether or not it carries a date. A heading this
    # command does not understand must still end the entry above it, or it gets carried
    # off with that entry's reasoning. Entries with no date are kept exactly as they
    # are: not trimmed, not archived, not reordered.
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    if not starts:
        return text, []
    preamble = "\n".join(lines[:starts[0]]).rstrip() + "\n"
    entries = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        match = LESSON_HEAD.match(lines[start])
        if match is None:
            entries.append(("", "keep", lines[start], lines[start + 1:end]))
            continue
        status, _headline = _split_status(match.group(2))
        entries.append((match.group(1), status, lines[start], lines[start + 1:end]))
    return preamble, entries


def cmd_memory_curate(args: argparse.Namespace) -> int:
    """Move what a run does not need out of a rules file, keep every rule that stands.

    Three moves, and only the first two are a script's business:
      1. A struck or disproven entry leaves the file entirely. It is history the
         moment it is struck, and history belongs where history is read.
      2. A long `Why:` block moves to the archive and leaves a pointer. The headline
         and the bounds stay, because those are what applying the rule needs.
      3. An entry still marked provisional after a while is reported, not touched.
         Confirming or striking it is a judgement, and quietly dropping an unconfirmed
         lesson would lose exactly the ones that were never checked.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such memory file: {args.file}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")
    preamble, entries = _split_lesson_entries(text)
    if not entries:
        print(f"ok: {source.relative_to(vault)} has no dated entries, nothing to curate "
              f"({len(text.splitlines())} line(s))")
        return 0

    kept: list[tuple[str, str, list[str]]] = []
    archived: dict[str, list[str]] = {}
    moved_out = 0
    trimmed = 0
    provisional_old = []
    today = _today()

    for month, status, head, body in entries:
        lowered = status.lower()
        if status == "keep" and not month:
            kept.append((head, status, body))
            continue
        if any(marker in lowered for marker in STRUCK_MARKERS):
            archived.setdefault(month, []).extend([head, *body, ""])
            moved_out += 1
            continue
        why_at = next((i for i, line in enumerate(body) if WHY_LINE.match(line)), None)
        if why_at is not None:
            why_block = body[why_at:]
            if len([line for line in why_block if line.strip()]) > args.why_lines:
                archived.setdefault(month, []).extend([head, *why_block, ""])
                pointer = (f"- **Why:** moved to `{_archive_dir(source).name}/{month}.md` "
                           f"to keep this file to the rules themselves.")
                body = body[:why_at] + [pointer]
                trimmed += 1
        if "provisional" in lowered and "confirmed" not in lowered:
            if month < today[:7]:
                provisional_old.append(head)
        kept.append((head, status, body))

    if args.dry_run:
        print(f"would keep {len(kept)} entry/entries, move {moved_out} struck one(s) out, "
              f"trim {trimmed} reasoning block(s)")
    else:
        if archived:
            adir = _archive_dir(source)
            adir.mkdir(exist_ok=True)
            for month, lines in sorted(archived.items()):
                target = adir / f"{month}.md"
                existing = target.read_text(encoding="utf-8") if target.is_file() else (
                    f"# {source.stem}, {month}\n\n"
                    "Struck entries and the reasoning behind entries that still stand. Read when a "
                    "rule is in doubt or a pattern is being traced, never at the start of a run.\n\n"
                )
                target.write_text(existing.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n",
                                  encoding="utf-8")
        out = [preamble.rstrip(), ""]
        for head, _status, body in kept:
            out.append(head)
            out.extend(body)
            if body and body[-1].strip():
                out.append("")
        if archived:
            out.append(f"Older reasoning and struck entries: `{_archive_dir(source).name}/`\n")
        source.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        _append_activity_log(vault, args.agent or "zanmai.py",
                             f"curated {source.relative_to(vault)} "
                             f"({moved_out} struck moved out, {trimmed} reasoning block(s) archived)")

    before = len(text.splitlines())
    after = len(source.read_text(encoding="utf-8").splitlines()) if not args.dry_run else before
    print(f"ok: {source.relative_to(vault)}: {len(entries)} entry/entries, {len(kept)} still stand, "
          f"{moved_out} struck moved out, {trimmed} reasoning block(s) archived, "
          f"{before} lines to {after}")
    if provisional_old:
        print(f"    {len(provisional_old)} entry/entries are still provisional from an earlier month. "
              "Confirm or strike them; a script must not drop a lesson nobody checked:")
        for head in provisional_old[:args.show]:
            print(f"      {head[:110]}")
    return 0


def cmd_memory_rotate(args: argparse.Namespace) -> int:
    """Move a chronological log's older months into an archive, leaving an index.

    For a record that is only ever appended to and only ever read by searching, which
    is what the activity log is. Nothing is lost; it moves to where the search still
    finds it and the read at session start does not.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such log: {args.file}", file=sys.stderr)
        return 1
    text = source.read_text(encoding="utf-8")
    lines = text.split("\n")
    keep_from = args.keep_months
    cutoff = (datetime.now(timezone.utc) - timedelta(days=31 * keep_from)).strftime("%Y-%m")
    header = []
    by_month: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        match = re.match(r"^##\s+\[(\d{4}-\d{2})-\d{2}", line)
        if match:
            current = match.group(1)
        if current is None:
            header.append(line)
            continue
        by_month.setdefault(current, []).append(line)
    old = {m: ls for m, ls in by_month.items() if m < cutoff}
    if not old:
        print(f"ok: nothing older than {cutoff} in {source.relative_to(vault)} "
              f"({len(by_month)} month(s), {len(lines)} line(s)); nothing moved")
        return 0
    adir = _archive_dir(source)
    if not args.dry_run:
        adir.mkdir(exist_ok=True)
        for month, month_lines in sorted(old.items()):
            target = adir / f"{month}.md"
            existing = target.read_text(encoding="utf-8") if target.is_file() else (
                f"# {source.stem}, {month}\n\n"
                "Moved out of the live log so it stays short. Searched, not read.\n"
            )
            target.write_text(existing.rstrip() + "\n\n" + "\n".join(month_lines).rstrip() + "\n",
                              encoding="utf-8")
        rest = [ln for m, ls in sorted(by_month.items()) if m >= cutoff for ln in ls]
        index = [f"Earlier months: `{adir.name}/` ("
                 + ", ".join(sorted(old)) + ")"]
        source.write_text("\n".join(header).rstrip() + "\n\n" + "\n".join(index) + "\n\n"
                          + "\n".join(rest).rstrip() + "\n", encoding="utf-8")
        _append_activity_log(vault, "zanmai.py",
                             f"rotated {source.relative_to(vault)} ({len(old)} month(s) archived)")
    moved = sum(len(ls) for ls in old.values())
    print(f"ok: {source.relative_to(vault)}: {len(old)} month(s) moved to {adir.name}/ "
          f"({moved} line(s)), {len(by_month) - len(old)} month(s) left in place")
    return 0


MEMORY_READ_EVERY_RUN = (
    (".zanmai/memory/general.md", 400),
    (".zanmai/memory/agents/*/lessons.md", 400),
    (".zanmai/memory/technique/*.md", 400),
)


def _memory_size_report(vault: Path) -> list[str]:
    """Files that go into a run's context, and whether any has outgrown being read.

    A line budget rather than a byte one, because that is what a person editing the
    file can see. The threshold is a prompt to curate, not a failure: nothing is
    broken, it is just being paid for on every dispatch.
    """
    notes = []
    for pattern, limit in MEMORY_READ_EVERY_RUN:
        for path in sorted(vault.glob(pattern)):
            if not path.is_file():
                continue
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > limit:
                notes.append(
                    f"{path.relative_to(vault)} is {count} lines and is read at the start of a run. "
                    f"Over {limit} it is worth curating: `memory curate --file "
                    f"{path.relative_to(vault)}` moves struck entries and old reasoning out and "
                    "leaves the rules."
                )
    return notes


# ---------------------------------------------------------------------------
# Voice notes: speech in, and the vault is what makes the transcript accurate.
#
# A dropped recording is the cheapest way to get something into the vault, and the
# worst thing about it is always the same: speech to text mangles exactly the words
# that carry the meaning, the names. A person, a nickname, a product, a project.
# Zanmai has an advantage no general transcriber has, and it grows with use: the vault
# already holds those names. So they are handed to the recogniser BEFORE it starts, as
# an initial prompt, which biases it toward the words that occur in this life rather
# than the words that are common in general. What it still gets wrong is corrected
# against the same list afterwards, and every substitution is written down, because
# silently rewriting what someone said is worse than the error.
#
# Local, not a service. A spoken journal entry is the most private material in the
# vault, so it is transcribed on this machine, with no key and nothing uploaded.
# ---------------------------------------------------------------------------

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac",
              ".aiff", ".aif", ".caf", ".amr", ".wma", ".mp4", ".m4b", ".mov")

# whisper accepts an initial prompt of at most half its text context, a few hundred
# tokens. So the list has to be short and ordered by what gets mangled most: people
# first, then the organisations and products around them, then recurring subjects. A
# longer list would simply be cut off at an arbitrary point.
LEXICON_BUDGET_CHARS = 800


def _tool_path(vault: Path, tool_id: str) -> str | None:
    """Where this machine's copy of a registered tool is, or None.

    Goes through the register rather than calling `which` on a hard-coded name, which
    is what the register is for: the invocation name differs per platform (a `.exe` on
    Windows), and a tool this vault fetched itself sits in its own runtime tree and is
    not on PATH at all. Asking `which` for one spelling gets both of those wrong.
    """
    spec = (_load_register().get("tools") or {}).get(tool_id)
    if not spec:
        return shutil.which(tool_id)
    found = _detect_tool(vault, tool_id, spec, _current_os())
    if found.get("present") and found.get("path"):
        return found["path"]
    if found.get("present"):
        osspec = (spec.get("os") or {}).get(_current_os()) or {}
        return shutil.which(osspec.get("invoke") or tool_id)
    return None


def _recordings_dir(vault: Path) -> Path:
    d = vault / "_import" / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_duration(path: Path, vault: Path | None = None) -> float | None:
    probe = (_tool_path(vault, "ffprobe") if vault else None) or shutil.which("ffprobe")
    if not probe:
        return None
    try:
        out = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError):
        return None


def _spoken_length(seconds: float) -> str:
    """Seconds under a minute, because "0 min" for a 13-second note reads as broken."""
    if seconds < 60:
        return f"{seconds:.0f} sec"
    return f"{seconds / 60:.1f} min"


# The file's own date orders the set, because a recorder writes it against the local
# clock the moment the recording is made, while arrival is not something the speaker
# controls: a note spoken in a dead spot or at the gym syncs whenever it syncs. What the
# name says is the fallback, for a file that carries no usable date, and otherwise the
# cross-check: where the two disagree, something is wrong and it is said rather than
# quietly sorted.
_NAME_STAMP_PATTERNS = (
    # 2026-08-01 14-32-05, 2026-08-01_1432, 20260801-1432, with any separators
    re.compile(r"(?P<y>20\d{2})[-_.]?(?P<mo>\d{2})[-_.]?(?P<d>\d{2})"
               r"(?:[-_.T ]?(?P<h>\d{2})[-_.:]?(?P<mi>\d{2})(?:[-_.:]?(?P<s>\d{2}))?)?"),
)
_NAME_SEQ_PATTERN = re.compile(r"(?:^|[^0-9])(\d{1,5})(?=[^0-9]*$)")


def _recording_name_key(path: Path) -> tuple[int, float, str, str] | None:
    """What the file name says about when this was recorded, or None if it says nothing."""
    for pattern in _NAME_STAMP_PATTERNS:
        m = pattern.search(path.name)
        if not m:
            continue
        parts = m.groupdict()
        try:
            stamp = datetime(int(parts["y"]), int(parts["mo"]), int(parts["d"]),
                             int(parts["h"] or 0), int(parts["mi"] or 0), int(parts["s"] or 0),
                             tzinfo=timezone.utc)
        except ValueError:
            break
        return (1, stamp.timestamp(), "name", stamp.strftime("%Y-%m-%d %H:%M"))
    seq = _NAME_SEQ_PATTERN.search(path.stem)
    if seq:
        return (2, float(seq.group(1)), "number", f"no. {seq.group(1)}")
    return None


def _recording_order_key(path: Path) -> tuple[int, float, str, str]:
    """(rank, value, basis, shown) so the order can be explained, not just applied.

    Rank 0 is the file's own date, which is when the recording was made. Rank 1 and 2 are
    what the name says, a timestamp or a running number, used when there is no date to
    read. Mixing them in one folder is normal, so they are ranked rather than compared as
    if they were the same kind of thing.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    if mtime:
        return (0, mtime, "file date",
                datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"))
    return _recording_name_key(path) or (3, 0.0, "no signal", "unknown")


def _recording_order_disagreement(files: list[Path]) -> str | None:
    """Where the dates and the names tell different stories, name the pair.

    Both orders are cheap to compute and they should agree. When they do not, one of the
    two has been rewritten somewhere between the recorder and this folder, and sorting on
    regardless is how a correction ends up before the thing it corrects.
    """
    named = [(f, _recording_name_key(f)) for f in files]
    if any(key is None for _f, key in named):
        return None  # a name that says nothing about order cannot contradict anything
    if len({key[0] for _f, key in named}) != 1:
        return None  # timestamps in some names and running numbers in others: not comparable
    by_name = [f for f, _k in sorted(named, key=lambda pair: pair[1][1])]
    by_date = sorted(files, key=_recording_order_key)
    if by_name == by_date:
        return None
    for a, b in zip(by_date, by_name):
        if a != b:
            return f"{a.name} vs {b.name}"
    return "order differs"


def _pending_recordings(vault: Path) -> list[Path]:
    folder = _recordings_dir(vault)
    return sorted((f for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in AUDIO_EXTS),
                  key=_recording_order_key)


def cmd_voice_scan(args: argparse.Namespace) -> int:
    """What is waiting to be transcribed, oldest first, with the count said out loud.

    Oldest first because several notes recorded in a row are usually one train of
    thought, and the order they were spoken in is the order they make sense in.
    """
    vault = Path(args.vault).resolve()
    folder = _recordings_dir(vault)
    files = _pending_recordings(vault)
    other = sorted(f.name for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() not in AUDIO_EXTS
                   and not f.name.startswith("."))
    total = 0.0
    bases: dict[str, int] = {}
    for f in files:
        seconds = _audio_duration(f)
        _rank, _value, basis, shown = _recording_order_key(f)
        bases[basis] = bases.get(basis, 0) + 1
        length = _spoken_length(seconds) if seconds else "length unknown"
        if seconds:
            total += seconds
        print(f"{shown:>16}  {length:>14}  ({basis})  {f.name}")
    print(f"ok: {len(files)} recording(s) waiting in _import/recordings/"
          + (f", {_spoken_length(total)} in total" if total else "")
          + (f", {len(other)} other file(s) left alone" if other else ""))
    if files:
        print("    ordered oldest first, by "
              + ", ".join(f"{basis} ({count})" for basis, count in sorted(bases.items())))
        clash = _recording_order_disagreement(files)
        if clash:
            print(f"    dates and names disagree ({clash}). Something rewrote one of the two; "
                  "read the notes before trusting the sequence.")
    if other:
        print("    not audio: " + ", ".join(other[:5]))
    return 0


def cmd_voice_lexicon(args: argparse.Namespace) -> int:
    """The names this vault holds, as a head start for the recogniser.

    Second line of defence, deliberately small. The first line is reading the transcript
    and understanding it: a garbled word gets resolved the way a person resolves a typo,
    from the sense of the sentence, and that needs no list at all. What understanding
    cannot reach is a surname nobody could infer, a company spelled a particular way, a
    term only this vault uses. That is what this is for, and it is worth having: measured,
    it fixed every name in a note where full names were spoken. Measured on ten minutes of
    a real meeting it changed almost nothing, because people say first names in a room and
    a recogniser knows those. A fallback that costs a flag on a call which happens anyway
    is worth keeping even when it is rarely the thing that saves the day.

    The one thing worth getting right is which names, because a prompt holds a few
    hundred characters and a vault holds hundreds of contacts. Ordered by how much the
    vault links to each one: a name a dozen notes point at is someone this person works
    with, a name nothing points at is a directory entry. Measured on a real vault of
    ninety-five contacts, filling alphabetically left out five of the six people in the
    recording being transcribed.
    """
    vault = Path(args.vault).resolve()

    inbound: dict[str, int] = {}
    patterns = vault / ".zanmai" / "memory" / "patterns.json"
    if patterns.is_file():
        try:
            hubs = json.loads(patterns.read_text(encoding="utf-8")).get("wikilink_hubs") or {}
            inbound = {slug: len((e or {}).get("linked_from") or []) for slug, e in hubs.items()}
        except (json.JSONDecodeError, OSError):
            pass

    def read_name(path: Path) -> tuple[str, dict]:
        fm, _order, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        for line in body.splitlines():
            if line.startswith("# "):
                return line[2:].strip(), fm
        return path.stem.replace("-", " ").title(), fm

    # An organisation's display name, so a person's `org` field does not put a slug
    # into a prompt: a hyphenated slug is not a word anybody says out loud.
    org_names: dict[str, str] = {}
    org_folder = vault / "inbox" / "contacts" / "organizations"
    if org_folder.is_dir():
        for f in sorted(org_folder.glob("*.md")):
            org_names[f.stem], _fm = read_name(f)

    # (rank, term). The house names first: they work before the vault holds anything,
    # and a spoken instruction names a specialist.
    ranked: list[tuple[int, str]] = [(10 ** 6, "Zanmai")]
    ranked += [(10 ** 6, name.capitalize()) for name, _a, _m in _ROSTER]

    for folder, is_person in ((vault / "inbox" / "contacts" / "people", True),
                              (org_folder, False)):
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*.md")):
            name, fm = read_name(f)
            links = inbound.get(f.stem, 0)
            ranked.append((links, name))
            nickname = fm.get("nickname")
            if isinstance(nickname, str) and nickname.strip():
                ranked.append((links, nickname.strip()))
            elif isinstance(nickname, list):
                ranked += [(links, n) for n in nickname if isinstance(n, str) and n.strip()]
            if is_person:
                org = fm.get("org")
                if isinstance(org, str) and org.strip():
                    ranked.append((links, org_names.get(org.strip(), org.strip())))

    for kind in ("focus", "habits", "knowledge"):
        folder = vault / "inbox" / kind
        if not folder.is_dir():
            continue
        for bundle in sorted(folder.iterdir()):
            if bundle.is_dir():
                title, _fm = read_name(bundle / f"{bundle.name}.md") if (
                    bundle / f"{bundle.name}.md").is_file() else (
                    bundle.name.replace("-", " "), {})
                ranked.append((inbound.get(bundle.name, 0), title))

    seen: set[str] = set()
    kept: list[str] = []
    used = 0
    for _links, term in sorted(ranked, key=lambda e: -e[0]):
        key = term.lower()
        if key in seen or len(term) < 2:
            continue
        seen.add(key)
        if used + len(term) + 2 > args.budget:
            continue
        kept.append(term)
        used += len(term) + 2

    prompt = ", ".join(kept)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = vault / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt + "\n", encoding="utf-8")
    print(prompt)
    print(f"ok: {len(kept)} of {len(seen)} name(s) fit the prompt "
          f"({used} of {args.budget} characters), most linked-to first", file=sys.stderr)
    return 0


def _whisper_model(vault: Path) -> Path | None:
    folder = vault / ".zanmai" / "runtime" / "whisper"
    models = sorted(folder.glob("ggml-*.bin")) if folder.is_dir() else []
    return models[0] if models else None


def cmd_voice_transcribe(args: argparse.Namespace) -> int:
    """One recording to text, on this machine, biased by the vault's own names."""
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1

    ffmpeg = _tool_path(vault, "ffmpeg")
    whisper = _tool_path(vault, "whisper")
    model = _whisper_model(vault)
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg, which turns what a phone recorded into what the recogniser reads")
    if not whisper:
        missing.append("whisper-cli, the recogniser itself")
    if not model:
        missing.append("a model in .zanmai/runtime/whisper/ (about 1.6 GB, fetched once)")
    if missing:
        print("fail: cannot transcribe, and nothing will be guessed instead. Missing:",
              file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    work = vault / ".zanmai" / "work" / "voice"
    work.mkdir(parents=True, exist_ok=True)
    wav = work / f"{source.stem}-16k.wav"
    subprocess.run([ffmpeg, "-y", "-i", str(source), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)], check=True, capture_output=True)

    prompt = ""
    if args.lexicon:
        lex = Path(args.lexicon)
        if not lex.is_absolute():
            lex = vault / args.lexicon
        if lex.is_file():
            prompt = lex.read_text(encoding="utf-8").strip()

    cmd = [whisper, "-m", str(model), "-f", str(wav), "-l", args.language,
           "-oj", "-of", str(work / source.stem), "--no-prints"]
    if prompt:
        cmd += ["--prompt", prompt, "--carry-initial-prompt"]
    subprocess.run(cmd, check=True, capture_output=True)

    result = work / f"{source.stem}.json"
    if not result.is_file():
        print("fail: the recogniser wrote no result", file=sys.stderr)
        return 1
    data = json.loads(result.read_text(encoding="utf-8"))
    segments = data.get("transcription") or []
    text = re.sub(r"\s+", " ",
                  " ".join(s.get("text", "").strip() for s in segments)).strip()
    detected = ((data.get("result") or {}).get("language")) or args.language
    seconds = _audio_duration(source) or 0.0

    target = work / f"{source.stem}.txt"
    target.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"ok: {len(text.split())} word(s) from {_spoken_length(seconds)}, language {detected}, "
          + (f"biased by {len([x for x in prompt.split(',') if x.strip()])} vault name(s)"
             if prompt else "no vault names given, so names are likely wrong")
          + f"; text at {target.relative_to(vault)}", file=sys.stderr)
    return 0


def cmd_voice_archive(args: argparse.Namespace) -> int:
    """Move a processed recording out of the drop folder, and keep it.

    Out of `_import/` so it cannot be transcribed twice, and kept rather than deleted:
    it is the user's own recording, and a transcript is a reading of it, not a
    replacement for it.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1
    stamp = datetime.fromtimestamp(source.stat().st_mtime)
    target_dir = vault / "assets" / "recordings" / stamp.strftime("%Y") / stamp.strftime("%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{stamp.strftime('%Y-%m-%d-%H%M')}-{_slugify(source.stem)}{source.suffix.lower()}"
    target = target_dir / name
    if target.exists():
        target = target.with_name(f"{target.stem}-2{target.suffix}")
    shutil.move(str(source), str(target))
    _append_activity_log(vault, args.agent or "zanmai.py",
                         f"filed recording {target.relative_to(vault)}")
    print(f"ok: recording kept at {target.relative_to(vault)}")
    return 0


def cmd_memory_log(args: argparse.Namespace) -> int:
    r"""Append one line to the activity log in the canonical format.

    Hand-written appends drifted in format, which broke the one thing the log is
    for: `grep "^## \["` parsing cleanly.
    """
    vault = Path(args.vault).resolve()
    log = vault / ".zanmai" / "memory" / "activity-log.md"
    if not log.exists():
        print(f"fail: no activity log at {log.relative_to(vault)}", file=sys.stderr)
        return 1
    _append_activity_log(vault, args.agent, args.activity)
    print(f"ok: logged for {args.agent}")
    return 0


def _resolve_vault_file(vault: Path, given: str) -> Path | None:
    """Accept a vault-relative path or a bare basename that is unique in the vault."""
    direct = (vault / given).resolve()
    if direct.is_file() and str(direct).startswith(str(vault)):
        return direct
    name = Path(given).name
    if not name.endswith(".md"):
        name += ".md"
    hits = [p for p in vault.glob(f"inbox/**/{name}") if p.is_file()]
    if len(hits) == 1:
        return hits[0]
    return None


def cmd_index_search(args: argparse.Namespace) -> int:
    """Search the vault's own text, and say how much was searched.

    Why this exists as a command: the vault ships a `.gitignore` that excludes every
    user folder, on purpose, so that a clone never commits private material. Both
    common search tools honour `.gitignore` by default, so a plain recursive search
    finds only the distribution and reports an empty result. An empty result is
    indistinguishable from "does not exist", and that produced a confident written
    falsehood. Walking the tree here cannot be configured wrong, and the count of
    files searched is printed so a zero is a measurement rather than a silence.
    """
    vault = Path(args.vault).resolve()
    roots = [vault / r for r in (args.root or ["inbox", "quick", "assets", "_export", ".zanmai"])]
    try:
        pattern = re.compile(args.pattern, 0 if args.case_sensitive else re.IGNORECASE)
    except re.error as exc:
        print(f"fail: bad pattern: {exc}", file=sys.stderr)
        return 1
    exts = tuple(args.ext or [".md", ".txt", ".csv", ".json", ".yaml", ".typ", ".css"])
    searched = 0
    hits = 0
    for root in roots:
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in exts:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            searched += 1
            for n, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits += 1
                    print(f"{f.relative_to(vault)}:{n}: {line.strip()[:200]}")
                    if args.max_hits and hits >= args.max_hits:
                        print(f"ok: stopped at {hits} hit(s); {searched} file(s) searched so far")
                        return 0
    print(f"ok: {hits} hit(s) in {searched} file(s) searched")
    return 0


# ---------------------------------------------------------------------------
# Work objects: one file per piece of work, and it owns the work.
#
# Before this, a piece of work had no owner. What it was lived in the chat, the
# result lived in `_export/`, the working files lived in `.zanmai/work/` and the
# open question lived nowhere at all, so it died when the session did. Every one
# of those is a different container with a different lifetime, and the user paid
# for it: a specialist re-briefed from scratch every round, decisions taken three
# weeks ago that nobody could name afterwards, and no figure for what any of it
# had cost.
#
# The object is a row in a database the user can open and answer in, plus a page
# holding the long form. The row is CSV and the page is markdown, so both stay
# readable in any editor; ZenNotes renders the same folder as a table and a board
# with no export step, which is what makes "what is waiting on me" answerable
# away from the desk.
# ---------------------------------------------------------------------------

WORK_DIR_NAME = "work.base"
WORK_FIELDS = [
    ("id", "text", None, True),
    ("work", "text", None, False),
    ("state", "select", ["open", "waiting on you", "done"], False),
    ("owner", "text", None, False),
    ("waiting for", "text", None, False),
    ("deliverable", "text", None, False),
    ("workshop", "text", None, False),
    ("updated", "date", None, False),
    ("tokens", "number", None, False),
    ("minutes", "number", None, False),
]


# Sync-hosted vaults: the normal case, and what has to stay out of the copy.
#
# A vault in a synced folder is not an edge case, it is how most people get a
# backup, and it should keep working. What must not travel is what is true of one
# machine only: the provisioned interpreter and the record of which tools this
# computer has. Carried to a second machine they claim tools that are not there;
# carried into a restore they bring a runtime built for another platform. The
# snapshots are the other one, because they are full copies of the vault and a
# backup does not need a backup inside it.
MACHINE_LOCAL_PATHS = (".zanmai/runtime", ".zanmai/work")
BULKY_PATHS = (".zanmai/snapshots",)

SYNC_HOSTS = (
    ("iCloud Drive", "exclude by renaming the folder so it ends in `.nosync`, or move the vault out of iCloud"),
    ("OneDrive", "the client has no per-folder ignore file: exclude the folders in OneDrive settings, Account, Choose folders"),
    ("Dropbox", "add the paths to a `.dropboxignore` file at the top of your Dropbox folder"),
    ("Nextcloud", "the client has no per-folder ignore file: add the paths to the client's ignore list, Settings, General, Edit ignored files"),
    ("Google Drive", "the client has no per-folder ignore file: exclude the folders in the Drive preferences"),
)


def _detect_sync_host(vault: Path) -> str:
    """Which sync client is this vault sitting under, if any. Path and marker based."""
    text = str(vault).replace("\\", "/")
    if "Library/Mobile Documents/com~apple~CloudDocs" in text or "/iCloud" in text:
        return "iCloud Drive"
    if "/OneDrive" in text:
        return "OneDrive"
    if "CloudStorage/GoogleDrive" in text or "/Google Drive" in text:
        return "Google Drive"
    for parent in [vault, *vault.parents]:
        try:
            names = {p.name for p in parent.iterdir()}
        except OSError:
            continue
        if any(n.startswith(".sync_") and n.endswith(".db") for n in names):
            return "Nextcloud"
        if ".dropbox" in names or ".dropbox.cache" in names:
            return "Dropbox"
        if parent == parent.parent:
            break
    return ""


def _work_base(vault: Path) -> Path:
    return vault / "inbox" / "review" / WORK_DIR_NAME


def _work_uuid(seed: str) -> str:
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"zanmai:work:{seed}"))


def _work_ensure(vault: Path) -> tuple[Path, Path, list[str]]:
    """Create the database folder on first use and return (csv, schema, headers)."""
    base = _work_base(vault)
    csv_path = base / "data.csv"
    schema_path = base / "schema.json"
    pages = base / "pages"
    headers = [name for name, _t, _o, _h in WORK_FIELDS]
    if csv_path.is_file() and schema_path.is_file():
        return csv_path, schema_path, headers
    base.mkdir(parents=True, exist_ok=True)
    pages.mkdir(exist_ok=True)
    fields = []
    for name, ftype, options, hidden in WORK_FIELDS:
        field = {"id": _work_uuid(f"field:{name}"), "name": name, "type": ftype}
        if options:
            field["options"] = [
                {"id": _work_uuid(f"option:{name}:{value}"), "value": value} for value in options
            ]
        if hidden:
            field["hidden"] = True
        fields.append(field)
    by_name = {f["name"]: f["id"] for f in fields}
    table_view = {
        "id": _work_uuid("view:table"), "name": "Everything", "type": "table",
        "filters": [], "sorts": [{"fieldId": by_name["updated"], "direction": "desc"}],
        "columnOrder": [f["id"] for f in fields],
    }
    board_view = {
        "id": _work_uuid("view:board"), "name": "By state", "type": "board",
        "filters": [], "sorts": [], "groupByFieldId": by_name["state"],
        "boardColumnOrder": ["waiting on you", "open", "done"],
        "cardFieldIds": [by_name["work"], by_name["owner"], by_name["waiting for"]],
    }
    schema = {
        "version": 1, "idFieldId": by_name["id"], "fields": fields,
        "views": [board_view, table_view], "activeViewId": board_view["id"], "pages": {},
    }
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    if not csv_path.is_file():
        import csv as _csv
        import io
        buf = io.StringIO()
        _csv.writer(buf).writerow(headers)
        csv_path.write_text(buf.getvalue(), encoding="utf-8")
    return csv_path, schema_path, headers


def _work_read(vault: Path) -> tuple[list[dict], list[str]]:
    import csv as _csv
    csv_path, _schema, headers = _work_ensure(vault)
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        headers = reader.fieldnames or headers
    return rows, list(headers)


def _work_write(vault: Path, rows: list[dict], headers: list[str]) -> None:
    import csv as _csv
    csv_path, _schema, _h = _work_ensure(vault)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def _work_find(rows: list[dict], wanted: str) -> dict | None:
    """Match on the full id or on a leading fragment, so a human can type eight chars."""
    exact = [r for r in rows if r.get("id") == wanted]
    if exact:
        return exact[0]
    partial = [r for r in rows if str(r.get("id", "")).startswith(wanted)]
    return partial[0] if len(partial) == 1 else None


def _work_page(vault: Path, row_id: str) -> Path:
    return _work_base(vault) / "pages" / f"{row_id}.md"


def _work_register_page(vault: Path, row_id: str) -> None:
    _csv_path, schema_path, _h = _work_ensure(vault)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema.setdefault("pages", {})[row_id] = f"pages/{row_id}.md"
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def cmd_work_open(args: argparse.Namespace) -> int:
    """Open a work object. Returns its id, which every later call uses."""
    vault = Path(args.vault).resolve()
    rows, headers = _work_read(vault)
    row_id = _work_uuid(f"{_timestamp_log()}:{args.title}")
    row = {h: "" for h in headers}
    row.update({
        "id": row_id, "work": args.title, "state": "open", "owner": args.owner or "",
        "deliverable": args.deliverable or "", "workshop": args.workshop or "",
        "updated": _today(),
    })
    rows.append(row)
    _work_write(vault, rows, headers)
    page = _work_page(vault, row_id)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f"# {args.title}\n\n"
        f"Opened {_today()}"
        + (f" for {args.owner}" if args.owner else "") + ".\n\n"
        "## What finished looks like\n\n"
        + ((args.goal or "").strip() + "\n\n" if args.goal else "(not stated yet)\n\n")
        + "## Waiting on you\n\n(nothing yet)\n\n"
        "## Decided\n\n"
        "## Log\n\n"
        f"- {_timestamp_log()} opened\n",
        encoding="utf-8")
    _work_register_page(vault, row_id)
    _append_activity_log(vault, args.owner or "zanmai.py", f"opened work '{args.title}' ({row_id[:8]})")
    print(f"ok: work opened, id {row_id}")
    print(f"    short id usable everywhere: {row_id[:8]}")
    return 0


def _work_touch(row: dict) -> None:
    row["updated"] = _today()


def _work_append_section(page: Path, heading: str, text: str) -> None:
    """Append under an existing heading, keeping everything already written."""
    content = page.read_text(encoding="utf-8") if page.is_file() else ""
    marker = f"## {heading}"
    if marker not in content:
        content = content.rstrip() + f"\n\n{marker}\n\n{text}\n"
    else:
        head, rest = content.split(marker, 1)
        lines = rest.split("\n")
        # Drop a placeholder line if that is all the section holds.
        body_end = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.startswith("## "):
                body_end = i
                break
        kept = [ln for ln in lines[:body_end]
                if ln.strip() and ln.strip() not in ("(nothing yet)", "(none yet)")]
        kept.append(text)
        content = head + marker + "\n\n" + "\n".join(kept) + "\n\n" + "\n".join(lines[body_end:]).lstrip("\n")
    page.write_text(content, encoding="utf-8")


def cmd_work_ask(args: argparse.Namespace) -> int:
    """Record something only the user can settle, and mark the object as waiting."""
    vault = Path(args.vault).resolve()
    rows, headers = _work_read(vault)
    row = _work_find(rows, args.id)
    if row is None:
        print(f"fail: no single work object matching id '{args.id}'", file=sys.stderr)
        return 1
    row["state"] = "waiting on you"
    row["waiting for"] = args.question.split("\n")[0][:160]
    _work_touch(row)
    _work_write(vault, rows, headers)
    page = _work_page(vault, row["id"])
    _work_append_section(page, "Waiting on you", f"- **{_today()}** {args.question}")
    _work_append_section(page, "Log", f"- {_timestamp_log()} asked: {args.question.splitlines()[0][:120]}")
    print(f"ok: {row['id'][:8]} is waiting on the user")
    return 0


def cmd_work_answer(args: argparse.Namespace) -> int:
    """Record the user's answer and put the object back to work."""
    vault = Path(args.vault).resolve()
    rows, headers = _work_read(vault)
    row = _work_find(rows, args.id)
    if row is None:
        print(f"fail: no single work object matching id '{args.id}'", file=sys.stderr)
        return 1
    row["state"] = "open"
    row["waiting for"] = ""
    _work_touch(row)
    _work_write(vault, rows, headers)
    page = _work_page(vault, row["id"])
    _work_append_section(page, "Decided", f"- **{_today()}** {args.answer}")
    _work_append_section(page, "Log", f"- {_timestamp_log()} answered")
    print(f"ok: {row['id'][:8]} answered and back to open")
    return 0


def cmd_work_log(args: argparse.Namespace) -> int:
    """Append one line to the object's log, and add up what the work has cost."""
    vault = Path(args.vault).resolve()
    rows, headers = _work_read(vault)
    row = _work_find(rows, args.id)
    if row is None:
        print(f"fail: no single work object matching id '{args.id}'", file=sys.stderr)
        return 1
    for field, given in (("tokens", args.tokens), ("minutes", args.minutes)):
        if given:
            try:
                row[field] = str(int(float(row.get(field) or 0)) + int(given))
            except ValueError:
                row[field] = str(given)
    if args.workshop:
        row["workshop"] = args.workshop
    if args.deliverable:
        row["deliverable"] = args.deliverable
    _work_touch(row)
    _work_write(vault, rows, headers)
    who = f"{args.agent}: " if args.agent else ""
    _work_append_section(_work_page(vault, row["id"]), "Log", f"- {_timestamp_log()} {who}{args.note}")
    print(f"ok: logged on {row['id'][:8]} (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_done(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    rows, headers = _work_read(vault)
    row = _work_find(rows, args.id)
    if row is None:
        print(f"fail: no single work object matching id '{args.id}'", file=sys.stderr)
        return 1
    row["state"] = "done"
    row["waiting for"] = ""
    _work_touch(row)
    _work_write(vault, rows, headers)
    _work_append_section(_work_page(vault, row["id"]), "Log", f"- {_timestamp_log()} closed")
    _append_activity_log(vault, args.agent or "zanmai.py", f"closed work '{row.get('work')}' ({row['id'][:8]})")
    print(f"ok: {row['id'][:8]} closed (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_list(args: argparse.Namespace) -> int:
    """What is open, and what is waiting on the user. Prints the denominator."""
    vault = Path(args.vault).resolve()
    rows, _headers = _work_read(vault)
    wanted = (args.state or "").strip().lower()
    shown = 0
    for row in sorted(rows, key=lambda r: (r.get("state") != "waiting on you", r.get("updated") or "")):
        if wanted and str(row.get("state", "")).lower() != wanted:
            continue
        shown += 1
        line = f"{row.get('id','')[:8]}  {str(row.get('state','')):14}  {row.get('work','')}"
        if row.get("owner"):
            line += f"  [{row['owner']}]"
        print(line)
        if row.get("waiting for"):
            print(f"          waiting for: {row['waiting for']}")
    waiting = sum(1 for r in rows if r.get("state") == "waiting on you")
    print(f"ok: {shown} of {len(rows)} work object(s) shown; {waiting} waiting on the user")
    return 0


def cmd_create_sub_bundle_truth(args: argparse.Namespace) -> int:
    """Write a truth file for an existing sub-bundle, with a parent-bundle
    wikilink in the body. The parent bundle is detected from the sub-bundle's
    folder path (one level up).

    `cmd_create_bundle` deliberately omits a truth file for sub-bundles
    (sub-bundles are folders-with-members, not hub-with-children). When the
    user's mental model actually treats the sub-bundle as a thematic node
    that needs a body and a parent-link, as in the recently established
    theme-hierarchy use (Niederlande > Zandvoort, Computer > Retrocomputing
    > Maximite), this command adds the truth file without re-running
    `bundle create`.

    The body holds a one-line "Part of [[<parent>]]" reference and a short
    title heading. Additional content is added later via ordinary edits.
    """
    vault = Path(args.vault).resolve()
    kind = args.kind
    if kind not in KIND_FIELDS:
        print(f"fail: unknown kind {kind}", file=sys.stderr)
        return 1
    segments, slug = _slugify_bundle_path(args.bundle_slug)
    if len(segments) < 2:
        print(f"fail: '{args.bundle_slug}' is not a sub-bundle path (must be parent/child or deeper)", file=sys.stderr)
        return 1
    bundle_dir = vault / "inbox" / kind / Path(*segments)
    if not bundle_dir.exists():
        print(f"fail: sub-bundle folder does not exist: {bundle_dir.relative_to(vault)}", file=sys.stderr)
        print("hint: run `bundle create --kind <k> --slug <parent>/<child>` first", file=sys.stderr)
        return 1
    truth_path = bundle_dir / f"{slug}.md"
    if truth_path.exists():
        print(f"fail: truth file already exists: {truth_path.relative_to(vault)}", file=sys.stderr)
        return 1

    parent_slug = segments[-2]
    title = args.title or slug.replace("-", " ").title()

    additions: dict = {"_title": title}
    for key in ("goal", "status", "cadence", "due", "topic", "last_done"):
        v = getattr(args, key, None)
        if v:
            additions[key] = v

    base_truth = _render_truth_file(kind=kind, slug=slug, additions=additions)

    # Inject parent wikilink into the body right after the title heading.
    parent_line = f"\nPart of [[{parent_slug}]].\n"
    if "\n# " in base_truth:
        head, _sep, rest = base_truth.partition("\n# ")
        title_end_idx = rest.find("\n")
        if title_end_idx >= 0:
            new_body = head + "\n# " + rest[:title_end_idx + 1] + parent_line + rest[title_end_idx + 1:]
        else:
            new_body = base_truth + parent_line
    else:
        new_body = base_truth + parent_line
    truth_path.write_text(new_body, encoding="utf-8")

    # The sub-bundle's own index has to learn that this file exists, and older indexes
    # additionally carry a sentence saying there is no truth file, which this command
    # has just made untrue. Both are dealt with here, so the state on disk matches
    # what the index claims about it.
    index_path = bundle_dir / "INDEX.md"
    if index_path.is_file():
        try:
            index_text = index_path.read_text(encoding="utf-8")
            stale = "This is a sub-bundle. Members are listed below, there is no separate truth file.\n"
            if stale in index_text:
                index_path.write_text(index_text.replace(stale, ""), encoding="utf-8")
        except OSError:
            pass
        _append_index(index_path, slug, summary="the bundle's main file")

    bundle_rel = bundle_dir.relative_to(vault).as_posix()
    _append_activity_log(
        vault, "zanmai.py",
        f"created sub-bundle truth {bundle_rel}/{slug}.md (parent [[{parent_slug}]])"
    )
    print(f"ok: sub-bundle truth at {truth_path.relative_to(vault)}, parent [[{parent_slug}]]")
    return 0






def cmd_rename_slug(args: argparse.Namespace) -> int:
    """Atomic slug rename for an existing markdown file in the vault.

    Performs five steps as one operation:
      1. Rename the markdown file in place (`<old>.md` -> `<new>.md`).
      2. Update the frontmatter `slug:` field to the new value.
      3. Rewrite vault-wide wikilinks via `update wikilinks` (honouring
         the default scope and hard-exclude rules).
      4. Refresh the master `INDEX.md`.
      5. Append one activity-log line.

    Replaces the previous five-step manual workaround (stage temp file,
    bundle add-file with new name, manual `source_detail` fix, trash old,
    update wikilinks). The manual sequence risked frontmatter corruption.

    The old slug is located either via `--bundle-slug`/`--bundle-kind` when
    given, or by a vault-wide search for `<old>.md` filtered by the hard-
    exclude set (no matches inside snapshots, logs, trash, archive, import,
    distribution). When the search returns multiple candidates, the command
    refuses and asks the caller to disambiguate.
    """
    vault = Path(args.vault).resolve()
    old_slug = args.old.strip()
    new_slug = args.new.strip()
    if not old_slug or not new_slug:
        print("fail: --old and --new must both be non-empty", file=sys.stderr)
        return 1
    if old_slug == new_slug:
        print("ok: nothing to do (old == new)")
        return 0

    # 1. Locate the existing file
    if args.bundle_slug:
        bundle_dir, _bundle_kind, _ = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
        if not bundle_dir:
            print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
            return 1
        old_path = bundle_dir / f"{old_slug}.md"
        if not old_path.exists():
            print(f"fail: file does not exist: {old_path.relative_to(vault)}", file=sys.stderr)
            return 1
    else:
        candidates = [
            m for m in vault.rglob(f"{old_slug}.md")
            if not _is_excluded_from_wikilink_ops(m.relative_to(vault).as_posix())
        ]
        if not candidates:
            print(f"fail: no file matching '{old_slug}.md' found in the active vault", file=sys.stderr)
            return 1
        if len(candidates) > 1:
            paths = "\n  ".join(str(c.relative_to(vault)) for c in candidates)
            print(f"fail: ambiguous, multiple files match '{old_slug}.md':\n  {paths}", file=sys.stderr)
            print("hint: pass --bundle-slug <slug> --bundle-kind <kind> to disambiguate", file=sys.stderr)
            return 1
        old_path = candidates[0]

    new_path = old_path.parent / f"{new_slug}.md"
    if new_path.exists():
        print(f"fail: target already exists: {new_path.relative_to(vault)}", file=sys.stderr)
        return 1

    # 2. Update frontmatter slug field
    text = old_path.read_text(encoding="utf-8")
    fm, order, body = _split_frontmatter(text)
    fm["slug"] = new_slug
    if "slug" not in order:
        order.insert(0, "slug")
    new_text = _render_frontmatter(fm, order) + body

    # 3. Write to new path, remove old
    new_path.write_text(new_text, encoding="utf-8")
    old_path.unlink()

    bundle_rel = old_path.parent.relative_to(vault).as_posix()

    # 4. Update wikilinks vault-wide via the existing subcommand
    wikilink_args = argparse.Namespace(vault=str(vault), old=old_slug, new=new_slug, scope=None)
    cmd_update_wikilinks(wikilink_args)

    # 5. Refresh master INDEX
    _update_master_index(vault)

    # 6. Activity log (one line capturing the whole atomic operation)
    _append_activity_log(
        vault, "zanmai.py",
        f"slug rename {old_slug} -> {new_slug} in {bundle_rel}"
    )

    print(f"ok: renamed {old_slug}.md -> {new_slug}.md in {bundle_rel}")
    return 0


_EMBED_EXTS = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "ics", "heic", "mp4", "mov", "svg", "tiff"}

_GENERIC_FOLDER_TOKENS = frozenset({
    "pkm", "inbox", "notes", "note", "import", "imports", "stuff", "misc",
    "files", "documents", "general", "various", "my", "life", "topics",
    "test", "tmp", "temp", "new", "old", "backup",
})


def cmd_inspect_scope(args: argparse.Namespace) -> int:
    """User-visible scan of an import scope. Walks the folder, counts files
    per extension, lists sub-folders, extracts folder-name token candidates,
    and counts embed references found inside markdown bodies.

    Designed to run before `index find`: gives the user a concrete look at
    what is in scope, and gives Hank the folder-token-candidates that must
    be added to the index find query.

    Output is plain text, ~20 lines, intended to be visible in chat.
    """
    vault = Path(args.vault).resolve()
    scope_arg = args.scope or ""
    candidate = Path(scope_arg)
    if not candidate.is_absolute():
        # Resolve relative scope against the vault, not the cwd.
        candidate = vault / scope_arg
    scope = candidate.resolve() if scope_arg else vault
    if not scope.exists() or not scope.is_dir():
        print(f"fail: scope is not a directory: {scope}", file=sys.stderr)
        return 1

    try:
        scope_rel = scope.relative_to(vault).as_posix()
    except ValueError:
        scope_rel = str(scope)

    ext_counts: dict[str, int] = {}
    folder_tokens: dict[str, int] = {}
    subfolders: list[tuple[str, int]] = []
    embed_refs: dict[str, int] = {"wiki": 0, "md": 0}

    for entry in scope.rglob("*"):
        if entry.is_dir():
            continue
        ext = entry.suffix.lstrip(".").lower() or "(none)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        if ext == "md":
            try:
                text = entry.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            embed_refs["wiki"] += len(_WIKI_EMBED_RE.findall(text))
            embed_refs["md"] += len(_MD_EMBED_RE.findall(text))

    for sub in sorted(scope.iterdir()):
        if not sub.is_dir():
            continue
        count = sum(1 for _ in sub.rglob("*") if _.is_file())
        subfolders.append((sub.name, count))
        for segment in sub.relative_to(scope).parts + (sub.name,):
            tokens = _tokenize(segment)
            for t in tokens:
                if t in _GENERIC_FOLDER_TOKENS or len(t) < 3:
                    continue
                folder_tokens[t] = folder_tokens.get(t, 0) + 1

    # Walk one level deeper for folder tokens to surface meaningful structure.
    for entry in scope.rglob("*"):
        if not entry.is_dir():
            continue
        try:
            rel_parts = entry.relative_to(scope).parts
        except ValueError:
            continue
        if not rel_parts:
            continue
        for part in rel_parts:
            for t in _tokenize(part):
                if t in _GENERIC_FOLDER_TOKENS or len(t) < 3:
                    continue
                folder_tokens[t] = folder_tokens.get(t, 0) + 1

    top_folder_tokens = sorted(folder_tokens.items(), key=lambda kv: -kv[1])[:15]

    lines = [f"scope: {scope_rel}", ""]
    lines.append("file counts by extension:")
    for ext, n in sorted(ext_counts.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"  .{ext}: {n}")
    lines.append("")
    lines.append(f"sub-folders (top-level, {len(subfolders)} total):")
    for name, n in subfolders[:12]:
        lines.append(f"  {name}/  ({n} files)")
    if len(subfolders) > 12:
        lines.append(f"  ... and {len(subfolders) - 12} more")
    lines.append("")
    lines.append("folder-name token candidates (domain-bearing, generic stripped):")
    if top_folder_tokens:
        lines.append("  " + ", ".join(f"{t} ({n})" for t, n in top_folder_tokens))
    else:
        lines.append("  (none above threshold)")
    lines.append("")
    lines.append(f"embed references found in markdown bodies: "
                 f"{embed_refs['wiki']} wiki-style ![[..]], "
                 f"{embed_refs['md']} markdown ![](..)")
    lines.append("")
    lines.append("next step: pass the user's tokens PLUS the folder-name candidates above "
                 "to `zanmai.py index find --tokens \"...\"`.")

    print("\n".join(lines))
    return 0

_WIKI_EMBED_RE = re.compile(r"!\[\[([^\]|]+?)(\|[^\]]*)?\]\]")
_MD_EMBED_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _rename_map_path(vault: Path) -> Path:
    """Location of the attachment rename map. AI-internal state, not in the
    user vault. Hidden so it does not appear in the user's file listings."""
    return vault / ".zanmai" / "memory" / ".embed-rename-map.json"


def _load_rename_map(vault: Path) -> dict[str, str]:
    """Read the attachment rename map (original-basename -> new-basename).
    Returns an empty dict when the file is missing or unreadable."""
    path = _rename_map_path(vault)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_rename_map(vault: Path, mapping: dict[str, str]) -> None:
    """Write the attachment rename map. Creates the parent directory if
    needed."""
    path = _rename_map_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_rename(vault: Path, original_name: str, new_name: str) -> None:
    """Record that an attachment was copied with a rename (original -> new).
    `update embeds` reads this map when the direct-basename and prefix-fallback
    lookups fail, so plan-driven renames at copy time get resolved automatically."""
    if not original_name or not new_name or original_name == new_name:
        return
    mapping = _load_rename_map(vault)
    mapping[original_name] = new_name
    _save_rename_map(vault, mapping)


def cmd_update_embeds(args: argparse.Namespace) -> int:
    """Rewrite `![[basename]]` and `![alt](path)` embeds in a bundle's markdown
    bodies so they point to the shared vault-root `assets/` folder.

    Walks every `.md` file under the bundle directory (recursive, so sub-bundles
    are included). For each embed match, looks up the basename in the vault-root
    `assets/` folder. If found, the embed is rewritten with the path relative
    to the markdown file's folder. Body text outside embeds is untouched.

    Resolution order per embed:
      1. Direct basename match in the assets index.
      2. `<md-stem>-<basename>` prefix-fallback for generic-source-name renames.
      3. Attachment rename map (`.zanmai/memory/.embed-rename-map.json`) for
         plan-driven renames recorded by `asset add` (when the import plan
         renames a source basename on copy, the body still references the old
         name and resolves via the map).

    Idempotent: a second run finds the embeds already point at the right place
    and exits with zero changes.

    Pass `--clear-rename-map` to wipe the map after a successful pass, useful
    at the end of an import wave to keep the map from growing across unrelated
    operations.
    """
    vault = Path(args.vault).resolve()
    bundle_dir, bundle_kind, _leaf = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1

    # Build an index of every asset in the shared vault-root assets/ folder,
    # keyed by basename.
    # Recursive: assets sit in subfolders as often as not (`assets/eu-ai-act/…`).
    # Indexing only the top level meant the lookup could not see them, and the run
    # then reported "0 rewritten in 0 files", which reads exactly like "nothing to
    # do" while four embeds sat unresolved.
    assets_dir = vault / "assets"
    attachments_index: dict[str, Path] = {}
    ambiguous: dict[str, int] = {}
    if assets_dir.is_dir():
        for f in sorted(assets_dir.rglob("*")):
            if not f.is_file():
                continue
            ext = f.suffix.lstrip(".").lower()
            if ext not in _EMBED_EXTS:
                continue
            if f.name in attachments_index:
                ambiguous[f.name] = ambiguous.get(f.name, 1) + 1
                continue
            attachments_index[f.name] = f

    if not attachments_index:
        print("ok: 0 assets indexed under assets/ (nothing this run could resolve against)")
        return 0

    rename_map = _load_rename_map(vault)
    files_changed: list[str] = []
    embeds_rewritten = 0
    # Counted so a zero can be told apart from a nothing: "0 rewritten" is a result
    # when it comes with "of 4 embeds seen, 4 already correct" and a failure when it
    # comes with "of 4 seen, 4 unresolved".
    embeds_seen = 0
    unresolved: list[str] = []

    def lookup_attachment(basename: str, md_stem: str, md_path: Path) -> tuple[Path | None, str | None]:
        """Find the attachment for an embed basename. Resolution order:
        direct basename, `<md-stem>-<basename>` prefix, every parent-dir name
        from md.parent up to the bundle root as `<dir>-<basename>` prefix
        (catches assets prefixed with the bundle-slug or any sub-bundle slug
        instead of the member's md-stem), then the rename map."""
        direct = attachments_index.get(basename)
        if direct is not None:
            return direct, basename
        prefixed_name = f"{md_stem}-{basename}"
        prefixed = attachments_index.get(prefixed_name)
        if prefixed is not None:
            return prefixed, prefixed_name
        p = md_path.parent
        bundle_parent = bundle_dir.parent
        while p != bundle_parent and p != p.parent:
            candidate = f"{p.name}-{basename}"
            hit = attachments_index.get(candidate)
            if hit is not None:
                return hit, candidate
            p = p.parent
        mapped_name = rename_map.get(basename)
        if mapped_name:
            mapped = attachments_index.get(mapped_name)
            if mapped is not None:
                return mapped, mapped_name
        return None, None

    for md in bundle_dir.rglob("*.md"):
        if not md.is_file():
            continue
        md_stem = md.stem
        text = md.read_text(encoding="utf-8")
        original = text

        def replace_wiki(m: re.Match) -> str:
            nonlocal embeds_rewritten, embeds_seen
            raw_target = m.group(1).strip()
            display = m.group(2) or ""
            basename = raw_target.split("/")[-1]
            ext = Path(basename).suffix.lstrip(".").lower()
            if ext not in _EMBED_EXTS:
                return m.group(0)
            embeds_seen += 1
            attachment, resolved_name = lookup_attachment(basename, md_stem, md)
            if attachment is None:
                unresolved.append(basename)
                return m.group(0)
            new_form = f"![[{resolved_name}{display}]]"
            if new_form != m.group(0):
                embeds_rewritten += 1
            return new_form

        def replace_md(m: re.Match) -> str:
            nonlocal embeds_rewritten, embeds_seen
            alt = m.group(1)
            raw_path = m.group(2).strip()
            if raw_path.startswith(("http://", "https://", "mailto:", "data:")):
                return m.group(0)
            basename = raw_path.split("/")[-1].split("?")[0].split("#")[0]
            ext = Path(basename).suffix.lstrip(".").lower()
            if ext not in _EMBED_EXTS:
                return m.group(0)
            embeds_seen += 1
            attachment, _resolved_name = lookup_attachment(basename, md_stem, md)
            if attachment is None:
                unresolved.append(basename)
                return m.group(0)
            # os.path.relpath, not Path.relative_to: the assets folder sits at the
            # vault root and the note sits inside a bundle, so the path has to walk
            # up. relative_to only descends and raised here, which meant a
            # markdown-style embed pointing at a shared asset could never be
            # rewritten, and the run counted it as already correct.
            rel = os.path.relpath(attachment, md.parent).replace(os.sep, "/")
            new_form = f"![{alt}]({rel})"
            if new_form != m.group(0):
                embeds_rewritten += 1
            return new_form

        text = _WIKI_EMBED_RE.sub(replace_wiki, text)
        text = _MD_EMBED_RE.sub(replace_md, text)

        if text != original:
            md.write_text(text, encoding="utf-8")
            files_changed.append(str(md.relative_to(vault)))

    _append_activity_log(
        vault, "zanmai.py",
        f"updated embeds in {bundle_dir.relative_to(vault)} "
        f"({embeds_rewritten} embed(s) in {len(files_changed)} file(s))"
    )
    if files_changed:
        for f in files_changed:
            print(f"  {f}")
    already = embeds_seen - embeds_rewritten - len(unresolved)
    print(f"ok: {embeds_rewritten} of {embeds_seen} embed(s) rewritten in "
          f"{len(files_changed)} file(s); {already} already correct; "
          f"{len(unresolved)} unresolved; {len(attachments_index)} asset(s) indexed")
    if unresolved:
        for name in sorted(set(unresolved)):
            print(f"  unresolved: {name} (no file of that name under assets/)")
    if ambiguous:
        for name, count in sorted(ambiguous.items()):
            print(f"  ambiguous: {name} exists {count}x under assets/, first one used")

    if getattr(args, "clear_rename_map", False) and rename_map:
        _save_rename_map(vault, {})
        print(f"  cleared rename map ({len(rename_map)} entry/entries removed)")

    return 0


_PLAN_AXIS_HEADING_RE = re.compile(r"(?im)^#{2,4}.*\b(axis|axes)\b")
_PLAN_QUESTION_LINE_RE = re.compile(r"\?")





def cmd_archive_review_item(args: argparse.Namespace) -> int:
    """Move a read-once briefing from inbox/review/ to .zanmai/logs/<YYYY>/<MM>/.

    For the read-once-briefing kind of review item (Reed's consolidations,
    Steve's one-shot summaries before a decision).
    The user has read it; the file moves to the AI-side archive so it does
    not clutter inbox/review/ while remaining browsable. Frontmatter status
    flips to 'archived'."""
    vault = Path(args.vault).resolve()
    item_path = Path(args.item_path)
    if not item_path.is_absolute():
        item_path = vault / item_path
    if not item_path.exists():
        print(f"fail: review item not found: {item_path}", file=sys.stderr)
        return 1
    if not item_path.is_file():
        print(f"fail: review path is not a file: {item_path}", file=sys.stderr)
        return 1

    now = datetime.now()
    target_dir = vault / ".zanmai" / "logs" / now.strftime("%Y") / now.strftime("%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / item_path.name
    if target.exists():
        print(f"fail: archive target exists: {target.relative_to(vault)}", file=sys.stderr)
        return 1

    text = item_path.read_text(encoding="utf-8")
    text = re.sub(
        r"^(status:\s*)\"?awaiting-archive\"?",
        r'\1archived',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    target.write_text(text, encoding="utf-8")
    item_path.unlink()

    _append_activity_log(
        vault, "zanmai.py",
        f"archived review item {item_path.name} from inbox/review/ to {target.relative_to(vault)}"
    )
    print(f"ok: review item archived to {target.relative_to(vault)}")
    return 0


_CHECKBOX_RE = re.compile(r"^(\s*-\s*\[[ x]\]\s+)(.+)$")
_TASK_MARKER_RE = re.compile(r"(@waiting\b|due:\d{4}-\d{2}-\d{2}|![a-z]+|#[a-zA-Z][\w-]*)")



def cmd_clear_plan_section(args: argparse.Namespace) -> int:
    """Remove the `## Plan` section from a bundle's truth file.

    Used after a successful filing run: the plan-in-vault has served its purpose
    (user approval, execution), the truth file no longer needs it. The body
    above and below stays verbatim.

    Section boundary is `## Plan` (start) to the next top-level heading
    (`\\n## `) or end-of-file. Frontmatter is untouched.
    """
    vault = Path(args.vault).resolve()
    bundle_dir, _bundle_kind, _leaf = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1

    target_name = args.truth_file or f"{_leaf}.md"
    truth = bundle_dir / target_name
    if not truth.exists():
        print(f"fail: truth file not found: {truth.relative_to(vault)}", file=sys.stderr)
        return 1

    text = truth.read_text(encoding="utf-8")
    # Section pattern: '## Plan' at line start, up to the next '## ' at line start
    # or end of file. Multiline-aware; dotall so '.' matches newlines.
    pattern = re.compile(r"(?ms)^## Plan\s*\n.*?(?=^## |\Z)")
    new_text, n = pattern.subn("", text)
    if n == 0:
        print(f"ok: no plan section in {truth.relative_to(vault)} (nothing to clear)")
        return 0

    # Tidy double-blank lines that result from the removal.
    new_text = re.sub(r"\n{3,}", "\n\n", new_text).rstrip() + "\n"
    truth.write_text(new_text, encoding="utf-8")

    _append_activity_log(
        vault, "zanmai.py",
        f"cleared plan section from {truth.relative_to(vault)}"
    )
    print(f"ok: plan section cleared from {truth.relative_to(vault)}")
    return 0


def _collect_open_todos(vault: Path, scope_dirs: list[str], days_back: int = 30) -> list[dict]:
    """Find `- [ ]` lines in markdown files under the given scope subfolders.
    Returns list of {path, line, date} dicts. Used for the briefing's open-items
    section. Days-back filter applies to file mtime; older items are dropped to
    keep the briefing relevant. ZenNotes database folders (`<Name>.base/`) are
    skipped, record pages there are database-synced, not freeform notes."""
    todos: list[dict] = []
    cutoff = datetime.now().timestamp() - days_back * 24 * 3600
    todo_re = re.compile(r"^\s*-\s*\[\s\]\s*(.+?)\s*$")
    for sub in scope_dirs:
        scope = vault / sub
        if not scope.is_dir():
            continue
        for md in scope.rglob("*.md"):
            if not md.is_file():
                continue
            try:
                rel = md.relative_to(vault).as_posix()
            except ValueError:
                continue
            if _is_inside_zennotes_database(rel):
                continue
            if md.stat().st_mtime < cutoff:
                continue
            try:
                lines = md.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                m = todo_re.match(line)
                if m:
                    todos.append({
                        "path": str(md.relative_to(vault)),
                        "text": m.group(1),
                    })
    return todos


def _recent_log_files(vault: Path, limit: int = 5) -> list[Path]:
    """Most recent N log files under .zanmai/logs/<YYYY>/<MM>/, sorted by mtime desc.
    Excludes builder-gaps.md and hidden files."""
    logs_root = vault / ".zanmai" / "logs"
    if not logs_root.is_dir():
        return []
    candidates: list[Path] = []
    for md in logs_root.rglob("*.md"):
        if md.name == "builder-gaps.md":
            continue
        if md.name.startswith("."):
            continue
        candidates.append(md)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:limit]


def _extract_section(body: str, heading: str) -> str:
    """Return the content of a Markdown section under `## <heading>` up to the
    next `## ` heading or end-of-body. Empty string if not found."""
    pattern = re.compile(rf"(?ms)^##\s*{re.escape(heading)}\s*\n(.+?)(?=\n##\s|\Z)")
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


def _recent_operations(vault: Path, limit: int = 3) -> list[dict]:
    """Return up to `limit` most recent operation-report dicts with their
    operation name, summary, and anomalies content."""
    result: list[dict] = []
    for log in _recent_log_files(vault, limit=10):
        text = log.read_text(encoding="utf-8", errors="ignore")
        fm, _, body = _split_frontmatter(text)
        if not isinstance(fm, dict):
            continue
        operation = fm.get("operation", "")
        if not operation:
            continue  # only operation reports, not arbitrary logs
        slug = fm.get("slug", log.stem)
        # First non-placeholder line of Summary.
        summary_block = _extract_section(body, "Summary")
        summary = ""
        for line in summary_block.splitlines():
            line = line.strip()
            if line and not line.startswith("("):
                summary = line
                break
        anomalies_block = _extract_section(body, "Anomalies")
        # Filter placeholder
        anomalies = ""
        for line in anomalies_block.splitlines():
            line = line.strip()
            if line and not line.startswith("("):
                anomalies = anomalies_block.strip()
                break
        result.append({
            "path": str(log.relative_to(vault)),
            "slug": slug,
            "operation": operation,
            "summary": summary,
            "anomalies": anomalies,
        })
        if len(result) >= limit:
            break
    return result


def _close_session_next_items(vault: Path, limit: int = 3) -> list[dict]:
    """Pull 'Next' items from the last N close-session logs. Returns list of
    {date, items}. Items is the raw text of the Next section so the briefing
    can render it verbatim."""
    result: list[dict] = []
    for log in _recent_log_files(vault, limit=15):
        text = log.read_text(encoding="utf-8", errors="ignore")
        fm, _, body = _split_frontmatter(text)
        if not isinstance(fm, dict):
            continue
        # Heuristic: close-session logs have session_type or a Next/Done/Intent block.
        is_close = fm.get("session_type", "").lower() in ("close-session", "close")
        if not is_close and not _extract_section(body, "Next"):
            continue
        next_block = _extract_section(body, "Next").strip()
        if not next_block or next_block.startswith("("):
            continue
        result.append({
            "path": str(log.relative_to(vault)),
            "date": fm.get("created", log.stem),
            "items": next_block,
        })
        if len(result) >= limit:
            break
    return result


def _active_focus_bundles(vault: Path) -> list[dict]:
    """List active focus bundles with their goal + status from the truth file."""
    focus_dir = vault / "inbox" / "focus"
    if not focus_dir.is_dir():
        return []
    result: list[dict] = []
    for bundle_dir in sorted(focus_dir.iterdir()):
        if not bundle_dir.is_dir():
            continue
        slug = bundle_dir.name
        truth = bundle_dir / f"{slug}.md"
        if not truth.exists():
            continue
        try:
            fm, _, _ = _split_frontmatter(truth.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not isinstance(fm, dict):
            continue
        result.append({
            "slug": slug,
            "goal": fm.get("goal", ""),
            "status": fm.get("status", ""),
            "due": fm.get("due", ""),
        })
    return result


_SMALL_WORDS = {
    "and", "or", "the", "of", "to", "with", "on", "at", "for", "from",
    "a", "an", "in", "by", "as",
}
_KNOWN_ACRONYMS = {
    "tcc", "mcp", "llm", "ai", "ki", "gui", "cli",
    "api", "rfc", "faq", "xml", "json", "yaml", "iso", "mlx", "url", "pkm",
    "adr", "crm", "ocr",
}


def _human_label_for_slug(slug: str) -> str:
    """Turn a kebab-case slug into a human-readable label. Small words stay
    lower (except as first word), known acronyms go full upper, numbers stay
    numbers. Used so the briefing doesn't dump raw slugs into prose."""
    if not slug:
        return slug
    parts = slug.split("-")
    out_parts: list[str] = []
    for idx, p in enumerate(parts):
        if not p:
            continue
        lower = p.lower()
        if lower in _KNOWN_ACRONYMS:
            out_parts.append(lower.upper())
        elif p.isdigit():
            out_parts.append(p)
        elif len(p) <= 4 and p.isalnum() and any(c.isdigit() for c in p):
            out_parts.append(p.upper())
        elif idx > 0 and lower in _SMALL_WORDS:
            out_parts.append(lower)
        else:
            out_parts.append(p[0].upper() + p[1:])
    return " ".join(out_parts)


def _relative_time(timestamp_iso: str, now: datetime | None = None) -> str:
    """ISO timestamp ('YYYY-MM-DD HH:MM') to a short relative phrase:
    - same day: 'today HH:MM'
    - yesterday: 'yesterday HH:MM'
    - last 7 days: 'N days ago'
    - older: 'YYYY-MM-DD'
    Returns the input unchanged on parse failure. Steve translates the
    output to the user's writing language at runtime when surfacing it."""
    try:
        dt = datetime.strptime(timestamp_iso, "%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp_iso
    ref = now if now is not None else datetime.now()
    today = ref.date()
    if dt.date() == today:
        return f"today {dt.strftime('%H:%M')}"
    if (today - dt.date()).days == 1:
        return f"yesterday {dt.strftime('%H:%M')}"
    days = (today - dt.date()).days
    if 1 < days <= 7:
        return f"{days} days ago"
    return dt.strftime("%Y-%m-%d")


def _recent_activity_bundles(vault: Path, hours_back: int = 48) -> list[dict]:
    """Bundles in inbox/{knowledge,habits,focus} with file mtimes in the last
    `hours_back` hours. Source-agnostic recency signal: catches reed-research,
    hank-imports, manual edits alike. The Open-Todos channel only surfaces
    Daily and Weekly items. This surfaces "user was busy with X yesterday" for
    any bundle. Returns descending by last_activity_unix."""
    import time as _time
    cutoff = _time.time() - (hours_back * 3600)
    kind_map = {"knowledge": "knowledge", "habits": "habit", "focus": "focus"}
    result: list[dict] = []
    for kind_folder, bundle_kind in kind_map.items():
        kind_path = vault / "inbox" / kind_folder
        if not kind_path.is_dir():
            continue
        for bundle_dir in sorted(kind_path.iterdir()):
            if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
                continue
            slug = bundle_dir.name
            max_mtime = 0.0
            file_count = 0
            for f in bundle_dir.rglob("*"):
                if not f.is_file() or f.name.startswith("."):
                    continue
                try:
                    mt = f.stat().st_mtime
                except OSError:
                    continue
                if mt > max_mtime:
                    max_mtime = mt
                if mt >= cutoff:
                    file_count += 1
            if max_mtime >= cutoff:
                result.append({
                    "slug": slug,
                    "kind": bundle_kind,
                    "last_activity_iso": datetime.fromtimestamp(max_mtime).strftime("%Y-%m-%d %H:%M"),
                    "last_activity_unix": max_mtime,
                    "file_count_changed": file_count,
                })
    result.sort(key=lambda b: b["last_activity_unix"], reverse=True)
    return result


def _attachment_basenames(vault: Path) -> set[str]:
    """All non-Markdown filenames in the vault (lowercased), used to resolve
    embed-shaped wikilinks like `[[some-frame.jpg]]` against the filesystem.
    Skips the same distribution/system areas as the markdown walker. Also
    skips ZenNotes database folders (`<Name>.base/`), their `data.csv`,
    `schema.json` and record-page assets are database-internal, not vault
    assets that markdown bodies embed."""
    out: set[str] = set()
    for p in vault.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".md":
            continue
        try:
            rel = p.relative_to(vault).as_posix()
        except ValueError:
            continue
        if rel.startswith(".zanmai/system/") or rel.startswith(".zanmai/snapshots/") or rel.startswith(".claude/"):
            continue
        if _is_inside_zennotes_database(rel):
            continue
        out.add(p.name.lower())
    return out


def _broken_wikilinks(vault: Path) -> list[dict]:
    """Wikilinks in the active user vault that point to slugs or filenames no
    file in the vault carries. Reads from vault-index.json (`wikilinks_out`
    per file). Two target classes: bare slugs (resolve against markdown
    slug-set), and file-extension targets like `[[frame.jpg]]` (resolve
    against the filesystem-walk of non-markdown files).

    Source paths under the hard-exclude list (`_WIKILINK_OPS_EXCLUDED_PREFIXES`
    plus `_WIKILINK_OPS_EXCLUDED_FILES`) are skipped: log files and
    operation reports contain pre-rename slug names as historical record
    by design, trashed and archived files keep their state at archive time,
    snapshots are immutable. None of these are "broken" in the user-vault
    sense, they are expected historical residue."""
    index_path = vault / ".zanmai" / "memory" / "vault-index.json"
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    known_slugs: set[str] = set()
    for entry in data.get("files", []):
        slug = entry.get("slug")
        if slug:
            known_slugs.add(slug.lower())
        path = entry.get("path", "")
        if path.endswith(".md"):
            stem = Path(path).stem
            known_slugs.add(stem.lower())
    attachments = _attachment_basenames(vault)
    broken: list[dict] = []
    for entry in data.get("files", []):
        source_path = entry.get("path", "")
        if _is_excluded_from_wikilink_ops(source_path):
            continue
        targets = entry.get("wikilinks_out") or []
        for t in targets:
            t_norm = str(t).split("/")[-1].split("#")[0].lower()
            if not t_norm:
                continue
            # Both pools, no extension list deciding which one to look in. The list
            # was an allowlist of file types, and a target whose type was not on it
            # got matched against markdown slugs, where a name with an extension can
            # never appear: every unanticipated type was reported broken with
            # certainty rather than left unchecked. Two `.eml` attachments sat in a
            # briefing as broken links for months while both files were on disk.
            # Present or not present is the whole question, and the disk answers it.
            if t_norm in attachments or t_norm in known_slugs:
                continue
            broken.append({
                "source": source_path,
                "target": str(t),
            })
    return broken


_MONTH_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_WEEKDAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _translate_title_pattern(pattern: str, date: datetime) -> str:
    """Translate a ZenNotes (Joda-style) titlePattern into a concrete filename
    string for the given date. Supports `/` inside the pattern for subfolders.

    Tokens:
      yyyy → 4-digit year
      MM   → 2-digit month number
      MMM  → English short month (Jan…Dec)
      dd   → 2-digit day
      EEE  → English short weekday (Mon…Sun)
      ww   → 2-digit ISO week number
      'X'  → literal X (single-quoted segment, quotes consumed)

    Anything not matching a token or quoted segment is treated as literal."""
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "'":
            end = pattern.find("'", i + 1)
            if end == -1:
                out.append(pattern[i + 1:])
                break
            out.append(pattern[i + 1:end])
            i = end + 1
            continue
        if pattern.startswith("yyyy", i):
            out.append(f"{date.year:04d}")
            i += 4
            continue
        if pattern.startswith("MMM", i):
            out.append(_MONTH_SHORT[date.month - 1])
            i += 3
            continue
        if pattern.startswith("EEE", i):
            out.append(_WEEKDAY_SHORT[date.weekday()])
            i += 3
            continue
        if pattern.startswith("MM", i):
            out.append(f"{date.month:02d}")
            i += 2
            continue
        if pattern.startswith("dd", i):
            out.append(f"{date.day:02d}")
            i += 2
            continue
        if pattern.startswith("ww", i):
            out.append(f"{date.isocalendar()[1]:02d}")
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _read_vault_json(vault: Path) -> dict:
    """Return the parsed .zennotes/vault.json or an empty dict when missing
    or unreadable. The empty dict signals 'ZenNotes not configured for this
    vault' to every consumer."""
    vault_json = vault / ".zennotes" / "vault.json"
    if not vault_json.exists():
        return {}
    try:
        return json.loads(vault_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


_NOTES_SECTION_KEYS = {
    "daily": "dailyNotes",
    "weekly": "weeklyNotes",
    "monthly": "monthlyNotes",
}
_NOTES_KINDS = ("daily", "weekly", "monthly")


def _resolve_note_folder(vault: Path, kind: str) -> str | None:
    """Return the folder path relative to the vault root for daily, weekly or
    monthly notes, or None when ZenNotes is not configured, primaryNotesLocation
    is invalid, the kind is disabled, or the directory field is missing.

    `kind` is 'daily', 'weekly' or 'monthly'. The result honours
    `primaryNotesLocation`: 'root' yields a vault-root folder, 'inbox' yields an
    `inbox/`-prefixed one."""
    zn = _read_vault_json(vault)
    if not zn:
        return None
    primary = zn.get("primaryNotesLocation")
    if primary not in ("root", "inbox"):
        return None
    section_key = _NOTES_SECTION_KEYS.get(kind)
    if section_key is None:
        return None
    cfg = zn.get(section_key) or {}
    if not cfg.get("enabled") or not cfg.get("directory"):
        return None
    prefix = "" if primary == "root" else "inbox/"
    return f"{prefix}{cfg['directory']}"


def _resolve_note_path(vault: Path, kind: str, date: datetime) -> Path | None:
    """Return the absolute path of the daily/weekly note for `date`, or None
    when the corresponding note kind is disabled or unconfigured. Combines
    `_resolve_note_folder` with `titlePattern` translation."""
    folder = _resolve_note_folder(vault, kind)
    if folder is None:
        return None
    zn = _read_vault_json(vault)
    section_key = _NOTES_SECTION_KEYS.get(kind)
    if section_key is None:
        return None
    pattern = (zn.get(section_key) or {}).get("titlePattern")
    if not pattern:
        return None
    filename = _translate_title_pattern(pattern, date)
    return vault / folder / f"{filename}.md"


def _daily_weekly_paths(vault: Path) -> list[str]:
    """Resolve enabled Daily/Weekly/Monthly Notes folder paths from
    .zennotes/vault.json. Returns only the enabled folders relative to the vault
    root. Empty when ZenNotes is not configured or all kinds are disabled."""
    paths: list[str] = []
    for kind in _NOTES_KINDS:
        folder = _resolve_note_folder(vault, kind)
        if folder:
            paths.append(folder)
    return paths


def cmd_daily_note(args: argparse.Namespace) -> int:
    """Deterministic notes daily operations: resolve the path from vault.json,
    optionally create the file with `--ensure`, optionally append a line with
    `--append`, or just print the resolved path with `--print-path`. Fails
    cleanly when daily notes are disabled or ZenNotes is not configured for
    this vault."""
    vault = Path(args.vault).resolve()
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("fail: invalid --date, expected YYYY-MM-DD", file=sys.stderr)
            return 1
    else:
        target_date = datetime.now()

    path = _resolve_note_path(vault, args._kind, target_date)
    if path is None:
        print(f"fail: {args._kind} notes are disabled or ZenNotes is not configured for this vault", file=sys.stderr)
        return 2

    rel = path.relative_to(vault).as_posix()
    if args.print_path:
        print(rel)
        return 0

    needs_file = args.ensure or args.append is not None
    if needs_file and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    if args.append:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        existing += args.append + "\n"
        path.write_text(existing, encoding="utf-8")
        _append_activity_log(vault, "zanmai.py", f"notes {args._kind} append -> {rel}")
        print(f"ok: appended to {rel}")
        return 0

    if needs_file:
        print(f"ok: {rel}")
    else:
        print(rel)
    return 0




def _render_briefing(vault: Path) -> str:
    """Build the briefing.md content from current vault state. Synthesises across
    Daily/Weekly Notes, Focus-Bundles, Operation-Reports and Close-Session-Logs -
    not just one source. Steve reads this at session start; the SessionStart
    hook inlines it into context."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    focus_bundles = _active_focus_bundles(vault)
    recent_ops = _recent_operations(vault, limit=3)
    recent_activity = _recent_activity_bundles(vault, hours_back=48)
    close_next = _close_session_next_items(vault, limit=3)
    daily_weekly_todos = _collect_open_todos(
        vault, _daily_weekly_paths(vault), days_back=30
    )
    focus_todos = _collect_open_todos(vault, ["inbox/focus"], days_back=90)
    broken = _broken_wikilinks(vault)

    lines: list[str] = []
    lines.append(f"# Zanmai briefing")
    lines.append("")
    lines.append(f"_Updated {timestamp}. Read by Steve at session start. "
                 f"Not user-editable - rebuilt automatically on close-session, "
                 f"on every operation report, and on demand via "
                 f"`zanmai.py memory briefing`._")
    lines.append("")

    # 1) Current state
    lines.append("## Current state")
    lines.append("")
    if focus_bundles:
        lines.append("**Active focus bundles:**")
        for b in focus_bundles:
            status_part = f", {b['status']}" if b["status"] else ""
            due_part = f" (due {b['due']})" if b["due"] else ""
            goal_part = f": {b['goal']}" if b["goal"] else ""
            lines.append(f"- [[{b['slug']}]]{status_part}{due_part}{goal_part}")
        lines.append("")
    else:
        lines.append("No active focus bundles.")
        lines.append("")
    if recent_ops:
        lines.append(f"**Recent operations ({len(recent_ops)}):**")
        for op in recent_ops:
            sum_part = f", {op['summary']}" if op["summary"] else ""
            lines.append(f"- {op['operation']}{sum_part} (`{op['path']}`)")
        lines.append("")
    else:
        lines.append("**Recent operations:** none.")
        lines.append("")

    # 1b) Recent activity, source-agnostic recency signal for any bundle
    # (research, imports, manual edits). Independent from open-todos channel.
    if recent_activity:
        lines.append(f"**Recent activity (last 48h, {len(recent_activity)}):**")
        for b in recent_activity[:8]:
            files_part = f", {b['file_count_changed']} files" if b["file_count_changed"] > 1 else ""
            label = _human_label_for_slug(b["slug"])
            when = _relative_time(b["last_activity_iso"], now=now)
            lines.append(f"- **{label}** ([[{b['slug']}]], {b['kind']}, {when}{files_part})")
        if len(recent_activity) > 8:
            lines.append(f"- _... plus {len(recent_activity) - 8} more_")
        lines.append("")

    # 2) Open items
    lines.append("## Open items")
    lines.append("")
    if close_next:
        lines.append(f"**Next items from close-session logs ({len(close_next)}):**")
        for entry in close_next:
            lines.append(f"- from `{entry['path']}` ({entry['date']}):")
            for body_line in entry["items"].splitlines():
                stripped = body_line.strip()
                if stripped:
                    lines.append(f"  {body_line}")
        lines.append("")
    if daily_weekly_todos:
        lines.append(f"**From Daily, Weekly and Monthly Notes (last 30 days, {len(daily_weekly_todos)}):**")
        for t in daily_weekly_todos[:20]:
            lines.append(f"- [ ] {t['text']} _({t['path']})_")
        if len(daily_weekly_todos) > 20:
            lines.append(f"- _... plus {len(daily_weekly_todos) - 20} more_")
        lines.append("")
    if focus_todos:
        lines.append(f"**From focus bundles (last 90 days, {len(focus_todos)}):**")
        for t in focus_todos[:20]:
            lines.append(f"- [ ] {t['text']} _({t['path']})_")
        if len(focus_todos) > 20:
            lines.append(f"- _... plus {len(focus_todos) - 20} more_")
        lines.append("")
    if not (daily_weekly_todos or focus_todos or close_next):
        lines.append("No open items in the current window.")
        lines.append("")

    # 3) Gaps and hints
    lines.append("## Gaps and hints")
    lines.append("")
    anomalies_found = [op for op in recent_ops if op.get("anomalies")]
    if anomalies_found:
        lines.append(f"**Anomalies in recent operations ({len(anomalies_found)}):**")
        for op in anomalies_found:
            lines.append(f"- from `{op['path']}` ({op['operation']}):")
            for body_line in op["anomalies"].splitlines():
                stripped = body_line.strip()
                if stripped:
                    lines.append(f"  {body_line}")
        lines.append("")
    if broken:
        lines.append(f"**Broken wikilinks ({len(broken)}):** target slugs without an existing file.")
        for b in broken[:10]:
            lines.append(f"- `[[{b['target']}]]` in `{b['source']}`")
        if len(broken) > 10:
            lines.append(f"- _... plus {len(broken) - 10} more_")
        lines.append("")
    if not broken and not anomalies_found:
        lines.append("No anomalies or broken wikilinks detected.")
        lines.append("")
    lines.append("_(Extended gap detection (person mentions without a contact, theme drift, "
                 "cross-domain links) is a future addition.)_")
    lines.append("")

    return "\n".join(lines)


def cmd_briefing(args: argparse.Namespace) -> int:
    """Atomic rebuild of `.zanmai/memory/briefing.md`. Triggered by `/close-session`,
    after `memory report`, or manually. The authority for Steve's session-start
    context."""
    vault = Path(args.vault).resolve()
    target = vault / ".zanmai" / "memory" / "briefing.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = _render_briefing(vault)
    target.write_text(content, encoding="utf-8")
    _append_activity_log(vault, "zanmai.py", "briefing.md rebuilt from vault state")
    if not getattr(args, "quiet", False):
        print(f"ok: briefing rebuilt -> {target.relative_to(vault)}")
    return 0


def cmd_write_report(args: argparse.Namespace) -> int:
    """Write an operation report to .zanmai/logs/<YYYY>/<MM>/<date-op-slug>.md.

    Pulls the last `--since-minutes` minutes of activity-log entries for context.
    The skill that calls this fills the Decisions / Anomalies sections via a
    follow-up Edit if it has detail to add; the skeleton is enough for cross-
    session recall on its own.
    """
    vault = Path(args.vault).resolve()
    now = datetime.now()
    date_part = now.strftime("%Y-%m-%d-%H%M")
    op = _slugify(args.operation)
    slug = _slugify(args.slug)
    report_slug = f"{date_part}-{op}-{slug}"
    report_dir = vault / ".zanmai" / "logs" / now.strftime("%Y") / now.strftime("%m")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{report_slug}.md"

    activity = _read_recent_activity(vault, since_minutes=args.since_minutes)
    activity_block = "\n".join(activity) if activity else "(no activity-log entries in the window)"

    fm = {
        "kind": "knowledge",
        "slug": report_slug,
        "created": _today(),
        "source": "ai-generated",
        "operation": args.operation,
        "scope": args.scope or "",
    }
    fm_text = _render_frontmatter(fm, list(fm.keys()))
    summary = args.summary.strip() if args.summary else "(skill fills this in)"

    body = (
        f"\n# Operation report - {args.operation} ({args.slug})\n\n"
        f"## Summary\n\n{summary}\n\n"
        f"## Files touched (from activity-log)\n\n"
        f"{activity_block}\n\n"
        f"## Decisions\n\n(skill fills this in if relevant)\n\n"
        f"## Anomalies\n\n(skill fills this in if relevant)\n\n"
        f"## Cross-links\n\n(previous reports, related bundles)\n"
    )
    report_path.write_text(fm_text + body, encoding="utf-8")
    _append_activity_log(vault, "zanmai.py", f"wrote operation report {report_path.relative_to(vault)}")
    print(f"ok: report at {report_path.relative_to(vault)}")

    # Operation reports are substantial state-changes - the briefing must reflect them.
    briefing_target = vault / ".zanmai" / "memory" / "briefing.md"
    try:
        briefing_target.parent.mkdir(parents=True, exist_ok=True)
        briefing_target.write_text(_render_briefing(vault), encoding="utf-8")
        _append_activity_log(vault, "zanmai.py", "briefing.md auto-rebuilt after memory report")
    except OSError:
        pass

    return 0


def _read_recent_activity(vault: Path, *, since_minutes: int) -> list[str]:
    log = vault / ".zanmai" / "memory" / "activity-log.md"
    if not log.exists() or since_minutes <= 0:
        return []
    cutoff = datetime.now().timestamp() - since_minutes * 60
    entries: list[str] = []
    current_entry: list[str] = []
    current_ts: float | None = None
    for line in log.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## \[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})\] - ", line)
        if m:
            # Flush previous.
            if current_entry and current_ts is not None and current_ts >= cutoff:
                entries.append("\n".join(current_entry))
            try:
                ts = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M").timestamp()
            except ValueError:
                ts = None
            current_entry = [line]
            current_ts = ts
        else:
            if current_entry:
                current_entry.append(line)
    if current_entry and current_ts is not None and current_ts >= cutoff:
        entries.append("\n".join(current_entry))
    return entries


def _zen_cli_path() -> str | None:
    """Locate the `zn` CLI binary. Tries PATH first, then a list of common
    install locations that may not be on the current process's PATH (Claude
    Code hooks often spawn with a minimal env that lacks `~/.local/bin`).
    Returns the absolute invocation string or None."""
    found = shutil.which("zn")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "zn",
        Path("/usr/local/bin/zn"),
        Path("/opt/homebrew/bin/zn"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def _zen_cli_usable(vault: Path) -> bool:
    """Whether `zn` can act on *this* vault. The binary alone is not enough:
    zn ignores the working directory and falls back to its own default vault,
    so a call from an unregistered vault silently hits a different one. The
    vault is registered once ZenNotes has opened it, which is exactly when
    `.zennotes/vault.json` exists."""
    if _zen_cli_path() is None:
        return False
    return (vault / ".zennotes" / "vault.json").is_file()


def cmd_trash_file(args: argparse.Namespace) -> int:
    """Move a file into vault-relative `trash/<original-path>`.

    Uses `zn trash` when zn can act on this vault (preserves restore-path
    natively). Falls back to Unix `mv` with the same target layout.
    """
    vault = Path(args.vault).resolve()
    path = Path(args.path).resolve()

    try:
        rel = path.relative_to(vault)
    except ValueError:
        print(f"fail: path '{path}' is not inside vault '{vault}'", file=sys.stderr)
        return 1

    if not path.exists():
        print(f"fail: path does not exist: {path}", file=sys.stderr)
        return 1

    rel_str = str(rel).replace("\\", "/")

    if _zen_cli_usable(vault):
        # `--vault` names the target explicitly. zn ignores the working
        # directory and would otherwise act on its own default vault.
        import subprocess
        result = subprocess.run(
            [_zen_cli_path() or "zn", "trash", rel_str, "--vault", str(vault)],
            cwd=str(vault),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"fail: zn trash failed: {result.stderr.strip()}", file=sys.stderr)
            return 1
        agent = "zanmai.py via zn"
    else:
        target = vault / "trash" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        agent = "zanmai.py via mv"

    _append_activity_log(vault, agent, f"trash {rel_str}")
    print(f"ok: trashed {rel_str}")
    return 0


def cmd_archive_file(args: argparse.Namespace) -> int:
    """Move a file into vault-relative `archive/<original-path>`.

    Uses `zn archive` when zn can act on this vault; Unix-fallback otherwise.
    """
    vault = Path(args.vault).resolve()
    path = Path(args.path).resolve()
    try:
        rel = path.relative_to(vault)
    except ValueError:
        print(f"fail: path '{path}' is not inside vault '{vault}'", file=sys.stderr)
        return 1
    if not path.exists():
        print(f"fail: path does not exist: {path}", file=sys.stderr)
        return 1

    rel_str = str(rel).replace("\\", "/")

    if _zen_cli_usable(vault):
        import subprocess
        result = subprocess.run(
            [_zen_cli_path() or "zn", "archive", rel_str, "--vault", str(vault)],
            cwd=str(vault),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"fail: zn archive failed: {result.stderr.strip()}", file=sys.stderr)
            return 1
        agent = "zanmai.py via zn"
    else:
        target = vault / "archive" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        agent = "zanmai.py via mv"

    _append_activity_log(vault, agent, f"archive {rel_str}")
    print(f"ok: archived {rel_str}")
    return 0


def cmd_register_contact(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    slug = _slugify(args.slug)
    sub = "people" if args.kind == "person" else "organizations"
    target_dir = vault / "inbox" / "contacts" / sub
    target = target_dir / f"{slug}.md"
    if target.exists():
        print(f"fail: contact exists: {target.relative_to(vault)}", file=sys.stderr)
        return 1
    kind_field = "contact/person" if args.kind == "person" else "contact/organization"

    # If a source file is given, import the body verbatim (like bundle add-file does for
    # bundle files). Frontmatter is migrated to the schema; non-schema fields go to the body.
    source_body = ""
    leftover_block = ""
    source_fm: dict = {}
    source_order: list[str] = []
    if args.source:
        source_path = Path(args.source)
        if not source_path.is_absolute():
            source_path = Path.cwd() / args.source
        source_path = source_path.resolve()
        if not source_path.exists() or not source_path.is_file():
            print(f"fail: source not a file: {source_path}", file=sys.stderr)
            return 1
        content = source_path.read_text(encoding="utf-8")
        source_fm, source_order, source_body = _split_frontmatter(content)

    overrides: dict = {"kind": kind_field, "slug": slug}
    additions: dict = {
        "created": _today(),
        "source": "organic" if args.source else "ai-generated",
    }
    if args.source:
        additions["source_detail"] = f"import:{Path(args.source).name}"
    mentions = [m for m in (getattr(args, "mentioned_in", []) or []) if m]
    if mentions:
        additions["mentioned_in"] = mentions
    # A value the user typed now beats one sitting in the file.
    for k in ("role", "org", "email", "phone", "kind_of", "website"):
        v = getattr(args, k, None)
        if v:
            overrides[k] = v

    fm, order, leftover = _migrate_frontmatter(
        source_fm, source_order, kind=kind_field, slug=slug,
        additions=additions, overrides=overrides,
    )
    fm_text = _render_frontmatter(fm, order)
    leftover_block = _render_original_metadata_block(leftover)

    full_name = args.full_name or slug.replace("-", " ").title()
    if source_body.strip():
        # Preserve user-written body verbatim. Strip leading H1 only if it exactly matches
        # full_name so we don't duplicate the heading we are about to write.
        body_stripped = source_body.lstrip()
        if body_stripped.startswith(f"# {full_name}"):
            body = "\n" + body_stripped
        else:
            body = f"\n# {full_name}\n\n{source_body.rstrip()}\n"
    elif mentions:
        bullets = "\n".join(f"- [[{m}]]" for m in mentions)
        body = f"\n# {full_name}\n\n{bullets}\n"
    else:
        body = f"\n# {full_name}\n"

    target.write_text(fm_text + body + leftover_block, encoding="utf-8")
    log_suffix = f" (body imported from {Path(args.source).name})" if args.source else ""
    _append_activity_log(vault, "zanmai.py", f"registered contact {kind_field} -> {target.relative_to(vault)}{log_suffix}")
    print(f"ok: contact created at {target.relative_to(vault)}")
    return 0


# ---------------------------------------------------------------------------
# Pattern-Engine: vault-index (Schicht A) and patterns (Schicht B).
#
# Schicht A: walk vault, extract metadata per markdown file. Write
#   .zanmai/memory/vault-index.json. Pure-data layer, no domain knowledge.
#
# Schicht B: aggregate themes/hubs/bundles from Schicht A. Write
#   .zanmai/memory/patterns.json. Still domain-free - token-overlap and graph
#   structure only, no vocabulary.
#
# Consumers (classify-note, import-bundle, Hank) read these JSON files
# instead of re-reading source markdown.
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Stop-words are structural (articles, conjunctions, copulas), not domain.
# English basics only, kept tight so legitimate domain tokens survive.
_STOP_WORDS = frozenset({
    "the", "and", "but", "with", "without", "from", "of", "on", "at", "to", "in",
    "is", "are", "was", "were", "be", "been", "being", "has", "have", "had",
    "it", "he", "she", "they", "we", "you", "this", "that", "these", "those",
    "for", "by", "as", "or", "if", "so", "not", "no", "yes",
    "a", "an", "do", "does", "did", "can", "will", "would", "should", "could",
})


def _ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def _tokenize(text: str) -> list[str]:
    """Tokenize text for matching. ASCII-fold, lowercase, drop stop-words and short tokens."""
    if not text:
        return []
    folded = _ascii_fold(text)
    raw = re.split(r"[^a-z0-9]+", folded)
    out = []
    seen = set()
    for tok in raw:
        if len(tok) < 3 or tok in _STOP_WORDS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _extract_body_tokens(body: str, max_chars: int = 8000) -> list[str]:
    """Extract deduplicated significant tokens from body content.

    Truncate body at max_chars to bound cost; tokens past the first ~2000 words
    rarely add signal a theme-cluster cares about.
    """
    # Strip code blocks, URLs, and inline markdown that pollute the token-stream.
    snippet = body[:max_chars]
    snippet = re.sub(r"```.*?```", " ", snippet, flags=re.DOTALL)
    snippet = re.sub(r"`[^`\n]+`", " ", snippet)
    snippet = re.sub(r"https?://\S+", " ", snippet)
    snippet = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", snippet)  # images
    snippet = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", snippet)  # markdown links
    return _tokenize(snippet)


def _extract_file_entry(file_path: Path, vault: Path) -> dict | None:
    """Extract index entry for one markdown file. Returns None on read error."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    fm, _, body = _split_frontmatter(content)

    stem = file_path.stem
    filename_tokens = _tokenize(stem)

    tags_raw = fm.get("tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [tags_raw]
    tags = [str(t).strip().lower() for t in tags_raw if t]

    h1_match = _H1_RE.search(body)
    h1 = h1_match.group(1).strip() if h1_match else ""
    h1_tokens = _tokenize(h1)

    if h1_match:
        after_h1 = body[h1_match.end():].lstrip()
    else:
        after_h1 = body.lstrip()
    first_para = after_h1.split("\n\n", 1)[0].strip()[:300]

    body_tokens = _extract_body_tokens(body)

    wikilinks: list[str] = []
    seen_links: set[str] = set()
    for raw_link in _WIKILINK_RE.findall(body):
        target = raw_link.strip().split("#", 1)[0].split("/")[-1].strip()
        if target and target not in seen_links:
            seen_links.add(target)
            wikilinks.append(target)

    try:
        rel_path = file_path.relative_to(vault).as_posix()
    except ValueError:
        rel_path = str(file_path)

    try:
        st = file_path.stat()
        size = st.st_size
        mtime = int(st.st_mtime)
    except OSError:
        size = 0
        mtime = 0

    return {
        "path": rel_path,
        "filename_stem": stem,
        "filename_tokens": filename_tokens,
        "kind": str(fm.get("kind") or ""),
        "slug": str(fm.get("slug") or ""),
        "name": str(fm.get("name") or ""),
        "tags": tags,
        "h1": h1,
        "h1_tokens": h1_tokens,
        "first_paragraph": first_para,
        "body_tokens": body_tokens,
        "wikilinks_out": wikilinks,
        "created": str(fm.get("created") or ""),
        "updated": str(fm.get("updated") or ""),
        "size": size,
        "mtime": mtime,
    }


def _is_inside_zennotes_database(rel_path: str) -> bool:
    """Return True if a vault-relative path sits inside a ZenNotes v2.4.0
    database folder (`<Name>.base/`). Database folders are user-owned and
    ZenNotes-managed; Zanmai reads and writes nothing inside them.

    Detection: any path segment ending in `.base` (case-sensitive, since
    ZenNotes uses that exact spelling) marks the rest of the segments as
    database-internal."""
    for segment in rel_path.split("/"):
        if segment.endswith(".base") and len(segment) > len(".base"):
            return True
    return False


def _walk_vault_markdown(vault: Path, scope: str | None = None) -> list[Path]:
    """Walk markdown files under vault (or vault/scope). Skip the internal
    `.zanmai/` tree entirely (contracts, generated state like `vault-config.md`
    and `briefing.md`, logs, memory), it is not user content, its wikilink-shaped
    examples produce false-positive broken-link reports, and its per-session
    regeneration would otherwise make the index look perpetually stale. Also skip
    `.claude/`, the `_import/` drop area, the root `CLAUDE.md`, and database
    folders (`<Name>.base/`, user-owned and ZenNotes-managed)."""
    base = (vault / scope) if scope else vault
    if not base.exists() or not base.is_dir():
        return []
    out = []
    for f in base.rglob("*.md"):
        if not f.is_file():
            continue
        try:
            rel = f.relative_to(vault).as_posix()
        except ValueError:
            continue
        if rel.startswith(".zanmai/"):
            continue
        if rel.startswith(".claude/"):
            continue
        if rel.startswith("_import/"):
            continue
        if rel == "CLAUDE.md":
            continue
        if _is_inside_zennotes_database(rel):
            continue
        out.append(f)
    return out


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def cmd_reindex(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    files = _walk_vault_markdown(vault, args.scope)
    entries = []
    for f in files:
        entry = _extract_file_entry(f, vault)
        if entry is not None:
            entries.append(entry)

    out = {
        "_meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "vault": str(vault),
            "file_count": len(entries),
            "scope": args.scope or ".",
        },
        "files": entries,
    }

    target = vault / ".zanmai" / "memory" / "vault-index.json"
    _atomic_write_json(target, out)

    # Clear the stale marker; the index now reflects current state.
    stale_marker = vault / ".zanmai" / "memory" / ".index-stale"
    if stale_marker.exists():
        try:
            stale_marker.unlink()
        except OSError:
            pass

    if not args.quiet:
        print(f"reindex ok: {len(entries)} files -> {target.relative_to(vault)}")
    return 0


def _bundle_segments(rel_path: str) -> tuple[str, str] | None:
    """Return (kind, slug) if rel_path is inside an inbox/<kind>/<slug>/ bundle, else None."""
    parts = rel_path.split("/")
    if len(parts) < 4 or parts[0] != "inbox":
        return None
    kind, slug = parts[1], parts[2]
    if kind not in ("focus", "habits", "knowledge"):
        return None
    if slug.startswith("_") or slug.startswith("."):
        return None
    return kind, slug


def _file_tokens(entry: dict) -> set[str]:
    """Union of all token-sources for one file, used by aggregations.

    Primary tokens (filename, tags, h1) are weighted equal to body tokens in
    the membership set; the separation matters only for surfacing strength,
    not for set membership.
    """
    tokens: set[str] = set()
    tokens.update(entry.get("filename_tokens") or [])
    for t in entry.get("tags") or []:
        tokens.update(_tokenize(t))
    tokens.update(entry.get("h1_tokens") or [])
    tokens.update(entry.get("body_tokens") or [])
    return tokens


def _aggregate_themes(entries: list[dict], min_count: int) -> dict:
    """Token-cluster across filename, tags, h1, body. Tokens with >= min_count files.

    Each theme entry also records sources counts (how many files carry the
    token in the strong slots - filename/tag/h1 - versus only in body) so
    consumers can tell strong themes from weak body-only co-occurrences.
    """
    theme_files: dict[str, set[str]] = {}
    theme_strong: dict[str, set[str]] = {}
    for e in entries:
        strong: set[str] = set()
        strong.update(e.get("filename_tokens") or [])
        for t in e.get("tags") or []:
            strong.update(_tokenize(t))
        strong.update(e.get("h1_tokens") or [])
        all_tokens = strong | set(e.get("body_tokens") or [])
        for tok in all_tokens:
            theme_files.setdefault(tok, set()).add(e["path"])
            if tok in strong:
                theme_strong.setdefault(tok, set()).add(e["path"])
    out = {}
    for token, paths in theme_files.items():
        if len(paths) < min_count:
            continue
        strong_paths = theme_strong.get(token, set())
        out[token] = {
            "files": sorted(paths),
            "count": len(paths),
            "strong_count": len(strong_paths),
        }
    return out


def _aggregate_co_occurrence(entries: list[dict], min_count: int, top_k: int = 8) -> dict:
    """Token co-occurrence: per token, the top-K other tokens that share files.

    Only emits tokens that themselves cross the min_count threshold (else the
    output is dominated by long-tail noise). For each surviving token, returns
    its top-K neighbours sorted by shared-file count descending.
    """
    # Files per token
    token_files: dict[str, set[str]] = {}
    for e in entries:
        for tok in _file_tokens(e):
            token_files.setdefault(tok, set()).add(e["path"])
    kept = {t: f for t, f in token_files.items() if len(f) >= min_count}

    # For each kept token, intersect with every other kept token and take top-K
    out: dict[str, list[dict]] = {}
    keys = list(kept.keys())
    for i, t1 in enumerate(keys):
        files1 = kept[t1]
        neighbours: list[tuple[str, int]] = []
        for t2 in keys:
            if t2 == t1:
                continue
            overlap = len(files1 & kept[t2])
            if overlap >= min_count:
                neighbours.append((t2, overlap))
        neighbours.sort(key=lambda x: (-x[1], x[0]))
        if neighbours:
            out[t1] = [{"token": t, "shared_files": c} for t, c in neighbours[:top_k]]
    return out


def _aggregate_wikilink_hubs(entries: list[dict], min_count: int) -> dict:
    """Reverse wikilink graph: per linked basename, files that point to it."""
    hub_files: dict[str, set[str]] = {}
    for e in entries:
        for link in e.get("wikilinks_out") or []:
            if not link:
                continue
            hub_files.setdefault(link, set()).add(e["path"])
    return {
        target: {"linked_from": sorted(paths), "count": len(paths)}
        for target, paths in hub_files.items()
        if len(paths) >= min_count
    }


def _aggregate_existing_bundles(entries: list[dict]) -> dict:
    """Detect bundles under inbox/<kind>/<slug>/. Aggregate tokens across bundle members."""
    bundles: dict[str, dict] = {}
    for entry in entries:
        seg = _bundle_segments(entry["path"])
        if seg is None:
            continue
        kind, slug = seg
        key = f"{kind}/{slug}"
        if key not in bundles:
            bundles[key] = {
                "slug": slug,
                "kind": kind,
                "path": f"inbox/{kind}/{slug}",
                "_files": [],
                "_tokens": set(),
            }
        b = bundles[key]
        b["_files"].append(entry["path"])
        b["_tokens"].update(entry.get("filename_tokens") or [])
        for t in entry.get("tags") or []:
            b["_tokens"].update(_tokenize(t))
        b["_tokens"].update(entry.get("h1_tokens") or [])
        b["_tokens"].update(entry.get("body_tokens") or [])
    out = {}
    for key, b in bundles.items():
        out[key] = {
            "slug": b["slug"],
            "kind": b["kind"],
            "path": b["path"],
            "files": sorted(b["_files"]),
            "tokens": sorted(b["_tokens"]),
            "file_count": len(b["_files"]),
        }
    return out


def cmd_patterns(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    index_path = vault / ".zanmai" / "memory" / "vault-index.json"
    if not index_path.exists():
        print(f"vault-index.json missing - run `zanmai.py index rebuild {vault}` first", file=sys.stderr)
        return 1

    data = json.loads(index_path.read_text(encoding="utf-8"))
    entries = data.get("files", [])

    out = {
        "_meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "vault": str(vault),
            "based_on_index": data.get("_meta", {}).get("generated", ""),
            "file_count": len(entries),
            "min_count": args.min_count,
        },
        "themes": _aggregate_themes(entries, min_count=args.min_count),
        "wikilink_hubs": _aggregate_wikilink_hubs(entries, min_count=args.min_count),
        "existing_bundles": _aggregate_existing_bundles(entries),
        "co_occurrence": _aggregate_co_occurrence(entries, min_count=args.min_count),
    }

    target = vault / ".zanmai" / "memory" / "patterns.json"
    _atomic_write_json(target, out)

    if not args.quiet:
        print(
            f"patterns ok: themes={len(out['themes'])} "
            f"hubs={len(out['wikilink_hubs'])} "
            f"bundles={len(out['existing_bundles'])} "
            f"co_occ_tokens={len(out['co_occurrence'])} "
            f"-> {target.relative_to(vault)}"
        )
    return 0


def cmd_find_theme(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    patterns_path = vault / ".zanmai" / "memory" / "patterns.json"
    if not patterns_path.exists():
        print(f"patterns.json missing - run `zanmai.py index patterns {vault}` first", file=sys.stderr)
        return 1

    data = json.loads(patterns_path.read_text(encoding="utf-8"))
    raw = [t.strip() for t in args.tokens.split(",") if t.strip()]
    tokens = []
    for r in raw:
        tokens.extend(_tokenize(r))
    tokens = list(dict.fromkeys(tokens))

    themes_idx = data.get("themes", {})
    co_idx = data.get("co_occurrence", {})

    matching_themes = []
    for tok in tokens:
        info = themes_idx.get(tok)
        if info:
            strong = info.get("strong_count", 0)
            matching_themes.append({
                "theme": tok,
                "files": info["files"],
                "count": info["count"],
                "strong_count": strong,
                "signal": "strong" if strong >= 2 else ("body_only" if strong == 0 else "mixed"),
            })
    # Rank by strong-count first, then total count.
    matching_themes.sort(key=lambda t: (-t["strong_count"], -t["count"]))

    matching_bundles = []
    for key, b in data.get("existing_bundles", {}).items():
        overlap = set(tokens) & set(b.get("tokens", []))
        if overlap:
            matching_bundles.append({
                "key": key,
                "slug": b["slug"],
                "kind": b["kind"],
                "path": b["path"],
                "score": len(overlap),
                "matched_tokens": sorted(overlap),
                "file_count": b.get("file_count", 0),
            })
    matching_bundles.sort(key=lambda b: -b["score"])

    matching_hubs = []
    for hub, info in data.get("wikilink_hubs", {}).items():
        hub_tokens = set(_tokenize(hub))
        if hub_tokens & set(tokens):
            matching_hubs.append({"hub": hub, **info})
    matching_hubs.sort(key=lambda h: -h["count"])

    # Related tokens via co-occurrence. For each query token, surface the top
    # neighbours that share files. Useful when the query token has weak direct
    # hits but the corpus knows it travels with another concept (e.g. a
    # village-name that always appears alongside an island-name).
    related_tokens: dict[str, list[dict]] = {}
    for tok in tokens:
        neighbours = co_idx.get(tok, [])
        if neighbours:
            related_tokens[tok] = neighbours

    # Bridge bundles: bundles that share NO direct token with the query but
    # share at least 2 strong neighbours (transitive match). Marked weak.
    direct_bundle_keys = {b["key"] for b in matching_bundles}
    expanded_tokens: set[str] = set(tokens)
    for tok, neighbours in related_tokens.items():
        for n in neighbours[:5]:
            expanded_tokens.add(n["token"])
    bridge_bundles = []
    for key, b in data.get("existing_bundles", {}).items():
        if key in direct_bundle_keys:
            continue
        overlap = (expanded_tokens - set(tokens)) & set(b.get("tokens", []))
        if len(overlap) >= 2:
            bridge_bundles.append({
                "key": key,
                "slug": b["slug"],
                "kind": b["kind"],
                "path": b["path"],
                "via_tokens": sorted(overlap),
                "file_count": b.get("file_count", 0),
                "signal": "weak_via_co_occurrence",
            })
    bridge_bundles.sort(key=lambda b: -len(b["via_tokens"]))

    result = {
        "tokens": tokens,
        "matching_themes": matching_themes,
        "matching_bundles": matching_bundles,
        "matching_hubs": matching_hubs,
        "related_tokens": related_tokens,
        "bridge_bundles": bridge_bundles,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# ----------------------------------------------------------------------------
# Setup, snapshot and first-run migration.
# ----------------------------------------------------------------------------

REQUIRED_FOLDERS_CORE = [
    "inbox/focus",
    "inbox/habits",
    "inbox/knowledge",
    "inbox/contacts/people",
    "inbox/contacts/organizations",
    "inbox/review",
    "quick",
    "_import",
    "_import/recordings",
    "_export",
    "archive",
    "trash",
    ".zanmai/extensions",
    ".zanmai/work",
    ".zanmai/memory",
    # .zanmai/memory/agents/<name> folders are derived from _ROSTER in
    # _setup_init, so the roster stays a single source (see _ROSTER).
    ".zanmai/logs",
    ".zanmai/snapshots",
    ".claude",
]


def _required_folders(vault_root: Path) -> list[str]:
    """Every folder a set-up vault must have, from the one list above.

    The single source matters more than it looks. This used to be two lists, the one
    above for a fresh install and a copy of it in the manifest for an existing vault,
    and they drifted: a release added `_import/recordings` here and not there, so a
    new vault got the folder and an updated one did not. The structure check read the
    manifest copy too, which is the part that makes such a drift invisible rather than
    merely wrong: producer and checker agreed with each other and were both missing
    the same entry, so a vault without the folder validated with exit code 0. One
    list, read by whoever creates and whoever checks, cannot disagree with itself.

    Excludes the conditional periodic-note folders (ZenNotes decides whether those
    exist at all) and `.zanmai/runtime/`, which describes this machine and is created
    when something needs it.
    """
    folders = list(REQUIRED_FOLDERS_CORE)
    folders += [f".zanmai/memory/agents/{name}" for name in _MEMORY_AGENTS]
    return folders


# Daily Notes and Weekly Notes are conditional, only created when ZenNotes
# has the corresponding feature enabled in .zennotes/vault.json. The current
# state is surfaced live in .zanmai/vault-config.md by the session-start
# hook on every session. Folder name and location come from vault.json
# (primaryNotesLocation, dailyNotes.directory, weeklyNotes.directory).


def _daily_weekly_folder_paths(vault_root: Path) -> tuple[str | None, str | None, str | None]:
    """Resolve Daily, Weekly and Monthly Notes folder paths from
    .zennotes/vault.json. Returns (daily_path, weekly_path, monthly_path), each
    is None when the corresponding note kind is not configured in vault.json (no
    ZenNotes, layout missing, or `enabled: false`). Migration creates only the
    folders that are not None."""
    vault_json = vault_root / ".zennotes" / "vault.json"
    if not vault_json.exists():
        return None, None, None
    try:
        zn = json.loads(vault_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None, None
    primary = zn.get("primaryNotesLocation")
    if primary not in ("root", "inbox"):
        return None, None, None
    prefix = "" if primary == "root" else "inbox/"

    def _path_for(section_key: str) -> str | None:
        cfg = zn.get(section_key) or {}
        if cfg.get("enabled") and cfg.get("directory"):
            return f"{prefix}{cfg['directory']}"
        return None

    return (
        _path_for("dailyNotes"),
        _path_for("weeklyNotes"),
        _path_for("monthlyNotes"),
    )


def _frontmatter_block(text: str) -> str:
    """Return a contract's raw `---`-fenced frontmatter block, fences included,
    or an empty string when there is none."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    return text[: end + 4]


def _install_skill_symlinks(vault_root: Path, mapping: list[tuple[str, str]]) -> None:
    """Write a thin adapter `.claude/skills/<folder>/SKILL.md` for each shipped
    skill: the skill's frontmatter (so the host discovers it) plus a one-line body
    pointing at the real procedure under `.zanmai/system/skills/`. Real files,
    not symlinks, portable across machines and safe to copy or sync. The
    canonical procedure stays in the AI-neutral `.zanmai/system/` tree, so a
    different host only needs its own adapter, not a rewrite. Stale adapters, a
    skill dropped by an update, or a legacy symlink from an older install, are
    pruned."""
    skills_dir = vault_root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for claude_folder, source_folder in mapping:
        source_rel = f".zanmai/system/skills/{source_folder}/SKILL.md"
        source_file = vault_root / source_rel
        if not source_file.exists():
            continue
        fm = _frontmatter_block(source_file.read_text(encoding="utf-8"))
        body = (
            f"\n\nAdapter only. Read the full procedure at `{source_rel}` and follow it, "
            "that file is authoritative. This file just registers the skill for the host."
        )
        target_dir = skills_dir / claude_folder
        target_dir.mkdir(exist_ok=True)
        target = target_dir / "SKILL.md"
        if target.exists() or target.is_symlink():
            target.unlink()  # replace a legacy symlink with a real file, never write through it
        target.write_text(fm.rstrip() + body + "\n", encoding="utf-8")
    keep = {cf for cf, _ in mapping}
    for sub in skills_dir.iterdir():
        if not sub.is_dir() or sub.name in keep:
            continue
        link = sub / "SKILL.md"
        try:
            is_ours = link.is_file() and ".zanmai/system/skills/" in link.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            is_ours = link.is_symlink()  # legacy dangling symlink
        if is_ours or (link.is_symlink() and not link.exists()):
            try:
                link.unlink()
                sub.rmdir()
            except OSError:
                pass


# Single roster source. Add or remove an expert HERE and nowhere else; every
# list below is derived from it, so the lists cannot drift apart, the exact
# failure class that crashed setup before (L31/L32: one list updated, another
# missed). Two flags per expert:
#   adapter, dispatchable as a Claude Code subagent (gets a .claude/agents adapter)
#   memory, gets .zanmai/memory/agents/<name>/ with a lessons.md so it learns
_ROSTER: list[tuple[str, bool, bool]] = [
    # name,     adapter, memory
    ("steve",   False,   True),   # main-loop identity: learns, never dispatched
    ("hank",    True,    True),
    ("reed",    True,    True),
    ("wong",    True,    True),
    ("pepper",  True,    True),
    ("carol",   True,    True),
    ("stan",    True,    True),
    ("loki",    True,    True),
]
_AGENT_NAMES: list[str] = [name for name, adapter, _ in _ROSTER if adapter]
_MEMORY_AGENTS: list[str] = [name for name, _, memory in _ROSTER if memory]
_SKILL_SYMLINK_MAP: list[tuple[str, str]] = [
    ("zanmai-close-session", "close-session"),
    ("zanmai-import", "import-bundle"),
    ("zanmai-snapshot", "snapshot"),
    ("zanmai-research", "research"),
    ("zanmai-journal", "journal"),
    ("zanmai-update", "update"),
    ("zanmai-connection", "manage-connections"),
    ("zanmai-voice", "voice"),
]


def _install_agent_symlinks(vault_root: Path, agent_names: list[str]) -> None:
    """Write a thin adapter `.claude/agents/<name>.md` for each expert: the
    expert's frontmatter (so the host discovers it) plus a one-line body pointing
    at the real contract under `.zanmai/system/experts/`. Real files, not
    symlinks, portable and copy/sync-safe. The contract stays in the AI-neutral
    `.zanmai/system/` tree, so another host only needs its own adapter. Stale
    adapters, an expert dropped by an update, or a legacy symlink, are
    pruned so no dead agent is left behind."""
    agents_dir = vault_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in agent_names:
        source_rel = f".zanmai/system/experts/{name}/{name}.md"
        source_file = vault_root / source_rel
        if not source_file.exists():
            continue
        fm = _frontmatter_block(source_file.read_text(encoding="utf-8"))
        body = (
            f"\n\nAdapter only. Read your full contract at `{source_rel}` and follow it before "
            "acting, that file is authoritative. This file just makes you discoverable to the host."
        )
        p = agents_dir / f"{name}.md"
        if p.exists() or p.is_symlink():
            p.unlink()  # replace a legacy symlink with a real file, never write through it
        p.write_text(fm.rstrip() + body + "\n", encoding="utf-8")
    keep = set(agent_names)
    for entry in agents_dir.glob("*.md"):
        if entry.stem in keep:
            continue
        try:
            is_ours = entry.is_file() and ".zanmai/system/experts/" in entry.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            is_ours = entry.is_symlink()  # legacy dangling symlink
        if is_ours or (entry.is_symlink() and not entry.exists()):
            entry.unlink()


def _render_user_md_init(
    *, first_name: str, last_name: str, language: str, owner_contact_slug: str,
    zennotes_installed: bool = True, zen_cli_installed: bool = True,
    preferred_address: str = "",
    python_cmd: str = "python3",
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    full_name = f"{first_name} {last_name}".strip()
    address_field = f'"{preferred_address}"' if preferred_address else '""'
    address_line = f"- **Preferred address**: {preferred_address}" if preferred_address else f"- **Preferred address**: (same as first name)"
    return f"""---
first_name: "{first_name}"
last_name: "{last_name}"
preferred_address: {address_field}
language: "{language}"
owner_contact: "{owner_contact_slug}"
python_cmd: "{python_cmd}"
auto_snapshots: true
zennotes_installed: {str(zennotes_installed).lower()}
zen_cli_installed: {str(zen_cli_installed).lower()}
created: "{today}"
---

# {full_name}'s Zanmai

This file holds personalisation that survives updates. The system reads it at session start.

## Identity

- **First name**: {first_name}
- **Last name**: {last_name}
{address_line}
- **Language preference**: {language} (auto-detected from how you write; override here if needed)
- **Owner contact**: [[{owner_contact_slug}]]

## Notes for Steve

Add anything you want Steve to know about you here: preferences, working style, anything that should persist across sessions. This is not a profile form, write freely.

## Feature toggles

- `auto_snapshots: true`. Master switch for every snapshot the system would otherwise take automatically (session-start snapshot, pre-import snapshot, pre-risky-write snapshot, `/zanmai:snapshot` slash-command). When `false`, all `zanmai.py snapshot create` calls exit silently with `skip: auto_snapshots disabled` and no folder is written, useful when the user has their own backup discipline (git, Time Machine, ...). Flip it with `zanmai.py snapshot enable` / `disable` or by editing this line directly.
- `python_cmd: "{python_cmd}"`. The Python invocation that worked at setup time. Steve uses this when running scripts, substitutes for `python3` in skill template phrasing. On Windows this is often `py -3` or `python`, on Linux and macOS usually `python3`.
- `zennotes_installed: {str(zennotes_installed).lower()}`. Whether the ZenNotes app was detected at setup time. Skills check this before invoking ZenNotes-specific features.
- `zen_cli_installed: {str(zen_cli_installed).lower()}`. Whether the `zn` CLI can act on this vault: the binary is installed and ZenNotes has opened this vault. Skills fall back to Unix commands when false.

Note templates are ZenNotes' own feature: when configured in ZenNotes settings, ZenNotes applies the template as you create a note. Zanmai's capture is template-independent, it appends below whatever the note already holds and neither requires nor writes a template.

Daily, Weekly and Monthly Notes state is not stored here. It lives in `.zennotes/vault.json` and is surfaced for the AI on every session start in `.zanmai/vault-config.md`.
"""


def _render_owner_contact_init(
    *, first_name: str, last_name: str, email: str, slug: str, language: str = "auto",
    nickname: str = "",
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    full_name = f"{first_name} {last_name}".strip()
    email_field = f'"{email}"' if email else "\"\""
    nickname_field = f'"{nickname}"' if nickname else '""'
    frontmatter = f"""---
kind: contact/person
slug: {slug}
created: {today}
nickname: {nickname_field}
role: ""
org: ""
email: {email_field}
phone: ""
birthday: ""
address: ""
website: ""
---

# {full_name}
"""
    if nickname:
        address_en = f"Steve addresses you as **{nickname}**. Setup picked this up from your answer. To change it, edit `nickname` in the frontmatter above."
    else:
        address_en = f"Steve addresses you as **{first_name}** (same as your first name). For a different address form, set `nickname` in the frontmatter above."

    body = f"""
This is the owner contact for this vault. `.zanmai/user.md` points here as `owner_contact`. Steve reads it at session start to know who the user is.

## Address style

{address_en}

## Tone preferences

Tell Steve about tone, reply length, language quirks you want. Two entries come preset because they are how Zanmai writes by default. Delete either one if you want it differently, and add your own below.

- **No dash-sentences.** No em dash or en dash used as sentence punctuation, and not the rhythm behind it either: a statement, a dash, an afterthought pinned on the end. Finish the thought, or split it into two sentences. Hyphens inside compound words are normal and stay.
- **No AI phrasing.** No "not just X, but Y", no sentence that only announces what the next one will say, no words that sound like a product page. Say the thing plainly, vary the sentence length, and leave out what carries nothing.

Steve adds what he observes over time below, and you can curate it.

## Lessons Steve learned about me

Cross-session learnings about you specifically that Steve has picked up. Steve only writes here through `close-session` graduation, never silently.

Sub-categories Steve uses when graduating lessons here:

- **Domain expertise**: areas where you have deep knowledge. Steve and Reed consult this before research and explanations so they do not waste your time with beginner content in fields you know cold. Audience calibration in the Reed dispatch reads this directly.
- **Style preferences**: how you want things written (reply length, formality, jargon tolerance).
- **Decisions you've made before**: choices Steve should respect (tool picks, workflows, naming conventions).
- **One-off context that recurred**: facts about you that came up more than once and are likely to matter again.

(empty)
"""
    return frontmatter + body


def _render_general_md(owner_slug: str) -> str:
    return f"""# General memory

Cross-session learnings, user preferences, open threads, decisions.

## Preferences

(none yet)

## Lessons

(none yet)

## Open threads

- Owner profile fields can be added on demand: birthday, phone, address, organisation, role, website. Add them to the frontmatter of [[{owner_slug}]] when the user mentions them or when a concrete trigger appears (a booking needs a phone number, a contact links to an organisation). Do not prompt unprompted.

## Decisions

(none yet)
"""


def _render_activity_log() -> str:
    return """# Activity log

Chronological append-only log of writes and notable actions across the vault.
Format per entry: `## [YYYY-MM-DD HH:MM] - <agent> - <what>` so the log greps cleanly.

"""


def _render_agent_lessons(agent_name: str) -> str:
    return f"""# {agent_name}'s lessons

Cross-session lessons specific to {agent_name}: what was learned, and, just as important, the bounds it holds within. A lesson applied in the wrong context is worse than no lesson, so every entry names where it stops.

Each entry, newest on top, datestamped:

## [YYYY-MM-DD] one-line lesson
- **Holds when:** the concrete situation this applies to.
- **Does not hold when:** where it would mislead, the boundary that keeps it from being over-applied.
- **Why:** the run or user-correction that taught it.
- **Standing:** `confirmed` once the user has judged the result it came from, `provisional` until then.

A lesson drawn from the agent's own view of its work is `provisional`: the run
looked good from the inside, and nobody has seen the result yet. Self-assessment
is the weakest evidence there is, so a provisional lesson is re-checked the next
time the topic comes up, and confirmed or struck then.

Later feedback that contradicts a lesson does not silently replace it. The entry
keeps its place and gains a **Disproven:** line with the date and what the
feedback showed, and it stops applying from that moment. A wrong lesson left
standing is worse than no lesson, because every run that follows it collects more
evidence for itself.

"""


def _render_master_index(first_name: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""# {first_name}'s Zanmai master index

Created {today}. Steve maintains this as bundles are added.

## Focus

Active attention bundles live here. See `inbox/focus/`.

(empty. Nothing in focus yet.)

## Habits

Recurring routines live here. See `inbox/habits/`.

(empty)

## Knowledge

Persistent reference material. Default class for anything that does not clearly belong in focus or habits. See `inbox/knowledge/`.

(empty)

## Contacts

Single files per person and organisation.

### People (`inbox/contacts/people/`)

(empty)

### Organisations (`inbox/contacts/organizations/`)

(empty)

## Review

`inbox/review/` is where the AI puts read-once briefings for a specific decision. Read, then archive. Multi-file operations approve via chat with a TL;DR and a structure tree, not via files here.

(empty)

## Daily and Weekly notes

ZenNotes-managed. Folder name and location come from `.zennotes/vault.json` and are surfaced in `.zanmai/vault-config.md`. Without ZenNotes configuration these notes do not exist for this vault.

## Drop area

`_import/` is the drop area. Put folders or files here for the `import-bundle` skill to file.

## System

- `.zanmai/user.md`: your profile.
- `.zanmai/system/`: the Zanmai distribution (do not edit, replaced on update).
- `.zanmai/memory/`: cross-session learnings and activity log.
- `.zanmai/snapshots/`: rollback points.
- `.zanmai/logs/`: session logs, operation reports, archived plans.
"""


def _render_settings_json(vault_root: Path, *, python_cmd: str = "python3") -> str:
    """Render .claude/settings.json with the Zanmai hooks wired. Every
    hook is a subcommand of the single zanmai.py CLI now. No connection-guard:
    a host-exposed MCP is available for use, Zanmai adds no second consent gate
    (LD6, re-decided 2026-07-15). The script path is rooted at $CLAUDE_PROJECT_DIR,
    which Claude Code shell-expands to the project root at hook run time, so this
    file is portable: it ships with the folder and works wherever the vault is
    copied, no absolute machine path baked in. vault_root is kept in the signature
    for the callers that pass it; the rendered command no longer needs it."""
    zb = "$CLAUDE_PROJECT_DIR/.zanmai/system/scripts/zanmai.py"
    config = {
        "autoMemoryEnabled": False,
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook session-start'}
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook kind-required'},
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook permission-guard'},
                    ],
                },
                {
                    "matcher": "Agent",
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook dispatch-guard'},
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook index-consistency'}
                    ],
                }
            ],
        },
    }
    return json.dumps(config, indent=2) + "\n"


def _shipped_hook_commands() -> set[str]:
    """The `hook <name>` fragments this distribution expects to find wired in
    `.claude/settings.json`, read out of the renderer itself so the two cannot
    drift apart. Used by `setup validate` to catch a host config that was written
    by an older version of this script."""
    config = json.loads(_render_settings_json(Path("."), python_cmd="python3"))
    found: set[str] = set()
    for groups in (config.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks") or []:
                match = re.search(r"(hook\s+[a-z-]+)\s*$", hook.get("command") or "")
                if match:
                    found.add(match.group(1))
    return found


def _verify_host_config(vault: Path) -> list[str]:
    """What the host config must actually carry, measured on disk. Empty means good.

    The distribution ships a hook, an expert or a skill; the host-side wiring for it
    is written separately and is machine-local, so shipped and arrived are two
    different facts. Everything that decided whether wiring was needed is off-limits
    here: this reads `.claude/` and reports what is not there. It does not create
    anything, because a check that repairs on the way past turns a missing piece into
    a piece that was never missing, and the gap it covers is then only findable by
    someone who already suspects it.

    Cheap on purpose, a handful of existence checks and one string search, so it can
    run on every session start rather than only when a version number moved.
    """
    problems: list[str] = []

    settings_file = vault / ".claude" / "settings.json"
    if not settings_file.is_file():
        problems.append("no .claude/settings.json, so no hook of this distribution is wired")
    else:
        try:
            wired = settings_file.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"cannot read .claude/settings.json ({exc})")
            wired = ""
        for expected in sorted(_shipped_hook_commands()):
            if expected not in wired:
                problems.append(f"hook not wired in .claude/settings.json: '{expected}'")

    for name in _AGENT_NAMES:
        if not (vault / ".claude" / "agents" / f"{name}.md").is_file():
            problems.append(f"expert adapter missing: .claude/agents/{name}.md")

    for claude_folder, source_folder in _SKILL_SYMLINK_MAP:
        if not (vault / ".zanmai" / "system" / "skills" / source_folder / "SKILL.md").is_file():
            continue  # not shipped in this version, so nothing to wire
        if not (vault / ".claude" / "skills" / claude_folder / "SKILL.md").is_file():
            problems.append(f"skill adapter missing: .claude/skills/{claude_folder}/SKILL.md")

    return problems


def _mcp_tools_from_experts(vault_root: Path) -> list[str]:
    """Distinct `mcp__<server>__<tool>` names any registered expert is granted,
    read verbatim from each expert contract's `tools:` frontmatter. Used to
    pre-allow those exact tools in settings.local.json so a dispatched expert can
    use a host-exposed MCP without a per-call prompt (LD6: a host-exposed MCP is
    available for use, the host config is the opt-in, so no gate and no prompt)."""
    tools: list[str] = []
    experts_dir = vault_root / ".zanmai" / "system" / "experts"
    for name in _AGENT_NAMES:
        contract = experts_dir / name / f"{name}.md"
        if not contract.exists():
            continue
        fm = _frontmatter_block(contract.read_text(encoding="utf-8"))
        for m in re.finditer(r"mcp__[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+", fm):
            if m.group(0) not in tools:
                tools.append(m.group(0))
    return tools


def _render_settings_local_json(vault_root: Path, *, python_cmd: str = "python3") -> str:
    """Render .claude/settings.local.json with the allow-rules. The zanmai.py
    script (every subcommand and hook routes through it) plus the exact MCP tools
    the registered experts are granted, so a host-exposed source runs without a
    per-call prompt."""
    scripts_dir = vault_root / ".zanmai" / "system" / "scripts"
    allow = [f'Bash({python_cmd} "{scripts_dir}/zanmai.py":*)']
    allow.extend(_mcp_tools_from_experts(vault_root))
    config = {"permissions": {"allow": allow}}
    return json.dumps(config, indent=2) + "\n"


def _run_init_migration(
    vault_root: Path,
    *,
    first_name: str,
    last_name: str,
    language: str = "auto",
    email: str = "",
    preferred_address: str = "",
    python_cmd: str = "python3",
    zennotes_installed: bool = True,
    zen_cli_installed: bool = True,
) -> None:
    """First-time vault setup. Creates folder skeleton, user.md, owner-contact,
    settings, symlinks, memory files and master INDEX. Idempotent only on the
    folder mkdir step; file writes overwrite. Used by `setup init`."""
    daily_path, weekly_path, monthly_path = _daily_weekly_folder_paths(vault_root)

    folders = _required_folders(vault_root)
    for note_path in (daily_path, weekly_path, monthly_path):
        if note_path:
            folders.append(note_path)
    for rel in folders:
        (vault_root / rel).mkdir(parents=True, exist_ok=True)

    nickname = preferred_address.strip() if preferred_address.strip() and preferred_address.strip() != first_name else ""

    contact_slug = _slugify(f"{first_name} {last_name}")
    contact_path_abs = vault_root / "inbox" / "contacts" / "people" / f"{contact_slug}.md"
    if not contact_path_abs.exists():
        contact_path_abs.write_text(
            _render_owner_contact_init(
                first_name=first_name,
                last_name=last_name,
                email=email,
                slug=contact_slug,
                language=language,
                nickname=nickname,
            ),
            encoding="utf-8",
        )

    user_md = vault_root / ".zanmai" / "user.md"
    user_md.write_text(
        _render_user_md_init(
            first_name=first_name,
            last_name=last_name,
            language=language,
            owner_contact_slug=contact_slug,
            zennotes_installed=zennotes_installed,
            zen_cli_installed=zen_cli_installed,
            preferred_address=nickname,
            python_cmd=python_cmd,
        ),
        encoding="utf-8",
    )

    (vault_root / ".claude" / "settings.json").write_text(
        _render_settings_json(vault_root, python_cmd=python_cmd), encoding="utf-8"
    )

    _install_skill_symlinks(vault_root, _SKILL_SYMLINK_MAP)

    _install_agent_symlinks(vault_root, _AGENT_NAMES)

    settings_local = vault_root / ".claude" / "settings.local.json"
    if not settings_local.exists():
        settings_local.write_text(
            _render_settings_local_json(vault_root, python_cmd=python_cmd), encoding="utf-8"
        )

    (vault_root / ".zanmai" / "memory" / "general.md").write_text(
        _render_general_md(contact_slug), encoding="utf-8"
    )
    (vault_root / ".zanmai" / "memory" / "activity-log.md").write_text(
        _render_activity_log(), encoding="utf-8"
    )
    for agent in _MEMORY_AGENTS:
        (vault_root / ".zanmai" / "memory" / "agents" / agent / "lessons.md").write_text(
            _render_agent_lessons(agent.capitalize()), encoding="utf-8"
        )

    (vault_root / "INDEX.md").write_text(_render_master_index(first_name), encoding="utf-8")

    (vault_root / ".zanmai" / "logs" / ".keep").touch()
    (vault_root / ".zanmai" / "snapshots" / ".keep").touch()


def cmd_setup_init(args: argparse.Namespace) -> int:
    vault = Path(args.vault_root).resolve()
    if not vault.exists():
        print(f"fail: vault root does not exist: {vault}", file=sys.stderr)
        return 1
    user_md = vault / ".zanmai" / "user.md"
    if user_md.exists():
        print(f"already initialised: {user_md} exists. use 'setup update' to change schema.")
        return 0
    _run_init_migration(
        vault,
        first_name=args.first_name,
        last_name=args.last_name,
        language=args.language,
        email=args.email,
        preferred_address=args.preferred_address,
        python_cmd=args.python_cmd,
        # Detect deterministically, do not trust an AI-passed flag. Store exactly
        # the signals the session-start recheck re-derives (`.zennotes/` dir and
        # a `zn` usable for this vault), so a fresh install without ZenNotes stores `false` and
        # never reports a phantom "was there at setup" drift later.
        zennotes_installed=(vault / ".zennotes").is_dir(),
        zen_cli_installed=_zen_cli_usable(vault),
    )
    print(f"ok: vault initialised at {vault}")
    return 0


def _manifest_distribution_paths(manifest_path: Path) -> list[str]:
    """Every path the manifest calls distribution. Tiny YAML extractor, so the
    script needs no pyyaml; the manifest format is known and stable.

    The manifest is the authority on which files an update owns, and nothing else.
    The required folders deliberately do not live here as well, see
    `_required_folders`: a second copy of a list is a list that drifts, and when the
    checker reads the copy the drift stops being visible.
    """
    dist_paths: list[str] = []
    collecting = False
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped.startswith("distribution_paths:"):
            collecting = True
            continue
        if not collecting:
            continue
        if not stripped.startswith("  - "):
            break
        value = stripped[4:].strip().strip('"').strip("'")
        if value:
            dist_paths.append(value)
    return dist_paths


def _manifest_scalar(manifest_path: Path, key: str) -> str:
    """Read a single top-level scalar out of the manifest."""
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or ":" not in stripped:
            continue
        name, _, value = stripped.partition(":")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _distribution_version(vault_or_tree: Path) -> str:
    version_file = vault_or_tree / ".zanmai" / "system" / "VERSION"
    if not version_file.exists():
        return ""
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("distribution_version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


def _version_tuple(version: str) -> tuple[int, ...]:
    """Comparable form of a dotted version, unparseable parts count as zero."""
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _is_newer(candidate: str, current: str) -> bool:
    """True only when candidate is ahead, so a vault is never offered a downgrade."""
    if not candidate:
        return False
    if not current:
        return True
    return _version_tuple(candidate) > _version_tuple(current)


def _fetch(url: str, timeout: int = 60) -> bytes:
    """Plain HTTPS GET. Stdlib only, so a vault needs no extra tooling to update."""
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "Zanmai-update"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _unpack_release(archive: bytes, into: Path) -> Path:
    """Unpack a source archive and return the tree root inside it.

    A hosted archive wraps everything in a single top-level folder whose name
    carries the branch or tag, so the wrapper is stripped here.
    """
    import io
    import tarfile

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if not m.name.startswith("/") and ".." not in m.name]
        tar.extractall(into, members=members)
    roots = [p for p in into.iterdir() if p.is_dir()]
    if len(roots) == 1 and not (into / ".zanmai").exists():
        return roots[0]
    return into


def _clone_remote(vault: Path) -> str:
    """The configured origin if this vault is a working clone, else empty."""
    import subprocess

    if not (vault / ".git").exists():
        return ""
    try:
        remotes = subprocess.run(["git", "-C", str(vault), "remote"],
                                 capture_output=True, text=True, timeout=20)
        if "origin" not in remotes.stdout.split():
            return ""
        url = subprocess.run(["git", "-C", str(vault), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=20)
        return url.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _remote_version_via_git(vault: Path, branch: str) -> str:
    """The version the clone's own origin offers.

    A clone must be measured against the remote it came from, not against an
    address in the manifest, or a vault cloned from a fork could never update.
    Fetch only moves refs, the working tree is untouched.
    """
    import subprocess

    def run(*cmd: str):
        return subprocess.run(["git", "-C", str(vault), *cmd],
                              capture_output=True, text=True, timeout=120)

    if run("fetch", "origin").returncode != 0:
        return ""
    shown = run("show", f"origin/{branch}:.zanmai/system/VERSION")
    if shown.returncode != 0:
        return ""
    for line in shown.stdout.splitlines():
        if line.startswith("distribution_version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


def _upgrade_via_git(vault: Path, branch: str) -> tuple[bool, str]:
    """Fast-forward a cloned vault, so it stays a clean clone.

    Copying files into a clone would leave it looking locally modified and a
    later `git pull` by hand would refuse, so a clone is upgraded through git.
    """
    import subprocess

    def run(*cmd: str):
        return subprocess.run(["git", "-C", str(vault), *cmd],
                              capture_output=True, text=True, timeout=180)

    dirty = run("status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        return False, ("the vault has local edits to distribution files, so a clean "
                       "fast-forward is not possible; review them first")
    fetched = run("fetch", "origin")
    if fetched.returncode != 0:
        return False, (fetched.stderr.strip() or "fetch failed")
    merged = run("merge", "--ff-only", f"origin/{branch}")
    if merged.returncode != 0:
        return False, (merged.stderr.strip() or "fast-forward not possible")
    return True, ""


def _refresh_host_config(vault: Path, quiet: bool = False) -> None:
    """Re-run the host-side refresh so adapters and settings match the new files.

    **In a separate process, and that is the whole point.** This runs right after
    an update replaced the distribution, so the module in memory is still the
    previous version. Rendering the host config from it writes the old shape and
    reports success, which is how a release that adds a hook, a matcher or a slash
    command can arrive with that addition silently missing: the function is in the
    new script on disk and nothing ever calls it. Worse, the caller then records the
    new version as the one the host config was built for, so the session-start
    check sees no drift and never repairs it. The script on disk is already the new
    one, so it is the one that must do the writing.

    Quiet when called from a hook, whose stdout is the session briefing and must
    not carry mechanical progress lines.
    """
    script = vault / ".zanmai" / "system" / "scripts" / "zanmai.py"
    if not script.is_file():
        print(f"warning: cannot refresh host config, no script at {script}", file=sys.stderr)
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "setup", "update", str(vault)],
            capture_output=True, text=True,
        )
    except OSError as exc:
        print(f"warning: host config refresh failed ({exc}), run 'setup update' by hand",
              file=sys.stderr)
        return
    if result.returncode != 0:
        print(f"warning: host config refresh failed ({result.stderr.strip()}), "
              "run 'setup update' by hand", file=sys.stderr)
        return
    if not quiet and result.stdout.strip():
        print(result.stdout.strip())


def _record_host_config_version(vault: Path, version: str) -> None:
    """Remember which distribution version the host config was built for.

    Machine-local on purpose: the session-start check uses it to notice a
    version that arrived some other way, for example a manual `git pull`.
    """
    marker = vault / ".zanmai" / "runtime" / "host-config-version"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(version + "\n", encoding="utf-8")
    except OSError:
        pass


def _quiet_update_probe(vault: Path) -> str:
    """Ask the update source for its version at most once a day, briefly.

    The session-start hook runs again on every resume and every compaction, so
    "once per session" is not once: it reached out to the network several times
    an hour and put the same offer back in front of the user each time. The
    answer changes about as often as a release does, so it is fetched once a day
    and read from the cache in between. No network call, no repeated offer.

    It must never delay the session or fail loudly: short timeout, any problem
    swallowed, and the last answer kept so a session without network still knows
    what the previous one found. Returns the newer version when there is one,
    otherwise an empty string.
    """
    cache = vault / ".zanmai" / "runtime" / "update-check.json"
    now = datetime.now(timezone.utc)

    state: dict = {}
    try:
        state = json.loads(cache.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        state = {}
    checked = str(state.get("checked", ""))
    if checked:
        try:
            age = now - datetime.fromisoformat(checked)
            if age < timedelta(hours=24):
                known = str(state.get("available", ""))
                return known if _is_newer(known, _distribution_version(vault)) else ""
        except ValueError:
            pass

    manifest = vault / ".zanmai" / "system" / "manifest.yaml"
    source = _manifest_scalar(manifest, "update_source") if manifest.exists() else ""
    branch = _manifest_scalar(manifest, "update_branch") or "main" if manifest.exists() else "main"
    available = ""
    if source:
        try:
            raw = _fetch(
                f"https://raw.githubusercontent.com/{source.strip('/')}/{branch}/.zanmai/system/VERSION",
                timeout=4,
            ).decode("utf-8", "replace")
            remote = ""
            for line in raw.splitlines():
                if line.startswith("distribution_version:"):
                    remote = line.split(":", 1)[1].strip().strip('"')
                    break
            if _is_newer(remote, _distribution_version(vault)):
                available = remote
        except Exception:  # noqa: BLE001
            # no network: keep whatever the last successful probe found
            try:
                state = json.loads(cache.read_text(encoding="utf-8"))
                previous = state.get("available", "")
                available = previous if _is_newer(previous, _distribution_version(vault)) else ""
            except (json.JSONDecodeError, ValueError, OSError):
                available = ""

    state.update({"checked": now.isoformat(timespec="seconds"), "available": available})
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return available


def _unattended_log_to_report(vault: Path) -> Path | None:
    """The last session's log, when nobody was in the chat for it and it has not been
    named yet. Derived from the log the run itself wrote, so there is no second marker to
    keep in step, and remembered by name so a resume or a compaction does not say it twice.
    """
    logs_dir = vault / ".zanmai" / "logs"
    logs = sorted(logs_dir.rglob("*.md"), key=lambda p: p.name) if logs_dir.is_dir() else []
    if not logs:
        return None
    newest = logs[-1]
    try:
        head = newest.read_text(encoding="utf-8")[:400]
    except OSError:
        return None
    if "session_type: unattended" not in head:
        return None
    state_file = vault / ".zanmai" / "runtime" / "session-state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        state = {}
    if state.get("unattended_reported") == newest.name:
        return None
    state["unattended_reported"] = newest.name
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return newest


def _update_offer_due(vault: Path) -> bool:
    """True once a day. Mentioning an available version is worth one line a day, not one
    per hook run, and the hook runs again on every resume and compaction."""
    cache = vault / ".zanmai" / "runtime" / "update-check.json"
    today = _today()
    try:
        state = json.loads(cache.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        state = {}
    if state.get("announced") == today:
        return False
    state["announced"] = today
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return True


def _hand_off_to_new_script(vault: Path, from_version: str, to_version: str, *,
                            origin: str = "", replaced: int | None = None,
                            withdrawn: int | None = None) -> int:
    """Everything after the file replacement runs in the new script, not this one.

    This process was started from the previous version and still holds it in memory,
    so any post-replacement step it performs is performed by the code the release just
    replaced. That is how a release can arrive with its new hook unwired while
    reporting success. Wrapping the one step that was known to be affected fixes one
    symptom and leaves the next step someone adds in the same trap, so the boundary
    sits here: the file swap is the last thing this side does, and the host refresh,
    the verification, the version marker and even the success message belong to the
    new side of it.
    """
    script = vault / ".zanmai" / "system" / "scripts" / "zanmai.py"
    if not script.is_file():
        print(f"error: the new version left no script at {script}, nothing was verified. "
              "Run 'setup update' and 'setup validate' by hand.", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(script), "setup", "post-upgrade", str(vault),
           "--from", from_version, "--to", to_version]
    if origin:
        cmd += ["--origin", origin]
    if replaced is not None:
        cmd += ["--replaced", str(replaced)]
    if withdrawn is not None:
        cmd += ["--withdrawn", str(withdrawn)]
    try:
        return subprocess.run(cmd).returncode
    except OSError as exc:
        print(f"error: the new version's files are in place but could not be run ({exc}). "
              "Run 'setup update' and then 'setup validate' by hand.", file=sys.stderr)
        return 1


def cmd_setup_post_upgrade(args: argparse.Namespace) -> int:
    """The tail of an upgrade, run by the new script on its own installation.

    Called by `setup upgrade` right after the files were replaced, never by hand in
    normal use. Refreshes the host config, then checks what actually arrived, and
    records the version only when that check passes.

    The order is the point. The version marker used to be written straight after the
    refresh, whatever the refresh achieved, and the session-start repair triggers on
    the marker disagreeing with the shipped version: one hopeful write of the marker
    permanently disarmed the mechanism built to catch exactly this. A marker that
    means "the host config was verified at this version" cannot do that; one that
    means "an upgrade to this version was attempted" can.
    """
    vault = Path(args.vault_root).resolve()
    to_version = args.to_version or _distribution_version(vault)

    # A refresh that cannot write, an unreadable permission, a full disk: whatever it
    # is, it must come out as a sentence and leave the marker alone. A traceback here
    # would end the upgrade in the one state this whole command exists to prevent,
    # unexplained and half-applied.
    try:
        refreshed = cmd_setup_update(argparse.Namespace(vault_root=str(vault)))
    except OSError as exc:
        print(f"error: the new files are in place but the host refresh could not write ({exc})",
              file=sys.stderr)
        refreshed = 1
    if refreshed != 0:
        print(f"error: the new files are in place but the host refresh failed. The recorded "
              f"version stays at {args.from_version or 'the previous one'}, so the next session "
              "repairs it. Run 'setup update' by hand to do it now.", file=sys.stderr)
        return 1

    problems = _verify_host_config(vault)
    if problems:
        print("error: the new files are in place but the host config is incomplete:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"the recorded version stays at {args.from_version or 'the previous one'}, so the "
              "next session repairs this instead of considering it done", file=sys.stderr)
        return 1

    _record_host_config_version(vault, to_version)

    detail = ""
    if args.replaced is not None:
        detail = f" ({args.replaced} files replaced"
        detail += f", {args.withdrawn} withdrawn)" if args.withdrawn else ")"
    elif args.origin:
        detail = f" from {args.origin}"
    print(f"ok: updated to {to_version}{detail}, host config verified")
    print("your notes, settings and extensions were not touched")
    return 0


def cmd_setup_upgrade(args: argparse.Namespace) -> int:
    """Replace the distribution files with the newest published version.

    Deliberately independent of how the vault arrived: an unpacked archive
    updates exactly like a clone. A clone is fast-forwarded through git so it
    stays a clean clone; anything else has the new files fetched over HTTPS.
    Only paths the manifest calls distribution are touched.
    """
    vault = Path(args.vault_root).resolve()
    manifest = vault / ".zanmai" / "system" / "manifest.yaml"
    if not manifest.exists():
        print(f"error: no Zanmai system folder at {vault}", file=sys.stderr)
        return 1

    local = _distribution_version(vault)
    branch = _manifest_scalar(manifest, "update_branch") or "main"
    is_clone = bool(_clone_remote(vault))

    if is_clone:
        remote = _remote_version_via_git(vault, branch)
        if not remote:
            print("error: could not read a version from this vault's own origin", file=sys.stderr)
            return 1
    else:
        source = _manifest_scalar(manifest, "update_source")
        if not source:
            print("error: the manifest names no update source", file=sys.stderr)
            return 1
        base = source.strip("/")
        try:
            raw = _fetch(
                f"https://raw.githubusercontent.com/{base}/{branch}/.zanmai/system/VERSION"
            ).decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            print(f"error: could not reach the update source ({exc})", file=sys.stderr)
            return 1
        remote = ""
        for line in raw.splitlines():
            if line.startswith("distribution_version:"):
                remote = line.split(":", 1)[1].strip().strip('"')
                break
        if not remote:
            print("error: the update source reports no version", file=sys.stderr)
            return 1

    if not _is_newer(remote, local):
        print(f"ok: already on the current version ({local})")
        return 0

    origin = source or "an unset origin"
    print(f"update available: {local} -> {remote} (from {origin})")
    if args.check:
        return 0

    # a clone is upgraded through git, so it stays a clean clone and a manual
    # `git pull` keeps working afterwards
    if is_clone:
        ok, problem = _upgrade_via_git(vault, branch)
        if ok:
            applied = _distribution_version(vault)
            return _hand_off_to_new_script(vault, local, applied, origin="the repository this vault was cloned from")
        print(f"error: {problem}", file=sys.stderr)
        return 1

    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as work:
        work_path = Path(work)
        try:
            archive = _fetch(f"https://codeload.github.com/{base}/tar.gz/refs/heads/{branch}", timeout=180)
        except Exception as exc:  # noqa: BLE001
            print(f"error: could not download the new version ({exc})", file=sys.stderr)
            return 1

        tree = _unpack_release(archive, work_path)
        new_manifest = tree / ".zanmai" / "system" / "manifest.yaml"
        if not new_manifest.exists():
            print("error: the downloaded version has no manifest, nothing applied", file=sys.stderr)
            return 1

        new_paths = _manifest_distribution_paths(new_manifest)
        old_paths = _manifest_distribution_paths(manifest)

        # Both path lists come out of a manifest that was just downloaded, so they
        # are input, not fact. Without a containment check, one `../` in a path
        # writes outside the vault, and the removal loop below deletes outside it.
        # Resolve BOTH sides: resolving only the candidate refuses every update on
        # macOS, where the temporary directory is itself a symlink, which would turn
        # a containment bug into a total denial of the update path.
        vault_real = vault.resolve()

        def contained(rel: str) -> Path | None:
            if rel.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:", rel):
                return None
            candidate = (vault_real / rel).resolve()
            if candidate == vault_real or vault_real not in candidate.parents:
                return None
            return candidate

        refused = [rel for rel in set(new_paths) | set(old_paths) if contained(rel) is None]
        if refused:
            print("error: the downloaded manifest lists paths outside the vault, nothing applied:",
                  file=sys.stderr)
            for rel in sorted(refused)[:10]:
                print(f"  {rel}", file=sys.stderr)
            return 1

        written = 0
        for rel in new_paths:
            src = tree / rel
            if not src.is_file():
                continue
            dst = contained(rel)
            if dst is None:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            written += 1

        # files the previous version shipped and this one no longer does
        removed = 0
        for rel in old_paths:
            if rel in new_paths:
                continue
            stale = contained(rel)
            if stale is not None and stale.is_file():
                stale.unlink()
                removed += 1

    return _hand_off_to_new_script(vault, local, remote, replaced=written, withdrawn=removed)


def cmd_setup_validate(args: argparse.Namespace) -> int:
    vault = Path(args.vault_root).resolve()
    fails: list[str] = []
    user_md = vault / ".zanmai" / "user.md"
    if not user_md.exists():
        fails.append("missing .zanmai/user.md, run 'setup init' first")
    manifest_path = vault / ".zanmai" / "system" / "manifest.yaml"
    if not manifest_path.exists():
        fails.append("missing .zanmai/system/manifest.yaml")
    else:
        for rel in _manifest_distribution_paths(manifest_path):
            if not (vault / rel).exists():
                fails.append(f"missing distribution file: {rel}")
    for rel in _required_folders(vault):
        if not (vault / rel).is_dir():
            fails.append(f"missing required folder: {rel}. Run 'setup update' to create it.")
    for rel in ["INDEX.md", ".zanmai/memory/general.md", ".zanmai/memory/activity-log.md"]:
        if not (vault / rel).is_file():
            fails.append(f"missing generated file: {rel}")
    # Everything the distribution ships and the host must carry: hooks wired, expert
    # and skill adapters present. Same function the upgrade and the session start use,
    # so what passes here is what passes there.
    for problem in _verify_host_config(vault):
        fails.append(f"{problem}. Run 'setup update' to rebuild the host config.")
    # Adapters must also not be left over: no dangling legacy symlink, and nothing
    # for an expert an update dropped from the roster.
    agents_dir = vault / ".claude" / "agents"
    if agents_dir.is_dir():
        roster = set(_AGENT_NAMES)
        for entry in agents_dir.glob("*.md"):
            if entry.is_symlink() and not entry.exists():
                fails.append(f"dangling agent adapter: {entry.relative_to(vault)}")
                continue
            try:
                ours = entry.is_file() and ".zanmai/system/experts/" in entry.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                ours = False
            if ours and entry.stem not in roster:
                fails.append(f"stale agent adapter (not in roster): {entry.relative_to(vault)}")
    # A synced folder is a normal home for a vault, so this is a note rather than a
    # failure. What it reports is the part that is genuinely wrong to copy.
    notes: list[str] = []
    notes.extend(_memory_size_report(vault))
    host = _detect_sync_host(vault)
    if host:
        present = [rel for rel in MACHINE_LOCAL_PATHS + BULKY_PATHS if (vault / rel).exists()]
        how = next((h for name, h in SYNC_HOSTS if name == host), "")
        notes.append(f"this vault sits under {host}, which is fine as a backup")
        if present:
            notes.append("keep these out of the copy: " + ", ".join(present))
            notes.append(f"  {host}: {how}")
            notes.append("  runtime/ and work/ describe this machine only, and the snapshots are "
                         "full copies of the vault, so a backup would contain a backup")
        conflicts = sorted(
            str(f.relative_to(vault))
            for f in vault.glob("inbox/**/*")
            if f.is_file() and any(mark in f.name.lower() for mark in
                                   ("conflicted copy", "conflict)", "-konflikt", "in konflikt"))
        )
        if conflicts:
            fails.append(
                f"{len(conflicts)} sync conflict copy/copies inside inbox/, which break the rule that a "
                f"fact exists once: {', '.join(conflicts[:5])}"
                + (" …" if len(conflicts) > 5 else "")
            )

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"ok: vault at {vault} validates")
    for note in notes:
        print(f"    {note}")
    return 0


def cmd_setup_update(args: argparse.Namespace) -> int:
    """Post-merge mechanic refresh for an updated vault. The git fetch and the
    ff-merge happen outside this command (Pepper runs them via Bash with the
    user-facing TL;DR preview gate). After the working tree carries the new
    distribution, this command refreshes the host-side state that does not
    live in git: agent symlinks under `.claude/agents/`, skill symlinks under
    `.claude/skills/`, `.claude/settings.json`, and the top-level folders the
    manifest requires (empty ones carry no files, so git cannot deliver them).
    Idempotent, safe to run repeatedly on the same merged state."""
    vault = Path(args.vault_root).resolve()
    if not vault.exists():
        print(f"fail: vault root does not exist: {vault}", file=sys.stderr)
        return 1
    user_md = vault / ".zanmai" / "user.md"
    if not user_md.exists():
        print(
            f"fail: vault not initialised (no .zanmai/user.md). Run 'setup init' first.",
            file=sys.stderr,
        )
        return 1

    python_cmd = "python3"
    try:
        fm = _session_parse_frontmatter(user_md.read_text(encoding="utf-8"))
        if fm.get("python_cmd"):
            python_cmd = fm["python_cmd"]
    except OSError:
        pass

    # Folders an empty release cannot deliver, since git carries no empty directory.
    # Same list `setup init` creates from and `setup validate` checks against.
    for rel in _required_folders(vault):
        (vault / rel).mkdir(parents=True, exist_ok=True)

    _install_agent_symlinks(vault, _AGENT_NAMES)
    _install_skill_symlinks(vault, _SKILL_SYMLINK_MAP)

    settings_path = vault / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        _render_settings_json(vault, python_cmd=python_cmd), encoding="utf-8"
    )

    # Merge the baseline allow-rules (zanmai.py + the experts' MCP tools) into
    # settings.local.json: add any that are missing, keep whatever the user added.
    local_path = vault / ".claude" / "settings.local.json"
    baseline = json.loads(_render_settings_local_json(vault, python_cmd=python_cmd))
    existing: dict = {}
    if local_path.exists():
        try:
            existing = json.loads(local_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    allow = list((existing.get("permissions") or {}).get("allow") or [])
    for rule in baseline["permissions"]["allow"]:
        if rule not in allow:
            allow.append(rule)
    existing.setdefault("permissions", {})["allow"] = allow
    local_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    # Backfill a lessons file for any expert added after this vault was
    # initialised. Memory is user-immune: create only, never overwrite.
    for agent in _MEMORY_AGENTS:
        lessons = vault / ".zanmai" / "memory" / "agents" / agent / "lessons.md"
        if not lessons.exists():
            lessons.parent.mkdir(parents=True, exist_ok=True)
            lessons.write_text(_render_agent_lessons(agent.capitalize()), encoding="utf-8")

    print(
        f"ok: refresh complete at {vault} "
        f"(agent symlinks, skill symlinks, settings.json, settings.local.json)"
    )
    return 0


# Snapshot ----

_SNAPSHOT_EXCLUDE_PATTERNS = ("__pycache__", ".DS_Store", "*.pyc")


def _snapshot_make_ignore(exclude_abs: Path | None):
    def ignore(dir_path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for pat in _SNAPSHOT_EXCLUDE_PATTERNS:
            ignored.update(fnmatch.filter(names, pat))
        if exclude_abs is not None:
            current = Path(dir_path).resolve()
            for n in names:
                if (current / n).resolve() == exclude_abs:
                    ignored.add(n)
        return ignored
    return ignore


def _set_auto_snapshots_flag(vault_root: Path, enabled: bool) -> int:
    """Flip `auto_snapshots` in `.zanmai/user.md`. Replaces an existing
    `auto_snapshots` line; if it is not present, inserts `auto_snapshots:`
    before the closing frontmatter delimiter."""
    user_md = vault_root / ".zanmai" / "user.md"
    if not user_md.exists():
        print(f"fail: {user_md} not found (run 'setup init' first)", file=sys.stderr)
        return 1
    text = user_md.read_text(encoding="utf-8")
    new_value = "true" if enabled else "false"
    pattern = re.compile(r"^auto_snapshots:\s*\S+\s*$", re.MULTILINE)
    if pattern.search(text):
        updated = pattern.sub(f"auto_snapshots: {new_value}", text, count=1)
    else:
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        inserted = False
        seen_open = False
        for line in lines:
            if line.startswith("---") and not seen_open:
                seen_open = True
                out.append(line)
                continue
            if line.startswith("---") and seen_open and not inserted:
                out.append(f"auto_snapshots: {new_value}\n")
                out.append(line)
                inserted = True
                continue
            out.append(line)
        updated = "".join(out)
        if not inserted:
            print("fail: could not locate frontmatter block in user.md", file=sys.stderr)
            return 1
    user_md.write_text(updated, encoding="utf-8")
    print(f"ok: auto_snapshots {'enabled' if enabled else 'disabled'} in {user_md.relative_to(vault_root)}")
    return 0


def cmd_snapshot_enable(args: argparse.Namespace) -> int:
    return _set_auto_snapshots_flag(Path(args.vault).resolve(), True)


def cmd_snapshot_disable(args: argparse.Namespace) -> int:
    return _set_auto_snapshots_flag(Path(args.vault).resolve(), False)


_SNAPSHOT_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4})-(.+)$")


def _iter_snapshot_dirs(snapshots_root: Path):
    if not snapshots_root.is_dir():
        return
    for entry in sorted(snapshots_root.iterdir()):
        if not entry.is_dir():
            continue
        m = _SNAPSHOT_NAME_RE.match(entry.name)
        if not m:
            continue
        date_str, time_str, slug = m.group(1), m.group(2), m.group(3)
        try:
            ts = datetime.strptime(f"{date_str}-{time_str}", "%Y-%m-%d-%H%M")
        except ValueError:
            continue
        yield entry, ts, slug


def cmd_snapshot_list(args: argparse.Namespace) -> int:
    """List snapshots under `<vault>/.zanmai/snapshots/` (or `--root`), newest
    first. One line per snapshot: date, reason slug, folder name."""
    vault = Path(args.vault).resolve()
    root = Path(args.root).resolve() if args.root else (vault / ".zanmai" / "snapshots")
    rows = list(_iter_snapshot_dirs(root))
    if not rows:
        print(f"no snapshots in {root}")
        return 0
    rows.sort(key=lambda r: r[1], reverse=True)
    for entry, ts, slug in rows:
        print(f"{ts.strftime('%Y-%m-%d %H:%M')}  {slug:<40}  {entry.name}")
    print(f"\n{len(rows)} snapshot(s) total in {root.relative_to(vault) if root.is_relative_to(vault) else root}")
    return 0


def cmd_snapshot_delete(args: argparse.Namespace) -> int:
    """Delete snapshots. Two modes:
      `snapshot delete <name>`, remove the named snapshot folder (exact match).
      `snapshot delete --older-than <days>`, bulk delete snapshots older than N days.
        Dry-run by default, prints what would go. Pass `--yes` to actually delete.
    The named-delete mode does not ask for confirmation: the caller typed the
    name explicitly. The age-bulk mode requires `--yes` because the intent is
    coarse."""
    vault = Path(args.vault).resolve()
    root = Path(args.root).resolve() if args.root else (vault / ".zanmai" / "snapshots")
    if not root.is_dir():
        print(f"fail: snapshots root not found: {root}", file=sys.stderr)
        return 1

    if args.name and args.older_than is not None:
        print("fail: pick either a name or --older-than, not both", file=sys.stderr)
        return 1

    if args.name:
        target = root / args.name
        if not target.is_dir():
            print(f"fail: no such snapshot: {target}", file=sys.stderr)
            return 1
        shutil.rmtree(target)
        print(f"deleted: {target}")
        return 0

    if args.older_than is None:
        print("fail: pass a snapshot name or --older-than <days>", file=sys.stderr)
        return 1

    cutoff = datetime.now() - timedelta(days=args.older_than)
    matches = [r for r in _iter_snapshot_dirs(root) if r[1] < cutoff]
    if not matches:
        print(f"no snapshots older than {args.older_than} day(s)")
        return 0

    if not args.yes:
        print(f"dry run, {len(matches)} snapshot(s) older than {args.older_than} day(s) would be deleted:")
        for entry, ts, slug in matches:
            print(f"  {entry.name}")
        print(f"\nrerun with --yes to delete.")
        return 0

    for entry, _ts, _slug in matches:
        shutil.rmtree(entry)
        print(f"deleted: {entry.name}")
    print(f"\n{len(matches)} snapshot(s) deleted from {root}")
    return 0


def _read_auto_snapshots_flag(vault_root: Path) -> bool:
    """Return the `auto_snapshots` flag from `.zanmai/user.md` (default true).
    Default-true means a vault without user.md (e.g. the builder's own dist
    tree) is never blocked by this check."""
    user_md = vault_root / ".zanmai" / "user.md"
    if not user_md.exists():
        return True
    try:
        fm = _session_parse_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return True
    raw = fm.get("auto_snapshots", "true")
    return str(raw).strip().strip('"').lower() != "false"


def cmd_snapshot_create(args: argparse.Namespace) -> int:
    """Make a timestamped copy of the vault under `<vault>/.zanmai/snapshots/`.
    The folder name is YYYY-MM-DD-HHMM-<reason-slug>. The vault argument
    defaults to the current directory like every other vault subcommand;
    `--root` moves the target elsewhere.

    Respects `auto_snapshots: false` in `.zanmai/user.md`, when set,
    exits 0 with `skip: auto_snapshots disabled` and writes nothing. The
    user has their own backup discipline."""
    source = Path(args.vault).resolve()
    target_base = (Path(args.root).resolve() if args.root
                   else source / ".zanmai" / "snapshots")
    # The reason becomes one path component, so it goes through the same slugify as
    # every other name in the vault. Hand-rolled lowercasing left a slash intact, and
    # a reason like "health/bones" then created a nested folder that no longer carried
    # the name it was given, which is how a snapshot stops being findable. The empty
    # check comes first, because slugify answers an empty reason with "untitled" and a
    # missing reason has to fail rather than acquire a name.
    if not args.reason.strip():
        print("fail: reason-slug empty", file=sys.stderr)
        return 1
    reason_slug = _slugify(args.reason)
    if not _read_auto_snapshots_flag(source):
        print("skip: auto_snapshots disabled in .zanmai/user.md")
        return 0
    if not source.exists():
        print(f"fail: source does not exist: {source}", file=sys.stderr)
        return 1
    if not source.is_dir():
        print(f"fail: source is not a directory: {source}", file=sys.stderr)
        return 1
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    target = target_base / f"{timestamp}-{reason_slug}"
    if target.exists():
        print(f"fail: target already exists: {target}", file=sys.stderr)
        return 2
    exclude_abs: Path | None = None
    try:
        target_base.relative_to(source)
        exclude_abs = target_base
    except ValueError:
        pass
    target_base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=_snapshot_make_ignore(exclude_abs))
    print(f"snapshot ok: {target}")
    return 0


# ----------------------------------------------------------------------------
# Connections. `scan` discovers what the host already exposes (MCP servers,
# plugins, CLIs, macOS apps) so Wong can use a source directly, the host
# configuration is the opt-in (LD6). There is no label-registry and no gate: a
# host-configured source is usable as-is. When a source cannot hold its own
# secret safely, Wong establishes and records it as a concrete-use-case
# extension (LD6 path b), built when that use case pulls it, not on spec.
# `scan` runs cross-platform; only its macOS app probe is platform-specific and
# degrades to a skip.
# ----------------------------------------------------------------------------

# Starting repertoire for `scan`'s CLI probe. A small, honest, cross-platform
# set checked via shutil.which. The list grows with the distribution; it is not
# the whole story, MCP servers are detected by Wong at runtime, not here.
_CONNECTION_SCAN_CLIS = {
    "gh": "GitHub CLI",
    "az": "Azure CLI",
    "gcloud": "Google Cloud CLI",
    "aws": "AWS CLI",
    "op": "1Password CLI",
}
# macOS-only app probe. Skipped entirely on Linux and Windows.
_CONNECTION_SCAN_MACOS_APPS = {
    "Calendar.app": "macOS Calendar",
    "Reminders.app": "macOS Reminders",
    "Mail.app": "macOS Mail",
}


def _scan_load_json(path: Path) -> dict:
    """Read a JSON config defensively. Any problem (missing, unreadable,
    malformed) returns {} so the scan degrades to fewer finds, never a crash."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _discover_mcp_servers(vault: Path) -> list[tuple[str, str]]:
    """MCP servers Claude Code knows on this machine, read from its config:
    global servers (settings.json, ~/.claude.json top-level), this project's
    servers (~/.claude.json projects[<vault>] and a project-local .mcp.json),
    plus servers configured for ANOTHER folder (scope "other folder"). The last
    group is not reachable here, but it is an access the user already has and
    that already works, so it is reused for this vault instead of establishing a
    second one beside it. Returns sorted (name, scope) pairs. Coupled to Claude
    Code's private layout by necessity, every read is defensive, a layout change
    just yields fewer."""
    home = Path.home()
    found: dict[str, str] = {}
    for name in (_scan_load_json(home / ".claude" / "settings.json").get("mcpServers") or {}):
        found.setdefault(name, "global")
    cj = _scan_load_json(home / ".claude.json")
    for name in (cj.get("mcpServers") or {}):
        found.setdefault(name, "global")
    projects = cj.get("projects") or {}
    for key, entry in projects.items():
        if key == str(vault) or not isinstance(entry, dict):
            continue
        for name in (entry.get("mcpServers") or {}):
            found.setdefault(name, "other folder")
    proj = projects.get(str(vault)) or {}
    for name in (proj.get("mcpServers") or {}):
        found[name] = "project"
    for name in (_scan_load_json(vault / ".mcp.json").get("mcpServers") or {}):
        found[name] = "project"
    return sorted(found.items())


def _discover_plugins() -> list[str]:
    """Enabled plugin identifiers from settings.json. Plugins may bring MCP tools
    or skills; the scan lists them so Wong can ask what they are for."""
    enabled = _scan_load_json(Path.home() / ".claude" / "settings.json").get("enabledPlugins") or {}
    return sorted({key.split("@")[0] for key, on in enabled.items() if on})


def cmd_connection_scan(args: argparse.Namespace) -> int:
    """Discover connectable sources for this vault: MCP servers and enabled
    plugins from Claude Code's config, plus CLIs on PATH and (macOS) relevant
    apps. Project-aware, only servers reachable from this vault are listed.
    Informational; registers nothing. The reads of Claude Code's config are
    defensive, so a layout change degrades gracefully."""
    vault = Path(args.vault).resolve()
    mcp = _discover_mcp_servers(vault)
    plugins = _discover_plugins()
    found_cli = [(name, desc) for name, desc in _CONNECTION_SCAN_CLIS.items() if shutil.which(name)]
    print("# Connection scan")
    print(f"# platform: {sys.platform}")
    print()
    reachable = [(name, scope) for name, scope in mcp if scope != "other folder"]
    elsewhere = [name for name, scope in mcp if scope == "other folder"]
    print("## MCP servers (reachable from this vault)")
    if reachable:
        for name, scope in reachable:
            print(f"  {name:<34} ({scope})")
    else:
        print("  none found")
    print()
    if elsewhere:
        print("## Already configured for another folder (not reachable here)")
        for name in elsewhere:
            print(f"  {name}")
        print("  A working access the user already has: reuse it for this vault, do not build a second one.")
        print()
    print("## Enabled plugins (may provide tools or skills)")
    if plugins:
        for name in plugins:
            print(f"  {name}")
    else:
        print("  none found")
    print()
    print("## CLIs on PATH")
    if found_cli:
        for name, desc in found_cli:
            print(f"  {name:<12} {desc}")
    else:
        print("  none from the known set")
    print()
    if sys.platform == "darwin":
        print("## macOS apps")
        app_dirs = [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
        found_app = [desc for app, desc in _CONNECTION_SCAN_MACOS_APPS.items()
                     if any((d / app).exists() for d in app_dirs)]
        for desc in (found_app or ["none from the known set"]):
            print(f"  {desc}")
        print()
    print("These are available host sources. A host-configured source is usable directly; "
          "recording or establishing one happens only when a concrete task needs it. A source "
          "registered now becomes usable in a new session, not the running one.")
    return 0


# ----------------------------------------------------------------------------
# Hooks (consolidated from the former hooks/ folder). Claude Code triggers each
# hook by invoking `python3 zanmai.py hook <name>` with the tool payload as
# stdin JSON. Each subcommand mirrors the behaviour of the previous standalone
# hook script.
# ----------------------------------------------------------------------------

_HOOK_ENFORCED_KIND_PREFIXES = (
    "inbox/focus/",
    "inbox/habits/",
    "inbox/knowledge/",
    "inbox/contacts/people/",
    "inbox/contacts/organizations/",
)
_HOOK_INDEX_PREFIXES = (
    "inbox/focus/",
    "inbox/habits/",
    "inbox/knowledge/",
)
_HOOK_EXEMPT_NAMES = ("INDEX.md", ".keep")
_HOOK_EXEMPT_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ics", ".webp")
_HOOK_NEVER_TARGETS = (
    "/.zanmai/system/",
    "/.zanmai/snapshots/",
    "/.zanmai/user.md",
    "/archive/",
    "/trash/",
)
_HOOK_NO_AI_CHECKBOX_PROTECTED = (
    re.compile(r"/.zanmai/memory/general\.md$"),
    re.compile(r"/.zanmai/memory/agents/[^/]+/lessons\.md$"),
    re.compile(r"/.zanmai/logs/.+\.md$"),
)
_HOOK_NO_AI_CHECKBOX_EXEMPT = (
    re.compile(r"/.zanmai/memory/briefing\.md$"),
)
_HOOK_CHECKBOX_LINE_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s+", re.MULTILINE)
_HOOK_ZEN_OPEN_PLAIN_RE = re.compile(
    r'(?:^|[;&|]\s*|\s&&\s|\s\|\|\s)\s*open\s+(?!-a\b)',
    re.MULTILINE,
)
_HOOK_ZEN_OPEN_MD_RE = re.compile(
    r'\.(md|markdown|canvas)(?=\s|$|"|\'|;|&|\|)',
    re.IGNORECASE,
)
_HOOK_ALLOWED_KINDS = {"focus", "habit", "knowledge", "contact/person", "contact/organization"}

# Triggers that flag a user prompt as a bulk-filing request. Language-neutral
# roots only; the `import` root and the literal `_import/` path mention catch
# the relevant German and English forms in practice (`import`, `imports`,
# `importing`, `importiere`, `importieren`, `importiert`). Language-specific
# triggers (other languages' verbs for "file", "take over", etc.) can be added
# via a future per-language config in `.zanmai/extensions/`; we do not bake
# non-English vocabulary into the distribution.
_HOOK_DISPATCH_TRIGGER_RE = re.compile(
    r"\b(import\w*|bulk[- ]?(?:import|file|filing))\b|_import/",
    re.IGNORECASE,
)

# Internal paths / filenames that must not appear in user-facing chat
# (operating-principles §7). Two rules cover everything:
#   1. Anything starting with a leading dot (hidden by convention), dotfiles
#      and dotfolders are internals: `.zanmai/...`, `.zennotes/...`,
#      `.last-session-end`, `.claude/...`, etc.
#   2. Any `.py` filename, script files are mechanic; the user never has to
#      type one.
# User-visible folders (`inbox/`, `_import/`, `assets/`, `quick/`, `archive/`,
# `trash/`) are not in the ban, they are the user's own workspace and naming
# them back to the user is fine.
_HOOK_PATH_LEAK_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])\.[A-Za-z][A-Za-z0-9_-]*(?:/[A-Za-z0-9_./-]*)?"),
    re.compile(r"\b[A-Za-z0-9_-]+\.py\b"),
)


def _hook_read_payload() -> dict:
    """Read the tool-call payload Claude Code passes on stdin. Returns empty
    dict on parse error so the hook never blocks because of a malformed pipe."""
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        return {}


def _hook_relative_under_prefix(path: str, prefixes: tuple[str, ...]) -> tuple[str, str] | None:
    norm = path.replace("\\", "/")
    for prefix in prefixes:
        idx = norm.find(prefix)
        if idx != -1:
            return norm[idx:], prefix
    return None


def _hook_extract_frontmatter(content: str) -> dict | None:
    """Tiny YAML frontmatter parser, flat string values only. Returns None
    when no `---`-fenced block is found."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 4)
    if end == -1:
        return None
    block = content[3:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip().strip('"').strip("'")
            result[key] = value
    return result


def cmd_hook_kind_required(args: argparse.Namespace) -> int:
    """PreToolUse Write|Edit hook: refuse writes under `inbox/<kind>/` whose
    markdown lacks valid `kind` and `slug` frontmatter. Database folders
    (`<Name>.base/`) are exempt, record pages there are database-synced."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") not in ("Write", "Edit"):
        return 0
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path.endswith(".md"):
        return 0
    name = Path(file_path).name
    if name in _HOOK_EXEMPT_NAMES or any(name.endswith(s) for s in _HOOK_EXEMPT_SUFFIXES):
        return 0
    located = _hook_relative_under_prefix(file_path, _HOOK_ENFORCED_KIND_PREFIXES)
    if located is None:
        return 0
    rel, _ = located
    norm = file_path.replace("\\", "/")
    for segment in norm.split("/"):
        if segment.endswith(".base") and len(segment) > len(".base"):
            return 0
    if payload.get("tool_name") == "Write":
        content = tool_input.get("content", "")
    else:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            content = tool_input.get("new_string", "")
        else:
            try:
                existing = file_path_obj.read_text(encoding="utf-8")
            except OSError:
                return 0
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
            if old_string and old_string in existing:
                content = existing.replace(old_string, new_string, 1)
            else:
                return 0
    fm = _hook_extract_frontmatter(content)
    if fm is None:
        print(f"kind-required: refusing {payload.get('tool_name')} on {rel}, file under inbox/ requires YAML frontmatter starting with ---", file=sys.stderr)
        return 2
    kind = fm.get("kind", "")
    if kind not in _HOOK_ALLOWED_KINDS:
        print(f"kind-required: refusing {payload.get('tool_name')} on {rel}, frontmatter 'kind' missing or invalid (got {kind!r}, expected one of {sorted(_HOOK_ALLOWED_KINDS)})", file=sys.stderr)
        return 2
    if not fm.get("slug"):
        print(f"kind-required: refusing {payload.get('tool_name')} on {rel}, frontmatter 'slug' required", file=sys.stderr)
        return 2
    return 0


def cmd_hook_permission_guard(args: argparse.Namespace) -> int:
    """PreToolUse Write|Edit hook: hard-block writes into the never-do bucket
    (.zanmai/system/, .zanmai/snapshots/, .zanmai/user.md, archive/,
    trash/)."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") not in ("Write", "Edit"):
        return 0
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0
    norm = file_path.replace("\\", "/")
    for target in _HOOK_NEVER_TARGETS:
        if target in norm:
            advice = {
                "/.zanmai/system/": "Distribution files live here; changes get overwritten on update. Use .zanmai/extensions/ for user-side additions.",
                "/.zanmai/snapshots/": "Only `zanmai.py snapshot create` writes here. Run the snapshot skill instead of writing directly.",
                "/.zanmai/user.md": "Only `zanmai.py setup init` writes the owner file. To change personalisation, edit manually outside this tool or re-run the setup workflow.",
                "/archive/": "Archive is ZenNotes-managed. Use `zn archive <path>` from the source location.",
                "/trash/": "Trash is ZenNotes-managed. Use `zn trash <path>` from the source location.",
            }.get(target, "")
            print(f"permission-guard: refusing {payload.get('tool_name')} on '{file_path}'. This path is in the never-do bucket. {advice}", file=sys.stderr)
            return 2
    return 0


def cmd_hook_dispatch_guard(args: argparse.Namespace) -> int:
    """PreToolUse Agent hook: refuse a main-thread expert dispatch that asks to
    run synchronously. An expert's job runs for minutes and
    `run_in_background: false` holds the whole turn, so the user sits in front of
    a concierge who cannot answer until the expert is done. The prose rule lives
    in Steve's Routing section; this is the mechanic behind it (operating
    principles section 4).

    The check is on the parameter, not on who is being addressed. Scoping it to
    the vault's own experts left the identical outage one agent name away: a
    generic helper agent blocks the loop exactly as long as a named expert does.

    A nested dispatch is exempt. The payload carries `agent_id` only when the
    hook fires inside a subagent, and an expert that pulls in another expert does
    need that result inside its own turn: a background child only reports back
    while the parent's turn is still open."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name") != "Agent":
        return 0
    if payload.get("agent_id"):
        return 0
    tool_input = payload.get("tool_input") or {}
    if tool_input.get("run_in_background") is not False:
        return 0
    subagent = str(tool_input.get("subagent_type") or "agent")
    print(
        f"dispatch-guard: refusing this {subagent} dispatch because it sets "
        "run_in_background: false, which holds this turn until the job returns, so "
        "nothing the user writes meanwhile reaches you. Call the Agent tool again "
        "with run_in_background: true, say in one line what is running, and relay "
        "the return when the notification lands.",
        file=sys.stderr,
    )
    return 2


def _hook_extract_text_from_content(content) -> str:
    """Concatenate the text of an assistant message `content`, which is either a
    plain string or a list of blocks. Only `type: text` blocks contribute."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text") or ""
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _hook_extract_assistant_text(message) -> str:
    """Text of the assistant message the Stop event passes inline on stdin as
    `last_assistant_message` (a dict with `role` and `content`)."""
    if not isinstance(message, dict):
        return ""
    return _hook_extract_text_from_content(message.get("content"))


def _hook_read_last_assistant_text(transcript_path: Path) -> str:
    """Fallback for when the Stop payload carries no inline message: read the
    JSONL transcript and return the text of the most recent assistant entry.
    Tolerates the shapes Claude Code has shipped, both the nested
    `{type: assistant, message: {content: [...]}}` and a flat
    `{type/role: assistant, content: [...]}`. Empty string when nothing is
    found or the file is unreadable."""
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        nested = entry.get("message")
        msg = nested if isinstance(nested, dict) else entry
        role = msg.get("role") or entry.get("type")
        if role != "assistant":
            continue
        return _hook_extract_text_from_content(msg.get("content"))
    return ""


def cmd_hook_voice_check(args: argparse.Namespace) -> int:
    """Stop hook: the runtime voice guard. Reads the assistant's final reply and
    blocks the turn when it carries an em-dash (U+2014), a banned AI tell in
    user-facing output (operating-principles section 7), so it is rewritten
    without it. style-check.py protects the distribution source at build time;
    this protects the live reply. Deterministic like style-check: only the
    em-dash, no soft heuristics that would misfire. The block recurs only while
    the em-dash is still there and Claude Code caps consecutive blocks, so it is
    self-limiting. Prefers the inline last_assistant_message the Stop event
    passes on stdin, and falls back to the transcript file."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    text = _hook_extract_assistant_text(payload.get("last_assistant_message"))
    if not text:
        transcript = payload.get("transcript_path", "")
        if transcript:
            text = _hook_read_last_assistant_text(Path(transcript))
    if "\u2014" in text:
        print(
            "voice-check: this reply contains an em-dash (\u2014), which is banned in "
            "user-facing output (operating-principles section 7). Rewrite it without "
            "the em-dash, use a full stop, a comma, or restructure the sentence, then send again.",
            file=sys.stderr,
        )
        return 2
    return 0


def cmd_hook_voice_check_tool(args: argparse.Namespace) -> int:
    """PreToolUse hook on AskUserQuestion: the runtime voice guard for menus.
    A menu's text rides inside the tool call, not in the chat reply, so the Stop
    hook cannot see it; this scans the AskUserQuestion input for an em-dash and
    refuses the call so the menu is rebuilt without it. Same banned tell, same
    determinism, the second user-facing surface."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name") != "AskUserQuestion":
        return 0
    em = chr(0x2014)
    blob = json.dumps(payload.get("tool_input", {}), ensure_ascii=False)
    if em in blob:
        print(
            "voice-check: this menu contains an em-dash (" + em + "), which is banned in "
            "user-facing output (operating-principles section 7). Rebuild the question, "
            "options and descriptions without it, then call the tool again.",
            file=sys.stderr,
        )
        return 2
    return 0


# Session-start hook helpers (consolidated from former session-start.py).

_SESSION_DAILY_WINDOW_DAYS = 7
_SESSION_WEEKLY_WINDOW_DAYS = 28
_SESSION_MONTHLY_WINDOW_DAYS = 92


def _session_find_vault_root() -> Path | None:
    """Walk upward from cwd to find a folder that has .zanmai/user.md."""
    cwd = Path.cwd().resolve()
    for path in [cwd] + list(cwd.parents):
        if (path / ".zanmai" / "user.md").exists():
            return path
    return None


def _session_parse_frontmatter(text: str) -> dict[str, str]:
    """Tiny YAML frontmatter parser, flat string values only. Empty dict when
    no `---`-fenced block is found. Shares one implementation with
    `_hook_extract_frontmatter`."""
    return _hook_extract_frontmatter(text) or {}


def _session_read_marker(vault: Path) -> datetime:
    """Read .last-session-end. Fall back to three days ago."""
    marker = vault / ".zanmai" / "memory" / ".last-session-end"
    if marker.exists():
        text = marker.read_text(encoding="utf-8").strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(days=3)


def _session_load_index(vault: Path) -> dict | None:
    idx_path = vault / ".zanmai" / "memory" / "vault-index.json"
    if not idx_path.exists():
        return None
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _session_resolve_notes_layout(vault_json: dict) -> dict:
    """Extract the Daily/Weekly/Monthly layout from vault.json. Without
    vault.json (or with missing/invalid fields), ZenNotes is not configured for
    this vault and these notes do not exist, the result marks them disabled
    with empty paths. There are no fallback defaults; vault.json is the only
    authority."""
    if not vault_json:
        return {
            "configured": False,
            "primary_location": None,
            "daily_enabled": False,
            "weekly_enabled": False,
            "monthly_enabled": False,
            "daily_dir": "",
            "weekly_dir": "",
            "monthly_dir": "",
            "daily_path": "",
            "weekly_path": "",
            "monthly_path": "",
            "daily_title_pattern": "",
            "weekly_title_pattern": "",
            "monthly_title_pattern": "",
        }
    primary = vault_json.get("primaryNotesLocation")
    if primary not in ("root", "inbox"):
        primary = None
    daily = vault_json.get("dailyNotes") or {}
    weekly = vault_json.get("weeklyNotes") or {}
    monthly = vault_json.get("monthlyNotes") or {}
    daily_enabled = bool(daily.get("enabled")) and primary is not None
    weekly_enabled = bool(weekly.get("enabled")) and primary is not None
    monthly_enabled = bool(monthly.get("enabled")) and primary is not None
    daily_dir = daily.get("directory", "") if daily_enabled else ""
    weekly_dir = weekly.get("directory", "") if weekly_enabled else ""
    monthly_dir = monthly.get("directory", "") if monthly_enabled else ""

    def _make_path(directory: str) -> str:
        if not directory or primary is None:
            return ""
        return directory if primary == "root" else f"inbox/{directory}"

    return {
        "configured": primary is not None,
        "primary_location": primary,
        "daily_enabled": daily_enabled,
        "weekly_enabled": weekly_enabled,
        "monthly_enabled": monthly_enabled,
        "daily_dir": daily_dir,
        "weekly_dir": weekly_dir,
        "monthly_dir": monthly_dir,
        "daily_path": _make_path(daily_dir),
        "weekly_path": _make_path(weekly_dir),
        "monthly_path": _make_path(monthly_dir),
        "daily_title_pattern": daily.get("titlePattern", "") if daily_enabled else "",
        "weekly_title_pattern": weekly.get("titlePattern", "") if weekly_enabled else "",
        "monthly_title_pattern": monthly.get("titlePattern", "") if monthly_enabled else "",
    }


def _session_write_vault_config_md(vault: Path, layout: dict, zennotes_installed: bool) -> None:
    """Write `.zanmai/vault-config.md` in AI-readable prose. Overwritten every
    session-start so changes to ZenNotes settings propagate on the next session."""
    cfg_path = vault / ".zanmai" / "vault-config.md"
    lines: list[str] = []
    lines.append("# Vault configuration")
    lines.append("")
    lines.append("Auto-generated by `zanmai.py hook session-start` on every session start. Reflects the live `.zennotes/vault.json` state. Do not edit by hand, changes are overwritten next session.")
    lines.append("")
    if not layout["configured"]:
        lines.append("ZenNotes is not configured for this vault. Daily, Weekly and Monthly Notes do not exist here. Steve and Hank read, propose and edit nothing in those folders.")
        lines.append("")
    else:
        lines.append("## Notes location")
        lines.append("")
        if layout["primary_location"] == "root":
            lines.append("New captures land at the vault root (`primaryNotesLocation: root`). Daily, Weekly and Monthly Notes folders sit directly under the vault root, not inside `inbox/`.")
        else:
            lines.append("New captures land in `inbox/` (`primaryNotesLocation: inbox`). Daily, Weekly and Monthly Notes folders sit under `inbox/`.")
        lines.append("")
        lines.append("## Daily Notes")
        lines.append("")
        if layout["daily_enabled"]:
            lines.append(f"Enabled. Folder: `{layout['daily_path']}/`. Filename pattern: `{layout['daily_title_pattern']}`.")
        else:
            lines.append("Disabled. Steve and Hank read, propose and edit nothing in the Daily Notes folder.")
        lines.append("")
        lines.append("## Weekly Notes")
        lines.append("")
        if layout["weekly_enabled"]:
            lines.append(f"Enabled. Folder: `{layout['weekly_path']}/`. Filename pattern: `{layout['weekly_title_pattern']}`.")
        else:
            lines.append("Disabled. Steve and Hank read, propose and edit nothing in the Weekly Notes folder.")
        lines.append("")
        lines.append("## Monthly Notes")
        lines.append("")
        if layout["monthly_enabled"]:
            lines.append(f"Enabled. Folder: `{layout['monthly_path']}/`. Filename pattern: `{layout['monthly_title_pattern']}`.")
        else:
            lines.append("Disabled. Steve and Hank read, propose and edit nothing in the Monthly Notes folder.")
        lines.append("")
    try:
        cfg_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass


def _session_parse_entry_timestamp(entry: dict) -> datetime | None:
    for field in ("updated", "created"):
        v = entry.get(field)
        if not v:
            continue
        try:
            if "T" in str(v):
                return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return datetime.strptime(str(v), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _session_collect_recent_daily_weekly(index: dict, vault: Path, layout: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    daily_cutoff = now - timedelta(days=_SESSION_DAILY_WINDOW_DAYS)
    weekly_cutoff = now - timedelta(days=_SESSION_WEEKLY_WINDOW_DAYS)
    monthly_cutoff = now - timedelta(days=_SESSION_MONTHLY_WINDOW_DAYS)
    daily_prefix = (layout["daily_path"] + "/") if layout["daily_path"] else None
    weekly_prefix = (layout["weekly_path"] + "/") if layout["weekly_path"] else None
    monthly_prefix = (layout["monthly_path"] + "/") if layout["monthly_path"] else None
    if daily_prefix is None and weekly_prefix is None and monthly_prefix is None:
        return []
    files = index.get("files", [])
    matches: list[dict] = []
    for entry in files:
        path = entry.get("path", "")
        if daily_prefix is not None and path.startswith(daily_prefix):
            cutoff = daily_cutoff
        elif weekly_prefix is not None and path.startswith(weekly_prefix):
            cutoff = weekly_cutoff
        elif monthly_prefix is not None and path.startswith(monthly_prefix):
            cutoff = monthly_cutoff
        else:
            continue
        ts = _session_parse_entry_timestamp(entry)
        if ts is None:
            abs_path = vault / path
            if not abs_path.exists():
                continue
            ts = datetime.fromtimestamp(abs_path.stat().st_mtime, timezone.utc)
        if ts >= cutoff:
            matches.append({**entry, "_ts": ts.isoformat(timespec="minutes")})
    matches.sort(key=lambda e: e.get("_ts", ""))
    return matches


def _session_aggregate_tokens(notes: list[dict], vault: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in notes:
        seen_in_this_note: set[str] = set()
        for source in ("filename_tokens", "h1_tokens", "body_tokens", "tags"):
            for t in n.get(source, []) or []:
                key = str(t).lower()
                if len(key) < 3:
                    continue
                seen_in_this_note.add(key)
        for key in seen_in_this_note:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _session_existing_bundle_slugs(vault: Path) -> set[str]:
    bundles: set[str] = set()
    for kind in ("focus", "habits", "knowledge"):
        kind_dir = vault / "inbox" / kind
        if not kind_dir.is_dir():
            continue
        for p in kind_dir.iterdir():
            if p.is_dir():
                bundles.add(p.name)
    return bundles


def _session_suggest_themes(token_counts: dict[str, int], bundles: set[str], top_n: int = 3) -> list[tuple[str, int]]:
    candidates: dict[str, int] = {}
    for slug in bundles:
        norm = slug.lower().replace("-", "")
        best = 0
        for token, count in token_counts.items():
            if count < 2:
                continue
            tnorm = token.replace("-", "")
            if tnorm == norm:
                best = max(best, count)
            elif len(tnorm) >= 3 and (tnorm in norm or norm in tnorm):
                best = max(best, count)
        if best > 0:
            candidates[slug] = best
    ranked = sorted(candidates.items(), key=lambda t: (-t[1], t[0]))
    return ranked[:top_n]


def _session_known_entities(vault: Path) -> dict[str, str]:
    """Map slug -> human label for contacts and top-level bundles, the entities
    a journal entry might mention by name."""
    ents: dict[str, str] = {}
    for sub in ("people", "organizations"):
        d = vault / "inbox" / "contacts" / sub
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file() and f.suffix == ".md":
                    ents[f.stem] = _human_label_for_slug(f.stem)
    for kind in ("focus", "habits", "knowledge"):
        d = vault / "inbox" / kind
        if d.is_dir():
            for b in d.iterdir():
                if b.is_dir():
                    ents[b.name] = _human_label_for_slug(b.name)
    return ents


def _session_journal_link_candidates(notes: list[dict], vault: Path, layout: dict, top_n: int = 5) -> list[dict]:
    """Known entities mentioned in recent periodic notes as plain text but not
    yet wikilinked there, ranked by recurrence (how many recent notes mention
    each unlinked). Conservative link proposals, capture becoming connected over
    time, without auto-linking. Reads the recent note bodies directly, so it does
    not depend on index freshness."""
    prefixes = tuple(
        f"{p}/" for p in (layout.get("daily_path"), layout.get("weekly_path"), layout.get("monthly_path")) if p
    )
    if not prefixes:
        return []
    ents = _session_known_entities(vault)
    matchers = {
        slug: re.compile(r"\b" + re.escape(label) + r"\b", re.IGNORECASE)
        for slug, label in ents.items()
        if len(label) >= 3
    }
    if not matchers:
        return []
    hits: dict[str, dict] = {}
    for n in notes:
        path = n.get("path", "")
        if not path.startswith(prefixes):
            continue
        try:
            body = (vault / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for slug, rx in matchers.items():
            if not rx.search(body):
                continue
            if f"[[{slug}" in body or f"[[{ents[slug]}" in body:
                continue  # already linked in this note
            h = hits.setdefault(slug, {"slug": slug, "label": ents[slug], "count": 0, "paths": []})
            h["count"] += 1
            if len(h["paths"]) < 3:
                h["paths"].append(path)
    return sorted(hits.values(), key=lambda x: (-x["count"], x["slug"]))[:top_n]


def _session_index_stale(vault: Path, index: dict | None) -> bool:
    """True when the vault's markdown no longer matches the index, a file was
    added, removed, or changed since the last rebuild. Compares path + mtime, so
    it catches edits the user made directly in ZenNotes, which set no marker. An
    index built before the per-file `mtime` field counts as stale once."""
    if not index:
        return True
    current: dict[str, int] = {}
    for f in _walk_vault_markdown(vault):
        try:
            current[f.relative_to(vault).as_posix()] = int(f.stat().st_mtime)
        except (OSError, ValueError):
            continue
    indexed: dict[str, int] = {}
    for e in index.get("files", []):
        p = e.get("path")
        if p is None:
            continue
        if "mtime" not in e:
            return True  # pre-mtime index, force one refresh
        indexed[p] = int(e.get("mtime") or 0)
    return current != indexed


def _session_refresh_index(vault: Path) -> None:
    """Rebuild the vault index and patterns in place. Called at session start when
    the index is stale, so every session opens on a current index without waiting
    for the first query. Sub-second on thousands of files; stdout is captured and
    failures swallowed so a refresh problem never pollutes or blocks the greet."""
    import io, contextlib
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_reindex(argparse.Namespace(vault=str(vault), scope=None, quiet=True))
            cmd_patterns(argparse.Namespace(vault=str(vault), min_count=2))
    except Exception:
        pass


def cmd_hook_session_start(args: argparse.Namespace) -> int:
    """SessionStart hook. The init point for every Zanmai session: reads
    all static state (`.zanmai/user.md`, `.zennotes/vault.json`, last-session-end
    marker, index entries), writes the current vault layout to
    `.zanmai/vault-config.md` for the AI to read, and prints a compact briefing
    that Claude Code injects into the session context as a system-reminder."""
    vault = _session_find_vault_root()
    if vault is None:
        import os
        env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        if env_dir:
            candidate = Path(env_dir)
            if (candidate / ".zanmai" / "user.md").exists():
                vault = candidate
    if vault is None:
        try:
            payload = json.loads(sys.stdin.read())
            cwd_hint = payload.get("cwd") or payload.get("project_dir")
            if cwd_hint and (Path(cwd_hint) / ".zanmai" / "user.md").exists():
                vault = Path(cwd_hint)
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    if vault is None:
        # No initialised vault found by the user.md marker. Detect an
        # uninitialised Zanmai vault (system tree present, user.md absent) and
        # drive setup with a hard directive, so a fresh session cannot slide into
        # a generic greeting instead of running setup.
        import os
        for cand in (Path.cwd(), Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".")):
            try:
                is_zb = (cand / ".zanmai" / "system" / "manifest.yaml").exists()
                fresh = not (cand / ".zanmai" / "user.md").exists()
            except OSError:
                continue
            if is_zb and fresh:
                print(
                    "Zanmai: this vault is not set up yet, there is no user profile. "
                    "Before any greeting or answer, read .zanmai/system/skills/setup/SKILL.md "
                    "and run its workflow now. Do not respond generically."
                )
                return 0
        return 0

    user_md = vault / ".zanmai" / "user.md"
    try:
        user_text = user_md.read_text(encoding="utf-8")
    except OSError:
        print("Zanmai session-start: .zanmai/user.md unreadable. Run `setup` skill if vault is fresh.")
        return 0

    # Prune the transient workspace so it never becomes a data graveyard, but
    # keep recent scratch so unfinished cross-session work is not lost ("done for
    # today, resume tomorrow"). Only entries untouched for over 7 days are removed;
    # anything modified within the window stays. Deliverables live in _export/.
    #
    # A workshop that declares itself open is never pruned, whatever its age. Age is
    # a guess about whether something still matters; `state: open` in the workshop's
    # own status file is a statement. An expert parked on a decision the user has not
    # taken yet can sit for weeks, and deleting the one folder that holds where the
    # work stood is how a run loses what it cannot write down twice.
    import shutil
    import time
    work_dir = vault / ".zanmai" / "work"
    if work_dir.is_dir():
        cutoff = time.time() - 7 * 86400
        for child in work_dir.iterdir():
            if child.name == ".gitkeep":
                continue
            try:
                if child.is_dir() and _work_is_open(child):
                    continue
                newest = child.stat().st_mtime
                if child.is_dir():
                    for f in child.rglob("*"):
                        try:
                            newest = max(newest, f.stat().st_mtime)
                        except OSError:
                            pass
                if newest < cutoff:
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            except OSError:
                pass

    fm = _session_parse_frontmatter(user_text)
    preferred = fm.get("preferred_address") or fm.get("first_name") or "there"
    owner_contact = fm.get("owner_contact", "")
    language = fm.get("language", "auto")
    auto_snapshots = fm.get("auto_snapshots", "true").lower() == "true"
    zennotes_installed = fm.get("zennotes_installed", "false").lower() == "true"

    vault_json = _read_vault_json(vault) if zennotes_installed else {}
    layout = _session_resolve_notes_layout(vault_json)
    _session_write_vault_config_md(vault, layout, zennotes_installed)
    daily_notes_enabled = layout["daily_enabled"]
    weekly_notes_enabled = layout["weekly_enabled"]
    monthly_notes_enabled = layout["monthly_enabled"]

    marker = _session_read_marker(vault)
    marker_iso = marker.astimezone(timezone.utc).isoformat(timespec="minutes")

    lines: list[str] = []
    lines.append("Zanmai session briefing")
    lines.append(f"- Address the user as **{preferred}** (from preferred_address / first_name in .zanmai/user.md).")

    # New distribution files can arrive without the host-side refresh, for
    # example when the user pulls the repository by hand. The refresh is
    # mechanical, so run it instead of reporting drift.
    #
    # The wiring itself is checked every session, not only when the version moved,
    # and that is what rescues a vault whose marker already claims the current
    # version while the host config is incomplete. Any release before this one wrote
    # that marker on hope: for those vaults the versions agree, so a check that
    # triggers on disagreement never looks again. This one looks regardless.
    shipped_version = _distribution_version(vault)
    host_marker = vault / ".zanmai" / "runtime" / "host-config-version"
    known_version = host_marker.read_text(encoding="utf-8").strip() if host_marker.exists() else ""
    version_moved = bool(shipped_version) and shipped_version != known_version
    problems = _verify_host_config(vault)
    if version_moved or problems:
        _refresh_host_config(vault, quiet=True)
        remaining = _verify_host_config(vault)
        if remaining:
            lines.append("- This vault's host config is incomplete and a refresh did not fix it: "
                         + "; ".join(remaining)
                         + ". Say so plainly and offer to run `setup validate` for the detail. The "
                           "recorded version is left alone, so this is looked at again next session.")
        else:
            if shipped_version:
                _record_host_config_version(vault, shipped_version)
            if problems and not version_moved:
                lines.append(f"- Part of Zanmai was on disk but not wired up ({len(problems)} item(s)), "
                             "and has now been wired. Mention it once, in one sentence, and carry on.")
            elif known_version and version_moved:
                lines.append(f"- Zanmai moved from {known_version} to {shipped_version}. Host config refreshed; "
                             "mention the new version once and point at the changelog if the user asks what changed.")

    # Recordings waiting are named, not transcribed. A hook that takes a minute is a
    # session that starts in a minute, and the reading of them is a background job.
    waiting = _pending_recordings(vault)
    if waiting:
        total = sum(_audio_duration(f) or 0.0 for f in waiting)
        lines.append(
            f"- {len(waiting)} voice note(s) waiting in _import/recordings/"
            + (f", {_spoken_length(total)} in total" if total else "")
            + ". Dispatch the `voice` skill in the background on the next turn and carry on; "
              "report when it is done, and only ask about what it could not settle."
        )

    # Work the user has not answered yet. Named in one line, because this is the one
    # class of open item the next session cannot work out for itself.
    try:
        rows, _headers = _work_read(vault)
    except Exception:
        rows = []
    # A session that ran with nobody in the chat is only useful if the next one says so.
    unattended = _unattended_log_to_report(vault)
    if unattended:
        lines.append(f"- The last session ran without the user: `{unattended.relative_to(vault)}`. "
                     "Open the greeting with one line from that log and the work objects, what was "
                     "handled and what it left open, then carry on as usual.")

    pending = [r for r in rows if str(r.get("state", "")).lower() == "waiting on you"]
    if pending:
        lines.append(f"- {len(pending)} piece(s) of work waiting on the user: "
                     + "; ".join(f"{r.get('work', '')[:60]} ({r.get('id', '')[:8]})"
                                 for r in pending[:3])
                     + ". Name them once, do not re-explain the whole piece.")

    # Named once a day, not once per hook run. This hook fires again on every resume and
    # every compaction, and an offer repeated three times in an afternoon reads as nagging
    # about something the user already declined.
    newer = _quiet_update_probe(vault)
    if newer and _update_offer_due(vault):
        lines.append(f"- Version {newer} is available (this vault runs {shipped_version}). Offer the update once, "
                     "in one plain line, at a moment that does not interrupt the user's task, and drop it for this "
                     "session if declined. On a yes, dispatch Pepper's update workflow.")
    if owner_contact:
        lines.append(f"- Owner contact: `inbox/contacts/people/{owner_contact}.md` (read for persistent user notes).")
    lines.append(f"- Language preference: {language}.")
    lines.append(f"- Last session ended: {marker_iso}.")
    lines.append(f"- auto_snapshots: {str(auto_snapshots).lower()}. When true and `.zanmai/snapshots/` has no today-dated folder, take a session-start snapshot SILENTLY (no chat line, no topic-list entry, no user question, infrastructure, not user-facing). When false, skip every automatic snapshot, the user has their own backup approach.")
    lines.append(f"- Vault layout: see `.zanmai/vault-config.md` for the current Daily/Weekly/Monthly Notes folder paths, primary notes location and enabled flags. The file is regenerated by this hook every session so any change in ZenNotes settings propagates on the next start.")
    lines.append(f"- daily_notes_enabled: {str(daily_notes_enabled).lower()}. When false, no read or edit of Daily Notes. Mention once per session at most if the user asks for today's view.")
    lines.append(f"- weekly_notes_enabled: {str(weekly_notes_enabled).lower()} (same honour rule as Daily).")
    lines.append(f"- monthly_notes_enabled: {str(monthly_notes_enabled).lower()} (same honour rule as Daily).")
    lines.append("- Daily, Weekly and Monthly Notes operations go through the `notes` skill (`.zanmai/system/skills/notes/SKILL.md`). The AI never writes into them on its own initiative, only on direct user instruction.")

    index = _session_load_index(vault)
    stale_marker = vault / ".zanmai" / "memory" / ".index-stale"
    if stale_marker.exists() or _session_index_stale(vault, index):
        _session_refresh_index(vault)
        index = _session_load_index(vault)
    if index is None:
        lines.append("- Pattern index not built yet. Run `zanmai.py index rebuild` plus `zanmai.py index patterns` before theme queries.")
    else:
        notes = _session_collect_recent_daily_weekly(index, vault, layout)
        window_desc = f"last {_SESSION_DAILY_WINDOW_DAYS} days Daily, last {_SESSION_WEEKLY_WINDOW_DAYS // 7} weeks Weekly, last {_SESSION_MONTHLY_WINDOW_DAYS // 30} months Monthly"
        if not notes:
            lines.append(f"- No Daily, Weekly or Monthly notes in the recent window ({window_desc}). Topic suggestions for the greet come from active focus bundles, recent operations and open items already synthesised in `.zanmai/memory/briefing.md`. Render the greet as the numbered-topic-choice format from steve.md Regular Session (3-5 numbered topics with short hints, not prose, not bullets), even when only a few focus bundles are active, open items per bundle and recent operations supply the extra topics.")
        else:
            daily_prefix = (layout["daily_path"] + "/") if layout["daily_path"] else None
            weekly_prefix = (layout["weekly_path"] + "/") if layout["weekly_path"] else None
            monthly_prefix = (layout["monthly_path"] + "/") if layout["monthly_path"] else None
            daily = [n for n in notes if daily_prefix and n["path"].startswith(daily_prefix)]
            weekly = [n for n in notes if weekly_prefix and n["path"].startswith(weekly_prefix)]
            monthly = [n for n in notes if monthly_prefix and n["path"].startswith(monthly_prefix)]
            lines.append(f"- Recent window ({window_desc}): {len(daily)} Daily, {len(weekly)} Weekly, {len(monthly)} Monthly note(s).")
            for n in notes[-5:]:
                lines.append(f"  * {n['path']}")
            candidates = _session_journal_link_candidates(notes, vault, layout)
            if candidates:
                pretty = ", ".join(f"[[{c['slug']}]] ({c['count']}x)" for c in candidates)
                lines.append(
                    f"- Journal link candidates (recent notes name these existing entities unlinked, ranked by recurrence): {pretty}. "
                    f"Offer to add the wikilinks, propose, do not auto-link. The more a name recurs across recent notes, the stronger the signal it belongs connected. This is how capture becomes connected over time."
                )
            counts = _session_aggregate_tokens(notes, vault)
            bundles = _session_existing_bundle_slugs(vault)
            suggestions = _session_suggest_themes(counts, bundles, top_n=3)
            if suggestions:
                pretty_pairs = ", ".join(
                    f"{_human_label_for_slug(slug)} ({count}/{len(notes)})"
                    for slug, count in suggestions
                )
                lines.append(
                    f"- Theme signal (distinct-note count of {len(notes)} new notes): {pretty_pairs}. "
                    f"Bundles for these already exist under `inbox/<kind>/<slug>/`."
                )
                lines.append(
                    "- When you open the conversation: address the user by the human label "
                    "of the bundle (the readable name with spaces and capitalisation), NOT "
                    "by the kebab-case slug. Slugs are internal pathnames."
                )
                lines.append(
                    "- The proposal you make must be concrete: name the file you would write, "
                    "the location, and the rough content. Avoid fuzzy standalone verbs that do "
                    "not commit to a deliverable."
                )

    stale = vault / ".zanmai" / "memory" / ".index-stale"
    if stale.exists():
        lines.append("- `.zanmai/memory/.index-stale` marker is set. Refresh `zanmai.py index rebuild` + `zanmai.py index patterns` before any theme query.")

    # Environment recheck: compare stored flags against live state. If anything
    # changed since setup, surface a one-liner so Steve can ask the user once
    # whether to switch the integration. Generic, applies to any env signal
    # we track (ZenNotes vault state, zn CLI), not per-case.
    import shutil
    stored_zennotes = fm.get("zennotes_installed", "false").lower() == "true"
    stored_zen_cli = fm.get("zen_cli_installed", "false").lower() == "true"
    live_zennotes = (vault / ".zennotes").is_dir()
    live_zen_cli = _zen_cli_usable(vault)
    env_changes: list[str] = []
    if live_zennotes != stored_zennotes:
        new_state = "now active (the `.zennotes/` vault folder exists)" if live_zennotes else "no longer active (`.zennotes/` folder is gone)"
        env_changes.append(f"ZenNotes for this vault: {new_state}; stored `zennotes_installed` is `{'true' if stored_zennotes else 'false'}`. Ask the user once in their writing language whether to switch the integration, then update `.zanmai/user.md` accordingly.")
    if live_zen_cli != stored_zen_cli:
        new_state = "now usable for this vault" if live_zen_cli else "not usable for this vault (binary missing, or ZenNotes has not opened this vault)"
        env_changes.append(f"`zn` CLI: {new_state}; stored `zen_cli_installed` is `{'true' if stored_zen_cli else 'false'}`. Ask the user once whether to switch the integration, then update `.zanmai/user.md` accordingly.")
    if env_changes:
        lines.append("- Environment change detected since last setup (ask the user, do not flip flags silently):")
        for ch in env_changes:
            lines.append(f"  * {ch}")

    briefing_path = vault / ".zanmai" / "memory" / "briefing.md"
    if briefing_path.exists():
        try:
            briefing_text = briefing_path.read_text(encoding="utf-8")
        except OSError:
            briefing_text = ""
        if briefing_text.strip():
            lines.append("")
            lines.append("---")
            lines.append("Below is the pre-built briefing (already synthesised, enough to shape the greet with no extra reads). It does NOT replace the three CLAUDE.md session-start reads (`.zanmai/user.md`, the owner-contact body, `.last-session-end`), which run before the first reply whether the turn opens with a greet or a direct request:")
            lines.append("")
            lines.append(briefing_text)
    else:
        lines.append("- `.zanmai/memory/briefing.md` does not exist yet. Run `zanmai.py memory briefing` once to build the first version.")

    lines.append("")
    lines.append(
        "Greet only when the user opens with a bare greeting or empty turn. "
        "If the first message is a direct request (research question, filing task, edit, observation, naming question), "
        "skip the greet entirely and respond to that request directly, but run the three session-start reads first; skipping the greet is not skipping the reads. "
        "Then apply pre-dispatch for research, plan-before-write for filing. "
        "The greet exists to surface what is open when the user has not already said what they want. Once they have, it is filler."
    )
    lines.append("")
    lines.append(
        f"When a greet is appropriate, address the user as **{preferred}** (translate any user-facing wording to the user's writing language at runtime). "
        "The shape is a teaser plus a numbered menu, not a single full proposal. "
        "First line: a short greeting line carrying the address only. "
        "Then one short context line drawn from the briefing. "
        "Then three to five numbered options drawn from recent activity, open items and the current state, each one line. "
        "Recent-activity bundles (yesterday's research, today's import, a habit touched this morning) count as user attention and belong alongside open todos, not below them. "
        "Render bundle references as human labels (the readable name with spaces and capitalisation), not as kebab-case slugs. "
        "The wikilink may follow in parentheses if the user needs the click target. "
        "End with one short closing line in the user's writing language inviting the user to pick a number or describe what they have planned. "
        "Detailed proposals (output path plus content sketch) come after the user picks a number, not in the greet. "
        "Avoid menu-pressuring closers and warmth-only filler sentences with no information content."
    )
    lines.append("")
    lines.append(
        "Pre-dispatch is mandatory before any Reed dispatch, and Steve never runs Reed's pipeline tools directly. "
        "When the user asks for research, video, audio or repository extraction, comparisons, state-of-the-art, or any external-sourcing question (pattern-match intent, not literal strings), "
        "state the planned brief in one user-facing sentence in the user's writing language, ask for confirmation, wait, then dispatch Reed via the `Agent` tool with `subagent_type: reed`. "
        "Steve must not call WebFetch on external video, audio, podcast or repository URLs, must not invoke Bash with external-source fetchers, transcription or repo cloning, and must not preview or probe a source before dispatch. "
        "Running any of those in the main loop is Reed's work in Steve's identity. "
        "See CLAUDE.md Hard Rule 9 and the Steve contract sections on research dispatch and Directive 5 for the full procedure."
    )
    lines.append("")
    lines.append(
        "Verify before reporting status on a greet item. When the user picks a number from the greet or asks about the state of a topic, "
        "do not just expand the briefing line into a status report. Daily-note todos drift. "
        "A checkbox from two weeks ago is often already done and documented in the bundle, but the checkbox stayed unticked. "
        "Before the status reply: read the relevant bundle truth file (`inbox/<kind>/<bundle-slug>/<bundle-slug>.md`). "
        "If the bundle contradicts the todo (a ticked checkbox, a status field that says done, a confirmation number filled in), "
        "name the discrepancy explicitly in the reply and ask whether to tick the notes daily todo. "
        "One or two reads are cheap, much cheaper than producing a wrong briefing. "
        "See `.zanmai/system/experts/steve/steve.md` for the follow-up procedure."
    )

    print("\n".join(lines))
    return 0


def cmd_hook_index_consistency(args: argparse.Namespace) -> int:
    """PostToolUse Write|Edit hook: warn (exit 2 non-blocking stderr) when a
    bundle file is written without being referenced in the bundle's INDEX.md.
    Also touches `.zanmai/memory/.index-stale` to flag the pattern index for
    refresh."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") not in ("Write", "Edit"):
        return 0
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path.endswith(".md"):
        return 0
    name = Path(file_path).name
    if name in _HOOK_EXEMPT_NAMES or any(name.endswith(s) for s in _HOOK_EXEMPT_SUFFIXES):
        return 0
    located = _hook_relative_under_prefix(file_path, _HOOK_INDEX_PREFIXES)
    if located is None:
        return 0
    # Mark the pattern index stale.
    norm = file_path.replace("\\", "/")
    inbox_idx = norm.find("/inbox/")
    if inbox_idx != -1:
        try:
            (Path(norm[:inbox_idx]) / ".zanmai" / "memory" / ".index-stale").touch(exist_ok=True)
        except OSError:
            pass
    rel, _ = located
    parts = rel.split("/")
    if len(parts) < 4:
        return 0
    bundle_dir = Path(file_path).parent
    file_name = parts[-1]
    bundle_slug = parts[2]
    truth_file = f"{bundle_slug}.md"
    if file_name == truth_file:
        return 0
    index_path = bundle_dir / "INDEX.md"
    if not index_path.exists():
        print(f"index-consistency: bundle '{bundle_slug}' has no INDEX.md yet, consider creating one to keep the bundle scannable.", file=sys.stderr)
        return 2
    try:
        index_text = index_path.read_text(encoding="utf-8")
    except OSError:
        return 0
    slug_no_ext = file_name[:-3]
    patterns = (
        rf"\[\[{re.escape(slug_no_ext)}\]\]",
        rf"\[\[{re.escape(file_name)}\]\]",
        rf"\[[^\]]+\]\([^)]*{re.escape(file_name)}\)",
    )
    if any(re.search(p, index_text) for p in patterns):
        return 0
    print(f"index-consistency: '{file_name}' was written under {bundle_slug}/ but is not referenced in {bundle_slug}/INDEX.md. Append a wikilink to keep the bundle discoverable.", file=sys.stderr)
    return 2


# media marking (EU AI Act) ----
#
# Deterministic, never model-drawn. Heavy deps (Pillow, c2pa) are imported lazily
# inside the handlers so the core CLI runs without them; when they are missing the
# step degrades to a clear warning, never a silent skip.

_LABEL_FONT_FRAC = 0.0095     # label cap-height as a fraction of image height (minimal, discreet)
_LABEL_PAD_Y_FRAC = 0.005     # vertical padding inside the pill
_LABEL_PAD_X_FRAC = 0.009     # horizontal padding, the rounded ends eat into it
_LABEL_MARGIN_FRAC = 0.020
_LABEL_MIN_PX = 9
_SANS_FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _c2pa_manifest_state(path: Path) -> tuple[bool | None, str | None]:
    """(present, issuer). present=None means c2pa lib unavailable (unknown)."""
    try:
        import c2pa  # noqa: F401
    except ImportError:
        return (None, None)
    try:
        reader = c2pa.Reader(str(path))
        data = json.loads(reader.json())
        m = (data.get("manifests") or {}).get(data.get("active_manifest"), {})
        return (True, (m.get("signature_info") or {}).get("issuer"))
    except Exception:
        return (False, None)


def _burn_visible_label(src: Path, text: str, font_path: str | None, out: Path) -> str:
    """Bottom-right rounded pill with light text, sized small. Returns font name."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(src).convert("RGB")
    w, h = img.size
    font_px = max(_LABEL_MIN_PX, round(h * _LABEL_FONT_FRAC))
    pad_y = round(h * _LABEL_PAD_Y_FRAC)
    pad_x = round(h * _LABEL_PAD_X_FRAC)
    margin = round(h * _LABEL_MARGIN_FRAC)
    font = None
    font_name = ""
    for p in ([font_path] if font_path else []) + list(_SANS_FONT_CANDIDATES):
        try:
            font = ImageFont.truetype(p, font_px)
            font_name = Path(p).name
            break
        except (OSError, ValueError):
            continue
    if font is None:
        font = ImageFont.load_default()
        font_name = "PIL-default(bitmap)"
    draw = ImageDraw.Draw(img, "RGBA")
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    pw, ph = tw + 2 * pad_x, th + 2 * pad_y
    x1, y1 = w - margin - pw, h - margin - ph
    draw.rounded_rectangle([x1, y1, x1 + pw, y1 + ph], radius=ph // 2, fill=(0, 0, 0, 125))
    draw.text((x1 + pad_x - l, y1 + pad_y - t), text, font=font, fill=(255, 255, 255, 235))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=95)
    return font_name


def _composite_eu_icon(src: Path, out: Path, ai_class: str, assets_dir: Path) -> dict:
    """Paste the official EU AI-content label icon bottom-right. Picks the black
    or white variant by the luminance of the corner it lands on and uses the
    transparent PNG. `ai_class` (generated|modified|base) is decided upstream in
    the flow; this only applies it."""
    from PIL import Image, ImageStat
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    region = img.crop((int(w * 0.6), int(h * 0.78), w, h)).convert("L")
    lum = ImageStat.Stat(region).mean[0]
    variant = "white" if lum < 128 else "black"
    # Full-opacity ink (the `black`/`white` files) for clear perceptibility; the
    # `-transparent` files are the subtler 50%-opacity treatment, not the default.
    icon_path = assets_dir / f"{ai_class}-{variant}.png"
    if not icon_path.is_file():
        return {"applied": False, "error": f"EU icon not found: {icon_path.name}"}
    icon = Image.open(icon_path).convert("RGBA")
    iw, ih = icon.size
    # As small as it can be, as large as it must be: the self-contained icon reads
    # well small, so scale to a modest share of the shorter side, with the legal
    # 24px floor (Code of Practice §2). Perceptible at first exposure, not dominant.
    short = min(w, h)
    target_h = max(24, round(short * 0.035))
    target_w = max(1, round(iw * (target_h / ih)))
    icon = icon.resize((target_w, target_h), Image.LANCZOS)
    margin = round(short * 0.025)
    img.alpha_composite(icon, (w - margin - target_w, h - margin - target_h))
    out.parent.mkdir(parents=True, exist_ok=True)
    final = img.convert("RGB") if out.suffix.lower() in (".jpg", ".jpeg") else img
    final.save(out)
    return {"applied": True, "eu_icon": ai_class, "variant": variant, "position": "bottom-right"}


_DST_TRAINED = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
_C2PA_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime"}


def _sign_c2pa(target: Path, cert: str, key: str, tsa: str,
               parent: Path | None = None) -> tuple[bool, str]:
    """Sign `target` in place with a self-managed cert chain (valid, not trust-listed).

    With `parent`, the pre-edit original that still carries its own manifest, record
    the edit and chain that original as a `parentOf` ingredient, so a platform credential
    (e.g. Google's) survives our pixel edit as documented provenance history instead of
    being silently discarded. Without `parent`, mark a fresh AI creation."""
    try:
        from c2pa import Builder, Signer, C2paSignerInfo
    except ImportError:
        return (False, "c2pa library not available in this runtime")
    try:
        if parent is not None:
            manifest = {"claim_generator": "Zanmai", "assertions": [
                {"label": "c2pa.actions.v2", "data": {"actions": [
                    {"action": "c2pa.opened"},
                    {"action": "c2pa.edited", "parameters": {"name": "visible AI label"}}]}}]}
        else:
            manifest = {"claim_generator": "Zanmai", "assertions": [
                {"label": "c2pa.actions.v2", "data": {"actions": [
                    {"action": "c2pa.created", "digitalSourceType": _DST_TRAINED}]}}]}
        signer = Signer.from_info(C2paSignerInfo(
            b"es256", Path(cert).read_bytes(), Path(key).read_bytes(), tsa.encode()))
        builder = Builder(json.dumps(manifest))
        if parent is not None:
            with open(parent, "rb") as ing:
                builder.add_ingredient_from_stream(
                    json.dumps({"title": "source render", "relationship": "parentOf"}),
                    _C2PA_MIME.get(parent.suffix.lower(), "application/octet-stream"), ing)
        tmp = target.with_name(target.name + ".c2pa.tmp")
        if tmp.exists():
            tmp.unlink()
        builder.sign_file(str(target), str(tmp), signer)
        tmp.replace(target)
        return (True, "self-managed C2PA applied (valid, not trust-listed)")
    except Exception as e:
        return (False, f"signing failed: {type(e).__name__}: {str(e)[:120]}")


def _signer_dir() -> Path:
    """Where the self-managed C2PA signing identity lives: outside the vault, in
    the user's config dir, never committed, never in the vault (LD6)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "zanmai" / "c2pa-signer"


def _signer_paths() -> tuple[Path, Path]:
    d = _signer_dir()
    return d / "cert.pem", d / "key.pem"


def _establish_signer(vault: Path | None) -> tuple[Path | None, Path | None, str]:
    """Create the self-managed signing identity if none exists, then return its
    paths. P-256, PKCS#8 key, cert with keyUsage=digitalSignature,
    EKU=emailProtection, CA:FALSE, and SubjectKeyIdentifier + AuthorityKeyIdentifier
    (c2pa rejects a signer cert lacking SKI/AKI, verified 2026-07-20). Valid, not
    trust-listed, that is the user's responsibility. Needs the `cryptography`
    library; provisions it into the runtime venv on first use if absent."""
    cert_p, key_p = _signer_paths()
    if cert_p.is_file() and key_p.is_file():
        return cert_p, key_p, "present"
    if vault is not None:
        _activate_runtime_venv_site(vault)
    try:
        from cryptography import x509  # noqa: F401
    except ImportError:
        if vault is None:
            return None, None, "cryptography not available and no vault to provision it"
        import subprocess
        py, _ = _ensure_runtime_venv(vault)
        if not py:
            return None, None, "could not build the runtime venv to provision cryptography"
        cmd = (["uv", "pip", "install", "--python", str(py), "cryptography"] if shutil.which("uv")
               else [str(py), "-m", "pip", "install", "cryptography"])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                return None, None, f"cryptography install failed: {(r.stderr or r.stdout).strip()[:160]}"
        except Exception as e:
            return None, None, f"cryptography install error: {type(e).__name__}: {e}"
        _activate_runtime_venv_site(vault)
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Zanmai self-managed signer"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Zanmai"),
        ])
        now = datetime.now(timezone.utc)
        ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
        cert = (x509.CertificateBuilder()
                .subject_name(name).issuer_name(name)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1))
                .not_valid_after(now + timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                    key_encipherment=False, data_encipherment=False, key_agreement=False,
                    key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
                .add_extension(ski, critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski), critical=False)
                .sign(key, hashes.SHA256()))
        cert_p.parent.mkdir(parents=True, exist_ok=True)
        cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_p.write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        for p in (cert_p, key_p):
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        return cert_p, key_p, "created"
    except Exception as e:
        return None, None, f"signer generation failed: {type(e).__name__}: {str(e)[:160]}"


def cmd_media_signer_ensure(args: argparse.Namespace) -> int:
    """Establish (or confirm) the self-managed signing identity. Wong's provisioning
    of the C2PA signer, run once; `media mark --sign` also calls it on demand."""
    vault = _find_vault_root(Path(args.vault)) if args.vault else _find_vault_root(Path.cwd())
    cert_p, key_p, state = _establish_signer(vault)
    ok = cert_p is not None
    print(json.dumps({"state": state, "cert": str(cert_p) if cert_p else None,
                      "key": str(key_p) if key_p else None,
                      "note": "valid, self-managed, not trust-listed (user responsibility)" if ok else None},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_media_mark(args: argparse.Namespace) -> int:
    """Mark a media file for the EU AI Act: read the machine-readable signature
    (present -> preserve; absent -> self-sign only when asked, else a clear
    warning) and optionally burn a visible label. The decisions come from the
    user's menu upstream; this command just executes them deterministically."""
    src = Path(args.image)
    if not src.exists():
        print(json.dumps({"error": f"no such file: {src}"}))
        return 1
    out = Path(args.out) if args.out else src
    status: dict = {"source": str(src), "out": str(out)}

    vault = _find_vault_root(out) or _find_vault_root(src) or _find_vault_root(Path.cwd())
    if vault:
        _activate_runtime_venv_site(vault)

    present, issuer = _c2pa_manifest_state(src)
    status["c2pa_source"] = "present" if present else ("absent" if present is False else "unknown (c2pa lib missing)")
    if issuer:
        status["c2pa_source_issuer"] = issuer

    reencoded = False
    parent_copy: Path | None = None
    # A visible mark (official EU icon or a text label) re-encodes the pixels and
    # breaks any source seal. Keep the pre-edit original so its credential can be
    # chained as a parent ingredient. The icon and the text label are alternatives;
    # the icon (the official EU symbol) takes precedence when both are given.
    if (args.eu_icon or args.visible_label) and present:
        parent_copy = src.with_name(src.stem + ".preedit" + src.suffix)
        shutil.copy2(src, parent_copy)
    if args.eu_icon:
        assets_dir = (vault / ".zanmai" / "system" / "assets" / "eu-ai-icons") if vault else Path(".")
        try:
            info = _composite_eu_icon(src, out, args.eu_icon, assets_dir)
            status["visible_label"] = info
            reencoded = bool(info.get("applied"))
        except ImportError:
            status["visible_label"] = {"applied": False, "error": "Pillow not available in this runtime"}
        except Exception as e:
            status["visible_label"] = {"applied": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    elif args.visible_label:
        try:
            font_used = _burn_visible_label(src, args.visible_label, args.font, out)
            status["visible_label"] = {"applied": True, "text": args.visible_label,
                                       "font": font_used, "position": "bottom-right"}
            reencoded = True
        except ImportError:
            status["visible_label"] = {"applied": False, "error": "Pillow not available in this runtime"}
        except Exception as e:
            status["visible_label"] = {"applied": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    else:
        if out != src:
            shutil.copy2(src, out)
        status["visible_label"] = {"applied": False, "reason": "not requested"}

    cert = args.cert or os.environ.get("ZANMAI_C2PA_CERT")
    key = args.key or os.environ.get("ZANMAI_C2PA_KEY")
    tsa = args.tsa or os.environ.get("ZANMAI_C2PA_TSA", "http://timestamp.digicert.com")
    # Fall back to the self-managed signer, and establish it on demand when this
    # mark actually needs to sign or re-seal (Tom: create the cert if none exists).
    if not (cert and key):
        cp, kp = _signer_paths()
        if not (cp.is_file() and kp.is_file()) and (args.sign or (reencoded and present is True)):
            ecp, ekp, _ = _establish_signer(vault)
            if ecp and ekp:
                cp, kp = ecp, ekp
        if cp.is_file() and kp.is_file():
            cert, key = str(cp), str(kp)
    have_signer = bool(cert and key)

    # The machine-readable credential must always end up on the final file, and a
    # source credential is never silently lost. Branch on: did we re-encode, and did
    # the source carry a credential (True / False / None = unreadable, c2pa missing).
    if reencoded and present is True:
        # our own edit broke the source seal, re-seal so the final file keeps a
        # credential AND the source origin survives as a parent ingredient.
        if have_signer:
            ok, detail = _sign_c2pa(out, cert, key, tsa, parent=parent_copy)
            status["c2pa_result"] = {"state": "re-sealed" if ok else "WARNING",
                "detail": (f"edit re-sealed with the Zanmai signer; source origin ({issuer or 'unknown'}) preserved as a parent ingredient" if ok else detail)}
        else:
            status["c2pa_result"] = {"state": "WARNING",
                "detail": f"the visible mark burn broke the source credential (issuer: {issuer or 'unknown'}) and the self-managed signer could not be established to re-seal (try `media signer ensure`), the delivered file would lose its provenance. Establish the signer, or deliver without the burned mark to keep the source credential intact."}
    elif present is True and not reencoded:
        status["c2pa_result"] = {"state": "preserved", "detail": "source machine-readable mark kept intact, never stripped"}
    elif present is None:
        status["c2pa_result"] = {"state": "WARNING",
            "detail": ("c2pa library missing: could not read the source before the label burn, so any source credential is now gone and none was applied" if reencoded
                       else "c2pa library missing: cannot read or apply a machine-readable credential")}
    elif args.sign:  # source carried no credential; self-sign only when the user chose it
        if have_signer:
            ok, detail = _sign_c2pa(out, cert, key, tsa, parent=None)
            status["c2pa_result"] = {"state": "self-signed" if ok else "WARNING", "detail": detail}
        else:
            status["c2pa_result"] = {"state": "WARNING",
                "detail": "self-sign requested but the self-managed signer could not be established (try `media signer ensure`; it needs the cryptography library, provisioned into the runtime venv)."}
    else:
        status["c2pa_result"] = {"state": "WARNING",
                                 "detail": "no machine-readable signature and self-sign not chosen, delivered unsigned"}

    if parent_copy is not None and parent_copy.exists():
        parent_copy.unlink()

    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


# ---- tools: the external-tool register + detection / provisioning ----------

def _register_path() -> Path:
    """The tool register ships alongside this script under .zanmai/system/."""
    return Path(__file__).resolve().parent.parent / "tool-register.json"


def _load_register() -> dict:
    p = _register_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _current_os() -> str:
    import platform
    s = platform.system().lower()
    if s.startswith("darwin"):
        return "macos"
    if s.startswith("windows"):
        return "windows"
    return "linux"


def _runtime_venv_dir(vault: Path) -> Path:
    return vault / ".zanmai" / "runtime" / "venv"


def _runtime_venv_python(vault: Path) -> Path | None:
    d = _runtime_venv_dir(vault)
    for rel in ("bin/python", "Scripts/python.exe"):
        p = d / rel
        if p.is_file():
            return p
    return None


def _user_python_cmd(vault: Path) -> str:
    """The Python invocation recorded at setup (user.md python_cmd); default python3."""
    um = vault / ".zanmai" / "user.md"
    if um.is_file():
        for line in um.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r'\s*python_cmd:\s*"?([^"\n]+)"?', line)
            if m:
                return m.group(1).strip()
    return "python3"


def _detect_binary(invoke: str, version_flag: str | None) -> dict:
    import subprocess
    token = invoke.split()[0]
    path = shutil.which(token)
    if not path:
        return {"present": False}
    out = {"present": True, "path": path}
    if version_flag:
        try:
            r = subprocess.run([path, version_flag], capture_output=True, text=True, timeout=10)
            lines = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            if lines:
                out["version"] = lines[0]
        except Exception:
            pass
    return out


def _detect_lib(vault: Path, module: str) -> dict:
    import subprocess
    py = _runtime_venv_python(vault)
    if py is None:
        return {"present": False, "note": "runtime venv not built"}
    code = f"import importlib.util as u;print('YES' if u.find_spec({module!r}) else 'NO')"
    try:
        r = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=15)
        return {"present": r.stdout.strip() == "YES", "runtime": str(py)}
    except Exception as e:
        return {"present": False, "note": type(e).__name__}


# Any Chromium-based browser can render HTML to PDF headless; which one does not
# matter. Detect broadly, cross-OS: PATH binaries first (Linux/Windows usual, and
# any browser on PATH), then the standard app-install locations per OS (macOS and
# Windows keep browsers off PATH). Windows almost always has Edge preinstalled.
_RENDERER_BINARIES = (
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    "chrome", "chrome.exe", "msedge", "microsoft-edge", "microsoft-edge-stable",
    "brave", "brave-browser", "vivaldi", "vivaldi-stable",
)
_RENDERER_APP_PATHS = {
    "macos": (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
    ),
    "windows": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ),
    "linux": (
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
        "/usr/bin/chromium-browser", "/usr/bin/brave-browser", "/usr/bin/microsoft-edge",
        "/snap/bin/chromium", "/var/lib/flatpak/exports/bin/org.chromium.Chromium",
    ),
}


def _detect_renderer(osname: str) -> dict:
    """Find any Chromium-based browser, cross-OS. Not a single hardcoded path."""
    for name in _RENDERER_BINARIES:
        p = shutil.which(name)
        if p:
            return {"present": True, "path": p, "via": name}
    for cand in _RENDERER_APP_PATHS.get(osname, ()):  # macOS/Windows keep them off PATH
        cp = Path(cand).expanduser()
        if cp.exists():
            return {"present": True, "path": str(cp)}
    return {"present": False}


def _detect_tool(vault: Path, tid: str, spec: dict, osname: str) -> dict:
    det = spec.get("detect", {})
    method = det.get("method")
    if method == "import":
        return _detect_lib(vault, det.get("import", tid))
    if method == "renderer":
        return _detect_renderer(osname)
    if method == "env":
        envs = det.get("env", [])
        return {"present": all(os.environ.get(e) for e in envs), "note": "env " + ",".join(envs)}
    if method in ("which", "runtime"):
        osspec = (spec.get("os") or {}).get(osname) or {}
        name = osspec.get("invoke") or tid
        # A binary this vault fetched itself lives in the runtime tree and is not
        # on PATH, so PATH alone would report it missing right after it was
        # installed, and every job would fetch it again. The vault's own copy is
        # looked at first, then the host's.
        own = vault / ((spec.get("provision") or {}).get("into") or ".zanmai/runtime/bin") / name
        if own.is_file():
            found = _detect_binary(str(own), det.get("version_flag"))
            if found.get("present"):
                return found
        return _detect_binary(name, det.get("version_flag"))
    if method == "file-glob":
        # A model file is neither a binary on PATH nor an importable library: it is a
        # large file the vault fetched into its own machine-local runtime tree. Without
        # this branch the entry fell through to "no detector", which reads as unknown
        # rather than missing, and a preflight cannot gate on unknown.
        hits = sorted(vault.glob(det.get("glob", "")))
        if hits:
            size = hits[0].stat().st_size / (1024 * 1024)
            return {"present": True, "path": str(hits[0].relative_to(vault)),
                    "note": f"{size:.0f} MB"}
        return {"present": False, "note": f"no file matching {det.get('glob', '')}"}
    if spec.get("kind") == "mcp":
        return {"present": None, "note": "host-configured (check the host)"}
    return {"present": None, "note": f"no detector for method {method!r}"}


def cmd_tools_doctor(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    tools = _load_register().get("tools", {})
    osname = _current_os()
    print(f"Zanmai tool doctor, os={osname}, vault={vault}")
    print(f"runtime venv python: {_runtime_venv_python(vault) or '(not built)'}\n")
    order = {"prerequisite": 0, "on-demand": 1, "recommended": 2, "host-configured": 3}
    cache = _load_tool_cache(vault)
    for tid, spec in sorted(tools.items(), key=lambda kv: (order.get(kv[1].get("tier"), 9), kv[0])):
        res = _detect_tool_cached(vault, tid, spec, osname, cache, refresh=getattr(args, "refresh", False))
        p = res.get("present")
        mark = "ok" if p is True else ("--" if p is False else "??")
        detail = res.get("version") or res.get("note") or res.get("path") or ""
        need = ",".join(spec.get("needed_by", []))
        print(f"  [{mark}] {tid:14} {spec.get('tier',''):14} {detail:40} «{need}»")
    _save_tool_cache(vault, cache)
    return 0


def cmd_tools_check(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    spec = (_load_register().get("tools") or {}).get(args.id)
    if not spec:
        print(json.dumps({"error": f"unknown tool id: {args.id}"}))
        return 1
    res = _detect_tool(vault, args.id, spec, _current_os())
    print(json.dumps({"id": args.id, "tier": spec.get("tier"), **res}, ensure_ascii=False, indent=2))
    return 0


def _ensure_runtime_venv(vault: Path) -> tuple[Path | None, str]:
    import subprocess
    py = _runtime_venv_python(vault)
    if py:
        return py, "present"
    d = _runtime_venv_dir(vault)
    d.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "venv", str(d)] if shutil.which("uv") else _user_python_cmd(vault).split() + ["-m", "venv", str(d)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return None, f"venv create failed: {(r.stderr or r.stdout).strip()[:160]}"
    except Exception as e:
        return None, f"venv create error: {type(e).__name__}: {e}"
    return _runtime_venv_python(vault), "created"


def _fetch_plain_file(vault: Path, tool_id: str, spec: dict, prov: dict) -> dict:
    """Fetch one large plain file, a model, and prove it works by using it.

    Separate from the pinned-binary path because that one unpacks an archive and then
    runs the result with a version flag. A model file is neither an archive nor
    executable, so both steps would fail on something that is perfectly fine. What
    replaces them is the same idea applied honestly: the file is not "installed"
    because it arrived at the right size, it is installed because the thing it exists
    for came out. So a second of silence is generated and transcribed with it, and only
    a clean run counts.
    """
    import urllib.request

    url = prov["url"]
    target = vault / prov["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}-download")
    try:
        with urllib.request.urlopen(url, timeout=600) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        return {"state": "WARNING", "detail": f"download failed: {type(exc).__name__}: {exc}",
                "url": url}

    size_mb = tmp.stat().st_size / (1024 * 1024)
    least = prov.get("expect_min_mb", 1)
    if size_mb < least:
        tmp.unlink(missing_ok=True)
        return {"state": "WARNING",
                "detail": f"downloaded {size_mb:.0f} MB, expected at least {least} MB, "
                          "so this is an error page rather than the file"}
    tmp.replace(target)

    canary = prov.get("canary_cmd")
    if canary:
        ffmpeg = _tool_path(vault, "ffmpeg")
        whisper = _tool_path(vault, canary) or shutil.which(canary)
        if not (ffmpeg and whisper):
            return {"state": "installed", "path": str(target.relative_to(vault)),
                    "size_mb": round(size_mb),
                    "detail": "downloaded, not proven: the tools to try it are not on this machine"}
        work = vault / ".zanmai" / "work" / "voice"
        work.mkdir(parents=True, exist_ok=True)
        probe = work / "canary.wav"
        try:
            subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                            "-t", "1", str(probe)], check=True, capture_output=True)
            subprocess.run([whisper, "-m", str(target), "-f", str(probe), "--no-prints"],
                           check=True, capture_output=True, timeout=300)
        except Exception as exc:  # noqa: BLE001
            return {"state": "WARNING", "path": str(target.relative_to(vault)),
                    "detail": f"downloaded but it does not load: {type(exc).__name__}"}
        finally:
            probe.unlink(missing_ok=True)
        return {"state": "installed", "path": str(target.relative_to(vault)),
                "size_mb": round(size_mb), "detail": "proven by transcribing a canary"}
    return {"state": "installed", "path": str(target.relative_to(vault)), "size_mb": round(size_mb)}


def _fetch_pinned_binary(vault: Path, tool_id: str, spec: dict, os_spec: dict, prov: dict) -> dict:
    """Fetch one self-contained binary at the pinned version, unpack it into the
    machine-local runtime tree, and prove it works before calling it installed.

    Three things make this dependable rather than hopeful. The version is pinned,
    so a render is reproducible and an upstream release cannot move the typesetting
    under a document. The binary is executed and its version matched, because an
    archive that unpacked badly still leaves a file of the right name in the right
    place. And where the spec names a canary, that canary is compiled, since the
    question is never "does the file exist" but "does the thing it is needed for
    actually come out".
    """
    import platform
    import subprocess
    import tarfile
    import urllib.request
    import zipfile

    version = spec["version_pin"]
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64", "amd64": "x86_64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    asset = os_spec["asset"].format(arch=arch, version=version)
    url = prov["release"].format(version=version, asset=asset)
    target_dir = vault / prov.get("into", ".zanmai/runtime/bin")
    target_dir.mkdir(parents=True, exist_ok=True)
    binary_name = os_spec.get("invoke", tool_id)

    tmp = target_dir / f".{tool_id}-download"
    try:
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
    except Exception as exc:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        return {"state": "WARNING", "detail": f"download failed: {type(exc).__name__}: {exc}",
                "url": url, "hint": (os_spec.get("install_hint") or {}).get("text")}

    unpacked = target_dir / f".{tool_id}-unpacked"
    shutil.rmtree(unpacked, ignore_errors=True)
    try:
        if asset.endswith(".zip"):
            with zipfile.ZipFile(tmp) as archive:
                archive.extractall(unpacked)
        else:
            with tarfile.open(tmp) as archive:
                archive.extractall(unpacked)
    except Exception as exc:  # noqa: BLE001
        return {"state": "WARNING", "detail": f"unpack failed: {type(exc).__name__}: {exc}"}
    finally:
        tmp.unlink(missing_ok=True)

    found = next((p for p in unpacked.rglob(binary_name) if p.is_file()), None)
    if not found:
        shutil.rmtree(unpacked, ignore_errors=True)
        return {"state": "WARNING", "detail": f"no '{binary_name}' inside {asset}"}
    installed = target_dir / binary_name
    shutil.move(str(found), str(installed))
    installed.chmod(0o755)
    shutil.rmtree(unpacked, ignore_errors=True)

    try:
        probe = subprocess.run([str(installed), "--version"], capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001
        return {"state": "WARNING", "detail": f"cannot run the fetched binary: {type(exc).__name__}: {exc}"}
    reported = (probe.stdout or probe.stderr).strip()
    if version not in reported:
        return {"state": "WARNING", "path": str(installed),
                "detail": f"fetched binary reports '{reported}', pinned version is {version}"}

    canary = prov.get("canary")
    if canary:
        source = vault / canary
        if not source.is_file():
            return {"state": "WARNING", "path": str(installed),
                    "detail": f"canary missing at {canary}, so the install is unproven"}
        out_pdf = vault / ".zanmai" / "runtime" / f"{tool_id}-canary.pdf"
        try:
            run = subprocess.run([str(installed), "compile", str(source), str(out_pdf)],
                                 capture_output=True, text=True, timeout=180)
        except Exception as exc:  # noqa: BLE001
            return {"state": "WARNING", "path": str(installed),
                    "detail": f"canary run failed: {type(exc).__name__}: {exc}"}
        if run.returncode != 0 or not out_pdf.is_file() or out_pdf.stat().st_size < 1024:
            return {"state": "WARNING", "path": str(installed),
                    "detail": f"canary did not produce a document: {(run.stderr or run.stdout).strip()[:200]}"}

    return {"state": "installed", "version": reported, "path": str(installed),
            "canary": "compiled" if canary else "none"}


def cmd_tools_ensure(args: argparse.Namespace) -> int:
    import subprocess
    vault = Path(args.vault).resolve()
    spec = (_load_register().get("tools") or {}).get(args.id)
    if not spec:
        print(json.dumps({"error": f"unknown tool id: {args.id}"}))
        return 1
    osname = _current_os()
    if _detect_tool(vault, args.id, spec, osname).get("present") is True:
        print(json.dumps({"id": args.id, "state": "already-present"}, ensure_ascii=False))
        return 0
    tier = spec.get("tier")
    if tier == "prerequisite":
        hint = ((spec.get("os") or {}).get(osname) or {}).get("install_hint") or {}
        print(json.dumps({"id": args.id, "state": "needs-user", "tier": "prerequisite",
                          "hint": hint.get("text"), "guide": hint.get("guide", "(guide TBD)")},
                         ensure_ascii=False, indent=2))
        return 0
    prov = spec.get("provision", {})
    method = prov.get("method")
    if method == "venv-pip":
        py, note = _ensure_runtime_venv(vault)
        if not py:
            print(json.dumps({"id": args.id, "state": "WARNING", "detail": note}))
            return 1
        pkg = prov["pip"]
        cmd = (["uv", "pip", "install", "--python", str(py), pkg] if shutil.which("uv")
               else [str(py), "-m", "pip", "install", pkg])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except Exception as e:
            print(json.dumps({"id": args.id, "state": "WARNING", "detail": f"{type(e).__name__}: {e}"}))
            return 1
        if r.returncode != 0:
            print(json.dumps({"id": args.id, "state": "WARNING", "detail": (r.stderr or r.stdout).strip()[:200]}))
            return 1
        ok = _detect_lib(vault, (spec.get("detect") or {}).get("import", args.id)).get("present")
        print(json.dumps({"id": args.id, "state": "installed" if ok else "WARNING",
                          "pip": pkg, "runtime": str(py), "venv": note}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if method == "file-fetch":
        if not (prov.get("url") and prov.get("target")):
            print(json.dumps({"id": args.id, "state": "needs-user", "tier": tier,
                              "detail": "no url and target for this file, so nothing is fetched on a guess"},
                             ensure_ascii=False, indent=2))
            return 0
        result = _fetch_plain_file(vault, args.id, spec, prov)
        print(json.dumps({"id": args.id, **result}, ensure_ascii=False, indent=2))
        return 0 if result.get("state") == "installed" else 1
    if method == "binary-fetch":
        os_spec = ((spec.get("os") or {}).get(osname) or {})
        hint = os_spec.get("install_hint") or {}
        if not (prov.get("release") and os_spec.get("asset") and spec.get("version_pin")):
            print(json.dumps({"id": args.id, "state": "needs-user", "tier": tier,
                              "detail": "no pinned release for this platform, so nothing is fetched on a guess",
                              "hint": hint.get("text"), "note": prov.get("note")}, ensure_ascii=False, indent=2))
            return 0
        result = _fetch_pinned_binary(vault, args.id, spec, os_spec, prov)
        print(json.dumps({"id": args.id, **result}, ensure_ascii=False, indent=2))
        return 0 if result.get("state") == "installed" else 1
    if method == "wong":
        print(json.dumps({"id": args.id, "state": "wong", "detail": "provisioned by Wong",
                          "recipe": prov.get("recipe"), "storage": prov.get("storage")}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"id": args.id, "state": "host-configured" if spec.get("kind") == "mcp" else "no-provisioner",
                      "detail": spec.get("purpose")}, ensure_ascii=False))
    return 0


# ---- tool cache (machine-local, update-immune) + preflight ------------------

def _tool_cache_path(vault: Path) -> Path:
    """Detection results live here, in the writable runtime tree that updates
    never touch. The register stays static and presence-free; this is the second,
    dynamic database of what was found on THIS machine, so a preflight is a quick
    look, not a full rescan each time."""
    return vault / ".zanmai" / "runtime" / "tool-cache.json"


def _load_tool_cache(vault: Path) -> dict:
    p = _tool_cache_path(vault)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_tool_cache(vault: Path, cache: dict) -> None:
    p = _tool_cache_path(vault)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _detect_tool_cached(vault: Path, tid: str, spec: dict, osname: str,
                        cache: dict, refresh: bool = False) -> dict:
    """Detection with the machine-local cache. A cached present-hit is validated
    cheaply before it is trusted (binary path still exists / venv python
    unchanged); anything absent or stale re-detects and re-registers. This is how
    a change gets picked up without paying a full scan every time."""
    method = (spec.get("detect") or {}).get("method")
    if refresh or method not in ("which", "runtime", "import"):
        return _detect_tool(vault, tid, spec, osname)
    entry = (cache.get("tools") or {}).get(tid)
    if entry and entry.get("os") == osname and entry.get("present") is True:
        if method in ("which", "runtime") and entry.get("path") and os.path.exists(entry["path"]):
            return {**entry, "cached": True}
        if method == "import":
            vp = _runtime_venv_python(vault)
            if vp and str(vp) == entry.get("runtime"):
                return {**entry, "cached": True}
    res = _detect_tool(vault, tid, spec, osname)
    cache.setdefault("tools", {})[tid] = {**res, "os": osname,
                                          "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    return res


def _required_tool_ids(reg: dict, expert: str, capability: str | None) -> list[str]:
    """Which tool ids gate this dispatch. With a capability, only that path's
    required set (fine-grained, e.g. carol html needs the renderer, not Affinity);
    without, the expert's full needed_by (coarse)."""
    if capability:
        caps = ((reg.get("capabilities") or {}).get(expert) or {}).get(capability) or {}
        return list(caps.get("required", []))
    tools = reg.get("tools") or {}
    return [tid for tid, spec in tools.items() if expert in (spec.get("needed_by") or [])]


def cmd_tools_preflight(args: argparse.Namespace) -> int:
    """Steve runs this BEFORE handing a job to an expert: are the prerequisites
    met? Deterministic, per OS, cache-backed. Every gap carries the WHY (what the
    tool does for the job, from the register purpose) and the HOW (install hint),
    so Steve can auto-provision a small library, ask for a heavy one, or stop with
    a clear message. No expert discovers a missing tool mid-run: a subagent cannot
    ask the user (operating-principles section 10)."""
    vault = Path(args.vault).resolve()
    reg = _load_register()
    tools = reg.get("tools") or {}
    osname = _current_os()
    ids = _required_tool_ids(reg, args.expert, args.capability)
    cache = _load_tool_cache(vault)
    present, auto_provision, needs_user, notes = [], [], [], []
    for tid in ids:
        spec = tools.get(tid)
        if not spec:
            needs_user.append({"id": tid, "why": "unknown tool id (register gap)", "how": None, "tier": "unknown"})
            continue
        res = _detect_tool_cached(vault, tid, spec, osname, cache, refresh=args.refresh)
        why = spec.get("purpose")
        hint = ((spec.get("os") or {}).get(osname) or {}).get("install_hint") or {}
        if res.get("present") is True:
            present.append({"id": tid, "version": res.get("version"), "path": res.get("path"),
                            "cached": res.get("cached", False)})
            continue
        tier = spec.get("tier")
        method = (spec.get("provision") or {}).get("method")
        if tier == "recommended":
            notes.append({"id": tid, "why": why, "note": "accelerator, not required"})
        elif tier == "on-demand" and method == "venv-pip":
            auto_provision.append({"id": tid, "why": why})
        elif tier == "on-demand" and method == "binary-fetch" and (spec.get("provision") or {}).get("release"):
            # A single pinned binary is Zanmai's to fetch: it needs no package
            # manager, no admin rights, and it is proven by its canary before use.
            auto_provision.append({"id": tid, "why": why, "version": spec.get("version_pin")})
        else:
            item = {"id": tid, "tier": tier, "why": why, "how": hint.get("text"), "guide": hint.get("guide")}
            if spec.get("kind") == "mcp" and not item["how"]:
                item["how"] = "configure the MCP at the host, then it is usable (LD6)"
            needs_user.append(item)
    _save_tool_cache(vault, cache)
    ready = not needs_user and not auto_provision
    print(json.dumps({"expert": args.expert, "capability": args.capability, "os": osname,
                      "ready": ready, "present": present, "auto_provision": auto_provision,
                      "needs_user": needs_user, "notes": notes},
                     ensure_ascii=False, indent=2))
    return 0


def _find_vault_root(start: Path) -> Path | None:
    p = start.resolve()
    for cand in [p] + list(p.parents):
        if (cand / ".zanmai").is_dir():
            return cand
    return None


def _activate_runtime_venv_site(vault: Path) -> None:
    """Make libraries provisioned into the runtime venv importable in-process, so
    a media command run under the recorded python can use what `tools ensure`
    installed. Same-Python assumption: the runtime venv is built with the vault's
    python_cmd, so its compiled extensions match this interpreter's ABI."""
    py = _runtime_venv_python(vault)
    if not py:
        return
    import glob
    base = py.parent.parent  # .../venv/bin/python -> .../venv
    for sp in glob.glob(str(base / "lib" / "python*" / "site-packages")) + [str(base / "Lib" / "site-packages")]:
        if os.path.isdir(sp) and sp not in sys.path:
            sys.path.insert(0, sp)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="zanmai", description="Zanmai CLI: setup, snapshots, bundles, assets, contacts, notes, plans, reviews, files, updates, index, memory, media, hooks.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # media -----
    p_media = sub.add_parser("media", help="Media marking (EU AI Act): C2PA signature and visible label.")
    sub_media = p_media.add_subparsers(dest="subcmd", required=True)
    pmk = sub_media.add_parser("mark", help="Read/preserve or self-sign the machine-readable mark; optionally burn a visible label.")
    pmk.add_argument("image")
    pmk.add_argument("--visible-label", dest="visible_label", help="Label text in the user's language (e.g. AI-generated / AI-edited, localised). Omit for no visible label.")
    pmk.add_argument("--eu-icon", dest="eu_icon", choices=["generated", "modified", "base"], help="Composite the official EU AI-content icon bottom-right (class decided upstream in the flow). Alternative to --visible-label; takes precedence if both are given.")
    pmk.add_argument("--font", help="TTF/TTC path from the active style profile.")
    pmk.add_argument("--out", help="Output path. Defaults to marking in place.")
    pmk.add_argument("--sign", action="store_true", help="Self-sign when no machine-readable mark is present (only when the user chose it).")
    pmk.add_argument("--cert", help="Signing cert chain PEM (else env ZANMAI_C2PA_CERT).")
    pmk.add_argument("--key", help="Signing key PEM (else env ZANMAI_C2PA_KEY).")
    pmk.add_argument("--tsa", help="RFC3161 timestamp URL (else env ZANMAI_C2PA_TSA).")
    pmk.set_defaults(func=cmd_media_mark)
    pmsig = sub_media.add_parser("signer", help="Manage the self-managed C2PA signing identity.")
    sub_media_signer = pmsig.add_subparsers(dest="signeraction", required=True)
    pmse = sub_media_signer.add_parser("ensure", help="Create the signer if none exists (Wong's provisioning), then report its paths. media mark also calls this on demand.")
    pmse.add_argument("vault", nargs="?", default=".")
    pmse.set_defaults(func=cmd_media_signer_ensure)

    # tools -----
    p_tools = sub.add_parser("tools", help="External-tool register: detect and provision what dist needs, per OS.")
    sub_tools = p_tools.add_subparsers(dest="subcmd", required=True)
    pt_doc = sub_tools.add_parser("doctor", help="Detect every registered tool on this machine.")
    pt_doc.add_argument("vault", nargs="?", default=".")
    pt_doc.add_argument("--refresh", action="store_true", help="Ignore the cache and re-detect everything.")
    pt_doc.set_defaults(func=cmd_tools_doctor)
    pt_pf = sub_tools.add_parser("preflight", help="Check an expert's prerequisites before dispatch (deterministic, cache-backed). Steve runs this first.")
    pt_pf.add_argument("expert")
    pt_pf.add_argument("--capability", default=None, help="Gate only this path's required tools (e.g. --capability html for a Carol flyer).")
    pt_pf.add_argument("--refresh", action="store_true", help="Ignore the cache and re-detect.")
    pt_pf.add_argument("vault", nargs="?", default=".")
    pt_pf.set_defaults(func=cmd_tools_preflight)
    pt_chk = sub_tools.add_parser("check", help="Detect one tool by id.")
    pt_chk.add_argument("id")
    pt_chk.add_argument("vault", nargs="?", default=".")
    pt_chk.set_defaults(func=cmd_tools_check)
    pt_ens = sub_tools.add_parser("ensure", help="Provision an on-demand tool at first use (venv libs now; binaries later).")
    pt_ens.add_argument("id")
    pt_ens.add_argument("vault", nargs="?", default=".")
    pt_ens.set_defaults(func=cmd_tools_ensure)

    # setup -----
    p_setup = sub.add_parser("setup", help="First-time install, validate, and (future) update.")
    sub_setup = p_setup.add_subparsers(dest="subcmd", required=True)

    ps_init = sub_setup.add_parser("init", help="First-time install.")
    ps_init.add_argument("vault_root", nargs="?", default=".")
    ps_init.add_argument("--first-name", required=True, dest="first_name")
    ps_init.add_argument("--last-name", required=True, dest="last_name")
    ps_init.add_argument("--language", default="auto")
    ps_init.add_argument("--email", default="")
    ps_init.add_argument("--preferred-address", default="", dest="preferred_address",
                         help="A nickname or short form distinct from first-name. Empty means same as first-name.")
    ps_init.add_argument("--python-cmd", default="python3", dest="python_cmd",
                         help="The Python invocation that works on this machine.")
    # Kept for compatibility; init now detects ZenNotes and the zn CLI itself
    # (deterministic, matching the session-start recheck), so these are not relied on.
    ps_init.add_argument("--zennotes-installed", dest="zennotes_installed", action="store_true", default=False)
    ps_init.add_argument("--no-zennotes", dest="zennotes_installed", action="store_false")
    ps_init.add_argument("--zen-cli-installed", dest="zen_cli_installed", action="store_true", default=False)
    ps_init.add_argument("--no-zen-cli", dest="zen_cli_installed", action="store_false")
    ps_init.set_defaults(func=cmd_setup_init)

    ps_validate = sub_setup.add_parser("validate", help="Check the vault is initialised and structurally sound.")
    ps_validate.add_argument("vault_root", nargs="?", default=".")
    ps_validate.set_defaults(func=cmd_setup_validate)

    ps_update = sub_setup.add_parser("update", help="Refresh host-side config after the distribution files changed (agent and skill symlinks, .claude/settings.json). Pepper's update workflow runs this after upgrade.")
    ps_update.add_argument("vault_root", nargs="?", default=".")
    ps_update.set_defaults(func=cmd_setup_update)

    ps_upgrade = sub_setup.add_parser("upgrade", help="Fetch the newest published version over HTTPS and replace the distribution files. Works the same whether the vault was cloned or unpacked from an archive. Never touches user-immune paths; Pepper snapshots first.")
    ps_upgrade.add_argument("vault_root", nargs="?", default=".")
    ps_upgrade.add_argument("--check", action="store_true", help="Only report whether a newer version exists.")
    ps_upgrade.set_defaults(func=cmd_setup_upgrade)

    ps_post = sub_setup.add_parser("post-upgrade", help="The tail of an upgrade, run by the new script on itself: host refresh, verification, version marker. Called by 'setup upgrade', not by hand.")
    ps_post.add_argument("vault_root", nargs="?", default=".")
    ps_post.add_argument("--from", dest="from_version", default="", help="Version the vault was on before.")
    ps_post.add_argument("--to", dest="to_version", default="", help="Version that was just installed. Defaults to the shipped one.")
    ps_post.add_argument("--origin", default="", help="Where the new version came from, for the success message.")
    ps_post.add_argument("--replaced", type=int, help="Number of files replaced, for the success message.")
    ps_post.add_argument("--withdrawn", type=int, help="Number of files withdrawn, for the success message.")
    ps_post.set_defaults(func=cmd_setup_post_upgrade)

    # snapshot -----
    p_snap = sub.add_parser("snapshot", help="Vault and dist snapshots.")
    sub_snap = p_snap.add_subparsers(dest="subcmd", required=True)

    ps_create = sub_snap.add_parser("create", help="Timestamped copy of the vault under `<vault>/.zanmai/snapshots/`. Respects auto_snapshots flag in .zanmai/user.md.")
    ps_create.add_argument("vault", nargs="?", default=".")
    ps_create.add_argument("--reason", required=True, help="Short slug naming why the snapshot is taken; becomes the folder suffix.")
    ps_create.add_argument("--root", default=None, help="Override snapshots root (default: `<vault>/.zanmai/snapshots/`).")
    ps_create.set_defaults(func=cmd_snapshot_create)

    ps_enable = sub_snap.add_parser("enable", help="Turn auto_snapshots ON in .zanmai/user.md.")
    ps_enable.add_argument("vault", nargs="?", default=".")
    ps_enable.set_defaults(func=cmd_snapshot_enable)

    ps_disable = sub_snap.add_parser("disable", help="Turn auto_snapshots OFF in .zanmai/user.md. No automatic snapshots until re-enabled.")
    ps_disable.add_argument("vault", nargs="?", default=".")
    ps_disable.set_defaults(func=cmd_snapshot_disable)

    ps_list = sub_snap.add_parser("list", help="List snapshots in `<vault>/.zanmai/snapshots/` newest first.")
    ps_list.add_argument("vault", nargs="?", default=".")
    ps_list.add_argument("--root", default=None, help="Override snapshots root (default: `<vault>/.zanmai/snapshots/`).")
    ps_list.set_defaults(func=cmd_snapshot_list)

    ps_del = sub_snap.add_parser("delete", help="Delete a named snapshot or all snapshots older than N days. Age-mode is dry-run unless --yes.")
    ps_del.add_argument("vault", nargs="?", default=".")
    ps_del.add_argument("--name", help="Exact snapshot folder name to delete (e.g. 2026-06-21-1620-pre-import).")
    ps_del.add_argument("--older-than", dest="older_than", type=int, help="Delete snapshots older than N days.")
    ps_del.add_argument("--yes", action="store_true", help="Required for --older-than bulk deletes (otherwise dry-run).")
    ps_del.add_argument("--root", default=None, help="Override snapshots root.")
    ps_del.set_defaults(func=cmd_snapshot_delete)

    # bundle -----


    p_voice = sub.add_parser("voice", help="Voice notes dropped in _import/recordings/: what waits, the vault's names, transcription, filing.")
    sub_voice = p_voice.add_subparsers(dest="voice_cmd", required=True)

    pv_scan = sub_voice.add_parser("scan", help="What is waiting to be transcribed, oldest first.")
    pv_scan.add_argument("vault", nargs="?", default=".")
    pv_scan.set_defaults(func=cmd_voice_scan)

    pv_lex = sub_voice.add_parser("lexicon", help="The vault's own names, to bias the recogniser before it starts.")
    pv_lex.add_argument("vault", nargs="?", default=".")
    pv_lex.add_argument("--out", help="Also write the list here.")
    pv_lex.add_argument("--budget", type=int, default=LEXICON_BUDGET_CHARS)
    pv_lex.set_defaults(func=cmd_voice_lexicon)

    pv_tr = sub_voice.add_parser("transcribe", help="One recording to text, locally, biased by the vault's names.")
    pv_tr.add_argument("vault", nargs="?", default=".")
    pv_tr.add_argument("--file", required=True)
    pv_tr.add_argument("--lexicon", help="File written by `voice lexicon --out`.")
    pv_tr.add_argument("--language", default="auto")
    pv_tr.set_defaults(func=cmd_voice_transcribe)

    pv_ar = sub_voice.add_parser("archive", help="Move a processed recording to assets/recordings/, keeping it.")
    pv_ar.add_argument("vault", nargs="?", default=".")
    pv_ar.add_argument("--file", required=True)
    pv_ar.add_argument("--agent")
    pv_ar.set_defaults(func=cmd_voice_archive)

    p_work = sub.add_parser("work", help="Work objects: one row plus one page per piece of work, in inbox/review/.")
    sub_work = p_work.add_subparsers(dest="work_cmd", required=True)

    pw_open = sub_work.add_parser("open", help="Open a work object and print its id.")
    pw_open.add_argument("vault", nargs="?", default=".")
    pw_open.add_argument("--title", required=True)
    pw_open.add_argument("--owner", help="Which specialist is on it.")
    pw_open.add_argument("--goal", help="What finished looks like.")
    pw_open.add_argument("--deliverable", help="Where the result will land.")
    pw_open.add_argument("--workshop", help="Where the working files live.")
    pw_open.set_defaults(func=cmd_work_open)

    pw_ask = sub_work.add_parser("ask", help="Record a question only the user can answer; marks the object as waiting.")
    pw_ask.add_argument("vault", nargs="?", default=".")
    pw_ask.add_argument("--id", required=True, help="Full id or its first characters.")
    pw_ask.add_argument("--question", required=True)
    pw_ask.set_defaults(func=cmd_work_ask)

    pw_answer = sub_work.add_parser("answer", help="Record the user's answer and put the object back to open.")
    pw_answer.add_argument("vault", nargs="?", default=".")
    pw_answer.add_argument("--id", required=True)
    pw_answer.add_argument("--answer", required=True)
    pw_answer.set_defaults(func=cmd_work_answer)

    pw_log = sub_work.add_parser("log", help="Append one line to the object's log and add up its cost.")
    pw_log.add_argument("vault", nargs="?", default=".")
    pw_log.add_argument("--id", required=True)
    pw_log.add_argument("--note", required=True)
    pw_log.add_argument("--agent")
    pw_log.add_argument("--tokens", type=int)
    pw_log.add_argument("--minutes", type=int)
    pw_log.add_argument("--workshop")
    pw_log.add_argument("--deliverable")
    pw_log.set_defaults(func=cmd_work_log)

    pw_done = sub_work.add_parser("done", help="Close a work object.")
    pw_done.add_argument("vault", nargs="?", default=".")
    pw_done.add_argument("--id", required=True)
    pw_done.add_argument("--agent")
    pw_done.set_defaults(func=cmd_work_done)

    pw_list = sub_work.add_parser("list", help="What is open and what is waiting on the user.")
    pw_list.add_argument("vault", nargs="?", default=".")
    pw_list.add_argument("--state", help="Filter: open, 'waiting on you', done.")
    pw_list.set_defaults(func=cmd_work_list)

    p_bundle = sub.add_parser("bundle", help="Bundle operations.")
    sub_bundle = p_bundle.add_subparsers(dest="subcmd", required=True)

    pb_create = sub_bundle.add_parser("create", help="Create inbox/<kind>/<slug>/<slug>.md from template plus INDEX.md.")
    pb_create.add_argument("vault", nargs="?", default=".")
    pb_create.add_argument("--kind", required=True, choices=list(KIND_FIELDS.keys()))
    pb_create.add_argument("--slug", required=True)
    pb_create.add_argument("--title")
    pb_create.add_argument("--source", choices=["organic", "ai-generated"],
                           help="Provenance. Default: the template's value.")
    pb_create.add_argument("--source-detail", dest="source_detail",
                           help="Where it came from, e.g. research:<slug> or import:<file>.")
    pb_create.add_argument("--goal")
    pb_create.add_argument("--status")
    pb_create.add_argument("--cadence")
    pb_create.add_argument("--due")
    pb_create.add_argument("--topic")
    pb_create.add_argument("--last_done")
    pb_create.add_argument("--heading-files", dest="heading_files",
                           help="Heading for the members list in INDEX.md, in the user's language. Default English.")
    pb_create.add_argument("--heading-activity", dest="heading_activity",
                           help="Heading for the activity list in INDEX.md, in the user's language. Default English.")
    pb_create.set_defaults(func=cmd_create_bundle)

    pb_addfile = sub_bundle.add_parser("add-file", help="Copy a markdown file into a bundle (body verbatim, frontmatter migrated to schema).")
    pb_addfile.add_argument("vault", nargs="?", default=".")
    pb_addfile.add_argument("--source", required=True)
    pb_addfile.add_argument("--bundle-slug", required=True, dest="bundle_slug",
                            help="Bundle slug. May include '/' for sub-bundles.")
    pb_addfile.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_addfile.add_argument("--target-kind", dest="target_kind", choices=list(KIND_FIELDS.keys()))
    pb_addfile.add_argument("--target-name", dest="target_name")
    pb_addfile.add_argument("--overwrite", action="store_true",
                            help="Allow overwriting an existing target with the same slug. Default: append '-imported'.")
    pb_addfile.add_argument("--source-class", dest="source_class",
                            choices=["organic", "collaborative", "ai-generated"],
                            help="Who wrote this. Beats what the file says about itself; without it a file that declares nothing counts as the user's own.")
    pb_addfile.add_argument("--source-detail", dest="source_detail",
                            help="Free-text refinement of where it came from, e.g. 'session:research-2026-08'.")
    pb_addfile.add_argument("--summary",
                            help="One-line role of this file inside the bundle, for its INDEX.md entry. Without it the file's own topic or title is used.")
    pb_addfile.set_defaults(func=cmd_copy_into_bundle)

    pb_addtruth = sub_bundle.add_parser("add-truth", help="Write a truth file for an existing sub-bundle with a 'Part of [[parent]]' wikilink.")
    pb_addtruth.add_argument("vault", nargs="?", default=".")
    pb_addtruth.add_argument("--bundle-slug", required=True, dest="bundle_slug",
                             help="Sub-bundle path (must contain '/').")
    pb_addtruth.add_argument("--kind", required=True, choices=list(KIND_FIELDS.keys()))
    pb_addtruth.add_argument("--title")
    pb_addtruth.add_argument("--goal")
    pb_addtruth.add_argument("--status")
    pb_addtruth.add_argument("--cadence")
    pb_addtruth.add_argument("--due")
    pb_addtruth.add_argument("--topic")
    pb_addtruth.add_argument("--last-done", dest="last_done")
    pb_addtruth.set_defaults(func=cmd_create_sub_bundle_truth)

    pb_rename = sub_bundle.add_parser("rename", help="Atomically rename a slug: file rename, frontmatter slug, vault-wide wikilink rewrite, master INDEX refresh.")
    pb_rename.add_argument("vault", nargs="?", default=".")
    pb_rename.add_argument("--old", required=True)
    pb_rename.add_argument("--new", required=True)
    pb_rename.add_argument("--bundle-slug", dest="bundle_slug")
    pb_rename.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_rename.set_defaults(func=cmd_rename_slug)

    pb_setbody = sub_bundle.add_parser("set-body", help="Replace the body of a file in a bundle. Frontmatter untouched.")
    pb_setbody.add_argument("vault", nargs="?", default=".")
    pb_setbody.add_argument("--file", required=True, help="Vault-relative path, or a unique basename under inbox/.")
    pb_setbody.add_argument("--body-file", dest="body_file", help="Read the new body from this file. Default: stdin.")
    pb_setbody.add_argument("--replace", action="store_true", help="Allow overwriting a body that already has content.")
    pb_setbody.add_argument("--agent", help="Name for the activity-log line.")
    pb_setbody.set_defaults(func=cmd_bundle_set_body)

    pb_editfile = sub_bundle.add_parser("edit-file", help="Correct frontmatter fields of an existing file in place. Body untouched.")
    pb_editfile.add_argument("vault", nargs="?", default=".")
    pb_editfile.add_argument("--file", required=True, help="Vault-relative path, or a unique basename under inbox/.")
    pb_editfile.add_argument("--set", action="append", default=[], help="key=value. A list is written as [a, b, c]. Repeatable.")
    pb_editfile.add_argument("--remove", action="append", default=[], help="Field to remove. Repeatable.")
    pb_editfile.add_argument("--agent", help="Name for the activity-log line.")
    pb_editfile.set_defaults(func=cmd_bundle_edit_file)

    # asset -----
    p_asset = sub.add_parser("asset", help="Non-markdown files in the shared vault-root assets/ folder.")
    sub_asset = p_asset.add_subparsers(dest="subcmd", required=True)

    pa_add = sub_asset.add_parser("add", help="Copy a non-markdown file into the shared vault-root assets/ folder.")
    pa_add.add_argument("vault", nargs="?", default=".")
    pa_add.add_argument("--source", required=True)
    pa_add.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pa_add.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pa_add.add_argument("--target-name", dest="target_name",
                        help="Override the target filename. Use when source basenames collide (e.g. multiple '1.jpg').")
    pa_add.add_argument("--overwrite", action="store_true")
    pa_add.set_defaults(func=cmd_copy_attachment)

    # contact -----
    p_contact = sub.add_parser("contact", help="Person and organisation contacts.")
    sub_contact = p_contact.add_subparsers(dest="subcmd", required=True)

    pc_create = sub_contact.add_parser("create", help="Create a contact file under inbox/contacts/<sub>/<slug>.md.")
    pc_create.add_argument("vault", nargs="?", default=".")
    pc_create.add_argument("--kind", required=True, choices=("person", "organization"))
    pc_create.add_argument("--slug", required=True)
    pc_create.add_argument("--full-name", dest="full_name")
    pc_create.add_argument("--source", help="Optional source markdown file. Body verbatim, frontmatter migrated to schema.")
    pc_create.add_argument("--email")
    pc_create.add_argument("--phone")
    pc_create.add_argument("--role")
    pc_create.add_argument("--org")
    pc_create.add_argument("--kind_of")
    pc_create.add_argument("--website")
    pc_create.add_argument("--mentioned-in", dest="mentioned_in", action="append", default=[],
                           help="Source slug (bundle or member) where this entity was found. Repeatable. Stored in frontmatter `mentioned_in:` and rendered as a wikilink list in the body so the user sees where the stub came from.")
    pc_create.set_defaults(func=cmd_register_contact)

    pc_update = sub_contact.add_parser("update", help="Enrich an existing contact: set frontmatter fields, append body lines.")
    pc_update.add_argument("vault", nargs="?", default=".")
    pc_update.add_argument("--slug", required=True)
    pc_update.add_argument("--set", action="append", default=[], help="key=value. Repeatable.")
    pc_update.add_argument("--remove", action="append", default=[], help="Field to remove. Repeatable.")
    pc_update.add_argument("--append", action="append", default=[], help="Body line to append. Repeatable.")
    pc_update.add_argument("--agent", help="Name for the activity-log line.")
    pc_update.set_defaults(func=cmd_contact_update)

    # notes -----
    p_notes = sub.add_parser("notes", help="Daily, Weekly and Monthly Notes (when configured in ZenNotes).")
    sub_notes = p_notes.add_subparsers(dest="subcmd", required=True)

    def _add_note_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("vault", nargs="?", default=".")
        p.add_argument("--date", default=None, help="Target date YYYY-MM-DD. Defaults to now (the note covering today, this week or this month for the chosen kind).")
        p.add_argument("--ensure", action="store_true", help="Create the note file if it does not exist.")
        p.add_argument("--append", default=None, help="Append a line to the note (implies --ensure).")
        p.add_argument("--print-path", dest="print_path", action="store_true",
                       help="Print the resolved path relative to vault root and exit.")

    pn_daily = sub_notes.add_parser("daily", help="Daily-note operations: print-path, ensure, append. Exit 2 if daily notes are disabled or unconfigured.")
    _add_note_args(pn_daily)
    pn_daily.set_defaults(func=cmd_daily_note, _kind="daily")

    pn_weekly = sub_notes.add_parser("weekly", help="Weekly-note operations: print-path, ensure, append. Exit 2 if weekly notes are disabled or unconfigured.")
    _add_note_args(pn_weekly)
    pn_weekly.set_defaults(func=cmd_daily_note, _kind="weekly")

    pn_monthly = sub_notes.add_parser("monthly", help="Monthly-note operations: print-path, ensure, append. Exit 2 if monthly notes are disabled or unconfigured.")
    _add_note_args(pn_monthly)
    pn_monthly.set_defaults(func=cmd_daily_note, _kind="monthly")

    # file -----
    p_file = sub.add_parser("file", help="File moves into system folders.")
    sub_file = p_file.add_subparsers(dest="subcmd", required=True)

    pf_trash = sub_file.add_parser("trash", help="Move a file to trash/ (zn trash with mv-fallback).")
    pf_trash.add_argument("vault", nargs="?", default=".")
    pf_trash.add_argument("--path", required=True)
    pf_trash.set_defaults(func=cmd_trash_file)

    pf_archive = sub_file.add_parser("archive", help="Move a file to archive/ (zn archive with mv-fallback).")
    pf_archive.add_argument("vault", nargs="?", default=".")
    pf_archive.add_argument("--path", required=True)
    pf_archive.set_defaults(func=cmd_archive_file)

    # plan -----
    p_plan = sub.add_parser("plan", help="Plan files in inbox/review/.")
    sub_plan = p_plan.add_subparsers(dest="subcmd", required=True)

    pp_clear = sub_plan.add_parser("clear-section", help="Remove the '## Plan' section from a bundle truth file after filing.")
    pp_clear.add_argument("vault", nargs="?", default=".")
    pp_clear.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pp_clear.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pp_clear.add_argument("--truth-file", dest="truth_file")
    pp_clear.set_defaults(func=cmd_clear_plan_section)

    # review -----
    p_review = sub.add_parser("review", help="Items in inbox/review/ other than plans.")
    sub_review = p_review.add_subparsers(dest="subcmd", required=True)

    pr_archive = sub_review.add_parser("archive", help="Move a read-once briefing from inbox/review/ to .zanmai/logs/<YYYY>/<MM>/.")
    pr_archive.add_argument("vault", nargs="?", default=".")
    pr_archive.add_argument("--item-path", required=True, dest="item_path")
    pr_archive.set_defaults(func=cmd_archive_review_item)

    # update -----
    p_update = sub.add_parser("update", help="Bundle-level index touches that follow filing operations.")
    sub_update = p_update.add_subparsers(dest="subcmd", required=True)

    pu_links = sub_update.add_parser("wikilinks", help="Rename [[old-slug]] to [[new-slug]] across markdown files.")
    pu_links.add_argument("vault", nargs="?", default=".")
    pu_links.add_argument("--old", required=True)
    pu_links.add_argument("--new", required=True)
    pu_links.add_argument("--scope", help="Subfolder under the vault to sweep. Defaults to 'inbox'. System paths are hard-excluded.")
    pu_links.set_defaults(func=cmd_update_wikilinks)

    pu_embeds = sub_update.add_parser("embeds", help="Rewrite embed references in a bundle's markdown to point at the shared assets/ folder.")
    pu_embeds.add_argument("vault", nargs="?", default=".")
    pu_embeds.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pu_embeds.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pu_embeds.add_argument("--clear-rename-map", dest="clear_rename_map", action="store_true",
                           help="Wipe the attachment rename map after this run.")
    pu_embeds.set_defaults(func=cmd_update_embeds)

    pu_master = sub_update.add_parser("master-index", help="Regenerate the vault-root INDEX.md.")
    pu_master.add_argument("vault", nargs="?", default=".")
    pu_master.set_defaults(func=cmd_update_master_index)

    # index -----
    p_idx = sub.add_parser("index", help="Vault-index and pattern queries.")
    sub_idx = p_idx.add_subparsers(dest="subcmd", required=True)

    pi_rebuild = sub_idx.add_parser("rebuild", help="Walk the vault, write .zanmai/memory/vault-index.json (Schicht A).")
    pi_rebuild.add_argument("vault", nargs="?", default=".")
    pi_rebuild.add_argument("--scope", help="Subfolder to limit the walk (e.g. _import/PKM).")
    pi_rebuild.add_argument("--quiet", action="store_true")
    pi_rebuild.set_defaults(func=cmd_reindex)

    pi_patterns = sub_idx.add_parser("patterns", help="Aggregate themes/hubs/bundles into .zanmai/memory/patterns.json (Schicht B).")
    pi_patterns.add_argument("vault", nargs="?", default=".")
    pi_patterns.add_argument("--min-count", type=int, default=2, dest="min_count")
    pi_patterns.add_argument("--quiet", action="store_true")
    pi_patterns.set_defaults(func=cmd_patterns)

    pi_find = sub_idx.add_parser("find", help="Query patterns.json for matching themes, bundles, hubs.")
    pi_find.add_argument("vault", nargs="?", default=".")
    pi_find.add_argument("--tokens", required=True, help="Comma-separated tokens.")
    pi_find.set_defaults(func=cmd_find_theme)

    pi_inspect = sub_idx.add_parser("inspect", help="User-visible scan of an import scope. Lists folders, file counts per extension, folder-name tokens, embed references.")
    pi_inspect.add_argument("vault", nargs="?", default=".")
    pi_inspect.add_argument("--scope", required=True)
    pi_inspect.set_defaults(func=cmd_inspect_scope)

    pi_search = sub_idx.add_parser("search", help="Search the vault's text and report how many files were searched.")
    pi_search.add_argument("vault", nargs="?", default=".")
    pi_search.add_argument("--pattern", required=True, help="Regular expression.")
    pi_search.add_argument("--root", action="append", help="Limit to these vault-relative roots. Repeatable.")
    pi_search.add_argument("--ext", action="append", help="Limit to these suffixes (with the dot). Repeatable.")
    pi_search.add_argument("--case-sensitive", dest="case_sensitive", action="store_true")
    pi_search.add_argument("--max-hits", dest="max_hits", type=int, default=200)
    pi_search.set_defaults(func=cmd_index_search)

    # memory -----
    p_mem = sub.add_parser("memory", help="Briefing and operation reports.")
    sub_mem = p_mem.add_subparsers(dest="subcmd", required=True)

    pm_briefing = sub_mem.add_parser("briefing", help="Atomic rebuild of .zanmai/memory/briefing.md.")
    pm_briefing.add_argument("vault", nargs="?", default=".")
    pm_briefing.add_argument("--quiet", action="store_true")
    pm_briefing.set_defaults(func=cmd_briefing)

    pm_report = sub_mem.add_parser("report", help="Write an operation report to .zanmai/logs/<YYYY>/<MM>/.")
    pm_report.add_argument("vault", nargs="?", default=".")
    pm_report.add_argument("--operation", required=True)
    pm_report.add_argument("--slug", required=True)
    pm_report.add_argument("--summary", default="")
    pm_report.add_argument("--scope", default="")
    pm_report.add_argument("--since-minutes", type=int, default=60, dest="since_minutes")
    pm_report.set_defaults(func=cmd_write_report)

    pm_log = sub_mem.add_parser("log", help="Append one line to the activity log in the canonical format.")
    pm_log.add_argument("vault", nargs="?", default=".")
    pm_log.add_argument("--agent", required=True)
    pm_log.add_argument("--activity", required=True)
    pm_log.set_defaults(func=cmd_memory_log)

    pm_curate = sub_mem.add_parser("curate", help="Keep a rules file to its rules: struck entries and long reasoning move to an archive.")
    pm_curate.add_argument("vault", nargs="?", default=".")
    pm_curate.add_argument("--file", required=True, help="Vault-relative path of the memory file.")
    pm_curate.add_argument("--why-lines", type=int, default=4, dest="why_lines",
                           help="A reasoning block longer than this moves to the archive.")
    pm_curate.add_argument("--show", type=int, default=10)
    pm_curate.add_argument("--agent")
    pm_curate.add_argument("--dry-run", action="store_true", dest="dry_run")
    pm_curate.set_defaults(func=cmd_memory_curate)

    pm_rotate = sub_mem.add_parser("rotate", help="Move a chronological log's older months into an archive beside it.")
    pm_rotate.add_argument("vault", nargs="?", default=".")
    pm_rotate.add_argument("--file", default=".zanmai/memory/activity-log.md")
    pm_rotate.add_argument("--keep-months", type=int, default=2, dest="keep_months")
    pm_rotate.add_argument("--dry-run", action="store_true", dest="dry_run")
    pm_rotate.set_defaults(func=cmd_memory_rotate)

    # connection -----
    p_conn = sub.add_parser("connection", help="External-source connections, run by Wong. Cross-platform.")
    sub_conn = p_conn.add_subparsers(dest="subcmd", required=True)

    pco_scan = sub_conn.add_parser("scan", help="Discover connectable host sources for this vault (MCP servers, plugins, CLIs, macOS apps). Informational, registers nothing.")
    pco_scan.add_argument("vault", nargs="?", default=".")
    pco_scan.set_defaults(func=cmd_connection_scan)

    # hook -----
    p_hook = sub.add_parser("hook", help="Claude Code hooks (PreToolUse, PostToolUse, SessionStart, Stop). Invoked by Claude Code via settings.json, not by users directly.")
    sub_hook = p_hook.add_subparsers(dest="subcmd", required=True)

    ph_session = sub_hook.add_parser("session-start", help="SessionStart hook. Reads user.md and vault.json, writes vault-config.md, prints the briefing on stdout.")
    ph_session.set_defaults(func=cmd_hook_session_start)

    ph_kind = sub_hook.add_parser("kind-required", help="PreToolUse Write|Edit. Refuses writes under inbox/<kind>/ without valid kind frontmatter.")
    ph_kind.set_defaults(func=cmd_hook_kind_required)

    ph_perm = sub_hook.add_parser("permission-guard", help="PreToolUse Write|Edit. Hard-blocks writes into the never-do bucket.")
    ph_perm.set_defaults(func=cmd_hook_permission_guard)

    ph_idx = sub_hook.add_parser("index-consistency", help="PostToolUse Write|Edit. Warns when a bundle file is written without being referenced in the bundle INDEX.md.")
    ph_idx.set_defaults(func=cmd_hook_index_consistency)

    ph_dispatch = sub_hook.add_parser("dispatch-guard", help="PreToolUse Agent. Refuses a main-thread expert dispatch that sets run_in_background: false; nested dispatches from inside an expert pass.")
    ph_dispatch.set_defaults(func=cmd_hook_dispatch_guard)

    ph_voice = sub_hook.add_parser("voice-check", help="Stop hook. Blocks a user-facing reply that contains an em-dash so it gets rewritten (runtime companion to style-check.py).")
    ph_voice.set_defaults(func=cmd_hook_voice_check)

    ph_voice_tool = sub_hook.add_parser("voice-check-tool", help="PreToolUse AskUserQuestion. Blocks a menu whose text contains an em-dash so it gets rebuilt.")
    ph_voice_tool.set_defaults(func=cmd_hook_voice_check_tool)

    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
