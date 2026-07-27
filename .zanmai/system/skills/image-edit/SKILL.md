---
name: image-edit
description: Loki's local pixel workbench, deterministic image edits that need no model and cost nothing to run, convert (incl. WebP), resize, rotate, crop, grayscale, composite, optimize, and batch a whole folder; plus colour grading (a .cube LUT or matching a reference image) and RAW develop where the host has the libraries. Prefer this to regenerating whenever the pixels already exist.
---

# image-edit

Not every image job is a generation. When the pixels already exist, a photo, an earlier render, a folder the user handed over, the honest, free move is to edit them, not spend credits making new ones. This skill is Loki's local workbench for exactly that: deterministic operations run through `.zanmai/system/scripts/image-edit.py`, no model, no backend, no cost. Loki still directs it with judgment (which operation serves the piece, what target size, which look), but the pixels are moved by code, not guessed by a model.

Reach for it before the generation gate whenever adapting existing imagery would do, the media skill's own rule ("prefer adapting given or existing imagery to generating fresh") lands here.

## The operations

Run `image-edit.py detect` first on an unfamiliar host, it reports which tiers this machine can do. Then:

**Core, always available once Pillow is provisioned.** `convert` (format from the output extension, WebP included), `resize` (exact, a scale factor, or fit-within keeping aspect), `rotate`, `crop`, `grayscale`, `composite` (overlay one image on another with position, scale, opacity), `optimize` (re-save smaller). `batch` applies convert / resize / rotate / grayscale / optimize to every image in a folder, the path for "prepare this whole set for the web" or "shrink these for the deck".

**Detected, heavier, host-dependent.** `grade --lut <file.cube>` bakes one colour look consistently across a shot or a whole batch; `grade --match <reference>` pulls a target image's colour toward a reference's, an approximation, not a per-pixel edit. `raw` develops a camera RAW to a viewable image. Each checks its own library at call time and, when it is missing, prints what to provision and stops rather than faking a result.

The script is the reference for exact flags; this file is the map of what exists and when to use it. Do not re-teach image libraries here.

## Judgment, not just mechanics

- **Right size at the source.** Generate or receive at the resolution the piece needs; do not upscale a small image to fake detail, that is a separate premium operation, not a resize. Downscaling for web or a deck is fine and belongs here.
- **A consistent look across a set** is the LUT case: fix the look once as a `.cube`, then apply it to the whole folder so every image carries the same grade. Reference-matching is the looser cousin when there is no LUT, only a target image to move toward.
- **See the result.** As with any render, read the edited file, do not trust the operation blind. A crop that cut the subject, a convert that flattened needed transparency, an over-optimized image with visible banding: caught by looking, per Hard Rule 10.
- **Format honesty.** JPEG has no transparency; converting an image with alpha to JPEG flattens it onto white. When transparency matters, PNG or WebP. The script does the flatten so a convert never crashes, but the choice is yours to make on purpose.

## Marking still applies

Editing does not exempt an image from lawful marking. When AI-generated or AI-adapted material is edited here and then shipped, the marking runs through `zanmai.py media mark` as always, and the wording shifts to **"AI-edited"** because existing material was adapted. See the media skill for the marking method; it is one obligation, not two tools.

A visible-label burn re-encodes the pixels, so if both an edit and a burned label are needed, edit first, mark last.

## Output and provenance

Intermediates render to the task's work folder (`.zanmai/work/<task>/`); the chosen result goes to `_export/<slug>/` for the user to pull, or into a design piece through the shared `assets/` folder with a slug prefix. Never write straight to the final place, show, then deliver on a yes.

## Provisioning (just-in-time)

Core editing needs Pillow. `grade --lut` needs numpy; `grade --match` needs color-matcher or scikit-image; `raw` needs rawpy. None are front-loaded by the core install, they are provisioned at first real use through the shared provisioning discipline (detect, then fetch what is missing, nothing assumed present), and Wong security-reviews anything external. Until a tier's library is present, its operation stops with a clear provision-this message; the core stays usable regardless.

## Field notes, verified vs. designed

- **Core ops (verified 2026-07-20, Pillow 12.3.0):** convert incl. PNG→WebP and alpha-flatten PNG→JPEG, resize (scale / exact / fit), rotate, crop, grayscale, composite, optimize, and batch, all exercised end-to-end on real images, outputs reopen with the right format, mode and dimensions.
- **Detected tiers (designed, not yet verified on a provisioned host):** LUT application (nearest-neighbour sample, a trilinear blend is the refinement when a real look needs it), reference colour-matching, and RAW develop are coded and dependency-guarded but await a machine that has numpy / color-matcher / rawpy and a real RAW or LUT to prove against. Mark them verified here once that run happens.
