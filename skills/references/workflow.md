# Workflow

Use this file when the user has an idea but not yet a clean Seedance prompt.

## Default flow

1. Identify the job: product, lifestyle, drama, music video, landscape, commercial, anime, or UGC.
2. Decide the mode:
   - `T2V`: no references, text must establish subject, scene, and style.
   - `I2V`: image exists, text should describe motion and camera only.
   - `R2V`: image, video, or audio references exist, text should explain how to use them.
3. Decide whether to interview or draft directly:
   - Interview when the user is vague, story-first, or uncertain about genre.
   - Draft directly when they already know the subject, action, and look.
4. Build one clip, not a whole film. Each Seedance request should express one beat.
5. Test short first. Short clips surface prompt errors faster.

## Director's journey

Use this lightweight interview when the user needs guidance:

1. Vision: ask for the one-sentence concept.
2. Genre: pick the category because genre changes prompt structure.
3. References: ask whether there are images, videos, or audio assets.
4. Emotional anchor: identify the key feeling or conflict.
5. Final beat: define what visibly changes in this clip.

Exit early if the user already has strong references and a clear genre. Move straight into prompt assembly.

## Intent over precision

Seedance behaves better when you direct outcomes instead of dictating every micro-detail.

- Bad: cataloguing every material, lens, and movement in one dense paragraph.
- Good: stating the subject, the action, the emotional tone, and the single camera move.

Use precise language only where the model historically fails without it:

- camera path
- timing of beats
- light source direction
- character identity anchors
- VFX consequence

## Reference-first workflow

If the user can show it, do not redescribe it.

- `[imageN]` (e.g. `[image1]`, `[image2]`): identity, costume, frame composition, background lock
- `[videoN]` (e.g. `[video1]`): motion, choreography, camera language, rhythm
- `[audioN]` (e.g. `[audio1]`): lip-sync reference, beat map, tone, pacing

Tag every passed reference inline next to the entity it controls. Indices are
1-based and follow the order in `image_urls=` / `video_urls=` / `audio_urls=`.
The text prompt should explain what changes relative to the tagged reference.

## I2V gate

In image-to-video mode:

- Describe motion.
- Describe camera movement.
- Describe expression change if needed.
- Do not restate clothing, environment, or style already visible in the image.

## Quick decisions

Use these defaults when the user gives little information:

| Situation | Default |
|---|---|
| Product image exists | `I2V`, motion-only prompt |
| Character scene with one face image | `I2V`, medium close-up or medium shot |
| Fight or dance with a reference clip | `R2V`, transfer motion from `[video1]` |
| No assets, broad idea | `T2V`, one clear subject + one action + one move |
| Dialogue scene | single speaker per clip, locked framing |

## Output contract

Before writing the prompt, define:

- subject
- action
- scene
- camera
- tone
- constraints

If one of these is missing, ask or infer before drafting.
