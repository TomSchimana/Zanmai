[← Zanmai Documentation](index.md)

# How Zanmai grows

What happens when you need something none of the specialists covers.

## A missing capability is not a no

Say what you need. The role is researched first, deliberately, because a specialist written from general knowledge reads like every other AI assistant and performs like one. What comes out of that research becomes a contract: what this specialist is for, how it works, where it stops, and which existing skills it leans on.

You see that draft before anything ships. Adding a specialist is expensive and awkward to undo, so it happens on your yes, not on a hunch.

## Where it lives, and why that matters

Anything grown for you lands in `zanmai/extensions`. That folder is never touched by an update. The specialists that ship with Zanmai live in the system folder instead, which an update does replace.

That split is the whole point: your own additions survive every version, and you never lose them to an upgrade. It also means the reverse is true, and worth knowing: editing a shipped file directly is pointless, because the next update overwrites it. Anything you want to keep belongs in the extensions folder.

## What a new specialist gets wired into

An expert is not real until every attachment point matches: the contract itself, the adapter that makes it dispatchable, and its own memory file so it can learn from its runs. Half-wiring is the classic failure, it looks installed and then dispatches nowhere, so the wiring is checked rather than assumed.

The same procedure is used whether you grow a specialist or one ships with Zanmai. One way of building means the roster stays consistent instead of accumulating one-offs.

## Skills, the other way to extend

Not everything needs a new specialist. A skill is a procedure an existing specialist follows, and often the better answer: the same expert, one more method. When you describe a need, the cheaper option is considered first rather than defaulting to a new expert for every gap.

## Related

- [Who does what](specialists.md), the current roster
- [Keeping Zanmai up to date](updates.md), what an update replaces and what it leaves alone

---

[← Back to the documentation index](index.md)
