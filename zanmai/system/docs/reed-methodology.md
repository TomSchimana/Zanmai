[← Zanmai Documentation](index.md)

# Reed, Research Methodology

This doc carries Reed's research method in detail: how to frame, search, triangulate, calibrate confidence and synthesise. Reed reads it as reference. The expert contract (`experts/reed/reed.md`) carries identity, hard rules, output format and pointers, not the method itself.

## Reed's five-phase workflow

### Phase 1: sharpen the question

Split the brief into three to seven sub-questions. Note ambiguities. Define what a good answer means for the user's use case (decision-grade versus survey versus quick check).

The audience parameter (item 4 in the pre-dispatch brief) drives the rest.

| Audience | Source priority | Definition discipline | Length tendency |
|---|---|---|---|
| Beginner | Primary explainers (Wikipedia, official intros) | Every term defined on first use, fundamentals included | Longer (context supplied) |
| Standard | Mix of explainer and primary | Jargon defined on first use, basics skipped | Medium (default when nothing else is said) |
| Expert | Primary technical (papers, specs, source code, expert guidelines) | Field vocabulary used without translation, no basics content | Shorter (meta-explanation drops out) |
| Reed chooses | The choice is documented in the methodology section of the deliverable | Depends on what Reed picked | Documented |

If the brief is missing the audience parameter, one clarifying question goes back to Steve before starting.

The most common quiet failure is writing for the wrong audience. An expert getting a beginner tutorial skims past content they already know. Audience calibration eliminates that skim cost.

### Phase 2: discover sources

`WebSearch` and `WebFetch`. Prefer primary sources (official docs, original announcements, peer-reviewed) over secondary (curated lists, reviews). Each source gets a one-line credibility note. Aim for at least five source candidates per major claim before filtering.

Cross-modal triage during search. Search results are not all the same shape. A video link is a video to watch, a GitHub link is a repository to read. Reed never cites sources that have not actually been consumed.

For each non-article candidate, a 30-second triage decides whether to invest the full pipeline.

- Video: `WebFetch` the page first (title, description, chapter markers). Switch to the video pipeline only if the metadata says the video answers the brief. Otherwise drop and note in the methodology section.
- GitHub repository: `WebFetch` the raw README before cloning. If the README answers the question, cite from it. Only clone when the source tree is needed.
- PDF: peek with `curl -sI` for size. Long PDFs are read by page range, not whole-document.

Triage decisions go explicitly into the methodology section ("watched three in full, skimmed four via description only, dropped five as off-topic"). Hidden filtering is forbidden (Reed contract Hard Rule 4).

For the Bash patterns that drive the pipelines, see `reed-source-pipelines.md`.

### Phase 3: triangulate and calibrate

Each weighty claim is anchored in two sources that do not share a lineage. The confidence vocabulary is fixed.

- High: three or more independent sources agree, no contradicting evidence.
- Medium: two sources agree, or one strong primary source.
- Low: one source only, or sources contradict (call out the contradiction).

Where confidence shows depends on the stakes parameter (brief item 3), not on whether confidence exists internally. Reed always knows the confidence, the question is whether the reader needs to see it inline per item.

| Stakes | Confidence display | Example briefs |
|---|---|---|
| High (health, legal, financial, safety, irreversible) | Per item, inline, on every key finding. Single-source claims flagged inline. | Treatment options, tax law, medication interactions. |
| Medium (tech choices, larger purchases, travel logistics with cost-of-rework) | Per item only for outliers and single-source claims. Remaining items rely on a global methodology note. | Framework picks, hotel comparisons, cloud-provider analysis. |
| Low (hobby, entertainment, wishlists) | Global in methodology and limitations. Per-item only for genuinely uncertain items. | Best classics in a genre, must-watch films, board-game wishlists. |

When stakes are ambiguous, default upward. Medium for unclear, high only when the brief is explicit. No claim silently dodges its level: a medium-stakes outlier still gets its inline marker, a low-stakes uncertain item still gets one. The contract drops verbosity, not honesty.

### Phase 4: synthesise and write

Output goes to disk as a Markdown file at the path the brief named. Output structure:

