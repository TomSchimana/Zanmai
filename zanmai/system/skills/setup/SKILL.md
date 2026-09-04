---
name: setup
description: First-time space setup. Runs when `zanmai/user.md` does not exist, or on any ask for an initial install or first run. Dialogue, then `zanmai.py setup init`.
---

# setup

First-time install. Steve runs this when the space has no `zanmai/user.md`. The skill is invoked by reading this file and following the workflow below, it is not a slash command.

## Directive

This skill drives the dialogue. The deterministic state changes (folder creation, `zanmai/user.md` write) are done by `zanmai/system/scripts/zanmai.py setup init`. Do not write `zanmai/user.md` directly from the conversation. Use the script. The script is the single point of state change so future migrations can reason about what got written.

## When to use

- `zanmai/user.md` is missing.
- The user asks for an initial install or first run in their writing language.
- The session-start hook reports a `setup_schema_version` below what this distribution ships: an
  update added questions this space never saw. Then only the section "Catching up an older space"
  runs, not the whole workflow, and it records with `setup catch-up`.
- An older install needs its host-side config refreshed, which is `zanmai.py setup update`, not `init`.

## When not to use

- `zanmai/user.md` already exists and `setup_schema_version` is current. Refuse and tell the user.
- The user wants to add a single bundle. That is `import-bundle`, not setup.
- The user wants to rename folders. That is a manual operation, not in scope here.

## How to ask the user

**One question per turn. Every block, every step, no exception.** Ask, stop, wait for the answer,
then ask the next. A turn ends after the question and nothing follows it: not the next question, not
the block after it, not a preview of what will be asked later, and not an announcement of what comes
once they have answered. This holds for the first-time dialogue and for the catch-up alike, and it
holds even when two questions look small enough to fit together, which is exactly when they get
batched.

Two questions in one message read as a form, and a form gets one careless answer for both. Everything
below is written so that each step also depends on the answer before it: the areas suggested in Step
2d come out of the purpose given in Step 2b, so asking them together produces the generic list the
question exists to avoid.

Only what the current question actually needs goes with it. The table in Step 2c is context for the
structure question and appears in that turn, not in an opening block of orientation before anything
has been asked.

**Every question is written for someone who has never heard of Zanmai, and it is the question that
has to carry that, not the user's prior knowledge.** Three tests, and a question that fails one is
not asked yet:

- **What is being asked** is understandable without knowing the product. No word from inside the
  system before it has been shown: workbench, life, bundle, area, filing all mean nothing to someone
  on their first day, and a question built on one of them reads as an exam. Either the turn shows
  what the word means, as Step 2c does for the folders, or the question uses ordinary language.
- **What the answer changes** is said in the same breath, concretely. Not "it makes the space more
  precise for you", which says nothing, but what will exist afterwards: folders with these names,
  ready to file into. A user who cannot see what their answer does cannot judge what to answer.
- **What happens if they have nothing to say** is stated: "not now" or "no idea yet" is a complete
  answer, nothing is lost by it, and it can be added whenever they want. Said once per question, in
  a clause, not as a paragraph of reassurance.
- **Why it is being asked at all**, and for anything personal, **where the answer goes**. A person
  being asked for their email by software they installed twenty minutes ago is entitled to know what
  it is for and where it ends up, and most people now assume the worst unless told otherwise. So the
  answer comes before the question, in a clause: it is written into a file in this folder on this
  machine, nothing is sent anywhere, and they can open or delete that file themselves. Where that is
  not true of some future field, the question does not get asked until it is.

A question the user has to interpret is a worse question than a long one. One sentence too many
costs a line; a question nobody understands costs the answer, and everything built on it afterwards.

The person asking already knows the product, which is exactly why this drifts: a question that is
obvious to the one writing it can be unanswerable for the one reading it. Where a question has been
compressed to a single sentence, it has usually lost the second test first.

Three modes:

- Structured choice with two to four options uses the `AskUserQuestion` form. Each option shows its own trade-off, the user picks one.
- Open text (name, email, free-form preference) uses an inline chat question.
- A trivial yes-or-no question with a sensible default does not get asked. Apply the default, mention it in one line if it might surprise the user, and let the user correct.

## The workflow

### Step 1: Detect

Check whether `zanmai/user.md` exists. If yes, stop. Report what is there, ask whether the user wants `update` (schema migration) or `validate` (structural check) instead.

