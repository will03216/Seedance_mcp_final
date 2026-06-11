# Safety

Use this file when the prompt is blocked, too generic, or risks policy collisions.

## Three safety passes

1. Copyright and likeness
2. Content-filter phrasing
3. Anti-slop cleanup

## Copyright and likeness

Avoid:

- named franchise characters
- direct brand and logo requests
- living public figures

**Real or virtual human portraits as references**: must be uploaded through the Assets API first. Direct upload (HTTP URL or `data:` URI) is rejected by input moderation with `InputImageSensitiveContentDetected.PrivacyInformation`. After upload, reference via `asset://<asset_id>`. The `seedance_generate` MCP tool handles this automatically — see [`assets.md`](assets.md) for the manual flow.

Rewrite toward archetypes and visual descriptors:

- `wall-crawling superhero` instead of a named IP
- `iconic shell-roof opera house` instead of a protected building name
- `luxury sports sedan with angular headlights` instead of a brand model name

## Content-filter strategy

Write like a filmmaker, not casual chat.

A safer prompt answers four questions:

1. where is the scene
2. what is visible
3. what is the camera doing
4. what is the atmosphere

Production language usually passes better than vague shorthand.

## Anti-slop rules

Every word should be observable or operational.

Delete:

- stunning
- cinematic
- epic
- breathtaking
- incredible
- beautiful
- masterpiece

Replace with:

- shot size
- camera move
- lighting source
- surface detail
- timing
- physical consequence

## Troubleshooting tree

### Jitter, blur, or morphing

- shorten the prompt
- reduce beat density
- remove stacked camera moves
- simplify action to one clear beat

### Camera ignores instructions

- enforce the One-Move Rule
- restate framing explicitly
- remove extra motion verbs

### Character drift

- add or restate the identity reference
- reduce scene complexity
- avoid changing wardrobe nouns mid-series

### Weak action

- use stronger verbs
- add physical consequences
- if available, transfer motion from a reference video

### Output feels wrong but not broken

- the prompt is probably too abstract
- front-load subject and action
- cut filler adjectives
- try a simpler five-second version first

## Quick filter-safe wording

- `low-angle tracking shot`
- `medium close-up, locked camera`
- `single hard key with soft fill`
- `tension, quiet, no dialogue`
- `impact sends dust outward`

These phrases are safer than mood-only language because they express production intent.
