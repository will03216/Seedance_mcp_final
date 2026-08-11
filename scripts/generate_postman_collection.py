"""Generate a Postman v2.1 collection for the Seedance API.

Request bodies for the valid cases are produced by executing the SDK with HTTP
mocked and capturing the payload at the wire boundary, so the collection cannot
drift from the code. Constraint-error cases are hand-built, because the SDK
rejects them locally and they exist precisely to show the API's own response.

    uv run python scripts/generate_postman_collection.py
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

logging.disable(logging.CRITICAL)

OUT = Path("postman/seedance.postman_collection.json")

DOC = "{{DOC_HOST}}"
IMG = f"{DOC}/doc_image/seedacne2.5_reference1.png"
REFV = f"{DOC}/doc_video/seedacne2.5_reference2.mp4"
REFV2 = f"{DOC}/doc_video/seedacne2.5_reference3.mp4"
EDIT_IN = f"{DOC}/doc_video/seedance2.5_edit_input.mov"
EXT_IN = f"{DOC}/doc_video/r2v_extend_video1_75.mov"
AUD = "https://download.samplelib.com/mp3/sample-15s.mp3"

client = SeedanceClient()

CAPTURE_TASK_ID = """const ok = pm.response.code === 200;
pm.test("submitted (200)", () => pm.expect(ok).to.be.true);
if (ok) {
    const id = pm.response.json().id;
    pm.test("returned a task id", () => pm.expect(id).to.be.a("string"));
    if (id) {
        pm.collectionVariables.set("TASK_ID", id);
        console.log("TASK_ID set to " + id + " — run 'Get task' to poll it.");
    }
}"""

EXPECT_400 = """pm.test("rejected at submit (400)", () => pm.response.to.have.status(400));
pm.test("no task was created", () => pm.expect(pm.response.json().id).to.be.undefined);
console.log(JSON.stringify(pm.response.json(), null, 2));"""


def sdk_body(fn) -> str:
    """Run an SDK call with HTTP mocked and return the captured payload as JSON."""
    cap: dict = {}

    def fake(url, **kw):
        cap["p"] = kw.get("payload")
        return {"id": "cgt-example", "status": "queued"}

    try:
        with patch("seedance.client.request_with_retry", side_effect=fake):
            fn()
    except SeedanceError as exc:
        raise SystemExit(f"SDK rejected a collection case that should be valid: {exc}") from exc
    return json.dumps(cap["p"], indent=2, ensure_ascii=False)


def post(name: str, body: str, description: str, test: str = CAPTURE_TASK_ID) -> dict:
    return {
        "name": name,
        "event": [{"listen": "test", "script": {"type": "text/javascript",
                                                "exec": test.split("\n")}}],
        "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": {"mode": "raw", "raw": body,
                     "options": {"raw": {"language": "json"}}},
            "url": {"raw": "{{BASE_URL}}/contents/generations/tasks",
                    "host": ["{{BASE_URL}}"],
                    "path": ["contents", "generations", "tasks"]},
            "description": description,
        },
    }


def get(name: str, path: list[str], description: str, query: list | None = None,
        test: str = "") -> dict:
    url: dict = {"raw": "{{BASE_URL}}/" + "/".join(path), "host": ["{{BASE_URL}}"],
                 "path": path}
    if query:
        url["query"] = query
        url["raw"] += "?" + "&".join(f"{q['key']}={q['value']}" for q in query if not q.get("disabled"))
    item: dict = {
        "name": name,
        "request": {"method": "GET", "header": [], "url": url, "description": description},
    }
    if test:
        item["event"] = [{"listen": "test", "script": {"type": "text/javascript",
                                                       "exec": test.split("\n")}}]
    return item


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

task_types = [
    post("Text-to-video",
         sdk_body(lambda: client.submit_text_to_video(
             "A brass compass rests on a folded paper map. The needle settles. Hard "
             "afternoon light rakes in from the left. Slow push-in, warm amber tones.",
             duration=5)),
         "No references. `ratio` and `duration` are both unconstrained."),

    post("First frame",
         sdk_body(lambda: client.submit_image_to_video(
             "The camera pushes in slowly. Light shifts across the surface.",
             first_frame_url=IMG, duration=5)),
         "`content.role=first_frame`. The output ratio is locked to the source image, "
         "so `ratio` must be `adaptive` — passing anything else fails."),

    post("First + last frame",
         sdk_body(lambda: client.submit_image_to_video(
             "A slow dissolve between the two states.",
             first_frame_url=IMG, last_frame_url=IMG, duration=6)),
         "Adds a `last_frame` role. There is no last-frame-only mode: `last_frame` "
         "always requires `first_frame`."),

    post("Reference-to-video — images",
         sdk_body(lambda: client.submit_image_to_video(
             "@Image1 sets the palette. Bright, premium, strongly rhythmic.",
             image_urls=[IMG], task_type="reference", ratio="16:9", duration=8,
             generate_audio=False)),
         "Declares `omni_reference_task_type=reference`, which has no ratio or "
         "duration constraints — hence the concrete 16:9."),

    post("Reference-to-video — audio only",
         sdk_body(lambda: client.submit_image_to_video(
             "A dancer moves to the rhythm of @Audio1. Neon warehouse, handheld, "
             "cuts landing on the downbeats.",
             audio_urls=[AUD], task_type="reference", ratio="16:9", duration=15,
             generate_audio=False)),
         "Seedance 2.5 exclusive: audio as the ONLY reference. Seedance 2.0 rejects this."),

    post("Reference-to-video — mixed",
         sdk_body(lambda: client.submit_image_to_video(
             "@Image1 sets the palette; camera rhythm follows @Video1; the burst "
             "energy follows @Video2.",
             image_urls=[IMG], video_urls=[REFV, REFV2], task_type="reference",
             ratio="16:9", duration=10, generate_audio=False)),
         "All three omni roles together. Tag every reference in the prompt or the "
         "model cannot bind them to subjects."),

    post("Video edit",
         sdk_body(lambda: client.submit_video_edit(
             "Video edit: remove all the people in the background of @Video1.",
             [EDIT_IN])),
         "`ratio` must be `adaptive` and `duration` must be `-1` — both are inherited "
         "from the source clip. The prompt MUST contain an edit trigger word "
         "(remove/add/replace/change), or the model generates a new clip instead."),

    post("Video edit — two source videos",
         sdk_body(lambda: client.submit_video_edit(
             "Video edit: remove the people in the background of @Video1.",
             [EXT_IN, REFV], generate_audio=False)),
         "An edit may carry several reference videos; the model edits the ONE your "
         "prompt names. Verified live."),

    post("Video extension",
         sdk_body(lambda: client.submit_video_extend(
             "Extend @Video1 forward; the camera keeps moving in the same direction.",
             [EXT_IN], duration=8, generate_audio=False)),
         "`ratio` must be `adaptive`. Unlike an edit, `duration` IS settable. "
         "`generate_audio` is off here — a generated track over a source that already "
         "has audio has tripped the copyright filter."),

    post("Video extension — model-chosen duration",
         sdk_body(lambda: client.submit_video_extend(
             "Continue @Video1 forward.", [EXT_IN], duration=-1, generate_audio=False)),
         "`duration=-1` lets the model choose within 4–30s."),
]

optional = [
    post("priority",
         sdk_body(lambda: client.submit_text_to_video("A city at dusk.", priority=7)),
         "Queue position, 0–9. Higher jumps ahead of lower-priority queued tasks."),
    post("callback_url",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", callback_url="https://example.com/hook")),
         "Status changes are POSTed here, so you do not have to poll."),
    post("return_last_frame",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", return_last_frame=True)),
         "Adds `last_frame_url` (PNG) to the result — the documented way to chain "
         "one clip into the next as its first frame."),
    post("execution_expires_after",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", execution_expires_after=7200)),
         "Timeout in seconds, 3600–259200 (default 48h). On expiry the task ends "
         "with status `expired`."),
    post("safety_identifier",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", safety_identifier="u_9f3a")),
         "Opaque end-user identifier for policy enforcement. Max 64 characters."),
    post("output_format = mov",
         sdk_body(lambda: client.submit_text_to_video(
             "Ink disperses through still water.", output_format="mov")),
         "Higher colour precision (H.264 + YUV444P + PCM) for grading and "
         "compositing. Seedance 2.5 only; plays in IINA, VLC, mpv, ffplay."),
    post("seed",
         sdk_body(lambda: client.submit_text_to_video("A city at dusk.", seed=42)),
         "Reproducible sampling."),
    post("Everything at once",
         sdk_body(lambda: client.submit_image_to_video(
             "@Image1 walks through neon rain; rhythm follows @Video1.",
             image_urls=[IMG], video_urls=[REFV], task_type="reference",
             ratio="21:9", duration=12, resolution="720p", generate_audio=True,
             output_format="mov", seed=7, priority=5,
             callback_url="https://example.com/hook", return_last_frame=True,
             execution_expires_after=7200, safety_identifier="u_9f3a")),
         "Every optional parameter on one reference-to-video request."),
]

models = [
    post("Seedance 2.0 — 1080p",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", model="2.0", resolution="1080p", duration=10)),
         "Seedance 2.5 tops out at 720p, so 2.0 is the only way to get 1080p "
         "straight from generation. It also has no mov output and no omni task type."),
    post("Seedance 2.0 Fast",
         sdk_body(lambda: client.submit_text_to_video(
             "A city at dusk.", fast_mode=True, duration=10)),
         "There is no Seedance 2.5 fast variant, so fast mode always means 2.0 Fast."),
]

management = [
    get("Get task", ["contents", "generations", "tasks", "{{TASK_ID}}"],
        "Poll a task. TASK_ID is set automatically by any request in this collection "
        "that submits successfully. Terminal statuses: succeeded, failed, cancelled, "
        "expired.\n\nOn success the response carries video_url, duration, ratio, "
        "resolution, output_format, and — when requested — last_frame_url.",
        test="""const b = pm.response.json();
