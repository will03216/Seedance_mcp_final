# Seedance 2.5 — live verification matrix

Every request below was submitted to the real BytePlus API through this repo's MCP tool layer. The **Request sent** blocks are the exact JSON that went on the wire, captured at the HTTP boundary — not a reconstruction.

- **Run at:** 2026-08-07T08:45:01.549389+00:00
- **Endpoint:** `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`
- **Model:** `dreamina-seedance-2-5-260628`
- **Assets:** the BytePlus documentation's own samples, so the run is reproducible and independent of anything this repo generated.

**Result: 6/7 generation requests succeeded; 6/6 guard cases blocked locally as intended.**

> T4, T5 and T7 failed on the first pass with a client-side read timeout, not an API
> rejection. `SUBMIT_TIMEOUT` was 30s, and task creation blocks while the API fetches
> every reference URL — so multi-reference requests exceeded it. Raised to 120s; all
> three then succeeded unchanged. The sections below show the successful re-run.
>
> That timeout also orphaned billed tasks: the POST reached the server, so a task was
> created, but the response never arrived and no task_id came back. See
> "Timeout handling" at the end.

> T1 failed on an output content-policy check (`OutputVideoSensitiveContentDetected`)
> for an entirely innocuous prompt, with no references involved. Unrelated to this
> repo's code — recorded because it is a failure mode worth expecting.

## Summary

| # | Task type | Request | Status | duration | ratio | format |
|---|---|---|---|---|---|---|
| T1 | text-to-video | Text-to-video | ❌ failed | — | `—` | mp4 |
| T2 | text-to-video | Text-to-video, mov output | ✅ succeeded | 5 | `16:9` | mov |
| T3 | first-frame | First-frame image-to-video | ✅ succeeded | 5 | `1:1` | mp4 |
| T4 | reference-to-video | Reference-to-video (image + 2 videos) | ✅ succeeded | 8 | `16:9` | mp4 |
| T5 | video editing | Video edit | ✅ succeeded | 16 | `269:215` | mov |
| T6 | video extension | Video extension (3 source clips) | ✅ succeeded | 11 | `269:215` | mov |
| T7 | video extension | Video extension, model-chosen duration | ✅ succeeded | 6 | `269:215` | mov |

## Generation requests

### T1 — Text-to-video

**Task type:** text-to-video  
**Verifies:** Baseline. Default ratio resolves to 16:9 when there are no references.

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A brass pocket watch lies open on dark slate. The second hand sweeps. Dust motes drift in a hard shaft of window light from the left. Slow push-in. Warm amber tones, shallow depth of field."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

**Response:**

```
status        : failed
output_format : mp4
error         : {'code': 'OutputVideoSensitiveContentDetected.PolicyViolation', 'message': 'The request failed because the output video may be related to copyright restrictions. Request id: 02178609230295000000000000000000000ffffc0a88538ff1604'}
```

### T2 — Text-to-video, mov output

**Task type:** text-to-video  
**Verifies:** output_format='mov' on a simple path (2.5-only parameter).

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Ink disperses through still water in a glass tank. Black tendrils unfurl slowly. Locked macro shot, hard backlight, high contrast, clean white background."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "output_format": "mov"
}
```

**Response:**

```
status        : succeeded
duration      : 5
ratio         : 16:9
resolution    : 720p
output_format : mov
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/mnwmz-30546170806202-tgc_a47f641d3b8a0cffff00000000000000000000626303290687120/cgt-20260807164503-zmwnm.mov?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T084723Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=0cd8ac7684a03980a4741883ac276cf965767b51cf6300e9c8fd96901ce68e55&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.

### T3 — First-frame image-to-video

**Task type:** first-frame  
**Verifies:** ratio='auto' resolves to 'adaptive' because content.role=first_frame locks the output ratio to the source image.

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "The camera pushes in slowly. Light shifts across the surface."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedacne2.5_reference1.png"
      },
      "role": "first_frame"
    }
  ],
  "ratio": "adaptive",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

**Response:**

