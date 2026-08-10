[← Zanmai Documentation](index.md)

# Your brand

One file holds what your things look and sound like, and everything Zanmai produces for you reads it: documents, images, video, and whatever gets built next.

## Why it is separate from the people who use it

Carol lays out documents, Loki generates images, Luis cuts video. If each of them settled the colours and the tone for their own piece, you would end up with three brands that almost match. So the identity sits above all three, in one place, and none of them may change it. Shuri owns that file. She writes it and produces nothing with it; the others produce and never write it.

That also means you can ask her things the others cannot answer: is this piece actually on brand, what is still undefined, what should we pin down before the website gets built.

## Where it lives

`trusted/brands/<your brand>/design.md`. In your own folders, not in Zanmai's system folder, because it is yours: you can open it, read it and disagree with it. `trusted/` is the part of the vault for what you have settled on, and a brand is exactly that.

If you have more than one brand, each gets its own folder. Alongside `design.md` sit the per-format build values and, for slides, the layouts harvested from your own decks.

The file has two halves. At the top, the measurable values in a machine-readable block, colours, type, spacing, corner radii, in the shape a coding agent expects, so a colour can be handed straight to a stylesheet instead of being retyped. Below it, in plain text, what a value cannot hold on its own: what each one is for, where it was read from, and what the brand never does. A section your brand genuinely does not need is listed as deliberately left out, which keeps "we decided against this" apart from "nobody has looked at it yet".

## Starting from whatever you have

Most people do not have a brand manual. They have a logo, an old presentation and a website, and that is enough to start.

Colours come out of a vector logo exactly. Fonts are read off a document rather than recognised from a picture of one. Anything measured off a render or estimated from a PDF is written down **as an estimate** and stays marked that way until something binding turns up. So you can always see which values are real and which are the best guess so far, instead of finding out much later that a colour was never actually yours.

What cannot be read from anything stays empty. An empty field is honest: it says nothing has been decided. A plausible default would quietly decide it for you, and nothing afterwards could tell the difference.

If you have nothing at all, no logo, no document, then it is not reading any more, it is your decision. You get walked through it and nothing is invented behind your back.

## What a complete one holds

Only a name and one colour are strictly required, and a brand that stops there is one that gets invented while a piece is being built, differently each time. So the target is the whole system, and you get told what is still missing rather than being left to find out from a finished page.

That means: nine to fifteen type levels rather than two, each with family, size and line height, because the levels nobody pinned are the ones a build guesses. A spacing scale with the base step and the two values a layout actually needs, the gap between columns and the margin around the block, since whitespace decided per piece is why things do not line up. Corner radii even where the answer is none, because sharp is a decision worth writing down. The surface colours and which text colour goes on each, checked at the contrast ordinary text needs, which is measured rather than judged. And the components your material actually shows, buttons, cards, quotes, with their variants.

Where your brand genuinely has no position on one of those, it is recorded as deliberately left out, with the reason. That reads differently from silence, and it stops the same question coming back every time.

## No brand, no build

Before anything that you will look at gets produced, Zanmai checks that the brand exists. If it does not, the job stops and tells you what is missing and who fixes it.

That is a stop, not a refusal: say "build it anyway" and the piece is produced plain, and the result says so. The reason for stopping first is that render time and, for generated imagery, real money are spent before you ever see the outcome. A piece built against invented colours looks finished and is wrong.

## Keeping it honest

A refined value replaces the old one, with the date and one line on what changed. Nothing accumulates a second opinion next to the first, because then it stops being an answer.

When something settles during a job, a logo position, a caption height, a loudness target, you are asked whether it becomes the standard. It only goes into the brand on your yes, and you see the change first.

## Related

- [Who does what](specialists.md)
- [Designing documents](design.md)
- [Generating images and video](images.md)
- [Editing video](video.md)

---

[← Back to the documentation index](index.md)