If no, the space is uninitialised: proceed to Step 1a and run the setup workflow now. A freshly copied space holds only `zanmai/`, `CLAUDE.md` and `README.md`, no `.claude/` and no hooks yet; `setup init` creates `.claude/settings.json` at the end, and the safety hooks become live when the user reopens the space after setup. This one setup dialogue therefore runs with no hook active, so hold the house voice by the canonical, em-dash-free text given in the steps below (operating-principles, principle:surfaces), do not free-compose it.

### Step 1a: Opening

A short greeting in the user's writing language, addressing them personally rather than distantly where the language distinguishes the two. The user's name is not known yet (no `zanmai/user.md`), so the greeting must not address them by any name. Speak this canonical opening, translated to the user's writing language, and in the personal form of address where that language has one (never the distant form), rather than free-composing it:

> Hello, I am Steve, your concierge for this space. Zanmai holds what does not have to stay in your head, and does more than store it: it sorts, connects, drafts and carries work through, in plain files that stay yours.
>
> The space is still empty, so let us set it up around what you actually need it for. First I take a quick look at your system, then a few short questions in four small blocks.

Mechanics (script names, `zanmai/user.md`, hooks, settings) do not belong here. They belong in Step 4, where the user is told what happened, and in the documentation, which is written for them and is never read as an instruction from in here.

After the greeting, continue with Step 1b. The next visible chat output is the first question in Step 2, or a single one-liner from Step 1b when something genuinely needs the user's attention (Python not found).

### Step 1b: Environment check

There is one check. Zanmai needs nothing installed but Python: no editor, no companion app, no command-line helper. The space is plain files and works with whatever the user already opens files in.

The check produces at most one short user-facing line in the user's writing language. No internal narration between tool calls, no "I'm probing the environment now" filler, no status reports.

**Check 0: Python interpreter available.**

Zanmai ships a Python CLI (`zanmai.py`) plus a handful of hooks. At least one of these invocations must work, tried in order:

1. `python3 --version`
2. `python --version` (accept only if it reports Python 3.x, on older Mac or Linux this can still be Python 2)
3. `py -3 --version` (Windows launcher)

Remember the first invocation that succeeded, call it `<python_cmd>`. Pass it to `zanmai.py setup init --python-cmd "<python_cmd>"` in Step 3. The script stores it in `zanmai/user.md` and uses it for hook registrations in `.claude/settings.json`. From then on, Steve substitutes `<python_cmd>` wherever skill files say `python3`.

If none of the invocations succeed, stop setup with a clear, OS-specific install hint, phrased in the user's writing language. The hint names that Zanmai needs Python 3.10 or newer, lists the standard install paths for macOS (Homebrew `brew install python`, or python.org), Windows (python.org or `winget install Python.Python.3`) and Linux (the platform package manager), and tells the user to start a new session and re-run setup after install. Nothing has been written yet at that point.

Do not invent alternative install paths. Do not try to download Python.

Do not ask the user to install anything mid-setup. Inform once and continue. The user can re-run setup later when the toolchain is complete.

### Step 2: Block 1, who you are

The dialogue runs in four blocks, in this order: who you are (Step 2), what the space is for (Step 2b), how the space is laid out and what to start with (Steps 2c to 2e), and what you want it to be able to do (Step 3c). Name the block before its first question, one short line, so the user can see how far they are.

Before each question, one or two sentences of context in the user's writing language. The user did not read the docs, they should know why each answer matters. Then the question. One at a time. Do not batch.

**The block opens with one sentence on where these four answers go**, before the first of them: into two plain text files in this folder, on this machine, which they can open, change or delete at any time, and nothing is sent anywhere. Said once, at the top of the block, not repeated per field. Without it, the very first thing this software does is ask a stranger for their name, address form and email with no stated reason, which is the moment a careful person stops.

Both the context and the question are spoken to the user. A bare question without context reads as rude and unclear. The shape: short context sentence(s) explaining why the answer matters, then the question itself, in the user's writing language.

If the user volunteered information in earlier turns (they typed it in this conversation), reuse it. Inferences from how the user wrote get a one-line confirm-and-correct, state what was inferred and how the user can change it, never a silent apply. Blindly re-asking data the user already gave is skipped. The list below is the field inventory, not a mandatory question script.

