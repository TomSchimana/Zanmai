---
name: zanmai:affinity
description: Field notes for building natively in Affinity, fast, verified idioms and stumble warnings from real runs, plus the pre-flight ladder that starts the app or repairs a wedged scripting session. Accelerators for Carol's design work, not the boundary of what is allowed.
---

# affinity

**Field notes, not law.** Everything here was verified the hard way on Affinity by Canva 2.6, working idioms and stumble warnings so you build fast instead of re-deriving. They are accelerators, not the boundary of what is allowed: the SDK is yours. When the design needs something these notes do not cover, explore (grep the JSLib, check `search_sdk_hints`, experiment on a scratch doc), and record what you find in `.zanmai/memory/technique/affinity.md` (dated, with a version and a confidence), curated, so the next run has it.

## What the SDK can and cannot do (the one hard shape)

The SDK can **edit and compose a document's content** (text, images, fills, shapes, vector geometry) but **cannot construct design furniture**, no API to create master pages, named text/character styles, or add/duplicate pages. So the working shape is: a copy of the strongest template as structural carrier, and free composition on its pages, in the design language of all the templates. No template means no CI: stop and ask for one. From-scratch (end of file) cannot carry a brand.

## Access and pre-flight (do this first)

- Tools: `mcp__affinity__*` (`execute_script`, `render_spread`, `render_selection`, `list_sdk_documentation`, `read_sdk_documentation_topic`, `list_library_scripts`, `read_library_script`, `search_sdk_hints`, `save_script_to_library`). Never `add_sdk_hint` (data egress).
- The app's scripting server is itself MCP. Reach it only through the granted tools, never a hand-rolled client.

Run this ladder before any build, repair first, give up last:

1. **Probe**: `list_sdk_documentation`. Clean list → step 3.
2. **App down?** If the probe errors or hangs: check the process, the process name is NOT plain "Affinity" (observed: "Affinity Affinity Store"), so match loosely (macOS: `pgrep -if affinity`, excluding the MCP-bridge node processes). Not running → start it (macOS: `open -a Affinity`), wait for the scripting server (~20-30 s), re-probe up to 3 times. Running but not answering → treat as wedged, step 4.
3. **Engine health-check**: read the `preamble` doc (the server tracks preamble-read per session, so this is mandatory anyway), then `execute_script` a one-line probe that logs a marker plus `app.userDesktopPath`. Output echoes back → ready, and the reported path is the staging root for this run. Accepted-but-empty → wedged, step 4.
4. **Repair a wedged session**: the engine accepts scripts but nothing happens (no output, no file writes, loaded docs invisible to `render_spread`), only an app restart fixes this (verified). Quit gracefully (macOS: `osascript -e 'tell application "Affinity" to quit'`), wait up to ~15 s. If it quits: relaunch, wait, redo steps 1-3 once. If it does not quit, a save dialog for the user's unsaved work may be pending, do NOT force-kill; stop and report: "Affinity is stuck and may hold unsaved work, please close or restart it by hand."
5. **Still dead after one repair cycle** → stop and report what was tried. Never launch a build into a hang, and never force-quit the app on your own, a hard kill can destroy the user's unsaved documents.

If a scripting call returns `NOT_ALLOWED`, the user has scripting, filesystem or AI switched off in Affinity's settings, report which switch is needed instead of retrying.

## Filesystem: Desktop-only (verified, hard)

The scripting filesystem is limited to the Desktop. The SDK exposes only `userDesktopPath`; the Affinity settings only turn filesystem access on or off, they never widen the location, verified: a load outside the Desktop returns `PERMISSION_DENIED` even with the app's filesystem AND network toggles on. So:

- The staging root is `<desktop>/zanmai-staging/<task>/`, where `<desktop>` is what the SDK reports as `app.userDesktopPath`, ask the SDK, never assume a path shape (`~/Desktop` is the macOS case; Windows has no `~`). Read it once in the pre-flight echo probe.
- Stage with the shell (not sandboxed): copy inputs (the template copy, image assets) into that folder. It must be **visible**, a dot-prefixed (hidden) folder does NOT work, the sandbox denies it (`PERMISSION_DENIED`, verified); visible subfolders are fine.
- Affinity reads, edits and exports there.
- Shell-move the finished files into `_export/<slug>/`, then delete the staging folder. Leave the Desktop empty.

## 1. Survey ALL templates, then choose the base

