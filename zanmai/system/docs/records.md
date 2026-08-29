[← Zanmai Documentation](index.md)

# What you keep

Contracts, policies, tax papers, certificates, the receipt you would need if the washing machine
broke. Things you hold on to because a law says so, because a contract runs, or because you would
be stuck without them.

## Why this is not the archive

They look alike from outside, and the difference decides what may happen to them.

The archive holds what answers no question any more. You may clear it out, and one day you will.
`records` holds what has to stay: the tax papers for as long as the tax office may ask, the policy
for as long as a claim can be made on it, the birth certificate for good. Every piece carries a
term, and throwing one away is a decision with a date attached rather than tidying up.

That is also why it sits beside the archive and not inside it. Anything that clears out an archive
would otherwise reach into the one folder that must not be cleared out.

The other difference is pace. Everywhere else in the vault something happens daily. Here a document
arrives, and then nothing happens to it for years. What eventually moves it is a term running out.

## Setting it up

The first time material would go there, Zanmai says what it is about to do and asks you two
things about it. Not a form and not a list to tick: it states the picture and you correct it.

- **What it takes as belonging there.** Zanmai has already looked at your material, so it names
  the sorts of document it found rather than asking you to remember yours. The question is only
  whether something is missing from that or something is too much. Whatever turns up later with no
  rule is asked about once, when it turns up, and remembered after that.
- **The keeping terms.** How long each sort is held, printed as it stands. They are on the long
  side deliberately, because holding a document too long costs disk space while letting go of it
  early can cost you a claim. So the question is whether they suit or you want changes, and yes is
  a normal answer. Zanmai does not ask which country you are in: it is not giving legal advice, and
  a list of legal areas would be wrong for everybody not on it.

The name is not asked. The area is called `records`.

What you confirm lands in `zanmai/retention.json`, and that file is what applies. The suggestions
shipped with Zanmai apply to nothing until you have been through them. Nothing is filed before that.

## What happens to a document

It arrives the way everything arrives, through `import`. A scanner drops a PDF there, you drop a
photo of a receipt, a mail export lands in it. It gets read, and then it gets a place and a term.

**The original is not rewritten.** What gets written is a note about the matter it belongs to: the
policy, the vehicle, the case. The individual letter is not turned into a note of its own, because
a hundred and twenty pay slips as a hundred and twenty notes turn up in every search you make for
years afterwards. Their words go into a search index instead, which nobody reads and everybody can
question.

## The matter, not the letter

A single letter answers nothing. What answers something is the matter it belongs to: this policy,
this employment, this car, this dispute. So the matter is what gets written down, once, and every
document that arrives becomes a line in its history.

Ask "does the household policy still run" and the answer comes from the matter, not from searching
twenty letters for the word "cancelled". Ask "what belongs to the tax year" and the matter lists it
in the order it happened.

You get a contact entry for whoever a matter runs with: the insurer, the landlord, the employer,
the bank. Not for every sender on every receipt. The shop you bought a bike from once is a line on
a document, findable in the index in seconds, and turning it into a contact would leave you with
hundreds of entries that lead nowhere.

A counterparty gets one name, however many ways it was written on paper. The same insurer turns up
as three spellings over ten years, and when they become three entries, one matter silently becomes
three. Where two spellings might be the same, you get asked; they are never merged behind your back,
because a wrong merge is invisible afterwards and takes both matters with it.

## Getting documents in

A pile at a time, not a document at a time. Point Zanmai at the folder and say which section of
the area it belongs in; the folders you already sorted it into are kept, because you have already
answered the question of what belongs together. Everything filed is read straight away, so it
answers a search the moment it lands.

Nothing is read out of a file's name. What a file is comes from the file itself, so a scan saved
without an extension, a contract that exists only as a saved web page and a mail exported under
some other name are all read the same way. What genuinely carries no text, a recording or a video,
is still filed and still findable by name.

## Finding things

Two different questions, two different answers.

"Where does this word appear" is answered by the index: every readable document, searched in
seconds. PDFs with a text layer are read directly, scans are read by machine, mails and images too.

"Does this still apply" is not a search question, and no index answers it. That is what the notes
are for: a policy that says it was cancelled, a contract with an end date, a case that closed.
Marcus, the curator, answers from those.

## Keeping terms

Three buckets, and nothing finer than that. **Four years** for everyday proof with no contract
behind it, **ten years** for money and contracts, and **for good** for what cannot be reissued.
Anything a rule somewhere would put at a year or two goes in the four-year bucket instead, and
anything beyond ten years is simply kept: past that point the difference is theoretical, and a disk
is cheaper than a paper you no longer have.

Alongside the bucket, each kept document has a state: **active** while the matter runs,
**retention-bound** while a rule says it has to stay, **evidence-only** where there is no duty but
you would want it, and **expired** once the term has run out.

Expired does not mean gone. It means it may go, and the decision is still yours: Zanmai proposes,
names how many pieces and which terms it rests on, and waits. Nothing is discarded on a date alone.

## Related

- [Folder architecture](folder-architecture.md), why this is a root of its own
- [Importing and filing material](importing.md), how things get in
- [Who does what](specialists.md)

---

[← Back to the documentation index](index.md)