The identity fields (preferred address, real first name, last name, email) are always asked, one plain open-text question per turn. Steve never reads or guesses them from the system account, the git config, an existing email address, or any other environment signal, and never folds two fields into a single yes-or-no confirmation. Reading a machine email to guess the name, and bundling the two into one confirmation, is exactly what leaves the user unsure which field they are answering. Ask, do not detect.

All questions are asked in the user's writing language at runtime (Steve detects the language from how they write and translates the prompts). **The names stay untranslated** (`CLAUDE.md`, Language): Zanmai, space, bundle, and the folders `inbox`, `workbench`, `life`, `knowledge`, `archive`, `journal`, `contacts`. The table shows them as they are, with the explanation beside them in the user's language. In a German sentence it is `der Space`, never "der Raum": a translated name sends somebody looking for a folder that does not exist. Translate into the personal form of address where the language has one. Asking someone for the name they want to be called by while addressing them formally contradicts itself, so the whole setup speaks to them personally. The labels below are the canonical English phrasing. Do not write any other language version into this file.

1. Preferred address. Context: how should I address you, this is the name I will use in every reply, it can differ from your real first name, many people prefer a nickname or a short form, or a different name entirely. Question: how should I address you? Do not list real-name examples in the question, the question is generic enough on its own.
2. First name (real). Context: your real first name is separate, it names the contact file that holds you and is used wherever your full identity is needed, if your preferred address is also your real first name, just repeat it here. Say what a slug is if the word is used at all, or leave the word out. Question: and your real first name?
3. Last name. Context: with the first name alone, the next contact who shares it would want the same filename, and one of the two would have to be renamed. Question: last name?
4. Email (optional). Context: this is the one field people rightly hesitate over, so it says three things before the question: what it is for (post, invoices and bookings that arrive addressed to you can be matched to you instead of ending up as an unattributed document), where it lands (the contact file in this folder, on this machine, like everything else here), and that skipping it costs nothing at all, now or ever. Never argue for it a second time after a no. Question: email, or skip it?
5. Language. Context: I detect language from how you write, this stores the preference explicitly so I do not second-guess on short messages. Question: I will reply in the detected language, OK, or pick another code (`en`, `de`, `es`)?

That is the minimum for v1.0. Birthday, phone, address, organisation, role, and website are surfaced as a checklist in the owner-contact body after setup. The user fills them at their own pace.

If preferred-address equals first-name, the owner-contact stores them once (no duplicate `nickname` field). If they differ, the owner-contact's frontmatter carries both: `first_name` and `last_name` for identity, `nickname` for address. Steve uses `nickname` for greetings and falls back to `first_name` only if `nickname` is empty.

### Step 2b: Block 2, what the space is for

One question, open text, and the answer decides what the next two blocks suggest. Context first, in the user's writing language: knowing what the space is mainly for is what lets Steve suggest a starting structure instead of asking about every folder.

The question names the possibilities in one breath rather than as a menu: to organise private life, to carry one particular project, to support work, or all of it together, work and private life in one space. **And it says plainly that "not clear yet" is a real answer**: whoever does not know yet writes that down in their own words, nothing is decided by it and nothing is lost.

Record it as one of `private`, `professional`, `project`, `all`, `unclear` for the script's `--purpose`. Where the answer is `project`, ask for the project's name in the same turn and pass it as `--purpose-detail`.

**Whatever else they said goes into `--purpose-detail` too, in their own words**, not only in the `project` and `unclear` cases. People rarely answer with the bare category: "everything private, work lives in a second space", "mostly the move for now", "our club, not me personally". That sentence is the part worth keeping, and a run that maps it onto one of five words and drops the rest has thrown away the only thing that was specific to this user. Keep it short, one line, theirs not yours. **A named project is not a folder here**: if the whole space is for one project, the space itself is that project, so the name goes into the profile and the next block suggests what belongs *inside* that project, never a bundle called "Projects".

### Step 2c: Block 3, how the space is laid out

Before asking where anything should go, show what the areas are. This is the one place in setup where a table is right, because the answer to the next two questions is only sensible once the user has seen the shape. Render it in the user's writing language, these eight rows and no more:

| Folder | What goes in |
|---|---|
| `inbox/` | what you drop in, not yet sorted |
| `workbench/` | what you are working on, with an end you can name |
| `life/` | what is yours and matters now, at work or at home |
| `knowledge/` | what would still be right for someone else |
| `archive/` | what is finished but kept |
| `journal/` | what happened on a day, in your words |
| `contacts/` | who you know |
| `zanmai/` | how the system runs, you never edit this |

