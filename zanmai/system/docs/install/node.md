[← Installation](index.md)

# Installing Node.js

Node.js is another free runtime, like Python but for a different set of tools. Zanmai needs it only for **some connected features**, for example generating images through an outside service. If you never use those, you do not need Node at all, and you can install it later, at the moment a feature asks for it.

## Install it

- **Simple way:** open [nodejs.org](https://nodejs.org/) and download the "LTS" (long-term support) version for your system, then run the installer.
- **macOS with Homebrew:** `brew install node`
- **Windows with winget:** `winget install OpenJS.NodeJS.LTS`
- **Linux:** use your distribution's package manager, or nodejs.org.

## Check it worked

In a Terminal / PowerShell:

```
node --version
```

Any recent version is fine. Then tell Zanmai to continue.

---

[← Installation](index.md) · [Documentation](../index.md)
