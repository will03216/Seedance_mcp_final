# Seedance 2.5

Generate AI videos with **BytePlus Seedance** — from your terminal, your AI client, or Claude Code.
Seedance 2.5 is the default model; Seedance 2.0 remains available behind `model="2.0"`.

## What Seedance 2.5 changes

| | Seedance 2.5 *(default)* | Seedance 2.0 |
|---|---|---|
| Duration | **4–30s**, or `-1` for model-chosen | 4–15s, or `-1` |
| Resolution | **480p / 720p** | 480p / 720p / **1080p** |
| Reference images | **up to 30** | up to 9 |
| Reference videos | **up to 10**, each ≤30s (≤30s total) | up to 3, each ≤15s (≤15s total) |
| Reference audio | **up to 10**, each ≤30s (≤30s total) | up to 3, each ≤15s (≤15s total) |
| Audio-only input | **yes** | no |
| Output container | **mp4 or mov** | mp4 |
| Video editing / extension | **first-class** (`seedance edit` / `extend`) | not supported |
| Prompt languages | + Spanish, Indonesian, Portuguese, Japanese, Malay, Thai, Arabic, Vietnamese, Korean | Chinese, English |
| Reference tags in prompts | `@Image1`, `@Video1`, `@Audio1` | `[image1]`, `[video1]`, `[audio1]` |

**Need 1080p?** Pass `model="2.0"` (MCP/SDK) or `--model 2.0` (CLI). Seedance 2.5 tops out at 720p —
generate at 720p and run `seedance upscale` for a 4K finish.

**Migrating from 2.0?** Two behaviours changed that can bite:

1. **Aspect ratio is locked for some task types.** On 2.5, first-frame, video-edit, and video-extend
   jobs take the ratio from the source image or video and accept only `ratio="adaptive"`. Passing
   `16:9` now raises a `ValidationError` before submission. Leave `ratio` unset (it defaults to
   `"auto"`, which resolves correctly per task type) and you never have to think about it.
2. **Duration is locked for video edits.** An edit keeps the source clip's length, so `duration`
   must be `-1`. `seedance edit` sets this for you.

If a job slips past local validation, the API rejects it *asynchronously* — the task fails minutes
later with `InvalidParameter.TaskTypeConstraint`. `seedance status` and `seedance_check_task` both
explain that error and point you at the right command.

---

## Choose your path

