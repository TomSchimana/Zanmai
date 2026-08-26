---
name: video-review
description: Read a video by pulling frames: the two-pass review of a render, picking usable moments out of footage, reading a style off a reference. Runs in sub-agents.
---

# video-review

A model cannot hear or watch a video, it can only read. Frames make it readable. That single fact is why a rough cut from a transcript is reliably good and why anything visual comes back with small faults: nothing looked at the result. This skill is the looking.

Three jobs use it, and only the first is about quality control.

## Looking briefly is not reviewing

Most requests to look at a video are not a review. "What is in this", "is this usable", "what is it
about" want an answer in under a minute, and there is one command for exactly that: `zanmai.py
video brief`. It measures the facts, reads the loudness, transcribes once and pulls four frames,
and that is the whole look. On anything long the words come from three samples, the start, the
middle and the end, because transcribing two hours to answer "what is this" is the waste this
command exists to prevent.

**Start with the one picture**, `video timeline`: filmstrip, loudness and words across the whole
runtime in a single image. Everything below is for what that picture cannot answer.

What that replaced, and why the rule is written down: asked to look at a 78-second clip, a run made
34 tool calls, pulled 24 frames, read every one of them, ran scene detection over the full runtime
and spent seven minutes and 75,000 tokens. Nothing in it was wrong; all of it was too much. Frames
are images and images are what looking costs, so they are rationed rather than gathered.

The two-pass review below is the other thing entirely: it runs on a finished render, before it goes
out, and it costs real time because it is meant to. Running it when somebody asked for a look wastes
their afternoon and teaches them not to ask. **Match the depth to the question, and say which one
you are doing.**

## Always in sub-agents

Frames are images and images fill a context window fast. Send the review out, get findings back as text. The main run holds the job, not the pictures. One sub-agent per pass, and for a long piece one per section.

## Job one: review a render, in two passes

The passes are separate on purpose, and this is the most useful rule in this skill.

**Technical, as a checklist.** Everything with a yes or no answer: an element that vanished, a stretched or squashed picture, a wrong colour, text running past the frame, a brightness step at a seam, a caption over a face, duplicated frames, sound that jumps at a join. A checklist finds these reliably because none of them is a matter of opinion.

**Composition, as its own named pass.** "Why is that up there", "that is too small to read", "does this actually help". None of it has a pass or fail, which is exactly why a checklist-driven reviewer walks past it while looking straight at the frame that shows the problem. This pass re-checks every overlay against what the style says for that kind of element, and accounts for every distinct visual moment the direction named: built, or deliberately dropped and said so. Never quietly simplified away.

**Report timestamped findings**, each with what is wrong and where, not "the graphics need work". The run then fixes, re-renders and reviews again.

**Two rounds, then hand it over.** Not "until it passes": that is an open-ended loop with a render
and a set of frames in every turn, and it is how a review ends up costing more than the edit. Two
rounds catch what is catchable this way; what survives them is either a judgement the user has to
make or something the loop cannot see, and both belong in the return, named, rather than in a third
round. A round that fixes nothing is the signal to stop immediately, not to look harder.

**At most eight frames per round**, chosen at the seams that matter. The temptation is to sample
more because more feels safer; it is the single largest cost in this skill and the one that buys
the least.

**Run an early spot check** after the first tenth of the work, not only at the end. Spotted once, a wrong placement costs one correction; spotted after everything is built, it costs the build.

**Where to look.** Not every frame: the seams. The first and last moment of every insert, the join between two graphics, the boundary where a format change happens, the frame after a hidden cut, and the closing moments of every clip, where a bad frame hides because nobody looks there. Plus a sample across the runtime for the general feel.

## Job two: pick usable moments out of existing footage

Before anything is generated, look at what is already there. Screen recordings, phone clips, supplied material: pull frames, see what each stretch actually shows, and match it to the lines that need showing rather than telling. Note in and out points and what is visible, so the placement step reads a list instead of guessing from filenames.

This is the common case and it comes first. Generating material is for the beat that genuinely has none.

## Job three: read a style off a reference video

Two passes, and one pass is not enough.

**First, across the whole runtime**, roughly a hundred frames at scene changes: what kinds of scene exist, what they are called, in what rhythm they alternate, how long a shot is held.

**Then densely, on a handful of chosen joins**: into a full-frame takeover and back out again, one graphic handing over to the next, and anything the first pass marked as odd. The first pass says what the scenes are; only the second says how they join. A style written from the first minute of a video is a mood board every time.

The result has to be usable without the reference: named scene types, what happens at each kind of join, where an inset sits and how large, how a title is built up, how the camera behaves within a shot, which typeface carries which job, and pacing in measured seconds. If it reads as adjectives, it is not finished.

**Take the mechanic, never the assets.** Pacing, placement, the way things enter and leave, mapped onto the user's own colours and typefaces. Copying a look wholesale from someone else's channel is not a style, it is their material. The exception is the user's own back catalogue, where the literal values are theirs and pulling them out is the point.

## What comes back into the brand

A correction that should hold for every future piece is written back before the job closes: caption height, logo placement, loudness target, how long a card holds. It is proposed with the change shown, never written silently, and it goes to the video style rather than the brand unless it is true for every medium. Because each review reads the style fresh, an absorbed correction tightens every later review with no further wiring.

Distinguish it from a one-off note, which is applied and forgotten.