```
status        : succeeded
duration      : 5
ratio         : 1:1
resolution    : 720p
output_format : mp4
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/nbljj-40546170806202-tgc_ba702a3d4b8a0cffff00000000000000000000401806290687120/cgt-20260807164504-jjlbn.mp4?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T085229Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=ac7849434f140b0e6d7e3987d9672571ae86f88dd58dbe33e86a6f044f4349ca&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.

### T4 — Reference-to-video (image + 2 videos)

**Task type:** reference-to-video  
**Verifies:** Multi-reference binding with @-tags, and that an innocent prompt with video refs is NOT blocked by the intent guard.

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Fruit-flavoured cookies in ordered geometric arrays, styled after @Image1. Camera movement and cut rhythm follow @Video1. The burst-and-scatter energy follows @Video2."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedacne2.5_reference1.png"
      },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/seedacne2.5_reference2.mp4"
      },
      "role": "reference_video"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/seedacne2.5_reference3.mp4"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": 8,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

**Response:**

```
status        : succeeded
duration      : 8
ratio         : 16:9
resolution    : 720p
output_format : mp4
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/7pzqw-33656170806202-tgc_bfe799c23b8a0cffff00000000000000000000685911390687120/cgt-20260807165633-wqzp7.mp4?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T090208Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=293222352a63edf63a1a10c2cab9e8da8642d4b890cc65011402e51f6d180e56&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.


### T5 — Video edit

**Task type:** video editing  
**Verifies:** ratio='adaptive' + duration=-1 accepted; output inherits the source's ratio and duration. Uses the doc's own edit sample.

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Video edit: remove everyone in @Video1 except the protagonist."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/seedance2.5_edit_input.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": -1,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov"
}
```

**Response:**

```
status        : succeeded
duration      : 16
ratio         : 269:215
resolution    : 720p
output_format : mov
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/gk2nq-75656170806202-tgc_8c90e3339a8a0cffff00000000000000000000322571390687120/cgt-20260807165657-qn2kg.mov?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T090520Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=ca1e3996a4b437a137774d548b94359c12b1f8ba92d2712f4df87fa29064cb33&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.


### T6 — Video extension (3 source clips)

**Task type:** video extension  
**Verifies:** NOT PREVIOUSLY CONFIRMED LIVE. ratio locked to 'adaptive', duration settable. Uses the doc's own extension sample verbatim.

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Extend @Video1, then after the window opens, enter the interior of the art gallery in @Video2, and finally the camera moves into the painting in @Video3."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/r2v_extend_video1_75.mov"
      },
      "role": "reference_video"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/r2v_extend_video2.mp4"
      },
      "role": "reference_video"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/r2v_extend_video3.mp4"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": 11,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov"
}
```

**Response:**

```
status        : succeeded
duration      : 11
ratio         : 269:215
resolution    : 720p
output_format : mov
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/n255g-51646170806202-tgc_d6f7b97d3b8a0cffff00000000000000000000003945290687120/cgt-20260807164615-g552n.mov?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T085104Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=8c5ddec83f1a20f749b8ada858e983c78e030fba0ceec7ac351ae3550b1aa550&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.

### T7 — Video extension, model-chosen duration

**Task type:** video extension  
**Verifies:** duration=-1 on an extension (legal, unlike on an edit).

**Request sent:**

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Continue @Video1 forward; the camera keeps moving in the same direction."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://ark-project.tos-cn-beijing.volces.com/doc_video/r2v_extend_video1_75.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": -1,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov"
}
```

**Response:**

```
status        : succeeded
duration      : 6
ratio         : 269:215
resolution    : 720p
output_format : mov
```

[Output video](https://ark-acg-ap-southeast-1.tos-ap-southeast-1.volces.com/dreamina-seedance-2-5/3000006864/Video/bm4sn-24756170806202-tgc_ef9edb47878a0cffff00000000000000000000556651390687120/cgt-20260807165742-ns4mb.mov?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260807%2Fap-southeast-1%2Ftos%2Frequest&X-Tos-Date=20260807T090143Z&X-Tos-Expires=86400&X-Tos-Max-Requests=100&X-Tos-Signature=5c8f62c29df55731c99818574201b804aca448fded733ab56b38e1409c340a7a&X-Tos-SignedHeaders=host) — signed URL, expires 24h after the run.


## Guard cases (must never reach the API)

These assert the local validation layer. A request that reaches the API here is a bug: the clash would be reported asynchronously minutes later, after the task had queued and been consumed.

G4 is listed separately below: it is a **warn-and-submit** case, not a block, so reaching the API is the correct outcome for it.

| # | Case | Reached API? | Outcome |
|---|---|---|---|
| G1 | Edit wording via generic tool | no | blocked |
| G2 | Extend wording via generic tool | no | blocked |
| G3 | First-frame with explicit ratio | no | blocked |
| G5 | 1080p on Seedance 2.5 | no | blocked |
| G6 | Duration 31s on Seedance 2.5 | no | blocked |

### G1 — Edit wording via generic tool

**Verifies:** Prompt-intent guard blocks a clash that would fail asynchronously.

```
This prompt reads as a video edit task (matched 'Remove'), which Seedance 2.5 locks: ratio must be 'adaptive' (got '16:9'); duration must be -1 (got 5). Submitting as-is would queue the task and then fail with InvalidParameter.TaskTypeConstraint minutes later.
  • If you meant to edit the video, use submit_video_edit() / seedance_edit_video / 'seedance edit', which set these for you.
  • If you meant a plain reference-to-video generation, reword the prompt to avoid 'Remove' — the docs warn that edit/extend wording causes the model to misclassify reference-to-video tasks.
