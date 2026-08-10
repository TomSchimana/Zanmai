---
name: motion
description: Timed visuals built as code and rendered headless: deciding whether a moment deserves one at all, the rules a jump-rendered timeline has to obey, what makes a design read as motion rather than as slides, and the failures that only surface once everything is assembled. Shared by anything that produces moving visuals.
---

# motion

A timed visual here is a small web page: markup for the content, a stylesheet for the look, a timeline for the movement, handed to a browser that saves one image per moment. Nothing limits how many a piece can hold. Everything that goes wrong goes wrong quietly.

Shared skill. Video editing reads it; so does anything else that has to make something move.

**Check that the renderer is there before planning anything that needs it** (`tools preflight
<expert> --capability motion`). Where it is missing, **the job stops here** (operating-principles §10): name what is
missing, name the one step that installs it, and hand it back. Not a substitute, not frames drawn
by hand and composited, not "close enough". That worked once for a caption bar and produced exactly
the wrong lesson: it looks like a result, it collapses at the first real graphic, and it hides the
missing prerequisite so nobody ever installs it. The user can then fetch the renderer or decide the
piece runs without motion graphics. Both are answers; improvising is not.

**How it is driven.** `zanmai.py tools ensure hyperframes` installs the renderer into the vault's
own runtime tree, pinned to one version; it lands at
`zanmai/runtime/node/node_modules/.bin/hyperframes` and is not on the PATH, so it is called by that
path. A piece is created once (`hyperframes init <name> --example blank --non-interactive`,
inside `zanmai/temp/<task>/`), checked (`lint`, `validate`, or `check` for both plus layout) and
rendered (`render`), which writes an MP4 into the project's `renders/`. Measured on the first run:
a ten-second composition, three hundred frames, six seconds of wall time. The project it creates
carries its own notes; read those for the composition format rather than guessing at it.

## Deciding, before building

**Most moments do not deserve one.** Restraint is the working assumption, and the case has to be made for adding, never for leaving out. A moment qualifies when it opens the piece, when it names something concrete that can be shown (a figure, a screen, a contrast), when it is the payoff a sentence was building toward, when a picture would replace a paragraph of explanation, or when the user asked. Everything between those, the connective sentences, the asides, the emotional lines, is stronger without.

Decide first, build second, and keep the two apart. Deciding while building produces choices made for ease of building.

## What kind

Settle on a handful of shapes and reuse them: a figure, a card, a captured screen, a full-frame takeover, a move across existing material, a diagram, a placeholder for something else.

**Pick the shape from what the moment is about, before writing a word of direction.** Choosing it up front is most of what stops the result reading as generic, because a shape chosen afterwards is whatever was easiest to build:

| the moment is about | reach for |
|---|---|
| one number landing | that number alone, counting up |
| several categories at once | a breakdown across them |
| parts of a whole | a ring or a divided bar |
| things ranked against each other | a podium or a ladder |
| a process or a system | a flow, drawn in step by step |
| something arriving | a notification, a message, an inbox |
| old against new | a before and an after, side by side or wiped |
| the words themselves being the payoff | the type moving, and nothing else on screen |

Showing beats telling, so real material beats a text card nearly every time. Save cards for the opening and the punchline, and even then give them something to look at besides letters.

Placement follows the frame shape, which is fixed before this skill runs.

Write the plan out as data, one entry per moment: identifier, when it starts and ends, its shape, and the actual direction. What is on screen, what dominates, and above all **what moves and in which order**. Moments without a visual do not appear at all. Check the plan mechanically before building: fields complete, times ascending, nothing overlapping, and neighbouring entries that either butt up exactly or stay a whole second apart. A gap of a few hundredths shows a flash of untreated picture.

## The timeline has to survive being jumped into

The renderer does not play the piece, it asks for arbitrary moments in arbitrary order. Every rule here follows from that one property.

Build a single timeline, paused, with every step placed at an absolute time rather than relative to its neighbour. Nothing may involve chance: the same moment has to come out identical every time it is asked for. Nothing may read a clock, because the clock has no relationship to the timeline position. Every movement needs a defined starting state, not only a target, or a jump into its middle finds nothing to interpolate from. Every element that disappears at a boundary needs its disappearance stated explicitly at that time, otherwise it lingers and then snaps. Work in seconds throughout. And never let stylesheet and timeline animate the same property, they will fight.

## Failures without an error message

This class costs days, because the run completes and the result is simply wrong.

