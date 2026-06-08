# Seedance 2.0

Generate AI videos with **BytePlus Seedance 2.0** — from your terminal, your AI client, or Claude Code.

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
| `ARK_AK` | IAM → Access Keys | Asset library (portrait / sensitive images) |
| `ARK_SK` | IAM → Access Keys | Asset library |

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
  prompt="[image1] smiles softly. Camera slowly pushes in. Soft studio light.",
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
→ { status: "succeeded", video_url: "https://..." }
```

> Never use `seedance_auto_generate` — it blocks for minutes and hits MCP timeout errors.

### Available tools

| Tool | Description |
|---|---|
| `seedance_generate` | **Start here.** Auto-uploads images + submits job. Returns `task_id`. |
| `seedance_check_task` | Poll for status and `video_url`. |
| `seedance_text_to_video` | Fine-grained T2V — skips asset upload. |
| `seedance_image_to_video` | Fine-grained I2V with multiple refs — skips asset upload. |
| `seedance_list_tasks` | Browse generation history. |
| `seedance_cancel_task` | Cancel a queued or running job. |
| `seedance_create_asset_group` | Create an asset group (manual flow). |
| `seedance_upload_asset` | Upload image to asset library, poll until Active. |
| `seedance_get_asset` | Check asset status. |
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
  --prompt "[image1] smiles softly, camera slowly pushes in. Soft studio light." \
  --image "https://example.com/portrait.jpg" \
  --ratio 9:16 --duration 6 --watch
```

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
  --prompt      "..."         # scene / motion description (required)
  --image       <url>         # reference image — auto-uploaded to asset library for portraits
  --first-frame <url>         # pin the exact starting frame
  --last-frame  <url>         # pin the ending frame (requires --first-frame)
  --ratio       9:16          # 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
  --duration    6             # seconds (4–15), default 5
  --resolution  1080p         # 480p | 720p | 1080p, default 720p
  --audio                     # generate matching audio track
  --fast                      # faster/cheaper model variant
  --seed        42            # reproducible results
  --camerafixed               # no camera movement (product shots)
  --asset-group <id>          # reuse existing asset group, skip group creation
  --watch                     # stream progress until done
```

### Full command reference

```bash
# Auth
seedance auth login           # store credentials interactively
seedance auth check           # verify all three keys are configured
seedance auth logout          # remove stored credentials

# Tasks
seedance status  <task_id>    # check status once
seedance watch   <task_id>    # stream until done
seedance list    [--status succeeded|running|failed] [--limit 20]
seedance cancel  <task_id>

# Asset library (manual flow — auto flow is built into seedance generate)
seedance asset group create <name>
seedance asset upload <url> --group <group_id>
seedance asset status <asset_id>

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
/seedance:generate [image1] smiles softly, camera slowly pushes in --image https://example.com/portrait.jpg --ratio 9:16
```

For portrait images, the asset library pipeline runs automatically — Claude creates the asset group, uploads the image, polls until Active, submits the job, and returns the video URL. All in one conversation turn. Passing a raw URL directly returns `InputImageSensitiveContentDetected`.

### Available commands

```
/seedance:generate <prompt> [--image <url>] [--ratio] [--duration] [--resolution] [--watch]
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
seedance generate --image "asset://asset-20260607-xxxx" --prompt "[image1] ..." --watch

# Or in MCP:
seedance_generate(image_url="asset://asset-20260607-xxxx", prompt="[image1] ...", asset_group_id="group-20260607-xxxx")
```

---

## SDK

For building custom integrations:

```python
from seedance import SeedanceClient

client = SeedanceClient()  # reads from env vars or ~/.seedance/credentials

# Submit (auto-handles asset upload for portrait images)
result = client.generate(
    prompt="[image1] smiles softly, camera slowly pushes in",
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
      auth.py generate.py tasks.py assets.py models.py skill.py

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
