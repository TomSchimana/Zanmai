[← Installation](index.md)

# ZenNotes

ZenNotes is the editor we recommend for a Zanmai vault, and the one Zanmai works with most closely. Any Markdown editor opens the same files, Obsidian included; ZenNotes is leaner and faster, which is why it is the recommendation. What exactly is integrated, and what to switch on, is in [your editor](../editors.md). It shows your notes as readable pages and handles the daily, weekly, and monthly notes. Zanmai stores everything as plain Markdown inside a ZenNotes vault, so your content stays yours and readable even without any app.

## Install it

Get the latest build from the ZenNotes releases page: <https://github.com/ZenNotes/zennotes/releases/latest>. The app updates itself after that, so you download it only once.

- **macOS:** easiest is Homebrew, `brew install --cask zennotes/tap/zennotes`. Or download the `.dmg` for your chip and drag ZenNotes to Applications.
- **Windows:** download and run the `.exe` installer.
- **Linux:** use the `.deb` package or the AppImage from the same releases page.

## The command-line helper

Zanmai uses a small companion command called `zn` to open files and move things to the archive or trash. You install it from inside the app, under Settings, CLI. Zanmai also works without it, using a simpler fallback, so this part is optional.

## Check it

In a Terminal or PowerShell, run `zn --version`. If it prints a version, Zanmai can use it.

---

[← Installation](index.md) · [Documentation](../index.md)
