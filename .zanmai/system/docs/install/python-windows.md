[← Installation](index.md)

# Installing Python on Windows

Windows does not come with Python, so you install it once.

## The simple way (recommended for most people)

1. Open [python.org/downloads](https://www.python.org/downloads/) in your browser.
2. Click the button that downloads the latest Windows installer.
3. Open the downloaded file. **On the first screen, tick the box "Add python.exe to PATH"**, this matters, it lets Zanmai find Python afterwards.
4. Click "Install Now" and follow the steps.

## The developer way (if you use winget)

Windows 10 and 11 include `winget`, a built-in installer you run in the Terminal / PowerShell:

```
winget install Python.Python.3.12
```

## Check it worked

Open **PowerShell** (press the Start button, type "PowerShell", open it). Type this and press Enter:

```
py -3 --version
```

You should see something like `Python 3.12.x`, any `3.10` or higher is fine. If you see that, come back to Zanmai and tell it to continue.

If you get an error, the "Add to PATH" box was probably not ticked, run the installer again and make sure it is.

> Note: these steps are written from the official Windows instructions and are being verified on a real Windows machine; if anything differs on your system, tell Zanmai what you see.

---

[← Installation](index.md) · [Documentation](../index.md)