Under the table, two sentences. First, what a bundle is: everything inside an area is a bundle, one folder for one matter, holding notes, documents and files side by side, with an `INDEX.md` that keeps it readable. Second, one neutral example that fits anyone, so the difference between the areas is concrete rather than abstract:

> A trip you are planning sits in `workbench/` while it is being planned, because it has an end. What you keep about the country afterwards belongs in `knowledge/`, the photos and the booking in `archive/`, and travelling itself, if it is one of the things your life is about, is a bundle in `life/`.

No further explanation, no tour of the system folder, no mention of hooks, scripts or file formats.

### Step 2d: Block 3, the areas to start with

Step 2c is context, not a turn of its own: the table, the two sentences and the example go in the
same message as this question, because that is the question they explain. Nothing is sent that ends
without a question in it. Now the one the table was for: shall I set up a starting structure right
away? Explain in one sentence why it helps: with a few named areas in place, everything filed later has somewhere obvious to go, instead of a new folder being invented for every note.

Then suggest, as a plain comma-separated line in the user's writing language, examples that match their answer from Step 2b, and ask them to simply write down the ones they want, in their own words, adding or dropping freely:

- `private`: health, finances, fitness, home, family, friends, hobbies, learning
- `professional`: meetings, clients, budget, team, suppliers, learning
- `project` (the space is that one project): the parts that project runs on, for example planning, budget, material, contacts, meetings
- `all`: a mix of both lists, said as such, for example health, finances, family, meetings, clients, budget
- `unclear`: two or three broad ones only, for example what is running now, what I want to keep, and offer to add more whenever something comes up

These become empty bundles under `life/`, passed to the script as `--bundles "a,b,c"`. Nothing is created that the user did not name, and a "not now" is a complete answer: the space works without them and they can be added at any time by asking.

### Step 2e: Block 3, projects and goals you already have

Its own turn, after the areas from Step 2d have been answered. One more question, and it is asked whatever the answer in Step 2b was, because both a working life and a private one have these: are there particular projects or goals you already have?

Say the difference in the same breath, since Step 2c already showed the areas: something with an end you can name goes on the workbench and clears itself off when it is done, something that runs on without a finishing date becomes its own bundle in your life.

The user answers in one line, in their own words. Steve sorts each named item into the two groups, then states the split back in a single line before anything is written ("<A> and <B> as work with an end, <C> as an ongoing one, correct?") and takes the correction if there is one. This is the same confirm-and-correct rule as everywhere else in this step: never a silent apply, never a question per item.

Pass the result as `--projects "a,b"` (each becomes a bundle in `workbench/`) and `--goals "c,d"` (each becomes a bundle in `life/`). Each keeps the user's own name. No catch-all bundle is ever created for either group.

### Step 3: Call the script

Run the script without prefacing it with a status line. The Bash invocation is sufficient signal, another sentence on top is filler. The next visible chat output is the Step 4 confirmation after the script returns.

Run from the space root, substituting `<python_cmd>` with the invocation that worked in Step 1b Check 0 (often `python3`, on Windows `py -3` or `python`):

```
<python_cmd> zanmai/system/scripts/zanmai.py setup init. --first-name "<first>" --last-name "<last>" --language "<lang>" --python-cmd "<python_cmd>" [--email "<email>"] [--preferred-address "<nickname>"] [--purpose <private|professional|project|all|unclear>] [--purpose-detail "<project name or their own words>"] [--bundles "a,b,c"] [--goals "a,b"] [--projects "a,b"]
```

Pass `--preferred-address` only if the user gave a value different from `--first-name`. Same value is fine to omit.

The four list flags carry the answers from Steps 2b to 2e, in the user's own words and their own language: `--bundles` the areas, `--goals` what runs on without an end, `--projects` what has one. Each name becomes one bundle, `--bundles` and `--goals` under `life/`, `--projects` under `workbench/`, built exactly like a bundle made by hand later. Omit a flag the user did not answer; none of them is required.

`--python-cmd` carries the detected invocation forward so the migration writes it into `zanmai/user.md` and the hook commands in `.claude/settings.json` use it instead of a hardcoded `python3`.

The script creates the folder skeleton plus:

