# Shot Design

Use this file for camera, motion, lighting, character control, style, and VFX.

## Camera

### One-Move Rule

For a single shot, specify one primary camera move only.

- good: `locked-off static camera`
- good: `slow dolly push-in`
- good: `slow orbit left around the subject`
- bad: `push in while panning left and tilting up`

### Stable camera contract

```text
Framing: wide / medium / close-up
Move: locked / push / pull / pan / tilt / orbit / tracking / handheld / crane
Speed: slow / moderate / fast
Angle: eye level / low angle / high angle
```

## Motion

Describe intent and consequence, not animation keyframes.

- `A charges, B sidesteps, dust kicks up at the turn.`
- `The bag swings once as she stops.`
- `Steam thickens as the coffee begins to pour.`

For complex action, use a reference video first. Text-only action should stay low-density.

## Lighting

Always name a source.

- `window backlight`
- `single overhead practical`
- `soft studio key top-left`
- `warm streetlamp backlight`

Useful additions:

- contrast: low-key / high-key
- color temperature: warm amber / cool blue / neutral white
- atmosphere: thin fog / dust motes / smoke drift / light rain

## Characters

### Identity anchors

Tag each reference inline next to the character it controls — 1-indexed,
matching the order of `image_urls=` in the API call:

- `Character A [image1] confronts Character B [image2] across the room.`
- `She [image1] turns toward the door.` (face + wardrobe consistency from image 1)
- `The hero [image1] in the rain-slick alley [image2].` (subject ref + scene ref)

Avoid ambiguous pronouns when multiple characters are present. **Without a
tag, Seedance falls back to using the first image as a literal first-frame**
— almost never what you want for character references. See
[`prompt-guidance.md`](prompt-guidance.md#reference-indexing--required-when-references-are-passed)
for the full convention.

### Hand and face safety

- prefer waist-up if hands are not essential
- use one simple hand action only
- avoid rapid head turns in extreme close-up
- re-upload identity references when extending a sequence

### First frame for I2V

The first frame should already contain:

- desired camera angle
- desired light direction
- starting pose, not mid-action
- clean background separation
- matching aspect ratio

## Style

Use one primary style anchor.

- `anamorphic, subtle grain, muted palette`
- `2D animation, bold outlines, flat shading`
- `stop-motion texture, visible material grain`

Useful material contract for CGI:

- base: glass / brushed aluminum / ceramic / leather
- roughness: matte / satin / glossy
- imperfection: dust / scratches / fingerprints / edge wear

Avoid empty boosters such as `masterpiece`, `ultra-real`, and `award-winning`.

## VFX

Describe the effect as a contract:

- source
- scale
- behavior
- interaction
- duration

Example:

`Blue sparks burst from the sword impact point, arc downward with gravity, briefly light the characters' faces, then fade within one second.`

For multiple effects, define hierarchy:

- primary effect
- secondary debris or particles
- environment reaction

## Fast presets

| Use case | Reliable approach |
|---|---|
| Product ad | orbit or slow push, soft key, clean background |
| Dialogue | locked medium close-up, single speaker, steady face |
| Fight | reference video or one beat per shot, handheld or tracking |
| Landscape | static wide or slow aerial pullback |
| MV | rhythm-led motion, strong style anchor, beat-visible camera |
