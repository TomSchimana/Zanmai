[← Zanmai Documentation](index.md)

# Media prompt craft, the depth behind the method

Loki's `media` skill names the *decision* (which model, which axis, cost, marking). This doc holds the *craft*, how to write a prompt that lands, and how to fight the tells that make generated media read as generated. Read it on demand; the skill points here.

**Portability.** This craft targets the behaviour of current natural-language-conditioned image and video models, not any one platform. The heavy models a platform fronts are usually shared third-party weights (a Google image model, a ByteDance video model) reachable through several backends, so the craft moves with the model, not the vendor. Two limits stay honest: it assumes the current model generation (natural description, not weighted-token syntax), and identical phrasing lands slightly differently per model family, treat this as a strong baseline to tune per model, not a constant. Per-model tuning accrues in the skill's field notes.

## The realism close, one block against every "AI look" tell

Most of what makes an image read as generated is fixed by one closing block that states real-camera physics. Five levers, tuned to the shot:

- **Skin as biology, not material.** Fine even pore texture, peach fuzz at jaw and hairline, subsurface scatter at ear edges and nostrils, matte, never plastic or waxy. The flattering ceiling is hard: realism stays fine and soft, never harsh or unflattering (no acne, no cratered pores). When "matte" and "flattering" pull apart, resolve toward flattering.
- **Hair strand by strand,** with flyaways, reacting to the scene (still settles, wind lifts, wet clumps), never a moving block.
- **Lens character by behaviour** (see below).
- **Light physics:** soft shadow falloff on real anatomy, highlights rolled off (never clipped white), blacks lifted (never crushed), wide dynamic range.
- **Real grain:** colour-negative film rendition, fine grain across the whole frame including skin and background.

The single strongest phrase in the block is *"photographed, not generated, on a real camera"*, it works as a language-level filter against AI uniformity.

## Depth between planes, the biggest single lever

State that haze / air density sits *between camera, subject, and background*, so far planes render softer, desaturated, lower-contrast than the foreground. This is the primary fix for the flat "video-game" look: it makes a subject sit *inside* depth instead of pasted on a plane. Default-on wherever the shot has planes; scale it thin (clean interior) to heavy (moody night), never drop it to zero except on a deliberately flat studio card.

## Neutral-grey capture ground for character builds

Build characters and reference stills on **even neutral mid-grey, not white.** White maximises subject-to-edge contrast, and models bake halo, edge instability and plastic into exactly those high-contrast edges, which then carry into any video seeded from the still. Grey lowers edge contrast: cleaner extraction, less inherited plastic. Keep the ground neutral but the subject true, skin and wardrobe render at their real tone, never cooled or washed out by the grey. Use a lean soft key on grey plates, not the full realism close (the heavy stack pushes contrast back up). White only on explicit request for a finished standalone card.

## Behaviour over brand for camera and lens

Describe optical *behaviour*, not gear names: "a normal prime near 50mm, wide aperture, round bokeh" for portraits; "vintage 2x anamorphic character, oval bokeh, soft edge falloff, gentle highlight bloom" for scene plates. The model pattern-matches the behaviour, not the brand, and brand names are noise it has to translate. (This also keeps output brand-neutral, which Zanmai requires anyway.)

## The reference carries identity; the prompt carries direction

When a reference image is attached, do not re-describe what it already shows. One short visual handle per subject is enough, put the prompt's weight on composition, pose, light, and the wardrobe or state *specific to this shot*. A leaner prompt with strong references beats a long one that fights them. Cut any sentence that re-states something the reference already carries, unless it is load-bearing for the composition.

## Frame before face, multi-subject consistency

Anchor everyone to a screen position *before* identity enters: who sits in which third, which depth layer, gaze, contact points. Once the positions are settled, there is nowhere left for a subject to wander. Then give each subject its own hold block (pose / gaze / state / "same face, hair, wardrobe, silhouette throughout"), never one merged paragraph. For multiple subjects in video, add explicit relations: no swap, no centre-crossing, no depth change, distance and sides held.

## Describe only what the lens can resolve