| I want to… | Use |
|---|---|
| Talk to Claude in natural language (Claude Desktop, Cursor, Windsurf) | [MCP Server](#-mcp-server) |
| Generate videos from the terminal | [CLI](#-cli) |
| Use slash commands inside Claude Code | [Claude Code Skill](#-claude-code-skill) |

All three share the same credentials and the same underlying pipeline — including automatic asset library handling for portrait images.

---

## Prerequisites

**Python 3.10+**, a local clone of this repo, and three keys from the [BytePlus console](https://console.byteplus.com):

| Key | Where | Used for |
|---|---|---|
| `ARK_API_KEY` | ModelArk → API Keys | Video generation |
| `ARK_AK` | IAM → Access Keys | Asset library + TOS uploads (portrait / sensitive images) |
| `ARK_SK` | IAM → Access Keys | Asset library + TOS uploads |
| `MEDIAKIT_API_KEY` | AI MediaKit → Settings → API Keys | Video upscaling *(optional)* |
| `SEEDANCE_TOS_BUCKET` | TOS console → Buckets | Default bucket for TOS uploads *(optional)* |
| `SEEDANCE_TOS_REGION` | — | TOS region, default `ap-southeast-1` *(optional)* |

---

## 🖥 MCP Server

Lets Claude Desktop, Cursor, and Windsurf generate videos from natural language — no code required.

### Setup

```bash
git clone https://github.com/mittulmadaan/byteplus-seedance-mcp
cd byteplus-seedance-mcp
pip install packages/seedance-sdk packages/seedance-mcp -e packages/seedance-cli
seedance auth login        # stores credentials in ~/.seedance/credentials
seedance skill install     # patches Claude Desktop + Claude Code configs automatically
# Restart your AI client
```

Then just ask Claude: *"Generate a 9:16 video of a woman smiling softly, camera slowly pushes in"*

### Manual config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or the equivalent on your OS:

```json
{
  "mcpServers": {
    "seedance": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "seedance_mcp"]
    }
  }
}
```

Set credentials via environment variables before launching your client.

### Hosted / Docker

> **Note:** The `byteplus/seedance-mcp` image will be available on Docker Hub after the first release. Until then, build it locally:
> ```bash
> docker build -f packages/seedance-mcp/docker/Dockerfile -t seedance-mcp .
> ```

```bash
docker run -p 8000:8000 \
  -e MCP_TRANSPORT=sse \
  -e ARK_API_KEY=<key> \
  -e ARK_AK=<ak> \
  -e ARK_SK=<sk> \
  -e MCP_AUTH_TOKEN=<strong-random-token> \
  byteplus/seedance-mcp
```

Your BytePlus credentials stay server-side. Clients connect using `MCP_AUTH_TOKEN` only.

Point your MCP client at `http://your-host:8000/mcp` (streamable HTTP transport). Use `Authorization: Bearer <MCP_AUTH_TOKEN>` if a token is set.

### How to use

Use `seedance_generate` for all generation tasks — it handles the full pipeline in one call:

```
# Text-to-video
seedance_generate(prompt="A sunrise over mountains, camera slowly pushes in", ratio="16:9", duration=5)
→ { task_id: "cgt-xxxx", status: "queued", mode: "T2V" }

# Image-to-video (portrait) — asset library upload is automatic
# Passing a raw HTTPS URL directly returns InputImageSensitiveContentDetected
seedance_generate(
  prompt="@Image1 smiles softly. Camera slowly pushes in. Soft studio light.",
  image_url="https://example.com/portrait.jpg",
  ratio="9:16",
  duration=6
)
→ {
    task_id: "cgt-xxxx",
    status: "queued",
    mode: "I2V-Reference",
    steps: [
      { step: "create_asset_group", group_id: "group-xxxx", outcome: "ok" },
      { step: "upload_asset",       asset_id: "asset-xxxx", outcome: "Active" },
      { step: "submit_job",         task_id:  "cgt-xxxx",   outcome: "queued" }
    ]
  }

# Then poll every 10–15s until done
seedance_check_task(task_id="cgt-xxxx")
→ { status: "succeeded", video_url: "https://...", duration: 6, ratio: "9:16",
    resolution: "720p", output_format: "mp4" }
```

To **change or continue an existing video**, use the two Seedance 2.5 task-type tools rather than
describing the operation through `seedance_generate` — they set the parameters those task types
lock, so a mistake surfaces immediately instead of failing the task minutes later:

```
# Editing — output keeps the source ratio AND duration
seedance_edit_video(
  prompt="Video edit: remove everyone in @Video1 except the protagonist.",
  video_urls=["https://example.com/scene.mov"]
)
→ { task_id: "cgt-xxxx", status: "queued", mode: "V2V-Edit(vid=1)" }

# Extending — output keeps the source ratio; duration is yours to set
seedance_extend_video(
  prompt="Extend @Video1 — the camera keeps pushing down the corridor.",
  video_urls=["https://example.com/corridor.mov"],
  duration=11
)
→ { task_id: "cgt-xxxx", status: "queued", mode: "V2V-Extend(vid=1)" }
```

Both default to `output_format="mov"`, which BytePlus recommends for edits and extensions: its
higher colour precision (H.264 + YUV444P + PCM) keeps audio and video in sync and survives further
grading or compositing. Pass `output_format="mp4"` when the file needs to play anywhere — mov needs
IINA, VLC, mpv, or ffplay.

To **upscale an existing video** (e.g. a generated output URL) use the standalone AI MediaKit
tool — it is independent of `seedance_generate` and needs `MEDIAKIT_API_KEY`:

```
byteplus_upscale_video(video_url="https://.../output.mp4", tool_version="standard", resolution="1080p")
→ { task_id: "amk-tool-enhance-video-xxxx", status: "submitted" }

# Poll every 10–15s; idempotent — identical params reuse the same task for 24h
byteplus_check_upscale_task(task_id="amk-tool-enhance-video-xxxx")
→ { status: "completed", video_url: "https://...", resolution: "1080p", fps: 60 }
```

> Never use `seedance_auto_generate` — it blocks for minutes and hits MCP timeout errors.

### Available tools

| Tool | Description |
|---|---|
| `seedance_generate` | **Start here.** Auto-uploads images + submits job. Returns `task_id`. |
| `seedance_check_task` | Poll for status and `video_url`. |
| `seedance_edit_video` | Edit an **existing** video — add/remove/replace elements *(Seedance 2.5)*. |
| `seedance_extend_video` | Continue an **existing** video forwards or backwards *(Seedance 2.5)*. |
| `seedance_text_to_video` | Fine-grained T2V — skips asset upload. |
| `seedance_image_to_video` | Fine-grained I2V with multiple refs — skips asset upload. |
| `byteplus_upscale_video` | Upscale/enhance an **existing** video (AI MediaKit, up to 4K). Needs `MEDIAKIT_API_KEY`. |
| `byteplus_check_upscale_task` | Poll an upscale task for status and enhanced `video_url`. |
| `seedance_list_tasks` | Browse generation history. |
| `seedance_cancel_task` | Cancel a queued or running job. |
| `seedance_create_asset_group` | Create an asset group (manual flow). |
| `seedance_upload_asset` | Upload image to asset library, poll until Active. |
| `seedance_get_asset` | Check asset status. |
| `seedance_list_tos_buckets` | List TOS buckets for your AK/SK (so Claude can ask which to use). |
| `seedance_upload_image_to_tos` | Upload a **local** image file to a TOS bucket; returns a public URL. |
| `seedance_list_models` | List models, resolutions, ratios, features. |
| `seedance_ping` | Verify credentials and connectivity. |

---

## 💻 CLI

Full-featured terminal interface with live progress output.

### Setup

```bash
git clone https://github.com/mittulmadaan/byteplus-seedance-mcp
cd byteplus-seedance-mcp
pip install packages/seedance-sdk packages/seedance-mcp -e packages/seedance-cli
seedance auth login
```

### Generate a video

```bash
# Text-to-video
seedance generate \
  --prompt "A silver espresso machine, morning light, steam rising, camera slowly pushes in." \
  --ratio 16:9 --duration 5 --watch

# Image-to-video — portrait auto-uploaded to asset library
seedance generate \
  --prompt "@Image1 smiles softly, camera slowly pushes in. Soft studio light." \
  --image "https://example.com/portrait.jpg" \
  --ratio 9:16 --duration 6 --watch

# Multi-reference — repeat --image (up to 30 on Seedance 2.5)
seedance generate \
  --prompt "@Image1 is the lead; @Image2 sets the wardrobe; camera follows @Video1." \
  --image "https://example.com/lead.jpg" \
  --image "https://example.com/wardrobe.jpg" \
  --video "https://example.com/camera-ref.mp4" \
  --duration 20 --watch
```

### Edit or extend an existing video *(Seedance 2.5)*

```bash
# Edit — output keeps the source ratio AND duration, so neither flag exists
seedance edit \
  --prompt "Video edit: remove everyone in @Video1 except the protagonist." \
  --video "https://example.com/scene.mov" --watch

# Extend — output keeps the source ratio; --duration is yours to set
seedance extend \
  --prompt "Extend @Video1 — the camera keeps pushing down the corridor." \
  --video "https://example.com/corridor.mov" --duration 11 --watch
```

Both default to `--output-format mov` for the best audio-video sync; pass `--output-format mp4`
when the file needs to play in any player.

`--watch` streams the full pipeline live:

```
  ✔  Created asset group   group-20260607-xxxx
  ✔  Asset uploaded        asset-20260607-xxxx
  ✔  Job submitted         cgt-20260607-xxxx   [mode=I2V-Reference]

  Watching cgt-20260607-xxxx (polling every 10s)…

  ✔  Video ready!  [120s]
     https://cdn.byteplus.com/...mp4
```

Without `--watch`, the command exits immediately with a `task_id` and you poll separately:

```bash
seedance status cgt-xxxx      # one-shot check
seedance watch  cgt-xxxx      # stream until done
```

### All flags

```bash
seedance generate \
  --prompt        "..."       # scene / motion description (required)
  --image         <url>       # reference image — repeatable, up to 30 on 2.5. Auto-uploaded for portraits
  --video         <url>       # reference video — repeatable, up to 10 on 2.5
  --audio-ref     <url>       # reference audio — repeatable, up to 10 on 2.5
  --first-frame   <url>       # pin the exact starting frame
  --last-frame    <url>       # pin the ending frame (requires --first-frame)
  --ratio         9:16        # 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive | auto (default)
  --duration      6           # seconds: 4–30 on 2.5, 4–15 on 2.0. Use --duration=-1 for model-chosen
  --resolution    720p        # 480p | 720p (2.0 also allows 1080p), default 720p
  --model         2.5         # 2.5 (default) | 2.0 | 2.0-fast — use 2.0 for 1080p
  --output-format mov         # mp4 (default) | mov — Seedance 2.5 only
  --audio                     # generate matching audio track
  --fast                      # faster/cheaper variant (always Seedance 2.0 Fast)
  --seed          42          # reproducible results
  --camerafixed               # no camera movement (product shots)
  --asset-group   <id>        # reuse existing asset group, skip group creation
  --watch                     # stream progress until done
```

> Use `--duration=-1`, not `-d -1` — a bare `-1` is parsed as a flag.

### Full command reference

```bash
# Auth
seedance auth login           # store credentials interactively
seedance auth check           # verify all three keys are configured
seedance auth logout          # remove stored credentials

# Generation
seedance generate --prompt "..." [--image <url>] [--watch]
seedance edit     --prompt "..." --video <url> [--watch]          # Seedance 2.5
seedance extend   --prompt "..." --video <url> [--duration 11]    # Seedance 2.5

# Tasks
seedance status  <task_id>    # check status once
seedance watch   <task_id>    # stream until done
seedance list    [--status succeeded|running|failed] [--model 2.5] [--limit 20]
seedance cancel  <task_id>

# Asset library (manual flow — auto flow is built into seedance generate)
seedance asset group create <name>
seedance asset upload <url> --group <group_id>
seedance asset status <asset_id>

# TOS object storage — upload a LOCAL file, get a public URL
seedance tos buckets                              # list buckets
seedance tos upload ./photo.png --bucket <name>   # upload, prints public URL
seedance tos upload ./photo.png --bucket <name> --key folder/photo.png

# Info
seedance models               # list models, resolutions, ratios
seedance ping                 # verify credentials and connectivity

# Skill management
seedance skill install        # install into Claude Desktop + Claude Code
seedance skill check          # show install status
seedance skill uninstall      # remove from all Claude clients
```

---

## 🧠 Claude Code Skill

Slash commands inside Claude Code, backed by the MCP server.

### Setup

```bash
git clone https://github.com/mittulmadaan/byteplus-seedance-mcp
cd byteplus-seedance-mcp
pip install packages/seedance-sdk packages/seedance-mcp -e packages/seedance-cli
seedance auth login
seedance skill install        # copies skill file + patches Claude Code settings
# Restart Claude Code
```

### Generate a video

```
/seedance:generate a silver espresso machine, morning light, camera slowly pushes in
```

```
/seedance:generate @Image1 smiles softly, camera slowly pushes in --image https://example.com/portrait.jpg --ratio 9:16
```

For portrait images, the asset library pipeline runs automatically — Claude creates the asset group, uploads the image, polls until Active, submits the job, and returns the video URL. All in one conversation turn. Passing a raw URL directly returns `InputImageSensitiveContentDetected`.

### Available commands

```
/seedance:generate <prompt> [--image <url>] [--ratio] [--duration] [--resolution] [--model] [--watch]
/seedance:edit     <prompt> --video <url>          # Seedance 2.5
/seedance:extend   <prompt> --video <url> [--duration]  # Seedance 2.5
/seedance:status   <task_id>
/seedance:watch    <task_id>
/seedance:list
```

---

## Asset Library

The asset library is required for portrait and sensitive images. Passing a plain HTTPS URL for a human face to any generation tool returns `InputImageSensitiveContentDetected`.

**All three surfaces handle this automatically** when you pass `image_url` / `--image` — no manual steps needed.

For power users who want to pre-upload and reuse assets across multiple generations:

```bash
# 1. Create a group once per project
seedance asset group create my-portraits
# → group_id: group-20260607-xxxx

# 2. Upload the image
seedance asset upload https://example.com/portrait.jpg --group group-20260607-xxxx
# → asset_ref: asset://asset-20260607-xxxx

# 3. Pass the asset ref directly on future generations (no re-upload)
seedance generate --image "asset://asset-20260607-xxxx" --prompt "@Image1 ..." --watch

# Or in MCP:
seedance_generate(image_url="asset://asset-20260607-xxxx", prompt="@Image1 ...", asset_group_id="group-20260607-xxxx")
```

---

## SDK

For building custom integrations:

```python
from seedance import SeedanceClient

client = SeedanceClient()  # reads from env vars or ~/.seedance/credentials

# Submit (auto-handles asset upload for portrait images)
result = client.generate(
    prompt="@Image1 smiles softly, camera slowly pushes in",
    image_url="https://example.com/portrait.jpg",
    ratio="9:16",
    duration=6,
    on_progress=lambda step, detail: print(f"  {step}: {detail}"),
)

# Poll until done
import time
while True:
    status = client.check_task(result.task_id)
    if status.succeeded:
        print(status.video_url)
        break
    if status.terminal:
        print("Failed:", status.error)
        break
    time.sleep(10)
```

Seedance 2.5 task types and model selection:

```python
# Video editing — ratio and duration are locked to the source clip
result = client.submit_video_edit(
    "Video edit: remove everyone in @Video1 except the protagonist.",
    video_urls=["https://example.com/scene.mov"],
)

# Video extension — ratio is locked; duration is not
result = client.submit_video_extend(
    "Extend @Video1 — the camera keeps pushing down the corridor.",
    video_urls=["https://example.com/corridor.mov"],
    duration=11,
)

# Audio-only input (Seedance 2.5 exclusive)
result = client.submit_image_to_video(
    "A dancer moves to the rhythm of @Audio1, neon warehouse, handheld.",
    audio_urls=["https://example.com/track.mp3"],
    duration=20,
)

# Fall back to Seedance 2.0 when you need 1080p
result = client.submit_text_to_video(
    "A silver espresso machine, morning light.",
    model="2.0", resolution="1080p",
)
```

Constraint violations raise `ValidationError` before the request leaves your process. If one slips
through, the API returns `InvalidParameter.TaskTypeConstraint` — surfaced as `TaskTypeConstraintError`
when synchronous, and as `result.task_type_constraint_error` on a failed task when asynchronous:

```python
from seedance import TaskTypeConstraintError
```

Install: `pip install packages/seedance-sdk` (from repo root; zero runtime dependencies — uses stdlib urllib only).

---

## Repo Structure

```
packages/
  seedance-sdk/          # core: HTTP client, HMAC signing, config, types (zero deps)
  seedance-mcp/          # MCP server — thin wrappers over SDK
    docker/              # Dockerfile + docker-compose
  seedance-cli/          # CLI — typer + rich
    seedance_cli/commands/
      auth.py generate.py edit.py tasks.py assets.py models.py skill.py

skills/
  seedance.md            # Claude Code skill definition

.github/workflows/
  ci.yml                 # lint + test (Python 3.10 / 3.11 / 3.12)
  release-sdk.yml        # → PyPI on tag sdk/v*
  release-mcp.yml        # → PyPI + Docker Hub on tag mcp/v*
  release-cli.yml        # → PyPI on tag cli/v*
```

---

## Credentials

Resolution order (first non-empty value wins):

1. Constructor args: `SeedanceClient(api_key="...", ak="...", sk="...")`
2. Environment variables: `ARK_API_KEY`, `ARK_AK`, `ARK_SK`
3. `~/.seedance/credentials` — written by `seedance auth login`
4. `.env` file in CWD (requires `python-dotenv`)
5. `ark_api_key.txt` next to the module (legacy)

> Never embed credentials in client config files or Docker images. Use `MCP_AUTH_TOKEN` to protect hosted SSE endpoints.

---

## Release

```bash
git tag sdk/v2.0.1 && git push --tags   # publishes seedance-sdk to PyPI
git tag mcp/v2.0.1 && git push --tags   # publishes seedance-mcp to PyPI + Docker Hub
git tag cli/v2.0.1 && git push --tags   # publishes seedance-cli to PyPI
```

---

## Support

- [BytePlus ModelArk docs](https://docs.byteplus.com/en/docs/ModelArk/2291680)
- [API key management](https://docs.byteplus.com/en/docs/ModelArk/1361424)
- [Asset library API](https://docs.byteplus.com/en/docs/ModelArk/2318270)
