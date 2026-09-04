#!/usr/bin/env python3
"""zanmai.py: the single CLI for Zanmai space operations.

Replaces AI-tool-call sequences (Write+Edit+Write+...) with deterministic
state-changes. AI decides (classification, plan); script executes.

Subcommand groups:
    setup, first-time install and validation (init/validate/update)
    snapshot, space snapshots (create)
    bundle, bundle operations (create, add-file, add-truth, rename)
    asset, non-markdown files into the bundle they belong to (add)
    contact, person and organisation contacts (create)
    journal, one entry per day (path, append, read, list)
    file, file moves to system folders (trash, archive)
    plan, plan-section maintenance on bundle truth files (clear-section)
    review, read-once briefings on the desk (archive)
    update, bundle-level index touches (wikilinks, embeds, master-index)
    index, space-index and pattern queries (rebuild, patterns, find, inspect)
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
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ----------------------------------------------------------------------------
# Space folder names. This is the only place they are spelled out.
#
# Every path this file builds starts from one of these names, never from a
# literal typed at the call site. Rename a folder here and a run over an empty
# space carries the new name everywhere, which is what makes a rename a change
# instead of a project: the same string used to sit in some two hundred path
# expressions, and each one was a chance to miss one.
#
# What these do NOT cover is prose. Help texts, hook messages, templates and
# the documentation describe a structure rather than address a file, and a
# renamed folder changes the sentence, not one word inside it. Those are
# rewritten by hand, in the same operation that changes a value here. A value
# changed on its own would ship a space that describes something other than
# what it does.
#
# A folder-shaped word that means something else keeps its literal, and there
# are two kinds of those. `archive` and `trash` are also verbs: `file archive`
# and `file trash` are commands, and the command keeps its name when the folder
# it writes to is renamed. `inbox` is also an ordinary word, one entry in the
# list of generic folder names the naming heuristic ignores, and that list is
# about what people call folders, not about what this space calls its own.
# Neither is this space's folder, so neither moves when a folder moves.
# ----------------------------------------------------------------------------

SYSTEM_DIR = "zanmai"           # what the machine keeps; the user never opens it by hand
HOST_DIR = ".claude"            # what the host reads: skills, agents, settings

# ----------------------------------------------------------------------------
# The areas. Each is defined by what happens to what lies in it, not by what
# kind of thing it is: that is what makes a misfiling visible instead of a
# matter of taste. A desk gets cleared, a filing cabinet does not.
# ----------------------------------------------------------------------------

INBOX_DIR = "inbox"             # where everything lands, however it got there. Empties daily.
# The desk. Only work that has an end belongs here, and the test is a plain one: name the event
# that closes it. "Bathroom finished" is an event, "the flat" is not. Without such an event a
# piece is not a workbench piece and belongs in a room that is not meant to empty.
WORKBENCH_DIR = "workbench"     # where the work happens. The one room that empties.
# What is mine and matters to me now, at work or at home: health, money, family, the flat, the
# car, hobbies, my own role, the team, a standing responsibility. The folders someone keeps open
# rather than a set of categories. The line against the archive is whether I still act on it, and
# the line against knowledge is whether it is mine: the research goes to knowledge, what I do with
# it lives here.
LIFE_DIR = "life"
# What would still be right for someone else. Not everything gathered: what could be looked up
# again or rebuilt from scratch, the way a memory holds a thing you can reproduce. A write-up of
# my own machine is not knowledge, a comparison of the best games for a C64 is.
KNOWLEDGE_DIR = "knowledge"
# The folder in the cupboard, the boxes in the cellar. Not "never needed again": it is kept
# precisely because it is taken out again - an invoice, a policy, a certificate. Nothing is
# actively worked on here, and nothing changes except when something is added or an error turns
# up. Every piece carries a date and a keeping reminder. The reminder reminds; it never deletes,
# nothing is removed without the owner seeing it and saying so.
ARCHIVE_DIR = "archive"
# The one bundle inside `life/` the system knows by name, because four experts read it by path.
# Created empty at setup: without the folder there is nowhere for an approved piece to land, and
# every run starts from nothing again. Measured: a first build of two slides took 26
# minutes and 76 tool calls, the correction of the same two 2.5 minutes and 11, and the only
# difference was that the way was known the second time.
# The brand lives under the system folder, not in the user's own areas. It is read by four
# specialists by path and written by exactly one, so it is machine state with the user's content in
# it rather than material they file. It stayed in `life/` for a while and that split the brand in
# two: the command that counts brands read one place and the specialist who writes them wrote the
# other. Update-immune, so nothing here is ever replaced by a release.

# Inside the system folder.
SYSTEM_MATERIAL_DIR = f"{SYSTEM_DIR}/system"        # distribution, replaced on update
EXTENSIONS_DIR = f"{SYSTEM_DIR}/extensions"
CONNECTIONS_DIR = f"{SYSTEM_DIR}/connections"
MEMORY_DIR = f"{SYSTEM_DIR}/memory"
DESIGN_DIR = f"{SYSTEM_DIR}/design"   # one folder per brand, update-immune, written by the design work
BRANDS_DIR = DESIGN_DIR              # the same place; two names for it split the brand in two once
LOGS_DIR = f"{SYSTEM_DIR}/logs"
HISTORY_DIR = f"{SYSTEM_DIR}/history"       # the snapshot repository, a git dir of its own
RUNTIME_DIR = f"{SYSTEM_DIR}/runtime"
SCRATCH_DIR = f"{SYSTEM_DIR}/temp"          # what the machine puts down mid-job, days
TRASH_DIR = f"{SYSTEM_DIR}/trash"           # what was thrown away, restorable for a month
USER_FILE = f"{SYSTEM_DIR}/user.md"
ACTIVITY_LOG_FILE = f"{MEMORY_DIR}/activity-log.md"

# The AI's own list of what is open. Under the system folder because it is the machine's, not the
# user's: "I do not look at my concierge's notepad to see what he still has to do."
#
# One JSON file plus one markdown page per entry. It was a `.base` folder with a CSV and a schema
# describing table and board views, because an editor rendered those; that editor is gone, and what
# stayed was a 5 KB view definition nobody drew, larger than the 3.7 KB of actual work it described,
# plus a migration step that existed only because a CSV header row drifts when a field is added. In
# JSON a missing field is a default on read, and a broken file fails loudly instead of parsing into
# something wrong. Not a database: twenty rows read and written whole, in a folder that syncs, where
# a binary file is the thing that loses a merge.
OPEN_DIR = f"{SYSTEM_DIR}/open"
WORK_FILE = "open.json"
# Where it used to live. Read once by `setup update` to carry an existing space across, and by
# nothing else.
LEGACY_OPEN_DIR = f"{SYSTEM_DIR}/open.base"

CONTACTS_DIR = "contacts"
PEOPLE_DIR = f"{CONTACTS_DIR}/people"
ORGANISATIONS_DIR = f"{CONTACTS_DIR}/organisations"
CONTACT_FOLDERS = (PEOPLE_DIR, ORGANISATIONS_DIR)

# The journal: the time axis. One entry per day, named by its date, filed under its year: `journal/2026/2026-08-31.md`. There
# used to be four layers with a rollup writing the one above from the one below, and that rollup was
# the only place in the system that wrote into the user's own text without being asked. A month is
# thirty short files and reads in a second, so the summary is a question anybody can ask rather than
# a file somebody has to keep true.
JOURNAL_DIR = "journal"
DAILY_DIR = JOURNAL_DIR

# The one list for what has to be done and belongs to no matter in the space: book a haircut, take
# the tablets at nine, the thing somebody mentioned in passing. In `life/`, because that is the area
# for what is yours and matters now, and loose in it rather than as a bundle of its own, because a
# bundle is a matter and this is a list. A plain file, so it can be edited, sorted and ticked off by
# hand in any editor. A task that does belong to a matter stays in that matter's bundle, next to the
# material it is about; this file is for everything with no such home, which used to be scattered
# across journal days, one line each, in the day it happened to be asked for.
TASKS_FILE = f"{LIFE_DIR}/task.md"


# Schema-required and -optional fields per kind. Sync with schema/frontmatter-v1.yaml.
COMMON_REQUIRED = ("kind", "slug", "created")
COMMON_OPTIONAL = ("updated", "source", "source_detail", "tags", "mentioned_in")
KIND_FIELDS = {
    # The desk. It asks for nothing beyond the common fields on purpose: what clears a bundle off
    # the desk is read from the file dates, not from a field somebody has to keep true.
    "workbench": {"required": (), "optional": ("status", "due")},
    # What is mine and matters now. Nothing is required: a goal and a plain folder of papers both
    # live here, and demanding a goal of the folder of papers would only teach people to write one
    # that means nothing.
    #
    # `cadence` and `last_done` stood here as options and were removed: they could be written and
    # were carried along by every move, and no line of code ever read them. A field that promises a
    # rhythm and reports nothing when the rhythm breaks is worse than no field, because somebody
    # fills it in and believes the space is watching. Nothing in any space had one.
    "life": {"required": (), "optional": ("goal", "status", "due")},
    "knowledge": {"required": (), "optional": ("topic", "status")},
    # Something kept. Nothing is required beyond the common fields, and that is deliberate: a scan
    # that arrives before anyone has worked out what it is still has to be filable. What gives it a
    # keeping reminder is `retention_policy`, and that is set once somebody knows.
    "archive": {"required": (), "optional": ("doc_type", "lifecycle", "retention_policy",
                                             "retention_until", "relates_to", "relates_via",
                                             "source_path", "status", "due")},
    "contact/person": {"required": (), "optional": ("nickname", "role", "org", "email", "phone", "birthday", "address", "website")},
    "contact/organization": {"required": (), "optional": ("kind_of", "website")},
}

# Where a kept document stands. Not a document type and not a folder: the same policy can hold a
# contract and a receipt, and the same contract moves between these as time passes. The bucket is
# what decides whether the thing may go, so it is the load-bearing field, not `doc_type`.
RECORD_LIFECYCLE = {
    "active": "the underlying matter is still in effect; nothing expires while it is",
    "retention-bound": "a law or a contract says how long this has to stay",
    "evidence-only": "no duty, but it proves something worth proving: a warranty, a repair history",
    "expired": "its term has run out; it may go, and going is still a decision somebody makes",
}

# How long a document stays. Three buckets and nothing else. An earlier version had five rules for
# computing a date from a contract end, an ownership period or a matter still running, which is
# five ways of asking somebody to work out a figure nobody will ever check. The only question put
# to a document is whether it can go yet, and disks are cheap while a missing paper is not: so
# anything a real rule would put at one or two years sits in `four-years`, and anything a real rule
# would put beyond ten sits in `forever`, because past ten years the difference is theoretical.
# The categories are not typed out here. They come from the shipped suggestions, and in a space that
# has confirmed its own terms they come from those. A list in the code beside a file that claims to
# hold the same thing is the shape that fails: one space carried a category its user had added, the
# filing command could not offer it, and the entry sat in the file doing nothing.
def _record_retention() -> dict:
    """Category to its reason, from the shipped suggestions."""
    daten = _retention_defaults()
    return {str(e.get("category")): str(e.get("why") or "")
            for e in daten.get("terms", []) if e.get("category")}


def _retention_categories(space: Path) -> list[str]:
    """What this space may set as a term: its own confirmed ones, else the shipped suggestions."""
    eigen = _retention(space)
    quelle = eigen or _retention_defaults()
    return [str(e["category"]) for e in quelle.get("terms", []) if e.get("category")]

# How one document relates to another. A closed vocabulary, because the point of naming a relation
# is that it can be asked about: which invoice paid this, what cancelled that, which version this
# replaced. An open list of free text answers none of those.
RECORD_RELATIONS = {
    "pays": "settles an invoice, a contract or a service",
    "cancels": "ends the thing it points at",
    "confirms": "acknowledges an action taken earlier",
    "amends": "changes the thing it points at without replacing it",
    "replaces": "supersedes an earlier version",
    "references": "mentions it, with no causal role",
    "part-of": "belongs to the same matter, without a specific role",
}


# What `status:` may say, and what each value does to the rest of the system.
#
# The field already existed, but it meant something different per kind and nothing checked the
# value, so it could say anything and nobody could act on it. These four are the lifecycle answers
# every kind shares: does this still stand. `cancelled` and `done` take a file's open task lines
# and its dates out of what the session start offers, which is the whole point of the field.
#
# The kind-specific values below them stay valid because they say where inside `active` something
# sits, not whether it stands at all. A file carrying one of those is treated as active.
STATUS_LIFECYCLE = {
    "active": "runs, and its open points are current",
    "waiting": "deliberately parked on something outside; give `due:` for when it comes back",
    "done": "finished; open points on it are history, not work",
    "cancelled": "does not happen any more; open points on it are void",
    "unclear": "seen but not settled; somebody has to look at it",
}
# Values a kind used before this field had a vocabulary. They all mean some flavour of active.
STATUS_KIND_SPECIFIC = ("planning", "wrap-up", "awaiting-archive")
STATUS_VALUES = tuple(STATUS_LIFECYCLE) + STATUS_KIND_SPECIFIC
# The two that silence a file: its task lines and its dates stop being offered at session start.
STATUS_CLOSED = ("done", "cancelled")


# A kind whose folder is not simply its own name. Empty since every room and the kind that lives in
# it carry the same word. The map stays because the check below needs somewhere to look, and because
# the next kind that differs has a place to be written down instead of being remembered: twice a
# kind was added and its mapping was not, and both times a folder in the singular sat next to the
# real one, filled, while everything that reads the space looked in the plural.
KIND_FOLDERS: dict[str, str] = {}
BUNDLE_KINDS = ("workbench", "life", "knowledge", "archive")
# Kinds that deliberately have no root folder of their own: a contact is a single file under
# `contacts/`, never a bundle. Listed so the check can tell "no folder" from "folder forgotten".
FOLDERLESS_KINDS = ("contact/person", "contact/organization")
# Kinds that exist as a bundle but are not opened with `bundle create`, because their own command
# does more than make a folder. Naming the command in the refusal is the whole point: a bare "not
# allowed" sends the next run looking for a way around instead of to the door that is open.
KINDS_WITH_OWN_COMMAND = {
    "archive": "A matter is opened with `archive matter new`, which also gives it its chronology "
               "and its counterparty.",
}


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


def _check_kind_folders() -> None:
    """Every kind either has a real root folder or is on the list of those that have none.

    Twice now a kind was added and its folder mapping was not, and both times the result was a
    folder in the singular sitting next to the real one, filled, while everything that reads the
    space looked in the plural. A map that has to be remembered is not a safeguard; failing at
    import time is. This costs one dict lookup per kind at startup.
    """
    fehlend = [k for k in KIND_FIELDS
               if k not in FOLDERLESS_KINDS and _kind_folder(k) not in USER_ROOTS]
    if fehlend:
        raise SystemExit(
            f"zanmai.py is inconsistent with itself: kind(s) {', '.join(fehlend)} map to a folder "
            f"that is not a space root. Add the mapping to KIND_FOLDERS, or the kind to "
            f"FOLDERLESS_KINDS where it is not meant to have a folder.")


def _space_mkdir(space: Path, ziel: Path, **kw) -> None:
    """Create a directory inside the space, refusing to invent a new root folder.

    The space has nine user folders and they are the whole list. Twice a write path was built from
    data, once from a kind value and once from a routing target, and each time it created a folder
    in the singular next to the real one: filled, invisible to everything that reads the space, and
    only noticed because a person saw it in the sidebar. Both times the code was correct in its own
    terms, and both times the wrong folder appeared anyway, because nothing checked the one thing
    that matters, which is whether the path lands somewhere that exists. So the check sits here,
    where the directory is actually made, and it fails loudly instead of building quietly.
    """
    try:
        rel = ziel.resolve().relative_to(space.resolve())
    except (ValueError, OSError):
        ziel.mkdir(**kw)      # outside the space: not this function's business
        return
    # A dotted folder at the root is somebody else's business by design, the host config, the
    # editor, git. The failure this guards against is a visible folder next to a visible folder.
    if (rel.parts and not rel.parts[0].startswith(".")
            and rel.parts[0] not in _SPACE_ROOT_ALLOWED_DIRS):
        raise SystemExit(
            f"fail: {rel.parts[0]}/ is not a folder this space has, so nothing was created. The "
            f"space's folders are: {', '.join(sorted(_SPACE_ROOT_ALLOWED_DIRS))}. A path that "
            f"lands anywhere else is a bug in whatever built it, not a folder to add.")
    ziel.mkdir(**kw)


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
    WORKBENCH_DIR,
    LIFE_DIR,
    KNOWLEDGE_DIR,
    ARCHIVE_DIR,
    CONTACTS_DIR,
)

_check_kind_folders()



def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _timestamp_log() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


_UMLAUT_MAP = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}


# German words written without their umlauts, in the shape a keyboard-shy run produces: `fuer`,
# `zurueck`, `naechste`. Only words that exist in no other language this way, so a match is a match
# and never a guess. A slug may be spelled like this, a file name may be; a sentence the user reads
# back may not, and that is the whole distinction this list carries.
#
# It exists because text entered through a command is text somebody typed under quoting pressure,
# and the shell is where umlauts get dropped for convenience. The space then shows that sentence
# back at every session start, in the user's own language, misspelled, and nothing ever corrects it
# because nothing ever looks. A word list is deterministic; asking a run to remember is not.
_OHNE_UMLAUT = (
    "fuer", "dafuer", "hierfuer", "wofuer", "ueber", "darueber", "gegenueber", "ueberhaupt",
    "zurueck", "natuerlich", "moeglich", "unmoeglich", "moeglichkeit", "noetig", "spaeter",
    "naechste", "naechsten", "naechster", "haeufig", "taeglich", "waehrend", "waehlen",
    "auswaehlen", "gewaehlt", "koennen", "koennte", "koennten", "moechte", "moechten",
    "muessen", "muesste", "duerfen", "duerfte", "gehoert", "hoeren", "erklaeren", "aendern",
    "geaendert", "aenderung", "loeschen", "geloescht", "pruefen", "ueberpruefen", "fuehren",
    "gefuehrt", "einfuehren", "durchfuehren", "buendel", "ausloeser", "groesse", "groesser",
    "stueck", "zurueckgeben", "verfuegbar", "beduerfnis", "ueblich", "schliesslich",
)
_OHNE_UMLAUT_RE = re.compile(r"\b(" + "|".join(_OHNE_UMLAUT) + r")\b", re.IGNORECASE)


def _umlaut_verlust(text: str) -> list[str]:
    """German words in this text that lost their umlauts. Empty where there are none."""
    return sorted({m.group(0) for m in _OHNE_UMLAUT_RE.finditer(text or "")})


def _refuse_umlaut_verlust(text: str, feld: str) -> str:
    """The refusal for text the user will read back, or "" where the text is fine."""
    treffer = _umlaut_verlust(text)
    if not treffer:
        return ""
    return (f"fail: {feld} carries German words without their umlauts: {', '.join(treffer)}. "
            f"This text is shown back to the user, in their own language, so it is spelled the way "
            f"they write it. Quote the argument and type the umlauts.")


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


def _resolve_bundle_dir(space: Path, bundle_slug: str, bundle_kind: str | None) -> tuple[Path | None, str | None, str]:
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
        candidate = space / _kind_folder(bundle_kind) / Path(*segments)
        return (candidate if candidate.is_dir() else None), bundle_kind, leaf

    for folder in BUNDLE_FOLDERS:
        candidate = space / folder / Path(*segments)
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


def _append_activity_log(space: Path, agent: str, what: str) -> None:
    log = space / MEMORY_DIR / "activity-log.md"
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
    candidates = ["## Files in this bundle", "## Knowledge", "## Life", "## Workbench"]
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
INDEX_TRUTH_DESCRIPTION = "the bundle's main file"


def _render_bundle_index(*, slug: str, title: str, bundle_kind: str = "knowledge",
                         is_sub_bundle: bool = False,
                         heading_files: str = INDEX_HEADING_FILES,
                         heading_activity: str = INDEX_HEADING_ACTIVITY,
                         truth_description: str = INDEX_TRUTH_DESCRIPTION) -> str:
    # INDEX inherits the bundle's kind so it stays consistent with the path.
    # The schema does not require goal or status on INDEX files. The
    # kind-required hook exempts INDEX.md from the required-field check.
    #
    # The two headings are passed in because this file is the user's, and a space
    # written in one language does not want two English headings in the middle of it.
    # The script cannot know the language, and a table of translations here would grow
    # with every language Zanmai meets, so the caller supplies the words; English is
    # the default for a caller that has nothing better.
    #
    # The line under the heading takes the same treatment, and it was missed the first time: a
    # caller that passed a German heading got a German heading with an English sentence directly
    # below it. Whatever is written into the user's file is the caller's to word.
    fm = {"kind": bundle_kind, "slug": "index", "created": _today(), "source": "ai-generated"}
    if is_sub_bundle:
        # No claim here about whether a truth file exists. It used to say there was
        # none, which `bundle add-truth` then made false without correcting it, and
        # that is the documented path for a sub-bundle with its own identity.
        return _render_frontmatter(fm, list(fm.keys())) + (
            f"\n# {title}, index\n\n"
            f"## {heading_files}\n\n"
            f"## {heading_activity}\n\n"
        )
    return _render_frontmatter(fm, list(fm.keys())) + (
        f"\n# {title}, index\n\n"
        f"## {heading_files}\n\n"
        f"- [[{slug}]]: {truth_description}\n\n"
        f"## {heading_activity}\n\n"
    )


# A bundle is a place things accumulate, and its name has to leave room for the second thing. Three
# words in a row is where a name stops being a subject and starts being the occasion that produced
# the first file: `ki-coding-workflows` instead of `ai`, `italien-suedliche-regionen-september`
# instead of `italien`. A bundle cut that tight can only ever hold the one file that named it, which
# is why the empty-bundle finding exists at the other end of the same mistake. The file may be as
# specific as it likes; the folder around it may not.
#
# Two words pass, because plenty of real subjects are two (`back-training`, `home-office`). A
# deliberately narrow name is still available, it just has to be said out loud with `--narrow`,
# which is the difference between a decision and a habit.
_BUNDLE_NAME_WORTE = 2


def _zu_enger_bundle_name(slug: str) -> str | None:
    """The broader name this slug is hiding, or None where the slug is already a subject.

    The head of the name is what stays: `ki-coding-workflows` is about `ki`, and `travel-italy-2026`
    is about `travel`. Returning it lets the refusal name the alternative instead of asking the
    caller to guess what "broader" means.
    """
    worte = [w for w in slug.split("-") if w]
    if len(worte) <= _BUNDLE_NAME_WORTE:
        return None
    return worte[0]


def cmd_create_bundle(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
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
    if kind not in BUNDLE_KINDS:
        print(f"fail: {kind} is not a bundle kind.", file=sys.stderr)
        return 1
    if kind in KINDS_WITH_OWN_COMMAND:
        print(f"fail: a {kind} bundle is not created here. {KINDS_WITH_OWN_COMMAND[kind]}",
              file=sys.stderr)
        return 1
    # Sub-bundle slugs are allowed via "/" (e.g. "computer/clippings"). Each
    # path segment is slugified independently; the last segment is the bundle slug.
    segments, slug = _slugify_bundle_path(args.slug)
    if not segments:
        print(f"fail: empty slug", file=sys.stderr)
        return 1
    breiter = None if getattr(args, "narrow", False) else _zu_enger_bundle_name(slug)
    if breiter:
        print(f"fail: '{slug}' names the occasion, not the subject, so nothing else will ever fit "
              f"in it and it stays a folder around one file. '{breiter}' is the subject here; "
              f"the file keeps the long name. Check what is already there first "
              f"(`index find --tokens {breiter}`), then either create '{breiter}' or, where the "
              f"narrow cut is really what is wanted, say so with --narrow.", file=sys.stderr)
        return 1
    folder = _kind_folder(kind)
    bundle_dir = space / folder / Path(*segments)
    if bundle_dir.exists():
        print(f"fail: bundle already exists: {bundle_dir}", file=sys.stderr)
        return 1
    _space_mkdir(space, bundle_dir, parents=True)
    bundle_rel = f"{folder}/{'/'.join(segments)}"
    is_sub_bundle = len(segments) > 1

    additions: dict = {"_title": args.title or slug.replace("-", " ").title()}
    for key in ("source", "source_detail", "goal", "status", "due", "topic"):
        v = getattr(args, key, None)
        if v:
            additions[key] = v
    tags = _tags_arg(getattr(args, "tags", None))
    if tags:
        additions["tags"] = tags

    # Sub-bundles get no truth file from this command by default. Two shapes
    # coexist:
    #   - Organisational sub-folder: container for loose items of a narrow
    #     shape inside the parent bundle. The parent's truth carries the
    #     matter; the sub-folder is just a grouping. Stays as-is (no truth).
    #   - Thematic sub-bundle: the sub-bundle has its own identity. Add the
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
            truth_description=(getattr(args, "truth_description", None) or INDEX_TRUTH_DESCRIPTION),
        ),
        encoding="utf-8",
    )

    _append_activity_log(space, "zanmai.py", f"created bundle {bundle_rel}/")
    _update_master_index(space)

    print(f"ok: bundle created at {bundle_rel}/")
    # What already exists, at the moment a new one is made. Filing happens one folder at a time and
    # each one looks right on its own; the shape nobody chose appears between them, and by the time
    # anybody notices there are four bundles for one matter. The names are printed across every
    # area, not just the one being written to, because the same matter often already has a home
    # somewhere else. Nothing is refused and nothing is proposed here: the list is the whole point,
    # and reading it is the job of whoever asked for the bundle.
    if not is_sub_bundle:
        # From one upwards here, not from two as in the sweep. An area holding a single bundle is
        # often exactly the home being looked for: research about travel sits alone in knowledge
        # while the trips pile up in life, and a threshold of two hides precisely that.
        for zeile in _area_shape(space, ab=1):
            print(f"  {zeile}")
    # A sub-bundle with an identity of its own needs a truth file, and two runs on two different days
    # created one, found it missing and reached for `bundle add-truth` afterwards. Doing it here
    # spares the second call; saying so spares the search for why the folder looks half-built.
    if is_sub_bundle and getattr(args, "truth", False):
        return cmd_create_sub_bundle_truth(argparse.Namespace(
            space=str(space), kind=kind, bundle_slug=args.slug, title=args.title,
            **{k: getattr(args, k, None)
               for k in ("goal", "status", "due", "topic")}))
    if is_sub_bundle:
        print(f"note: no truth file, because a sub-bundle is a grouping unless it carries a matter of its own "
              f"of its own. Where it does, `bundle create --truth` writes one in the same call, or "
              f"`bundle add-truth --kind {kind} --bundle-slug {args.slug}` adds it now.")
    return 0


def cmd_copy_into_bundle(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_file():
        print(f"fail: source not a file: {source}", file=sys.stderr)
        return 1

    bundle_dir, bundle_kind, leaf_slug = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
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
    _clear_inbox_source(space, source, target)

    bundle_rel = target.parent.relative_to(space).as_posix()
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
        space, "zanmai.py",
        f"copied {source.name} into {bundle_rel}/ (body verbatim, "
        f"frontmatter migrated, {len(leftover)} non-schema field(s) moved to body)"
    )

    print(f"ok: copied to {target.relative_to(space)}")
    return 0


def _clear_inbox_source(space: Path, source: Path, target: Path) -> None:
    """Take a file out of the inbox once its content is filed, and say so.

    The inbox is the one area whose whole purpose is to become empty, and until now nothing emptied
    it: filing copied the file into its bundle and left the original lying there. The next session
    found it waiting again, worked it a second time, and the day after that a third. There is no
    time limit here and there should not be one, because the question is not how old the file is,
    it is whether its content has arrived.

    **Leaving is moving, not deleting**, and which of the two exits a file takes is a question about
    the file rather than about tidiness: does it still carry something the result does not? A scanned
    invoice does, so it goes to the matter it belongs to and lives there. A voice note saying "put
    this on my list" does not, so it goes to the trash once the task exists. The run decides that by
    reading; where the user has answered it once for a kind of file, the answer is in their routing
    rule as `keep` and nobody is asked twice.

    Nothing is deleted either way: the trash is restorable for thirty days, with the line in the log
    saying where the content went.
    """
    try:
        rel = source.resolve().relative_to(space.resolve()).as_posix()
    except ValueError:
        return  # came from outside the space; nothing of ours to clear
    if not rel.startswith(f"{INBOX_DIR}/"):
        return
    ziel_rel = target.relative_to(space).as_posix()
    # Where the file itself is still wanted, its home is beside what was made from it. Filing has
    # usually put a copy there already, and then the one in the inbox is a second file that will
    # drift from the first. Where it has not, this moves the file rather than discarding it, so a
    # step that forgot to carry the original cannot lose it. Asked before the gate below, because
    # that gate wants a destination that already holds the content, and here the file being moved
    # is what arrives there.
    quell_regel = _route_for_file(space, source)
    behalten = str(quell_regel.get("keep") or "").lower()
    ziel_ordner = target.parent if target.suffix else target
    if behalten == "with-result" and not (ziel_ordner / source.name).exists():
        ziel_ordner.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(ziel_ordner / source.name))
        neu_rel = (ziel_ordner / source.name).relative_to(space).as_posix()
        _append_activity_log(space, "zanmai.py", f"moved {rel} to {neu_rel} (kept with its result)")
        print(f"ok: {rel} left {INBOX_DIR}/ and now sits with its result at {neu_rel}")
        _routing_learn_keep(space, quell_regel, "with-result")
        return
    _grund, fehler = _import_exit(space, ziel_rel, source)
    if fehler:
        print(f"note: {rel} stays in {INBOX_DIR}/. {fehler.removeprefix('fail: ')}", file=sys.stderr)
        return
    if _move_into(space, source, TRASH_DIR, "trashed", dated=True, filed_to=ziel_rel) == 0:
        print(f"ok: {rel} left {INBOX_DIR}/, its content is at {ziel_rel}")


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
    space = Path(args.space).resolve()
    source = Path(args.source).resolve()

    bundle_dir, _kind, _leaf = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
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
    _clear_inbox_source(space, source, target)

    # Record any rename (original -> final) so `update embeds` can resolve
    # plan-driven attachment renames automatically. Stable across import waves
    # until cleared via `update embeds --clear-rename-map`.
    if target.name != source.name:
        _record_rename(space, source.name, target.name)

    rel = target.relative_to(space).as_posix()
    _append_activity_log(space, "zanmai.py", f"attachment {target.name} -> {rel}")
    print(f"ok: attachment at {rel}")
    return 0


def _update_master_index(space: Path) -> None:
    """Regenerate space-root INDEX.md from existing bundles."""
    master = space / "INDEX.md"
    if not master.exists():
        return
    text = master.read_text(encoding="utf-8")

    def list_contacts(sub: str) -> list[str]:
        contacts_dir = space / CONTACTS_DIR / sub
        if not contacts_dir.is_dir():
            return []
        return sorted(p.stem for p in contacts_dir.iterdir() if p.is_file() and p.suffix == ".md")

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
        root = space / folder
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

    def render_grouped(header: str, folder: str, intro: str) -> str:
        """Every bundle in an area, with whatever sits inside it listed under it.

        Both levels appear, because both exist: an area holds bundles directly and a bundle may
        hold bundles. Listing only the inner level hid every bundle without a sub-bundle, which
        after setup is most of them, and the index then reported an area as empty while it held
        four folders. The outer name is a link rather than a bold label for the same reason: it is
        a bundle with a page of its own, not a drawer.
        """
        root = space / folder
        lines = [f"## {header}", "", intro, ""]
        if not root.is_dir():
            return "\n".join(lines + ["(empty)"]) + "\n"
        etwas = False
        for bereich in sorted(p for p in root.iterdir() if p.is_dir()):
            etwas = True
            lines.append(f"- [[{bereich.name}]]")
            lines += [f"  - [[{s}]]" for s in sorted(s.name for s in bereich.iterdir() if s.is_dir())]
        lose = sorted(s.stem for s in root.iterdir()
                      if s.is_file() and s.suffix == ".md" and s.stem != "INDEX")
        if lose:
            etwas = True
            lines += [f"- [[{s}]]" for s in lose]
        if not etwas:
            lines.append("(empty)")
        return "\n".join(lines).rstrip() + "\n"

    new_workbench = render_flat_root(
        "Workbench", WORKBENCH_DIR,
        "The desk: work that has an end, with every draft of it together in one bundle. If you "
        "cannot name the event that finishes a piece, it does not belong here. You put things here "
        f"and so does Zanmai. See `{WORKBENCH_DIR}/`.")
    new_life = render_grouped(
        "Life", LIFE_DIR,
        "What is yours and matters to you now, at work or at home. The research goes to knowledge; "
        f"what you do with it lives here. See `{LIFE_DIR}/`.")
    new_knowledge = render_grouped(
        "Knowledge", KNOWLEDGE_DIR,
        "What would still be right for someone else: what you could look up again or rebuild from "
        f"scratch. See `{KNOWLEDGE_DIR}/`.")
    new_archive = render_grouped(
        "Archive", ARCHIVE_DIR,
        "The folder in the cupboard: kept because you take it out again. Each piece carries a date "
        f"and a keeping reminder, and nothing goes without you saying so. See `{ARCHIVE_DIR}/`.")
    new_contacts = render_contacts()

    # Each section is replaced up to the next heading, so the order here is the order in the file
    # that `_render_master_index` writes. A section whose successor heading is missing is left
    # alone rather than swallowing the rest of the file.
    for pattern, replacement in (
        (r"## Workbench\n.*?(?=\n## Life)", new_workbench),
        (r"## Life\n.*?(?=\n## Knowledge)", new_life),
        (r"## Knowledge\n.*?(?=\n## Archive)", new_knowledge),
        (r"## Archive\n.*?(?=\n## Contacts)", new_archive),
        (r"## Contacts\n.*?(?=\n## Inbox)", new_contacts),
    ):
        text = re.sub(pattern, replacement + "\n", text, flags=re.DOTALL)

    master.write_text(text, encoding="utf-8")


def cmd_update_master_index(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    _update_master_index(space)
    _append_activity_log(space, "zanmai.py", "master INDEX.md regenerated from existing bundles")
    print("ok: master INDEX updated")
    return 0


# Hard-exclude paths for all wikilink operations (write-time sweep AND
# read-time aggregation). These paths hold content that must not be mutated
# retroactively (sweeps) and must not surface as user-space "issues"
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
    f"{INBOX_DIR}/",
    f"{TRASH_DIR}/",
    f"{ARCHIVE_DIR}/",
)
_WIKILINK_OPS_EXCLUDED_FILES = (
    ACTIVITY_LOG_FILE,
)


def _is_excluded_from_wikilink_ops(rel_path: str) -> bool:
    """True if a space-relative path must not be touched by wikilink sweeps
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

    Scope: defaults to the whole space, because the user's material is no longer under one folder.
    Pass `--scope <path>` to narrow it. Hard-excluded paths (see
    `_WIKILINK_OPS_EXCLUDED_PREFIXES` and `_WIKILINK_OPS_EXCLUDED_FILES`) are never rewritten
    regardless of the requested scope: the history, the logs, the activity log, the trash, the
    archive and the import folder must stay verbatim.
    """
    space = Path(args.space).resolve()
    old_slug = args.old.strip()
    new_slug = args.new.strip()
    if not old_slug or not new_slug:
        print("fail: --old and --new must both be non-empty", file=sys.stderr)
        return 1
    if old_slug == new_slug:
        print("ok: nothing to do (old == new)")
        return 0

    scope_root = space / args.scope if args.scope else space
    if not scope_root.exists():
        print(f"fail: scope does not exist: {scope_root}", file=sys.stderr)
        return 1

    pattern = re.compile(r"\[\[" + re.escape(old_slug) + r"(\|[^\]]*)?\]\]")
    files_touched: list[str] = []
    occurrences = 0

    for md in scope_root.rglob("*.md"):
        rel = md.relative_to(space).as_posix()
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
        space, "zanmai.py",
        f"wikilink rename [[{old_slug}]] -> [[{new_slug}]] "
        f"({occurrences} occurrence(s) in {len(files_touched)} file(s))"
    )
    # The file list is on stdout only when it was asked for. It used to print always, and what a
    # command prints is what gets read out loud: a person asking for one rename was handed the
    # paths of every file that happened to mention it, which is the machine's bookkeeping and not
    # an answer. The count is the answer. The paths stay available for a run that has to check.
    if args.verbose and files_touched:
        for f in files_touched:
            print(f"  {f}")
    # Called as a step inside a rename, the count is that step's bookkeeping and the rename says the
    # result once. Two success lines for one operation is how a technical one ends up being read out.
    if not getattr(args, "quiet", False):
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
    space = Path(args.space).resolve()
    target = _resolve_space_file(space, args.file)
    if target is None:
        print(f"fail: no such file in the space: {args.file}", file=sys.stderr)
        return 1
    new_body = (Path(args.body_file).read_text(encoding="utf-8")
                if args.body_file else sys.stdin.read())
    text = target.read_text(encoding="utf-8")
    fm, order, old_body = _split_frontmatter(text)
    if not fm:
        print(f"fail: {target.relative_to(space)} has no frontmatter; refusing to write a body into it",
              file=sys.stderr)
        return 1
    meaningful = [ln for ln in old_body.splitlines() if ln.strip() and not ln.startswith("#")]
    if meaningful and not args.replace:
        print(f"fail: {target.relative_to(space)} already has {len(meaningful)} line(s) of body. "
              f"Pass --replace to overwrite, and be sure it is not the user's own writing.",
              file=sys.stderr)
        return 1
    if not new_body.startswith("\n"):
        new_body = "\n" + new_body
    target.write_text(_render_frontmatter(fm, order) + new_body.rstrip() + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"wrote body of {target.relative_to(space)} "
                         f"({len(meaningful)} line(s) replaced, {len(new_body.splitlines())} written)")
    print(f"ok: body written to {target.relative_to(space)} "
          f"({len(meaningful)} line(s) replaced, {len(new_body.splitlines())} written)")
    return 0


def cmd_bundle_edit_file(args: argparse.Namespace) -> int:
    """Correct frontmatter fields of an existing file in place. Body untouched."""
    space = Path(args.space).resolve()
    target = _resolve_space_file(space, args.file)
    if target is None:
        print(f"fail: no such file in the space: {args.file}", file=sys.stderr)
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
        _append_activity_log(space, args.agent or "zanmai.py",
                             f"edited frontmatter of {target.relative_to(space)} ({changed} field(s))")
    print(f"ok: {changed} of {len(sets) + len(args.remove or [])} requested field(s) changed "
          f"in {target.relative_to(space)}")
    return 1 if notes and not changed else 0


def cmd_contact_update(args: argparse.Namespace) -> int:
    """Enrich an existing contact: set frontmatter fields, optionally append body lines.

    The path a stub takes from auto-created to filled in. Appending never rewrites
    what is already in the body.
    """
    space = Path(args.space).resolve()
    candidates = [space / folder / f"{args.slug}.md" for folder in CONTACT_FOLDERS]
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
        _append_activity_log(space, args.agent or "zanmai.py",
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
# space after three days of use, one agent's lessons had reached 48 KB across 42
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


# A rule written as a bullet under a `## ` heading, which is what `general.md` is made of. The
# dated-entry reader below sees four headings there and nothing else, so the file that grows fastest
# was the one file the curation could not read: 21 rules in four weeks, four of them saying the same
# thing, one of them stating in its own text that it refines an earlier one and standing next to it
# anyway.
_REGEL_BULLET = re.compile(r"^- \*\*(?P<kopf>.+?)\*\*(?P<rest>.*)$")

# Words that mark a sentence as being about now rather than about always. A memory entry carrying
# one of these was a situation, not a rule: "the dev session is here today" became the standing rule
# "every guard refusal is reported to the dev session", and the word "today" was in the sentence.
# Kept to the unmistakable ones. Words like "jetzt" and "gerade" appear in ordinary prose and
# flagging those turns the report into noise, which is how a check stops being read.
_LAGE_WOERTER = ("heute", "für diesen lauf", "in dieser sitzung", "diesmal", "vorerst",
                 "today", "for this run", "this session", "for now", "for today")
# A calendar date or a running instance's own name in a rule is the same failure by another
# route: both tie a supposedly standing rule to one moment or one machine. "Stand 2026-09-02" and
# "dev0602" read as precise, which is exactly what let them slip past a word list built for vaguer
# phrasing like "heute".
_MEMORY_RULE_DATE_RE = re.compile(r"\b(?:stand|as of)\s+\d{4}-\d{2}-\d{2}\b", re.IGNORECASE)
_MEMORY_RULE_INSTANCE_RE = re.compile(r"\bdev\d+\b", re.IGNORECASE)


def _regel_eintraege(text: str) -> list[tuple[str, str, str]]:
    """(section, headline, full line) for every rule written as a bullet."""
    treffer: list[tuple[str, str, str]] = []
    abschnitt = ""
    for zeile in text.splitlines():
        if zeile.startswith("## "):
            abschnitt = zeile[3:].strip()
            continue
        passt = _REGEL_BULLET.match(zeile)
        if passt:
            treffer.append((abschnitt, passt.group("kopf").strip(), zeile))
    return treffer


def _regel_woerter(text: str) -> set[str]:
    """The words of a rule that carry its meaning, for comparing two wordings of one rule."""
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 5}


_REGEL_GLEICH = 0.6   # how much of the shorter headline has to appear in the longer one
_REGEL_MIN_WOERTER = 4  # below this a headline is too short for the overlap to mean anything
# When a rules file is worth reading through. Not a limit and nothing is dropped at it: it is the
# point where nobody reads the file as a whole any more, and unread rules are the same as absent
# ones. A live space reached 21 in four weeks.
_REGELN_MARKE = 20


def _regel_doppelungen(eintraege: list[tuple[str, str, str]]) -> list[tuple[str, str, float]]:
    """Pairs of rules worded so alike that one of them is redundant, most alike first.

    Compared on the headline rather than the whole entry, because the body carries the example and
    two entries about one rule cite different examples.

    What this finds is a repetition, not a contradiction and not a rule stated twice in different
    words. Four entries in a live space said "do not act unasked" in four vocabularies, and no
    amount of word counting reaches that: it is a judgement about meaning and it belongs to the
    close, which is why the count below exists to trigger a reading rather than to replace it.
    """
    paare: list[tuple[str, str, float]] = []
    # Short headlines are left out rather than compared. With three meaningful words in one, a
    # single word in common already reads as half the rule, and a report of coincidences is a
    # report nobody opens twice: "do not judge, collect" came back paired with "text to copy goes
    # to VimR as .txt" at 50 per cent.
    woerter = [(kopf, _regel_woerter(kopf)) for _abschnitt, kopf, _zeile in eintraege]
    woerter = [(kopf, w) for kopf, w in woerter if len(w) >= _REGEL_MIN_WOERTER]
    for i, (kopf_a, wa) in enumerate(woerter):
        for kopf_b, wb in woerter[i + 1:]:
            anteil = len(wa & wb) / min(len(wa), len(wb))
            if anteil >= _REGEL_GLEICH:
                paare.append((kopf_a, kopf_b, anteil))
    return sorted(paare, key=lambda p: p[2], reverse=True)


def _lage_statt_regel(eintraege: list[tuple[str, str, str]]) -> list[str]:
    """Rules whose own wording says they are about a moment rather than about always."""
    treffer = []
    for _abschnitt, kopf, zeile in eintraege:
        klein = zeile.lower()
        if any(w in klein for w in _LAGE_WOERTER):
            treffer.append(kopf)
    return treffer


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
    space = Path(args.space).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = space / args.file
    if not source.is_file():
        print(f"fail: no such memory file: {args.file}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8")

    # The bullet pass runs on every file, before the dated-entry pass, because it is the one that
    # reads `general.md` at all. It reports and changes nothing: a merge is a judgement.
    regeln = _regel_eintraege(text)
    if regeln:
        doppel = _regel_doppelungen(regeln)
        lage = _lage_statt_regel(regeln)
        zeichen = sum(len(z) for _a, _k, z in regeln)
        print(f"rules as bullets: {len(regeln)}, {zeichen} characters")
        # The number is the point. Every one of these is read on every dispatch that touches this
        # file, so a file that only grows is a cost that only grows. Past the mark it is worth
        # reading the whole thing once and merging what says the same thing twice, which no script
        # can decide for you.
        if len(regeln) > _REGELN_MARKE:
            print(f"  over {_REGELN_MARKE} rules. Read the file through once and merge what repeats: "
                  f"a rule that refines an earlier one replaces it, it does not stand beside it.")
        if doppel:
            print(f"  {len(doppel)} pair(s) that look like the same rule twice. Merge them by hand: "
                  f"keep one wording, delete the other, and where one refines the other say so in "
                  f"the one that stays.")
            for a, b, anteil in doppel[:10]:
                print(f"    {anteil:.0%}  {a[:60]}")
                print(f"          {b[:60]}")
        if lage:
            print(f"  {len(lage)} entry/entries word themselves as being about a moment, not about "
                  f"always. A situation is not a rule; check each one and strike what has passed:")
            for kopf in lage[:10]:
                print(f"    {kopf[:70]}")
        if not doppel and not lage:
            # Said plainly, because "nothing found" reads as "nothing there". What this pass sees
            # is repeated wording and words like "today". Four entries in a live space said "do not
            # act unasked" in four vocabularies and none of them said "today"; no count reaches
            # either. Reading the file is what reaches them.
            print("  no repeated wording and no time words. That is not the same as no repetition: "
                  "two rules saying one thing in different words are found by reading, not counting.")

    preamble, entries = _split_lesson_entries(text)
    if not entries:
        print(f"ok: {source.relative_to(space)} has no dated entries, nothing to curate "
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
        _append_activity_log(space, args.agent or "zanmai.py",
                             f"curated {source.relative_to(space)} "
                             f"({moved_out} struck moved out, {trimmed} reasoning block(s) archived)")

    before = len(text.splitlines())
    after = len(source.read_text(encoding="utf-8").splitlines()) if not args.dry_run else before
    print(f"ok: {source.relative_to(space)}: {len(entries)} entry/entries, {len(kept)} still stand, "
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
    space = Path(args.space).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = space / args.file
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
        print(f"ok: nothing older than {cutoff} in {source.relative_to(space)} "
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
        _append_activity_log(space, "zanmai.py",
                             f"rotated {source.relative_to(space)} ({len(old)} month(s) archived)")
    moved = sum(len(ls) for ls in old.values())
    print(f"ok: {source.relative_to(space)}: {len(old)} month(s) moved to {adir.name}/ "
          f"({moved} line(s)), {len(by_month) - len(old)} month(s) left in place")
    return 0


MEMORY_READ_EVERY_RUN = (
    (f"{MEMORY_DIR}/general.md", 400),
    (f"{MEMORY_DIR}/agents/*/lessons.md", 400),
    (f"{MEMORY_DIR}/technique/*.md", 400),
)


def _memory_size_report(space: Path) -> list[str]:
    """Files that go into a run's context, and whether any has outgrown being read.

    A line budget rather than a byte one, because that is what a person editing the
    file can see. The threshold is a prompt to curate, not a failure: nothing is
    broken, it is just being paid for on every dispatch.
    """
    notes = []
    for pattern, limit in MEMORY_READ_EVERY_RUN:
        for path in sorted(space.glob(pattern)):
            if not path.is_file():
                continue
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > limit:
                notes.append(
                    f"{path.relative_to(space)} is {count} lines and is read at the start of a run. "
                    f"Over {limit} it is worth curating: `memory curate --file "
                    f"{path.relative_to(space)}` moves struck entries and old reasoning out and "
                    "leaves the rules."
                )
    return notes


# ---------------------------------------------------------------------------
# Voice notes: speech in, and the space is what makes the transcript accurate.
#
# A dropped recording is the cheapest way to get something into the space, and the
# worst thing about it is always the same: speech to text mangles exactly the words
# that carry the meaning, the names. A person, a nickname, a product, a project.
# Zanmai has an advantage no general transcriber has, and it grows with use: the space
# already holds those names. So they are handed to the recogniser BEFORE it starts, as
# an initial prompt, which biases it toward the words that occur in this life rather
# than the words that are common in general. What it still gets wrong is corrected
# against the same list afterwards, and every substitution is written down, because
# silently rewriting what someone said is worse than the error.
#
# Local, not a service. A spoken journal entry is the most private material in the
# space, so it is transcribed on this machine, with no key and nothing uploaded.
# ---------------------------------------------------------------------------

AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac",
              ".aiff", ".aif", ".caf", ".amr", ".wma", ".mp4", ".m4b", ".mov")

# whisper accepts an initial prompt of at most half its text context, a few hundred
# tokens. So the list has to be short and ordered by what gets mangled most: people
# first, then the organisations and products around them, then recurring subjects. A
# longer list would simply be cut off at an arbitrary point.
LEXICON_BUDGET_CHARS = 800


def _tool_path(space: Path, tool_id: str) -> str | None:
    """Where this machine's copy of a registered tool is, or None.

    Goes through the register rather than calling `which` on a hard-coded name, which
    is what the register is for: the invocation name differs per platform (a `.exe` on
    Windows), and a tool this space fetched itself sits in its own runtime tree and is
    not on PATH at all. Asking `which` for one spelling gets both of those wrong.
    """
    spec = (_load_register().get("tools") or {}).get(tool_id)
    if not spec:
        return shutil.which(tool_id)
    found = _detect_tool(space, tool_id, spec, _current_os())
    if found.get("present") and found.get("path"):
        return found["path"]
    if found.get("present"):
        osspec = (spec.get("os") or {}).get(_current_os()) or {}
        return shutil.which(osspec.get("invoke") or tool_id)
    return None


def _recordings_dir(space: Path) -> Path:
    """Recordings wait in the import folder like everything else.

    There is no `recordings/` sub-folder any more: the folder is the automation, and the type of a
    file decides its route, not where somebody happened to put it. A phone that syncs into a folder
    of its own is fine, because the scan walks whatever structure it finds.
    """
    d = space / INBOX_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_duration(path: Path, space: Path | None = None) -> float | None:
    probe = (_tool_path(space, "ffprobe") if space else None) or shutil.which("ffprobe")
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
    # 14-32-05, 2026-08-01_1432, 20260801-1432, with any separators
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


def _pending_recordings(space: Path) -> list[Path]:
    """Every recording waiting in the import folder, sub-folders included."""
    folder = _recordings_dir(space)
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


# Where incoming material goes, as a file the user can open rather than a rule in the code. What
# lands where is a decision that accumulates: a spoken note goes into the day, a backup log goes
# into its own place, a scanned invoice goes to the archive. Written into skills and hooks, those
# decisions spread across a dozen files, none of which the user can read, and every new one needs a
# release. Written here, the user changes a line.
#
# A rule keys on what something IS, never on the file it arrived as. A file type says how to read
# something and nothing at all about what it is for: two `.txt` files are a shopping list and a
# server's nightly report, and a rule that caught one caught the other. So the condition is a word
# in the content or a pattern in the name, and the rule carries the sentence the user said about
# it. Where nothing matches, that is the answer too: the file stays put and the user is asked once.
#
# JSON rather than Markdown because it is read by machine at the moment a file is being routed, and
# `json.load` either gives a structure or fails; prose always gives back something. JSON rather
# than a database because a rule the user set has to be readable by the user who set it.
ROUTING_FILE = "routing.json"

# How much of a file is looked at to decide what it is. A rule that needs more than the opening of
# a document to recognise it is a rule about something other than the document.
ROUTE_TEXT_CHARS = 20000


def _routing_path(space: Path) -> Path:
    return space / SYSTEM_DIR / ROUTING_FILE


def _routing(space: Path) -> dict:
    """The user's routing table, or an empty one. A missing file changes nothing.

    Deliberately forgiving: this is read on every import, and a space whose routing file was never
    written, or was broken by a hand edit, still has to work exactly as before. What it cannot do
    is fail silently in a way that looks like a decision, so a broken file is reported by
    `routing show` rather than swallowed here.
    """
    try:
        daten = json.loads(_routing_path(space).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _routing_rules(space: Path) -> list[dict]:
    """The user's rules, in the order they were written. First match wins, so order is a decision."""
    regeln = _routing(space).get("rules")
    if not isinstance(regeln, list):
        return []
    return [r for r in regeln if isinstance(r, dict) and r.get("name")]


def _rule_matches(regel: dict, path: Path, text_of) -> bool:
    """Whether this rule covers this file. Every condition given has to hold, an absent one is silent.

    `text_of` is a callable and not the text: reading a file costs, and a rule that only names a
    filename pattern must not pay for it. A rule with no conditions at all matches nothing on its
    own; it exists to be pointed at by name when somebody decides this file belongs to it.
    """
    when = regel.get("when")
    if not isinstance(when, dict) or not when:
        return False
    muster = when.get("name")
    if muster and not fnmatch.fnmatch(path.name.lower(), str(muster).lower()):
        return False
    worte = when.get("text")
    if worte:
        if isinstance(worte, str):
            worte = [worte]
        inhalt = (text_of() or "").lower()
        if not inhalt or not all(str(w).lower() in inhalt for w in worte):
            return False
    return True


def _route_for_file(space: Path, path: Path) -> dict:
    """The first rule that covers this file, or an empty rule where the user has not said yet."""
    gelesen: dict[str, str] = {}

    def text_of() -> str:
        if "t" not in gelesen:
            try:
                _art, text = _read_as_text(path)
            except Exception:
                text = ""
            gelesen["t"] = (text or "")[:ROUTE_TEXT_CHARS]
        return gelesen["t"]

    for regel in _routing_rules(space):
        if _rule_matches(regel, path, text_of):
            return regel
    return {}


def _rule_phrase(regel: dict) -> str:
    """One rule as one readable line: where it goes and what the user said to do with it."""
    if not regel:
        return ""
    teile = [f"{regel.get('name', '?')} -> {regel.get('to') or '(no destination)'}"]
    if regel.get("by"):
        teile.append(f"done by {regel['by']}")
    if regel.get("do"):
        teile.append(str(regel["do"]))
    if regel.get("keep") == "with-result":
        teile.append("the file itself is kept, beside what is made from it")
    elif regel.get("keep") == "discard":
        teile.append("the file itself is not needed afterwards and goes to the trash")
    if regel.get("ask_first") is True:
        teile.append("ask first")
    elif regel.get("ask_first") is False:
        teile.append("no need to ask")
    return "; ".join(teile)


# The user's own keeping terms, and the suggestions they were built from. Two files on purpose: one
# ships and is replaced by every update, the other belongs to the space and is never touched.
# A term that lives in the code cannot be corrected without a release, and terms do change: one
# country shortened its figure for accounting vouchers from ten years to eight, and a table built
# on the old number still said ten months afterwards, because nothing about it invited a look.
RETENTION_FILE = "retention.json"
RETENTION_DEFAULTS = "retention-defaults.json"


def _retention_defaults() -> dict:
    try:
        return json.loads((Path(__file__).resolve().parent.parent / RETENTION_DEFAULTS)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _retention(space: Path) -> dict:
    """What actually applies here: the shipped periods, with whatever the user changed on top.

    Nothing applies until the user has confirmed once, and that is the `_confirmed` line. A period
    nobody confirmed is a period nobody chose, and a number applied behind somebody's back is worse
    than no number at all.

    The user's file holds the confirmation and their changes, not a copy of the three periods. It
    used to hold the copy, and then there were two lists of the same thing: a space set up before a
    change kept its old wording for ever, answered with figures the product had retired, and no
    update could reach it because the file is the user's. Kept as a difference, an update improves
    the wording of a period without touching what they decided.
    """
    try:
        eigen = json.loads((space / SYSTEM_DIR / RETENTION_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(eigen, dict) or not eigen.get("_confirmed"):
        return {}
    zusammen = dict(_retention_defaults())
    zusammen["_confirmed"] = eigen["_confirmed"]
    if eigen.get("_checked"):
        zusammen["_checked"] = eigen["_checked"]
    # A period the user rewrote wins over the shipped one of the same name; one they added is added.
    eigene_zeiten = {str(e.get("category")): e for e in eigen.get("terms", []) if e.get("category")}
    if eigene_zeiten:
        zeiten = [eigene_zeiten.pop(str(e.get("category")), e) for e in zusammen.get("terms", [])]
        zusammen["terms"] = zeiten + list(eigene_zeiten.values())
    return zusammen


# The searchable copy of what is kept. Derived, never a source: it is built from the files and can
# be thrown away and rebuilt at any time, which is what makes it safe to keep out of sight and out
# of every backup. It lives under the runtime folder for exactly that reason.
#
# Why a database and not a note per document: the shape this replaces wrote one Markdown file per
# document, and a hundred and twenty pay slips became a hundred and twenty files that turned up in
# every search for years afterwards. The meaning of a matter belongs in a note somebody reads; the
# words of five thousand documents belong somewhere nobody looks unless they are searching.
ARCHIVE_DB = "archive.sqlite3"
# What can be read as text at all, and how.
_TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".csv", ".tsv", ".log")
_MAIL_SUFFIXES = (".eml", ".msg")
_OCR_SUFFIXES = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".heic", ".webp")


def _index_name_words(rel: str) -> str:
    """The path as words, the way the index holds it.

    One function because two places produce it: the read that fills the index, and the migration
    that moves a row to a new area. They drifted apart once already, which left the old area name
    sitting in the searchable text of every document while the path column was correct.
    """
    return " ".join(re.split(r"[^\w]+", rel.replace("/", " ")))


def _archive_db(space: Path):
    """The index, opened and ready. Created on first use, schema included."""
    import sqlite3
    pfad = space / RUNTIME_DIR / ARCHIVE_DB
    pfad.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(pfad))
    db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            path      TEXT PRIMARY KEY,
            size      INTEGER,
            -- Fractional, not whole seconds. A file whose length happens not to change and whose
            -- edit falls in the same second as the last read looks untouched to a whole-second
            -- comparison, and then a document that did change is never read again. Seen while
            -- building this: an amount edited from 1250 to 1400 is the same number of characters.
            mtime     REAL,
            kind      TEXT,
            read_at   TEXT,
            note      TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS content USING fts5(
            path UNINDEXED, body, tokenize='unicode61'
        );
    """)
    return db


# What a file is, read from the file. A name is a label somebody typed and it is wrong often
# enough to matter: a PDF saved without an extension, a scan called `.txt`, a mail exported as
# `.file`. The first bytes of a file say what it is and cannot be typed wrong, so they are asked
# first and the name is only used where they stay silent.
_MAGIC = (
    (b"%PDF", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"II*\x00", ".tiff"),
    (b"MM\x00*", ".tiff"),
    (b"PK\x03\x04", ""),          # a zip: which office format is decided by the name
    (b"{\\rtf", ".rtf"),
    (b"From ", ".eml"),
    (b"Return-Path:", ".eml"),
    (b"Received:", ".eml"),
)


def _sniff(pfad: Path) -> str:
    """The suffix a file would have if it were named after what it is, or "" where that is unclear.

    Reading eight kilobytes costs nothing next to reading the document, and it closes the whole
    class of gap where a file is skipped, or read the wrong way, because of its name.
    """
    try:
        kopf = pfad.open("rb").read(8192)
    except OSError:
        return ""
    for muster, suffix in _MAGIC:
        if kopf.startswith(muster):
            if suffix:
                return suffix
            # A zip. Office formats are zips with a known part inside them; anything else is left
            # to the name, so an ordinary archive is not read as a document.
            return pfad.suffix.lower() if pfad.suffix.lower() in _OFFICE_PARTS else ""
    if kopf.lstrip()[:1] == b"<":
        return ".html"
    # RIFF and ISO media containers: audio and video carry no text to index, but saying what they
    # are beats calling them binary.
    if kopf[:4] in (b"RIFF", b"OggS", b"fLaC") or kopf[4:8] == b"ftyp":
        return ".media"
    return ""


def _text_from_html(roh: str) -> str:
    """The readable text out of a page, with the markup dropped.

    Deliberately the standard library and no dependency: the job is to feed a full-text index, not
    to render the page. Script and style content goes, tags go, entities are resolved, and runs of
    whitespace collapse so the extract in a search result reads as a sentence.
    """
    import html as _html
    import re as _re
    ohne = _re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", roh)
    ohne = _re.sub(r"(?s)<[^>]+>", " ", ohne)
    return _re.sub(r"\s+", " ", _html.unescape(ohne)).strip()


def _read_as_text(pfad: Path) -> tuple[str, str]:
    """(kind, text) for one file, or ("", "") where nothing can be read here.

    Reading is per format and none of it is guessed from the name alone: a PDF may carry a text
    layer or be a photograph of paper, and the only way to know is to try the cheap way first.
    """
    suffix = _sniff(pfad) or pfad.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        try:
            return "text", pfad.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "", ""
    if suffix in _MAIL_SUFFIXES:
        try:
            import email
            from email import policy
            nachricht = email.message_from_bytes(pfad.read_bytes(), policy=policy.default)
            teile = [str(nachricht.get(k, "")) for k in ("Subject", "From", "To", "Date")]
            koerper = nachricht.get_body(preferencelist=("plain", "html"))
            if koerper is not None:
                inhalt = koerper.get_content()
                if koerper.get_content_subtype() == "html":
                    inhalt = _text_from_html(inhalt)
                teile.append(inhalt)
            return "mail", "\n".join(t for t in teile if t)
        except Exception:  # noqa: BLE001 -- a mail that will not parse is skipped, not fatal
            return "mail", ""
    if suffix == ".pdf":
        if not shutil.which("pdftotext"):
            return "pdf", ""
        try:
            lauf = subprocess.run(["pdftotext", "-q", str(pfad), "-"],
                                  capture_output=True, text=True, timeout=120)
            text = lauf.stdout or ""
        except Exception:  # noqa: BLE001
            return "pdf", ""
        # A scan has no text layer. Four in five carry one; the rest need reading with eyes, which
        # is what OCR is. Trying the cheap way first and only then the expensive one is the whole
        # difference between minutes and hours on a real archive.
        if len(text.strip()) > 40 or not shutil.which("ocrmypdf"):
            return "pdf", text
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ziel = Path(tmp) / "ocr.pdf"
                subprocess.run(["ocrmypdf", "-q", "--skip-text", str(pfad), str(ziel)],
                               capture_output=True, timeout=600)
                if ziel.is_file():
                    lauf = subprocess.run(["pdftotext", "-q", str(ziel), "-"],
                                          capture_output=True, text=True, timeout=120)
                    return "pdf-ocr", lauf.stdout or ""
        except Exception:  # noqa: BLE001
            pass
        return "pdf", text
    if suffix in _OCR_SUFFIXES:
        if not shutil.which("tesseract"):
            return "image", ""
        try:
            lauf = subprocess.run(["tesseract", str(pfad), "stdout", "-l", "deu+eng"],
                                  capture_output=True, text=True, timeout=300)
            return "image", lauf.stdout or ""
        except Exception:  # noqa: BLE001
            return "image", ""
    return _read_anything(pfad, suffix)


# Office files are ZIP archives of XML. Reading them needs no library at all, and refusing to look
# because no library is installed is how a contract ends up outside the index.
_OFFICE_PARTS = {
    ".docx": ("word/document.xml",),
    ".pptx": ("ppt/slides/",),
    ".xlsx": ("xl/sharedStrings.xml", "xl/worksheets/"),
    ".odt": ("content.xml",),
    ".odp": ("content.xml",),
    ".ods": ("content.xml",),
}


def _read_anything(pfad: Path, suffix: str = "") -> tuple[str, str]:
    """Last resort for a file no specific reader claimed: read it, do not skip it.

    This function exists because of a list. Readable formats were named one by one, and everything
    not on the list fell through in silence: the index answered, it just answered short, and the
    one contract that existed only as a saved web page was invisible. A list of what can be read
    is a list that is always one format out of date. So the question is turned around. Every file
    is read; the format only decides how. What genuinely carries no text says so, by name, instead
    of disappearing.
    """
    suffix = suffix or pfad.suffix.lower()
    if suffix in _OFFICE_PARTS:
        try:
            import zipfile
            stuecke = []
            with zipfile.ZipFile(pfad) as archiv:
                for name in archiv.namelist():
                    if not any(name.startswith(teil) or name == teil
                               for teil in _OFFICE_PARTS[suffix]):
                        continue
                    if not name.endswith(".xml"):
                        continue
                    stuecke.append(_text_from_html(archiv.read(name).decode("utf-8", "replace")))
            return suffix.lstrip("."), " ".join(s for s in stuecke if s)
        except Exception:  # noqa: BLE001 -- a broken archive is read as bytes below
            pass
    # Anything else: read it as text and see. A file that is mostly printable is a text file
    # whatever it is called, and one that is not says so rather than filling the index with noise.
    if suffix == ".media":
        return "media", ""
    try:
        roh = pfad.read_bytes()[:2_000_000]
    except OSError:
        return "", ""
    text = roh.decode("utf-8", errors="replace")
    druckbar = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    if text and druckbar / len(text) > 0.85:
        if "<" in text[:2000] and ">" in text[:2000]:
            return suffix.lstrip(".") or "text", _text_from_html(text)
        return suffix.lstrip(".") or "text", text
    return suffix.lstrip(".") or "binary", ""


# The matter, and the documents hanging off it. A single letter answers nothing; what answers
# something is the policy, the employment, the vehicle, the case it belongs to. So the matter is
# the unit that gets a note, and everything else is a line in its chronology plus a row in the
# index. The shape this replaces wrote a note per document and drowned in them.
MATTER_SUFFIX = "-matter"


def _matter_doc_type(roh: str) -> str:
    """The kind of a matter, with the suffix on it once.

    It was appended without looking, so a kind that already carried it came out as
    `contract-matter-matter`. Anything a person types twice by mistake is something the code has to
    absorb, because the alternative is a field that reads as broken to whoever opens the file.
    """
    art = (roh or "matter").strip()
    while art.endswith(MATTER_SUFFIX):
        art = art[: -len(MATTER_SUFFIX)]
    return f"{art or 'matter'}{MATTER_SUFFIX}"
_CHRONO_HEADING = "## Chronology"
_CHRONO_HEADER = ("| Date | What happened | Amount | With |\n"
                  "|---|---|---|---|")

# A matter note is the user's file, not a system file, so its headings belong in the language they
# write in. The house rule already draws that line, the generator did not: notes came out with
# English column headings in a space kept in another language. Only the languages the distribution
# actually speaks are here; anything else falls back to English rather than to a guess.
_CHRONO_WORDS = {
    "de": ("## Verlauf", "| Datum | Was geschah | Betrag | Mit wem |\n|---|---|---|---|"),
    "en": (_CHRONO_HEADING, _CHRONO_HEADER),
}


def _chrono_words(space: Path) -> tuple[str, str]:
    """Heading and table header for a matter note, in the language the space is kept in."""
    try:
        fm = _session_parse_frontmatter((space / SYSTEM_DIR / "user.md").read_text(encoding="utf-8"))
    except OSError:
        return _CHRONO_WORDS["en"]
    sprache = str(fm.get("language", "") or "").strip().lower()[:2]
    return _CHRONO_WORDS.get(sprache, _CHRONO_WORDS["en"])


def _matter_path(space: Path, slug: str, bereich: str = "") -> Path:
    ordner = space / ARCHIVE_DIR / bereich / slug if bereich else space / ARCHIVE_DIR / slug
    return ordner / f"{slug}.md"


def _find_matter(space: Path, slug: str) -> Path | None:
    """The matter note for this slug, wherever in the archive it sits."""
    wurzel = space / ARCHIVE_DIR
    if not wurzel.is_dir():
        return None
    treffer = [p for p in wurzel.rglob(f"{slug}.md") if p.is_file()]
    return treffer[0] if treffer else None


# One counterparty, however many ways it is written. The same insurer arrives as three spellings
# across ten years of paper, and each spelling that becomes its own entry splits a matter that
# belongs together. What this cannot do is decide: two legal entities of one brand may or may not
# be one counterparty depending on why you are asking, and getting that wrong is invisible
# afterwards. So it matches what it knows and proposes what it does not.
ALIASES_FILE = "aliases.json"


def _aliases(space: Path) -> dict:
    try:
        daten = json.loads((space / SYSTEM_DIR / ALIASES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _alias_lookup(space: Path, name: str) -> tuple[str, list[str]]:
    """(canonical, near misses). An exact hit resolves; near misses are for a person to settle."""
    tabelle = _aliases(space).get("counterparties") or {}
    gesucht = _slugify(name)
    for kanon, eintrag in tabelle.items():
        schreibweisen = {_slugify(s) for s in ([kanon] + list(eintrag.get("seen") or []))}
        if gesucht in schreibweisen:
            return kanon, []
    # Near, not equal: a shared stem is a reason to ask, never a reason to merge.
    stamm = gesucht.split("-")[0]
    nah = [k for k in tabelle if k.split("-")[0] == stamm and len(stamm) >= 4]
    return "", nah


def cmd_archive_who(args: argparse.Namespace) -> int:
    """Resolve a counterparty name, or say what it might be."""
    space = _work_space(args)
    kanon, nah = _alias_lookup(space, args.name)
    if kanon:
        print(kanon)
        return 0
    if nah:
        print(f"unresolved: {args.name!r} is not listed. Close to: {', '.join(nah)}. "
              f"Ask whether it is one of those before filing anything against it; "
              f"`archive who {args.name} --same-as <canonical>` records the answer.", file=sys.stderr)
        return 1
    print(f"unknown: {args.name!r} is new here. `archive who {args.name} --new` adds it.",
          file=sys.stderr)
    return 1


def cmd_archive_who_set(args: argparse.Namespace) -> int:
    """Record the answer: this spelling is that counterparty, or this one is new."""
    space = _work_space(args)
    daten = _aliases(space)
    # Assigned rather than defaulted, and the difference matters after a rename. `setdefault` writes
    # it once and never again, so a space carries the sentence of the version that created the file
    # for ever: this one still named a command family that had been renamed, in a file no update
    # touches. The line describes the machine's own file, so the machine owns it and rewrites it.
    daten["_comment"] = ("One canonical name per counterparty, and the spellings seen for "
                         "it. Written by `zanmai.py archive who`, never merged silently.")
    tabelle = daten.setdefault("counterparties", {})
    if args.same_as:
        kanon = _slugify(args.same_as)
        if kanon not in tabelle:
            print(f"fail: no counterparty '{kanon}' to attach this to. Add it with --new first.",
                  file=sys.stderr)
            return 1
        gesehen = tabelle[kanon].setdefault("seen", [])
        if args.name not in gesehen:
            gesehen.append(args.name)
    else:
        kanon = _slugify(args.name)
        tabelle.setdefault(kanon, {"seen": [], "note": args.note or ""})
        if args.note:
            tabelle[kanon]["note"] = args.note
    ziel = space / SYSTEM_DIR / ALIASES_FILE
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py", f"records: counterparty {kanon}")
    print(f"ok: {args.name} -> {kanon}")
    return 0


def cmd_archive_matter_new(args: argparse.Namespace) -> int:
    """Open a matter: the thing documents belong to.

    Written before the first document is filed against it rather than derived afterwards, because
    the decision it records, that these papers are one matter, is exactly what nobody can
    reconstruct later from a folder full of scans.
    """
    space = _work_space(args)
    slug = _slugify(args.slug or args.title)
    if _find_matter(space, slug) and not args.force:
        print(f"fail: a matter '{slug}' already exists. Use it, or pass --force to make a second "
              f"one and say in its body why they are not the same matter.", file=sys.stderr)
        return 1
    if args.retention:
        erlaubt = _retention_categories(space)
        if args.retention not in erlaubt:
            eigen = "this space's confirmed terms" if _retention(space) else "the shipped suggestions"
            print(f"fail: '{args.retention}' is not a keeping term in {eigen}. Available: "
                  f"{', '.join(erlaubt) or 'none, run `retention adopt` first'}. A term the user "
                  f"never confirmed applies to nobody.", file=sys.stderr)
            return 1
    ziel = _matter_path(space, slug, args.into or "")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    zeilen = ["---", "kind: record", f"slug: {slug}", f"created: {_today()}",
              f"doc_type: {_matter_doc_type(args.doc_type)}",
              f"lifecycle: {args.lifecycle}"]
    if args.retention:
        zeilen.append(f"retention_policy: {args.retention}")
    if args.until:
        zeilen.append(f"retention_until: {args.until}")
    if args.with_whom:
        zeilen.append(f"relates_to: {_slugify(args.with_whom)}")
    zeilen += ["---", "", f"# {args.title}", ""]
    if args.about:
        zeilen += [args.about, ""]
    ueberschrift, kopf = _chrono_words(space)
    zeilen += [ueberschrift, "", kopf, ""]
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"records: opened matter {ziel.relative_to(space)}")
    print(f"ok: {ziel.relative_to(space)}")
    return 0


def _date_in_name(name: str) -> str:
    """The date a filename carries, or "". Written down on purpose, so it beats the text."""
    for muster in (r"(\d{4})-(\d{2})-(\d{2})", r"(\d{4})(\d{2})(\d{2})"):
        treffer = re.search(muster, name)
        if treffer:
            iso = "-".join(treffer.groups())
            if _as_iso_date(iso):
                return iso
    treffer = re.search(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})", name)
    return _as_iso_date(".".join(treffer.groups())) if treffer else ""


def _as_iso_date(roh: str) -> str:
    """A date somebody wrote, as a date that sorts. Empty where it is not one.

    A chronology whose rows do not sort is not a chronology, it is a list in the order the files
    happened to be read. Dates come out of documents in whatever form the document used, so they
    are brought to one form here rather than displayed as found: `04.02.2026` sorting above
    `05.03.2025` is the kind of wrong that looks like a small formatting matter and is actually the
    table saying something untrue about what happened when.
    """
    roh = (roh or "").strip()
    treffer = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", roh)
    if treffer:
        return roh
    treffer = re.match(r"^(\d{1,2})[.\/](\d{1,2})[.\/](\d{2,4})$", roh)
    if not treffer:
        return ""
    tag, monat, jahr = treffer.groups()
    if len(jahr) == 2:
        jahr = f"20{jahr}"
    try:
        datetime(int(jahr), int(monat), int(tag))
    except ValueError:
        return ""
    return f"{jahr}-{int(monat):02d}-{int(tag):02d}"


def _matter_add_documents(space: Path, notiz: Path, slug: str, dokumente: list[Path],
                          args: argparse.Namespace) -> int:
    """Hang documents on a matter, the chronology filled from what was read out of them.

    The date, the amount and the counterparty are established already: the index pulled the text
    out and `_extract` found the shape in it. Asking a person to type them again per document is
    asking them to redo work a machine has done, and on a real pile that is where the hours go.
    """
    db = _archive_db(space)
    kandidaten = []
    for datei in dokumente:
        rel = datei.relative_to(space).as_posix()
        treffer = db.execute("SELECT body FROM content WHERE path = ?", (rel,)).fetchone()
        form = _extract(treffer[0]) if treffer else {}
        # The name first, then the text. A date in a filename was put there deliberately, by the
        # user or by whatever exported the file, and it is the day the document is about. The first
        # date inside a document is whatever the document mentions first, which is as often a term,
        # a due date or a validity than the day it was written: a cancellation confirmation from
        # February landed a year out because the letter opened with the date the contract runs to.
        kandidaten.append((
            args.date or _date_in_name(datei.name)
            or _as_iso_date((form.get("dates") or [""])[0]) or _today(),
            rel,
            datei.name,
            args.amount or (form.get("amounts") or [""])[0],
            args.with_whom or (form.get("parties") or [""])[0],
        ))
    db.close()

    text = notiz.read_text(encoding="utf-8")
    ueberschrift, kopf = _chrono_words(space)
    if ueberschrift not in text and _CHRONO_HEADING not in text:
        text = text.rstrip() + f"\n\n{ueberschrift}\n\n{kopf}\n"
    zeilen = text.rstrip().split("\n")
    zugefuegt = 0
    for datum, rel, name, betrag, wer in sorted(kandidaten):
        if rel in text:      # already on this matter; saying it twice says nothing new
            continue
        zeilen.append(f"| {datum} | [{name}]({rel}) | {betrag} | {wer} |")
        zugefuegt += 1
    notiz.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"{zugefuegt} document(s) hung on matter {slug}")
    print(f"ok: {zugefuegt} document(s) on {notiz.relative_to(space)}"
          + (f", {len(kandidaten) - zugefuegt} were already there"
             if zugefuegt < len(kandidaten) else ""))
    return 0


def cmd_archive_matter_add(args: argparse.Namespace) -> int:
    """Hang a document on its matter: a line in the chronology, and the link back.

    Both directions in one step on purpose. A document that names its matter while the matter does
    not list it is half a link, and half a link is what makes an archive stop being answerable.
    """
    space = _work_space(args)
    slug = _slugify(args.matter)
    notiz = _find_matter(space, slug)
    if notiz is None:
        print(f"fail: no matter '{slug}'. Open it first with `archive matter new`; a document "
              f"without a matter is one nobody finds again.", file=sys.stderr)
        return 1
    if args.via not in RECORD_RELATIONS:
        print(f"fail: '{args.via}' is not a relation. Use one of: "
              f"{', '.join(sorted(RECORD_RELATIONS))}", file=sys.stderr)
        return 1

    # A document, rather than a typed sentence. Everything the chronology wants, the date, the
    # amount, who it was with, is already in the index, put there by machine when the file was
    # read. Making somebody retype it per document is what turned filing thirty-four documents
    # into an afternoon: the judgement is which matter something belongs to, and that is the only
    # part worth a person's time.
    dokumente: list[Path] = []
    if args.path:
        einer = _resolve_space_file(space, args.path)
        if einer is None:
            print(f"fail: no such file: {args.path}", file=sys.stderr)
            return 1
        dokumente = [einer]
    elif args.folder:
        ordner = space / args.folder
        if not ordner.is_dir():
            print(f"fail: no such folder: {args.folder}", file=sys.stderr)
            return 1
        dokumente = sorted(f for f in ordner.rglob("*")
                           if f.is_file() and f.name not in _SYSTEM_LITTER)
        if not dokumente:
            print(f"nothing to add: {args.folder} holds no documents")
            return 0
    if dokumente:
        return _matter_add_documents(space, notiz, slug, dokumente, args)
    if not args.what:
        print("fail: say what happened, or point at a document with --path or --folder.",
              file=sys.stderr)
        return 1

    text = notiz.read_text(encoding="utf-8")
    zeile = (f"| {args.date or _today()} | {args.what} | {args.amount or ''} | "
             f"{args.with_whom or ''} |")
    ueberschrift, kopf = _chrono_words(space)
    if ueberschrift not in text and _CHRONO_HEADING not in text:
        text = text.rstrip() + f"\n\n{ueberschrift}\n\n{kopf}\n"
    zeilen = text.rstrip().split("\n")
    # Appended at the end of the table rather than sorted in: a chronology people read is written
    # in the order things arrived, and a run that reorders somebody's table changes their file for
    # its own convenience.
    zeilen.append(zeile)
    notiz.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    # And the other direction, where the document has a note of its own.
    if args.document:
        dok = _resolve_space_file(space, args.document)
        if dok is None:
            print(f"fail: no such file: {args.document}", file=sys.stderr)
            return 1
        geaendert, notes = _edit_frontmatter_in_place(
            dok, {"relates_to": slug, "relates_via": args.via}, [])
        for n in notes:
            print(f"  {n}")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"records: {args.what[:60]} -> {slug} ({args.via})")
    print(f"ok: added to {notiz.relative_to(space)} ({args.via})")
    return 0


def cmd_archive_matter_show(args: argparse.Namespace) -> int:
    """One matter, whole: what it is, where it stands, and everything under it."""
    space = _work_space(args)
    slug = _slugify(args.matter)
    notiz = _find_matter(space, slug)
    if notiz is None:
        print(f"unknown: no matter '{slug}'", file=sys.stderr)
        return 1
    text = notiz.read_text(encoding="utf-8")
    fm, _o, _b = _split_frontmatter(text)
    print(f"{notiz.relative_to(space)}")
    print(f"  state     {fm.get('lifecycle', '(not stated)')}")
    if fm.get("retention_policy"):
        print(f"  kept      {fm['retention_policy']}"
              + (f" until {fm['retention_until']}" if fm.get("retention_until") else ""))
    unter = sorted(p for p in notiz.parent.rglob("*") if p.is_file() and p != notiz)
    print(f"  documents {len(unter)}")
    for p in unter[:20]:
        print(f"    {p.relative_to(notiz.parent)}")
    if len(unter) > 20:
        print(f"    ... and {len(unter) - 20} more")
    print()
    print(text[text.index("# "):] if "# " in text else text)
    return 0


# What can be pulled out of a document without understanding it. Dates, amounts and the names that
# look like parties are shapes, not meaning, so a regular expression finds them as well as a model
# would and costs nothing.
#
# This is the whole economy of the thing. Reading five thousand documents with a model is millions
# of tokens and hours; reading five thousand extracts is a fraction of one document each. And for
# the decision that actually has to be made at this point, which is "is this something to keep, and
# what matter does it belong to", the extract is usually enough: a paper that says invoice, carries
# a date and an amount, and names a company is an invoice from that company on that date. The model
# opens the file only where the extract leaves the question open.
_DATUM_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
_BETRAG_RE = re.compile(r"\b\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\s?(?:EUR|USD|CHF|GBP|€|\$|£)"
                        r"|(?:EUR|USD|CHF|GBP|€|\$|£)\s?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}")
# A run of capitalised words is a name in most Latin-script languages, and a legal-form suffix
# makes it a company almost anywhere. Deliberately not a keyword list: a list of German document
# words would work in one country and nowhere else.
_FIRMA_RE = re.compile(r"\b([A-ZÄÖÜ][\w&.\-]+(?:\s+[A-ZÄÖÜ][\w&.\-]+){0,3}\s+"
                       r"(?:GmbH|AG|KG|OHG|SE|mbH|Ltd|Limited|Inc|LLC|S\.p\.A|SARL|BV|NV|AB|Oy|"
                       r"e\.?V|UG))\b")


def _extract(text: str, limit: int = 400) -> dict:
    """The shape of a document, without reading it for meaning.

    Everything here is a pattern: dates look like dates in any language, an amount is digits and a
    currency, a company is capitalised words ending in a legal form. What none of it says is what
    the document is *about*, and that is on purpose: this exists so that something else can decide
    whether it needs to look.
    """
    if not text.strip():
        return {}
    daten = sorted(set(_DATUM_RE.findall(text)))[:6]
    # Whitespace collapsed first: an amount split across a line break comes out of a PDF as
    # "EUR\n62,90" and would otherwise be carried into the survey with the break in it.
    betraege = sorted(set(re.sub(r"\s+", " ", m.group(0)).strip()
                          for m in _BETRAG_RE.finditer(text)))[:6]
    firmen = []
    for m in _FIRMA_RE.finditer(text):
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        if name not in firmen:
            firmen.append(name)
    kopf = re.sub(r"\s+", " ", text.strip())[:limit]
    return {"opening": kopf, "dates": daten, "amounts": betraege, "parties": firmen[:4]}


def cmd_survey(args: argparse.Namespace) -> int:
    """What a pile of files is, established by machine, for anybody who has to decide about them.

    Not tied to the archive, because the problem is not: an expert handed twenty sources, a
    folder of scans, a mail export, all face the same question first, which is what these things
    are. That question does not need understanding, it needs shape, and shape is free.

    The rule this exists to make cheap: **a run reads a file with a model only where the survey
    leaves the question open.** Measured on real material, the survey is a sixteenth of the text.
    Over a few thousand documents that is the difference between an afternoon and a minute, and the
    answer to "what is this and where does it belong" is the same either way.
    """
    space = _work_space(args)
    wurzel = Path(args.path)
    if not wurzel.is_absolute():
        wurzel = space / args.path
    if not wurzel.exists():
        print(f"fail: no such path: {args.path}", file=sys.stderr)
        return 1
    dateien = ([wurzel] if wurzel.is_file()
               else sorted(f for f in wurzel.rglob("*")
                           if f.is_file() and not f.name.startswith(".")))
    if not dateien:
        print(f"empty: nothing in {args.path}")
        return 0
    if len(dateien) > args.limit:
        print(f"note: {len(dateien)} files, surveying the first {args.limit}. "
              f"Raise it with --limit where the whole pile has to be seen at once.")
        dateien = dateien[:args.limit]

    ausgabe, stumm = [], 0
    for f in dateien:
        art, text = _read_as_text(f)
        eintrag = {"path": (f.relative_to(space).as_posix()
                            if f.is_relative_to(space) else str(f)),
                   "kind": art or f.suffix.lstrip(".").lower() or "unknown"}
        merkmale = _extract(text or "", limit=args.opening)
        for feld in ("dates", "amounts", "parties", "opening"):
            if merkmale.get(feld):
                eintrag[feld] = merkmale[feld]
        if not merkmale.get("opening"):
            eintrag["note"] = "nothing readable by machine; this one has to be opened"
            stumm += 1
        ausgabe.append(eintrag)

    if args.json:
        print(json.dumps(ausgabe, ensure_ascii=False, indent=2))
    else:
        for e in ausgabe:
            print(f"{e['path']}  [{e['kind']}]")
            for feld in ("dates", "amounts", "parties"):
                if e.get(feld):
                    print(f"    {feld:8} {', '.join(e[feld])}")
            if e.get("opening"):
                print(f"    opening  {e['opening'][:160]}")
            if e.get("note"):
                print(f"    {e['note']}")
    print(f"\n{len(ausgabe)} file(s) surveyed by machine, {stumm} unreadable."
          + ("  Those are the ones worth opening; the rest were answered here."
             if stumm else "  None of this needed a model."))
    return 0


def cmd_archive_survey(args: argparse.Namespace) -> int:
    """One line per document, from the index, for something else to decide on.

    The point of this command is what it is *not*: it is not a model reading files. It is the
    machine handing over what it could establish for free, so that whoever decides what to do with
    five thousand documents reads five thousand short lines instead of five thousand documents.

    `--scope` takes the same folder `archive index --scope` was given, and it is not a convenience.
    The two are named in one sentence wherever the reading pass is described, so a run reads them as
    a pair: index this folder, then survey it. Without the argument here, the pair silently became
    "index the inbox, then survey the entire archive", which on a real one is thousands of lines
    about documents nobody asked about. Two runs typed `archive survey --scope import` on the same
    day and both got an argparse error, which is the honest reading of a sentence that offers it.
    """
    space = _work_space(args)
    db = _archive_db(space)
    bereich = (args.scope or "").strip("/") if getattr(args, "scope", None) else ""
    if bereich:
        zeilen = db.execute(
            "SELECT d.path, d.kind, c.body FROM documents d LEFT JOIN content c ON c.path = d.path "
            "WHERE d.path = ? OR d.path LIKE ? ORDER BY d.path",
            (bereich, f"{bereich}/%")).fetchall()
    else:
        zeilen = db.execute(
            "SELECT d.path, d.kind, c.body FROM documents d LEFT JOIN content c ON c.path = d.path "
            "ORDER BY d.path").fetchall()
    db.close()
    if not zeilen:
        if bereich:
            print(f"empty: nothing indexed under {bereich}/. `archive index --scope {bereich}` "
                  f"reads it in first, mechanically and without a model.")
        else:
            print(f"empty: nothing indexed yet. `archive index --scope <folder>` reads it in first, "
                  f"mechanically and without a model.")
        return 1
    ausgabe = []
    for pfad, art, text in zeilen:
        merkmale = _extract(text or "", limit=args.opening)
        eintrag = {"path": pfad, "kind": art}
        if merkmale.get("dates"):
            eintrag["dates"] = merkmale["dates"]
        if merkmale.get("amounts"):
            eintrag["amounts"] = merkmale["amounts"]
        if merkmale.get("parties"):
            eintrag["parties"] = merkmale["parties"]
        if merkmale.get("opening"):
            eintrag["opening"] = merkmale["opening"]
        elif not text:
            eintrag["note"] = "nothing readable; the file has to be opened to say what it is"
        ausgabe.append(eintrag)
    if args.json:
        print(json.dumps(ausgabe, ensure_ascii=False, indent=2))
    else:
        for e in ausgabe:
            print(f"{e['path']}  [{e.get('kind', '?')}]")
            for feld in ("dates", "amounts", "parties"):
                if e.get(feld):
                    print(f"    {feld:8} {', '.join(e[feld])}")
            if e.get("opening"):
                print(f"    opening  {e['opening'][:160]}")
            if e.get("note"):
                print(f"    {e['note']}")
    stumm = sum(1 for e in ausgabe if e.get("note"))
    print(f"\n{len(ausgabe)} document(s) surveyed, {stumm} of them unreadable by machine."
          + ("  Those are the ones worth opening." if stumm else
             "  Nothing here needed a model to produce."))
    return 0


def _archive_db_repath(db, alt_rel: str, neu_rel: str) -> None:
    """Carry index entries over to where something now lies, for one file or a whole section.

    A prefix rewrite rather than a single-row update, because a section is renamed about as often as
    a document is, and re-reading a filed archive to recover what merely moved costs minutes on a
    real pile. Anything this misses, the next index run picks up.
    """
    for tabelle in ("documents", "content"):
        db.execute(f"DELETE FROM {tabelle} WHERE path = ? OR path LIKE ?",
                   (neu_rel, f"{neu_rel}/%"))
        db.execute(f"UPDATE {tabelle} SET path = ? WHERE path = ?", (neu_rel, alt_rel))
        db.execute(f"UPDATE {tabelle} SET path = ? || substr(path, ?) WHERE path LIKE ?",
                   (neu_rel, len(alt_rel) + 1, f"{alt_rel}/%"))


def _archive_relocate(space: Path, quelle: Path, ziel: Path, agent: str, was: str) -> int:
    """Move a document or a whole section inside `archive/`, index entry included.

    Both `archive rename` and `archive move` end here, because they are the same operation with a
    different target: the file changes place, the index has to follow, and the activity log has to
    say so. Neither existed, so every real run ended in a hand-rolled `mv`, which moves the file and
    leaves the index pointing at where it used to be.

    Only inside `archive/`. Taking something out of what is kept is a different decision with a
    different command, and letting this do it quietly would make discarding look like tidying.
    """
    for name, p in (("--path", quelle), ("the target", ziel)):
        if not p.is_relative_to(space):
            print(f"fail: {name} '{p}' is not inside the space.", file=sys.stderr)
            return 1
        rel = p.relative_to(space).as_posix()
        if rel != ARCHIVE_DIR and not rel.startswith(f"{ARCHIVE_DIR}/"):
            print(f"fail: {name} '{rel}' lies outside {ARCHIVE_DIR}/. This moves things within what "
                  f"is kept. To take something out, use `file archive` or `file trash`.",
                  file=sys.stderr)
            return 1
    alt_rel = quelle.relative_to(space).as_posix()
    neu_rel = ziel.relative_to(space).as_posix()
    if not quelle.exists():
        print(f"fail: nothing at {alt_rel}", file=sys.stderr)
        return 1
    if alt_rel == neu_rel:
        print(f"ok: {alt_rel} is already where it should be, nothing moved.")
        return 0
    if ziel.exists():
        print(f"fail: {neu_rel} is already taken. Deal with that copy first, nothing was moved.",
              file=sys.stderr)
        return 1
    if quelle.is_dir() and ziel.is_relative_to(quelle):
        print(f"fail: {neu_rel} lies inside {alt_rel}, so this would move a folder into itself.",
              file=sys.stderr)
        return 1
    _space_mkdir(space, ziel.parent, parents=True, exist_ok=True)
    shutil.move(str(quelle), str(ziel))
    db = _archive_db(space)
    _archive_db_repath(db, alt_rel, neu_rel)
    db.commit()
    db.close()
    _append_activity_log(space, agent or "zanmai.py", f"{was} {alt_rel} -> {neu_rel}")
    print(f"ok: {was} {alt_rel} -> {neu_rel}")
    return 0


def cmd_archive_rename(args: argparse.Namespace) -> int:
    """Give a kept document or a section a name that says what it is.

    A scan arrives called `scan-0007.pdf` and nothing about that name helps anybody find it again.
    The name is the user's to choose, so it is taken as typed rather than slugified; only a path
    separator is refused, because that is a move and says so.
    """
    space = _work_space(args)
    quelle = space / args.path
    name = args.to.strip().strip("/")
    if not name:
        print("fail: --to needs a name.", file=sys.stderr)
        return 1
    if "/" in name or "\\" in name:
        print(f"fail: --to takes a name, not a path. To put it somewhere else, use "
              f"`archive move --path {args.path} --to <folder>`.", file=sys.stderr)
        return 1
    # A rename that silently drops `.pdf` makes the file unopenable for the tool that reads it.
    if quelle.is_file() and quelle.suffix and not Path(name).suffix:
        name += quelle.suffix
    return _archive_relocate(space, quelle, quelle.parent / name, args.agent, "renamed")


def cmd_archive_move(args: argparse.Namespace) -> int:
    """Put a kept document or a whole section somewhere else inside `archive/`."""
    space = _work_space(args)
    quelle = space / args.path
    return _archive_relocate(space, quelle, space / args.to.strip("/") / quelle.name,
                             args.agent, "moved")


def cmd_archive_intake(args: argparse.Namespace) -> int:
    """Move documents into the archive, or within it, a pile at a time, and read them there.

    The source is any folder in the space, not only `inbox/`: moving a pile that is already filed
    onto a different section is the same operation and uses the same command. It was written as if
    it only pointed inwards, and the run that needed it went back to moving files by hand.

    This is the step that was missing. Everything around it existed, reading, searching, matters,
    counterparties, and the one thing nobody could do was move a document in. So a run had to move
    files by hand, one call each, and what actually happened on a real pile was that nothing moved
    at all for hours while every file was thought about individually.

    The folders under the source are kept as they are. A person who sorted their own material into
    `telekom` and `insurance` has already answered the question of what belongs together, and
    rebuilding that from the content produces a different, worse answer at great expense.
    """
    space = _work_space(args)
    quelle = space / args.source
    if not quelle.exists():
        print(f"fail: nothing at {args.source}", file=sys.stderr)
        return 1
    # `--into ange/gesundheit` used to arrive as the single folder `ange-gesundheit`, because the
    # plain slugifier eats the separator. A section inside a section is the normal shape of a real
    # archive, and the run that wanted one had to file flat and move by hand afterwards.
    bereich = "/".join(_slugify_bundle_path(args.into)[0]) if args.into else ""
    ziel_wurzel = space / ARCHIVE_DIR / bereich if bereich else space / ARCHIVE_DIR

    dateien = [p for p in ([quelle] if quelle.is_file() else sorted(quelle.rglob("*")))
               if p.is_file() and p.name not in _SYSTEM_LITTER]
    if not dateien:
        print(f"nothing to file: {args.source} holds no documents")
        return 0

    basis = quelle.parent if quelle.is_file() else quelle
    paare: list[tuple[Path, Path]] = []
    for f in dateien:
        ziel = ziel_wurzel / f.relative_to(basis)
        if ziel.exists():
            print(f"fail: {ziel.relative_to(space)} is already there. Deal with that copy first, "
                  f"nothing was moved.", file=sys.stderr)
            return 1
        paare.append((f, ziel))

    if args.dry_run:
        for f, ziel in paare:
            print(f"  {f.relative_to(space)} -> {ziel.relative_to(space)}")
        print(f"{len(paare)} document(s) would be filed. Nothing was moved.")
        return 0

    # The index entry moves with the file. Its content did not change, only where it lies, and
    # reading a filed archive again costs minutes it does not need to cost. Whatever this misses,
    # the index run below picks up.
    db = _archive_db(space)
    for f, ziel in paare:
        _space_mkdir(space, ziel.parent, parents=True, exist_ok=True)
        shutil.move(str(f), str(ziel))
        _archive_db_repath(db, f.relative_to(space).as_posix(), ziel.relative_to(space).as_posix())
    db.commit()
    db.close()
    # The source folders are left behind empty, and an empty folder in `inbox/` is read again at
    # every session start as if something were waiting there.
    if quelle.is_dir():
        # A folder holding nothing but a `.DS_Store` is an empty folder to everyone except the
        # filesystem. Left standing, it makes every later session start report material waiting.
        for d in sorted((p for p in quelle.rglob("*") if p.is_dir()) or [], key=lambda p: len(p.parts),
                        reverse=True) + [quelle]:
            rest = list(d.iterdir()) if d.is_dir() else []
            if rest and all(r.is_file() and r.name in _SYSTEM_LITTER for r in rest):
                for r in rest:
                    r.unlink(missing_ok=True)
            try:
                d.rmdir()
            except OSError:
                pass

    _append_activity_log(space, args.agent or "zanmai.py",
                         f"{len(paare)} document(s) filed into {ARCHIVE_DIR}/{bereich}")
    print(f"ok: {len(paare)} document(s) filed into {ARCHIVE_DIR}/{bereich or ''}".rstrip("/"))
    # Reading them now rather than later, because a document that is filed but not readable is a
    # document the search cannot answer about, and nobody comes back to run a second command.
    return cmd_archive_index(argparse.Namespace(
        space=str(space), scope=f"{ARCHIVE_DIR}/{bereich}" if bereich else ARCHIVE_DIR,
        rebuild=False, agent=args.agent))


def cmd_archive_index(args: argparse.Namespace) -> int:
    """Read what is kept, once each, into the searchable copy.

    Incremental by size and modification time: a second run over five thousand files touches only
    what changed. That is not an optimisation, it is what makes the thing usable at all, because a
    full read of a real archive is measured in hours once scans are in it.
    """
    space = _work_space(args)
    wurzel = space / (args.scope or ARCHIVE_DIR)
    if not wurzel.is_dir():
        print(f"fail: no such folder: {wurzel.relative_to(space) if wurzel.is_relative_to(space) else wurzel}",
              file=sys.stderr)
        return 1
    db = _archive_db(space)
    bekannt = {p: (s, m) for p, s, m in db.execute("SELECT path, size, mtime FROM documents")}
    gelesen, uebersprungen, leer = 0, 0, 0
    for datei in sorted(f for f in wurzel.rglob("*") if f.is_file()):
        if datei.name.startswith("."):
            continue
        rel = datei.relative_to(space).as_posix()
        try:
            stat = datei.stat()
        except OSError:
            continue
        if bekannt.get(rel) == (stat.st_size, stat.st_mtime) and not args.rebuild:
            uebersprungen += 1
            continue
        art, text = _read_as_text(datei)
        if not art:
            continue
        if not text.strip():
            leer += 1
        db.execute("DELETE FROM content WHERE path = ?", (rel,))
        # The name goes into the searchable text with the content. What a document is called is
        # very often the only place its subject is written in plain words: a scan reads as the
        # broken output of a fax from 2008, and the one word somebody will actually type is on the
        # file, not in it. Searching for the exact name of a file and being told there is no such
        # thing is the answer that makes people stop trusting a search.
        db.execute("INSERT INTO content (path, body) VALUES (?, ?)",
                   (rel, f"{_index_name_words(rel)}\n{text}"))
        db.execute("INSERT INTO documents (path, size, mtime, kind, read_at, note) "
                   "VALUES (?, ?, ?, ?, ?, COALESCE((SELECT note FROM documents WHERE path = ?), '')) "
                   "ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, "
                   "kind=excluded.kind, read_at=excluded.read_at",
                   (rel, stat.st_size, stat.st_mtime, art, _today(), rel))
        gelesen += 1

    # Entries whose file is gone. A document that was moved, filed elsewhere or deleted by hand
    # stays in the index otherwise, and every search answers with it: a hit on a path that does not
    # exist, next to the hit on the same document where it actually lies. Reading everything again
    # does not fix that, because reading only ever adds. The index is a copy of what is there, so
    # what is not there any more leaves it, and only inside the scope that was just walked, since
    # nothing outside it was looked at.
    praefix = f"{(args.scope or ARCHIVE_DIR).strip('/')}/"
    tot = [pfad for (pfad,) in db.execute("SELECT path FROM documents WHERE path LIKE ?",
                                          (praefix + "%",))
           if not (space / pfad).exists()]
    for pfad in tot:
        db.execute("DELETE FROM documents WHERE path = ?", (pfad,))
        db.execute("DELETE FROM content WHERE path = ?", (pfad,))
    db.commit()
    gesamt = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    db.close()
    print(f"ok: {gelesen} read, {uebersprungen} unchanged, {gesamt} in the index"
          + (f", {len(tot)} gone" if tot else "")
          + (f", {leer} of them carried no readable text" if leer else ""))
    if leer:
        print("  A file with no readable text is still indexed by its path, so it can be found by "
              "name and by what somebody writes about it. What it cannot do is answer a search for "
              "a word inside it.")
    return 0


def _fts_query(roh: str) -> str:
    """What somebody typed, as something the index will actually accept.

    The search language has its own punctuation, and a date, an amount or a case number is written
    in exactly that punctuation: `31.12.2024` is a syntax error, `250,00` is another, and what the
    user sees is a failure rather than an answer. Nobody searching an archive of paperwork is
    writing a query language; they are typing what is printed on the paper. So each word is passed
    as a phrase, which the index takes literally, and the operators stay available for anyone who
    types them deliberately by quoting the whole thing themselves.
    """
    roh = roh.strip()
    if roh.startswith('"') and roh.endswith('"') and len(roh) > 1:
        return roh
    if any(op in roh for op in (" AND ", " OR ", " NOT ", " NEAR(")):
        return roh
    worte = [w for w in roh.split() if w]
    if not worte:
        return roh
    return " ".join('"' + w.replace('"', '""') + '"' for w in worte)


def cmd_archive_search(args: argparse.Namespace) -> int:
    """Find a word in what is kept, and say where it stands."""
    space = _work_space(args)
    db = _archive_db(space)
    try:
        treffer = db.execute(
            "SELECT c.path, d.kind, snippet(content, 1, '[', ']', ' ... ', 12) "
            "FROM content c LEFT JOIN documents d ON d.path = c.path "
            "WHERE content MATCH ? ORDER BY rank LIMIT ?",
            (_fts_query(args.query), args.limit)).fetchall()
    except Exception as fehler:  # noqa: BLE001 -- a malformed query is the user's, not a crash
        print(f"fail: {fehler}", file=sys.stderr)
        db.close()
        return 1
    gelesen = db.execute("SELECT count(*) FROM documents").fetchone()[0]
    db.close()
    if not treffer:
        # An index that was never filled and an index without this word give the same empty
        # result, and the same sentence for both sent a search past a database that had lost its
        # content: it read as an archive nobody had indexed yet. The count separates the two.
        if gelesen == 0:
            print(f"the index is empty: nothing has been read yet, so no search can find "
                  f"anything. Run `archive index` first.")
        else:
            print(f"nothing found for {args.query!r}. The index holds the {gelesen} document(s) "
                  f"`archive index` has read; one that arrived since then is not in it yet.")
        return 1
    for pfad, art, stelle in treffer:
        print(f"  {pfad}  [{art or '?'}]")
        if stelle:
            print(f"      {' '.join(stelle.split())}")
    print(f"{len(treffer)} hit(s)")
    return 0


def cmd_retention_show(args: argparse.Namespace) -> int:
    """What applies here, or what would be proposed if nobody has decided yet."""
    space = _work_space(args)
    eigen = _retention(space)
    quelle = eigen or _retention_defaults()
    if not quelle:
        print("no keeping terms available at all", file=sys.stderr)
        return 1
    if eigen:
        print(f"in force here (confirmed {eigen.get('_confirmed', 'date not stated')}):")
        print("These are Zanmai's own periods, not statutory retention periods and not tied to any "
              "country. Do not present them as deadlines or as what a law requires.")
    else:
        print("These are Zanmai's own periods, not statutory retention periods and not tied to any "
              "country. Do not present them as deadlines or as what a law requires.")
        print(f"nothing confirmed for this space yet. These are suggestions, set on the generous "
              f"side on purpose, and they apply to nothing until the user has said whether they "
              f"fit:")
    for eintrag in quelle.get("terms", []):
        jahre = eintrag.get("years")
        dauer = f"{jahre}y" if jahre else eintrag.get("policy", "")
        print(f"  {eintrag.get('category', ''):22} {dauer:22} {eintrag.get('label', '')}")
        if args.verbose and eintrag.get("why"):
            print(f"    {eintrag['why']}")
    return 0


def cmd_retention_adopt(args: argparse.Namespace) -> int:
    """Take the suggestions into this space as the terms that apply.

    Written as a whole file rather than merged, so what is in force is always readable in one go.
    Editing single terms afterwards is a hand edit on purpose: it is rare, it is the user's
    decision, and it should feel like one.
    """
    space = _work_space(args)
    vorschlag = _retention_defaults()
    if not vorschlag:
        print("fail: no suggestions shipped with this version", file=sys.stderr)
        return 1
    ziel = space / SYSTEM_DIR / RETENTION_FILE
    if ziel.is_file() and not args.force:
        print(f"fail: {ziel.relative_to(space)} already exists. Pass --force to replace it, and "
              f"be sure the user asked for that: what is in there was decided once.",
              file=sys.stderr)
        return 1
    # Only the decision is written, never a copy of the periods. A copy would be a second list of
    # the same thing: it ages where the shipped one is improved, and no update can reach it, because
    # this file is the user's. What they change later is added here as a difference and wins.
    entscheidung = {"_comment": ("What you confirmed about how long things are kept, and anything "
                                 "you changed. The periods themselves ship with Zanmai and are "
                                 "improved with it; only your decision lives here."),
                    "_confirmed": _today()}
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(entscheidung, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"retention terms confirmed "
                         f"({len(vorschlag.get('terms', []))} periods in force)")
    print(f"ok: {len(vorschlag.get('terms', []))} term(s) now in force in "
          f"{ziel.relative_to(space)}. Change by hand what the user said did not fit; this file is "
          f"the one that counts.")
    return 0


def cmd_routing_show(args: argparse.Namespace) -> int:
    """Print the routing table, and say plainly where it is silent."""
    space = _work_space(args)
    pfad = _routing_path(space)
    if not pfad.is_file():
        print(f"no routing table yet at {pfad.relative_to(space)}. Every kind of material takes "
              f"its default route. `routing set` writes the first rule.")
        return 0
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        print(f"fail: {pfad.relative_to(space)} is not readable as JSON ({fehler}). Nothing is "
              f"routed by it until that is fixed; every kind takes its default route meanwhile.",
              file=sys.stderr)
        return 1
    regeln = [r for r in (daten.get("rules") or []) if isinstance(r, dict)]
    if not regeln:
        print(f"{pfad.relative_to(space)} exists and holds no rules.")
        return 0
    print(f"{len(regeln)} rule(s) in {pfad.relative_to(space)}, first match wins:")
    for regel in regeln:
        when = regel.get("when") or {}
        bedingung = []
        if when.get("name"):
            bedingung.append(f"name {when['name']}")
        if when.get("text"):
            worte = when["text"] if isinstance(when["text"], list) else [when["text"]]
            bedingung.append("text " + " + ".join(f'"{w}"' for w in worte))
        print(f"  {regel.get('name', '?')}")
        print(f"      when   {', '.join(bedingung) or '(nothing, so it never matches by itself)'}")
        print(f"      to     {regel.get('to') or '(no destination)'}")
        if regel.get("about"):
            print(f"      about  {regel['about']}")
        if regel.get("do"):
            print(f"      do     {regel['do']}")
        if regel.get("by"):
            print(f"      by     {regel['by']}")
        # Printed even when unanswered, because that is the interesting state: it is the one
        # question a rule of this kind leaves open, and a blank line here is what says it is coming.
        behalten = regel.get("keep")
        print(f"      keep   " + {
            "with-result": "the file itself, beside what is made from it",
            "discard": "nothing, the file goes to the trash once its content is filed",
        }.get(behalten, "(not answered yet, so you are asked the first time one arrives)"))
    return 0


def cmd_routing_set(args: argparse.Namespace) -> int:
    """Write one rule. A command rather than a hand edit, so the file stays valid JSON.

    A rule of the same name is replaced in place rather than appended: order decides which rule
    wins, and a correction that moved a rule to the end would quietly change which files it catches.
    """
    space = _work_space(args)
    pfad = _routing_path(space)
    daten = _routing(space) or {}
    daten["_comment"] = ("What incoming material is, and where it goes. Written by "
                         "`zanmai.py routing set`, read on every import. First match wins.")
    regeln = daten.setdefault("rules", [])
    if not isinstance(regeln, list):
        print(f"fail: 'rules' in {pfad.relative_to(space)} is not a list. Fix that by hand first.",
              file=sys.stderr)
        return 1
    regel = next((r for r in regeln if isinstance(r, dict) and r.get("name") == args.name), None)
    neu_angelegt = regel is None
    if regel is None:
        regel = {"name": args.name}
        regeln.append(regel)
    regel["to"] = args.to
    when = regel.setdefault("when", {})
    if args.when_name:
        when["name"] = args.when_name
    if args.when_text:
        when["text"] = list(args.when_text)
    if args.about:
        regel["about"] = args.about
    if args.do:
        regel["do"] = args.do
    if args.ask is not None:
        regel["ask_first"] = args.ask
    if getattr(args, "keep", None):
        regel["keep"] = args.keep
    if getattr(args, "by", None):
        regel["by"] = args.by
    if not when:
        print(f"note: '{args.name}' has no condition yet, so nothing matches it on its own. "
              f"Add --when-text or --when-name.")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"routing: {args.name} -> {args.to}"
                         + ("" if neu_angelegt else " (rule rewritten)"))
    print(f"ok: {args.name} -> {args.to}")
    return 0


def _import_pending(space: Path) -> list[Path]:
    """Everything waiting in the import folder, oldest first, subfolders included.

    Subfolders are walked rather than respected. Whatever structure something arrives in is the
    sender's, not an instruction, and the point of the folder is that nobody has to sort before
    dropping.
    """
    root = space / INBOX_DIR
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
    space = Path(args.space).resolve()
    files = _import_pending(space)
    if not files:
        print(f"empty: nothing waiting in {INBOX_DIR}/")
        return 0
    nach_art: dict[str, int] = {}
    ohne_regel: list[str] = []
    for f in files:
        kind, verhalten = _import_route(f)
        nach_art[kind] = nach_art.get(kind, 0) + 1
        _rank, _value, basis, shown = _recording_order_key(f)
        rel = f.relative_to(space).as_posix()
        # The kind says how to read the file and nothing about where it goes. Where the user has
        # written a rule that covers this file, that is the answer, and it is printed with the file
        # rather than left in a table nobody opens.
        regel = _route_for_file(space, f)
        if not regel:
            ohne_regel.append(rel)
        print(f"{shown:>16}  read as {kind:>10}  {rel}"
              + (f"   -> {_rule_phrase(regel)}" if regel else "   -> no rule yet"))
        if args.verbose:
            print(f"{'':>16}  {'':>18}  {verhalten}")
    zusammen = ", ".join(f"{count} {kind}" for kind, count in sorted(nach_art.items()))
    print(f"ok: {len(files)} file(s) waiting in {INBOX_DIR}/ (read as: {zusammen})")
    print("    read all of them before processing any: the later one can withdraw the earlier.")
    if ohne_regel:
        print(f"    no rule yet for {len(ohne_regel)} of them: {', '.join(ohne_regel[:6])}"
              + (", and more" if len(ohne_regel) > 6 else "") + ". Ask the user what this sort of "
              f"thing is and where it belongs, once, then write it down with `routing set <name> "
              f"<destination> --when-text <a word that appears in it>` so the next one of its sort "
              f"answers itself. Nothing leaves {INBOX_DIR}/ before its content is in the space.")
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
    space = Path(args.space).resolve()
    folder = _recordings_dir(space)
    files = _pending_recordings(space)
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
    print(f"ok: {len(files)} recording(s) waiting in {INBOX_DIR}/"
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
    """The names this space holds, as a head start for the recogniser.

    Second line of defence, deliberately small. The first line is reading the transcript
    and understanding it: a garbled word gets resolved the way a person resolves a typo,
    from the sense of the sentence, and that needs no list at all. What understanding
    cannot reach is a surname nobody could infer, a company spelled a particular way, a
    term only this space uses. That is what this is for, and it is worth having: measured,
    it fixed every name in a note where full names were spoken. Measured on ten minutes of
    a real meeting it changed almost nothing, because people say first names in a room and
    a recogniser knows those. A fallback that costs a flag on a call which happens anyway
    is worth keeping even when it is rarely the thing that saves the day.

    The one thing worth getting right is which names, because a prompt holds a few
    hundred characters and a space holds hundreds of contacts. Ordered by how much the
    space links to each one: a name a dozen notes point at is someone this person works
    with, a name nothing points at is a directory entry. Measured on a space of
    ninety-five contacts, filling alphabetically left out five of the six people in the
    recording being transcribed.
    """
    space = Path(args.space).resolve()

    inbound: dict[str, int] = {}
    patterns = space / MEMORY_DIR / "patterns.json"
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
    org_folder = space / ORGANISATIONS_DIR
    if org_folder.is_dir():
        for f in sorted(org_folder.glob("*.md")):
            org_names[f.stem], _fm = read_name(f)

    # (rank, term). The house names first: they work before the space holds anything,
    # and a spoken instruction names a specialist.
    ranked: list[tuple[int, str]] = [(10 ** 6, "Zanmai")]
    ranked += [(10 ** 6, name.capitalize()) for name, _a, _m in _ROSTER]

    for folder, is_person in ((space / PEOPLE_DIR, True),
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
        folder = space / kind
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
            out = space / args.out
        _space_mkdir(space, out.parent, parents=True, exist_ok=True)
        out.write_text(prompt + "\n", encoding="utf-8")
    print(prompt)
    print(f"ok: {len(kept)} of {len(seen)} name(s) fit the prompt "
          f"({used} of {args.budget} characters), most linked-to first", file=sys.stderr)
    return 0


def _whisper_model(space: Path) -> Path | None:
    folder = space / RUNTIME_DIR / "whisper"
    models = sorted(folder.glob("ggml-*.bin")) if folder.is_dir() else []
    return models[0] if models else None


def cmd_voice_transcribe(args: argparse.Namespace) -> int:
    """One recording to text, on this machine, biased by the space's own names."""
    space = Path(args.space).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = space / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1

    ffmpeg = _tool_path(space, "ffmpeg")
    whisper = _tool_path(space, "whisper")
    model = _whisper_model(space)
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg, which turns what a phone recorded into what the recogniser reads")
    if not whisper:
        missing.append("whisper-cli, the recogniser itself")
    if not model:
        missing.append("a model in zanmai/runtime/whisper/. Fetch it with `zanmai.py tools ensure "
                       "whisper-model`, one file of about 1.6 GB over HTTPS, once. An interrupted "
                       "fetch resumes where it stopped")
    if missing:
        print("fail: cannot transcribe, and nothing will be guessed instead. Missing:",
              file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    work = space / SCRATCH_DIR / "voice"
    work.mkdir(parents=True, exist_ok=True)
    wav = work / f"{source.stem}-16k.wav"
    subprocess.run([ffmpeg, "-y", "-i", str(source), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(wav)], check=True, capture_output=True)

    prompt = ""
    if args.lexicon:
        lex = Path(args.lexicon)
        if not lex.is_absolute():
            lex = space / args.lexicon
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
          + (f"biased by {len([x for x in prompt.split(',') if x.strip()])} space name(s)"
             if prompt else "no space names given, so names are likely wrong")
          + f"; text at {target.relative_to(space)}", file=sys.stderr)
    return 0


def cmd_voice_archive(args: argparse.Namespace) -> int:
    """Move a processed recording out of the import folder into the day it was spoken on.

    Out of the import folder so it cannot be transcribed twice, and kept rather than deleted: it is
    the user's own recording, and a transcript is a reading of it, not a replacement for it. It
    lands in the day's bundle beside whatever came out of it, because what was said on a day belongs
    to that day, and because keeping the original next to the reading is what makes a garbled word
    repairable years later.
    """
    space = Path(args.space).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = space / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1
    stamp = datetime.fromtimestamp(source.stat().st_mtime)
    target_dir = space / DAILY_DIR / stamp.strftime("%Y") / stamp.strftime("%Y-%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{stamp.strftime('%Y-%m-%d-%H%M')}-{_slugify(source.stem)}{source.suffix.lower()}"
    target = target_dir / name
    if target.exists():
        target = target.with_name(f"{target.stem}-2{target.suffix}")
    shutil.move(str(source), str(target))
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"filed recording {target.relative_to(space)}")
    print(f"ok: recording kept at {target.relative_to(space)}")
    return 0


def cmd_voice_journal_append(args: argparse.Namespace) -> int:
    """Append text to the daily note for the day a recording was made, not the day it is read.

    A recording processed days after it was spoken still belongs to the day it was
    spoken on: the words were true then, and misplacing "heute war kein guter Tag" a
    week later reads as if it happened on the wrong day. The date is derived here, from
    the recording itself, so the caller never has to work it out or remember to pass it.
    """
    space = Path(args.space).resolve()
    source = Path(args.file)
    if not source.is_absolute():
        source = space / args.file
    if not source.is_file():
        print(f"fail: no such recording: {args.file}", file=sys.stderr)
        return 1
    date, basis = _recording_date(source)
    rel = _journal_append(space, _journal_note(space, date), args.text,
                          "voice journal append")
    print(f"ok: appended to {rel} (dated by {basis})")
    return 0


def cmd_memory_log(args: argparse.Namespace) -> int:
    r"""Append one line to the activity log in the canonical format.

    Hand-written appends drifted in format, which broke the one thing the log is
    for: `grep "^## \["` parsing cleanly.
    """
    space = Path(args.space).resolve()
    log = space / MEMORY_DIR / "activity-log.md"
    if not log.exists():
        print(f"fail: no activity log at {log.relative_to(space)}", file=sys.stderr)
        return 1
    _append_activity_log(space, args.agent, args.activity)
    print(f"ok: logged for {args.agent}")
    return 0


def _resolve_space_file(space: Path, given: str) -> Path | None:
    """Accept a space-relative path or a bare basename that is unique in the space."""
    direct = (space / given).resolve()
    if direct.is_file() and str(direct).startswith(str(space)):
        return direct
    name = Path(given).name
    if not name.endswith(".md"):
        name += ".md"
    hits = [p for p in space.glob(f"**/{name}") if p.is_file() and not p.relative_to(space).as_posix().startswith((f"{SYSTEM_DIR}/", ".claude/", ".git/"))]
    if len(hits) == 1:
        return hits[0]
    return None


def cmd_index_search(args: argparse.Namespace) -> int:
    """Search the space's own text, and say how much was searched.

    Why this exists as a command: the space ships a `.gitignore` that excludes every
    user folder, on purpose, so that a clone never commits private material. Both
    common search tools honour `.gitignore` by default, so a plain recursive search
    finds only the distribution and reports an empty result. An empty result is
    indistinguishable from "does not exist", and that produced a confident written
    falsehood. Walking the tree here cannot be configured wrong, and the count of
    files searched is printed so a zero is a measurement rather than a silence.
    """
    space = Path(args.space).resolve()
    roots = [space / r for r in (args.root or USER_ROOTS + (INBOX_DIR, SYSTEM_DIR))]
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
                    print(f"{f.relative_to(space)}:{n}: {line.strip()[:200]}")
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

# The fields of a work object, in the order they are written. A field added here appears empty on
# every existing entry the next time one is read; nothing has to migrate for that.
WORK_FIELDS = [
    "id", "work", "state", "owner", "waiting for", "deliverable", "workshop",
    "updated", "due", "tokens", "minutes",
]


# Sync-hosted spaces: the normal case, and what has to stay out of the copy.
#
# A space in a synced folder is not an edge case, it is how most people get a
# backup, and it should keep working. What must not travel is what is true of one
# machine only: the provisioned interpreter and the record of which tools this
# computer has. Carried to a second machine they claim tools that are not there;
# carried into a restore they bring a runtime built for another platform. The
# snapshots are the other one, because they are full copies of the space and a
# backup does not need a backup inside it.
MACHINE_LOCAL_PATHS = (RUNTIME_DIR, SCRATCH_DIR)
BULKY_PATHS = (HISTORY_DIR,)

SYNC_HOSTS = (
    ("iCloud Drive", "exclude by renaming the folder so it ends in `.nosync`, or move the space out of iCloud"),
    ("OneDrive", "the client has no per-folder ignore file: exclude the folders in OneDrive settings, Account, Choose folders"),
    ("Dropbox", "add the paths to a `.dropboxignore` file at the top of your Dropbox folder"),
    ("Nextcloud", "the client has no per-folder ignore file: add the paths to the client's ignore list, Settings, General, Edit ignored files"),
    ("Google Drive", "the client has no per-folder ignore file: exclude the folders in the Drive preferences"),
)


def _detect_sync_host(space: Path) -> str:
    """Which sync client is this space sitting under, if any. Path and marker based."""
    text = str(space).replace("\\", "/")
    if "Library/Mobile Documents/com~apple~CloudDocs" in text or "/iCloud" in text:
        return "iCloud Drive"
    if "/OneDrive" in text:
        return "OneDrive"
    if "CloudStorage/GoogleDrive" in text or "/Google Drive" in text:
        return "Google Drive"
    for parent in [space, *space.parents]:
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


def _work_space(args: argparse.Namespace) -> Path:
    """The space a work command acts on: the root, never the folder someone happens to stand in.

    Found on the live space: a `work` call made from inside `workbench/<slug>/` created a
    second, empty `zanmai/open` there, because the default was the literal `.`. A work object
    written into it would have been invisible to every later `work list`, which is the one thing
    this database exists to prevent.
    """
    start = Path(args.space) if getattr(args, "space", None) else Path.cwd()
    wurzel = _find_space_root(start)
    return wurzel if wurzel is not None else start.resolve()


def _work_wanted_id(args: argparse.Namespace) -> str:
    """The id, given either as `--id` or as the first positional. Both, because the flag is what
    the skills write and the bare id is what a person types."""
    return (getattr(args, "id", None) or getattr(args, "id_pos", None) or "").strip()


def _work_base(space: Path) -> Path:
    return space / OPEN_DIR


def _work_id(vorhanden: set[str]) -> str:
    """A fresh id for a work object. Random, and checked against what is already there.

    It used to be derived from the title and the timestamp to the minute, which meant two objects
    opened in the same minute under the same title got the same id: the second was written into the
    list and was then unreachable, because every lookup matched the first, and closing it closed the
    other one. Two objects of the same name inside a minute is not exotic, it is what a run that
    opens one per file does. The set is passed in rather than read here, so the caller reads the
    list once and the check cannot race against its own write.
    """
    import uuid
    for _ in range(1000):
        neu = str(uuid.uuid4())
        if neu not in vorhanden:
            return neu
    raise SystemExit("fail: could not find a free work id, which should be impossible")


def _work_ensure(space: Path) -> Path:
    """Create the folder on first use and return the file the work objects live in."""
    base = _work_base(space)
    base.mkdir(parents=True, exist_ok=True)
    (base / "pages").mkdir(exist_ok=True)
    datei = base / WORK_FILE
    if not datei.is_file():
        datei.write_text(json.dumps({"work": []}, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    return datei


def _work_read(space: Path) -> tuple[list[dict], list[str]]:
    """Every work object, and the field order to write them back in.

    A file that will not parse is not treated as an empty list: this is the machine's record of what
    it still owes, and answering "nothing open" from a broken file is worse than failing. A field the
    file has not seen yet reads as empty, which is what makes adding one free.
    """
    datei = _work_ensure(space)
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise SystemExit(f"fail: {datei.relative_to(space).as_posix()} will not parse as JSON "
                         f"({fehler}). Nothing is read from it until that is fixed, because "
                         f"answering 'nothing open' out of a broken file is the one wrong answer.")
    eintraege = daten.get("work") if isinstance(daten, dict) else None
    if not isinstance(eintraege, list):
        eintraege = []
    felder = list(WORK_FIELDS)
    for eintrag in eintraege:
        for name in eintrag:
            if name not in felder:
                felder.append(name)
    rows = [{name: str(eintrag.get(name, "") or "") for name in felder}
            for eintrag in eintraege if isinstance(eintrag, dict)]
    return rows, felder


def _work_write(space: Path, rows: list[dict], headers: list[str]) -> None:
    """Write the whole list back. Empty fields are dropped rather than stored as empty strings."""
    datei = _work_ensure(space)
    eintraege = [{h: row[h] for h in headers if str(row.get(h, "")).strip()} for row in rows]
    datei.write_text(json.dumps({"work": eintraege}, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def _work_adopt_legacy(space: Path) -> str:
    """Carry a space that still has the old `.base` folder across, once. Returns what it did.

    Reads the CSV rather than trusting the schema beside it: the schema described views, the CSV
    held the work. The pages move as they are, the old folder goes to the trash rather than being
    deleted, and a space that has already crossed is left alone.
    """
    alt_dir = space / LEGACY_OPEN_DIR
    alt_csv = alt_dir / "data.csv"
    if not alt_csv.is_file():
        return ""
    neu_datei = _work_ensure(space)
    import csv as _csv
    with alt_csv.open(newline="", encoding="utf-8") as fh:
        rows = [dict(r) for r in _csv.DictReader(fh)]
    vorhanden, felder = _work_read(space)
    bekannt = {r.get("id") for r in vorhanden}
    dazu = [r for r in rows if r.get("id") and r.get("id") not in bekannt]
    for row in dazu:
        for name in row:
            if name not in felder:
                felder.append(name)
    _work_write(space, vorhanden + [{k: (v or "") for k, v in r.items()} for r in dazu], felder)

    seiten = 0
    alt_pages = alt_dir / "pages"
    neu_pages = _work_base(space) / "pages"
    if alt_pages.is_dir():
        for seite in sorted(alt_pages.glob("*.md")):
            ziel = neu_pages / seite.name
            if not ziel.exists():
                shutil.move(str(seite), str(ziel))
                seiten += 1
    # Deliberately not `.resolve()`: the space path is taken as it was given, and resolving only
    # this half of the comparison turns a symlinked parent into "outside the space". Built as
    # `space / ...`, it is inside by construction.
    if alt_dir.is_dir() and _move_into(space, alt_dir, TRASH_DIR,
                                       f"replaced by {OPEN_DIR}/", dated=True) != 0:
        return (f"work objects were copied to {neu_datei.relative_to(space).as_posix()}, but "
                f"{LEGACY_OPEN_DIR}/ could not be moved out of the way. Both lists exist until "
                f"that is dealt with by hand.")
    return (f"work objects moved from {LEGACY_OPEN_DIR}/ to "
            f"{neu_datei.relative_to(space).as_posix()}: {len(dazu)} entry(s), {seiten} page(s)")


def _work_find(rows: list[dict], wanted: str) -> dict | None:
    """Match on the full id or on a leading fragment, so a human can type eight chars."""
    exact = [r for r in rows if r.get("id") == wanted]
    if exact:
        return exact[0]
    partial = [r for r in rows if str(r.get("id", "")).startswith(wanted)]
    return partial[0] if len(partial) == 1 else None


def _work_page(space: Path, row_id: str) -> Path:
    return _work_base(space) / "pages" / f"{row_id}.md"


def cmd_work_open(args: argparse.Namespace) -> int:
    """Open a work object. Returns its id, which every later call uses."""
    space = _work_space(args)
    titel = (args.title or args.title_pos or "").strip()
    for feld, wert in (("the title", titel), ("--goal", getattr(args, "goal", "") or "")):
        meldung = _refuse_umlaut_verlust(wert, feld)
        if meldung:
            print(meldung, file=sys.stderr)
            return 1
    if not titel:
        print("fail: no title. Give it as `work open \"the title\"` or as `--title \"the title\"`.",
              file=sys.stderr)
        return 1
    if args.due and not _task_date_ok(args.due):
        print("fail: --due expects YYYY-MM-DD", file=sys.stderr)
        return 1
    rows, headers = _work_read(space)
    row_id = _work_id({str(r.get("id", "")) for r in rows})
    row = {h: "" for h in headers}
    row.update({
        "id": row_id, "work": titel, "state": "open", "owner": args.owner or "",
        "deliverable": args.deliverable or "", "workshop": args.workshop or "",
        "updated": _today(), "due": args.due or "",
    })
    rows.append(row)
    _work_write(space, rows, headers)
    page = _work_page(space, row_id)
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
    _append_activity_log(space, args.owner or "zanmai.py", f"opened work '{titel}' ({row_id[:8]})")
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
    space = _work_space(args)
    rows, headers = _work_read(space)
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
    _work_write(space, rows, headers)
    page = _work_page(space, row["id"])
    _work_append_section(page, "Waiting on you", f"- **{_today()}** {args.question}")
    _work_append_section(page, "Log", f"- {_timestamp_log()} asked: {args.question.splitlines()[0][:120]}")
    print(f"ok: {row['id'][:8]} is waiting on the user")
    # Said at the one moment somebody is certain to read it: right after writing the question down.
    # A work object is read at the start of a session and when somebody goes looking, neither of
    # which happens while a run is in flight. A background run that wrote its question here and
    # then waited for an answer waited for something nobody had been shown.
    print("note: this question is now on the work object, which is not somewhere the user is "
          "looking right now. Put it in your result and return; do not wait for an answer. Only a "
          "run the user can see may park (operating-principles 12).", file=sys.stderr)
    return 0


def cmd_work_answer(args: argparse.Namespace) -> int:
    """Record the user's answer and put the object back to work."""
    space = _work_space(args)
    rows, headers = _work_read(space)
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
    _work_write(space, rows, headers)
    page = _work_page(space, row["id"])
    _work_append_section(page, "Decided", f"- **{_today()}** {args.answer}")
    _work_append_section(page, "Log", f"- {_timestamp_log()} answered")
    print(f"ok: {row['id'][:8]} answered and back to open")
    return 0


def cmd_work_log(args: argparse.Namespace) -> int:
    """Append one line to the object's log, and add up what the work has cost."""
    space = _work_space(args)
    rows, headers = _work_read(space)
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
    _work_write(space, rows, headers)
    who = f"{args.agent}: " if args.agent else ""
    _work_append_section(_work_page(space, row["id"]), "Log", f"- {_timestamp_log()} {who}{args.note}")
    print(f"ok: logged on {row['id'][:8]} (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_done(args: argparse.Namespace) -> int:
    space = _work_space(args)
    rows, headers = _work_read(space)
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
    _work_write(space, rows, headers)
    _work_append_section(_work_page(space, row["id"]), "Log", f"- {_timestamp_log()} closed")
    _append_activity_log(space, args.agent or "zanmai.py", f"closed work '{row.get('work')}' ({row['id'][:8]})")
    print(f"ok: {row['id'][:8]} closed (tokens {row.get('tokens') or 0}, minutes {row.get('minutes') or 0})")
    return 0


def cmd_work_show(args: argparse.Namespace) -> int:
    """One work object, whole: the row and the page under it.

    `list` prints a short id and every other command takes one, so the one thing missing was a way
    to read what that id stands for. Without it the only route to the content was the page folder
    and its full uuid, which is the machine's own filing and not something anyone should have to
    know. Found in practice: when a live session went looking for it and had to `ls` the folder.
    """
    space = _work_space(args)
    rows, _headers = _work_read(space)
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
    page = _work_page(space, row["id"])
    if page.is_file():
        print()
        print(page.read_text(encoding="utf-8").rstrip())
    else:
        print("\n(no page on disk for this object)")
    return 0


def cmd_work_list(args: argparse.Namespace) -> int:
    """What is open, and what is waiting on the user. Prints the denominator."""
    space = _work_space(args)
    rows, _headers = _work_read(space)
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
# disagree with, and `life/` is already defined as what they have settled on. Shuri writes it;
# Carol, Loki and Luis read it and produce from it.
#
# The gate exists because a piece rendered against an invented colour looks finished and is wrong,
# and by then the render time and, with generated imagery, the money are already spent. So the
# check runs before the dispatch, not inside it.
#
# What counts as unfilled is the template's own angle-bracket placeholder. That is deliberate: an
# empty field says "not decided yet", where a plausible default would quietly make a decision the
# user never made, and nothing downstream could tell the two apart afterwards.

BRAND_DIR = f"{LIFE_DIR}/brands"
_BRAND_PLACEHOLDER_RE = re.compile(r"<[^<>\n]{2,}>")


def _brand_root(space: Path) -> Path:
    return space / BRAND_DIR


def _brand_file(space: Path, name: str) -> Path:
    return _brand_root(space) / name / "design.md"


def _brand_names(space: Path) -> list[str]:
    root = _brand_root(space)
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
    space = Path(args.space).resolve()
    namen = [n for n in _brand_names(space)
             if _brand_named(_brand_file(space, n).read_text(encoding="utf-8"))]
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
        pfad = _brand_file(space, name)
        text = pfad.read_text(encoding="utf-8")
        gaps = _brand_gaps(text)
        befunde = _brand_findings(_brand_frontmatter(text))
        rel = pfad.relative_to(space).as_posix()
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
    space = Path(args.space).resolve()
    namen = _brand_names(space)
    for name in namen:
        print(f"{name}  {_brand_file(space, name).relative_to(space).as_posix()}")
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
# Three spellings, because three are in use. The brackets used to be required, and the bare
# `due:2026-09-15` that the space itself writes was therefore not a date at all: two live tasks sat
# in the undated pile from the day they were written, one of them a flight that expires.
_TASK_DUE_RE = re.compile(r"(?:\U0001F4C5|\(?\bdue:?)\s*(\d{4}-\d{2}-\d{2})\)?")
_TASK_HEADING = "## Tasks"
_TASK_SKIP_ROOTS = (SYSTEM_DIR, HOST_DIR, INBOX_DIR)


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


# When a piece of work on the desk has been still long enough to be worth a word. Two weeks,
# because a week is an ordinary gap in anything that waits on somebody else and two is where a
# thing stops being between steps and starts being forgotten. It is a reminder, never a demand:
# nothing has to move because this line appeared.
DESK_IDLE_DAYS = 14


def _desk_idle(space: Path, days: int = DESK_IDLE_DAYS) -> list[dict]:
    """Pieces on the desk nobody has touched for a while, oldest first.

    Left out: anything the truth file marks `done` or `cancelled`, and anything marked `waiting`
    whose `due:` has not arrived. The second is the point of that value. Parking a thing on a
    workshop three weeks out is a decision, and a decision that gets asked about every morning was
    not recorded, it was ignored.
    """
    wurzel = space / WORKBENCH_DIR
    if not wurzel.is_dir():
        return []
    heute = datetime.now().date()
    grenze = datetime.now().timestamp() - days * 86400
    raus: list[dict] = []
    for ordner in sorted(p for p in wurzel.iterdir() if p.is_dir()):
        dateien = [f for f in ordner.rglob("*") if f.is_file()]
        if not dateien:
            continue
        wahrheit = ordner / f"{ordner.name}.md"
        status, faellig, angefasst = "", "", ""
        try:
            inhalt = wahrheit.read_text(encoding="utf-8")
            status = _status_of(inhalt)
            fm, _o, _b = _split_frontmatter(inhalt)
            faellig = str(fm.get("due") or "").strip()
            angefasst = str(fm.get("updated") or "").strip()
        except (OSError, UnicodeDecodeError):
            pass
        # When somebody last worked on this, not when a file was last written. An update rewrites
        # a `kind:` line and moves a folder, which sets a fresh modification time on everything it
        # touches. After an update every piece reads as touched today, and the reminder that exists
        # to notice a forgotten one stays silent for another two weeks. The truth file's
        # own `updated:` says what actually happened; the file time is the fallback where it is
        # missing.
        if angefasst and _task_date_ok(angefasst):
            neueste = datetime.strptime(angefasst, "%Y-%m-%d").timestamp()
        else:
            neueste = max(f.stat().st_mtime for f in dateien)
        if neueste >= grenze:
            continue
        if status in STATUS_CLOSED:
            continue
        if status == "waiting" and faellig and _task_date_ok(faellig):
            if datetime.strptime(faellig, "%Y-%m-%d").date() > heute:
                continue
        raus.append({
            "slug": ordner.name,
            "label": _buendel_titel(space, f"{WORKBENCH_DIR}/{ordner.name}"),
            "days": int((datetime.now().timestamp() - neueste) / 86400),
            "files": len(dateien),
            "status": status,
        })
    return sorted(raus, key=lambda e: e["days"], reverse=True)


def _status_of(content: str) -> str:
    """The `status:` a file's frontmatter carries, lowercased. Empty when it carries none.

    Reads the raw text rather than taking a parsed dict, because every caller here already has the
    text in hand and parsing the whole block to look at one field is the expensive way round.
    """
    if not content.startswith("---"):
        return ""
    ende = content.find("\n---", 4)
    if ende == -1:
        return ""
    for zeile in content[3:ende].splitlines():
        if zeile.startswith("status:"):
            return zeile.split(":", 1)[1].strip().strip('"').strip("'").lower()
    return ""


def _task_scan(space: Path, only_open: bool = True) -> list[dict]:
    """Every task line in the user's part of the space, wherever it sits.

    Folder-independent on purpose, and that is the whole point of it. A deadline does not stop being
    one because the bundle around it was archived; the flight that made this necessary disappeared
    from view the moment its trip bundle left `life/`, with the money still in play. Left out are
    the system folder (the machine's own files), the host folder, the import queue and database
    folders, which an editor writes and nobody types by hand.
    """
    treffer: list[dict] = []
    for md in sorted(space.rglob("*.md")):
        if not md.is_file():
            continue
        rel = md.relative_to(space).as_posix()
        kopf = rel.split("/", 1)[0]
        if kopf in _TASK_SKIP_ROOTS or kopf.startswith("."):
            continue
        if _is_inside_database_folder(rel):
            continue
        try:
            inhalt = md.read_text(encoding="utf-8")
            zeilen = inhalt.splitlines()
            geaendert = md.stat().st_mtime
        except (OSError, UnicodeDecodeError):
            continue
        # A cancelled trip still carries every checkbox it ever had. Reading them out at session
        # start is how a cancelled booking was offered as a live decision while the replacement
        # trip sat two lines below it, and no amount of thinking about the list could catch that:
        # the list was right about the file and the file was out of date. So the file says it once,
        # in `status:`, and every task line under it goes quiet.
        if _status_of(inhalt) in STATUS_CLOSED:
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


# How far ahead a dated task counts as open. A week: near enough that doing it now is sensible, far
# enough that Friday's deadline is visible on Monday. Beyond it the task exists and is findable, it
# is simply not today's business, and reading it out every session until then trains the user to
# skip the list. Anything already due, however old, stays open by definition.
TASK_OPEN_HORIZON_DAYS = 7


def _task_due_soon(space: Path, days: int, eintraege: list[dict] | None = None) -> list[dict]:
    """Open tasks whose date falls inside the window, overdue ones first. Undated ones stay out.

    Undated stay out because a list of everything open is read once and skipped forever after. What
    earns a line at the start of a session is a date that is about to pass.
    """
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    faellig: list[dict] = []
    for eintrag in (_task_scan(space) if eintraege is None else eintraege):
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


def _dated_files_ahead(space: Path, days: int) -> list[dict]:
    """Files whose own name carries a date from today onward, anywhere in the user's folders.

    The other three date sources are places the machine keeps itself: a task line it wrote, a bundle's
    `due:` field, a work object. A meeting prepared yesterday for tomorrow sits in none of them, and on
    2026-08-12 that is exactly what went missing from a greeting while the file for it lay in the
    space. A date in a filename is the user's own convention and costs one walk to read.

    The system folder and the journal are skipped: a log or a daily entry named by its date is the
    date axis itself, not something coming up.
    """
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    treffer: list[dict] = []
    for pfad in space.rglob("*.md"):
        rel = pfad.relative_to(space)
        erste = rel.parts[0]
        if erste.startswith(".") or erste in (SYSTEM_DIR, INBOX_DIR, JOURNAL_DIR):
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
        try:
            if _status_of(pfad.read_text(encoding="utf-8")) in STATUS_CLOSED:
                continue
        except (OSError, UnicodeDecodeError):
            continue
        treffer.append({
            "date": m.group(0),
            "days": (wann - heute).days,
            # the date comes out wherever it sits. Cutting the first ten characters assumed it
            # always leads: `UEBERGABE-2026-08-27` then kept the date as its own label and showed
            # up in a greeting as "2026 08 27", a thing nobody had ever named.
            "label": _human_label_for_slug(
                (pfad.stem[:m.start()] + pfad.stem[m.end():]).strip("-_ ") or pfad.stem),
            "path": rel.as_posix(),
        })
    return sorted(treffer, key=lambda e: e["days"])


def _work_due_soon(space: Path, days: int) -> list[dict]:
    """Unfinished work objects with a date inside the window, overdue first."""
    heute = datetime.now().date()
    grenze = heute + timedelta(days=days)
    rows, _headers = _work_read(space)
    faellig = []
    for row in rows:
        wert = (row.get("due") or "").strip()
        if not wert or not _task_date_ok(wert) or row.get("state") == "done":
            continue
        if datetime.strptime(wert, "%Y-%m-%d").date() <= grenze:
            faellig.append(row)
    return sorted(faellig, key=lambda r: abs((datetime.strptime(r["due"], "%Y-%m-%d").date() - heute).days))


# How often a recurring task comes back, and how far ahead that is. Kept as a table rather than as
# a calculation, because a month is not thirty days and a quarter is not ninety: the next one falls
# on the same day of the month, and where that day does not exist the month decides.
_TASK_EVERY = {"weekly": 7, "monthly": 1, "quarterly": 3, "yearly": 12}


def _task_next_due(due: str, every: str) -> str:
    """The next occurrence after this one, or "" where there is none.

    Days are added for a weekly one and months for the rest, which is why they are not the same
    calculation. A 31st in a month that has thirty days lands on the last day of that month, the
    way a person would read it, rather than sliding into the next.
    """
    if every not in _TASK_EVERY or not _task_date_ok(due):
        return ""
    tag = datetime.strptime(due, "%Y-%m-%d").date()
    if every == "weekly":
        return (tag + timedelta(days=7)).isoformat()
    monate = _TASK_EVERY[every]
    jahr, monat = tag.year + (tag.month - 1 + monate) // 12, (tag.month - 1 + monate) % 12 + 1
    letzter = [31, 29 if (jahr % 4 == 0 and jahr % 100 != 0) or jahr % 400 == 0 else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1]
    return f"{jahr:04d}-{monat:02d}-{min(tag.day, letzter):02d}"


def _ensure_tasks_file(space: Path) -> Path:
    """The one list for tasks that belong to no matter in the space, created if it is not there."""
    datei = space / TASKS_FILE
    if not datei.exists():
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(
            "# Tasks\n\n"
            "Everything to do that belongs to no particular matter in this space. Tasks that do "
            "belong to one live in that bundle, next to the material they are about.\n\n"
            "This is your file. Write in it, tick things off, delete lines, sort it how you like. "
            "One task per line, starting `- [ ]`, and a date as `\U0001F4C5 YYYY-MM-DD` where "
            "there is one.\n\n",
            encoding="utf-8")
    return datei


def _task_target(space: Path, given: str | None, due: str = "") -> Path:
    """Where a commissioned task goes: the file the user named, else the one task list.

    A task that belongs to a matter goes into that matter's bundle, beside the material it is
    about, and the caller names that file. Everything else lands in `TASKS.md` at the space root:
    the haircut to book, the tablets at nine, the thing somebody said in passing. One file, at the
    top, editable by hand in any editor.

    It used to go into a journal day instead, today's for an undated task and the due day's for a
    dated one. The second half was the mistake. A reminder for an anniversary eleven months out
    created a journal entry in a year nobody had reached yet, holding one line, and the journal is
    a record of days that happened rather than a place to file the future. The date now says when
    something surfaces, not where it lives.
    """
    if not given:
        return _ensure_tasks_file(space)
    bekannt = _resolve_space_file(space, given)
    return bekannt if bekannt is not None else (space / given)


# How long a task line may be. Not a style preference: a line this long is no longer something you
# can read and act on, and the material that makes it long is always material that already sits
# somewhere else in the space. Measured against real lines in a working space, the longest
# legitimate one ran to about 120 characters.
TASK_TEXT_MAX = 160


def cmd_task_add(args: argparse.Namespace) -> int:
    """Write a task the user asked for onto one of their lists."""
    space = Path(args.space).resolve()
    due = (args.due or "").strip()
    if due and not _task_date_ok(due):
        print("fail: --due expects YYYY-MM-DD", file=sys.stderr)
        return 1
    text = args.text.strip()
    if not text:
        print("fail: a task needs words", file=sys.stderr)
        return 1
    meldung = _refuse_umlaut_verlust(text, "the task")
    if meldung:
        print(meldung, file=sys.stderr)
        return 1
    # A task is an action, in one line. Asked to merge four scattered lines about one flight into
    # one task, a run produced three lines carrying a booking number, a price, a phone number, a
    # refund figure, a rebooking fee and three separate dates, every one of which already stood
    # four lines higher in the same file. Merging is not addition: the context goes where context
    # lives and the task points at it. Past this length the line stops being readable as a thing to
    # do and becomes a note with a checkbox in front of it.
    if len(text) > TASK_TEXT_MAX:
        print(f"fail: this is {len(text)} characters, and a task line holds {TASK_TEXT_MAX}. "
              f"Do not simply cut it: what gets cut is information somebody needs, and losing it "
              f"is the same mistake in the other direction. Put the numbers, amounts, deadlines, "
              f"reference numbers and reasoning where they belong, in the bundle or the journal "
              f"entry, and point the task at that with `--see <slug>`, which writes the link into "
              f"the line. Where they are already written down somewhere, and they usually are, "
              f"nothing needs filing and only the link is missing. Where several tasks are merged, "
              f"the context is filed once, not added together.", file=sys.stderr)
        return 1
    # The link is part of the line, not decoration. A task with context elsewhere and no way to
    # reach it is a task whose reader has to go looking, and going looking is what the context was
    # written down to prevent.
    verweis = (getattr(args, "see", "") or "").strip().strip("[]")
    if verweis:
        text = f"{text} ([[{verweis}]])"
    target = _task_target(space, args.file, due)
    if target.suffix.lower() not in (".md", ".markdown"):
        print(f"fail: a task belongs in a markdown file, not in {target.name}", file=sys.stderr)
        return 1
    try:
        rel = target.resolve().relative_to(space).as_posix()
    except ValueError:
        print(f"fail: {args.file} is outside the space", file=sys.stderr)
        return 1

    jeder = (getattr(args, "every", "") or "").strip()
    if jeder and jeder not in _TASK_EVERY:
        print(f"fail: --every takes one of {', '.join(sorted(_TASK_EVERY))}", file=sys.stderr)
        return 1
    if jeder and not due:
        print("fail: --every needs a --due to count from", file=sys.stderr)
        return 1
    # The repeat is written into the line itself, not into a list beside it. A second list would
    # have to be kept in step with the first, and the day somebody edits the task by hand in their
    # editor is the day the two stop agreeing.
    zeile = (f"- [ ] {text}" + (f" \U0001F4C5 {due}" if due else "")
             + (f" (every {jeder})" if jeder else ""))
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
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"task written for the user -> {rel}: {text}")
    print(f"ok: {rel}: {zeile}")
    return 0


def cmd_task_done(args: argparse.Namespace) -> int:
    """Tick a task off. One unmistakable match or nothing: a tick on the wrong line is a false report."""
    space = Path(args.space).resolve()
    muster = args.text.strip().lower()
    kandidaten = [t for t in _task_scan(space) if muster in t["text"].lower()]
    if args.file:
        gesucht = _task_target(space, args.file)
        try:
            rel = gesucht.resolve().relative_to(space).as_posix()
        except ValueError:
            print(f"fail: {args.file} is outside the space", file=sys.stderr)
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
    pfad = space / treffer["path"]
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    stelle = treffer["line"] - 1
    passt = _TASK_LINE_RE.match(zeilen[stelle])
    if passt is None:
        print(f"fail: {treffer['path']}:{treffer['line']} changed while it was being read", file=sys.stderr)
        return 1
    zeilen[stelle] = f"{passt.group('indent')}{passt.group('bullet')}x{passt.group('rest')}"
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    _append_activity_log(space, args.agent or "zanmai.py",
                         f"task ticked for the user -> {treffer['path']}: {treffer['text']}")
    print(f"ok: ticked in {treffer['path']}: {treffer['text']}")

    # A recurring task writes its next occurrence the moment this one is ticked, into the journal
    # day it falls on. Doing it here rather than on a schedule is what keeps it from being missed:
    # there is no sweep to run and nothing to remember, and the day it comes round it is already
    # standing in that day's entry, where somebody will be looking anyway.
    alte_zeile = zeilen[stelle]
    wieder = re.search(r"\(every (weekly|monthly|quarterly|yearly)\)", alte_zeile)
    faellig = _task_due(alte_zeile)
    if wieder and faellig:
        naechste = _task_next_due(faellig, wieder.group(1))
        if naechste:
            roh = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "", alte_zeile).strip()
            roh = _TASK_DUE_RE.sub("", roh)
            roh = re.sub(r"\(every \w+\)", "", roh).strip()
            weiter = argparse.Namespace(space=str(space), text=roh, file=None, due=naechste,
                                        see=None, every=wieder.group(1),
                                        agent=args.agent or "zanmai.py")
            cmd_task_add(weiter)
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """What is open across the whole space, dated first, with the deadline said in days."""
    space = Path(args.space).resolve()
    if args.due_within is not None:
        eintraege = _task_due_soon(space, args.due_within)
        gesamt = len(eintraege)
    else:
        alle = _task_scan(space)
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
    bundle hierarchy use (Niederlande > Zandvoort, Computer > Retrocomputing
    > Maximite), this command adds the truth file without re-running
    `bundle create`.

    The body holds a one-line "Part of [[<parent>]]" reference and a short
    title heading. Additional content is added later via ordinary edits.
    """
    space = Path(args.space).resolve()
    kind = args.kind
    if kind not in KIND_FIELDS:
        print(f"fail: unknown kind {kind}", file=sys.stderr)
        return 1
    segments, slug = _slugify_bundle_path(args.bundle_slug)
    if len(segments) < 2:
        print(f"fail: '{args.bundle_slug}' is not a sub-bundle path (must be parent/child or deeper)", file=sys.stderr)
        return 1
    bundle_dir = space / _kind_folder(kind) / Path(*segments)
    if not bundle_dir.exists():
        print(f"fail: sub-bundle folder does not exist: {bundle_dir.relative_to(space)}", file=sys.stderr)
        print("hint: run `bundle create --kind <k> --slug <parent>/<child>` first", file=sys.stderr)
        return 1
    truth_path = bundle_dir / f"{slug}.md"
    if truth_path.exists():
        print(f"fail: truth file already exists: {truth_path.relative_to(space)}", file=sys.stderr)
        return 1

    parent_slug = segments[-2]
    title = args.title or slug.replace("-", " ").title()

    additions: dict = {"_title": title}
    for key in ("goal", "status", "due", "topic"):
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

    bundle_rel = bundle_dir.relative_to(space).as_posix()
    _append_activity_log(
        space, "zanmai.py",
        f"created sub-bundle truth {bundle_rel}/{slug}.md (parent [[{parent_slug}]])"
    )
    print(f"ok: sub-bundle truth at {truth_path.relative_to(space)}, parent [[{parent_slug}]]")
    return 0






def cmd_rename_slug(args: argparse.Namespace) -> int:
    """Atomic slug rename for an existing markdown file in the space.

    Performs five steps as one operation:
      1. Rename the markdown file in place (`<old>.md` -> `<new>.md`).
      2. Update the frontmatter `slug:` field to the new value.
      3. Rewrite space-wide wikilinks via `update wikilinks` (honouring
         the default scope and hard-exclude rules).
      4. Refresh the master `INDEX.md`.
      5. Append one activity-log line.

    Replaces the previous five-step manual workaround (stage temp file,
    bundle add-file with new name, manual `source_detail` fix, trash old,
    update wikilinks). The manual sequence risked frontmatter corruption.

    The old slug is located either via `--bundle-slug`/`--bundle-kind` when
    given, or by a space-wide search for `<old>.md` filtered by the hard-
    exclude set (no matches inside snapshots, logs, trash, archive, import,
    distribution). When the search returns multiple candidates, the command
    refuses and asks the caller to disambiguate.
    """
    space = Path(args.space).resolve()
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
        bundle_dir, _bundle_kind, _ = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
        if not bundle_dir:
            print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
            return 1
        old_path = bundle_dir / f"{old_slug}.md"
        if not old_path.exists():
            print(f"fail: file does not exist: {old_path.relative_to(space)}", file=sys.stderr)
            return 1
    else:
        candidates = [
            m for m in space.rglob(f"{old_slug}.md")
            if not _is_excluded_from_wikilink_ops(m.relative_to(space).as_posix())
        ]
        if not candidates:
            print(f"fail: no file matching '{old_slug}.md' found in the active space", file=sys.stderr)
            return 1
        if len(candidates) > 1:
            paths = "\n  ".join(str(c.relative_to(space)) for c in candidates)
            print(f"fail: ambiguous, multiple files match '{old_slug}.md':\n  {paths}", file=sys.stderr)
            print("hint: pass --bundle-slug <slug> --bundle-kind <kind> to disambiguate", file=sys.stderr)
            return 1
        old_path = candidates[0]

    new_path = old_path.parent / f"{new_slug}.md"
    if new_path.exists():
        print(f"fail: target already exists: {new_path.relative_to(space)}", file=sys.stderr)
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

    # 4. A bundle carries its name twice, on its main file and on the folder around it. Renaming
    # only the file leaves the folder saying the old thing, and the next run reaches for `mv` by
    # hand, outside every check this command exists to run. So the folder comes along, and only
    # where it really is this bundle's own: `<slug>/<slug>.md`.
    ordner = old_path.parent
    umbenannt = None
    if ordner.name == old_slug and ordner != space:
        ziel = ordner.parent / new_slug
        if ziel.exists():
            print(f"fail: {ziel.relative_to(space).as_posix()} already exists, so the folder "
                  f"cannot follow the name. Nothing was changed.", file=sys.stderr)
            # Put the file back, the operation is one thing or nothing.
            new_path.rename(old_path)
            return 1
        ordner.rename(ziel)
        umbenannt = ziel
        new_path = ziel / new_path.name
    bundle_rel = (umbenannt or ordner).relative_to(space).as_posix()

    # 5. Update wikilinks space-wide via the existing subcommand
    wikilink_args = argparse.Namespace(space=str(space), old=old_slug, new=new_slug,
                                      scope=None, verbose=False, quiet=True)
    cmd_update_wikilinks(wikilink_args)

    # 6. Refresh master INDEX
    _update_master_index(space)

    # 7. Activity log (one line capturing the whole atomic operation)
    _append_activity_log(
        space, "zanmai.py",
        f"slug rename {old_slug} -> {new_slug} in {bundle_rel}"
    )

    # The old name can survive in running text, where no wikilink rewrite reaches it: a sentence in
    # a neighbouring bundle's page, a description in an INDEX. Looking for that is the command's job
    # and not the caller's, and this is why. A run that has to check for itself runs a search, sees
    # its results, and then reports them, which is how a person ends up being told that a field
    # called source_detail still carries the old name in a provenance note. That sentence asks
    # nothing and means nothing to them. Whatever the history holds is history and is never counted:
    # the same exclusion the wikilink rewrite uses decides what history is.
    reste = []
    for pfad in space.rglob("*.md"):
        rel = pfad.relative_to(space).as_posix()
        if _is_excluded_from_wikilink_ops(rel) or pfad == new_path:
            continue
        try:
            if old_slug in pfad.read_text(encoding="utf-8", errors="ignore"):
                reste.append(rel)
        except OSError:
            continue

    # What this prints is what gets repeated to the user, so it says the result, the way back, and
    # anything actually left to do. Not the files it touched: a list invites a run to read it out.
    print(f"ok: {old_slug} is now {new_slug}, in {bundle_rel}")
    print(f"undo: bundle rename --old {new_slug} --new {old_slug}")
    if reste:
        print(f"still says {old_slug} in running text, so it reads wrong now: "
              f"{', '.join(reste[:5])}" + (f" and {len(reste) - 5} more" if len(reste) > 5 else ""))
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
    space = Path(args.space).resolve()
    scope_arg = args.scope or ""
    candidate = Path(scope_arg)
    if not candidate.is_absolute():
        # Resolve relative scope against the space, not the cwd.
        candidate = space / scope_arg
    scope = candidate.resolve() if scope_arg else space
    if not scope.exists() or not scope.is_dir():
        print(f"fail: scope is not a directory: {scope}", file=sys.stderr)
        return 1

    try:
        scope_rel = scope.relative_to(space).as_posix()
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


def _rename_map_path(space: Path) -> Path:
    """Location of the attachment rename map. AI-internal state, not in the
    user space. Hidden so it does not appear in the user's file listings."""
    return space / MEMORY_DIR / ".embed-rename-map.json"


def _load_rename_map(space: Path) -> dict[str, str]:
    """Read the attachment rename map (original-basename -> new-basename).
    Returns an empty dict when the file is missing or unreadable."""
    path = _rename_map_path(space)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_rename_map(space: Path, mapping: dict[str, str]) -> None:
    """Write the attachment rename map. Creates the parent directory if
    needed."""
    path = _rename_map_path(space)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record_rename(space: Path, original_name: str, new_name: str) -> None:
    """Record that an attachment was copied with a rename (original -> new).
    `update embeds` reads this map when the direct-basename and prefix-fallback
    lookups fail, so plan-driven renames at copy time get resolved automatically."""
    if not original_name or not new_name or original_name == new_name:
        return
    mapping = _load_rename_map(space)
    mapping[original_name] = new_name
    _save_rename_map(space, mapping)


def cmd_update_embeds(args: argparse.Namespace) -> int:
    """Rewrite `![[basename]]` and `![alt](path)` embeds in a bundle's markdown bodies so they
    point at the file they mean, inside the same bundle.

    Walks every `.md` file under the bundle directory (recursive, so sub-bundles are included). For
    each embed match, looks up the basename among the bundle's own non-markdown files. If found,
    the embed is rewritten with the path relative to the markdown file's folder. Body text outside
    embeds is untouched.

    The search stays inside the bundle because that is where attachments live: a bundle holds
    everything about one matter regardless of file type, so the picture a note embeds is a file
    beside it, not an entry in a shared pool somewhere else in the space.

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
    space = Path(args.space).resolve()
    bundle_dir, bundle_kind, _leaf = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
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
        rel_bundle = bundle_dir.relative_to(space).as_posix()
        print(f"ok: no attachments in {rel_bundle}/ (nothing this run could resolve against)")
        return 0

    rename_map = _load_rename_map(space)
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
            files_changed.append(str(md.relative_to(space)))

    _append_activity_log(
        space, "zanmai.py",
        f"updated embeds in {bundle_dir.relative_to(space)} "
        f"({embeds_rewritten} embed(s) in {len(files_changed)} file(s))"
    )
    if files_changed:
        for f in files_changed:
            print(f"  {f}")
    already = embeds_seen - embeds_rewritten - len(unresolved)
    rel_bundle = bundle_dir.relative_to(space).as_posix()
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
        _save_rename_map(space, {})
        print(f"  cleared rename map ({len(rename_map)} entry/entries removed)")

    return 0







def cmd_archive_review_item(args: argparse.Namespace) -> int:
    """Move a read-once briefing off the desk into the logs, by year and month.

    For the read-once-briefing kind of item: a consolidation or a one-shot summary written for a
    single decision. The user has read it, so it moves to the machine's own side, where it stays
    browsable without sitting on the desk. The desk is the one place that empties, and this is one
    of the ways it does. Frontmatter status flips to 'archived'."""
    space = Path(args.space).resolve()
    item_path = Path(args.item_path)
    if not item_path.is_absolute():
        item_path = space / item_path
    if not item_path.exists():
        print(f"fail: review item not found: {item_path}", file=sys.stderr)
        return 1
    if not item_path.is_file():
        print(f"fail: review path is not a file: {item_path}", file=sys.stderr)
        return 1

    now = datetime.now()
    target_dir = space / LOGS_DIR / now.strftime("%Y") / now.strftime("%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / item_path.name
    if target.exists():
        print(f"fail: archive target exists: {target.relative_to(space)}", file=sys.stderr)
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
        space, "zanmai.py",
        f"archived review item {item_path.name} to {target.relative_to(space)}"
    )
    print(f"ok: review item archived to {target.relative_to(space)}")
    return 0





def cmd_clear_plan_section(args: argparse.Namespace) -> int:
    """Remove the `## Plan` section from a bundle's truth file.

    Used after a successful filing run: the plan-in-space has served its purpose
    (user approval, execution), the truth file no longer needs it. The body
    above and below stays verbatim.

    Section boundary is `## Plan` (start) to the next top-level heading
    (`\\n## `) or end-of-file. Frontmatter is untouched.
    """
    space = Path(args.space).resolve()
    bundle_dir, _bundle_kind, _leaf = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1

    target_name = args.truth_file or f"{_leaf}.md"
    truth = bundle_dir / target_name
    if not truth.exists():
        print(f"fail: truth file not found: {truth.relative_to(space)}", file=sys.stderr)
        return 1

    text = truth.read_text(encoding="utf-8")
    # Section pattern: '## Plan' at line start, up to the next '## ' at line start
    # or end of file. Multiline-aware; dotall so '.' matches newlines.
    pattern = re.compile(r"(?ms)^## Plan\s*\n.*?(?=^## |\Z)")
    new_text, n = pattern.subn("", text)
    if n == 0:
        print(f"ok: no plan section in {truth.relative_to(space)} (nothing to clear)")
        return 0

    # Tidy double-blank lines that result from the removal.
    new_text = re.sub(r"\n{3,}", "\n\n", new_text).rstrip() + "\n"
    truth.write_text(new_text, encoding="utf-8")

    _append_activity_log(
        space, "zanmai.py",
        f"cleared plan section from {truth.relative_to(space)}"
    )
    print(f"ok: plan section cleared from {truth.relative_to(space)}")
    return 0


def _collect_open_todos(space: Path, scope_dirs: list[str], days_back: int = 30,
                        eintraege: list[dict] | None = None) -> list[dict]:
    """The open tasks under given folders, recent ones only, for the briefing's open-items sections.

    A narrowing of `_task_scan`, not a second reader: one definition of what a task line is, in one
    place. Pass `eintraege` to reuse a scan the caller already has, which is what the briefing does.

    **A task that carries a date is judged by that date, never by the file it sits in.** The window
    used to be on the file alone, on the reasoning that it keeps the section about what is currently
    going on. It does the opposite in both directions, and both were seen in a real space. A
    reminder written today for an anniversary next year sits in a file touched today, so it was read
    out as an open item eleven months early, every session until then. And a deadline in a file
    nobody has opened for two months falls out of the window entirely, which is when it matters
    most. So: a date in the past or within the next few days is open, a date beyond that is not open
    yet, and a task with no date at all is judged by its file as before.
    """
    cutoff = datetime.now().timestamp() - days_back * 24 * 3600
    horizont = datetime.now().date() + timedelta(days=TASK_OPEN_HORIZON_DAYS)
    praefixe = tuple(f"{sub.rstrip('/')}/" for sub in scope_dirs)
    alle = _task_scan(space) if eintraege is None else eintraege

    def zaehlt(t: dict) -> bool:
        if not t["path"].startswith(praefixe):
            return False
        if t["due"] and _task_date_ok(t["due"]):
            return datetime.strptime(t["due"], "%Y-%m-%d").date() <= horizont
        return t["mtime"] >= cutoff

    return [t for t in alle if zaehlt(t)]


def _recent_log_files(space: Path, limit: int = 5) -> list[Path]:
    """Most recent N log files under zanmai/logs/<YYYY>/<MM>/, sorted by mtime desc.
    Excludes builder-gaps.md and hidden files."""
    logs_root = space / LOGS_DIR
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


def _recent_operations(space: Path, limit: int = 3) -> list[dict]:
    """Return up to `limit` most recent operation-report dicts with their
    operation name, summary, and anomalies content."""
    result: list[dict] = []
    for log in _recent_log_files(space, limit=10):
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
            "path": str(log.relative_to(space)),
            "slug": slug,
            "operation": operation,
            "summary": summary,
            "anomalies": anomalies,
        })
        if len(result) >= limit:
            break
    return result


def _last_session_end(space: Path) -> str:
    """The timestamp of the last clean session close, or an empty string."""
    marker = space / MEMORY_DIR / ".last-session-end"
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# The host's own record of the conversation
#
# Every session is written down in full by the host as it happens, turn by turn, outside the space.
# That record answers what the activity log cannot: what was said, what was asked, where a tool
# failed. Reading it costs nothing, because it is written whether anything reads it or not, and
# nothing has to be remembered during the work for it to be complete. The two are not the same
# thing and neither replaces the other: the activity log is the space's own chronicle, which is
# the user's, stays in their folder and outlives any program; this is the conversation, which
# belongs to the program that held it.
#
# So everything here is optional. No record found means every caller falls back to what it did
# before, and a space carried to another program keeps working, it only loses this convenience.
# ---------------------------------------------------------------------------

_RECORD_ROOT = "~/.claude/projects"
# A user turn the host inserted rather than the user typing it: hook output, reminders, the
# tool results themselves. None of that is what somebody said.
_RECORD_NOISE = ("<system-reminder>", "<projekt-briefing>", "Caveat:", "<command-name>",
                 "<local-command-stdout>")


def _record_dir(space: Path) -> Path | None:
    """The folder holding this space's conversation records, or None where the host keeps none."""
    wurzel = Path(_RECORD_ROOT).expanduser()
    if not wurzel.is_dir():
        return None
    # The host names the folder after the space's path with every separator turned into a dash.
    kandidat = wurzel / str(space.resolve()).replace("/", "-")
    return kandidat if kandidat.is_dir() else None


def _records(space: Path, *, seit: str = "") -> list[Path]:
    """This space's conversation records, oldest first, optionally only those touched after `seit`.

    `seit` is the `.last-session-end` marker, UTC and ISO 8601. Comparison is by the file's own
    modification time, which is when the session last wrote to it.
    """
    ordner = _record_dir(space)
    if ordner is None:
        return []
    grenze = 0.0
    if seit:
        try:
            grenze = datetime.strptime(seit, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc).timestamp()
        except ValueError:
            grenze = 0.0
    treffer = [p for p in ordner.glob("*.jsonl") if p.stat().st_mtime > grenze]
    return sorted(treffer, key=lambda p: p.stat().st_mtime)


def _record_essenz(pfad: Path, *, kappe: int = 600) -> dict:
    """What one conversation record carries, without the prose.

    What is kept: what the user typed, verbatim but capped; every question that was put to them,
    because those are the ones that get missed on a busy screen; every tool call that failed; every
    guard that fired. What is dropped: the assistant's prose, the tool output, the thinking. That is
    the bulk of the file and none of it is what somebody needs to pick the thread back up.
    """
    eingaben: list[str] = []
    fragen: list[str] = []
    fehler: list[str] = []
    waechter: list[str] = []
    werkzeuge = 0
    von = bis = ""
    for zeile in pfad.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            satz = json.loads(zeile)
        except ValueError:
            continue
        wann = (satz.get("timestamp") or "")[:16].replace("T", " ")
        if wann:
            von = von or wann
            bis = wann
        inhalt = (satz.get("message") or {}).get("content")
        if satz.get("type") == "user":
            if isinstance(inhalt, str) and inhalt.strip():
                if not any(m in inhalt for m in _RECORD_NOISE):
                    eingaben.append(f"{wann} {' '.join(inhalt.split())[:kappe]}")
            elif isinstance(inhalt, list):
                for block in inhalt:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and block.get("text", "").strip():
                        text = block["text"]
                        if not any(m in text for m in _RECORD_NOISE):
                            eingaben.append(f"{wann} {' '.join(text.split())[:kappe]}")
                    elif block.get("type") == "tool_result" and block.get("is_error"):
                        roh = block.get("content")
                        text = roh if isinstance(roh, str) else json.dumps(roh)[:kappe]
                        kurz = " ".join(str(text).split())[:kappe]
                        (waechter if "guard" in kurz else fehler).append(f"{wann} {kurz}")
        elif satz.get("type") == "assistant" and isinstance(inhalt, list):
            for block in inhalt:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    werkzeuge += 1
                elif block.get("type") == "text" and block.get("text", "").rstrip().endswith("?"):
                    letzter = block["text"].rstrip().split("\n")[-1]
                    fragen.append(f"{wann} {' '.join(letzter.split())[:kappe]}")
    return {"datei": pfad.name, "von": von, "bis": bis, "eingaben": eingaben, "fragen": fragen,
            "fehler": fehler, "waechter": waechter, "werkzeuge": werkzeuge}


def _essenz_als_markdown(essenzen: list[dict]) -> str:
    """The digest as one readable block. Empty sections are left out rather than shown empty."""
    zeilen: list[str] = []
    for e in essenzen:
        zeilen.append(f"## Session {e['datei'][:8]} ({e['von']} to {e['bis']})")
        zeilen.append("")
        zeilen.append(f"{len(e['eingaben'])} thing(s) the user said, {e['werkzeuge']} tool call(s), "
                      f"{len(e['fehler'])} failure(s), {len(e['waechter'])} guard(s) fired.")
        zeilen.append("")
        for titel, eintraege in (("What the user said", e["eingaben"]),
                                 ("Questions put to them", e["fragen"]),
                                 ("Where something failed", e["fehler"]),
                                 ("Guards that fired", e["waechter"])):
            if not eintraege:
                continue
            zeilen.append(f"### {titel}")
            zeilen.append("")
            zeilen.extend(f"- {x}" for x in eintraege)
            zeilen.append("")
    return "\n".join(zeilen)


def cmd_session_digest(args: argparse.Namespace) -> int:
    """The essence of one or more conversations, for a close that has to be written afterwards."""
    space = Path(args.space).resolve()
    seit = args.since if args.since is not None else _last_session_end(space)
    dateien = _records(space, seit=seit)
    if not dateien:
        wo = _record_dir(space)
        if wo is None:
            print("fail: this host keeps no conversation record, or it sits somewhere else. "
                  "The activity log is the fallback: `zanmai.py memory briefing`.", file=sys.stderr)
            return 1
        print(f"ok: nothing after {seit or 'the beginning'} in {wo}")
        return 0
    if args.limit:
        dateien = dateien[-args.limit:]
    print(_essenz_als_markdown([_record_essenz(p) for p in dateien]))
    return 0


def cmd_session_check(args: argparse.Namespace) -> int:
    """Was the last session closed properly? The check a machine runs after a hard power-off."""
    space = Path(args.space).resolve()
    seit = _last_session_end(space)
    offen = _records(space, seit=seit)
    if not offen:
        print(f"ok: nothing open. Last clean close {seit or '(never)'}.")
        return 0
    juengste = datetime.fromtimestamp(offen[-1].stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    print(f"unclosed: {len(offen)} session(s) after the last clean close "
          f"({seit or 'never'}), newest {juengste}. "
          f"`zanmai.py session digest` reads what happened in them.")
    return 0


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


def _activity_since(space: Path, since: str, limit: int = 25) -> list[dict]:
    """Activity-log entries written after `since`, newest last.

    The activity log is the only record of a session that is written while the work happens
    rather than at the end, so it is the one that survives a session nobody closed. Found
    2026-08-26 on a live space: `briefing.md` stood at 15:13 while the log carried entries up
    to 16:24 and the whole afternoon, an escalation included, was invisible at the next start.
    """
    log = space / MEMORY_DIR / "activity-log.md"
    if not log.is_file():
        return []
    # The marker is UTC, the activity log is local time. Comparing them as text put the line two
    # hours in the wrong place, which on a live space means either replaying entries that were
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


def _close_session_next_items(space: Path, limit: int = 3) -> list[dict]:
    """Pull 'Next' items from the last N close-session logs. Returns list of
    {date, items}. Items is the raw text of the Next section so the briefing
    can render it verbatim."""
    result: list[dict] = []
    for log in _recent_log_files(space, limit=15):
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
            "path": str(log.relative_to(space)),
            "date": fm.get("created", log.stem),
            "items": next_block,
        })
        if len(result) >= limit:
            break
    return result


def _active_focus_bundles(space: Path) -> list[dict]:
    """List active focus bundles with their goal + status from the truth file."""
    focus_dir = space / LIFE_DIR
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


def _recent_activity_bundles(space: Path, hours_back: int = 48) -> list[dict]:
    """Bundles under the knowledge, life and workbench areas with file mtimes in the last
    `hours_back` hours. Source-agnostic recency signal: catches reed-research,
    hank-imports, manual edits alike. The Open-Todos channel only surfaces
    journal entries. This surfaces "user was busy with X yesterday" for
    any bundle. Returns descending by last_activity_unix."""
    import time as _time
    cutoff = _time.time() - (hours_back * 3600)
    result: list[dict] = []
    for kind_folder in BUNDLE_FOLDERS:
        bundle_kind = _folder_kind(kind_folder)
        kind_path = space / kind_folder
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


def _attachment_basenames(space: Path) -> set[str]:
    """All non-Markdown filenames in the space (lowercased), used to resolve
    embed-shaped wikilinks like `[[some-frame.jpg]]` against the filesystem.
    Skips the same distribution and system parts as the markdown walker. Also
    skips the work objects and the user's own database folders (`<Name>.base/`):
    what is in those is internal to whatever owns them, not the space's own
    files that markdown bodies embed."""
    out: set[str] = set()
    for p in space.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".md":
            continue
        try:
            rel = p.relative_to(space).as_posix()
        except ValueError:
            continue
        if rel.startswith(f"{SYSTEM_MATERIAL_DIR}/") or rel.startswith(f"{HISTORY_DIR}/") or rel.startswith(".claude/"):
            continue
        if rel.startswith(f"{OPEN_DIR}/"):
            continue
        if _is_inside_database_folder(rel):
            continue
        out.add(p.name.lower())
    return out


def _broken_wikilinks(space: Path) -> list[dict]:
    """Wikilinks in the active user space that point to slugs or filenames no
    file in the space carries. Reads from space-index.json (`wikilinks_out`
    per file). Two target classes: bare slugs (resolve against markdown
    slug-set), and file-extension targets like `[[frame.jpg]]` (resolve
    against the filesystem-walk of non-markdown files).

    Source paths under the hard-exclude list (`_WIKILINK_OPS_EXCLUDED_PREFIXES`
    plus `_WIKILINK_OPS_EXCLUDED_FILES`) are skipped: log files and
    operation reports contain pre-rename slug names as historical record
    by design, trashed and archived files keep their state at archive time,
    snapshots are immutable. None of these are "broken" in the user-space
    sense, they are expected historical residue."""
    index_path = space / MEMORY_DIR / "space-index.json"
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
    attachments = _attachment_basenames(space)
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


def _journal_note(space: Path, date: datetime) -> Path:
    """The entry for one day: `journal/<year>/<date>.md`. One layer, one file, no bundle."""
    tag = date.strftime("%Y-%m-%d")
    return space / JOURNAL_DIR / tag[:4] / f"{tag}.md"


def _journal_roots() -> list[str]:
    """The journal root, space-relative. Used to scan for open items."""
    return [JOURNAL_DIR]




def _journal_target_date(args: argparse.Namespace) -> datetime | None:
    """The date the command works on. None means the argument was unusable and the caller reports."""
    if not args.date:
        return datetime.now()
    try:
        return datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("fail: invalid --date, expected YYYY-MM-DD", file=sys.stderr)
        return None


def _journal_append(space: Path, path: Path, text: str, was: str) -> str:
    """Append to a journal entry, creating it if needed. Never overwrites, never edits.

    This is the only way a day comes into being: nothing creates an empty entry for a day on which
    nothing was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    bestand = path.read_text(encoding="utf-8") if path.exists() else ""
    if bestand and not bestand.endswith("\n"):
        bestand += "\n"
    if bestand.strip():
        bestand += "\n"
    path.write_text(bestand + text.rstrip("\n") + "\n", encoding="utf-8")
    rel = path.relative_to(space).as_posix()
    _append_activity_log(space, "zanmai.py", f"{was} -> {rel}")
    return rel


def cmd_journal_path(args: argparse.Namespace) -> int:
    """Print the path of a journal entry. Creates nothing."""
    space = Path(args.space).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    print(_journal_note(space, date).relative_to(space).as_posix())
    return 0


def cmd_journal_append(args: argparse.Namespace) -> int:
    """Append the user's words to a journal entry, verbatim, below whatever is already there."""
    space = Path(args.space).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    rel = _journal_append(space, _journal_note(space, date), args.text,
                          "journal append")
    print(f"ok: appended to {rel}")
    return 0


def cmd_journal_read(args: argparse.Namespace) -> int:
    """Print a journal entry, or say plainly that the period holds nothing yet."""
    space = Path(args.space).resolve()
    date = _journal_target_date(args)
    if date is None:
        return 1
    path = _journal_note(space, date)
    rel = path.relative_to(space).as_posix()
    if not path.is_file():
        print(f"empty: {rel} does not exist, nothing was written for that day")
        return 0
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def cmd_journal_list(args: argparse.Namespace) -> int:
    """List the entries of one kind that exist, newest last. The bundle contents come with it."""
    space = Path(args.space).resolve()
    root = space / JOURNAL_DIR
    if not root.is_dir():
        print("empty: no journal entries yet")
        return 0
    notes = sorted(p for p in root.rglob("*.md") if p.is_file())
    if not notes:
        print("empty: no journal entries yet")
        return 0
    for note in notes[-args.limit:] if args.limit else notes:
        rel = note.relative_to(space).as_posix()
        beilagen = [f for f in note.parent.iterdir() if f.is_file() and f != note]
        zusatz = f"  (+{len(beilagen)} file(s) in the bundle)" if beilagen else ""
        print(f"{rel}{zusatz}")
    return 0


# What one line may cost. The host replaces hook output over its limit with a preview and says
# nothing about it, so the list has to fit whatever the space holds. A task line in a live space ran
# to 452 characters, and twenty of those would have been the whole budget. The cut is also the right
# shape for a greet: a line nobody can read at a glance is not a line.
_GREET_LINE_MAX = 200


# The order the chosen lines are laid out in. Selection is by urgency, layout by group: sorting the
# selection by group instead put a four-day-old entry in slot one ahead of seven items due that day.
_GREET_GROUPS = ("waiting", "overdue", "today", "tomorrow", "this week", "open")

_GREET_HEADINGS = {
    "waiting": "Waiting on you",
    "overdue": "Overdue",
    "today": "Today",
    "tomorrow": "Tomorrow",
    "this week": "Coming up",
    "open": "Open tasks",
}

_GREET_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")


# Caps and windows for the greet list. Ten lines per block is a ceiling, never a target: the filters
# decide what is relevant and the list is as long as they leave it. Zero lines in a block is a
# correct answer and the block is then left out.
_GREET_CAP_DATED = 10         # block one: what has a day, from any source
_GREET_CAP_TASKS = 10         # block two: task lines the user wrote, no day on them
# From how many loose ends in one bundle they arrive as one line instead of one each.
_GREET_BUENDEL_AB = 3
_GREET_WEEK_DAYS = 7          # what still counts as coming up rather than later
_GREET_RECENT_OVERDUE = 14    # older than this, an overdue item is backlog: counted, not listed


def _greet_shorten(text: str) -> str:
    """One greet line, cut at a word boundary where it runs long. The full text stays in the file."""
    if len(text) <= _GREET_LINE_MAX:
        return text
    schnitt = text[:_GREET_LINE_MAX].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return f"{schnitt} …"


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
    work object, a dated file. A real space had four items sitting in two of those at once, worded
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


def _buendel_titel(space: Path, buendel: str) -> str:
    """What a bundle is called, read from its own truth file, falling back to its slug.

    The slug is ASCII by rule, so deriving the label from it prints a place name with the accents
    stripped out. The file says what it is called; a heading it wrote itself is closer to how the
    user says it than anything reconstructed from a pathname.
    """
    slug = buendel.split("/")[-1]
    wahrheit = space / buendel / f"{slug}.md"
    try:
        for zeile in wahrheit.read_text(encoding="utf-8").splitlines():
            if zeile.startswith("# "):
                return zeile[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return _human_label_for_slug(slug)


def _work_deliverable_exists(space: Path, row: dict) -> bool:
    """Is the thing this piece of work was for already lying in the space?

    Only where the row names where the result goes, and only where that is a real path in the
    space. A row with no deliverable says nothing about whether it is finished, and guessing from
    the title would close work by keyword.
    """
    ziel = (row.get("deliverable") or "").strip()
    if not ziel:
        return False
    pfad = _resolve_space_file(space, ziel)
    if pfad is not None:
        return True
    kandidat = (space / ziel).resolve()
    try:
        kandidat.relative_to(space.resolve())
    except ValueError:
        return False
    return kandidat.exists()


def _greet_items(space: Path, now: datetime | None = None) -> dict:
    """What the greet names: chosen, grouped, sorted and capped, ready to be worded.

    Returns `{"items": [...], "overflow": {...} | None, "totals": {...}}`. Every item carries its
    group, its display text and where it came from. The caller renders them in the order given and
    adds nothing: the selection is the decision, and it was made here.
    """
    jetzt = now or datetime.now()
    heute = jetzt.date()
    aufgaben = _task_scan(space)

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

    for eintrag in _task_due_soon(space, _GREET_WEEK_DAYS, eintraege=aufgaben):
        tage = eintrag["days"]
        if tage < -_GREET_RECENT_OVERDUE:
            rueckstand += 1
            continue
        aufnehmen(_greet_group(tage), eintrag["text"], eintrag["path"], abs(tage),
                  faellig=eintrag["due"])

    # Waiting on the user, with no date on it. This comes first and on its own pass, because
    # `_work_due_soon` filters by date before anything else sees the row, so an undated one never
    # arrived at all. Found in practice, on the first greet after the greet itself was
    # fixed: the most active piece of work in the space, three days old and explicitly waiting on the
    # user, was missing from the list, and the three work objects in that state all had no due date.
    # A due date is a plan; `waiting on you` is a recorded fact about who holds the thing. Dropping
    # the fact because the plan is absent is backwards, and the comment below already said so while
    # the line above threw the row away.
    try:
        alle_rows, _h = _work_read(space)
    except Exception:
        alle_rows = []
    fertig_aussehend = 0
    for row in alle_rows:
        if (row.get("state") or "").strip() != "waiting on you":
            continue
        # The result is already lying there. A live space read out "create design.md for the brand"
        # as waiting on the user while that file had been written two hours earlier; the work had
        # been done and only the row was never closed. A list that shows something finished twice
        # stops being read, so the file on disk wins over the row. Counted rather than silently
        # dropped, because the row does still need closing and somebody has to hear that.
        if _work_deliverable_exists(space, row):
            fertig_aussehend += 1
            continue
        if _task_date_ok((row.get("due") or "").strip()):
            continue  # dated ones come through the pass below, with their real distance
        aufnehmen("waiting", row.get("work", ""), "work object", _GREET_WEEK_DAYS, rang=0)

    for row in _work_due_soon(space, _GREET_WEEK_DAYS):
        faellig = (row.get("due") or "").strip()
        if not _task_date_ok(faellig):
            continue
        tage = (datetime.strptime(faellig, "%Y-%m-%d").date() - heute).days
        if tage < -_GREET_RECENT_OVERDUE:
            rueckstand += 1
            continue
        # `waiting on you` is the one urgency signal in the space that is a recorded fact rather
        # than a judgement: something is on the user and the machine cannot move it. It goes first,
        # ahead of distance. Without it a hard deadline four days out sits behind every routine
        # item due today and drops out of the six.
        wartet = (row.get("state") or "").strip() == "waiting on you"
        # The row's `id` stays here. It is the handle for `zanmai.py work` and tells the user
        # nothing; one reached a greet because the rule against it lived in prose.
        aufnehmen("waiting" if wartet else _greet_group(tage), row.get("work", ""),
                  "work object", abs(tage), rang=0 if wartet else 1, faellig=faellig)

    for eintrag in _dated_files_ahead(space, _GREET_WEEK_DAYS):
        aufnehmen(_greet_group(eintrag["days"]), eintrag["label"], eintrag["path"],
                  abs(eintrag["days"]), faellig=eintrag["date"])

    # Block two: every open task line the user wrote that carries no date, from anywhere in their
    # folders. Both limits that used to sit here are gone, and each one was losing real work. The
    # scope was `journal/` plus `life/` only, so seventeen of twenty open lines in a live space sat
    # in `knowledge/` and could never arrive. The seven-day window on the file then cut most of the
    # rest, on the theory that an old file means a stale task; what it actually means is that nobody
    # has touched the file since writing the task down, which is the definition of still open.
    #
    # Nothing replaces them, because nothing has to: a task line is either ticked or it is not, and
    # `status:` on the file settles the case where the whole matter fell away. Newest file first, so
    # what was written down last is read first.
    #
    # Every open line goes through here, dated ones included, and the dedup above drops the ones
    # block one already took. Filtering to undated lines instead left a hole exactly one window
    # wide: a flight that expires in eighteen days is too far out for block one's seven days and
    # was no longer undated, so it appeared in neither. A task the space holds is in one of the two
    # blocks or in one of the two overflow counts, never in none.
    # Points from one bundle arrive as one line, not as six. A trip whose booking may already be
    # off filled eight of seventeen lines with its own loose ends, and the reader had to notice
    # that for themselves; worse, the one thing worth seeing, that two trips sat in the same month,
    # was buried under the very entries that made the month look busy. Which bundle a task belongs
    # to is its path, so this is arithmetic rather than judgement.
    def ist_rueckstand(a: dict) -> bool:
        if not (a["due"] and _task_date_ok(a["due"])):
            return False
        return (datetime.strptime(a["due"], "%Y-%m-%d").date() - heute).days < -_GREET_RECENT_OVERDUE

    # Dated further out than block one reaches. Block two is defined as the task lines with no day
    # on them, and it was not keeping to that: every open task went in, whatever its date, so a
    # reminder written for an anniversary next August was read out as an open task in September, and
    # again in every session until then. A date in the future is a plan, not something waiting to be
    # done today, so it is left out of the list entirely, not even counted: the name of this thing
    # means absorption in one matter, and a line about what is due in eleven months is exactly the
    # pull away from it. The item is in the space, it is findable, and it walks into the week block
    # on its own as its date approaches.
    def ist_spaeter(a: dict) -> bool:
        if not (a["due"] and _task_date_ok(a["due"])):
            return False
        return (datetime.strptime(a["due"], "%Y-%m-%d").date() - heute).days > _GREET_WEEK_DAYS


    # Bundles only, and a bundle is a folder under one of the kind roots. A journal day is a date,
    # not a topic: rolling five entries from one morning into one line named by that date says a
    # day back at the user, which tells them nothing they did not know.
    nach_buendel: dict[str, list[dict]] = {}
    for a in aufgaben:
        if ist_rueckstand(a) or ist_spaeter(a):
            continue   # counted in an overflow; naming it here would count it twice
        teile = a["path"].split("/")
        if len(teile) < 3 or teile[0] not in BUNDLE_FOLDERS:
            continue
        nach_buendel.setdefault("/".join(teile[:-1]), []).append(a)

    gebuendelt = {s: eintraege for s, eintraege in nach_buendel.items()
                  if len(eintraege) >= _GREET_BUENDEL_AB}
    for schluessel, eintraege in sorted(gebuendelt.items(),
                                        key=lambda kv: max(a["mtime"] for a in kv[1]), reverse=True):
        label = _buendel_titel(space, schluessel)
        offen = len(eintraege)
        aufnehmen("open", f"{label}: {offen} open points", schluessel, _GREET_WEEK_DAYS + 1)

    for a in sorted(aufgaben, key=lambda a: a["mtime"], reverse=True):
        teile = a["path"].split("/")
        if "/".join(teile[:-1]) in gebuendelt:
            continue   # already named by the bundle line above
        # Except what the backlog count above already stands for. Listing those here as well would
        # show them and count them in the same breath, and the count would be a lie by exactly the
        # number of lines standing above it.
        if ist_rueckstand(a) or ist_spaeter(a):
            continue
        aufnehmen("open", a["text"], a["path"], _GREET_WEEK_DAYS + 1, faellig=a["due"])

    # Selection by urgency: what waits on the user first, then distance from today, and an overdue
    # item ahead of a coming one at equal distance because that one is already missed.
    kandidaten.sort(key=lambda e: (e["rank"], e["near"], 0 if e["group"] == "overdue" else 1))

    datiert = [e for e in kandidaten if e["group"] != "open"]
    reine_aufgaben = [e for e in kandidaten if e["group"] == "open"]

    def kappen(eintraege: list[dict], cap: int, extra_verdeckt: int = 0) -> tuple[list[dict], list[dict]]:
        """The visible part of one block and what it hides. The overflow line costs a slot."""
        braucht = (len(eintraege) + extra_verdeckt) > cap
        grenze = cap - 1 if braucht else cap
        return eintraege[:grenze], eintraege[grenze:]

    sichtbar, verdeckt = kappen(datiert, _GREET_CAP_DATED, rueckstand)
    sichtbar_aufgaben, verdeckt_aufgaben = kappen(reine_aufgaben, _GREET_CAP_TASKS)

    # Layout by group, once the slots are settled. Same items, read in an order that says something.
    ordnung = {name: i for i, name in enumerate(_GREET_GROUPS)}
    sichtbar.sort(key=lambda e: (ordnung[e["group"]], e["near"]))

    ueberlauf = None
    if verdeckt or rueckstand:
        heute_verdeckt = sum(1 for e in verdeckt if e["group"] == "today")
        teile: list[str] = []
        if verdeckt:
            zusatz = f" ({heute_verdeckt} of them today)" if heute_verdeckt else ""
            teile.append(f"{len(verdeckt)} more within the next {_GREET_WEEK_DAYS} days{zusatz}")
        if rueckstand:
            teile.append(f"{rueckstand} older overdue")
        ueberlauf = {"group": "more", "text": ", ".join(teile),
                     "hidden_near": len(verdeckt), "hidden_today": heute_verdeckt,
                     "hidden_backlog": rueckstand}

    ueberlauf_aufgaben = None
    if verdeckt_aufgaben:
        # Counted apart from the dated block, because folding an undated item into "within the next
        # 7 days" states a deadline nobody wrote.
        #
        # Work dated further out than the week is not counted here either, and that is the point of
        # the whole list: it exists to put one thing in front of the user, not to account for
        # everything the space holds. A line saying four things are due in the coming months is an
        # invitation to think about the coming months, which is the opposite of what an opening
        # list is for. Those items are in the space, they are findable, and they arrive here by
        # themselves as their date comes into the week.
        ueberlauf_aufgaben = {"group": "more", "text": f"{len(verdeckt_aufgaben)} more open task(s)",
                              "hidden_undated": len(verdeckt_aufgaben)}

    return {
        "items": sichtbar,
        "overflow": ueberlauf,
        "tasks": sichtbar_aufgaben,
        "tasks_overflow": ueberlauf_aufgaben,
        "totals": {
            "open_tasks": len(aufgaben),
            "candidates": len(kandidaten),
            "backlog": rueckstand,
            "finished_looking": fertig_aussehend,
        },
    }


def _greet_block(space: Path, now: datetime | None = None) -> list[str]:
    """The greet list as hook output: two blocks, numbered straight through, nothing left to arrange.

    Rendered as data rather than as a suggestion. The numbers are printed, so they cannot skip and
    they cannot restart at the second block; an overflow arrives as its own numbered line, so it
    cannot become a sub-bullet; an empty space prints no list at all rather than a padded one.
    """
    walk = _greet_items(space, now=now)
    items = walk["items"]
    ueberlauf = walk["overflow"]
    aufgaben = walk["tasks"]
    ueberlauf_aufgaben = walk["tasks_overflow"]
    if not (items or ueberlauf or aufgaben or ueberlauf_aufgaben):
        return ["- Nothing open and nothing dated. Greet in one sentence and ask what they want to "
                "do; do not invent a list."]

    lines = [
        "The greet list, already selected, sorted and capped. Render exactly these lines, in this "
        "order, one numbered line each, with the numbers as printed. Translate the group headings "
        "and the wording into the user's writing language, keep the item's own words, and add "
        "nothing: no extra item, no sub-bullet, no path, no id. Each block holds at most ten lines "
        "and is as short as the space leaves it; a block with no lines is absent and is not "
        "mentioned. `greeting.md` covers the tone, the address and the closing sentence.",
        "",
    ]
    heute = (now or datetime.now()).date()
    nummer = 0
    letzte_gruppe = None
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
        lines.append(f"{nummer}. {_greet_shorten(eintrag['text'])}")
    if ueberlauf:
        nummer += 1
        lines.append("GROUP The rest")
        lines.append(f"{nummer}. + {ueberlauf['text']}. Offer: say \"show the open points\".")

    # The second block, and the numbering carries on rather than restarting: two lists that both
    # begin at 1 read as one list that lost its place.
    if aufgaben or ueberlauf_aufgaben:
        lines.append(f"GROUP {_GREET_HEADINGS['open']}")
        for eintrag in aufgaben:
            nummer += 1
            lines.append(f"{nummer}. {_greet_shorten(eintrag['text'])}")
        if ueberlauf_aufgaben:
            nummer += 1
            lines.append(f"{nummer}. + {ueberlauf_aufgaben['text']}. Offer: say \"show the open tasks\".")

    # Work whose result is already lying in the space, left out of the list above and said here
    # instead. Not a line for the user: it is the machine's own bookkeeping that is behind, and
    # what it needs is `work close`, not the user's attention.
    fertig = walk["totals"].get("finished_looking") or 0
    if fertig:
        lines.append(f"NOTE {fertig} piece(s) of work still marked as waiting have their result in "
                     f"the space already. Left out of the list. Close them with `zanmai.py work "
                     f"close`; do not put them to the user as open.")
    return lines


def _render_briefing(space: Path) -> str:
    """Build the briefing.md content from current space state. Synthesises across
    journal entries, Focus-Bundles, Operation-Reports and Close-Session-Logs -
    not just one source. Steve reads this at session start; the SessionStart
    hook inlines it into context."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")

    focus_bundles = _active_focus_bundles(space)
    recent_ops = _recent_operations(space, limit=3)
    recent_activity = _recent_activity_bundles(space, hours_back=48)
    close_next = _close_session_next_items(space, limit=1)
    # One walk over the space feeds all three task sections below, which is also what keeps them
    # from disagreeing with each other.
    offene_aufgaben = _task_scan(space)
    journal_todos = _collect_open_todos(
        space, _journal_roots(), days_back=30, eintraege=offene_aufgaben
    )
    focus_todos = _collect_open_todos(space, [LIFE_DIR], days_back=90,
                                      eintraege=offene_aufgaben)
    broken = _broken_wikilinks(space)

    lines: list[str] = []
    lines.append(f"# Zanmai briefing")
    lines.append("")
    lines.append(f"_Updated {timestamp}. Read by Steve at session start. "
                 f"Not user-editable - rebuilt automatically on close-session, "
                 f"on every operation report, and on demand via "
                 f"`zanmai.py memory briefing`._")
    lines.append("")

    # 0) What has a date on it, from anywhere in the space and from the machine's own list.
    #
    # First, and folder-independent, because that was the defect: a deadline used to be visible only
    # while its bundle sat in `life/` and went dark the moment the bundle was archived, with the
    # money still in play. Only dated items appear. A list of everything open is read once and
    # skipped from then on, and then the one line that mattered is lost in it.
    faellig = _task_due_soon(space, _BRIEFING_DUE_DAYS, eintraege=offene_aufgaben)
    work_faellig = _work_due_soon(space, _BRIEFING_DUE_DAYS)
    datiert = _dated_files_ahead(space, _BRIEFING_DUE_DAYS)
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
    # when no close-session log exists, which on a live space is the normal case rather than the
    # exception: the close is a skill someone has to invoke, and nobody invokes it when they simply
    # shut the window. The activity log is written during the work, so it is there either way.
    seit = _last_session_end(space)
    nachgetragen = _activity_since(space, seit)
    if nachgetragen:
        lines.append("## Since the last clean close")
        lines.append("")
        # Two things this heading has to settle, both found on a live space the morning after it
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
            lines.append("_No session has ever been closed cleanly in this space. "
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
    if journal_todos:
        lines.append(f"**From the journal (last 30 days, {len(journal_todos)}):**")
        for t in journal_todos[:20]:
            lines.append(f"- [ ] {t['text']} _({t['path']})_")
        if len(journal_todos) > 20:
            lines.append(f"- _... plus {len(journal_todos) - 20} more_")
        lines.append("")
    if focus_todos:
        lines.append(f"**From focus bundles (last 90 days, {len(focus_todos)}):**")
        for t in focus_todos[:20]:
            lines.append(f"- [ ] {t['text']} _({t['path']})_")
        if len(focus_todos) > 20:
            lines.append(f"- _... plus {len(focus_todos) - 20} more_")
        lines.append("")
    if not (journal_todos or focus_todos or close_next):
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
    lines.append("_(Extended gap detection (person mentions without a contact, bundle drift, "
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


_DOCS_TRIGGER = "**Read this when:**"
_DOCS_INDEX_START = "<!-- generated: read-this-when -->"
_DOCS_INDEX_END = "<!-- /generated -->"


def _docs_triggers(system_dir: Path) -> list[tuple[str, str, str]]:
    """(file, title, situation) for every documentation page that carries a trigger line.

    The situation, not the topic. A page called "How the space is organised" tells nobody when to
    open it; "something has to be filed and it is not obvious where" does. Read off the page itself
    rather than kept in a second list, so the two cannot drift apart.
    """
    raus: list[tuple[str, str, str]] = []
    ordner = system_dir / "docs"
    if not ordner.is_dir():
        return raus
    for pfad in sorted(ordner.glob("*.md")):
        if pfad.name in ("index.md", "_TEMPLATE.md"):
            continue
        titel, lage = "", ""
        for zeile in pfad.read_text(encoding="utf-8").splitlines()[:12]:
            if zeile.startswith("# ") and not titel:
                titel = zeile[2:].strip()
            if zeile.startswith(_DOCS_TRIGGER):
                lage = zeile[len(_DOCS_TRIGGER):].strip().rstrip(".")
        if titel and lage:
            raus.append((pfad.name, titel, lage))
    return raus


def _docs_index_block(system_dir: Path) -> str:
    """The directory itself: one line per page, the situation first.

    A reference system needs a directory, and the directory has to sit where it is read before the
    decision rather than behind it. Without one, a page is found when somebody happens to remember
    it, and a page nobody remembers is a page that was never written: the failure is invisible,
    because noticing it would take exactly the knowledge that is missing. Generated, never typed. A
    hand-kept copy of thirty trigger lines is thirty chances to drift.
    """
    zeilen = [_DOCS_INDEX_START, "", "| Read this when | Page |", "|---|---|"]
    for datei, titel, lage in _docs_triggers(system_dir):
        zeilen.append(f"| {lage} | [{titel}]({datei}) |")
    zeilen += ["", _DOCS_INDEX_END]
    return "\n".join(zeilen)


def cmd_docs_index(args: argparse.Namespace) -> int:
    """Rebuild the situation directory inside `docs/index.md` from the pages themselves."""
    wurzel = Path(args.space).resolve()
    system_dir = wurzel / SYSTEM_MATERIAL_DIR if (wurzel / SYSTEM_MATERIAL_DIR).is_dir() else wurzel
    index = system_dir / "docs" / "index.md"
    if not index.is_file():
        print(f"fail: no docs/index.md under {system_dir}", file=sys.stderr)
        return 1
    text = index.read_text(encoding="utf-8")
    block = _docs_index_block(system_dir)
    if _DOCS_INDEX_START in text and _DOCS_INDEX_END in text:
        neu = text.split(_DOCS_INDEX_START)[0] + block + text.split(_DOCS_INDEX_END, 1)[1]
    else:
        neu = text.rstrip() + "\n\n## When to read what\n\n" + block + "\n"
    if neu == text:
        print("ok: the directory is already in step with the pages")
        return 0
    index.write_text(neu, encoding="utf-8")
    print(f"ok: directory rebuilt from {len(_docs_triggers(system_dir))} page(s)")
    return 0


def cmd_welcome(args: argparse.Namespace) -> int:
    """The same list the session opens with, rebuilt from the space as it stands now.

    It exists because the greet scrolls away. An hour into a session the list is somewhere above
    a dozen tool calls, and the way back to it was to start a new session, which is an absurd price
    for reading nine lines. Same builder as the greet, so the two can never drift into two different
    answers to the same question, and rebuilt on every call rather than remembered: half the point
    is that what was dealt with in the meantime is gone from it.
    """
    space = Path(args.space).resolve()
    for zeile in _greet_block(space):
        print(zeile)
    return 0


def cmd_briefing(args: argparse.Namespace) -> int:
    """Atomic rebuild of `zanmai/memory/briefing.md`. Triggered by `/close-session`,
    after `memory report`, or manually. The authority for Steve's session-start
    context."""
    space = Path(args.space).resolve()
    target = space / MEMORY_DIR / "briefing.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = _render_briefing(space)
    target.write_text(content, encoding="utf-8")
    _append_activity_log(space, "zanmai.py", "briefing.md rebuilt from space state")
    fehlt = _briefing_sections_missing(content)
    if not getattr(args, "quiet", False):
        print(f"ok: briefing rebuilt -> {target.relative_to(space)}")
    if fehlt:
        # Whoever generates a text that behaviour is built on checks that text. A briefing that
        # swallowed a section looks exactly like a full one from the outside, and the greet then
        # reads from a source that silently lost the part it existed for.
        print("warning: briefing is missing section(s): " + ", ".join(fehlt), file=sys.stderr)
        return 1
    return 0


def cmd_hook_session_end(args: argparse.Namespace) -> int:
    """SessionEnd hook: rebuild the briefing, and mark the close only if one really happened.

    Until the handover between sessions ran entirely through the `close-session` skill,
    which someone has to invoke. On a live space after four weeks, no session log had ever been
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
    space = _find_space_root(Path(start))
    if space is None:
        return 0
    ziel = space / MEMORY_DIR / "briefing.md"
    if not ziel.parent.is_dir():
        return 0
    try:
        ziel.write_text(_render_briefing(space), encoding="utf-8")
    except OSError as exc:
        print(f"session-end: briefing not rebuilt ({exc})", file=sys.stderr)
        return 0
    if _close_log_today(space):
        # Same format the close-session skill writes: UTC, ISO 8601, seconds.
        (space / MEMORY_DIR / ".last-session-end").write_text(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
    return 0


def _close_log_today(space: Path) -> bool:
    """Whether a close-session log was written today. The condition for calling a session closed."""
    heute = datetime.now().strftime("%Y-%m-%d")
    for log in _recent_log_files(space, limit=10):
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
    space = Path(args.space).resolve()
    now = datetime.now()
    date_part = now.strftime("%Y-%m-%d-%H%M")
    op = _slugify(args.operation)
    slug = _slugify(args.slug)
    report_slug = f"{date_part}-{op}-{slug}"
    report_dir = space / LOGS_DIR / now.strftime("%Y") / now.strftime("%m")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{report_slug}.md"

    activity = _read_recent_activity(space, since_minutes=args.since_minutes)
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
    _append_activity_log(space, "zanmai.py", f"wrote operation report {report_path.relative_to(space)}")
    print(f"ok: report at {report_path.relative_to(space)}")

    # Operation reports are substantial state-changes - the briefing must reflect them.
    briefing_target = space / MEMORY_DIR / "briefing.md"
    try:
        briefing_target.parent.mkdir(parents=True, exist_ok=True)
        briefing_target.write_text(_render_briefing(space), encoding="utf-8")
        _append_activity_log(space, "zanmai.py", "briefing.md auto-rebuilt after memory report")
    except OSError:
        pass

    return 0


def _read_recent_activity(space: Path, *, since_minutes: int) -> list[str]:
    log = space / MEMORY_DIR / "activity-log.md"
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
    """Set the one-line description of a member in its bundle's INDEX.md, adding the line if it is new.

    It used to rewrite an existing line and refuse with "no entry" when there was none, which is
    exactly the case a new sub-bundle presents: the folder is there, the index is there, and the
    line that should point at it has never been written. Two runs on two different days hit that and
    both went round it the same way, with `bundle set-body` over the whole INDEX file. That is a
    hand-edit of a generated file, and it skips the frontmatter guard, the index hook and the
    activity log at once. Adding the line is the same act as correcting it, so it is the same
    command.
    """
    space = Path(args.space).resolve()
    bundle_dir, _kind, _leaf = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1
    index_path = bundle_dir / "INDEX.md"
    if not index_path.is_file():
        print(f"fail: {bundle_dir.relative_to(space).as_posix()}/INDEX.md does not exist.",
              file=sys.stderr)
        return 1
    slug = _slugify(args.file[:-3] if args.file.lower().endswith(".md") else args.file)
    summary = args.summary.strip()
    if _index_line_set(index_path, slug, summary):
        was = "rewrote"
    else:
        # A line is added only for something that is actually in the bundle: a member file or a
        # sub-bundle folder. Otherwise a typo in `--file` writes a wikilink pointing at nothing,
        # which is the same broken index this command exists to prevent, arrived at from the other
        # side.
        if not (bundle_dir / f"{slug}.md").is_file() and not (bundle_dir / slug).is_dir():
            print(f"fail: no entry for [[{slug}]] in "
                  f"{bundle_dir.relative_to(space).as_posix()}/INDEX.md, and there is no "
                  f"{slug}.md or {slug}/ in the bundle to write one for.", file=sys.stderr)
            return 1
        _append_index(index_path, slug, summary)
        if f"[[{slug}]]" not in index_path.read_text(encoding="utf-8"):
            print(f"fail: could not place a line for [[{slug}]] in "
                  f"{bundle_dir.relative_to(space).as_posix()}/INDEX.md. The file has no heading to "
                  f"put it under.", file=sys.stderr)
            return 1
        was = "added"
    _append_activity_log(space, "zanmai.py",
                         f"{was} the index entry for {slug} in "
                         f"{bundle_dir.relative_to(space).as_posix()}/")
    print(f"ok: index entry for {slug} {'now reads' if was == 'rewrote' else 'added'}: {summary}")
    return 0


def cmd_bundle_remove_file(args: argparse.Namespace) -> int:
    """Discard a member: to the trash, out of the index, into the activity log, in one call.

    `file trash` moved the file and logged it but left the index line pointing at nothing, so every
    discard ended in a hand-edit of INDEX.md. Two halves of one act belong in one command.
    """
    space = Path(args.space).resolve()
    bundle_dir, _kind, _leaf = _resolve_bundle_dir(space, args.bundle_slug, args.bundle_kind)
    if not bundle_dir:
        print(f"fail: bundle '{args.bundle_slug}' not found", file=sys.stderr)
        return 1
    slug = _slugify(args.file[:-3] if args.file.lower().endswith(".md") else args.file)
    target = bundle_dir / f"{slug}.md"
    if not target.is_file():
        print(f"fail: no such member: {target.relative_to(space)}", file=sys.stderr)
        return 1

    rc = cmd_trash_file(argparse.Namespace(space=str(space), path=str(target)))
    if rc != 0:
        # The file is still where it was, so the index still tells the truth. Leave it alone.
        return rc
    entfernt = _index_line_remove(bundle_dir / "INDEX.md", slug)
    _append_activity_log(space, "zanmai.py",
                         f"discarded {slug} from {bundle_dir.relative_to(space).as_posix()}/ "
                         f"(to {TRASH_DIR}/, index entry {'removed' if entfernt else 'was not present'})")
    print(f"ok: {slug} moved to {TRASH_DIR}/ and taken out of the bundle index")
    return 0


# Nothing is thrown away out of the inbox before it has arrived somewhere in the space. Reading
# a file and saying what it was in the conversation is not arriving: the conversation is gone
# tomorrow, the file is in the trash, and the trash is swept. So a trashing out of `inbox/` has to
# name one of two things, and refuses without either: the space path the content actually reached,
# or the user's own words saying it can go. Written as a condition on the move rather than as a
# sentence in a contract, because the sentence was there and did not hold.
#
# It used to take the user's own words as an override, in a free-text field. That field was filled by
# the run, not by the user: one wrote a sentence the user had never said, for a file they had asked
# to keep. A gate the guarded party fills in itself is not a gate. What remains is the destination,
# checked against the space, and the routing table, which the user writes once and which holds for
# every file of that kind.
def _routing_learn_keep(space: Path, regel: dict, wert: str) -> None:
    """Write down what happened to the file itself, where the rule that covered it had no answer yet.

    The answer is learned from the act rather than asked for. Asking was the first design and it was
    the same mistake this project keeps making: the run was told, in the text it reads at session
    start, to put the question once and record the answer. On the first real morning it decided and
    said nothing, so the rule was as empty afterwards as before and the next day decided again.

    A decision that already happened is not a guess, and writing it down is what makes it a rule
    rather than a mood. It is said out loud with the command that changes it, and `routing show`
    carries it from then on, so a wrong one costs the user a sentence rather than staying invisible.

    The rule is passed in rather than looked up here, because by the time this runs the file has
    already moved: a rule that matches on a word in the content would find nothing to read and
    quietly learn nothing, while one matching on the name would still work. Half a mechanic that
    depends on how the user happened to write their rule is worse than none.
    """
    if wert not in ("with-result", "discard") or not regel or regel.get("keep"):
        return
    daten = _routing(space)
    for eintrag in daten.get("rules") or []:
        if isinstance(eintrag, dict) and eintrag.get("name") == regel.get("name"):
            eintrag["keep"] = wert
            break
    else:
        return
    try:
        _routing_path(space).write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    except OSError:
        return
    was = ("the file itself is kept beside what is made from it" if wert == "with-result"
           else "the file itself goes to the trash once its content is filed")
    print(f"note: your rule `{regel.get('name', '?')}` did not say what happens to the file itself. "
          f"Written down from what happened here: {was}. Change it with `zanmai.py routing set "
          f"\"{regel.get('name', '?')}\" {regel.get('to', '')} --keep "
          f"{'discard' if wert == 'with-result' else 'with-result'}`.")


def _import_exit(space: Path, filed_to: str | None, path: Path | None = None) -> tuple[str, str]:
    """(what to log, what to refuse with) for a file on its way out of the inbox.

    There is no way to keep a file in the inbox, and there was one for a while: a rule could say the
    file stays, and one did. That is against what the inbox is. A file left there is read again at
    every session start, is indistinguishable from one that arrived this morning, and turns the one
    area that exists to empty into a place things live. What a rule decides is where a file goes,
    never whether it goes.
    """
    if not filed_to:
        return "", (
            f"fail: nothing is thrown away out of {INBOX_DIR}/ before its content is in the space. "
            f"Say where it landed with `--filed-to <space path>`. A summary in the conversation is "
            f"not a place, and there is no wording that substitutes for one: the gate used to take "
            f"the user's words in a free-text field, and a run that meant to get past it wrote the "
            f"sentence itself. Where a kind of file is meant to stay put, that belongs in the "
            f"routing table, where it holds for every file of that kind.")
    ziel = (space / filed_to).resolve() if not Path(filed_to).is_absolute() else Path(filed_to).resolve()
    # Both sides resolved, and that is not tidiness. Resolving only the target refuses every filing
    # in a space that is reached through a symlink, which is the ordinary case for a temporary
    # folder on macOS and happens to anybody whose home or disk is linked. The same one-sided
    # comparison was found in the update path and fixed there; this was the second place.
    try:
        ziel_rel = ziel.relative_to(space.resolve()).as_posix()
    except ValueError:
        return "", f"fail: --filed-to '{filed_to}' is not inside the space."
    if not ziel.exists():
        return "", (f"fail: --filed-to '{ziel_rel}' does not exist. The content has to be somewhere "
                    f"before the file it came from can go.")
    for tot in (INBOX_DIR, TRASH_DIR, ARCHIVE_DIR):
        if ziel_rel == tot or ziel_rel.startswith(f"{tot}/"):
            return "", (f"fail: --filed-to '{ziel_rel}' is in {tot}/, which is not a place content "
                        f"arrives at.")
    return f"content filed to {ziel_rel}", ""


def _move_into(space: Path, path: Path, folder: str, done: str, *, dated: bool = False,
               filed_to: str | None = None) -> int:
    """Move a file to `<folder>/[<date>/]<its current space-relative path>` and log it.

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
        rel = path.relative_to(space)
    except ValueError:
        print(f"fail: path '{path}' is not inside space '{space}'", file=sys.stderr)
        return 1
    if not path.exists():
        print(f"fail: path does not exist: {path}", file=sys.stderr)
        return 1

    rel_str = rel.as_posix()
    grund = ""
    # Only the trash. The archive is a place in the space: what goes there stays indexed and
    # findable, which is exactly the condition being asked for, so demanding a second destination
    # for it would be circular. The trash is swept.
    if rel_str.startswith(f"{INBOX_DIR}/") and folder == TRASH_DIR:
        grund, fehler = _import_exit(space, filed_to, path)
        if fehler:
            print(fehler, file=sys.stderr)
            return 1
    unter = Path(_today()) / rel if dated else rel
    target = space / folder / unter
    if target.exists() and folder == TRASH_DIR:
        # Two files of the same name discarded on the same day is ordinary, and the second one is
        # not an error: a repeated repair step, a file that came back and went again. It goes next
        # to the first under a counter, the way every other collision in the space is resolved.
        # Refusing it stopped a migration halfway through on its second run.
        n = 1
        while target.exists():
            target = target.with_name(f"{target.stem}-{n}{target.suffix}")
            n += 1
    elif target.exists():
        print(f"fail: {folder}/{unter.as_posix()} is already taken. Deal with that copy first.",
              file=sys.stderr)
        return 1
    # Read while the file is still there: a rule matching on a word in the content cannot be
    # found once it has moved, and this has to hold whichever way the user wrote their rule.
    regel = (_route_for_file(space, path)
             if rel_str.startswith(f"{INBOX_DIR}/") and folder == TRASH_DIR else {})
    _space_mkdir(space, target.parent, parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    _append_activity_log(space, "zanmai.py",
                         f"{done} {rel_str}" + (f" ({grund})" if grund else ""))
    print(f"ok: {done} {rel_str} -> {target.relative_to(space).as_posix()}"
          + (f" ({grund})" if grund else ""))
    _routing_learn_keep(space, regel, "discard")
    return 0


# How far a status change is followed, and how much of it is ever put in front of a person. Two
# steps, because the thing that hangs off the cancelled thing usually has something hanging off it
# in turn: the trip carries the flight, the flight carries the seat. Three steps reach half the
# space and turn a decision into a reading exercise. Thirty items is where a list stops being read.
_STATUS_CHAIN_DEPTH = 2
_STATUS_CHAIN_CAP = 30


def _status_change_material(space: Path, target: Path) -> dict:
    """Gather what a status change on `target` touches, for a person to judge, not to decide.

    Both directions, and that is the point of it. Outgoing links are what the file itself names.
    Incoming links are what named the file, and that is where the consequences of a cancellation
    actually live: cancel a trip and the flight, the hotel and the car point at it, not the other
    way round. Following only outgoing links found the one direction that mostly does not matter.

    Two levels deep, because what hangs off the cancelled thing usually carries something in turn.
    Capped, and the cap is reported rather than hidden.

    The mechanic's job stops at finding. It never guesses which of those still matter once the
    status changes, and it never changes one: a cancelled trip does not cancel the camera somebody
    bought for it, it only raises the question. That question is a reading judgement, and a script
    gets it wrong as often as right. What a script can do reliably is make sure nothing that hangs
    off this goes unread before the question is put.
    """
    def eigene_zeilen(text: str) -> list[dict]:
        raus = []
        for nr, zeile in enumerate(text.splitlines(), start=1):
            m = _TASK_LINE_RE.match(zeile)
            if m and m.group("state") == " ":
                raus.append({"line": nr, "text": zeile.strip(), "due": _task_due(zeile)})
        return raus

    def eintrag(pfad: Path, text: str, richtung: str, stufe: int) -> dict:
        _fm, _order, body = _split_frontmatter(text)
        return {"path": pfad.relative_to(space).as_posix(), "status": _status_of(text),
                "excerpt": body.strip()[:300], "open_tasks": eigene_zeilen(text),
                "direction": richtung, "level": stufe}

    eigener_text = target.read_text(encoding="utf-8")
    ergebnis: dict = {"own_tasks": eigene_zeilen(eigener_text), "linked": [], "cut": 0}

    def zeigt_auf(text: str, ziel: Path) -> bool:
        for slug in _WIKILINK_RE.findall(text):
            aufgeloest = _resolve_space_file(space, slug)
            if aufgeloest is not None and aufgeloest == ziel:
                return True
        return False

    gesehen: set[Path] = {target}
    front: list[Path] = [target]
    for stufe in range(1, _STATUS_CHAIN_DEPTH + 1):
        naechste: list[Path] = []
        for quelle in front:
            try:
                quelltext = quelle.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # What this file names.
            for slug in _WIKILINK_RE.findall(quelltext):
                verlinkt = _resolve_space_file(space, slug)
                if verlinkt is None or verlinkt in gesehen:
                    continue
                try:
                    text = verlinkt.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                gesehen.add(verlinkt)
                if len(ergebnis["linked"]) >= _STATUS_CHAIN_CAP:
                    ergebnis["cut"] += 1
                    continue
                ergebnis["linked"].append(eintrag(verlinkt, text, "names it", stufe))
                naechste.append(verlinkt)
            # What names this file. Read over the user's own areas only: the machine's own folders
            # link for their own bookkeeping and none of it is a consequence for anybody.
            for kandidat in sorted(space.rglob("*.md")):
                if kandidat in gesehen or not kandidat.is_file():
                    continue
                kopf = kandidat.relative_to(space).as_posix().split("/", 1)[0]
                if kopf in _TASK_SKIP_ROOTS or kopf.startswith("."):
                    continue
                try:
                    text = kandidat.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if not zeigt_auf(text, quelle):
                    continue
                gesehen.add(kandidat)
                if len(ergebnis["linked"]) >= _STATUS_CHAIN_CAP:
                    ergebnis["cut"] += 1
                    continue
                ergebnis["linked"].append(eintrag(kandidat, text, "points at it", stufe))
                naechste.append(kandidat)
        front = naechste
        if not front:
            break
    return ergebnis


def cmd_file_status(args: argparse.Namespace) -> int:
    """Set or read a file's `status:`, the one field that says whether it still stands.

    A command rather than a hand edit, because the value has a vocabulary and a hand edit has none.
    Setting it to `done` or `cancelled` is what takes the file's own open task lines and its dates
    out of the session start, so a wrong spelling is not a cosmetic problem: it silences nothing and
    nobody notices. It never touches a linked file's own status or content: `--check` surfaces what
    is linked so a person judges it, `--set` alone never does.
    """
    space = Path(args.space).resolve()
    target = _resolve_space_file(space, args.path)
    if target is None:
        print(f"fail: no such file in the space: {args.path}", file=sys.stderr)
        return 1
    rel = target.relative_to(space)
    if not args.set:
        jetzt = _status_of(target.read_text(encoding="utf-8"))
        print(f"{jetzt or '(none)'}  {rel}")
        return 0
    wert = args.set.strip().lower()
    if wert not in STATUS_VALUES:
        print(f"fail: '{wert}' is not a status. Use one of: {', '.join(STATUS_VALUES)}", file=sys.stderr)
        return 1
    # Closing something is where the chain matters, so the look is not optional there. Asked to
    # cancel a trip, a run set the status and moved on; the flight, the hotel and the money still
    # in play pointed at that trip and none of them was ever raised. So a closing status refuses
    # once, prints what hangs off this, and goes through on the second call with `--reviewed`.
    #
    # What that flag is: a forced stop, not proof. The run sets it itself, and a run determined to
    # get past a gate can. It is here because the failure it addresses was not defiance, it was a
    # step nobody thought of; a stop that puts the consequences on the screen fixes that kind and
    # no other. `--user-said` was the version of this that pretended to be proof and was removed.
    schliesst = wert in STATUS_CLOSED
    gesehen = bool(getattr(args, "reviewed", False))
    if getattr(args, "check", False) or (schliesst and not gesehen):
        material = _status_change_material(space, target)
        jetzt = _status_of(target.read_text(encoding="utf-8"))
        etwas = bool(material["own_tasks"] or material["linked"])
        if schliesst and not gesehen and not etwas and not getattr(args, "check", False):
            pass  # nothing hangs off it, so there is nothing to put to anybody: fall through
        else:
            print(f"Setting {rel} from '{jetzt or '(none)'}' to '{wert}'. Nothing written yet.")
            eigene = material["own_tasks"]
            if eigene:
                print(f"\n{rel} itself has {len(eigene)} open task line(s):")
                for t in eigene:
                    print(f"  {t['text']}")
            for verlinkt in material["linked"]:
                print(f"\n{verlinkt['direction']}: {verlinkt['path']} "
                      f"(status: {verlinkt['status'] or 'none'})")
                auszug = " ".join(verlinkt["excerpt"].split())[:160]
                print(f"  excerpt: {auszug}")
                for t in verlinkt["open_tasks"]:
                    print(f"  {t['text']}")
            if material["cut"]:
                print(f"\n{material['cut']} more not listed. Say so; a longer list is not read.")
            if not etwas:
                print("\nNothing hangs off this, no open task lines. Nothing for a person to weigh in on.")
            print(f"\nRelay this as a short list, one line per item, ending in one clear question: "
                  f"which of these, if any, should also be closed or changed once '{wert}' is set. "
                  f"Nothing here is closed by this change; each one is a question. Do not summarise "
                  f"it into a paragraph, and do not set the status until answered.")
            if getattr(args, "check", False):
                return 0
            print(f"\nRefused for now: this closes something and what hangs off it has not been "
                  f"put to the user yet. Ask them, then run the same command again with "
                  f"`--reviewed`.", file=sys.stderr)
            return 2
    changed, notes = _edit_frontmatter_in_place(target, {"status": wert}, [])
    for note in notes:
        print(f"  {note}")
    if not changed:
        print(f"ok: {rel} already carries status: {wert}")
        return 1 if notes else 0
    _append_activity_log(space, args.agent or "zanmai.py", f"status of {rel} set to {wert}")
    folge = (" Its open task lines and its dates stop being offered at session start."
             if wert in STATUS_CLOSED else "")
    print(f"ok: {rel} -> status: {wert}.{folge}")
    return 0


def cmd_trash_file(args: argparse.Namespace) -> int:
    """Move a file into space-relative `<trash>/<original-path>`. Reversible with `file restore`.

    `getattr` on the two inbox arguments rather than plain attributes: this is also called from
    inside `bundle remove-file`, which builds its own namespace and has nothing to do with imports.
    """
    space = Path(args.space).resolve()
    return _move_into(space, Path(args.path).resolve(), TRASH_DIR, "trashed", dated=True,
                      filed_to=getattr(args, "filed_to", None))


def cmd_archive_file(args: argparse.Namespace) -> int:
    """Move a file into space-relative `<archive>/<original-path>`. Reversible with `file restore`."""
    space = Path(args.space).resolve()
    return _move_into(space, Path(args.path).resolve(), ARCHIVE_DIR, "archived")


def cmd_restore_file(args: argparse.Namespace) -> int:
    """Put a trashed or archived file back where it came from.

    The counterpart was missing: files went into the trash and nothing brought them out, which makes
    a trash a delete with extra steps. The origin is read off the path, so this works for anything
    that got there through `file trash` or `file archive`, whoever moved it.
    """
    space = Path(args.space).resolve()
    path = Path(args.path).resolve()
    try:
        rel = path.relative_to(space)
    except ValueError:
        print(f"fail: path '{path}' is not inside space '{space}'", file=sys.stderr)
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

    target = space / origin_rel
    if target.exists():
        print(f"fail: {origin_rel.as_posix()} exists again. Move or rename it first, "
              f"otherwise the restore would overwrite it.", file=sys.stderr)
        return 1
    _space_mkdir(space, target.parent, parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    _append_activity_log(space, "zanmai.py", f"restored {origin_rel.as_posix()} from {holder}/")
    print(f"ok: restored {origin_rel.as_posix()}")
    return 0


def cmd_register_contact(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    slug = _slugify(args.slug)
    target_dir = space / (PEOPLE_DIR if args.kind == "person" else ORGANISATIONS_DIR)
    # `bundle create` makes its own folder; this one did not and died with a traceback instead. In a
    # set-up space the folder is there, so it only ever showed on a space that predates it.
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slug}.md"
    if target.exists():
        print(f"fail: contact exists: {target.relative_to(space)}", file=sys.stderr)
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
    # practice address ended up as body prose in practice's place.
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
    _append_activity_log(space, "zanmai.py", f"registered contact {kind_field} -> {target.relative_to(space)}{log_suffix}")
    print(f"ok: contact created at {target.relative_to(space)}")
    return 0


# ---------------------------------------------------------------------------
# Pattern-Engine: space-index (Schicht A) and patterns (Schicht B).
#
# Schicht A: walk space, extract metadata per markdown file. Write
#   zanmai/memory/space-index.json. Pure-data layer, no domain knowledge.
#
# Schicht B: aggregate hubs and bundles from Schicht A. Write
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
    rarely add signal a bundle cluster cares about.
    """
    # Strip code blocks, URLs, and inline markdown that pollute the token-stream.
    snippet = body[:max_chars]
    snippet = re.sub(r"```.*?```", " ", snippet, flags=re.DOTALL)
    snippet = re.sub(r"`[^`\n]+`", " ", snippet)
    snippet = re.sub(r"https?://\S+", " ", snippet)
    snippet = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", snippet)  # images
    snippet = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", snippet)  # markdown links
    return _tokenize(snippet)


def _extract_file_entry(file_path: Path, space: Path) -> dict | None:
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
        rel_path = file_path.relative_to(space).as_posix()
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
    """Return True if a space-relative path sits inside a `<Name>.base/` folder.

    Some editors keep a table or board as a folder with that suffix, holding a schema and rows that
    only that editor writes. They are the user's, whatever put them there, and Zanmai reads and
    writes nothing inside them. Detection is any path segment ending in `.base`."""
    for segment in rel_path.split("/"):
        if segment.endswith(".base") and len(segment) > len(".base"):
            return True
    return False


def _walk_space_markdown(space: Path, scope: str | None = None) -> list[Path]:
    """Walk markdown files under space (or space/scope). Skip the internal
    `zanmai/` tree entirely (contracts, generated state like `briefing.md`,
    logs, memory), it is not user content, its wikilink-shaped
    examples produce false-positive broken-link reports, and its per-session
    regeneration would otherwise make the index look perpetually stale. Also skip
    `.claude/`, the import folder, the root `CLAUDE.md`, and database
    folders (`<Name>.base/`, the user's own)."""
    base = (space / scope) if scope else space
    if not base.exists() or not base.is_dir():
        return []
    out = []
    for f in base.rglob("*.md"):
        if not f.is_file():
            continue
        try:
            rel = f.relative_to(space).as_posix()
        except ValueError:
            continue
        if rel.startswith(f"{SYSTEM_DIR}/"):
            continue
        if rel.startswith(".claude/"):
            continue
        if rel.startswith(f"{INBOX_DIR}/"):
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
    space = Path(args.space).resolve()
    files = _walk_space_markdown(space, args.scope)
    entries = []
    for f in files:
        entry = _extract_file_entry(f, space)
        if entry is not None:
            entries.append(entry)

    out = {
        "_meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "space": str(space),
            "file_count": len(entries),
            "scope": args.scope or ".",
        },
        "files": entries,
    }

    target = space / MEMORY_DIR / "space-index.json"
    _atomic_write_json(target, out)

    # Clear the stale marker; the index now reflects current state.
    stale_marker = space / MEMORY_DIR / ".index-stale"
    if stale_marker.exists():
        try:
            stale_marker.unlink()
        except OSError:
            pass

    if not args.quiet:
        print(f"reindex ok: {len(entries)} files -> {target.relative_to(space)}")
    return 0


def _bundle_segments(rel_path: str) -> tuple[str, str] | None:
    """Return (kind-folder, slug) if rel_path sits inside a `<kind>/<slug>/` bundle, else None.

    Two segments plus a file, not three: the kind folder is a space root now, so the shortest path
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


def _aggregate_bundles(entries: list[dict], min_count: int) -> dict:
    """Token-cluster across filename, tags, h1, body. Tokens with >= min_count files.

    Each cluster entry also records sources counts (how many files carry the
    token in the strong slots - filename/tag/h1 - versus only in body) so
    consumers can tell strong clusters from weak body-only co-occurrences.
    """
    bundle_files: dict[str, set[str]] = {}
    bundle_strong: dict[str, set[str]] = {}
    for e in entries:
        strong: set[str] = set()
        strong.update(e.get("filename_tokens") or [])
        for t in e.get("tags") or []:
            strong.update(_tokenize(t))
        strong.update(e.get("h1_tokens") or [])
        all_tokens = strong | set(e.get("body_tokens") or [])
        for tok in all_tokens:
            bundle_files.setdefault(tok, set()).add(e["path"])
            if tok in strong:
                bundle_strong.setdefault(tok, set()).add(e["path"])
    out = {}
    for token, paths in bundle_files.items():
        if len(paths) < min_count:
            continue
        strong_paths = bundle_strong.get(token, set())
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
    space = Path(args.space).resolve()
    index_path = space / MEMORY_DIR / "space-index.json"
    if not index_path.exists():
        print(f"space-index.json missing - run `zanmai.py index rebuild {space}` first", file=sys.stderr)
        return 1

    data = json.loads(index_path.read_text(encoding="utf-8"))
    entries = data.get("files", [])

    out = {
        "_meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "space": str(space),
            "based_on_index": data.get("_meta", {}).get("generated", ""),
            "file_count": len(entries),
            "min_count": args.min_count,
        },
        "bundles": _aggregate_bundles(entries, min_count=args.min_count),
        "wikilink_hubs": _aggregate_wikilink_hubs(entries, min_count=args.min_count),
        "existing_bundles": _aggregate_existing_bundles(entries),
        "co_occurrence": _aggregate_co_occurrence(entries, min_count=args.min_count),
    }

    target = space / MEMORY_DIR / "patterns.json"
    _atomic_write_json(target, out)

    if not args.quiet:
        print(
            f"patterns ok: bundles={len(out['bundles'])} "
            f"hubs={len(out['wikilink_hubs'])} "
            f"bundles={len(out['existing_bundles'])} "
            f"co_occ_tokens={len(out['co_occurrence'])} "
            f"-> {target.relative_to(space)}"
        )
    return 0


def cmd_find_bundle(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    if not space.is_dir():
        print(
            f"space not found: {space} - `--tokens` takes one comma-separated value "
            f"(`--tokens a,b`, not `--tokens a b`); a missing comma pushes the next word "
            f"into the space argument",
            file=sys.stderr,
        )
        return 1
    patterns_path = space / MEMORY_DIR / "patterns.json"
    if not patterns_path.exists():
        print(f"patterns.json missing - run `zanmai.py index patterns {space}` first", file=sys.stderr)
        return 1

    data = json.loads(patterns_path.read_text(encoding="utf-8"))
    raw = [t.strip() for t in args.tokens.split(",") if t.strip()]
    tokens = []
    for r in raw:
        tokens.extend(_tokenize(r))
    tokens = list(dict.fromkeys(tokens))

    bundles_idx = data.get("bundles", {})
    co_idx = data.get("co_occurrence", {})

    matching_clusters = []
    for tok in tokens:
        info = bundles_idx.get(tok)
        if info:
            strong = info.get("strong_count", 0)
            matching_clusters.append({
                "bundle": tok,
                "files": info["files"],
                "count": info["count"],
                "strong_count": strong,
                "signal": "strong" if strong >= 2 else ("body_only" if strong == 0 else "mixed"),
            })
    # Rank by strong-count first, then total count.
    matching_clusters.sort(key=lambda t: (-t["strong_count"], -t["count"]))

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
        "matching_clusters": matching_clusters,
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

# The ten entries at the space root, and what has to exist inside them. Flat on purpose: no
# container above the content folders, because a container is what the old `inbox/` was, and it put
# everything a person actually works with one level down while the machine sat on top.
#
# All ten are created even when empty, so the shape of the space is visible before anything is in
# it. Nothing below an area is created: a life's
# subject headings belong to whoever owns the space, and an example shipped in the distribution
# becomes a default nobody chose.
REQUIRED_FOLDERS_CORE = [
    # Where it falls in.
    JOURNAL_DIR,
    # Where it takes shape, gathers and settles.
    WORKBENCH_DIR,
    LIFE_DIR,
    BRANDS_DIR,
    KNOWLEDGE_DIR,
    ARCHIVE_DIR,
    # Who it is about.
    PEOPLE_DIR,
    ORGANISATIONS_DIR,
    # Where it comes in.
    INBOX_DIR,
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


def _required_folders(space_root: Path) -> list[str]:
    """Every folder a set-up space must have, from the one list above.

    The single source matters more than it looks. This used to be two lists, the one
    above for a fresh install and a copy of it in the manifest for an existing space,
    and they drifted: a release added a folder here and not there, so a
    new space got the folder and an updated one did not. The structure check read the
    manifest copy too, which is the part that makes such a drift invisible rather than
    merely wrong: producer and checker agreed with each other and were both missing
    the same entry, so a space without the folder validated with exit code 0. One
    list, read by whoever creates and whoever checks, cannot disagree with itself.

    Excludes the runtime folder, which describes this machine and is created when something needs
    it, and the history, which git creates when the first snapshot is taken.
    """
    folders = list(REQUIRED_FOLDERS_CORE)
    folders += [f"{MEMORY_DIR}/agents/{name}" for name in _MEMORY_AGENTS]
    return folders


# The fixed family the space root may hold, plus the generated files that live there. Anything
# else at the root is either a dotfile (an editor's or the OS's own business, left alone by
# design) or a folder that arrived outside any write Zanmai made, a manual Finder action, a
# colleague dropping something into a shared sync folder, a half-finished move. No hook can see
# or refuse that, since it happens outside any Claude Code session, so this is a detector rather
# than a guard: it surfaces the entry so it gets dealt with in days, not found by accident weeks
# later.
_SPACE_ROOT_ALLOWED_DIRS = frozenset({
    JOURNAL_DIR, WORKBENCH_DIR, LIFE_DIR, KNOWLEDGE_DIR,
    ARCHIVE_DIR, CONTACTS_DIR, INBOX_DIR, SYSTEM_DIR,
})
_SPACE_ROOT_ALLOWED_FILES = frozenset({"CLAUDE.md", "README.md", "INDEX.md"})


def _unexpected_root_entries(space: Path) -> list[str]:
    """Names at the space root outside the fixed family, dotfiles excluded. Empty when the root
    is exactly what setup and the folder architecture say it should be."""
    if not space.is_dir():
        return []
    found = []
    for entry in sorted(space.iterdir()):
        name = entry.name
        if name.startswith("."):
            continue
        if entry.is_dir() and name in _SPACE_ROOT_ALLOWED_DIRS:
            continue
        if entry.is_file() and name in _SPACE_ROOT_ALLOWED_FILES:
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


def _install_skill_symlinks(space_root: Path, mapping: list[tuple[str, str]]) -> None:
    """Write a thin adapter `.claude/skills/<folder>/SKILL.md` for each shipped
    skill: the skill's frontmatter (so the host discovers it) plus a one-line body
    pointing at the real procedure under `zanmai/system/skills/`. Real files,
    not symlinks, portable across machines and safe to copy or sync. The
    canonical procedure stays in the AI-neutral `zanmai/system/` tree, so a
    different host only needs its own adapter, not a rewrite. Stale adapters, a
    skill dropped by an update, or a legacy symlink from an older install, are
    pruned."""
    skills_dir = space_root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for claude_folder, source_folder in mapping:
        source_rel = f"{SYSTEM_MATERIAL_DIR}/skills/{source_folder}/SKILL.md"
        source_file = space_root / source_rel
        if not source_file.exists():
            continue
        fm = _frontmatter_block(source_file.read_text(encoding="utf-8"))
        # The adapter's name has to be the folder it sits in, because that is what the host offers as
        # a command. Copying the source's own `name:` shipped `zanmai:update` in a folder called
        # `zanmai-update`, and typing either one answered "Unknown command": the colon form is how a
        # plugin skill is addressed, not a project one. Found in a space in daily use, and it
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
    ("marcus",  True,    True),
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
    ("zanmai-housekeeping", "housekeeping"),
    ("zanmai-show-welcome", "welcome"),
    ("zanmai-connection", "manage-connections"),
    ("zanmai-voice", "voice"),
    ("zanmai-write", "write"),
    ("zanmai-grill-me", "brief"),
    ("zanmai-create-launcher", "create-launcher"),
]

# What is deliberately NOT in that list, and why the list is short.
#
# Registering a skill puts it in the command menu the user opens by typing a slash. That menu is
# theirs: it answers "what can I ask for". A specialist's working method is not something anybody
# asks for by name, and fifteen of them in there buried the eleven that are. On 2026-08-26 all
# twenty-six were registered at once, on the reasoning that a skill the host cannot see is a file
# rather than a capability. That reasoning does not hold for these fifteen, and it is measurable why:
# every one of them is named with its full path in the contract of the expert who runs it (Carol
# reads `skills/typst/SKILL.md`, Loki reads `skills/media/SKILL.md`, and so on down the list). The
# expert finds its method by reading its own contract, not by the host routing to it. What the host
# routes on is the expert's description, and that has not changed.
#
# So the rule is one sentence: an adapter is a command, a command is for the user, and a method that
# only a specialist ever runs is reached through that specialist's contract. `one-home.py` holds the
# documentation to this, so a skill cannot claim one thing and be registered as the other.


def _model_overrides(space_root: Path) -> dict[str, str]:
    """Per-expert model choices the user made in `zanmai/user.md`, as `models:` in the frontmatter.

    Absent means the contracts' own defaults apply. Nothing here is guessed and nothing is written
    back: which model an expert runs on is configuration, and a run never decides it about itself.
    """
    user_md = space_root / SYSTEM_DIR / "user.md"
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


def _install_agent_symlinks(space_root: Path, agent_names: list[str]) -> None:
    """Write a thin adapter `.claude/agents/<name>.md` for each expert: the
    expert's frontmatter (so the host discovers it) plus a one-line body pointing
    at the real contract under `zanmai/system/experts/`. Real files, not
    symlinks, portable and copy/sync-safe. The contract stays in the AI-neutral
    `zanmai/system/` tree, so another host only needs its own adapter. Stale
    adapters, an expert dropped by an update, or a legacy symlink, are
    pruned so no dead agent is left behind."""
    agents_dir = space_root / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    model_overrides = _model_overrides(space_root)
    for name in agent_names:
        source_rel = f"{SYSTEM_MATERIAL_DIR}/experts/{name}/{name}.md"
        source_file = space_root / source_rel
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
            f"\n\nAdapter only, so the host can find you. The procedure lives in the space.\n\n"
            f"## On every invocation, in order\n\n"
            f"1. Read `{source_rel}`, your full contract. It is authoritative over anything here.\n"
            f"2. Read `{SYSTEM_MATERIAL_DIR}/operating-principles.md`. Everything in it applies to "
            f"you in full, and your contract does not repeat it: approval before write, source "
            f"files, indexing and logging, parking a run, how a reply reads. A rule you do not find "
            f"in your contract is in there, not absent.\n"
            f"3. Read the skills your contract names for this job, at the point the job needs them, "
            f"from `{SYSTEM_MATERIAL_DIR}/skills/<name>/SKILL.md`. Anything longer than a line that "
            f"gets written for the user goes through the `write` skill, whoever runs it.\n\n"
            f"## Running the script\n\n"
            f"`zanmai.py <subcommand>` in your contract and in every skill is shorthand for "
            f"`<python_cmd> {SYSTEM_MATERIAL_DIR}/scripts/zanmai.py <subcommand>`, run from the "
            f"space root, with `<python_cmd>` from the frontmatter of `{USER_FILE}` (usually "
            f"`python3`). There is no zanmai.py at the space root, and it is not on `PATH`.\n\n"
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


# The setup dialogue's own schema version, independent of the distribution version. A space
# whose `zanmai/user.md` carries no `setup_schema_version` field is read as 1, the shape before
# purpose, structure and starter bundles existed. The greeting skill compares this constant
# against that field: lower means a later setup version added a mandatory block this space never
# saw, and `setup catch-up` asks it once, then stamps the field so it is never asked again.
#
# Which round added what is written out in the setup skill, under "Catching up an older space",
# because that is where it is read. Raising this number is what makes a space ask the new block, so
# it goes up in the same change that adds one, never on its own and never afterwards.
#   1  identity only
#   2  purpose, the areas to start with, projects and goals
#   3  the capability overview, its prerequisites, and that a missing one can be built
CURRENT_SETUP_SCHEMA_VERSION = 3

PURPOSE_CHOICES = ("private", "professional", "project", "all", "unclear")


def _render_user_md_init(
    *, first_name: str, last_name: str, language: str, owner_contact_slug: str,
    preferred_address: str = "",
    python_cmd: str = "python3",
    purpose: str = "",
    purpose_detail: str = "",
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    full_name = f"{first_name} {last_name}".strip()
    address_field = f'"{preferred_address}"' if preferred_address else '""'
    address_line = f"- **Preferred address**: {preferred_address}" if preferred_address else f"- **Preferred address**: (same as first name)"
    purpose_line = f"- **What this space is for**: {purpose}" + (f" ({purpose_detail})" if purpose_detail else "") if purpose else ""
    return f"""---
first_name: "{first_name}"
last_name: "{last_name}"
preferred_address: {address_field}
language: "{language}"
owner_contact: "{owner_contact_slug}"
purpose: "{purpose}"
purpose_detail: "{purpose_detail}"
python_cmd: "{python_cmd}"
update_channel: ""
auto_snapshots: true
setup_schema_version: {CURRENT_SETUP_SCHEMA_VERSION}
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
{purpose_line}

## Notes for Steve

Add anything you want Steve to know about you here: preferences, working style, anything that should persist across sessions. This is not a profile form, write freely.

One thing does not belong here: what should happen to a kind of file that arrives. That goes in the routing table (`zanmai.py routing set`), which is read every time something lands in `inbox/`. Written here instead, it steers your material from outside the import path, where no scan sees it and no rule covers it. Say it to Steve and he writes the rule.

## Feature toggles

- `models:` (optional). Which model each expert runs on, one line per expert, for example `carol: opus`
  or `pepper: haiku`. Absent means the default each expert's contract ships with. This lives here and
  not in the contracts because an update replaces those, and because the choice is yours: no run
  decides how hard its own work is. A job that genuinely needs more says so and waits for you.
- `auto_snapshots: true`. Master switch for every snapshot Zanmai takes on its own, which is only ever before it overwrites existing material (update, bulk repair, space-wide rename, restore). When `false`, all `zanmai.py snapshot create` calls exit silently with `skip: auto_snapshots disabled` and no folder is written, useful when the user has their own backup discipline (git, Time Machine, ...). Flip it with `zanmai.py snapshot enable` / `disable` or by editing this line directly.
- `python_cmd: "{python_cmd}"`. The Python invocation that worked at setup time. Steve uses this when running scripts, substitutes for `python3` in skill template phrasing. On Windows this is often `py -3` or `python`, on Linux and macOS usually `python3`.
- `update_check: true` (optional, add the line to turn it off). Whether Zanmai may ask the update source once a day whether a newer version exists. Set to `false` and nothing reaches the network on its own; you can still update whenever you ask for one. It is read here first and in the manifest second, so a decision written here survives every update.
- `update_channel: ""`. Which branch `zanmai.py setup upgrade` tracks. Empty means the published release. Set with `zanmai.py setup upgrade . --channel <name>`, which switches immediately and remembers the choice here, update-immune so it survives every future update; `--channel release` switches back.
- `purpose` / `purpose_detail`. What the space is mainly for (`private`, `professional`, `project`, `all`, or `unclear`), plus a free-text detail: the project's name when `purpose` is `project`, or the user's own words when it is `unclear`. Set once at setup or catch-up, changed by editing this file directly.
- `setup_schema_version`. Which round of setup questions this space has answered, as a number in the frontmatter above. Where it is lower than what the running distribution ships, an update added questions this space never saw, and the next session asks them once. Written by setup and by `setup catch-up`, never by hand.
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
This is the owner contact for this space. `zanmai/user.md` points here as `owner_contact`. Steve reads it at session start to know who the user is.

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

- **Domain expertise**: fields where you have deep knowledge. Steve and Reed consult this before research and explanations so they do not waste your time with beginner content in fields you know cold. Audience calibration in the Reed dispatch reads this directly.
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

Chronological append-only log of writes and notable actions across the space.
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

The areas below are a workplace. Things arrive in the inbox, come onto the desk to be worked on,
and are put away when the work is done: into your own life, into what you know, or into the
cupboard. Nothing has to travel the whole way, and only the desk is meant to empty.

## Journal

`{JOURNAL_DIR}/` is the time axis: one entry per day, filed under its year. What is on your mind
goes in today, and what happened on a day belongs to that day. Nothing is ever taken out of an
entry.

## Workbench

The desk: work that has an end, with every draft of it together in one bundle. If you cannot name
the event that finishes a piece, it does not belong here. You put things here and so does Zanmai.
See `{WORKBENCH_DIR}/`.

(empty)

## Life

What is yours and matters to you now, at work or at home: health, money, the flat, a hobby, your
own role, the team, a standing responsibility. The research goes to knowledge; what you do with it
lives here. See `{LIFE_DIR}/`.

(empty)

## Knowledge

What would still be right for someone else: what you could look up again or rebuild from scratch.
A write-up of your own machine is not knowledge, a comparison of the best games for a C64 is. See
`{KNOWLEDGE_DIR}/`.

(empty)

## Archive

The folder in the cupboard: an invoice, a policy, a certificate. Not "never needed again" - it is
kept precisely because you take it out again. Each piece carries a date and a keeping reminder, and
nothing goes without you seeing it and saying so. See `{ARCHIVE_DIR}/`.

(empty)

## Contacts

Single files per person and organisation.

### People (`{PEOPLE_DIR}/`)

(empty)

### Organisations (`{ORGANISATIONS_DIR}/`)

(empty)

## Inbox

`{INBOX_DIR}/` is where you drop things. However it lands in there, Zanmai takes it up by itself;
the kind of file decides what happens to it, not a sub-folder. It empties itself.

## System

- `{USER_FILE}`: your profile.
- `{SYSTEM_MATERIAL_DIR}/`: the Zanmai distribution (do not edit, replaced on update).
- `{MEMORY_DIR}/`: cross-session learnings and activity log.
- `{HISTORY_DIR}/`: the snapshots taken before something risky, kept {SNAPSHOT_RETENTION_DAYS} days.
- `{TRASH_DIR}/`: what was thrown away, restorable for {TRASH_RETENTION_DAYS} days.
- `{SCRATCH_DIR}/`: what the machine puts down mid-job, cleared after {SCRATCH_RETENTION_DAYS} days.
- `{LOGS_DIR}/`: session logs and operation reports.
"""


def _known_hooks() -> set[str]:
    """Every hook this script implements, read from its own functions rather than from a list.

    A list beside them is a second copy that goes stale in exactly the release where it matters.
    """
    return {name[len("cmd_hook_"):].replace("_", "-")
            for name in globals() if name.startswith("cmd_hook_")}


def _render_settings_json(space_root: Path, *, python_cmd: str = "python3") -> str:
    """Render .claude/settings.json with the Zanmai hooks wired. Every
    hook is a subcommand of the single zanmai.py CLI now. No connection-guard:
    a host-exposed MCP is available for use, Zanmai adds no second consent gate
    (LD6, re-decided 2026-07-15). The script path is rooted at $CLAUDE_PROJECT_DIR,
    which Claude Code shell-expands to the project root at hook run time, so this
    file is portable: it ships with the folder and works wherever the space is
    copied, no absolute machine path baked in. space_root is kept in the signature
    for the callers that pass it; the rendered command no longer needs it.

    `defaultMode: auto` is set here rather than left to the user. Zanmai routes nearly
    every filing, index and check through its own engine, so the strictest mode turns a
    session into a queue of prompts, and the person who has just finished setup is the
    least equipped to know that a mode switch is what they need. The value is written
    into the space's own settings, never into the user's global config, so it applies
    where Zanmai runs and nowhere else. Zanmai's own guards do not depend on it: they
    are checks on every write, not questions put to the user."""
    zb = f"$CLAUDE_PROJECT_DIR/{SYSTEM_MATERIAL_DIR}/scripts/zanmai.py"
    bekannt = _known_hooks()

    def h(*namen: str) -> list[dict]:
        """The hook entries for the names this script actually implements.

        Filtered rather than listed, because the two halves are written at different moments and a
        space that ends up with a settings.json naming a guard its script does not have is locked
        out: the host reads the script's exit 2 as "block", every Bash call is refused, and the call
        that would finish the update is one of them. Filtering here means the registration can never
        be ahead of the script it points at, whichever direction the version moved.
        """
        return [{"type": "command", "command": f'{python_cmd} "{zb}" hook {n}'}
                for n in namen if n in bekannt]

    def gruppe(matcher: str | None, *namen: str) -> list[dict]:
        eintraege = h(*namen)
        if not eintraege:
            return []
        return [({"matcher": matcher, "hooks": eintraege} if matcher else {"hooks": eintraege})]

    config = {
        "autoMemoryEnabled": False,
        "permissions": {"defaultMode": "auto"},
        "hooks": {
            "SessionStart": gruppe(None, "session-start"),
            "PreToolUse": (
                gruppe("Write|Edit", "checkbox-guard", "prose-guard", "kind-required",
                       "permission-guard")
                + gruppe("Agent", "dispatch-guard")
                + gruppe("mcp__.*", "outward-guard")
                # `permission-guard` hangs on both, and that is the whole point of it: a path is
                # protected from being written, not from a particular tool. It sat on Write|Edit
                # alone, and a `python3 - <<EOF` walked past it into the owner file.
                + gruppe("Bash", "delete-guard", "library-check-guard", "park-guard", "prose-guard",
                         "permission-guard")
            ),
            "PostToolUse": gruppe("Write|Edit", "index-consistency"),
            "SessionEnd": gruppe(None, "session-end"),
        },
    }
    config["hooks"] = {k: v for k, v in config["hooks"].items() if v}
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


def _verify_host_config(space: Path) -> list[str]:
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

    settings_file = space / ".claude" / "settings.json"
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
        # And the other direction, which cost a space its whole shell once. A config naming a hook
        # this script does not implement is the same drift, arrived at from the other side: the
        # wiring ran ahead of the program. Since 0.5.0 an unknown hook name exits 0 instead of
        # blocking, so it no longer locks anybody out, but nothing said it was there, and a config
        # that quietly disagrees with the script is the state every later confusion grows out of.
        bekannt = set(_known_hooks())
        for name in sorted(set(re.findall(r'hook ([a-z][a-z0-9-]*)', wired))):
            if name not in bekannt:
                problems.append(f"hook wired in .claude/settings.json that this version does not "
                                f"implement: '{name}'. `setup update` rewrites the wiring from what "
                                f"the script actually has.")

    for name in _AGENT_NAMES:
        if not (space / ".claude" / "agents" / f"{name}.md").is_file():
            problems.append(f"expert adapter missing: .claude/agents/{name}.md")

    for claude_folder, source_folder in _SKILL_SYMLINK_MAP:
        if not (space / SYSTEM_MATERIAL_DIR / "skills" / source_folder / "SKILL.md").is_file():
            continue  # not shipped in this version, so nothing to wire
        if not (space / ".claude" / "skills" / claude_folder / "SKILL.md").is_file():
            problems.append(f"skill adapter missing: .claude/skills/{claude_folder}/SKILL.md")

    return problems


def _mcp_tools_from_experts(space_root: Path) -> list[str]:
    """Distinct `mcp__<server>__<tool>` names any registered expert is granted,
    read verbatim from each expert contract's `tools:` frontmatter. Used to
    pre-allow those exact tools in settings.local.json so a dispatched expert can
    use a host-exposed MCP without a per-call prompt (LD6: a host-exposed MCP is
    available for use, the host config is the opt-in, so no gate and no prompt)."""
    tools: list[str] = []
    experts_dir = space_root / SYSTEM_MATERIAL_DIR / "experts"
    for name in _AGENT_NAMES:
        contract = experts_dir / name / f"{name}.md"
        if not contract.exists():
            continue
        fm = _frontmatter_block(contract.read_text(encoding="utf-8"))
        for m in re.finditer(r"mcp__[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+", fm):
            if m.group(0) not in tools:
                tools.append(m.group(0))
    return tools


def _render_settings_local_json(space_root: Path, *, python_cmd: str = "python3") -> str:
    """Render .claude/settings.local.json with the allow-rules. The zanmai.py
    script (every subcommand and hook routes through it) plus the exact MCP tools
    the registered experts are granted, so a host-exposed source runs without a
    per-call prompt."""
    scripts_dir = space_root / SYSTEM_MATERIAL_DIR / "scripts"
    rel = f"{SYSTEM_MATERIAL_DIR}/scripts/zanmai.py"
    # Both spellings, because a rule matches the command as it was typed. Only the absolute form was
    # shipped, while every caller in the space runs from the space root and types the relative path,
    # so the rule never matched anything and every write went to a permission prompt. It stayed
    # invisible because read-only calls are waved through on their own merits: the update check ran,
    # and the apply right behind it stopped dead.
    allow = [
        f'Bash({python_cmd} "{scripts_dir}/zanmai.py":*)',
        f'Bash({python_cmd} {scripts_dir}/zanmai.py:*)',
        f'Bash({python_cmd} {rel}:*)',
        f'Bash({python_cmd} "{rel}":*)',
    ]
    allow.extend(_mcp_tools_from_experts(space_root))
    config = {"permissions": {"allow": allow}}
    return json.dumps(config, indent=2) + "\n"


def _run_init_migration(
    space_root: Path,
    *,
    first_name: str,
    last_name: str,
    language: str = "auto",
    email: str = "",
    preferred_address: str = "",
    python_cmd: str = "python3",
    purpose: str = "",
    purpose_detail: str = "",
    bundles: tuple[str, ...] = (),
    goals: tuple[str, ...] = (),
    projects: tuple[str, ...] = (),
) -> None:
    """First-time space setup. Creates folder skeleton, user.md, owner-contact,
    settings, symlinks, memory files and master INDEX. Idempotent only on the
    folder mkdir step; file writes overwrite. Used by `setup init`."""
    folders = _required_folders(space_root)
    for rel in folders:
        (space_root / rel).mkdir(parents=True, exist_ok=True)

    # A space created today has no older shape to move, so every structural step counts as done.
    # Without this the next update would walk them all looking for folders that never existed.
    (space_root / MIGRATIONS_FILE).parent.mkdir(parents=True, exist_ok=True)
    (space_root / MIGRATIONS_FILE).write_text(
        "".join(f"{name}@{revision}\n" for name, revision, _ in _MIGRATIONS), encoding="utf-8")

    nickname = preferred_address.strip() if preferred_address.strip() and preferred_address.strip() != first_name else ""

    contact_slug = _slugify(f"{first_name} {last_name}")
    contact_path_abs = space_root / PEOPLE_DIR / f"{contact_slug}.md"
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

    user_md = space_root / SYSTEM_DIR / "user.md"
    user_md.write_text(
        _render_user_md_init(
            first_name=first_name,
            last_name=last_name,
            language=language,
            owner_contact_slug=contact_slug,
            preferred_address=nickname,
            python_cmd=python_cmd,
            purpose=purpose,
            purpose_detail=purpose_detail,
        ),
        encoding="utf-8",
    )

    (space_root / ".claude" / "settings.json").write_text(
        _render_settings_json(space_root, python_cmd=python_cmd), encoding="utf-8"
    )

    # The distribution repository's ignore rules go where only it reads them, the search rules go
    # where every search tool reads them, and the history of the user's own material starts here,
    # with the empty space as its first state. Starting it now rather than at the first risky write
    # means there is always something to compare against.
    _write_ignore_rules(space_root)
    if shutil.which("git") is not None:
        try:
            _history_ensure(space_root)
            _git(space_root, "add", "-A")
            if _git(space_root, "rev-parse", "HEAD", check=False).returncode != 0:
                _git(space_root, "commit", "-q", "-m", "the-space-as-it-was-set-up")
        except RuntimeError:
            pass  # a space without a history still works; the first snapshot starts one

    _install_skill_symlinks(space_root, _SKILL_SYMLINK_MAP)

    _install_agent_symlinks(space_root, _AGENT_NAMES)

    settings_local = space_root / ".claude" / "settings.local.json"
    if not settings_local.exists():
        settings_local.write_text(
            _render_settings_local_json(space_root, python_cmd=python_cmd), encoding="utf-8"
        )

    (space_root / MEMORY_DIR / "general.md").write_text(
        _render_general_md(contact_slug), encoding="utf-8"
    )
    (space_root / MEMORY_DIR / "activity-log.md").write_text(
        _render_activity_log(), encoding="utf-8"
    )
    for agent in _MEMORY_AGENTS:
        (space_root / MEMORY_DIR / "agents" / agent / "lessons.md").write_text(
            _render_agent_lessons(agent.capitalize()), encoding="utf-8"
        )

    (space_root / "INDEX.md").write_text(_render_master_index(first_name), encoding="utf-8")

    # There from the first day rather than on the first task, so somebody who opens the folder sees
    # where their own to-dos will be before anything has written one.
    _ensure_tasks_file(space_root)

    _create_starter_bundles(space_root, bundles=bundles, goals=goals, projects=projects)

    (space_root / LOGS_DIR / ".keep").touch()


def _parse_csv_list(value: str | None) -> tuple[str, ...]:
    """A comma-separated CLI value into a tuple of trimmed, non-empty names."""
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _create_starter_bundles(space: Path, *, bundles: tuple[str, ...] = (),
                            goals: tuple[str, ...] = (), projects: tuple[str, ...] = ()) -> list[str]:
    """Create one empty bundle per named item, right after setup or a catch-up collected them.

    Not one container bundle: a broad area (health, budget) and a personal goal without a fixed
    end both go to `life`, a named project WITH an end goes to `workbench`, that area's own
    definition. Reuses `cmd_create_bundle` so a starter bundle is built exactly like one made by
    hand later, INDEX.md and activity log included, and a name that already exists is skipped
    rather than failing the whole batch.
    """
    created: list[str] = []
    for kind, titles in (("life", bundles), ("life", goals), ("workbench", projects)):
        for title in titles:
            slug = _slugify(title)
            if (space / _kind_folder(kind) / slug).exists():
                continue
            rc = cmd_create_bundle(argparse.Namespace(space=str(space), kind=kind, slug=slug, title=title))
            if rc == 0:
                created.append(f"{_kind_folder(kind)}/{slug}")
    return created


def cmd_setup_init(args: argparse.Namespace) -> int:
    space = Path(args.space_root).resolve()
    if not space.exists():
        print(f"fail: space root does not exist: {space}", file=sys.stderr)
        return 1
    user_md = space / SYSTEM_DIR / "user.md"
    if user_md.exists():
        print(f"already initialised: {user_md} exists. use 'setup update' to change schema.")
        return 0
    _run_init_migration(
        space,
        first_name=args.first_name,
        last_name=args.last_name,
        language=args.language,
        email=args.email,
        preferred_address=args.preferred_address,
        python_cmd=args.python_cmd,
        purpose=args.purpose or "",
        purpose_detail=args.purpose_detail,
        bundles=_parse_csv_list(args.bundles),
        goals=_parse_csv_list(args.goals),
        projects=_parse_csv_list(args.projects),
    )
    print(f"ok: space initialised at {space}")
    return 0


def _setup_schema_version(space: Path) -> int:
    """The setup schema round this space has answered, 1 for a space with no such field."""
    user_md = space / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return 1
    try:
        fm, _order, _body = _split_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return 1
    raw = str(fm.get("setup_schema_version") or "").strip()
    return int(raw) if raw.isdigit() else 1


def cmd_setup_catchup(args: argparse.Namespace) -> int:
    """Ask and record what a later setup version added, for a space that predates it.

    Run once per version gap, from the greeting skill's gate, never for a space already current.
    Only fields the user actually answers this time are written: `purpose`/`purpose_detail` are
    set if still empty, never overwritten, because a value already there is the user's own answer
    from setup, not a placeholder. The version stamp always advances to the running distribution's,
    the whole point of running this at all.
    """
    space = Path(args.space_root).resolve()
    user_md = space / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        print(f"fail: {user_md} does not exist. Run 'setup init' first.", file=sys.stderr)
        return 1

    # The stamp is what ends the asking, so it may not be set in the same breath as the question.
    # A run asked its block, called this straight afterwards and stopped for the answer; the answer
    # never arrived, the stamp did, and the question was gone for good with nothing recorded. So a
    # call carrying nothing at all is refused: either it brings answers, or it says the user
    # declined. Both are claims the run makes, and a determined run can make either falsely; what
    # this stops is the reflex, which is what actually happened.
    hat_antwort = any([args.purpose, args.purpose_detail, args.bundles, args.goals, args.projects])
    if not hat_antwort and not getattr(args, "declined", False):
        print("fail: nothing to record. Ask the block first and call this with what the user "
              "answered, or with --declined where they said not now. Calling it empty would stamp "
              "the version and end the asking without a single answer.", file=sys.stderr)
        return 1

    fm, order, body = _split_frontmatter(user_md.read_text(encoding="utf-8"))
    if args.purpose and not str(fm.get("purpose") or "").strip():
        fm["purpose"] = args.purpose
        if "purpose" not in order:
            insert_at = order.index("owner_contact") + 1 if "owner_contact" in order else len(order)
            order.insert(insert_at, "purpose")
    if args.purpose_detail and not str(fm.get("purpose_detail") or "").strip():
        fm["purpose_detail"] = args.purpose_detail
        if "purpose_detail" not in order:
            insert_at = order.index("purpose") + 1 if "purpose" in order else len(order)
            order.insert(insert_at, "purpose_detail")
    fm["setup_schema_version"] = CURRENT_SETUP_SCHEMA_VERSION
    if "setup_schema_version" not in order:
        order.append("setup_schema_version")
    user_md.write_text(_render_frontmatter(fm, order) + body, encoding="utf-8")

    created = _create_starter_bundles(
        space,
        bundles=_parse_csv_list(args.bundles),
        goals=_parse_csv_list(args.goals),
        projects=_parse_csv_list(args.projects),
    )
    print(f"ok: setup schema at {CURRENT_SETUP_SCHEMA_VERSION}"
          + (f", created {', '.join(created)}" if created else ""))
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


def _distribution_version(space_or_tree: Path) -> str:
    version_file = space_or_tree / SYSTEM_MATERIAL_DIR / "VERSION"
    if not version_file.exists():
        return ""
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("distribution_version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


# --- One-off repairs to a space that already exists -------------------------
#
# The rules that keep the user's material out of the distribution repository. They used to live in a
# `.gitignore` in the space, and that was the problem: a file in the working tree is read by every
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
    f"/{INBOX_DIR}/",
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


def _write_dist_exclude(space: Path) -> bool:
    """Put the distribution's ignore rules where only its own repository reads them."""
    if not (space / ".git").is_dir():
        return False
    info = space / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "exclude").write_text(_DIST_EXCLUDE, encoding="utf-8")
    return True


# What a search of this space walks, and what it does not.
#
# Moving the rules above into the repository's own `info/exclude` kept them out of the second
# repository. It did not keep them away from search, because a search tool reads that file too, and
# every area of the user's is named in it. So a search of the user's own notes finds a fraction of
# what is there, reports no error, and looks exactly like a search that worked. An empty result and
# "does not exist" are the same sentence, which is how a confident written falsehood gets made.
# Rule, skill and guard were stacked in front of search because of it, none of them touching the
# cause.
#
# `.ignore` is read by search tools and by nothing else, and it is read ahead of the git rules, so a
# line here overrides one there. Derived from the list above rather than typed out a second time,
# because two hand-kept lists of the same folder names is how a rename ends up half applied.
_NIE_DURCHSUCHEN = (HISTORY_DIR, TRASH_DIR, SCRATCH_DIR, RUNTIME_DIR)

_SEARCH_IGNORE_OWN = (
    # Everything the git rules take out comes back, except what a search should never wade through.
    *(f"!{line}" for line in _DIST_EXCLUDE_OWN
      if line.startswith("/") and line.strip("/") not in _NIE_DURCHSUCHEN),
    # Out, whatever the git rules say. The snapshot repository holds every earlier version of every
    # file, so a search of it answers with the past; the trash holds what was thrown away; the two
    # generated indexes would answer every search with a copy of itself.
    *(f"/{d}/" for d in _NIE_DURCHSUCHEN),
    "/.git/",
    f"/{MEMORY_DIR}/space-index.json",
    f"/{MEMORY_DIR}/patterns.json",
    # An editor's own database folder. Everything else in the space says these are the user's and
    # that nothing of Zanmai's reads inside them; a search that walked in anyway would break that
    # promise at the one moment it is most visible, when the results come back.
    "*.base/",
    "__pycache__/",
    "*.pyc",
)

_SEARCH_IGNORE = (
    "# What a search of this space walks. Written by zanmai.py, edits here are overwritten.\n"
    "# Rules of your own belong in `.rgignore`, which every search tool reads ahead of this file.\n"
    "#\n"
    "# git keeps your own material out of the distribution repository, and a search tool reads\n"
    "# those rules too. Without the lines below, a search of your own notes finds nothing and\n"
    "# looks exactly like a search that worked.\n"
    + "".join(f"{line}\n" for line in _SEARCH_IGNORE_OWN)
)


def _write_search_ignore(space: Path) -> None:
    """Put the search rules where every search tool reads them, ahead of the git rules."""
    (space / ".ignore").write_text(_SEARCH_IGNORE, encoding="utf-8")


def _write_ignore_rules(space: Path) -> None:
    """Both ignore files, written from the same constants.

    Idempotent and cheap, so it runs on every session start rather than once at install. The one in
    a live space was written when the areas had different names and still carried them a month
    later: a list written once and never again is a list that goes wrong quietly, and this one
    decides whether the user's material stays out of a commit and whether a search can see it.
    """
    _write_dist_exclude(space)
    _write_search_ignore(space)


# How long the machine keeps what it put aside.
#
# This runs on its own, at session start, and reports what it did. That is deliberate: a cleanup that
# waits for someone to agree to it is a cleanup that never happens, and every folder it reaches holds
# only what the machine itself put there. Nothing the user filed is ever in scope.
#
# One number for all three was the earlier design, and it was wrong for a reason worth writing down:
# it read the three folders as one kind of leaving. Snapshots were then left out of the sweep
# altogether, on the argument that content-addressed storage makes age irrelevant. It does not. A
# changed video or deck is stored again in full, and one live space reached 2.6 GB in twenty-five
# snapshots that way, nearly all of it the user's own binaries carried a second time.
# Three leavings, three clocks. The trash holds what the user threw away, so it waits a month for
# them to change their mind. The other two are the machine's own: a scratch folder outlives its job
# by nothing at all, and a snapshot exists to undo an update or a large edit that went wrong, which
# is known within days. Keeping those for a month is not caution, it is a pile.
TRASH_RETENTION_DAYS = 30
SCRATCH_RETENTION_DAYS = 7
SNAPSHOT_RETENTION_DAYS = 7

# How long a bundle may stand empty before the structure check names it. Long enough that a
# starting structure laid out at setup, or a matter mapped out before anything is filed into it,
# is not reported as a fault on the day it was made; short enough that a place nobody ever used
# still surfaces.
EMPTY_BUNDLE_GRACE_DAYS = 30

def _lesbare_groesse(bytes_gesamt: float) -> str:
    for einheit in ("B", "KB", "MB", "GB"):
        if bytes_gesamt < 1024 or einheit == "GB":
            return f"{bytes_gesamt:.0f} {einheit}" if einheit == "B" else f"{bytes_gesamt:.1f} {einheit}"
        bytes_gesamt /= 1024
    return "0 B"


def _trash_days_past_retention(space: Path) -> list[Path]:
    """Whole days in the trash that are past the keeping time.

    The date is read off the folder name, never off a file timestamp: the timestamp says when
    something was last edited, which has nothing to do with when it was discarded.
    """
    root = space / TRASH_DIR
    if not root.is_dir():
        return []
    grenze = datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)
    alt = []
    for tag in sorted(p for p in root.iterdir() if p.is_dir()):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", tag.name):
            continue
        if datetime.strptime(tag.name, "%Y-%m-%d") < grenze:
            alt.append(tag)
    return alt


def _past_retention(root: Path, days: int) -> list[Path]:
    """Top-level entries under a machine folder that are older than the retention window."""
    if not root.is_dir():
        return []
    grenze = (datetime.now() - timedelta(days=days)).timestamp()
    return sorted(p for p in root.iterdir()
                  if not p.name.startswith(".") and p.stat().st_mtime < grenze)


def _sweep_retention(space: Path) -> list[str]:
    """Clear what is past its keeping time, and say what went. One rule, two folders, no question.

    This is the only place in Zanmai that deletes, and it can only ever reach material the machine
    put there itself: what someone threw away, what a run left behind, and the copies taken before a
    risky write. Nothing the user filed is in scope, and nothing here is decided by judgement at the
    moment of deleting; the folder and the age decide, which is what makes it safe to run unattended.
    """
    notes: list[str] = []

    weg = _trash_days_past_retention(space)
    if weg:
        dateien = sum(1 for tag in weg for f in tag.rglob("*") if f.is_file())
        groesse = _lesbare_groesse(sum(f.stat().st_size for tag in weg
                                       for f in tag.rglob("*") if f.is_file()))
        for tag in weg:
            shutil.rmtree(tag)
        notes.append(f"emptied {dateien} file(s) from {TRASH_DIR}/, thrown away more than "
                     f"{TRASH_RETENTION_DAYS} days ago ({groesse}).")

    liegen = _past_retention(space / SCRATCH_DIR, SCRATCH_RETENTION_DAYS)
    if liegen:
        for p in liegen:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        notes.append(f"cleared {len(liegen)} leftover(s) from {SCRATCH_DIR}/ older than "
                     f"{SCRATCH_RETENTION_DAYS} days. Scratch space is not meant to hold anything "
                     f"that long, so each of those is a run that never finished tidying up after "
                     f"itself.")

    notes.extend(_sweep_snapshots(space))

    if notes:
        _append_activity_log(space, "zanmai.py", "retention sweep: " + " ".join(notes))
    return notes


def cmd_gaps(args: argparse.Namespace) -> int:
    """What the experts wrote into the tooling log recently, and nobody read.

    A dispatched expert has no way to speak while it runs: it returns to whoever called it, once,
    at the end. `builder-gaps.md` is the one channel it can use in the meantime, and the experts use
    it without being told to. What was missing is the other half, somebody reading it: a whole day
    of entries can sit there, including one saying the expert cannot send messages at all, and
    reach the workshop only where a person happens to relay one.
    """
    space = Path(args.space).resolve()
    grenze = datetime.now() - timedelta(hours=args.hours)
    dateien = sorted((space / LOGS_DIR).glob("*/*/builder-gaps.md"))
    if not dateien:
        print(f"no {LOGS_DIR}/<year>/<month>/builder-gaps.md in this space")
        return 0
    gefunden = 0
    for datei in dateien:
        if datetime.fromtimestamp(datei.stat().st_mtime) < grenze:
            continue
        text = datei.read_text(encoding="utf-8", errors="replace")
        # Entries start at a heading. Anything under a heading whose date is inside the window is
        # new enough to matter; a file without dated headings is printed from its tail instead.
        bloecke, aktuell = [], []
        for zeile in text.splitlines():
            if zeile.startswith("## "):
                if aktuell:
                    bloecke.append(aktuell)
                aktuell = [zeile]
            elif aktuell:
                aktuell.append(zeile)
        if aktuell:
            bloecke.append(aktuell)
        for block in bloecke:
            datum = re.search(r"(\d{4}-\d{2}-\d{2})", block[0])
            if datum and datetime.strptime(datum.group(1), "%Y-%m-%d") < grenze - timedelta(days=1):
                continue
            if not datum:
                continue
            gefunden += 1
            print("\n".join(block[:12]).rstrip())
            print()
    if not gefunden:
        print(f"nothing new in builder-gaps.md in the last {args.hours} hour(s)")
    else:
        print(f"{gefunden} entry/entries from the last {args.hours} hour(s). These are the experts' "
              f"only way to report while they run; act on them or carry them where they belong.")
    return 0


def _area_shape(space: Path, ab: int = 2) -> list[str]:
    """One line per area: how many bundles sit at its top, and what they are called.

    No vocabulary and no guessing. Whether four folders are four pieces of one matter is a
    judgement about somebody's life, not a string comparison: a list of words would catch travel in
    two languages and miss cars, doctors, customers and everything else. What a machine can do is
    put the names side by side, which is the one thing nobody does while filing one folder at a
    time. The reading is left to whoever is looking at them.

    Every area, never one. The same matter often already has a home elsewhere: research about
    travel sits in knowledge while four trips sit in life, and neither list on its own shows that.
    """
    raus: list[str] = []
    for bereich in (LIFE_DIR, WORKBENCH_DIR, KNOWLEDGE_DIR, ARCHIVE_DIR):
        wurzel = space / bereich
        if not wurzel.is_dir():
            continue
        namen = sorted(p.name for p in wurzel.iterdir() if p.is_dir() and not p.name.startswith("."))
        if len(namen) < ab:
            continue
        raus.append(f"{bereich}/ holds {len(namen)} bundle{'' if len(namen) == 1 else 's'}: "
                    f"{', '.join(namen)}")
    return raus


def cmd_housekeeping(args: argparse.Namespace) -> int:
    """Sweep what is past its keeping time, then say what has drifted out of shape.

    Two different things, and the second is the reason this command is worth running by hand. The
    sweep is mechanical and needs nobody. What it cannot see is that the space slowly grew a shape
    nobody chose: one bundle per trip instead of one for travel, a bundle holding nothing but its
    own page. Neither is wrong on the day it happens, both are wrong after the fourth time, and
    nothing notices because every single step looked right.

    It reports and moves nothing. Where material goes is the user's decision.
    """
    space = Path(args.space).resolve()
    notes = _sweep_retention(space)
    if notes:
        for n in notes:
            print(f"ok: {n}")
    else:
        print(f"ok: nothing is past its keeping time ({TRASH_RETENTION_DAYS} days in the trash, "
              f"{SCRATCH_RETENTION_DAYS} for scratch space and snapshots)")

    duenn = [f"{b} holds nothing but its own page, so it is a single item that was given a folder"
             for b in _bundles_without_material(space)]
    if duenn:
        print()
        print("Worth a look, nothing was moved:")
        for b in duenn:
            print(f"  {b}")

    form = _area_shape(space)
    if form:
        print()
        print("The bundles at the top of every area, side by side. Read them across the areas, not "
              "one at a time: several bundles that are pieces of one matter, or a matter that "
              "already has a home in another area while pieces of it sit here. Say what you see "
              "and propose it; move nothing.")
        for zeile in form:
            print(f"  {zeile}")
    if not duenn and not form:
        print("ok: the shape of the space is in order")
    return 0


def _version_tuple(version: str) -> tuple[int, ...]:
    """Comparable form of a dotted version, unparseable parts count as zero."""
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _is_newer(candidate: str, current: str) -> bool:
    """True only when candidate is ahead, so a space is never offered a downgrade."""
    if not candidate:
        return False
    if not current:
        return True
    return _version_tuple(candidate) > _version_tuple(current)


def _fetch(url: str, timeout: int = 60) -> bytes:
    """Plain HTTPS GET. Stdlib only, so a space needs no extra tooling to update."""
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


def _clone_remote(space: Path) -> str:
    """The configured origin if this space is a working clone, else empty."""
    import subprocess

    if not (space / ".git").exists():
        return ""
    try:
        remotes = subprocess.run(["git", "-C", str(space), "remote"],
                                 capture_output=True, text=True, timeout=20)
        if "origin" not in remotes.stdout.split():
            return ""
        url = subprocess.run(["git", "-C", str(space), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=20)
        return url.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _remote_version_via_git(space: Path, branch: str) -> str:
    """The version the clone's own origin offers.

    A clone must be measured against the remote it came from, not against an
    address in the manifest, or a space cloned from a fork could never update.
    Fetch only moves refs, the working tree is untouched.
    """
    import subprocess

    def run(*cmd: str):
        return subprocess.run(["git", "-C", str(space), *cmd],
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


def _remote_changelog_via_git(space: Path, branch: str) -> str:
    """The origin's CHANGELOG.md, unapplied.

    A preview built before Apply (Pepper's Update workflow step 2, before step
    5) has no local file to read yet: the working tree still holds the old
    version. `fetch` already ran in `_remote_version_via_git` right before
    this is called, so the ref is current; a second cheap fetch here would
    only be needed if this were ever called on its own.
    """
    import subprocess

    shown = subprocess.run(
        ["git", "-C", str(space), "show", f"origin/{branch}:{SYSTEM_MATERIAL_DIR}/CHANGELOG.md"],
        capture_output=True, text=True, timeout=120,
    )
    return shown.stdout if shown.returncode == 0 else ""


def _remote_changelog_via_https(source: str, branch: str) -> str:
    """The origin's CHANGELOG.md for a non-clone space, fetched over HTTPS, unapplied."""
    try:
        raw = _fetch(
            f"https://raw.githubusercontent.com/{source.strip('/')}/{branch}/{SYSTEM_MATERIAL_DIR}/CHANGELOG.md"
        )
        return raw.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


def _upgrade_via_git(space: Path, branch: str) -> tuple[bool, str]:
    """Fast-forward a cloned space, so it stays a clean clone.

    Copying files into a clone would leave it looking locally modified and a
    later `git pull` by hand would refuse, so a clone is upgraded through git.
    """
    import subprocess

    def run(*cmd: str):
        return subprocess.run(["git", "-C", str(space), *cmd],
                              capture_output=True, text=True, timeout=180)

    dirty = run("status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        return False, ("the space has local edits to distribution files, so a clean "
                       "fast-forward is not possible; review them first")
    fetched = run("fetch", "origin")
    if fetched.returncode != 0:
        return False, (fetched.stderr.strip() or "fetch failed")
    merged = run("merge", "--ff-only", f"origin/{branch}")
    if merged.returncode != 0:
        return False, (merged.stderr.strip() or "fast-forward not possible")
    return True, ""


def _checkout_version_via_git(space: Path, version: str) -> tuple[bool, str]:
    """Put a clone's distribution files on a published tag, in either direction.

    The branch is left where it is and only the distribution paths are checked out, so `git status`
    afterwards says the truth: this space is not on its branch's head any more. A `reset --hard`
    would hide that, and hiding it is how somebody later wonders why a pull brings nothing.
    """
    import subprocess

    def run(*cmd: str):
        return subprocess.run(["git", "-C", str(space), *cmd],
                              capture_output=True, text=True, timeout=180)

    if run("fetch", "--tags", "origin").returncode != 0:
        return False, "could not fetch tags from origin"
    tag = f"v{version}"
    if run("rev-parse", "--verify", f"{tag}^{{commit}}").returncode != 0:
        return False, f"the source has no tag {tag}"
    holen = run("checkout", tag, "--", "CLAUDE.md", SYSTEM_MATERIAL_DIR)
    if holen.returncode != 0:
        return False, (holen.stderr.strip() or f"could not take the files from {tag}")
    return True, ""


def _refresh_host_config(space: Path, quiet: bool = False) -> None:
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
    script = space / SYSTEM_MATERIAL_DIR / "scripts" / "zanmai.py"
    if not script.is_file():
        print(f"warning: cannot refresh host config, no script at {script}", file=sys.stderr)
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "setup", "update", str(space)],
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


def _record_host_config_version(space: Path, version: str) -> None:
    """Remember which distribution version the host config was built for.

    Machine-local on purpose: the session-start check uses it to notice a
    version that arrived some other way, for example a manual `git pull`.
    """
    marker = space / RUNTIME_DIR / "host-config-version"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(version + "\n", encoding="utf-8")
    except OSError:
        pass


def _update_check_allowed(space: Path) -> bool:
    """May this space ask the outside whether a newer version exists?

    Two places say no, and either one is enough. `zanmai/user.md` is the user's own file and no
    update touches it, so a decision written there survives; the manifest is where the shipped
    documentation has always pointed, and a copy handed on to somebody else carries it. Both spell
    it the same way, `update_check: false`.

    Default is on. Absent means nobody has decided, and the daily question is the whole reason a
    space ever hears that a fix exists.
    """
    def aus(text: str) -> bool:
        return re.search(r"^\s*update_check:\s*(?:\"|')?false(?:\"|')?\s*$", text, re.M) is not None

    for datei in (space / SYSTEM_DIR / "user.md", space / SYSTEM_MATERIAL_DIR / "manifest.yaml"):
        try:
            if aus(datei.read_text(encoding="utf-8")):
                return False
        except OSError:
            continue
    return True


def _quiet_update_probe(space: Path) -> str:
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

    Switched off entirely where the user says so, and that is checked before anything reaches the
    network. The switch was documented in two shipped files for months while no code read it, so a
    space set to stay off the network asked anyway, every day, and the only person who could have
    noticed was the one who had been told it was off.
    """
    if not _update_check_allowed(space):
        return ""
    cache = space / RUNTIME_DIR / "update-check.json"
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
                return known if _is_newer(known, _distribution_version(space)) else ""
        except ValueError:
            pass

    manifest = space / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    source = _manifest_scalar(manifest, "update_source") if manifest.exists() else ""
    default_branch = _manifest_scalar(manifest, "update_branch") or "main" if manifest.exists() else "main"
    branch = _update_channel(space) or default_branch
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
            if _is_newer(remote, _distribution_version(space)):
                available = remote
        except Exception:  # noqa: BLE001
            # no network: keep whatever the last successful probe found
            try:
                state = json.loads(cache.read_text(encoding="utf-8"))
                previous = state.get("available", "")
                available = previous if _is_newer(previous, _distribution_version(space)) else ""
            except (json.JSONDecodeError, ValueError, OSError):
                available = ""

    state.update({"checked": now.isoformat(timespec="seconds"), "available": available})
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return available


def _unattended_log_to_report(space: Path) -> Path | None:
    """The last session's log, when nobody was in the chat for it and it has not been
    named yet. Derived from the log the run itself wrote, so there is no second marker to
    keep in step, and remembered by name so a resume or a compaction does not say it twice.
    """
    logs_dir = space / LOGS_DIR
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
    state_file = space / RUNTIME_DIR / "session-state.json"
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


def _update_offer_due(space: Path) -> bool:
    """True once a day. Mentioning an available version is worth one line a day, not one
    per hook run, and the hook runs again on every resume and compaction."""
    cache = space / RUNTIME_DIR / "update-check.json"
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


def _housekeeping_due(space: Path) -> bool:
    """True once a week: has the shape report (thin bundles, area layout) not been surfaced
    in the last seven days, or never.

    Modelled on `_update_offer_due`, the same reason applies: the hook runs again on every
    resume and every compaction, so "once per session" is really several times an hour. The
    retention sweep runs every time regardless, because it is cheap and self-contained; the
    shape report is a paragraph the user has to read, so it earns one slot a week rather than
    one per hook run. Marks itself due immediately on a fresh space, so a week-old space that
    was never checked still gets a first look rather than waiting out the window.
    """
    cache = space / RUNTIME_DIR / "housekeeping-check.json"
    now = datetime.now(timezone.utc)
    try:
        state = json.loads(cache.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        state = {}
    checked = str(state.get("checked", ""))
    if checked:
        try:
            if now - datetime.fromisoformat(checked) < timedelta(days=7):
                return False
        except ValueError:
            pass
    state["checked"] = now.isoformat(timespec="seconds")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
    return True


def _record_update_history(space: Path, from_version: str, to_version: str, result: str) -> None:
    """One line per applied update, written by the script that applied it.

    It used to be written by the specialist who ran the update, which means it exists only when
    the update went through that specialist. Every other route left no trace at all: no line, no
    origin, and afterwards no way to tell from inside the space what had arrived or where from.
    A trail that depends on who did the work is not a trail, so the step that knows the versions
    writes it.

    The file is user-immune, so it survives the update it describes; a missing one is created
    rather than treated as an error, because a space that never updated has nothing to carry
    forward.
    """
    datei = space / SYSTEM_DIR / "update-history.md"
    try:
        if not datei.is_file():
            datei.parent.mkdir(parents=True, exist_ok=True)
            datei.write_text("# Update history\n\nAudit trail of update, restore and delete "
                             "operations.\n\n| Date | Operation | From | To | Result |\n"
                             "|------|-----------|------|-----|--------|\n", encoding="utf-8")
        zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M")
        with datei.open("a", encoding="utf-8") as f:
            f.write(f"| {zeitpunkt} | update | {from_version or '?'} | {to_version or '?'} | "
                    f"{result} |\n")
    except OSError:
        # An update that worked is not undone by a line that could not be written.
        pass


def _hand_off_to_new_script(space: Path, from_version: str, to_version: str, *,
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
    script = space / SYSTEM_MATERIAL_DIR / "scripts" / "zanmai.py"
    if not script.is_file():
        print(f"error: the new version left no script at {script}, nothing was verified. "
              "Run 'setup update' and 'setup validate' by hand.", file=sys.stderr)
        return 1
    cmd = [sys.executable, str(script), "setup", "post-upgrade", str(space),
           "--from", from_version, "--to", to_version]
    if origin:
        cmd += ["--origin", origin]
    if replaced is not None:
        cmd += ["--replaced", str(replaced)]
    if withdrawn is not None:
        cmd += ["--withdrawn", str(withdrawn)]
    # Everything this side printed goes out before the new script starts writing. Without the flush
    # the two streams interleave by buffer rather than by time, and the run reads as if the files
    # were replaced before the snapshot was taken. Seen exactly that way in a live update: "updated
    # to 0.6.0, 196 files replaced" stood three lines above "snapshot ok". The snapshot was there
    # and was first; the output said otherwise, and for the one operation whose whole promise is
    # "the copy exists before anything is overwritten", the order on screen is the promise.
    sys.stdout.flush()
    sys.stderr.flush()
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
    space = Path(args.space_root).resolve()
    to_version = args.to_version or _distribution_version(space)

    # A refresh that cannot write, an unreadable permission, a full disk: whatever it
    # is, it must come out as a sentence and leave the marker alone. A traceback here
    # would end the upgrade in the one state this whole command exists to prevent,
    # unexplained and half-applied.
    try:
        refreshed = cmd_setup_update(argparse.Namespace(space_root=str(space)))
    except OSError as exc:
        print(f"error: the new files are in place but the host refresh could not write ({exc})",
              file=sys.stderr)
        refreshed = 1
    if refreshed != 0:
        print(f"error: the new files are in place but the host refresh failed. The recorded "
              f"version stays at {args.from_version or 'the previous one'}, so the next session "
              "repairs it. Run 'setup update' by hand to do it now.", file=sys.stderr)
        return 1

    problems = _verify_host_config(space)
    if problems:
        print("error: the new files are in place but the host config is incomplete:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"the recorded version stays at {args.from_version or 'the previous one'}, so the "
              "next session repairs this instead of considering it done", file=sys.stderr)
        return 1

    _record_host_config_version(space, to_version)
    _record_update_history(space, args.from_version, to_version,
                           f"ok, from {args.origin}" if args.origin else "ok")

    detail = ""
    if args.replaced is not None:
        detail = f" ({args.replaced} files replaced"
        detail += f", {args.withdrawn} withdrawn)" if args.withdrawn else ")"
    elif args.origin:
        detail = f" from {args.origin}"
    print(f"ok: updated to {to_version}{detail}, host config verified")
    print("your notes, settings and extensions were not touched")
    return 0


def _update_channel(space: Path) -> str:
    """The branch `zanmai/user.md` names to track, or "" for the manifest's default.

    Update-immune by construction: `user.md` is never touched by an update, so a
    channel choice survives the very upgrades it steers. "release" and "" both
    mean "no override, follow the manifest's `update_branch`" (currently `main`).
    """
    user_md = space / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return ""
    try:
        fm, _order, _body = _split_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return ""
    channel = str(fm.get("update_channel") or "").strip()
    return "" if channel in ("", "release") else channel


def _set_update_channel(space: Path, channel: str) -> None:
    """Persist the channel choice to `zanmai/user.md`. "release" clears the override."""
    user_md = space / SYSTEM_DIR / "user.md"
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


def _apply_distribution_tree(space: Path, tree: Path, manifest: Path) -> tuple[int, int] | None:
    """Copy an unpacked distribution tree over this space's distribution files.

    Shared by both routes that arrive with a tree: the published archive over HTTPS and a source
    named by hand. One function rather than two copies, because the containment check below is the
    part that must not drift. The paths come out of a manifest that just arrived from somewhere
    else, so they are input and not fact, and a single `../` would write outside the space.

    Returns (written, removed), or None when nothing was applied; the reason is printed.
    """
    import shutil

    new_manifest = tree / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    if not new_manifest.exists():
        print("error: the new version has no manifest, nothing applied", file=sys.stderr)
        return None

    new_paths = _manifest_distribution_paths(new_manifest)
    old_paths = _manifest_distribution_paths(manifest)

    # Resolve BOTH sides: resolving only the candidate refuses every update on macOS, where the
    # temporary directory is itself a symlink. A guard that then blocks every legitimate update has
    # not made anything safer, it has traded one failure for a worse one.
    space_real = space.resolve()

    def contained(rel: str) -> Path | None:
        if rel.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:", rel):
            return None
        candidate = (space_real / rel).resolve()
        if candidate == space_real or space_real not in candidate.parents:
            return None
        return candidate

    refused = [rel for rel in set(new_paths) | set(old_paths) if contained(rel) is None]
    if refused:
        print("error: the manifest lists paths outside the space, nothing applied:",
              file=sys.stderr)
        for rel in sorted(refused)[:10]:
            print(f"  {rel}", file=sys.stderr)
        return None

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
    return written, removed


def _upgrade_from_named_source(space: Path, manifest: Path, source: str, *,
                               check_only: bool = False) -> int:
    """Update from a folder, an archive or a URL the caller names, instead of from the release.

    Two cases need this and neither is ordinary: a version that is not published yet has to be
    tried in a working space before it goes out, and a fix sometimes has to arrive before there is
    a release to carry it. Both used to end in files copied in by hand, which proves the copy
    worked and nothing about the update.

    A named source is a decision, so a snapshot is taken every time, without asking whether the
    version on the other side is newer. It is the one route where the version carries no promise.
    """
    import tempfile

    local = _distribution_version(space)
    with tempfile.TemporaryDirectory() as work:
        work_path = Path(work)
        given = Path(source).expanduser()
        if source.startswith(("http://", "https://")):
            try:
                archive = _fetch(source, timeout=180)
            except Exception as exc:  # noqa: BLE001
                print(f"error: could not download from {source} ({exc})", file=sys.stderr)
                return 1
            tree = _unpack_release(archive, work_path)
        elif given.is_dir():
            tree = given.resolve()
        elif given.is_file():
            try:
                tree = _unpack_release(given.read_bytes(), work_path)
            except Exception as exc:  # noqa: BLE001
                print(f"error: could not unpack {given} ({exc})", file=sys.stderr)
                return 1
        else:
            print(f"error: no such source: {source}", file=sys.stderr)
            return 1

        remote = _distribution_version(tree)
        if not remote:
            print(f"error: {source} carries no {SYSTEM_MATERIAL_DIR}/VERSION, nothing applied",
                  file=sys.stderr)
            return 1

        print(f"going to {local} -> {remote} (from {source})")
        # A named source can be read without being applied, so `--check` answers here the way it
        # answers for the release. Refusing it turned the ordinary first step of the update
        # workflow into a special case, and a workflow with a hole in step one gets improvised.
        if check_only:
            return 0
        snap = argparse.Namespace(space=str(space), reason=f"before going to {remote} from {source}",
                                  agent="zanmai.py")
        try:
            cmd_snapshot_create(snap)
        except Exception as fehler:  # noqa: BLE001
            print(f"error: no snapshot could be taken ({fehler}), so nothing was changed.",
                  file=sys.stderr)
            return 1

        applied = _apply_distribution_tree(space, tree, manifest)

    if applied is None:
        return 1
    written, removed = applied
    return _hand_off_to_new_script(space, local, remote, origin=source,
                                   replaced=written, withdrawn=removed)


def cmd_setup_upgrade(args: argparse.Namespace) -> int:
    """Replace the distribution files with the newest published version.

    Deliberately independent of how the space arrived: an unpacked archive
    updates exactly like a clone. A clone is fast-forwarded through git so it
    stays a clean clone; anything else has the new files fetched over HTTPS.
    Only paths the manifest calls distribution are touched.
    """
    space = Path(args.space_root).resolve()
    manifest = space / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    if not manifest.exists():
        print(f"error: no Zanmai system folder at {space}", file=sys.stderr)
        return 1

    # A source named by hand short-circuits every question about branches and published versions.
    # It runs the same unpack and the same copy as the release route, so what a test measures here
    # is the update itself and not a second way of doing it.
    named = (getattr(args, "from_source", None) or "").strip()
    if named:
        return _upgrade_from_named_source(space, manifest, named, check_only=args.check)

    requested_channel = getattr(args, "channel", None)
    if requested_channel:
        _set_update_channel(space, requested_channel)

    local = _distribution_version(space)
    channel = _update_channel(space)
    branch = channel or _manifest_scalar(manifest, "update_branch") or "main"
    is_clone = bool(_clone_remote(space))

    # A named version is a decision, so it is taken as one: forwards or backwards, without asking
    # whether it is newer. The automatic offer still never goes backwards; this is the deliberate
    # way, and it exists because there was none. A release that turns out broken could only be
    # undone by replacing files by hand in a live space, which is the one thing E11 forbids.
    gewuenscht = (getattr(args, "to", None) or "").strip().lstrip("v")
    ziel_ref = f"refs/tags/v{gewuenscht}" if gewuenscht else f"refs/heads/{branch}"

    # Named per branch, because a clone asks its own git remote and every other space
    # asks the manifest's source. It used to be read from the manifest either way,
    # which for a clone read a name that was never assigned: the command crashed with
    # an interpreter error the moment an update genuinely existed, which is the one
    # moment it is ever run. A clone that was up to date returned before reaching the
    # line, so the fault sat there through several releases and surfaced as a
    # traceback in front of the user rather than a version to say yes to.
    if gewuenscht:
        source = _manifest_scalar(manifest, "update_source")
        origin = (_clone_remote(space) if is_clone else source) or "the update source"
        remote = gewuenscht
        if not is_clone and not source:
            print("error: the manifest names no update source", file=sys.stderr)
            return 1
        base = (source or "").strip("/")
    elif is_clone:
        origin = _clone_remote(space) or "the repository this space was cloned from"
        remote = _remote_version_via_git(space, branch)
        if not remote:
            print("error: could not read a version from this space's own origin", file=sys.stderr)
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
    # `--force` applies the files again even where the version says there is nothing to do. Two
    # cases need it and neither is exotic: a release re-cut under the same number carries different
    # content and is invisible to a comparison of numbers, and an update that broke halfway leaves a
    # space whose version says it is current while its files are not. Without this the only way out
    # was replacing files by hand, which is the one thing the update path exists to prevent.
    erzwingen = bool(getattr(args, "force", False))
    if not gewuenscht and not _is_newer(remote, local) and not erzwingen:
        print(f"ok: already on the current version ({local}{channel_note}). "
              f"Use --force to fetch and apply it again anyway.")
        return 0
    if gewuenscht and remote == local and not erzwingen:
        print(f"ok: already on {local}. Use --force to apply it again anyway.")
        return 0
    if erzwingen and not _is_newer(remote, local):
        print(f"applying {remote} again over {local} (--force){channel_note}")

    richtung = "going to" if gewuenscht else "update available:"
    print(f"{richtung} {local} -> {remote} (from {origin}{channel_note})")
    if gewuenscht and not _is_newer(remote, local):
        print("    this goes backwards. A snapshot is taken first, and the version you are on now "
              "can be reached the same way.")
    if args.check:
        if getattr(args, "changelog", False):
            changelog = (_remote_changelog_via_git(space, branch) if is_clone
                         else _remote_changelog_via_https(source, branch))
            if changelog:
                print("--- remote CHANGELOG.md ---")
                print(changelog)
            else:
                print("warning: could not read the remote CHANGELOG.md", file=sys.stderr)
        return 0

    # a clone is upgraded through git, so it stays a clean clone and a manual
    # `git pull` keeps working afterwards
    # Before anything is replaced, and only where a version was named: that is the case where the
    # space is deliberately moved off a state somebody may want back.
    if gewuenscht:
        schnapp = argparse.Namespace(space=str(space), reason=f"before going to {remote}",
                                     agent="zanmai.py")
        try:
            cmd_snapshot_create(schnapp)
        except Exception as fehler:  # noqa: BLE001
            print(f"error: no snapshot could be taken ({fehler}), so nothing was changed.",
                  file=sys.stderr)
            return 1

    if is_clone:
        ok, problem = (_checkout_version_via_git(space, remote) if gewuenscht
                       else _upgrade_via_git(space, branch))
        if ok:
            applied = _distribution_version(space)
            return _hand_off_to_new_script(space, local, applied, origin="the repository this space was cloned from")
        print(f"error: {problem}", file=sys.stderr)
        return 1

    import tempfile

    with tempfile.TemporaryDirectory() as work:
        try:
            archive = _fetch(f"https://codeload.github.com/{base}/tar.gz/{ziel_ref}", timeout=180)
        except Exception as exc:  # noqa: BLE001
            print(f"error: could not download the new version ({exc})", file=sys.stderr)
            return 1

        tree = _unpack_release(archive, Path(work))
        applied = _apply_distribution_tree(space, tree, manifest)

    if applied is None:
        return 1
    written, removed = applied
    return _hand_off_to_new_script(space, local, remote, replaced=written, withdrawn=removed)


def _bundles_without_material(space: Path) -> list[str]:
    """Top-level bundles in the user's areas whose whole content is their own page.

    The two files a bundle always has are its truth file, named after the folder, and the index.
    A folder with those and nothing else was made for a single item: one trip, one reminder, one
    appliance. It is not wrong material, it is the wrong shape, and the shape is what makes it
    invisible later, because a search for the wider matter never reaches it.

    Only the top level of an area, and only where the truth file is actually there: a folder deeper
    down is a section of something bigger, and a folder without a truth file is somebody's own
    filing rather than a bundle.

    A bundle made in the last few weeks is left out, because for that span the empty case has a
    second reading: setup creates the areas the user named as places to file into, and so does
    anyone who lays out a matter before filling it. Reporting those the same day would call the
    intended state a fault. What the window does not do is forgive them forever: a place nothing
    was ever put into is worth naming once it has had a month to be used.
    """
    raus: list[str] = []
    grenze = (datetime.now() - timedelta(days=EMPTY_BUNDLE_GRACE_DAYS)).timestamp()
    for bereich in (LIFE_DIR, WORKBENCH_DIR, KNOWLEDGE_DIR):
        wurzel = space / bereich
        if not wurzel.is_dir():
            continue
        for ordner in sorted(p for p in wurzel.iterdir() if p.is_dir()):
            wahrheit = ordner / f"{ordner.name}.md"
            if not wahrheit.is_file():
                continue
            eigen = [f for f in ordner.rglob("*")
                     if f.is_file() and not f.name.startswith(".")
                     and f != wahrheit and f.name.lower() != "index.md"]
            if not eigen and wahrheit.stat().st_mtime < grenze:
                raus.append(f"{bereich}/{ordner.name}")
    return raus


def cmd_setup_validate(args: argparse.Namespace) -> int:
    space = Path(args.space_root).resolve()
    fails: list[str] = []
    user_md = space / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        fails.append("missing zanmai/user.md, run 'setup init' first")
    manifest_path = space / SYSTEM_MATERIAL_DIR / "manifest.yaml"
    if not manifest_path.exists():
        fails.append("missing zanmai/system/manifest.yaml")
    else:
        for rel in _manifest_distribution_paths(manifest_path):
            if not (space / rel).exists():
                fails.append(f"missing distribution file: {rel}")
    for rel in _required_folders(space):
        if not (space / rel).is_dir():
            fails.append(f"missing required folder: {rel}. Run 'setup update' to create it.")
    # A command in a standing rule is read back as an instruction for as long as the space exists,
    # and no update ever touches these files. The guard stops a wrong one from being written; this
    # finds the ones that were written before the guard existed, or that a rename made wrong after
    # the fact. Reported, never corrected: the sentence around the command is the user's.
    for rel in [USER_FILE, f"{MEMORY_DIR}/general.md"]:
        datei = space / rel
        if not datei.is_file():
            continue
        try:
            inhalt = datei.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for befund in _stale_calls(inhalt):
            fails.append(f"{rel}: {befund}. A rule here runs every session; correct the line by "
                         f"hand or ask the command with `--help` and write what it answers.")

    # A file the distribution once shipped and no longer lists is only removed by an update when
    # the version being left still named it. Anything dropped earlier than that stays for ever, and
    # a leftover under the system folder reads like part of the product: a retired template still
    # carrying a kind that no longer exists is indistinguishable from a current one. Reported, not
    # removed, because this is a check and the user decides what goes.
    if manifest_path.exists():
        gelistet = set(_manifest_distribution_paths(manifest_path))
        system_ordner = space / SYSTEM_MATERIAL_DIR
        if system_ordner.is_dir():
            fremd = sorted(p.relative_to(space).as_posix() for p in system_ordner.rglob("*")
                           if p.is_file() and p.relative_to(space).as_posix() not in gelistet
                           and p.suffix not in (".pyc",) and "__pycache__" not in p.parts)
            for rel in fremd[:10]:
                fails.append(f"not in the manifest and still shipped-looking: {rel}. "
                             f"A leftover from an earlier version; move it out or add it.")
            if len(fremd) > 10:
                fails.append(f"... and {len(fremd) - 10} more file(s) under {SYSTEM_MATERIAL_DIR}/ "
                             f"that the manifest does not list")

    for rel in ["INDEX.md", f"{MEMORY_DIR}/general.md", ACTIVITY_LOG_FILE]:
        if not (space / rel).is_file():
            fails.append(f"missing generated file: {rel}")
    # Everything the distribution ships and the host must carry: hooks wired, expert
    # and skill adapters present. Same function the upgrade and the session start use,
    # so what passes here is what passes there.
    for problem in _verify_host_config(space):
        fails.append(f"{problem}. Run 'setup update' to rebuild the host config.")
    # Adapters must also not be left over: no dangling legacy symlink, and nothing
    # for an expert an update dropped from the roster.
    agents_dir = space / ".claude" / "agents"
    if agents_dir.is_dir():
        roster = set(_AGENT_NAMES)
        for entry in agents_dir.glob("*.md"):
            if entry.is_symlink() and not entry.exists():
                fails.append(f"dangling agent adapter: {entry.relative_to(space)}")
                continue
            try:
                ours = entry.is_file() and f"{SYSTEM_MATERIAL_DIR}/experts/" in entry.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                ours = False
            if ours and entry.stem not in roster:
                fails.append(f"stale agent adapter (not in roster): {entry.relative_to(space)}")
    # A synced folder is a normal home for a space, so this is a note rather than a
    # failure. What it reports is the part that is genuinely wrong to copy.
    notes: list[str] = []
    notes.extend(_memory_size_report(space))
    host = _detect_sync_host(space)
    if host:
        present = [rel for rel in MACHINE_LOCAL_PATHS + BULKY_PATHS if (space / rel).exists()]
        how = next((h for name, h in SYNC_HOSTS if name == host), "")
        notes.append(f"this space sits under {host}, which is a fine place for it")
        if present:
            notes.append("these three are worth leaving out of the copy: " + ", ".join(present))
            notes.append(f"  {host}: {how}")
            notes.append("  runtime/ and temp/ describe this machine only, and the history holds "
                         "jump-back points that exist for a few days, not a backup worth carrying")
            notes.append("  it is your call, nothing here depends on it")
        conflicts = sorted(
            str(f.relative_to(space))
            for f in space.glob("**/*")
            if f.is_file() and any(mark in f.name.lower() for mark in
                                   ("conflicted copy", "conflict)", "-konflikt", "in konflikt"))
        )
        if conflicts:
            fails.append(
                f"{len(conflicts)} sync conflict copy/copies in the space, which break the rule that a "
                f"fact exists once: {', '.join(conflicts[:5])}"
                + (" …" if len(conflicts) > 5 else "")
            )

    # A bundle is the broad matter, never the single item: travel is a bundle and one trip is a note
    # in it. That rule was prose in the folder documentation and in the filing expert's contract,
    # and nothing measured it, so a space filled up with one bundle per trip and one per reminder.
    # What is measurable without any judgement is the empty case: a folder whose whole content is
    # its own truth file and an index holds nothing that needed a folder. It is reported, never
    # changed: where the material goes is the user's call, and a note is one command away.
    duenn = _bundles_without_material(space)
    if duenn:
        fails.append(
            f"{len(duenn)} bundle(s) hold nothing but their own page: {', '.join(duenn[:5])}"
            + (" …" if len(duenn) > 5 else "")
            + ". A bundle is the broad matter, not the single item. Each of these belongs as a note "
              "inside a wider bundle; `bundle add-file` moves it there."
        )

    stray = _unexpected_root_entries(space)
    if stray:
        fails.append(
            f"{len(stray)} entr(y/ies) at the space root outside the folder architecture: "
            f"{', '.join(stray[:5])}"
            + (" …" if len(stray) > 5 else "")
            + ". Nothing writes there on its own, this got created outside a Zanmai session, "
              "move its contents into the right bundle and remove it."
        )

    if fails:
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"ok: space at {space} validates")
    for note in notes:
        print(f"    {note}")
    return 0


# Structural changes to an existing space, run by the script and never by a model. A run that moves
# a few thousand files by hand costs a session and gets it subtly wrong; a function does it in a
# second and can be checked. Each step is named, runs at most once per space, and is recorded in
# `zanmai/memory/.migrations` so a repeat update is a no-op. Steps only ever move and rename; nothing
# here deletes, so a step that turns out wrong is undone from the snapshot the upgrade took first.
MIGRATIONS_FILE = f"{MEMORY_DIR}/.migrations"
_RE_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _migrations_done(space: Path) -> dict[str, int]:
    """Which structural step this space has had, and at which revision of it.

    A line is `name` or `name@revision`; a line without one is revision 1, which is what every
    space written before revisions existed carries. The highest revision seen wins, so a file that
    was appended to over several updates reads correctly no matter what order the lines are in.
    """
    datei = space / MIGRATIONS_FILE
    if not datei.is_file():
        return {}
    stand: dict[str, int] = {}
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        eintrag = zeile.strip()
        if not eintrag:
            continue
        name, _, roh = eintrag.partition("@")
        try:
            rev = int(roh) if roh else 1
        except ValueError:
            rev = 1
        stand[name] = max(stand.get(name, 0), rev)
    return stand


def _migration_record(space: Path, name: str, revision: int = 1) -> None:
    datei = space / MIGRATIONS_FILE
    datei.parent.mkdir(parents=True, exist_ok=True)
    with datei.open("a", encoding="utf-8") as f:
        f.write(f"{name}@{revision}\n")


def _holds_nothing(folder: Path) -> bool:
    """Does this folder hold anything anybody wrote, at any depth.

    The shallow version of this asked only about the first level and called a folder occupied as
    soon as it held any subfolder at all, empty or not. That mattered on the one day it was wrong:
    a rename found four target folders that contained nothing but the empty shells of a previous
    layout, treated each as a name already taken, and would have parked the arriving material
    beside it under a counter. Four archives would have been split in two, and every path in the
    search index would have pointed at the half that stayed empty.
    """
    try:
        for eintrag in folder.iterdir():
            if eintrag.is_dir():
                if not _holds_nothing(eintrag):
                    return False
            elif not eintrag.name.startswith("."):
                return False
    except OSError:
        return False
    return True


def _drop_if_only_metadata(folder: Path) -> None:
    """A folder holding nothing but hidden OS metadata and empty shells is empty, and goes.

    The two ways of not doing this both leave something behind. Carrying the metadata along gives
    the file a year it does not have and creates a visible folder whose only content is junk;
    leaving it where it is keeps the old layout standing as an empty shell. Nothing anybody wrote
    is ever touched: a single file at any depth stops this.
    """
    if not folder.is_dir() or not _holds_nothing(folder):
        return
    try:
        for eintrag in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if eintrag.is_dir():
                eintrag.rmdir()
            else:
                eintrag.unlink()
        folder.rmdir()
    except OSError:
        pass


def _migrate_journal_to_one_layer(space: Path) -> list[str]:
    """Four journal layers, each entry its own bundle, become one entry per day under its year.

    `journal/daily/2026/2026-08-22/2026-08-22.md` becomes `journal/2026/2026-08-22.md`. Anything
    else that sat in the day's bundle moves next to it and keeps its name. Week, month and year
    notes are not thrown away: they carry text the user may have written themselves, so they move
    to `journal/<year>/` under their own names and simply stop being written to.
    """
    getan: list[str] = []
    for schicht in ("daily", "weekly", "monthly", "yearly"):
        wurzel = space / JOURNAL_DIR / schicht
        if not wurzel.is_dir():
            continue
        for eintrag in sorted(wurzel.rglob("*")):
            # Hidden files are the operating system's, not the journal's: they carry no date, so
            # they would land in a folder named for the year they do not have.
            if not eintrag.is_file() or eintrag.name.startswith("."):
                continue
            name = eintrag.name
            teile = eintrag.relative_to(wurzel).parts
            tagesordner = teile[-2] if len(teile) > 1 else ""
            if _RE_ISO_DATE.fullmatch(tagesordner) and not name.startswith(tagesordner):
                name = f"{tagesordner}-{name}"
            jahr = next((teil for teil in teile if len(teil) == 4 and teil.isdigit()), None) or name[:4]
            if not (len(jahr) == 4 and jahr.isdigit()):
                jahr = "undated"
            ziel = space / JOURNAL_DIR / jahr / name
            if ziel.exists() and ziel.read_bytes() == eintrag.read_bytes():
                eintrag.unlink()
                continue
            n = 1
            while ziel.exists():
                ziel = ziel.with_name(f"{ziel.stem}-{n}{ziel.suffix}")
                n += 1
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(eintrag), str(ziel))
            getan.append(f"{eintrag.relative_to(space).as_posix()} -> {ziel.relative_to(space).as_posix()}")
        for ordner in sorted((d for d in wurzel.rglob("*") if d.is_dir()),
                             key=lambda d: len(d.parts), reverse=True):
            _drop_if_only_metadata(ordner)
        _drop_if_only_metadata(wurzel)
    return getan


# Rooms that were merged or renamed, source first. Six became four, so two of the targets take
# more than one source and the order below is the order they are folded in.
_ROOM_MOVES = (
    ("import", INBOX_DIR),
    ("doing", WORKBENCH_DIR),
    ("focus", LIFE_DIR),
    ("habits", LIFE_DIR),
    ("trusted", LIFE_DIR),
    ("records", ARCHIVE_DIR),
)
# The frontmatter kind moves with the room it named.
_KIND_MOVES = {"focus": "life", "habit": "life", "doing": "workbench", "record": "archive"}


def _move_areas(space: Path, moves: tuple[tuple[str, str], ...],
                kinds: dict[str, str]) -> list[str]:
    """Eleven areas become eight: what was scattered over focus, habits and trusted is one life,
    and what was kept in records is the same cupboard as the archive.

    Nothing is thrown away and no file is ever written over. Folders of the same name are joined,
    files of the same name are not: a folder is a container, and two containers with one name hold
    one thing between them, while two files with one name are two files. The first version counted
    folders as well, and it split an archive in two because the same cupboard existed under both
    the old name and the new one. The user was left with `vertraege` and `vertraege-1` holding the
    same bundles, and every path in the search index pointing at one of the halves.

    The `kind:` line moves with the room, because a file whose kind names a room that no longer
    exists is invisible to everything that looks by kind.
    """
    getan: list[str] = []

    def hinein(quelle: Path, ziel_ordner: Path) -> None:
        """Move the contents of one folder into another, joining folders, never overwriting."""
        ziel_ordner.mkdir(parents=True, exist_ok=True)
        for eintrag in sorted(quelle.iterdir()):
            if eintrag.name.startswith("."):
                continue
            ziel = ziel_ordner / eintrag.name
            if eintrag.is_dir() and ziel.is_dir():
                hinein(eintrag, ziel)
                _drop_if_only_metadata(eintrag)
                continue
            n = 1
            while ziel.exists():
                ziel = (ziel_ordner / f"{eintrag.stem}-{n}{eintrag.suffix}" if eintrag.is_file()
                        else ziel_ordner / f"{eintrag.name}-{n}")
                n += 1
            shutil.move(str(eintrag), str(ziel))
            getan.append(f"{eintrag.relative_to(space).as_posix()} -> "
                         f"{ziel.relative_to(space).as_posix()}")

    for alt_name, ziel_name in moves:
        quelle = space / alt_name
        if not quelle.is_dir() or alt_name == ziel_name:
            continue
        # An empty shell on the other side is the one setup created, not a name already taken, and
        # it goes before anything arrives. Left standing it would push the real contents aside.
        ziel_wurzel = space / ziel_name
        if ziel_wurzel.is_dir():
            for vorhanden in list(ziel_wurzel.iterdir()):
                if vorhanden.is_dir():
                    _drop_if_only_metadata(vorhanden)
        hinein(quelle, ziel_wurzel)
        _drop_if_only_metadata(quelle)

    # The kind line, in everything the user owns. A file under the system folder is the
    # distribution's and is replaced by the update itself.
    for datei in sorted(space.rglob("*.md")):
        rel = datei.relative_to(space).as_posix()
        if rel.startswith((f"{SYSTEM_DIR}/system/", f"{HISTORY_DIR}/", f"{TRASH_DIR}/")):
            continue
        try:
            text = datei.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        neu_text = re.sub(rf"(?m)^kind: *({'|'.join(re.escape(k) for k in kinds)}) *$",
                          lambda m: f"kind: {kinds[m.group(1)]}", text) if kinds else text
        if neu_text != text:
            datei.write_text(neu_text, encoding="utf-8")
            getan.append(f"kind rewritten in {rel}")

    # Paths the machine keeps for itself: the routing table the user built and the open-work pages.
    for pfad in [space / SYSTEM_DIR / "routing.json"] + sorted((space / SYSTEM_DIR / "open").rglob("*")):
        if not pfad.is_file() or pfad.suffix not in (".json", ".md"):
            continue
        try:
            text = pfad.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        neu_text = text
        for alt_name, ziel_name in moves:
            neu_text = re.sub(rf'(?<=["\'`\s(]){re.escape(alt_name)}/', f"{ziel_name}/", neu_text)
        # The journal lost its four layers in the step before this one, and a routing rule written
        # while they existed still sends material to `journal/daily`, which no longer exists. A
        # rule that points nowhere is worse than none: the import runs, reports a target, and the
        # material lands where nobody looks.
        neu_text = re.sub(r'(?<=["\'`\s(])journal/(daily|weekly|monthly|yearly)\b',
                          "journal", neu_text)
        if neu_text != text:
            pfad.write_text(neu_text, encoding="utf-8")
            getan.append(f"paths rewritten in {pfad.relative_to(space).as_posix()}")

    # The master index is written by the machine, and its headings are the old rooms. Replacing a
    # section only works where the heading exists, so an old index would keep `## Focus` for ever
    # and never show what is in `life/`. It is rebuilt from the template and the previous one goes
    # to the trash rather than over the edge: it is generated, but it was the user's page.
    master = space / "INDEX.md"
    if master.is_file():
        text = master.read_text(encoding="utf-8", errors="ignore")
        if "\n## Life\n" not in text:
            ablage = space / TRASH_DIR / "INDEX.md"
            n = 1
            while ablage.exists():
                ablage = space / TRASH_DIR / f"INDEX-{n}.md"
                n += 1
            ablage.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(master), str(ablage))
            vorname = ""
            benutzer = space / USER_FILE
            if benutzer.is_file():
                treffer = re.search(r'(?m)^first_name: *"?([^"\n]*)"?',
                                    benutzer.read_text(encoding="utf-8", errors="ignore"))
                vorname = (treffer.group(1).strip() if treffer else "")
            master.write_text(_render_master_index(vorname), encoding="utf-8")
            _update_master_index(space)
            getan.append(f"INDEX.md rebuilt for the new rooms, the old one is in {TRASH_DIR}/")

    return getan


def _migrate_archive_db_name(space: Path) -> list[str]:
    """The archive index keeps what it has read across the rename of `records` to `archive`.

    The file is named after the command family, and the family was renamed while the file was not.
    The next read then opened a fresh, empty database beside a full one and reported an empty
    index, which reads exactly like an archive nobody has filled yet. Everything that had been read
    was invisible while every command reported success, and that is the shape of failure that costs
    the most to notice.

    A step of its own rather than a line inside the rename, because a space that already took the
    rename records it as done and never runs it again. The repair has to be able to arrive after
    the damage.
    """
    import sqlite3

    getan: list[str] = []
    alt = space / RUNTIME_DIR / "records.sqlite3"
    neu = space / RUNTIME_DIR / ARCHIVE_DB
    if not alt.is_file():
        return getan

    def dokumente(pfad: Path) -> int:
        """How many documents that database holds. An unreadable file holds none."""
        if not pfad.is_file():
            return 0
        try:
            db = sqlite3.connect(str(pfad))
            try:
                return db.execute("SELECT count(*) FROM documents").fetchone()[0]
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            return 0

    # Both sides full is the one case where nothing is safe to do automatically: whichever way it
    # went, somebody's reading would be thrown away. It is said out loud instead.
    if dokumente(neu) > 0:
        getan.append(f"{RUNTIME_DIR}/records.sqlite3 left as it is: {ARCHIVE_DB} already holds "
                     f"documents, so the two have to be looked at")
        return getan

    if neu.is_file():
        # An empty database created by a read that came before this step. It goes where everything
        # goes that is no longer needed, never over the edge.
        ziel = space / TRASH_DIR / datetime.now().strftime("%Y-%m-%d") / ARCHIVE_DB
        ziel.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while ziel.exists():
            ziel = ziel.with_name(f"{ziel.stem}-{n}{ziel.suffix}")
            n += 1
        shutil.move(str(neu), str(ziel))
        getan.append(f"empty {ARCHIVE_DB} moved to {ziel.relative_to(space).as_posix()}")

    shutil.move(str(alt), str(neu))
    getan.append(f"{RUNTIME_DIR}/records.sqlite3 -> {RUNTIME_DIR}/{ARCHIVE_DB}")
    return getan


def _rename_in_archive_index(space: Path,
                             moves: tuple[tuple[str, str], ...]) -> list[str]:
    """Every path inside the archive index moves with the area it points into.

    Renaming the database file was only half of it. The rows inside still named the area each
    document came from, so a search answered in full and handed back paths that all led nowhere,
    with no error anywhere. That is worse than an index that is plainly broken: it looks like an
    archive whose files somebody deleted.

    A step of its own, and not a line inside the rename, so it also reaches a space that already
    took the rename. Whether a row is rewritten is decided per row against the disk, never by
    string replacement alone: the area move resolved name collisions by appending a counter, so the
    obvious new path is a guess until the file is actually there. A row whose file cannot be found
    is left exactly as it was and counted, because a wrong path that is honest about itself can
    still be searched for by hand, and a rewritten wrong path cannot.
    """
    import sqlite3

    pfad = space / RUNTIME_DIR / ARCHIVE_DB
    if not pfad.is_file():
        return []

    getan: list[str] = []
    try:
        db = sqlite3.connect(str(pfad))
    except Exception:  # noqa: BLE001
        return []
    try:
        try:
            zeilen = [r[0] for r in db.execute("SELECT path FROM documents").fetchall()]
        except Exception:  # noqa: BLE001 -- not an archive index, nothing to do
            return []

        umgeschrieben = 0
        offen = 0
        for alt_pfad in zeilen:
            wurzel = alt_pfad.split("/", 1)[0]
            ziel_wurzel = next((neu for alt, neu in moves if alt == wurzel), "")
            if not ziel_wurzel:
                continue
            neuer = f"{ziel_wurzel}/{alt_pfad.split('/', 1)[1]}" if "/" in alt_pfad else ziel_wurzel
            if not (space / neuer).exists():
                offen += 1
                continue
            db.execute("UPDATE documents SET path = ? WHERE path = ?", (neuer, alt_pfad))
            # The searchable text carries the path as its first line, so that the name of a file
            # can be searched for and not only its content. Moving the path column alone leaves
            # that line naming the old area: a search for the area that no longer exists returns
            # every document, and a search for the one they are all in returns nothing. Both
            # answers look like ordinary results.
            zeile = db.execute("SELECT body FROM content WHERE path = ?", (alt_pfad,)).fetchone()
            if zeile is not None:
                rumpf = zeile[0].split("\n", 1)[1] if "\n" in zeile[0] else ""
                db.execute("DELETE FROM content WHERE path = ?", (alt_pfad,))
                db.execute("INSERT INTO content (path, body) VALUES (?, ?)",
                           (neuer, f"{_index_name_words(neuer)}\n{rumpf}"))
            umgeschrieben += 1
        # The name line is checked against the path itself, not against a list of old area names.
        # The narrow version of this only repaired a row whose path was still wrong, so a space
        # whose paths had already been corrected kept the old name in its searchable text for ever:
        # the one repair that could reach it was the one that decided there was nothing to do. What
        # has to hold is simple and has no history in it, so it is stated that way: the first line
        # of the text is the path as words.
        nachgezogen = 0
        for jetzt_pfad, koerper in db.execute("SELECT path, body FROM content").fetchall():
            soll = _index_name_words(jetzt_pfad)
            kopf, _, rumpf = koerper.partition("\n")
            if kopf == soll:
                continue
            db.execute("DELETE FROM content WHERE path = ?", (jetzt_pfad,))
            db.execute("INSERT INTO content (path, body) VALUES (?, ?)",
                       (jetzt_pfad, f"{soll}\n{rumpf}"))
            nachgezogen += 1

        if umgeschrieben or nachgezogen:
            db.commit()
        if umgeschrieben:
            getan.append(f"{umgeschrieben} path(s) in the archive index moved to their new area")
        if nachgezogen:
            getan.append(f"{nachgezogen} document(s) in the archive index had a searchable name "
                         f"that no longer matched their path")
        if offen:
            getan.append(f"{offen} path(s) in the archive index point to a file that is not at the "
                         f"new place either; left as they are, `archive index` reads them again")
    finally:
        db.close()
    return getan


# What a rename may not touch: anything that records what happened. The activity log, the update
# history, the operation reports and the journal are statements about a day that is over, and on
# that day the folder really was called what it was called. Correcting them makes the record wrong
# in order to make a path right, and the path in a finished report leads nowhere useful anyway.
# Found the hard way: a first run rewrote 134 lines of an activity log before anybody looked.
_TEXT_PATH_SKIP = (f"{SYSTEM_DIR}/system/", f"{HISTORY_DIR}/", f"{TRASH_DIR}/", f"{LOGS_DIR}/",
                   f"{JOURNAL_DIR}/")
_TEXT_PATH_SKIP_FILES = frozenset({
    ACTIVITY_LOG_FILE,
    f"{SYSTEM_DIR}/update-history.md",
    f"{MEMORY_DIR}/briefing.md",
})


def _rename_in_notes(space: Path,
                     moves: tuple[tuple[str, str], ...]) -> list[str]:
    """Paths the user or an expert wrote into a note follow the area they point into.

    The area move renamed folders and rewrote what the machine keeps for itself. What it left alone
    was every sentence that names a path: a note saying where the documents for someone are kept, a
    `source_detail` recording where a text came from. Those read as correct and lead nowhere, and
    nothing about them looks broken, which is why nobody finds them.

    Two limits keep this from doing damage in order to be thorough. A candidate is only rewritten
    when something is actually at the new path, so a guess is never written into somebody's text.
    And it has to be written as a path, with the slash that makes it one: the old area names are
    ordinary words in running prose, and correcting a link is not worth corrupting a sentence.
    """
    getan: list[str] = []
    ziele = dict(moves)
    muster = re.compile(r"(?<=[\"'`\s(\[])(" + "|".join(re.escape(a) for a, _ in moves)
                        + r")/([A-Za-z0-9._\-/]*)")
    for datei in sorted(space.rglob("*.md")):
        rel = datei.relative_to(space).as_posix()
        if rel.startswith(_TEXT_PATH_SKIP) or rel in _TEXT_PATH_SKIP_FILES:
            continue
        try:
            alt_text = datei.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        def ersetze(m: re.Match) -> str:
            neu_wurzel = ziele[m.group(1)]
            rest = m.group(2)
            kandidat = f"{neu_wurzel}/{rest}" if rest else f"{neu_wurzel}/"
            if not (space / kandidat.rstrip("/")).exists():
                return m.group(0)
            return kandidat

        neu_text = muster.sub(ersetze, alt_text)
        if neu_text != alt_text:
            datei.write_text(neu_text, encoding="utf-8")
            getan.append(f"paths rewritten in {rel}")
    return getan


# Files an earlier version shipped under the system folder and no version ships now. An update only
# withdraws what the version being left still listed, so anything dropped before that stays for
# ever, and a leftover there reads like part of the product: a documentation page for an area that
# no longer exists, a template carrying a retired kind. Named one by one rather than derived,
# because deriving them means comparing against a manifest that has itself been wrong.
_RETIRED_SYSTEM_FILES = (
    f"{SYSTEM_MATERIAL_DIR}/docs/records.md",
    f"{SYSTEM_MATERIAL_DIR}/templates/record.md",
)


def _neuer_als(eins: Path, anderes: Path) -> bool:
    """Is the first the more recent of the two, folders included.

    A folder answers with the newest thing in it, because a folder's own timestamp says when
    something was added to it and not when its contents last changed.
    """
    def jung(pfad: Path) -> float:
        try:
            if pfad.is_dir():
                zeiten = [f.stat().st_mtime for f in pfad.rglob("*") if f.is_file()]
                return max(zeiten) if zeiten else pfad.stat().st_mtime
            return pfad.stat().st_mtime
        except OSError:
            return 0.0
    return jung(eins) > jung(anderes)


# What moved out of the documentation, and where to. The documentation is for the person who owns
# the space; these four were instructions to a specialist and sat there because there was nowhere
# else. A reader looking for help found working notes, and a specialist looking for its own method
# found it in a folder it never opens.
_DOC_MOVES = (
    (f"{SYSTEM_MATERIAL_DIR}/docs/reed-methodology.md",
     f"{SYSTEM_MATERIAL_DIR}/experts/reed/methodology.md"),
    (f"{SYSTEM_MATERIAL_DIR}/docs/reed-source-pipelines.md",
     f"{SYSTEM_MATERIAL_DIR}/experts/reed/source-pipelines.md"),
    (f"{SYSTEM_MATERIAL_DIR}/docs/media-prompt-craft.md",
     f"{SYSTEM_MATERIAL_DIR}/skills/media/prompt-craft.md"),
    (f"{SYSTEM_MATERIAL_DIR}/docs/operating-principles.md",
     f"{SYSTEM_MATERIAL_DIR}/operating-principles-reasoning.md"),
)


def _migrate_docs_out_of_the_manual(space: Path) -> list[str]:
    """Take the leftovers of four pages out of the documentation folder.

    The update writes the pages at their new place by itself, because the manifest lists them there.
    What it does not do is remove the old copies: a withdrawal only reaches files the version being
    left still listed, and these were listed under their old names. Both would then sit in the space,
    the old one visible in the documentation index of an older reader.
    """
    getan: list[str] = []
    for alt, neu in _DOC_MOVES:
        verirrt = space / alt
        if verirrt.is_file() and _move_into(space, verirrt, TRASH_DIR, "trashed", dated=True) == 0:
            getan.append(f"{alt} is not part of the documentation any more, it moved to {neu}")
    return getan


def _migrate_empty_journal_days(space: Path) -> list[str]:
    """Take out journal days that hold a heading and nothing else.

    A day exists as a file only once something has been written into it, which is why nothing
    creates an empty one. A heading is not something written into it: a day whose whole content is
    `## Tasks` says there is a task and there is none. The user opens it, finds nothing, and now
    doubts every other day too. These came from a task that was added and later taken out again,
    which left its heading standing.

    Only where nothing at all is left besides headings and blank lines. One word of anybody's text
    and the file stays exactly as it is.
    """
    getan: list[str] = []
    wurzel = space / JOURNAL_DIR
    if not wurzel.is_dir():
        return getan
    for datei in sorted(wurzel.rglob("*.md")):
        try:
            zeilen = datei.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        inhalt = [z for z in zeilen if z.strip() and not z.lstrip().startswith("#")]
        if inhalt:
            continue
        if _move_into(space, datei, TRASH_DIR, "trashed", dated=True) == 0:
            getan.append(f"{datei.relative_to(space).as_posix()} held a heading and nothing else")
    return getan


def _migrate_brands_into_system(space: Path) -> list[str]:
    """Bring the brand under what Zanmai keeps, from the area it sat in.

    It was in two places at once and that is not a tidiness question: the command that counts brands
    read one of them and the specialist who writes a brand wrote the other, so a space could hold a
    brand that no run could find. One place, and the one that four specialists already read by path.

    The move goes through the general rename, so the search index, the routing table and any
    sentence naming the old path follow along. A brand folder can hold thousands of files, and they
    are moved rather than copied, so the size of it costs nothing.
    """
    if not (space / f"{LIFE_DIR}/brands").is_dir():
        return []
    return rename_areas(space, ((f"{LIFE_DIR}/brands", DESIGN_DIR),))


def _migrate_retention_to_a_difference(space: Path) -> list[str]:
    """Reduce the user's keeping terms to their confirmation and what they changed.

    The file used to be a full copy of the shipped periods, which made it a second list of the same
    thing: it aged, an update could not reach it because it is the user's, and a space answered with
    wording the product had retired. What is kept is the decision, not the copy.

    Where a space carried two of these files, both are read and the newer confirmation wins, so a
    confirmation written into the copy that was left behind is not lost.
    """
    ziel = space / SYSTEM_DIR / RETENTION_FILE
    quellen = [p for p in (ziel, space / RETENTION_FILE) if p.is_file()]
    if not quellen:
        return []

    gelesen: list[dict] = []
    for p in quellen:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            gelesen.append(d)
    if not gelesen:
        return []

    bestaetigt = max((str(d.get("_confirmed") or "") for d in gelesen), default="")
    geprueft = max((str(d.get("_checked") or "") for d in gelesen), default="")
    if not bestaetigt:
        return []

    # Only what actually differs from what ships today. A period whose wording matches is dropped:
    # keeping it would recreate the copy this step exists to remove.
    vorgabe = {str(e.get("category")): e for e in _retention_defaults().get("terms", [])}
    abweichend = []
    for d in gelesen:
        for e in d.get("terms", []):
            name = str(e.get("category") or "")
            if not name:
                continue
            if name not in vorgabe or any(e.get(k) != vorgabe[name].get(k)
                                          for k in ("years", "label", "why")):
                if not any(str(a.get("category")) == name for a in abweichend):
                    abweichend.append(e)

    schlank = {"_comment": ("What you confirmed about how long things are kept, and anything you "
                            "changed. The periods themselves ship with Zanmai and are improved with "
                            "it; only your decision lives here."),
               "_confirmed": bestaetigt}
    if geprueft:
        schlank["_checked"] = geprueft
    if abweichend:
        schlank["terms"] = abweichend

    alt_gross = max(len(json.dumps(d)) for d in gelesen)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(schlank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    getan = [f"{SYSTEM_DIR}/{RETENTION_FILE} now holds your decision instead of a copy of the "
             f"periods ({alt_gross} bytes down to {len(json.dumps(schlank))}), confirmed "
             f"{bestaetigt}"]
    if len(quellen) > 1:
        weg = space / RETENTION_FILE
        if _move_into(space, weg, TRASH_DIR, "trashed", dated=True) == 0:
            getan.append(f"a second {RETENTION_FILE} at the space root was read first and then "
                         f"moved to {TRASH_DIR}/")
    if abweichend:
        getan.append(f"{len(abweichend)} period(s) you had changed were kept")
    return getan


def _migrate_retention_without_jurisdiction(space: Path) -> list[str]:
    """Take a keeping-terms file out of use that still carries the shape this product withdrew.

    The terms used to be per legal category and per country, which is a promise nobody here can
    keep: the figures differ by jurisdiction, they change, and being wrong about one of them costs
    a document somebody needed. They were replaced by three plain buckets and no country at all.

    A space that was set up before that keeps its old file for ever, because the keeping terms are
    the user's and no update touches them. So a space answers "how long is this kept" with figures
    the product retired, under a confirmation date the user does not recognise. The file goes to
    the trash rather than being rewritten, and Zanmai falls back to the shipped suggestion and puts
    it to the user once, which is the same path a new space takes.

    Recognised by `_jurisdiction`, a field the current shape does not have and the old one always
    did. A file somebody wrote themselves in the current shape carries no such field and is not
    touched.
    """
    datei = space / SYSTEM_DIR / RETENTION_FILE
    if not datei.is_file():
        return []
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(daten, dict) or "_jurisdiction" not in daten:
        return []
    if _move_into(space, datei, TRASH_DIR, "trashed", dated=True) != 0:
        return []
    return [f"{SYSTEM_DIR}/{RETENTION_FILE} carried the retired shape, with a legal category per "
            f"country. It went to {TRASH_DIR}/, and the shipped suggestion applies until you "
            f"confirm one"]


def _migrate_stray_root_copies(space: Path) -> list[str]:
    """Take what the machine keeps out of the space root, where earlier versions kept it.

    These are not stray writes, they are a move nobody finished. The machine's own files lived at
    the root until they were gathered under the system folder, and the versions that gathered them
    started writing to the new place without taking the old copies along. Both then existed, with
    different content, and the older one is the one a person opens because it is the one they can
    see.

    Named from the constants rather than from a list typed out here, so a folder that moves under
    the system folder tomorrow is covered by this the day it moves. Only an exact name at the root
    counts: a note somebody wrote called `memory.md` is not this, and a folder of their own called
    `logs` is not either, because the names compared are the ones the machine owns.
    """
    getan: list[str] = []
    eigene = {Path(rel).name for rel in (
        OPEN_DIR, RUNTIME_DIR, MEMORY_DIR, LOGS_DIR, HISTORY_DIR, SCRATCH_DIR, TRASH_DIR,
        DESIGN_DIR, CONNECTIONS_DIR, EXTENSIONS_DIR, SYSTEM_MATERIAL_DIR, USER_FILE,
        f"{SYSTEM_DIR}/{ROUTING_FILE}", f"{SYSTEM_DIR}/{RETENTION_FILE}",
        f"{SYSTEM_DIR}/{ALIASES_FILE}", f"{SYSTEM_DIR}/update-history.md")}
    for name in sorted(eigene):
        verirrt = space / name
        richtig = space / SYSTEM_DIR / name
        if not verirrt.exists() or verirrt == richtig:
            continue
        # Only where the machine already keeps its own copy in the right place. Without that this
        # would move the one working copy of something into the trash and call it tidying up.
        if not richtig.exists():
            getan.append(f"{name} sits at the space root and nothing is under {SYSTEM_DIR}/ yet, "
                         f"so it was left alone and needs a look")
            continue
        # "The new place holds it" is not the same as "the new place holds the newer one". A
        # confirmation written into the old copy after the move was made would be tidied away here
        # and never seen again, and the file it went missing from is the one that says how long
        # documents are kept. Where the old copy is the newer one, nothing is moved and the two are
        # put to the user, because which one is right is a question about their decisions.
        if _neuer_als(verirrt, richtig):
            getan.append(f"{name} at the space root is NEWER than the copy under {SYSTEM_DIR}/, so "
                         f"nothing was moved. Compare the two: something was written to the old "
                         f"place after the move")
            continue
        if _move_into(space, verirrt, TRASH_DIR, "trashed", dated=True) == 0:
            getan.append(f"{name} at the space root belonged under {SYSTEM_DIR}/ and went to "
                         f"{TRASH_DIR}/, where the copy under {SYSTEM_DIR}/ is the one in use")
    return getan


def _migrate_archive_db_restale(space: Path) -> list[str]:
    """Read a document into the index again where a step of this update changed the file itself.

    The index holds a copy of the text as it was at the moment it was read. A rename moves the file
    and rewrites lines inside it, and until now nothing read it again: the copy in the index kept
    the old field values, so a search for a retired word answered with documents that no longer
    contain it, quoting text that is not there any more.

    Runs last, after every step that could have touched a file. Two limits keep it cheap enough to
    sit in every update. Only text is considered, because a step of an update rewrites a field or a
    path and never touches a scan; and only a file whose size no longer matches the index is read
    again, because a modification time changes whenever a checkout puts a file back, without a
    single character having changed. Measured on a real archive: the time-based question read all
    55 documents, the size-based one read the 14 that had actually changed. On an archive with
    thousands of scans in it, the difference is hours of text recognition.
    """
    pfad = space / RUNTIME_DIR / ARCHIVE_DB
    if not pfad.is_file():
        return []

    import sqlite3
    try:
        db = sqlite3.connect(str(pfad))
    except Exception:  # noqa: BLE001
        return []
    try:
        try:
            zeilen = db.execute("SELECT path, size, mtime FROM documents").fetchall()
        except Exception:  # noqa: BLE001
            return []
        getan: list[str] = []
        for rel, groesse, zeit in zeilen:
            datei = space / rel
            if datei.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            try:
                stat = datei.stat()
            except OSError:
                continue
            if stat.st_size == groesse:
                continue
            art, text = _read_as_text(datei)
            if not art:
                continue
            db.execute("DELETE FROM content WHERE path = ?", (rel,))
            db.execute("INSERT INTO content (path, body) VALUES (?, ?)",
                       (rel, f"{_index_name_words(rel)}\n{text}"))
            db.execute("UPDATE documents SET size = ?, mtime = ?, kind = ? WHERE path = ?",
                       (stat.st_size, stat.st_mtime, art, rel))
            getan.append(f"{rel} read into the archive index again")
        if getan:
            db.commit()
            return getan
    finally:
        db.close()
    return []


def _migrate_retire_system_files(space: Path) -> list[str]:
    """Take what the distribution no longer ships out of the system folder, into the trash.

    Into the trash and not over the edge, like everything else: the file was the product's, but a
    space is the user's, and a step that quietly removes things from it is not one they can check
    afterwards.
    """
    getan: list[str] = []
    for rel in _RETIRED_SYSTEM_FILES:
        pfad = space / rel
        if pfad.is_file() and _move_into(space, pfad, TRASH_DIR, "trashed", dated=True) == 0:
            getan.append(f"{rel} is not part of the distribution any more, moved to {TRASH_DIR}/")
    return getan


def rename_areas(space: Path, moves: tuple[tuple[str, str], ...],
                 kinds: dict[str, str] | None = None) -> list[str]:
    """Rename areas in a space, everywhere a path can live. The whole checklist, in order.

    Until 1.0 the areas can still change, so this is the mechanism rather than one migration: a
    future rename is a list of pairs and a raised revision, not six places to remember. The order
    matters and is the reason this is one function. Folders move first, because every step after it
    decides whether to rewrite a path by asking whether the file is at the new place. The index
    follows, then the notes, and the master index last, because it is rebuilt from what the others
    left behind.

    Six places hold a path, and the day one of them was forgotten cost a working archive that
    reported success on every command:

    1. the folders themselves, with their `kind:` fields
    2. the machine's own files: the routing table, the pages of open work
    3. the search index: the path column of every row
    4. the search index again: the path is the first line of the searchable text
    5. sentences in notes that name a path
    6. the master index, whose headings are the area names

    Records of what happened are not on that list and never will be. The activity log, the
    operation reports and the journal say what was true on a day, and on that day the folder really
    was called what it was called.
    """
    getan = _move_areas(space, moves, kinds or {})
    getan += _rename_in_archive_index(space, moves)
    getan += _rename_in_notes(space, moves)
    return getan


def _migrate_rooms_to_eight(space: Path) -> list[str]:
    """Eleven areas become eight, through the general rename."""
    return _move_areas(space, _ROOM_MOVES, _KIND_MOVES)


def _migrate_archive_db_paths(space: Path) -> list[str]:
    """The archive index follows the areas of the eight-area move."""
    return _rename_in_archive_index(space, _ROOM_MOVES)


def _migrate_area_paths_in_text(space: Path) -> list[str]:
    """Sentences naming a path follow the areas of the eight-area move."""
    return _rename_in_notes(space, _ROOM_MOVES)


# Name, revision, step. Raise the revision when the step itself was wrong, never when only the data
# changed: it is the one way a fix reaches a space that already ran the faulty version, and it costs
# one repeat run everywhere else.
def _migrate_routing_keeps_a_file(space: Path) -> list[str]:
    """Take the sentence out of a routing rule that told a file to stay in the inbox.

    A rule could once say that, and the mechanic enforced it. It is gone, because a file left in the
    inbox is read again at every session start and cannot be told from one that arrived this
    morning. The sentence in the rule is not gone with it: it sits in the user's own words, it
    contradicts what now happens, and the run that reads the rule follows the sentence.

    So the sentence goes and nothing takes its place. What the file's own fate should be is the
    user's answer, in `keep`, and guessing it here would be the same mistake in the other direction:
    a rule that quietly starts discarding a file the user wanted kept. Left empty, it is asked once,
    the next time such a file arrives.
    """
    veraltet = re.compile(
        r"[^.;\n]*\b(stays? where it is|stays put|bleibt liegen|"
        r"nicht (gel[öo]scht|entfernt|verschoben|abgelegt)|"
        r"not (be )?(deleted|removed|moved|filed))\b[^.;\n]*[.;]?", re.I)
    pfad = _routing_path(space)
    daten = _routing(space)
    regeln = daten.get("rules") if isinstance(daten.get("rules"), list) else []
    geaendert: list[str] = []
    for regel in regeln:
        if not isinstance(regel, dict):
            continue
        anweisung = str(regel.get("do") or "")
        gekuerzt = veraltet.sub("", anweisung).strip(" ;,")
        if gekuerzt != anweisung.strip(" ;,"):
            regel["do"] = re.sub(r"\s{2,}", " ", gekuerzt)
            geaendert.append(str(regel.get("name", "?")))
    if geaendert:
        pfad.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _append_activity_log(space, "zanmai.py",
                             f"routing: took the stay-in-the-inbox sentence out of "
                             f"{len(geaendert)} rule(s): {', '.join(geaendert)}")
    return geaendert


_MIGRATIONS = (
    ("journal-one-layer", 1, _migrate_journal_to_one_layer),
    # 2: two folders of the same name were counted as two things, which split an archive that
    # existed under both the old area name and the new one.
    ("rooms-to-eight", 2, _migrate_rooms_to_eight),
    ("archive-db-name", 1, _migrate_archive_db_name),
    # 3: the searchable text kept the old area name. Revision 2 only repaired rows whose path was
    # also still wrong, which is never the case in a space that already ran revision 1.
    ("archive-db-paths", 3, _migrate_archive_db_paths),
    # 2: the first version rewrote the activity log, the operation reports and the journal, which
    # are records of days that are over.
    ("area-paths-in-text", 2, _migrate_area_paths_in_text),
    ("retire-system-files", 1, _migrate_retire_system_files),
    ("brands-into-system", 1, _migrate_brands_into_system),
    ("empty-journal-days", 1, _migrate_empty_journal_days),
    ("docs-out-of-the-manual", 1, _migrate_docs_out_of_the_manual),
    ("retention-without-jurisdiction", 1, _migrate_retention_without_jurisdiction),
    ("retention-as-a-difference", 1, _migrate_retention_to_a_difference),
    ("stray-root-copies", 1, _migrate_stray_root_copies),
    ("archive-db-restale", 1, _migrate_archive_db_restale),
    ("routing-keeps-a-file", 1, _migrate_routing_keeps_a_file),
)


def _run_space_migrations(space: Path) -> list[str]:
    """Every structural step this space has not had at its current revision, in order.

    The revision is what makes a correction reach the spaces that need it most. A step used to be
    recorded by name alone, so a space that had run a faulty version of it was the one space the
    fix could never arrive in: the name was there, the step was skipped for ever, and the damage
    stayed while every later update reported success. Raising the revision of a step makes it run
    again everywhere, which is why every step here has to be safe to run twice. They are: each one
    decides per file, against the disk, and does nothing where there is nothing to do.
    """
    schon = _migrations_done(space)
    zeilen: list[str] = []
    for name, revision, schritt in _MIGRATIONS:
        if schon.get(name, 0) >= revision:
            continue
        try:
            bewegt = schritt(space)
        except OSError as fehler:
            zeilen.append(f"migration {name} could not finish ({fehler}); nothing recorded, it runs again")
            continue
        _migration_record(space, name, revision)
        if bewegt:
            zeilen.append(f"migration {name}: {len(bewegt)} file(s) moved")
    return zeilen


def cmd_setup_update(args: argparse.Namespace) -> int:
    """Post-merge mechanic refresh for an updated space. The git fetch and the
    ff-merge happen outside this command (Pepper runs them via Bash with the
    user-facing TL;DR preview gate). After the working tree carries the new
    distribution, this command refreshes the host-side state that does not
    live in git: agent symlinks under `.claude/agents/`, skill symlinks under
    `.claude/skills/`, `.claude/settings.json`, and the top-level folders the
    manifest requires (empty ones carry no files, so git cannot deliver them).
    Idempotent, safe to run repeatedly on the same merged state."""
    space = Path(args.space_root).resolve()
    if not space.exists():
        print(f"fail: space root does not exist: {space}", file=sys.stderr)
        return 1
    user_md = space / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        print(
            f"fail: space not initialised (no zanmai/user.md). Run 'setup init' first.",
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
    for rel in _required_folders(space):
        _space_mkdir(space, space / rel, parents=True, exist_ok=True)

    # Both ignore lists, rewritten from the current folder names. A release that renames an area
    # otherwise leaves a space excluding a folder that no longer exists and committing one that does.
    _write_ignore_rules(space)

    # Structural steps the script does itself, before anything else reads the tree.
    for zeile in _run_space_migrations(space):
        print(f"  {zeile}")

    # Again, because a rename removes empty shells so that arriving material is not pushed aside
    # into `<name>-1`, and a required folder that happened to be empty is such a shell. It is the
    # end state that has to be complete, not the starting one: `zanmai/design` was created above,
    # emptied as a shell during the move, and the space then failed its own structure check.
    for rel in _required_folders(space):
        _space_mkdir(space, space / rel, parents=True, exist_ok=True)

    _install_agent_symlinks(space, _AGENT_NAMES)
    _install_skill_symlinks(space, _SKILL_SYMLINK_MAP)

    settings_path = space / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        _render_settings_json(space, python_cmd=python_cmd), encoding="utf-8"
    )

    # Merge the baseline allow-rules (zanmai.py + the experts' MCP tools) into
    # settings.local.json: add any that are missing, keep whatever the user added.
    local_path = space / ".claude" / "settings.local.json"
    baseline = json.loads(_render_settings_local_json(space, python_cmd=python_cmd))
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

    # Carry a space that still keeps its work objects in the old `.base` folder across. Once,
    # here rather than on first read: a migration that runs inside a read runs during every
    # session start, and one that never runs leaves a space silently holding two lists.
    umzug = _work_adopt_legacy(space)
    if umzug:
        print(f"    {umzug}")

    # Backfill a lessons file for any expert added after this space was
    # initialised. Memory is user-immune: create only, never overwrite.
    for agent in _MEMORY_AGENTS:
        lessons = space / MEMORY_DIR / "agents" / agent / "lessons.md"
        if not lessons.exists():
            lessons.parent.mkdir(parents=True, exist_ok=True)
            lessons.write_text(_render_agent_lessons(agent.capitalize()), encoding="utf-8")

    print(
        f"ok: refresh complete at {space} "
        f"(agent symlinks, skill symlinks, settings.json, settings.local.json)"
    )
    return 0


# Snapshot ----

def _set_auto_snapshots_flag(space_root: Path, enabled: bool) -> int:
    """Flip `auto_snapshots` in `zanmai/user.md`. Replaces an existing
    `auto_snapshots` line; if it is not present, inserts `auto_snapshots:`
    before the closing frontmatter delimiter."""
    user_md = space_root / SYSTEM_DIR / "user.md"
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
    print(f"ok: auto_snapshots {'enabled' if enabled else 'disabled'} in {user_md.relative_to(space_root)}")
    return 0


def cmd_snapshot_enable(args: argparse.Namespace) -> int:
    return _set_auto_snapshots_flag(Path(args.space).resolve(), True)


def cmd_snapshot_disable(args: argparse.Namespace) -> int:
    return _set_auto_snapshots_flag(Path(args.space).resolve(), False)


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


def _git(space: Path, *args: str, check: bool = True,
         env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run git against the history repository: its own git dir, the space as the working tree.

    Two repositories share this folder. The distribution's `.git/` tracks what ships and is how an
    update arrives; this one tracks what the user owns and never leaves the machine. Keeping them
    apart is one environment variable, and it is what makes a snapshot cost the change rather than a
    copy of everything.
    """
    env = {**os.environ,
           "GIT_DIR": str(space / HISTORY_DIR),
           "GIT_WORK_TREE": str(space),
           "GIT_CONFIG_NOSYSTEM": "1",
           **(env_extra or {})}
    result = subprocess.run(["git", *args], env=env, cwd=str(space),
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _history_ready(space: Path) -> bool:
    return (space / HISTORY_DIR / "HEAD").is_file()


def _history_ensure(space: Path) -> list[str]:
    """Create the history repository if it is not there. Idempotent, says what it did.

    The excludes live in the repository's own `info/exclude`, not in a `.gitignore` in the space: a
    file in the working tree would be read by both repositories, and the two want opposite things.
    """
    notes: list[str] = []
    if not _history_ready(space):
        (space / HISTORY_DIR).parent.mkdir(parents=True, exist_ok=True)
        _git(space, "init", "-q", "-b", "main")
        notes.append(f"started the history in {HISTORY_DIR}/")
    (space / HISTORY_DIR / "info").mkdir(parents=True, exist_ok=True)
    (space / HISTORY_DIR / "info" / "exclude").write_text(
        "# What the history leaves out. Written by zanmai.py, edits are overwritten.\n"
        + "\n".join(_HISTORY_EXCLUDE) + "\n", encoding="utf-8")
    # An identity, so a commit never fails on a machine where git was never configured. It is local
    # to this repository and says what it is, because nobody signed up to be an author here.
    _git(space, "config", "user.name", "Zanmai")
    _git(space, "config", "user.email", "zanmai@localhost")
    _git(space, "config", "gc.auto", "256")
    return notes


def cmd_snapshot_list(args: argparse.Namespace) -> int:
    """List the snapshots, newest first: when, why, and the name to restore from."""
    space = Path(args.space).resolve()
    if not _history_ready(space):
        print("no snapshots yet. The first one is taken before anything overwrites your material.")
        return 0
    log = _git(space, "log", "--format=%h  %ad  %s", "--date=format:%Y-%m-%d %H:%M", check=False)
    if log.returncode != 0 or not log.stdout.strip():
        print("no snapshots yet. The first one is taken before anything overwrites your material.")
        return 0
    print(log.stdout, end="")
    anzahl = len(log.stdout.strip().splitlines())
    groesse = _lesbare_groesse(sum(f.stat().st_size for f in (space / HISTORY_DIR).rglob("*") if f.is_file()))
    print(f"\n{anzahl} snapshot(s), {groesse} on disk for all of them together.")
    return 0


def _restore_whole_space(space: Path, snapshot: str) -> int:
    """Put the whole space back the way it was in one snapshot, in one operation.

    This exists because the documentation promised it and the command could not do it: an update
    replaces well over a hundred files, and putting them back one named path at a time is not a way
    back, it is a way to build a half-and-half state by hand. The snapshot before an update is only
    a way back if it can be taken as a whole.

    What makes it safe is not that it asks, it is that nothing is destroyed. A snapshot of the
    current state is taken first, so going back is itself reversible, and anything that exists now
    and did not exist then goes to the trash rather than over the edge, named one by one in the
    output. The runtime folder is outside the history entirely, so an index or a cache is neither
    restored nor removed.
    """
    if not _history_ready(space):
        print("fail: there are no snapshots to restore from", file=sys.stderr)
        return 1
    if _git(space, "rev-parse", "--verify", f"{snapshot}^{{commit}}", check=False).returncode != 0:
        print(f"fail: no such snapshot: {snapshot}. `snapshot list` shows what there is.",
              file=sys.stderr)
        return 1

    # The state being left has to be reachable afterwards, or this command is the one operation in
    # Zanmai with no way back out of it.
    sicherung = argparse.Namespace(space=str(space), reason=f"before going back to {snapshot}",
                                   agent="zanmai.py")
    try:
        cmd_snapshot_create(sicherung)
    except Exception as fehler:  # noqa: BLE001
        print(f"error: the current state could not be snapshotted ({fehler}), so nothing was "
              f"changed.", file=sys.stderr)
        return 1

    def dateien(ref: str) -> set[str]:
        out = _git(space, "ls-tree", "-r", "--name-only", ref, check=False)
        return {z for z in out.stdout.splitlines() if z.strip()}

    damals = dateien(snapshot)
    jetzt = dateien("HEAD")

    # Never through its own trash, and never into the history: both would move a folder into
    # itself. Their content is the record of what was already put aside.
    seither = sorted(p for p in (jetzt - damals)
                     if not p.startswith((f"{TRASH_DIR}/", f"{HISTORY_DIR}/")))
    weggelegt: list[str] = []
    geblieben: list[str] = []
    for rel in seither:
        pfad = space / rel
        if not pfad.is_file():
            continue
        # A file another rule protects stays where it is, and that is right: a keeping rule does
        # not stop applying because a restore is running. What was missing is that the answer got
        # lost, printed as a failure line at the top of a run that then succeeded completely.
        if _move_into(space, pfad, TRASH_DIR, "trashed", dated=True) == 0:
            weggelegt.append(rel)
        else:
            geblieben.append(rel)

    aus = _git(space, "checkout", snapshot, "--", ".", check=False)
    if aus.returncode != 0:
        print(f"error: the space could not be put back ({aus.stderr.strip()}). The state before "
              f"this attempt is in the snapshot just taken.", file=sys.stderr)
        return 1

    # Folders the snapshot never had stay behind otherwise, because git carries no empty folder and
    # a checkout cannot remove what it does not know. A space after a way back looked like neither
    # state: both layouts side by side, the new ones empty. Only empty ones go, so nothing anybody
    # put anywhere is touched.
    leer = 0
    for ordner in sorted((d for d in space.rglob("*") if d.is_dir()),
                         key=lambda d: len(d.parts), reverse=True):
        rel = ordner.relative_to(space).as_posix()
        if rel.startswith((f"{TRASH_DIR}", f"{HISTORY_DIR}", ".git")):
            continue
        if any(ordner.iterdir()):
            continue
        if any(p.startswith(f"{rel}/") for p in damals):
            continue
        ordner.rmdir()
        leer += 1

    _append_activity_log(space, "zanmai.py", f"restored the whole space from snapshot {snapshot}")
    print(f"ok: the space is back as it was in {snapshot} ({len(damals)} file(s)).")
    if weggelegt:
        print(f"{len(weggelegt)} file(s) that did not exist then went to {TRASH_DIR}/, restorable:")
        for rel in weggelegt[:20]:
            print(f"  {rel}")
        if len(weggelegt) > 20:
            print(f"  ... and {len(weggelegt) - 20} more")
    if leer:
        print(f"{leer} empty folder(s) that did not exist then were removed.")
    if geblieben:
        print(f"{len(geblieben)} file(s) stayed where they are, because a rule of yours protects "
              f"them. Look at each one: the snapshot may hold the same material under its old "
              f"path, and then you have it twice.")
        for rel in geblieben:
            print(f"  {rel}")
    print("The state you just left is a snapshot of its own, so this step is undoable as well.")
    return 0


def cmd_snapshot_restore(args: argparse.Namespace) -> int:
    """Put back what a snapshot held: one named file, or the whole space with `--all`.

    One path at a time is the ordinary case and stays the default. The whole space is the case an
    update needs, and it was missing while the documentation named it as the way back from a bad
    update.
    """
    space = Path(args.space).resolve()
    if getattr(args, "all", False):
        if args.path:
            print("fail: --path and --all ask for different things; use one of them",
                  file=sys.stderr)
            return 1
        return _restore_whole_space(space, args.snapshot)
    if not args.path:
        print("fail: name the path to put back, or --all for the whole space", file=sys.stderr)
        return 1
    if not _history_ready(space):
        print("fail: there are no snapshots to restore from", file=sys.stderr)
        return 1
    rel = args.path.replace("\\", "/").lstrip("/")
    zeigt = _git(space, "show", f"{args.snapshot}:{rel}", check=False)
    if zeigt.returncode != 0:
        print(f"fail: {rel} is not in snapshot {args.snapshot}. `snapshot list` shows what there is, "
              f"and `snapshot show --snapshot <name>` lists what a snapshot holds.", file=sys.stderr)
        return 1
    jetzt = space / rel
    if jetzt.is_file():
        rc = _move_into(space, jetzt, TRASH_DIR, "trashed", dated=True)
        if rc != 0:
            return rc
    _space_mkdir(space, jetzt.parent, parents=True, exist_ok=True)
    _git(space, "checkout", args.snapshot, "--", rel)
    _append_activity_log(space, "zanmai.py", f"restored {rel} from snapshot {args.snapshot}")
    print(f"ok: {rel} is back as it was in {args.snapshot}. The version that was there went to "
          f"{TRASH_DIR}/, so this is undoable too.")
    return 0


def cmd_snapshot_show(args: argparse.Namespace) -> int:
    """What one snapshot holds, or what changed in it."""
    space = Path(args.space).resolve()
    if not _history_ready(space):
        print("no snapshots yet")
        return 0
    if args.path:
        out = _git(space, "show", f"{args.snapshot}:{args.path.lstrip('/')}", check=False)
        if out.returncode != 0:
            print(f"fail: {args.path} is not in snapshot {args.snapshot}", file=sys.stderr)
            return 1
        print(out.stdout, end="")
        return 0
    out = _git(space, "show", "--stat", "--format=%h  %ad  %s",
               "--date=format:%Y-%m-%d %H:%M", args.snapshot, check=False)
    if out.returncode != 0:
        print(f"fail: no such snapshot: {args.snapshot}", file=sys.stderr)
        return 1
    print(out.stdout, end="")
    return 0


def _snapshot_entries(space: Path) -> list[tuple[str, str, str]]:
    """Every snapshot, newest first: full hash, committed date in ISO, subject line."""
    log = _git(space, "log", "--format=%H%x1f%cI%x1f%s", check=False)
    if log.returncode != 0 or not log.stdout.strip():
        return []
    eintraege = []
    for zeile in log.stdout.splitlines():
        teile = zeile.split("\x1f")
        if len(teile) == 3:
            eintraege.append((teile[0], teile[1], teile[2]))
    return eintraege


def _sweep_snapshots(space: Path) -> list[str]:
    """Cut the snapshot history back to its keeping window.

    A snapshot is a point to jump back to, taken before an update or a large edit, and whether that
    went wrong is known within days. Kept for a month it stops being a safety line and becomes a
    pile: 25 of them held 2.6 GB, almost all of it the user's own video
    and slide files carried along a second time.

    The newest one always survives, however old it is. A space nobody touched for three weeks would
    otherwise sit with no jump-back point at all, which is the one state this whole mechanism exists
    to prevent.

    The cut is a rebuild, not a rewrite in place: the surviving snapshots are re-committed onto a
    fresh root with their trees and dates unchanged, the branch is moved over, and the objects the
    dropped ones held are then unreachable and go with the prune. Their hashes change, which is why
    `snapshot list` is the way to name one rather than a hash written down somewhere.
    """
    if not _history_ready(space):
        return []
    eintraege = _snapshot_entries(space)
    if len(eintraege) < 2:
        return []
    grenze = datetime.now().astimezone() - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    behalten = [e for e in eintraege if datetime.fromisoformat(e[1]) >= grenze] or [eintraege[0]]
    if len(behalten) == len(eintraege):
        return []
    vorher = sum(f.stat().st_size for f in (space / HISTORY_DIR).rglob("*") if f.is_file())
    elternteil = ""
    for commit, datum, betreff in reversed(behalten):   # oldest first, so each gets its parent
        baum = _git(space, "rev-parse", f"{commit}^{{tree}}").stdout.strip()
        args = ["commit-tree", baum, "-m", betreff]
        if elternteil:
            args += ["-p", elternteil]
        elternteil = _git(space, *args,
                          env_extra={"GIT_AUTHOR_DATE": datum, "GIT_COMMITTER_DATE": datum}
                          ).stdout.strip()
    _git(space, "update-ref", "refs/heads/main", elternteil)
    _git(space, "reflog", "expire", "--expire=now", "--all", check=False)
    _git(space, "gc", "--prune=now", "--quiet", check=False)
    nachher = sum(f.stat().st_size for f in (space / HISTORY_DIR).rglob("*") if f.is_file())
    weg = len(eintraege) - len(behalten)
    return [f"dropped {weg} snapshot(s) older than {SNAPSHOT_RETENTION_DAYS} days, "
            f"{len(behalten)} left, {_lesbare_groesse(vorher)} -> {_lesbare_groesse(nachher)}. "
            f"A snapshot is a point to jump back to after an update or a large edit, not a backup, "
            f"so it is not kept once that is known to have gone well."]


def cmd_snapshot_compact(args: argparse.Namespace) -> int:
    """Let git pack the history down. Loses nothing, every snapshot stays."""
    space = Path(args.space).resolve()
    if not _history_ready(space):
        print("no history to compact")
        return 0
    vorher = sum(f.stat().st_size for f in (space / HISTORY_DIR).rglob("*") if f.is_file())
    _git(space, "gc", "--quiet")
    nachher = sum(f.stat().st_size for f in (space / HISTORY_DIR).rglob("*") if f.is_file())
    print(f"ok: history packed, {_lesbare_groesse(vorher)} -> {_lesbare_groesse(nachher)}. "
          f"Every snapshot is still there.")
    return 0


def _read_auto_snapshots_flag(space_root: Path) -> bool:
    """Return the `auto_snapshots` flag from `zanmai/user.md` (default true).
    Default-true means a space without user.md (e.g. the builder's own dist
    tree) is never blocked by this check."""
    user_md = space_root / SYSTEM_DIR / "user.md"
    if not user_md.exists():
        return True
    try:
        fm = _session_parse_frontmatter(user_md.read_text(encoding="utf-8"))
    except OSError:
        return True
    raw = fm.get("auto_snapshots", "true")
    return str(raw).strip().strip('"').lower() != "false"


def cmd_snapshot_create(args: argparse.Namespace) -> int:
    """Take a snapshot: commit the whole space into the history repository.

    A snapshot used to be a full copy of the space, which cost what the user owns every single time
    while protecting one change. Measured: two copies, thirteen gigabytes, for three
    gigabytes of material, because each copy also copied the copies before it. The history stores
    every file once by content, so an unchanged file costs nothing on the second snapshot and a
    changed line costs the line.

    Respects `auto_snapshots: false` in `zanmai/user.md`.
    """
    space = Path(args.space).resolve()
    if not args.reason.strip():
        print("fail: reason-slug empty", file=sys.stderr)
        return 1
    reason = _slugify(args.reason)
    if not _read_auto_snapshots_flag(space):
        print(f"skip: auto_snapshots disabled in {USER_FILE}")
        return 0
    if not space.is_dir():
        print(f"fail: not a directory: {space}", file=sys.stderr)
        return 1
    if shutil.which("git") is None:
        print("fail: git is not on this machine, and the history is a git repository. "
              "Install git, then take the snapshot again. Nothing has been changed.", file=sys.stderr)
        return 1

    try:
        for note in _history_ensure(space):
            print(f"ok: {note}")
        _git(space, "add", "-A")
        stand = _git(space, "status", "--porcelain")
        if not stand.stdout.strip() and _git(space, "rev-parse", "HEAD", check=False).returncode == 0:
            letzte = _git(space, "log", "-1", "--format=%h %s", check=False).stdout.strip()
            print(f"ok: nothing has changed since the last snapshot ({letzte}), so there is nothing "
                  f"to take. That one still covers you.")
            return 0
        _git(space, "commit", "-q", "-m", reason)
        kurz = _git(space, "rev-parse", "--short", "HEAD").stdout.strip()
    except RuntimeError as exc:
        print(f"fail: the snapshot could not be taken ({exc}). Nothing has been changed.",
              file=sys.stderr)
        return 1

    _append_activity_log(space, "zanmai.py", f"snapshot {kurz} ({reason})")
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


def _discover_mcp_servers(space: Path) -> list[tuple[str, str]]:
    """MCP servers Claude Code knows on this machine, read from its config:
    global servers (settings.json, ~/.claude.json top-level), this project's
    servers (~/.claude.json projects[<space>] and a project-local .mcp.json),
    plus servers configured for ANOTHER folder (scope "other folder"). The last
    group is not reachable here, but it is an access the user already has and
    that already works, so it is reused for this space instead of establishing a
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
        if key == str(space) or not isinstance(entry, dict):
            continue
        for name in (entry.get("mcpServers") or {}):
            found.setdefault(name, "other folder")
    proj = projects.get(str(space)) or {}
    for name in (proj.get("mcpServers") or {}):
        found[name] = "project"
    for name in (_scan_load_json(space / ".mcp.json").get("mcpServers") or {}):
        found[name] = "project"
    return sorted(found.items())


def _discover_plugins() -> list[str]:
    """Enabled plugin identifiers from settings.json. Plugins may bring MCP tools
    or skills; the scan lists them so Wong can ask what they are for."""
    enabled = _scan_load_json(Path.home() / ".claude" / "settings.json").get("enabledPlugins") or {}
    return sorted({key.split("@")[0] for key, on in enabled.items() if on})


def cmd_connection_scan(args: argparse.Namespace) -> int:
    """Discover connectable sources for this space: MCP servers and enabled
    plugins from Claude Code's config, plus CLIs on PATH and (macOS) relevant
    apps. Project-aware, only servers reachable from this space are listed.
    Informational; registers nothing. The reads of Claude Code's config are
    defensive, so a layout change degrades gracefully."""
    space = Path(args.space).resolve()
    mcp = _discover_mcp_servers(space)
    plugins = _discover_plugins()
    found_cli = [(name, desc) for name, desc in _CONNECTION_SCAN_CLIS.items() if shutil.which(name)]
    print("# Connection scan")
    print(f"# platform: {sys.platform}")
    print()
    reachable = [(name, scope) for name, scope in mcp if scope != "other folder"]
    elsewhere = [name for name, scope in mcp if scope == "other folder"]
    print("## MCP servers (reachable from this space)")
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
        print("  A working access the user already has: reuse it for this space, do not build a second one.")
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
# copy of a fact that lives above them, and the copy fell behind: `workbench/` became a space root and
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
    f"/{ARCHIVE_DIR}/": "Nothing is written here directly. Use `zanmai.py file archive <path>` from where the file is now, so it keeps its path and can be restored.",
    f"/{TRASH_DIR}/": "Nothing is written here directly. Use `zanmai.py file trash <path>` from where the file is now, so it keeps its path and can be restored.",
}

# The files where something stays true after this session ends. A refusal is wrong here, because
# these files do have to change; what is wrong is changing them without the user. So this list does
# not block, it hands the decision to the host, which stops and shows the user what would be
# written before anything is.
#
# The distinction to the list above is what the user gets out of it. Up there, writing is always the
# wrong move and another command does the job. Down here, writing is sometimes exactly right, and
# only the user knows which time it is.
#
# `user.md` sat in the list above and that was the defect, not the protection: a standing rule in it
# was wrong, the guard refused every attempt to correct it, and the user was told to edit the file
# by hand. A guard that shuts the repair route while the damage route stays open protects nothing.
_HOOK_ASK_TARGETS = {
    f"{USER_FILE}": "the owner file, which holds personalisation and standing rules",
    f"{SYSTEM_DIR}/{ROUTING_FILE}": "the routing table, which decides where incoming material goes",
    f"{SYSTEM_DIR}/{RETENTION_FILE}": "the keeping terms, which decide how long documents stay",
}


def _hook_names_path(text: str, ziel: str) -> bool:
    """Does this call name that space path, absolute or relative?

    Written after the guard was tried in a real space and stayed silent: it matched on a leading
    slash, and a run works from the space root, so it writes `zanmai/memory/general.md` without one.
    The guard would have held against every absolute path and let through the form that actually
    gets typed. What is required instead is that nothing word-like sits directly in front, so
    `myzanmai/user.md` is a different file and stays one.
    """
    return re.search(rf"(?:^|[^\w.\-]){re.escape(ziel)}", text) is not None
_HOOK_ALLOWED_KINDS = set(KIND_FIELDS)




def _guard_refused(payload: dict, guard: str, grund: str) -> None:
    """Write down that a guard turned something away.

    Until no guard left a trace of any kind. The user's own words: "ich habe das Gefuehl,
    dass die Live-Umgebung nicht alles meldet, dass sie so beschaeftigt ist, dass es untergeht." That
    could not be answered, because nothing was written down: a refusal existed only in the session
    that saw it, and reporting it depended on a busy session remembering to. So it goes in the
    activity log, which is the one file written while the work happens, and from there it reaches the
    next briefing on its own.

    Never fails loudly. A guard that cannot write its note still has to make its decision.
    """
    _guard_notiz(payload, guard, "refused", grund)


def _guard_notiz(payload: dict, guard: str, art: str, grund: str) -> None:
    """One line in the activity log for a guard that fired. Never fails loudly."""
    try:
        start = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or "."
        space = _find_space_root(Path(start))
        if space is None:
            return
        _append_activity_log(space, guard, f"{art}: {' '.join(str(grund).split())[:300]}")
    except Exception:  # noqa: BLE001 -- a note that cannot be written never blocks the decision
        return


_LAST_PAYLOAD: dict = {}


def _hook_read_payload() -> dict:
    """Read the tool-call payload Claude Code passes on stdin. Returns empty
    dict on parse error so the hook never blocks because of a malformed pipe.

    The payload is kept because stdin can only be read once, and the refusal note written after the
    guard returns needs the working directory in it to find the space."""
    global _LAST_PAYLOAD
    # A hook is given its payload on a pipe that closes. Anywhere else stdin may be open with
    # nothing on it and no end of file coming, and a plain `.read()` there waits for ever: the hook
    # runs before every session start, so that is a session that never begins. `isatty()` alone does
    # not cover it, because an inherited pipe is not a terminal and still never closes. Caught by the
    # test suite on, which hung on exactly this the first time the payload was read
    # unconditionally. So: wait a moment for data to appear, and treat silence as "no payload".
    _LAST_PAYLOAD = {}
    try:
        import select
        strom = sys.stdin
        if strom is None:
            return _LAST_PAYLOAD
        # An in-memory stand-in (`io.StringIO`, which the tests substitute) is an `io.IOBase` like
        # any other but has no descriptor to wait on, and asking for one raises. Ask, and where the
        # answer is no, just read: such a stream ends the moment it is empty and cannot block.
        try:
            fd = strom.fileno()
        except Exception:
            fd = None
        if fd is not None:
            try:
                bereit, _, _ = select.select([strom], [], [], 2.0)
            except (OSError, ValueError):
                return _LAST_PAYLOAD
            if not bereit:
                return _LAST_PAYLOAD
        roh = strom.read()
        _LAST_PAYLOAD = json.loads(roh) if roh.strip() else {}
    except (json.JSONDecodeError, OSError, ValueError, AttributeError, TypeError):
        _LAST_PAYLOAD = {}
    return _LAST_PAYLOAD


def _hook_nein(text: str) -> int:
    """Turn a call away without dressing it as a crash, and return its exit code.

    A guard that has to refuse still does not have to look like a failure. Written to stderr with a
    non-zero exit, a refusal reaches the person as a red block of error text for something the run
    can put right by itself in the next breath, and it did: an ordinary handover to a specialist
    showed up as twenty red lines while the second attempt went through a moment later. The host
    reads this off stdout instead, stops the call the same way, and shows the reason as a note.

    Kept apart from `_hook_frage` on purpose. That one hands the decision to the user, where they
    are the only one who can make it. This one makes the decision and says why, where there is
    nothing for them to decide.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": text,
    }}))
    return 0


def _hook_frage(text: str) -> int:
    """Put a guard's finding to the user as a question rather than a wall, and return its exit code.

    A wall teaches how to get around it; a question teaches why. These guards catch a move that is
    usually the wrong one and now and then exactly right, and the person at the keyboard is the only
    one who knows which it is this time. Three guards stay hard, because no later yes repairs what
    they catch: writing into somebody else's system, deleting, overwriting a distribution file.

    The host reads this off stdout and asks; the exit code stays 0, since a non-zero one is the
    refusal this is replacing.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": text,
    }}))
    return 0


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
        return _hook_frage(
            f"checkbox-guard: this {tool} on {rel} is {was}: {beispiel}. A task line rarely belongs "
            f"in a file edit. Asked for one, `zanmai.py task add --text ... [--file ...] "
            f"[--due YYYY-MM-DD]` writes it and `task done` ticks it off. Not asked for one: an "
            f"obligation you worked out goes in the reply as a sentence, something still owed goes "
            f"on a work object via `zanmai.py work`. Say yes where the line is the user's own text."
        )
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
    of them, so such a file would always read as clean. Found in practice: a
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
    written, with `inbox/` exempt because that is where the user's own material arrives.
    """
    datei = Path(file_path)
    if datei.suffix.lower() in (".md", ".markdown"):
        return _hook_authored_by_ai(text, datei)
    if f"/{INBOX_DIR}/" in f"/{file_path}":
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
    takes. Until it took a markdown file, written by Write or Edit, carrying frontmatter
    that said the AI wrote it, and all three had to hold. A finished slide with a dash-sentence on it
    proved how little that covers: the text came out of a JSON content file (not markdown, no
    frontmatter possible) and reached the deck through a Python build script (Bash, not Write). Each
    of the three conditions on its own was enough to make the guard silent, which is the same failure
    `library-check-guard` had before 0.3.5, a guard bound to a tool rather than to the moment the
    decision is made. So: every content file type, frontmatter required only where a file can carry
    it, and a Python build resolving into a `workbench/<slug>/` bundle read as what it is, a write.

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
        # which is what the dash pattern needs. Found in practice: `--text "Wir schaffen -"` was
        # silent because the dash was followed by a quote mark, so neither a space nor a line end
        # closed it, and that is the same end-of-string construction the 0.3.6 fix was built for.
        dazu = [z for z, gescannt in ((z, _hook_command_prose(z)) for z in command.splitlines())
                if _HOOK_EM_DASH in gescannt or _HOOK_EN_DASH_SENTENCE.search(gescannt)]
        if not dazu:
            return 0
        return _hook_frage(
            f"prose-guard: {len(dazu)} line(s) of the text this writes use a dash as sentence "
            f"punctuation. First: {' '.join(dazu[0].split())[:140]}. Finishing the thought or "
            f"splitting it into two sentences reads better. A hyphen inside a compound word and a "
            f"number range keep their dash, and a quotation keeps whatever it came with."
        )

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
        teile = [f"prose-guard: {tool} on {rel}."]
        if dazu:
            teile.append(f"{len(dazu)} line(s) use a dash as sentence punctuation. First: "
                         f"{dazu[0][:140]}. Finishing the thought or splitting it in two reads "
                         f"better; a compound word and a number range keep their dash.")
        if dazu_real:
            zeile, grund = dazu_real[0]
            teile.append(f"{len(dazu_real)} line(s) read as generic phrasing or a leftover "
                         f"placeholder. First: {zeile[:140]} [{grund}]. Say the concrete thing, or "
                         f"fill in the real value.")
        teile.append("The rest of the content is fine. Say yes where the wording is quoted or the "
                     "user's own.")
        return _hook_frage(" ".join(teile))
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

    # The fields a kind actually requires, not just that it has a kind at all. `KIND_FIELDS` has
    # carried them since the schema existed and nothing read them: the guard checked `kind` and
    # `slug` and passed everything else, while `CLAUDE.md` told the user it enforced the required
    # fields. A rule that is announced and not applied is worse than one that is absent, because
    # nobody goes looking for the gap.
    #
    # Only on a bundle's main file. A member inside the bundle carries the bundle from where it
    # lies, and demanding a goal on every note in a focus bundle would make the bundle unusable
    # for anything but its own hub.
    pflicht = KIND_FIELDS.get(kind, {}).get("required", ())
    if pflicht and Path(file_path).stem == Path(file_path).parent.name:
        fehlt = [f for f in pflicht if not str(fm.get(f, "")).strip()]
        if fehlt:
            print(f"kind-required: refusing {payload.get('tool_name')} on {rel}. A `{kind}` bundle's "
                  f"main file carries {', '.join(pflicht)}; missing: {', '.join(fehlt)}.",
                  file=sys.stderr)
            return 2
    return 0


# A shell command that writes says so somewhere in its own text. Reading is left alone: a guard that
# stops `cat` and `rg` on a protected file is a guard the user clicks away twenty times a day, and a
# warning that appears too often stops being read.
# Two things that look like a redirect and write nothing: sending output to the bit bucket, and
# pointing one channel at another (`2>&1`, `>&2`). Both sit at the end of ordinary reads, so both
# come out of the text before anything goes looking for a target. The first form was missing when
# this was written and held the command every session opens with for a write; the second was found
# the same day by running the guard against the shapes a shell actually produces.
_HOOK_SHELL_NO_TARGET = re.compile(r"(&|\d)?>>?\s*(/dev/null|&\s*\d|&\s*-)")
# A redirect with a target, plus the commands that write without one. Deliberately not anchored to
# `echo` or `printf` with anything in between: a pattern that allowed any run of characters between
# the word and the arrow reached across `&&` into the next command, so a read that merely started
# with an echo and ended with a redirect of its errors was held for a write to the file it read.
# Two questions, not one, because they need different text. A redirect is shell syntax and can never
# stand inside quotes, so it is looked for with the quoted spans taken out. Everything else is a
# command word or an API call whose arguments ARE quoted, and taking the quotes out would blind it:
# `open('/v/zanmai/user.md','w')` inside a here-document is a write, and the mode flag it is
# recognised by sits in quotes.
_HOOK_SHELL_REDIRECT = re.compile(r">>?\s*\S")
_HOOK_SHELL_WRITES = re.compile(
    r"\btee\b|\bsed\s+-i|\bmv\b|\bcp\b|\btouch\b|\bdd\b|"
    r"write_text|open\([^)]*['\"][aw]",
    re.I,
)


_HOOK_ZITATE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _hook_shell_writes(text: str) -> bool:
    """Does this shell call write anything, or does it only read.

    One function rather than two patterns every caller has to combine correctly, because that
    combination going wrong is the same failure in a new place.

    Quoted spans come out first, and that is not tidiness: a shell redirect can never sit inside
    quotes, but a greater-than can, and does. `awk 'NR>1 && /^### Step/{p=1}' file` reads a file and
    was refused as a write to it, because `>1` looked like a redirect. The same shape hits every
    comparison, every arrow in a message and every regexp with a bracket. What is inside quotes is
    an argument, not a target.
    """
    ohne_zitate = _HOOK_ZITATE.sub(" ", text)
    if _HOOK_SHELL_REDIRECT.search(_HOOK_SHELL_NO_TARGET.sub(" ", ohne_zitate)):
        return True
    return bool(_HOOK_SHELL_WRITES.search(text))


# How many standing rules the general memory may hold, and how long each may be. Both halves are
# needed: a cap on the count alone is walked around by hanging the next case onto an existing rule,
# which is how one entry there grew seven clauses out of seven incidents and stopped being read.
#
# Ten because a set nobody can hold in their head at the moment of acting works like no set at all,
# and it still costs the user their time and leaves the impression the matter was dealt with.
MEMORY_RULE_CAP = 10
# Measured in characters, not in lines, and that is the point. The rule this cap exists for sits on
# a single line of markdown and runs 1655 characters: seven clauses from seven incidents, each one
# hung onto the one before it. Counting lines would have called that one rule and passed it.
MEMORY_RULE_MAX_CHARS = 300


def _memory_rules(space: Path) -> list[str]:
    """One entry per standing rule in the general memory, the text as written.

    A rule is a top-level list item under the sections that say how things are done. Open threads
    and decisions are not counted: they describe a situation, they do not tell a later session what
    to do.
    """
    datei = space / MEMORY_DIR / "general.md"
    if not datei.is_file():
        return []
    regeln: list[str] = []
    zaehlt = False
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        if zeile.startswith("## "):
            zaehlt = zeile[3:].strip().lower() in ("preferences", "lessons")
            continue
        if not zaehlt:
            continue
        if zeile.startswith("- "):
            regeln.append(zeile[2:].strip())
        elif regeln and zeile.strip():
            regeln[-1] = f"{regeln[-1]} {zeile.strip()}"
    return regeln


def _memory_rule_note(space: Path) -> str:
    """What the user needs in order to decide, when the write is a rule in the general memory."""
    regeln = _memory_rules(space)
    if not regeln:
        return ""
    lang = sorted((r for r in regeln if len(r) > MEMORY_RULE_MAX_CHARS), key=len, reverse=True)
    satz = f" The file holds {len(regeln)} standing rule(s) today."
    if len(regeln) >= MEMORY_RULE_CAP:
        satz += (f" That is at or over the cap of {MEMORY_RULE_CAP}, so a new one means another has "
                 f"to go, and which one is your call.")
    if lang:
        satz += (f" {len(lang)} of them run past {MEMORY_RULE_MAX_CHARS} characters, which is how a "
                 f"cap gets walked around: the next case is hung onto an existing rule instead of "
                 f"counted. The longest is {len(lang[0])} characters and starts "
                 f"'{lang[0][:60]}'.")
    return satz


# The script's own invocation, in every shape it is actually run in: bare relative, absolute, or
# via the `$CLAUDE_PROJECT_DIR` the hook wiring itself uses, quoted or not. Matched so it can be
# taken out of the guard text before the never-do and ask-first checks run, because invoking the
# script is a read of it, never a write into it.
_SCRIPT_INVOCATION_RE = re.compile(r'''["']?[^\s"']*zanmai/system/scripts/zanmai\.py["']?''')


# Where a path in a command is not a path in this space. Both of these cost a real interruption in
# a live space: a command that rewrote a file on the user's own server was stopped and put to them
# as a write to the routing table, because the text being sent over named that table.
#
# The guards below protect paths inside this space. A path that reaches another machine, or that is
# being written into a file as its content, is neither, and reading it as a target is the same
# mistake three guards have now made: taking the whole command line for the thing it acts on.
_FREMDER_RECHNER_RE = re.compile(
    r"\b(?:ssh|scp|rsync|sftp)\b(?:\s+-\S+)*\s+\S+"     # the command and where it goes
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'|\S+))*",             # and everything it hands over
)

# A here-document is the body of a command, and whether that body is a target depends on the
# command. `python3 - <<EOF` runs it here, so a path inside it is written here, and that is the case
# the never-do list exists for. `cat > file <<EOF` and anything piped to another machine write the
# body down as text; the paths in it are words in a file, not writes.
_LOKALER_INTERPRETER_RE = re.compile(r"(?:^|[|;&]\s*)(?:python3?|bash|sh|zsh|node|perl|ruby)\s+-?\s*<<")
_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\1", re.DOTALL)


def _ohne_fremden_rechner(text: str) -> str:
    """The command with everything that runs on, or is sent to, another machine taken out."""
    return _FREMDER_RECHNER_RE.sub(" ", text)


def _ohne_inhalts_heredoc(text: str) -> str:
    """The command with every here-document body removed that is written down rather than run."""
    if _LOKALER_INTERPRETER_RE.search(text):
        return text
    return _HEREDOC_RE.sub(" ", text)


def _hook_guard_text(payload: dict) -> str:
    """Everything in this call that could name a path, whatever the tool is called.

    The old version asked whether the tool was `Write` or `Edit`. That is a question about how
    something is written, and the answer decided whether a file was protected. A `python3 - <<EOF`
    over Bash writes the same file and was never asked. So the question is now what the call says,
    not which tool it arrived through.
    """
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return ""
    teile = [str(ti.get(k) or "") for k in ("file_path", "command", "notebook_path", "path")]
    text = " ".join(t for t in teile if t).replace("\\", "/")
    text = _ohne_fremden_rechner(text)
    text = _ohne_inhalts_heredoc(text)
    # A here-document body is deliberately NOT taken out here, though it is content rather than a
    # target. It is also how a write gets past a guard that only reads the command line:
    # `python3 - <<EOF` with the path inside the body is the exact case this guard was written for,
    # and stripping bodies let it through again. What separates content from target is the shape of
    # the path, and that is handled where the never-list is matched.
    # The script's own invocation path names `zanmai/system/` too, and every Bash call that both
    # writes something and runs the script this way (the normal way) put that path in front of
    # every never-do check: a plain `... > zanmai/logs/today.md` alongside
    # `zanmai/system/scripts/zanmai.py` in the same command line was refused as a write into the
    # distribution folder, because the guard reads the whole line rather than the write target.
    # Running the script is never itself a write there, so its own path is stripped before the
    # never-do and ask-first checks look at what is left.
    return _SCRIPT_INVOCATION_RE.sub(" ", text)


# A call to this script, written into a sentence: the command, then sub-commands and options in
# the order they were typed. A placeholder or a word of prose ends the call rather than breaking it.
_SELF_CALL = re.compile(
    r"zanmai\.py\s+([a-z][a-z0-9-]*)((?:\s+(?:[a-z][a-z0-9-]*|--[a-z][a-z0-9-]*))*)")


def _unknown_in_call(aufruf: str) -> str:
    """The first part of a call to this script that does not exist, or "" if it all does.

    Asked of the running script's own parser rather than of a list, because a list agrees with
    whoever wrote it and this has to agree with what a command will actually accept.
    """
    teile = aufruf.split()
    if not teile:
        return ""
    pfad: list[str] = []
    for wort in teile:
        if wort.startswith("--"):
            break
        pfad.append(wort)
    # Sub-commands, longest first: a word of prose after a real command is not an error, an unknown
    # word in place of a real sub-command is. `--help` on the shorter path settles which it is.
    while pfad:
        lauf = subprocess.run([sys.executable, str(Path(__file__).resolve()), *pfad, "--help"],
                              capture_output=True, text=True, timeout=30)
        if lauf.returncode == 0:
            hilfe = lauf.stdout
            for wort in teile:
                if wort.startswith("--") and wort not in hilfe:
                    return wort
            return ""
        pfad.pop()
    # Nothing left that the parser knows, so this was a sentence and not a call: "the AI plans,
    # `zanmai.py` does the writes" must not stop a write. A guard that fires on prose is one the
    # user learns to route around, and a typo in a command name is caught where the shipped text is
    # checked, not here.
    return ""


def _stale_calls(text: str) -> list[str]:
    """Every call to this script in that text that names something the script does not have.

    The reason this sits in the guard and not in a check somebody runs: the text goes into a file
    that stays true after this session, and no update ever touches those files again. A command
    written from memory into a standing rule is read back as an instruction for years. One was:
    a flag that never existed in any version, in a rule that ran at every session start.
    """
    gefunden: list[str] = []
    for m in _SELF_CALL.finditer(text):
        aufruf = f"{m.group(1)}{m.group(2)}"
        try:
            fehlt = _unknown_in_call(aufruf)
        except (OSError, subprocess.SubprocessError):
            return []  # cannot ask the parser, so nothing is claimed about the text
        if fehlt and fehlt not in gefunden:
            gefunden.append(f"`zanmai.py {aufruf.strip()}` names {fehlt}, which does not exist")
    return gefunden


def cmd_hook_permission_guard(args: argparse.Namespace) -> int:
    """PreToolUse hook: hard-block the never-do bucket, and put the durable files to the user.

    Two lists, two behaviours, and the difference is what the user gets out of it.
    `_HOOK_NEVER_TARGETS` is refused, because writing there is always the wrong move and another
    command does the job. `_HOOK_ASK_TARGETS` is handed to the host, which stops and shows the user
    what would be written, because those files do have to change and only the user knows when.

    Both lists are checked against everything the call names, not against the name of the tool. A
    guard that asks how something is written protects the path only from the tools that announce
    themselves.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    tool = payload.get("tool_name", "")
    text = _hook_guard_text(payload)
    if not text:
        return 0
    ist_shell = tool == "Bash"
    # A shell call is only interesting where it writes; a Write or an Edit always writes.
    schreibt = (not ist_shell) or _hook_shell_writes(text)

    # With the closing slash kept, so the folder is matched as a folder. Without it, `archive` and
    # `trash` are ordinary words: a command mentioning the archive in a comment, a filename, or a
    # sentence it writes was refused as a write into `archive/`. Three times now a guard has read
    # the whole command line as if it were the write target, so the shape of the match is the fix,
    # not another exception bolted on.
    for target, advice in _HOOK_NEVER_TARGETS.items():
        if _hook_names_path(text, target.strip("/") + "/") and schreibt:
            print(f"permission-guard: refusing {tool} on '{text.strip()[:120]}'. This path is in "
                  f"the never-do bucket. {advice}", file=sys.stderr)
            return 2

    # Before the question of whether this write is wanted comes the question of whether what it says
    # is true. A rule in one of these files outlives every session and no update corrects it, so a
    # command typed from memory is read back as an instruction for as long as the space exists.
    if schreibt and not ist_shell:
        inhalt = str((payload.get("tool_input") or {}).get("content")
                     or (payload.get("tool_input") or {}).get("new_string") or "")
        if inhalt and any(_hook_names_path(text, ziel) for ziel in _HOOK_ASK_TARGETS):
            for befund in _stale_calls(inhalt):
                print(f"permission-guard: refusing {tool}. {befund}. Ask the command itself with "
                      f"`--help` and write what it answers; a rule in this file is read back for "
                      f"years and no update corrects it.", file=sys.stderr)
                return 2
        # A rule naming a specific date or a specific running instance is a note about a moment,
        # not a standing rule, and general.md exists to hold only what still applies without
        # knowing when or where it was written. `_lage_statt_regel` already catches this by
        # wording, but only at session-close, after the write already reached the user as a
        # decision to click through by hand, more than once in one evening before this existed.
        if inhalt and _hook_names_path(text, "general.md"):
            klein = inhalt.lower()
            if (any(w in klein for w in _LAGE_WOERTER)
                    or _MEMORY_RULE_DATE_RE.search(inhalt)
                    or _MEMORY_RULE_INSTANCE_RE.search(inhalt)):
                print(f"permission-guard: refusing this write to general.md. It names a specific "
                      f"date or a specific running instance, which makes it a note about a moment "
                      f"rather than a standing rule. A dated correction belongs in the session "
                      f"record or the activity log; general.md holds only what still applies "
                      f"without knowing when or where it was written.", file=sys.stderr)
                return 2

    for target, was in _HOOK_ASK_TARGETS.items():
        if _hook_names_path(text, target) and schreibt:
            zusatz = ""
            if target.endswith("general.md"):
                wurzel = _session_find_space_root() or Path.cwd()
                try:
                    zusatz = _memory_rule_note(wurzel)
                except OSError:
                    zusatz = ""
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"permission-guard: this writes {was}. It stays true after this session ends, "
                    f"so it is the user's call and not the run's. The full text that would be "
                    f"written is in the call above.{zusatz} Three ways out: let it through as it "
                    f"stands, refuse it and nothing is written, or refuse it and say what should be "
                    f"written instead."),
            }}, ensure_ascii=False))
            return 0

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return 0

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
# in every space and a sub-command of this very script, so matching it anywhere in the line refused
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


# What an operating system leaves lying around. None of it is anybody's material, none of it is
# worth a trip through the space's trash, and refusing to remove it refuses the whole chained
# command it sits in: a copy that only added files was turned down because it tidied up two
# `.DS_Store` afterwards, and the error text then offered `file trash`, which would have filed
# them. The guard exists for the user's material, and this is not it.
_SYSTEM_LITTER = (".DS_Store", "Thumbs.db", "desktop.ini", ".localized", "__pycache__", ".pyc")


def _nur_systemmuell(argumente: list[str]) -> bool:
    """Whether a removing command names nothing but operating-system litter.

    False on an empty argument list, on a bare flag list, and on anything with a wildcard in it: a
    `rm -rf *` that happens to sit in a folder of `.DS_Store` is still a command nobody should be
    able to slip past by naming the pattern rather than the file.
    """
    ziele = [a for a in argumente if not a.startswith("-")]
    if not ziele:
        return False
    for ziel in ziele:
        if any(z in ziel for z in "*?["):
            return False
        name = Path(ziel).name
        if name not in _SYSTEM_LITTER and not name.endswith(".pyc"):
            return False
    return True


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
                if _nur_systemmuell(tokens[i + 1:]):
                    continue
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


def _video_job_dir(space: Path, slug: str) -> Path:
    """Working area for one job. Under temp: intermediates are volatile by design and the
    retention sweep clears them, while what the user keeps goes to their own bundle."""
    d = space / SCRATCH_DIR / "video" / slug
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


def _video_probe(space: Path, path: Path) -> dict:
    """What the file actually is, read from the file. Never assumed, never rounded: a frame rate
    guessed as 24 where the source is 24000/1001 drifts a frame every forty seconds."""
    ffprobe = _tool_path(space, "ffprobe") or _tool_path(space, "ffmpeg")
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    info = _video_probe(space, src)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    job = _video_job_dir(space, args.slug)
    ziel = job / f"{src.stem}.words.json"
    if ziel.is_file() and not args.force:
        d = json.loads(ziel.read_text(encoding="utf-8"))
        print(f"ok: already transcribed, {len(d.get('words', []))} word(s) at "
              f"{ziel.relative_to(space)} (--force to redo)")
        return 0

    ffmpeg = _tool_path(space, "ffmpeg")
    whisper = _tool_path(space, "whisper")
    model = _whisper_model(space)
    fehlt = []
    if not ffmpeg:
        fehlt.append("ffmpeg, which turns the recording into what the recogniser reads")
    if not whisper:
        fehlt.append("whisper-cli, the recogniser itself")
    if not model:
        fehlt.append("a model in zanmai/runtime/whisper/. Fetch it with `zanmai.py tools ensure "
                       "whisper-model`, one file of about 1.6 GB over HTTPS, once. An interrupted "
                       "fetch resumes where it stopped")
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
          f"at {ziel.relative_to(space)}")
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
    space = Path(args.space).resolve()
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
    space = Path(args.space).resolve()
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
    space = Path(args.space).resolve()
    blatt = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
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
    probe = _video_probe(space, Path(quellen[0]).expanduser())
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
                for g in (_video_probe(space, Path(q).expanduser()) for q in quellen)}
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
    raus = _video_probe(space, ziel)
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
    space = Path(args.space).resolve()
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
    space = Path(args.space).resolve()
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
        return _burn_captions(space, Path(args.burn).expanduser(),
                              Path(args.burn_out) if args.burn_out else None, zeilen, args)
    return 0


def _burn_captions(space: Path, quelle: Path, ziel: Path | None, zeilen: list[dict],
                   args: argparse.Namespace) -> int:
    """Draw the captions as images and lay them over the picture.

    Not through a subtitle filter, deliberately. Whether ffmpeg can draw text at all depends on how
    that particular copy was built, and the common builds cannot: no subtitle renderer, no text
    filter. Detected on the machine this was written on, where both are absent. Drawing the lines
    ourselves works on every build, gives the brand's own typeface and box, and needs one image per
    line rather than per word, which is what keeps it renderable at length.
    """
    ffmpeg = _tool_path(space, "ffmpeg")
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
    info = _video_probe(space, quelle)
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

    ordner = _video_job_dir(space, args.slug) / "captions"
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    if args.format not in VIDEO_FORMATS:
        print(f"fail: unknown format {args.format}, expected one of "
              f"{', '.join(VIDEO_FORMATS)}", file=sys.stderr)
        return 1
    info = _video_probe(space, src)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
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
        dauer = _video_probe(space, src).get("duration", 0.0)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ziel = Path(args.out).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    info = _video_probe(space, src)
    breite, hoehe = int(info.get("width") or 1920), int(info.get("height") or 1080)
    fps = info.get("fps_exact") or "25/1"
    zwischen = _video_job_dir(space, args.slug)

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
        hat_ton = bool(_video_probe(space, quelle).get("audio"))
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
          f"{_spoken_length(_video_probe(space, ziel).get('duration', 0.0))} at {ziel}")
    return 0


def cmd_video_chapters(args: argparse.Namespace) -> int:
    """Chapter marks from the transcript, as a list to paste and as metadata in the file."""
    space = Path(args.space).resolve()
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("fail: needs the image library: `tools ensure pillow`.", file=sys.stderr)
        return 1
    dauer = _video_probe(space, src).get("duration", 0.0)
    raus = Path(args.out).expanduser() if args.out else _video_job_dir(space, args.slug) / "thumbs"
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
    space = Path(args.space).resolve()
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
    space = Path(args.space).resolve()
    a, b = Path(args.a).expanduser(), Path(args.b).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not a.is_file() or not b.is_file():
        print("fail: need ffmpeg and both files", file=sys.stderr)
        return 1
    job = _video_job_dir(space, args.slug)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("fail: needs the image library: `tools ensure pillow`.", file=sys.stderr)
        return 1

    info = _video_probe(space, src)
    dauer = info.get("duration") or 0.0
    if dauer <= 0:
        print("fail: cannot read the duration", file=sys.stderr)
        return 1
    arbeit = _video_job_dir(space, args.slug)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    ffmpeg = _tool_path(space, "ffmpeg")
    info = _video_probe(space, src)
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
        arbeit = _video_job_dir(space, args.slug or "brief")
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
        ns = argparse.Namespace(space=str(space), file=str(probe_quelle), slug=args.slug,
                                language=args.language, lexicon=None, dtw_preset=None, force=False)
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_video_transcribe(ns)
        wd = _video_job_dir(space, args.slug) / f"{probe_quelle.stem}.words.json"
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
        if not _detect_tool(space, tid, spec, _current_os()).get("present"):
            fehlend.append(tid)
    if fehlend:
        print(f"\nmissing for parts of the pipeline: {', '.join(fehlend)}")
        print("  Cutting, captions and sound need the first four. Motion graphics need the last "
              "two, and without them that step is not available at all: say so and offer to fetch "
              "them, rather than drawing frames by hand and calling it done.")

    # What the piece would be dressed in. Asked here because it is the question that gets skipped:
    # a run that finds nothing quietly picks its own colours and typeface, and the user first sees
    # the choice in a finished render.
    marken = sorted(d.name for d in (space / DESIGN_DIR).iterdir()
                    if d.is_dir()) if (space / DESIGN_DIR).is_dir() else []
    print()
    if marken:
        print(f"brand(s) available: {', '.join(marken)}")
    else:
        print("no brand set in this space. Anything visible (captions, a logo, an opening, a "
              "graphic) has no colours, typeface or mark to take, so ask before making them up: "
              "which brand, or which colours and typeface, or explicitly plain.")

    # One picture, not a handful of frames. A composite of filmstrip, loudness and words says where
    # the scenes change, where it is quiet and roughly what about, at the cost of a single image.
    # Separate frames cost that much each, and twenty-four of them cost more than the edit.
    if ffmpeg:
        ns = argparse.Namespace(
            space=str(space), file=str(src),
            words=str(_video_job_dir(space, args.slug) / f"{probe_quelle.stem}.words.json")
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg or not src.is_file():
        print("fail: need ffmpeg and an existing file", file=sys.stderr)
        return 1
    info = _video_probe(space, src)
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
    space = Path(args.space).resolve()
    src = Path(args.file).expanduser()
    ffmpeg = _tool_path(space, "ffmpeg")
    if not ffmpeg:
        print("fail: ffmpeg missing: `tools ensure ffmpeg`.", file=sys.stderr)
        return 1
    if not src.is_file():
        print(f"fail: no such file: {src}", file=sys.stderr)
        return 1
    raus = Path(args.out).expanduser() if args.out else _video_job_dir(space, args.slug) / "frames"
    raus.mkdir(parents=True, exist_ok=True)
    zeiten = [float(x) for x in args.at.split(",")] if args.at else []
    if not zeiten:
        dauer = _video_probe(space, src).get("duration", 0.0)
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


# The wait block from operating-principles 12, in the shapes it is actually written in. Matched on
# the pair rather than on `sleep` alone: a one-off `sleep 2` between two calls is nobody's problem,
# a loop that polls for a signal file is the thing that turns a background run into twelve minutes
# of nothing.
_PARK_SCHLEIFE = re.compile(r"\b(?:until|while)\b[^\n]*\bsleep\b|\bsleep\b[^\n]*\b(?:done|until)\b",
                            re.IGNORECASE)


def cmd_hook_park_guard(args: argparse.Namespace) -> int:
    """PreToolUse Bash hook: refuse a wait loop inside a background expert.

    Parking is for a run the user can see. A background expert's report reaches nobody until it
    returns, so a question it writes down and then waits on is a question nobody has been shown:
    one such run spent twelve minutes and tens of thousands of tokens on a five-second job, waiting
    for an answer to something that sat on a work object while the user watched a spinner.

    The check is on `agent_id`, which the host sets only inside a subagent. The conversation itself
    keeps the wait block, because there the user is right there and can answer it.
    """
    payload = _hook_read_payload()
    if not payload:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    if not payload.get("agent_id"):
        return 0   # the conversation itself may park; principle 12 is written for it
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not _PARK_SCHLEIFE.search(command):
        return 0
    print(
        "park-guard: refusing this wait loop. You are a background run, so nothing you write is in "
        "front of the user while you wait, and waiting is indistinguishable from hanging. Write "
        "where you stand, put the open point in your result, and return now. Whoever dispatched you "
        "asks the user and dispatches again with the answer. Parking is for the conversation "
        "itself, which is what operating-principles 12 describes.",
        file=sys.stderr,
    )
    return 2


def cmd_hook_delete_guard(args: argparse.Namespace) -> int:
    """PreToolUse Bash hook: refuse to delete anything in the space.

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
    # A move out of the inbox is the same act as throwing it away, and `zanmai.py file trash`
    # is where the condition on that lives: content in the space first, or the user's own words.
    # Left out, the whole gate is one `mv` wide. `cp` is not caught on purpose: it leaves the
    # original lying, so nothing is lost and the next session start reads it again.
    if _MOVE_VERB_RE.search(command) and _IMPORT_PATH_RE.search(command):
        print(
            f"delete-guard: refusing this command. It moves something out of `{INBOX_DIR}/` by hand, "
            f"which skips the check that the material actually arrived somewhere. Where it belongs "
            f"in the space, move it with `zanmai.py file archive --path <path>` or file it where it "
            f"goes. Where it is done with, file the content first, then `zanmai.py file trash --path "
            f"<path> --filed-to <where it landed>`.",
            file=sys.stderr,
        )
        return 2

    treffer = _delete_verb_in(command)
    if not treffer:
        return 0
    if any(hint in command for hint in _DELETE_ALLOWED_HINTS):
        return 0
    # Two different situations reach this point and they need two different answers. Answering both
    # with the space's trash sent a run that only wanted to clear its own unpacked archive off to
    # `file trash`, which is for the user's material and wrong for a scratch directory. It then went
    # looking for a way around instead of moving its work to where clearing up is allowed.
    print(
        f"delete-guard: refusing this command, it removes things and nothing in Zanmai removes "
        f"things. To give a kept document a better name or put it in another section, that is "
        f"`zanmai.py archive rename` and `zanmai.py archive move`, which take the search index "
        f"along; a hand-rolled move leaves the index pointing at where the file used to be. "
        f"If this is the user's material and it is meant to go, use `zanmai.py file trash --path "
        f"<path>`, which keeps the file and its original path so `zanmai.py file restore` can bring "
        f"it back. If it "
        f"is your own working material, it does not belong outside the space: put intermediates in "
        f"`{SCRATCH_DIR}/<task>/`, where clearing up is permitted and the retention sweep clears "
        f"what is left after {SCRATCH_RETENTION_DAYS} days. That sweep is the only thing that really "
        f"deletes. Found: {treffer!r}.",
        file=sys.stderr,
    )
    return 2


# `mv` run as a command, with a path in the drop area somewhere on the line. Deliberately blunt in
# the same way the delete verbs are: working out which of the two paths is the source means parsing
# shell, and a guard that parses shell can be talked around. A refusal costs a sentence.
_MOVE_VERB_RE = re.compile(r"(?:^|[\s;&|(])(?:sudo\s+|command\s+|env\s+)*mv\b")
_IMPORT_PATH_RE = re.compile(r"(?:^|[\s'\"=/])" + INBOX_DIR + r"/")

_PPTX_SAVE_RE = re.compile(r'\.save\(\s*["\']([^"\']+\.pptx)["\']')
_PYTHON_RUN_RE = re.compile(r"(?:^|[\s;&|])python3?\b")
# A python run that could produce a deck, as opposed to any python run at all. The wide version
# bound every command that mentioned a bundle path anywhere, which in a bundle whose name has
# nothing to do with slides meant a refusal for reading a file or ticking a checkbox off in
# markdown. A guard that fires on work it has no business with gets worked around, and then it
# guards nothing.
#
# Two things still bind, and between them they cover how a deck actually gets written: the command
# names a `.pptx`, or it runs a script that lives inside the bundle, which is where a build script
# sits and whose own `.save()` cannot be seen from here.
_PPTX_HINT_RE = re.compile(r"\.pptx\b|python[-_]pptx|from\s+pptx|Presentation\(", re.IGNORECASE)
# `slide-library.py` is mostly checks, and a check writes nothing. Binding the whole tool held up a
# render because a font folder happened to sit under a bundle path: the folder was a source being
# read from, no deck was written, and pictures are not presentations. Only the subcommands that
# actually produce or alter a deck bind.
_SLIDE_LIBRARY_WRITES = ("build", "fill", "nudge", "swap-image", "keep", "extract", "migrate")
_SLIDE_LIBRARY_RE = re.compile(r"slide[-_]library\.py\s+(?:[-\w/.]*\s+)*?(" +
                               "|".join(_SLIDE_LIBRARY_WRITES) + r")\b")
# Python handed a script file, as opposed to python handed text. A build script's own `.save()`
# cannot be seen from out here, so running one binds; a `-c` snippet or a heredoc carries its whole
# behaviour in the command, where the deck hint above can see it. That is the line between a build
# and somebody ticking a checkbox off in a markdown file with a throwaway script.
_PY_SCRIPT_RUN_RE = re.compile(r"(?:^|[\s;&|])python3?\s+(?!-)([^\s;&|]*\.py)\b")
# The space's own CLI never writes a deck, whatever it is asked to do, and neither does asking any
# script for its help text. Binding those meant a plain `zanmai.py journal --help` was refused
# because the shell happened to stand in a bundle called `ci`, a word that turns up constantly in
# marketing work. A guard has to be able to tell a build from a question.
def _ohne_heredoc(command: str) -> str:
    """The command with every heredoc body removed, so prose inside one is not read as a command."""
    return re.sub(r"<<-?\s*['\"]?(\w+)['\"]?\n.*?\n\1", " ", command, flags=re.DOTALL)


_NIE_DECK = ("zanmai.py", "image-edit.py", "design-check.py", "document.py")
_HILFE_RE = re.compile(r"(?:^|\s)(--help|-h)\b")
# Preceded by start, a slash, a quote or whitespace: a workbench/<slug> path shows up embedded in a
# quoted .save() argument, after a `cd`, or as a bare relative path, not only at a path boundary.
_WORKBENCH_SLUG_RE = re.compile(r"(?:^|[/'\"\s])" + re.escape(WORKBENCH_DIR) + r"/([^/'\"\s]+)")


# A word that shows up in a bundle name but names nothing on its own. Requiring a link on these
# would fire on every second line. Kept deliberately short: only words that are structural in a
# space name, never topic words, because a topic word is exactly what should be linked.
def _library_guard_slug(command: str, space: Path | None = None,
                        cwd: str | None = None) -> str | None:
    """The `workbench/<slug>` bundle a Bash command produces into, or None.

    Two ways to know. The command names the path, which is the case a `cd` or an absolute
    argument covers. Or the command says nothing because the working directory is already
    inside the bundle and every path in it is relative: found on a real run, where
    dropping the `cd` was used as the way past the guard. Reading the working directory closes
    that, and it is the same fact either way.
    """
    match = _WORKBENCH_SLUG_RE.search(command)
    if match:
        return match.group(1)
    # The working directory of the shell that runs the command, which the hook payload carries,
    # never the hook process's own. Found in practice: a hook runs from the project root, so
    # `Path.cwd()` here is always the space root and the whole branch was dead code. That made the
    # 0.3.5 fix for a dropped `cd` ineffective, and it never showed because nothing tested it from
    # inside a bundle.
    hier = Path(cwd) if cwd else Path.cwd()
    # The root is searched from there too. Searching from the hook process's own directory found
    # the wrong space, or none, whenever the shell stood somewhere else.
    wurzel = space if space is not None else _find_space_root(hier)
    if wurzel is None:
        return None
    try:
        rel = hier.resolve().relative_to(wurzel.resolve())
    except (ValueError, OSError):
        return None
    teile = rel.parts
    if len(teile) >= 2 and teile[0] == WORKBENCH_DIR:
        return teile[1]
    return None


def cmd_hook_library_check_guard(args: argparse.Namespace) -> int:
    """PreToolUse Bash hook: refuse to save a `.pptx` into a `workbench/<slug>/` bundle until
    `slide-library.py check <library> --task <slug>` has run at least once for that slug.

    The `powerpoint` skill's library-first order (Match, then Adapt, then Compose, only
    when nothing in the library carries it) lived only as prose, and a live build on
    2026-08-24 went straight to Compose twice without it, which is where that run's whole
    cost went. A rule that has to be repeated in text is the signal that it needs a
    mechanic instead (an earlier lesson), and this is that mechanic. It does not
    judge whether Compose was the right tier, only that the library was actually looked
    at before the deliverable was written, which is the step that kept getting skipped.

    Two ways a command can produce a `.pptx`: a literal `.save("x.pptx")` inline in the
    Bash command (a one-off `python3 -c ...`), or a call into a separate script file whose
    own `.save(...)` is invisible here. Found on a real run: a `sales-play-bauen.py`
    invocation slipped past the guard entirely, no `.pptx` literal for the old regex to
    find, because the save lived inside the script, not the command line. Any Python run
    that resolves into a `workbench/<slug>/` bundle now binds the same way, whether or not the
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
    if _HILFE_RE.search(command):
        return 0
    # The body of a heredoc is data, not command. It blocked the writing of a findings file that
    # mentioned this very guard, because the prose in it named `.pptx`. Text about a deck is not a
    # deck being written, and a guard that cannot tell the two apart blocks the report about
    # itself.
    command = _ohne_heredoc(command)
    skripte = [Path(m).name for m in _PY_SCRIPT_RUN_RE.findall(command)]
    fremde = [s for s in skripte if s not in _NIE_DECK and s != "slide-library.py"]
    if "slide-library.py" in skripte and not fremde:
        # A slide-library call names a deck almost every time, including when it only measures one.
        # So the file name says nothing here and the subcommand says everything: `fill` writes,
        # `align-check` reads. Letting the `.pptx` decide held up a render for having a font folder
        # under a bundle path.
        baut_deck = bool(_SLIDE_LIBRARY_RE.search(command))
    else:
        baut_deck = bool(_PPTX_HINT_RE.search(command)) or bool(fremde)
    if not baut_deck:
        return 0
    space = _session_find_space_root()
    slug = _library_guard_slug(command, space, cwd=payload.get("cwd"))
    if slug is None:
        return 0
    # Against the space root, never against the working directory. Found on a real run
    # with the shell sitting in the bundle, `Path.cwd()` looked for the marker at
    # `workbench/<slug>/zanmai/temp/<slug>/`, which cannot exist, so a run that had done the check
    # was refused anyway and went looking for a way around a guard that was right in principle.
    checked = (space or Path.cwd()) / SCRATCH_DIR / slug / "library-checked.json"
    if checked.is_file():
        return 0
    return _hook_frage(
        f"library-check-guard: {slug!r} has no record of `slide-library.py check <library> --task "
        f"{slug}` having run. That check prints the brand's own slides, so a matching one can be "
        f"cloned and filled in seconds, which is the cheap tier this save skips past. If nothing in "
        f"the library carries this shape of content, composing from scratch is still the honest "
        f"answer; the check only proves the library was looked at first."
    )


# The label that marks a handover as briefed. Matching on the user's own block rather than on a
# keyword nobody would write by accident is deliberate: the thing being checked for is that the
# user's words were carried over at all, so the check and the content are the same fact.
_BRIEF_MARKER = "What the user said:"

# The same heading in the languages a handover is actually written in, because the rule above this
# one says Steve writes in the user's writing language and a handover is mostly the user's own
# quoted words. A German space therefore wrote "Was der Nutzer gesagt hat", was refused, lost the
# whole assembled dispatch and rebuilt it with an English heading in an otherwise German prompt.
# The guard checks that the user's words were carried over; which language the label is in says
# nothing about whether they were.
_BRIEF_MARKERS = (
    _BRIEF_MARKER,
    "Was der Nutzer gesagt hat",
    "Was der Nutzer sagte",
    "Was der Nutzer gesagt hat:",
)


def _brief_present(prompt: str) -> bool:
    """Whether a handover carries the user's-words block, in any of the labels we accept."""
    klein = prompt.lower()
    return any(m.lower().rstrip(":") in klein for m in _BRIEF_MARKERS)


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

    Writing into the space is reversible and private. Writing into Confluence, a mailbox, a ticket
    system or a repository is neither: colleagues see it, and an undo does not reach them. Hard Rule 3
    says such a write waits for an explicit yes in the same message. That was prose, and prose at this
    point does not hold: a session was asked in the chat where information was missing,
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
            f"outward-guard: this writes into {dienst}, outside the space. Other people see it and an "
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
    the space's own experts left the identical outage one agent name away: a
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
    brief_fehlt = not _brief_present(prompt)
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
        return _hook_nein(
            f"dispatch-guard: this {subagent} handover carries no brief, so it is not sent. "
            f"Put two labelled blocks at the top of the prompt. '{_BRIEF_MARKER}': the "
            f"user's own words, quoted or close to it, nothing added. 'What I concluded:': "
            f"where it lands, which format, how big the job is, form and destination only. "
            f"A fact that sits in the space you go and find; what only the user knows you ask "
            f"now, before the send-off, because the expert runs in the background and has "
            f"nobody to ask. See `{SYSTEM_MATERIAL_DIR}/skills/brief/SKILL.md`.")
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

# How far back the session start reads the journal: the current day and the seven before it.
# There were three of these, one per journal layer, from when the journal had four. The other
# two have not been read by anything since the journal became one layer per day.
_SESSION_DAILY_WINDOW_DAYS = 7

# What the session-start hook may print. The host caps hook output at 10,000 characters and
# replaces anything longer with a 2 KB preview plus a path to a file, without telling the model
# that it is looking at a fragment. The cap is undocumented in the hooks reference and the two
# reports about it (anthropics/claude-code #44086, #70460) are closed as not planned, so this is
# ours to stay under. The budget sits below the cap rather than at it: what the hook prints grows
# with the space, and the margin is what keeps a busy space from silently crossing the line.
_HOOK_OUTPUT_BUDGET = 9000


def _session_find_space_root() -> Path | None:
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


def _session_read_marker(space: Path) -> datetime:
    """Read .last-session-end. Fall back to three days ago."""
    marker = space / MEMORY_DIR / ".last-session-end"
    if marker.exists():
        text = marker.read_text(encoding="utf-8").strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(days=3)


def _session_load_index(space: Path) -> dict | None:
    idx_path = space / MEMORY_DIR / "space-index.json"
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


_SESSION_JOURNAL_WINDOWS = {JOURNAL_DIR: _SESSION_DAILY_WINDOW_DAYS}


def _session_collect_recent_journal(index: dict, space: Path) -> list[dict]:
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
            abs_path = space / path
            if not abs_path.exists():
                continue
            ts = datetime.fromtimestamp(abs_path.stat().st_mtime, timezone.utc)
        if ts >= cutoff:
            matches.append({**entry, "_ts": ts.isoformat(timespec="minutes")})
    matches.sort(key=lambda e: e.get("_ts", ""))
    return matches


def _session_aggregate_tokens(notes: list[dict], space: Path) -> dict[str, int]:
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


def _session_existing_bundle_slugs(space: Path) -> set[str]:
    bundles: set[str] = set()
    for kind in BUNDLE_FOLDERS:
        kind_dir = space / kind
        if not kind_dir.is_dir():
            continue
        for p in kind_dir.iterdir():
            if p.is_dir():
                bundles.add(p.name)
    return bundles


def _session_suggest_bundles(token_counts: dict[str, int], bundles: set[str], top_n: int = 3) -> list[tuple[str, int]]:
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


def _session_known_entities(space: Path) -> dict[str, str]:
    """Map slug -> human label for contacts and top-level bundles, the entities
    a journal entry might mention by name."""
    ents: dict[str, str] = {}
    for folder in CONTACT_FOLDERS:
        d = space / folder
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file() and f.suffix == ".md":
                    ents[f.stem] = _human_label_for_slug(f.stem)
    for kind in BUNDLE_FOLDERS:
        d = space / kind
        if d.is_dir():
            for b in d.iterdir():
                if b.is_dir():
                    ents[b.name] = _human_label_for_slug(b.name)
    return ents


def _session_journal_link_candidates(notes: list[dict], space: Path, top_n: int = 5) -> list[dict]:
    """Known entities mentioned in recent periodic notes as plain text but not
    yet wikilinked there, ranked by recurrence (how many recent notes mention
    each unlinked). Conservative link proposals, capture becoming connected over
    time, without auto-linking. Reads the recent note bodies directly, so it does
    not depend on index freshness."""
    prefixes = tuple(f"{r}/" for r in _SESSION_JOURNAL_WINDOWS)
    ents = _session_known_entities(space)
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
            body = (space / path).read_text(encoding="utf-8", errors="ignore")
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


def _session_index_stale(space: Path, index: dict | None) -> bool:
    """True when the space's markdown no longer matches the index, a file was
    added, removed, or changed since the last rebuild. Compares path + mtime, so
    it catches edits the user made in their editor, which set no marker. An
    index built before the per-file `mtime` field counts as stale once."""
    if not index:
        return True
    current: dict[str, int] = {}
    for f in _walk_space_markdown(space):
        try:
            current[f.relative_to(space).as_posix()] = int(f.stat().st_mtime)
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


def _session_refresh_index(space: Path, *, detached: bool = True) -> None:
    """Rebuild the space index and patterns. At session start this is handed to a detached
    process and the hook does not wait for it.

    It used to run inline, on a docstring that claimed sub-second on thousands of files. Measured
    in a space in daily use: median 248 ms, worst case 8,452 ms, against the host's
    10-second SessionStart timeout. A hook that times out delivers nothing at all, so the greet
    would have opened blind, which is worse than the truncation this same day was spent fixing.
    Nothing in the greet needs the index, so waiting for it buys nothing and risks everything.

    `detached=False` runs it inline and is for callers that need the result, and for tests.
    """
    import io, contextlib
    if detached:
        import subprocess
        try:
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "index", "rebuild",
                 str(space), "--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                start_new_session=True)
        except Exception:
            pass  # a refresh that cannot start is a stale index, never a failed session start
        return
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_reindex(argparse.Namespace(space=str(space), scope=None, quiet=True))
            cmd_patterns(argparse.Namespace(space=str(space), min_count=2))
    except Exception:
        pass


def cmd_hook_session_start(args: argparse.Namespace) -> int:
    """SessionStart hook. The init point for every Zanmai session: reads
    all static state (`zanmai/user.md`, last-session-end
    marker, index entries) and prints a compact briefing
    that Claude Code injects into the session context as a system-reminder."""
    # Read the payload once, up front. stdin can only be read once, and two things want it now: the
    # space fallback below and the model name at the end. `SessionStart` is the only event that
    # carries `model` at all, and the docs say it is not guaranteed to be there, so everything that
    # reads it treats it as optional.
    payload = _hook_read_payload()
    # Whether this is a new session or the same one picked up again. Read here rather than at the
    # greet, because everything below has to know: a resumed session already did its session-start
    # work, and repeating it means a second import run over the same files every time somebody
    # steps out of the terminal and back in.
    fortsetzung = str(payload.get("source") or "").lower() in ("resume", "compact")
    space = _session_find_space_root()
    if space is None:
        import os
        env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        if env_dir:
            candidate = Path(env_dir)
            if (candidate / SYSTEM_DIR / "user.md").exists():
                space = candidate
    if space is None:
        cwd_hint = payload.get("cwd") or payload.get("project_dir")
        if cwd_hint and (Path(cwd_hint) / SYSTEM_DIR / "user.md").exists():
            space = Path(cwd_hint)
    if space is None:
        # No initialised space found by the user.md marker. Detect an
        # uninitialised Zanmai space (system tree present, user.md absent) and
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
                    "Zanmai: this space is not set up yet, there is no user profile. "
                    "Before any greeting or answer, read zanmai/system/skills/setup/SKILL.md "
                    "as a file, there is no slash command for it, "
                    "and run its workflow now. Do not respond generically."
                )
                return 0
        return 0

    user_md = space / SYSTEM_DIR / "user.md"
    try:
        user_text = user_md.read_text(encoding="utf-8")
    except OSError:
        print("Zanmai session-start: zanmai/user.md unreadable. Run `setup` skill if space is fresh.")
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
    work_dir = space / SCRATCH_DIR
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
    # time they are in the space after setup. It is the one moment where an offer to explain the
    # place is welcome rather than noise.
    first_session = not (space / MEMORY_DIR / ".last-session-end").exists()

    marker = _session_read_marker(space)
    marker_iso = marker.astimezone(timezone.utc).isoformat(timespec="minutes")

    lines: list[str] = []
    lines.append("Zanmai session briefing")
    lines.append(f"- Address the user as **{preferred}** (from preferred_address / first_name in zanmai/user.md).")
    # Every line below writes `zanmai.py <subcommand>`, and so do the skills and the expert
    # contracts, 188 times against 38 that spell the path out. The resolution was written down only
    # inside the expert contracts, under a heading a run reads when it is already that expert. So a
    # session start would say `zanmai.py archive index`, the run typed exactly that at the space
    # root, and there is no zanmai.py at the space root. Two runs on the same day spent their first
    # commands looking for the file. It costs one line to say it where every run passes.
    lines.append(f"- `zanmai.py <subcommand>` here and in every skill is shorthand for "
                 f"`{fm.get('python_cmd') or 'python3'} {SYSTEM_DIR}/system/scripts/zanmai.py "
                 f"<subcommand>`, run from the space root. There is no zanmai.py at the root.")

    # New distribution files can arrive without the host-side refresh, for
    # example when the user pulls the repository by hand. The refresh is
    # mechanical, so run it instead of reporting drift.
    #
    # The wiring itself is checked every session, not only when the version moved,
    # and that is what rescues a space whose marker already claims the current
    # version while the host config is incomplete. Any release before this one wrote
    # that marker on hope: for those spaces the versions agree, so a check that
    # triggers on disagreement never looks again. This one looks regardless.
    # Both ignore lists, rewritten from the current folder names. Silent and cheap: two small files,
    # no comparison, nothing to report. It runs here because this is the one place that runs in
    # every space on every session, and because what it writes decides two things nobody would
    # notice going wrong: whether the user's material stays out of a commit, and whether a search
    # of their own notes can see them at all.
    try:
        _write_ignore_rules(space)
    except OSError:
        pass                                  # a read-only space still greets

    shipped_version = _distribution_version(space)
    host_marker = space / RUNTIME_DIR / "host-config-version"
    known_version = host_marker.read_text(encoding="utf-8").strip() if host_marker.exists() else ""
    version_moved = bool(shipped_version) and shipped_version != known_version
    problems = _verify_host_config(space)
    if version_moved or problems:
        _refresh_host_config(space, quiet=True)
        remaining = _verify_host_config(space)
        if remaining:
            lines.append("- This space's host config is incomplete and a refresh did not fix it: "
                         + "; ".join(remaining)
                         + ". Say so plainly and offer to run `setup validate` for the detail. The "
                           "recorded version is left alone, so this is looked at again next session.")
        else:
            if shipped_version:
                _record_host_config_version(space, shipped_version)
            if problems and not version_moved:
                lines.append(f"- Part of Zanmai was on disk but not wired up ({len(problems)} item(s)), "
                             "and has now been wired. Mention it once, in one sentence, and carry on.")
            elif known_version and version_moved:
                lines.append(f"- Zanmai moved from {known_version} to {shipped_version}. Host config refreshed; "
                             "mention the new version once and point at the changelog if the user asks what changed.")

    # A session ends when somebody shuts the window, and that leaves no handover: the close is a
    # command someone has to type. A machine that was switched off at the wall says so on the way
    # back up and offers to check itself, and this is the same moment. The host wrote the whole
    # conversation down while it happened, so what was lost is not lost, it just has to be read.
    # Nothing is done here except saying it: writing the handover needs judgement about what it all
    # meant, and this hook has no model.
    if not first_session:
        offen = _records(space, seit=_last_session_end(space))
        if offen:
            wann = datetime.fromtimestamp(offen[-1].stat().st_mtime).strftime("%d.%m. %H:%M")
            lines.append(
                f"- **{len(offen)} session(s) were never closed**, the newest on {wann}. Say so in "
                f"one sentence and offer to write the handover for them now, out of "
                f"`zanmai.py session digest`, which reads what actually happened from the host's "
                f"own record of those conversations. Then say that closing a session is "
                f"`/zanmai-session-close` and takes a moment. Write nothing before the user "
                f"says yes.")

    # A later version added questions to setup that this space never saw. The gap is read here
    # rather than left to a number written into a skill file, because a number in prose drifts
    # away from the one the code ships and then the catch-up either never fires or fires forever.
    # Once answered, `setup catch-up` stamps the field and this line is gone for good.
    if not fortsetzung and _setup_schema_version(space) < CURRENT_SETUP_SCHEMA_VERSION:
        lines.append(
            f"- This space was set up before the current setup dialogue existed "
            f"(setup_schema_version {_setup_schema_version(space)}, current {CURRENT_SETUP_SCHEMA_VERSION}). "
            f"Read `{SYSTEM_DIR}/system/skills/setup/SKILL.md` as a file (no slash command exists "
            f"for it), section 'Catching up an older space', "
            "and run only the blocks it names as missing, before the ordinary greet. Ask once; the "
            "answers are recorded with `setup catch-up` and this never comes back."
        )

    # Recordings waiting are named, not transcribed. A hook that takes a minute is a
    # session that starts in a minute, and the reading of them is a background job.
    waiting = _pending_recordings(space) if not fortsetzung else []
    if waiting:
        total = sum(_audio_duration(f) or 0.0 for f in waiting)
        lines.append(
            f"- {len(waiting)} voice note(s) waiting in {INBOX_DIR}/"
            + (f", {_spoken_length(total)} in total" if total else "")
            + ". **Dispatch the `import` skill in the background in this same turn**, before the "
              "greet goes out; a background dispatch does not hold it up and the greet is written "
              "while it runs. Not on the next turn: the next turn belongs to the user, so a greet "
              "that says it will look is a greet that never does. The greet says the reading is "
              "under way, in one line, in the present tense, and then nothing more about it. The "
              "user knows something is lying there, they put it there, so announcing it is not "
              "news and asking permission asks them to repeat themselves. What comes back is "
              "reported when it comes back, and only then is there anything to ask: where "
              "something belongs when the file does not say, or a tool to fetch, with its size."
        )

    # Work the user has not answered yet. Named in one line, because this is the one
    # class of open item the next session cannot work out for itself.
    try:
        rows, _headers = _work_read(space)
    except Exception:
        rows = []
    # A session that ran with nobody in the chat is only useful if the next one says so.
    unattended = _unattended_log_to_report(space)
    if unattended:
        lines.append(f"- The last session ran without the user: `{unattended.relative_to(space)}`. "
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
    newer = _quiet_update_probe(space)
    if newer and _update_offer_due(space):
        lines.append(f"- Version {newer} is available (this space runs {shipped_version}). Offer the update once, "
                     "in one plain line, at a moment that does not interrupt the user's task, and drop it for this "
                     "session if declined. On a yes, dispatch Pepper's update workflow.")
    if owner_contact:
        lines.append(f"- Owner contact: `{PEOPLE_DIR}/{owner_contact}.md` (read for persistent user notes).")
    lines.append(f"- Language preference: {language}.")
    lines.append(f"- Last session ended: {marker_iso}.")
    lines.append(f"- auto_snapshots: {str(auto_snapshots).lower()}. A snapshot is taken before something that could lose the user's own work, never because a session began or a version changed. When false, skip every automatic snapshot, the user has their own backup approach.")
    for note in _sweep_retention(space):
        lines.append(f"- Housekeeping: {note}")

    stray = _unexpected_root_entries(space)
    if stray:
        lines.append(
            f"- {len(stray)} entr(y/ies) at the space root do not belong to the folder architecture: "
            f"{', '.join(stray[:5])}"
            + (" …" if len(stray) > 5 else "")
            + ". This did not come from a Zanmai write. Name it once, in one line, and offer to move "
              "its contents into the right bundle."
        )

    # The weekly shape-and-memory report: what `zanmai.py housekeeping` finds beyond the
    # retention sweep, plus a critical read of general.md, surfaced together without the user
    # having to ask for either or run anything by hand. Report only, nothing here is moved.
    # general.md writes without asking first now; this replaces that dialogue. The write-time
    # gate only ever catches the narrow, syntactic version of a bad entry (a date, an instance
    # name); telling a lasting principle from a single case dressed up as one is reading, so it
    # goes to the same dispatch as the shape report rather than a second, separate one.
    if _housekeeping_due(space):
        duenn = _bundles_without_material(space)
        form = _area_shape(space)
        if duenn or form:
            lines.append("- Housekeeping (weekly): the space's shape, not just its keeping "
                         "times. The list below is raw, not a finding: connect what belongs "
                         "together by matter, not by name (a bundle in workbench/ and bundles in "
                         "life/ can be the same shape with no word in common), say what you see, "
                         "do not move anything without a yes.")
            for b in duenn[:5]:
                lines.append(f"  - {b} holds nothing but its own page, a single item given a folder.")
            if len(duenn) > 5:
                lines.append(f"  - {len(duenn) - 5} more of the same.")
            for zeile in form[:10]:
                lines.append(f"  - {zeile}")
        if (space / MEMORY_DIR / "general.md").is_file():
            lines.append("- Same weekly moment: dispatch Pepper with `run_in_background: true` "
                         "to read every rule in general.md against its own purpose (a lasting "
                         "principle, not a single case: no person's name, no one trip, no one "
                         "running instance, no note about a new command's own behaviour). Do not "
                         "wait on it; report what she finds, in the user's writing language, "
                         "whenever she returns. Nothing is removed without a yes.")

    lines.append(f"- The journal lives under `{JOURNAL_DIR}/`, one entry per day, named by its date and filed under its year. It is always there; there is no switch and nothing to configure. A summary over a week or a month is a question asked of those files, not a file of its own.")
    lines.append("- Journal operations go through `zanmai.py journal` and the `journal` skill. The AI never writes into an entry on its own initiative, only on direct user instruction.")

    # Not on a resume. The reading was dispatched when the session started; doing it again because
    # the user stepped out of the terminal and back in runs the same files through the same expert
    # a second time, at the same cost, for the same answer.
    wartend = _import_pending(space) if not fortsetzung else []

    if wartend:
        arten: dict[str, int] = {}
        for f in wartend:
            art, _weg = _import_route(f)
            arten[art] = arten.get(art, 0) + 1
        pretty = ", ".join(f"{n} {a}" for a, n in sorted(arten.items()))
        namen = ", ".join(f.name for f in wartend[:6])
        if len(wartend) > 6:
            namen += f", and {len(wartend) - 6} more"
        # What the user already decided about this material, said here rather than left in a file
        # nobody opens mid-turn. Where a rule covers a file it is the answer, and asking again asks
        # the user to repeat themselves.
        treffer = {}
        for f in wartend:
            regel = _route_for_file(space, f)
            if regel:
                treffer[regel.get("name", "?")] = _rule_phrase(regel)
        geregelt = [treffer[k] for k in sorted(treffer)]
        # There used to be a note here of which files had been handed over before, because a file
        # could stay in the inbox and would then be worked again at the next session start. Nothing
        # stays any more, so a file lying here has not been dealt with, whatever happened earlier,
        # and a list of what was already seen would now be the thing that stops it being finished.
        lines.append(
            f"- {len(wartend)} file(s) waiting in `{INBOX_DIR}/` ({pretty}): {namen}. "
            + (f"The routing table already answers part of it: {'; '.join(geregelt)}. Follow it "
               f"rather than asking again. " if geregelt else "")
            + f"**Read it by machine first**: `zanmai.py archive index --scope {INBOX_DIR}` pulls "
              f"the text out of every file for free, then `zanmai.py archive survey --scope "
              f"{INBOX_DIR}` gives one line each with dates, amounts, parties and the opening. "
              f"Both take the same folder; without it the survey reports the whole archive. Work "
              f"from those lines and open a file only where one leaves the question open. Reading "
              f"them all with a model costs about sixteen times as much and answers the same "
              f"question. "
            + f"Run `zanmai.py import scan` for the route per file. Read all of them before "
            f"processing any, the later one can withdraw the earlier. Anything can land here: a "
            f"screenshot, a rental protocol, a spoken note, an idea, a document, a training log. "
            f"The reading runs in the background from this turn, not the next one. Report what "
            f"each was and where it belongs when the run returns. The question comes after the "
            f"reading, never instead of it, and only where the material itself leaves something "
            f"open. Nothing is written into the space before that answer. **Every one of these "
            f"leaves `{INBOX_DIR}/` in the same run, and nothing may be left lying there.** Where the "
            f"file itself still carries something the result does not, a scan or a recording, it goes "
            f"to live beside what was made from it; where it does not, a note that asked for a task, "
            f"it goes to the trash. Where a rule of the user's does not answer that yet, it is worth "
            f"one question, once, and the answer goes into the rule with `routing set <name> "
            f"<destination> --keep with-result|discard`. A rule naming who does the work is followed "
            f"on that too. Anything the "
            f"routing table sends to `{ARCHIVE_DIR}/` goes to Marcus rather than Hank, and it "
            f"moves as a pile: `zanmai.py archive file --source <folder> --into <bundle>` files "
            f"the lot in one call, keeps the folders the user already sorted it into and reads "
            f"what it filed. **Do not move documents one at a time.** Deciding each one before "
            f"anything moves is how a pile of thirty sits untouched while every file is thought "
            f"about, and it is the same work the one call does in seconds. The matter notes come "
            f"after the documents are in, and only where there is something to say that stands in "
            f"no document. Where a kind has no rule yet and the user says where it belongs, write "
            f"that down with `zanmai.py routing set <name> <destination> --when-text <a word in "
            f"it>`, so the next one of its sort does not have to be asked about again. To give a "
            f"filed document a name that says what it is, or to put it in a section underneath, "
            f"use `zanmai.py archive rename` and `zanmai.py archive move`; a hand-rolled `mv` "
            f"moves the file and leaves the index pointing at where it used to be.")
        # The handover, written out rather than left to be composed. `dispatch-guard` checks for
        # the user's-words block and refuses without it, and at a session start there is no
        # sentence to quote: the user said "hello". Composing one on the spot means inventing a
        # request nobody made, so the block says the true thing instead, which is that putting the
        # files there was the request. A dispatch that has to be assembled from scratch at the one
        # moment the session is trying to start is a dispatch that gets refused, and that is what
        # happened the first time this ran.
        lines.append(
            f"  The prompt for that dispatch starts with these two blocks, verbatim:\n"
            f"  `What the user said:` They put {len(wartend)} file(s) into `{INBOX_DIR}/`: "
            f"{namen}. Dropping material there is the instruction to take it in; nothing was said "
            f"in the conversation about it.\n"
            f"  `What I concluded:` This is the reading pass from `import-bundle/SKILL.md`, not a "
            f"filing run. Open every file, work out what each one is, write nothing into the "
            f"space, ask nothing, and return per file what it is and where it would belong, plus "
            f"what is still open. Check a tool with `tools check <id>` before needing it and "
            f"report the gap rather than fetching it.")

    # Material for the archive, before anybody is sent to file it. Put as a statement with two
    # open questions hanging off it, never as a menu to pick from. A menu asks the user to work
    # through options where there is nothing to choose: the area is called archive, and the sorts of
    # document that go in it are visible in their own material. What is worth asking is only what
    # the machine cannot see, namely whether something is missing from that picture and whether the
    # terms suit. Both answers are usually one word, and that is the point. The country is not
    # asked either: shipping a list of legal areas is wrong for everybody not on it, so the terms
    # lean long instead and are offered as a suggestion. An expert cannot run this conversation, it
    # runs in the background and has nobody to ask, so it happens here or it happens never. Written
    # as a mechanical check rather than as a rule in a contract: a rule that tells a background run
    # to ask a question is a rule that cannot hold.
    if wartend and not fortsetzung:
        arten_da = {_import_route(f)[0] for f in wartend}
        will_records = any((_route_for_file(space, f).get("to") or "").startswith(ARCHIVE_DIR)
                           for f in wartend)
        eingerichtet = bool(_retention(space))
        if not eingerichtet and (will_records or not _routing(space)):
            gesehen = ", ".join(sorted(arten_da)[:8]) or "whatever the reading turns up"
            lines.append(
                f"- **The archive is not set up, so nothing gets filed there yet.** Settle it "
                f"in this turn, in the user's language, as plain sentences and not as a menu of "
                f"options to choose from. Write it for somebody who has never used this before, "
                f"in this order: what you found lying in `inbox/` and what sort it is "
                f"({gesehen}); that this sort is kept rather than filed away, which is a different "
                f"job with a different specialist, Marcus, who looks after documents that have to "
                f"be produced again years later; that the area for it is called `{ARCHIVE_DIR}`; "
                f"what you would therefore take as belonging in it; and how long you would keep "
                f"each sort. Print that last part with `zanmai.py retention show` and put it in as "
                f"it stands, the terms are deliberately on the long side, so fine is the normal "
                f"answer. Then two questions and wait: is anything missing from that or anything "
                f"too much, and do those terms suit. Close by offering that you can say more about "
                f"how the archive works, from `zanmai/system/docs/archive.md`, if they want it. Do "
                f"not offer a choice of names, do not ask which country they are in, do not build "
                f"a list to tick. On the answers: `zanmai.py retention adopt`, then `zanmai.py "
                f"routing set <name> {ARCHIVE_DIR} --when-text <a word in it>` per sort that "
                f"stands. Only then is anything "
                f"dispatched to Marcus. He runs in the background and cannot ask, so a run sent "
                f"out before this either guesses or stops, and both are worse than a question "
                f"here.")

    # The desk, once, as a sentence. `workbench/` is the one folder that empties, so what sits there
    # untouched is either finished and not filed, or waiting on something nobody wrote down. In a
    # working space this fills up faster than anyone notices: fifteen pieces, nine of them still
    # for more than a fortnight. It is a reminder and not a demand, so it says the count, names a
    # few, and offers the one move that makes a piece go quiet on purpose.
    liegend = _desk_idle(space)
    if liegend:
        namen = ", ".join(e["label"] for e in liegend[:3])
        rest = f" and {len(liegend) - 3} more" if len(liegend) > 3 else ""
        lines.append(
            f"- {len(liegend)} piece(s) on the desk have not moved for over {DESK_IDLE_DAYS} days, "
            f"longest first: {namen}{rest}. Say this in one sentence after the list, not as items, "
            f"and only where it is worth a word: nothing here has to move. Where the user says one "
            f"is waiting on something, record it with `zanmai.py file status --path "
            f"<workbench/<slug>/<slug>.md> --set waiting` and a `due:` for when it comes back, and it "
            f"stays quiet until then. Where one is simply finished, `--set done` and it stops "
            f"being asked about."
        )

    if first_session:
        lines.append("- **First session after setup.** Before anything else, ask the user in their writing language whether they would like a short tour: what the folders are for, and what they can actually do with Zanmai. One question, two sentences at most, and a no is a fine answer. On a yes, answer from `zanmai/system/docs/index.md` and the pages it points at, shaped for this user, never a page pasted back at them.")

    index = _session_load_index(space)
    stale_marker = space / MEMORY_DIR / ".index-stale"
    if stale_marker.exists() or _session_index_stale(space, index):
        # Handed off, not waited for: the greet reads none of this, and the rebuild's worst case
        # sits within one second of the host's timeout for the whole hook. The session works from
        # the index as it stands; the refreshed one is there for the first query that needs it.
        _session_refresh_index(space)
    if index is None:
        lines.append("- Pattern index not built yet. Run `zanmai.py index rebuild` plus `zanmai.py index patterns` before bundle queries.")
    else:
        notes = _session_collect_recent_journal(index, space)
        window_desc = f"last {_SESSION_DAILY_WINDOW_DAYS} days"
        if not notes:
            lines.append(f"- No journal entries in the recent window ({window_desc}). The greet still runs the same walk over what is open, from `zanmai/memory/briefing.md` and the work objects; with fewer sources it simply finds fewer items, and it names the ones it finds.")
        else:
            lines.append(f"- Recent window ({window_desc}): {len(notes)} journal entr{'y' if len(notes) == 1 else 'ies'}.")
            for n in notes[-5:]:
                lines.append(f"  * {n['path']}")
            candidates = _session_journal_link_candidates(notes, space)
            if candidates:
                pretty = ", ".join(f"[[{c['slug']}]] ({c['count']}x)" for c in candidates)
                lines.append(
                    f"- Journal link candidates (recent notes name these existing entities unlinked, ranked by recurrence): {pretty}. "
                    f"Offer to add the wikilinks, propose, do not auto-link. The more a name recurs across recent notes, the stronger the signal it belongs connected. This is how capture becomes connected over time."
                )
            counts = _session_aggregate_tokens(notes, space)
            bundles = _session_existing_bundle_slugs(space)
            suggestions = _session_suggest_bundles(counts, bundles, top_n=3)
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

    stale = space / MEMORY_DIR / ".index-stale"
    if stale.exists():
        lines.append("- `zanmai/memory/.index-stale` marker is set. Refresh `zanmai.py index rebuild` + `zanmai.py index patterns` before any bundle query.")

    # The briefing is named, never pasted. Embedding it put the payload over the host's
    # hook-output limit, and everything past that limit is replaced by a 2 KB preview the
    # model cannot tell is incomplete. Measured on 79 real starts in a live space: every
    # single one exceeded the limit, the greet list and the greet shape sat past it, and
    # the greet was composed from the briefing's first two kilobytes instead. A path plus
    # one read is cheaper than a greet built on a fragment.
    briefing_path = space / MEMORY_DIR / "briefing.md"
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
            greet_lines = _greet_block(space)
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
    # A resumed conversation is not a new one. The host says which it is in the payload, and where
    # it says resume the session already carries everything a greet exists to establish. Greeting
    # there reads as amnesia: a user reopened a running build in another terminal on,
    # got a full greet with a task list, and answered "I am completely lost about where you are".
    if fortsetzung:
        lines.append(
            f"- **This session was resumed, so it is not greeted.** The thread is picked up where "
            f"it stopped: what is running, what it was waiting for, what comes next, in one or two "
            f"sentences. The list above is context, not something to read out. Where the thread is "
            f"genuinely gone, say so in one line and ask, rather than opening with a greeting."
        )
    elif (space / greeting_rel).exists():
        lines.append(
            f"- **Open the file `{greeting_rel}` and follow it before the first user-facing "
            f"sentence.** Open it as a file: this is not a registered skill and there is no slash "
            f"command for it. Every registered one is named `zanmai-<something>`, which is exactly "
            f"why `zanmai-greeting` gets guessed; that call fails and costs the first turn of the "
            f"session. The file carries the greet shape, the mandatory reads and what a greet must "
            f"never contain. Address the user as **{preferred}** where it applies."
        )
    else:
        lines.append(
            f"- `{greeting_rel}` is missing. Say so in one line, then greet from "
            f"`{MEMORY_DIR}/briefing.md` and the greet list above: address, the open items grouped "
            f"by time, nearest first, six lines at most, no ids and no paths."
        )

    # Which model is running, one line at the end, because the user asked for it on and
    # the answer changes what a turn can be trusted with. `SessionStart` is the only hook event that
    # carries the field, there is no `$CLAUDE_MODEL` in the environment (measured: none), and
    # `settings.json` holds the default rather than what a `/model` switch left running. So the
    # payload is the one honest source, and where it does not carry the field the line is left out
    # rather than guessed.
    modell = payload.get("model")
    if isinstance(modell, dict):
        # The display name, never the id: "Opus 5 (1M context)" answers the user's question,
        # "claude-opus-5[1m]" does not. Both exist at runtime and the greet must not take whichever
        # arrives first, or it reads plausibly and stays wrong.
        modell = modell.get("display_name") or modell.get("id") or modell.get("name")
    if isinstance(modell, str) and modell.strip():
        lines.append("")
        lines.append(f"- End the greet with one line naming the model in the user's writing "
                     f"language: this session runs on {modell.strip()}. The line is the whole of it, "
                     f"no assessment and no recommendation.")
    elif not payload:
        # Nothing arrived on stdin at all. That is not the same as "the host sent no model", and
        # without saying so the two are indistinguishable from the outside: the line is simply
        # absent either way. It matters because another SessionStart hook may have drained stdin
        # first: a hook that reads stdin before checking whether it should run consumes it on every
        # start. Whether hooks share one stdin or get their own is not documented, and this line is
        # what tells us which, the first time it matters.
        lines.append("")
        lines.append("- The session-start payload was empty, so the model is unknown and that line "
                     "is left out. Not a fault by itself. Worth one look only if it persists: it "
                     "can mean another SessionStart hook read stdin first.")

    ausgabe = "\n".join(lines)
    # Size guard. The host replaces hook output over its limit with a 2 KB preview plus a file
    # path, and a preview is worse than nothing: it carries enough to compose a plausible reply
    # from and no sign that the rest was dropped. Measured, every
    # one of 79 recorded starts was over, so the greet had never once seen its own instructions.
    # Kept well under the limit rather than at it: what this hook prints grows with the space.
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
    # Mark the pattern index stale. The space root is whatever sits above the bundle root, and the
    # first match is the one that gives it: a path may well repeat a folder name further down
    # (`knowledge/knowledge-management/`), and the later occurrence would put the marker inside the
    # bundle instead of in the space.
    norm = file_path.replace("\\", "/")
    found = [i for i in (norm.find(f"/{r}/") for r in BUNDLE_FOLDERS) if i != -1]
    if found:
        try:
            (Path(norm[:min(found)]) / MEMORY_DIR / ".index-stale").touch(exist_ok=True)
        except OSError:
            pass
    rel, _ = located
    parts = rel.split("/")
    # `<kind>/<slug>/<file>`: three segments now that the kind folder is a space root.
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
    """Where the self-managed C2PA signing identity lives: outside the space, in
    the user's config dir, never committed, never in the space (LD6)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "zanmai" / "c2pa-signer"


def _signer_paths() -> tuple[Path, Path]:
    d = _signer_dir()
    return d / "cert.pem", d / "key.pem"


def _establish_signer(space: Path | None) -> tuple[Path | None, Path | None, str]:
    """Create the self-managed signing identity if none exists, then return its
    paths. P-256, PKCS#8 key, cert with keyUsage=digitalSignature,
    EKU=emailProtection, CA:FALSE, and SubjectKeyIdentifier + AuthorityKeyIdentifier
    (c2pa rejects a signer cert lacking SKI/AKI, verified 2026-07-20). Valid, not
    trust-listed, that is the user's responsibility. Needs the `cryptography`
    library; provisions it into the runtime venv on first use if absent."""
    cert_p, key_p = _signer_paths()
    if cert_p.is_file() and key_p.is_file():
        return cert_p, key_p, "present"
    if space is not None:
        _activate_runtime_venv_site(space)
    try:
        from cryptography import x509  # noqa: F401
    except ImportError:
        if space is None:
            return None, None, "cryptography not available and no space to provision it"
        import subprocess
        py, _ = _ensure_runtime_venv(space)
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
        _activate_runtime_venv_site(space)
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
    space = _find_space_root(Path(args.space)) if args.space else _find_space_root(Path.cwd())
    cert_p, key_p, state = _establish_signer(space)
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

    space = _find_space_root(out) or _find_space_root(src) or _find_space_root(Path.cwd())
    if space:
        _activate_runtime_venv_site(space)

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
        icons_dir = (space / SYSTEM_MATERIAL_DIR / "icons" / "eu-ai") if space else Path(".")
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
    # mark actually needs to sign or re-seal: the certificate is created when none exists.
    if not (cert and key):
        cp, kp = _signer_paths()
        if not (cp.is_file() and kp.is_file()) and (args.sign or (reencoded and present is True)):
            ecp, ekp, _ = _establish_signer(space)
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
    """Terminal apps this machine can start a space session in.

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


def _launcher_create_macos(space: Path, name: str, terminal_id: str, icon_png: Path, claude_bin: str) -> int:
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

        space_escaped = str(space).replace("'", "'\\''")
        if terminal_id == "terminal":
            start_cmd = resources_dir / "start.command"
            start_cmd.write_text(f"#!/bin/bash\ncd '{space_escaped}'\nexec '{claude_bin}'\n", encoding="utf-8")
            start_cmd.chmod(0o755)
            launch_body = (
                "#!/bin/bash\n"
                'DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"\n'
                'exec open -a Terminal "$DIR/start.command"\n'
            )
        else:
            app_name = next((n for tid, n in _MAC_TERMINAL_CANDIDATES if tid == terminal_id), terminal_id)
            inner = f"cd '{space_escaped}' && exec '{claude_bin}'"
            inner_escaped = inner.replace('"', '\\"')
            launch_body = f"#!/bin/bash\nopen -na '{app_name}' --args -e /bin/zsh -c \"{inner_escaped}\"\n"
        (macos_dir / "launch").write_text(launch_body, encoding="utf-8")
        (macos_dir / "launch").chmod(0o755)

    subprocess.run(["xattr", "-cr", str(app_dir)], capture_output=True)
    print(f"ok: {app_dir}")
    return 0


def _launcher_create_windows(space: Path, name: str, terminal_id: str, icon_ico: Path, claude_bin: str) -> int:
    """Designed against documented PowerShell/WScript.Shell behaviour, never run on
    real Windows hardware, same status as the rest of this project's Windows path.
    """
    desktop = Path.home() / "Desktop"
    lnk_path = desktop / f"{name}.lnk"
    if terminal_id == "wt":
        target = "wt.exe"
        arguments = f'-d "{space}" {claude_bin}'
    else:
        target = "cmd.exe"
        arguments = f'/k "cd /d ""{space}"" && {claude_bin}"'

    ps_script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath = '{target}';"
        "$s.Arguments = '{args}';"
        "$s.IconLocation = '{icon}';"
        "$s.WorkingDirectory = '{cwd}';"
        "$s.Save()"
    ).format(lnk=str(lnk_path), target=target, args=arguments.replace("'", "''"),
             icon=str(icon_ico), cwd=str(space))

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
    """Build a double-clickable starter for this space: an .app on macOS, a .lnk
    on Windows. Deliberately its own command, independent of `setup init`, so it
    can be asked for anytime in a session, not only once during first install.
    """
    space = Path(args.space_root).resolve()
    if not (space / SYSTEM_MATERIAL_DIR / "manifest.yaml").exists():
        print(f"error: no Zanmai system folder at {space}", file=sys.stderr)
        return 1
    name = args.name.strip()
    if not name:
        print("error: --name must not be empty", file=sys.stderr)
        return 1

    osname = _current_os()
    claude_bin = shutil.which("claude") or "claude"

    if osname == "macos":
        icon_png = space / SYSTEM_MATERIAL_DIR / "icons" / "app-icon.png"
        if not icon_png.exists():
            print(f"error: missing shipped icon at {icon_png}", file=sys.stderr)
            return 1
        return _launcher_create_macos(space, name, args.terminal, icon_png, claude_bin)
    if osname == "windows":
        icon_ico = space / SYSTEM_MATERIAL_DIR / "icons" / "app-icon.ico"
        if not icon_ico.exists():
            print(f"error: missing shipped icon at {icon_ico}", file=sys.stderr)
            return 1
        return _launcher_create_windows(space, name, args.terminal, icon_ico, claude_bin)
    print("error: no launcher mechanic for this platform yet", file=sys.stderr)
    return 1


def _runtime_venv_dir(space: Path) -> Path:
    return space / RUNTIME_DIR / "venv"


def _runtime_venv_python(space: Path) -> Path | None:
    d = _runtime_venv_dir(space)
    for rel in ("bin/python", "Scripts/python.exe"):
        p = d / rel
        if p.is_file():
            return p
    return None


def _user_python_cmd(space: Path) -> str:
    """The Python invocation recorded at setup (user.md python_cmd); default python3."""
    um = space / SYSTEM_DIR / "user.md"
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


def _detect_lib(space: Path, module: str) -> dict:
    import subprocess
    py = _runtime_venv_python(space)
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


def _detect_tool(space: Path, tid: str, spec: dict, osname: str) -> dict:
    det = spec.get("detect", {})
    method = det.get("method")
    if method == "import":
        return _detect_lib(space, det.get("import", tid))
    if method == "renderer":
        return _detect_renderer(osname)
    if method == "env":
        envs = det.get("env", [])
        return {"present": all(os.environ.get(e) for e in envs), "note": "env " + ",".join(envs)}
    if method in ("which", "runtime"):
        osspec = (spec.get("os") or {}).get(osname) or {}
        name = osspec.get("invoke") or tid
        # A binary this space fetched itself lives in the runtime tree and is not
        # on PATH, so PATH alone would report it missing right after it was
        # installed, and every job would fetch it again. The space's own copy is
        # looked at first, then the host's.
        own = space / ((spec.get("provision") or {}).get("into") or f"{RUNTIME_DIR}/bin") / name
        if own.is_file():
            found = _detect_binary(str(own), det.get("version_flag"))
            if found.get("present"):
                return found
        return _detect_binary(name, det.get("version_flag"))
    if method == "file-glob":
        # A model file is neither a binary on PATH nor an importable library: it is a
        # large file the space fetched into its own machine-local runtime tree. Without
        # this branch the entry fell through to "no detector", which reads as unknown
        # rather than missing, and a preflight cannot gate on unknown.
        hits = sorted(space.glob(det.get("glob", "")))
        if hits:
            size = hits[0].stat().st_size / (1024 * 1024)
            return {"present": True, "path": str(hits[0].relative_to(space)),
                    "note": f"{size:.0f} MB"}
        return {"present": False, "note": f"no file matching {det.get('glob', '')}"}
    if spec.get("kind") == "mcp":
        return {"present": None, "note": "host-configured (check the host)"}
    return {"present": None, "note": f"no detector for method {method!r}"}


def cmd_tools_doctor(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    tools = _load_register().get("tools", {})
    osname = _current_os()
    print(f"Zanmai tool doctor, os={osname}, space={space}")
    print(f"runtime venv python: {_runtime_venv_python(space) or '(not built)'}\n")
    order = {"prerequisite": 0, "on-demand": 1, "recommended": 2, "host-configured": 3}
    cache = _load_tool_cache(space)
    for tid, spec in sorted(tools.items(), key=lambda kv: (order.get(kv[1].get("tier"), 9), kv[0])):
        res = _detect_tool_cached(space, tid, spec, osname, cache, refresh=getattr(args, "refresh", False))
        p = res.get("present")
        mark = "ok" if p is True else ("--" if p is False else "??")
        detail = res.get("version") or res.get("note") or res.get("path") or ""
        need = ",".join(spec.get("needed_by", []))
        print(f"  [{mark}] {tid:14} {spec.get('tier',''):14} {detail:40} «{need}»")
    _save_tool_cache(space, cache)
    return 0


def _tools_table(tools: dict) -> str:
    """The register as a table, so the documentation page cannot drift from the register.

    Generated rather than written: the page a user reads about what gets installed has to say
    what the machine will actually install, and a hand-kept second copy of a list is how the
    two stop matching.
    """
    who = {"venv-pip": "Zanmai fetches it", "node-package": "Zanmai fetches it",
           "file-fetch": "Zanmai fetches it", "binary-fetch": "Zanmai fetches it"}
    lines = ["| Tool | What it is for | Size | Who installs it |", "|---|---|---|---|"]
    order = {"prerequisite": 0, "on-demand": 1, "recommended": 2, "host-configured": 3}
    for tid, spec in sorted(tools.items(), key=lambda kv: (order.get(kv[1].get("tier"), 9), kv[0])):
        if spec.get("tier") == "host-configured":
            continue
        mb = spec.get("size_mb")
        size = "-" if mb is None else ("included" if mb == 0 else
                                       (f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb} MB"))
        method = (spec.get("provision") or {}).get("method")
        wer = ("you, before Zanmai starts" if spec.get("tier") == "prerequisite"
               else who.get(method, "you, with one command"))
        purpose = (spec.get("purpose") or "").split(". ")[0].rstrip(".")
        lines.append(f"| `{tid}` | {purpose} | {size} | {wer} |")
    return "\n".join(lines)


def _size_text(spec: dict) -> str:
    """What this tool costs in disk, or nothing where it was never measured."""
    mb = spec.get("size_mb")
    if mb is None:
        return ""
    if mb == 0:
        return "included"
    return f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def cmd_tools_list(args: argparse.Namespace) -> int:
    """Every outside program Zanmai can use, with what it is for and what it costs.

    Written because a user was asked whether to fetch a group of tools and could not see
    which ones they were: the setup skill named their purpose and withheld their names, so
    the question had no answer. A number nobody sees is not transparency.
    """
    space = Path(args.space).resolve()
    tools = _load_register().get("tools", {})
    osname = _current_os()
    if getattr(args, "markdown", False):
        print(_tools_table(tools))
        return 0
    tiers = [("prerequisite", "You bring these. Zanmai never installs them behind your back."),
             ("on-demand", "Fetched the first time a job needs it."),
             ("recommended", "Makes things easier, never required."),
             ("host-configured", "Set up at the host, nothing to install here.")]
    cache = _load_tool_cache(space)
    total = 0
    for tier, what in tiers:
        rows = sorted((t, sp) for t, sp in tools.items() if sp.get("tier") == tier)
        if not rows:
            continue
        print(f"\n{tier} ({len(rows)}) - {what}")
        for tid, spec in rows:
            present = _detect_tool_cached(space, tid, spec, osname, cache).get("present")
            mark = "have" if present is True else ("--" if present is False else "??")
            size = _size_text(spec)
            if present is not True and spec.get("size_mb"):
                total += spec["size_mb"]
            fetches = (spec.get("provision") or {}).get("method") in (
                "venv-pip", "node-package", "file-fetch", "binary-fetch")
            who = "Zanmai fetches" if fetches and tier == "on-demand" else "you install"
            if tier in ("prerequisite", "host-configured"):
                who = ""
            purpose = (spec.get("purpose") or "").split(". ")[0]
            print(f"  [{mark}] {tid:15} {size:>9}  {who:15} {purpose[:70]}")
    if total:
        print(f"\nStill missing, added up: about {total} MB. Libraries share dependencies, "
              f"so the real total is lower.")
    print("\nSizes measured on macOS; see zanmai/system/docs/tools.md for the same list in prose.")
    _save_tool_cache(space, cache)
    return 0


def cmd_tools_check(args: argparse.Namespace) -> int:
    space = Path(args.space).resolve()
    spec = (_load_register().get("tools") or {}).get(args.id)
    if not spec:
        print(json.dumps({"error": f"unknown tool id: {args.id}"}))
        return 1
    res = _detect_tool(space, args.id, spec, _current_os())
    print(json.dumps({"id": args.id, "tier": spec.get("tier"), **res}, ensure_ascii=False, indent=2))
    return 0


def _ensure_runtime_venv(space: Path) -> tuple[Path | None, str]:
    import subprocess
    py = _runtime_venv_python(space)
    if py:
        return py, "present"
    d = _runtime_venv_dir(space)
    d.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "venv", str(d)] if shutil.which("uv") else _user_python_cmd(space).split() + ["-m", "venv", str(d)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return None, f"venv create failed: {(r.stderr or r.stdout).strip()[:160]}"
    except Exception as e:
        return None, f"venv create error: {type(e).__name__}: {e}"
    return _runtime_venv_python(space), "created"


def _fetch_plain_file(space: Path, tool_id: str, spec: dict, prov: dict) -> dict:
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
    target = space / prov["target"]
    _space_mkdir(space, target.parent, parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}-download")
    # An interrupted fetch used to throw away what it had. On a 1.6 GB model over a home line that
    # is minutes, and it happened: 962 MB were on disk and the next attempt started at zero. The
    # part-file is kept and continued with a Range request. Where the server will not resume, the
    # part-file is dropped and the whole thing is fetched again, which is the old behaviour and now
    # the fallback rather than the rule.
    schon = tmp.stat().st_size if tmp.exists() else 0
    kopf = {"Range": f"bytes={schon}-"} if schon else {}
    try:
        anfrage = urllib.request.Request(url, headers=kopf)
        with urllib.request.urlopen(anfrage, timeout=600) as response:
            fortgesetzt = response.status == 206
            with tmp.open("ab" if fortgesetzt else "wb") as out:
                shutil.copyfileobj(response, out)
    except Exception as exc:  # noqa: BLE001
        # What arrived stays on disk, so the next attempt continues instead of starting over.
        gehalten = tmp.stat().st_size / (1024 * 1024) if tmp.exists() else 0
        return {"state": "WARNING", "detail": f"download failed: {type(exc).__name__}: {exc}",
                "url": url, "kept_mb": round(gehalten),
                "note": "the part already fetched is kept; run the same command again to continue"}

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
        ffmpeg = _tool_path(space, "ffmpeg")
        whisper = _tool_path(space, canary) or shutil.which(canary)
        if not (ffmpeg and whisper):
            return {"state": "installed", "path": str(target.relative_to(space)),
                    "size_mb": round(size_mb),
                    "detail": "downloaded, not proven: the tools to try it are not on this machine"}
        work = space / SCRATCH_DIR / "voice"
        work.mkdir(parents=True, exist_ok=True)
        probe = work / "canary.wav"
        try:
            subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                            "-t", "1", str(probe)], check=True, capture_output=True)
            subprocess.run([whisper, "-m", str(target), "-f", str(probe), "--no-prints"],
                           check=True, capture_output=True, timeout=300)
        except Exception as exc:  # noqa: BLE001
            return {"state": "WARNING", "path": str(target.relative_to(space)),
                    "detail": f"downloaded but it does not load: {type(exc).__name__}"}
        finally:
            probe.unlink(missing_ok=True)
        return {"state": "installed", "path": str(target.relative_to(space)),
                "size_mb": round(size_mb), "detail": "proven by transcribing a canary"}
    return {"state": "installed", "path": str(target.relative_to(space)), "size_mb": round(size_mb)}


def _fetch_pinned_binary(space: Path, tool_id: str, spec: dict, os_spec: dict, prov: dict) -> dict:
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
    target_dir = space / prov.get("into", f"{RUNTIME_DIR}/bin")
    _space_mkdir(space, target_dir, parents=True, exist_ok=True)
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
        source = space / canary
        if not source.is_file():
            return {"state": "WARNING", "path": str(installed),
                    "detail": f"canary missing at {canary}, so the install is unproven"}
        out_pdf = space / RUNTIME_DIR / f"{tool_id}-canary.pdf"
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
    """Everything this space could need, in one pass, offered at setup instead of drop by drop.

    Without `--yes` it only reports, and that report is the question the user answers. Nothing that
    costs money, needs an account or wants a decision is included: those are listed as theirs to
    do. The point is that a user should not meet a missing prerequisite for the first time in the
    middle of a job that is already running.
    """
    import io
    import contextlib
    space = Path(args.space).resolve()
    tools = (_load_register().get("tools") or {})
    osname = _current_os()

    da, selbst, automatisch, extern = [], [], [], []
    for tid, spec in sorted(tools.items()):
        if spec.get("kind") == "mcp":
            extern.append(tid)
            continue
        if _detect_tool(space, tid, spec, osname).get("present") is True:
            da.append(tid)
            continue
        method = (spec.get("provision") or {}).get("method")
        ziel = automatisch if method in ("venv-pip", "node-package", "file-fetch", "binary-fetch") else selbst
        ziel.append((tid, spec, method))

    print(f"{len(da)} of {len(tools)} tool(s) already here.")
    if automatisch:
        summe = sum(sp.get("size_mb") or 0 for _t, sp, _m in automatisch)
        print(f"\nZanmai can fetch these itself ({len(automatisch)}"
              + (f", about {summe} MB together" if summe else "") + "):")
        for tid, spec, _m in automatisch:
            groesse = _size_text(spec)
            print(f"  {tid:15} {groesse:>9}  {(spec.get('purpose') or '').split('. ')[0]}.")
    if selbst:
        print(f"\nThese are yours to install, each with the one command that does it ({len(selbst)}):")
        for tid, spec, _m in selbst:
            hint = ((spec.get("os") or {}).get(osname) or {}).get("install_hint") or {}
            groesse = _size_text(spec)
            print(f"  {tid:15} {groesse:>9}  {hint.get('text') or (spec.get('purpose') or '').split('. ')[0]}")
    if extern:
        print(f"\nConfigured at the host, not here: {', '.join(extern)}")
    if not automatisch:
        print("\nNothing left for Zanmai to fetch.")
        return 0
    if not args.yes:
        print("\nSay the word and Zanmai fetches the first group; the second stays yours. "
              "`--only a,b` fetches just those.")
        return 0

    gewaehlt = [x.strip() for x in (getattr(args, "only", "") or "").split(",") if x.strip()]
    if gewaehlt:
        unbekannt = [g for g in gewaehlt if g not in {t for t, _s, _m in automatisch}]
        if unbekannt:
            print(f"not on the fetchable list: {', '.join(unbekannt)}")
            return 1
        automatisch = [x for x in automatisch if x[0] in gewaehlt]

    print("")
    fehler = 0
    for tid, _spec, _m in automatisch:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            # `--yes` is already the gate on this command: the user answered the report above
            # before this loop runs, so the consent is carried through rather than asked twice.
            rc = cmd_tools_ensure(argparse.Namespace(space=str(space), id=tid, yes=True))
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
    space = Path(args.space).resolve()
    spec = (_load_register().get("tools") or {}).get(args.id)
    if not spec:
        print(json.dumps({"error": f"unknown tool id: {args.id}"}))
        return 1
    osname = _current_os()
    if _detect_tool(space, args.id, spec, osname).get("present") is True:
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
    # Nothing is fetched or installed on this machine without the user saying so, whatever it
    # costs. `ensure-all` had this gate from the start and `ensure` did not, and the gap is not
    # theoretical: a background run fetched 1.6 GB of model weights that nobody had agreed to,
    # while its own question about that very download sat unanswered on a work object. Without
    # `--yes` this reports what it would cost, and that report is the question the user answers.
    if not getattr(args, "yes", False):
        mb = spec.get("size_mb")
        groesse = "unmeasured" if mb is None else (f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb} MB")
        print(json.dumps({
            "id": args.id, "state": "needs-consent", "tier": tier, "method": method,
            "size": groesse,
            "purpose": (spec.get("purpose") or "").split(". ")[0],
            "target": prov.get("target") or prov.get("into") or prov.get("root") or f"{RUNTIME_DIR}/",
            "ask": f"Tell the user what this costs and what it is for, then run "
                   f"`tools ensure {args.id} --yes` once they agree.",
        }, ensure_ascii=False, indent=2))
        return 0
    if method == "venv-pip":
        py, note = _ensure_runtime_venv(space)
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
        ok = _detect_lib(space, (spec.get("detect") or {}).get("import", args.id)).get("present")
        print(json.dumps({"id": args.id, "state": "installed" if ok else "WARNING",
                          "pip": pkg, "runtime": str(py), "venv": note}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if method == "file-fetch":
        if not (prov.get("url") and prov.get("target")):
            print(json.dumps({"id": args.id, "state": "needs-user", "tier": tier,
                              "detail": "no url and target for this file, so nothing is fetched on a guess"},
                             ensure_ascii=False, indent=2))
            return 0
        result = _fetch_plain_file(space, args.id, spec, prov)
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
        result = _fetch_pinned_binary(space, args.id, spec, os_spec, prov)
        print(json.dumps({"id": args.id, **result}, ensure_ascii=False, indent=2))
        return 0 if result.get("state") == "installed" else 1
    if method == "node-package":
        # Installed into the space's own runtime tree, never globally: a global install needs
        # rights this script must not assume, and it would leak one space's pinned version into
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
        wurzel = space / (prov.get("root") or f"{RUNTIME_DIR}/node")
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
        ok = _detect_tool(space, args.id, spec, osname)
        print(json.dumps({"id": args.id, "state": "installed" if ok.get("present") else "WARNING",
                          "package": spez, "root": str(wurzel.relative_to(space)),
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

def _tool_cache_path(space: Path) -> Path:
    """Detection results live here, in the writable runtime tree that updates
    never touch. The register stays static and presence-free; this is the second,
    dynamic database of what was found on THIS machine, so a preflight is a quick
    look, not a full rescan each time."""
    return space / RUNTIME_DIR / "tool-cache.json"


# Facts a run establishes about the ground it stands on: a typeface is installed, a bundle file
# sits at this path, a helper answers on this port. Each one costs a minute to establish and gives
# the same answer every time, so a run that establishes it again has spent that minute for nothing.
# Measured on one piece of work: fifteen runs in a row re-checked the same typeface.
#
# What makes this more than a cache is the scope, and the scope is the whole point. "Montserrat is
# installed" is true of a machine, "poppler is here" of an installation, "the bundle is at this
# path" of one bundle. Without saying which, a run on another machine reads a stranger's finding
# and believes it. So a fact carries what it is about, and a fact about a machine is checked
# against the machine before it is handed back.
FACTS_FILE = "facts.json"
FACT_SCOPES = ("machine", "install", "bundle")


def _facts_path(space: Path) -> Path:
    # Under runtime, which is machine-local and never travels in a backup. A findings file that
    # syncs to a second computer is worse than none: it is confidently wrong there.
    return space / RUNTIME_DIR / FACTS_FILE


def _machine_signature() -> str:
    """What identifies this machine well enough that a finding about it can be trusted here."""
    import platform
    return f"{platform.node()}|{platform.system()}|{platform.machine()}"


def _facts_load(space: Path) -> dict:
    try:
        return json.loads(_facts_path(space).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _facts_save(space: Path, facts: dict) -> None:
    ziel = _facts_path(space)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _fact_valid_here(eintrag: dict) -> tuple[bool, str]:
    """Whether a recorded fact still applies in this run, and why not where it does not."""
    if eintrag.get("scope") == "machine" and eintrag.get("machine") != _machine_signature():
        return False, "recorded on a different machine"
    return True, ""


def cmd_fact_set(args: argparse.Namespace) -> int:
    """Write down something established, with what it is about and when."""
    space = _work_space(args)
    facts = _facts_load(space)
    schluessel = args.key.strip()
    facts[schluessel] = {
        "value": args.value,
        "scope": args.scope,
        "about": args.about or "",
        "recorded": _today(),
        "machine": _machine_signature(),
        "by": args.agent or "",
    }
    _facts_save(space, facts)
    print(f"ok: {schluessel} = {args.value} (about this {args.scope}"
          + (f", {args.about}" if args.about else "") + f", {_today()})")
    return 0


def cmd_fact_get(args: argparse.Namespace) -> int:
    """Read one back, or say plainly that it has to be established."""
    space = _work_space(args)
    eintrag = _facts_load(space).get(args.key.strip())
    if not eintrag:
        print(f"unknown: {args.key} has not been established here. Find out, then "
              f"`fact set {args.key} <value>`.")
        return 1
    gilt, warum = _fact_valid_here(eintrag)
    if not gilt:
        print(f"stale: {args.key} was {eintrag['value']} on {eintrag['recorded']}, but {warum}. "
              f"Establish it again here.")
        return 1
    ueber = f" about {eintrag['about']}" if eintrag.get("about") else ""
    print(f"{eintrag['value']}\n  established {eintrag['recorded']}, holds for this "
          f"{eintrag['scope']}{ueber}")
    return 0


def cmd_fact_list(args: argparse.Namespace) -> int:
    space = _work_space(args)
    facts = _facts_load(space)
    if not facts:
        print("nothing established yet")
        return 0
    for schluessel, eintrag in sorted(facts.items()):
        gilt, warum = _fact_valid_here(eintrag)
        mark = "ok" if gilt else "--"
        ueber = f" ({eintrag['about']})" if eintrag.get("about") else ""
        print(f"  [{mark}] {schluessel:28} {str(eintrag['value'])[:28]:28} "
              f"{eintrag['scope']}{ueber}, {eintrag['recorded']}" + (f"; {warum}" if warum else ""))
    return 0


def cmd_fact_forget(args: argparse.Namespace) -> int:
    space = _work_space(args)
    facts = _facts_load(space)
    if args.key.strip() not in facts:
        print(f"unknown: {args.key}", file=sys.stderr)
        return 1
    facts.pop(args.key.strip())
    _facts_save(space, facts)
    print(f"ok: {args.key} forgotten; the next run establishes it again")
    return 0


def _load_tool_cache(space: Path) -> dict:
    p = _tool_cache_path(space)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_tool_cache(space: Path, cache: dict) -> None:
    p = _tool_cache_path(space)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _detect_tool_cached(space: Path, tid: str, spec: dict, osname: str,
                        cache: dict, refresh: bool = False) -> dict:
    """Detection with the machine-local cache. A cached present-hit is validated
    cheaply before it is trusted (binary path still exists / venv python
    unchanged); anything absent or stale re-detects and re-registers. This is how
    a change gets picked up without paying a full scan every time."""
    method = (spec.get("detect") or {}).get("method")
    if refresh or method not in ("which", "runtime", "import"):
        return _detect_tool(space, tid, spec, osname)
    entry = (cache.get("tools") or {}).get(tid)
    if entry and entry.get("os") == osname and entry.get("present") is True:
        if method in ("which", "runtime") and entry.get("path") and os.path.exists(entry["path"]):
            return {**entry, "cached": True}
        if method == "import":
            vp = _runtime_venv_python(space)
            if vp and str(vp) == entry.get("runtime"):
                return {**entry, "cached": True}
    res = _detect_tool(space, tid, spec, osname)
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
    space = Path(args.space).resolve()
    reg = _load_register()
    tools = reg.get("tools") or {}
    osname = _current_os()
    ids = _required_tool_ids(reg, args.expert, args.capability)
    cache = _load_tool_cache(space)
    present, auto_provision, needs_user, notes = [], [], [], []
    for tid in ids:
        spec = tools.get(tid)
        if not spec:
            needs_user.append({"id": tid, "why": "unknown tool id (register gap)", "how": None, "tier": "unknown"})
            continue
        res = _detect_tool_cached(space, tid, spec, osname, cache, refresh=args.refresh)
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
    _save_tool_cache(space, cache)
    ready = not needs_user and not auto_provision
    print(json.dumps({"expert": args.expert, "capability": args.capability, "os": osname,
                      "ready": ready, "present": present, "auto_provision": auto_provision,
                      "needs_user": needs_user, "notes": notes},
                     ensure_ascii=False, indent=2))
    return 0


def _find_space_root(start: Path) -> Path | None:
    p = start.resolve()
    for cand in [p] + list(p.parents):
        if (cand / SYSTEM_DIR).is_dir():
            return cand
    return None


def _activate_runtime_venv_site(space: Path) -> None:
    """Make libraries provisioned into the runtime venv importable in-process, so
    a media command run under the recorded python can use what `tools ensure`
    installed. Same-Python assumption: the runtime venv is built with the space's
    python_cmd, so its compiled extensions match this interpreter's ABI."""
    py = _runtime_venv_python(space)
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

    puffer, mit = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stderr(puffer), contextlib.redirect_stdout(mit):
            rc = args.func(args)
    finally:
        text, ausgabe = puffer.getvalue(), mit.getvalue()
        if text:
            sys.stderr.write(text)
        if ausgabe:
            sys.stdout.write(ausgabe)
    if rc == 2:
        name = getattr(args, "hook_cmd", None) or getattr(args, "subcmd", None) or "hook"
        _guard_refused(_LAST_PAYLOAD, str(name), text or f"exit 2 from {name}")
    # A guard that asks is deliberately not written down. The question stood on the user's screen
    # and they answered it, so repeating it in tomorrow's briefing tells them nothing they have not
    # seen, while pushing real entries out of a list that stops at 25. What a refusal is written
    # down for is the opposite case: nobody saw it. Whatever else is wanted afterwards sits in the
    # host's own record of the conversation, which `session digest` reads.
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
    pmse.add_argument("space", nargs="?", default=".")
    pmse.set_defaults(func=cmd_media_signer_ensure)

    # tools -----
    p_tools = sub.add_parser("tools", help="External-tool register: detect and provision what dist needs, per OS.")
    sub_tools = p_tools.add_subparsers(dest="subcmd", required=True)
    pt_doc = sub_tools.add_parser("doctor", help="Detect every registered tool on this machine.")
    pt_doc.add_argument("space", nargs="?", default=".")
    pt_doc.add_argument("--refresh", action="store_true", help="Ignore the cache and re-detect everything.")
    pt_doc.set_defaults(func=cmd_tools_doctor)
    pt_pf = sub_tools.add_parser("preflight", help="Check an expert's prerequisites before dispatch (deterministic, cache-backed). Steve runs this first.")
    pt_pf.add_argument("expert")
    pt_pf.add_argument("--capability", default=None, help="Gate only this path's required tools (e.g. --capability html for a Carol flyer).")
    pt_pf.add_argument("--refresh", action="store_true", help="Ignore the cache and re-detect.")
    pt_pf.add_argument("space", nargs="?", default=".")
    pt_pf.set_defaults(func=cmd_tools_preflight)
    pt_chk = sub_tools.add_parser("check", help="Detect one tool by id.")
    pt_chk.add_argument("id")
    pt_chk.add_argument("space", nargs="?", default=".")
    pt_chk.set_defaults(func=cmd_tools_check)
    pt_lst = sub_tools.add_parser("list", help="Every outside program Zanmai can use: what it is for, how big it is, who installs it.")
    pt_lst.add_argument("space", nargs="?", default=".")
    pt_lst.add_argument("--markdown", action="store_true", help="The register as a table, the form the documentation page carries.")
    pt_lst.set_defaults(func=cmd_tools_list)
    pt_ens = sub_tools.add_parser("ensure", help="Provision an on-demand tool at first use. Reports what it would cost; fetches only with --yes.")
    pt_ens.add_argument("id")
    pt_ens.add_argument("space", nargs="?", default=".")
    pt_ens.add_argument("--yes", action="store_true",
                        help="The user agreed to this download or install. Without it nothing is fetched.")
    pt_ens.set_defaults(func=cmd_tools_ensure)

    pt_all = sub_tools.add_parser("ensure-all", help="What this space still needs, in one pass. Reports without --yes; that report is the question the user answers.")
    pt_all.add_argument("space", nargs="?", default=".")
    pt_all.add_argument("--yes", action="store_true", help="Fetch everything Zanmai can fetch itself. What needs the user, or money, or an account stays theirs.")
    pt_all.add_argument("--only", default="", help="Comma-separated ids to fetch instead of the whole group, so the answer can be some rather than all.")
    pt_all.set_defaults(func=cmd_tools_ensure_all)

    # setup -----
    p_setup = sub.add_parser("setup", help="First-time install, validate, and (future) update.")
    sub_setup = p_setup.add_subparsers(dest="subcmd", required=True)

    ps_init = sub_setup.add_parser("init", help="First-time install.")
    ps_init.add_argument("space_root", nargs="?", default=".")
    ps_init.add_argument("--first-name", required=True, dest="first_name")
    ps_init.add_argument("--last-name", required=True, dest="last_name")
    ps_init.add_argument("--language", default="auto")
    ps_init.add_argument("--email", default="")
    ps_init.add_argument("--preferred-address", default="", dest="preferred_address",
                         help="A nickname or short form distinct from first-name. Empty means same as first-name.")
    ps_init.add_argument("--python-cmd", default="python3", dest="python_cmd",
                         help="The Python invocation that works on this machine.")
    ps_init.add_argument("--purpose", choices=PURPOSE_CHOICES,
                         help="What the space is mainly for: private, professional, one named "
                              "project, all (a mix), or unclear.")
    ps_init.add_argument("--purpose-detail", dest="purpose_detail", default="",
                         help="The project's name when --purpose is 'project', or the user's own "
                              "words when it is 'unclear'.")
    ps_init.add_argument("--bundles", default="",
                         help="Comma-separated names of broad, ongoing life areas to create as "
                              "empty bundles under life/, e.g. 'Health,Finances,Family'.")
    ps_init.add_argument("--goals", default="",
                         help="Comma-separated personal goals without a fixed end, each becomes "
                              "its own empty bundle under life/.")
    ps_init.add_argument("--projects", default="",
                         help="Comma-separated named projects WITH an end, each becomes its own "
                              "empty bundle under workbench/.")
    # (deterministic, matching the session-start recheck), so these are not relied on.
    ps_init.set_defaults(func=cmd_setup_init)

    ps_catchup = sub_setup.add_parser("catch-up", help="Ask and record what a later setup version added, for a space that predates it. Called by the greeting skill's gate, not by hand.")
    ps_catchup.add_argument("space_root", nargs="?", default=".")
    ps_catchup.add_argument("--purpose", choices=PURPOSE_CHOICES)
    ps_catchup.add_argument("--purpose-detail", dest="purpose_detail", default="")
    ps_catchup.add_argument("--bundles", default="")
    ps_catchup.add_argument("--goals", default="")
    ps_catchup.add_argument("--projects", default="")
    ps_catchup.add_argument("--declined", action="store_true",
                            help="The block was put to the user and they said not now. Needed to "
                                 "record that outcome, because an empty call is refused: the stamp "
                                 "ends the asking and may not be set before an answer exists.")
    ps_catchup.set_defaults(func=cmd_setup_catchup)

    ps_validate = sub_setup.add_parser("validate", help="Check the space is initialised and structurally sound.")
    ps_validate.add_argument("space_root", nargs="?", default=".")
    ps_validate.set_defaults(func=cmd_setup_validate)

    ps_update = sub_setup.add_parser("update", help="Refresh host-side config after the distribution files changed (agent and skill symlinks, .claude/settings.json). Pepper's update workflow runs this after upgrade.")
    ps_update.add_argument("space_root", nargs="?", default=".")
    ps_update.set_defaults(func=cmd_setup_update)

    ps_upgrade = sub_setup.add_parser("upgrade", help="Fetch the newest published version over HTTPS and replace the distribution files. Works the same whether the space was cloned or unpacked from an archive. Never touches user-immune paths; Pepper snapshots first.")
    ps_upgrade.add_argument("space_root", nargs="?", default=".")
    ps_upgrade.add_argument("--check", action="store_true", help="Only report whether a newer version exists.")
    ps_upgrade.add_argument("--to", metavar="VERSION",
                            help="Go to this published version instead of the newest, backwards "
                                 "included. A snapshot is taken first. Use when a release has to be "
                                 "undone: nothing else in Zanmai moves a space back.")
    ps_upgrade.add_argument("--channel", metavar="NAME",
                             help="Switch which branch this space tracks (e.g. 'beta') and remember "
                                  "the choice in zanmai/user.md. 'release' switches back to the "
                                  "manifest's default branch. Omit to use whatever is already set.")
    ps_upgrade.add_argument("--changelog", action="store_true",
                             help="With --check, also print the remote CHANGELOG.md, unapplied.")
    ps_upgrade.add_argument("--force", action="store_true",
                             help="Apply the files again even when the version says there is "
                                  "nothing to do. For a release re-cut under the same number, and "
                                  "for a space whose last update did not finish. Snapshots first "
                                  "like any other update.")
    ps_upgrade.add_argument("--from", dest="from_source", metavar="PATH|URL",
                             help="Update from this folder, archive or URL instead of from the "
                                  "published release. For a version that is not published yet and "
                                  "for a fix that has to reach a space before a release exists. "
                                  "Always snapshots first; the version is read from the source.")
    ps_upgrade.set_defaults(func=cmd_setup_upgrade)

    ps_post = sub_setup.add_parser("post-upgrade", help="The tail of an upgrade, run by the new script on itself: host refresh, verification, version marker. Called by 'setup upgrade', not by hand.")
    ps_post.add_argument("space_root", nargs="?", default=".")
    ps_post.add_argument("--from", dest="from_version", default="", help="Version the space was on before.")
    ps_post.add_argument("--to", dest="to_version", default="", help="Version that was just installed. Defaults to the shipped one.")
    ps_post.add_argument("--origin", default="", help="Where the new version came from, for the success message.")
    ps_post.add_argument("--replaced", type=int, help="Number of files replaced, for the success message.")
    ps_post.add_argument("--withdrawn", type=int, help="Number of files withdrawn, for the success message.")
    ps_post.set_defaults(func=cmd_setup_post_upgrade)

    # snapshot -----
    p_snap = sub.add_parser("snapshot", help="Space and dist snapshots.")
    sub_snap = p_snap.add_subparsers(dest="subcmd", required=True)

    ps_create = sub_snap.add_parser("create", help="Take a snapshot: commit the whole space into the history. Respects auto_snapshots in user.md.")
    ps_create.add_argument("space", nargs="?", default=".")
    ps_create.add_argument("--reason", required=True, help="Short slug naming why the snapshot is taken; it becomes the snapshot's message.")
    ps_create.set_defaults(func=cmd_snapshot_create)

    ps_enable = sub_snap.add_parser("enable", help="Turn auto_snapshots ON in zanmai/user.md.")
    ps_enable.add_argument("space", nargs="?", default=".")
    ps_enable.set_defaults(func=cmd_snapshot_enable)

    ps_disable = sub_snap.add_parser("disable", help="Turn auto_snapshots OFF in zanmai/user.md. No automatic snapshots until re-enabled.")
    ps_disable.add_argument("space", nargs="?", default=".")
    ps_disable.set_defaults(func=cmd_snapshot_disable)

    ps_list = sub_snap.add_parser("list", help="The snapshots, newest first, and what they occupy together.")
    ps_list.add_argument("space", nargs="?", default=".")
    ps_list.set_defaults(func=cmd_snapshot_list)

    ps_show = sub_snap.add_parser("show", help="What one snapshot changed, or one file as it was in it.")
    ps_show.add_argument("space", nargs="?", default=".")
    ps_show.add_argument("--snapshot", required=True, help="The short name from `snapshot list`.")
    ps_show.add_argument("--path", default=None, help="A space-relative path. Without it, the change list.")
    ps_show.set_defaults(func=cmd_snapshot_show)

    ps_restore = sub_snap.add_parser("restore", help="Put one file back the way it was in a snapshot. The current version goes to the trash first.")
    ps_restore.add_argument("space", nargs="?", default=".")
    ps_restore.add_argument("--snapshot", required=True, help="The short name from `snapshot list`.")
    ps_restore.add_argument("--path", help="The space-relative path to put back.")
    ps_restore.add_argument("--all", action="store_true",
                             help="Put the whole space back as it was in that snapshot. Takes a "
                                  "snapshot of the current state first, and anything that did not "
                                  "exist then goes to the trash rather than being removed.")
    ps_restore.set_defaults(func=cmd_snapshot_restore)

    ps_compact = sub_snap.add_parser("compact", help="Let git pack the history down. Loses nothing.")
    ps_compact.add_argument("space", nargs="?", default=".")
    ps_compact.set_defaults(func=cmd_snapshot_compact)

    # bundle -----


    # import -----
    p_import = sub.add_parser("import", help=f"The drop area {INBOX_DIR}/: what is waiting and which way each file goes.")
    sub_import = p_import.add_subparsers(dest="subcmd", required=True)
    pi_scan = sub_import.add_parser("scan", help="What is waiting, oldest first, with the route per file.")
    pi_scan.add_argument("space", nargs="?", default=".")
    pi_scan.add_argument("--verbose", action="store_true", help="Say what happens to each file, not just what it is.")
    pi_scan.set_defaults(func=cmd_import_scan)


    p_docs = sub.add_parser("docs", help="The documentation's own directory.")
    sub_docs = p_docs.add_subparsers(dest="subcmd", required=True)
    pd_index = sub_docs.add_parser("index", help="Rebuild the 'read this when' directory in "
                                                "docs/index.md from the pages themselves.")
    pd_index.add_argument("space", nargs="?", default=".")
    pd_index.set_defaults(func=cmd_docs_index)

    p_welcome = sub.add_parser("welcome", help="The list the session opened with, rebuilt as the "
                                               "space stands now. For when the greet has scrolled "
                                               "away and the user asks to see it again.")
    p_welcome.add_argument("space", nargs="?", default=".")
    p_welcome.set_defaults(func=cmd_welcome)

    # housekeeping -----
    p_gaps = sub.add_parser("gaps", help="what the experts wrote into builder-gaps.md recently. "
                                        "Read after a dispatch returns; it is their only channel "
                                        "while they run.")
    p_gaps.add_argument("space", nargs="?", default=".")
    p_gaps.add_argument("--hours", type=int, default=24)
    p_gaps.set_defaults(func=cmd_gaps)

    p_house = sub.add_parser("housekeeping", help=f"Clear what is past its keeping time: the trash after {TRASH_RETENTION_DAYS} days, the scratch area and the snapshots after {SCRATCH_RETENTION_DAYS}. Runs itself at session start.")
    p_house.add_argument("space", nargs="?", default=".")
    p_house.set_defaults(func=cmd_housekeeping)

    p_video = sub.add_parser("video", help="The mechanic under a cut: probe, transcribe with word timings, check a cut sheet, cut, pull frames.")
    sub_video = p_video.add_subparsers(dest="video_cmd", required=True)

    pvi_probe = sub_video.add_parser("probe", help="What a file actually is: length, size, exact frame rate, whether it carries chapters.")
    pvi_probe.add_argument("space", nargs="?", default=".")
    pvi_probe.add_argument("--file", required=True)
    pvi_probe.set_defaults(func=cmd_video_probe)

    pvi_tr = sub_video.add_parser("transcribe", help="One source to words with start and end times. Runs once per source; re-running reads the saved result.")
    pvi_tr.add_argument("space", nargs="?", default=".")
    pvi_tr.add_argument("--file", required=True)
    pvi_tr.add_argument("--slug", required=True, help="The job this belongs to.")
    pvi_tr.add_argument("--language", default="auto")
    pvi_tr.add_argument("--lexicon", help="Names from the space, to bias the recogniser.")
    pvi_tr.add_argument("--dtw-preset", dest="dtw_preset", help="Override the alignment preset; derived from the model by default.")
    pvi_tr.add_argument("--force", action="store_true", help="Transcribe again even though a result exists.")
    pvi_tr.set_defaults(func=cmd_video_transcribe)

    pvi_cs = sub_video.add_parser("cutsheet", help="Check a cut sheet before anything renders, and say what it would produce.")
    pvi_cs.add_argument("space", nargs="?", default=".")
    pvi_cs.add_argument("--file", required=True)
    pvi_cs.add_argument("--words", help="The transcript, to check that no word is cut through.")
    pvi_cs.add_argument("--text", action="store_true", help="Print the spoken line of every segment, so the cut can be read.")
    pvi_cs.set_defaults(func=cmd_video_cutsheet)

    pvi_pr = sub_video.add_parser("propose", help="A first cut sheet from the word timings: speech kept, long silence dropped. Measurement only.")
    pvi_pr.add_argument("space", nargs="?", default=".")
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
    pvi_cut.add_argument("space", nargs="?", default=".")
    pvi_cut.add_argument("--file", required=True, help="The cut sheet.")
    pvi_cut.add_argument("--out", required=True)
    pvi_cut.add_argument("--crf", type=int, default=19)
    pvi_cut.add_argument("--preset", default="medium")
    pvi_cut.add_argument("--size", help="Target WIDTHxHEIGHT. Without it, the first source decides, and a mismatch is reported.")
    pvi_cut.add_argument("--fps", help="Target frame rate as an exact fraction, e.g. 30000/1001. Without it, the first source decides.")
    pvi_cut.add_argument("--cover", type=float, default=0.0, help="Hide the seams: alternate the framing by this percent from passage to passage. About 5 is enough to stop a jump registering; 0 leaves the cuts bare.")
    pvi_cut.set_defaults(func=cmd_video_cut)

    pvi_co = sub_video.add_parser("correct", help="Fix spellings in a transcript before building from it. Without --replace it reports what looks unknown.")
    pvi_co.add_argument("space", nargs="?", default=".")
    pvi_co.add_argument("--words", required=True)
    pvi_co.add_argument("--replace", action="append", help="heard=correct, single whole words only. Repeatable.")
    pvi_co.add_argument("--list", help="A file of heard=correct lines, one per line, that grows with the brand.")
    pvi_co.add_argument("--threshold", type=float, default=0.55, help="Report words the recogniser was less certain about than this.")
    pvi_co.add_argument("--out", help="Write elsewhere instead of in place.")
    pvi_co.set_defaults(func=cmd_video_correct)

    pvi_cap = sub_video.add_parser("caption", help="Captions from the transcript: a subtitle file, and optionally burned into a copy.")
    pvi_cap.add_argument("space", nargs="?", default=".")
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
    pvi_rf.add_argument("space", nargs="?", default=".")
    pvi_rf.add_argument("--file", required=True)
    pvi_rf.add_argument("--out", required=True)
    pvi_rf.add_argument("--format", required=True, help="wide, upright, square or classic.")
    pvi_rf.add_argument("--fit", action="store_true", help="Keep the whole picture and fill the rest with a blurred enlargement, instead of cropping.")
    pvi_rf.add_argument("--centre", type=float, default=0.5, help="Where the crop window sits across the width, 0 to 1.")
    pvi_rf.add_argument("--height", type=int)
    pvi_rf.add_argument("--crf", type=int, default=19)
    pvi_rf.set_defaults(func=cmd_video_reframe)

    pvi_mx = sub_video.add_parser("mix", help="The audio passes: denoise, a music bed, levelling. The picture is copied, never re-encoded.")
    pvi_mx.add_argument("space", nargs="?", default=".")
    pvi_mx.add_argument("--file", required=True)
    pvi_mx.add_argument("--out", required=True)
    pvi_mx.add_argument("--music", help="A licensed track. Never downloaded, always supplied.")
    pvi_mx.add_argument("--music-db", dest="music_db", type=float, default=-18.0)
    pvi_mx.add_argument("--denoise", action="store_true")
    pvi_mx.add_argument("--denoise-db", dest="denoise_db", type=float, default=6.0, help="How many decibels of noise to take out. Above about 12 the voice starts to sound hollow.")
    pvi_mx.add_argument("--loudness", type=float, default=-16.0, help="Target in LUFS. -16 for speech on the web, -14 where a platform expects it.")
    pvi_mx.set_defaults(func=cmd_video_mix)

    pvi_ex = sub_video.add_parser("export", help="One file per purpose. The master is never overwritten.")
    pvi_ex.add_argument("space", nargs="?", default=".")
    pvi_ex.add_argument("--file", required=True)
    pvi_ex.add_argument("--name", required=True, help="What the piece is called, without a suffix.")
    pvi_ex.add_argument("--profile", default="master,web", help="Comma-separated: master, web, platform.")
    pvi_ex.add_argument("--out-dir", dest="out_dir")
    pvi_ex.add_argument("--overwrite", action="store_true")
    pvi_ex.set_defaults(func=cmd_video_export)

    pvi_tx = sub_video.add_parser("text", help="Write the transcript out for editing, or read an edited one back as a cut.")
    pvi_tx.add_argument("space", nargs="?", default=".")
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
    pvi_sy.add_argument("space", nargs="?", default=".")
    pvi_sy.add_argument("--a", required=True)
    pvi_sy.add_argument("--b", required=True)
    pvi_sy.add_argument("--slug", default="sync")
    pvi_sy.add_argument("--window", type=float, default=180.0, help="Seconds compared from the start of each file.")
    pvi_sy.add_argument("--max-offset", dest="max_offset", type=float, default=60.0)
    pvi_sy.add_argument("--min-confidence", dest="min_confidence", type=float, default=1.0)
    pvi_sy.set_defaults(func=cmd_video_sync)

    pvi_br = sub_video.add_parser("brand", help="An opening, a closing and a logo held throughout, from the brand.")
    pvi_br.add_argument("space", nargs="?", default=".")
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
    pvi_chap.add_argument("space", nargs="?", default=".")
    pvi_chap.add_argument("--words", required=True)
    pvi_chap.add_argument("--out")
    pvi_chap.add_argument("--count", type=int, default=8)
    pvi_chap.add_argument("--min-gap", dest="min_gap", type=float, default=45.0)
    pvi_chap.add_argument("--title-words", dest="title_words", type=int, default=6)
    pvi_chap.set_defaults(func=cmd_video_chapters)

    pvi_th = sub_video.add_parser("thumbnail", help="Candidates for a thumbnail: the sharpest, best-lit frames.")
    pvi_th.add_argument("space", nargs="?", default=".")
    pvi_th.add_argument("--file", required=True)
    pvi_th.add_argument("--out")
    pvi_th.add_argument("--slug", default="thumbs")
    pvi_th.add_argument("--sample", type=int, default=24)
    pvi_th.add_argument("--keep", type=int, default=5)
    pvi_th.set_defaults(func=cmd_video_thumbnail)

    pvi_tl = sub_video.add_parser("timeline", help="One picture of the whole piece: filmstrip, loudness, words. The cheap way to look.")
    pvi_tl.add_argument("space", nargs="?", default=".")
    pvi_tl.add_argument("--file", required=True)
    pvi_tl.add_argument("--words", help="Transcript, to write the words along the strip.")
    pvi_tl.add_argument("--columns", type=int, default=12)
    pvi_tl.add_argument("--slug", default="timeline")
    pvi_tl.add_argument("--out")
    pvi_tl.set_defaults(func=cmd_video_timeline)

    pvi_bf = sub_video.add_parser("brief", help="Everything needed to judge footage, in one call: facts, loudness, transcript, a few frames. Cheap on purpose.")
    pvi_bf.add_argument("space", nargs="?", default=".")
    pvi_bf.add_argument("--file", required=True)
    pvi_bf.add_argument("--slug", default="brief", help="Where the transcript is kept, so later steps reuse it.")
    pvi_bf.add_argument("--language", default="auto")
    pvi_bf.add_argument("--sample-over", dest="sample_over", type=float, default=600.0, help="Longer than this and the words come from three samples instead of the whole thing.")
    pvi_bf.add_argument("--sample-seconds", dest="sample_seconds", type=float, default=90.0)
    pvi_bf.add_argument("--columns", type=int, default=12, help="How many stills go into the one overview picture.")
    pvi_bf.set_defaults(func=cmd_video_brief)

    pvi_ck = sub_video.add_parser("check", help="The measurable half of a review: duplicated frames, brightness steps at the joins, actual length.")
    pvi_ck.add_argument("space", nargs="?", default=".")
    pvi_ck.add_argument("--file", required=True)
    pvi_ck.add_argument("--seams", help="Comma-separated seconds where a graphic was composited in. A plain cut is not a seam in this sense.")
    pvi_ck.add_argument("--composited", action="store_true", help="The file came out of a composite. Only then are duplicated frames a fault rather than a still screen.")
    pvi_ck.add_argument("--duplicate-limit", dest="duplicate_limit", type=float, default=8.0)
    pvi_ck.add_argument("--luma-limit", dest="luma_limit", type=float, default=0.06)
    pvi_ck.add_argument("--max-seams", dest="max_seams", type=int, default=40)
    pvi_ck.set_defaults(func=cmd_video_check)

    pvi_fr = sub_video.add_parser("frames", help="Pull frames so they can be looked at.")
    pvi_fr.add_argument("space", nargs="?", default=".")
    pvi_fr.add_argument("--file", required=True)
    pvi_fr.add_argument("--slug", default="review")
    pvi_fr.add_argument("--at", help="Comma-separated seconds. Without it, an even sample.")
    pvi_fr.add_argument("--count", type=int, default=6)
    pvi_fr.add_argument("--out")
    pvi_fr.set_defaults(func=cmd_video_frames)

    p_voice = sub.add_parser("voice", help="Voice notes waiting in the import folder: what waits, the space's names, transcription, filing.")
    sub_voice = p_voice.add_subparsers(dest="voice_cmd", required=True)

    pv_scan = sub_voice.add_parser("scan", help="What is waiting to be transcribed, oldest first.")
    pv_scan.add_argument("space", nargs="?", default=".")
    pv_scan.set_defaults(func=cmd_voice_scan)

    pv_lex = sub_voice.add_parser("lexicon", help="The space's own names, to bias the recogniser before it starts.")
    pv_lex.add_argument("space", nargs="?", default=".")
    pv_lex.add_argument("--out", help="Also write the list here.")
    pv_lex.add_argument("--budget", type=int, default=LEXICON_BUDGET_CHARS)
    pv_lex.set_defaults(func=cmd_voice_lexicon)

    pv_tr = sub_voice.add_parser("transcribe", help="One recording to text, locally, biased by the space's names.")
    pv_tr.add_argument("space", nargs="?", default=".")
    pv_tr.add_argument("--file", required=True)
    pv_tr.add_argument("--lexicon", help="File written by `voice lexicon --out`.")
    pv_tr.add_argument("--language", default="auto")
    pv_tr.set_defaults(func=cmd_voice_transcribe)

    pv_ar = sub_voice.add_parser("archive", help="Move a processed recording into the day it was spoken on, keeping it.")
    pv_ar.add_argument("space", nargs="?", default=".")
    pv_ar.add_argument("--file", required=True)
    pv_ar.add_argument("--agent")
    pv_ar.set_defaults(func=cmd_voice_archive)

    pv_ja = sub_voice.add_parser("journal-append", help="Append text to the daily note of the day the recording was made, not the day it is read.")
    pv_ja.add_argument("space", nargs="?", default=".")
    pv_ja.add_argument("--file", required=True)
    pv_ja.add_argument("--text", required=True)
    pv_ja.set_defaults(func=cmd_voice_journal_append)

    p_fact = sub.add_parser("fact", help="What a run established about this machine, install or bundle, so the next one does not establish it again.")
    sub_fact = p_fact.add_subparsers(dest="fact_cmd", required=True)

    pfa_set = sub_fact.add_parser("set", help="Write down something established, with what it is about.")
    pfa_set.add_argument("key", help="Short name, e.g. `font.montserrat` or `bundle.path`.")
    pfa_set.add_argument("value")
    pfa_set.add_argument("--space", default=None)
    pfa_set.add_argument("--scope", choices=list(FACT_SCOPES), default="machine",
                         help="What it is true of. A machine fact is refused on another machine.")
    pfa_set.add_argument("--about", default="", help="Which install or bundle, where that is what it hangs on.")
    pfa_set.add_argument("--agent", default="")
    pfa_set.set_defaults(func=cmd_fact_set)

    pfa_get = sub_fact.add_parser("get", help="Read one back. Exit 1 where it is unknown or does not hold here.")
    pfa_get.add_argument("key")
    pfa_get.add_argument("--space", default=None)
    pfa_get.set_defaults(func=cmd_fact_get)

    pfa_list = sub_fact.add_parser("list", help="Everything established, and whether it still holds here.")
    pfa_list.add_argument("--space", default=None)
    pfa_list.set_defaults(func=cmd_fact_list)

    pfa_forget = sub_fact.add_parser("forget", help="Drop one, so the next run establishes it again.")
    pfa_forget.add_argument("key")
    pfa_forget.add_argument("--space", default=None)
    pfa_forget.set_defaults(func=cmd_fact_forget)

    p_survey = sub.add_parser("survey", help="What a pile of files is, established by machine: dates, amounts, parties, opening. Read this before reading the files.")
    p_survey.add_argument("path", help="A file or a folder.")
    p_survey.add_argument("--space", default=None)
    p_survey.add_argument("--json", action="store_true", help="As JSON, for a run to read.")
    p_survey.add_argument("--opening", type=int, default=400, help="How much of the opening to carry.")
    p_survey.add_argument("--limit", type=int, default=500, help="How many files at most.")
    p_survey.set_defaults(func=cmd_survey)

    p_records = sub.add_parser("archive", help="What is kept and its searchable copy: file it, build the index, search it.")
    sub_records = p_records.add_subparsers(dest="archive_cmd", required=True)

    prc_who = sub_records.add_parser("who", help="One counterparty, however many ways it is written.")
    prc_who.add_argument("name")
    prc_who.add_argument("--space", default=None)
    prc_who.add_argument("--new", action="store_true", help="This is a counterparty not seen before.")
    prc_who.add_argument("--same-as", dest="same_as", help="This spelling is that counterparty.")
    prc_who.add_argument("--note", help="What distinguishes it, where two are close.")
    prc_who.add_argument("--agent", default="")
    prc_who.set_defaults(func=lambda a: (cmd_archive_who_set(a) if (a.new or a.same_as)
                                         else cmd_archive_who(a)))

    prc_matter = sub_records.add_parser("matter", help="A matter: the thing documents belong to.")
    sub_matter = prc_matter.add_subparsers(dest="matter_cmd", required=True)

    pm_new = sub_matter.add_parser("new", help="Open a matter, before the first document is filed against it.")
    pm_new.add_argument("title", help="What it is called, in the user's words.")
    pm_new.add_argument("--space", default=None)
    pm_new.add_argument("--slug", help="Default: derived from the title, lowercased ASCII with spaces and punctuation turned into single dashes.")
    pm_new.add_argument("--into", dest="into", help=f"The bundle inside {ARCHIVE_DIR}/ this belongs in, e.g. `insurance`, or `health/x-rays` for one inside another. The matter lands at {ARCHIVE_DIR}/<into>/<slug>/<slug>.md.")
    pm_new.add_argument("--doc-type", dest="doc_type", help="What kind of matter: policy, employment, vehicle, case.")
    pm_new.add_argument("--lifecycle", default="active", choices=list(RECORD_LIFECYCLE))
    pm_new.add_argument("--retention", help="A category from this space's keeping terms (`retention show`).")
    pm_new.add_argument("--until", help="YYYY-MM-DD, where the term resolves to a day.")
    pm_new.add_argument("--with", dest="with_whom", help="The counterparty, as a contact slug.")
    pm_new.add_argument("--about", help="A sentence on what this matter is.")
    pm_new.add_argument("--force", action="store_true", help="Open a second matter with this slug.")
    pm_new.add_argument("--agent", default="")
    pm_new.set_defaults(func=cmd_archive_matter_new)

    pm_add = sub_matter.add_parser("add", help="Hang a document on its matter, both directions at once.")
    pm_add.add_argument("matter")
    pm_add.add_argument("what", nargs="?", default="",
                        help="What this document did, in one line. Leave it out when pointing at a document with --path or --folder: the line is then filled from what was read out of it.")
    pm_add.add_argument("--space", default=None)
    pm_add.add_argument("--path", default="", help="A document to hang on the matter. Its date, amount and counterparty come from the index.")
    pm_add.add_argument("--folder", default="", help="Every document in this folder, the same way.")
    pm_add.add_argument("--via", default="part-of", choices=list(RECORD_RELATIONS))
    pm_add.add_argument("--date", help="YYYY-MM-DD; default today.")
    pm_add.add_argument("--amount", help="Where there is one.")
    pm_add.add_argument("--with", dest="with_whom", help="Who it was with.")
    pm_add.add_argument("--document", help="A note of its own, where one exists; its fields are set too.")
    pm_add.add_argument("--agent", default="")
    pm_add.set_defaults(func=cmd_archive_matter_add)

    pm_show = sub_matter.add_parser("show", help="One matter, whole.")
    pm_show.add_argument("matter")
    pm_show.add_argument("--space", default=None)
    pm_show.set_defaults(func=cmd_archive_matter_show)

    prc_file = sub_records.add_parser("file", help="Move a pile of documents into or within the archive, and read them where they land.")
    prc_file.add_argument("--space", default=None)
    prc_file.add_argument("--source", required=True, help=f"File or folder inside the space, e.g. {INBOX_DIR}/Abonnements to bring a pile in, or {ARCHIVE_DIR}/vertraege/telekom to move one that is already there.")
    prc_file.add_argument("--into", dest="into", default="", help=f"The bundle under {ARCHIVE_DIR}/ they belong in, e.g. vertraege. Omitted puts them at the top.")
    prc_file.add_argument("--dry-run", dest="dry_run", action="store_true", help="Show what would move, move nothing.")
    prc_file.add_argument("--agent", default="")
    prc_file.set_defaults(func=cmd_archive_intake)

    prc_rename = sub_records.add_parser("rename", help="Give a kept document or a section a name that says what it is. The index follows.")
    prc_rename.add_argument("--space", default=None)
    prc_rename.add_argument("--path", required=True, help=f"The document or folder, e.g. {ARCHIVE_DIR}/health/scan-0007.pdf.")
    prc_rename.add_argument("--to", required=True, help="The new name, as it should read. The extension is kept when none is given.")
    prc_rename.add_argument("--agent", default="")
    prc_rename.set_defaults(func=cmd_archive_rename)

    prc_move = sub_records.add_parser("move", help="Put a kept document or a whole section somewhere else inside the archive. The index follows.")
    prc_move.add_argument("--space", default=None)
    prc_move.add_argument("--path", required=True, help="The document or folder to move.")
    prc_move.add_argument("--to", required=True, help=f"The folder it goes into, e.g. {ARCHIVE_DIR}/health/x-rays. Created when it does not exist.")
    prc_move.add_argument("--agent", default="")
    prc_move.set_defaults(func=cmd_archive_move)

    prc_index = sub_records.add_parser("index", help="Read what is kept, once each. A second run touches only what changed.")
    prc_index.add_argument("--space", default=None)
    prc_index.add_argument("--scope", help=f"A folder to read instead of {ARCHIVE_DIR}/.")
    prc_index.add_argument("--rebuild", action="store_true", help="Read everything again, changed or not.")
    prc_index.set_defaults(func=cmd_archive_index)

    prc_survey = sub_records.add_parser("survey", help="One line per indexed document: dates, amounts, parties, opening. Made by machine, for something else to decide on.")
    prc_survey.add_argument("--space", default=None)
    prc_survey.add_argument("--scope", help=f"Only what lies under this folder, the same one `archive index --scope` was given. Omitted surveys everything indexed, which on a real archive is thousands of lines.")
    prc_survey.add_argument("--json", action="store_true", help="As JSON, for a run to read.")
    prc_survey.add_argument("--opening", type=int, default=400, help="How much of the opening to carry.")
    prc_survey.set_defaults(func=cmd_archive_survey)

    prc_search = sub_records.add_parser("search", help="Find a word in what is kept.")
    prc_search.add_argument("query")
    prc_search.add_argument("--space", default=None)
    prc_search.add_argument("--limit", type=int, default=15)
    prc_search.set_defaults(func=cmd_archive_search)

    p_retention = sub.add_parser("retention", help="How long kept documents stay: what applies here, and what was suggested.")
    sub_retention = p_retention.add_subparsers(dest="retention_cmd", required=True)

    prn_show = sub_retention.add_parser("show", help="What is in force, or what would be proposed.")
    prn_show.add_argument("--space", default=None)
    prn_show.add_argument("--verbose", action="store_true", help="Say where each figure comes from.")
    prn_show.set_defaults(func=cmd_retention_show)

    prn_adopt = sub_retention.add_parser("adopt", help="Take the suggestions into this space as the terms that apply.")
    prn_adopt.add_argument("--space", default=None)
    prn_adopt.add_argument("--force", action="store_true", help="Replace terms already in force.")
    prn_adopt.add_argument("--agent", default="")
    prn_adopt.set_defaults(func=cmd_retention_adopt)

    p_routing = sub.add_parser("routing", help="What incoming material is and where it goes, as a table the user owns.")
    sub_routing = p_routing.add_subparsers(dest="routing_cmd", required=True)

    prt_show = sub_routing.add_parser("show", help="Print the rules, and say where they are silent.")
    prt_show.add_argument("--space", default=None)
    prt_show.set_defaults(func=cmd_routing_show)

    prt_set = sub_routing.add_parser("set", help="Write one rule about a sort of material.")
    prt_set.add_argument("name", help="What this sort of thing is, in the user's words, e.g. `nightly backup report`.")
    prt_set.add_argument("to", help="Where it goes: a folder, a bundle slug, or `ask`.")
    prt_set.add_argument("--space", default=None)
    prt_set.add_argument("--when-text", dest="when_text", nargs="+", metavar="WORD",
                         help="Words that appear in the content. All of them have to be there.")
    prt_set.add_argument("--when-name", dest="when_name", metavar="PATTERN",
                         help="A pattern the file name matches, e.g. `backuplog*`. Only where the "
                              "name is genuinely part of what the thing is.")
    prt_set.add_argument("--about", help="What this sort of material is, for whoever reads the rule later.")
    prt_set.add_argument("--do", dest="do", help="What to do with it, in the user's own words.")
    prt_set.add_argument("--ask", type=lambda v: v.lower() in ("1", "true", "yes", "ja"),
                         help="Whether to ask before acting on it. Omit to leave unchanged.")
    prt_set.add_argument("--keep", choices=("with-result", "discard"),
                         help="What happens to the file itself once its content is in the space. "
                              "`with-result` where the file still carries something the result does "
                              "not, a scanned invoice or a recording: it lives beside what was made "
                              "from it. `discard` where it does not, a voice note asking for a task: "
                              "it goes to the trash. Nothing ever stays in the inbox.")
    prt_set.add_argument("--by", help="Who does the work for this sort of material, by expert name. "
                                      "Omit and the usual routing decides.")
    prt_set.add_argument("--agent", default="")
    prt_set.set_defaults(func=cmd_routing_set)

    p_work = sub.add_parser("work", help="Work objects: one row plus one page per piece of work, on the machine's own side.")
    sub_work = p_work.add_subparsers(dest="work_cmd", required=True)

    # Every one of these takes its subject as a bare positional as well as a flag. The flag is
    # what the skills write; the bare form is what a person types, and until the bare
    # form was silently eaten by an optional `space` positional that nothing in the product ever
    # passed: `work open "a title"` failed with "the following arguments are required: --title",
    # naming the flag the user had not used instead of the argument they had. The space is a flag
    # now, and it is resolved to the space root either way.
    pw_open = sub_work.add_parser("open", help="Open a work object and print its id.")
    pw_open.add_argument("title_pos", nargs="?", metavar="TITLE", help="The title. Same as --title.")
    pw_open.add_argument("--space", default=None, help="Where the space is. Default: found from here.")
    pw_open.add_argument("--title")
    pw_open.add_argument("--owner", "--agent", dest="owner", help="Which specialist is on it.")
    pw_open.add_argument("--goal", help="What finished looks like.")
    pw_open.add_argument("--deliverable", help="Where the result will land.")
    pw_open.add_argument("--workshop", help="Where the working files live.")
    pw_open.add_argument("--due", help="YYYY-MM-DD, only where the work has a real deadline.")
    pw_open.set_defaults(func=cmd_work_open)

    # One subject, one space flag, one agent flag, on every subcommand that takes an id. They used to
    # be written out per parser and drifted: `log` took `--agent`, `ask` did not, and a run that had
    # just used it on one spent a turn being refused on the other. Every refusal costs the whole
    # context again, so four wrong guesses in a row cost more than the work they were guessing at.
    def gemeinsam(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        parser.add_argument("id_pos", nargs="?", metavar="ID", help="The work object. Same as --id.")
        parser.add_argument("--space", default=None, help="Where the space is. Default: found from here.")
        parser.add_argument("--id", help="Full id or its first characters.")
        parser.add_argument("--agent", help="Who is doing it. Recorded on the log line.")
        return parser

    pw_ask = gemeinsam(sub_work.add_parser("ask", help="Record a question only the user can answer; marks the object as waiting."))
    # `--text` and `--note` are here as aliases for exactly one reason: they were guessed, in that
    # order, by a run that knew the subcommand and not its flag. A synonym costs one line; the guess
    # costs a turn.
    pw_ask.add_argument("--question", "--text", "--note", dest="question", required=True)
    pw_ask.set_defaults(func=cmd_work_ask)

    pw_answer = gemeinsam(sub_work.add_parser("answer", help="Record the user's answer and put the object back to open."))
    pw_answer.add_argument("--answer", "--text", "--note", dest="answer", required=True)
    pw_answer.set_defaults(func=cmd_work_answer)

    pw_log = gemeinsam(sub_work.add_parser("log", help="Append one line to the object's log and add up its cost."))
    pw_log.add_argument("--note", "--text", "--message", dest="note", required=True)
    pw_log.add_argument("--tokens", type=int)
    pw_log.add_argument("--minutes", type=int)
    pw_log.add_argument("--workshop")
    pw_log.add_argument("--deliverable")
    pw_log.add_argument("--due", help="Set or move the deadline, YYYY-MM-DD.")
    pw_log.set_defaults(func=cmd_work_log)

    pw_done = gemeinsam(sub_work.add_parser("done", help="Close a work object."))
    pw_done.set_defaults(func=cmd_work_done)

    pw_list = sub_work.add_parser("list", help="What is open and what is waiting on the user.")
    pw_list.add_argument("--space", default=None, help="Where the space is. Default: found from here.")
    pw_list.add_argument("--state", help="Filter: open, 'waiting on you', done.")
    pw_list.set_defaults(func=cmd_work_list)

    pw_show = gemeinsam(sub_work.add_parser("show", help="Print one work object: its row and its page."))
    pw_show.set_defaults(func=cmd_work_show)

    p_prose = sub.add_parser("prose", help="Check draft prose before it is written, so the write is not later refused by the prose-guard hook.")
    sub_prose = p_prose.add_subparsers(dest="prose_cmd", required=True)

    pp_check = sub_prose.add_parser("check", help="Report lines using a dash as sentence punctuation. Exit 0 always; the finding is the output, never a failure.")
    pp_check.add_argument("--text", help="Text to check. Omit to read from stdin.")
    pp_check.set_defaults(func=cmd_prose_check)

    p_brand = sub.add_parser("brand", help="The brand a piece is built against: is there one, and what is still undecided in it.")
    sub_brand = p_brand.add_subparsers(dest="brand_cmd", required=True)

    pb_check = sub_brand.add_parser("check", help="Exit 1 when no brand exists. Run before dispatching anyone who produces something the user looks at.")
    pb_check.add_argument("space", nargs="?", default=".")
    pb_check.add_argument("--brand", help="Check one brand by name instead of all.")
    pb_check.add_argument("--limit", type=int, default=12, help="How many open fields to print per brand.")
    pb_check.set_defaults(func=cmd_brand_check)

    pb_list = sub_brand.add_parser("list", help="Every brand that exists, and where it lives.")
    pb_list.add_argument("space", nargs="?", default=".")
    pb_list.set_defaults(func=cmd_brand_list)

    p_task = sub.add_parser("task", help="Task lines on the user's own lists: write one they asked for, tick one off, see what is due.")
    sub_task = p_task.add_subparsers(dest="task_cmd", required=True)

    pt_add = sub_task.add_parser("add", help="Write a task the user asked for. The only route to a task line; inside an ordinary write it stays refused.")
    pt_add.add_argument("space", nargs="?", default=".")
    pt_add.add_argument("--text", required=True, help="The task in the user's own words.")
    pt_add.add_argument("--file", help="Which list it goes on. Default: today's journal entry.")
    pt_add.add_argument("--due", help="YYYY-MM-DD, only where there is a real deadline. The task "
                                       "goes into the journal day it is due, not into today.")
    pt_add.add_argument("--every", choices=sorted(_TASK_EVERY),
                        help="Repeat: when the task is ticked off it is written again at the next "
                             "occurrence, in that day's journal entry. Needs --due to count from.")
    pt_add.add_argument("--see", help="Where the detail lives: a bundle or note slug, written into "
                                      "the line as a wikilink. This is how a task stays one line "
                                      "without losing what somebody needs to do it.")
    pt_add.add_argument("--agent", help="Name for the activity-log line.")
    pt_add.set_defaults(func=cmd_task_add)

    pt_done = sub_task.add_parser("done", help="Tick a task off, matched on a fragment of its text.")
    pt_done.add_argument("space", nargs="?", default=".")
    pt_done.add_argument("--text", required=True, help="Enough of the wording to hit exactly one.")
    pt_done.add_argument("--file", help="Restrict the search to one list.")
    pt_done.add_argument("--agent", help="Name for the activity-log line.")
    pt_done.set_defaults(func=cmd_task_done)

    pt_list = sub_task.add_parser("list", help="Open tasks across the whole space, wherever they sit.")
    pt_list.add_argument("space", nargs="?", default=".")
    pt_list.add_argument("--due-within", dest="due_within", type=int, help="Only dated ones falling due within N days, overdue included.")
    pt_list.add_argument("--limit", type=int, default=40)
    pt_list.set_defaults(func=cmd_task_list)

    p_bundle = sub.add_parser("bundle", help="Bundle operations.")
    sub_bundle = p_bundle.add_subparsers(dest="subcmd", required=True)

    pb_create = sub_bundle.add_parser("create", help="Create <kind>/<slug>/<slug>.md from template plus INDEX.md.")
    pb_create.add_argument("space", nargs="?", default=".")
    pb_create.add_argument("--kind", required=True, choices=list(KIND_FIELDS.keys()))
    pb_create.add_argument("--slug", required=True)
    pb_create.add_argument("--title")
    pb_create.add_argument("--source", choices=["organic", "ai-generated"],
                           help="Provenance. Default: the template's value.")
    pb_create.add_argument("--source-detail", dest="source_detail",
                           help="Where it came from, e.g. research:<slug> or import:<file>.")
    pb_create.add_argument("--goal")
    pb_create.add_argument("--status")
    pb_create.add_argument("--due")
    pb_create.add_argument("--topic")
    pb_create.add_argument("--tags", help="Comma-separated tags, e.g. 'sport,ernaehrung'. Without this the file carries whatever tags its own frontmatter had, which for a source without frontmatter is none.")
    pb_create.add_argument("--heading-files", dest="heading_files",
                           help="Heading for the members list in INDEX.md, in the user's language. Default English.")
    pb_create.add_argument("--heading-activity", dest="heading_activity",
                           help="Heading for the activity list in INDEX.md, in the user's language. Default English.")
    pb_create.add_argument("--truth-description", dest="truth_description",
                           help="The line describing the main file in INDEX.md, in the user's language. Default English. Without it a translated heading sits above an English sentence.")
    pb_create.add_argument("--truth", action="store_true",
                           help="For a sub-bundle: write its truth file too, with a 'Part of [[parent]]' link. Without it a sub-bundle gets only its folder and INDEX.md, which is right for a plain grouping and wrong for a sub-bundle.")
    pb_create.add_argument("--narrow", action="store_true",
                           help="Allow a slug of more than two words. A narrow name holds only the "
                                "one file that named it, so this has to be said deliberately.")
    pb_create.set_defaults(func=cmd_create_bundle)

    pb_addfile = sub_bundle.add_parser("add-file", help="Copy a markdown file into a bundle (body verbatim, frontmatter migrated to schema).")
    pb_addfile.add_argument("space", nargs="?", default=".")
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
    pb_addtruth.add_argument("space", nargs="?", default=".")
    pb_addtruth.add_argument("--bundle-slug", required=True, dest="bundle_slug",
                             help="Sub-bundle path (must contain '/').")
    pb_addtruth.add_argument("--kind", required=True, choices=list(KIND_FIELDS.keys()))
    pb_addtruth.add_argument("--title")
    pb_addtruth.add_argument("--goal")
    pb_addtruth.add_argument("--status")
    pb_addtruth.add_argument("--due")
    pb_addtruth.add_argument("--topic")
    pb_addtruth.add_argument("--tags", help="Comma-separated tags, e.g. 'sport,ernaehrung'.")
    pb_addtruth.set_defaults(func=cmd_create_sub_bundle_truth)

    pb_rename = sub_bundle.add_parser("rename", help="Atomically rename a slug: file rename, frontmatter slug, space-wide wikilink rewrite, master INDEX refresh.")
    pb_rename.add_argument("space", nargs="?", default=".")
    pb_rename.add_argument("--old", required=True)
    pb_rename.add_argument("--new", required=True)
    pb_rename.add_argument("--bundle-slug", dest="bundle_slug")
    pb_rename.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_rename.set_defaults(func=cmd_rename_slug)

    pb_ientry = sub_bundle.add_parser("index-entry", help="Rewrite a member's one-line description in the bundle's INDEX.md.")
    pb_ientry.add_argument("space", nargs="?", default=".")
    pb_ientry.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pb_ientry.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_ientry.add_argument("--file", required=True, help="Member slug or filename.")
    pb_ientry.add_argument("--summary", required=True, help="What this file is, in one line.")
    pb_ientry.set_defaults(func=cmd_bundle_index_entry)

    pb_remove = sub_bundle.add_parser("remove-file", help="Discard a member: to trash/, out of INDEX.md, into the activity log, in one call.")
    pb_remove.add_argument("space", nargs="?", default=".")
    pb_remove.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pb_remove.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pb_remove.add_argument("--file", required=True, help="Member slug or filename.")
    pb_remove.set_defaults(func=cmd_bundle_remove_file)

    pb_setbody = sub_bundle.add_parser("set-body", help="Replace the body of a file in a bundle. Frontmatter untouched.")
    pb_setbody.add_argument("space", nargs="?", default=".")
    pb_setbody.add_argument("--file", required=True, help="Space-relative path, or a basename unique in the space.")
    pb_setbody.add_argument("--body-file", dest="body_file", help="Read the new body from this file. Default: stdin.")
    pb_setbody.add_argument("--replace", action="store_true", help="Allow overwriting a body that already has content.")
    pb_setbody.add_argument("--agent", help="Name for the activity-log line.")
    pb_setbody.set_defaults(func=cmd_bundle_set_body)

    pb_editfile = sub_bundle.add_parser("edit-file", help="Correct frontmatter fields of an existing file in place. Body untouched.")
    pb_editfile.add_argument("space", nargs="?", default=".")
    pb_editfile.add_argument("--file", required=True, help="Space-relative path, or a basename unique in the space.")
    pb_editfile.add_argument("--set", action="append", default=[], help="key=value. A list is written as [a, b, c]. Repeatable.")
    pb_editfile.add_argument("--remove", action="append", default=[], help="Field to remove. Repeatable.")
    pb_editfile.add_argument("--agent", help="Name for the activity-log line.")
    pb_editfile.set_defaults(func=cmd_bundle_edit_file)

    # asset -----
    p_asset = sub.add_parser("asset", help="Non-markdown files, filed into the bundle they belong to.")
    sub_asset = p_asset.add_subparsers(dest="subcmd", required=True)

    pa_add = sub_asset.add_parser("add", help="Copy a non-markdown file into the bundle it belongs to.")
    pa_add.add_argument("space", nargs="?", default=".")
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
    pc_create.add_argument("space", nargs="?", default=".")
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
    pc_update.add_argument("space", nargs="?", default=".")
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
        p.add_argument("space", nargs="?", default=".")
        if with_date:
            p.add_argument("--date", default=None,
                           help="Target date YYYY-MM-DD. Defaults to today; the entry is the one covering that date.")

    pj_path = sub_journal.add_parser("path", help="Print the entry's path. Creates nothing.")
    _add_journal_args(pj_path)
    pj_path.set_defaults(func=cmd_journal_path)


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


    # file -----
    def _add_drop_area_args(parser: argparse.ArgumentParser) -> None:
        """How a file may leave the drop area. Only checked for files that came from it."""
        parser.add_argument("--filed-to", dest="filed_to",
                            help=f"Where in the space this file's content ended up. Required for "
                                 f"anything coming out of {INBOX_DIR}/.")

    p_file = sub.add_parser("file", help="File moves into system folders.")
    sub_file = p_file.add_subparsers(dest="subcmd", required=True)

    pf_trash = sub_file.add_parser("trash", help=f"Move a file to {TRASH_DIR}/, keeping its path. Undo with `file restore`.")
    pf_trash.add_argument("space", nargs="?", default=".")
    pf_trash.add_argument("--path", required=True)
    _add_drop_area_args(pf_trash)
    pf_trash.set_defaults(func=cmd_trash_file)

    pf_archive = sub_file.add_parser("archive", help=f"Move a file to {ARCHIVE_DIR}/, keeping its path. Undo with `file restore`.")
    pf_archive.add_argument("space", nargs="?", default=".")
    pf_archive.add_argument("--path", required=True)
    pf_archive.set_defaults(func=cmd_archive_file)

    pf_status = sub_file.add_parser("status", help="Read or set a file's `status:`, the field that says whether it still stands.")
    pf_status.add_argument("space", nargs="?", default=".")
    pf_status.add_argument("--path", required=True)
    pf_status.add_argument("--set", dest="set", choices=list(STATUS_VALUES),
                           help="Omit to read the current value. " +
                                "; ".join(f"{k}: {v}" for k, v in STATUS_LIFECYCLE.items()))
    pf_status.add_argument("--agent", default="")
    pf_status.add_argument("--check", action="store_true",
                           help="With --set: report what hangs off this file, in both directions "
                                "and two levels deep, with each one's open task lines and a short "
                                "excerpt. Writes nothing; a person judges what still matters.")
    pf_status.add_argument("--reviewed", action="store_true",
                           help="The list above has been put to the user and answered. Needed to "
                                "set 'done' or 'cancelled' where something hangs off the file: "
                                "without it that change is refused once and the list printed.")
    pf_status.set_defaults(func=cmd_file_status)

    pf_restore = sub_file.add_parser("restore", help=f"Put a file from {TRASH_DIR}/ or {ARCHIVE_DIR}/ back where it came from.")
    pf_restore.add_argument("space", nargs="?", default=".")
    pf_restore.add_argument("--path", required=True, help=f"The file as it lies now, e.g. {TRASH_DIR}/<its old path>.")
    pf_restore.set_defaults(func=cmd_restore_file)

    # plan -----
    p_plan = sub.add_parser("plan", help="Plan sections on a bundle's truth file.")
    sub_plan = p_plan.add_subparsers(dest="subcmd", required=True)

    pp_clear = sub_plan.add_parser("clear-section", help="Remove the '## Plan' section from a bundle truth file after filing.")
    pp_clear.add_argument("space", nargs="?", default=".")
    pp_clear.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pp_clear.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pp_clear.add_argument("--truth-file", dest="truth_file")
    pp_clear.set_defaults(func=cmd_clear_plan_section)

    # review -----
    p_review = sub.add_parser("review", help="Read-once briefings written for a single decision.")
    sub_review = p_review.add_subparsers(dest="subcmd", required=True)

    pr_archive = sub_review.add_parser("archive", help="Move a read-once briefing off the desk into zanmai/logs/<YYYY>/<MM>/.")
    pr_archive.add_argument("space", nargs="?", default=".")
    pr_archive.add_argument("--item-path", required=True, dest="item_path")
    pr_archive.set_defaults(func=cmd_archive_review_item)

    # update -----
    p_update = sub.add_parser("update", help="Bundle-level index touches that follow filing operations.")
    sub_update = p_update.add_subparsers(dest="subcmd", required=True)

    pu_links = sub_update.add_parser("wikilinks", help="Rename [[old-slug]] to [[new-slug]] across markdown files.")
    pu_links.add_argument("space", nargs="?", default=".")
    pu_links.add_argument("--old", required=True)
    pu_links.add_argument("--new", required=True)
    pu_links.add_argument("--scope", help="Subfolder under the space to sweep. Defaults to the whole space. System paths are hard-excluded.")
    pu_links.add_argument("--verbose", action="store_true",
                          help="Also print every file that was touched. Off by default: the count "
                               "is the answer, the paths are the bookkeeping.")
    pu_links.set_defaults(func=cmd_update_wikilinks)

    pu_embeds = sub_update.add_parser("embeds", help="Rewrite embed references in a bundle's markdown to point at the bundle's own files.")
    pu_embeds.add_argument("space", nargs="?", default=".")
    pu_embeds.add_argument("--bundle-slug", required=True, dest="bundle_slug")
    pu_embeds.add_argument("--bundle-kind", dest="bundle_kind", choices=list(KIND_FIELDS.keys()))
    pu_embeds.add_argument("--clear-rename-map", dest="clear_rename_map", action="store_true",
                           help="Wipe the attachment rename map after this run.")
    pu_embeds.set_defaults(func=cmd_update_embeds)

    pu_master = sub_update.add_parser("master-index", help="Regenerate the space-root INDEX.md.")
    pu_master.add_argument("space", nargs="?", default=".")
    pu_master.set_defaults(func=cmd_update_master_index)

    # index -----
    p_idx = sub.add_parser("index", help="Space-index and pattern queries.")
    sub_idx = p_idx.add_subparsers(dest="subcmd", required=True)

    pi_rebuild = sub_idx.add_parser("rebuild", help="Walk the space, write zanmai/memory/space-index.json (Schicht A).")
    pi_rebuild.add_argument("space", nargs="?", default=".")
    pi_rebuild.add_argument("--scope", help="Subfolder to limit the walk.")
    pi_rebuild.add_argument("--quiet", action="store_true")
    pi_rebuild.set_defaults(func=cmd_reindex)

    pi_patterns = sub_idx.add_parser("patterns", help="Aggregate hubs and bundles into zanmai/memory/patterns.json (Schicht B).")
    pi_patterns.add_argument("space", nargs="?", default=".")
    pi_patterns.add_argument("--min-count", type=int, default=2, dest="min_count")
    pi_patterns.add_argument("--quiet", action="store_true")
    pi_patterns.set_defaults(func=cmd_patterns)

    pi_find = sub_idx.add_parser("find", help="Query patterns.json for matching bundles, bundles, hubs.")
    pi_find.add_argument("space", nargs="?", default=".")
    pi_find.add_argument("--tokens", required=True, help="Comma-separated tokens.")
    pi_find.set_defaults(func=cmd_find_bundle)

    pi_inspect = sub_idx.add_parser("inspect", help="User-visible scan of an import scope. Lists folders, file counts per extension, folder-name tokens, embed references.")
    pi_inspect.add_argument("space", nargs="?", default=".")
    pi_inspect.add_argument("--scope", required=True)
    pi_inspect.set_defaults(func=cmd_inspect_scope)

    pi_search = sub_idx.add_parser("search", help="Search the space's text and report how many files were searched.")
    pi_search.add_argument("space", nargs="?", default=".")
    pi_search.add_argument("--pattern", required=True, help="Regular expression.")
    pi_search.add_argument("--root", "--scope", dest="root", action="append",
                            help="Limit to these space-relative roots. Repeatable. "
                                 "(`--scope` works too, same meaning as elsewhere in `index`/`archive`.)")
    pi_search.add_argument("--ext", action="append", help="Limit to these suffixes (with the dot). Repeatable.")
    pi_search.add_argument("--case-sensitive", dest="case_sensitive", action="store_true")
    pi_search.add_argument("--max-hits", dest="max_hits", type=int, default=200)
    pi_search.set_defaults(func=cmd_index_search)

    # memory -----
    p_ses = sub.add_parser("session", help="The conversation record the host keeps: digest, close check.")
    sub_ses = p_ses.add_subparsers(dest="subcmd", required=True)

    ps_digest = sub_ses.add_parser(
        "digest",
        help="The essence of the conversations since the last clean close: what was said, what was "
             "asked, where something failed. For a close written afterwards.")
    ps_digest.add_argument("space", nargs="?", default=".")
    ps_digest.add_argument("--since", default=None,
                           help="UTC marker to start from. Default: the last clean close.")
    ps_digest.add_argument("--limit", type=int, default=0,
                           help="Only the newest N sessions.")
    ps_digest.set_defaults(func=cmd_session_digest)

    ps_check = sub_ses.add_parser(
        "check", help="Was the last session closed properly? Runs at session start.")
    ps_check.add_argument("space", nargs="?", default=".")
    ps_check.set_defaults(func=cmd_session_check)

    p_mem = sub.add_parser("memory", help="Briefing and operation reports.")
    sub_mem = p_mem.add_subparsers(dest="subcmd", required=True)

    pm_briefing = sub_mem.add_parser("briefing", help="Atomic rebuild of zanmai/memory/briefing.md.")
    pm_briefing.add_argument("space", nargs="?", default=".")
    pm_briefing.add_argument("--quiet", action="store_true")
    pm_briefing.set_defaults(func=cmd_briefing)

    pm_report = sub_mem.add_parser("report", help="Write an operation report to zanmai/logs/<YYYY>/<MM>/.")
    pm_report.add_argument("space", nargs="?", default=".")
    pm_report.add_argument("--operation", required=True)
    pm_report.add_argument("--slug", required=True)
    pm_report.add_argument("--summary", default="")
    pm_report.add_argument("--scope", default="")
    pm_report.add_argument("--since-minutes", type=int, default=60, dest="since_minutes")
    pm_report.set_defaults(func=cmd_write_report)

    pm_log = sub_mem.add_parser("log", help="Append one line to the activity log in the canonical format.")
    pm_log.add_argument("space", nargs="?", default=".")
    pm_log.add_argument("--agent", required=True)
    pm_log.add_argument("--activity", required=True)
    pm_log.set_defaults(func=cmd_memory_log)

    pm_curate = sub_mem.add_parser("curate", help="Keep a rules file to its rules: struck entries and long reasoning move to an archive.")
    pm_curate.add_argument("space", nargs="?", default=".")
    pm_curate.add_argument("--file", required=True, help="Space-relative path of the memory file.")
    pm_curate.add_argument("--why-lines", type=int, default=4, dest="why_lines",
                           help="A reasoning block longer than this moves to the archive.")
    pm_curate.add_argument("--show", type=int, default=10)
    pm_curate.add_argument("--agent")
    pm_curate.add_argument("--dry-run", action="store_true", dest="dry_run")
    pm_curate.set_defaults(func=cmd_memory_curate)

    pm_rotate = sub_mem.add_parser("rotate", help="Move a chronological log's older months into an archive beside it.")
    pm_rotate.add_argument("space", nargs="?", default=".")
    pm_rotate.add_argument("--file", default=ACTIVITY_LOG_FILE)
    pm_rotate.add_argument("--keep-months", type=int, default=2, dest="keep_months")
    pm_rotate.add_argument("--dry-run", action="store_true", dest="dry_run")
    pm_rotate.set_defaults(func=cmd_memory_rotate)

    # connection -----
    p_conn = sub.add_parser("connection", help="External-source connections, run by Wong. Cross-platform.")
    sub_conn = p_conn.add_subparsers(dest="subcmd", required=True)

    pco_scan = sub_conn.add_parser("scan", help="Discover connectable host sources for this space (MCP servers, plugins, CLIs, macOS apps). Informational, registers nothing.")
    pco_scan.add_argument("space", nargs="?", default=".")
    pco_scan.set_defaults(func=cmd_connection_scan)

    # hook -----
    p_hook = sub.add_parser("hook", help="Claude Code hooks (PreToolUse, PostToolUse, SessionStart, Stop). Invoked by Claude Code via settings.json, not by users directly.")
    sub_hook = p_hook.add_subparsers(dest="subcmd", required=True)

    ph_session = sub_hook.add_parser("session-start", help="SessionStart hook. Reads user.md and the space state, prints the briefing on stdout.")
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

    ph_perm = sub_hook.add_parser("permission-guard", help="PreToolUse on any tool. Hard-blocks writes into the never-do bucket, and puts a write into a file that stays true after this session to the user before it happens.")
    ph_perm.set_defaults(func=cmd_hook_permission_guard)

    ph_idx = sub_hook.add_parser("index-consistency", help="PostToolUse Write|Edit. Warns when a bundle file is written without being referenced in the bundle INDEX.md.")
    ph_idx.set_defaults(func=cmd_hook_index_consistency)

    ph_dispatch = sub_hook.add_parser("dispatch-guard", help="PreToolUse Agent. Refuses a main-thread expert dispatch that sets run_in_background: false; nested dispatches from inside an expert pass.")
    ph_dispatch.set_defaults(func=cmd_hook_dispatch_guard)

    ph_delete = sub_hook.add_parser("delete-guard", help="PreToolUse Bash. Refuses any command that removes something; discarding goes through `file trash`.")
    ph_delete.set_defaults(func=cmd_hook_delete_guard)

    ph_park = sub_hook.add_parser("park-guard", help="PreToolUse Bash. Refuses a wait loop inside a background run, which can only wait where nobody is looking.")
    ph_park.set_defaults(func=cmd_hook_park_guard)

    ph_libcheck = sub_hook.add_parser("library-check-guard", help=f"PreToolUse Bash. Refuses to save a .pptx into a {WORKBENCH_DIR}/<slug>/ bundle until `slide-library.py check` has run for that slug.")
    ph_libcheck.set_defaults(func=cmd_hook_library_check_guard)

    # launcher -----
    p_launcher = sub.add_parser("launcher", help="Double-clickable starter for this space (an .app on macOS, a .lnk on Windows). Callable anytime, not only during setup.")
    sub_launcher = p_launcher.add_subparsers(dest="subcmd", required=True)

    pl_detect = sub_launcher.add_parser("detect-terminals", help="List id/name pairs of terminal apps this machine can start a space session in, for the caller to offer as a choice.")
    pl_detect.set_defaults(func=cmd_launcher_detect_terminals)

    pl_create = sub_launcher.add_parser("create", help="Build the starter. macOS: an .app under /Applications. Windows: a .lnk on the Desktop (designed, unverified).")
    pl_create.add_argument("space_root", nargs="?", default=".")
    pl_create.add_argument("--name", required=True, help="Display name for the starter.")
    pl_create.add_argument("--terminal", required=True, help="A terminal id from 'launcher detect-terminals'.")
    pl_create.set_defaults(func=cmd_launcher_create)

    # A hook this version does not have is not an error, it is a hook that has nothing to guard.
    # Checked before argparse, because argparse exits 2 on an unknown sub-command and the host reads
    # exit 2 as "block this tool call". That is how a space locked itself out completely: an update
    # left a settings.json naming `park-guard` beside a script that predated it, every Bash call was
    # refused including the one that would have finished the update, and the only way out was the
    # user typing a command themselves. Silence is the only safe answer here: a guard that is not
    # installed must not be able to stop the machine that would install it.
    if len(argv) > 2 and argv[1] == "hook":
        if argv[2] not in sub_hook.choices and not argv[2].startswith("-"):
            return 0

    args = parser.parse_args(argv[1:])
    if getattr(args, "cmd", None) == "hook":
        return _run_hook_and_record(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