pm.test("fetched", () => pm.response.to.have.status(200));
console.log("status: " + b.status);
const done = ["succeeded", "failed", "cancelled", "expired"].includes(b.status);
if (!done) { console.log("still running — send again in 10-15s"); }
if (b.status === "failed") { console.log("error: " + JSON.stringify(b.error)); }"""),

    get("List tasks", ["contents", "generations", "tasks"],
        "Browse recent tasks. Useful after a submit timeout, when a task may have "
        "been created without returning an id.",
        query=[{"key": "page_num", "value": "1"},
               {"key": "page_size", "value": "10"},
               {"key": "filter.status", "value": "succeeded", "disabled": True},
               {"key": "filter.model", "value": "dreamina-seedance-2-5-260628",
                "disabled": True}]),

    {"name": "Cancel task",
     "request": {"method": "DELETE", "header": [],
                 "url": {"raw": "{{BASE_URL}}/contents/generations/tasks/{{TASK_ID}}",
                         "host": ["{{BASE_URL}}"],
                         "path": ["contents", "generations", "tasks", "{{TASK_ID}}"]},
                 "description": "Cancel a queued or running task."}},
]

# Hand-built: the SDK blocks these locally, and they exist to show the API's reply.
errors = [
    post("edit + concrete ratio and duration",
         json.dumps({
             "model": "dreamina-seedance-2-5-260628",
             "content": [
                 {"type": "text", "text": "Video edit: remove the people in the background of @Video1."},
                 {"type": "video_url", "video_url": {"url": EDIT_IN}, "role": "reference_video"},
             ],
             "omni_reference_task_type": "edit",
             "ratio": "16:9", "duration": 5, "resolution": "720p", "watermark": False,
         }, indent=2),
         "An edit inherits ratio and duration from the source, so neither may be set.\n\n"
         "This is the payoff of declaring the task type: WITHOUT "
         "`omni_reference_task_type` the identical request is accepted, queues, "
         "consumes a billed slot, and only then fails with "
         "InvalidParameter.TaskTypeConstraint. Declared, it fails here at submit and "
         "no task is created.",
         EXPECT_400),

    post("extend + concrete ratio",
         json.dumps({
             "model": "dreamina-seedance-2-5-260628",
             "content": [
                 {"type": "text", "text": "Extend @Video1 forward."},
                 {"type": "video_url", "video_url": {"url": EXT_IN}, "role": "reference_video"},
             ],
             "omni_reference_task_type": "extend",
             "ratio": "9:16", "duration": 8, "resolution": "720p", "watermark": False,
         }, indent=2),
         "Extension locks the ratio to the source. Duration, unlike an edit, is free.",
         EXPECT_400),

    post("edit with no reference video",
         json.dumps({
             "model": "dreamina-seedance-2-5-260628",
             "content": [
                 {"type": "text", "text": "Video edit: remove the background people."},
                 {"type": "image_url", "image_url": {"url": IMG}, "role": "reference_image"},
             ],
             "omni_reference_task_type": "edit",
             "ratio": "adaptive", "duration": -1, "resolution": "720p", "watermark": False,
         }, indent=2),
         "An edit needs something to edit. The reply says 'exactly one reference "
         "video', but that describes the semantic — the model edits one video, "
         "selected from the inputs — not a cap: several ARE allowed.",
         EXPECT_400),

    post("invalid omni_reference_task_type",
         json.dumps({
             "model": "dreamina-seedance-2-5-260628",
             "content": [
                 {"type": "text", "text": "A city at dusk."},
                 {"type": "video_url", "video_url": {"url": REFV}, "role": "reference_video"},
             ],
             "omni_reference_task_type": "remix",
             "ratio": "adaptive", "duration": 5, "resolution": "720p", "watermark": False,
         }, indent=2),
         "The API lists the permitted values in its error, which is a handy way to "
         "confirm the enum: auto, reference, edit, extend.",
         EXPECT_400),

    post("1080p on Seedance 2.5",
         json.dumps({
             "model": "dreamina-seedance-2-5-260628",
             "content": [{"type": "text", "text": "A city at dusk."}],
             "ratio": "16:9", "duration": 5, "resolution": "1080p", "watermark": False,
         }, indent=2),
         "Seedance 2.5 offers 480p and 720p only. For a higher-resolution master, "
         "generate at 720p and upscale, or switch to Seedance 2.0.",
         EXPECT_400),
]

collection = {
    "info": {
        "name": "BytePlus Seedance 2.5",
        "description": (
            "Every Seedance request type, ready to run.\n\n"
            "## Setup\n\n"
            "Set the `ARK_API_KEY` collection variable to your ModelArk key. Nothing "
            "else is required — the sample assets are BytePlus's own public "
            "documentation samples, so every request works as-is.\n\n"
            "## How it flows\n\n"
            "Any request that submits successfully stores its task id in `TASK_ID`, "
            "so **Task management → Get task** polls whatever you just sent. Repeat it "
            "every 10–15s until the status is terminal.\n\n"
            "## Seedance 2.5 in one paragraph\n\n"
            "Requests fall into five task types. Text-to-video and reference-to-video "
            "have no special constraints. First-frame, video-edit and video-extend all "
            "lock the output ratio to their source (`ratio` must be `adaptive`), and an "
            "edit additionally locks the duration (`duration` must be `-1`).\n\n"
            "The catch: edit and extend are classified from your PROMPT, not your "
            "parameters, and that happens after the task queues — so a clash normally "
            "surfaces minutes later as a failed, already-billed task. Declaring "
            "`omni_reference_task_type` moves that check to submit time. The "
            "'Constraint errors' folder demonstrates it.\n\n"
            "Generated by scripts/generate_postman_collection.py — request bodies come "
            "from executing the SDK, so they cannot drift from the code."
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{ARK_API_KEY}}", "type": "string"}]},
    "variable": [
        {"key": "ARK_API_KEY", "value": "", "type": "string",
         "description": "Your ModelArk API key. Required."},
        {"key": "BASE_URL", "value": "https://ark.ap-southeast.bytepluses.com/api/v3",
         "type": "string"},
        {"key": "DOC_HOST", "value": "https://ark-project.tos-cn-beijing.volces.com",
         "type": "string", "description": "Host for the BytePlus sample assets."},
        {"key": "TASK_ID", "value": "", "type": "string",
         "description": "Set automatically after any successful submit."},
    ],
    "item": [
        {"name": "1 · Task types", "item": task_types,
         "description": "One request per Seedance task type."},
        {"name": "2 · Optional parameters", "item": optional,
         "description": "Each optional parameter in isolation, then all together."},
        {"name": "3 · Model selection", "item": models,
         "description": "Seedance 2.0 and 2.0 Fast, for 1080p and for cheaper drafts."},
        {"name": "4 · Task management", "item": management,
         "description": "Poll, browse, and cancel."},
        {"name": "5 · Constraint errors", "item": errors,
         "description": "Requests that SHOULD fail, each asserting a 400. These show "
                        "why declaring omni_reference_task_type is worth it."},
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n")
n = sum(len(f["item"]) for f in collection["item"])
print(f"wrote {OUT} — {len(collection['item'])} folders, {n} requests")
