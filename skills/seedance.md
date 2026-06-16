---
name: seedance
description: Generate videos with BytePlus Seedance 2.0 — text-to-video, image-to-video, prompt optimization, shot design, audio/lip-sync, asset management, and task tracking.
version: 2.2.1
---

# Seedance Video Generation

Use this skill to generate AI videos with BytePlus Seedance 2.0 directly from Claude Code.

> **🚨 MANDATORY PRE-FLIGHT RULE #1 — Prompt optimization**
>
> Before calling `seedance_generate`, you **MUST** rewrite the user's input
> through the optimization pipeline in
> [`references/prompt-guidance.md`](references/prompt-guidance.md):
>
> 1. Capture intent → 2. Fill the 6-component scaffold (Subject + Action +
>    Environment + Camera + Lighting + Style) → 3. Compile to one paragraph
>    → 4. Anti-slop pass → 5. Length check → 6. Final integrity check.
>
> **Submit the optimized prompt, never the raw user input.** Show the user the
> optimized prompt before submission so they can confirm or tweak it.
>
> **If references are passed** (`--image`, `--video`, `--audio-ref`),
> the optimized prompt **MUST tag every reference** as `[image1]`, `[image2]`,
> `[video1]`, `[audio1]`, etc. (1-indexed, in argument order) next to the
> entity it represents. Without these tags, Seedance cannot bind references to
> subjects and falls back to using the first image as a literal first-frame —
> which is wrong for character / object / style references.
>
> (`--audio-ref` passes a **reference audio clip** for lip-sync / beat / pacing.
> The separate `--audio` flag is a boolean that asks Seedance to *generate* a
> matching audio track — it is not a reference and is not tagged.)
>
> The only opt-out: the user explicitly says "use this prompt as-is" *and* the
> input already follows the 6-component framework *and* (if refs are passed)
> already contains the `[imageN]` / `[videoN]` / `[audioN]` tags. Even then,
> run the integrity check (step 6) before submission.

> **🚨 MANDATORY PRE-FLIGHT RULE #2 — Real or virtual human portraits**
>
> If **any** input image contains a real or virtual human portrait (face / full-body / character reference):
>
> - **Automatic path**: use `seedance_generate` — it auto-uploads *every* plain-HTTPS image reference to the asset library before submitting (there is no portrait detector; it uploads unconditionally, which is exactly why portraits are always safe). Refs already in `asset://` form are passed through untouched.
> - **Manual path**: call `seedance_create_asset_group` → `seedance_upload_asset` → use the returned `asset://` URL.
>
> **Do NOT** pass raw HTTP URLs for human portraits to `seedance_image_to_video` directly — they trigger `InputImageSensitiveContentDetected.PrivacyInformation`.
>
> Non-human references (backgrounds, storyboards, objects, scenery) can use plain URLs as before.
>
> **See [`references/assets.md`](references/assets.md) for the full Assets API workflow.**

## Prerequisites

Install and configure before first use (run from the repo root):

```bash
git clone https://github.com/mittulmadaan/byteplus-seedance-mcp
cd byteplus-seedance-mcp
pip install packages/seedance-sdk packages/seedance-mcp -e packages/seedance-cli
seedance auth login        # stores credentials in ~/.seedance/credentials
seedance skill install     # wires up MCP server into Claude Code & Claude Desktop
```

Then restart Claude Code/Desktop.

---

## Loading map

- **Read [prompt-guidance](references/prompt-guidance.md) on EVERY submission** — mandatory 6-component optimization pipeline, anti-slop checklist, integrity checklist, and worked rewrites. Run the user's input through it before calling `seedance_generate`.
- Read [workflow](references/workflow.md) when the user needs ideation, genre routing, or I2V/T2V decision rules.
- Read [shot-design](references/shot-design.md) for the deep vocab on camera, motion, lighting, characters, style, and VFX.
- Read [audio](references/audio.md) for dialogue, music, lip-sync, and beat-sync.
- Read [safety](references/safety.md) for copyright, content filters, anti-slop rewrites, and troubleshooting.
- **Read [assets](references/assets.md) whenever the input includes a real or virtual human portrait** — the Assets-upload flow is mandatory before generation.
- Read [examples](references/examples.md) for genre templates and Chinese examples.
- Read [vocabulary-zh](references/vocabulary-zh.md) when the user wants prompt-ready Chinese film language.
- Read [platform](references/platform.md) for operational constraints, asset budgets, and API key setup.

