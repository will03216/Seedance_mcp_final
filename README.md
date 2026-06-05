# Seedance 2.0 MCP Server

MCP server for **BytePlus Seedance 2.0** — lets any MCP-compatible AI client (Claude Desktop, Cursor, Windsurf) generate videos from natural language. No API integration required.

---

## Setup

**Requirements:** Python 3.10+, BytePlus ModelArk API key, active prepaid resource pack, IAM Access Key + Secret Key.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set credentials in your shell (never in client config files):

```bash
export ARK_API_KEY="your-modelark-api-key"
export ARK_AK="your-iam-access-key"
export ARK_SK="your-iam-secret-key"
```

Add to Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "seedance": {
      "command": "/absolute/path/to/repo/.venv/bin/python",
      "args": ["-m", "seedance_mcp"]
    }
  }
}
```

Restart Claude Desktop — hammer icon confirms it's live.

---

## Asset Library Integration

The asset library is required for **portrait and sensitive images**. Passing a plain URL for a human face returns `InputImageSensitiveContentDetected`. The asset library pre-registers the image with BytePlus before generation.

### Automatic flow — `seedance_generate` (recommended)

Pass any image URL directly. The tool handles the full pipeline in one call:

1. Creates an asset group
2. Uploads the image and waits until Active
3. Submits the generation job
4. Returns `task_id` immediately

```
seedance_generate(
  prompt="[image1] The woman smiles softly. Camera slowly pushes in. Soft studio light.",
  image_url="https://example.com/portrait.jpg",
  ratio="9:16",
  duration=6
)
→ { task_id: "cgt-xxxx", status: "queued", asset_id: "asset-xxxx", steps: [...] }
```

Then poll until done:

```
seedance_check_task(task_id="cgt-xxxx")   # every 10–15s
→ { status: "succeeded", video_url: "https://..." }
```

### Manual flow — full control

Use this when you need to reuse an uploaded asset across multiple generations:

```
1. seedance_create_asset_group(name="my-project")  →  group_id
2. seedance_upload_asset(image_url="...", group_id) →  asset_ref  (e.g. "asset://asset-xxxx")
3. seedance_image_to_video(image_urls=[asset_ref], prompt="...")  →  task_id
4. seedance_check_task(task_id)  →  video_url
```

Pass `asset_group_id` to `seedance_generate` on repeat runs to skip group creation.

---

## Tools

| Tool | Description |
|------|-------------|
| `seedance_generate` | Full pipeline — upload + submit + return `task_id` |
| `seedance_check_task` | Poll for status and `video_url` |
| `seedance_image_to_video` | Fine-grained I2V — reference, first frame, last frame |
| `seedance_text_to_video` | Text-only generation |
| `seedance_create_asset_group` | Create an asset group (one-time per project) |
| `seedance_upload_asset` | Upload image to asset library, returns `asset_ref` |
| `seedance_get_asset` | Check asset status |
| `seedance_cancel_task` | Cancel a queued or running job |
| `seedance_list_tasks` | Browse generation history |
| `seedance_ping` | Verify server and credentials |

---

## Security

> **`ARK_API_KEY`, `ARK_AK`, and `ARK_SK` are billing credentials. Never share them with customers or embed them in client config.**

For customer-facing deployments, run the server as an HTTP service and protect it with a gateway token — the same pattern used by Magnific's hosted MCP endpoint:

```bash
# copy .env.example → .env and fill in your credentials, then:
docker compose -f docker/docker-compose.yml up
```

Or with plain Docker:

```bash
docker build -f docker/Dockerfile -t seedance-mcp .
docker run -p 8000:8000 \
  -e MCP_TRANSPORT=sse \
  -e ARK_API_KEY=<your-key> \
  -e ARK_AK=<your-ak> \
  -e ARK_SK=<your-sk> \
  -e MCP_AUTH_TOKEN=<strong-random-token> \
  seedance-mcp
```

Customers connect with `MCP_AUTH_TOKEN` — your BytePlus credentials stay server-side. Issue per-user tokens from your own identity system (OAuth 2.0 / SSO), store credentials in a secret manager, and serve over HTTPS only.

---

## Support

- [BytePlus ModelArk docs](https://docs.byteplus.com/en/docs/ModelArk/2291680)
- [API key management](https://docs.byteplus.com/en/docs/ModelArk/1361424)
