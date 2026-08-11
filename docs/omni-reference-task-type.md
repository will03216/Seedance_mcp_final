# `omni_reference_task_type` — curl reference

`omni_reference_task_type` tells Seedance 2.5 which **omni-reference subtask** you intend, so the
API can validate that subtask's parameter constraints **when you submit** instead of after the
task has queued and been consumed.

Every request below was run against the live API. Task IDs and outcomes are the real ones.

| Value | Constraints the API enforces | Validation timing |
|---|---|---|
| `auto` *(default)* | none up front — the model infers from assets + prompt | **asynchronous**: task queues, is consumed, then fails |
| `reference` | none on `ratio` / `duration` | synchronous |
| `edit` | ≥1 `reference_video` (several allowed — the model picks the target), source 4–30s, `ratio=adaptive`, `duration=-1` | synchronous |
| `extend` | ≥1 `reference_video`, `ratio=adaptive` | synchronous |

Applies to **Seedance 2.5 only**, and only to omni-reference requests — those whose `content[]`
carries `reference_image`, `reference_video`, or `reference_audio` roles. It does **not** apply to
first-frame tasks (classified by `content.role`, a different task family) or to text-to-video.

Set up once:

```bash
export ARK_API_KEY=<your key>
export ARK_URL=https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
export DOC=https://ark-project.tos-cn-beijing.volces.com
```

---

## 1. `auto` — the default

Omitting the parameter is identical to `auto`. The model classifies from the prompt **after**
queuing, so a parameter clash is only reported once the task has been consumed.

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "A dancer moves through a neon-lit warehouse; camera rhythm follows @Video1." },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/seedacne2.5_reference2.mp4" },
        "role": "reference_video" }
    ],
    "ratio": "adaptive",
    "duration": 8,
    "resolution": "720p",
    "generate_audio": false,
    "watermark": false
  }'
```

> With `auto`, use `ratio: "adaptive"` when reference videos are present. It is the only value
> legal under all three subtasks, so it cannot clash with whatever the model decides. Sending a
> concrete ratio here is what produces the asynchronous failure shown at the end of this document.
>
> The tutorial also says `duration` "must be `-1`" under `auto`. That is **advisory, not enforced**:
> verified live, `auto` with `duration: 8` was accepted and succeeded (`cgt-20260812020652-f4mzd`,
> 8s · `16:9`). The rule is a safe recipe — `-1` cannot clash with any subtask — but a concrete
> duration is fine as long as the model classifies the request as `reference`, where duration is
> free. It only bites if the prompt reads as an edit.

**Verified** — task `cgt-20260812020652-f4mzd` → `succeeded`, 8s · `16:9` · 720p · mp4.

---

## 2. `reference` — generate a new video from references

No constraints on `ratio` or `duration`, so a concrete aspect ratio is fine.

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "@Image1 sets the palette; camera rhythm follows @Video1. Bright, premium, rhythmic." },
      { "type": "image_url",
        "image_url": { "url": "'"$DOC"'/doc_image/seedacne2.5_reference1.png" },
        "role": "reference_image" },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/seedacne2.5_reference2.mp4" },
        "role": "reference_video" }
    ],
    "omni_reference_task_type": "reference",
    "ratio": "16:9",
    "duration": 8,
    "resolution": "720p",
    "generate_audio": false,
    "watermark": false
  }'
```

**Verified** — task `cgt-20260812003021-frrv2` → `succeeded`, 8s · `16:9` · 720p · mp4.

### Audio-only variant

Seedance 2.5 accepts audio as the sole reference — no image, no video.

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "A dancer moves to the rhythm of @Audio1. Neon warehouse, handheld, cuts on the downbeats." },
      { "type": "audio_url",
        "audio_url": { "url": "https://download.samplelib.com/mp3/sample-15s.mp3" },
        "role": "reference_audio" }
    ],
    "omni_reference_task_type": "reference",
    "ratio": "16:9",
    "duration": 15,
    "resolution": "720p",
    "generate_audio": false,
    "watermark": false
  }'
```

**Verified** — task `cgt-20260812003147-5pztf` → `succeeded`, 15s · `16:9` · 720p · mp4.

---

## 3. `edit` — change what is in an existing video

`ratio` must be `adaptive` and `duration` must be `-1`; both are inherited from the source clip.
The prompt must state the operation ("remove", "add", "replace", "change"), or the model treats
the request as a plain generation.

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "Video edit: remove all the people in the background of @Video1." },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/seedance2.5_edit_input.mov" },
        "role": "reference_video" }
    ],
    "omni_reference_task_type": "edit",
    "ratio": "adaptive",
    "duration": -1,
    "resolution": "720p",
    "generate_audio": true,
    "watermark": false,
    "output_format": "mov"
  }'
```

**Verified** — task `cgt-20260812003101-5rgjw` → `succeeded`, **16s · `269:215`** · 720p · mov.

Both values came from the source, not from the request. `269:215` is the source clip's exact
aspect ratio — note it is **not** one of the seven values the request accepts, so a response
`ratio` must never be fed back into a later request.

### Several source videos

An edit may carry more than one reference video. The model edits **one** of them — the one your
prompt names — so tag the target explicitly.

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "Video edit: remove the people in the background of @Video1." },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/r2v_extend_video1_75.mov" },
        "role": "reference_video" },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/seedacne2.5_reference2.mp4" },
        "role": "reference_video" }
    ],
    "omni_reference_task_type": "edit",
    "ratio": "adaptive",
    "duration": -1,
    "resolution": "720p",
    "generate_audio": false,
    "watermark": false
  }'