---

## Core rules

1. **Always optimize before submission.** Run the user's input through [`references/prompt-guidance.md`](references/prompt-guidance.md) (the 6-component pipeline + anti-slop pass + integrity check). Submit the optimized prompt, not the raw user input. Show the optimized prompt to the user before submitting.
2. Intent over micromanagement. Tell the model what happens and how it should feel.
3. References beat description. **If the reference is a human portrait → `seedance_generate` handles upload automatically. Other references can use direct URLs.**
4. In I2V, describe motion and camera only. Do not restate the image.
5. One primary camera move per shot. One primary action verb per shot.
6. Always name a lighting source — it is the highest-leverage single quality lever.
7. Keep prompts dense. Default target: 30–100 Chinese chars or one compact paragraph (50–120 English words). Past 150 words the model averages.
8. Use async submission only. Submit → return `task_id` → poll `seedance_check_task` on demand. No blocking, no `time.sleep`.
9. If the user wants to submit but no `ARK_API_KEY` is configured, run `seedance auth login` or see [platform](references/platform.md). Do not assume a key already exists.
10. **Watermark defaults to off.** Never enable watermark unless the user explicitly asks.
11. **Resolution defaults to `720p`.** Never fall back to `480p` silently. Use `1080p` only when the user explicitly requests it.
12. **Tag every reference in the prompt.** When `--image`, `--video`, or `--audio` are passed, the optimized prompt MUST tag each reference inline as `[image1]`, `[image2]`, `[video1]`, `[audio1]`, etc. (1-indexed, in argument order). Coverage rule: every passed reference must appear at least once as a tag; if you don't tag it, drop it from the call.

---

## Generate a video

Invoke with `/seedance generate <prompt>` or just describe what you want — the skill triggers automatically.

**Text-to-video:**
```
/seedance generate a silver espresso machine on a modern kitchen counter,
morning light cuts in, steam rises slowly, camera slowly pushes in
```

**Image-to-video (portrait / reference image):**
```
/seedance generate [image1] smiles softly, camera slowly pushes in --image https://example.com/portrait.jpg
```

**Full options:**
```
/seedance generate <prompt>
  --image <url>          Reference image (auto-uploaded to asset library for portraits)
  --video <url>          Reference video — motion/camera rhythm, or a clip to extend. Repeatable, max 3. Tag [video1]…
  --audio-ref <url>      Reference audio — lip-sync / beat / pacing (MP3/WAV). Repeatable, max 3. Tag [audio1]…
  --first-frame <url>    Pin the exact starting frame
  --last-frame <url>     Pin the ending frame (requires --first-frame)
  --ratio 9:16           Aspect ratio: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
  --duration 6           Length in seconds (4–15)
  --resolution 1080p     Quality: 480p | 720p | 1080p
  --audio                GENERATE a matching audio track (boolean — not a reference)
  --fast                 Use faster/cheaper model variant
  --seed 42              Reproducible results
  --camerafixed          No camera movement (product shots)
```

**All-round reference (image + video + audio):**
```
/seedance generate the singer [image1] performs on the neon stage, dance timing and
camera rhythm follow [video1], cuts land on the beats of [audio1]
  --image https://example.com/singer.jpg
  --video https://example.com/dance-ref.mp4
  --audio-ref https://example.com/track.mp3
```

**Video extension (continue an existing clip):** there is no separate extend
endpoint — pass the previous output as a `--video` reference and describe the
continuation. Keep character, scene, and lighting locked.
```
/seedance generate extend [video1] backward by 5 seconds; the woman keeps walking
down the same corridor, character, background, and lighting unchanged
  --video https://.../previous-output.mp4
```
For dramas longer than ~15s, prefer **segmented splicing**: generate each
10–13s beat independently with the *same* reference set + template, then splice
in an editor. Use extension for single continuous takes (dialogue, one-path
movement); use splicing for scene changes and fast action.

The MCP tool `seedance_generate` handles everything automatically:
1. Creates an asset group and uploads every plain-HTTPS `--image` reference to the BytePlus asset library (any non-`asset://` URL — not just portraits); `asset://` refs are passed through untouched
2. Passes any `--video` / `--audio-ref` references through (URL-only, not uploaded) — bound by content role and matched to `[video1]` / `[audio1]` tags
3. Submits the generation job
4. Returns `task_id` — poll `seedance_check_task` every 10–15 seconds until `status == "succeeded"`

---

## Check task status

```
/seedance status <task_id>
```

