# Seedance request permutations

Every payload below is produced by **executing the SDK** with the HTTP layer mocked and
capturing the request at the wire boundary. The file is generated, so it cannot drift from
the code: if behaviour changes, regenerating this document changes with it.

Endpoint: `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`

Only non-default values are sent — every optional parameter is omitted unless set, so the
API's own defaults apply.

## Model capabilities

| | Seedance 2.5 | Seedance 2.0 Standard | Seedance 2.0 Fast |
|---|---|---|---|
| **Resolutions** | 480p, 720p | 480p, 720p, 1080p | 480p, 720p, 1080p |
| **Duration** | 4–30s or -1 | 4–15s or -1 | 4–15s or -1 |
| **Refs img/vid/aud** | 30/10/10 | 9/3/3 | 9/3/3 |
| **Audio-only input** | yes | no | no |
| **output_format** | mp4, mov | mp4 | mp4 |
| **omni_reference_task_type** | yes | no | no |
| **priority** | yes | yes | yes |
| **return_last_frame** | yes | yes | yes |
| **camera_fixed** | no | no | no |
| **frames** | no | no | no |
| **service_tier=flex** | no | no | no |

## Task types

### Text-to-video

No references. `ratio` free, `duration` free.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city at dusk."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Reference-to-video — images

`reference_image` roles. No task-type constraints.

`content[]` roles: reference_image

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "@Image1 walks through rain."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/ref.jpg"
      },
      "role": "reference_image"
    }
  ],
  "ratio": "16:9",
  "duration": 8,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Reference-to-video — audio only

Seedance 2.5 exclusive: audio with no image or video.

`content[]` roles: reference_audio

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A dancer moves to @Audio1."
    },
    {
      "type": "audio_url",
      "audio_url": {
        "url": "https://example.com/track.mp3"
      },
      "role": "reference_audio"
    }
  ],
  "ratio": "16:9",
  "duration": 15,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Reference-to-video — mixed

All three omni roles in one request.

`content[]` roles: reference_image, reference_video, reference_audio

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "@Image1 performs; rhythm follows @Video1; beats from @Audio1."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/ref.jpg"
      },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    },
    {
      "type": "audio_url",
      "audio_url": {
        "url": "https://example.com/track.mp3"
      },
      "role": "reference_audio"
    }
  ],
  "ratio": "adaptive",
  "duration": 10,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Reference-to-video — declared

`task_type='reference'` sends `omni_reference_task_type`, moving validation to submit time.

`content[]` roles: reference_image, reference_video

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "@Image1 walks."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/ref.jpg"
      },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "16:9",
  "duration": 8,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "omni_reference_task_type": "reference"
}
```

Optional keys sent: `omni_reference_task_type`

### First frame

`first_frame` role. Ratio locked to the source image.

`content[]` roles: first_frame

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "She turns to camera."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/first.jpg"
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

### First + last frame

Transition between two stills. Ratio still locked.

`content[]` roles: first_frame, last_frame

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A slow dissolve between the two states."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/first.jpg"
      },
      "role": "first_frame"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/last.jpg"
      },
      "role": "last_frame"
    }
  ],
  "ratio": "adaptive",
  "duration": 6,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Video edit

Ratio AND duration locked to the source clip; neither is settable.

`content[]` roles: reference_video

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Video edit: remove the crowd in @Video1."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": -1,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov",
  "omni_reference_task_type": "edit"
}
```

Optional keys sent: `output_format`, `omni_reference_task_type`

### Video extension — explicit duration

Ratio locked; duration is yours.

`content[]` roles: reference_video

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Extend @Video1 forward."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": 11,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov",
  "omni_reference_task_type": "extend"
}
```

Optional keys sent: `output_format`, `omni_reference_task_type`

### Video extension — model-chosen duration

`duration=-1` lets the model pick within 4–30s.

`content[]` roles: reference_video

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "Continue @Video1."
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "adaptive",
  "duration": -1,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "output_format": "mov",
  "omni_reference_task_type": "extend"
}
```

Optional keys sent: `output_format`, `omni_reference_task_type`

## Optional parameters

### priority

Queue position, 0–9. Supported on 2.5 and the 2.0 series.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "priority": 7
}
```

Optional keys sent: `priority`

### callback_url

Status changes are POSTed here, removing the need to poll.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "callback_url": "https://example.com/hook"
}
```

Optional keys sent: `callback_url`

### return_last_frame

Adds `last_frame_url` (PNG) to the result — the documented way to chain clips.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "return_last_frame": true
}
```

Optional keys sent: `return_last_frame`

### execution_expires_after

Timeout in seconds, 3600–259200. On expiry the task ends with status `expired`.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "execution_expires_after": 7200
}
```

Optional keys sent: `execution_expires_after`

### safety_identifier

Opaque end-user identifier, max 64 chars.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "safety_identifier": "u_9f3a"
}
```

Optional keys sent: `safety_identifier`

### service_tier

`default` only on 2.5/2.0; `flex` is rejected.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "service_tier": "default"
}
```

Optional keys sent: `service_tier`

### seed

