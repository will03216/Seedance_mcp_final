---
name: seedance
description: Generate videos with BytePlus Seedance 2.0 — text-to-video, image-to-video, asset management, and task tracking.
version: 2.0.0
---

# Seedance Video Generation

Use this skill to generate AI videos with BytePlus Seedance 2.0 directly from Claude Code.

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

## /seedance:generate

Generate a video from a text prompt or image reference.

**Text-to-video:**
```
/seedance:generate a silver espresso machine on a modern kitchen counter,
morning light cuts in, steam rises slowly, camera slowly pushes in
```

**Image-to-video (portrait / reference image):**
```
/seedance:generate [image1] smiles softly, camera slowly pushes in --image https://example.com/portrait.jpg
```

**Full options:**
```
/seedance:generate <prompt>
  --image <url>          Reference image (auto-uploaded to asset library for portraits)
  --first-frame <url>    Pin the exact starting frame
  --last-frame <url>     Pin the ending frame (requires --first-frame)
  --ratio 9:16           Aspect ratio: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
  --duration 6           Length in seconds (4–15)
  --resolution 1080p     Quality: 480p | 720p | 1080p
  --audio                Generate matching audio track
  --fast                 Use faster/cheaper model variant
  --seed 42              Reproducible results
  --camerafixed          No camera movement (product shots)
  --watch                Auto-poll until video is ready (streams progress)
```

The MCP tool `seedance_generate` handles everything automatically:
1. Creates an asset group and uploads any plain HTTPS image to the BytePlus asset library
2. Submits the generation job
3. Returns `task_id` — poll `seedance_check_task` every 10–15 seconds until `status == "succeeded"`

---

## /seedance:status

Check the current status of a submitted job.

```
/seedance:status <task_id>
```

Returns `status` (queued | running | succeeded | failed | cancelled) and `video_url` when done.

---

## /seedance:watch

Stream live progress for a task until the video is ready.

```
/seedance:watch <task_id>
```

Polls every 10 seconds and prints the `video_url` on completion.

---

## /seedance:list

List recent generation tasks.

```
/seedance:list
/seedance:list --status succeeded
/seedance:list --limit 20
```

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

---

## MCP tools reference

| Tool | Description |
|---|---|
| `seedance_generate` | Full pipeline: upload + submit + return task_id (preferred) |
| `seedance_check_task` | Poll status, get video_url when succeeded |
| `seedance_text_to_video` | Fine-grained T2V — returns task_id |
| `seedance_image_to_video` | Fine-grained I2V with multiple refs — returns task_id |
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

**`ARK_API_KEY not configured`** — Run `seedance auth login` or export `ARK_API_KEY`.

**MCP timeout** — Never use `seedance_auto_generate` (it blocks). Always use the two-step pattern: submit → poll `seedance_check_task`.

**Reinstall after update:**
```bash
pip install --upgrade "seedance-cli[mcp]"
seedance skill install
```
