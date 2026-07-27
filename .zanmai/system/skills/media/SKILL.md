---
name: media
description: Loki's method for generating images and video, backend routing, the swappable model registry, prompt craft, the quality axes, cost control and lawful marking. The judgment layer. The runnable generate and labeling scripts are provisioned when a backend is wired.
---

# media

Loki runs this. It carries the judgment, which backend, which model, the prompt, the read of the render, the lawful mark. Rendering itself is a backend call; the runnable client and the labeling pipeline are provisioned at first real use (see Provisioning). Until a backend is configured, the fallback is a design briefing the user renders elsewhere.

## Backends and routing

Three standard backends, held in `registry.json`:

- **Two connector backends** (host-configured MCP, interactive session), reached through the host's MCP tools. These are granted to Loki directly in its contract (`mcp__<server>__*`), so call them directly, **ToolSearch is main-loop-only and does not work inside a subagent**; never route a connector call through it. Async video polls for minutes.
- **One key backend** (API key, runs unattended), driven by a generate script. The only path that survives a headless/scheduled run, because the connector sessions need an interactive login.

**Availability first:** route only among the backends actually wired (read the connection records Wong writes), if just one is wired, use it; if the situationally-preferred class is not wired, fall back to whatever is. Among the wired ones, route by situation: **interactive design → a connector backend; unattended or scheduled runs → the key backend.** Wong configures a backend once (the connection and, only for the key backend, the secret); you then use it directly and never wire or hold a secret yourself. No backend wired → write the design briefing and stop.

## The registry (swappable, so it cannot rot)

`registry.json` holds the services and, per task class, the current model recommendation with a one-line reason and a `last_updated` stamp. **This file names the current models; this method names the decision axes.** The split is deliberate, the landscape shifts monthly, so the names live in data, not in prose. **The model is the constant, the backend a swappable transport:** the heavy models are shared third-party weights reachable through more than one service, so the prompt craft keys to the model and only the routing keys to the service. **A registry model is a candidate, not a guarantee:** which models and functions a wired backend exposes depends on the account's plan, so resolve the task's best model against what the wired connection reports as available (recorded by Wong at connection time), fall back to the next available option, and surface it in the return when the plan covers none, never assume a listed model is reachable. If the registry is older than about thirty days, say so and offer a refresh (a research pass updates it). Concrete backend call refs are confirmed when a backend is wired, not guessed here.

## Model choice, the axes (names live in the registry)

- **Text inside the image** (signage, poster, packaging, UI, multilingual) → the text-capable model.
- **Fast, high volume, vivid colour** → the fast model.
- **Complex layout with long readable text** → the layout model.
- **Faithful real objects or places, native 4K** → the fidelity model.
- **Design-taste raster** (marketing image, editorial, mockup) → the design model, raster only; vector/SVG is the sister expert, never here.
- **References / character consistency** is its own class: an edit model that actually reads reference images (a plain text-to-image model ignores them silently), plus a character model for face/emotion continuity. Proven flow: establish the character, then carry key references into a volume model.
- **Video:** a general default (control + length + cheap), a price/motion option, a cinematic option, a human-performance option.
- **Upscale splits on fidelity vs reinvention:** restore real footage faithfully, or hallucinate detail / relight for AI art. The wrong choice gives a dead image or an alien one.

## Prompt craft

