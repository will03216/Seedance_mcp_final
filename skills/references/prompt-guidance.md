# Prompt Guidance — Seedance 2.0 Optimization Framework

This file is the **mandatory pre-submission optimizer**. Before calling
`seedance_generate`, run the user's input through the 7-step pipeline
below and submit the **rewritten** prompt — never the raw user input.

Exception: user says "use this prompt as-is" AND it already follows the
6-component framework. Even then, run step 6 (the integrity check).

---

## Optimization principles (read first)

The optimizer is a **scalpel, not a blender**. Three rules govern every edit:

1. **Preserve user-provided structure.** If the input has explicit per-beat
   timestamps (`0–3s: …`), preserve them. Do **not** collapse a multi-beat
   timeline into one paragraph just because the default pattern is one
   paragraph.
2. **Preserve concrete technical detail.** `Kodak Vision3 250D`, `50mm
   anamorphic`, `T2.8`, `magic-hour rim light`, `Wong Kar-wai color`,
   `dust motes in the beam` — these are **signal**, not slop. Keep them
   verbatim. Anti-slop only deletes vague mood words (`epic`, `beautiful`,
   `amazing`, `cinematic` *alone*).
3. **Edit surgically.** When the only problem is a real public figure's name
   or a copyrighted IP, rewrite **just that span** to a descriptive original.
   Do not rewrite the whole prompt.
