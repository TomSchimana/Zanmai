---
name: zanmai:typst
description: Set a paged document with Typst: text flow across pages, deferred full-width elements, column balancing, hyphenation, folios, bleed. Verified idioms only.
---

# typst

A browser paginates a web page. It was never a typesetting system, and the one
thing it cannot do is the thing a document is made of: a full-width element that
no longer fits is pushed to the next page and the rest of the current page is
left white, because text does not flow around it. Measured on a real 62-page
piece: 22 pages under 70 percent coverage, one of them 97 percent white. That is
not a composition problem to work around, it is the wrong tool, and this is the
right one.

Everything below was compiled and looked at, not read somewhere. Where a version
matters, the pin in the tool register is the one it was verified on.

## What it gives you that a browser does not

- **Page floats.** A block placed with `float: true` moves to where it fits while
  the text keeps filling the page it came from.
- **Columns with real flow**, so content continues from one column to the next.
- **Hyphenation from dictionaries**, per language, correct German breaks.
- **Folios and totals** without stamping a second file over the first.
- **Colour to the page edge** without the silent full-document downscale a browser
  does when a padded box exceeds the page.
- Seconds per run for a document of this size.

## The two traps

**The font is silently the wrong one.** Set the family and pass the brand's own
font folder: `typst compile --font-path <brand fonts> in.typ out.pdf`. Without it
Typst falls back to its own default face, and if the brand font happens to be
installed on the machine, the omission is invisible exactly where the piece was
built and shows up on someone else's. So verify the output, do not trust the run:
`pdffonts out.pdf` must list the brand face with `emb yes`.

**Anything the check cannot measure is not proven.** Run
`design-check.py <kit> --tokens <palette> --pdf <render>` on the render, and read
its numbers, not its exit code alone.

## Verified idioms

Page, furniture, folio with total:

```typst
#set page(
  paper: "a4", margin: (top: 26mm, bottom: 20mm, x: 20mm),
  footer: context [#h(1fr) #counter(page).display() / #context counter(page).final().first()],
)
#set text(lang: "de", hyphenate: true, size: 10pt, fill: rgb("#00005a"))
#set par(justify: true, leading: 0.62em)
```

A full-width element inside a two-column flow, deferred rather than leaving a hole.
`scope: "parent"` is what lets it span the columns; without it the block stays
inside one column:

```typst
#let wide(caption, cols, ..cells) = place(
  top, scope: "parent", float: true, clearance: 12pt,
  block(width: 100%)[
    #table(columns: cols, inset: 5pt, stroke: none, ..cells)
    #text(size: 7.5pt, caption)
  ],
)
#columns(2)[ ... #wide("caption", (1fr,) * 4, [a], [b], [c], [d]) ... ]
```

A form is a `#let`, which is what makes the form ceiling real: one definition per
form, reused everywhere, and a second variant is visible as a second definition.

```typst
#let quote-inline(body) = block(inset: (left: 8pt), stroke: (left: 2pt + red))[#emph(body)]
#let quote-panel(body, who: none) = block(width: 100%, fill: grey, radius: 3mm, inset: 10pt)[...]
```

A section opener as one carried-through form, via a show rule rather than by hand
per chapter:

```typst
#show heading.where(level: 1): it => pagebreak(weak: true) + block(inset: (y: 10pt))[
  #text(size: 8pt, weight: "semibold", tracking: 1.2pt, fill: red, upper[Kapitel])
  #linebreak() #text(size: 26pt, weight: "bold", it.body)
]
```

Colour to all four edges, for a cover or a closing statement:

```typst
#page(margin: 0pt, header: none, footer: none)[
  #rect(width: 100%, height: 100%, fill: red, inset: 24mm)[ ... ]
]
```

Contents, generated from the headings rather than maintained by hand:
`#outline(title: [Inhalt], depth: 2)`. Captions are styled once with
`#show figure.caption: it => text(size: 7.5pt, it.body)`.

## Where Typst is not the answer

A piece a person will keep editing by hand, or a real press run with an exact
colour profile and crop marks, goes to `affinity`. A deliverable that is itself a
web page goes to `html`. Both are named, not worked around.