Stage and open every given template (as copies) and probe each one the same way: slots and their state, completeness (placeholder share like `xxx`, empty card bodies, missing icons), actual theme (the filename can lie, verified), and its CI values. Out of this comes the **kit**, concrete values, not adjectives (each colour as hex + its job, the type levels in pt, the spacing unit and margins, the corner radius, the block inventory with real geometry, the never-list), plus the **base decision**: which template carries the structure (masters, grid, logo), and what gets borrowed from the others. An unfinished or off-topic template is flagged, never silently built on. The values persist under `.zanmai/design/<brand>/`, the durable identity in `brand.md`, the format's blocks in `<format>.md`, and accumulate across runs; the run's status file heartbeats progress.

Survey copies stay open (docs cannot be closed by script), keep their sessionUuids, the borrow step (section 6) reads from exactly these open docs. Tell the user in the handoff that the working documents are left open in the app to close.

Traversal that works (verified on real templates):
```js
for (const spread of doc.spreads)            // direct for...of ONLY, spreading the
  for (const node of spread.layers.all)      // iterators ([...]) yields an incomplete,
    ...                                      // shifting node set (verified)
```
- Type-gate text as `node.isTextNode || node.isFrameTextNode || node.isArtTextNode`, grouped card text reports only `isTextNode` (verified).
- Layers are often **unnamed** (`node.name` empty on the organization's own templates): identify slots by existing text content and geometry; use `name`/`description` when present.
- CI values: fill colours of branded nodes (`SolidFill.colour` via the fill descriptors) and the fonts of text runs. The templates are the CI truth, every value used later comes from this sheet, never from memory of the brand.

## 2. Open the working copy

Copy the chosen base to the staging folder with the shell, then `Document.load(copyPath)` (read-write by default). Never `save()` over an original; only `saveAs()`/`export()` to new paths.

## 3. Fill text in place (preserves the frame; hierarchy is restored, not lost)

- **`TextNode.setText()` is broken in Affinity 2.6** (its JSLib internals call a method that does not exist, it throws `TextSelection.from is not a function`). Use the equivalent working idiom (verified end-to-end):
```js
const { DocumentCommand } = require('/commands');
const { TextSelection } = require('/selections');
doc.executeCommand(DocumentCommand.createSetCurrentSpread(spread));  // MANDATORY first per spread, else COMMAND_FAILED
const sel = node.selfSelection;
sel.addSubSelectionForNode(node, TextSelection.create(node.storyInterface.storyRange));
doc.executeCommand(DocumentCommand.createSetText(sel, newText));
```
  Pass the frame's `storyInterface.storyRange`, a selection built without it collapses to a caret and *inserts* instead of replacing.
- **Two-phase fill, always** (verified): `executeCommand` mid-traversal collapses the running enumeration. Pass 1 traverses read-only and collects target node refs; pass 2 applies the fills on the held refs (refs survive across commands).
- **Fill every matching instance**: some cards carry stacked duplicate text frames; editing only one leaves the other showing through (verified, this caused icon/text overlap). No dedup when replacing.
- **Restore hierarchy after every fill**: the replace flattens the story to the first run's style. A frame that had headline + body gets its levels back via `document.formatText(delta, selection)`, `StoryDelta.createGlyphDouble(GlyphAttDoubleType.Height, px)` and `StoryDelta.createWeight(FontWeight.Bold)` on a `TextSelection.create(new StoryRange(a, b))` sub-range. Glyph height is px at doc dpi (`px = pt*dpi/72`). This is part of the fill, not optional polish.
- All copy follows the writing baseline (content-brief). Fit the copy to the frame; if it overflows, tighten the words, never distort the frame and **never empty the slot to make a collision disappear**.

## 4. Fill images in place

- `const bmp = Bitmap.loadFromFile(path)` then `DocumentCommand.createReplaceBitmap(selection, bmp)`.
- For a picture frame, target the contained image via `node.pictureFrameInterface.frameContents`; frame geometry and crop are preserved. (Fit-mode is not exposed to script; the frame's existing fit applies.)

## 5. Recolour accents (only if intended)

`setBrushFillDescriptor` / `setPenFillDescriptor` / `setOpacity` on a node, using colours read from the template (walk a branded node's `SolidFill.colour`). Do not recolour brand furniture; only content accents the design intends to vary.

## 6. Compose: rebuild patterns and borrow across templates

The base copy's pages are yours to compose in the extracted language, fill is the floor, not the ceiling.

- **New objects**: `AddChildNodesCommandBuilder` (`addNode`/`addImageNode`/`addShapeNode`) with `setInsertionTarget(spreadNode)`. Images: `ImageNodeDefinition.create(format).setBitmap(Bitmap.loadFromFile(...))`. Shapes: `ShapeNodeDefinition.create(shape, rect, brushFill, lineFill, lineStyle, transparencyFill)`. Corner rounding is a **version-fragile primitive**: `setRadius` (fraction 0–1) has applied in one run and been a silent no-op in another, with Bezier corners via a curve builder working where it did not, do not trust either from memory, render a test corner at run start, use what actually rounds, and record it in `technique/affinity.md` with the version. Every value (font, colour, spacing, radius) comes from the kit, so the addition is invisible as an addition. Newest node stacks in front. Set the current spread before editing its nodes, via `doc.executeCommand(DocumentCommand.createSetCurrentSpread(spreadNode))`; there is no `doc.setCurrentSpread()` (not if already current; setting clears the selection). Units: px, `mm→px = mm*doc.dpi/25.4`, `pt→px = pt*doc.dpi/72`.
- **Borrow vector motifs and icons from sibling templates** (cross-document node moves fail with COMMAND_FAILED, copy the GEOMETRY instead, verified): open the sibling copy, collect the motif's contours via `node.curvesInterface.polyCurve` into one `PolyCurve` (`combined.addCurve(c)`), scale/position with `combined.transform(Transform.createScale/createTranslate)`, then in the working doc `PolyCurveNodeDefinition.createDefault()` → `setCurves(combined)` → `setBrushFillDescriptor(FillDescriptor.createSolid(colour), 0)` → `doc.addNode(def)`. Resolution-independent, recolourable, native.
- **Rebuild a card pattern the base lacks** (a stats grid, an anchor list) from the sheet's values: the pattern's box, radius, padding, headline/body levels, icon slot, measured from the template that has it, built with the base's units.

## SDK limits to respect (verified absent, do not fight them)

- **No page add/duplicate/delete.** Keep to the page count the template already has. A flyer is 1-2 pages; that is fine. If the content needs more pages than the template has, stop and report, do not improvise.
- **No master create/apply/edit.** Masters are inherited from the template, read-only. Rely on them.
- **No named text/character-style API.** Preserve styling by editing text in place (step 3), never by trying to reapply styles.
- **Picture-frame fit-mode not exposed.** Swap at bitmap level only.

## Render and self-score

`render_spread(sessionUuid, spread_index)`, `spread_index` is REQUIRED (default 0). Renders the whole spread ≤1024px; both pages of a two-page doc may share spread 0. The render is scored by the fresh-eyes check in the `designer` skill (step 3), a separate pass, not self-certified; failures are fixed by copy-tightening or layout rework, never by emptying the slot. Never deliver a failing render.

## Export, and the press-PDF caveat (be honest)

- `document.export(path, exportOptions, exportArea, size)`. `FileExportArea.createForWholeDocument()` exports all pages as one file.
- Named export presets exist and work (verified, Affinity 2.6): enumerate `FileExportOptions.allPresetNames` and pick, the names are **localized** (German UI: "PDF (für Druck)", "PDF (Druckerei-fertig)", "PDF/X-1a:2003", "PDF/X-4"), so never hardcode a preset string, always select from the live list. `FileExportOptions.createWithPresetName(...)`.
- What a preset does NOT give you from script: verified control over bleed and printer's marks. So name the preset used in the handoff, and deliver the editable working file (via `saveAs`) alongside the PDF so the user can make the final press export in the app with their print shop's exact requirements.

## Fallback only: no template available

If there is genuinely no template, a document can be built from scratch (`NewDocumentOptions` with `isMultiPage`, `pageCount`, `dpi`, `bleed`, `colourProfile`; `StoryBuilder` text; `Font.create(family, weight, isItalic, width)`, all four args; a real logo only via SVG curve-takeover, never typed). Warn the user first: a from-scratch document will NOT carry their CI (no masters, no styles). Prefer getting a template.

## Gotchas

- Documents cannot be closed via the SDK (`doc.close` → NOT_IMPLEMENTED). Reuse one scratch doc; orphaned "Untitled" docs are closed by the user in the UI.
- The Desktop path is a **property**: `require('/application').app.userDesktopPath`, `getUserDesktopPath()` is a deprecated getter and errors as a call. `File` comes from `require('/fs')`.
- `doc.saveAs(path)` switches the active document to that path (then `doc.save()` works). A `.af~lock~` sidecar sits next to an open doc, never ship it; it disappears once the doc is closed.
- To learn a signature not covered here, first `search_sdk_hints`, then grep the on-disk JSLib (`/Applications/Affinity.app/Contents/Resources/JSLib`; `commands.js` is the authority on what is possible) rather than paging the doc tool.
- After a successful run, `save_script_to_library` the proven fill script so the next run starts from it instead of re-deriving.
- If `execute_script` turns inert mid-build (accepted but empty, zero effect), the engine has wedged, run the pre-flight repair ladder (step 4) before anything else.
