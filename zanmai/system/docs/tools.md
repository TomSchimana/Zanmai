[← Zanmai Documentation](index.md)

# Tools Zanmai uses

What outside programs Zanmai relies on, and how they get onto your computer.

## Two kinds

One thing has to be there before Zanmai can start: Python, since Zanmai runs on it. If it is missing, Zanmai tells you plainly and points you to the [installation guide](install/index.md). It never installs it silently.

Your notes are plain Markdown, so they open in any editor and you need nothing special to read or write them. The folder names, the journal and the trash are Zanmai's own, so they work the same whichever editor you use.

Everything else, a feature needs only when you use it: small helper libraries for images, tools for video, and so on. Zanmai fetches those itself the first time, keeps them in its own corner of the vault so your system stays untouched, and asks first when something bigger is involved.

## Good to know

Zanmai never assumes a tool is present. It checks, on your computer, what is really there. The same program can even have a different name on macOS, Windows, or Linux, so it looks properly and works with what it finds, or helps you get the rest.

## Three kinds of dependency

- **Prerequisites** you bring: Python, git, and Claude Code itself. Named plainly if missing, never installed silently.
- **Fetched on demand** by Zanmai when a job needs it: small Python libraries for images and signing, media tools for video work. Python libraries go into Zanmai's own environment inside the vault, so your system Python stays untouched.
- **Recommended, never required**: a package manager makes installing easier, but the on-demand path works without one.

## The whole list

Every outside program Zanmai can use, what it is for, how big it is and who installs it. The table
is generated from Zanmai's own register, so it says what actually happens rather than what somebody
once wrote down; `python3 zanmai/system/scripts/zanmai.py tools list` prints the same thing with a
mark against everything already on your machine. Sizes were measured on macOS and are the installed
size including what a tool pulls in with it. Libraries share their dependencies, so a group costs
less than its parts added up: the eight Python libraries come to 373 apart and 323 together.

<!-- generated: zanmai.py tools list --markdown -->
| Tool | What it is for | Size | Who installs it |
|---|---|---|---|
| `git` | Distribution update (ff-merge, version check) | - | you, before Zanmai starts |
| `node` | Launches MCP servers (the connection layer) | 90 MB | you, before Zanmai starts |
| `python` | The runtime everything runs on, zanmai.py, image-edit.py, all hooks | - | you, before Zanmai starts |
| `c2pa` | media-mark machine-readable credential (read/preserve/re-seal) | 13 MB | Zanmai fetches it |
| `c2pa_signer` | Self-managed signing identity for the fallback / re-seal case (valid, not trust-listed) | - | you, with one command |
| `c2patool` | C2PA via CLI (alternative to the python lib) | - | Zanmai fetches it |
| `chromium` | Turns Carol's designed HTML into an exact print-ready PDF | - | you, with one command |
| `color_matcher` | image-edit grade --match | 117 MB | Zanmai fetches it |
| `cryptography` | Generate the self-managed C2PA signing identity (P-256 cert + key) when none exists | 15 MB | Zanmai fetches it |
| `ffmpeg` | Video frames (Reed), video label burn and assembly (Loki), and converting a dropped voice note from whatever a phone recorded (m4a, aac, mp3, ogg) into the 16 kHz mono the transcriber needs | 52 MB | Zanmai fetches it |
| `ffprobe` | Reads how long a recording is, and whether a media file is what its name claims | included | you, with one command |
| `ghostscript` | Converts the final PDF to CMYK for a real press run (html skill) | 128 MB | you, with one command |
| `hyperframes` | Builds a motion graphic from markup and renders it frame by frame in a headless browser, which is what lets a cut carry graphics at all | - | Zanmai fetches it |
| `libreoffice` | Renders a deck without opening PowerPoint: one picture per slide, and the PDF export of a finished deck | 804 MB | you, with one command |
| `numpy` | image-edit grade --lut | 34 MB | Zanmai fetches it |
| `pillow` | image-edit core, the visible label on generated media, and measuring a document render per column | 15 MB | Zanmai fetches it |
| `poppler` | Turns a render into pixels and text so it can be measured rather than assumed (pdftoppm for coverage, bleed and the contact sheet; pdftotext to check the text arrived complete; pdffonts to check the fonts are embedded) | 33 MB | you, with one command |
| `python_pptx` | Reads and writes a native.pptx without opening PowerPoint: which layout a slide uses, whether its placeholders are filled, whether a run overrides the layout, which faces and colours are actually in the file | 25 MB | Zanmai fetches it |
| `rawpy` | image-edit raw develop | 6 MB | Zanmai fetches it |
| `scikit_image` | image-edit grade --match fallback | 148 MB | Zanmai fetches it |
| `secret_store` | Hold connection secrets and the signer key outside the vault (LD6) | - | you, with one command |
| `typst` | Sets a document: real text flow across pages, a full-width block deferred to the next page while text keeps filling the current one, column balancing, hyphenation dictionaries, page numbers and bleed | 43 MB | Zanmai fetches it |
| `whisper` | Turns speech into text on this machine, with no network and no key, which is what a spoken journal entry needs | - | Zanmai fetches it |
| `whisper-model` | The weights whisper runs on | 1.5 GB | Zanmai fetches it |
| `yt_dlp` | Video/source download (Reed) | 29 MB | Zanmai fetches it |
| `connection_clis` | Optional host CLIs Wong can bridge to, opt-in per use-case | - | you, with one command |
| `imagemagick` | image-edit format fallback beyond Pillow | 60 MB | you, with one command |
<!-- /generated -->

## Everything at once, offered at setup

At the end of setup you are asked once whether the tools Zanmai can fetch itself should be fetched now. You see how many are already there, then every one of the rest by name, what it is for and how big it is, and the total. Nothing is fetched from a question you cannot see the contents of. Where one item is much larger than the others, it is asked separately, so the answer can be some rather than all. Whatever needs you, a package manager command, an account, money, is listed with its size and the one command that does it, and is never installed behind your back.

This exists so a missing tool is not met for the first time in the middle of a job that is already running. You can ask for the same overview at any point later; the answer is the same list, minus whatever has arrived since.

## Before a job starts

When a task needs one of those on-demand tools, Zanmai checks the prerequisites are in place before it begins, not halfway through. If something is missing it tells you what, why it is needed for this particular job, and the simplest way to get it. So a job never stalls partway for a tool it could have named at the start. To keep this quick, it remembers what it already found on your machine and only looks again when something changed.

---

[← Back to the documentation index](index.md)