Before writing any detail, ask whether the camera at this distance, focal length, motion and light could physically see it. A car at 60m in motion at dawn has no readable badges, it is silhouette, colour blocks, headlights, motion blur. Detail the camera couldn't resolve is detail the model will hallucinate. Detail is earned by proximity, stillness, and light.

## Positive locks over prohibitions

Translate every "don't" into a "does": "don't drift" → "feet stay on the same marks"; "don't change the face" → "same face and wardrobe throughout". Positive constraints pull harder than negatives. The only sanctioned negatives are known-failure suppressions (e.g. video's "no on-screen text, no captions").

## Character build order

One-and-done, in order: text spec → mirror it back for confirmation → lock a canonical identity reference (the anchor for everything after) → base outfit → multi-angle sheet → scene. Each stage builds on the locked one before it. Preparation is what buys a first-try render: the shots that need no second attempt are the ones whose references, wardrobe and environment were already settled when it ran.

## Video specifics

- **Diegetic audio only** in the prompt, footsteps, breath, room tone; no music or lyrics (music is added in post).
- **One idea per shot**, one dominant action, one camera strategy; more than that, split into a multi-shot sequence with hard cuts.
- **Suppress hallucinated text** with a closing line unless text is explicitly wanted.
- **Density:** shorter renders better, trim to what does work; a five-second clip carries a complex scene, longer needs one clear thread. Derive the length from the motion, not a fixed default: a walk-in, turn and walk-out crammed into five seconds reads rushed; give the action the seconds it needs or warn that it does not fit.
- **Image-to-video with a person:** anchor identity with keyframes built from the character set (start / mid / end as the motion needs), each a real render of that person, not one lone start frame the model must invent a face for. For a *continuous* move, a turn, a walk-and-face, both keyframes must share the identical background; different backdrops give the model nothing to interpolate and it hard-cuts between them, a two-shot reveal, not one shot. Compose the end frame into the exact start background first.

## Compositing a screenshot or artwork onto a device (real, not sticker-on-glass)

Placing a real screenshot on a generated device is the right move when text must stay pixel-sharp, but it only reads as real if the craft is done, not improvised (an improvised paste looks stuck-on and defeats the point):

- **Device-appropriate content first.** A tablet shows the site's *tablet* layout, a phone its *phone* layout, never a desktop screenshot squeezed onto a small screen (that is the "would never look like that" tell). Render or crop to the device's viewport and orientation.
- **Compose so the screen is the hero.** For a showcase the device sits frontal and prominent; a steep oblique angle shrinks the screen and softens the content. Compose for the purpose.
- **Measure, don't guess.** Detect the four screen-glass corners (flood-fill the screen, or render the base with a marked screen), then fit the content by real homography, following the vanishing lines, not pasted flat, not overshooting the edge.
- **Integrate the light.** Match the content's brightness, contrast and colour temperature to the scene; add a faint screen reflection and a slight display glow so it emits rather than sticks; match grain and a touch of softness so the sharpness does not break against the photo.
- **Size to the critical area.** Resolution is judged at the screen region, not the whole frame, the base must carry enough pixels there for the content to read.
- **Tools.** Deterministic Python (Pillow, four-point perspective transform) does this for free and repeatably, and the same deterministic path covers the mechanical raster jobs (resize, greyscale, format convert, crop) that need no model at all. For pro-grade placement (true smart-object, perfect reflection) escalate to the design expert's native tool. Then grade against the purpose: is the screen the readable hero, or does it look pasted on?

## The pre-generation confirmation loop

The highest-value habit, and where an agent beats a bare model call: before spending on a render, mirror the read-back to the one live with the user, references seen, subject, wardrobe, backdrop, framing, and generate only on the go-ahead. It catches the wrong prompt before credits burn (in practice it turns 8–10 throwaway takes per shot into 2–3). A minor tweak to an already-approved prompt skips the check and delivers directly. In Zanmai, Loki cannot ask mid-run, so this loop is carried by the live-at-user layer, not inside the subagent.

---

[← Back to the documentation index](index.md)