```
---
kind: knowledge
slug: <slug>
created: <today>
source: ai-generated
operation: research
researcher: reed
---

# <Topic>

## Executive Summary
<Two or three sentences. The answer to the brief in one paragraph.>

## Key Findings
1. **<Finding>** (Confidence: high, medium or low)
   <one-line statement>
2. **<Finding>** (Confidence: ...)
   ...

## Evidence
### <Finding 1>
- Source A: <URL>. <one-line credibility note>. <what it says verbatim or near-verbatim>.
- Source B: <URL>. ...

### <Finding 2>
...

## Methodology
<Which queries, which sources prioritised, which filtered out, what order.>

## Limitations
<What stayed unverified. What fell outside scope.>

## Anti-patterns surfaced
<Common bad practices Reed encountered, one line each on why they look attractive but disappoint.>

## Recommendations
<Next questions worth asking. Adjacent topics.>
```

Length scales with scope. Narrow questions resolve at 200 to 400 words; broader work runs 600 to 1200, longer only when the brief genuinely demands it. Citations are mandatory. Every weighty claim ships with its source and its confidence.

Checkboxes are the user's (operating-principles section 8, enforced by `hook checkbox-guard`). Reed writes none, in any deliverable. Findings are prose with citations; where one calls for action, that is a sentence and the user decides whether it becomes a task of theirs.

When the source is visual (video, screencast, slide deck, infographic), the evidence section embeds the frames that carry the claim, with the wikilink embed next to the timestamp citation. The reader verifies without leaving the vault. Audio sources quote the transcript span. Code sources quote file lines with a SHA-pinned citation.

### Phase 5: surface entities for the network

When Reed surfaces new entities (people, organisations, products) that Zanmai might want as contacts or bundles, list them at the end of the deliverable under `## Entities surfaced` so Steve can decide whether to register contacts.

## Filing target picking

Knowledge files live inside theme bundles, never as their own top-level bundle. The user's mental model is broad-to-specific. A top-level theme holds specific items as members. A specific item (a particular medication, appliance, product model, destination) is never the top-level bundle.

Steve picks the target path via this procedure (also applies when Reed has to pick because Steve delegated the choice).

1. Match an existing theme bundle. Look at the bundles under `knowledge/`. If one fits, the file becomes a member of it.
2. Propose a new theme. Steve names one inferred from the topic and confirms with the user before dispatching Reed.
3. Emergency landing flat at `knowledge/<topic-slug>.md`, only when no theme makes sense yet. This is a transitional state, not the resting place. The user gets a "homeless item to file later" prompt in the briefing.

The deliverable lands as a file inside the matching theme bundle: `<kind>/<theme>/<topic-slug>.md`. Binary material the source brings (transcripts, frame images, repo snippet archives, domain page captures) lies flat in the same bundle as the deliverable, because it is the same matter.

The full folder-architecture rules (theme-truth-file initial boilerplate, sub-bundle distinction, sub-theme growth, where attachments live) live in `zanmai/system/docs/folder-architecture.md`. Reed follows it.

## Two filing kinds

The brief's filing target carries a kind in addition to the path.

- Reference (default): a stand-the-test-of-time knowledge note the user will come back to later. The path is inside `knowledge/`.
- Read-once briefing (explicit): a temporary summary for a single decision (consolidation before a meeting, a one-shot answer the user will read and dispatch). The path is `doing/<slug>/<slug>.md` with `status: awaiting-archive`. The user reads it once, then it moves to `zanmai/logs/` via `zanmai.py review archive`. Read-once does not pollute the knowledge corpus.

Steve sets the kind in the brief. Default is reference. Read-once is picked when the user phrased the request as a temporary summary for a specific upcoming use, not as a permanent reference need.

## Anti-pattern discussion

Recurring failure modes Reed avoids.

- Model-memory smuggling. Stating a must-read or best-of item without a current source. Looks plausible, cannot be verified, may include mediocre items, misses recent re-evaluations. This is exactly what Reed exists to prevent.
- Hidden filtering. Dropping candidates without saying why. The methodology section names what got cut.
- Wrong audience. Writing basics for an expert or skipping fundamentals for a beginner. Audience calibration handles it. Getting it wrong burns reader time.
- Source over-fetch. Reading every extracted video frame, cloning a whole monorepo to verify one sentence. Transcript-first selection and shallow clone plus targeted Read handle this. Over-fetch burns tokens linearly with no gain.
- Citing the search result without reading it. Reed cites sources that have actually been consumed. Search hits are candidates, not citations.

---

[← Back to the documentation index](index.md)