- `zanmai/user.md` with `first_name`, `last_name`, `language`, `owner_contact` pointer, `auto_snapshots: true` (single master switch for every automatic snapshot, turn off via `zanmai.py snapshot disable` when the user has their own backup discipline).
- `contacts/people/<slug>.md` as the owner-contact (slug derived from first plus last name, kebab-case ASCII).
- `INDEX.md` at the space root (master index, Steve maintains it as bundles are added).
- `zanmai/memory/general.md`, `zanmai/memory/activity-log.md`, `zanmai/memory/agents/{steve,hank}/lessons.md`.
- `.claude/settings.json` with `autoMemoryEnabled: false`, the `kind-required` and `permission-guard` PreToolUse hooks, the `index-consistency` PostToolUse hook, and the `session-start` SessionStart hook. No MCP consent gate: a host-exposed MCP is available for use (LD6).
- `.claude/settings.local.json` with Bash allow-rules for the Zanmai scripts so the user is not prompted on every invocation.

### Step 3b: Localize the owner-contact body

Init writes the owner-contact at `contacts/people/<slug>.md` with an English body. If the user's writing language is not English, Steve reads the file, translates every line from `# <Full Name>` onwards into the user's writing language, and writes it back. The frontmatter block between the two `---` lines stays English, those labels are machine-readable. Code identifiers in backticks (`nickname`, `owner_contact`, `zanmai/user.md`, `close-session`) stay verbatim. Section headings, prose, sub-category bullets and `(empty)` placeholders all translate. If the user's writing language is English, skip this step.

### Step 3c: Block 4, what is still missing on this machine

Most of what Zanmai does needs nothing installed. A few things do, and meeting that requirement for
the first time in the middle of a job is where it is most expensive. So it is settled here, while
nothing is running, and in the same conversation: nothing fetched here needs a restart.

**Look before asking.** Run `zanmai.py tools ensure-all <space>` and read what it reports: what is
already on this machine, what Zanmai can fetch itself, and what the user installs. Anything already
there is not mentioned. This is not a courtesy, it is the difference between a question and a
questionnaire: a space that has been in use has most of this already, and asking about it reads as
if nobody looked.

**Where nothing is missing, there is no question here.** One sentence saying everything needed is
already on the machine, then straight on to Step 3d.

**Group what is missing by capability, never by tool.** `tool-register.json` carries a
`capabilities` block, and every on-demand tool belongs to exactly one entry there. Take the
capabilities that are not complete, name each as the thing the user would want, and add up the sizes
of its missing tools. One line per capability, at most five lines:

> Sprachnotizen zu Text machen: einmalig etwa 1,6 GB.
> Bilder erzeugen und bearbeiten: etwa 350 MB.
> Folien und gesetzte Dokumente bauen: etwa 70 MB.

That is the whole shape: the outcome in their words, the size, one line. **Never a line about a
single library.** "Turning pages from PDF or SVG into pixels" is a building block, not a wish: a
person can say whether they want to work with images and cannot say whether they want a rasteriser.
Where a tool belongs to a capability that is otherwise complete, it comes with that capability's
line and gets none of its own. No table, no roster, no column of who does what.

**Then one question, and it has to be answerable:** shall any of this be fetched now? Several at
once is normal, "not now" is complete, and nothing is lost by it, because each one is offered again
by the job that first needs it. Where one item is far larger than the rest, it gets its own yes or
no. On a yes, `zanmai.py tools ensure-all <space> --yes --only a,b` fetches exactly that selection
and each item is reported. On a no, the offer is not repeated.

**What they wanted but did not fetch** goes into `zanmai/memory/general.md` under "Open threads",
one line, in their words, so the job that needs it later says "you wanted this, it takes 40 MB,
shall I" instead of asking as if for the first time. Nothing else about this block is written down:
what is installed is read from the machine, never from a list in a file.

Anything the user installs themselves is named afterwards, each with its size and the one command,
as information rather than as a task. Anything host-configured is not mentioned at all.

**One closing sentence: the list is not the limit.** There is an expert whose job is building new
experts, so where something they need does not exist yet, it gets built for their case. One
sentence, standing offer, then stop.

**It is a note, never a proposal.** No suggested roles, no examples, nothing worked out from what
they said earlier, however obvious the gap looks. A run that names three experts the user should
want has invented three capabilities nobody asked for. The next move is theirs.

What Zanmai can do in full is a question they can ask at any time and is answered then, from the
documentation. It is not read out here.

### Step 3d: Offer a launcher icon

