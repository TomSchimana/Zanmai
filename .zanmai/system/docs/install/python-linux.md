[← Installation](index.md)

# Installing Python on Linux

Most Linux systems already have Python 3, and if not, your distribution's package manager installs it in one line. Because there are many distributions, this page stays short, a Linux user will know their own package manager.

## Check what you have

```
python3 --version
```

If you see `3.10` or higher, you are done.

## If it is missing or too old

Install it with your distribution's package manager, for example:

- Debian / Ubuntu: `sudo apt install python3 python3-venv`
- Fedora: `sudo dnf install python3`
- Arch: `sudo pacman -S python`

(`python3-venv` on Debian/Ubuntu lets Zanmai set up its own isolated helper libraries later, without touching your system Python.)

Then check again with `python3 --version` and tell Zanmai to continue.

---

[← Installation](index.md) · [Documentation](../index.md)
