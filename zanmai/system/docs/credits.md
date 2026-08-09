[← Zanmai Documentation](index.md)

# Credits and third-party material

Who and what Zanmai builds on. Everything Zanmai ships is written from scratch, apart from the one set of files under "Bundled material" and one borrowed idea of layout, both named below. This page names the rest anyway, because the people and projects behind them earned it.

## Bundled material

- **EU icons for labelling AI-generated content**, published by the European Commission and the AI Office. Shipped under `zanmai/system/icons/eu-ai/` and used as the visible disclosure on generated media. The Commission makes them available for anyone to use freely and asks for no attribution; naming them here is a courtesy, not an obligation. Source: [digital-strategy.ec.europa.eu](https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content).

## Shape borrowed, not content

- **Tech Snacks**, MIT licence, copyright 2026 Sean Kochel. How a skill file is built here, the
  procedure in numbered steps, then the shortcuts that sound sensible and are not, then the signs that
  it is being misapplied, was prompted by that project's own skill format. No text, no wording and no
  procedure of theirs is used, and the section names are our own. The MIT licence asks for nothing in
  this case, since nothing of the software is being passed on; the entry is here because an idea worth
  copying is worth crediting.

## Standards Zanmai implements

- **EU AI Act, Article 50**, the transparency obligations for AI-generated and AI-manipulated content, and the accompanying Code of Practice on transparency.
- **C2PA / Content Credentials** (ISO/IEC 21694), the open provenance standard Zanmai writes into generated and edited media.

## Companion app


## Tools Zanmai calls

None of these are included in the download. Zanmai detects what a machine already has and offers to fetch the small ones only when a job needs them. Each stays under its own licence, held by its own authors.

- **Prerequisites:** Python, Node.js, git.
- **Fetched on demand:** Pillow, c2pa, cryptography, NumPy, color-matcher, scikit-image, rawpy, ffmpeg, c2patool, yt-dlp, Whisper, a Chromium-based browser, Poppler, Ghostscript, ImageMagick.
- **Connected services**, used only where the person running Zanmai has configured them: image and video generation services, and design applications with a scripting interface.

## Platform

Zanmai runs on **Claude Code** by Anthropic and uses its skills, hooks and subagent mechanics.

## Craft that informed the method

Parts of the media prompt method were informed by a freely distributed set of image and video generation skills, published by an AI filmmaker for anyone to take and adapt. No author name or licence accompanied those files and the publisher could not be identified, so nothing of their wording remains; the method here is written from scratch. If the author is ever identified, they will be named in this spot.

## Trademarks

All product, service and company names mentioned in Zanmai and in this documentation are the property of their respective owners. They are used only to identify the tools Zanmai can work with, and imply no affiliation with, sponsorship by, or endorsement from those owners.

---

[← Back to the documentation index](index.md)