Ask, via the `AskUserQuestion` form (two options, one sentence each): build a one-click starter now, or
skip it. There is no sensible default to apply silently here, people genuinely differ on whether they
want an icon, so this is asked rather than assumed.

On yes, run the `create-launcher` skill's workflow (detect installed terminals, ask the name, build it,
confirm) inline, then continue to Step 4. On no, say nothing further about it and continue to Step 4:
a "no" here is about this moment, not a standing refusal, the user can ask for it anytime later the
same way `create-launcher` describes.

### Step 4: Confirm

No snapshot here. A snapshot exists to undo a change, and a space that was just set up holds nothing
to undo: the copy would be of an empty skeleton. The first one is taken before the first import, where
there is finally something to lose.

Tell the user, in their writing language, that setup is done. The confirmation has three parts: a substantive Zanmai-identity paragraph (not just a place to remember but a system that sorts, connects, drafts and carries work through, with folders named after what is going on rather than what stage a file is at, and nothing obliged to move between them), the collaboration model in one sentence, and the instruction to open a fresh session. Tone: written prose, not chat. No em-dashes as stylistic markers. No casual filler.

Canonical English template, runtime-translates to the user's writing language:

> Hello <preferred-address>. Zanmai is set up.
>
> Zanmai takes what does not have to stay in your head, and does more than remember it: it sorts, connects, drafts and carries work through. It holds what occupies you now, what recurs as routine, what you keep as knowledge, plus contacts, plans and source material for every matter in your life. You write things yourself or describe them to me; I structure, sort, retrieve and keep the cross-references clean, and the capabilities built on top act for you.
>
> Close this session and open a new one on this space. From then on, Zanmai takes over and I walk you through the first steps.

Where Steps 2d and 2e created something, one line goes between the two paragraphs, naming what is now there in the user's own words ("Health, finances and family are ready in your life, the kitchen renovation is on the workbench"). Names only, no paths and no counts of files: the point is that their own answer became something real, not a report on folders.

