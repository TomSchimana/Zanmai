// Proof that a freshly provisioned Typst can do the things a set document
// depends on. Not "is the binary there", which an exit code answers and a
// version string flatters: this compiles the primitives themselves, so a broken
// or half-unpacked install fails here instead of failing on page 40 of real
// work. Deliberately asset-free, so it needs nothing but the binary.
//
// Expected result: two A4 pages, the first one filled. It is filled because the
// wide block that no longer fits is deferred to the next page while the text
// keeps flowing into the current one, which is the one thing a browser cannot
// do and the reason this renderer exists in Zanmai.

#set page(
  paper: "a4",
  margin: 22mm,
  numbering: "1",
  background: place(top + left, rect(width: 100%, height: 12mm, fill: rgb("#cccccc"))),
)
#set text(lang: "de", hyphenate: true, size: 10pt)
#set par(justify: true)

#let wide(caption, cells) = place(
  top, scope: "parent", float: true, clearance: 10pt,
  block(radius: 3mm, inset: 6pt, fill: rgb("#f2f2f5"), width: 100%)[
    #text(size: 8pt, weight: "semibold", caption)
    #table(columns: (1fr,) * 4, stroke: none, ..cells)
  ],
)

#let filler = lorem(120) + " Datenschutzfolgenabschaetzung Betriebsvereinbarung Kuendigungsfristverlaengerung."

= Canary
#columns(2)[
  #filler
  #wide("A full-width block that does not fit here", ("A", "B", "C", "D", "1", "2", "3", "4", "5", "6", "7", "8"))
  #filler
  #filler
  #wide("A second one", ("X", "Y", "Z", "W", "1", "2", "3", "4"))
  #filler
  #filler
]
