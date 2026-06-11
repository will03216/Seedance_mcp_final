# Audio

Use this file for dialogue, lip-sync, beat-sync, and audio failure diagnosis.

## Scope

This guidance is for Seedance video generation, not the separate Jimeng digital-human workflow.

## Default rule

If exact audio playback is not required, describe sound in natural language:

- `soft room tone and distant rain`
- `low electronic pulse under the scene`
- `brief metallic impact when the blade lands`

Use `[audio1]` when rhythm or lip-sync matters — tag it inline next to the
speaking subject (e.g. `She [image1] speaks in sync with [audio1].`).

## Hard constraints from repo guidance

Treat these as working assumptions and re-check in the UI if needed:

- prefer MP3
- keep clips short
- single speaking face per clip is the safest setup
- short dialogue lines sync better than long monologues

## Lip-sync rules

### Text-driven

Most reliable for one speaker:

`She says: "We leave at dawn." Locked medium close-up. Minimal head motion.`

### Audio-driven

Use when timing must follow an uploaded file:

`The speaker [image1] lip-syncs to [audio1]. Locked medium close-up. No fast turns or nodding.`

## Multi-character workaround

Do not attempt dual-character lip-sync in one generation.

Use this workaround:

1. Generate speaker A alone.
2. Generate speaker B alone.
3. Composite the two clips in post.

## Beat-sync

Use compact rhythm language:

- `cuts land on the snare`
- `camera push on the chorus hit`
- `quick whip pan at beat drop`
- `卡点` for short-form Chinese prompts

## Audio failures

### Audio ignored or rewritten

Reduce competing motion instructions and shorten the clip. Treat uploaded audio as a reference signal, not guaranteed passthrough.

### Lip-sync drifting

- shorten dialogue
- lock the camera
- reduce head rotation
- keep one face in frame

### Distorted or weak audio

Regenerate shorter clips first. If the voice is critical, prefer compositing the final master audio in post.
