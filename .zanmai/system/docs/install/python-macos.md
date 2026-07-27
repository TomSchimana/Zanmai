[← Installation](index.md)

# Installing Python on macOS

macOS ships with an old Python (3.9), and Apple's copy should be left untouched. Zanmai needs a newer one, **version 3.10 or higher**, so you install a current Python once.

## The easy way (recommended)

Homebrew is the common way to install developer tools on macOS from the Terminal. If you already installed Claude Code or Git through it, you have Homebrew, and this is the same kind of one-liner. If you do not have it yet, get it from [brew.sh](https://brew.sh) first, then run:

```
brew install python
```

When Homebrew installs itself the first time, it prints two lines to add to your `~/.zprofile` so the `brew` command is found afterwards. Follow those, then quit and reopen the Terminal once.

## The other way (a plain installer)

1. Open [python.org/downloads](https://www.python.org/downloads/) in your browser.
2. Click the button that downloads the latest macOS installer.
3. Open the downloaded file and follow the steps, like any other app.

## Check it worked

**Open a new Terminal window first.** A Terminal that was already open still remembers the old Python, so you would see the old version and think the install failed. Open a fresh window (Spotlight: press ⌘-Space, type "Terminal"), then type this and press Return:

```
python3 --version
```

You should see `3.10` or higher, for example `Python 3.14.x`. If you do, you are done. Come back to Zanmai and start a new session.

If a fresh window still shows `3.9.x`, quit the Terminal completely and open it again. With Homebrew, its Python is `python3` once the `~/.zprofile` line is in place.

If you see "command not found", the installation did not finish. Try one of the ways above again.

---

[← Installation](index.md) · [Documentation](../index.md)