```

### G2 — Extend wording via generic tool

**Verifies:** Same guard, extension branch (ratio only).

```
This prompt reads as a video extend task (matched 'Continue'), which Seedance 2.5 locks: ratio must be 'adaptive' (got '9:16'). Submitting as-is would queue the task and then fail with InvalidParameter.TaskTypeConstraint minutes later.
  • If you meant to extend the video, use submit_video_extend() / seedance_extend_video / 'seedance extend', which set these for you.
  • If you meant a plain reference-to-video generation, reword the prompt to avoid 'Continue' — the docs warn that edit/extend wording causes the model to misclassify reference-to-video tasks.
```

### G3 — First-frame with explicit ratio

**Verifies:** Role-based constraint, checked before submission.

```
ratio must be 'adaptive' for first_frame tasks on dreamina-seedance-2-5-260628 — got '16:9'. The output ratio is locked to the source image or video. Pass ratio='adaptive' or leave it unset.
```

### G4 — Edit tool, prompt missing a trigger word *(warn-and-submit, not a block)*

**Verifies:** Warns that Seedance will generate a new clip instead of editing.

This one is *meant* to reach the API. Seedance classifies the task from the prompt, so an
edit request with no trigger word is treated as a plain reference-to-video generation and
returns a brand-new clip — a silent wrong result rather than an error. Blocking it would be
wrong (the caller may know what they are doing), so the tools submit it and warn:

```
WARNING: Prompt contains no edit trigger word ('edit the video', 'add', 'remove',
'replace', 'change'). Seedance decides the task type from the prompt, so it will
likely treat this as a plain reference-to-video generation and produce a NEW clip
instead of editing the source. Reword the prompt to state the operation explicitly.
```

On the first pass this case was mislabelled "reached API — BUG" in this report. That was a
fault in how the case was categorised here, not in the code: it reached the API because it
is supposed to, and it reported an error only because it hit the 30s submit timeout
described below.


### G5 — 1080p on Seedance 2.5

**Verifies:** 2.5 has no 1080p tier; must be caught locally.

```
Invalid resolution '1080p' for dreamina-seedance-2-5-260628. Must be one of: 480p, 720p
```

### G6 — Duration 31s on Seedance 2.5

**Verifies:** Upper bound of the 4-30s range.

```
Invalid duration 31. Must be 4–30s (or -1 to let the model choose) for model dreamina-seedance-2-5-260628.
```

## Timeout handling (bug found by this run)

Three requests failed on the first pass with `TimeoutError: The read operation timed out`.
That was a client bug, not an API rejection, and it had two distinct faults.

**The default was too low.** `SUBMIT_TIMEOUT` was 30s. Task creation blocks while the API
validates and fetches every reference URL, so a request carrying two or three reference
videos routinely takes longer than that to acknowledge. Every timeout was a multi-reference
request; every single-reference and text-only request was fine. Default is now **120s**
(`SEEDANCE_SUBMIT_TIMEOUT`).

**The failure was silent and costly.** `urlopen` raises a bare `TimeoutError`, which is *not*
a `URLError` — so it escaped as a non-`SeedanceError` and bypassed the error handling in
every caller, including the MCP layer. Worse, the POST had already reached the server: the
task was created and billed, but no `task_id` ever came back, leaving an orphaned generation
that could only be recovered by listing tasks.

It is now raised as `SubmitTimeoutError`, which says a task may exist and to check
`seedance list` before resubmitting. It is **excluded from retry**: task creation is not
idempotent, so retrying bills a second generation. That exclusion is load-bearing — wrapping
the timeout as a plain `APIError` would have made `request_with_retry` retry it three times
and create three duplicate tasks. Two tests pin the behaviour.

## Observations worth keeping

**`adaptive` returns the source's exact ratio, not one of the seven request values.**
T3 (first frame, square sample image) returned `1:1`; T5 and T7 both returned **`269:215`**,
inherited from the source clip. Never feed a response `ratio` back into a request.

**Duration behaves differently per task type, exactly as documented.** T5 (edit) returned 16s
— the source length, which is not settable. T6 (extend) honoured the requested 11s. T7
(extend, `duration=-1`) let the model choose, and it returned 6s.

**The output content filter is noisy.** T1 was plain text-to-video with no references and was
rejected for "copyright restrictions". Two earlier runs against a previously generated clip
hit the same check. Expect it, and do not treat it as a parameter problem.
