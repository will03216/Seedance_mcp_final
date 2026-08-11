"""Generate docs/request-permutations.md by executing every permutation.

Each row is produced by actually calling the SDK with HTTP mocked and capturing
the payload at the wire boundary, so the document cannot drift from the code:
if behaviour changes, regenerating changes the doc.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

from seedance import SeedanceClient
from seedance.config import MODELS
from seedance.exceptions import SeedanceError

logging.disable(logging.CRITICAL)

IMG = "https://example.com/ref.jpg"
VID = "https://example.com/clip.mov"
AUD = "https://example.com/track.mp3"
FF = "https://example.com/first.jpg"
LF = "https://example.com/last.jpg"

CORE = ("model", "content", "ratio", "duration", "resolution",
        "generate_audio", "watermark")

c = SeedanceClient()


def run(fn):
    """Return (payload | None, error | None)."""
    cap = {}

    def fake(url, **kw):
        cap["p"] = kw.get("payload")
        return {"id": "cgt-example", "status": "queued"}

    try:
        with patch("seedance.client.request_with_retry", side_effect=fake):
            fn()
    except SeedanceError as exc:
        return None, str(exc)
    return cap.get("p"), None


def roles(payload):
    return [i.get("role", "—") for i in payload["content"] if i["type"] != "text"]


# (section, name, what it demonstrates, callable)
CASES: list[tuple[str, str, str, object]] = [
    # ---- task types -----------------------------------------------------
    ("Task types", "Text-to-video",
     "No references. `ratio` free, `duration` free.",
     lambda: c.submit_text_to_video("A city at dusk.", duration=5)),

    ("Task types", "Reference-to-video — images",
     "`reference_image` roles. No task-type constraints.",
     lambda: c.submit_image_to_video("@Image1 walks through rain.", image_urls=[IMG], duration=8)),

    ("Task types", "Reference-to-video — audio only",
     "Seedance 2.5 exclusive: audio with no image or video.",
     lambda: c.submit_image_to_video("A dancer moves to @Audio1.", audio_urls=[AUD], duration=15)),

    ("Task types", "Reference-to-video — mixed",
     "All three omni roles in one request.",
     lambda: c.submit_image_to_video(
         "@Image1 performs; rhythm follows @Video1; beats from @Audio1.",
         image_urls=[IMG], video_urls=[VID], audio_urls=[AUD], duration=10)),

    ("Task types", "Reference-to-video — declared",
     "`task_type='reference'` sends `omni_reference_task_type`, moving validation to submit time.",
     lambda: c.submit_image_to_video(
         "@Image1 walks.", image_urls=[IMG], video_urls=[VID],
         task_type="reference", ratio="16:9", duration=8)),

    ("Task types", "First frame",
     "`first_frame` role. Ratio locked to the source image.",
     lambda: c.submit_image_to_video("She turns to camera.", first_frame_url=FF, duration=5)),

    ("Task types", "First + last frame",
     "Transition between two stills. Ratio still locked.",
     lambda: c.submit_image_to_video(
         "A slow dissolve between the two states.",
         first_frame_url=FF, last_frame_url=LF, duration=6)),

    ("Task types", "Video edit",
     "Ratio AND duration locked to the source clip; neither is settable.",
     lambda: c.submit_video_edit("Video edit: remove the crowd in @Video1.", [VID])),

    ("Task types", "Video extension — explicit duration",
     "Ratio locked; duration is yours.",
     lambda: c.submit_video_extend("Extend @Video1 forward.", [VID], duration=11)),

    ("Task types", "Video extension — model-chosen duration",
     "`duration=-1` lets the model pick within 4–30s.",
     lambda: c.submit_video_extend("Continue @Video1.", [VID], duration=-1)),

    # ---- optional parameters --------------------------------------------
    ("Optional parameters", "priority",
     "Queue position, 0–9. Supported on 2.5 and the 2.0 series.",
     lambda: c.submit_text_to_video("A city.", priority=7)),

    ("Optional parameters", "callback_url",
     "Status changes are POSTed here, removing the need to poll.",
     lambda: c.submit_text_to_video("A city.", callback_url="https://example.com/hook")),

    ("Optional parameters", "return_last_frame",
     "Adds `last_frame_url` (PNG) to the result — the documented way to chain clips.",
     lambda: c.submit_text_to_video("A city.", return_last_frame=True)),

    ("Optional parameters", "execution_expires_after",
     "Timeout in seconds, 3600–259200. On expiry the task ends with status `expired`.",
     lambda: c.submit_text_to_video("A city.", execution_expires_after=7200)),

    ("Optional parameters", "safety_identifier",
     "Opaque end-user identifier, max 64 chars.",
     lambda: c.submit_text_to_video("A city.", safety_identifier="u_9f3a")),

    ("Optional parameters", "service_tier",
     "`default` only on 2.5/2.0; `flex` is rejected.",
     lambda: c.submit_text_to_video("A city.", service_tier="default")),

    ("Optional parameters", "seed",
     "Reproducible sampling.",
     lambda: c.submit_text_to_video("A city.", seed=42)),

    ("Optional parameters", "output_format=mov",
     "Higher colour precision for grading; 2.5 only.",
     lambda: c.submit_text_to_video("A city.", output_format="mov")),

    ("Optional parameters", "Everything at once",
     "All optional parameters combined on one reference-to-video request.",
     lambda: c.submit_image_to_video(
         "@Image1 walks through rain; rhythm follows @Video1.",
         image_urls=[IMG], video_urls=[VID], task_type="reference",
         ratio="21:9", duration=12, resolution="720p", generate_audio=True,
         output_format="mov", seed=7, priority=5,
         callback_url="https://example.com/hook", return_last_frame=True,
         execution_expires_after=7200, safety_identifier="u_9f3a",
         service_tier="default")),

    # ---- model selection -------------------------------------------------
    ("Model selection", "Seedance 2.0 (1080p)",
     "The only way to get 1080p; no omni task type, no mov.",
     lambda: c.submit_text_to_video("A city.", model="2.0", resolution="1080p", duration=10)),

    ("Model selection", "Seedance 2.0 Fast",
     "`fast_mode=True` always resolves here — there is no 2.5 fast variant.",
     lambda: c.submit_text_to_video("A city.", fast_mode=True, duration=10)),

    ("Model selection", "Duration -1 on text-to-video",
     "Model picks the length within 4–30s.",
     lambda: c.submit_text_to_video("A city.", duration=-1)),
]

REJECTS: list[tuple[str, str, object]] = [
    ("Ratio on a first-frame task",
     "Output ratio is locked to the source image.",
     lambda: c.submit_image_to_video("She turns.", first_frame_url=FF, ratio="16:9")),
    ("Concrete duration on an edit",
     "Output duration is locked to the source clip.",
     lambda: c.submit_image_to_video(
         "Remove the crowd from @Video1.", video_urls=[VID], task_type="edit",
         ratio="adaptive", duration=10)),
    ("Edit wording through a generic tool",
     "Prompt-intent guard: this would fail asynchronously after being billed.",
     lambda: c.submit_image_to_video("Remove the crowd from @Video1.", video_urls=[VID], ratio="16:9")),
    ("Extend wording through a generic tool",
     "Same guard, extension branch.",
     lambda: c.submit_image_to_video("Continue the story of @Video1.", video_urls=[VID], ratio="9:16")),
    ("1080p on Seedance 2.5",
     "2.5 tops out at 720p; use --model 2.0 or upscale afterwards.",
     lambda: c.submit_text_to_video("A city.", resolution="1080p")),
    ("Duration 31s on Seedance 2.5",
     "Range is 4–30s (or -1).",
     lambda: c.submit_text_to_video("A city.", duration=31)),
    ("Duration 20s on Seedance 2.0",
     "2.0 range is 4–15s.",
     lambda: c.submit_text_to_video("A city.", model="2.0", duration=20)),
    ("camera_fixed on Seedance 2.5",
     "Documented for Seedance 1.5 pro / 1.0 pro only.",
     lambda: c.submit_text_to_video("A city.", camerafixed=True)),
    ("priority=10",
     "Range is 0–9.",
     lambda: c.submit_text_to_video("A city.", priority=10)),
    ("service_tier=flex on 2.5",
     "flex is unsupported on the 2.5 and 2.0 series.",
     lambda: c.submit_text_to_video("A city.", service_tier="flex")),
    ("frames on Seedance 2.5",
     "frames is unsupported on 2.5/2.0; use duration.",
     lambda: c.submit_text_to_video("A city.", frames=33)),
    ("execution_expires_after=3599",
     "Range is 3600–259200 seconds.",
     lambda: c.submit_text_to_video("A city.", execution_expires_after=3599)),
    ("safety_identifier over 64 chars",
     "Maximum length is 64.",
     lambda: c.submit_text_to_video("A city.", safety_identifier="x" * 65)),
    ("Non-http callback_url",
     "Must be an http(s) URL.",
     lambda: c.submit_text_to_video("A city.", callback_url="ftp://example.com")),
    ("audio-only on Seedance 2.0",
     "Audio-only input is a 2.5 exclusive.",
     lambda: c.submit_image_to_video("A dancer to @Audio1.", model="2.0", audio_urls=[AUD])),
    ("11 reference videos on 2.5",
     "Limit is 10 videos.",
     lambda: c.submit_image_to_video("test", video_urls=[f"https://e/{i}.mov" for i in range(11)])),
    ("last_frame_url without first_frame_url",
     "The API has no last-frame-only mode.",
     lambda: c.submit_image_to_video("test", last_frame_url=LF)),
    ("Two reference videos on an edit",
     "Verified live: the API requires exactly one video per edit.",
     lambda: c.submit_video_edit("Video edit: remove the crowd.", [VID, "https://example.com/b.mov"])),
]

L: list[str] = []
A = L.append

A("# Seedance request permutations\n")
A("Every payload below is produced by **executing the SDK** with the HTTP layer mocked and")
A("capturing the request at the wire boundary. The file is generated, so it cannot drift from")
A("the code: if behaviour changes, regenerating this document changes with it.\n")
A("Endpoint: `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`\n")
A("Only non-default values are sent — every optional parameter is omitted unless set, so the")
A("API's own defaults apply.\n")

A("## Model capabilities\n")
A("| | " + " | ".join(m["label"] for m in MODELS.values()) + " |")
A("|---|" + "---|" * len(MODELS))
rows = [
    ("Resolutions", lambda m: ", ".join(m["resolutions"])),
    ("Duration", lambda m: f"{m['duration_range'][0]}–{m['duration_range'][1]}s or -1"),
    ("Refs img/vid/aud", lambda m: f"{m['max_reference_images']}/{m['max_reference_videos']}/{m['max_reference_audio']}"),
    ("Audio-only input", lambda m: "yes" if m["supports_audio_only"] else "no"),
    ("output_format", lambda m: "mp4, mov" if m["supports_output_format"] else "mp4"),
    ("omni_reference_task_type", lambda m: "yes" if m["supports_omni_task_type"] else "no"),
    ("priority", lambda m: "yes" if m["supports_priority"] else "no"),
    ("return_last_frame", lambda m: "yes" if m["supports_return_last_frame"] else "no"),
    ("camera_fixed", lambda m: "yes" if m["supports_camerafixed"] else "no"),
    ("frames", lambda m: "yes" if m["supports_frames"] else "no"),
    ("service_tier=flex", lambda m: "yes" if m["supports_service_tier_flex"] else "no"),
]
for label, fn in rows:
    A(f"| **{label}** | " + " | ".join(fn(m) for m in MODELS.values()) + " |")
A("")

section = None
for sec, name, note, fn in CASES:
    if sec != section:
        section = sec
        A(f"## {sec}\n")
    payload, err = run(fn)
    A(f"### {name}\n")
    A(f"{note}\n")
    if err:
        A("Rejected before submission:\n")
        A("```")
        A(err.strip()[:600])
        A("```\n")
        continue
    A(f"`content[]` roles: {', '.join(roles(payload)) or 'text only'}\n")
    A("```json")
    A(json.dumps(payload, indent=2, ensure_ascii=False))
    A("```\n")
    extras = {k: v for k, v in payload.items() if k not in CORE}
    if extras:
        A("Optional keys sent: " + ", ".join(f"`{k}`" for k in extras) + "\n")

A("## Rejected before submission\n")
A("These never reach the API. Each would otherwise either fail immediately or — for the")
A("task-type cases — queue, consume a billed slot, and fail asynchronously minutes later.\n")
A("| Request | Why | Error |")
A("|---|---|---|")
for name, note, fn in REJECTS:
    payload, err = run(fn)
    if err is None:
        A(f"| {name} | {note} | **NOT REJECTED — BUG** |")
        continue
    first = " ".join(err.strip().splitlines()[0].split())
    if len(first) > 150:
        first = first[:147] + "…"
    A(f"| {name} | {note} | {first} |")
A("")

with open("docs/request-permutations.md", "w") as fh:
    fh.write("\n".join(L))
print(f"wrote docs/request-permutations.md ({len(L)} lines)")
