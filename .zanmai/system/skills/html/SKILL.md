---
name: zanmai:html
description: Turning a design into a handoff-ready file through HTML, construction is free, so the work goes into the look; the format follows the piece, fonts are embedded, the preview is cheap. Only the things that actually bite, plus the edges where a native tool is the honest answer.
---

# html

In HTML the layout is free, CSS does the construction, so nothing competes with the design itself, and every iteration is one cheap render you can look at. You already know HTML and CSS; this file does not teach them. It pins the few things that genuinely bite on the way to a *deliverable*, and names the edges where another tool serves the piece better.

## Format follows the piece, never a fixed default

The page size is read from the ask, the templates and the region, a flyer in the German-speaking region is A4, the US is Letter; A3, A5 or a custom size when the piece calls for it. Set it in CSS: `@page { size: A4 }`, or exact millimetres `@page { size: 210mm 297mm }`. The browser holds the size precisely (checked: A5 renders as 420 × 594.96 pt); `pdfinfo` confirms what actually came out. The failure to avoid is a hardcoded default that stalls the work, not a considered guess from context.

## Fonts embed, or they vanish silently

This is the one that bites. A deliverable carries its fonts. Reference the brand's real CI font with `@font-face` and embed it, a local font file by path, or base64 in the CSS when the file itself must travel. A font that is only *named*, or linked but not found, is replaced by a default face with no error at all, and the same is true for a relative or remote image in a headless render. So inline every asset, and verify the result with `pdffonts`: every face must read `emb yes` (a Latin subset covers ä ö ü ß). `fc-list` shows what the machine has.

## Size placed images to the output

A raster placed in the page is embedded at its full pixel size. A generated photo is often ~16 MP (≈500 ppi on A4), far more than any output needs, it bloats the file and makes some PDF viewers (macOS Preview) drop image tiles to black at certain zooms. Downscale the placed image to the target: ~300 ppi for print, ~150 for screen, at the size it occupies on the page. The pixels the reader sees are the same; only the wasted excess goes.

## Render, and see it

Render headless to PDF with a Chromium-based browser (any one, Chrome, Edge, Brave, Chromium), using its print-to-PDF mode against the `file://` HTML. Do not search for it yourself: Steve's preflight has ensured a renderer is present before this job started and resolved its path, so read that path from `zanmai.py tools check chromium` (the `path` it returns) rather than probing `/Applications` or guessing. Then look: `pdftoppm -png -r 100 out.pdf preview` gives a PNG to read on every pass. This cheap seeing-loop is the point of the medium; render early and often and judge against what is on screen, not what was intended. A PNG for the user, or the raw HTML in a browser, is the same pipeline stopped one step earlier. The render is then judged by the design method (`designer` skill); one with an open fail is not delivered.

## Where it runs, where it goes

Compose and render under `.zanmai/work/<task>/` (transient scratch, one folder per task); move only the finished files to `_export/<slug>/`. The tools above are the host's, not bundled, if one is missing, that is a boundary to report, not to fake.

## Where HTML stops, recommend, do not improvise

The browser renders RGB, right for screen, mail and an office or laser print. Two edges belong to a native tool, and at them you name the boundary and recommend it rather than working around it:

- an editable native file a person will open and change → `affinity` / `powerpoint`;
- a real press run, CMYK to an exact profile, bleed, crop marks. When only a CMYK copy is needed and `gs` is present, it can convert (`-sColorConversionStrategy=CMYK -sProcessColorModel=DeviceCMYK`, fonts and size survive); the profile is verified per job, and marks and bleed are not the browser's job.

## Learn

What a run teaches, an idiom, a stumble, a font quirk, goes into `.zanmai/memory/technique/html.md` (dated, with a confidence), curated: a corrected entry replaces the wrong one, it does not grow beside it.
