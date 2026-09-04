[← Zanmai Documentation](index.md)

# Commands and procedures

**Read this when:** a procedure has to be added or found, or the question is which command does something.

Everything Zanmai does is either a **procedure** it follows or a **command** it runs. You rarely need either by name, because asking in your own words reaches the same place. This page is the list, for when you want to know what exists.

## The commands you type yourself

Thirteen of them, each a shortcut for something you could also just ask for.

| | |
| --- | --- |
| `/zanmai-import` | take in what is waiting in `inbox/` |
| `/zanmai-journal <text>` | put this into today's entry, word for word |
| `/zanmai-voice` | read the voice notes that are waiting right now |
| `/zanmai-write` | write a document |
| `/zanmai-research` | research something with real sources |
| `/zanmai-connection` | set up or check a source outside the space |
| `/zanmai-snapshot` | record the space as it stands |
| `/zanmai-update` | check for a new version and apply it |
| `/zanmai-housekeeping` | check keeping times and the shape of the space |
| `/zanmai-close-session` | write the hand-off and end the working session |
| `/zanmai-show-welcome` | show what the session opened with, rebuilt as things stand |
| `/zanmai-grill-me <topic>` | question a raw idea of yours until it is decided |
| `/zanmai-create-launcher` | build a double-clickable starter for this space |

## The procedures behind them

A procedure is a written method a specialist follows, so the same job is done the same way every time rather than reinvented. Most have no command of their own because they run as part of something else.

The ones with a command above: `import-bundle`, `journal`, `voice`, `write`, `research`, `manage-connections`, `snapshot`, `update`, `housekeeping`, `close-session`, `welcome`, `brief`, `create-launcher`.

The ones that run inside a job: `setup` (the first conversation), `greeting` (the first reply of a session), `classify-note` (deciding what a piece of material is), `content-brief` (turning source material into something a document can be built from), `designer`, `html`, `typst`, `powerpoint` and `affinity` (the four ways a designed piece is actually produced), `media` and `image-edit` (generating an image, and editing one that exists), `video`, `video-review` and `motion` (a cut, watching the render, and graphics that move), `create-expert` (building a new specialist).

## The engine

One program does everything that changes state, so that filing, indexing and checking do not depend on anyone remembering to do them: `zanmai.py` (the space CLI with all subcommands, media, tools, setup, snapshot, import, docs, welcome, gaps, housekeeping, video, voice, fact, survey, archive, retention, routing, work, prose, brand, task, bundle, asset, contact, journal, file, plan, review, update, index, session, memory, connection, hook, launcher).

Three more sit beside it for work that is its own trade: `image-edit.py` for editing pixels without a model, `design-check.py` for measuring a rendered document against your brand, and `slide-library.py` for reading your own slides and reusing them.

Every command answers `--help`, and asking Zanmai what a command does gets you the same answer in your language.

## The specialists

Eleven, plus the one you talk to. Who does what is in [who does what](specialists.md); the names are `hank`, `marcus`, `ben`, `reed`, `wong`, `shuri`, `carol`, `loki`, `luis`, `pepper` and `stan`, and you meet them when one of them is working on something for you.

## Adding to it

A recurring job that no procedure covers becomes one, rather than being improvised each time. Where it has to be exact rather than judged, it becomes a command instead, because a command does not depend on anyone remembering the discipline. And where a whole trade is missing, a new specialist is built for it, researched first so it comes out with a real method. All three land in a part of the space no update overwrites.

## You do not have to read any of this

The full documentation ships under `zanmai/system/docs/`, mapped by its own index, and asking
is the intended way in. A "how
do I" or "why does" question is answered from these same pages, in your language and shaped to your
own space, which is why nobody has to work through them to use Zanmai.

## Related

- [Who does what](specialists.md), the specialists and their trades
- [How Zanmai grows](growing.md), what happens when something is missing
- [What runs automatically](hooks.md), the checks nobody has to invoke

---

[← Back to the documentation index](index.md)