4. **Tag every reference.** If `image_urls=` / `video_urls=` / `audio_urls=`
   are passed to the API, each one **must** appear in the optimized prompt
   as `[imageN]` / `[videoN]` / `[audioN]` next to the entity it represents.
   Without these tags Seedance cannot bind references to subjects and falls
   back to "use first image as literal first-frame" — which is almost always
   wrong for character / object / style references. See the
   [Reference indexing](#reference-indexing--required-when-references-are-passed)
   section below.

If the raw input is already detailed and well-structured, the optimizer's job
is mostly the integrity check + safety rewrite + reference tagging — not a
full rebuild.

---

## The 6-component formula

Seedance 2.0 honors the **earliest strong instruction**. Default order:

> **`Subject → Action → Environment → Camera → Lighting → Style`** (+ optional Constraints)

| # | Component | What goes here |
|---|-----------|----------------|
| 1 | **Subject** | Who/what — singular if possible. Age, clothing, material, identity refs. |
| 2 | **Action** | One verb in present tense. One physical movement per shot. |
| 3 | **Environment** | Location + 1–2 renderable atmospheric elements. |
| 4 | **Camera** | Shot size + **ONE** move + angle/lens cue. See [`shot-design.md`](shot-design.md). |
| 5 | **Lighting** | Named setup — the highest-leverage quality lever, never skip. See [`shot-design.md`](shot-design.md). |
| 6 | **Style** | One concrete visual anchor + 1–2 modifiers. See [`shot-design.md`](shot-design.md). |
| 7 | Constraints | Negative list, duration, tempo, consistency. Last. |

### Length targets

| Prompt type | Target |
|-------------|--------|
| Single shot, simple | 50–80 words / 30–60 Chinese chars |
| Single shot, layered | 80–120 words / 60–100 Chinese chars |
| Multi-beat timeline (preamble + beats) | 200–350 words; preamble ≤120, each beat ≤30 |

The 150-word averaging limit applies to **single-paragraph** prompts. A
preamble + per-beat timeline can run longer because the per-beat lines act as
local anchors for each time window. Trim order: filler adjectives → repeated
environment details → secondary style tokens → sound notes → extra camera
modifiers. Never cut: subject, action, identity refs, per-beat timestamps,
**or reference tags** (`[imageN]` / `[videoN]` / `[audioN]`).

---

## Reference indexing — REQUIRED when references are passed

Whenever the user supplies image, video, or audio references, the optimized
prompt **MUST** tag each reference inline so Seedance knows which asset binds
to which subject. The tag goes immediately after the noun phrase the reference
describes.

### The tag convention

| Asset arg | Tag for index 0 | Tag for index 1 | … |
|-----------|-----------------|-----------------|---|
| `--image a --image b` | `[image1]` | `[image2]` | `[image3]` |
| `--video a --video b` | `[video1]` | `[video2]` | — |
| `--audio a`            | `[audio1]` | — | — |

Indices are **1-based** and follow the **order of the argument list**.
Chinese prompts may use `[图1]` / `[视频1]` / `[音频1]` instead — pick one
language style and stay consistent within a single prompt.

### What happens without tags

| Refs passed | Prompt has tags? | What Seedance does |
|-------------|------------------|--------------------|
| 0 refs | n/a | T2V — fine |
| 1 image | no tag | Treats it as **first frame** (I2V default) |
| 1 image | `[image1]` next to subject | Treats it as a **subject reference** |
| 2+ images | no tags | **First image becomes literal first-frame**, others are guessed at — ❌ this is almost always the wrong behavior |
| 2+ images | each tagged | References bound correctly to subjects |

So: **with two or more references, tags are not optional.** With one
reference, choose deliberately — first-frame (no tag) vs. subject reference
(tagged) — and write the prompt to match.

### How to place the tag

Put it **adjacent to the entity** the reference describes, not at the end of
the sentence. The tag binds locally.

✅ Good:
> The Carthaginian commander [image1] in bronze scale armor, sits atop an
> armored war elephant [image2]. He raises his curved sword high; camera
> tilts up. Audio bed: [audio1] (battlefield ambience).

❌ Bad (tags floating, no binding):
> The Carthaginian commander in bronze scale armor sits atop an armored war
> elephant. He raises his sword. References: [image1], [image2], [audio1].

### Multi-beat timelines

Tag at the **first introduction** of each entity (usually in the
identity-sentence between preamble and beat 0). Re-tag at major identity
beats (close-ups, scale changes) to lock continuity. Don't spam every beat —
that adds noise.

### Coverage rule

**Every URL passed must appear at least once as a tag.** Unreferenced URLs
waste budget and confuse the model. If the user supplies a reference you
don't use, drop it from the call rather than leaving it dangling.

---

## The optimization pipeline

### Step 1 — Triage & capture intent

First decide the **input shape**:

| Shape | Signal | How to optimize |
|-------|--------|-----------------|
| **Vague brief** | One line, mood words, no structure | Full rebuild via 6-component pipeline |
| **Single-shot draft** | One paragraph, has subject + action | Light polish + safety + integrity check |
| **Multi-beat timeline** | Preamble + `0–Xs:` lines | **Preserve beat structure**; rewrite only what fails safety/integrity |
| **Already optimized** | Follows 6-component, named lighting, no slop | Integrity check only |

Then capture: subject, goal (genre/mood/brand), references (flag human
portraits → [`assets.md`](assets.md)), hard constraints (duration, ratio,
audio, language).

Ask one clarifying question if something material is missing. Otherwise infer
from genre defaults in [`workflow.md`](workflow.md).

### Step 2 — Fill the compiler scaffold

```text
Mode:        T2V | I2V | R2V | V2V (face swap)
References:  [URL / asset:// — flag portraits]
Subject:
Action:
Environment:
Camera:
Lighting:
Style:
Constraints:
Audio:       (only if --audio flag is used)
```

- **I2V:** omit Subject/Environment (the image carries them); describe
  motion + camera + lighting changes only.
- **R2V / face swap:** state explicitly what to preserve from each reference.

### Step 3 — Compile to final form

**Single-shot prompt** → assemble into one paragraph in order: `Subject →
Action → Environment → Camera → Lighting → Style → Constraints`. Plain
commas and periods.

**Multi-beat timeline** → use this two-part shape (this is the format
Seedance honors best for time-based direction):

```text
[Preamble: shared technical contract — film stock, lens, aperture, color
 grade, lighting, atmosphere, audio bed. One block.]

[Subject identity sentence — original character, no public-figure names.]

0–Xs:  [shot size + camera move] — [action / dialogue]. [Sound cue.]
X–Ys:  …
```

Keep each beat to one camera move + one action + at most one dialogue line.
Different beats may use different camera moves — the "one move per shot"
rule is per beat, not per prompt.

Never use JSON or bullet `-` lists in the final string. Plain text only.

### Step 4 — Anti-slop pass (slop ≠ detail)

Delete every banned **mood word**: `cinematic` (alone), `epic`, `beautiful`,
`stunning`, `amazing`, `masterpiece`, `8K ultra-real`, `fast` (unqualified),
`dynamic` (unqualified), `lots of movement`. Full list in
[`safety.md`](safety.md).

**Do NOT delete concrete technical specs** — they look verbose but are
high-signal:

| Keep (signal) | Delete (slop) |
|---------------|---------------|
| `Kodak Vision3 250D`, `Fuji 8553` | `8K ultra-real` |
| `50mm anamorphic`, `T2.8`, `35mm feel` | `ARRI Alexa`, `RED Komodo` |
| `magic-hour rim light from camera-back` | `cinematic lighting` |
| `Wong Kar-wai color`, `Roger Deakins natural` | `epic look` |
| `dust motes in the beam`, `heat shimmer` | `beautiful atmosphere` |
| `slow push-in transitioning into forward tracking` (across beats) | `fast dynamic camera` |

If a banned mood word survives or a real public figure's name remains, the
pass is incomplete.

### Step 5 — Length check

Trim to target band. Never cut subject, action, or identity references.

### Step 6 — Final integrity check

Verify ALL before submitting:

- [ ] **Per beat (or per single-shot prompt):** one primary camera move + one
      primary action verb
- [ ] Lighting is **named** (not just implied)
- [ ] No banned mood words remain
- [ ] No camera brand names (`ARRI`, `RED`, `Sony`, etc.); film stock + focal
      length + aperture are fine
- [ ] No conflicting style/motion (e.g. "static slow handheld")
- [ ] Style has at least one concrete anchor
- [ ] Length within target band for the prompt shape
- [ ] **Multi-beat timeline:** beat structure preserved (not collapsed to one
      paragraph), timestamps intact
- [ ] **I2V:** prompt does NOT restate visible image content
- [ ] **Audio:** dialogue language matches user intent; lines quoted verbatim
- [ ] **Portraits in refs:** uploaded as `asset://` — handled automatically
      by `seedance_generate`, or manually via `seedance_upload_asset`
      (see [`assets.md`](assets.md))
- [ ] **Reference tags present:** every reference URL is tagged inline as
      `[imageN]` / `[videoN]` / `[audioN]` next to the entity it represents.
      With 2+ references this is mandatory; with 1 reference, choose
      first-frame (no tag) vs. subject-ref (tagged) deliberately
- [ ] No real public figures, named IP, or branded music
      (see [`safety.md`](safety.md)) — rewrite the offending span only, not
      the whole prompt

### Step 7 — Submit & log

Pass the **optimized** prompt to the `seedance_generate` MCP tool (or
`/seedance:generate` CLI command). Log both the raw and optimized versions
when iterating so you can compare outputs across iterations.

---

## Mode-specific patterns

### T2V

> A young woman in a red windbreaker walks across a wet alley at night. Slow
> tracking follow, medium shot, normal lens. Practical neon lights only, cool
> blue ambience, reflections on the pavement. 35mm film tone, subtle grain.

### I2V

> She turns her head toward camera, eyes narrowing. Slow push-in from medium
> shot to medium close-up over 4 seconds. Rim light unchanged. Rain continues
> in the background.

*(Never restate what the image already shows — motion + camera + light changes
only. Single image with no tag = first-frame default. Add `[image1]` only if
you want it treated as a styled subject reference instead of a literal first
frame.)*

### R2V — motion transfer

> Transfer the dance timing and camera rhythm from [video1] to the singer
> [image1]. Stage neon-lit, cuts aligned to the beat. One orbit move per
> chorus, otherwise locked-off.

### V2V — face swap

> Replace the face of the woman in [video1] with the face from the portrait
> [image1]. Preserve original body motion, background, clothing, and lighting
> from [video1]. Match skin tone and hairline blending. Static camera carried
> over from source.

### Multi-beat timeline (preserve when user provides one)

When the user supplies an explicit per-beat timeline, **keep the timeline**.
Lead with a shared technical-contract preamble, then the beat list:

```text
Film stock: Kodak Vision3 250D. Lens: 50mm anamorphic, T2.8 shallow depth.
Color grade: golden magic-hour, deep contrast. Lighting: low backlit sun
creating strong rim light, dust glowing in light rays, heat shimmer.
Atmosphere: drifting sand, banners in the wind. Audio: wind, distant army,
elephant rumble, soldiers shouting.

[Original character description with reference tag at first introduction —
no public-figure names.] Example: `The commander [image1] in bronze scale
armor sits atop an armored war elephant [image2].`

0–3s:   Wide rear tracking shot. The commander [image1] on the elephant
        [image2] surveys the battlefield from a dune ridge, army stretched
        behind him. Wind, low rumble.
3–6s:   Medium push-in from side. He turns slightly, scanning the lines,
        focused. Flags ripple, armor creaks.
6–9s:   Medium close-up. He grips his sword and raises it high; camera
        tilts up with the motion. Rising rumble.
9–11s:  Low-angle close-up. He [image1] shouts: "For Carthage!" Sun flares
        behind him. Wind surge.
11–13s: Wide shot from behind. The army roars in unison, weapons raised,
        line surging. Unified battle cry.
13–15s: Dynamic forward tracking. Cavalry and infantry charge past the
        elephant [image2], dust exploding skyward. Thunder of hooves,
        battle cries.
```

Drop timestamps **only as a fallback** — if the model produces jitter or
averages the beats after a first attempt, then collapse to one dominant
action and re-submit. Do not pre-emptively drop them.

---

## Worked rewrites

### Example 1 — Skateboarding

**Raw input:** `cool skateboard video, cinematic, fast, amazing tricks, lots of movement, epic style`

**Optimized:**
> A skateboarder in a dark hoodie lands a clean kickflip in an empty dawn
> parking lot. Low tracking shot, normal lens, subtle rise on the landing.
> Soft golden hour from camera-left, long shadows. 35mm film tone, modern
> contrast, light grain. Avoid jitter and bent limbs.

### Example 2 — Perfume product

**Raw input:** `beautiful product shot of a perfume bottle, very fast camera, cinematic dynamic epic feel, 8K ultra-real`

**Optimized:**
> A faceted perfume bottle on a black mirror surface. Slow dolly-in over 5
> seconds, telephoto (85mm feel), shallow depth of field. Single overhead
> spotlight refracting warm gold through the crystal, dust motes drifting in
> the beam. Anamorphic lens flare, rich blacks, bokeh background.

### Example 3 — Chinese coffee shop

**Raw input:** `拍一个咖啡店女生很美的视频，电影感`

**Optimized:**
> 一位短发女生坐在木质咖啡店窗边，双手捧杯轻吹热气。镜头从中景缓推至中近景。窗外晨光斜射，蒸汽在光柱中升起。35mm胶片质感、暖色调、轻微颗粒。

### Example 4 — UGC vlog (Bahasa Indonesia)

**Raw input:** `tiktok vlog street food jakarta, indo language, vibey`

**Optimized:**
> A young man vlogger walks through a Jakarta evening warung, waves at the
> camera, and says in fluent Bahasa Indonesia: "Halo guys, hari ini kita
> jalan-jalan makan makanan lokal." Handheld vertical 9:16, normal lens, eye
> level. Practical street-stall lighting, golden-hour warmth, mild handheld
> sway. Soft lo-fi music low under speech. Avoid watermarks and subtitles.

### Example 5 — Multi-beat historical timeline (preserve structure + tag refs)

**Setup:** the user passes two portrait images — commander and war elephant
(so `[image1]` = commander, `[image2]` = elephant).

**What's wrong with the raw input:**
1. Real public figure (`actor Denzel Washington`) — must be replaced with an
   original character.
2. **No reference tags** — Seedance will fall back to "first image as
   first-frame", which is wrong here.

Otherwise the input is well-structured and high-signal: keep the technical
preamble, keep the 6 beats, keep the dialogue line. **Do not collapse to one
paragraph.**

**Optimized (timeline preserved, public-figure span rewritten, references tagged):**
> Film stock: Kodak Vision3 250D. Lens: 50mm anamorphic, T2.8 shallow depth.
> Color grade: rich golden magic-hour, warm highlights, deep contrast, dusty
> mids. Lighting: low backlit sun creating strong rim light and silhouette,
> dust glowing in light rays, heat shimmer. Atmosphere: drifting sand,
> layered dust haze, banners moving in wind. Audio: wind, distant army
> movement, elephant rumble, soldiers shouting, dialogue.
>
> The Carthaginian commander [image1] — a tall, weathered general in bronze
> scale armor and a crimson cloak, dark beard, sun-darkened skin — sits atop
> an armored war elephant [image2].
>
> 0–3s:   Wide rear tracking shot. The commander [image1] sits high on the
>         elephant [image2] on a dune ridge, looking out across the
>         battlefield. His army stretches behind him. Camera pushes slowly
>         forward. Wind, low rumble.
> 3–6s:   Medium push-in from side. He turns slightly, scanning the lines,
>         expression focused. Flags ripple, soldiers shift.
> 6–9s:   Medium close-up. He raises his sword high; camera tilts up.
>         Rising rumble, soldiers beginning to react.
> 9–11s:  Low-angle close-up. He [image1] shouts: "For Carthage!" Sun
>         flares behind him. Wind surge.
> 11–13s: Wide shot from behind. The army responds — weapons raised, banners
>         whipping, line surging. Unified battle cry.
> 13–15s: Dynamic forward tracking. Cavalry and infantry charge past the
>         elephant [image2], dust exploding. Thunderous hooves, battle cries.

**What changed vs. raw:**
- `actor Denzel Washington` → original character description (surgical span only)
- **Added `[image1]` and `[image2]` tags** at first introduction and at
  identity-critical beats
- All technical specs, atmosphere, beat structure, timestamps: **kept verbatim**