The confirmation follows the global communication rule (see `zanmai/system/operating-principles.md, principle:surfaces): solution-focused, plain language, no assumed knowledge of Zanmai's scripts, paths or internal terminology. No capability claims for anything that is not in the space. The user asked for setup, not an architecture manual or a usage tour.

### Step 4b: The three habits, then stop

The order at the end is fixed: the confirmation paragraph from Step 4, then these three habits, then
the closing line from Step 5 as the final thing said. Three habits and no more, each one sentence,
in the user's writing language, because each one is a thing the space cannot do for itself:

1. **Starting is just saying hello.** No briefing, no context, no repeating what was going on. The
   space reads its own state and opens by saying what is waiting and what has been sitting too long.
2. **Ending is worth one command**, `/zanmai-close-session`. It writes the hand-off the next session
   starts from: what was done, what is next, what was intended, and what you corrected along the way.
   Without it the next session begins with less than you left behind.
3. **Drop things in `inbox/` rather than filing them by hand**, in whatever state they arrive. What
   something is decides where it goes, and that is the part the space does for you.

Corrections are the fourth thing and they are not a habit, they are how the space learns: what the
user says was wrong is kept and holds from then on. One clause, inside the third sentence or after
it, never its own numbered point.

No fourth habit, no feature list, no slash-command menu. Anything else is learned at the moment it
is needed, which is the only moment it is remembered.

Two things called closing sit next to each other here and must not be run together: the restart in
Step 5 happens once, now, so the guards load, and the hand-off command is what ends a working day
from here on. Where the wording risks reading as one, the habit says "at the end of a working
session" and the closing line says "right now, once".

If the user explicitly asked during setup about something specific, answer that one thing in one sentence and stop.

### Step 5: The closing line

The instruction to open a fresh session is the last thing setup says, after the three habits in Step 4b. It appears once: the template in Step 4 carries it as its closing paragraph, so it is not written a second time underneath. Phrase it as closing this session and opening a new one, not as quitting and relaunching the app. In the desktop app a relaunch can drop the user back into the same session, where the freshly written settings have not loaded yet. No mention of which settings change, no list of hooks. The user does not need to debug what the new session does, they only need to know a new session is required.

## Sounds sensible, is wrong

| Rationalization | Reality |
|---|---|
| "I'll ask everything in one message to save round-trips." | Four blocks, one question at a time. Batching produces vaguer answers, and the later blocks depend on the earlier ones. |
| "I can write `zanmai/user.md` directly with the user's answers." | The script is the only writer. Bypassing it breaks future migrations. |
| "The user did not give a last name, I'll just use the first name as the contact slug." | A first-name-only slug collides with the first additional contact added later. Ask. |
| "The user did not give a language, I'll pick English." | Ask. Defaults the user did not pick erode trust. |
| "I'll add timezone, working hours, birthday and integrations so it feels complete." | The four blocks are the whole dialogue. A profile field nobody asked for goes onto the checklist in the owner-contact, not into setup. |
| "The user named a project, so I'll create a bundle called Projects and put it in there." | Each named project gets its own bundle under its own name. A catch-all called "Projects" is a drawer, and where the whole space is one project, the space already is it. |
| "They said health and finances, so I'll fill the bundles with a starter note each." | Empty is correct. The bundle is a place to put things, and content the user did not write is content they now have to read and delete. |
| "The capability block is long, I'll skip it and let the tools be fetched when a job needs them." | Then the first fetch happens mid-job, which is the expensive moment this block exists to avoid. Ask once, here. |
| "Only two questions are missing in the catch-up, that fits in one message." | It fits and it fails. Two questions in one message get one careless answer, and the second one depends on the first. One per turn. |
| "I'll show the folder table up front so they have the orientation before the questions." | The table is the context of the structure question and goes in that turn. Sent earlier it is a wall of text in front of a question it does not belong to. |
| "I'll say at the end that the normal overview follows once they answer." | Then the user reads that their session is being held up by a questionnaire. The greet follows when the answers are in, unannounced. |
| "They know their own space, so I can ask the short version without the table and the examples." | Knowing the space is not knowing the question. Strip the context and the user is guessing at what is wanted; the transcript of that reads as an exam, not a setup. |
| "Asking for a name and an email is self-explanatory, the context sentence is padding there." | It is the least self-explanatory question in the whole dialogue. Software installed twenty minutes ago is asking a stranger for personal data; say what it is for and where it stays, or expect a skip and a doubt that outlasts the setup. |
| "They answered with the category plus a sentence of their own, the category is what the field takes." | The sentence is the part that was specific to them. It goes into `--purpose-detail`, in their words. |
| "The user said `setup` but `zanmai/user.md` already exists, I'll just rerun." | Refuse and ask whether the user wants `update` or `validate`. Idempotent does not mean silently overwrite. |
| "I'll mention that auto-memory is now off, the hook is wired, permissions are set, the user should know." | The user was not asked about any of that. They asked for setup. They got setup. Background mechanics belong in docs, not in the confirmation. |
| "Preferred address and first name are the same field with two labels." | They are not. Preferred address is how to call the person (a nickname or short form), first name is the real name on the contact (the full given name). Two fields, two values, often equal but not always. Ask both. |
| "The Step 4 confirmation should list all the features so the user knows what is possible." | The confirmation is identity sentence plus collaboration sentence plus two or three entry verbs. Not a feature tour. Further detail comes when the user asks. |
| "I'll list external integrations (calendar, mail, fitness, project-management) in the confirmation so the user knows the full scope." | Zanmai is the space. External tools are not in the space. They are not listed as Zanmai capabilities, not hinted at as future capabilities, not mentioned at all. |

## Catching up an older space

A space set up by an earlier version never saw the blocks a later one added. The session-start hook
notices that on its own, by comparing `setup_schema_version` in `zanmai/user.md` against what the
running distribution ships, and says so in one line. This section is what it points at. It runs
before the ordinary greet, once, and never again after the answers are recorded.

**Look before asking.** Read `zanmai/user.md` and list what is in `life/` and `workbench/`. Whatever
is already answered or already there is not asked about again: a space with eight bundles in `life/`
does not get the starting-structure question, it gets one line saying what is there and an offer to
add to it. Suggesting a bundle that exists is the failure this look prevents.

**What each round added**, against the space's own `setup_schema_version`. Everything above that
number is missing here, whatever the space looks like otherwise:

| Round | What it added |
|---|---|
| 1 | identity only, the shape before any of this |
| 2 | the purpose (Step 2b), the areas to start with (Steps 2c and 2d), projects and goals (Step 2e) |
| 3 | the capability overview with its prerequisites, and the closing note that a missing one can be built (Step 3c) |

**Ask those blocks and only those**, in that order, with the same context sentences and the same
table from Step 2c. **The table is shown even though the space is not new**, because the question is
whether this user has seen it, not whether the folders exist. A round is skipped only where its
answer is already on disk: `purpose` already filled, the area already holding bundles. A round with
nothing on disk to check, which is round 3, is asked whenever the number says it was never reached.

Skip the identity block, that one is answered. The three habits in Step 4b are not repeated either:
this user has been working in the space for a while and is being asked, not onboarded.

**One question per turn holds here exactly as it does in the first-time dialogue**, and this is where
it is hardest to keep: the missing blocks are few and they look like they would fit in one message.
They do fit, and the result is a wall of text with two questions in it, an orientation table nobody
asked for yet, and a closing line promising the real session afterwards. That is a form, not a
conversation, and it was written that way once already. So: the opening line and the first missing
question, then stop. The next question only after the answer. The table travels with the structure
question, in that turn and no earlier.

Say in one line at the start what is happening: an update added questions that make the space work
better for them, it takes a minute, and it is asked once. Not a version number, not a schema name.
That line and the first question share one turn; the line is not a turn of its own either.

Nothing is said about what happens after the catch-up. The ordinary greet follows when the answers
are in, and announcing it in advance only tells the user their real session is being held up.

Then record it, from the space root:

```
<python_cmd> zanmai/system/scripts/zanmai.py setup catch-up. [--purpose <p>] [--purpose-detail "<text>"] [--bundles "a,b"] [--goals "a,b"] [--projects "a,b"]
```

The command writes only what is still empty, never over an answer that is already there, creates one
bundle per name exactly as `setup init` does, and stamps `setup_schema_version` so the hook stops
mentioning it.

**It is called after the answer, never in the same turn as the question.** The stamp is what ends
the asking. Called straight after asking, it ends the asking before anybody answered, and the block
is gone for good with nothing recorded. That happened once: the questions went out, the command ran
in the same turn, the session was restarted before the user replied, and the space came up stamped
and silent. An empty call is refused for that reason.

**A "not now" is an answer and gets recorded**, with `--declined`, because without the stamp the
same question comes back every session, which is the one outcome worse than not asking. The offer to
add areas anytime is one sentence, then the session goes on.

**Round 3 is a real block here, not a footnote.** An earlier version of this section said to mention
capabilities only if the user asked, on the argument that tools get fetched at first use anyway.
That confuses two things: the fetching, which can indeed wait, and knowing what the space can do at
all, which cannot. A user who has worked in their space for months and has never seen what the
experts cover does not know what to ask for, and so never asks. Run Step 3c as written, table
included, and end it with the same one sentence about a missing capability being built.

The one part of setup that does not come back here is the launcher icon (Step 3d). It is a yes-or-no
offer with no lasting consequence, it is available at any time by asking for one, and putting it in
a catch-up turns a short set of questions into an installation.

## Stop and look again

Stop if any of the following happens:

- Writing to `zanmai/user.md` from the conversation (Step 3 is the only write path).
- Asking a catch-up block whose answer is already in `zanmai/user.md` or already on disk.
- Ending a catch-up without running `setup catch-up`, which leaves it to repeat next session.
- More than one question in a single message, in any block, first-time or catch-up.
- A message that ends without a question in it while the dialogue is still running.
- Skipping the language confirmation because the language seems obvious.
- Creating folders the user did not name and the manifest does not list.
- Renaming the script's outputs.
- Adding placeholder content to `zanmai/user.md` that the user did not provide.
- Producing a feature menu in Step 4 instead of identity plus collaboration plus two or three entry verbs.
- Listing capabilities Zanmai does not own in the Step 4 confirmation.

If any of these, re-read this skill file and rerun the workflow from Step 1.

## Files

- `zanmai/system/scripts/zanmai.py` (`setup init` subcommand): the single CLI; the deterministic state change for first-time install.
- `zanmai/system/scripts/zanmai.py` (`setup catch-up` subcommand): the same state change for the blocks an older space never saw, plus the version stamp that ends the asking.
- `zanmai/system/tool-register.json`: what Step 3c's table is built from, capabilities and `needed_by` per expert.
- `zanmai/system/manifest.yaml`: canonical list of folders and distribution files.
- `zanmai/system/skills/create-launcher/SKILL.md`: Step 3d's optional offer, and the same skill the
  user can invoke directly, anytime, by asking for an icon, an app or a shortcut.
