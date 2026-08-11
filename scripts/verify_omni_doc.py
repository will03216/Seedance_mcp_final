"""Verify docs/omni-reference-task-type.md against reality.

Three independent checks:
  1. Every curl block's -d body is valid JSON.
  2. Every claimed payload matches what the SDK actually sends for that case.
  3. Every cited task id really exists, with the status/duration/ratio claimed.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

logging.disable(logging.CRITICAL)

DOC_HOST = "https://ark-project.tos-cn-beijing.volces.com"
MD = Path("docs/omni-reference-task-type.md").read_text()
client = SeedanceClient()

fails: list[str] = []
warns: list[str] = []


# --------------------------------------------------------------------------
# 1. Curl bodies must be valid JSON
# --------------------------------------------------------------------------
blocks = re.findall(r"-d '(\{.*?\})'\n```", MD, re.S)
print(f"curl blocks found: {len(blocks)}")
payloads = []
for i, b in enumerate(blocks, 1):
    # Undo the shell interpolation used for the asset host.
    raw = b.replace("'\"$DOC\"'", DOC_HOST)
    try:
        payloads.append(json.loads(raw))
        print(f"  block {i}: valid JSON")
    except json.JSONDecodeError as exc:
        fails.append(f"block {i}: INVALID JSON — {exc}")
        print(f"  block {i}: INVALID JSON — {exc}")

# --------------------------------------------------------------------------
# 2. Claimed payloads must match what the SDK produces
# --------------------------------------------------------------------------
print("\nSDK payload agreement:")
from unittest.mock import patch  # noqa: E402

IMG = f"{DOC_HOST}/doc_image/seedacne2.5_reference1.png"
REFV = f"{DOC_HOST}/doc_video/seedacne2.5_reference2.mp4"
EDIT = f"{DOC_HOST}/doc_video/seedance2.5_edit_input.mov"
EXT = f"{DOC_HOST}/doc_video/r2v_extend_video1_75.mov"
AUD = "https://download.samplelib.com/mp3/sample-15s.mp3"


def sdk_payload(fn):
    cap = {}

    def fake(url, **kw):
        cap["p"] = kw.get("payload")
        return {"id": "x", "status": "queued"}

    try:
        with patch("seedance.client.request_with_retry", side_effect=fake):
            fn()
    except SeedanceError as exc:
        return None, str(exc)
    return cap.get("p"), None


# Each doc section paired with the SDK call a reader would use for it.
SECTIONS = [
    ("reference (image+video)", lambda: client.submit_image_to_video(
        "@Image1 sets the palette; camera rhythm follows @Video1. Bright, premium, rhythmic.",
        image_urls=[IMG], video_urls=[REFV], task_type="reference",
        ratio="16:9", duration=8, generate_audio=False)),
    ("reference (audio only)", lambda: client.submit_image_to_video(
        "A dancer moves to the rhythm of @Audio1. Neon warehouse, handheld, cuts on the downbeats.",
        audio_urls=[AUD], task_type="reference", ratio="16:9", duration=15,
        generate_audio=False)),
    ("edit", lambda: client.submit_video_edit(
        "Video edit: remove all the people in the background of @Video1.", [EDIT])),
    ("edit (two videos)", lambda: client.submit_video_edit(
        "Video edit: remove the people in the background of @Video1.", [EXT, REFV],
        generate_audio=False)),
    ("extend", lambda: client.submit_video_extend(
        "Extend @Video1 forward; the camera keeps moving in the same direction.",
        [EXT], duration=8, generate_audio=False)),
]

# Divergences that are real, intentional, and called out in the document itself.
# Anything not listed here is a failure.
ALLOWED_DIVERGENCES = {
    ("edit (two videos)", "output_format"):
        "curl omits it (API default mp4); submit_video_edit defaults to mov",
}

for name, fn in SECTIONS:
    p, err = sdk_payload(fn)
    if err:
        fails.append(f"SDK rejects the documented {name} case: {err.splitlines()[0]}")
        print(f"  {name}: SDK REJECTED — {err.splitlines()[0][:90]}")
        continue
    # Find the doc payload with the same omni type + same reference count.
    want_omni = p.get("omni_reference_task_type")
    match = None
    for d in payloads:
        if d.get("omni_reference_task_type") != want_omni:
            continue
        if len(d["content"]) != len(p["content"]):
            continue
        match = d
        break
    if match is None:
        warns.append(f"no doc block matches the SDK payload for {name}")
        print(f"  {name}: no matching doc block")
        continue
    diffs = []
    for k in ("model", "ratio", "duration", "resolution", "omni_reference_task_type",
              "output_format", "generate_audio"):
        if match.get(k) == p.get(k):
            continue
        if (name, k) in ALLOWED_DIVERGENCES:
            print(f"  {name}: {k} differs as documented — {ALLOWED_DIVERGENCES[(name, k)]}")
            continue
        diffs.append(f"{k}: doc={match.get(k)!r} sdk={p.get(k)!r}")
    if diffs:
        fails.append(f"{name}: doc/SDK mismatch — {'; '.join(diffs)}")
        print(f"  {name}: MISMATCH — {'; '.join(diffs)}")
    else:
        print(f"  {name}: matches SDK")

# --------------------------------------------------------------------------
# 3. Cited task ids must exist with the claimed outcome
# --------------------------------------------------------------------------
print("\nCited task ids:")
claims = re.findall(
    r"`(cgt-[0-9a-z-]+)` → `(\w+)`(?:, \*{0,2}([0-9]+)s[^`]*`([^`]+)`)?", MD)
seen = set()
for tid, status, dur, ratio in claims:
    if tid in seen:
        continue
    seen.add(tid)
    try:
        r = client.check_task(tid)
    except SeedanceError as exc:
        fails.append(f"{tid}: cannot fetch — {exc}")
        print(f"  {tid}: FETCH FAILED — {str(exc)[:80]}")
        continue
    problems = []
    if r.status != status:
        problems.append(f"status doc={status} api={r.status}")
    if dur and r.duration is not None and int(dur) != r.duration:
        problems.append(f"duration doc={dur} api={r.duration}")
    if ratio and r.ratio and ratio != r.ratio:
        problems.append(f"ratio doc={ratio} api={r.ratio}")
    if problems:
        fails.append(f"{tid}: {'; '.join(problems)}")
        print(f"  {tid}: MISMATCH — {'; '.join(problems)}")
    else:
        print(f"  {tid}: {r.status}, {r.duration}s, {r.ratio} — matches")

# Any task id mentioned but not in a claim line
all_ids = set(re.findall(r"cgt-[0-9a-z-]+", MD))
for tid in sorted(all_ids - seen):
    print(f"  {tid}: mentioned without a structured claim (not checked)")

print("\n" + "=" * 60)
if fails:
    print(f"FAILURES ({len(fails)}):")
    for f in fails:
        print("  -", f)
else:
    print("No failures.")
if warns:
    print(f"Warnings ({len(warns)}):")
    for w in warns:
        print("  -", w)