Reproducible sampling.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false,
  "seed": 42
}
```

Optional keys sent: `seed`

### output_format=mov

Higher colour precision for grading; 2.5 only.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
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

Optional keys sent: `output_format`

### Everything at once

All optional parameters combined on one reference-to-video request.

`content[]` roles: reference_image, reference_video

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "@Image1 walks through rain; rhythm follows @Video1."
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/ref.jpg"
      },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": {
        "url": "https://example.com/clip.mov"
      },
      "role": "reference_video"
    }
  ],
  "ratio": "21:9",
  "duration": 12,
  "resolution": "720p",
  "generate_audio": true,
  "watermark": false,
  "seed": 7,
  "output_format": "mov",
  "omni_reference_task_type": "reference",
  "priority": 5,
  "callback_url": "https://example.com/hook",
  "return_last_frame": true,
  "execution_expires_after": 7200,
  "safety_identifier": "u_9f3a",
  "service_tier": "default"
}
```

Optional keys sent: `seed`, `output_format`, `omni_reference_task_type`, `priority`, `callback_url`, `return_last_frame`, `execution_expires_after`, `safety_identifier`, `service_tier`

## Model selection

### Seedance 2.0 (1080p)

The only way to get 1080p; no omni task type, no mov.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 10,
  "resolution": "1080p",
  "generate_audio": false,
  "watermark": false
}
```

### Seedance 2.0 Fast

`fast_mode=True` always resolves here — there is no 2.5 fast variant.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-0-fast-260128",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": 10,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

### Duration -1 on text-to-video

Model picks the length within 4–30s.

`content[]` roles: text only

```json
{
  "model": "dreamina-seedance-2-5-260628",
  "content": [
    {
      "type": "text",
      "text": "A city."
    }
  ],
  "ratio": "16:9",
  "duration": -1,
  "resolution": "720p",
  "generate_audio": false,
  "watermark": false
}
```

## Rejected before submission

These never reach the API. Each would otherwise either fail immediately or — for the
task-type cases — queue, consume a billed slot, and fail asynchronously minutes later.

| Request | Why | Error |
|---|---|---|
| Ratio on a first-frame task | Output ratio is locked to the source image. | ratio must be 'adaptive' for first_frame tasks on dreamina-seedance-2-5-260628 — got '16:9'. The output ratio is locked to the source image or vide… |
| Concrete duration on an edit | Output duration is locked to the source clip. | duration must be -1 for edit tasks on dreamina-seedance-2-5-260628 — got 10. The output duration is locked to the source video. Pass duration=-1 or… |
| Edit wording through a generic tool | Prompt-intent guard: this would fail asynchronously after being billed. | This prompt reads as a video edit task (matched 'Remove'), which Seedance 2.5 locks: ratio must be 'adaptive' (got '16:9'); duration must be -1 (go… |
| Extend wording through a generic tool | Same guard, extension branch. | This prompt reads as a video extend task (matched 'Continue'), which Seedance 2.5 locks: ratio must be 'adaptive' (got '9:16'). Submitting as-is wo… |
| 1080p on Seedance 2.5 | 2.5 tops out at 720p; use --model 2.0 or upscale afterwards. | Invalid resolution '1080p' for dreamina-seedance-2-5-260628. Must be one of: 480p, 720p |
| Duration 31s on Seedance 2.5 | Range is 4–30s (or -1). | Invalid duration 31. Must be 4–30s (or -1 to let the model choose) for model dreamina-seedance-2-5-260628. |
| Duration 20s on Seedance 2.0 | 2.0 range is 4–15s. | Invalid duration 20. Must be 4–15s (or -1 to let the model choose) for model dreamina-seedance-2-0-260128. |
| camera_fixed on Seedance 2.5 | Documented for Seedance 1.5 pro / 1.0 pro only. | camera_fixed is not supported by dreamina-seedance-2-5-260628. The API documents it for Dreamina Seedance 1.5 pro and 1.0 pro only. Express a locke… |
| priority=10 | Range is 0–9. | Invalid priority 10. Must be 0–9. |
| service_tier=flex on 2.5 | flex is unsupported on the 2.5 and 2.0 series. | service_tier='flex' is not supported by dreamina-seedance-2-5-260628. |
| frames on Seedance 2.5 | frames is unsupported on 2.5/2.0; use duration. | frames is not supported by dreamina-seedance-2-5-260628. Use duration instead. |
| execution_expires_after=3599 | Range is 3600–259200 seconds. | Invalid execution_expires_after 3599. Must be 3600–259200 seconds (1h–72h). |
| safety_identifier over 64 chars | Maximum length is 64. | safety_identifier is 65 characters; the maximum is 64. |
| Non-http callback_url | Must be an http(s) URL. | callback_url must be an http(s) URL — got 'ftp://example.com'. |
| audio-only on Seedance 2.0 | Audio-only input is a 2.5 exclusive. | Seedance 2.0 Standard does not support audio-only input. Pair audio_urls with image_urls, video_urls, or a first frame (audio-only generation requi… |
| 11 reference videos on 2.5 | Limit is 10 videos. | Too many video_urls: 11 (max 10 for Seedance 2.5). |
| last_frame_url without first_frame_url | The API has no last-frame-only mode. | last_frame_url requires first_frame_url. The API does not support last-frame-only mode. |
| Two reference videos on an edit | Verified live: the API requires exactly one video per edit. | A video edit takes exactly one reference video — got 2. Edit one clip per request; to edit several, submit several tasks. (Extension does accept mu… |
