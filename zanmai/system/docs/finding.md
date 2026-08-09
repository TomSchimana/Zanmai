[← Zanmai Documentation](index.md)

# Finding things again

How Zanmai answers a question about your own material, and why it does not quietly go to the internet.

## Four layers, in order

A question about something you kept walks four layers and stops at the first one that answers it.

1. **The vault index.** A map of your material, rebuilt at session start whenever something changed. It knows themes, bundles, contacts and how they relate, so a question can be answered without reading every file.
3. **Direct search** across your notes, for the case where wording matters more than structure.
4. **The internet**, and only when you explicitly asked for research.

That last step is the important one. Zanmai does not slide from "nothing in the vault" into a web search. If your material does not answer the question, you are told that in one line and asked, rather than handed something from the internet dressed up as your own note.

## Why an index at all

Search alone finds words. The index also knows structure: that a file belongs to a theme, that a person appears in several places, that two bundles cover related ground. That is what makes "what did I decide about that supplier last spring" answerable, and what lets an import land next to material it belongs with instead of creating a duplicate theme.

It also keeps itself honest. Every write into a bundle updates the theme's own index and the activity log, and a check flags omissions rather than letting them accumulate. That is why the map stays usable as the vault grows instead of decaying.

## The overviews it keeps for you

Two things are written and maintained without you asking.

Every theme folder holds an index note: a line saying what the theme is for, then one link per file in it with a one-line summary of what that file is. So opening a theme tells you what is inside before you open anything, and the links work in any editor.

At the vault root sits a master index over all themes and contacts, regenerated from what actually exists rather than patched, so it cannot quietly drift out of step with the folders.

The point is that they stay current. An overview kept by hand decays: the fifth file lands, the list does not get updated, and from then on it lies about what is in there. Here the update happens in the same operation that writes the file, and a check flags anything written without its entry. So the overview is worth trusting, which is the only thing that makes an overview useful.

## What helps you find things later

Two habits pay off, both of them things Zanmai nudges rather than enforces. Keeping one fact in one place, with links pointing at it, so there is a single thing to find. And letting names become links once they recur: a name mentioned in passing stays text, a name that keeps coming back is offered as a connection, so your notes gradually knit together instead of staying a pile.

## Related

- [Folder architecture](folder-architecture.md), how material is sorted in the first place
- [Tags](tags.md), how tags are kept consistent
- [Research](research.md), when the answer genuinely has to come from outside

---

[← Back to the documentation index](index.md)
