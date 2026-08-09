[← Zanmai Documentation](../index.md)

# Requirements & installation

What Zanmai needs on your computer, in plain steps. You do not have to prepare everything in advance: Zanmai checks what is there and guides you when something is missing. Most of the heavier pieces it fetches itself the first time a feature needs them. There is really only one thing it cannot set up for you, because it is what Zanmai itself runs on: **Python**.

## What is Python, and why does Zanmai need it?

Python is a widely used programming language. Zanmai's engine, the part that files your notes, keeps the index, and runs the checks, is written in it. So Python has to be present before Zanmai can do its work. You never write any Python yourself; you just install it once, like installing any other app, and then forget about it. It is free and made by a non-profit foundation.

Zanmai needs **Python version 3.10 or newer**.

Install it for your system:

- [macOS](python-macos.md)
- [Windows](python-windows.md)
- [Linux](python-linux.md)

## Git, for getting Zanmai and keeping it current

Git is the usual way to get Zanmai onto your computer, and the tidiest way to keep it current. Most machines already have it: type `git --version` in a terminal, and if you see a version number you are set. If not, macOS offers to install it the first time you run that command, Windows users get it from [git-scm.com](https://git-scm.com/downloads), and on Linux it is in your package manager.

You can also download the repository as an archive and unpack it. Updates work either way, see [keeping Zanmai up to date](../updates.md).

## The other pieces

- [Node.js](node.md), needed only for some connected features (for example generating images). You can install it later, when a feature asks for it.

Everything else a feature needs, small helper libraries, media tools, Zanmai sets up on its own the first time you use that feature, and tells you if it needs your go.

---

[← Back to the documentation index](../index.md)
