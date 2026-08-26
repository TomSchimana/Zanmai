#!/usr/bin/env python3
"""zanmai.py: the single CLI for Zanmai vault operations.

Replaces AI-tool-call sequences (Write+Edit+Write+...) with deterministic
state-changes. AI decides (classification, plan); script executes.

Subcommand groups:
    setup, first-time install and validation (init/validate/update)
    snapshot, vault snapshots (create)
    bundle, bundle operations (create, add-file, add-truth, rename)
    asset, non-markdown files into the bundle they belong to (add)
    contact, person and organisation contacts (create)
    notes, daily, weekly and monthly notes (daily, weekly, monthly)
    file, file moves to system folders (trash, archive)
    plan, plan-section maintenance on bundle truth files (clear-section)
    review, read-once briefings on the desk (archive)
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
import contextlib
import io
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ----------------------------------------------------------------------------
# Vault folder names. This is the only place they are spelled out.
#
# Every path this file builds starts from one of these names, never from a
# literal typed at the call site. Rename a folder here and a run over an empty
# vault carries the new name everywhere, which is what makes a rename a change
# instead of a project: the same string used to sit in some two hundred path
# expressions, and each one was a chance to miss one.
#
# What these do NOT cover is prose. Help texts, hook messages, templates and
# the documentation describe a structure rather than address a file, and a
# renamed folder changes the sentence, not one word inside it. Those are
# rewritten by hand, in the same operation that changes a value here. A value
# changed on its own would ship a vault that describes something other than
# what it does.
#
# A folder-shaped word that means something else keeps its literal, and there
# are two kinds of those. `archive` and `trash` are also verbs: `file archive`
# and `file trash` are commands, and the command keeps its name when the folder
# it writes to is renamed. `inbox` is also an ordinary word, one entry in the
# list of generic folder names the naming heuristic ignores, and that list is
# about what people call folders, not about what this vault calls its own.
# Neither is this vault's folder, so neither moves when a folder moves.
# ----------------------------------------------------------------------------

SYSTEM_DIR = "zanmai"           # what the machine keeps; the user never opens it by hand
IMPORT_DIR = "import"           # drop something in and it gets taken up
ARCHIVE_DIR = "archive"         # finished and kept; answers no question any more
HOST_DIR = ".claude"            # what the host reads: skills, agents, settings

# The five that describe what is going on in a head, not where a file type belongs.
FOCUS_DIR = "focus"             # what I want to reach and what I am looking at
DOING_DIR = "doing"             # the desk: work that has an end. The one place that empties.
HABITS_DIR = "habits"           # what has a beat
KNOWLEDGE_DIR = "knowledge"     # everything gathered, no ranking, and it may contradict itself
TRUSTED_DIR = "trusted"         # what I have settled on. Small, curated, one answer.

# Inside the system folder.
SYSTEM_MATERIAL_DIR = f"{SYSTEM_DIR}/system"        # distribution, replaced on update
EXTENSIONS_DIR = f"{SYSTEM_DIR}/extensions"
CONNECTIONS_DIR = f"{SYSTEM_DIR}/connections"
MEMORY_DIR = f"{SYSTEM_DIR}/memory"
DESIGN_DIR = f"{SYSTEM_DIR}/design"   # one folder per brand, update-immune, written by the design work
LOGS_DIR = f"{SYSTEM_DIR}/logs"
HISTORY_DIR = f"{SYSTEM_DIR}/history"       # the snapshot repository, a git dir of its own
RUNTIME_DIR = f"{SYSTEM_DIR}/runtime"
SCRATCH_DIR = f"{SYSTEM_DIR}/temp"          # what the machine puts down mid-job, 30 days
TRASH_DIR = f"{SYSTEM_DIR}/trash"           # what was thrown away, 30 days, restorable
USER_FILE = f"{SYSTEM_DIR}/user.md"
ACTIVITY_LOG_FILE = f"{MEMORY_DIR}/activity-log.md"

# The AI's own list of what is open. Under the system folder because it is the machine's, not the
# user's: "I do not look at my concierge's notepad to see what he still has to do."
# The `.base` suffix is the database format's, not a second folder: a markdown editor that
# understands it renders the rows as a table and as a board grouped by state, so "what is waiting on
# me" is answerable on a phone from the same files, with nothing exported to make the view work.
OPEN_DIR = f"{SYSTEM_DIR}/open.base"

CONTACTS_DIR = "contacts"
PEOPLE_DIR = f"{CONTACTS_DIR}/people"
ORGANISATIONS_DIR = f"{CONTACTS_DIR}/organisations"
CONTACT_FOLDERS = (PEOPLE_DIR, ORGANISATIONS_DIR)

# The journal: the time axis. One bundle per period, four kinds, split by kind rather than nested by
# time, because a week runs across a month boundary and any time-nesting breaks exactly there. The
# year folder under daily, weekly and monthly is grouping only and carries no note of its own; the
# year as a thing is `yearly/<year>/`.
JOURNAL_DIR = "journal"
DAILY_DIR = f"{JOURNAL_DIR}/daily"
WEEKLY_DIR = f"{JOURNAL_DIR}/weekly"
MONTHLY_DIR = f"{JOURNAL_DIR}/monthly"
YEARLY_DIR = f"{JOURNAL_DIR}/yearly"


# Schema-required and -optional fields per kind. Sync with schema/frontmatter-v1.yaml.
COMMON_REQUIRED = ("kind", "slug", "created")
COMMON_OPTIONAL = ("updated", "source", "source_detail", "tags", "mentioned_in")
KIND_FIELDS = {
    "focus": {"required": ("goal", "status"), "optional": ("due",)},
    # The desk. It asks for nothing beyond the common fields on purpose: what clears a bundle off
    # the desk is read from the file dates, not from a field somebody has to keep true.
    "doing": {"required": (), "optional": ("status", "due")},
    "habit": {"required": ("cadence",), "optional": ("last_done",)},
    "knowledge": {"required": (), "optional": ("topic", "status")},
    "contact/person": {"required": (), "optional": ("nickname", "role", "org", "email", "phone", "birthday", "address", "website")},
    "contact/organization": {"required": (), "optional": ("kind_of", "website")},
}

# A routine's frontmatter kind is singular (`habit`), its folder is plural (`habits/`). Every
# other bundle kind spells both the same, which is why the mismatch stayed invisible for so long:
# `bundle create` built its path straight from the kind value and quietly created a second
# `habit/` beside the real one, while the index build, the briefing scan and the structure check
# only ever looked in the plural. A live vault ended up with a filled `habit/` next to an empty
# `habits/`, and the user's routines were invisible to half the system (found 2026-08-05).
# These two functions are the only place that knows about the difference. The previous shape - a
# hand-kept folder list in five places plus one local `kind_map` patch - is exactly what drifted.
KIND_FOLDERS = {"habit": "habits"}
BUNDLE_KINDS = ("focus", "doing", "habit", "knowledge")


def _tags_arg(value: str | None) -> list[str] | None:
    """Comma-separated tags from the command line as a list, or None when the flag was absent.

    Tags used to be settable only afterwards, through a second `bundle edit-file --set` call, and a
    source file without frontmatter therefore landed with no tags at all until someone noticed.
    """
    if value is None:
        return None
    return [t.strip() for t in value.split(",") if t.strip()]


def _kind_folder(kind: str) -> str:
    """Root folder name for a frontmatter kind value."""
    return KIND_FOLDERS.get(kind, kind)


def _folder_kind(folder: str) -> str:
    """Frontmatter kind value for a root folder name."""
    for kind, name in KIND_FOLDERS.items():
        if name == folder:
            return kind
    return folder


# Folder names, in the same order as BUNDLE_KINDS. Derived, never hand-kept.
#
# These are root entries now, not children of one content folder, and that is what makes a bundle
# path two segments instead of three: the kind folder, then the bundle.
BUNDLE_FOLDERS = tuple(_kind_folder(k) for k in BUNDLE_KINDS)

# Every root a user's own material can sit under. Ordered as the concept lists them: where it falls
# in, where it is worked on, where it settles. `import` is deliberately absent, because nothing in
# there has been taken up yet, and so is the system folder, which is the machine's.
USER_ROOTS = (
    JOURNAL_DIR,
    FOCUS_DIR,
    DOING_DIR,
    HABITS_DIR,
    KNOWLEDGE_DIR,
    TRUSTED_DIR,
    ARCHIVE_DIR,
    CONTACTS_DIR,
)



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

    # The caller passes a kind value, the folder may spell it differently, and what comes back is a
    # kind value again because it ends up in frontmatter.
    if bundle_kind:
        candidate = vault / _kind_folder(bundle_kind) / Path(*segments)
        return (candidate if candidate.is_dir() else None), bundle_kind, leaf

    for folder in BUNDLE_FOLDERS:
        candidate = vault / folder / Path(*segments)
        if candidate.is_dir():
            return candidate, _folder_kind(folder), leaf
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
    log = vault / MEMORY_DIR / "activity-log.md"
    if not log.exists():
        return
    line = f"\n## [{_timestamp_log()}] - {agent} - {what}\n"
    with log.open("a", encoding="utf-8") as f:
        f.write(line)


def _index_line_set(index_path: Path, slug: str, summary: str) -> bool:
    """Rewrite the description on an existing member line. True when a line was found.

    `bundle add-file --summary` sets that text once, at filing time, and nothing could change it
    afterwards. A brief that shifts mid-run left every wrong line to be corrected by hand, which is a
    write that skips the frontmatter guard, the index hook and the activity log all at once.
    """
    if not index_path.exists():
        return False
    text = index_path.read_text(encoding="utf-8")
    muster = re.compile(rf"^(\s*-\s*\[\[{re.escape(slug)}\]\])(?:\s*[-:]\s*.*)?$", re.M)
    if not muster.search(text):
        return False
    ersatz = rf"\1 - {summary}" if summary else r"\1"
    index_path.write_text(muster.sub(ersatz, text, count=1), encoding="utf-8")
    return True


def _index_line_remove(index_path: Path, slug: str) -> bool:
    """Take a member line out again. True when one was there.

    The counterpart to `_append_index`, missing until a discarded member had to be removed by hand.
    """
    if not index_path.exists():
        return False
    text = index_path.read_text(encoding="utf-8")
    muster = re.compile(rf"^\s*-\s*\[\[{re.escape(slug)}\]\].*\n?", re.M)
    if not muster.search(text):
        return False
    index_path.write_text(muster.sub("", text, count=1), encoding="utf-8")
    return True


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
    folder = _kind_folder(kind)
    bundle_dir = vault / folder / Path(*segments)
    if bundle_dir.exists():
        print(f"fail: bundle already exists: {bundle_dir}", file=sys.stderr)
        return 1
    bundle_dir.mkdir(parents=True)
    bundle_rel = f"{folder}/{'/'.join(segments)}"
    is_sub_bundle = len(segments) > 1

    additions: dict = {"_title": args.title or slug.replace("-", " ").title()}
    for key in ("source", "source_detail", "goal", "status", "cadence", "due", "topic", "last_done"):
        v = getattr(args, key, None)
        if v:
            additions[key] = v
    tags = _tags_arg(getattr(args, "tags", None))
    if tags:
        additions["tags"] = tags

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
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
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
    # Same reasoning as provenance: stated on the command line it wins, because the caller knows what
    # the file does not say about itself. A source file with no frontmatter otherwise arrives untagged
    # and needs a second `edit-file` call, which is what happened three times in one filing run.
    tags = _tags_arg(getattr(args, "tags", None))
    if tags:
        overrides["tags"] = tags
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
    """Copy a non-markdown file into the bundle it belongs to.

    Target shape: `<kind>/<slug>/<basename>`, flat beside the bundle's own markdown. There is no
    shared attachment folder and no `files/` inside the bundle either, because a folder that sorts
    by file type cuts the one thing apart that the bundle exists to hold together: the recording,
    the transcript, the scan and the note about them are one matter, and a PDF is not an appendix
    to markdown, it is another file about the same thing.

    `--target-name` lets the caller rename on copy, which is what a set of phone photos with
    identical generic names needs. It may carry a sub-path when the sub-folder is a nameable thing
    rather than a container. `--overwrite` allows replacement of an existing target; otherwise the
    new name gets an `-imported` suffix.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.source).resolve()

    bundle_dir, _kind, _leaf = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if bundle_dir is None:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        print("hint: run `bundle create --kind <k> --slug <slug>` first", file=sys.stderr)
        return 1

    target_name = args.target_name or source.name
    target = Path(os.path.normpath(bundle_dir / target_name))
    # Resolving first is what keeps a name with `..` in it from writing outside the bundle.
    if bundle_dir not in target.parents:
        print(f"fail: target name must stay inside the bundle: {target_name}", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not args.overwrite:
        stem, dot, ext = target.name.rpartition(".")
        target = target.parent / (f"{stem}-imported.{ext}" if dot else f"{target.name}-imported")
    shutil.copy2(source, target)

    # Record any rename (original -> final) so `update embeds` can resolve
    # plan-driven attachment renames automatically. Stable across import waves
    # until cleared via `update embeds --clear-rename-map`.
    if target.name != source.name:
        _record_rename(vault, source.name, target.name)

    rel = target.relative_to(vault).as_posix()
    _append_activity_log(vault, "zanmai.py", f"attachment {target.name} -> {rel}")
    print(f"ok: attachment at {rel}")
    return 0


def _update_master_index(vault: Path) -> None:
    """Regenerate vault-root INDEX.md from existing bundles."""
    master = vault / "INDEX.md"
    if not master.exists():
        return
    text = master.read_text(encoding="utf-8")

    def list_bundles(kind: str) -> list[str]:
        kind_dir = vault / _kind_folder(kind)
        if not kind_dir.is_dir():
            return []
        bundles = sorted(p.name for p in kind_dir.iterdir() if p.is_dir())
        return bundles

    def list_single_notes(kind: str) -> list[str]:
        kind_dir = vault / _kind_folder(kind)
        if not kind_dir.is_dir():
            return []
        return sorted(p.stem for p in kind_dir.iterdir() if p.is_file() and p.suffix == ".md")

    def list_contacts(sub: str) -> list[str]:
        contacts_dir = vault / CONTACTS_DIR / sub
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
        orgs = list_contacts("organisations")
        lines = ["## Contacts", "",
                 "Single files per person and organisation.", "",
                 f"### People (`{PEOPLE_DIR}/`)", ""]
        if people:
            for p in people:
                lines.append(f"- [[{p}]]")
        else:
            lines.append("(empty)")
        lines += ["", f"### Organisations (`{ORGANISATIONS_DIR}/`)", ""]
        if orgs:
            for o in orgs:
                lines.append(f"- [[{o}]]")
        else:
            lines.append("(empty)")
        return "\n".join(lines) + "\n"

    def render_flat_root(header: str, folder: str, intro: str) -> str:
        """A root that holds bundles directly, with no kind folder in between."""
        root = vault / folder
        entries = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
        singles = sorted(p.stem for p in root.iterdir()
                         if p.is_file() and p.suffix == ".md" and p.stem != "INDEX") if root.is_dir() else []
        lines = [f"## {header}", "", intro, ""]
        if not entries and not singles:
            lines.append("(empty)")
        else:
            for e in entries + singles:
                lines.append(f"- [[{e}]]")
        return "\n".join(lines) + "\n"

    new_focus = render_section("Focus", "focus",
                               f"What you want to reach and what you are looking at. See `{FOCUS_DIR}/`.")
    new_doing = render_flat_root(
        "Doing", DOING_DIR,
        "The desk: work that has an end, with every draft of it together in one bundle. You put "
        f"things here and so does Zanmai. See `{DOING_DIR}/`.")
    new_habits = render_section("Habits", "habit", f"What has a beat. See `{HABITS_DIR}/`.")
    new_knowledge = render_section(
        "Knowledge", "knowledge",
        "Everything gathered, with no ranking, and it is allowed to contradict itself. The default "
        "place for anything that does not clearly belong elsewhere, and the place where most of it "
        f"stays. See `{KNOWLEDGE_DIR}/`.")
    new_trusted = render_flat_root(
        "Trusted", TRUSTED_DIR,
        "What you have settled on and what cannot be worked out from the files themselves. Small, "
        f"curated, one answer per question. See `{TRUSTED_DIR}/`.")
    new_archive = render_flat_root(
        "Archive", ARCHIVE_DIR,
        "Finished and kept: the document from outside and your own completed piece. It answers no "
        f"question any more, and nothing has to end up here. See `{ARCHIVE_DIR}/`.")
    new_contacts = render_contacts()

    # Each section is replaced up to the next heading, so the order here is the order in the file
    # that `_render_master_index` writes. A section whose successor heading is missing is left
    # alone rather than swallowing the rest of the file.
    for pattern, replacement in (
        (r"## Focus\n.*?(?=\n## Doing)", new_focus),
        (r"## Doing\n.*?(?=\n## Habits)", new_doing),
        (r"## Habits\n.*?(?=\n## Knowledge)", new_habits),
        (r"## Knowledge\n.*?(?=\n## Trusted)", new_knowledge),
        (r"## Trusted\n.*?(?=\n## Archive)", new_trusted),
        (r"## Archive\n.*?(?=\n## Contacts)", new_archive),
        (r"## Contacts\n.*?(?=\n## Import)", new_contacts),
    ):
        text = re.sub(pattern, replacement + "\n", text, flags=re.DOTALL)

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
#   - the system material: distribution files, replaced on update.
#   - the snapshot history: immutable rollback points, must stay bit-identical.
#   - the logs: append-only history (operation reports, plans, gap logs).
#     Old slug names appear here as historical record, by design.
#   - the activity log: append-only activity history. Same reason as the logs.
#   - the import folder: source material stays verbatim until the user's trash
#     question at the end of an import run is answered.
#   - the trash: trashed files keep the wikilinks they had when trashed,
#     so a future restore lands in a coherent state.
#   - the archive: what is kept there keeps the state it was finished in.
_WIKILINK_OPS_EXCLUDED_PREFIXES = (
    f"{SYSTEM_MATERIAL_DIR}/",
    f"{HISTORY_DIR}/",
    f"{LOGS_DIR}/",
    f"{IMPORT_DIR}/",
    f"{TRASH_DIR}/",
    f"{ARCHIVE_DIR}/",
)
_WIKILINK_OPS_EXCLUDED_FILES = (
    ACTIVITY_LOG_FILE,
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

    Scope: defaults to the whole vault, because the user's material is no longer under one folder.
    Pass `--scope <path>` to narrow it. Hard-excluded paths (see
    `_WIKILINK_OPS_EXCLUDED_PREFIXES` and `_WIKILINK_OPS_EXCLUDED_FILES`) are never rewritten
    regardless of the requested scope: the history, the logs, the activity log, the trash, the
    archive and the import folder must stay verbatim.
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

    scope_root = vault / args.scope if args.scope else vault
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
    candidates = [vault / folder / f"{args.slug}.md" for folder in CONTACT_FOLDERS]
    target = next((c for c in candidates if c.is_file()), None)
    if target is None:
        print(f"fail: no contact '{args.slug}' under {CONTACTS_DIR}/", file=sys.stderr)
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
    (f"{MEMORY_DIR}/general.md", 400),
    (f"{MEMORY_DIR}/agents/*/lessons.md", 400),
    (f"{MEMORY_DIR}/technique/*.md", 400),
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
    """Recordings wait in the import folder like everything else.

    There is no `recordings/` sub-folder any more: the folder is the automation, and the type of a
    file decides its route, not where somebody happened to put it. A phone that syncs into a folder
    of its own is fine, because the scan walks whatever structure it finds.
    """
    d = vault / IMPORT_DIR
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


def _recording_date(path: Path) -> tuple[datetime, str]:
    """The day a recording was made, and how that was determined.

    Same signal `voice scan` already orders by: the file's own date first, a timestamp
    parsed from the name second. A running number or no signal at all cannot date
    anything, today stands in and the caller is told why rather than presenting it as
    the recording's own date.
    """
    rank, value, basis, _shown = _recording_order_key(path)
    if rank in (0, 1):
        return datetime.fromtimestamp(value), basis
    return datetime.now(), "no date signal, using today"


def _pending_recordings(vault: Path) -> list[Path]:
    """Every recording waiting in the import folder, sub-folders included."""
    folder = _recordings_dir(vault)
    return sorted((f for f in folder.rglob("*")
                   if f.is_file() and f.suffix.lower() in AUDIO_EXTS),
                  key=_recording_order_key)


# What a file in the import folder is, and therefore which way it goes. The type decides the route,
# never a subfolder: the folder is the automation, so anything anyone drops in is taken.
_IMPORT_ROUTES = (
    ("recording", AUDIO_EXTS, "read it out, no question asked"),
    ("video", (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"),
     "ask what it is for: a cut, or only the words spoken in it"),
    ("document", (".pdf", ".doc", ".docx", ".pages", ".odt", ".rtf"), "ask what to do with it"),
    ("presentation", (".ppt", ".pptx", ".key"), "ask what to do with it"),
    ("sheet", (".xls", ".xlsx", ".numbers", ".csv"), "ask what to do with it"),
    ("image", (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tiff", ".svg"), "ask what to do with it"),
    ("text", (".md", ".markdown", ".txt"), "read it and file it"),
    ("link", (".url", ".webloc", ".html", ".htm"), "look at the page, ask before reading a video out"),
    ("archive", (".zip", ".tar", ".gz", ".7z", ".rar"), "unpack into the scratch area first"),
)


# The container tells you nothing about the content: .mp4, .mov and .m4a all carry either sound
# alone or sound with picture, and both lists below have to contain them or one of the two cases
# would be unroutable. Extension alone therefore decided the wrong thing every time a video was
# dropped, because "recording" comes first and won: a screen recording was read out as a voice
# note. The file itself knows, so it is asked.
_AMBIGUOUS_MEDIA = {".mp4", ".mov", ".m4a", ".m4b", ".m4v", ".webm", ".mkv", ".ogg", ".3gp"}


def _has_video_stream(path: Path) -> bool | None:
    """Whether this file carries a picture. None where nothing can measure it."""
    probe = shutil.which("ffprobe") or shutil.which("ffmpeg")
    if not probe:
        return None
    try:
        r = subprocess.run([probe, "-v", "error", "-select_streams", "v",
                            "-show_entries", "stream=codec_type,disposition=attached_pic",
                            "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    for zeile in (r.stdout or "").strip().splitlines():
        teile = zeile.split(",")
        # Cover art in an audio file is a video stream too, and it is not a picture anyone films.
        if teile and teile[0] == "video" and (len(teile) < 2 or teile[1].strip() != "1"):
            return True
    return False


def _import_route(path: Path) -> tuple[str, str]:
    """The kind of a dropped file and what happens to it. Unknown is a kind, not a gap."""
    suffix = path.suffix.lower()
    if suffix in _AMBIGUOUS_MEDIA:
        hat_bild = _has_video_stream(path)
        if hat_bild is True:
            # A picture inside does not mean a video is wanted. Somebody recording themselves for
            # a spoken note gets a picture whether they want one or not, and reading the words out
            # is then the right answer. So this asks rather than deciding.
            return "video", "ask what it is for: a cut, or only the words spoken in it"
        if hat_bild is False:
            return "recording", "read it out, no question asked"
        # Nothing could look inside. Say that rather than guessing from the name, because guessing
        # wrong here means a video gets transcribed and filed as a spoken note.
        return "media", "ask: nothing on this machine can tell whether it carries a picture"
    for kind, suffixes, verhalten in _IMPORT_ROUTES:
        if suffix in suffixes:
            return kind, verhalten
    return "unknown", "say so, never quietly leave it lying"


def _import_pending(vault: Path) -> list[Path]:
    """Everything waiting in the import folder, oldest first, subfolders included.

    Subfolders are walked rather than respected. Whatever structure something arrives in is the
    sender's, not an instruction, and the point of the folder is that nobody has to sort before
    dropping.
    """
    root = vault / IMPORT_DIR
    if not root.is_dir():
        return []
    return sorted((f for f in root.rglob("*")
                   if f.is_file() and not f.name.startswith(".")),
                  key=_recording_order_key)


def cmd_import_scan(args: argparse.Namespace) -> int:
    """What is waiting in the import folder, oldest first, with the route for each.

    Oldest first and read whole before anything is processed: several files dropped in a row are
    usually one train of thought, and the later one can withdraw the earlier.
    """
    vault = Path(args.vault).resolve()
    files = _import_pending(vault)
    if not files:
        print(f"empty: nothing waiting in {IMPORT_DIR}/")
        return 0
    nach_art: dict[str, int] = {}
    for f in files:
        kind, verhalten = _import_route(f)
        nach_art[kind] = nach_art.get(kind, 0) + 1
        _rank, _value, basis, shown = _recording_order_key(f)
        rel = f.relative_to(vault).as_posix()
        print(f"{shown:>16}  {kind:>12}  {rel}")
        if args.verbose:
            print(f"{'':>16}  {'':>12}  {verhalten}")
    zusammen = ", ".join(f"{count} {kind}" for kind, count in sorted(nach_art.items()))
    print(f"ok: {len(files)} file(s) waiting in {IMPORT_DIR}/ ({zusammen})")
    print("    read all of them before processing any: the later one can withdraw the earlier.")
    clash = _recording_order_disagreement(files)
    if clash:
        print(f"    dates and names disagree ({clash}). Read the order out of the contents "
              f"and say so, rather than reporting an order as certain.")
    return 0


def cmd_voice_scan(args: argparse.Namespace) -> int:
    """What is waiting to be transcribed, oldest first, with the count said out loud.

    Oldest first because several notes recorded in a row are usually one train of
    thought, and the order they were spoken in is the order they make sense in.
    """
    vault = Path(args.vault).resolve()
    folder = _recordings_dir(vault)
    files = _pending_recordings(vault)
    other = sorted(f.name for f in folder.rglob("*")
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
    print(f"ok: {len(files)} recording(s) waiting in {IMPORT_DIR}/"
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
    patterns = vault / MEMORY_DIR / "patterns.json"
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
    org_folder = vault / ORGANISATIONS_DIR
    if org_folder.is_dir():
        for f in sorted(org_folder.glob("*.md")):
            org_names[f.stem], _fm = read_name(f)

    # (rank, term). The house names first: they work before the vault holds anything,
    # and a spoken instruction names a specialist.
    ranked: list[tuple[int, str]] = [(10 ** 6, "Zanmai")]
    ranked += [(10 ** 6, name.capitalize()) for name, _a, _m in _ROSTER]

    for folder, is_person in ((vault / PEOPLE_DIR, True),
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

    for kind in BUNDLE_FOLDERS:
        folder = vault / kind
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
    folder = vault / RUNTIME_DIR / "whisper"
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
        missing.append("a model in zanmai/runtime/whisper/ (about 1.6 GB, fetched once)")
    if missing:
        print("fail: cannot transcribe, and nothing will be guessed instead. Missing:",
              file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    work = vault / SCRATCH_DIR / "voice"
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
    """Move a processed recording out of the import folder into the day it was spoken on.

    Out of the import folder so it cannot be transcribed twice, and kept rather than deleted: it is
    the user's own recording, and a transcript is a reading of it, not a replacement for it. It
    lands in the day's bundle beside whatever came out of it, because what was said on a day belongs
    to that day, and because keeping the original next to the reading is what makes a garbled word
    repairable years later.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1
    stamp = datetime.fromtimestamp(source.stat().st_mtime)
    target_dir = vault / DAILY_DIR / stamp.strftime("%Y") / stamp.strftime("%Y-%m-%d")
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


def cmd_voice_journal_append(args: argparse.Namespace) -> int:
    """Append text to the daily note for the day a recording was made, not the day it is read.

    A recording processed days after it was spoken still belongs to the day it was
    spoken on: the words were true then, and misplacing "heute war kein guter Tag" a
    week later reads as if it happened on the wrong day. The date is derived here, from
    the recording itself, so the caller never has to work it out or remember to pass it.
    """
    vault = Path(args.vault).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = vault / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1
    date, basis = _recording_date(source)
    rel = _journal_append(vault, _journal_note(vault, "daily", date), args.text,
                          "voice journal append")
    print(f"ok: appended to {rel} (dated by {basis})")
    return 0


def cmd_memory_log(args: argparse.Namespace) -> int:
    r"""Append one line to the activity log in the canonical format.

    Hand-written appends drifted in format, which broke the one thing the log is
    for: `grep "^## \["` parsing cleanly.
    """
    vault = Path(args.vault).resolve()
    log = vault / MEMORY_DIR / "activity-log.md"
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
    hits = [p for p in vault.glob(f"**/{name}") if p.is_file() and not p.relative_to(vault).as_posix().startswith((f"{SYSTEM_DIR}/", ".claude/", ".git/"))]
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
    roots = [vault / r for r in (args.root or USER_ROOTS + (IMPORT_DIR, SYSTEM_DIR))]
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
# result lived in a folder for finished things, the working files lived in the
# scratch area and the open question lived nowhere at all, so it died when the
# session did. Every one
# of those is a different container with a different lifetime, and the user paid
# for it: a specialist re-briefed from scratch every round, decisions taken three
# weeks ago that nobody could name afterwards, and no figure for what any of it
# had cost.
#
# The object is a row in a database the user can open and answer in, plus a page
# holding the long form. The row is CSV and the page is markdown, so both stay
# readable in any editor
# with no export step, which is what makes "what is waiting on me" answerable
# away from the desk.
# ---------------------------------------------------------------------------

WORK_FIELDS = [
    ("id", "text", None, True),
    ("work", "text", None, False),
    ("state", "select", ["open", "waiting on you", "done"], False),
    ("owner", "text", None, False),
    ("waiting for", "text", None, False),
    ("deliverable", "text", None, False),
    ("workshop", "text", None, False),
    ("updated", "date", None, False),
    ("due", "date", None, False),
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
MACHINE_LOCAL_PATHS = (RUNTIME_DIR, SCRATCH_DIR)
BULKY_PATHS = (HISTORY_DIR,)

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


def _work_vault(args: argparse.Namespace) -> Path:
    """The vault a work command acts on: the root, never the folder someone happens to stand in.

    Found 2026-08-26 on the live vault: a `work` call made from inside `doing/<slug>/` created a
    second, empty `zanmai/open.base` there, because the default was the literal `.`. A work object
    written into it would have been invisible to every later `work list`, which is the one thing
    this database exists to prevent.
    """
    start = Path(args.vault) if getattr(args, "vault", None) else Path.cwd()
    wurzel = _find_vault_root(start)
    return wurzel if wurzel is not None else start.resolve()


def _work_wanted_id(args: argparse.Namespace) -> str:
    """The id, given either as `--id` or as the first positional. Both, because the flag is what
    the skills write and the bare id is what a person types."""
    return (getattr(args, "id", None) or getattr(args, "id_pos", None) or "").strip()


def _work_base(vault: Path) -> Path:
    return vault / OPEN_DIR


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
        _work_migrate(csv_path, schema_path, headers)
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


def _work_migrate(csv_path: Path, schema_path: Path, headers: list[str]) -> None:
    """Give a database made by an earlier version the fields a later one added.

    Without this it keeps its old columns for good: the reader takes the header row as it finds it
    and the writer writes that same row back, so a field added later is dropped on every save and
    never says so. Existing rows get the field empty, which is what an unset date should look like.
    """
    import csv as _csv
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        vorhanden = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    fehlend = [h for h in headers if h not in vorhanden]
    if not fehlend:
        return
    neu = vorhanden + fehlend
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=neu)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in neu})
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bekannt = {f.get("name") for f in schema.get("fields", [])}
    for name, ftype, options, hidden in WORK_FIELDS:
        if name in bekannt:
            continue
        feld = {"id": _work_uuid(f"field:{name}"), "name": name, "type": ftype}
        if options:
            feld["options"] = [
                {"id": _work_uuid(f"option:{name}:{value}"), "value": value} for value in options
            ]
        if hidden:
            feld["hidden"] = True
        schema.setdefault("fields", []).append(feld)
        for view in schema.get("views", []):
            if view.get("type") == "table" and isinstance(view.get("columnOrder"), list):
                view["columnOrder"].append(feld["id"])
    schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


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
    vault = _work_vault(args)
    titel = (args.title or args.title_pos or "").strip()
    if not titel:
        print("fail: no title. Give it as `work open \"the title\"` or as `--title \"the title\"`.",
              file=sys.stderr)
        return 1
    if args.due and not _task_date_ok(args.due):
        print("fail: --due expects YYYY-MM-DD", file=sys.stderr)
        return 1
    rows, headers = _work_read(vault)
    row_id = _work_uuid(f"{_timestamp_log()}:{titel}")
    row = {h: "" for h in headers}
    row.update({
        "id": row_id, "work": titel, "state": "open", "owner": args.owner or "",
        "deliverable": args.deliverable or "", "workshop": args.workshop or "",
        "updated": _today(), "due": args.due or "",
    })
    rows.append(row)
    _work_write(vault, rows, headers)
    page = _work_page(vault, row_id)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f"# {titel}\n\n"
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
    _append_activity_log(vault, args.owner or "zanmai.py", f"opened work '{titel}' ({row_id[:8]})")
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
    vault = _work_vault(args)
    rows, headers = _work_read(vault)
    wanted = _work_wanted_id(args)
    if not wanted:
        print("fail: no id. Give it as `work <cmd> <id>` or as `--id <id>`.", file=sys.stderr)
        return 1
    row = _work_find(rows, wanted)
    if row is None:
        print(f"fail: no single work object matching id '{wanted}'", file=sys.stderr)
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
    vault = _work_vault(args)
    rows, headers = _work_read(vault)
    wanted = _work_wanted_id(args)
    if not wanted:
        print("fail: no id. Give it as `work <cmd> <id>` or as `--id <id>`.", file=sys.stderr)
        return 1
    row = _work_find(rows, wanted)
    if row is None:
        print(f"fail: no single work object matching id '{wanted}'", file=sys.stderr)
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
    vault = _work_vault(args)
    rows, headers = _work_read(vault)
    wanted = _work_wanted_id(args)
    if not wanted:
        print("fail: no id. Give it as `work <cmd> <id>` or as `--id <id>`.", file=sys.stderr)
        return 1
    row = _work_find(rows, wanted)
    if row is None:
        print(f"fail: no single work object matching id '{wanted}'", file=sys.stderr)
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
    if args.due:
        if not _task_date_ok(args.due):
            print("fail: --due expects YYYY-MM-DD", file=sys.stderr)
            return 1
        row["due"] = args.due
    _work_touch(row)
    _work_write(vault, rows, headers)
    who = f"{args.agent}: " if args.agent else ""
    _work_append_section(_work_page(vault, row["id"]), "Log", f"- {_timestamp_log()} {who}{args.note}")
    print(f"ok: logged on {row['id'][:8]} (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_done(args: argparse.Namespace) -> int:
    vault = _work_vault(args)
    rows, headers = _work_read(vault)
    wanted = _work_wanted_id(args)
    if not wanted:
        print("fail: no id. Give it as `work <cmd> <id>` or as `--id <id>`.", file=sys.stderr)
        return 1
    row = _work_find(rows, wanted)
    if row is None:
        print(f"fail: no single work object matching id '{wanted}'", file=sys.stderr)
        return 1
    row["state"] = "done"
    row["waiting for"] = ""
    _work_touch(row)
    _work_write(vault, rows, headers)
    _work_append_section(_work_page(vault, row["id"]), "Log", f"- {_timestamp_log()} closed")
    _append_activity_log(vault, args.agent or "zanmai.py", f"closed work '{row.get('work')}' ({row['id'][:8]})")
    print(f"ok: {row['id'][:8]} closed (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_show(args: argparse.Namespace) -> int:
    """One work object, whole: the row and the page under it.

    `list` prints a short id and every other command takes one, so the one thing missing was a way
    to read what that id stands for. Without it the only route to the content was the page folder
    and its full uuid, which is the machine's own filing and not something anyone should have to
    know. Found 2026-08-26, when a live session went looking for it and had to `ls` the folder.
    """
    vault = _work_vault(args)
    rows, _headers = _work_read(vault)
    wanted = _work_wanted_id(args)
    if not wanted:
        print("fail: no id. Give it as `work show <id>` or as `--id <id>`.", file=sys.stderr)
        return 1
    row = _work_find(rows, wanted)
    if row is None:
        print(f"fail: no single work object matching id '{wanted}'", file=sys.stderr)
        return 1
    print(f"{row.get('work','')}")
    print(f"  id        {row.get('id','')}")
    for feld in ("state", "owner", "due", "updated", "deliverable", "workshop", "waiting for"):
        if row.get(feld):
            print(f"  {feld:9} {row[feld]}")
    page = _work_page(vault, row["id"])
    if page.is_file():
        print()
        print(page.read_text(encoding="utf-8").rstrip())
    else:
        print("\n(no page on disk for this object)")
    return 0


def cmd_work_list(args: argparse.Namespace) -> int:
    """What is open, and what is waiting on the user. Prints the denominator."""
    vault = _work_vault(args)
    rows, _headers = _work_read(vault)
    wanted = (args.state or "").strip().lower()
    shown = 0
    for row in sorted(rows, key=lambda r: (r.get("state") != "waiting on you", r.get("updated") or "")):
        if wanted and str(row.get("state", "")).lower() != wanted:
            continue
        shown += 1
        line = f"{row.get('id','')[:8]}  {str(row.get('state','')):14}  {row.get('work','')}"
        if row.get("due"):
            line += f"  (due {row['due']})"
        if row.get("owner"):
            line += f"  [{row['owner']}]"
        print(line)
        if row.get("waiting for"):
            print(f"          waiting for: {row['waiting for']}")
    waiting = sum(1 for r in rows if r.get("state") == "waiting on you")
    print(f"ok: {shown} of {len(rows)} work object(s) shown; {waiting} waiting on the user")
    return 0


# --- The brand, and the gate in front of it --------------------------------
#
# One brand file per brand, under the user's own folders because it is theirs to read and to
# disagree with, and `trusted/` is already defined as what they have settled on. Shuri writes it;
# Carol, Loki and Luis read it and produce from it.
#
# The gate exists because a piece rendered against an invented colour looks finished and is wrong,
# and by then the render time and, with generated imagery, the money are already spent. So the
# check runs before the dispatch, not inside it.
#
# What counts as unfilled is the template's own angle-bracket placeholder. That is deliberate: an
# empty field says "not decided yet", where a plausible default would quietly make a decision the
# user never made, and nothing downstream could tell the two apart afterwards.

BRAND_DIR = f"{TRUSTED_DIR}/brands"
_BRAND_PLACEHOLDER_RE = re.compile(r"<[^<>\n]{2,}>")


def _brand_root(vault: Path) -> Path:
    return vault / BRAND_DIR


def _brand_file(vault: Path, name: str) -> Path:
    return _brand_root(vault) / name / "design.md"


def _brand_names(vault: Path) -> list[str]:
    root = _brand_root(vault)
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if (d / "design.md").is_file())


def _brand_frontmatter(text: str) -> dict:
    """The token block, read without a YAML library.

    Two nesting levels is all the format uses (`typography.body-md.fontSize`, `components.button.
    padding`), so an indentation reader covers it and the distribution keeps its one dependency
    rule: no library for a format we can read in twenty lines.
    """
    block = _frontmatter_block(text)
    if not block:
        return {}
    daten: dict = {}
    eins: dict | None = None
    zwei: dict | None = None
    liste: list | None = None

    def wert_von(roh: str) -> str:
        # A comment starts at a `#` that follows whitespace. A `#` that opens the value is a colour,
        # which is the whole reason this is not a plain split.
        return re.sub(r"\s+#.*$", "", roh).strip().strip('"').strip("'")

    for zeile in block.splitlines()[1:-1]:
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        einzug = len(zeile) - len(zeile.lstrip())
        if liste is not None and zeile.lstrip().startswith("- "):
            liste.append(wert_von(zeile.lstrip()[2:]))
            continue
        if liste and einzug >= 4:
            # The object form of an omitted section: `- section: x` then an indented `reason:`.
            liste[-1] = f"{liste[-1]}, {wert_von(zeile.strip())}"
            continue
        name, _, roh = zeile.strip().partition(":")
        name, wert = name.strip(), wert_von(roh)
        if einzug == 0:
            eins = zwei = liste = None
            if wert in ("[]", "{}"):
                daten[name] = [] if wert == "[]" else {}
            elif wert:
                daten[name] = wert
            elif name == "omitted":
                daten[name] = liste = []
            else:
                daten[name] = eins = {}
        elif einzug == 2 and isinstance(eins, dict):
            zwei = None
            if wert:
                eins[name] = wert
            else:
                eins[name] = zwei = {}
        elif einzug >= 4 and isinstance(zwei, dict):
            zwei[name] = wert
    return daten


def _brand_rgb(wert: str) -> tuple[int, int, int] | None:
    """A hex colour as three channels. Other CSS forms are valid in the format and simply not
    measured here, which is said out loud rather than guessed at."""
    treffer = re.fullmatch(r"#([0-9a-fA-F]{3})([0-9a-fA-F]{3})?[0-9a-fA-F]{0,2}", wert.strip())
    if not treffer:
        return None
    roh = wert.strip().lstrip("#")
    if len(roh) in (3, 4):
        roh = "".join(z * 2 for z in roh[:3])
    return tuple(int(roh[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _brand_contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG contrast ratio. Text under 4.5 is unreadable for someone, and that is measurable
    rather than a matter of taste, which is exactly why it belongs in a check and not in a review."""
    def leuchtdichte(farbe: tuple[int, int, int]) -> float:
        kanaele = []
        for wert in farbe:
            v = wert / 255
            kanaele.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * kanaele[0] + 0.7152 * kanaele[1] + 0.0722 * kanaele[2]
    hell, dunkel = sorted((leuchtdichte(a), leuchtdichte(b)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


def _brand_findings(daten: dict) -> list[str]:
    """What is weak about this brand as a system, beyond which fields are still empty.

    A brand strategist is asked what is missing, not only whether the file parses, so this is the
    part that says a two-level type scale will be invented at build time and that a button nobody
    can read is a defect with a number on it.
    """
    befunde: list[str] = []

    def gesetzt(wert) -> bool:
        return bool(wert) and not _BRAND_PLACEHOLDER_RE.search(str(wert))

    farben = {k: v for k, v in (daten.get("colors") or {}).items() if gesetzt(v)}
    if not farben.get("primary"):
        befunde.append("no primary colour, which is the one value the format requires")

    stufen = [k for k, v in (daten.get("typography") or {}).items()
              if isinstance(v, dict) and gesetzt(v.get("fontFamily")) and gesetzt(v.get("fontSize"))]
    if not stufen:
        befunde.append("no typography level is pinned; every size will be invented per piece")
    elif len(stufen) < 5:
        befunde.append(f"only {len(stufen)} typography level(s) pinned, most brands need nine "
                       f"to fifteen; what is missing gets invented differently in every piece")

    abstaende = {k: v for k, v in (daten.get("spacing") or {}).items() if gesetzt(v)}
    if not abstaende:
        befunde.append("no spacing scale, so whitespace is decided per piece and nothing lines up")
    elif not ({"gutter", "margin"} & set(abstaende)):
        befunde.append("spacing has no gutter or margin, the two values a layout actually needs")

    if not any(gesetzt(v) for v in (daten.get("rounded") or {}).values()):
        befunde.append("no corner radii, not even `none`; sharp is a decision worth writing down")

    for eintrag in (daten.get("omitted") or []):
        if isinstance(eintrag, str) and eintrag.strip("- ") and "reason" not in str(eintrag):
            befunde.append(f"'{eintrag}' is omitted without a reason on the record")

    # Contrast, measured where both sides of a pair resolve to a hex value.
    def aufloesen(wert: str) -> str:
        if wert.startswith("{") and wert.endswith("}"):
            teile = wert[1:-1].split(".")
            knoten: object = daten
            for teil in teile:
                knoten = (knoten or {}).get(teil) if isinstance(knoten, dict) else None
            return str(knoten or "")
        return wert

    for name, eigenschaften in (daten.get("components") or {}).items():
        if not isinstance(eigenschaften, dict):
            continue
        grund = _brand_rgb(aufloesen(str(eigenschaften.get("backgroundColor", ""))))
        text = _brand_rgb(aufloesen(str(eigenschaften.get("textColor", ""))))
        if grund and text:
            verhaeltnis = _brand_contrast(grund, text)
            if verhaeltnis < 4.5:
                befunde.append(f"{name}: text on its own background is {verhaeltnis:.1f}:1, "
                               f"below the 4.5:1 that ordinary text needs")
    return befunde


def _brand_named(text: str) -> bool:
    """Has anybody actually started this brand, or is it the shipped template untouched?

    The name is the one field the format itself requires, so it is the honest test. A file whose
    name is still the placeholder is a form, not a brand, and building against it would mean
    inventing every value in it.
    """
    for zeile in _frontmatter_block(text).splitlines():
        if zeile.startswith("name:"):
            wert = zeile.split(":", 1)[1].strip().strip("\"'")
            return bool(wert) and not _BRAND_PLACEHOLDER_RE.fullmatch(wert)
    return False


def _brand_gaps(text: str) -> list[str]:
    """The fields still carrying a placeholder, named by the section they sit in."""
    gaps: list[str] = []
    section = "(top)"
    for zeile in text.splitlines():
        if zeile.startswith("## "):
            section = zeile[3:].strip()
            continue
        if _BRAND_PLACEHOLDER_RE.search(zeile):
            kurz = " ".join(zeile.strip("- ").split())[:60]
            gaps.append(f"{section}: {kurz}")
    return gaps


def cmd_brand_check(args: argparse.Namespace) -> int:
    """Is there a brand to build against? Exit 1 when there is none, so a caller can gate on it."""
    vault = Path(args.vault).resolve()
    namen = [n for n in _brand_names(vault)
             if _brand_named(_brand_file(vault, n).read_text(encoding="utf-8"))]
    if args.brand:
        namen = [n for n in namen if n == args.brand]
    if not namen:
        gesucht = f" named '{args.brand}'" if args.brand else ""
        print(f"fail: no brand{gesucht} under {BRAND_DIR}/", file=sys.stderr)
        print("  Shuri establishes one from the user's own material (logo, an existing document, "
              "a presentation, a website).", file=sys.stderr)
        return 1

    unvollstaendig = 0
    for name in namen:
        pfad = _brand_file(vault, name)
        text = pfad.read_text(encoding="utf-8")
        gaps = _brand_gaps(text)
        befunde = _brand_findings(_brand_frontmatter(text))
        rel = pfad.relative_to(vault).as_posix()
        if not gaps and not befunde:
            print(f"ok: {name} ({rel}), nothing left open")
            continue
        unvollstaendig += 1
        print(f"ok: {name} ({rel}), {len(gaps)} field(s) not decided yet, "
              f"{len(befunde)} thing(s) the brand cannot answer")
        for befund in befunde:
            print(f"  ! {befund}")
        for gap in gaps[:args.limit]:
            print(f"    {gap}")
        if len(gaps) > args.limit:
            print(f"    ... plus {len(gaps) - args.limit} open field(s)")
    if unvollstaendig:
        print("A piece can be built on this, but everything above is a value somebody would "
              "otherwise invent, differently in each piece. Shuri settles them.")
    return 0


def cmd_brand_list(args: argparse.Namespace) -> int:
    """Every brand that exists, with where it lives."""
    vault = Path(args.vault).resolve()
    namen = _brand_names(vault)
    for name in namen:
        print(f"{name}  {_brand_file(vault, name).relative_to(vault).as_posix()}")
    print(f"ok: {len(namen)} brand(s)")
    return 0


# --- Tasks on the user's own lists -----------------------------------------
#
# Section 8 is about authorship, not about whose fingers produce the line. A task on the user's list
# is one the user wants; the AI writes it when it is asked to, and invents none of its own. What the
# machine still owes goes on a work object, which is its own list and stays out of the user's files.
# The earlier rule banned the writing instead of the inventing, which left a plain instruction
# ("put that on my list") with no route at all.
#
# `task add` is that route and the only one: `hook checkbox-guard` still refuses a task line that
# turns up inside an ordinary Write or Edit, so a box cannot arrive as a side effect of editing
# prose. No mechanism can check whether the user really asked. These two can be had, so they are:
# writing a task is a deliberate, named act, and every one lands in the activity log, where an
# invented task is visible afterwards.
#
# The date is written as the common task plugin reads it, so a deadline set here also shows up in
# the user's own queries and not only in ours. Read generously, written one way.

_TASK_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<bullet>[-*+][ \t]+\[)(?P<state>[ xX-])(?P<rest>\].*)$")
_TASK_DUE_RE = re.compile(r"(?:\U0001F4C5|\(due:?)\s*(\d{4}-\d{2}-\d{2})\)?")
_TASK_HEADING = "## Tasks"
_TASK_SKIP_ROOTS = (SYSTEM_DIR, HOST_DIR, IMPORT_DIR)


def _task_due(text: str) -> str:
    """The due date carried by a task line, or "" when it carries none."""
    treffer = _TASK_DUE_RE.search(text)
    return treffer.group(1) if treffer else ""


def _task_date_ok(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _task_scan(vault: Path, only_open: bool = True) -> list[dict]:
    """Every task line in the user's part of the vault, wherever it sits.

    Folder-independent on purpose, and that is the whole point of it. A deadline does not stop being
    one because the bundle around it was archived; the flight that made this necessary disappeared
    from view the moment its trip bundle left `focus/`, with the money still in play. Left out are
    the system folder (the machine's own files), the host folder, the import queue and database
    folders, which an editor writes and nobody types by hand.
    """
    treffer: list[dict] = []
    for md in sorted(vault.rglob("*.md")):
        if not md.is_file():
            continue
        rel = md.relative_to(vault).as_posix()
        kopf = rel.split("/", 1)[0]
        if kopf in _TASK_SKIP_ROOTS or kopf.startswith("."):
            continue
        if _is_inside_database_folder(rel):
            continue
        try:
            zeilen = md.read_text(encoding="utf-8").splitlines()
            geaendert = md.stat().st_mtime
        except (OSError, UnicodeDecodeError):
            continue
        for nummer, zeile in enumerate(zeilen, start=1):
            passt = _TASK_LINE_RE.match(zeile)
            if not passt:
                continue
            offen = passt.group("state") == " "
            if only_open and not offen:
                continue
            roh = passt.group("rest")[1:].strip()
            faellig = _task_due(roh)
            # The date is carried in its own field from here on, so it comes out of the wording:
            # printed twice it reads like two different things.
            text = _TASK_DUE_RE.sub("", roh) if faellig else roh
            treffer.append({"path": rel, "line": nummer, "text": text.strip(),
                            "due": faellig, "open": offen, "mtime": geaendert})
    return treffer


def _task_due_soon(vault: Path, days: int, eintraege: list[dict] | None = None) -> list[dict]:
    """Open tasks whose date falls inside the window, overdue ones first. Undated ones stay out.

    Undated stay out because a list of everything open is read once and skipped forever after. What
    earns a line at the start of a session is a date that is about to pass.
    """
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    faellig: list[dict] = []
    for eintrag in (_task_scan(vault) if eintraege is None else eintraege):
        if not eintrag["due"] or not _task_date_ok(eintrag["due"]):
            continue
        tag = datetime.strptime(eintrag["due"], "%Y-%m-%d").date()
        if tag <= grenze:
            eintrag = dict(eintrag)
            eintrag["days"] = (tag - heute).days
            faellig.append(eintrag)
    # Nearest to today first, overdue or not. A task due tomorrow, written today, is
    # what a session start exists to surface; sorted purely chronologically, it sorts
    # dead last behind months of unresolved backlog and never makes the 12-item cap
    # below, since the backlog only grows and a fresh item always lands after it.
    return sorted(faellig, key=lambda e: abs(e["days"]))


_BRIEFING_DUE_DAYS = 14


_DATEINAME_DATUM = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def _dated_files_ahead(vault: Path, days: int) -> list[dict]:
    """Files whose own name carries a date from today onward, anywhere in the user's folders.

    The other three date sources are places the machine keeps itself: a task line it wrote, a bundle's
    `due:` field, a work object. A meeting prepared yesterday for tomorrow sits in none of them, and on
    2026-08-12 that is exactly what went missing from a greeting while the file for it lay in the
    vault. A date in a filename is the user's own convention and costs one walk to read.

    The system folder and the journal are skipped: a log or a daily entry named by its date is the
    date axis itself, not something coming up.
    """
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    treffer: list[dict] = []
    for pfad in vault.rglob("*.md"):
        rel = pfad.relative_to(vault)
        erste = rel.parts[0]
        if erste.startswith(".") or erste in (SYSTEM_DIR, IMPORT_DIR, JOURNAL_DIR):
            continue
        m = _DATEINAME_DATUM.search(pfad.stem)
        if not m:
            continue
        try:
            wann = datetime.strptime(m.group(0), "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (heute <= wann <= grenze):
            continue
        treffer.append({
            "date": m.group(0),
            "days": (wann - heute).days,
            "label": _human_label_for_slug(pfad.stem[len(m.group(0)):].strip("-_ ") or pfad.stem),
            "path": rel.as_posix(),
        })
    return sorted(treffer, key=lambda e: e["days"])


def _work_due_soon(vault: Path, days: int) -> list[dict]:
    """Unfinished work objects with a date inside the window, overdue first."""
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    rows, _headers = _work_read(vault)
    faellig = []
    for row in rows:
        wert = (row.get("due") or "").strip()
        if not wert or not _task_date_ok(wert) or row.get("state") == "done":
            continue
        if datetime.strptime(wert, "%Y-%m-%d").date() <= grenze:
            faellig.append(row)
    return sorted(faellig, key=lambda r: abs((datetime.strptime(r["due"], "%Y-%m-%d").date() - heute).days))


def _task_target(vault: Path, given: str | None) -> Path:
    """Where a commissioned task goes: the file the user named, else today's journal entry."""
    if not given:
        return _journal_note(vault, "daily", datetime.now())
    bekannt = _resolve_vault_file(vault, given)
    return bekannt if bekannt is not None else (vault / given)


def cmd_task_add(args: argparse.Namespace) -> int:
    """Write a task the user asked for onto one of their lists."""
    vault = Path(args.vault).resolve()
    due = (args.due or "").strip()
    if due and not _task_date_ok(due):
        print("fail: --due expects YYYY-MM-DD", file=sys.stderr)
        return 1
    text = args.text.strip()
    if not text:
        print("fail: a task needs words", file=sys.stderr)
        return 1
    target = _task_target(vault, args.file)
    if target.suffix.lower() not in (".md", ".markdown"):
        print(f"fail: a task belongs in a markdown file, not in {target.name}", file=sys.stderr)
        return 1
    try:
        rel = target.resolve().relative_to(vault).as_posix()
    except ValueError:
        print(f"fail: {args.file} is outside the vault", file=sys.stderr)
        return 1

    zeile = f"- [ ] {text}" + (f" \U0001F4C5 {due}" if due else "")
    target.parent.mkdir(parents=True, exist_ok=True)
    bestand = target.read_text(encoding="utf-8") if target.is_file() else ""
    zeilen = bestand.splitlines()
    kopf = next((i for i, z in enumerate(zeilen)
                 if z.strip().lower() == _TASK_HEADING.lower()), None)
    if kopf is None:
        if zeilen and zeilen[-1].strip():
            zeilen.append("")
        zeilen.extend([_TASK_HEADING, "", zeile])
    else:
        letzte, lauf = kopf, kopf + 1
        while lauf < len(zeilen) and not zeilen[lauf].startswith("## "):
            if _TASK_LINE_RE.match(zeilen[lauf]):
                letzte = lauf
            lauf += 1
        if letzte == kopf:
            while letzte + 1 < len(zeilen) and not zeilen[letzte + 1].strip():
                letzte += 1
        zeilen.insert(letzte + 1, zeile)
    target.write_text("\n".join(zeilen).rstrip("\n") + "\n", encoding="utf-8")
    _append_activity_log(vault, args.agent or "zanmai.py",
                         f"task written for the user -> {rel}: {text}")
    print(f"ok: {rel}: {zeile}")
    return 0


def cmd_task_done(args: argparse.Namespace) -> int:
    """Tick a task off. One unmistakable match or nothing: a tick on the wrong line is a false report."""
    vault = Path(args.vault).resolve()
    muster = args.text.strip().lower()
    kandidaten = [t for t in _task_scan(vault) if muster in t["text"].lower()]
    if args.file:
        gesucht = _task_target(vault, args.file)
        try:
            rel = gesucht.resolve().relative_to(vault).as_posix()
        except ValueError:
            print(f"fail: {args.file} is outside the vault", file=sys.stderr)
            return 1
        kandidaten = [t for t in kandidaten if t["path"] == rel]
    if not kandidaten:
        print(f"fail: no open task matching '{args.text}'", file=sys.stderr)
        return 1
    if len(kandidaten) > 1:
        print(f"fail: {len(kandidaten)} open tasks match '{args.text}'; say which one:", file=sys.stderr)
        for eintrag in kandidaten[:5]:
            print(f"  {eintrag['path']}:{eintrag['line']}  {eintrag['text']}", file=sys.stderr)
        return 1

    treffer = kandidaten[0]
    pfad = vault / treffer["path"]
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    stelle = treffer["line"] - 1
    passt = _TASK_LINE_RE.match(zeilen[stelle])
    if passt is None:
        print(f"fail: {treffer['path']}:{treffer['line']} changed while it was being read", file=sys.stderr)
        return 1
    zeilen[stelle] = f"{passt.group('indent')}{passt.group('bullet')}x{passt.group('rest')}"
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    _append_activity_log(vault, args.agent or "zanmai.py",
                         f"task ticked for the user -> {treffer['path']}: {treffer['text']}")
    print(f"ok: ticked in {treffer['path']}: {treffer['text']}")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """What is open across the whole vault, dated first, with the deadline said in days."""
    vault = Path(args.vault).resolve()
    if args.due_within is not None:
        eintraege = _task_due_soon(vault, args.due_within)
        gesamt = len(eintraege)
    else:
        alle = _task_scan(vault)
        gesamt = len(alle)
        eintraege = sorted(alle, key=lambda e: (not e["due"], e["due"], e["path"]))
    for eintrag in eintraege[:args.limit]:
        datum = f"{eintrag['due']}  " if eintrag["due"] else " " * 12
        print(f"{datum}{eintrag['text']}  ({eintrag['path']}:{eintrag['line']})")
    if len(eintraege) > args.limit:
        print(f"... plus {len(eintraege) - args.limit} more")
    if args.due_within is not None:
        print(f"ok: {gesamt} dated task(s) due within {args.due_within} day(s)")
    else:
        print(f"ok: {gesamt} open task(s)")
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
    bundle_dir = vault / _kind_folder(kind) / Path(*segments)
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
    tags = _tags_arg(getattr(args, "tags", None))
    if tags:
        additions["tags"] = tags

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
    return vault / MEMORY_DIR / ".embed-rename-map.json"


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
    """Rewrite `![[basename]]` and `![alt](path)` embeds in a bundle's markdown bodies so they
    point at the file they mean, inside the same bundle.

    Walks every `.md` file under the bundle directory (recursive, so sub-bundles are included). For
    each embed match, looks up the basename among the bundle's own non-markdown files. If found,
    the embed is rewritten with the path relative to the markdown file's folder. Body text outside
    embeds is untouched.

    The search stays inside the bundle because that is where attachments live: a bundle holds
    everything about one matter regardless of file type, so the picture a note embeds is a file
    beside it, not an entry in a shared pool somewhere else in the vault.

    Resolution order per embed:
      1. Direct basename match in the bundle index.
      2. `<md-stem>-<basename>` prefix-fallback for generic-source-name renames.
      3. Attachment rename map for plan-driven renames recorded by `asset add` (when the import
         plan renames a source basename on copy, the body still references the old name and
         resolves via the map).

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

    # Index the bundle's own attachments by basename. Recursive, because a sub-bundle is a nameable
    # thing inside the bundle (the flight, the year of statements) and its files count as the
    # bundle's own.
    attachments_index: dict[str, Path] = {}
    ambiguous: dict[str, int] = {}
    for f in sorted(bundle_dir.rglob("*")):
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
        rel_bundle = bundle_dir.relative_to(vault).as_posix()
        print(f"ok: no attachments in {rel_bundle}/ (nothing this run could resolve against)")
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
        (catches files prefixed with the bundle-slug or any sub-bundle slug
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
            # os.path.relpath, not Path.relative_to: a sub-bundle puts the note below the file
            # it embeds, so the path has to be able to walk up. relative_to only descends and
            # raised here, which meant such an embed could never be rewritten and the run counted
            # it as already correct.
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
    rel_bundle = bundle_dir.relative_to(vault).as_posix()
    print(f"ok: {embeds_rewritten} of {embeds_seen} embed(s) rewritten in "
          f"{len(files_changed)} file(s); {already} already correct; "
          f"{len(unresolved)} unresolved; {len(attachments_index)} attachment(s) indexed")
    if unresolved:
        for name in sorted(set(unresolved)):
            print(f"  unresolved: {name} (no file of that name in {rel_bundle}/)")
    if ambiguous:
        for name, count in sorted(ambiguous.items()):
            print(f"  ambiguous: {name} exists {count}x in {rel_bundle}/, first one used")

    if getattr(args, "clear_rename_map", False) and rename_map:
        _save_rename_map(vault, {})
        print(f"  cleared rename map ({len(rename_map)} entry/entries removed)")

    return 0







def cmd_archive_review_item(args: argparse.Namespace) -> int:
    """Move a read-once briefing off the desk into the logs, by year and month.

    For the read-once-briefing kind of item: a consolidation or a one-shot summary written for a
    single decision. The user has read it, so it moves to the machine's own side, where it stays
    browsable without sitting on the desk. The desk is the one place that empties, and this is one
    of the ways it does. Frontmatter status flips to 'archived'."""
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
    target_dir = vault / LOGS_DIR / now.strftime("%Y") / now.strftime("%m")
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
        f"archived review item {item_path.name} to {target.relative_to(vault)}"
    )
    print(f"ok: review item archived to {target.relative_to(vault)}")
    return 0





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


def _collect_open_todos(vault: Path, scope_dirs: list[str], days_back: int = 30,
                        eintraege: list[dict] | None = None) -> list[dict]:
    """The open tasks under given folders, recent ones only, for the briefing's open-items sections.

    A narrowing of `_task_scan`, not a second reader: one definition of what a task line is, in one
    place. The date window is on the file, not on the task, and it is what keeps these sections
    about what is currently going on; deadlines are a different question and are not filtered by it.
    Pass `eintraege` to reuse a scan the caller already has, which is what the briefing does.
    """
    cutoff = datetime.now().timestamp() - days_back * 24 * 3600
    praefixe = tuple(f"{sub.rstrip('/')}/" for sub in scope_dirs)
    alle = _task_scan(vault) if eintraege is None else eintraege
    return [t for t in alle if t["path"].startswith(praefixe) and t["mtime"] >= cutoff]


def _recent_log_files(vault: Path, limit: int = 5) -> list[Path]:
    """Most recent N log files under zanmai/logs/<YYYY>/<MM>/, sorted by mtime desc.
    Excludes builder-gaps.md and hidden files."""
    logs_root = vault / LOGS_DIR
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


def _last_session_end(vault: Path) -> str:
    """The timestamp of the last clean session close, or an empty string."""
    marker = vault / MEMORY_DIR / ".last-session-end"
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


_ACTIVITY_HEAD_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] - ([^-]+) - (.*)$")


def _marker_as_local_minute(marker: str) -> str:
    """`.last-session-end` is written in UTC; the activity log carries local time. This is the one
    place the two meet, so the conversion lives here rather than at each caller."""
    text = (marker or "").strip()
    if not text:
        return ""
    try:
        stamp = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return text.replace("T", " ").replace("Z", "")[:16]
    return stamp.astimezone().strftime("%Y-%m-%d %H:%M")


def _activity_since(vault: Path, since: str, limit: int = 25) -> list[dict]:
    """Activity-log entries written after `since`, newest last.

    The activity log is the only record of a session that is written while the work happens
    rather than at the end, so it is the one that survives a session nobody closed. Found
    2026-08-26 on a live vault: `briefing.md` stood at 15:13 while the log carried entries up
    to 16:24 and the whole afternoon, an escalation included, was invisible at the next start.
    """
    log = vault / MEMORY_DIR / "activity-log.md"
    if not log.is_file():
        return []
    # The marker is UTC, the activity log is local time. Comparing them as text put the line two
    # hours in the wrong place, which on a live vault means either replaying entries that were
    # already handed over or dropping ones that were not. Found by the check for this function.
    grenze = _marker_as_local_minute(since)
    treffer: list[dict] = []
    for zeile in log.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = _ACTIVITY_HEAD_RE.match(zeile)
        if not match:
            continue
        wann, wer, was = match.group(1), match.group(2).strip(), match.group(3).strip()
        if grenze and wann <= grenze:
            continue
        treffer.append({"when": wann, "who": wer, "what": was})
    return treffer[-limit:]


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
    focus_dir = vault / FOCUS_DIR
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
    """Bundles under the knowledge, habits and focus roots with file mtimes in the last
    `hours_back` hours. Source-agnostic recency signal: catches reed-research,
    hank-imports, manual edits alike. The Open-Todos channel only surfaces
    Daily and Weekly items. This surfaces "user was busy with X yesterday" for
    any bundle. Returns descending by last_activity_unix."""
    import time as _time
    cutoff = _time.time() - (hours_back * 3600)
    result: list[dict] = []
    for kind_folder in BUNDLE_FOLDERS:
        bundle_kind = _folder_kind(kind_folder)
        kind_path = vault / kind_folder
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
    skips database folders (`<Name>.base/`), their `data.csv`,
    `schema.json` and record-page files are database-internal, not the vault's
    own files that markdown bodies embed."""
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
        if rel.startswith(f"{SYSTEM_MATERIAL_DIR}/") or rel.startswith(f"{HISTORY_DIR}/") or rel.startswith(".claude/"):
            continue
        if _is_inside_database_folder(rel):
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
    index_path = vault / MEMORY_DIR / "vault-index.json"
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


_JOURNAL_KINDS = ("daily", "weekly", "monthly", "yearly")
_JOURNAL_ROOTS = {
    "daily": DAILY_DIR,
    "weekly": WEEKLY_DIR,
    "monthly": MONTHLY_DIR,
    "yearly": YEARLY_DIR,
}


def _journal_period(kind: str, date: datetime) -> str:
    """The name of the period a date falls in: `2026-08-09`, `2026-W32`, `2026-08`, `2026`.

    One string does two jobs, it is the bundle's folder name and the note's basename. That is not
    thrift, it is what keeps the note findable: a folder holding a note called `note.md` hides it
    behind a name nobody would search for.
    """
    if kind == "daily":
        return date.strftime("%Y-%m-%d")
    if kind == "weekly":
        iso = date.isocalendar()
        return f"{iso[0]:04d}-W{iso[1]:02d}"
    if kind == "monthly":
        return date.strftime("%Y-%m")
    if kind == "yearly":
        return date.strftime("%Y")
    raise ValueError(f"unknown journal kind: {kind}")


def _journal_bundle(vault: Path, kind: str, date: datetime) -> Path:
    """The bundle folder for one journal entry.

    Every entry is a bundle, week and month and year included, so a photo, a recording or a PDF has
    somewhere to sit next to the note it belongs to. The grouping year comes off the period name, so
    a week in the first days of January files under the ISO year its own name carries and does not
    split away from the week before it.
    """
    period = _journal_period(kind, date)
    if kind == "yearly":
        return vault / YEARLY_DIR / period
    return vault / _JOURNAL_ROOTS[kind] / period[:4] / period


def _journal_note(vault: Path, kind: str, date: datetime) -> Path:
    """The note inside a journal bundle. Same basename as the bundle."""
    return _journal_bundle(vault, kind, date) / f"{_journal_period(kind, date)}.md"


def _journal_roots() -> list[str]:
    """The four journal roots, vault-relative. Used to scan for open items."""
    return [_JOURNAL_ROOTS[k] for k in _JOURNAL_KINDS]


_ROLLUP_SOURCE = {"weekly": "daily", "monthly": "weekly", "yearly": "monthly"}
_ROLLUP_HEADING = "## Rollup"


def _journal_target_date(args: argparse.Namespace) -> datetime | None:
    """The date the command works on. None means the argument was unusable and the caller reports."""
    if not args.date:
        return datetime.now()
    try:
        return datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("fail: invalid --date, expected YYYY-MM-DD", file=sys.stderr)
        return None


def _journal_entries(vault: Path, kind: str, since: datetime, until: datetime) -> list[Path]:
    """The notes of one journal kind whose period starts inside [since, until), oldest first.

    The period comes off the folder name, not off a file timestamp: a sync client rewrites those, and
    then a rollup either misses entries or picks up ones it already used.
    """
    root = vault / _JOURNAL_ROOTS[kind]
    if not root.is_dir():
        return []
    treffer: list[tuple[str, Path]] = []
    tag = since
    grenzen = set()
    while tag < until:
        grenzen.add(_journal_period(kind, tag))
        tag += timedelta(days=1)
    for period in sorted(grenzen):
        note = _journal_bundle(vault, kind, _journal_period_start(kind, period)) / f"{period}.md"
        if note.is_file():
            treffer.append((period, note))
    return [n for _, n in sorted(treffer)]


def _journal_period_start(kind: str, period: str) -> datetime:
    """The first day of a named period. The inverse of `_journal_period`."""
    if kind == "daily":
        return datetime.strptime(period, "%Y-%m-%d")
    if kind == "weekly":
        jahr, woche = period.split("-W")
        return datetime.fromisocalendar(int(jahr), int(woche), 1)
    if kind == "monthly":
        return datetime.strptime(period, "%Y-%m")
    if kind == "yearly":
        return datetime.strptime(period, "%Y")
    raise ValueError(f"unknown journal kind: {kind}")


def _journal_previous_period(kind: str, date: datetime) -> datetime:
    """A date inside the period before the one `date` falls in."""
    start = _journal_period_start(kind, _journal_period(kind, date))
    return start - timedelta(days=1)


def _journal_period_bounds(kind: str, date: datetime) -> tuple[datetime, datetime]:
    """First day of the period containing `date`, and the first day of the next one."""
    start = _journal_period_start(kind, _journal_period(kind, date))
    if kind == "daily":
        return start, start + timedelta(days=1)
    if kind == "weekly":
        return start, start + timedelta(days=7)
    if kind == "monthly":
        naechster = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, naechster
    return start, start.replace(year=start.year + 1)


def _journal_has_rollup(note: Path) -> bool:
    return note.is_file() and _ROLLUP_HEADING in note.read_text(encoding="utf-8", errors="ignore")


def _journal_append(vault: Path, path: Path, text: str, was: str) -> str:
    """Append to a journal note, creating its bundle if needed. Never overwrites, never edits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    bestand = path.read_text(encoding="utf-8") if path.exists() else ""
    if bestand and not bestand.endswith("\n"):
        bestand += "\n"
    if bestand.strip():
        bestand += "\n"
    path.write_text(bestand + text.rstrip("\n") + "\n", encoding="utf-8")
    rel = path.relative_to(vault).as_posix()
    _append_activity_log(vault, "zanmai.py", f"{was} -> {rel}")
    return rel


def cmd_journal_path(args: argparse.Namespace) -> int:
    """Print the path of a journal entry. Creates nothing."""
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    print(_journal_note(vault, args._kind, date).relative_to(vault).as_posix())
    return 0


def cmd_journal_ensure(args: argparse.Namespace) -> int:
    """Create the entry and its bundle if they are not there yet. Touches an existing entry not at all."""
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    path = _journal_note(vault, args._kind, date)
    rel = path.relative_to(vault).as_posix()
    if path.exists():
        print(f"ok: {rel} is already there")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    _append_activity_log(vault, "zanmai.py", f"journal {args._kind} created -> {rel}")
    print(f"ok: {rel}")
    return 0


def cmd_journal_append(args: argparse.Namespace) -> int:
    """Append the user's words to a journal entry, verbatim, below whatever is already there."""
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    rel = _journal_append(vault, _journal_note(vault, args._kind, date), args.text,
                          f"journal {args._kind} append")
    print(f"ok: appended to {rel}")
    return 0


def cmd_journal_read(args: argparse.Namespace) -> int:
    """Print a journal entry, or say plainly that the period holds nothing yet."""
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    path = _journal_note(vault, args._kind, date)
    rel = path.relative_to(vault).as_posix()
    if not path.is_file():
        print(f"empty: {rel} does not exist, nothing was written for that {args._kind[:-2]}")
        return 0
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def cmd_journal_list(args: argparse.Namespace) -> int:
    """List the entries of one kind that exist, newest last. The bundle contents come with it."""
    vault = Path(args.vault).resolve()
    root = vault / _JOURNAL_ROOTS[args._kind]
    if not root.is_dir():
        print(f"empty: no {args._kind} entries yet")
        return 0
    notes = sorted(p for p in root.rglob("*.md") if p.is_file() and p.stem == p.parent.name)
    if args._kind == "yearly":
        notes = sorted(p for p in root.rglob("*.md") if p.is_file())
    if not notes:
        print(f"empty: no {args._kind} entries yet")
        return 0
    for note in notes[-args.limit:] if args.limit else notes:
        rel = note.relative_to(vault).as_posix()
        beilagen = [f for f in note.parent.iterdir() if f.is_file() and f != note]
        zusatz = f"  (+{len(beilagen)} file(s) in the bundle)" if beilagen else ""
        print(f"{rel}{zusatz}")
    return 0


def _journal_rollups_due(vault: Path, date: datetime) -> list[str]:
    """Which rollups are due, and which entries each one reads. Reports, writes nothing.

    The whole decision sits here rather than in a contract: which period just ended, whether its
    entry already carries a rollup, and whether the layer below holds anything to summarise. What is
    left to judgement is the summary text, and nothing else. The session-start hook and the command
    both read this, so the two can never disagree about whether something is due.
    """
    zeilen: list[str] = []
    for kind, quelle in _ROLLUP_SOURCE.items():
        vorher = _journal_previous_period(kind, date)
        ziel = _journal_note(vault, kind, vorher)
        if _journal_has_rollup(ziel):
            continue
        von, bis = _journal_period_bounds(kind, vorher)
        quellen = _journal_entries(vault, quelle, von, bis)
        if not quellen:
            continue
        zeilen.append(f"{kind} {_journal_period(kind, vorher)} -> {ziel.relative_to(vault).as_posix()}")
        zeilen.extend(f"  reads {q.relative_to(vault).as_posix()}" for q in quellen)
    return zeilen


def cmd_journal_rollup_due(args: argparse.Namespace) -> int:
    """Say which rollups are due and name the entries each one reads. Writes nothing."""
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    zeilen = _journal_rollups_due(vault, date)
    print("\n".join(zeilen) if zeilen else "none: no rollup is due")
    return 0


def cmd_journal_rollup(args: argparse.Namespace) -> int:
    """Write one rollup into the period entry it belongs to, once.

    Refusing the second one is the point. A rollup is written without asking because it only ever
    appends, and that only stays true if it cannot run twice over the same period.
    """
    vault = Path(args.vault).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    kind = args._kind
    vorher = _journal_previous_period(kind, date) if not args.this_period else date
    ziel = _journal_note(vault, kind, vorher)
    rel = ziel.relative_to(vault).as_posix()
    if _journal_has_rollup(ziel):
        print(f"skip: {rel} already carries a rollup. One per period, no second.")
        return 0
    von, bis = _journal_period_bounds(kind, vorher)
    quellen = _journal_entries(vault, _ROLLUP_SOURCE[kind], von, bis)
    if not quellen:
        print(f"skip: nothing in {_ROLLUP_SOURCE[kind]} for {_journal_period(kind, vorher)}, so there is nothing to roll up")
        return 0
    _journal_append(vault, ziel, f"{_ROLLUP_HEADING}\n\n{args.text.strip()}",
                    f"journal {kind} rollup")
    print(f"ok: rollup written to {rel} from {len(quellen)} {_ROLLUP_SOURCE[kind]} entries")
    return 0


# The greet list, decided here instead of in the prompt.
#
# `experts/steve/greeting.md` used to carry the whole judgement: which sources, in what order, a cap
# of six, the overflow as its own numbered line rather than a nested sub-bullet, no work-object id.
# Each of those was written down plainly, with its reason, and each broke in a live session anyway.
# On 2026-08-12 two months of meeting backlog buried a task written that same day. On 2026-08-14 a
# work-object id reached the user. On 2026-08-17 the overflow came back as a sub-bullet and the
# numbering jumped from 4 to 6. A rule that does not hold on the third attempt is not a wording
# problem, so ordering, the cap, the overflow line and id-stripping happen here. What is left to
# judgement is the wording of a line and the closing sentence.
_GREET_CAP = 6
_GREET_WEEK_DAYS = 7          # what still counts as coming up rather than later
_GREET_RECENT_OVERDUE = 14    # older than this, an overdue item is backlog: counted, not listed
_GREET_UNDATED_DAYS = 7       # how fresh a journal or focus file must be for its undated items

# Two orders, and keeping them apart is the point. Which items get one of the six slots is decided
# by urgency alone; how the chosen ones are laid out is decided by group. Sorting the selection by
# group instead was tried first and reproduced the 2026-08-12 defect in miniature: a four-day-old
# test entry took slot one from seven items due that day, because "overdue" led the group order.
_GREET_GROUPS = ("waiting", "overdue", "today", "tomorrow", "this week", "open")

_GREET_HEADINGS = {
    "waiting": "Waiting on you",
    "overdue": "Overdue",
    "today": "Today",
    "tomorrow": "Tomorrow",
    "this week": "Coming up",
    "open": "Open, no date",
}

_GREET_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")


def _greet_group(days: int) -> str:
    """Which time group a day-distance belongs to."""
    if days < 0:
        return "overdue"
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return "this week"


def _greet_text(raw: str) -> str:
    """The display form of an item: wikilinks reduced to what they show, whitespace normalised.

    A greet line is read, not clicked, so `[[anna-berg|Anna]]` has to arrive as `Anna`. Doing it
    here rather than asking for it means a link cannot survive into the greet by being overlooked.
    """
    ohne_link = _GREET_LINK_RE.sub(
        lambda m: (m.group(2) or _human_label_for_slug(m.group(1))).strip(), raw or ""
    )
    return re.sub(r"\s+", " ", ohne_link).strip()


_GREET_SAME_SHARE = 0.6   # how much of the shorter wording has to appear in the longer one


def _greet_words(text: str) -> set[str]:
    """The words of an item that carry its meaning, for comparing two wordings of one matter."""
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 4}


def _greet_same(a: dict, b: dict) -> bool:
    """Whether two entries are the same matter said twice.

    They arrive from separate lists that do not know about each other: a task line in the journal, a
    work object, a dated file. A real vault had four items sitting in two of those at once, worded
    differently each time, because the task line keeps the user's own sentence while the work object
    carries the shorthand the machine wrote for it. Comparing the strings catches none of those, so
    the overlap of the meaningful words decides, and only for entries that fall on the same day. Two
    different jobs sharing a date and one word stay two jobs.
    """
    if (a.get("due") or "") != (b.get("due") or ""):
        return False
    wa, wb = a["words"], b["words"]
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= _GREET_SAME_SHARE


def _greet_items(vault: Path, now: datetime | None = None) -> dict:
    """What the greet names: chosen, grouped, sorted and capped, ready to be worded.

    Returns `{"items": [...], "overflow": {...} | None, "totals": {...}}`. Every item carries its
    group, its display text and where it came from. The caller renders them in the order given and
    adds nothing: the selection is the decision, and it was made here.
    """
    jetzt = now or datetime.now()
    heute = jetzt.date()
    aufgaben = _task_scan(vault)

    kandidaten: list[dict] = []
    rueckstand = 0

    def aufnehmen(gruppe: str, roh: str, quelle: str, naehe: int,
                  rang: int = 1, faellig: str = "") -> None:
        text = _greet_text(roh)
        if not text:
            return
        neu = {"group": gruppe, "text": text, "source": quelle, "near": naehe,
               "rank": rang, "due": faellig, "words": _greet_words(text)}
        for alt in kandidaten:
            if _greet_same(alt, neu):
                # Keep the earlier one: task lines carry the user's own wording, work objects carry
                # a shorthand the machine wrote. Only the rank is taken over, because "waiting on
                # you" is a fact about the matter no matter which source states it.
                alt["rank"] = min(alt["rank"], rang)
                if rang == 0:
                    alt["group"] = "waiting"
                return
        kandidaten.append(neu)

    for eintrag in _task_due_soon(vault, _GREET_WEEK_DAYS, eintraege=aufgaben):
        tage = eintrag["days"]
        if tage < -_GREET_RECENT_OVERDUE:
            rueckstand += 1
            continue
        aufnehmen(_greet_group(tage), eintrag["text"], eintrag["path"], abs(tage),
                  faellig=eintrag["due"])

    # Waiting on the user, with no date on it. This comes first and on its own pass, because
    # `_work_due_soon` filters by date before anything else sees the row, so an undated one never
    # arrived at all. Found in the field on 2026-08-26, on the first greet after the greet itself was
    # fixed: the most active piece of work in the vault, three days old and explicitly waiting on the
    # user, was missing from the list, and the three work objects in that state all had no due date.
    # A due date is a plan; `waiting on you` is a recorded fact about who holds the thing. Dropping
    # the fact because the plan is absent is backwards, and the comment below already said so while
    # the line above threw the row away.
    try:
        alle_rows, _h = _work_read(vault)
    except Exception:
        alle_rows = []
    for row in alle_rows:
        if (row.get("state") or "").strip() != "waiting on you":
            continue
        if _task_date_ok((row.get("due") or "").strip()):
            continue  # dated ones come through the pass below, with their real distance
        aufnehmen("waiting", row.get("work", ""), "work object", _GREET_WEEK_DAYS, rang=0)

    for row in _work_due_soon(vault, _GREET_WEEK_DAYS):
        faellig = (row.get("due") or "").strip()
        if not _task_date_ok(faellig):
            continue
        tage = (datetime.strptime(faellig, "%Y-%m-%d").date() - heute).days
        if tage < -_GREET_RECENT_OVERDUE:
            rueckstand += 1
            continue
        # `waiting on you` is the one urgency signal in the vault that is a recorded fact rather
        # than a judgement: something is on the user and the machine cannot move it. It goes first,
        # ahead of distance. Without it a hard deadline four days out sits behind every routine
        # item due today and drops out of the six.
        wartet = (row.get("state") or "").strip() == "waiting on you"
        # The row's `id` stays here. It is the handle for `zanmai.py work` and tells the user
        # nothing; on 2026-08-14 one reached a greet because the rule against it lived in prose.
        aufnehmen("waiting" if wartet else _greet_group(tage), row.get("work", ""),
                  "work object", abs(tage), rang=0 if wartet else 1, faellig=faellig)

    for eintrag in _dated_files_ahead(vault, _GREET_WEEK_DAYS):
        aufnehmen(_greet_group(eintrag["days"]), eintrag["label"], eintrag["path"],
                  abs(eintrag["days"]), faellig=eintrag["date"])

    # Undated, and only from a file touched in the last few days: a task written into today's
    # journal belongs in the greet whether it carries a date or not. The window is what stops a
    # month of ticked-over lists from arriving as if it were current.
    frisch = _collect_open_todos(vault, _journal_roots() + [FOCUS_DIR],
                                 days_back=_GREET_UNDATED_DAYS, eintraege=aufgaben)
    for t in sorted((t for t in frisch if not t["due"]), key=lambda t: t["mtime"], reverse=True):
        aufnehmen("open", t["text"], t["path"], _GREET_WEEK_DAYS + 1)

    # Selection by urgency: what waits on the user first, then distance from today, and an overdue
    # item ahead of a coming one at equal distance because that one is already missed.
    kandidaten.sort(key=lambda e: (e["rank"], e["near"], 0 if e["group"] == "overdue" else 1))

    # The cap is six lines including the overflow line, never six plus one. Where an overflow is
    # needed it takes the last slot, which is why the visible list is cut one short.
    braucht_ueberlauf = rueckstand > 0 or len(kandidaten) > _GREET_CAP
    grenze = _GREET_CAP - 1 if braucht_ueberlauf else _GREET_CAP
    sichtbar = kandidaten[:grenze]
    verdeckt = kandidaten[grenze:]

    # Layout by group, once the six are settled. Same items, read in an order that says something.
    ordnung = {name: i for i, name in enumerate(_GREET_GROUPS)}
    sichtbar.sort(key=lambda e: (ordnung[e["group"]], e["near"]))

    ueberlauf = None
    if braucht_ueberlauf:
        heute_verdeckt = sum(1 for e in verdeckt if e["group"] == "today")
        offen_verdeckt = sum(1 for e in verdeckt if e["group"] == "open")
        nah_verdeckt = len(verdeckt) - offen_verdeckt
        teile: list[str] = []
        if nah_verdeckt:
            zusatz = f" ({heute_verdeckt} of them today)" if heute_verdeckt else ""
            teile.append(f"{nah_verdeckt} more within the next {_GREET_WEEK_DAYS} days{zusatz}")
        if offen_verdeckt:
            # Counted apart, because folding an undated item into "within the next 7 days" states a
            # deadline nobody wrote.
            teile.append(f"{offen_verdeckt} open with no date")
        if rueckstand:
            teile.append(f"{rueckstand} older overdue")
        ueberlauf = {
            "group": "more",
            "text": ", ".join(teile),
            "hidden_near": nah_verdeckt,
            "hidden_today": heute_verdeckt,
            "hidden_undated": offen_verdeckt,
            "hidden_backlog": rueckstand,
        }

    return {
        "items": sichtbar,
        "overflow": ueberlauf,
        "totals": {
            "open_tasks": len(aufgaben),
            "candidates": len(kandidaten),
            "backlog": rueckstand,
        },
    }


def _greet_block(vault: Path, now: datetime | None = None) -> list[str]:
    """The greet list as hook output: numbered, grouped, capped, nothing left to arrange.

    Rendered as data rather than as a suggestion. The numbers are printed, so they cannot skip; the
    overflow arrives as its own numbered line, so it cannot become a sub-bullet; an empty vault
    prints no list at all rather than a padded one.
    """
    walk = _greet_items(vault, now=now)
    items = walk["items"]
    ueberlauf = walk["overflow"]
    if not items and not ueberlauf:
        return ["- Nothing open and nothing dated. Greet in one sentence and ask what they want to "
                "do; do not invent a list."]

    lines = [
        "The greet list, already selected, sorted and capped. Render exactly these lines, in this "
        "order, one numbered line each, with the numbers as printed. Translate the group headings "
        "and the wording into the user's writing language, keep the item's own words, and add "
        "nothing: no extra item, no sub-bullet, no path, no id. `greeting.md` covers the tone, the "
        "address and the closing sentence.",
        "",
    ]
    heute = (now or datetime.now()).date()
    letzte_gruppe = None
    nummer = 0
    for eintrag in items:
        if eintrag["group"] != letzte_gruppe:
            letzte_gruppe = eintrag["group"]
            titel = _GREET_HEADINGS[letzte_gruppe]
            # The date on the heading is what turns "today" from a word into a fact the user can
            # check against their own calendar.
            if letzte_gruppe == "today":
                titel += f" ({heute.isoformat()})"
            elif letzte_gruppe == "tomorrow":
                titel += f" ({(heute + timedelta(days=1)).isoformat()})"
            lines.append(f"GROUP {titel}")
        nummer += 1
        lines.append(f"{nummer}. {eintrag['text']}")
    if ueberlauf:
        nummer += 1
        lines.append("GROUP The rest")
        lines.append(f"{nummer}. + {ueberlauf['text']}. Offer: say \"show the open points\".")
    return lines


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
    close_next = _close_session_next_items(vault, limit=1)
    # One walk over the vault feeds all three task sections below, which is also what keeps them
    # from disagreeing with each other.
    offene_aufgaben = _task_scan(vault)
    daily_weekly_todos = _collect_open_todos(
        vault, _journal_roots(), days_back=30, eintraege=offene_aufgaben
    )
    focus_todos = _collect_open_todos(vault, [FOCUS_DIR], days_back=90,
                                      eintraege=offene_aufgaben)
    broken = _broken_wikilinks(vault)

    lines: list[str] = []
    lines.append(f"# Zanmai briefing")
    lines.append("")
    lines.append(f"_Updated {timestamp}. Read by Steve at session start. "
                 f"Not user-editable - rebuilt automatically on close-session, "
                 f"on every operation report, and on demand via "
                 f"`zanmai.py memory briefing`._")
    lines.append("")

    # 0) What has a date on it, from anywhere in the vault and from the machine's own list.
    #
    # First, and folder-independent, because that was the defect: a deadline used to be visible only
    # while its bundle sat in `focus/` and went dark the moment the bundle was archived, with the
    # money still in play. Only dated items appear. A list of everything open is read once and
    # skipped from then on, and then the one line that mattered is lost in it.
    faellig = _task_due_soon(vault, _BRIEFING_DUE_DAYS, eintraege=offene_aufgaben)
    work_faellig = _work_due_soon(vault, _BRIEFING_DUE_DAYS)
    datiert = _dated_files_ahead(vault, _BRIEFING_DUE_DAYS)
    if faellig or work_faellig or datiert:
        lines.append(f"## Due (next {_BRIEFING_DUE_DAYS} days, overdue included)")
        lines.append("")
        for eintrag in faellig[:12]:
            wann = ("overdue" if eintrag["days"] < 0
                    else "today" if eintrag["days"] == 0
                    else f"in {eintrag['days']} days")
            lines.append(f"- **{eintrag['due']}** ({wann}) {eintrag['text']} _({eintrag['path']})_")
        if len(faellig) > 12:
            lines.append(f"- _... plus {len(faellig) - 12} more dated item(s)_")
        for row in work_faellig[:8]:
            lines.append(f"- **{row['due']}** (work object) {row.get('work','')}")
        for eintrag in datiert[:8]:
            wann = ("today" if eintrag["days"] == 0
                    else "tomorrow" if eintrag["days"] == 1
                    else f"in {eintrag['days']} days")
            lines.append(f"- **{eintrag['date']}** ({wann}) {eintrag['label']} _({eintrag['path']})_")
        if len(datiert) > 8:
            lines.append(f"- _... plus {len(datiert) - 8} more dated file(s)_")
        lines.append("")

    # 1) Current state
    # What happened after the last clean close. This is the section that answers "where were we"
    # when no close-session log exists, which on a live vault is the normal case rather than the
    # exception: the close is a skill someone has to invoke, and nobody invokes it when they simply
    # shut the window. The activity log is written during the work, so it is there either way.
    seit = _last_session_end(vault)
    nachgetragen = _activity_since(vault, seit)
    if nachgetragen:
        lines.append("## Since the last clean close")
        lines.append("")
        # Two things this heading has to settle, both found on a live vault the morning after it
        # first shipped. It is the newest thing in the file, so where it contradicts a status table
        # or a bundle's own STAND.md, it wins; without that said, the older source won and a session
        # opened by proposing the very plan the user had struck out an hour earlier. And every line
        # under it was written by a different session, so the "I" in it is not the reader's: one
        # session reported "I deliberately left those alone" about work it had never done.
        if seit:
            lines.append(f"_The last session closed at {seit}. "
                         f"{len(nachgetragen)} thing(s) happened after that and were never "
                         f"handed over._")
        else:
            lines.append("_No session has ever been closed cleanly in this vault. "
                         "This is what the activity log carries._")
        lines.append("")
        lines.append("**This is the newest thing in this briefing.** Where it contradicts anything "
                     "below, or a status table in a bundle, this wins and the other is stale. "
                     "**Every line here was written by an earlier session, not by you.** Their "
                     "\"I\" is that session's, so report them as what happened, never as what you "
                     "did or decided.")
        lines.append("")
        for eintrag in nachgetragen:
            lines.append(f"- **{eintrag['when']}** (earlier session, {eintrag['who']}) "
                         f"{eintrag['what']}")
        lines.append("")

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


_BRIEFING_REQUIRED = ("## Current state", "## Open items", "## Gaps and hints")


def _briefing_sections_missing(content: str) -> list[str]:
    """Which of the briefing's fixed sections did not make it into the rendered text.

    The greet walks this file, so a section that fell out is a source that silently went quiet. It
    reads as "nothing open" rather than as "the renderer broke", which is the more expensive of the
    two failures because nobody looks for it.
    """
    return [s for s in _BRIEFING_REQUIRED if s not in content]


def cmd_briefing(args: argparse.Namespace) -> int:
    """Atomic rebuild of `zanmai/memory/briefing.md`. Triggered by `/close-session`,
    after `memory report`, or manually. The authority for Steve's session-start
    context."""
    vault = Path(args.vault).resolve()
    target = vault / MEMORY_DIR / "briefing.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = _render_briefing(vault)
    target.write_text(content, encoding="utf-8")
    _append_activity_log(vault, "zanmai.py", "briefing.md rebuilt from vault state")
    fehlt = _briefing_sections_missing(content)
    if not getattr(args, "quiet", False):
        print(f"ok: briefing rebuilt -> {target.relative_to(vault)}")
    if fehlt:
        # Whoever generates a text that behaviour is built on checks that text. A briefing that
        # swallowed a section looks exactly like a full one from the outside, and the greet then
        # reads from a source that silently lost the part it existed for.
        print("warning: briefing is missing section(s): " + ", ".join(fehlt), file=sys.stderr)
        return 1
    return 0


def cmd_hook_session_end(args: argparse.Namespace) -> int:
    """SessionEnd hook: rebuild the briefing, and mark the close only if one really happened.

    Until 2026-08-26 the handover between sessions ran entirely through the `close-session` skill,
    which someone has to invoke. On a live vault after four weeks, no session log had ever been
    written: shutting the window is what actually ends a session, and nothing was bound to that.
    The next morning then opened on a briefing that stood at the previous afternoon, with the whole
    day after it invisible, which reads from the outside exactly like a system with no memory.

    So the briefing is rebuilt here, mechanically, at the one moment that always arrives. It is
    deliberately not a substitute for the skill: this hook has no model, so it can record what
    happened but not what it meant. The marker file is therefore only advanced when a real close
    log exists for today; otherwise it stays put and the briefing's own catch-up section carries
    the day forward, which is the honest state rather than a clean-looking one.
    """
    payload = _hook_read_payload()
    start = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "."
    vault = _find_vault_root(Path(start))
    if vault is None:
        return 0
    ziel = vault / MEMORY_DIR / "briefing.md"
    if not ziel.parent.is_dir():
        return 0
    try:
        ziel.write_text(_render_briefing(vault), encoding="utf-8")
    except OSError as exc:
        print(f"session-end: briefing not rebuilt ({exc})", file=sys.stderr)
        return 0
    if _close_log_today(vault):
        # Same format the close-session skill writes: UTC, ISO 8601, seconds.
        (vault / MEMORY_DIR / ".last-session-end").write_text(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
    return 0


def _close_log_today(vault: Path) -> bool:
    """Whether a close-session log was written today. The condition for calling a session closed."""
    heute = datetime.now().strftime("%Y-%m-%d")
    for log in _recent_log_files(vault, limit=10):
        text = log.read_text(encoding="utf-8", errors="ignore")
        fm, _, _body = _split_frontmatter(text)
        if not isinstance(fm, dict):
            continue
        if str(fm.get("session_type", "")).lower() in ("close-session", "close", "unattended"):
            if str(fm.get("date", ""))[:10] == heute or log.name.startswith(heute):
                return True
    return False


def cmd_write_report(args: argparse.Namespace) -> int:
    """Write an operation report to zanmai/logs/<YYYY>/<MM>/<date-op-slug>.md.

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
    report_dir = vault / LOGS_DIR / now.strftime("%Y") / now.strftime("%m")
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
    briefing_target = vault / MEMORY_DIR / "briefing.md"
    try:
        briefing_target.parent.mkdir(parents=True, exist_ok=True)
        briefing_target.write_text(_render_briefing(vault), encoding="utf-8")
        _append_activity_log(vault, "zanmai.py", "briefing.md auto-rebuilt after memory report")
    except OSError:
        pass

    return 0


def _read_recent_activity(vault: Path, *, since_minutes: int) -> list[str]:
    log = vault / MEMORY_DIR / "activity-log.md"
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


def cmd_bundle_index_entry(args: argparse.Namespace) -> int:
    """Correct the one-line description of a member in its bundle's INDEX.md."""
    vault = Path(args.vault).resolve()
    bundle_dir, _kind, _leaf = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1
    slug = _slugify(args.file[:-3] if args.file.lower().endswith(".md") else args.file)
    if not _index_line_set(bundle_dir / "INDEX.md", slug, args.summary.strip()):
        print(f"fail: no entry for [[{slug}]] in {bundle_dir.relative_to(vault)}/INDEX.md",
              file=sys.stderr)
        return 1
    _append_activity_log(vault, "zanmai.py",
                         f"rewrote the index entry for {slug} in "
                         f"{bundle_dir.relative_to(vault).as_posix()}/")
    print(f"ok: index entry for {slug} now reads: {args.summary.strip()}")
    return 0


def cmd_bundle_remove_file(args: argparse.Namespace) -> int:
    """Discard a member: to the trash, out of the index, into the activity log, in one call.

    `file trash` moved the file and logged it but left the index line pointing at nothing, so every
    discard ended in a hand-edit of INDEX.md. Two halves of one act belong in one command.
    """
    vault = Path(args.vault).resolve()
    bundle_dir, _kind, _leaf = _resolve_bundle_dir(vault, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1
    slug = _slugify(args.file[:-3] if args.file.lower().endswith(".md") else args.file)
    target = bundle_dir / f"{slug}.md"
    if not target.is_file():
        print(f"fail: no such member: {target.relative_to(vault)}", file=sys.stderr)
        return 1

    rc = cmd_trash_file(argparse.Namespace(vault=str(vault), path=str(target)))
    if rc != 0:
        # The file is still where it was, so the index still tells the truth. Leave it alone.
        return rc
    entfernt = _index_line_remove(bundle_dir / "INDEX.md", slug)
    _append_activity_log(vault, "zanmai.py",
                         f"discarded {slug} from {bundle_dir.relative_to(vault).as_posix()}/ "
                         f"(to {TRASH_DIR}/, index entry {'removed' if entfernt else 'was not present'})")
    print(f"ok: {slug} moved to {TRASH_DIR}/ and taken out of the bundle index")
    return 0


def _move_into(vault: Path, path: Path, folder: str, done: str, *, dated: bool = False) -> int:
    """Move a file to `<folder>/[<date>/]<its current vault-relative path>` and log it.

    The path under the folder is not decoration, it is the record of where the file came from.
    Nothing is written down beside it, no manifest, no sidecar: the only place a restore path can get
    out of sync with the file is a second place that also claims to know it.

    The trash adds the day it was thrown away as the first segment, and that is not tidiness either.
    The retention sweep has to know how long something has been in there, and the file's own
    timestamp answers a different question, when it was last edited. A file written a year ago and
    thrown away this morning would have been swept the same morning. Now the day is in the path,
    which means it survives a copy, a sync client and a restore, and the sweep is a date comparison
    on a folder name rather than a guess about what a timestamp means.
    """
    try:
        rel = path.relative_to(vault)
    except ValueError:
        print(f"fail: path '{path}' is not inside vault '{vault}'", file=sys.stderr)
        return 1
    if not path.exists():
        print(f"fail: path does not exist: {path}", file=sys.stderr)
        return 1

    rel_str = rel.as_posix()
    unter = Path(_today()) / rel if dated else rel
    target = vault / folder / unter
    if target.exists():
        print(f"fail: {folder}/{unter.as_posix()} is already taken. Deal with that copy first.",
              file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    _append_activity_log(vault, "zanmai.py", f"{done} {rel_str}")
    print(f"ok: {done} {rel_str} -> {target.relative_to(vault).as_posix()}")
    return 0


def cmd_trash_file(args: argparse.Namespace) -> int:
    """Move a file into vault-relative `<trash>/<original-path>`. Reversible with `file restore`."""
    vault = Path(args.vault).resolve()
    return _move_into(vault, Path(args.path).resolve(), TRASH_DIR, "trashed", dated=True)


def cmd_archive_file(args: argparse.Namespace) -> int:
    """Move a file into vault-relative `<archive>/<original-path>`. Reversible with `file restore`."""
    vault = Path(args.vault).resolve()
    return _move_into(vault, Path(args.path).resolve(), ARCHIVE_DIR, "archived")


def cmd_restore_file(args: argparse.Namespace) -> int:
    """Put a trashed or archived file back where it came from.

    The counterpart was missing: files went into the trash and nothing brought them out, which makes
    a trash a delete with extra steps. The origin is read off the path, so this works for anything
    that got there through `file trash` or `file archive`, whoever moved it.
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

    parts = rel.parts
    holder = next((f for f in (TRASH_DIR, ARCHIVE_DIR)
                   if rel.as_posix() == f or rel.as_posix().startswith(f"{f}/")), None)
    if holder is None:
        print(f"fail: {rel.as_posix()} is not in {TRASH_DIR}/ or {ARCHIVE_DIR}/, so there is nothing to restore it from",
              file=sys.stderr)
        return 1
    rest = list(parts[len(Path(holder).parts):])
    # The trash carries the day it was thrown away as its first segment; the archive does not.
    if holder == TRASH_DIR and rest and re.fullmatch(r"\d{4}-\d{2}-\d{2}", rest[0]):
        rest = rest[1:]
    if not rest:
        print(f"fail: {rel.as_posix()} is a folder, name a file inside it", file=sys.stderr)
        return 1
    origin_rel = Path(*rest)

    target = vault / origin_rel
    if target.exists():
        print(f"fail: {origin_rel.as_posix()} exists again. Move or rename it first, "
              f"otherwise the restore would overwrite it.", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    _append_activity_log(vault, "zanmai.py", f"restored {origin_rel.as_posix()} from {holder}/")
    print(f"ok: restored {origin_rel.as_posix()}")
    return 0


def cmd_register_contact(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    slug = _slugify(args.slug)
    target_dir = vault / (PEOPLE_DIR if args.kind == "person" else ORGANISATIONS_DIR)
    # `bundle create` makes its own folder; this one did not and died with a traceback instead. In a
    # set-up vault the folder is there, so it only ever showed on a vault that predates it.
    target_dir.mkdir(parents=True, exist_ok=True)
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
    # Straight from the schema, not from a second list typed out here. The hand-kept version had
    # drifted: `address` and `birthday` are in the schema for a person and were not accepted, so a
    # practice address ended up as body prose in the field's place.
    for k in KIND_FIELDS[kind_field]["optional"]:
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
#   zanmai/memory/vault-index.json. Pure-data layer, no domain knowledge.
#
# Schicht B: aggregate themes/hubs/bundles from Schicht A. Write
#   zanmai/memory/patterns.json. Still domain-free - token-overlap and graph
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


def _is_inside_database_folder(rel_path: str) -> bool:
    """Return True if a vault-relative path sits inside a `<Name>.base/` folder.

    Some editors keep a table or board as a folder with that suffix, holding a schema and rows that
    only that editor writes. They are the user's, whatever put them there, and Zanmai reads and
    writes nothing inside them. Detection is any path segment ending in `.base`."""
    for segment in rel_path.split("/"):
        if segment.endswith(".base") and len(segment) > len(".base"):
            return True
    return False


def _walk_vault_markdown(vault: Path, scope: str | None = None) -> list[Path]:
    """Walk markdown files under vault (or vault/scope). Skip the internal
    `zanmai/` tree entirely (contracts, generated state like `briefing.md`,
    logs, memory), it is not user content, its wikilink-shaped
    examples produce false-positive broken-link reports, and its per-session
    regeneration would otherwise make the index look perpetually stale. Also skip
    `.claude/`, the import folder, the root `CLAUDE.md`, and database
    folders (`<Name>.base/`, the user's own)."""
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
        if rel.startswith(f"{SYSTEM_DIR}/"):
            continue
        if rel.startswith(".claude/"):
            continue
        if rel.startswith(f"{IMPORT_DIR}/"):
            continue
        if rel == "CLAUDE.md":
            continue
        if _is_inside_database_folder(rel):
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

    target = vault / MEMORY_DIR / "vault-index.json"
    _atomic_write_json(target, out)

    # Clear the stale marker; the index now reflects current state.
    stale_marker = vault / MEMORY_DIR / ".index-stale"
    if stale_marker.exists():
        try:
            stale_marker.unlink()
        except OSError:
            pass

    if not args.quiet:
        print(f"reindex ok: {len(entries)} files -> {target.relative_to(vault)}")
    return 0


def _bundle_segments(rel_path: str) -> tuple[str, str] | None:
    """Return (kind-folder, slug) if rel_path sits inside a `<kind>/<slug>/` bundle, else None.

    Two segments plus a file, not three: the kind folder is a vault root now, so the shortest path
    into a bundle is `<kind>/<slug>/<file>`.
    """
    parts = rel_path.split("/")
    if len(parts) < 3 or parts[0] not in BUNDLE_FOLDERS:
        return None
    kind, slug = parts[0], parts[1]
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
    """Detect bundles under <kind>/<slug>/. Aggregate tokens across bundle members."""
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
                "path": f"{kind}/{slug}",
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
    index_path = vault / MEMORY_DIR / "vault-index.json"
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

    target = vault / MEMORY_DIR / "patterns.json"
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
    patterns_path = vault / MEMORY_DIR / "patterns.json"
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

# The ten entries at the vault root, and what has to exist inside them. Flat on purpose: no
# container above the content folders, because a container is what the old `inbox/` was, and it put
# everything a person actually works with one level down while the machine sat on top.
#
# All ten are created even when empty, so the shape of the vault is visible before anything is in
# it. Areas inside `knowledge`, `trusted` and `archive` are deliberately NOT created: a life's
# subject headings belong to whoever owns the vault, and an example shipped in the distribution
# becomes a default nobody chose.
REQUIRED_FOLDERS_CORE = [
    # Where it falls in.
    DAILY_DIR,
    WEEKLY_DIR,
    MONTHLY_DIR,
    YEARLY_DIR,
    # Where it takes shape, gathers and settles.
    FOCUS_DIR,
    DOING_DIR,
    HABITS_DIR,
    KNOWLEDGE_DIR,
    TRUSTED_DIR,
    ARCHIVE_DIR,
    # Who it is about.
    PEOPLE_DIR,
    ORGANISATIONS_DIR,
    # Where it comes in.
    IMPORT_DIR,
    # What the machine keeps.
    EXTENSIONS_DIR,
    MEMORY_DIR,
    # `<memory>/agents/<name>` folders are derived from _MEMORY_AGENTS below, so the roster stays a
    # single source.
    LOGS_DIR,
    SCRATCH_DIR,
    TRASH_DIR,
    OPEN_DIR,
    # What the host reads.
    HOST_DIR,
]


def _required_folders(vault_root: Path) -> list[str]:
    """Every folder a set-up vault must have, from the one list above.

    The single source matters more than it looks. This used to be two lists, the one
    above for a fresh install and a copy of it in the manifest for an existing vault,
    and they drifted: a release added a folder here and not there, so a
    new vault got the folder and an updated one did not. The structure check read the
    manifest copy too, which is the part that makes such a drift invisible rather than
    merely wrong: producer and checker agreed with each other and were both missing
    the same entry, so a vault without the folder validated with exit code 0. One
    list, read by whoever creates and whoever checks, cannot disagree with itself.

    Excludes the runtime folder, which describes this machine and is created when something needs
    it, and the history, which git creates when the first snapshot is taken.
    """
    folders = list(REQUIRED_FOLDERS_CORE)
    folders += [f"{MEMORY_DIR}/agents/{name}" for name in _MEMORY_AGENTS]
    return folders


# The fixed family the vault root may hold, plus the generated files that live there. Anything
# else at the root is either a dotfile (an editor's or the OS's own business, left alone by
# design) or a folder that arrived outside any write Zanmai made, a manual Finder action, a
# colleague dropping something into a shared sync folder, a half-finished move. No hook can see
# or refuse that, since it happens outside any Claude Code session, so this is a detector rather
# than a guard: it surfaces the entry so it gets dealt with in days, not found by accident weeks
# later.
_VAULT_ROOT_ALLOWED_DIRS = frozenset({
    JOURNAL_DIR, FOCUS_DIR, DOING_DIR, HABITS_DIR, KNOWLEDGE_DIR, TRUSTED_DIR,
    ARCHIVE_DIR, CONTACTS_DIR, IMPORT_DIR, SYSTEM_DIR,
})
_VAULT_ROOT_ALLOWED_FILES = frozenset({"CLAUDE.md", "README.md", "INDEX.md"})


def _unexpected_root_entries(vault: Path) -> list[str]:
    """Names at the vault root outside the fixed family, dotfiles excluded. Empty when the root
    is exactly what setup and the folder architecture say it should be."""
    if not vault.is_dir():
        return []
    found = []
    for entry in sorted(vault.iterdir()):
        name = entry.name
        if name.startswith("."):
            continue
        if entry.is_dir() and name in _VAULT_ROOT_ALLOWED_DIRS:
            continue
        if entry.is_file() and name in _VAULT_ROOT_ALLOWED_FILES:
            continue
        found.append(name)
    return found


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
    pointing at the real procedure under `zanmai/system/skills/`. Real files,
    not symlinks, portable across machines and safe to copy or sync. The
    canonical procedure stays in the AI-neutral `zanmai/system/` tree, so a
    different host only needs its own adapter, not a rewrite. Stale adapters, a
    skill dropped by an update, or a legacy symlink from an older install, are
    pruned."""
    skills_dir = vault_root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for claude_folder, source_folder in mapping:
        source_rel = f"{SYSTEM_MATERIAL_DIR}/skills/{source_folder}/SKILL.md"
        source_file = vault_root / source_rel
        if not source_file.exists():
            continue
        fm = _frontmatter_block(source_file.read_text(encoding="utf-8"))
        # The adapter's name has to be the folder it sits in, because that is what the host offers as
        # a command. Copying the source's own `name:` shipped `zanmai:update` in a folder called
        # `zanmai-update`, and typing either one answered "Unknown command": the colon form is how a
        # plugin skill is addressed, not a project one. Found in a live vault on 2026-08-06, and it
        # was true for all eight commands at once.
        fm = re.sub(r"^name:.*$", f"name: {claude_folder}", fm, count=1, flags=re.M)
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
            is_ours = link.is_file() and f"{SYSTEM_MATERIAL_DIR}/skills/" in link.read_text(encoding="utf-8", errors="ignore")
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
#   memory, gets zanmai/memory/agents/<name>/ with a lessons.md to keep what a run taught it
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
    ("luis",    True,    True),
    ("shuri",   True,    True),
    ("ben",     True,    True),
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
    ("zanmai-write", "write"),
    ("zanmai-grill-me", "brief"),
    ("zanmai-greeting", "greeting"),
    # Below: the skills that carry the craft. They shipped for months with no adapter, which meant
    # the host never offered them and they were reached only when a contract line happened to be
    # remembered at the right moment. A skill the host cannot see is a file, not a capability. The
    # slash form is a side effect of registering; the point is the `description`, which is what the
    # host shows the model when it is deciding what this job needs.
    ("zanmai-classify-note", "classify-note"),
    ("zanmai-content-brief", "content-brief"),
    ("zanmai-design", "designer"),
    ("zanmai-powerpoint", "powerpoint"),
    ("zanmai-html", "html"),
    ("zanmai-typst", "typst"),
    ("zanmai-affinity", "affinity"),
    ("zanmai-media", "media"),
    ("zanmai-image-edit", "image-edit"),
    ("zanmai-video", "video"),
    ("zanmai-video-review", "video-review"),
    ("zanmai-motion", "motion"),
    ("zanmai-create-expert", "create-expert"),
    ("zanmai-create-launcher", "create-launcher"),
    ("zanmai-setup", "setup"),
]


def _model_overrides(vault_root: Path) -> dict[str, str]:
    """Per-expert model choices the user made in `zanmai/user.md`, as `models:` in the frontmatter.

    Absent means the contracts' own defaults apply. Nothing here is guessed and nothing is written
    back: which model an expert runs on is configuration, and a run never decides it about itself.
    """
    user_md = vault_root / SYSTEM_DIR / "user.md"
    if not user_md.is_file():
        return {}
    try:
        fm = _frontmatter_block(user_md.read_text(encoding="utf-8"))
    except OSError:
        return {}
    block = re.search(r"^models:\s*$((?:\n[ \t]+\S.*)*)", fm, re.M)
    if not block:
        return {}
    return {m.group(1): m.group(2).strip().strip('"')
            for m in re.finditer(r"^[ \t]+([a-z]+):[ \t]*(\S+)", block.group(1), re.M)}


def _install_agent_symlinks(vault_root: Path, agent_names: list[str]) -> None:
    """Write a thin adapter `.claude/agents/<name>.md` for each expert: the
    expert's frontmatter (so the host discovers it) plus a one-line body pointing
    at the real contract under `zanmai/system/experts/`. Real files, not
    symlinks, portable and copy/sync-safe. The contract stays in the AI-neutral
    `zanmai/system/` tree, so another host only needs its own adapter. Stale
    adapters, an expert dropped by an update, or a legacy symlink, are
    pruned so no dead agent is left behind."""
    agents_dir = vault_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    model_overrides = _model_overrides(vault_root)
    for name in agent_names:
        source_rel = f"{SYSTEM_MATERIAL_DIR}/experts/{name}/{name}.md"
        source_file = vault_root / source_rel
        if not source_file.exists():
            continue
        fm = _frontmatter_block(source_file.read_text(encoding="utf-8"))
        # A model set in `zanmai/user.md` wins over the one the contract ships with. The contract is
        # replaced by every update, so a choice written there would be silently undone; and the choice
        # is the user's to begin with, not something a run decides about itself.
        gewaehlt = model_overrides.get(name)
        if gewaehlt:
            fm = (re.sub(r"^model:.*$", f"model: {gewaehlt}", fm, count=1, flags=re.M)
                  if re.search(r"^model:", fm, re.M) else fm.rstrip() + f"\nmodel: {gewaehlt}")
        # A reading list in execution order, not a pointer. "Read your contract" left it to the
        # run to work out what else it needed and when, and what it did not think of, it did not
        # read: the rule that turned a dispatch back sat in a file nobody opened at the moment of
        # dispatch. Numbered steps that name the file and say when it applies are what a fresh
        # context can actually follow.
        body = (
            f"\n\nAdapter only, so the host can find you. The procedure lives in the vault.\n\n"
            f"## On every invocation, in order\n\n"
            f"1. Read `{source_rel}`, your full contract. It is authoritative over anything here.\n"
            f"2. Read `{SYSTEM_MATERIAL_DIR}/operating-principles.md` for the rules that hold across "
            f"every expert: approval before write, source files, indexing and logging, how a reply "
            f"reads.\n"
            f"3. Read the skills your contract names for this job, at the point the job needs them, "
            f"from `{SYSTEM_MATERIAL_DIR}/skills/<name>/SKILL.md`. Anything longer than a line that "
            f"gets written for the user goes through the `write` skill, whoever runs it.\n\n"
            f"## Cold start\n\n"
            f"Your context is fresh every time. What you were not handed, you do not know. Where the "
            f"brief is too thin to act on, say so in the return rather than inventing the missing "
            f"half: you run in the background and have nobody to ask.\n\n"
            f"## What you return\n\n"
            f"One status line, then the paths of every file you wrote, then anything you parked for "
            f"the user, then anomalies. Your final text is the return value, not a message to a "
            f"person."
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
            is_ours = entry.is_file() and f"{SYSTEM_MATERIAL_DIR}/experts/" in entry.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            is_ours = entry.is_symlink()  # legacy dangling symlink
        if is_ours or (entry.is_symlink() and not entry.exists()):
            entry.unlink()


def _render_user_md_init(
    *, first_name: str, last_name: str, language: str, owner_contact_slug: str,
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
update_channel: ""
auto_snapshots: true
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

- `models:` (optional). Which model each expert runs on, one line per expert, for example `carol: opus`
  or `pepper: haiku`. Absent means the default each expert's contract ships with. This lives here and
  not in the contracts because an update replaces those, and because the choice is yours: no run
  decides how hard its own work is. A job that genuinely needs more says so and waits for you.
- `auto_snapshots: true`. Master switch for every snapshot Zanmai takes on its own, which is only ever before it overwrites existing material (update, bulk repair, vault-wide rename, restore). When `false`, all `zanmai.py snapshot create` calls exit silently with `skip: auto_snapshots disabled` and no folder is written, useful when the user has their own backup discipline (git, Time Machine, ...). Flip it with `zanmai.py snapshot enable` / `disable` or by editing this line directly.
- `python_cmd: "{python_cmd}"`. The Python invocation that worked at setup time. Steve uses this when running scripts, substitutes for `python3` in skill template phrasing. On Windows this is often `py -3` or `python`, on Linux and macOS usually `python3`.
- `update_channel: ""`. Which branch `zanmai.py setup upgrade` tracks. Empty means the published release. Set with `zanmai.py setup upgrade . --channel <name>`, which switches immediately and remembers the choice here, update-immune so it survives every future update; `--channel release` switches back.
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
This is the owner contact for this vault. `zanmai/user.md` points here as `owner_contact`. Steve reads it at session start to know who the user is.

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

The order below is the way things travel: they arrive in the journal, take shape in focus and on
the desk, gather in knowledge, and settle into what recurs and what holds. Nothing has to move
along it. Staying put is a valid end state everywhere except the desk.

## Journal

`{JOURNAL_DIR}/` is the time axis: a bundle per day, week, month and year. What is on your mind goes
in the day, and what happened on a day belongs to that day. Nothing is ever taken out of an entry.

## Focus

What you want to reach and what you are looking at. See `{FOCUS_DIR}/`.

(empty. Nothing in focus yet.)

## Doing

The desk: work that has an end, with every draft of it together in one bundle. You put things here
and so does Zanmai. See `{DOING_DIR}/`.

(empty)

## Habits

What has a beat. See `{HABITS_DIR}/`.

(empty)

## Knowledge

Everything gathered, with no ranking, and it is allowed to contradict itself. The default place for
anything that does not clearly belong elsewhere, and the place where most of it stays. See
`{KNOWLEDGE_DIR}/`.

(empty)

## Trusted

What you have settled on and what cannot be worked out from the files themselves. Small, curated,
one answer per question. See `{TRUSTED_DIR}/`.

(empty)

## Archive

Finished and kept: the document from outside and your own completed piece. It answers no question
any more, and nothing has to end up here. See `{ARCHIVE_DIR}/`.

(empty)

## Contacts

Single files per person and organisation.

### People (`{PEOPLE_DIR}/`)

(empty)

### Organisations (`{ORGANISATIONS_DIR}/`)

(empty)

## Import

`{IMPORT_DIR}/` is where you drop things. However it lands in there, Zanmai takes it up by itself;
the kind of file decides what happens to it, not a sub-folder. It empties itself.

## System

- `{USER_FILE}`: your profile.
- `{SYSTEM_MATERIAL_DIR}/`: the Zanmai distribution (do not edit, replaced on update).
- `{MEMORY_DIR}/`: cross-session learnings and activity log.
- `{HISTORY_DIR}/`: the snapshot history, every version of every file kept once.
- `{TRASH_DIR}/`: what was thrown away, restorable for 30 days.
- `{SCRATCH_DIR}/`: what the machine puts down mid-job, cleared after 30 days.
- `{LOGS_DIR}/`: session logs and operation reports.
"""


def _render_settings_json(vault_root: Path, *, python_cmd: str = "python3") -> str:
    """Render .claude/settings.json with the Zanmai hooks wired. Every
    hook is a subcommand of the single zanmai.py CLI now. No connection-guard:
    a host-exposed MCP is available for use, Zanmai adds no second consent gate
    (LD6, re-decided 2026-07-15). The script path is rooted at $CLAUDE_PROJECT_DIR,
    which Claude Code shell-expands to the project root at hook run time, so this
    file is portable: it ships with the folder and works wherever the vault is
    copied, no absolute machine path baked in. vault_root is kept in the signature
    for the callers that pass it; the rendered command no longer needs it.

    `defaultMode: auto` is set here rather than left to the user. Zanmai routes nearly
    every filing, index and check through its own engine, so the strictest mode turns a
    session into a queue of prompts, and the person who has just finished setup is the
    least equipped to know that a mode switch is what they need. The value is written
    into the vault's own settings, never into the user's global config, so it applies
    where Zanmai runs and nowhere else. Zanmai's own guards do not depend on it: they
    are checks on every write, not questions put to the user."""
    zb = f"$CLAUDE_PROJECT_DIR/{SYSTEM_MATERIAL_DIR}/scripts/zanmai.py"
    config = {
        "autoMemoryEnabled": False,
        "permissions": {"defaultMode": "auto"},
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
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook checkbox-guard'},
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook prose-guard'},
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
                {
                    "matcher": "mcp__.*",
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook outward-guard'},
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook delete-guard'},
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook library-check-guard'},
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook prose-guard'},
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
            "SessionEnd": [
                {
                    "hooks": [
                        {"type": "command", "command": f'{python_cmd} "{zb}" hook session-end'}
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
        if not (vault / SYSTEM_MATERIAL_DIR / "skills" / source_folder / "SKILL.md").is_file():
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
    experts_dir = vault_root / SYSTEM_MATERIAL_DIR / "experts"
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
    scripts_dir = vault_root / SYSTEM_MATERIAL_DIR / "scripts"
    rel = f"{SYSTEM_MATERIAL_DIR}/scripts/zanmai.py"
    # Both spellings, because a rule matches the command as it was typed. Only the absolute form was
    # shipped, while every caller in the vault runs from the vault root and types the relative path,
    # so the rule never matched anything and every write went to a permission prompt. It stayed
    # invisible because read-only calls are waved through on their own merits: the update check ran,
    # and the apply right behind it stopped dead. Measured in a live vault on 2026-08-06.
    allow = [
        f'Bash({python_cmd} "{scripts_dir}/zanmai.py":*)',
        f'Bash({python_cmd} {scripts_dir}/zanmai.py:*)',
        f'Bash({python_cmd} {rel}:*)',
        f'Bash({python_cmd} "{rel}":*)',
    ]
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
) -> None:
    """First-time vault setup. Creates folder skeleton, user.md, owner-contact,
    settings, symlinks, memory files and master INDEX. Idempotent only on the
    folder mkdir step; file writes overwrite. Used by `setup init`."""
    folders = _required_folders(vault_root)
    for rel in folders:
        (vault_root / rel).mkdir(parents=True, exist_ok=True)

    nickname = preferred_address.strip() if preferred_address.strip() and preferred_address.strip() != first_name else ""

    contact_slug = _slugify(f"{first_name} {last_name}")
    contact_path_abs = vault_root / PEOPLE_DIR / f"{contact_slug}.md"
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

    user_md = vault_root / SYSTEM_DIR / "user.md"
    user_md.write_text(
        _render_user_md_init(
            first_name=first_name,
            last_name=last_name,
            language=language,
            owner_contact_slug=contact_slug,
            preferred_address=nickname,
            python_cmd=python_cmd,
        ),
        encoding="utf-8",
    )

    (vault_root / ".claude" / "settings.json").write_text(
        _render_settings_json(vault_root, python_cmd=python_cmd), encoding="utf-8"
    )

    # The distribution repository's ignore rules go where only it reads them, and the history of the
    # user's own material starts here, with the empty vault as its first state. Starting it now
    # rather than at the first risky write means there is always something to compare against.
    _write_dist_exclude(vault_root)
    if shutil.which("git") is not None:
        try:
            _history_ensure(vault_root)
            _git(vault_root, "add", "-A")
            if _git(vault_root, "rev-parse", "HEAD", check=False).returncode != 0:
                _git(vault_root, "commit", "-q", "-m", "the-vault-as-it-was-set-up")
        except RuntimeError:
            pass  # a vault without a history still works; the first snapshot starts one

    _install_skill_symlinks(vault_root, _SKILL_SYMLINK_MAP)

    _install_agent_symlinks(vault_root, _AGENT_NAMES)

    settings_local = vault_root / ".claude" / "settings.local.json"
    if not settings_local.exists():
        settings_local.write_text(
            _render_settings_local_json(vault_root, python_cmd=python_cmd), encoding="utf-8"
        )

    (vault_root / MEMORY_DIR / "general.md").write_text(
        _render_general_md(contact_slug), encoding="utf-8"
    )
    (vault_root / MEMORY_DIR / "activity-log.md").write_text(
        _render_activity_log(), encoding="utf-8"
    )
    for agent in _MEMORY_AGENTS:
        (vault_root / MEMORY_DIR / "agents" / agent / "lessons.md").write_text(
            _render_agent_lessons(agent.capitalize()), encoding="utf-8"
        )

    (vault_root / "INDEX.md").write_text(_render_master_index(first_name), encoding="utf-8")

    (vault_root / LOGS_DIR / ".keep").touch()


def cmd_setup_init(args: argparse.Namespace) -> int:
    vault = Path(args.vault_root).resolve()
    if not vault.exists():
        print(f"fail: vault root does not exist: {vault}", file=sys.stderr)
        return 1
    user_md = vault / SYSTEM_DIR / "user.md"
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
    version_file = vault_or_tree / SYSTEM_MATERIAL_DIR / "VERSION"
    if not version_file.exists():
        return ""
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("distribution_version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


# --- One-off repairs to a vault that already exists -------------------------
#
# The rules that keep the user's material out of the distribution repository. They used to live in a
# `.gitignore` in the vault, and that was the problem: a file in the working tree is read by every
# repository that shares the tree, and by every search tool. So the history repository inherited them
# and left out exactly what it exists to keep, and a search across the user's own notes came back
# empty. Here they reach only the repository they belong to.
#
# Built from the folder constants rather than typed out, because a hand-kept second list of the same
# names is how a renamed folder ends up shipped: the rename lands in one list, the other keeps
# excluding a folder that no longer exists, and the new one gets committed into the distribution
# with the user's material in it. Nothing here is a name in its own right.
_DIST_EXCLUDE_OWN = (
    # Everything of the user's, at the root.
    *(f"/{d}/" for d in USER_ROOTS),
    f"/{IMPORT_DIR}/",
    "/INDEX.md",
    # Inside the system folder, everything except the distribution itself.
    f"/{USER_FILE}",
    f"/{SYSTEM_DIR}/update-history.md",
    *(f"/{d}/" for d in (EXTENSIONS_DIR, CONNECTIONS_DIR, MEMORY_DIR, LOGS_DIR,
                         HISTORY_DIR, RUNTIME_DIR, SCRATCH_DIR, TRASH_DIR, OPEN_DIR)),
    f"/{SYSTEM_DIR}/design/",
    # What the host reads, and what every machine leaves lying around.
    f"/{HOST_DIR}/",
    ".DS_Store",
    "__pycache__/",
    "*.pyc",
)

_DIST_EXCLUDE = (
    "# What the distribution repository leaves alone: everything that is yours.\n"
    f"# Written by zanmai.py, edits here are overwritten. The history in {HISTORY_DIR}/ keeps your\n"
    "# material; this repository only tracks what Zanmai ships.\n"
    + "".join(f"{line}\n" for line in _DIST_EXCLUDE_OWN)
)


def _write_dist_exclude(vault: Path) -> bool:
    """Put the distribution's ignore rules where only its own repository reads them."""
    if not (vault / ".git").is_dir():
        return False
    info = vault / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "exclude").write_text(_DIST_EXCLUDE, encoding="utf-8")
    return True


# How long the machine keeps what it put aside. One number for both folders, because two numbers
# would be two things to remember and nobody would remember them. Thirty days is long
# enough that "I need that back" has already happened by then, and short enough that a vault does not
# quietly grow a second copy of itself.
#
# This runs on its own, at session start, and reports what it did. That is deliberate: a cleanup that
# waits for someone to agree to it is a cleanup that never happens, and both of these folders hold
# only what the machine itself put there. Nothing the user filed is ever in scope. Snapshots are not
# in it at all any more: the history keeps every file once by content, so age is not what costs.
RETENTION_DAYS = 30

def _lesbare_groesse(bytes_gesamt: float) -> str:
    for einheit in ("B", "KB", "MB", "GB"):
        if bytes_gesamt < 1024 or einheit == "GB":
            return f"{bytes_gesamt:.0f} {einheit}" if einheit == "B" else f"{bytes_gesamt:.1f} {einheit}"
        bytes_gesamt /= 1024
    return "0 B"


def _trash_days_past_retention(vault: Path) -> list[Path]:
    """Whole days in the trash that are past the keeping time.

    The date is read off the folder name, never off a file timestamp: the timestamp says when
    something was last edited, which has nothing to do with when it was discarded.
    """
    root = vault / TRASH_DIR
    if not root.is_dir():
        return []
    grenze = datetime.now() - timedelta(days=RETENTION_DAYS)
    alt = []
    for tag in sorted(p for p in root.iterdir() if p.is_dir()):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tag.name):
            continue
        if datetime.strptime(tag.name, "%Y-%m-%d") < grenze:
            alt.append(tag)
    return alt


def _past_retention(root: Path) -> list[Path]:
    """Top-level entries under a machine folder that are older than the retention window."""
    if not root.is_dir():
        return []
    grenze = (datetime.now() - timedelta(days=RETENTION_DAYS)).timestamp()
    return sorted(p for p in root.iterdir()
                  if not p.name.startswith(".") and p.stat().st_mtime < grenze)


def _sweep_retention(vault: Path) -> list[str]:
    """Clear what is past its keeping time, and say what went. One rule, two folders, no question.

    This is the only place in Zanmai that deletes, and it can only ever reach material the machine
    put there itself: what someone threw away, what a run left behind, and the copies taken before a
    risky write. Nothing the user filed is in scope, and nothing here is decided by judgement at the
    moment of deleting; the folder and the age decide, which is what makes it safe to run unattended.
    """
    notes: list[str] = []

    weg = _trash_days_past_retention(vault)
    if weg:
        dateien = sum(1 for tag in weg for f in tag.rglob("*") if f.is_file())
        groesse = _lesbare_groesse(sum(f.stat().st_size for tag in weg
                                       for f in tag.rglob("*") if f.is_file()))
        for tag in weg:
            shutil.rmtree(tag)
        notes.append(f"emptied {dateien} file(s) from {TRASH_DIR}/, thrown away more than "
                     f"{RETENTION_DAYS} days ago ({groesse}).")

    liegen = _past_retention(vault / SCRATCH_DIR)
    if liegen:
        for p in liegen:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        notes.append(f"cleared {len(liegen)} leftover(s) from {SCRATCH_DIR}/ older than "
                     f"{RETENTION_DAYS} days. Scratch space is not meant to hold anything that long, "
                     f"so each of those is a run that never finished tidying up after itself.")

    if notes:
        _append_activity_log(vault, "zanmai.py", "retention sweep: " + " ".join(notes))
    return notes


def cmd_housekeeping(args: argparse.Namespace) -> int:
    """Run the retention sweep by hand. It also runs itself at every session start."""
    vault = Path(args.vault).resolve()
    notes = _sweep_retention(vault)
    if not notes:
        print(f"ok: nothing is past {RETENTION_DAYS} days")
        return 0
    for n in notes:
        print(f"ok: {n}")
    return 0


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
    if len(roots) == 1 and not (into / SYSTEM_DIR).exists():
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
    shown = run("show", f"origin/{branch}:{SYSTEM_MATERIAL_DIR}/VERSION")
    if shown.returncode != 0:
        return ""
    for line in shown.stdout.splitlines():
        if line.startswith("distribution_version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


def _remote_changelog_via_git(vault: Path, branch: str) -> str:
    """The origin's CHANGELOG.md, unapplied.

    A preview built before Apply (Pepper's Update workflow step 2, before step
    5) has no local file to read yet: the working tree still holds the old
    version. `fetch` already ran in `_remote_version_via_git` right before
    this is called, so the ref is current; a second cheap fetch here would
    only be needed if this were ever called on its own.
    """
    import subprocess

    shown = subprocess.run(
        ["git", "-C", str(vault), "show", f"origin/{branch}:{SYSTEM_MATERIAL_DIR}/CHANGELOG.md"],
        capture_output=True, text=True, timeout=120,
    )
    return shown.stdout if shown.returncode == 0 else ""


def _remote_changelog_via_https(source: str, branch: str) -> str:
    """The origin's CHANGELOG.md for a non-clone vault, fetched over HTTPS, unapplied."""
    try:
        raw = _fetch(
            f"https://raw.githubusercontent.com/{source.strip('/')}/{branch}/{SYSTEM_MATERIAL_DIR}/CHANGELOG.md"
        )
        return raw.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
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
    script = vault / SYSTEM_MATERIAL_DIR / "scripts" / "zanmai.py"
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
    marker = vault / RUNTIME_DIR / "host-config-version"
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
    cache = vault / RUNTIME_DIR / "update-check.json"
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

    manifest = vault / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    source = _manifest_scalar(manifest, "update_source") if manifest.exists() else ""
    default_branch = _manifest_scalar(manifest, "update_branch") or "main" if manifest.exists() else "main"
    branch = _update_channel(vault) or default_branch
    available = ""
    if source:
        try:
            raw = _fetch(
                f"https://raw.githubusercontent.com/{source.strip('/')}/{branch}/{SYSTEM_MATERIAL_DIR}/VERSION",
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
    logs_dir = vault / LOGS_DIR
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
    state_file = vault / RUNTIME_DIR / "session-state.json"
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
    cache = vault / RUNTIME_DIR / "update-check.json"
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
    script = vault / SYSTEM_MATERIAL_DIR / "scripts" / "zanmai.py"
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


def _update_channel(vault: Path) -> str:
    """The branch `zanmai/user.md` names to track, or "" for the manifest's default.

    Update-immune by construction: `user.md` is never touched by an update, so a
    channel choice survives the very upgrades it steers. "release" and "" both
    mean "no override, follow the manifest's `update_branch`" (currently `main`).
    """
    user_md = vault / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return ""
    try:
        fm, _order, _body = _split_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return ""
    channel = str(fm.get("update_channel") or "").strip()
    return "" if channel in ("", "release") else channel


def _set_update_channel(vault: Path, channel: str) -> None:
    """Persist the channel choice to `zanmai/user.md`. "release" clears the override."""
    user_md = vault / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return
    text = user_md.read_text(encoding="utf-8")
    fm, order, body = _split_frontmatter(text)
    fm["update_channel"] = "" if channel == "release" else channel
    if "update_channel" not in order:
        # Placed right after python_cmd, next to the other setup-time fields.
        insert_at = order.index("python_cmd") + 1 if "python_cmd" in order else len(order)
        order.insert(insert_at, "update_channel")
    user_md.write_text(_render_frontmatter(fm, order) + body, encoding="utf-8")


def cmd_setup_upgrade(args: argparse.Namespace) -> int:
    """Replace the distribution files with the newest published version.

    Deliberately independent of how the vault arrived: an unpacked archive
    updates exactly like a clone. A clone is fast-forwarded through git so it
    stays a clean clone; anything else has the new files fetched over HTTPS.
    Only paths the manifest calls distribution are touched.
    """
    vault = Path(args.vault_root).resolve()
    manifest = vault / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    if not manifest.exists():
        print(f"error: no Zanmai system folder at {vault}", file=sys.stderr)
        return 1

    requested_channel = getattr(args, "channel", None)
    if requested_channel:
        _set_update_channel(vault, requested_channel)

    local = _distribution_version(vault)
    channel = _update_channel(vault)
    branch = channel or _manifest_scalar(manifest, "update_branch") or "main"
    is_clone = bool(_clone_remote(vault))

    # Named per branch, because a clone asks its own git remote and every other vault
    # asks the manifest's source. It used to be read from the manifest either way,
    # which for a clone read a name that was never assigned: the command crashed with
    # an interpreter error the moment an update genuinely existed, which is the one
    # moment it is ever run. A clone that was up to date returned before reaching the
    # line, so the fault sat there through several releases and surfaced as a
    # traceback in front of the user rather than a version to say yes to.
    if is_clone:
        origin = _clone_remote(vault) or "the repository this vault was cloned from"
        remote = _remote_version_via_git(vault, branch)
        if not remote:
            print("error: could not read a version from this vault's own origin", file=sys.stderr)
            return 1
    else:
        source = _manifest_scalar(manifest, "update_source")
        origin = source or "an unset origin"
        if not source:
            print("error: the manifest names no update source", file=sys.stderr)
            return 1
        base = source.strip("/")
        try:
            raw = _fetch(
                f"https://raw.githubusercontent.com/{base}/{branch}/{SYSTEM_MATERIAL_DIR}/VERSION"
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

    channel_note = f", channel: {channel}" if channel else ""
    if not _is_newer(remote, local):
        print(f"ok: already on the current version ({local}{channel_note})")
        return 0

    print(f"update available: {local} -> {remote} (from {origin}{channel_note})")
    if args.check:
        if getattr(args, "changelog", False):
            changelog = (_remote_changelog_via_git(vault, branch) if is_clone
                         else _remote_changelog_via_https(source, branch))
            if changelog:
                print("--- remote CHANGELOG.md ---")
                print(changelog)
            else:
                print("warning: could not read the remote CHANGELOG.md", file=sys.stderr)
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
        new_manifest = tree / SYSTEM_MATERIAL_DIR / "manifest.yaml"
        if not new_manifest.exists():
            print("error: the downloaded version has no manifest, nothing applied", file=sys.stderr)
            return 1

        new_paths = _manifest_distribution_paths(new_manifest)
        old_paths = _manifest_distribution_paths(manifest)

        # Both path lists come out of a manifest that was just downloaded, so they
        # are input, not fact. Without a containment check, one `../` in a path
        # writes outside the vault, and the removal loop below deletes outside it.
        # Resolve BOTH sides: resolving only the candidate refuses every update on
        # macOS, where the temporary directory is itself a symlink. A guard that then
        # blocks every legitimate update has not made anything safer, it has only
        # traded one failure for a worse one.
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
    user_md = vault / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        fails.append("missing zanmai/user.md, run 'setup init' first")
    manifest_path = vault / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    if not manifest_path.exists():
        fails.append("missing zanmai/system/manifest.yaml")
    else:
        for rel in _manifest_distribution_paths(manifest_path):
            if not (vault / rel).exists():
                fails.append(f"missing distribution file: {rel}")
    for rel in _required_folders(vault):
        if not (vault / rel).is_dir():
            fails.append(f"missing required folder: {rel}. Run 'setup update' to create it.")
    for rel in ["INDEX.md", f"{MEMORY_DIR}/general.md", ACTIVITY_LOG_FILE]:
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
                ours = entry.is_file() and f"{SYSTEM_MATERIAL_DIR}/experts/" in entry.read_text(encoding="utf-8", errors="ignore")
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
            for f in vault.glob("**/*")
            if f.is_file() and any(mark in f.name.lower() for mark in
                                   ("conflicted copy", "conflict)", "-konflikt", "in konflikt"))
        )
        if conflicts:
            fails.append(
                f"{len(conflicts)} sync conflict copy/copies in the vault, which break the rule that a "
                f"fact exists once: {', '.join(conflicts[:5])}"
                + (" …" if len(conflicts) > 5 else "")
            )

    stray = _unexpected_root_entries(vault)
    if stray:
        fails.append(
            f"{len(stray)} entr(y/ies) at the vault root outside the folder architecture: "
            f"{', '.join(stray[:5])}"
            + (" …" if len(stray) > 5 else "")
            + ". Nothing writes there on its own, this got created outside a Zanmai session, "
              "move its contents into the right theme and remove it."
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
    user_md = vault / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        print(
            f"fail: vault not initialised (no zanmai/user.md). Run 'setup init' first.",
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
        lessons = vault / MEMORY_DIR / "agents" / agent / "lessons.md"
        if not lessons.exists():
            lessons.parent.mkdir(parents=True, exist_ok=True)
            lessons.write_text(_render_agent_lessons(agent.capitalize()), encoding="utf-8")

    print(
        f"ok: refresh complete at {vault} "
        f"(agent symlinks, skill symlinks, settings.json, settings.local.json)"
    )
    return 0


# Snapshot ----

def _set_auto_snapshots_flag(vault_root: Path, enabled: bool) -> int:
    """Flip `auto_snapshots` in `zanmai/user.md`. Replaces an existing
    `auto_snapshots` line; if it is not present, inserts `auto_snapshots:`
    before the closing frontmatter delimiter."""
    user_md = vault_root / SYSTEM_DIR / "user.md"
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


# What the history never takes in. Two of them are the machine's own bookkeeping, and one is the
# distribution's git dir: a repository inside a repository is how the first attempt at this quadrupled
# in size over four snapshots, each one swallowing the last.
_HISTORY_EXCLUDE = (
    ".git/",
    f"{HISTORY_DIR}/",
    f"{RUNTIME_DIR}/",
    f"{SCRATCH_DIR}/",
    ".DS_Store",
    "__pycache__/",
    "*.pyc",
)


def _git(vault: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run git against the history repository: its own git dir, the vault as the working tree.

    Two repositories share this folder. The distribution's `.git/` tracks what ships and is how an
    update arrives; this one tracks what the user owns and never leaves the machine. Keeping them
    apart is one environment variable, and it is what makes a snapshot cost the change rather than a
    copy of everything.
    """
    env = {**os.environ,
           "GIT_DIR": str(vault / HISTORY_DIR),
           "GIT_WORK_TREE": str(vault),
           "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(["git", *args], env=env, cwd=str(vault),
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _history_ready(vault: Path) -> bool:
    return (vault / HISTORY_DIR / "HEAD").is_file()


def _history_ensure(vault: Path) -> list[str]:
    """Create the history repository if it is not there. Idempotent, says what it did.

    The excludes live in the repository's own `info/exclude`, not in a `.gitignore` in the vault: a
    file in the working tree would be read by both repositories, and the two want opposite things.
    """
    notes: list[str] = []
    if not _history_ready(vault):
        (vault / HISTORY_DIR).parent.mkdir(parents=True, exist_ok=True)
        _git(vault, "init", "-q", "-b", "main")
        notes.append(f"started the history in {HISTORY_DIR}/")
    (vault / HISTORY_DIR / "info").mkdir(parents=True, exist_ok=True)
    (vault / HISTORY_DIR / "info" / "exclude").write_text(
        "# What the history leaves out. Written by zanmai.py, edits are overwritten.\n"
        + "\n".join(_HISTORY_EXCLUDE) + "\n", encoding="utf-8")
    # An identity, so a commit never fails on a machine where git was never configured. It is local
    # to this repository and says what it is, because nobody signed up to be an author here.
    _git(vault, "config", "user.name", "Zanmai")
    _git(vault, "config", "user.email", "zanmai@localhost")
    _git(vault, "config", "gc.auto", "256")
    return notes


def cmd_snapshot_list(args: argparse.Namespace) -> int:
    """List the snapshots, newest first: when, why, and the name to restore from."""
    vault = Path(args.vault).resolve()
    if not _history_ready(vault):
        print("no snapshots yet. The first one is taken before anything overwrites your material.")
        return 0
    log = _git(vault, "log", "--format=%h  %ad  %s", "--date=format:%Y-%m-%d %H:%M", check=False)
    if log.returncode != 0 or not log.stdout.strip():
        print("no snapshots yet. The first one is taken before anything overwrites your material.")
        return 0
    print(log.stdout, end="")
    anzahl = len(log.stdout.strip().splitlines())
    groesse = _lesbare_groesse(sum(f.stat().st_size for f in (vault / HISTORY_DIR).rglob("*") if f.is_file()))
    print(f"\n{anzahl} snapshot(s), {groesse} on disk for all of them together.")
    return 0


def cmd_snapshot_restore(args: argparse.Namespace) -> int:
    """Put one file back the way it was in a snapshot. The current version goes to the trash first.

    Only a named path, never the whole vault: restoring everything is a decision about material the
    user may have worked on since, and that is a conversation, not a flag.
    """
    vault = Path(args.vault).resolve()
    if not _history_ready(vault):
        print("fail: there are no snapshots to restore from", file=sys.stderr)
        return 1
    rel = args.path.replace("\\", "/").lstrip("/")
    zeigt = _git(vault, "show", f"{args.snapshot}:{rel}", check=False)
    if zeigt.returncode != 0:
        print(f"fail: {rel} is not in snapshot {args.snapshot}. `snapshot list` shows what there is, "
              f"and `snapshot show --snapshot <name>` lists what a snapshot holds.", file=sys.stderr)
        return 1
    jetzt = vault / rel
    if jetzt.is_file():
        rc = _move_into(vault, jetzt, TRASH_DIR, "trashed", dated=True)
        if rc != 0:
            return rc
    jetzt.parent.mkdir(parents=True, exist_ok=True)
    _git(vault, "checkout", args.snapshot, "--", rel)
    _append_activity_log(vault, "zanmai.py", f"restored {rel} from snapshot {args.snapshot}")
    print(f"ok: {rel} is back as it was in {args.snapshot}. The version that was there went to "
          f"{TRASH_DIR}/, so this is undoable too.")
    return 0


def cmd_snapshot_show(args: argparse.Namespace) -> int:
    """What one snapshot holds, or what changed in it."""
    vault = Path(args.vault).resolve()
    if not _history_ready(vault):
        print("no snapshots yet")
        return 0
    if args.path:
        out = _git(vault, "show", f"{args.snapshot}:{args.path.lstrip('/')}", check=False)
        if out.returncode != 0:
            print(f"fail: {args.path} is not in snapshot {args.snapshot}", file=sys.stderr)
            return 1
        print(out.stdout, end="")
        return 0
    out = _git(vault, "show", "--stat", "--format=%h  %ad  %s",
               "--date=format:%Y-%m-%d %H:%M", args.snapshot, check=False)
    if out.returncode != 0:
        print(f"fail: no such snapshot: {args.snapshot}", file=sys.stderr)
        return 1
    print(out.stdout, end="")
    return 0


def cmd_snapshot_compact(args: argparse.Namespace) -> int:
    """Let git pack the history down. Loses nothing, every snapshot stays."""
    vault = Path(args.vault).resolve()
    if not _history_ready(vault):
        print("no history to compact")
        return 0
    vorher = sum(f.stat().st_size for f in (vault / HISTORY_DIR).rglob("*") if f.is_file())
    _git(vault, "gc", "--quiet")
    nachher = sum(f.stat().st_size for f in (vault / HISTORY_DIR).rglob("*") if f.is_file())
    print(f"ok: history packed, {_lesbare_groesse(vorher)} -> {_lesbare_groesse(nachher)}. "
          f"Every snapshot is still there.")
    return 0


def _read_auto_snapshots_flag(vault_root: Path) -> bool:
    """Return the `auto_snapshots` flag from `zanmai/user.md` (default true).
    Default-true means a vault without user.md (e.g. the builder's own dist
    tree) is never blocked by this check."""
    user_md = vault_root / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return True
    try:
        fm = _session_parse_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return True
    raw = fm.get("auto_snapshots", "true")
    return str(raw).strip().strip('"').lower() != "false"


def cmd_snapshot_create(args: argparse.Namespace) -> int:
    """Take a snapshot: commit the whole vault into the history repository.

    A snapshot used to be a full copy of the vault, which cost what the user owns every single time
    while protecting one change. Measured in a live vault: two copies, thirteen gigabytes, for three
    gigabytes of material, because each copy also copied the copies before it. The history stores
    every file once by content, so an unchanged file costs nothing on the second snapshot and a
    changed line costs the line.

    Respects `auto_snapshots: false` in `zanmai/user.md`.
    """
    vault = Path(args.vault).resolve()
    if not args.reason.strip():
        print("fail: reason-slug empty", file=sys.stderr)
        return 1
    reason = _slugify(args.reason)
    if not _read_auto_snapshots_flag(vault):
        print(f"skip: auto_snapshots disabled in {USER_FILE}")
        return 0
    if not vault.is_dir():
        print(f"fail: not a directory: {vault}", file=sys.stderr)
        return 1
    if shutil.which("git") is None:
        print("fail: git is not on this machine, and the history is a git repository. "
              "Install git, then take the snapshot again. Nothing has been changed.", file=sys.stderr)
        return 1

    try:
        for note in _history_ensure(vault):
            print(f"ok: {note}")
        _git(vault, "add", "-A")
        stand = _git(vault, "status", "--porcelain")
        if not stand.stdout.strip() and _git(vault, "rev-parse", "HEAD", check=False).returncode == 0:
            letzte = _git(vault, "log", "-1", "--format=%h %s", check=False).stdout.strip()
            print(f"ok: nothing has changed since the last snapshot ({letzte}), so there is nothing "
                  f"to take. That one still covers you.")
            return 0
        _git(vault, "commit", "-q", "-m", reason)
        kurz = _git(vault, "rev-parse", "--short", "HEAD").stdout.strip()
    except RuntimeError as exc:
        print(f"fail: the snapshot could not be taken ({exc}). Nothing has been changed.",
              file=sys.stderr)
        return 1

    _append_activity_log(vault, "zanmai.py", f"snapshot {kurz} ({reason})")
    print(f"snapshot ok: {kurz} ({reason})")
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

# Derived from the bundle kinds, never hand-kept. Written out by hand, these three lists were a
# copy of a fact that lives above them, and the copy fell behind: `doing/` became a vault root and
# a bundle folder, and neither list heard about it, so the desk was not protected but unwatched.
# Anything writable there landed with no frontmatter check and no index check at all.
_HOOK_ENFORCED_KIND_PREFIXES = tuple(f"{f}/" for f in BUNDLE_FOLDERS) + (
    f"{PEOPLE_DIR}/",
    f"{ORGANISATIONS_DIR}/",
)
_HOOK_INDEX_PREFIXES = tuple(f"{f}/" for f in BUNDLE_FOLDERS)
_HOOK_EXEMPT_NAMES = ("INDEX.md", ".keep")
_HOOK_EXEMPT_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ics", ".webp")
# Paths the permission guard refuses outright, each with the sentence that says what to do instead.
# Path and advice sit together because they used to sit apart, the same five strings written once as a
# tuple and once as the keys of a lookup inside the hook; a renamed folder would have changed one and
# left the other silently matching nothing.
_HOOK_NEVER_TARGETS = {
    f"/{SYSTEM_MATERIAL_DIR}/": f"Distribution files live here; changes get overwritten on update. Use {EXTENSIONS_DIR}/ for user-side additions.",
    f"/{HISTORY_DIR}/": "Only `zanmai.py snapshot` writes here. Take a snapshot instead of writing into the history.",
    f"/{USER_FILE}": "Only `zanmai.py setup init` writes the owner file. To change personalisation, edit manually outside this tool or re-run the setup workflow.",
    f"/{ARCHIVE_DIR}/": "Nothing is written here directly. Use `zanmai.py file archive <path>` from where the file is now, so it keeps its path and can be restored.",
    f"/{TRASH_DIR}/": "Nothing is written here directly. Use `zanmai.py file trash <path>` from where the file is now, so it keeps its path and can be restored.",
}
_HOOK_ALLOWED_KINDS = set(KIND_FIELDS)




def _guard_refused(payload: dict, guard: str, grund: str) -> None:
    """Write down that a guard turned something away.

    Until 2026-08-26 no guard left a trace of any kind. The user's own words: "ich habe das Gefuehl,
    dass die Live-Umgebung nicht alles meldet, dass sie so beschaeftigt ist, dass es untergeht." That
    could not be answered, because nothing was written down: a refusal existed only in the session
    that saw it, and reporting it depended on a busy session remembering to. So it goes in the
    activity log, which is the one file written while the work happens, and from there it reaches the
    next briefing on its own.

    Never fails loudly. A guard that cannot write its note still has to make its decision.
    """
    try:
        start = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "."
        vault = _find_vault_root(Path(start))
        if vault is None:
            return
        _append_activity_log(vault, guard, f"refused: {' '.join(str(grund).split())[:300]}")
    except Exception:  # noqa: BLE001 -- a note that cannot be written never blocks the decision
        return


_LAST_PAYLOAD: dict = {}


def _hook_read_payload() -> dict:
    """Read the tool-call payload Claude Code passes on stdin. Returns empty
    dict on parse error so the hook never blocks because of a malformed pipe.

    The payload is kept because stdin can only be read once, and the refusal note written after the
    guard returns needs the working directory in it to find the vault."""
    global _LAST_PAYLOAD
    try:
        _LAST_PAYLOAD = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        _LAST_PAYLOAD = {}
    return _LAST_PAYLOAD


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


# A markdown task line, in every spelling a renderer accepts: any bullet marker, any amount of
# leading space, an empty or a ticked box.
_HOOK_CHECKBOX_RE = re.compile(r"^[ \t]*[-*+][ \t]+\[[ xX]\]", re.MULTILINE)


def _hook_checkbox_lines(text: str) -> list[str]:
    """Every task line in a piece of text, whitespace-normalised, in the order they appear.

    Normalised so that reindenting a list or turning `-` into `*` is not read as writing a task.
    What the comparison is meant to catch is a box appearing, disappearing or changing state.
    """
    return [" ".join(line.split()) for line in text.splitlines() if _HOOK_CHECKBOX_RE.match(line)]


def cmd_hook_checkbox_guard(args: argparse.Namespace) -> int:
    """PreToolUse Write|Edit hook: refuse a task line that turns up inside an ordinary write.

    A task on the user's list is the user's, and that is a statement about who wanted it, not about
    who typed it. Asked for one, the AI writes it, through `zanmai.py task add` and nowhere else.
    What it must never do is invent one: a reminder to itself, an obligation it derived from a
    source, a leftover from a test, all of which used to end up on the user's list and be read back
    to him as his own.

    This hook holds the second half of that. A box that appears while prose is being edited was
    never commissioned, whatever the intention was; going through the named command is a deliberate
    act, and it leaves a line in the activity log. That is the honest limit of the mechanic: it
    cannot read intent, so it makes the commissioned path narrow and visible and closes the wide one.

    Why a hook and not a sentence in a contract: this rule stood in the distribution's prose in six
    places, and prose is what you write again when the last writing did not hold. Writing a bad
    instruction more often does not make it better. It has to be in one place, said once, and
    enforced where the decision actually happens, which is the moment of the write.

    Mechanic: compare the task lines before and after. Anything that changes the set is refused,
    which covers writing a new one, deleting one, and ticking one. Everything else in the same
    write passes untouched, so editing the prose around a task list is normal work.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    tool = payload.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not file_path.endswith((".md", ".markdown")):
        return 0

    # Write carries the whole new body, so the file on disk is the before. Edit carries the pair
    # directly. A file that does not exist yet has no tasks in it, which makes every box in a fresh
    # write a new one.
    paare: list[tuple[str, str]] = []
    if tool == "Write":
        try:
            vorher = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            vorher = ""
        paare.append((vorher, tool_input.get("content") or ""))
    elif tool == "Edit":
        paare.append((tool_input.get("old_string") or "", tool_input.get("new_string") or ""))
    else:
        for edit in tool_input.get("edits") or []:
            paare.append((edit.get("old_string") or "", edit.get("new_string") or ""))

    for vorher, nachher in paare:
        alt, neu = _hook_checkbox_lines(vorher), _hook_checkbox_lines(nachher)
        if alt == neu:
            continue
        dazu = [z for z in neu if z not in alt]
        weg = [z for z in alt if z not in neu]
        rel = Path(file_path).name
        was = ("writing a task" if dazu and not weg
               else "removing a task" if weg and not dazu
               else "changing a task")
        beispiel = (dazu or weg)[0]
        print(f"checkbox-guard: refusing {tool} on {rel}, because it is {was}: {beispiel}",
              file=sys.stderr)
        print("  A task line never arrives as a side effect of editing a file.", file=sys.stderr)
        print("  Asked for one, write it with `zanmai.py task add --text ... [--file ...] "
              "[--due YYYY-MM-DD]`, and tick it off with `task done`.", file=sys.stderr)
        print("  Not asked for one: an obligation you worked out goes in the reply as a sentence, "
              "and something you still owe goes on a work object via `zanmai.py work`.",
              file=sys.stderr)
        return 2
    return 0


# A dash splitting a sentence is the single most recognisable machine-made construction, and the one
# the house style bans first (operating-principles section 7). Prose said it in five files across the
# distribution and it still reached a page the user's colleagues read: 21 of them in one produced
# document, written by a run that had the rule in context. A sentence that has not held is either
# built or dropped (principle 4), so it is built here.
#
# Em dash always. En dash only when it is doing the same job, which is why the spaces matter: a number
# range (`2020–2024`) is legitimate typography and stays.
#
# Written as codepoints on purpose. A guard that carries the character it bans fails the project's own
# style check on its own implementation, and the fix for that is never to widen the check: it is to
# keep the forbidden thing out of the guard.
_HOOK_EM_DASH = "\u2014"
# Whitespace or a boundary on both sides, not whitespace on both sides. A line that ends on the
# dash is the same construction and was the one that got through: the text of a slide is split
# across several strings, so "... schaffen –" ends one of them and the thought continues in the
# next. Requiring a following space made the check blind to exactly that. A number range keeps its
# dash because it carries no spaces at all ("2024–2026").
_HOOK_EN_DASH_SENTENCE = re.compile("(?:^|\\s)–(?:\\s|$)")
# A dash inside a matched pair of quote marks is someone else's wording, reproduced, not the AI's own
# sentence punctuation. The signal is the quote marks actually being there, not a guess at intent, so
# this only exempts a dash strictly between them, in the styles this project actually writes: straight
# double quotes and the German „low-high" and guillemet pairs.
# Just the quote marks, not a matched pair: used where a mark has to become a word boundary so a
# dash sitting against it is still seen. Separate from _HOOK_QUOTE_SPAN, which blanks whole spans.
_HOOK_QUOTE_MARKS = re.compile('["\'\u201e\u201c\u201d\u00ab\u00bb]')
_HOOK_QUOTE_SPAN = re.compile(
    '"[^"\\n]*"'
    '|\u201e[^\u201c\\n]*\u201c'
    '|\u00ab[^\u00bb\\n]*\u00bb'
    '|\u00bb[^\u00ab\\n]*\u00ab'
)


def _hook_strip_quotes(line: str) -> str:
    return _HOOK_QUOTE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


# Generic AI-marketing phrasing: the "buzzwords, filler" failure operating-principles section 7
# already names for chat prose, never checked on a written file until now. Curated to phrases that
# are near-universally a tell rather than legitimate technical vocabulary, so a real, specific claim
# is never caught in passing. English and German, since the guard binds on AI-authored content in
# either language.
_HOOK_REALISM_PHRASES = (
    "unlock the power of", "unlock your potential", "unleash the power of",
    "in today's fast-paced world", "in today's digital age", "in the ever-evolving landscape",
    "take it to the next level", "elevate your", "seamlessly integrate", "seamless integration",
    "cutting-edge", "state-of-the-art solution", "game-changer", "game changer",
    "revolutionize the way", "delve into", "navigate the complexities of",
    "harness the power of", "robust solution", "streamline your workflow", "empower you to",
    "holistic approach", "paradigm shift", "tapestry of", "at the forefront of",
    "boost your productivity",
    "in der heutigen schnelllebigen welt", "auf die nächste stufe heben",
    "das volle potenzial ausschöpfen", "bahnbrechend", "nahtlos integrieren",
    "ganzheitlicher ansatz", "zukunftsweisend",
)
# A placeholder left in place: a bracketed instruction to fill something in, or one of the stock
# names a template ships with. Presented as fact rather than filled in, "[Your Company]" and
# "Musterfirma" read as real the same way an invented number does; unlike a number, a script can
# actually tell these apart from real content, because the marker is the placeholder syntax itself.
_HOOK_PLACEHOLDER_MARK = re.compile(
    r"\[[^\]]*\b(company|name|insert|logo|brand|platzhalter|firmenname)\b[^\]]*\]"
    r"|\b(acme (corp|inc)|example company|musterfirma|musterunternehmen|lorem ipsum)\b"
    r"|\b(example\.com|yourcompany\.[a-z]{2,}|musterfirma\.de)\b",
    re.IGNORECASE,
)


def _hook_realism_hits(text: str) -> list[tuple[str, str]]:
    """Every line carrying a generic AI-marketing phrase or a placeholder left unfilled, as
    `(line, reason)`. A dash inside quote marks is exempt in `_hook_dash_hits` so a verbatim quote
    is not refused; the same reasoning applies here, reusing the same span blank-out, so a
    documented example of what not to write is not itself flagged.

    Deliberately does not attempt to catch an invented number: a script cannot tell a real figure
    from a fabricated one without knowing the domain, and a check that guesses at that would fail
    the project's own "measured, not eyeballed" standard. What is caught here is narrower and
    actually decidable: a phrase from a fixed, curated list, or a placeholder marker that is
    syntactically a placeholder, not a judgement call.
    """
    treffer: list[tuple[str, str]] = []
    for line in text.splitlines():
        checked = _hook_strip_quotes(line).lower()
        found = False
        for phrase in _HOOK_REALISM_PHRASES:
            if phrase in checked:
                treffer.append((" ".join(line.split()), f'generic phrase "{phrase}"'))
                found = True
                break
        if found:
            continue
        match = _HOOK_PLACEHOLDER_MARK.search(checked)
        if match:
            treffer.append((" ".join(line.split()), f'placeholder left in place ("{match.group(0)}")'))
    return treffer


def _hook_dash_hits(text: str) -> list[str]:
    """Every line of `text` carrying a dash used as sentence punctuation, whitespace-normalised.

    Normalised the same way as the checkbox lines, so that rewrapping a paragraph does not read as a
    new occurrence. The comparison is what keeps this off the user's own words: only a construction
    that was not in the file before is refused. A dash inside quote marks is checked with the quoted
    span blanked out first, so a verbatim quote does not need to be rewritten to pass.
    """
    treffer: list[str] = []
    for line in text.splitlines():
        checked = _hook_strip_quotes(line)
        if _HOOK_EM_DASH in checked or _HOOK_EN_DASH_SENTENCE.search(checked):
            treffer.append(" ".join(line.split()))
    return treffer


_HOOK_PROSE_SUFFIXES = (".md", ".markdown", ".json", ".txt", ".yaml", ".yml", ".html", ".htm")


def _hook_prose_text(text: str, suffix: str) -> str:
    """The prose inside a written file, as lines the dash and realism scans can read.

    A JSON content file carries its prose inside quoted string values, and the quote-span
    blank-out that keeps a verbatim quote in markdown from being refused would blank every one
    of them, so such a file would always read as clean. Found on a real run 2026-08-25: a
    dash-as-punctuation sentence reached a finished slide through exactly such a file, and the
    guard never saw it. The string values are pulled out and scanned as their own lines instead.
    """
    if suffix != ".json":
        return text
    try:
        daten = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text
    werte: list[str] = []

    def sammeln(knoten: object) -> None:
        if isinstance(knoten, str):
            werte.append(knoten)
        elif isinstance(knoten, dict):
            for wert in knoten.values():
                sammeln(wert)
        elif isinstance(knoten, list):
            for wert in knoten:
                sammeln(wert)

    sammeln(daten)
    return "\n".join(werte)


def _hook_prose_binds(file_path: str, text: str) -> bool:
    """Whether prose-guard binds on this write.

    A markdown file is bound by its `source:` frontmatter, which is what keeps the guard off an
    import of the user's own writing. A content file that cannot carry frontmatter at all (JSON,
    plain text, a template) has no such marker, and requiring one there meant the guard bound on
    nothing: every deliverable is built from files of exactly that kind. Those bind on being
    written, with `import/` exempt because that is where the user's own material arrives.
    """
    datei = Path(file_path)
    if datei.suffix.lower() in (".md", ".markdown"):
        return _hook_authored_by_ai(text, datei)
    if f"/{IMPORT_DIR}/" in f"/{file_path}":
        return False
    return True


def _hook_authored_by_ai(text: str, datei: Path) -> bool:
    """Whether this file's frontmatter says the AI wrote the content.

    `source:` is a required frontmatter field with three values (organic, collaborative,
    ai-generated). The guard binds on the two that mean the AI produced the prose. On `organic`, on a
    file that carries no frontmatter, and on anything unreadable it does not bind at all: principle 2
    outranks house style, and refusing an import of the user's own writing because they like dashes
    would cost the whole operation to save a line.
    """
    for quelle in (text, ""):
        if not quelle:
            try:
                quelle = datei.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return False
        fm, _, _ = _split_frontmatter(quelle)
        if isinstance(fm, dict) and fm.get("source"):
            return str(fm["source"]).strip().lower() in ("ai-generated", "collaborative")
    return False


def cmd_prose_check(args: argparse.Namespace) -> int:
    """Non-blocking precheck: the same dash-as-punctuation and content-realism scans the prose-guard
    hook runs, callable on a draft before Write so a finding shows up as normal output instead of a
    refused write.

    Always exits 0. A finding is something to fix, not a crash; only `prose-guard` itself, bound to
    the actual Write, has reason to block.
    """
    text = args.text if args.text is not None else sys.stdin.read()
    dash_treffer = _hook_dash_hits(text)
    realism_treffer = _hook_realism_hits(text)
    if not dash_treffer and not realism_treffer:
        print("clean: no dash used as sentence punctuation, no generic phrase or leftover placeholder")
        return 0
    if dash_treffer:
        print(f"found: {len(dash_treffer)} line(s) use a dash as sentence punctuation")
        for zeile in dash_treffer:
            print(f"  {zeile[:140]}")
        print("Finish the thought, or split it into two sentences. A hyphen inside a compound word and a "
              "number range keep their dash.")
    if realism_treffer:
        print(f"found: {len(realism_treffer)} line(s) read as generic AI phrasing or a leftover "
              f"placeholder")
        for zeile, grund in realism_treffer:
            print(f"  {zeile[:140]}  [{grund}]")
        print("Say the concrete thing instead, or fill in the real value.")
    return 0


# A single character in quotes is a character literal, not a sentence: `'-'` in a list of dashes to
# search for is the shape a cleanup script has, and refusing it stops exactly the work that fixes the
# problem. Found within the hour of shipping the quote-blanking below, on a script written to hunt
# dashes down. Removed before the marks are blanked, because blanking would turn the list into
# something that reads like prose with spaces around a dash.
_HOOK_CHAR_LITERAL = re.compile(r"""(['"])(.)\1""")
# The same thing one level up: a bracketed set that carries no letters is a character class, so
# `['-','-']` or a regex `[--]` is a list of things to find, never a sentence. Letters inside mean
# it is prose in brackets and stays.
_HOOK_CHAR_CLASS = re.compile(r"\[[^\[\]A-Za-z\u00c0-\u024f]*\]")


def _hook_command_prose(zeile: str) -> str:
    """A build command reduced to the prose inside it, ready for the dash scan.

    Quote marks become word boundaries so a dash sitting against one is still seen; what stands
    between them is kept, because in a build command that is the text being written. Character
    literals go first, as they are code and never a sentence.
    """
    ohne_code = _HOOK_CHAR_CLASS.sub(" ", _HOOK_CHAR_LITERAL.sub(" ", zeile))
    return _HOOK_QUOTE_MARKS.sub(" ", ohne_code)


def cmd_hook_prose_guard(args: argparse.Namespace) -> int:
    """PreToolUse Write|Edit|Bash: refuse a dash-as-punctuation, a generic AI-marketing phrase, or a
    leftover placeholder the AI is adding to its own prose.

    Mechanic: compare the dash and realism lines before and after, exactly as `checkbox-guard`
    compares task lines. Only a line that was not there before is refused, so moving, importing or
    re-indenting the user's material passes untouched.

    It binds at every point the prose can reach a deliverable, not only at the one the AI usually
    takes. Until 2026-08-25 it took a markdown file, written by Write or Edit, carrying frontmatter
    that said the AI wrote it, and all three had to hold. A finished slide with a dash-sentence on it
    proved how little that covers: the text came out of a JSON content file (not markdown, no
    frontmatter possible) and reached the deck through a Python build script (Bash, not Write). Each
    of the three conditions on its own was enough to make the guard silent, which is the same failure
    `library-check-guard` had before 0.3.5, a guard bound to a tool rather than to the moment the
    decision is made. So: every content file type, frontmatter required only where a file can carry
    it, and a Python build resolving into a `doing/<slug>/` bundle read as what it is, a write.

    The refusal names the line and what to do instead, because a refusal with no route named produces
    a report about the refusal rather than the work.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    tool = payload.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit", "Bash"):
        return 0
    tool_input = payload.get("tool_input") or {}

    if tool == "Bash":
        command = tool_input.get("command", "") or ""
        if not _PYTHON_RUN_RE.search(command):
            return 0
        if _library_guard_slug(command, cwd=payload.get("cwd")) is None:
            return 0
        # The quote marks themselves are blanked, never what stands between them: in a build
        # command the prose sits inside the string literals, so blanking the content would hide
        # exactly what this is looking for. Blanking only the marks makes them a word boundary,
        # which is what the dash pattern needs. Found 2026-08-26: `--text "Wir schaffen -"` was
        # silent because the dash was followed by a quote mark, so neither a space nor a line end
        # closed it, and that is the same end-of-string construction the 0.3.6 fix was built for.
        dazu = [z for z, gescannt in ((z, _hook_command_prose(z)) for z in command.splitlines())
                if _HOOK_EM_DASH in gescannt or _HOOK_EN_DASH_SENTENCE.search(gescannt)]
        if not dazu:
            return 0
        print(f"prose-guard: refusing this build, {len(dazu)} line(s) of the text it writes use a "
              f"dash as sentence punctuation. First: {' '.join(dazu[0].split())[:140]}",
              file=sys.stderr)
        print("  Finish the thought, or split it into two sentences. A hyphen inside a compound word "
              "and a number range keep their dash.", file=sys.stderr)
        return 2

    file_path = tool_input.get("file_path", "")
    suffix = Path(file_path).suffix.lower()
    if suffix not in _HOOK_PROSE_SUFFIXES:
        return 0

    paare: list[tuple[str, str]] = []
    if tool == "Write":
        neu_text = tool_input.get("content") or ""
        try:
            vorher = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            vorher = ""
        if not _hook_prose_binds(file_path, neu_text):
            return 0
        paare.append((_hook_prose_text(vorher, suffix), _hook_prose_text(neu_text, suffix)))
    elif tool == "Edit":
        if not _hook_prose_binds(file_path, ""):
            return 0
        paare.append((tool_input.get("old_string") or "", tool_input.get("new_string") or ""))
    else:
        if not _hook_prose_binds(file_path, ""):
            return 0
        for edit in tool_input.get("edits") or []:
            paare.append((edit.get("old_string") or "", edit.get("new_string") or ""))

    for vorher, nachher in paare:
        alt, neu = _hook_dash_hits(vorher), _hook_dash_hits(nachher)
        dazu = [z for z in neu if z not in alt]
        alt_real, neu_real = _hook_realism_hits(vorher), _hook_realism_hits(nachher)
        dazu_real = [t for t in neu_real if t not in alt_real]
        if not dazu and not dazu_real:
            continue
        rel = Path(file_path).name
        if dazu:
            print(f"prose-guard: refusing {tool} on {rel}, {len(dazu)} line(s) use a dash as sentence "
                  f"punctuation. First: {dazu[0][:140]}", file=sys.stderr)
            print("  Finish the thought, or split it into two sentences. A hyphen inside a compound word "
                  "and a number range keep their dash.", file=sys.stderr)
        if dazu_real:
            zeile, grund = dazu_real[0]
            print(f"prose-guard: refusing {tool} on {rel}, {len(dazu_real)} line(s) read as generic AI "
                  f"phrasing or a leftover placeholder. First: {zeile[:140]} [{grund}]", file=sys.stderr)
            print("  Say the concrete thing instead, or fill in the real value.", file=sys.stderr)
        print("  Rewrite those lines and write the file again; the rest of the content is fine.",
              file=sys.stderr)
        return 2
    return 0


def cmd_hook_kind_required(args: argparse.Namespace) -> int:
    """PreToolUse Write|Edit hook: refuse writes into a bundle root whose
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
        print(f"kind-required: refusing {payload.get('tool_name')} on {rel}, a file in a bundle requires YAML frontmatter starting with ---", file=sys.stderr)
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
    """PreToolUse Write|Edit hook: hard-block writes into the never-do bucket.

    What is in the bucket and the sentence saying what to do instead both live in
    `_HOOK_NEVER_TARGETS`, so this docstring does not name them a second time and cannot fall
    behind them."""
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") not in ("Write", "Edit"):
        return 0
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0
    norm = file_path.replace("\\", "/")
    for target, advice in _HOOK_NEVER_TARGETS.items():
        if target in norm:
            print(f"permission-guard: refusing {payload.get('tool_name')} on '{file_path}'. This path is in the never-do bucket. {advice}", file=sys.stderr)
            return 2

    # Emptying a file is deleting it with the name left behind, and the delete-guard cannot see it
    # because no shell runs. A file that holds something keeps holding something.
    if payload.get("tool_name") == "Write":
        inhalt = (payload.get("tool_input", {}) or {}).get("content", "")
        vorhanden = Path(file_path)
        if not inhalt.strip() and vorhanden.is_file() and vorhanden.stat().st_size > 0:
            print(f"permission-guard: refusing to write an empty file over '{file_path}', which holds "
                  f"something. Emptying a file is deleting it with the name left behind, and nothing "
                  f"in Zanmai deletes. To discard it: `zanmai.py file trash --path {file_path}`, "
                  f"which keeps it and its path so `file restore` can bring it back.", file=sys.stderr)
            return 2
    return 0


# Shell verbs that take something away. The guard stays blunt about the target: it never works out
# which path a verb would hit, because a command line can hide that behind a variable, a glob, a pipe
# or a subshell, and a guard that has to parse shell to decide is a guard that can be talked around.
# What it does decide is whether the word is being run as a command at all. `trash` is also a folder
# in every vault and a sub-command of this very script, so matching it anywhere in the line refused
# `ls zanmai/trash`, a find that excludes the trash, and `zanmai.py file trash` itself, which is the
# way out the refusal message recommends.
_DELETE_COMMANDS = frozenset({"rm", "rmdir", "unlink", "shred", "trash", "truncate", "mkfs"})

# Words that stand in front of the real command without being one: wrappers, and the shell keywords
# a loop or a branch puts there (`do rm $f` inside a for-loop is still an rm).
_COMMAND_PREFIXES = frozenset({
    "sudo", "command", "builtin", "exec", "env", "time", "nohup", "doas",
    "do", "then", "else", "elif", "!",
})

# A subshell starts a fresh command, so its opener counts as a separator like `;` or `|`.
_SEGMENT_SPLIT_RE = re.compile(r"[;&|\n]+")
_SUBSHELL_OPEN_RE = re.compile(r"\$\(|[`(){}]")

# Where a command name can also appear: whatever these hand a command to.
_HANDS_OVER = frozenset({"xargs", "-exec", "-execdir", "-ok", "-okdir"})


def _delete_verb_in(command: str) -> str | None:
    """Return the removing command in `command`, or None. Fails closed: a line this cannot take
    apart is checked with the old blunt word search, so an unparsable command is refused, never
    waved through."""
    # Separators are padded so they survive as tokens of their own; shlex would otherwise leave `;`
    # glued to the word before it and `ls; trash x` would read as one command called `ls;`.
    gepolstert = _SEGMENT_SPLIT_RE.sub(r" \g<0> ", _SUBSHELL_OPEN_RE.sub(" ; ", command))
    try:
        segments = shlex.split(gepolstert)
    except ValueError:
        wort = re.search(r"\b(" + "|".join(sorted(_DELETE_COMMANDS)) + r")\b", command)
        return wort.group(1) if wort else None

    # shlex drops the separators, so split again on the tokens that are pure separators.
    zeilen: list[list[str]] = [[]]
    for token in segments:
        if _SEGMENT_SPLIT_RE.fullmatch(token):
            zeilen.append([])
        else:
            zeilen[-1].append(token)

    for tokens in zeilen:
        if not tokens:
            continue
        # The command word: skip prefixes and leading VAR=value assignments.
        i = 0
        while i < len(tokens) and (tokens[i] in _COMMAND_PREFIXES or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[i])):
            i += 1
        if i < len(tokens):
            kopf = Path(tokens[i]).name
            if kopf in _DELETE_COMMANDS:
                return kopf
            if kopf == "git" and i + 1 < len(tokens) and tokens[i + 1] in ("rm", "clean"):
                return f"git {tokens[i + 1]}"
            if kopf == "dd" and any(t.startswith("of=") for t in tokens[i + 1:]):
                return "dd of="
            if kopf == "find" and "-delete" in tokens[i + 1:]:
                return "find -delete"
        # Anything that hands a command on: everything behind it is a candidate, because the
        # options in between differ per tool and guessing them wrong would let a verb through.
        if any(t in _HANDS_OVER for t in tokens):
            start = min(tokens.index(t) for t in tokens if t in _HANDS_OVER)
            for token in tokens[start + 1:]:
                if Path(token).name in _DELETE_COMMANDS:
                    return Path(token).name
    return None

# Paths the guard does not police, because they are not the user's material and something has to be
# able to tidy them: the machine's own scratch space and the runtime it provisions for this computer.
_DELETE_ALLOWED_HINTS = (f"{SCRATCH_DIR}/", f"{RUNTIME_DIR}/")


# ---- video: the mechanic under the video skills -----------------------------
#
# Every state change a cut makes lives here, the judgement lives in the skills. The split matters
# because a cut is arithmetic on measured numbers: where a word ends, what frame rate the source
# actually has, how long a piece really is. A model that estimates any of those produces a cut that
# drifts, and drift is invisible until the whole thing is assembled.

VIDEO_TAIL = 0.5             # s of margin past a nominal end, so a late boundary finds something
VIDEO_MIN_GAP = 1.0          # s of silence before it counts as a pause worth removing
# Deliberately not the four tenths that fast-cut talking heads use. Measured on a real recording:
# at 0.4 the mechanical pass produced 53 cuts in 132 seconds, one every two and a half seconds,
# which reads as chopped rather than tightened. Breath is rhythm; what is worth removing is the
# gap where somebody is visibly thinking, and that is around a second.


def _video_job_dir(vault: Path, slug: str) -> Path:
    """Working area for one job. Under temp: intermediates are volatile by design and the
    retention sweep clears them, while what the user keeps goes to their own bundle."""
    d = vault / SCRATCH_DIR / "video" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ffprobe_json(ffprobe: str, path: Path, *args: str) -> dict:
    r = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", *args, str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}


def _video_probe(vault: Path, path: Path) -> dict:
    """What the file actually is, read from the file. Never assumed, never rounded: a frame rate
    guessed as 24 where the source is 24000/1001 drifts a frame every forty seconds."""
    ffprobe = _tool_path(vault, "ffprobe") or _tool_path(vault, "ffmpeg")
    if not ffprobe:
        return {}
    d = _ffprobe_json(ffprobe, path, "-show_streams", "-show_format", "-show_chapters")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    rate = v.get("r_frame_rate") or "0/1"
    try:
        num, den = (int(x) for x in rate.split("/"))
        fps = num / den if den else 0.0
    except ValueError:
        fps = 0.0
    return {
        "path": str(path),
        "duration": float(d.get("format", {}).get("duration") or 0.0),
        "width": v.get("width"), "height": v.get("height"),
        "fps": round(fps, 5), "fps_exact": rate,
        "audio": bool(a), "audio_rate": a.get("sample_rate"),
        # A screen recording can carry chapters that inflate the reported length and leave a black
        # tail. Reported here so the caller strips them instead of trimming to a wrong duration.
        "chapters": len(d.get("chapters") or []),
    }


def cmd_video_probe(args: argparse.Namespace) -> int:
    """What a file is, measured. Every later step reads these numbers."""
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    info = _video_probe(vault, src)
    if not info:
        print("fail: cannot read this file, and nothing will be guessed instead. "
              "Missing ffprobe: `tools ensure ffprobe`.", file=sys.stderr)
        return 1
    print(json.dumps(info, indent=2))
    return 0


def _words_from_dtw(data: dict) -> list[dict]:
    """Words with a start and an end, out of the recogniser's token timings.

    The recogniser reports the END of each token. A word therefore ends at its last token and
    starts where the previous one ended, which is right inside continuous speech and wrong after a
    pause, where the gap belongs to the silence and not to the word. `video cut` corrects those
    against the audio; here the raw reading is kept, so the two stay separable.
    """
    worte: list[dict] = []
    letzte = 0.0
    for seg in data.get("transcription", []):
        for tok in seg.get("tokens", []):
            text = tok.get("text", "")
            if text.startswith("[_"):
                continue
            ende = tok.get("t_dtw", -1)
            sicher = tok.get("p")
            if text.startswith(" ") and text.strip():
                worte.append({"word": text.strip(), "start": round(letzte, 3), "end": None,
                              "p": round(sicher, 3) if isinstance(sicher, (int, float)) else None})
            elif worte and text.strip():
                worte[-1]["word"] += text.strip()
                # A word is only as certain as its least certain piece: a name usually breaks into
                # several tokens and one of them is the one that went wrong.
                if isinstance(sicher, (int, float)) and worte[-1].get("p") is not None:
                    worte[-1]["p"] = round(min(worte[-1]["p"], sicher), 3)
            if ende >= 0:
                letzte = ende / 100.0
                if worte:
                    worte[-1]["end"] = round(letzte, 3)
    return [w for w in worte if w["end"] is not None and w["end"] > w["start"]]


def _rms_envelope(wav: Path, hop: float = 0.01) -> tuple[list[float], float]:
    """Loudness per 10 ms window, straight from the samples. Used to find where speech actually
    starts after a pause, which is the one thing the recogniser cannot know."""
    import wave as _wave
    with _wave.open(str(wav), "rb") as w:
        rate, roh = w.getframerate(), w.readframes(w.getnframes())
    import array
    werte = array.array("h")
    werte.frombytes(roh[: len(roh) // 2 * 2])
    schritt = max(1, int(rate * hop))
    huelle = [sum(abs(v) for v in werte[i:i + schritt]) / schritt
              for i in range(0, max(0, len(werte) - schritt), schritt)]
    return huelle, hop


def cmd_video_transcribe(args: argparse.Namespace) -> int:
    """One source to words with timings, locally. Runs once per source and is then read from disk.

    This is the slowest step in the whole pipeline, so re-running finds the saved result and stops.
    The recogniser needs two flags that are easy to miss and silent when wrong: the alignment has to
    be switched on explicitly, and fast attention has to be off, or the alignment is skipped without
    a word and every timing comes back as the decoder's guess.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    job = _video_job_dir(vault, args.slug)
    ziel = job / f"{src.stem}.words.json"
    if ziel.is_file() and not args.force:
        d = json.loads(ziel.read_text(encoding="utf-8"))
        print(f"ok: already transcribed, {len(d.get('words', []))} word(s) at "
              f"{ziel.relative_to(vault)} (--force to redo)")
        return 0

    ffmpeg = _tool_path(vault, "ffmpeg")
    whisper = _tool_path(vault, "whisper")
    model = _whisper_model(vault)
    fehlt = []
    if not ffmpeg:
        fehlt.append("ffmpeg, which turns the recording into what the recogniser reads")
    if not whisper:
        fehlt.append("whisper-cli, the recogniser itself")
    if not model:
        fehlt.append("a model in zanmai/runtime/whisper/ (about 1.6 GB, fetched once)")
    if fehlt:
        print("fail: cannot transcribe, and nothing will be guessed instead. Missing:",
              file=sys.stderr)
        for x in fehlt:
            print(f"  {x}", file=sys.stderr)
        return 1

    wav = job / f"{src.stem}.16k.wav"
    subprocess.run([ffmpeg, "-y", "-i", str(src), "-vn", "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)], check=True, capture_output=True)

    # `--dtw` takes a preset name that must match the model, and the presets spell it with dots.
    preset = args.dtw_preset or _whisper_dtw_preset(model)
    roh = job / f"{src.stem}.raw"
    cmd = [whisper, "-m", str(model), "-f", str(wav), "-l", args.language,
           "-nfa", "--output-json-full", "--output-file", str(roh), "--no-prints"]
    if preset:
        cmd += ["--dtw", preset]
    if args.lexicon and Path(args.lexicon).is_file():
        cmd += ["--prompt", Path(args.lexicon).read_text(encoding="utf-8").strip(),
                "--carry-initial-prompt"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # The recogniser appends its own suffix to the whole name, so this is not with_suffix().
    ergebnis = Path(str(roh) + ".json")
    if r.returncode != 0 or not ergebnis.is_file():
        print(f"fail: the recogniser wrote no result. {(r.stderr or '')[-400:]}", file=sys.stderr)
        return 1

    data = json.loads(ergebnis.read_text(encoding="utf-8"))
    worte = _words_from_dtw(data)
    # Measured boundaries, written once, here. Everything downstream reads this file, so there is
    # exactly one set of times in the job: a second refinement further along would silently
    # compare against numbers nobody else has.
    if worte and wav.is_file():
        worte = _refine_word_bounds(worte, wav)
    if not worte:
        print("fail: no word timings came back. The alignment was skipped, which happens silently "
              "when fast attention is on or the preset does not match the model.", file=sys.stderr)
        return 1
    text = " ".join(w["word"] for w in worte)
    ziel.write_text(json.dumps({
        "source": str(src), "language": args.language, "aligned": bool(preset),
        "measured": bool(wav.is_file()),
        "words": worte, "text": text,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (job / f"{src.stem}.txt").write_text(text + "\n", encoding="utf-8")
    print(f"ok: {len(worte)} word(s), timings {'aligned' if preset else 'from the decoder only'}, "
          f"at {ziel.relative_to(vault)}")
    return 0


def _whisper_dtw_preset(model: Path) -> str | None:
    """The alignment preset that goes with this model file. The names use dots, and a mismatch is
    rejected loudly, which is the good case; the bad case is fast attention silently disabling it."""
    name = model.name.lower()
    for kandidat, preset in (
        ("large-v3-turbo", "large.v3.turbo"), ("large-v3", "large.v3"),
        ("large-v2", "large.v2"), ("large-v1", "large.v1"),
        ("medium.en", "medium.en"), ("medium", "medium"),
        ("small.en", "small.en"), ("small", "small"),
        ("base.en", "base.en"), ("base", "base"),
        ("tiny.en", "tiny.en"), ("tiny", "tiny"),
    ):
        if kandidat in name:
            return preset
    return None


def cmd_video_cutsheet(args: argparse.Namespace) -> int:
    """Check a cut sheet before anything renders, and report what it would produce.

    Five of these are ordinary field checks. The sixth is the one nobody guesses: two neighbouring
    passages either butt up exactly or stay a real distance apart, because a gap of a few
    hundredths shows a flash of untreated picture at the seam.
    """
    vault = Path(args.vault).resolve()
    blatt = Path(args.file).expanduser()
    if not blatt.is_file():
        print(f"fail: no such cut sheet: {blatt}", file=sys.stderr)
        return 1
    try:
        eintraege = json.loads(blatt.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"fail: not readable as JSON: {e}", file=sys.stderr)
        return 1
    if isinstance(eintraege, dict):
        eintraege = eintraege.get("segments", [])
    fehler: list[str] = []
    gesamt = 0.0
    vorher: dict | None = None
    for i, s in enumerate(eintraege):
        wo = f"segment {i}"
        for feld in ("source", "start", "end"):
            if feld not in s:
                fehler.append(f"{wo}: missing '{feld}'")
        if fehler and wo in fehler[-1]:
            continue
        if not (float(s["end"]) > float(s["start"])):
            fehler.append(f"{wo}: end is not after start")
            continue
        gesamt += float(s["end"]) - float(s["start"])
        if vorher and s["source"] == vorher["source"]:
            # A gap here is the material being dropped, so a gap is the normal case and not a
            # fault. What is a fault is a passage that starts before the previous one ended: the
            # same moment would then appear twice, and the assembled sound stutters at the join.
            if float(s["start"]) < float(vorher["end"]):
                fehler.append(f"{wo}: starts before the previous one ends, so the same moment "
                              f"would be used twice")
            elif float(s["start"]) < float(vorher["start"]):
                fehler.append(f"{wo}: runs backwards against the one before it")
        vorher = s
    if fehler:
        print(f"FAIL: {len(fehler)} problem(s) in {blatt.name}", file=sys.stderr)
        for f in fehler:
            print(f"  {f}", file=sys.stderr)
        return 1
    # A cut is only honest if it keeps whole words. Checking that here, against the transcript,
    # is the difference between "it rendered" and "it says what it said": a passage that starts a
    # fraction late swallows the first syllable, and nothing downstream would ever notice.
    if args.words:
        wd = Path(args.words).expanduser()
        if wd.is_file():
            worte = json.loads(wd.read_text(encoding="utf-8")).get("words", [])
            angeschnitten = [w for w in worte
                             if any(float(s["start"]) < w["end"] and w["start"] < float(s["end"])
                                    for s in eintraege)
                             and not any(float(s["start"]) <= w["start"] and w["end"] <= float(s["end"])
                                         for s in eintraege)]
            if angeschnitten:
                print(f"WARN: {len(angeschnitten)} word(s) are cut through rather than kept or "
                      f"dropped whole; they will sound clipped", file=sys.stderr)
                for w in angeschnitten[:5]:
                    print(f"  {w['start']:8.2f}  {w['word']}", file=sys.stderr)
            else:
                print(f"ok: all {len(worte)} words are kept or dropped whole")

    print(f"ok: {len(eintraege)} segment(s), {_spoken_length(gesamt)} of output")
    if args.text:
        for s in eintraege:
            if s.get("text"):
                print(f"  {float(s['start']):8.2f}  {s['text']}")
    return 0


def _refine_word_bounds(worte: list[dict], wav: Path) -> list[dict]:
    """Move each word's start and end to where speech actually starts and stops, in the audio.

    Both directions are needed and for the same reason: the aligner reports the moment a word is
    recognised, not the moment it is over. Trusting its start swallows the beginning of the word
    after a pause; trusting its end cuts the last word before a pause off while it is still
    sounding, which is audible as a swallowed syllable and was exactly the fault this fixes.

    Only boundaries with real quiet beside them are moved: elsewhere there is nothing observable to
    measure against, and inventing one would be worse than the aligner's own reading. The threshold
    comes from the recording itself, because a quiet room and a noisy one differ by more than any
    constant would survive.
    """
    huelle, hop = _rms_envelope(wav)
    if not huelle:
        return worte
    ruhig = sorted(huelle)[max(1, len(huelle) // 10)]
    schwelle = max(ruhig * 4.0, 40.0)
    halten = max(1, int(0.03 / hop))
    raus: list[dict] = []
    for i, w in enumerate(worte):
        start = w["start"]
        vorher = worte[i - 1]["end"] if i else 0.0
        a, b = int(vorher / hop), int(w["end"] / hop)
        if b - a > halten:
            fenster = huelle[a:b]
            # Read backwards from the word's own end: the last stretch of quiet before it is the
            # pause, and speech starts where that quiet ends.
            j = len(fenster) - 1
            while j > 0 and fenster[j] > schwelle:
                j -= 1
            if j > 0:
                gemessen = (a + j + 1) * hop
                if gemessen > start:
                    start = round(gemessen, 3)
        # The same measurement forwards: let the word run until the sound actually drops, at most
        # up to where the next one starts.
        ende = w["end"]
        grenze = worte[i + 1]["start"] if i + 1 < len(worte) else ende + 1.0
        k = int(ende / hop)
        letzte = min(len(huelle) - 1, int(grenze / hop))
        while k < letzte and huelle[k] > schwelle:
            k += 1
        if k * hop > ende:
            ende = round(min(k * hop, grenze), 3)
        raus.append({**w, "start": min(start, max(0.0, ende - 0.02)), "end": ende})
    return raus


def cmd_video_propose(args: argparse.Namespace) -> int:
    """A first cut sheet out of the measured word timings: speech kept, long silence dropped.

    This is measurement, not judgement. It removes what is provably nothing (a gap longer than the
    threshold) and leaves every decision about content to the skill that reads it afterwards. The
    spoken line travels with each segment so the whole cut can be checked by reading.
    """
    vault = Path(args.vault).resolve()
    worte_datei = Path(args.words).expanduser()
    if not worte_datei.is_file():
        print(f"fail: no such transcript: {worte_datei}", file=sys.stderr)
        return 1
    daten = json.loads(worte_datei.read_text(encoding="utf-8"))
    worte = daten.get("words", [])
    quelle = args.source or daten.get("source")
    if not worte or not quelle:
        print("fail: the transcript carries no words, or no source to cut from", file=sys.stderr)
        return 1

    if not daten.get("measured"):
        print("fail: this transcript carries the recogniser's own timings, which report when a word "
              "was recognised rather than when it was spoken. Every gap in it is zero, so nothing "
              "would ever be removed. Run `video transcribe` again with this version.",
              file=sys.stderr)
        return 1

    # Padding is not one number. It depends on where the cut falls, and these values come from
    #a pipeline that was tuned against real edits rather than guessed:
    #   inside a sentence (the passage ends on a comma)  100 ms after, 80 ms before
    #   at a sentence boundary (full stop, question)     200 ms after, 140 ms before
    #   at the very end of the piece                     650 ms, so the last word rings out
    # A single value produces either a clipped word or a video that seems to keep running.
    rand = args.padding
    tail = args.tail if args.tail is not None else max(args.padding, VIDEO_TAIL / 2)
    segmente: list[dict] = []
    offen: dict | None = None
    def _rand_fuer(letztes_wort: str, am_ende: bool) -> tuple[float, float]:
        """How much to leave before and after, by where the cut falls."""
        if am_ende:
            return args.padding, args.end_tail
        if letztes_wort.rstrip().endswith((".", "?", "!")):
            return args.boundary_lead, args.boundary_tail
        return args.padding, tail

    for w in worte:
        if offen is None:
            offen = {"source": quelle, "start": max(0.0, w["start"] - rand), "end": w["end"],
                     "text": w["word"]}
            continue
        if w["start"] - offen["end"] > args.gap:
            vorne, hinten = _rand_fuer(offen["text"].split()[-1], False)
            offen["end"] = round(offen["end"] + hinten, 3)
            segmente.append(offen)
            offen = {"source": quelle, "start": max(0.0, w["start"] - vorne), "end": w["end"],
                     "text": w["word"]}
        else:
            offen["end"] = w["end"]
            offen["text"] += " " + w["word"]
    if offen:
        # The last passage of the piece gets the most room. A recogniser reading a whole file marks
        # the final word up to a second late, counting the breath after it as part of the word, so
        # trusting that number leaves the recording visibly running after the speaker has finished.
        offen["end"] = round(offen["end"] + args.end_tail, 3)
        segmente.append(offen)

    # Merge what is barely separated. Two passages a fifth of a second apart are not two shots,
    # they are one with a hole in it, and cutting there costs a visible jump to save nothing.
    verdichtet: list[dict] = []
    for s in segmente:
        if verdichtet and s["start"] - verdichtet[-1]["end"] < args.merge:
            verdichtet[-1]["end"] = s["end"]
            verdichtet[-1]["text"] += " " + s["text"]
        else:
            verdichtet.append(s)
    segmente = verdichtet
    for s in segmente:
        s["start"] = round(s["start"], 3)
        s["end"] = round(s["end"], 3)
    behalten = sum(s["end"] - s["start"] for s in segmente)
    roh = float(worte[-1]["end"])
    ziel = Path(args.out).expanduser()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({"segments": segmente}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    je_minute = len(segmente) / max(1.0, behalten / 60.0)
    print(f"ok: {len(segmente)} segment(s), {_spoken_length(behalten)} kept out of "
          f"{_spoken_length(roh)}, {100 * (1 - behalten / roh):.0f}% removed as silence, "
          f"at {ziel}")
    print("   This is the mechanical pass. What comes out for being wrong, weak or off-topic is "
          "decided by reading it.")
    if je_minute > 12:
        print(f"   {je_minute:.0f} cuts per minute. That reads as chopped unless every jump is "
              f"covered; either raise --gap or plan on hiding the seams.")
    return 0


def _audio_out(ziel: Path, endgueltig: bool = False) -> list[str]:
    """How to write the sound of an intermediate file.

    Every pass that re-encodes lossy audio costs quality, and a cut goes through four of them
    before anyone hears it: cut, brand, mix, export. Measured on a real recording, the result was
    audibly duller than the source. So intermediates carry the sound uncompressed where the
    container allows it, and the one compressed encode happens at the end.
    """
    if endgueltig:
        return ["-c:a", "aac", "-b:a", "192k"]
    if ziel.suffix.lower() in (".mov", ".mkv", ".nut"):
        return ["-c:a", "pcm_s16le"]
    # MP4 cannot carry uncompressed sound in any way players agree on, so this is the fallback:
    # a bitrate high enough that four passes do not add up to something you can hear.
    return ["-c:a", "aac", "-b:a", "320k"]


def cmd_video_cut(args: argparse.Namespace) -> int:
    """Assemble the kept passages into one file.

    Three things here are decided by how the format works, not by preference. Each piece is
    re-encoded rather than stream-copied, because a copy can only cut on its own key frames and
    slides the sound against the picture everywhere else. The sound rides through untouched and is
    levelled once at the end, because encoding each piece separately puts a click at every join.
    And the frame rate comes from the source as an exact fraction.
    """
    vault = Path(args.vault).resolve()
    blatt = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg:
        print("fail: ffmpeg missing: `tools ensure ffmpeg`.", file=sys.stderr)
        return 1
    if not blatt.is_file():
        print(f"fail: no such cut sheet: {blatt}", file=sys.stderr)
        return 1
    daten = json.loads(blatt.read_text(encoding="utf-8"))
    segmente = daten.get("segments", daten) if isinstance(daten, dict) else daten
    if not segmente:
        print("fail: the cut sheet keeps nothing", file=sys.stderr)
        return 1

    quellen: list[str] = []
    for s in segmente:
        if s["source"] not in quellen:
            quellen.append(s["source"])
    probe = _video_probe(vault, Path(quellen[0]).expanduser())
    fps = args.fps or probe.get("fps_exact") or "25/1"
    # Where several sources meet, the target size is a decision and not a side effect of which file
    # happened to be listed first. Stated here, said out loud below, so nobody discovers afterwards
    # that a 4K source was flattened to 720p because the first passage came from a webcam.
    if args.size:
        try:
            zb, zh = (int(x) for x in args.size.lower().split("x"))
        except ValueError:
            print(f"fail: expected --size WIDTHxHEIGHT, got {args.size!r}", file=sys.stderr)
            return 1
    else:
        zb, zh = int(probe.get("width") or 1920), int(probe.get("height") or 1080)
    groessen = {(int(g.get("width") or 0), int(g.get("height") or 0))
                for g in (_video_probe(vault, Path(q).expanduser()) for q in quellen)}
    if len(groessen) > 1 and not args.size:
        print(f"note: sources differ in size ({', '.join(f'{w}x{h}' for w, h in sorted(groessen))}); "
              f"everything is brought to {zb}x{zh}, taken from the first source. Pass --size to "
              f"decide it instead.")

    # Hiding the seam. A removed pause leaves the picture standing in exactly the same place, and
    # the eye reads that as a jump rather than as continuity. Alternating the framing slightly from
    # passage to passage covers it: the change is small enough not to be noticed as an effect and
    # large enough that the jump stops registering. Never on every cut in a row with the same
    # amount, which is why it alternates rather than accumulates, and off by default because a
    # piece with two cuts does not need it.
    stufen = [1.0, 1.0 + args.cover / 100.0] if args.cover else [1.0]
    breite_q, hoehe_q = zb, zh
    teile, filter_ = [], []
    for i, s in enumerate(segmente):
        idx = quellen.index(s["source"])
        a, b = float(s["start"]), float(s["end"])
        z = stufen[i % len(stufen)]
        rahmen = ""
        if z != 1.0:
            zb, zh = int(breite_q * z / 2) * 2, int(hoehe_q * z / 2) * 2
            rahmen = (f",scale={zb}:{zh},crop={breite_q}:{hoehe_q}:"
                      f"{(zb - breite_q) // 2}:{(zh - hoehe_q) // 2}")
        # Every piece is brought to the same size, frame rate, pixel shape and sound format as the
        # first source. Joining them otherwise fails outright, and material from two cameras almost
        # never matches: 4K at 25 frames beside 720p at 60 is the normal case, not the exception.
        angleich = (f"scale={breite_q}:{hoehe_q}:force_original_aspect_ratio=decrease,"
                    f"pad={breite_q}:{hoehe_q}:(ow-iw)/2:(oh-ih)/2,setsar=1")
        filter_.append(
            f"[{idx}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,{angleich},fps={fps}{rahmen}[v{i}];"
            f"[{idx}:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
        teile.append(f"[v{i}][a{i}]")
    graph = ";".join(filter_) + ";" + "".join(teile) + f"concat=n={len(segmente)}:v=1:a=1[vv][ao]"
    # No levelling here. The sound is levelled exactly once, in `mix`, at the end. Doing it in the
    # cut as well means normalising twice against different material, and every pass that touches
    # the sound also re-encodes it.

    cmd = [ffmpeg, "-y"]
    for q in quellen:
        cmd += ["-i", str(Path(q).expanduser())]
    cmd += ["-filter_complex", graph, "-map", "[vv]", "-map", "[ao]",
            "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
            "-pix_fmt", "yuv420p", *_audio_out(ziel),
            "-movflags", "+faststart", str(ziel), "-loglevel", "error"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"fail: the cut did not render.\n{(r.stderr or '')[-800:]}", file=sys.stderr)
        return 1
    raus = _video_probe(vault, ziel)
    print(f"ok: {len(segmente)} segment(s) into {ziel}, "
          f"{_spoken_length(raus.get('duration', 0.0))}, {raus.get('fps')} fps, "
          f"{ziel.stat().st_size / 1e6:.1f} MB")
    return 0


def _srt_time(sekunden: float) -> str:
    ms = int(round(sekunden * 1000))
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


_SATZ_ENDE = (".", "?", "!", ":", ";")
_SATZ_PAUSE = (",", "–", "-")


# The two caption classes want different grouping, and using one set of numbers for both is what
# produced either seven-word run-ons or a card holding a fragment. Word-by-word captions are short
# by design, so every comma is a break; a set subtitle track follows the broadcast convention of
# roughly forty characters over one or two lines, where breaking at every comma leaves fragments.
# The word-by-word numbers come from a pipeline that has been running in production.
CAPTION_STYLES = {
    "karaoke":  {"max_words": 4, "max_chars": 34, "min_duration": 0.6, "comma_always": True},
    "subtitle": {"max_words": 7, "max_chars": 42, "min_duration": 1.0, "comma_always": False},
}


def _caption_lines(worte: list[dict], max_woerter: int, max_zeichen: int,
                   min_dauer: float = 1.0, komma_immer: bool = False) -> list[dict]:
    """Group words into readable lines, at meaning rather than at a character count.

    Three things decide a break, in order. A sentence ending always breaks. A comma breaks when the
    line is already more than half full, because a clause boundary reads far better than a break
    mid-phrase. The limits break what is left. Without the comma rule the result is either seven
    words of run-on or, at the other end, a card holding a fragment.

    Then a floor on duration: a line that would stand for a quarter of a second is a flash nobody
    reads, so it is merged into its neighbour. That happens whenever a sentence ends on a short
    word, which is often.
    """
    zeilen: list[dict] = []
    aktuell: list[dict] = []
    for w in worte:
        probe = " ".join(x["word"] for x in aktuell + [w])
        voll = len(aktuell) >= max_woerter or len(probe) > max_zeichen
        letzter = aktuell[-1]["word"] if aktuell else ""
        halb = len(" ".join(x["word"] for x in aktuell)) > max_zeichen * 0.5
        brechen = bool(aktuell) and (
            voll
            or letzter.endswith(_SATZ_ENDE)
            or (letzter.endswith(_SATZ_PAUSE) and (komma_immer or halb)))
        if brechen:
            zeilen.append({"start": aktuell[0]["start"], "end": aktuell[-1]["end"],
                           "text": " ".join(x["word"] for x in aktuell)})
            aktuell = []
        aktuell.append(w)
    if aktuell:
        zeilen.append({"start": aktuell[0]["start"], "end": aktuell[-1]["end"],
                       "text": " ".join(x["word"] for x in aktuell)})

    # A line that stands too briefly is held longer rather than merged into its neighbour. Merging
    # would fix the flash and break the limits above, which is how a four-word rule quietly becomes
    # a five-word line; holding changes nothing but how long it is readable. Only where the next
    # line starts immediately, and holding is therefore impossible, are the two joined.
    gehalten: list[dict] = []
    for i, z_ in enumerate(zeilen):
        neu_z = dict(z_)
        if neu_z["end"] - neu_z["start"] < min_dauer:
            spielraum = (zeilen[i + 1]["start"] if i + 1 < len(zeilen)
                         else neu_z["start"] + min_dauer)
            neu_z["end"] = round(min(neu_z["start"] + min_dauer, max(neu_z["end"], spielraum)), 3)
        gehalten.append(neu_z)

    # What could not be held long enough is joined to a neighbour: the one before where there is
    # one, otherwise the one after, so a short first line is not left flashing either.
    raus: list[dict] = []
    for neu_z in gehalten:
        if neu_z["end"] - neu_z["start"] < min_dauer * 0.6 and raus:
            raus[-1]["end"] = neu_z["end"]
            raus[-1]["text"] += " " + neu_z["text"]
        else:
            raus.append(neu_z)
    while len(raus) > 1 and raus[0]["end"] - raus[0]["start"] < min_dauer * 0.6:
        raus[1]["start"] = raus[0]["start"]
        raus[1]["text"] = raus[0]["text"] + " " + raus[1]["text"]
        raus.pop(0)
    return raus


def _remap_words(worte: list[dict], segmente: list[dict]) -> list[dict]:
    """Move word times onto the cut timeline. Everything after a cut reads this, and nothing
    re-transcribes: a second pass over the cut file would come back with different words at the
    joins, and then two files would disagree about what was said."""
    raus: list[dict] = []
    versatz = 0.0
    for s in segmente:
        a, b = float(s["start"]), float(s["end"])
        for w in worte:
            if w["start"] >= a and w["end"] <= b:
                raus.append({**w,
                             "start": round(w["start"] - a + versatz, 3),
                             "end": round(w["end"] - a + versatz, 3)})
        versatz += b - a
    return raus


def cmd_video_correct(args: argparse.Namespace) -> int:
    """Fix spellings in a transcript before anything is built from it.

    Recognition gets ordinary words right and proper nouns wrong: product names, people, the
    company. Correcting them in the captions afterwards means doing it again next time, so the fix
    belongs in a list that grows. Without `--replace` this only reports what looks unknown, which is
    the short list where those names sit.

    **Only whole single words are swapped.** A fix that turns two words into one changes the word
    count, and from there every timing belongs to the wrong word: the captions drift, the cut drifts
    with them, and nothing says so.
    """
    vault = Path(args.vault).resolve()
    wd = Path(args.words).expanduser()
    if not wd.is_file():
        print(f"fail: no such transcript: {wd}", file=sys.stderr)
        return 1
    daten = json.loads(wd.read_text(encoding="utf-8"))
    worte = daten.get("words", [])
    if not worte:
        print("fail: the transcript carries no words", file=sys.stderr)
        return 1

    ersetzungen: dict[str, str] = {}
    for paar in (args.replace or []):
        if "=" not in paar:
            print(f"fail: expected heard=correct, got {paar!r}", file=sys.stderr)
            return 1
        a, b = paar.split("=", 1)
        if len(b.split()) != 1:
            print(f"fail: {b!r} is more than one word. Swapping two words for one changes the "
                  f"word count and every timing after it.", file=sys.stderr)
            return 1
        ersetzungen[a.strip()] = b.strip()
    if args.list:
        liste = Path(args.list).expanduser()
        if liste.is_file():
            for zeile in liste.read_text(encoding="utf-8").splitlines():
                zeile = zeile.strip()
                if zeile and not zeile.startswith("#") and "=" in zeile:
                    a, b = zeile.split("=", 1)
                    if len(b.split()) == 1:
                        ersetzungen[a.strip()] = b.strip()

    if not ersetzungen:
        # Report the suspects. Not against a dictionary: the one on this machine is English, and
        # against it every German word looks unknown, which buries the three names that matter in
        # a list of a hundred and sixty. The recogniser's own confidence is language-independent
        # and points at exactly the places it was unsure, which is where the proper nouns are.
        mit_wert = [w for w in worte if isinstance(w.get("p"), (int, float))]
        if not mit_wert:
            print("this transcript carries no confidence values, so nothing can be singled out. "
                  "Transcribe again with this version.", file=sys.stderr)
            return 1
        verdaechtig = sorted((w for w in mit_wert if w["p"] < args.threshold),
                             key=lambda w: w["p"])
        print(f"{len(verdaechtig)} of {len(mit_wert)} words below {args.threshold:.2f} confidence, "
              f"least certain first:")
        for w in verdaechtig[:30]:
            print(f"  {w['p']:.2f}  {w['start']:7.2f}s  {w['word']}")
        print("   Read these in context, then pass the real ones as --replace heard=correct.")
        print("   A name that recurs belongs in a list the next video reads too.")
        return 0

    getroffen = 0
    for w in worte:
        vorne = re.match(r"^\W*", w["word"]).group(0)
        hinten = re.search(r"\W*$", w["word"]).group(0)
        kern = w["word"][len(vorne):len(w["word"]) - len(hinten) if hinten else None]
        if kern in ersetzungen:
            w["word"] = vorne + ersetzungen[kern] + hinten
            getroffen += 1
    daten["words"] = worte
    daten["text"] = " ".join(w["word"] for w in worte)
    ziel = Path(args.out).expanduser() if args.out else wd
    ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: {getroffen} word(s) corrected in {len(worte)}, word count unchanged, at {ziel}")
    return 0


def cmd_video_caption(args: argparse.Namespace) -> int:
    """Captions, as a separate track or burned in.

    Two classes on purpose. A subtitle track scales to any length, can be switched off and is what
    platforms prefer; burning in is for short pieces where the look is part of the piece. Never
    caption something that is already captioned, so the input is stated rather than assumed.
    """
    vault = Path(args.vault).resolve()
    wd = Path(args.words).expanduser()
    if not wd.is_file():
        print(f"fail: no such transcript: {wd}", file=sys.stderr)
        return 1
    daten = json.loads(wd.read_text(encoding="utf-8"))
    worte = daten.get("words", [])
    if args.cutsheet:
        blatt = json.loads(Path(args.cutsheet).expanduser().read_text(encoding="utf-8"))
        worte = _remap_words(worte, blatt.get("segments", blatt))
        if not worte:
            print("fail: nothing of the transcript falls inside the cut", file=sys.stderr)
            return 1
    stil = CAPTION_STYLES.get(args.style, CAPTION_STYLES["subtitle"])
    zeilen = _caption_lines(
        worte,
        args.max_words if args.max_words else stil["max_words"],
        args.max_chars if args.max_chars else stil["max_chars"],
        args.min_duration if args.min_duration else stil["min_duration"],
        stil["comma_always"])

    srt = Path(args.out).expanduser()
    srt.parent.mkdir(parents=True, exist_ok=True)
    teile = []
    for i, z_ in enumerate(zeilen, 1):
        teile.append(f"{i}\n{_srt_time(z_['start'])} --> {_srt_time(z_['end'])}\n{z_['text']}\n")
    srt.write_text("\n".join(teile), encoding="utf-8")
    print(f"ok: {len(zeilen)} caption line(s) at {srt}")

    if args.burn:
        return _burn_captions(vault, Path(args.burn).expanduser(),
                              Path(args.burn_out) if args.burn_out else None, zeilen, args)
    return 0


def _burn_captions(vault: Path, quelle: Path, ziel: Path | None, zeilen: list[dict],
                   args: argparse.Namespace) -> int:
    """Draw the captions as images and lay them over the picture.

    Not through a subtitle filter, deliberately. Whether ffmpeg can draw text at all depends on how
    that particular copy was built, and the common builds cannot: no subtitle renderer, no text
    filter. Detected on the machine this was written on, where both are absent. Drawing the lines
    ourselves works on every build, gives the brand's own typeface and box, and needs one image per
    line rather than per word, which is what keeps it renderable at length.
    """
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not quelle.is_file():
        print("fail: need ffmpeg and the file to draw into", file=sys.stderr)
        return 1
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("fail: drawing captions needs the image library: `tools ensure pillow`.",
              file=sys.stderr)
        return 1
    ziel = ziel or quelle.with_name(quelle.stem + "-captioned.mp4")
    info = _video_probe(vault, quelle)
    breite, hoehe = int(info.get("width") or 1920), int(info.get("height") or 1080)
    # Everything is proportional to the frame, so the same numbers hold at any resolution.
    groesse = max(14, round(hoehe * args.font_size / 1080))
    rand = round(hoehe * args.margin / 1080)
    innen = round(groesse * 0.5)
    try:
        schrift = ImageFont.truetype(args.font_file, groesse) if args.font_file else \
            ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", groesse)
    except OSError:
        schrift = ImageFont.load_default()

    ordner = _video_job_dir(vault, args.slug) / "captions"
    ordner.mkdir(parents=True, exist_ok=True)
    mess = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    maxbreite = breite - 2 * round(breite * 0.06)
    bilder: list[tuple[Path, float, float]] = []
    for i, z_ in enumerate(zeilen):
        worte, gebrochen, laufend = z_["text"].split(), [], ""
        for w in worte:
            probe = (laufend + " " + w).strip()
            if mess.textbbox((0, 0), probe, font=schrift)[2] > maxbreite and laufend:
                gebrochen.append(laufend)
                laufend = w
            else:
                laufend = probe
        if laufend:
            gebrochen.append(laufend)
        zeilenhoehe = round(groesse * 1.35)
        block = zeilenhoehe * len(gebrochen)
        bild = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
        zeichne = ImageDraw.Draw(bild)
        oben = hoehe - rand - block
        kasten = max(mess.textbbox((0, 0), g, font=schrift)[2] for g in gebrochen)
        zeichne.rounded_rectangle(
            [breite / 2 - kasten / 2 - innen, oben - innen,
             breite / 2 + kasten / 2 + innen, oben + block + innen],
            radius=round(groesse * 0.3), fill=args.box_colour)
        for k, g in enumerate(gebrochen):
            # A fixed baseline per line: centring the drawn shape instead would lift every line
            # that happens to have no descender in it.
            zeichne.text((breite / 2, oben + k * zeilenhoehe + zeilenhoehe / 2), g,
                         font=schrift, fill=args.text_colour, anchor="mm")
        pfad = ordner / f"c{i:04d}.png"
        bild.save(pfad)
        bilder.append((pfad, z_["start"], z_["end"]))

    # One overlay, not one per line. Chaining a filter per caption works and is unusably slow:
    # measured at 232 seconds for a two-minute piece with 104 lines, because every link in the
    # chain re-composites the whole frame. Instead the captions become a single transparent track
    # of their own, assembled from the images with their own durations, and the picture meets it
    # exactly once.
    fps = float(info.get("fps") or 25)
    leer = ordner / "leer.png"
    Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0)).save(leer)
    liste, zeit = [], 0.0
    for pfad, a, b in bilder:
        if a > zeit + 0.01:
            liste.append((leer, a - zeit))
        liste.append((pfad, max(0.04, b - a)))
        zeit = b
    dauer = float(info.get("duration") or zeit)
    if dauer > zeit:
        liste.append((leer, dauer - zeit))
    spur = ordner / "track.txt"
    zeilen_txt = []
    for pfad, d in liste:
        zeilen_txt.append(f"file '{pfad}'")
        zeilen_txt.append(f"duration {d:.3f}")
    zeilen_txt.append(f"file '{liste[-1][0]}'")   # the concat demuxer needs the last one twice
    spur.write_text("\n".join(zeilen_txt) + "\n", encoding="utf-8")

    cmd = [ffmpeg, "-y", "-i", str(quelle),
           "-f", "concat", "-safe", "0", "-i", str(spur),
           "-filter_complex",
           f"[1:v]fps={fps},format=rgba[subs];[0:v][subs]overlay=0:0:eof_action=pass[o]",
           "-map", "[o]", "-map", "0:a?",
           "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
           str(ziel), "-loglevel", "error"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"fail: drawing the captions in did not work.\n{(r.stderr or '')[-600:]}",
              file=sys.stderr)
        return 1
    print(f"ok: {len(bilder)} caption(s) drawn into {ziel}, {ziel.stat().st_size / 1e6:.1f} MB")
    return 0


VIDEO_FORMATS = {
    "wide": (16, 9), "upright": (9, 16), "square": (1, 1), "classic": (4, 3),
}

# What the export profiles are for, in the user's terms rather than in codec terms.
VIDEO_PROFILES = {
    "master": {"crf": 18, "preset": "slow", "audio": "192k", "scale": None,
               "why": "the one to keep and to work from again"},
    "web": {"crf": 24, "preset": "fast", "audio": "128k", "scale": 1080,
            "why": "small enough to send, good enough to watch"},
    "platform": {"crf": 21, "preset": "medium", "audio": "192k", "scale": 1080,
                 "why": "what a platform re-encodes without making it worse"},
}


def cmd_video_reframe(args: argparse.Namespace) -> int:
    """Put the picture into another aspect ratio.

    Two ways, and the choice is the point. Cropping keeps the picture full-height and throws away
    the sides, which is right when what matters is in the middle and wrong the moment a face or a
    caption sits outside the new frame: going from wide to upright throws away two thirds of the
    width. Fitting keeps everything and fills the rest with a blurred enlargement of the same
    picture, which loses nothing and is what platforms are used to seeing.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    if args.format not in VIDEO_FORMATS:
        print(f"fail: unknown format {args.format}, expected one of "
              f"{', '.join(VIDEO_FORMATS)}", file=sys.stderr)
        return 1
    info = _video_probe(vault, src)
    bw, bh = int(info.get("width") or 1920), int(info.get("height") or 1080)
    zw, zh = VIDEO_FORMATS[args.format]
    hoehe = args.height or (1920 if zh > zw else 1080)
    breite = int(round(hoehe * zw / zh / 2) * 2)
    verloren = 100 * (1 - min(1.0, (bh * zw / zh) / bw))

    if args.fit:
        graph = (f"[0:v]scale={breite}:{hoehe}:force_original_aspect_ratio=increase,"
                 f"crop={breite}:{hoehe},boxblur=luma_radius=min(h\\,w)/12:luma_power=1[bg];"
                 f"[0:v]scale={breite}:{hoehe}:force_original_aspect_ratio=decrease[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
        art = "fitted, nothing cropped away"
    else:
        # The crop window sits centred unless told otherwise. `--centre` is a fraction of the
        # width, so it survives a change of resolution.
        mitte = max(0.0, min(1.0, args.centre))
        graph = (f"[0:v]crop=min(iw\\,ih*{zw}/{zh}):min(ih\\,iw*{zh}/{zw}):"
                 f"(iw-min(iw\\,ih*{zw}/{zh}))*{mitte}:(ih-min(ih\\,iw*{zh}/{zw}))/2,"
                 f"scale={breite}:{hoehe}")
        art = f"cropped, about {verloren:.0f}% of the width dropped"

    r = subprocess.run([ffmpeg, "-y", "-i", str(src), "-filter_complex", graph,
                        "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                        str(ziel), "-loglevel", "error"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"fail: reframing did not work.\n{(r.stderr or '')[-600:]}", file=sys.stderr)
        return 1
    print(f"ok: {bw}x{bh} to {breite}x{hoehe} ({args.format}), {art}, at {ziel}")
    if not args.fit and verloren > 40:
        print(f"   {verloren:.0f}% of the picture is gone. Look at what was on those sides before "
              f"this goes out, or use --fit.")
    return 0


def cmd_video_mix(args: argparse.Namespace) -> int:
    """The audio passes: clean it, add a bed, level it. Picture untouched.

    Copying the picture rather than re-encoding is not an optimisation, it is the difference
    between one generation of quality loss and two. The bed sits well below speech and does not
    duck: where it is too loud, the level is wrong, and a sidechain only hides that.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    ketten = []
    if args.denoise:
        # Gentle, and through the right knob. How much is removed is `nr` in decibels; the noise
        # floor is a separate value with its own valid range, and setting the amount there is
        # rejected outright ("result too large") rather than merely being wrong. Six decibels
        # takes the hiss off without hollowing out the voice; the default of twelve already
        # reads as muffled on a voice recorded in a normal room.
        ketten.append(f"afftdn=nr={args.denoise_db}:nf=-35")
    ketten.append(f"loudnorm=I={args.loudness}:TP=-1.5:LRA=11")
    sprache = ",".join(ketten)

    cmd = [ffmpeg, "-y", "-i", str(src)]
    if args.music:
        musik = Path(args.music).expanduser()
        if not musik.is_file():
            print(f"fail: no such music file: {musik}", file=sys.stderr)
            return 1
        dauer = _video_probe(vault, src).get("duration", 0.0)
        cmd += ["-stream_loop", "-1", "-i", str(musik), "-filter_complex",
                f"[0:a]{sprache}[v];"
                f"[1:a]volume={args.music_db}dB,afade=t=out:st={max(0.0, dauer - 2.0)}:d=2[m];"
                f"[v][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-filter:a", sprache, "-map", "0:v", "-map", "0:a"]
    cmd += ["-c:v", "copy", *_audio_out(ziel),
            "-movflags", "+faststart", str(ziel), "-loglevel", "error"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"fail: the audio pass did not work.\n{(r.stderr or '')[-600:]}", file=sys.stderr)
        return 1
    teile = ["levelled to " + str(args.loudness) + " LUFS"]
    if args.denoise:
        teile.insert(0, "denoised")
    if args.music:
        teile.append(f"bed at {args.music_db} dB")
    print(f"ok: {', '.join(teile)}, picture copied untouched, at {ziel}")
    return 0


def cmd_video_export(args: argparse.Namespace) -> int:
    """One file per purpose, and the master is never overwritten.

    By the end of a job the folder holds several attempts and nobody remembers which one went out.
    Naming by purpose fixes that, and refusing to write over an existing master fixes the worse
    version of it, where the good file is gone and the loss shows up weeks later.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    profile = args.profile.split(",")
    unbekannt = [p_ for p_ in profile if p_ not in VIDEO_PROFILES]
    if unbekannt:
        print(f"fail: unknown profile(s) {', '.join(unbekannt)}, expected from "
              f"{', '.join(VIDEO_PROFILES)}", file=sys.stderr)
        return 1
    raus = Path(args.out_dir).expanduser() if args.out_dir else src.parent
    raus.mkdir(parents=True, exist_ok=True)
    for name in profile:
        spec = VIDEO_PROFILES[name]
        ziel = raus / f"{args.name}-{name}.mp4"
        if ziel.exists() and not args.overwrite:
            print(f"skip: {ziel.name} exists. Nothing is written over: pass --overwrite if that "
                  f"is really what you want.")
            continue
        vf = []
        if spec["scale"]:
            vf = ["-vf", f"scale=-2:'min({spec['scale']},ih)'"]
        r = subprocess.run([ffmpeg, "-y", "-i", str(src), *vf,
                            "-c:v", "libx264", "-crf", str(spec["crf"]),
                            "-preset", spec["preset"], "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", spec["audio"],
                            "-movflags", "+faststart", str(ziel), "-loglevel", "error"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"fail: {name} did not render.\n{(r.stderr or '')[-400:]}", file=sys.stderr)
            return 1
        print(f"ok: {ziel.name}, {ziel.stat().st_size / 1e6:.1f} MB, {spec['why']}")
    return 0


def cmd_video_brand(args: argparse.Namespace) -> int:
    """Put the brand on the picture: an opening, a closing, a logo held throughout.

    The bumpers are joined rather than overlaid, which means they have to match the piece in size,
    frame rate and audio layout or the join tears. They are re-encoded to match rather than the
    other way round: the piece is the master here, the bumper is the guest.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    info = _video_probe(vault, src)
    breite, hoehe = int(info.get("width") or 1920), int(info.get("height") or 1080)
    fps = info.get("fps_exact") or "25/1"
    zwischen = _video_job_dir(vault, args.slug)

    mit_logo = src
    if args.logo:
        logo = Path(args.logo).expanduser()
        if not logo.is_file():
            print(f"fail: no such logo: {logo}", file=sys.stderr)
            return 1
        # Proportional to the frame, so the same numbers hold at any resolution, and inside the
        # margin that platforms cover with their own controls.
        lb = max(24, round(breite * args.logo_width / 100))
        rand_x = round(breite * args.logo_margin / 100)
        rand_y = round(hoehe * args.logo_margin / 100)
        stelle = {
            "top-left": (rand_x, rand_y),
            "top-right": (f"W-w-{rand_x}", rand_y),
            "bottom-left": (rand_x, f"H-h-{rand_y}"),
            "bottom-right": (f"W-w-{rand_x}", f"H-h-{rand_y}"),
        }.get(args.logo_position)
        if not stelle:
            print(f"fail: unknown logo position {args.logo_position}", file=sys.stderr)
            return 1
        mit_logo = zwischen / "with-logo.mp4"
        r = subprocess.run(
            # -loop, for the same reason as the captions: a still image is one frame at time zero,
            # and an overlay reading it composites nothing for the rest of the piece. Silently.
            [ffmpeg, "-y", "-i", str(src), "-loop", "1", "-i", str(logo), "-filter_complex",
             f"[1:v]scale={lb}:-1,format=rgba,colorchannelmixer=aa={args.logo_opacity}[lg];"
             f"[0:v][lg]overlay={stelle[0]}:{stelle[1]}:eof_action=pass[o]",
             "-map", "[o]", "-map", "0:a?", "-shortest",
             "-c:v", "libx264", "-crf", str(args.crf),
             "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy",
             str(mit_logo), "-loglevel", "error"], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"fail: the logo did not composite.\n{(r.stderr or '')[-500:]}", file=sys.stderr)
            return 1

    teile = []
    for rolle, pfad in (("intro", args.intro), ("main", None), ("outro", args.outro)):
        if rolle == "main":
            teile.append(mit_logo)
            continue
        if not pfad:
            continue
        quelle = Path(pfad).expanduser()
        if not quelle.is_file():
            print(f"fail: no such {rolle}: {quelle}", file=sys.stderr)
            return 1
        angepasst = zwischen / f"{rolle}-matched.mp4"
        # A bumper without a sound track cannot simply be joined to one that has: the join needs
        # the same number of streams on both sides, so silence is generated for its exact length
        # rather than hoping the concat sorts it out.
        hat_ton = bool(_video_probe(vault, quelle).get("audio"))
        cmd_b = [ffmpeg, "-y", "-i", str(quelle)]
        if not hat_ton:
            cmd_b += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        cmd_b += ["-filter_complex",
                  f"[0:v]scale={breite}:{hoehe}:force_original_aspect_ratio=decrease,"
                  f"pad={breite}:{hoehe}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1[v]",
                  "-map", "[v]", "-map", "0:a" if hat_ton else "1:a", "-shortest",
                  "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                  "-ar", "48000", "-ac", "2", str(angepasst), "-loglevel", "error"]
        r = subprocess.run(cmd_b, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"fail: the {rolle} could not be matched to the piece.\n"
                  f"{(r.stderr or '')[-400:]}", file=sys.stderr)
            return 1
        teile.insert(0 if rolle == "intro" else len(teile), angepasst)

    if len(teile) == 1:
        if mit_logo != src:
            shutil.move(str(mit_logo), str(ziel))
            print(f"ok: logo held throughout, at {ziel}")
            return 0
        print("fail: nothing to do: no intro, no outro, no logo", file=sys.stderr)
        return 1

    # Joined through the filter rather than by listing the files. Listing them is cheaper because
    # nothing is decoded, and it fails the moment two sound tracks differ in a detail nobody set on
    # purpose: a bumper made elsewhere, a silence track written by a different encoder. The filter
    # decodes both and writes one clean stream, which is what a join has to survive.
    cmd_j = [ffmpeg, "-y"]
    for teil in teile:
        cmd_j += ["-i", str(teil)]
    ketten = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(len(teile)))
    cmd_j += ["-filter_complex", f"{ketten}concat=n={len(teile)}:v=1:a=1[v][a]",
              "-map", "[v]", "-map", "[a]",
              "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
              "-pix_fmt", "yuv420p", *_audio_out(ziel),
              "-movflags", "+faststart", str(ziel), "-loglevel", "error"]
    r = subprocess.run(cmd_j, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"fail: joining did not work.\n{(r.stderr or '')[-600:]}", file=sys.stderr)
        return 1
    was = [x for x, y in (("intro", args.intro), ("outro", args.outro), ("logo", args.logo)) if y]
    print(f"ok: {', '.join(was)} applied, "
          f"{_spoken_length(_video_probe(vault, ziel).get('duration', 0.0))} at {ziel}")
    return 0


def cmd_video_chapters(args: argparse.Namespace) -> int:
    """Chapter marks from the transcript, as a list to paste and as metadata in the file."""
    vault = Path(args.vault).resolve()
    wd = Path(args.words).expanduser()
    if not wd.is_file():
        print(f"fail: no such transcript: {wd}", file=sys.stderr)
        return 1
    worte = json.loads(wd.read_text(encoding="utf-8")).get("words", [])
    if not worte:
        print("fail: the transcript carries no words", file=sys.stderr)
        return 1
    ende = worte[-1]["end"]
    schritt = max(args.min_gap, ende / max(1, args.count))
    kapitel, naechste = [], 0.0
    for w in worte:
        if w["start"] >= naechste:
            # Start a chapter on a word that begins a sentence where possible, so the title reads
            # like something rather than starting mid-clause.
            kapitel.append({"start": round(w["start"], 3), "words": [w["word"]]})
            naechste = w["start"] + schritt
        elif kapitel:
            if len(kapitel[-1]["words"]) < args.title_words:
                kapitel[-1]["words"].append(w["word"])
    zeilen = []
    for k in kapitel:
        m, s = divmod(int(k["start"]), 60)
        h, m = divmod(m, 60)
        stempel = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        zeilen.append(f"{stempel} {' '.join(k['words']).strip('.,')}")
    text = "\n".join(zeilen) + "\n"
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8")
    print(f"ok: {len(kapitel)} chapter(s)")
    print(text, end="")
    print("   Titles are the first words spoken, not a summary. Rewrite them before they go out.")
    return 0


def cmd_video_thumbnail(args: argparse.Namespace) -> int:
    """Candidates for a thumbnail: the sharpest, best-lit frames rather than an arbitrary one.

    Sharpness is measured as local contrast, which is what a blurred or motion-smeared frame
    lacks; brightness is checked so a candidate is not a cut to black. Choosing between the
    candidates is a judgement and stays with whoever is looking at them.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("fail: needs the image library: `tools ensure pillow`.", file=sys.stderr)
        return 1
    dauer = _video_probe(vault, src).get("duration", 0.0)
    raus = Path(args.out).expanduser() if args.out else _video_job_dir(vault, args.slug) / "thumbs"
    raus.mkdir(parents=True, exist_ok=True)
    kandidaten = []
    for i in range(args.sample):
        t0 = dauer * (i + 0.5) / args.sample
        pfad = raus / f"cand{i:02d}.jpg"
        if not _grab_frame(ffmpeg, src, t0, pfad, "-q:v", "2"):
            continue
        klein = Image.open(pfad).convert("L").resize((160, 90))
        px = list(klein.get_flattened_data()) if hasattr(klein, "get_flattened_data") \
            else list(klein.getdata())
        hell = sum(px) / len(px)
        schaerfe = sum(abs(px[j] - px[j - 1]) for j in range(1, len(px))) / len(px)
        kandidaten.append((schaerfe, hell, t0, pfad))
    brauchbar = [k for k in kandidaten if 40 < k[1] < 225]
    brauchbar.sort(reverse=True)
    if not brauchbar:
        print("fail: no usable frame found", file=sys.stderr)
        return 1
    for schaerfe, hell, t0, pfad in brauchbar[:args.keep]:
        print(f"  {t0:8.2f}s  detail {schaerfe:5.1f}  brightness {hell:5.1f}  {pfad.name}")
    for _, _, _, pfad in brauchbar[args.keep:]:
        pfad.unlink(missing_ok=True)
    print(f"ok: {min(args.keep, len(brauchbar))} candidate(s) in {raus}. Which one works is a "
          f"judgement; look at them.")
    return 0


def cmd_video_text(args: argparse.Namespace) -> int:
    """Write the transcript out for editing, and read an edited one back as a cut.

    Two directions of the same idea. Written out, it is plain paragraphs with no timings in the
    way, because a file full of numbers does not get edited. Read back, the words that survived are
    matched against the original in order, and what disappeared becomes a cut. Only deletions are
    honoured: a corrected word changes the captions, not the picture, and moving a paragraph is not
    supported, so a text that has been reordered is reported rather than half-applied.
    """
    vault = Path(args.vault).resolve()
    wd = Path(args.words).expanduser()
    if not wd.is_file():
        print(f"fail: no such transcript: {wd}", file=sys.stderr)
        return 1
    daten = json.loads(wd.read_text(encoding="utf-8"))
    worte = daten.get("words", [])
    if not worte:
        print("fail: the transcript carries no words", file=sys.stderr)
        return 1

    if args.write:
        ziel = Path(args.write).expanduser()
        ziel.parent.mkdir(parents=True, exist_ok=True)
        absaetze, laufend, letzte = [], [], worte[0]["end"]
        for w in worte:
            # A pause is where a paragraph ends, which is also where a deletion is cheapest.
            if w["start"] - letzte > args.paragraph_gap and laufend:
                absaetze.append(" ".join(laufend))
                laufend = []
            laufend.append(w["word"])
            letzte = w["end"]
        if laufend:
            absaetze.append(" ".join(laufend))
        kopf = ("<!-- Delete what should go: a word, a sentence, a whole paragraph. Correcting a\n"
                "     word changes the captions, not the cut. Do not reorder. -->\n\n")
        ziel.write_text(kopf + "\n\n".join(absaetze) + "\n", encoding="utf-8")
        print(f"ok: {len(absaetze)} paragraph(s), {len(worte)} words at {ziel}")
        return 0

    bearbeitet = Path(args.read).expanduser()
    if not bearbeitet.is_file():
        print(f"fail: no such edited text: {bearbeitet}", file=sys.stderr)
        return 1
    import difflib
    import re as _re

    def schluessel(s: str) -> str:
        return _re.sub(r"[^0-9a-zäöüßA-ZÄÖÜ]", "", s).lower()

    roh = _re.sub(r"<!--.*?-->", " ", bearbeitet.read_text(encoding="utf-8"), flags=_re.S)
    neu = [schluessel(x) for x in roh.split() if schluessel(x)]
    alt = [schluessel(w["word"]) for w in worte]
    passung = difflib.SequenceMatcher(None, alt, neu)
    behalten = [False] * len(worte)
    umgestellt = 0
    for tag, i1, i2, j1, j2 in passung.get_opcodes():
        if tag in ("equal", "replace"):
            # `replace` is a correction of the wording: the moment stays, the text changes.
            for i in range(i1, i2):
                behalten[i] = True
        elif tag == "insert":
            umgestellt += j2 - j1
    if umgestellt > args.tolerance:
        print(f"fail: the text has {umgestellt} word(s) that are not in the original. Words can be "
              f"deleted and corrected, not added or moved; nothing was cut.", file=sys.stderr)
        return 1

    quelle = args.source or daten.get("source")
    segmente, offen = [], None
    for w, bleibt in zip(worte, behalten):
        if not bleibt:
            if offen:
                segmente.append(offen)
                offen = None
            continue
        if offen and w["start"] - offen["end"] <= args.join:
            offen["end"] = w["end"]
            offen["text"] += " " + w["word"]
        else:
            if offen:
                segmente.append(offen)
            offen = {"source": quelle, "start": round(max(0.0, w["start"] - 0.08), 3),
                     "end": w["end"], "text": w["word"]}
    if offen:
        segmente.append(offen)
    for s in segmente:
        s["end"] = round(s["end"] + VIDEO_TAIL / 2, 3)
    weg = sum(1 for b in behalten if not b)
    ziel = Path(args.out).expanduser()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({"segments": segmente}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    behalten_s = sum(s["end"] - s["start"] for s in segmente)
    print(f"ok: {weg} of {len(worte)} words deleted, {len(segmente)} segment(s), "
          f"{_spoken_length(behalten_s)} left, at {ziel}")
    if weg == 0:
        print("   Nothing was deleted, so this cut is the whole recording.")
    return 0


def cmd_video_sync(args: argparse.Namespace) -> int:
    """Find the offset between two recordings of the same conversation.

    Two people recording themselves start at different moments, and nothing in the files says by
    how much. The sound does: both microphones pick up the same speech, so the offset is where the
    two signals line up best. Measured on the loudness envelope rather than the waveform, which
    survives different microphones, different rooms and different gain.
    """
    vault = Path(args.vault).resolve()
    a, b = Path(args.a).expanduser(), Path(args.b).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not a.is_file() or not b.is_file():
        print("fail: need ffmpeg and both files", file=sys.stderr)
        return 1
    job = _video_job_dir(vault, args.slug)
    huellen = []
    for name, quelle in (("a", a), ("b", b)):
        wav = job / f"sync-{name}.wav"
        subprocess.run([ffmpeg, "-y", "-i", str(quelle), "-vn", "-ac", "1", "-ar", "8000",
                        "-t", str(args.window), "-c:a", "pcm_s16le", str(wav)],
                       check=True, capture_output=True)
        h, hop = _rms_envelope(wav, hop=0.02)
        mittel = sum(h) / len(h) if h else 0.0
        huellen.append([x - mittel for x in h])
    ha, hb = huellen
    if not ha or not hb:
        print("fail: no audio to compare", file=sys.stderr)
        return 1
    grenze = int(args.max_offset / 0.02)
    bestes, versatz = None, 0
    for k in range(-grenze, grenze + 1):
        summe, n = 0.0, 0
        for i in range(len(ha)):
            j = i + k
            if 0 <= j < len(hb):
                summe += ha[i] * hb[j]
                n += 1
        if n > 50:
            wert = summe / n
            if bestes is None or wert > bestes:
                bestes, versatz = wert, k
    sekunden = versatz * 0.02
    print(f"ok: the second recording runs {abs(sekunden):.2f}s "
          f"{'behind' if sekunden > 0 else 'ahead of'} the first")
    print(f"   trim: ffmpeg -ss {abs(sekunden):.3f} on "
          f"{'the second' if sekunden > 0 else 'the first'} file")
    if bestes is not None and bestes < args.min_confidence:
        print("   The match is weak. Either the two recordings do not overlap in the window that "
              "was compared, or one side never picks up the other speaker.", file=sys.stderr)
        return 1
    return 0


def _grab_frame(ffmpeg: str, src: Path, t0: float, ziel: Path, *filter_args: str) -> bool:
    """One frame at one moment, reliably.

    Seeking before the input is fast, because the decoder jumps straight there, and on some files
    it returns nothing at all: a container whose index the fast path cannot use produces an empty
    output and an error nobody reads. Seeking after the input decodes up to the moment, which is
    slower and always works. Fast first, exact second: on a long file the difference is seconds
    against a minute, and on a stubborn file it is a picture against none.
    """
    for cmd in (
        [ffmpeg, "-y", "-ss", f"{t0:.3f}", "-i", str(src), "-frames:v", "1", *filter_args,
         str(ziel), "-loglevel", "error"],
        [ffmpeg, "-y", "-i", str(src), "-ss", f"{t0:.3f}", "-frames:v", "1", *filter_args,
         str(ziel), "-loglevel", "error"],
    ):
        subprocess.run(cmd, capture_output=True)
        if ziel.is_file() and ziel.stat().st_size > 0:
            return True
    return False


def cmd_video_timeline(args: argparse.Namespace) -> int:
    """One picture of the whole piece: a filmstrip, the loudness underneath, the words along it.

    This is the cheap way to look at a video. Twenty-four separate frames cost more than the edit
    they were meant to inform; one composite the size of a screenshot says where the scenes change,
    where it is quiet, where somebody is talking, and roughly what about. Read this first and pull
    individual frames only for a spot the strip actually raises a question about.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("fail: needs the image library: `tools ensure pillow`.", file=sys.stderr)
        return 1

    info = _video_probe(vault, src)
    dauer = info.get("duration") or 0.0
    if dauer <= 0:
        print("fail: cannot read the duration", file=sys.stderr)
        return 1
    arbeit = _video_job_dir(vault, args.slug)
    n = max(4, min(args.columns, 24))
    # Both even. An odd height is rejected outright by the colour format every JPEG uses, and
    # the error it produces ("invalid argument") says nothing about which of the two numbers
    # was wrong. 135 cost half an hour.
    kachel_b, kachel_h = 240, 136
    welle_h, wort_h, rand = 60, 46, 10

    # The filmstrip: evenly spaced, small, in one row.
    streifen = Image.new("RGB", (n * kachel_b, kachel_h), (20, 20, 20))
    for i in range(n):
        t0 = dauer * (i + 0.5) / n
        einzel = arbeit / f"strip{i:02d}.jpg"
        _grab_frame(ffmpeg, src, t0, einzel,
                    "-vf", f"scale={kachel_b}:{kachel_h}:force_original_aspect_ratio=decrease,"
                           f"pad={kachel_b}:{kachel_h}:(ow-iw)/2:(oh-ih)/2", "-q:v", "5")
        if einzel.is_file() and einzel.stat().st_size > 0:
            streifen.paste(Image.open(einzel), (i * kachel_b, 0))
            einzel.unlink(missing_ok=True)

    breite = n * kachel_b
    bild = Image.new("RGB", (breite, kachel_h + welle_h + wort_h + rand * 2), (16, 16, 16))
    bild.paste(streifen, (0, 0))
    zeichne = ImageDraw.Draw(bild)
    try:
        schrift = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except OSError:
        schrift = ImageFont.load_default()

    # The loudness underneath, from the same audio the transcript came from.
    wav = arbeit / f"{src.stem}.16k.wav"
    if not wav.is_file():
        subprocess.run([ffmpeg, "-y", "-i", str(src), "-vn", "-ar", "16000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(wav), "-loglevel", "error"], capture_output=True)
    oben = kachel_h + rand
    if wav.is_file():
        huelle, hop = _rms_envelope(wav, hop=max(0.02, dauer / breite))
        spitze = max(huelle) or 1.0
        for x in range(breite):
            i = int(x * len(huelle) / breite)
            h = int(welle_h * min(1.0, huelle[i] / spitze))
            zeichne.line([(x, oben + welle_h - h), (x, oben + welle_h)], fill=(90, 170, 230))

    # The words along the bottom, thinned to what fits rather than overlapped into a smear.
    wd = Path(args.words).expanduser() if args.words else None
    if wd and wd.is_file():
        worte = json.loads(wd.read_text(encoding="utf-8")).get("words", [])
        letzte_x = -999
        for w in worte:
            x = int(w["start"] / dauer * breite)
            if x - letzte_x < 70:
                continue
            zeichne.text((x + 2, oben + welle_h + 4), w["word"][:14], font=schrift,
                         fill=(220, 220, 220))
            letzte_x = x

    # A time ruler on the strip itself, so a finding can be named in seconds.
    for i in range(n):
        t0 = dauer * i / n
        x = i * kachel_b
        zeichne.line([(x, 0), (x, kachel_h)], fill=(60, 60, 60))
        zeichne.text((x + 3, 3), f"{int(t0 // 60)}:{int(t0 % 60):02d}", font=schrift,
                     fill=(255, 255, 255))

    ziel = Path(args.out).expanduser() if args.out else arbeit / "timeline.jpg"
    bild.save(ziel, quality=82)
    print(f"ok: one picture of {_spoken_length(dauer)} at {ziel}")
    print("   Read this instead of pulling frames. Pull a frame only where the strip raises a "
          "question, and name the second it is at.")
    return 0


def cmd_video_brief(args: argparse.Namespace) -> int:
    """Everything needed to judge a piece of footage, in one call.

    This exists because the alternative happened: asked to look at a 78-second clip, a run made 34
    tool calls, pulled 24 frames, read every one of them and spent seven minutes and 75,000 tokens.
    Frames are images and images are the expensive thing; a transcript costs almost nothing and
    says most of it. So this measures what can be measured for free, transcribes once, and pulls a
    handful of frames on purpose rather than as many as seem interesting.

    The point of looking before working is to spend less, not more. An analysis that costs as much
    as the edit has defeated itself.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    ffmpeg = _tool_path(vault, "ffmpeg")
    info = _video_probe(vault, src)
    dauer = info.get("duration", 0.0)
    print(f"# {src.name}")
    print(f"{_spoken_length(dauer)}, {info.get('width')}x{info.get('height')}, "
          f"{info.get('fps')} fps, {src.stat().st_size / 1e6:.0f} MB"
          + (f", {info.get('chapters')} chapter track(s)" if info.get("chapters") else ""))

    # Loudness, measured in one pass. Free, and it is the fact that decides most of the audio work.
    if ffmpeg:
        r = subprocess.run([ffmpeg, "-i", str(src), "-af", "ebur128=framelog=verbose",
                            "-f", "null", "-", "-loglevel", "info"],
                           capture_output=True, text=True)
        werte = re.findall(r"I:\s*(-?[0-9.]+) LUFS", r.stderr or "")
        spitze = re.findall(r"Peak:\s*(-?[0-9.]+) dBFS", r.stderr or "")
        if werte:
            lufs = float(werte[-1])
            print(f"loudness {lufs:.1f} LUFS"
                  + (f", peak {spitze[-1]} dBFS" if spitze else ""))
            if lufs < -20:
                print(f"  {abs(lufs + 16):.0f} dB below a normal target for speech. Lifting it "
                      f"brings the room noise up with it.")

    # The words. Whole where that is cheap, sampled where it is not: transcribing runs at roughly
    # thirty times real time, so two hours of recording is four minutes of waiting for a first
    # look. Past the threshold, beginning, middle and end answer the question (operating-principles
    # §14); the full transcript is made later, once the work has been agreed.
    worte: list[dict] = []
    probe_quelle = src
    gestueckelt = False
    if ffmpeg and dauer > args.sample_over:
        stuecke, laenge = [], args.sample_seconds
        arbeit = _video_job_dir(vault, args.slug or "brief")
        for i, start in enumerate((0.0, max(0.0, dauer / 2 - laenge / 2), max(0.0, dauer - laenge))):
            stueck = arbeit / f"sample{i}.wav"
            subprocess.run([ffmpeg, "-y", "-ss", f"{start:.2f}", "-t", str(laenge), "-i", str(src),
                            "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(stueck),
                            "-loglevel", "error"], capture_output=True)
            if stueck.is_file():
                stuecke.append(stueck)
        if len(stuecke) == 3:
            liste = arbeit / "sample.txt"
            liste.write_text("".join(f"file '{s}'\n" for s in stuecke), encoding="utf-8")
            probe_quelle = arbeit / "sample.wav"
            subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
                            "-c", "copy", str(probe_quelle), "-loglevel", "error"],
                           capture_output=True)
            gestueckelt = probe_quelle.is_file()
            if gestueckelt:
                print(f"\nlonger than {_spoken_length(args.sample_over)}, so the words come from "
                      f"three samples of {laenge:.0f}s: the start, the middle and the end")
    if args.slug:
        ns = argparse.Namespace(vault=str(vault), file=str(probe_quelle), slug=args.slug,
                                language=args.language, lexicon=None, dtw_preset=None, force=False)
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_video_transcribe(ns)
        wd = _video_job_dir(vault, args.slug) / f"{probe_quelle.stem}.words.json"
        if wd.is_file():
            worte = json.loads(wd.read_text(encoding="utf-8")).get("words", [])

    if worte:
        pausen = [] if gestueckelt else [(worte[i + 1]["start"] - worte[i]["end"], worte[i]["end"])
                  for i in range(len(worte) - 1)
                  if worte[i + 1]["start"] - worte[i]["end"] > 0.5]
        laengste = sorted(pausen, reverse=True)[:3]
        gesprochen = sum(w["end"] - w["start"] for w in worte)
        print(f"{len(worte)} words, {gesprochen / max(dauer, 1) * 100:.0f}% of the runtime is "
              f"speech, {len(pausen)} pause(s) over half a second")
        for laenge, wann in laengste:
            print(f"  {laenge:.1f}s of silence at {wann:.0f}s")
        print("\n--- what is said ---")
        print(" ".join(w["word"] for w in worte))

    # What is missing before it becomes a surprise mid-job. The register knows what each path
    # needs; asking it here costs nothing and turns "it stopped working" into "fetch this first".
    fehlend: list[str] = []
    for tid in ("ffmpeg", "ffprobe", "whisper", "whisper-model", "node", "hyperframes"):
        spec = (_load_register().get("tools") or {}).get(tid)
        if not spec:
            continue
        if not _detect_tool(vault, tid, spec, _current_os()).get("present"):
            fehlend.append(tid)
    if fehlend:
        print(f"\nmissing for parts of the pipeline: {', '.join(fehlend)}")
        print("  Cutting, captions and sound need the first four. Motion graphics need the last "
              "two, and without them that step is not available at all: say so and offer to fetch "
              "them, rather than drawing frames by hand and calling it done.")

    # What the piece would be dressed in. Asked here because it is the question that gets skipped:
    # a run that finds nothing quietly picks its own colours and typeface, and the user first sees
    # the choice in a finished render.
    marken = sorted(d.name for d in (vault / DESIGN_DIR).iterdir()
                    if d.is_dir()) if (vault / DESIGN_DIR).is_dir() else []
    print()
    if marken:
        print(f"brand(s) available: {', '.join(marken)}")
    else:
        print("no brand set in this vault. Anything visible (captions, a logo, an opening, a "
              "graphic) has no colours, typeface or mark to take, so ask before making them up: "
              "which brand, or which colours and typeface, or explicitly plain.")

    # One picture, not a handful of frames. A composite of filmstrip, loudness and words says where
    # the scenes change, where it is quiet and roughly what about, at the cost of a single image.
    # Separate frames cost that much each, and twenty-four of them cost more than the edit.
    if ffmpeg:
        ns = argparse.Namespace(
            vault=str(vault), file=str(src),
            words=str(_video_job_dir(vault, args.slug) / f"{probe_quelle.stem}.words.json")
            if worte else None,
            columns=args.columns, slug=args.slug or "brief", out=None)
        print()
        cmd_video_timeline(ns)
    return 0


def cmd_video_check(args: argparse.Namespace) -> int:
    """The technical half of the review, measured rather than looked at.

    Three faults belong here because a pair of eyes is the wrong instrument for them. Duplicated
    frames are the vicious one: chain several short overlays over a long base and the scheduler
    starts repeating output frames on a regular cadence. Every input measures clean on its own and
    the result reports a flawless constant frame rate, while the content actually updates at a
    fraction of it. It reads as judder on anything smooth, and the search goes to the wrong place
    every time. The other two are a brightness step at a join, which is what round-tripping
    footage through a browser costs, and a length that does not match what was asked for.
    """
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    info = _video_probe(vault, src)
    befunde: list[str] = []
    print(f"{src.name}: {_spoken_length(info.get('duration', 0.0))}, "
          f"{info.get('width')}x{info.get('height')}, {info.get('fps')} fps")

    # Duplicated frames: let the decoder drop everything identical to its predecessor and compare
    # what survives with what went in. Counting log lines does not work, the filter writes one per
    # frame whether it drops it or not.
    def _frames(vf: list[str]) -> int:
        r = subprocess.run([ffmpeg, "-i", str(src), *vf, "-f", "null", "-", "-loglevel", "info"],
                           capture_output=True, text=True)
        treffer = re.findall(r"frame=\s*(\d+)", r.stderr or "")
        return int(treffer[-1]) if treffer else 0

    gesamt = max(1, _frames([]))
    behalten = _frames(["-vf", "mpdecimate"])
    doppelt = max(0, gesamt - behalten)
    anteil = 100.0 * doppelt / gesamt
    print(f"  duplicated frames: {doppelt} of about {gesamt} ({anteil:.1f}%)")
    # Only a fault after compositing. Raw material duplicates frames for honest reasons: a shared
    # screen that nobody touches for ten seconds is ten seconds of identical frames, and reporting
    # that as judder would train everyone to ignore the check.
    if args.composited and anteil > args.duplicate_limit:
        befunde.append(f"{anteil:.1f}% duplicated frames, above the {args.duplicate_limit}% limit. "
                       f"The file will still report a constant frame rate; do not fix it by "
                       f"forcing one, the cause is a layer repeating past its end.")

    # Brightness at the joins. Only where a graphic was composited in: a plain cut is meant to
    # change the picture, so measuring a step there would report the cut itself as a fault. The
    # suspect is footage that went through a browser and came back a few percent darker.
    if args.seams:
        naht = [float(x) for x in args.seams.split(",") if x.strip()]
        werte = []
        for t0 in naht[: args.max_seams]:
            hell = []
            for versatz in (-0.12, 0.12):
                r2 = subprocess.run(
                    [ffmpeg, "-ss", f"{max(0.0, t0 + versatz):.3f}", "-i", str(src),
                     "-frames:v", "1", "-vf", "scale=64:36,format=gray",
                     "-f", "rawvideo", "-", "-loglevel", "error"],
                    capture_output=True)
                roh = r2.stdout
                hell.append(sum(roh) / len(roh) if roh else 0.0)
            if all(hell):
                werte.append((abs(hell[1] - hell[0]) / max(hell), t0))
        sprung = [(d, t0) for d, t0 in werte if d > args.luma_limit]
        print(f"  joins measured: {len(werte)}, brightness step beyond "
              f"{100 * args.luma_limit:.0f}%: {len(sprung)}")
        for d, t0 in sprung[:5]:
            befunde.append(f"brightness steps {100 * d:.0f}% at {t0:.2f}s, which is a seam the "
                           f"viewer sees as a flicker on the face")

    if befunde:
        print(f"FAIL: {len(befunde)} finding(s)", file=sys.stderr)
        for b in befunde:
            print(f"  {b}", file=sys.stderr)
        return 1
    print("ok: nothing measurable is wrong. What a checklist cannot judge is composition; "
          "that is a separate pass, done by looking.")
    return 0


def cmd_video_frames(args: argparse.Namespace) -> int:
    """Pull frames so they can be read. The eyes of the review loop, and of picking usable
    moments out of footage that already exists."""
    vault = Path(args.vault).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(vault, "ffmpeg")
    if not ffmpeg:
        print("fail: ffmpeg missing: `tools ensure ffmpeg`.", file=sys.stderr)
        return 1
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    raus = Path(args.out).expanduser() if args.out else _video_job_dir(vault, args.slug) / "frames"
    raus.mkdir(parents=True, exist_ok=True)
    zeiten = [float(x) for x in args.at.split(",")] if args.at else []
    if not zeiten:
        dauer = _video_probe(vault, src).get("duration", 0.0)
        n = max(1, args.count)
        zeiten = [dauer * (i + 0.5) / n for i in range(n)]
    geschrieben = []
    for t in zeiten:
        ziel = raus / f"t{t:09.3f}.jpg".replace(".", "_", 1)
        if _grab_frame(ffmpeg, src, t, ziel, "-q:v", "3"):
            geschrieben.append(ziel)
    if not geschrieben:
        print("fail: no frame could be read", file=sys.stderr)
        return 1
    print(f"ok: {len(geschrieben)} frame(s) in {raus}")
    for g in geschrieben:
        print(f"  {g.name}")
    return 0


def cmd_hook_delete_guard(args: argparse.Namespace) -> int:
    """PreToolUse Bash hook: refuse to delete anything in the vault.

    The AI does not delete. Not with `rm`, not with a find, not by emptying a file, not "just this
    once because it is obviously junk". Everything that goes away goes through `zanmai.py file trash`
    and stays recoverable, and the only thing that ever really deletes is the retention sweep, which
    reaches nothing but what the machine put aside itself.

    The reason is not caution about a particular file. It is that whoever deletes has to be right at
    the moment of deleting, and an AI reading a folder is exactly the wrong thing to bet a life's
    material on. A wrong file in the trash costs a sentence; a wrong file gone costs the file.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") != "Bash":
        return 0
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not command.strip():
        return 0
    treffer = _delete_verb_in(command)
    if not treffer:
        return 0
    if any(hint in command for hint in _DELETE_ALLOWED_HINTS):
        return 0
    # Two different situations reach this point and they need two different answers. Answering both
    # with the vault's trash sent a run that only wanted to clear its own unpacked archive off to
    # `file trash`, which is for the user's material and wrong for a scratch directory. It then went
    # looking for a way around instead of moving its work to where clearing up is allowed.
    print(
        f"delete-guard: refusing this command, it removes things and nothing in Zanmai removes "
        f"things. If this is the user's material, use `zanmai.py file trash --path <path>`, which "
        f"keeps the file and its original path so `zanmai.py file restore` can bring it back. If it "
        f"is your own working material, it does not belong outside the vault: put intermediates in "
        f"`{SCRATCH_DIR}/<task>/`, where clearing up is permitted and the retention sweep clears "
        f"what is left after {RETENTION_DAYS} days. That sweep is the only thing that really "
        f"deletes. Found: {treffer!r}.",
        file=sys.stderr,
    )
    return 2


_PPTX_SAVE_RE = re.compile(r'\.save\(\s*["\']([^"\']+\.pptx)["\']')
_PYTHON_RUN_RE = re.compile(r"(?:^|[\s;&|])python3?\b")
# Preceded by start, a slash, a quote or whitespace: a doing/<slug> path shows up embedded in a
# quoted .save() argument, after a `cd`, or as a bare relative path, not only at a path boundary.
_DOING_SLUG_RE = re.compile(r"(?:^|[/'\"\s])" + re.escape(DOING_DIR) + r"/([^/'\"\s]+)")


# A word that shows up in a bundle name but names nothing on its own. Requiring a link on these
# would fire on every second line. Kept deliberately short: only words that are structural in a
# vault name, never topic words, because a topic word is exactly what should be linked.
def _library_guard_slug(command: str, vault: Path | None = None,
                        cwd: str | None = None) -> str | None:
    """The `doing/<slug>` bundle a Bash command produces into, or None.

    Two ways to know. The command names the path, which is the case a `cd` or an absolute
    argument covers. Or the command says nothing because the working directory is already
    inside the bundle and every path in it is relative: found on a real run 2026-08-25, where
    dropping the `cd` was used as the way past the guard. Reading the working directory closes
    that, and it is the same fact either way.
    """
    match = _DOING_SLUG_RE.search(command)
    if match:
        return match.group(1)
    # The working directory of the shell that runs the command, which the hook payload carries,
    # never the hook process's own. Found 2026-08-26: a hook runs from the project root, so
    # `Path.cwd()` here is always the vault root and the whole branch was dead code. That made the
    # 0.3.5 fix for a dropped `cd` ineffective, and it never showed because nothing tested it from
    # inside a bundle.
    hier = Path(cwd) if cwd else Path.cwd()
    # The root is searched from there too. Searching from the hook process's own directory found
    # the wrong vault, or none, whenever the shell stood somewhere else.
    wurzel = vault if vault is not None else _find_vault_root(hier)
    if wurzel is None:
        return None
    try:
        rel = hier.resolve().relative_to(wurzel.resolve())
    except (ValueError, OSError):
        return None
    teile = rel.parts
    if len(teile) >= 2 and teile[0] == DOING_DIR:
        return teile[1]
    return None


def cmd_hook_library_check_guard(args: argparse.Namespace) -> int:
    """PreToolUse Bash hook: refuse to save a `.pptx` into a `doing/<slug>/` bundle until
    `slide-library.py check <library> --task <slug>` has run at least once for that slug.

    The `powerpoint` skill's library-first order (Match, then Adapt, then Compose, only
    when nothing in the library carries it) lived only as prose, and a live build on
    2026-08-24 went straight to Compose twice without it, which is where that run's whole
    cost went. A rule that has to be repeated in text is the signal that it needs a
    mechanic instead (the lesson from 2026-08-09), and this is that mechanic. It does not
    judge whether Compose was the right tier, only that the library was actually looked
    at before the deliverable was written, which is the step that kept getting skipped.

    Two ways a command can produce a `.pptx`: a literal `.save("x.pptx")` inline in the
    Bash command (a one-off `python3 -c ...`), or a call into a separate script file whose
    own `.save(...)` is invisible here. Found on a real run: a `sales-play-bauen.py`
    invocation slipped past the guard entirely, no `.pptx` literal for the old regex to
    find, because the save lived inside the script, not the command line. Any Python run
    that resolves into a `doing/<slug>/` bundle now binds the same way, whether or not the
    filename is visible, because a script's own behaviour cannot be known without running
    it; the check itself is cheap enough that gating a script that turns out not to touch
    a deck costs one extra command, not a wasted build.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name", "") != "Bash":
        return 0
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not _PPTX_SAVE_RE.search(command) and not _PYTHON_RUN_RE.search(command):
        return 0
    vault = _session_find_vault_root()
    slug = _library_guard_slug(command, vault, cwd=payload.get("cwd"))
    if slug is None:
        return 0
    # Against the vault root, never against the working directory. Found on a real run
    # 2026-08-25: with the shell sitting in the bundle, `Path.cwd()` looked for the marker at
    # `doing/<slug>/zanmai/temp/<slug>/`, which cannot exist, so a run that had done the check
    # was refused anyway and went looking for a way around a guard that was right in principle.
    checked = (vault or Path.cwd()) / SCRATCH_DIR / slug / "library-checked.json"
    if checked.is_file():
        return 0
    print(
        f"library-check-guard: refusing this save. {slug!r} has no record of "
        f"`slide-library.py check <library> --task {slug}` having run. Run that first: it "
        f"prints the brand's own slides, so a matching one can be cloned and filled in "
        f"seconds, the cheap tier this save is skipping past. If nothing in the library "
        f"carries this shape of content, composing from scratch is still the honest "
        f"answer, run the check first anyway; its only job is proving the library was "
        f"looked at before the deck was written.",
        file=sys.stderr,
    )
    return 2


# The label that marks a handover as briefed. Matching on the user's own block rather than on a
# keyword nobody would write by accident is deliberate: the thing being checked for is that the
# user's words were carried over at all, so the check and the content are the same fact.
_BRIEF_MARKER = "What the user said:"


# A tool name that writes into somebody else's system. Matched on the verb, because every MCP server
# names its own operations and no list of servers stays current. Read-only verbs are deliberately not
# here: fetching a page, searching, listing are how questions get answered and must stay free.
# What a name starts with when it only looks. Checked before the write verbs, never after.
_READ_VERBS = ("get", "list", "search", "read", "fetch", "view", "download", "find", "query",
               "describe", "show", "check", "count", "resolve")
_OUTWARD_VERBS = ("create", "update", "delete", "publish", "post", "send", "add", "upload", "write",
                  "edit", "append", "move", "archive", "comment", "attach", "remove", "set", "copy",
                  "restrict", "label", "assign", "transition", "merge", "push")


def cmd_hook_outward_guard(args: argparse.Namespace) -> int:
    """PreToolUse on MCP tools: make a write into somebody else's system a decision the user takes.

    Writing into the vault is reversible and private. Writing into Confluence, a mailbox, a ticket
    system or a repository is neither: colleagues see it, and an undo does not reach them. Hard Rule 3
    says such a write waits for an explicit yes in the same message. That was prose, and prose at this
    point does not hold: on 2026-08-26 a session was asked in the chat where information was missing,
    built the answer as an XHTML file, published it to Confluence, and then offered to delete it again
    if that was not wanted. The offer came after the page existed.

    So the decision is handed to the host, which asks the user. Nothing is refused: a publish the user
    wants is one confirmation away, and a publish nobody asked for cannot happen silently. Read-only
    calls pass untouched, because a question that cannot be looked up is a question that cannot be
    answered.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    name = str(payload.get("tool_name") or "")
    if not name.startswith("mcp__"):
        return 0
    teile = name.lower().replace("-", "_").split("__")
    operation = teile[-1] if teile else ""
    # A reading verb decides first. `get_comments` carries "comment" and is a read; matching the
    # write verbs anywhere in the name turned it into a write, which would have put a confirmation
    # in front of every lookup and taught everyone to click it away.
    wort = operation.split("_")
    if wort and wort[0] in _READ_VERBS:
        return 0
    if not any(verb in wort for verb in _OUTWARD_VERBS):
        return 0
    dienst = teile[1] if len(teile) > 2 else "an external system"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": (
            f"outward-guard: this writes into {dienst}, outside the vault. Other people see it and an "
            f"undo does not reach them, so it waits for the user rather than happening on the way "
            f"past (Hard Rule 3). If they asked for it, this is one confirmation. If they asked a "
            f"question, answer it in the chat instead."),
    }}, ensure_ascii=False))
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
    subagent = str(tool_input.get("subagent_type") or "agent")
    prompt = str(tool_input.get("prompt") or "")
    hintergrund_falsch = tool_input.get("run_in_background") is False
    brief_fehlt = _BRIEF_MARKER.lower() not in prompt.lower()
    if not hintergrund_falsch and not brief_fehlt:
        return 0
    # Corrected, not refused. Refusing worked, and the user watched it work: a red error on their
    # screen at nearly every dispatch, followed by a retry that spent a turn saying the same thing
    # twice. A guard that fires as routine is a rule sitting in the wrong place. The host lets a
    # PreToolUse hook hand back an amended input, so the flag is simply put right on the way
    # through, and neither the user nor the run ever sees the wrong version.
    if brief_fehlt:
        # Refused, not corrected, and this is the one place in this hook where that is right. The
        # background flag is a fact about the call and can simply be put right on the way through.
        # A brief is content: the two blocks cannot be written by a hook, because only the turn that
        # just read the user's words knows what they said. Handing the dispatch back is what puts
        # the interview where it belongs, in front of the send-off, with the user still there. The
        # expert cannot hold it: it runs in the background and has nobody to ask.
        print(
            f"dispatch-guard: refusing this {subagent} dispatch, its handover is missing the two "
            f"labelled blocks. What this checks is formal, and only that: the words "
            f"'{_BRIEF_MARKER}' have to appear. A handover can be rich in detail and still be "
            f"refused here, which is what happened the first time this fired in the field. "
            f"The expert never met the user, and it runs in the background where it cannot ask, so "
            f"whatever is missing here gets invented and comes back looking like the expert's "
            f"fault. Put two labelled blocks at the top of the prompt. '{_BRIEF_MARKER}': their "
            f"words, quoted or close to it, nothing added; a file or link is named as what came "
            f"with the ask, not transcribed as content. 'What I concluded:' where it lands, which "
            f"format, how big the job is, form and destination only, never new subject matter. "
            f"Then read this expert's own contract for what it needs, and fill the gaps: a fact "
            f"that sits in the vault or on disk you go and find, that is your job. What is "
            f"load-bearing, missing, and only the user can know, you ask now, in one numbered "
            f"round with a recommended answer each so they can wave it through, and you wait. See "
            f"`{SYSTEM_MATERIAL_DIR}/skills/brief/SKILL.md`.",
            file=sys.stderr)
        return 2
    korrigiert = dict(tool_input)
    korrigiert["run_in_background"] = True
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": (
            f"dispatch-guard: this {subagent} dispatch asked to run synchronously, which would "
            "hold the turn until the job returns and cut the user off meanwhile. Switched to the "
            "background; say in one line what is running and relay the return when it lands."),
        "updatedInput": korrigiert,
    }}, ensure_ascii=False))
    return 0







# Session-start hook helpers (consolidated from former session-start.py).

_SESSION_DAILY_WINDOW_DAYS = 7
_SESSION_WEEKLY_WINDOW_DAYS = 28
_SESSION_MONTHLY_WINDOW_DAYS = 92

# What the session-start hook may print. The host caps hook output at 10,000 characters and
# replaces anything longer with a 2 KB preview plus a path to a file, without telling the model
# that it is looking at a fragment. The cap is undocumented in the hooks reference and the two
# reports about it (anthropics/claude-code #44086, #70460) are closed as not planned, so this is
# ours to stay under. The budget sits below the cap rather than at it: what the hook prints grows
# with the vault, and the margin is what keeps a busy vault from silently crossing the line.
_HOOK_OUTPUT_BUDGET = 9000


def _session_find_vault_root() -> Path | None:
    """Walk upward from cwd to find a folder that has zanmai/user.md."""
    cwd = Path.cwd().resolve()
    for path in [cwd] + list(cwd.parents):
        if (path / SYSTEM_DIR / "user.md").exists():
            return path
    return None


def _session_parse_frontmatter(text: str) -> dict[str, str]:
    """Tiny YAML frontmatter parser, flat string values only. Empty dict when
    no `---`-fenced block is found. Shares one implementation with
    `_hook_extract_frontmatter`."""
    return _hook_extract_frontmatter(text) or {}


def _session_read_marker(vault: Path) -> datetime:
    """Read .last-session-end. Fall back to three days ago."""
    marker = vault / MEMORY_DIR / ".last-session-end"
    if marker.exists():
        text = marker.read_text(encoding="utf-8").strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(days=3)


def _session_load_index(vault: Path) -> dict | None:
    idx_path = vault / MEMORY_DIR / "vault-index.json"
    if not idx_path.exists():
        return None
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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


_SESSION_JOURNAL_WINDOWS = {
    DAILY_DIR: _SESSION_DAILY_WINDOW_DAYS,
    WEEKLY_DIR: _SESSION_WEEKLY_WINDOW_DAYS,
    MONTHLY_DIR: _SESSION_MONTHLY_WINDOW_DAYS,
}


def _session_collect_recent_journal(index: dict, vault: Path) -> list[dict]:
    """Journal entries recent enough to matter for the greet, each kind with its own window."""
    now = datetime.now(timezone.utc)
    files = index.get("files", [])
    matches: list[dict] = []
    for entry in files:
        path = entry.get("path", "")
        root = next((r for r in _SESSION_JOURNAL_WINDOWS if path.startswith(f"{r}/")), None)
        if root is None:
            continue
        cutoff = now - timedelta(days=_SESSION_JOURNAL_WINDOWS[root])
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
    for kind in BUNDLE_FOLDERS:
        kind_dir = vault / kind
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
    for folder in CONTACT_FOLDERS:
        d = vault / folder
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file() and f.suffix == ".md":
                    ents[f.stem] = _human_label_for_slug(f.stem)
    for kind in BUNDLE_FOLDERS:
        d = vault / kind
        if d.is_dir():
            for b in d.iterdir():
                if b.is_dir():
                    ents[b.name] = _human_label_for_slug(b.name)
    return ents


def _session_journal_link_candidates(notes: list[dict], vault: Path, top_n: int = 5) -> list[dict]:
    """Known entities mentioned in recent periodic notes as plain text but not
    yet wikilinked there, ranked by recurrence (how many recent notes mention
    each unlinked). Conservative link proposals, capture becoming connected over
    time, without auto-linking. Reads the recent note bodies directly, so it does
    not depend on index freshness."""
    prefixes = tuple(f"{r}/" for r in _SESSION_JOURNAL_WINDOWS)
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
    it catches edits the user made in their editor, which set no marker. An
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
    all static state (`zanmai/user.md`, last-session-end
    marker, index entries) and prints a compact briefing
    that Claude Code injects into the session context as a system-reminder."""
    vault = _session_find_vault_root()
    if vault is None:
        import os
        env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        if env_dir:
            candidate = Path(env_dir)
            if (candidate / SYSTEM_DIR / "user.md").exists():
                vault = candidate
    if vault is None:
        try:
            payload = json.loads(sys.stdin.read())
            cwd_hint = payload.get("cwd") or payload.get("project_dir")
            if cwd_hint and (Path(cwd_hint) / SYSTEM_DIR / "user.md").exists():
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
                is_zb = (cand / SYSTEM_MATERIAL_DIR / "manifest.yaml").exists()
                fresh = not (cand / SYSTEM_DIR / "user.md").exists()
            except OSError:
                continue
            if is_zb and fresh:
                print(
                    "Zanmai: this vault is not set up yet, there is no user profile. "
                    "Before any greeting or answer, read zanmai/system/skills/setup/SKILL.md "
                    "and run its workflow now. Do not respond generically."
                )
                return 0
        return 0

    user_md = vault / SYSTEM_DIR / "user.md"
    try:
        user_text = user_md.read_text(encoding="utf-8")
    except OSError:
        print("Zanmai session-start: zanmai/user.md unreadable. Run `setup` skill if vault is fresh.")
        return 0

    # Prune the transient workspace so it never becomes a data graveyard, but
    # keep recent scratch so unfinished cross-session work is not lost ("done for
    # today, resume tomorrow"). Only entries untouched for over 7 days are removed;
    # anything modified within the window stays. Finished pieces live on the desk.
    #
    # A workshop that declares itself open is never pruned, whatever its age. Age is
    # a guess about whether something still matters; `state: open` in the workshop's
    # own status file is a statement. An expert parked on a decision the user has not
    # taken yet can sit for weeks, and deleting the one folder that holds where the
    # work stood is how a run loses what it cannot write down twice.
    import shutil
    import time
    work_dir = vault / SCRATCH_DIR
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
    # No end-of-session marker means the user has never closed a session here, so this is the first
    # time they are in the vault after setup. It is the one moment where an offer to explain the
    # place is welcome rather than noise.
    first_session = not (vault / MEMORY_DIR / ".last-session-end").exists()

    marker = _session_read_marker(vault)
    marker_iso = marker.astimezone(timezone.utc).isoformat(timespec="minutes")

    lines: list[str] = []
    lines.append("Zanmai session briefing")
    lines.append(f"- Address the user as **{preferred}** (from preferred_address / first_name in zanmai/user.md).")

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
    host_marker = vault / RUNTIME_DIR / "host-config-version"
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
            f"- {len(waiting)} voice note(s) waiting in {IMPORT_DIR}/"
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
        lines.append(f"- Owner contact: `{PEOPLE_DIR}/{owner_contact}.md` (read for persistent user notes).")
    lines.append(f"- Language preference: {language}.")
    lines.append(f"- Last session ended: {marker_iso}.")
    lines.append(f"- auto_snapshots: {str(auto_snapshots).lower()}. A snapshot is taken before something that could lose the user's own work, never because a session began or a version changed. When false, skip every automatic snapshot, the user has their own backup approach.")
    for note in _sweep_retention(vault):
        lines.append(f"- Housekeeping: {note}")

    stray = _unexpected_root_entries(vault)
    if stray:
        lines.append(
            f"- {len(stray)} entr(y/ies) at the vault root do not belong to the folder architecture: "
            f"{', '.join(stray[:5])}"
            + (" …" if len(stray) > 5 else "")
            + ". This did not come from a Zanmai write. Name it once, in one line, and offer to move "
              "its contents into the right theme."
        )

    lines.append(f"- The journal lives under `{JOURNAL_DIR}/`, one bundle per period, four kinds (daily, weekly, monthly, yearly). It is always there; there is no switch and nothing to configure.")
    lines.append("- Journal operations go through `zanmai.py journal` and the `journal` skill. The AI never writes into an entry on its own initiative, only on direct user instruction. The one exception is the period rollup, which appends and never overwrites.")

    faellig = _journal_rollups_due(vault, datetime.now())
    if faellig:
        lines.append("- A rollup is due. Write the summary in the user's own words from the entries below, then `zanmai.py journal rollup`. It refuses a second one for the same period, so it cannot double up:")
        lines.extend(f"  {zeile}" for zeile in faellig)

    wartend = _import_pending(vault)
    if wartend:
        arten: dict[str, int] = {}
        for f in wartend:
            art, _weg = _import_route(f)
            arten[art] = arten.get(art, 0) + 1
        pretty = ", ".join(f"{n} {a}" for a, n in sorted(arten.items()))
        lines.append(f"- {len(wartend)} file(s) waiting in `{IMPORT_DIR}/` ({pretty}). Run `zanmai.py import scan` for the list and the route per file. Read all of them before processing any, the later one can withdraw the earlier. A recording is read out without asking; everything else asks first.")

    if first_session:
        lines.append("- **First session after setup.** Before anything else, ask the user in their writing language whether they would like a short tour: what the folders are for, and what they can actually do with Zanmai. One question, two sentences at most, and a no is a fine answer. On a yes, answer from `zanmai/system/docs/index.md` and the pages it points at, shaped for this user, never a page pasted back at them.")

    index = _session_load_index(vault)
    stale_marker = vault / MEMORY_DIR / ".index-stale"
    if stale_marker.exists() or _session_index_stale(vault, index):
        _session_refresh_index(vault)
        index = _session_load_index(vault)
    if index is None:
        lines.append("- Pattern index not built yet. Run `zanmai.py index rebuild` plus `zanmai.py index patterns` before theme queries.")
    else:
        notes = _session_collect_recent_journal(index, vault)
        window_desc = f"last {_SESSION_DAILY_WINDOW_DAYS} days Daily, last {_SESSION_WEEKLY_WINDOW_DAYS // 7} weeks Weekly, last {_SESSION_MONTHLY_WINDOW_DAYS // 30} months Monthly"
        if not notes:
            lines.append(f"- No Daily, Weekly or Monthly notes in the recent window ({window_desc}). The greet still runs the same walk over what is open, from `zanmai/memory/briefing.md` and the work objects; with fewer sources it simply finds fewer items, and it names the ones it finds.")
        else:
            daily = [n for n in notes if n["path"].startswith(f"{DAILY_DIR}/")]
            weekly = [n for n in notes if n["path"].startswith(f"{WEEKLY_DIR}/")]
            monthly = [n for n in notes if n["path"].startswith(f"{MONTHLY_DIR}/")]
            lines.append(f"- Recent window ({window_desc}): {len(daily)} Daily, {len(weekly)} Weekly, {len(monthly)} Monthly note(s).")
            for n in notes[-5:]:
                lines.append(f"  * {n['path']}")
            candidates = _session_journal_link_candidates(notes, vault)
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
                    f"Bundles for these already exist under `<kind>/<slug>/`."
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

    stale = vault / MEMORY_DIR / ".index-stale"
    if stale.exists():
        lines.append("- `zanmai/memory/.index-stale` marker is set. Refresh `zanmai.py index rebuild` + `zanmai.py index patterns` before any theme query.")

    # The briefing is named, never pasted. Embedding it put the payload over the host's
    # hook-output limit, and everything past that limit is replaced by a 2 KB preview the
    # model cannot tell is incomplete. Measured on 79 real starts in a live vault: every
    # single one exceeded the limit, the greet list and the greet shape sat past it, and
    # the greet was composed from the briefing's first two kilobytes instead. A path plus
    # one read is cheaper than a greet built on a fragment.
    briefing_path = vault / MEMORY_DIR / "briefing.md"
    if briefing_path.exists():
        try:
            briefing_size = briefing_path.stat().st_size
        except OSError:
            briefing_size = 0
        lines.append("")
        lines.append("---")
        lines.append(
            f"- The pre-built briefing is at `{MEMORY_DIR}/briefing.md` ({briefing_size} bytes): what is due, "
            "what happened since the last close, current state, open items. **Read that file before the first "
            "reply.** It does not replace the three CLAUDE.md session-start reads (`zanmai/user.md`, the "
            "owner-contact body, `.last-session-end`), which run whether the turn opens with a greet or a "
            "direct request."
        )
    else:
        lines.append("- `zanmai/memory/briefing.md` does not exist yet. Run `zanmai.py memory briefing` once to build the first version.")

    # The greet list itself, after the briefing and before the greet shape, because it is the answer
    # the shape is about. Built fresh here rather than read out of the briefing: the briefing is as
    # old as the last close-session, and "today" computed against a stale build is simply wrong.
    if not first_session:
        try:
            greet_lines = _greet_block(vault)
        except Exception as fehler:  # a broken greet list must not cost the session its start
            greet_lines = [f"- Greet list unavailable ({fehler.__class__.__name__}). "
                           f"Compose the greet from the briefing above and say so in one line."]
        lines.append("")
        lines.append("---")
        lines.extend(greet_lines)

    # The greet shape is named, never pasted. A hand-carried copy of it is what pushed the
    # payload past the host's hook-output limit, and past that limit the model sees a 2 KB
    # preview with no sign that anything is missing. One file decides the shape; this hook
    # points at it and the reply reads it.
    lines.append("")
    lines.append("---")
    greeting_rel = f"{SYSTEM_MATERIAL_DIR}/skills/greeting/SKILL.md"
    if (vault / greeting_rel).exists():
        lines.append(
            f"- **Read `{greeting_rel}` and follow it before the first user-facing sentence.** It "
            f"carries the greet shape, the mandatory reads and what a greet must never contain. "
            f"Address the user as **{preferred}** where it applies."
        )
    else:
        lines.append(
            f"- `{greeting_rel}` is missing. Say so in one line, then greet from "
            f"`{MEMORY_DIR}/briefing.md` and the greet list above: address, the open items grouped "
            f"by time, nearest first, six lines at most, no ids and no paths."
        )

    ausgabe = "\n".join(lines)
    # Size guard. The host replaces hook output over its limit with a 2 KB preview plus a file
    # path, and a preview is worse than nothing: it carries enough to compose a plausible reply
    # from and no sign that the rest was dropped. Measured in a live vault on 2026-08-26, every
    # one of 79 recorded starts was over, so the greet had never once seen its own instructions.
    # Kept well under the limit rather than at it: what this hook prints grows with the vault.
    if len(ausgabe) > _HOOK_OUTPUT_BUDGET:
        kopf = [l for l in lines if l.startswith("Zanmai session briefing")]
        rest = [l for l in lines if l not in kopf]
        gekuerzt = kopf + [
            f"- **This briefing was cut**: it came to {len(ausgabe)} characters against a budget of "
            f"{_HOOK_OUTPUT_BUDGET}, and the host silently replaces anything over its own limit with "
            f"a 2 KB preview. The lines below are the ones that decide the first reply; the rest is "
            f"in `{MEMORY_DIR}/briefing.md`. Say in one line that the session start was trimmed.",
        ]
        for zeile in rest:
            if len("\n".join(gekuerzt)) + len(zeile) + 1 > _HOOK_OUTPUT_BUDGET:
                break
            gekuerzt.append(zeile)
        ausgabe = "\n".join(gekuerzt)

    print(ausgabe)
    return 0


def cmd_hook_index_consistency(args: argparse.Namespace) -> int:
    """PostToolUse Write|Edit hook: warn (exit 2 non-blocking stderr) when a
    bundle file is written without being referenced in the bundle's INDEX.md.
    Also touches `zanmai/memory/.index-stale` to flag the pattern index for
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
    # Mark the pattern index stale. The vault root is whatever sits above the bundle root, and the
    # first match is the one that gives it: a path may well repeat a folder name further down
    # (`knowledge/knowledge-management/`), and the later occurrence would put the marker inside the
    # bundle instead of in the vault.
    norm = file_path.replace("\\", "/")
    found = [i for i in (norm.find(f"/{r}/") for r in BUNDLE_FOLDERS) if i != -1]
    if found:
        try:
            (Path(norm[:min(found)]) / MEMORY_DIR / ".index-stale").touch(exist_ok=True)
        except OSError:
            pass
    rel, _ = located
    parts = rel.split("/")
    # `<kind>/<slug>/<file>`: three segments now that the kind folder is a vault root.
    if len(parts) < 3:
        return 0
    # `parts` is `<kind>/<slug>/.../<file>`: for a file sitting directly in the bundle root that is
    # three segments and the immediate parent is the bundle dir. A file nested under a working
    # subfolder (`arbeit/recherche/…`) adds segments without adding a bundle, so the bundle dir is
    # found by walking up to the slug level, not by taking the file's immediate parent: otherwise
    # every subfolder without its own INDEX.md reports the bundle-level one as missing.
    bundle_dir = Path(file_path).parents[len(parts) - 3]
    file_name = parts[-1]
    bundle_slug = parts[1]
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
    # A wikilink is matched by basename regardless of case (Hard Rule 1); `STAND.md` linked as
    # `[[stand]]` is the same reference, not a miss.
    if any(re.search(p, index_text, re.IGNORECASE) for p in patterns):
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


_VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")


def _burn_visible_label_video(src: Path, text: str, font_path: str | None, out: Path) -> str:
    """The same label on moving pictures, and it has to be built differently.

    A still takes a discreet pill at low opacity. On video that frays: the mark has to survive
    re-encoding by whatever platform it is uploaded to, and a semi-transparent one smears. So it
    is drawn opaque, a little larger, and held for the whole clip rather than appearing somewhere.
    Drawn as an image and composited, because whether this ffmpeg can draw text at all depends on
    how it was built, and the common ones cannot.
    """
    from PIL import Image, ImageDraw, ImageFont
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg missing: a video label cannot be drawn")
    masse = subprocess.run(
        [shutil.which("ffprobe") or ffmpeg, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True)
    try:
        w, h = (int(x) for x in (masse.stdout or "").strip().split(",")[:2])
    except ValueError:
        w, h = 1920, 1080

    font_px = max(_LABEL_MIN_PX, round(h * _LABEL_FONT_FRAC * 1.4))
    pad_y, pad_x = round(h * _LABEL_PAD_Y_FRAC), round(h * _LABEL_PAD_X_FRAC)
    margin = round(h * _LABEL_MARGIN_FRAC)
    font, font_name = None, ""
    for kandidat in ([font_path] if font_path else []) + list(_SANS_FONT_CANDIDATES):
        try:
            font = ImageFont.truetype(kandidat, font_px)
            font_name = Path(kandidat).name
            break
        except (OSError, ValueError):
            continue
    if font is None:
        font, font_name = ImageFont.load_default(), "PIL-default(bitmap)"

    schicht = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    zeichne = ImageDraw.Draw(schicht)
    l, o, r, u = zeichne.textbbox((0, 0), text, font=font)
    pw, ph = (r - l) + 2 * pad_x, (u - o) + 2 * pad_y
    x1, y1 = w - margin - pw, h - margin - ph
    zeichne.rounded_rectangle([x1, y1, x1 + pw, y1 + ph], radius=ph // 2, fill=(0, 0, 0, 255))
    zeichne.text((x1 + pad_x - l, y1 + pad_y - o), text, font=font, fill=(255, 255, 255, 255))
    schicht_datei = out.with_name(out.stem + ".label.png")
    schicht.save(schicht_datei)

    ergebnis = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-loop", "1", "-i", str(schicht_datei),
         "-filter_complex", "[0:v][1:v]overlay=0:0:eof_action=pass[v]",
         "-map", "[v]", "-map", "0:a?", "-shortest",
         "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(out), "-loglevel", "error"],
        capture_output=True, text=True)
    schicht_datei.unlink(missing_ok=True)
    if ergebnis.returncode != 0:
        raise RuntimeError((ergebnis.stderr or "")[-300:])
    return font_name


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


def _composite_eu_icon(src: Path, out: Path, ai_class: str, icons_dir: Path) -> dict:
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
    icon_path = icons_dir / f"{ai_class}-{variant}.png"
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
        icons_dir = (vault / SYSTEM_MATERIAL_DIR / "icons" / "eu-ai") if vault else Path(".")
        try:
            info = _composite_eu_icon(src, out, args.eu_icon, icons_dir)
            status["visible_label"] = info
            reencoded = bool(info.get("applied"))
        except ImportError:
            status["visible_label"] = {"applied": False, "error": "Pillow not available in this runtime"}
        except Exception as e:
            status["visible_label"] = {"applied": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    elif args.visible_label:
        try:
            zeichner = (_burn_visible_label_video
                        if src.suffix.lower() in _VIDEO_SUFFIXES else _burn_visible_label)
            font_used = zeichner(src, args.visible_label, args.font, out)
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
    """The tool register ships alongside this script under zanmai/system/."""
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


# id, app name for the macOS scan below. Terminal itself is not in this list:
# it ships with every macOS install, so it is always offered without a
# filesystem check, and it is the only one launched through a `.command` file
# rather than `-e`, because it runs the file as a full login shell and the
# others (tested: Ghostty) do not, they get PATH only through an explicit
# absolute binary path.
_MAC_TERMINAL_CANDIDATES = [
    ("ghostty", "Ghostty"),
    ("iterm", "iTerm"),
    ("warp", "Warp"),
    ("alacritty", "Alacritty"),
    ("kitty", "kitty"),
    ("wezterm", "WezTerm"),
    ("hyper", "Hyper"),
]


def _detect_terminals(osname: str) -> list[dict]:
    """Terminal apps this machine can start a vault session in.

    macOS always offers Terminal (system app) plus whatever else this scan
    finds under /Applications, so the caller can turn the list into a choice.
    Windows offers exactly one, no choice: Windows Terminal if `wt` resolves,
    else the always-present Command Prompt. Kept to one option deliberately,
    Windows terminal alternatives are not verified the way Terminal and
    Ghostty are on macOS.
    """
    if osname == "windows":
        if shutil.which("wt"):
            return [{"id": "wt", "name": "Windows Terminal"}]
        return [{"id": "cmd", "name": "Command Prompt"}]
    if osname != "macos":
        return [{"id": "generic", "name": "the default terminal"}]
    found = [{"id": "terminal", "name": "Terminal"}]
    for tid, name in _MAC_TERMINAL_CANDIDATES:
        if (Path("/Applications") / f"{name}.app").exists():
            found.append({"id": tid, "name": name})
    return found


_MACOS_LAUNCHER_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>{name}</string>
  <key>CFBundleDisplayName</key><string>{name}</string>
  <key>CFBundleIdentifier</key><string>{bundle_id}</string>
  <key>CFBundleVersion</key><string>0.1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>icon.icns</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""


def _launcher_create_macos(vault: Path, name: str, terminal_id: str, icon_png: Path, claude_bin: str) -> int:
    for tool in ("sips", "iconutil"):
        if not shutil.which(tool):
            print(f"error: {tool} not found, cannot build a macOS icon", file=sys.stderr)
            return 1

    app_dir = Path("/Applications") / f"{name}.app"
    if app_dir.exists():
        print(f"error: {app_dir} already exists, pick a different name or remove it first", file=sys.stderr)
        return 1

    import tempfile

    with tempfile.TemporaryDirectory() as work:
        work_path = Path(work)
        iconset = work_path / "icon.iconset"
        iconset.mkdir()
        for sz in (16, 32, 128, 256, 512):
            subprocess.run(["sips", "-z", str(sz), str(sz), str(icon_png),
                             "--out", str(iconset / f"icon_{sz}x{sz}.png")],
                            check=True, capture_output=True)
            dbl = sz * 2
            subprocess.run(["sips", "-z", str(dbl), str(dbl), str(icon_png),
                             "--out", str(iconset / f"icon_{sz}x{sz}@2x.png")],
                            check=True, capture_output=True)
        icns = work_path / "icon.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
                        check=True, capture_output=True)

        macos_dir = app_dir / "Contents" / "MacOS"
        resources_dir = app_dir / "Contents" / "Resources"
        macos_dir.mkdir(parents=True)
        resources_dir.mkdir(parents=True)
        shutil.copy2(icns, resources_dir / "icon.icns")

        bundle_id = "dev.zanmai.launcher." + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        (app_dir / "Contents" / "Info.plist").write_text(
            _MACOS_LAUNCHER_PLIST.format(name=name, bundle_id=bundle_id), encoding="utf-8")

        vault_escaped = str(vault).replace("'", "'\\''")
        if terminal_id == "terminal":
            start_cmd = resources_dir / "start.command"
            start_cmd.write_text(f"#!/bin/bash\ncd '{vault_escaped}'\nexec '{claude_bin}'\n", encoding="utf-8")
            start_cmd.chmod(0o755)
            launch_body = (
                "#!/bin/bash\n"
                'DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"\n'
                'exec open -a Terminal "$DIR/start.command"\n'
            )
        else:
            app_name = next((n for tid, n in _MAC_TERMINAL_CANDIDATES if tid == terminal_id), terminal_id)
            inner = f"cd '{vault_escaped}' && exec '{claude_bin}'"
            inner_escaped = inner.replace('"', '\\"')
            launch_body = f"#!/bin/bash\nopen -na '{app_name}' --args -e /bin/zsh -c \"{inner_escaped}\"\n"
        (macos_dir / "launch").write_text(launch_body, encoding="utf-8")
        (macos_dir / "launch").chmod(0o755)

    subprocess.run(["xattr", "-cr", str(app_dir)], capture_output=True)
    print(f"ok: {app_dir}")
    return 0


def _launcher_create_windows(vault: Path, name: str, terminal_id: str, icon_ico: Path, claude_bin: str) -> int:
    """Designed against documented PowerShell/WScript.Shell behaviour, never run on
    real Windows hardware, same status as the rest of this project's Windows path.
    """
    desktop = Path.home() / "Desktop"
    lnk_path = desktop / f"{name}.lnk"
    if terminal_id == "wt":
        target = "wt.exe"
        arguments = f'-d "{vault}" {claude_bin}'
    else:
        target = "cmd.exe"
        arguments = f'/k "cd /d ""{vault}"" && {claude_bin}"'

    ps_script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath = '{target}';"
        "$s.Arguments = '{args}';"
        "$s.IconLocation = '{icon}';"
        "$s.WorkingDirectory = '{cwd}';"
        "$s.Save()"
    ).format(lnk=str(lnk_path), target=target, args=arguments.replace("'", "''"),
             icon=str(icon_ico), cwd=str(vault))

    result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script],
                             capture_output=True, text=True)
    if result.returncode != 0:
        print(f"error: PowerShell could not build the shortcut: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"ok: {lnk_path}")
    return 0


def cmd_launcher_detect_terminals(args: argparse.Namespace) -> int:
    for t in _detect_terminals(_current_os()):
        print(f"{t['id']}\t{t['name']}")
    return 0


def cmd_launcher_create(args: argparse.Namespace) -> int:
    """Build a double-clickable starter for this vault: an .app on macOS, a .lnk
    on Windows. Deliberately its own command, independent of `setup init`, so it
    can be asked for anytime in a session, not only once during first install.
    """
    vault = Path(args.vault_root).resolve()
    if not (vault / SYSTEM_MATERIAL_DIR / "manifest.yaml").exists():
        print(f"error: no Zanmai system folder at {vault}", file=sys.stderr)
        return 1
    name = args.name.strip()
    if not name:
        print("error: --name must not be empty", file=sys.stderr)
        return 1

    osname = _current_os()
    claude_bin = shutil.which("claude") or "claude"

    if osname == "macos":
        icon_png = vault / SYSTEM_MATERIAL_DIR / "icons" / "app-icon.png"
        if not icon_png.exists():
            print(f"error: missing shipped icon at {icon_png}", file=sys.stderr)
            return 1
        return _launcher_create_macos(vault, name, args.terminal, icon_png, claude_bin)
    if osname == "windows":
        icon_ico = vault / SYSTEM_MATERIAL_DIR / "icons" / "app-icon.ico"
        if not icon_ico.exists():
            print(f"error: missing shipped icon at {icon_ico}", file=sys.stderr)
            return 1
        return _launcher_create_windows(vault, name, args.terminal, icon_ico, claude_bin)
    print("error: no launcher mechanic for this platform yet", file=sys.stderr)
    return 1


def _runtime_venv_dir(vault: Path) -> Path:
    return vault / RUNTIME_DIR / "venv"


def _runtime_venv_python(vault: Path) -> Path | None:
    d = _runtime_venv_dir(vault)
    for rel in ("bin/python", "Scripts/python.exe"):
        p = d / rel
        if p.is_file():
            return p
    return None


def _user_python_cmd(vault: Path) -> str:
    """The Python invocation recorded at setup (user.md python_cmd); default python3."""
    um = vault / SYSTEM_DIR / "user.md"
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
        own = vault / ((spec.get("provision") or {}).get("into") or f"{RUNTIME_DIR}/bin") / name
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
        work = vault / SCRATCH_DIR / "voice"
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
    target_dir = vault / prov.get("into", f"{RUNTIME_DIR}/bin")
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
        out_pdf = vault / RUNTIME_DIR / f"{tool_id}-canary.pdf"
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


def cmd_tools_ensure_all(args: argparse.Namespace) -> int:
    """Everything this vault could need, in one pass, offered at setup instead of drop by drop.

    Without `--yes` it only reports, and that report is the question the user answers. Nothing that
    costs money, needs an account or wants a decision is included: those are listed as theirs to
    do. The point is that a user should not meet a missing prerequisite for the first time in the
    middle of a job that is already running.
    """
    import io
    import contextlib
    vault = Path(args.vault).resolve()
    tools = (_load_register().get("tools") or {})
    osname = _current_os()

    da, selbst, automatisch, extern = [], [], [], []
    for tid, spec in sorted(tools.items()):
        if spec.get("kind") == "mcp":
            extern.append(tid)
            continue
        if _detect_tool(vault, tid, spec, osname).get("present") is True:
            da.append(tid)
            continue
        method = (spec.get("provision") or {}).get("method")
        ziel = automatisch if method in ("venv-pip", "node-package", "file-fetch", "binary-fetch") else selbst
        ziel.append((tid, spec, method))

    print(f"{len(da)} of {len(tools)} tool(s) already here.")
    if automatisch:
        print(f"\nZanmai can fetch these itself ({len(automatisch)}):")
        for tid, spec, _m in automatisch:
            print(f"  {tid}: {(spec.get('purpose') or '').split('.')[0]}.")
    if selbst:
        print(f"\nThese are yours to install, each with the one command that does it ({len(selbst)}):")
        for tid, spec, _m in selbst:
            hint = ((spec.get("os") or {}).get(osname) or {}).get("install_hint") or {}
            print(f"  {tid}: {hint.get('text') or (spec.get('purpose') or '').split('.')[0]}")
    if extern:
        print(f"\nConfigured at the host, not here: {', '.join(extern)}")
    if not automatisch:
        print("\nNothing left for Zanmai to fetch.")
        return 0
    if not args.yes:
        print("\nSay the word and Zanmai fetches the first group; the second stays yours.")
        return 0

    print("")
    fehler = 0
    for tid, _spec, _m in automatisch:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_tools_ensure(argparse.Namespace(vault=str(vault), id=tid))
        try:
            ergebnis = json.loads(buf.getvalue())
        except json.JSONDecodeError:
            ergebnis = {"state": "unreadable"}
        zustand = ergebnis.get("state", "?")
        print(f"  {tid}: {zustand}" + (f" ({ergebnis.get('detail','')[:80]})"
                                       if zustand == "WARNING" else ""))
        fehler += 1 if rc != 0 else 0
    print(f"\nok: {len(automatisch) - fehler} fetched, {fehler} did not work out")
    return 0


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
    if method == "node-package":
        # Installed into the vault's own runtime tree, never globally: a global install needs
        # rights this script must not assume, and it would leak one vault's pinned version into
        # every other project on the machine. Detection already looks in the runtime tree first
        # (`provision.into`), so the copy is found right after it lands.
        npm = shutil.which("npm")
        if not npm:
            print(json.dumps({"id": args.id, "state": "needs-user", "tier": tier,
                              "hint": "Node 22 or newer, which brings npm. macOS: brew install node. "
                                      "Windows: winget install OpenJS.NodeJS. Linux: your package manager.",
                              "guide": "zanmai/system/docs/install/node.md"},
                             ensure_ascii=False, indent=2))
            return 0
        wurzel = vault / (prov.get("root") or f"{RUNTIME_DIR}/node")
        wurzel.mkdir(parents=True, exist_ok=True)
        pin = prov.get("version_pin")
        paket = prov.get("package") or args.id
        spez = f"{paket}@{pin}" if pin else paket
        try:
            r = subprocess.run([npm, "install", "--prefix", str(wurzel), "--no-fund",
                                "--no-audit", "--loglevel", "error", spez],
                               capture_output=True, text=True, timeout=900)
        except Exception as e:
            print(json.dumps({"id": args.id, "state": "WARNING", "detail": f"{type(e).__name__}: {e}"}))
            return 1
        if r.returncode != 0:
            print(json.dumps({"id": args.id, "state": "WARNING",
                              "detail": (r.stderr or r.stdout).strip()[:300]}, ensure_ascii=False))
            return 1
        ok = _detect_tool(vault, args.id, spec, osname)
        print(json.dumps({"id": args.id, "state": "installed" if ok.get("present") else "WARNING",
                          "package": spez, "root": str(wurzel.relative_to(vault)),
                          "version": ok.get("version"), "path": ok.get("path")},
                         ensure_ascii=False, indent=2))
        return 0 if ok.get("present") else 1
    if method == "message":
        # Nothing to fetch: this one is installed by the user, and the honest answer is the hint for
        # their platform. It used to fall through to "no-provisioner", which reads like a defect in
        # Zanmai rather than a step for the user.
        hint = ((spec.get("os") or {}).get(osname) or {}).get("install_hint") or {}
        print(json.dumps({"id": args.id, "state": "needs-user", "tier": tier,
                          "hint": hint.get("text") or spec.get("purpose"),
                          "guide": hint.get("guide")}, ensure_ascii=False, indent=2))
        return 0
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
    return vault / RUNTIME_DIR / "tool-cache.json"


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
        alle = reg.get("capabilities") or {}
        # A capability an expert does not define may still be one anybody may use. Motion graphics
        # are the case that made this necessary: they are needed by whoever produces timed visuals,
        # a cut today and a web page tomorrow, and copying the requirement into each expert is how
        # two copies drift apart. Own entry first, shared as the fallback.
        caps = (alle.get(expert) or {}).get(capability) or (alle.get("shared") or {}).get(capability) or {}
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
        if (cand / SYSTEM_DIR).is_dir():
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


def _run_hook_and_record(args: argparse.Namespace) -> int:
    """Run a hook and write down every refusal, in one place rather than in each guard.

    Central on purpose. Putting the note in each guard means the next guard someone writes is the
    one that stays silent, which is the failure this whole family keeps having. Here it holds for
    every hook there is and every hook there will be.

    The refusal text is the guard's own words on stderr, so nothing has to be restated and the log
    carries what the session actually saw. stderr is passed through unchanged: the host reads it,
    and a guard whose message went missing would be worse than one that logs nothing.
    """
    import contextlib
    import io

    puffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(puffer):
            rc = args.func(args)
    finally:
        text = puffer.getvalue()
        if text:
            sys.stderr.write(text)
    if rc == 2:
        name = getattr(args, "hook_cmd", None) or getattr(args, "subcmd", None) or "hook"
        _guard_refused(_LAST_PAYLOAD, str(name), text or f"exit 2 from {name}")
    return rc


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="zanmai", description="Zanmai CLI: setup, snapshots, bundles, attachments, contacts, notes, plans, reviews, files, updates, index, memory, media, hooks.")
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

    pt_all = sub_tools.add_parser("ensure-all", help="What this vault still needs, in one pass. Reports without --yes; that report is the question the user answers.")
    pt_all.add_argument("vault", nargs="?", default=".")
    pt_all.add_argument("--yes", action="store_true", help="Fetch everything Zanmai can fetch itself. What needs the user, or money, or an account stays theirs.")
    pt_all.set_defaults(func=cmd_tools_ensure_all)

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
    # (deterministic, matching the session-start recheck), so these are not relied on.
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
    ps_upgrade.add_argument("--channel", metavar="NAME",
                             help="Switch which branch this vault tracks (e.g. 'beta') and remember "
                                  "the choice in zanmai/user.md. 'release' switches back to the "
                                  "manifest's default branch. Omit to use whatever is already set.")
    ps_upgrade.add_argument("--changelog", action="store_true",
                             help="With --check, also print the remote CHANGELOG.md, unapplied.")
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

    ps_create = sub_snap.add_parser("create", help="Take a snapshot: commit the whole vault into the history. Respects auto_snapshots in user.md.")
    ps_create.add_argument("vault", nargs="?", default=".")
    ps_create.add_argument("--reason", required=True, help="Short slug naming why the snapshot is taken; it becomes the snapshot's message.")
    ps_create.set_defaults(func=cmd_snapshot_create)

    ps_enable = sub_snap.add_parser("enable", help="Turn auto_snapshots ON in zanmai/user.md.")
    ps_enable.add_argument("vault", nargs="?", default=".")
    ps_enable.set_defaults(func=cmd_snapshot_enable)

    ps_disable = sub_snap.add_parser("disable", help="Turn auto_snapshots OFF in zanmai/user.md. No automatic snapshots until re-enabled.")
    ps_disable.add_argument("vault", nargs="?", default=".")
    ps_disable.set_defaults(func=cmd_snapshot_disable)

    ps_list = sub_snap.add_parser("list", help="The snapshots, newest first, and what they occupy together.")
    ps_list.add_argument("vault", nargs="?", default=".")
    ps_list.set_defaults(func=cmd_snapshot_list)

    ps_show = sub_snap.add_parser("show", help="What one snapshot changed, or one file as it was in it.")
    ps_show.add_argument("vault", nargs="?", default=".")
    ps_show.add_argument("--snapshot", required=True, help="The short name from `snapshot list`.")
    ps_show.add_argument("--path", default=None, help="A vault-relative path. Without it, the change list.")
    ps_show.set_defaults(func=cmd_snapshot_show)

    ps_restore = sub_snap.add_parser("restore", help="Put one file back the way it was in a snapshot. The current version goes to the trash first.")
    ps_restore.add_argument("vault", nargs="?", default=".")
    ps_restore.add_argument("--snapshot", required=True, help="The short name from `snapshot list`.")
    ps_restore.add_argument("--path", required=True, help="The vault-relative path to put back.")
    ps_restore.set_defaults(func=cmd_snapshot_restore)

    ps_compact = sub_snap.add_parser("compact", help="Let git pack the history down. Loses nothing.")
    ps_compact.add_argument("vault", nargs="?", default=".")
    ps_compact.set_defaults(func=cmd_snapshot_compact)

    # bundle -----


    # import -----
    p_import = sub.add_parser("import", help=f"The drop area {IMPORT_DIR}/: what is waiting and which way each file goes.")
    sub_import = p_import.add_subparsers(dest="subcmd", required=True)
    pi_scan = sub_import.add_parser("scan", help="What is waiting, oldest first, with the route per file.")
    pi_scan.add_argument("vault", nargs="?", default=".")
    pi_scan.add_argument("--verbose", action="store_true", help="Say what happens to each file, not just what it is.")
    pi_scan.set_defaults(func=cmd_import_scan)

    # housekeeping -----
    p_house = sub.add_parser("housekeeping", help=f"Clear what is past {RETENTION_DAYS} days in the trash, the scratch area and the snapshots. Runs itself at session start.")
    p_house.add_argument("vault", nargs="?", default=".")
    p_house.set_defaults(func=cmd_housekeeping)

    p_video = sub.add_parser("video", help="The mechanic under a cut: probe, transcribe with word timings, check a cut sheet, cut, pull frames.")
    sub_video = p_video.add_subparsers(dest="video_cmd", required=True)

    pvi_probe = sub_video.add_parser("probe", help="What a file actually is: length, size, exact frame rate, whether it carries chapters.")
    pvi_probe.add_argument("vault", nargs="?", default=".")
    pvi_probe.add_argument("--file", required=True)
    pvi_probe.set_defaults(func=cmd_video_probe)

    pvi_tr = sub_video.add_parser("transcribe", help="One source to words with start and end times. Runs once per source; re-running reads the saved result.")
    pvi_tr.add_argument("vault", nargs="?", default=".")
    pvi_tr.add_argument("--file", required=True)
    pvi_tr.add_argument("--slug", required=True, help="The job this belongs to.")
    pvi_tr.add_argument("--language", default="auto")
    pvi_tr.add_argument("--lexicon", help="Names from the vault, to bias the recogniser.")
    pvi_tr.add_argument("--dtw-preset", dest="dtw_preset", help="Override the alignment preset; derived from the model by default.")
    pvi_tr.add_argument("--force", action="store_true", help="Transcribe again even though a result exists.")
    pvi_tr.set_defaults(func=cmd_video_transcribe)

    pvi_cs = sub_video.add_parser("cutsheet", help="Check a cut sheet before anything renders, and say what it would produce.")
    pvi_cs.add_argument("vault", nargs="?", default=".")
    pvi_cs.add_argument("--file", required=True)
    pvi_cs.add_argument("--words", help="The transcript, to check that no word is cut through.")
    pvi_cs.add_argument("--text", action="store_true", help="Print the spoken line of every segment, so the cut can be read.")
    pvi_cs.set_defaults(func=cmd_video_cutsheet)

    pvi_pr = sub_video.add_parser("propose", help="A first cut sheet from the word timings: speech kept, long silence dropped. Measurement only.")
    pvi_pr.add_argument("vault", nargs="?", default=".")
    pvi_pr.add_argument("--words", required=True, help="The transcript written by `video transcribe`.")
    pvi_pr.add_argument("--out", required=True)
    pvi_pr.add_argument("--source", help="Override the source path recorded in the transcript.")
    pvi_pr.add_argument("--gap", type=float, default=VIDEO_MIN_GAP, help="Silence longer than this is dropped.")
    pvi_pr.add_argument("--padding", type=float, default=0.08, help="Breath left on each side of a kept passage.")
    pvi_pr.add_argument("--boundary-tail", dest="boundary_tail", type=float, default=0.2, help="Margin after a passage that ends on a full stop.")
    pvi_pr.add_argument("--boundary-lead", dest="boundary_lead", type=float, default=0.14, help="Margin before a passage that follows a sentence end.")
    pvi_pr.add_argument("--end-tail", dest="end_tail", type=float, default=0.65, help="Margin after the final passage, so the last word rings out.")
    pvi_pr.add_argument("--merge", type=float, default=0.35, help="Passages closer than this are joined rather than cut apart; a hole this small is not worth a visible jump.")
    pvi_pr.add_argument("--tail", type=float, default=None, help="Margin after a kept passage. Larger than the one in front by default, because a word trails off below the level that counts as speech.")
    pvi_pr.set_defaults(func=cmd_video_propose)

    pvi_cut = sub_video.add_parser("cut", help="Assemble the kept passages into one file.")
    pvi_cut.add_argument("vault", nargs="?", default=".")
    pvi_cut.add_argument("--file", required=True, help="The cut sheet.")
    pvi_cut.add_argument("--out", required=True)
    pvi_cut.add_argument("--crf", type=int, default=19)
    pvi_cut.add_argument("--preset", default="medium")
    pvi_cut.add_argument("--size", help="Target WIDTHxHEIGHT. Without it, the first source decides, and a mismatch is reported.")
    pvi_cut.add_argument("--fps", help="Target frame rate as an exact fraction, e.g. 30000/1001. Without it, the first source decides.")
    pvi_cut.add_argument("--cover", type=float, default=0.0, help="Hide the seams: alternate the framing by this percent from passage to passage. About 5 is enough to stop a jump registering; 0 leaves the cuts bare.")
    pvi_cut.set_defaults(func=cmd_video_cut)

    pvi_co = sub_video.add_parser("correct", help="Fix spellings in a transcript before building from it. Without --replace it reports what looks unknown.")
    pvi_co.add_argument("vault", nargs="?", default=".")
    pvi_co.add_argument("--words", required=True)
    pvi_co.add_argument("--replace", action="append", help="heard=correct, single whole words only. Repeatable.")
    pvi_co.add_argument("--list", help="A file of heard=correct lines, one per line, that grows with the brand.")
    pvi_co.add_argument("--threshold", type=float, default=0.55, help="Report words the recogniser was less certain about than this.")
    pvi_co.add_argument("--out", help="Write elsewhere instead of in place.")
    pvi_co.set_defaults(func=cmd_video_correct)

    pvi_cap = sub_video.add_parser("caption", help="Captions from the transcript: a subtitle file, and optionally burned into a copy.")
    pvi_cap.add_argument("vault", nargs="?", default=".")
    pvi_cap.add_argument("--words", required=True)
    pvi_cap.add_argument("--out", required=True, help="Where the subtitle file goes.")
    pvi_cap.add_argument("--cutsheet", help="Remap the times onto the cut before writing.")
    pvi_cap.add_argument("--style", choices=sorted(CAPTION_STYLES), default="subtitle", help="karaoke: short phrases, every comma breaks, for short pieces where each word is highlighted. subtitle: the broadcast convention, for anything long.")
    pvi_cap.add_argument("--max-words", dest="max_words", type=int, default=0, help="Override the style's word limit.")
    pvi_cap.add_argument("--max-chars", dest="max_chars", type=int, default=0, help="Override the style's character limit.")
    pvi_cap.add_argument("--min-duration", dest="min_duration", type=float, default=0.0, help="Shorter lines are merged into their neighbour; anything under a second is a flash nobody reads.")
    pvi_cap.add_argument("--burn", help="Also burn the captions into this file.")
    pvi_cap.add_argument("--burn-out", dest="burn_out")
    pvi_cap.add_argument("--slug", default="captions")
    pvi_cap.add_argument("--font-file", dest="font_file", help="A real font file from the brand. Without one, a system font.")
    pvi_cap.add_argument("--box-colour", dest="box_colour", default="#000000C0", help="Caption box, from the brand.")
    pvi_cap.add_argument("--text-colour", dest="text_colour", default="#FFFFFF")
    pvi_cap.add_argument("--font-size", dest="font_size", type=int, default=44, help="At a frame height of 1080; scaled for anything else.")
    pvi_cap.add_argument("--margin", type=int, default=90, help="Distance from the bottom at a frame height of 1080.")
    pvi_cap.add_argument("--crf", type=int, default=19)
    pvi_cap.set_defaults(func=cmd_video_caption)

    pvi_rf = sub_video.add_parser("reframe", help="Put the picture into another aspect ratio, by cropping or by fitting it whole.")
    pvi_rf.add_argument("vault", nargs="?", default=".")
    pvi_rf.add_argument("--file", required=True)
    pvi_rf.add_argument("--out", required=True)
    pvi_rf.add_argument("--format", required=True, help="wide, upright, square or classic.")
    pvi_rf.add_argument("--fit", action="store_true", help="Keep the whole picture and fill the rest with a blurred enlargement, instead of cropping.")
    pvi_rf.add_argument("--centre", type=float, default=0.5, help="Where the crop window sits across the width, 0 to 1.")
    pvi_rf.add_argument("--height", type=int)
    pvi_rf.add_argument("--crf", type=int, default=19)
    pvi_rf.set_defaults(func=cmd_video_reframe)

    pvi_mx = sub_video.add_parser("mix", help="The audio passes: denoise, a music bed, levelling. The picture is copied, never re-encoded.")
    pvi_mx.add_argument("vault", nargs="?", default=".")
    pvi_mx.add_argument("--file", required=True)
    pvi_mx.add_argument("--out", required=True)
    pvi_mx.add_argument("--music", help="A licensed track. Never downloaded, always supplied.")
    pvi_mx.add_argument("--music-db", dest="music_db", type=float, default=-18.0)
    pvi_mx.add_argument("--denoise", action="store_true")
    pvi_mx.add_argument("--denoise-db", dest="denoise_db", type=float, default=6.0, help="How many decibels of noise to take out. Above about 12 the voice starts to sound hollow.")
    pvi_mx.add_argument("--loudness", type=float, default=-16.0, help="Target in LUFS. -16 for speech on the web, -14 where a platform expects it.")
    pvi_mx.set_defaults(func=cmd_video_mix)

    pvi_ex = sub_video.add_parser("export", help="One file per purpose. The master is never overwritten.")
    pvi_ex.add_argument("vault", nargs="?", default=".")
    pvi_ex.add_argument("--file", required=True)
    pvi_ex.add_argument("--name", required=True, help="What the piece is called, without a suffix.")
    pvi_ex.add_argument("--profile", default="master,web", help="Comma-separated: master, web, platform.")
    pvi_ex.add_argument("--out-dir", dest="out_dir")
    pvi_ex.add_argument("--overwrite", action="store_true")
    pvi_ex.set_defaults(func=cmd_video_export)

    pvi_tx = sub_video.add_parser("text", help="Write the transcript out for editing, or read an edited one back as a cut.")
    pvi_tx.add_argument("vault", nargs="?", default=".")
    pvi_tx.add_argument("--words", required=True)
    pvi_tx.add_argument("--write", help="Write the transcript here, in paragraphs, for editing.")
    pvi_tx.add_argument("--read", help="Read the edited text back.")
    pvi_tx.add_argument("--out", help="Where the cut sheet goes when reading back.")
    pvi_tx.add_argument("--source", help="Override the source path recorded in the transcript.")
    pvi_tx.add_argument("--paragraph-gap", dest="paragraph_gap", type=float, default=1.2)
    pvi_tx.add_argument("--join", type=float, default=0.35, help="Kept words closer than this stay in one passage.")
    pvi_tx.add_argument("--tolerance", type=int, default=0, help="How many added words are tolerated before the text is refused as reordered.")
    pvi_tx.set_defaults(func=cmd_video_text)

    pvi_sy = sub_video.add_parser("sync", help="The offset between two recordings of the same conversation, measured in their sound.")
    pvi_sy.add_argument("vault", nargs="?", default=".")
    pvi_sy.add_argument("--a", required=True)
    pvi_sy.add_argument("--b", required=True)
    pvi_sy.add_argument("--slug", default="sync")
    pvi_sy.add_argument("--window", type=float, default=180.0, help="Seconds compared from the start of each file.")
    pvi_sy.add_argument("--max-offset", dest="max_offset", type=float, default=60.0)
    pvi_sy.add_argument("--min-confidence", dest="min_confidence", type=float, default=1.0)
    pvi_sy.set_defaults(func=cmd_video_sync)

    pvi_br = sub_video.add_parser("brand", help="An opening, a closing and a logo held throughout, from the brand.")
    pvi_br.add_argument("vault", nargs="?", default=".")
    pvi_br.add_argument("--file", required=True)
    pvi_br.add_argument("--out", required=True)
    pvi_br.add_argument("--intro")
    pvi_br.add_argument("--outro")
    pvi_br.add_argument("--logo")
    pvi_br.add_argument("--logo-position", dest="logo_position", default="bottom-right")
    pvi_br.add_argument("--logo-width", dest="logo_width", type=float, default=8.0, help="Percent of the frame width.")
    pvi_br.add_argument("--logo-margin", dest="logo_margin", type=float, default=4.0, help="Percent of the frame, kept clear of the platform's own controls.")
    pvi_br.add_argument("--logo-opacity", dest="logo_opacity", type=float, default=0.9)
    pvi_br.add_argument("--slug", default="brand")
    pvi_br.add_argument("--crf", type=int, default=19)
    pvi_br.set_defaults(func=cmd_video_brand)

    pvi_chap = sub_video.add_parser("chapters", help="Chapter marks from the transcript, to paste under a video.")
    pvi_chap.add_argument("vault", nargs="?", default=".")
    pvi_chap.add_argument("--words", required=True)
    pvi_chap.add_argument("--out")
    pvi_chap.add_argument("--count", type=int, default=8)
    pvi_chap.add_argument("--min-gap", dest="min_gap", type=float, default=45.0)
    pvi_chap.add_argument("--title-words", dest="title_words", type=int, default=6)
    pvi_chap.set_defaults(func=cmd_video_chapters)

    pvi_th = sub_video.add_parser("thumbnail", help="Candidates for a thumbnail: the sharpest, best-lit frames.")
    pvi_th.add_argument("vault", nargs="?", default=".")
    pvi_th.add_argument("--file", required=True)
    pvi_th.add_argument("--out")
    pvi_th.add_argument("--slug", default="thumbs")
    pvi_th.add_argument("--sample", type=int, default=24)
    pvi_th.add_argument("--keep", type=int, default=5)
    pvi_th.set_defaults(func=cmd_video_thumbnail)

    pvi_tl = sub_video.add_parser("timeline", help="One picture of the whole piece: filmstrip, loudness, words. The cheap way to look.")
    pvi_tl.add_argument("vault", nargs="?", default=".")
    pvi_tl.add_argument("--file", required=True)
    pvi_tl.add_argument("--words", help="Transcript, to write the words along the strip.")
    pvi_tl.add_argument("--columns", type=int, default=12)
    pvi_tl.add_argument("--slug", default="timeline")
    pvi_tl.add_argument("--out")
    pvi_tl.set_defaults(func=cmd_video_timeline)

    pvi_bf = sub_video.add_parser("brief", help="Everything needed to judge footage, in one call: facts, loudness, transcript, a few frames. Cheap on purpose.")
    pvi_bf.add_argument("vault", nargs="?", default=".")
    pvi_bf.add_argument("--file", required=True)
    pvi_bf.add_argument("--slug", default="brief", help="Where the transcript is kept, so later steps reuse it.")
    pvi_bf.add_argument("--language", default="auto")
    pvi_bf.add_argument("--sample-over", dest="sample_over", type=float, default=600.0, help="Longer than this and the words come from three samples instead of the whole thing.")
    pvi_bf.add_argument("--sample-seconds", dest="sample_seconds", type=float, default=90.0)
    pvi_bf.add_argument("--columns", type=int, default=12, help="How many stills go into the one overview picture.")
    pvi_bf.set_defaults(func=cmd_video_brief)

    pvi_ck = sub_video.add_parser("check", help="The measurable half of a review: duplicated frames, brightness steps at the joins, actual length.")
    pvi_ck.add_argument("vault", nargs="?", default=".")
    pvi_ck.add_argument("--file", required=True)
    pvi_ck.add_argument("--seams", help="Comma-separated seconds where a graphic was composited in. A plain cut is not a seam in this sense.")
    pvi_ck.add_argument("--composited", action="store_true", help="The file came out of a composite. Only then are duplicated frames a fault rather than a still screen.")
    pvi_ck.add_argument("--duplicate-limit", dest="duplicate_limit", type=float, default=8.0)
    pvi_ck.add_argument("--luma-limit", dest="luma_limit", type=float, default=0.06)
    pvi_ck.add_argument("--max-seams", dest="max_seams", type=int, default=40)
    pvi_ck.set_defaults(func=cmd_video_check)

    pvi_fr = sub_video.add_parser("frames", help="Pull frames so they can be looked at.")
    pvi_fr.add_argument("vault", nargs="?", default=".")
    pvi_fr.add_argument("--file", required=True)
    pvi_fr.add_argument("--slug", default="review")
    pvi_fr.add_argument("--at", help="Comma-separated seconds. Without it, an even sample.")
    pvi_fr.add_argument("--count", type=int, default=6)
    pvi_fr.add_argument("--out")
    pvi_fr.set_defaults(func=cmd_video_frames)

    p_voice = sub.add_parser("voice", help="Voice notes waiting in the import folder: what waits, the vault's names, transcription, filing.")
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

    pv_ar = sub_voice.add_parser("archive", help="Move a processed recording into the day it was spoken on, keeping it.")
    pv_ar.add_argument("vault", nargs="?", default=".")
    pv_ar.add_argument("--file", required=True)
    pv_ar.add_argument("--agent")
    pv_ar.set_defaults(func=cmd_voice_archive)

    pv_ja = sub_voice.add_parser("journal-append", help="Append text to the daily note of the day the recording was made, not the day it is read.")
    pv_ja.add_argument("vault", nargs="?", default=".")
    pv_ja.add_argument("--file", required=True)
    pv_ja.add_argument("--text", required=True)
    pv_ja.set_defaults(func=cmd_voice_journal_append)

    p_work = sub.add_parser("work", help="Work objects: one row plus one page per piece of work, on the machine's own side.")
    sub_work = p_work.add_subparsers(dest="work_cmd", required=True)

    # Every one of these takes its subject as a bare positional as well as a flag. The flag is
    # what the skills write; the bare form is what a person types, and until 2026-08-26 the bare
    # form was silently eaten by an optional `vault` positional that nothing in the product ever
    # passed: `work open "a title"` failed with "the following arguments are required: --title",
    # naming the flag the user had not used instead of the argument they had. The vault is a flag
    # now, and it is resolved to the vault root either way.
    pw_open = sub_work.add_parser("open", help="Open a work object and print its id.")
    pw_open.add_argument("title_pos", nargs="?", metavar="TITLE", help="The title. Same as --title.")
    pw_open.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_open.add_argument("--title")
    pw_open.add_argument("--owner", "--agent", dest="owner", help="Which specialist is on it.")
    pw_open.add_argument("--goal", help="What finished looks like.")
    pw_open.add_argument("--deliverable", help="Where the result will land.")
    pw_open.add_argument("--workshop", help="Where the working files live.")
    pw_open.add_argument("--due", help="YYYY-MM-DD, only where the work has a real deadline.")
    pw_open.set_defaults(func=cmd_work_open)

    pw_ask = sub_work.add_parser("ask", help="Record a question only the user can answer; marks the object as waiting.")
    pw_ask.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
    pw_ask.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_ask.add_argument("--id", help="Full id or its first characters.")
    pw_ask.add_argument("--question", required=True)
    pw_ask.set_defaults(func=cmd_work_ask)

    pw_answer = sub_work.add_parser("answer", help="Record the user's answer and put the object back to open.")
    pw_answer.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
    pw_answer.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_answer.add_argument("--id")
    pw_answer.add_argument("--answer", required=True)
    pw_answer.set_defaults(func=cmd_work_answer)

    pw_log = sub_work.add_parser("log", help="Append one line to the object's log and add up its cost.")
    pw_log.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
    pw_log.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_log.add_argument("--id")
    pw_log.add_argument("--note", required=True)
    pw_log.add_argument("--agent")
    pw_log.add_argument("--tokens", type=int)
    pw_log.add_argument("--minutes", type=int)
    pw_log.add_argument("--workshop")
    pw_log.add_argument("--deliverable")
    pw_log.add_argument("--due", help="Set or move the deadline, YYYY-MM-DD.")
    pw_log.set_defaults(func=cmd_work_log)

    pw_done = sub_work.add_parser("done", help="Close a work object.")
    pw_done.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
    pw_done.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_done.add_argument("--id")
    pw_done.add_argument("--agent")
    pw_done.set_defaults(func=cmd_work_done)

    pw_list = sub_work.add_parser("list", help="What is open and what is waiting on the user.")
    pw_list.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_list.add_argument("--state", help="Filter: open, 'waiting on you', done.")
    pw_list.set_defaults(func=cmd_work_list)

    pw_show = sub_work.add_parser("show", help="Print one work object: its row and its page.")
    pw_show.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
    pw_show.add_argument("--vault", default=None, help="Where the vault is. Default: found from here.")
    pw_show.add_argument("--id")
    pw_show.set_defaults(func=cmd_work_show)

    p_prose = sub.add_parser("prose", help="Check draft prose before it is written, so the write is not later refused by the prose-guard hook.")
    sub_prose = p_prose.add_subparsers(dest="prose_cmd", required=True)

    pp_check = sub_prose.add_parser("check", help="Report lines using a dash as sentence punctuation. Exit 0 always; the finding is the output, never a failure.")
    pp_check.add_argument("--text", help="Text to check. Omit to read from stdin.")
    pp_check.set_defaults(func=cmd_prose_check)

    p_brand = sub.add_parser("brand", help="The brand a piece is built against: is there one, and what is still undecided in it.")
    sub_brand = p_brand.add_subparsers(dest="brand_cmd", required=True)

    pb_check = sub_brand.add_parser("check", help="Exit 1 when no brand exists. Run before dispatching anyone who produces something the user looks at.")
    pb_check.add_argument("vault", nargs="?", default=".")
    pb_check.add_argument("--brand", help="Check one brand by name instead of all.")
    pb_check.add_argument("--limit", type=int, default=12, help="How many open fields to print per brand.")
    pb_check.set_defaults(func=cmd_brand_check)

    pb_list = sub_brand.add_parser("list", help="Every brand that exists, and where it lives.")
    pb_list.add_argument("vault", nargs="?", default=".")
    pb_list.set_defaults(func=cmd_brand_list)

    p_task = sub.add_parser("task", help="Task lines on the user's own lists: write one they asked for, tick one off, see what is due.")
    sub_task = p_task.add_subparsers(dest="task_cmd", required=True)

    pt_add = sub_task.add_parser("add", help="Write a task the user asked for. The only route to a task line; inside an ordinary write it stays refused.")
    pt_add.add_argument("vault", nargs="?", default=".")
    pt_add.add_argument("--text", required=True, help="The task in the user's own words.")
    pt_add.add_argument("--file", help="Which list it goes on. Default: today's journal entry.")
    pt_add.add_argument("--due", help="YYYY-MM-DD, only where there is a real deadline.")
    pt_add.add_argument("--agent", help="Name for the activity-log line.")
    pt_add.set_defaults(func=cmd_task_add)

    pt_done = sub_task.add_parser("done", help="Tick a task off, matched on a fragment of its text.")
    pt_done.add_argument("vault", nargs="?", default=".")
    pt_done.add_argument("--text", required=True, help="Enough of the wording to hit exactly one.")
    pt_done.add_argument("--file", help="Restrict the search to one list.")
    pt_done.add_argument("--agent", help="Name for the activity-log line.")
    pt_done.set_defaults(func=cmd_task_done)

    pt_list = sub_task.add_parser("list", help="Open tasks across the whole vault, wherever they sit.")
    pt_list.add_argument("vault", nargs="?", default=".")
    pt_list.add_argument("--due-within", dest="due_within", type=int, help="Only dated ones falling due within N days, overdue included.")
    pt_list.add_argument("--limit", type=int, default=40)
    pt_list.set_defaults(func=cmd_task_list)

    p_bundle = sub.add_parser("bundle", help="Bundle operations.")
    sub_bundle = p_bundle.add_subparsers(dest="subcmd", required=True)

    pb_create = sub_bundle.add_parser("create", help="Create <kind>/<slug>/<slug>.md from template plus INDEX.md.")
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
    pb_create.add_argument("--tags", help="Comma-separated tags, e.g. 'sport,ernaehrung'. Without this the file carries whatever tags its own frontmatter had, which for a source without frontmatter is none.")
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
    pb_addfile.add_argument("--tags",
                            help="Comma-separated tags. Beats what the file says about itself; a source without frontmatter otherwise lands with none.")
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
    pb_addtruth.add_argument("--tags", help="Comma-separated tags, e.g. 'sport,ernaehrung'.")
    pb_addtruth.set_defaults(func=cmd_create_sub_bundle_truth)

    pb_rename = sub_bundle.add_parser("rename", help="Atomically rename a slug: file rename, frontmatter slug, vault-wide wikilink rewrite, master INDEX refresh.")
    pb_rename.add_argument("vault", nargs="?", default=".")
    pb_rename.add_argument("--old", required=True)
    pb_rename.add_argument("--new", required=True)
    pb_rename.add_argument("--bundle-slug", dest="bundle_slug")
    pb_rename.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_rename.set_defaults(func=cmd_rename_slug)

    pb_ientry = sub_bundle.add_parser("index-entry", help="Rewrite a member's one-line description in the bundle's INDEX.md.")
    pb_ientry.add_argument("vault", nargs="?", default=".")
    pb_ientry.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pb_ientry.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_ientry.add_argument("--file", required=True, help="Member slug or filename.")
    pb_ientry.add_argument("--summary", required=True, help="What this file is, in one line.")
    pb_ientry.set_defaults(func=cmd_bundle_index_entry)

    pb_remove = sub_bundle.add_parser("remove-file", help="Discard a member: to trash/, out of INDEX.md, into the activity log, in one call.")
    pb_remove.add_argument("vault", nargs="?", default=".")
    pb_remove.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pb_remove.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_remove.add_argument("--file", required=True, help="Member slug or filename.")
    pb_remove.set_defaults(func=cmd_bundle_remove_file)

    pb_setbody = sub_bundle.add_parser("set-body", help="Replace the body of a file in a bundle. Frontmatter untouched.")
    pb_setbody.add_argument("vault", nargs="?", default=".")
    pb_setbody.add_argument("--file", required=True, help="Vault-relative path, or a basename unique in the vault.")
    pb_setbody.add_argument("--body-file", dest="body_file", help="Read the new body from this file. Default: stdin.")
    pb_setbody.add_argument("--replace", action="store_true", help="Allow overwriting a body that already has content.")
    pb_setbody.add_argument("--agent", help="Name for the activity-log line.")
    pb_setbody.set_defaults(func=cmd_bundle_set_body)

    pb_editfile = sub_bundle.add_parser("edit-file", help="Correct frontmatter fields of an existing file in place. Body untouched.")
    pb_editfile.add_argument("vault", nargs="?", default=".")
    pb_editfile.add_argument("--file", required=True, help="Vault-relative path, or a basename unique in the vault.")
    pb_editfile.add_argument("--set", action="append", default=[], help="key=value. A list is written as [a, b, c]. Repeatable.")
    pb_editfile.add_argument("--remove", action="append", default=[], help="Field to remove. Repeatable.")
    pb_editfile.add_argument("--agent", help="Name for the activity-log line.")
    pb_editfile.set_defaults(func=cmd_bundle_edit_file)

    # asset -----
    p_asset = sub.add_parser("asset", help="Non-markdown files, filed into the bundle they belong to.")
    sub_asset = p_asset.add_subparsers(dest="subcmd", required=True)

    pa_add = sub_asset.add_parser("add", help="Copy a non-markdown file into the bundle it belongs to.")
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

    pc_create = sub_contact.add_parser("create", help="Create a contact file under contacts/<people|organisations>/<slug>.md.")
    pc_create.add_argument("vault", nargs="?", default=".")
    pc_create.add_argument("--kind", required=True, choices=("person", "organization"))
    pc_create.add_argument("--slug", required=True)
    pc_create.add_argument("--full-name", dest="full_name")
    pc_create.add_argument("--source", help="Optional source markdown file. Body verbatim, frontmatter migrated to schema.")
    # Every optional field the schema defines for either contact kind, derived rather than listed a
    # second time. The hand-kept list was missing `address`, `birthday` and `nickname`.
    for _field in dict.fromkeys(KIND_FIELDS["contact/person"]["optional"]
                                + KIND_FIELDS["contact/organization"]["optional"]):
        pc_create.add_argument(f"--{_field}")
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

    # journal -----
    p_journal = sub.add_parser("journal", help=f"Everything the journal under {JOURNAL_DIR}/ does: read, write, roll up.")
    sub_journal = p_journal.add_subparsers(dest="subcmd", required=True)

    def _add_journal_args(p: argparse.ArgumentParser, *, with_date: bool = True) -> None:
        p.add_argument("vault", nargs="?", default=".")
        p.add_argument("--kind", required=True, choices=list(_JOURNAL_KINDS),
                       dest="_kind", help="Which layer of the journal.")
        if with_date:
            p.add_argument("--date", default=None,
                           help="Target date YYYY-MM-DD. Defaults to today; the entry is the one covering that date.")

    pj_path = sub_journal.add_parser("path", help="Print the entry's path. Creates nothing.")
    _add_journal_args(pj_path)
    pj_path.set_defaults(func=cmd_journal_path)

    pj_ensure = sub_journal.add_parser("ensure", help="Create the entry and its bundle if they are not there yet.")
    _add_journal_args(pj_ensure)
    pj_ensure.set_defaults(func=cmd_journal_ensure)

    pj_append = sub_journal.add_parser("append", help="Append text to the entry, verbatim, below what is already there.")
    _add_journal_args(pj_append)
    pj_append.add_argument("--text", required=True, help="The user's words, unchanged.")
    pj_append.set_defaults(func=cmd_journal_append)

    pj_read = sub_journal.add_parser("read", help="Print the entry, or say that the period holds nothing.")
    _add_journal_args(pj_read)
    pj_read.set_defaults(func=cmd_journal_read)

    pj_list = sub_journal.add_parser("list", help="List the entries of one kind that exist, oldest first.")
    _add_journal_args(pj_list, with_date=False)
    pj_list.add_argument("--limit", type=int, default=0, help="Show only the newest N. 0 shows all.")
    pj_list.set_defaults(func=cmd_journal_list)

    pj_due = sub_journal.add_parser("rollup-due", help="Which rollups are due, and which entries each one reads. Writes nothing.")
    pj_due.add_argument("vault", nargs="?", default=".")
    pj_due.add_argument("--date", default=None, help="Pretend today is this date.")
    pj_due.set_defaults(func=cmd_journal_rollup_due)

    pj_rollup = sub_journal.add_parser("rollup", help="Write the rollup into the period entry. Refuses a second one for the same period.")
    _add_journal_args(pj_rollup)
    pj_rollup.add_argument("--text", required=True, help="The summary, in the user's own words where possible.")
    pj_rollup.add_argument("--this-period", dest="this_period", action="store_true",
                           help="Roll up the period the date falls in, instead of the one before it.")
    pj_rollup.set_defaults(func=cmd_journal_rollup)

    # file -----
    p_file = sub.add_parser("file", help="File moves into system folders.")
    sub_file = p_file.add_subparsers(dest="subcmd", required=True)

    pf_trash = sub_file.add_parser("trash", help=f"Move a file to {TRASH_DIR}/, keeping its path. Undo with `file restore`.")
    pf_trash.add_argument("vault", nargs="?", default=".")
    pf_trash.add_argument("--path", required=True)
    pf_trash.set_defaults(func=cmd_trash_file)

    pf_archive = sub_file.add_parser("archive", help=f"Move a file to {ARCHIVE_DIR}/, keeping its path. Undo with `file restore`.")
    pf_archive.add_argument("vault", nargs="?", default=".")
    pf_archive.add_argument("--path", required=True)
    pf_archive.set_defaults(func=cmd_archive_file)

    pf_restore = sub_file.add_parser("restore", help=f"Put a file from {TRASH_DIR}/ or {ARCHIVE_DIR}/ back where it came from.")
    pf_restore.add_argument("vault", nargs="?", default=".")
    pf_restore.add_argument("--path", required=True, help=f"The file as it lies now, e.g. {TRASH_DIR}/<its old path>.")
    pf_restore.set_defaults(func=cmd_restore_file)

    # plan -----
    p_plan = sub.add_parser("plan", help="Plan sections on a bundle's truth file.")
    sub_plan = p_plan.add_subparsers(dest="subcmd", required=True)

    pp_clear = sub_plan.add_parser("clear-section", help="Remove the '## Plan' section from a bundle truth file after filing.")
    pp_clear.add_argument("vault", nargs="?", default=".")
    pp_clear.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pp_clear.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pp_clear.add_argument("--truth-file", dest="truth_file")
    pp_clear.set_defaults(func=cmd_clear_plan_section)

    # review -----
    p_review = sub.add_parser("review", help="Read-once briefings written for a single decision.")
    sub_review = p_review.add_subparsers(dest="subcmd", required=True)

    pr_archive = sub_review.add_parser("archive", help="Move a read-once briefing off the desk into zanmai/logs/<YYYY>/<MM>/.")
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
    pu_links.add_argument("--scope", help="Subfolder under the vault to sweep. Defaults to the whole vault. System paths are hard-excluded.")
    pu_links.set_defaults(func=cmd_update_wikilinks)

    pu_embeds = sub_update.add_parser("embeds", help="Rewrite embed references in a bundle's markdown to point at the bundle's own files.")
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

    pi_rebuild = sub_idx.add_parser("rebuild", help="Walk the vault, write zanmai/memory/vault-index.json (Schicht A).")
    pi_rebuild.add_argument("vault", nargs="?", default=".")
    pi_rebuild.add_argument("--scope", help="Subfolder to limit the walk.")
    pi_rebuild.add_argument("--quiet", action="store_true")
    pi_rebuild.set_defaults(func=cmd_reindex)

    pi_patterns = sub_idx.add_parser("patterns", help="Aggregate themes/hubs/bundles into zanmai/memory/patterns.json (Schicht B).")
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

    pm_briefing = sub_mem.add_parser("briefing", help="Atomic rebuild of zanmai/memory/briefing.md.")
    pm_briefing.add_argument("vault", nargs="?", default=".")
    pm_briefing.add_argument("--quiet", action="store_true")
    pm_briefing.set_defaults(func=cmd_briefing)

    pm_report = sub_mem.add_parser("report", help="Write an operation report to zanmai/logs/<YYYY>/<MM>/.")
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
    pm_rotate.add_argument("--file", default=ACTIVITY_LOG_FILE)
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

    ph_session = sub_hook.add_parser("session-start", help="SessionStart hook. Reads user.md and the vault state, prints the briefing on stdout.")
    ph_session.set_defaults(func=cmd_hook_session_start)

    ph_send = sub_hook.add_parser("session-end", help="SessionEnd hook. Rebuilds the briefing so the next session opens on today, not on the last time someone ran close-session.")
    ph_send.set_defaults(func=cmd_hook_session_end)

    ph_outward = sub_hook.add_parser("outward-guard", help="PreToolUse on MCP tools. A write into somebody else's system is put to the user rather than done on the way past.")
    ph_outward.set_defaults(func=cmd_hook_outward_guard)

    ph_check = sub_hook.add_parser("checkbox-guard", help="PreToolUse Write|Edit. Refuses any write that adds, removes or ticks a markdown task. Checkboxes are the user's.")
    ph_check.set_defaults(func=cmd_hook_checkbox_guard)

    ph_prose = sub_hook.add_parser("prose-guard", help="PreToolUse Write|Edit. Refuses a dash used as sentence punctuation, a generic AI-marketing phrase, or a leftover placeholder in prose the AI wrote (source: ai-generated or collaborative).")
    ph_prose.set_defaults(func=cmd_hook_prose_guard)

    ph_kind = sub_hook.add_parser("kind-required", help="PreToolUse Write|Edit. Refuses writes into a bundle root without valid kind frontmatter.")
    ph_kind.set_defaults(func=cmd_hook_kind_required)

    ph_perm = sub_hook.add_parser("permission-guard", help="PreToolUse Write|Edit. Hard-blocks writes into the never-do bucket.")
    ph_perm.set_defaults(func=cmd_hook_permission_guard)

    ph_idx = sub_hook.add_parser("index-consistency", help="PostToolUse Write|Edit. Warns when a bundle file is written without being referenced in the bundle INDEX.md.")
    ph_idx.set_defaults(func=cmd_hook_index_consistency)

    ph_dispatch = sub_hook.add_parser("dispatch-guard", help="PreToolUse Agent. Refuses a main-thread expert dispatch that sets run_in_background: false; nested dispatches from inside an expert pass.")
    ph_dispatch.set_defaults(func=cmd_hook_dispatch_guard)

    ph_delete = sub_hook.add_parser("delete-guard", help="PreToolUse Bash. Refuses any command that removes something; discarding goes through `file trash`.")
    ph_delete.set_defaults(func=cmd_hook_delete_guard)

    ph_libcheck = sub_hook.add_parser("library-check-guard", help="PreToolUse Bash. Refuses to save a .pptx into a doing/<slug>/ bundle until `slide-library.py check` has run for that slug.")
    ph_libcheck.set_defaults(func=cmd_hook_library_check_guard)

    # launcher -----
    p_launcher = sub.add_parser("launcher", help="Double-clickable starter for this vault (an .app on macOS, a .lnk on Windows). Callable anytime, not only during setup.")
    sub_launcher = p_launcher.add_subparsers(dest="subcmd", required=True)

    pl_detect = sub_launcher.add_parser("detect-terminals", help="List id/name pairs of terminal apps this machine can start a vault session in, for the caller to offer as a choice.")
    pl_detect.set_defaults(func=cmd_launcher_detect_terminals)

    pl_create = sub_launcher.add_parser("create", help="Build the starter. macOS: an .app under /Applications. Windows: a .lnk on the Desktop (designed, unverified).")
    pl_create.add_argument("vault_root", nargs="?", default=".")
    pl_create.add_argument("--name", required=True, help="Display name for the starter.")
    pl_create.add_argument("--terminal", required=True, help="A terminal id from 'launcher detect-terminals'.")
    pl_create.set_defaults(func=cmd_launcher_create)

    args = parser.parse_args(argv[1:])
    if getattr(args, "cmd", None) == "hook":
        return _run_hook_and_record(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