Moving or scaling a video element directly makes it vanish from the output, silently. The way around is to leave the video untouched and animate the box around it instead, cropping through layout rather than through transformation.

Blur and desaturation as filters do not survive the render. A soft reveal is built from staggered letter opacity, a drained look by animating the colour toward something flatter.

Animating a class instead of a property does not apply, and can strip the element's styling on the way.

An instant change needs a real duration, a couple of tenths, or it applies unreliably. It still reads as instant.

A single emoji character can occupy the renderer indefinitely while it hunts for a font it will never find, without erroring and without timing out. Use the brand's own typeface or a prepared image. The symptom is a part taking several times as long as a comparable one.

A transparent layer has nothing behind it to blur, so frosted panels have to work from their own fill.

## What makes it read as motion

Reveal text by mask or word by word rather than fading it in. Never start two things together, offset everything by at least four tenths. Give the background structure. Let the accent colour touch exactly one element per scene. Numbers arrive by counting or flipping. Departures are composed, not omitted. Be more generous with empty space than instinct suggests. One thing dominates each frame, and never more than two things move. Make scale decisive. Draw lines and connectors in. Add small expensive details, a thin highlight, a faint reflection. Blur fast travel and clear it once things settle.

Invert that list and you have the look everyone recognises as automated: one layout reused, everything fading in together, flat backgrounds, unnamed easing, timid type, no exits, too many colours.

A moment lasting twenty seconds or more needs something moving throughout. An animation that resolves after six seconds leaves fourteen seconds of still frame; write down what carries the rest.

## Two kinds of part, and why it matters

Ask one question of every part: does it alter the picture beneath it, or sit on top of it?

Sitting on top means rendering alone against transparency and laying it over the base at its time. Altering the picture means the part carries its own copy of the base underneath and covers it completely for its window.

The base cut itself is never re-rendered, and that is the entire economy of this approach: changing one visual rebuilds one part, in seconds, followed by a single assembly pass.

Hold a visual until the next one begins rather than fading out into nothing. Enter an inset layout once and stay there; jumping between full frame and inset repeatedly is the clearest tell of an automated edit. Use the real logo and the real screen capture with a slow move on them instead of redrawing an approximation. Measure what you are framing, in pixels, from an actual frame, rather than estimating it. And let every part outlast its window by roughly half a second, so an assembly boundary that lands slightly late never finds nothing there.

## Assembly

These surface only when the pieces come together.

Every part matches the base frame rate exactly, read from the file, never assumed. A part that carries base footage takes its copy from the time it will actually sit at, not the time it was designed at; if the cut shifts afterwards, a copy taken at the old position jumps and drifts out of sync for its whole length. Parts that only sit on top can move freely.

Layers that sit on top must be told to stop at their end rather than repeat. Otherwise the assembly begins duplicating output frames at a steady rate: the file measures as a flawless constant frame rate while the content updates at a fraction of it, which reads as judder on anything smooth. Every input measures clean alone, so the search goes to the wrong place. Count identical consecutive frames in the result instead, and fail the assembly when they pass a low threshold. Do not paper over it by forcing a frame rate. The one legitimate exception is a frame meant to be held, such as a closing move that should not spring back.

Never hold a movement by padding frames; it never reaches an end and the file grows without bound.

Round-tripping footage through the browser costs a little brightness, and the face visibly dips at each such seam. Solve it in order: keep footage movement out of the browser entirely, because a move across a picture is geometry and needs nothing else; where the browser is unavoidable because live graphics appear behind moving footage, render its input losslessly, which halves the loss, and correct the remainder at assembly with a gamma adjustment rather than a flat gain, so black and white stay where they are.

A move applied to a slice taken from the middle needs its frame counter reset, or it renders as a constant and reads as a hard cut. Take the slice inside the filter chain and reset its timing rather than seeking to a position. A part starting at zero works by accident, every later one does not.

Anchor movement to cuts measured in the rendered file, not to the planned times. The render drifts from the plan across a long piece, and the transcript drifts with it.

Captured screens usually carry black borders. Detect and remove them before placing one inside a card, or the borders get scaled up and the content shrinks. Size such cards larger than seems right; type that looks generous while writing it renders small.

## Working practice

Both the linter and the validator run on every part before it renders. A contrast warning on intentionally dim text is answered by raising opacity, not brightness. A density warning on a small build is expected and not a reason to restructure.

Keep the sources with the job, never only in scratch space, which is swept on a schedule. Only the heavy, reproducible renders belong in a cache.