```

**Verified** — task `cgt-20260812020825-clk9t` → `succeeded`, 5s · `269:215` · 720p. The
source-derived ratio confirms it edited the selected clip rather than generating something new.

---

## 4. `extend` — continue an existing video

`ratio` must be `adaptive`. Unlike `edit`, `duration` **is** settable (4–30, or `-1`).

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text",
        "text": "Extend @Video1 forward; the camera keeps moving in the same direction." },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/r2v_extend_video1_75.mov" },
        "role": "reference_video" }
    ],
    "omni_reference_task_type": "extend",
    "ratio": "adaptive",
    "duration": 8,
    "resolution": "720p",
    "generate_audio": false,
    "watermark": false,
    "output_format": "mov"
  }'
```

**Verified** — task `cgt-20260812003814-rv7nb` → `succeeded`, 8s · `269:215` · 720p · mov.

> `generate_audio` is `false` here deliberately. An earlier run with it enabled failed on
> `OutputAudioSensitiveContentDetected.PolicyViolation` — the source clip has audio, and the
> generated track tripped a copyright filter. If you need audio on an extension, expect that.

---

## Poll any of the above

```bash
curl -H "Authorization: Bearer $ARK_API_KEY" \
  "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/<task_id>"
```

---

## Rejected at submit — the reason to declare a task type

Each of these returns **HTTP 400 immediately**, with no task ID and no task created. Under `auto`
the equivalent request queues, consumes a slot, and fails minutes later.

### `edit` with a concrete ratio and duration

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text", "text": "Video edit: remove the people in the background of @Video1." },
      { "type": "video_url",
        "video_url": { "url": "'"$DOC"'/doc_video/seedance2.5_edit_input.mov" },
        "role": "reference_video" }
    ],
    "omni_reference_task_type": "edit",
    "ratio": "16:9",
    "duration": 5,
    "resolution": "720p",
    "watermark": false
  }'
```

```
HTTP 400 — The parameter duration specified in the request is not valid. You specified the
task type video editing. For this task type, the output ratio and duration follow the input
video selected by the model for editing.
```

### `extend` with a concrete ratio

Same shape, `"omni_reference_task_type": "extend"` with `"ratio": "9:16"`:

```
HTTP 400 — The parameter ratio specified in the request is not valid. You specified the task
type video extension. For this task type, the output ratio follows the input video selected
by the model for extension.
```

### `edit` with no reference video

`content[]` carrying only a `reference_image`:

```
HTTP 400 — The parameter content specified in the request is not valid. You specified the
task type video editing. For this task type, the request must include exactly one reference
video to be edited.
```

> The phrase "**exactly one**" describes the *semantic*, not a cap on the array: the model edits
> one video, which it **selects from the inputs**. Verified live — a declared edit carrying two
> reference videos was accepted and succeeded (`cgt-20260812020825-clk9t`, 5s · `269:215`). Zero
> videos is what fails. Name the target in the prompt (`@Video1`) so the model picks the one you
> mean.

### An invalid value

`"omni_reference_task_type": "remix"`:

```
HTTP 400 — The parameter `omni_reference_task_type` specified in the request is not valid:
invalid value `remix`, allowed values: auto, reference, edit, extend
```

---

## The contrast this parameter exists to remove

The same clashing request, submitted **without** a declared task type
(`omni_reference_task_type` omitted → `auto`):

```bash
curl -X POST "$ARK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-5-260628",
    "content": [
      { "type": "text", "text": "Remove the compass from @Video1 and leave only the map." },
      { "type": "video_url", "video_url": { "url": "https://example.com/source.mp4" },
        "role": "reference_video" }
    ],
    "ratio": "16:9",
    "duration": 5,
    "resolution": "720p",
    "watermark": false
  }'
```

This is **accepted**:

```json
{ "id": "cgt-20260807155131-4787d", "status": "queued" }
```

and then fails minutes later, after consuming a billed slot:

```json
{
  "status": "failed",
  "error": {
    "code": "InvalidParameter.TaskTypeConstraint",
    "message": "The parameters `ratio` and `duration` specified in the request are not valid.
      Seedance identified your task as video editing based on your prompt. ...
      Issues: [0] `ratio` must be `adaptive`. [1] `duration` must be -1."
  }
}
```

Declaring the task type converts that into the HTTP 400 shown above.

---

## Caveats found while verifying

**A declaration does not exempt you from writing the right prompt.** The tutorial states that
while processing, "the model still further determines the task type based on the prompt. If the
actual task type identified by the model does not match the specified value, the task still
triggers an asynchronous error."

One attempt to provoke that did not error: an `edit` declaration paired with a plain-generation
prompt ("A calm wide shot of a mountain lake at sunrise") was accepted and generated a video
(`cgt-20260812005402-v42bp`, 5s · `269:215`). That is **not** evidence the check is absent — the
model may simply have agreed the request was an edit, since redrawing a whole frame is one. The
two outcomes are indistinguishable from the outside.

Treat the documented behaviour as authoritative: declare the task type **and** write a prompt
that matches it. The declaration moves parameter validation earlier; it does not override the
model's reading of your prompt.

**Reference URLs must be promptly fetchable.** Several submissions failed with
`content[N].video_url ... timeout while fetching resource` on an asset that succeeded moments
earlier. This is a fetch-time failure at submit, unrelated to the task type.

**Content filters are independent of all of this.** Runs in this series failed on
`OutputVideoSensitiveContentDetected` and `OutputAudioSensitiveContentDetected` for innocuous
material. Those are output-side policy checks, not parameter problems.
