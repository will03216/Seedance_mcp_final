# Platform

Operational notes for submitting Seedance jobs through this repo's MCP/CLI layer.
Seedance 2.5 is the default model; Seedance 2.0 is available via `model="2.0"` /
`--model 2.0`.

## Submission via MCP or CLI

All video generation goes through the `seedance_generate` MCP tool (preferred)
or the fine-grained `seedance_text_to_video` / `seedance_image_to_video` tools.
The equivalent CLI command is `seedance generate` / `/seedance:generate`.

Two Seedance 2.5 task types have dedicated tools because they lock parameters
the generic path cannot validate: `seedance_edit_video` / `seedance edit`
(changes what is in a clip) and `seedance_extend_video` / `seedance extend`
(continues a clip). Use them rather than routing an edit through
`seedance_generate` — see the task-type table below.

The MCP server:
1. Auto-uploads any portrait references to the asset library
2. Submits the generation job async via `POST /contents/generations/tasks`
3. Returns `task_id` — poll `seedance_check_task` every 10–15 seconds

For status checks, call `seedance_check_task(task_id)` on demand. No cron, no background polling.

## Working assumptions

- Short clips are safer than long clips; default 5s, ceiling 30s on Seedance 2.5 (15s on 2.0). A raised ceiling is not a target — see [`duration-calculus.md`](duration-calculus.md).
- Common ratios: `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `adaptive`. The SDK/CLI/MCP default is `auto`, which resolves per task type.
- Image references are usually easier to control than text-only generations.
- Shorter prompts generally fail less often than verbose ones.
- Resolution: `"480p"`, `"720p"` on Seedance 2.5; 2.0 also offers `"1080p"`. **Default is `"720p"`** — never silently fall back to 480p. For a higher-resolution master, generate 720p and finish with `byteplus_upscale_video`.
- Output container: `mp4` (default) or `mov` on Seedance 2.5. mov carries higher colour precision (H.264 + YUV444P + PCM) for grading and compositing, and is recommended for edit/extend tasks; it plays only in IINA, VLC, mpv, and ffplay. Seedance 2.0 is mp4-only.
- Prompt languages: Seedance 2.5 adds Spanish, Indonesian, Portuguese, Japanese, Malay, Thai, Arabic, Vietnamese, and Korean to Chinese and English.

## Task types and what they lock

Seedance 2.5 classifies each request into a task type — from `content[].role`
for first-frame jobs, and from **the prompt** for everything else — then applies
that type's parameter rules. Violations of a prompt-inferred rule can only be
reported *after* the task is consumed, so they arrive asynchronously as a failed
task carrying `InvalidParameter.TaskTypeConstraint`.

| Task type | Triggered by | Ratio | Duration |
|---|---|---|---|
| Text-to-video | no references | any | 4–30 or -1 |
| Reference-to-video | images / videos / audio, no edit or extend intent | any | 4–30 or -1 |
| First frame (+ last frame) | `first_frame_url` | **`adaptive` only** | 4–30 or -1 |
| Video edit | prompt intent: add, remove, replace, change | **`adaptive` only** | **-1 only** |
| Video extend | prompt intent: extend, continue, forward/backward | **`adaptive` only** | 4–30 or -1 |

The SDK validates these locally before submitting and raises `ValidationError`
with the offending parameter named. Using `seedance edit` / `seedance extend`
(or their MCP equivalents) sets the locked values for you, which is why they
are preferred over describing the operation through `seedance_generate`.

### The prompt-intent guard

First-frame is decided from a *parameter* (`content.role`), so it can always be
checked up front. Editing and extension are decided from the *prompt*, which the
API only reads after the task is queued — so those clashes come back minutes
later on a failed task.

To close that gap, the SDK scans the prompt for the documented trigger words
whenever reference videos are present and no task type was declared:

| Intent | Trigger words (docs give these as "such as" — not exhaustive) |
|---|---|
| Edit | edit the video, add, delete/remove, modify/replace/change |
| Extend | extend forward/backward, continue, continue the story |

The check is **advisory**: it raises only when the parameters you passed would
actually violate the detected task type's constraints. An edit-worded prompt with
`ratio="adaptive"` and `duration=-1` already satisfies them and goes through
untouched, so a false positive costs nothing. The error names both ways out —
switch to the dedicated command, or reword the prompt if you really meant a plain
reference-to-video generation.

That second option matters: the docs warn that edit/extend wording in a
reference-to-video prompt can make the model misclassify the task. If you want a
plain generation, keep those verbs out of the prompt.

The dedicated commands run the check in reverse. `seedance edit` with a prompt
containing no edit trigger word emits a warning, because Seedance will classify
it as a plain generation and return a **brand-new clip instead of an edited one** —
a silent wrong result rather than an error.

## Asset budget habits

Keep the request simple:

- one hero subject
- only the references needed for this clip
- one camera move
- one primary style anchor

### Reference limits vs. reference *strategy*

The hard ceiling on Seedance 2.5 is **30 images, 10 videos, 10 audio** (50 items
total; each video or audio clip 2–30s, and ≤30s in total per media type). On
Seedance 2.0 it is 9 images, 3 videos, 3 audio at ≤15s.

**The ceiling rose; the advice did not.** Too many references still dilute
priority and the model still struggles to decide what matters — 2.5 simply
fails less catastrophically when you overload it. A reliable short-drama config
remains **4–5 assets total**, one per function. Reach past that only when each
additional reference has a distinct, nameable job (the multi-video advertising
pattern in [`examples.md`](examples.md) is the case that genuinely earns it):

| Functional role | Asset | Binds via |
|-----------------|-------|-----------|
| Character anchor | 1–2 portrait images (face / full body) | `reference_image` → `@Image1`/`@Image2` |
| Scene / style | 1 scene image | `reference_image` → `@Image2`/`@Image3` |
| Camera & rhythm | 1 reference video | `reference_video` → `@Video1` |
| Pacing / mood | 1 audio clip | `reference_audio` → `@Audio1` |

Seedance 2.5 also accepts **audio-only input** — a track with no image or video
reference at all, driving rhythm, pacing, and cuts. Seedance 2.0 requires a
visual reference alongside any audio.

When a video is used only for camera/motion, say so explicitly (`use @Video1
for camera and timing only — do not copy its characters or scene`), or the
model may import its subjects.

---

## API key requirement

The underlying API uses `Authorization: Bearer <ARK_API_KEY>`. The MCP server
resolves the key in this order:

1. `ARK_API_KEY` environment variable (preferred)
2. `~/.seedance/credentials` (set via `seedance auth login`)

If none is present, `seedance_ping` will return an auth error.

### How to obtain a key

Share these steps with the user when no key is configured:

1. Sign in / register at <https://console.byteplus.com>.
2. Navigate to **ModelArk → API Keys** (docs: <https://docs.byteplus.com/en/docs/ModelArk/1361424>).
3. Click **Create Key**, copy the value (shown only once).
4. Optional: purchase a Seedance 2.0 resource pack on the same page — required before tasks can run.
5. Run `seedance auth login` and paste the key when prompted, or:
   - export it: `export ARK_API_KEY="..."`

Minimum guidance to give the user (Chinese):

```text
请到 BytePlus 控制台获取 ModelArk API Key：
1. 打开 https://console.byteplus.com 登录
2. 进入 ModelArk → API Keys → Create Key，复制 key（只显示一次）
3. 在 ModelArk 计费页面购买 Seedance 2.0 资源包（必需）
4. 运行 seedance auth login 粘贴 key，或设置环境变量 export ARK_API_KEY="..."
```

---

## Endpoints (handled by MCP server)

| Method | URL | Used by |
|--------|-----|---------|
| `POST` | `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` | `seedance_generate` / `seedance_text_to_video` / `seedance_image_to_video` |
| `GET`  | `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{id}` | `seedance_check_task` |
| `GET`  | `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks` | `seedance_list_tasks` |
| `DELETE` | `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{id}` | `seedance_cancel_task` |

Reference docs:
- Seedance model overview: <https://docs.byteplus.com/en/docs/ModelArk/2291680>
- Create task API: <https://docs.byteplus.com/en/docs/ModelArk/1520757>
- Retrieve task API: <https://docs.byteplus.com/en/docs/ModelArk/1521309>

---

## Reference assets

The API consumes URLs, not raw bytes. Three accepted forms:

- HTTP / HTTPS URL (publicly fetchable by ModelArk) — for **non-portrait** references
- `data:image/...;base64,...` — for **non-portrait** references (small files)
- **`asset://<asset_id>` — REQUIRED for any real or virtual human portrait reference**

`seedance_generate` auto-uploads every plain-HTTPS `--image` reference to the asset library (no portrait detection — it uploads all non-`asset://` URLs unconditionally, so portraits are always covered). For manual asset management, see [`assets.md`](assets.md).

---

## Suggested downstream pipeline

1. generate a short proof clip with `--fast` flag
2. iterate until motion and identity are correct
3. switch to default model for final quality output
4. composite exact audio, graphics, or subtitles in post if needed

## Operational warning

Do not treat repository notes about policy or platform behavior as live guarantees. If the user asks for the latest supported limits, model IDs, or pricing, verify against current official sources before answering.
