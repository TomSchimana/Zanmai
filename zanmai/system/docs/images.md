[← Zanmai Documentation](index.md)

# Generating images and video

Stills, short clips and upscales, made through a service you have connected, and marked so you can publish them.

## Before anything is rendered

Generating spends real money, so it never runs unasked. Asking for an image is your go, and the cost is quoted first. An image that another job needs, for instance a flyer that is missing a photo, comes back to you for a yes before it is rendered. Where existing material can be adapted instead, that is preferred over generating something new.

You get asked for a few things because they decide the result: what the subject is, where the image will be used, a reference for style or mood, the format and resolution, any text that must appear inside the image, and for video how long it should be. Video is billed per second, so the duration is quoted before it runs and derived from the movement you described rather than a fixed default.

## Real people

A likeness of a real person is anchored to a real photograph that Zanmai can open and inspect, never to a description and never to another generated image. If you name someone, the character library is searched for them first; an unclear or missing match becomes a question to you rather than a silent guess.

For someone appearing across several images, in different outfits, or in video, a character set is built from several real photos and used as the anchor, so the face stays the same person. Without such a set Zanmai makes no claim that the result resembles anyone and says so plainly instead of asserting it.

For a person, and always for video, the first thing you get is the reference frames themselves, the character set or the start, middle and end frames. You approve those before any paid clip is rendered. Skipping that is how you pay for a clip whose face drifts halfway through.

## Judging the result

The rendered file is looked at, not just described from the prompt: artefacts, hands, garbled text, faithfulness to what you asked, composition, light, and whether it reads as AI slop. For video also whether the motion is consistent and the physics plausible. A miss across the whole image means rendering again with a sharper prompt or a different model; a local defect is repaired in place by editing, inpainting, upscaling or relighting.

## Marking, so you can publish it

Two separate duties, both handled without guesswork.

A machine-readable credential travels with every generated or edited asset. If the generating service already signed the file, that signature is preserved and passed through rather than stripped. If it was not signed, one can be added. If neither is possible you get a clear warning; a file is never quietly delivered as unmarked.

A visible mark goes on when disclosure is actually required, which is the case for photoreal material resembling a real or plausible person, place or event. It uses the European Commission's official icon by default, or a text label reading "AI-generated" or "AI-edited" in your language. Zanmai works out which class applies and recommends it with a one-line reason; the decision stays yours, offered as a short menu. Abstract or obviously synthetic work carries the machine-readable mark only.

## Editing what you already have

When the pixels exist, editing them locally costs nothing and involves no model: converting formats, resizing, cropping, rotating, greyscale, compositing, batch operations across a folder. Heavier work such as applying a colour lookup table, matching colour to a reference, or developing a camera raw file is available once the tool for it is present. This path is preferred whenever the image already exists.

## What you get

Variants are rendered into a scratch area and shown to you first. The one you pick moves to `doing`, or into a design piece, where it sits in that piece's own bundle. The prompt, the references, the model and the parameters travel with the file, so a later variant inherits the right anchors instead of losing them.

## Related

- [Connecting outside tools](connections.md), how an image service is set up once
- [Designing documents](design.md), when the image belongs inside a piece

---

[← Back to the documentation index](index.md)
