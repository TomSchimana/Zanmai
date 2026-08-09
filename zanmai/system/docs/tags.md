[← Zanmai Documentation](index.md)

# Tags

Why your tags stay usable instead of turning into three spellings of the same thing.

## The problem tags have

Tags rot quietly. You write `trip` once, `travel` next month, `vacation` after that, and now the same idea is split three ways and none of the three finds all of it. Material imported from another app makes it worse, because it arrives with whatever tags that app encouraged.

So tags are consolidated as material comes in, rather than left to accumulate.

## What happens to a tag on the way in

Every tag on an incoming file goes through three steps.

First it is compared against the tags your vault already uses. If you have been writing `travel`, an incoming `trip` becomes `travel` rather than starting a second pile.

Then it is checked against a list of known equivalents, so common variants map onto one form even when your vault has not seen either yet:

| Kept as | Merged into it |
| --- | --- |
| `travel` | `trip`, `vacation`, `holiday` |
| `home` | `house`, `household` |
| `work` | `job`, `career` |
| `health` | `medical` |
| `learning` | `education`, `studies`, `course` |
| `food` | `cooking`, `recipes`, `kitchen` |
| `finance` | `money`, `budget` |
| `reading` | `books`, `literature` |
| `tech` | `it`, `software`, `programming`, `technology` |

Finally, tags that carry no information are dropped. What lands on the file is a short, consolidated list.

If your vault works in another language, the list above simply does not match, and that is fine: the first time a real conflict comes up you are asked which form you want to keep, and your answer is added. The list grows into your vault rather than being imposed on it.

## What never becomes a tag

- **Dates.** A year, a month, a quarter. Those are moments in time and belong in the note's date fields, where they can be sorted and filtered. A date as a tag is a dead end. Existing ones are moved to the right field on import.
- **Importance and status.** Urgent, important, todo. If everything is tagged important, nothing is. That kind of meaning belongs in the text or in a task marker.
- **Where it came from.** The name of the app you exported from. The origin is recorded in the note's own fields instead.
- **One-offs** with no context, unless you say you want them kept.

## When Zanmai is unsure

A tag that is neither in use in your vault, nor a known variant, nor obviously droppable is not decided quietly. It appears in the plan you approve before an import, with three options: a suggested form, drop it, or keep it as it is. You decide there.

## Related

- [Importing and filing material](importing.md), where consolidation happens
- [Finding things again](finding.md), what actually makes material findable

---

[← Back to the documentation index](index.md)
