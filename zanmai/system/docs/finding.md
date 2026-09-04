[← Zanmai Documentation](index.md)

# Finding things again

**Read this when:** something in the space has to be found again and the name is not known.

A question about your own material is answered from your space. Which tool answers it depends on what you asked, and Zanmai does not go to the internet unless you say so.

## Two questions, two tools

**"Where is the thing about X, and what hangs off it?"** The index answers that. It is a map of your material, rebuilt at session start whenever something changed, and it knows bundles, contacts and how they relate, so the answer comes without reading every file.

**"Where does this word appear?"** An ordinary text search answers that, and it is the faster of the two. It is the right one whenever the wording matters more than the structure.

Neither of them goes to the internet. If your material does not answer the question, you are told that in one line and asked, rather than handed something from the web dressed up as your own note.

## Why a plain search used to come back empty

Your space is a git repository, which is how updates reach it. So that your own material never gets committed into it, every one of your areas is named in that repository's ignore rules. Search tools read those same rules, and that is why a search of your own notes could report nothing while looking exactly like a search that had worked.

A file named `.ignore` at the top of your space settles it. Search tools read it ahead of the git rules, it puts your areas back in, and it keeps out what a search should never wade through: the snapshots, which hold every earlier version of every file, the trash, and the generated index files. Zanmai rewrites it at every session start, so it cannot fall behind a folder that was renamed. Rules of your own belong in `.rgignore`, which is read ahead of it.

## Why an index at all

Search alone finds words. The index also knows structure: that a file belongs to a bundle, that a person appears in several places, that two bundles cover related ground. That is what makes "what did I decide about that supplier last spring" answerable, and what lets an import land next to material it belongs with instead of creating a duplicate bundle.

It also keeps itself honest. Every write into a bundle updates the bundle's own index and the activity log, and a check flags omissions rather than letting them accumulate. That is why the map stays usable as the space grows instead of decaying.

## The overviews it keeps for you

Two things are written and maintained without you asking.

Every bundle folder holds an index note: a line saying what the bundle is for, then one link per file in it with a one-line summary of what that file is. So opening a bundle tells you what is inside before you open anything, and the links work in any editor.

At the space root sits a master index over all bundles and contacts, regenerated from what actually exists rather than patched, so it cannot quietly drift out of step with the folders.

The point is that they stay current. An overview kept by hand decays: the fifth file lands, the list does not get updated, and from then on it lies about what is in there. Here the update happens in the same operation that writes the file, and a check flags anything written without its entry. So the overview is worth trusting, which is the only thing that makes an overview useful.

## What helps you find things later

Two habits pay off, both of them things Zanmai nudges rather than enforces. Keeping one fact in one place, with links pointing at it, so there is a single thing to find. And letting names become links once they recur: a name mentioned in passing stays text, a name that keeps coming back is offered as a connection, so your notes gradually knit together instead of staying a pile.

## Related

- [Folder architecture](folder-architecture.md), how material is sorted in the first place
- [Tags](tags.md), how tags are kept consistent
- [Research](research.md), when the answer genuinely has to come from outside

---

[← Back to the documentation index](index.md)