Returns `status` (queued | running | succeeded | failed | cancelled) and `video_url` when done.

---

## List recent tasks

```
/seedance list
/seedance list --status succeeded
/seedance list --limit 20
```

---

## Upscale / enhance an existing video

Standalone capability — **independent of `seedance_generate`**. Takes a publicly accessible
video URL (e.g. a Seedance output URL) and runs AI enhancement (denoise, color, artifact
removal, super-resolution up to 4K) via BytePlus AI MediaKit.

- Requires `MEDIAKIT_API_KEY` (separate from `ARK_API_KEY`; created in the AI MediaKit console).
- Async, two-step like generation: submit → poll. Terminal status is `completed` | `failed`
  (note: **not** `succeeded`), so poll with `byteplus_check_upscale_task`, not `seedance_check_task`.
- **Idempotent**: identical parameters reuse the same task for 24h. Pass `force_new=True` (or a
  distinct `client_token`) to force a fresh task on identical input.
- Output `video_url` is valid for **24 hours** — download promptly.

MCP:
```
byteplus_upscale_video(video_url="https://.../output.mp4", tool_version="standard", resolution="1080p")
→ { task_id: "amk-tool-enhance-video-xxxx", status: "submitted" }

byteplus_check_upscale_task(task_id="amk-tool-enhance-video-xxxx")
→ { status: "completed", video_url: "https://...", resolution: "1080p", fps: 60 }
```

CLI:
```bash
seedance upscale https://.../output.mp4 --resolution 1080p --watch
seedance upscale-status <task_id>
```

Key options: `--tool-version standard|professional`; `--resolution 240p..1080p|2k|4k`
(mutually exclusive with `--resolution-limit <128..2160>`); `--scene` (standard only:
`common|ugc|short_series|aigc|old_film`); `--bitrate-level low|medium|high`; `--fps 15..120`.

---

## Asset library (for portraits / sensitive images)

Plain HTTPS image URLs for human faces return `InputImageSensitiveContentDetected`.
`seedance_generate` (MCP) and `seedance generate` (CLI) handle this automatically.

For manual control or reusing assets across multiple generations:

```bash
seedance asset group create my-portraits       # one-time per project
seedance asset upload https://... --group <id> # returns asset://asset-xxx
seedance generate --image "asset://asset-xxx"  # skip re-upload
```

See [`references/assets.md`](references/assets.md) for the full API reference,
best practices for splitting portrait references, and failure recovery.

---

## MCP tools reference

| Tool | Description |
|---|---|
| `seedance_generate` | Full pipeline: upload portraits + submit + return task_id (preferred) |
| `seedance_check_task` | Poll status, get video_url when succeeded |
| `seedance_text_to_video` | Fine-grained T2V — returns task_id |
| `seedance_image_to_video` | Fine-grained I2V with multiple refs — returns task_id |
| `byteplus_upscale_video` | Upscale/enhance an existing video (AI MediaKit, up to 4K) — returns task_id |
| `byteplus_check_upscale_task` | Poll an upscale task; get enhanced video_url when completed |
| `seedance_list_tasks` | Browse generation history |
| `seedance_cancel_task` | Cancel a queued or running job |
| `seedance_create_asset_group` | Create asset group (manual flow) |
| `seedance_upload_asset` | Upload image, poll until Active (manual flow) |
| `seedance_get_asset` | Check asset status |
| `seedance_list_models` | Show available models and capabilities |
| `seedance_ping` | Verify credentials and connectivity |

---

## Troubleshooting

**`InputImageSensitiveContentDetected`** — Use `seedance_generate` (auto-uploads to asset library) instead of passing the raw URL to `seedance_image_to_video`.

**`ARK_API_KEY not configured`** — Run `seedance auth login` or `export ARK_API_KEY=...`.

**MCP timeout** — Never use blocking generation. Always use the two-step pattern: submit → poll `seedance_check_task`.

**Output jitter or drift** — Shorten the prompt, enforce One-Move Rule (one camera move per shot), add explicit lighting source.

**Character identity drift** — Re-upload identity references as separate assets (face / outfit / three-view). See [`references/assets.md`](references/assets.md) → Best practice section.

**Prompt blocked by content filter** — Rewrite using production language: name the shot size, camera move, lighting source, and surface detail. See [`references/safety.md`](references/safety.md).

**Reinstall after update:**
```bash
pip install --upgrade "seedance-cli[mcp]"
seedance skill install
```