The spine, five parts, in order: **format/aspect** (state first, repeat in the requirement list at the end, models default to square otherwise); **identity anchor** if a real person is in frame (reference photo first, passed through the model's native reference parameter, never described in prose); **scene** in concrete nouns; **material and light**, where the style profile's imagery direction lands; **style modifiers and negatives**, explicit. Modern models want natural descriptive language, not weighted token syntax. **Video** takes a separate motion prompt, what happens and how the camera moves; a five-second clip carries a complex scene, a longer one needs a single clear thread or it falls apart.

The depth behind the spine, the realism close against the "AI look", depth between planes, neutral-grey grounds for character builds, behaviour-over-brand lensing, reference-carries-identity, frame-before-face for multi-subject, resolution-aware detail, and the pre-generation confirmation loop, is in `.zanmai/system/docs/media-prompt-craft.md`. Read it on demand; it is model-agnostic craft, not one backend's recipe.

## Judge the render, the axes, not "looks good"

**See the output**: Read the rendered still; for video, extract frames and read them. Then grade against named axes.

- **Image:** technical artifacts; hands and anatomy; text rendering; prompt-faithfulness; composition and focus (does the eye land in ~0.3s, the poster test); light coherence; colour (grayscale test for hierarchy, 60-30-10 for distribution, both under the style profile); AI-slop signature (box-in-box, generic gradients, interchangeable stock, the piece must be one that could not have been made for any brand); brand-fit.
- **Video adds:** temporal consistency (flicker, warping, identity drift), motion/physics plausibility, lip-sync, camera coherence.
- **Slider method:** pin a vague adjective to a named axis and place the result on it; a five-point checklist a second agent would replicate is the bar.
- **Regenerate vs fix:** a global or structural miss (wrong subject, wrong composition, prompt discrepancy, a slop look, video-wide flicker) → regenerate with a sharper prompt, seed, or model. A local defect (one hand, small text, an artifact, the light, soft resolution) → fix in place: edit, inpaint, upscale, relight. Never loop blind hoping for luck; never rebuild from zero where a fix would do.

## The generation gate, never spend blind

Generation costs money and commits to AI imagery, so it never runs unbidden. A direct image request is the user's go; an image needed as a side-step for another expert's piece is not, that goes back for the user's yes first (the gate bubbles to the one live with them). **Prefer adapting given or existing imagery to generating fresh.**

Before spending, settle the brief precisely, never generic: **how many** images (with a recommendation for this case; `count` is linear, no bulk discount), **which model** (named, with a one-line reason from the axes below), **target resolution/quality** (asked, generate directly at the resolution needed; reproducing the same image larger drifts and upscaling is a separate premium operation, not a shortcut), and **the exact cost** quoted with the backend estimate (`simulate_cost`) plus the standing (`account_balance`, X of Y credits) and the billing unit. Video is per-second, default five seconds, never open at ten. Once cleared, deliver the agreed number of variants.

## Character consistency, advise, don't blind-generate

When a real or recurring person must stay the same across a new scene or outfit, do not just render, a single image dropped into a new situation usually drifts into a different-looking person. First **search the backend's library** (`library_list`, types character and style) for that person: if one exists, recommend reusing it; if not, recommend **building a character first**, a reusable character asset from several images (`library_create`, referenced by id) holds identity far better than one shot. Say it plainly, like the hint to set up a brand/style before designing, and let the user choose reuse / build / proceed-anyway. Then generate with the character reference so the person stays themselves. For a real person the set must be built from real photos of that person and kept where you can open them to check the result against; a set seeded only from generations has no ground truth, cannot certify a likeness, and any similarity is reported as unverifiable, never asserted (Loki's identity rail). A stature or look note from the user is reconciled against that real reference, not dropped in as free prompt text that can pull the render off the person.

## Know what the backend can do

Generation is one operation among many. The `registry.json` capabilities list names them, edit, upscale, variations, background removal, relight, expand, change-camera, video, character library, and more. Read the user's intent and offer the operation that fits ("upscale this", "same person, new outfit", "remove the background"), not only a fresh generation. Which operations a wired backend exposes is detected at runtime and is plan-gated.

**Use a backend's unique strengths where they win**, a Magnific Space/Flow to run a repeatable multi-step pipeline, a Higgsfield Soul for a trained recurring character, rather than flattening every backend to the portable common core. The craft is portable; the specialties are used on the platform that has them.

## Lawful marking (EU AI Act), deterministic, never model-drawn

Two independent obligations; assume both. Run deterministically through `zanmai.py media mark`, styled from the active style profile, never drawn by the model:

- **Machine-readable credential, always, and a source credential is never silently lost.** `media mark` reads the render first. An untouched signed render is **preserved** as-is (never stripped). A visible mark burn (icon or text) re-encodes the pixels and so breaks any source seal, then `media mark` **re-seals** the final image with the self-managed signer and chains the original as a `parentOf` ingredient, so a platform credential (the model provider's, e.g. Google's on its image output) survives as documented origin ("provider-generated → Zanmai-edited") rather than being discarded. With no source credential it self-signs a fresh manifest only when the user chose to (`--sign`), valid but not trust-listed; the self-managed signer is created on first use (`media signer ensure`, or on demand by the sign path) and kept outside the vault. If it can neither preserve nor re-seal, no signer configured, or the C2PA library missing, it returns a **clear warning** and never ships a stripped file as if it were marked.
- **Visible mark, only when a disclosure duty actually applies (Art. 50(4)), never a reflex stamp.** Decide the case, then apply it deterministically; `media mark` only executes what it is told.
  - **When:** a deep-fake image, video or audio (photoreal, resembling a real or plausible person, place or event), or AI text published to inform the public on a matter of public interest. Nothing AI-involved, private or unpublished, a trivial edit that does not alter semantics, or an obviously artistic, creative, satirical or fictional work means no visible mark (the machine-readable credential still applies where the content is AI). Art and fiction are reduced, not a blank exemption, the choice is the user's, surfaced by the one live with them.
  - **Which mark:** the official EU icon is the default (`media mark --eu-icon <class>`), the recognised standardised symbol; a text label is the fallback (`--visible-label`), and "I do it myself, or none" stays open. Class by what happened: fully AI-made is `generated`; a human original the AI partially changed is `modified`; published AI text or general involvement is `base`. Never reflex to `base` for an image.
  - **How it renders (deterministic in `media mark`, never model-drawn):** bottom-right; the icon opaque black or white by the corner luminance (a dark corner takes white, a light one black; the 50%-opacity files are a subtler option, not the default); sized as small as stays legible at thumbnail size, `max(24px, ~3.5% of the shorter side)`, never dominant; it must survive reshare and download. On video the still recipe does not carry: burn the mark fully opaque (a faint or semi-transparent pill frays and smears under video re-encode), larger, into a low-texture quiet zone held for the whole clip, sized to stay legible after compression. For a print PDF the mark lives in the pixels, print loses metadata. A text fallback uses the style profile typeface (`design.md`), else a standard sans that renders on every OS, its wording in the user's language ("AI-generated" fully generated, "AI-edited" adapted).

The trigger and class are read from the brief up front and confirmed against the render.

## Output and provenance

Variants render to your work folder; the chosen asset goes to `_export/<slug>/`, or into a design piece via the shared `assets/` folder with a slug prefix. A provenance sidecar, prompt, references, model, parameters, travels with it so the result is reproducible. Show, then deliver on a yes; never write straight to the final place.

## Provisioning (just-in-time, when a backend is wired)

The runnable pieces need dependencies the core install does not front-load: the key-backend client, ffmpeg (video frames and label burn-in), the C2PA library, and an image library for the still label. These are provisioned at first real use through the shared provisioning discipline, detect, then fetch what is missing, no assumption that any tool is present, and Wong security-reviews anything external and holds the key. This is why the method ships before the runnable client: the judgment is backend-independent; the plumbing lands with the backend.

## Field notes, verified invocation idioms (accelerators, not the boundary)

- **Key backend (proven reference):** submit `model_id` with an arguments dict; upload a reference file and pass its returned URL through the model's reference parameter; the model spec carries the output path to pull the result URL; aspect-preserving upscale uses a single scalar factor applied to both axes. Append each generation to a provenance sidecar.
- **Connector backends:** the `mcp__<server>__*` tools are granted directly in your contract, call them directly (no ToolSearch in a subagent); video is async, poll; credits are charged per model and resolution.
- **Character consistency, Magnific (verified 2026-07-20, high confidence):** build a reusable character with `library_create` type `character` from 1–6 images (reference-based, no training) → keep the returned numeric `id` → pass it into `images_generate` `references` as type `character` so the person holds across every shot. `images_variations` (modes `angles`/`expressions`/`age`) turns one base image into a multi-angle sheet to seed a stronger character. Building the character and generating both spend credits → the generation gate applies.
- **Local files → Magnific (verified idiom):** the server cannot read local paths. Per file, upload first: `creations_request_upload` with the `mimeType` → HTTP **PUT** the raw bytes to the returned presigned URL (`curl -T <file> "<url>"`) → `creations_finalize_upload` with the returned path → use the returned creation identifier. Batch up to 6, then feed the identifiers into `library_create` (character) or `images_generate` references. A public HTTPS URL skips this via `creations_upload_image`.

Add newly proven idioms here, dated with a confidence, as they are verified live.
