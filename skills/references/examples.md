# Examples

Use this file for starter templates and compact working examples.

## Genre templates

### Product

`Glass perfume bottle on white marble. Slow orbit hero shot. Soft studio key with rear rim light. Macro depth-of-field. Clean background, no text.`

### Lifestyle

`A young woman pours coffee in a sunlit kitchen. Handheld phone perspective with slight sway. Warm morning light, candid and casual.`

### Drama

`A man @Image1 walks through a narrow corridor holding a flashlight. Handheld follow from behind. The scene is quiet except for footsteps and breath.`

### Music video

`A singer @Image1 performs to the track @Audio1. Neon warehouse stage. Quick camera bursts and cut rhythm aligned to the chorus. Strong magenta-blue palette.`

### Landscape

`Sweeping aerial over mountain ridges at dawn. Mist hangs in the valley. Slow pullback reveals scale. Cold blue shadows shifting to warm sunrise gold.`

### Commercial

`A black sports car moves along a mountain road at sunset. Low tracking camera beside the bodywork. Warm flare and restrained premium mood.`

### Stylized / anime

`White-haired warrior draws a glowing blade. Dynamic low-angle shot. Bold outlines, flat shading, high-contrast anime rendering, blue particle trail.`

## Short-drama templates (multi-asset, timeline)

Short dramas lean on character consistency + storyboard rhythm. Lead with an
asset/role declaration, then a per-beat timeline, then style + the portrait
constraint block. Keep one camera move + one action per beat; externalize
emotion as physical cues.

### Dialogue-heavy (dorm scene)

Assets: `@Image1` female lead (half body), `@Image2` dorm scene, `@Video1`
indoor dialogue camera ref, `@Audio1` room ambience.

> The girl @Image1 is the lead; @Image2 sets the dorm style; camera movement
> follows @Video1; ambience blends with @Audio1.
>
> 0–5s:   Early evening. The girl @Image1 walks briskly to the dorm door.
>         Medium shot, steady tracking. Warm sunlight spills down the corridor.
>         She pauses, takes a breath; lips press together, a flicker of nerves.
> 5–10s:  She pushes the door open. Cut to indoor medium shot. A roommate looks
>         up: "How'd the exam go? Did you pass?" Camera eases between half-body
>         close-ups.
> 10–15s: She lowers her head, shoulders dropping — close-up. Then looks up,
>         unable to hold back a grin: "Just kidding!" Camera slowly pulls back
>         to a wide shot of the laughing dorm.
>
> Warm tones, soft light, documentary feel. Stable face without deformation,
> normal proportions, natural fluid movement, no flicker, no stutter.

### Action / atmosphere-heavy (cliff duel)

Assets: `@Image1` red-robed lead, `@Image2` black-robed antagonist, `@Image3`
cliff bamboo forest, `@Video1` duel camera ref, `@Audio1` drums. Use `@Video1`
for camera/timing only.

> @Image1 is the lead, @Image2 the antagonist, scene from @Image3; camera and
> rhythm follow @Video1 (camera only, not its characters); drums from @Audio1.
>
> 0–5s:   Dusk. Slow push-in, side medium shot of the red-robed woman @Image1
>         at the cliff edge; robes sway in the wind; jaw set, gaze cold. A dark
>         figure @Image2 is faint in the distant bamboo.
> 5–10s:  Focus-shift to a wide aerial. The two stand at opposite ends of the
>         cliff; wind whips dust. Rhythm lifts with the drums.
> 10–15s: Ground-level close-up. Both draw swords; the black-clad woman's @Image2
>         sword tip trembles. Camera follows as they circle, freezing on the
>         instant before the blades meet.
>
> Cool desaturated tones, misty wuxia texture, vintage film grain. Stable faces
> and body proportions, fluid movement, no stiffness, no stutter.

## Chinese prompt examples

### Product I2V

`镜头缓慢环绕香水瓶九十度，玻璃折射高光，柔和棚灯主光，标签保持清晰，背景纯净无文字。`

### Drama I2V

`她缓慢转身看向镜头，眼神从犹豫变得坚定。中景缓推到中近景，雨夜霓虹继续在身后反光。`

### Action with references

`角色A@Image1冲刺逼近角色B@Image2，B侧身闪开后反击。动作节奏与运镜参考@Video1。地面扬起灰尘，低角度跟拍。`

*(中文 prompt 也可用 `[图1]` / `[视频1]` / `[音频1]`，但同一段提示词只用一种语言风格。)*

## Seedance 2.5 templates

These four patterns are only possible on Seedance 2.5. Each names its task type,
because the model classifies from the prompt and the classification decides which
parameters it will accept.

### Multi-video advertising cut (reference-to-video)

The pattern the 30s / 10-video ceiling actually earns: one reference video per
*function*, each named for the exact quality it contributes. Note that no clip is
borrowed wholesale — each is cited for composition, or motion, or impact, or
rhythm.

> Bright, colourful advertising-film style with fruit-flavoured cookies as the
> subject: strawberry, apple, grape, orange. The strawberry flavour follows
> @Image1. Cookies and fruit sit in strongly ordered geometric arrays; the frame
> is clean, premium, rhythmic. Open on a fast build of visual focus on the fruit,
> composition following @Video1, with the music downbeat cutting in. Cookies of
> different flavours arrange into rows, then cut to close-ups, motion and camera
> movement following @Video2. At the climax one cookie snaps in half and drops
> into slow motion — filling bursts, crumbs fly, the juicy texture and granular
> impact amplified, following the impact of @Video3. A horizontal array traces a
> rhythmic parabola, movement following @Video4, then the cut rate snaps back up.

`--duration 15 --ratio 16:9 --audio`

Every reference carries a named job. A reference you cannot describe a job for is
a reference you should drop.

### Video edit — remove an element

Task type: **edit**. Ratio and duration are locked to the source; pass neither.

> Video edit: remove everyone in @Video1 except the protagonist.

`seedance edit --video https://…/scene.mov --output-format mov`

Lead with the operation ("Video edit:", "Remove", "Replace", "Add") so the
classifier does not read the request as a fresh generation. Name the target clip
explicitly whenever more than one video is passed.

### Video extension — continue a shot

Task type: **extend**. Ratio is locked to the source; duration is yours.

> Extend @Video1: after the window opens, the camera moves through into the
> gallery interior of @Video2, and finally pushes into the painting in @Video3.
> Character, lighting, and grade unchanged across the join.

`seedance extend --video …/1.mov --video …/2.mp4 --video …/3.mp4 --duration 11`

Extension can pull *new* material from additional reference videos — the shot
continues into somewhere it has not been. Restate what must not change; the join
is where continuity breaks first.

### Audio-driven generation (no visual reference)

Task type: reference-to-video, with audio as the only reference.

> A dancer moves to the rhythm of @Audio1. Neon warehouse, wet concrete floor
> throwing back magenta and cyan. Handheld camera, short bursts of movement,
> cuts landing on the downbeats. Hard rim light from behind, haze in the air.

`--audio-ref https://…/track.mp3 --duration 20`

The track sets the cut points, so the duration math in
[`duration-calculus.md`](duration-calculus.md) yields to the clip's actual
length — estimate it and commit to an integer.

## Template for fast drafting

```text
[reference if any]
[subject]
[single visible action]
[scene]
[single camera move]
[light or style anchor]
[optional sound or constraint]
```
