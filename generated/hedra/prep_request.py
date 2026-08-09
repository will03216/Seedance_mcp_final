#!/usr/bin/env python3
"""
Prep the Hedra #48195 reproduction: upload assets, build the payload, PRINT it.
Does NOT submit — review the printed payload, then run the curl in the README.

Requires env: ARK_API_KEY, ARK_AK, ARK_SK  (see .env.example)
Run from repo root:  python generated/hedra/prep_request.py
"""
import json
import pathlib
import sys

# SDK on path
ROOT = pathlib.Path(__file__).resolve().parents[3] / "packages" / "seedance-sdk"
sys.path.insert(0, str(ROOT))

from seedance.tos import TosClient          # noqa: E402
from seedance.asset import AssetClient      # noqa: E402
from seedance.credentials import load_credentials  # noqa: E402

HERE = pathlib.Path(__file__).parent
BUCKET = "mittu-demo-1"

creds = load_credentials()                  # reads ARK_AK / ARK_SK / ARK_API_KEY
tos = TosClient(ak=creds.ak, sk=creds.sk)
assets = AssetClient(ak=creds.ak, sk=creds.sk)

def tos_url(local: str, key: str, content_type: str) -> str:
    data = (HERE / local).read_bytes()
    return tos.put_object(BUCKET, key, data, content_type=content_type)

# 1) Images -> TOS -> asset library (referenced as asset://<id>)
img1_url = tos_url("content1_reference_image_1.png", "hedra/ref1.png", "image/png")
img2_url = tos_url("content2_reference_image_2.jpeg", "hedra/ref2.jpeg", "image/jpeg")
group = assets.create_group("hedra-48195", "Hedra ticket 48195 repro")
asset1 = assets.upload_and_wait(img1_url, group)
asset2 = assets.upload_and_wait(img2_url, group)

# 2) Audio -> TOS bucket mittu-demo-1 (presigned so the generation API can fetch it)
tos_url("content3_audio.mp3", "hedra/content3_audio.mp3", "audio/mpeg")
audio_url = tos.presign_get(BUCKET, "hedra/content3_audio.mp3", expires=86400)

prompt = (HERE / "content0_text_prompt.txt").read_text()

payload = {
    "model": "dreamina-seedance-2-0-260128",   # set to your seedance-2.0-mini Ark mapping
    "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"asset://{asset1}"}, "role": "reference_image"},
        {"type": "image_url", "image_url": {"url": f"asset://{asset2}"}, "role": "reference_image"},
        {"type": "audio_url", "audio_url": {"url": audio_url}, "role": "reference_audio"},
    ],
    "ratio": "9:16",
    "duration": 10,
    "resolution": "720p",
    "generate_audio": False,
    "watermark": False,
}

print("\n===== FINAL PAYLOAD (review before submitting) =====\n")
print(json.dumps(payload, indent=2))
(HERE / "final_payload.json").write_text(json.dumps(payload, indent=2))
print("\nWrote final_payload.json. To submit, run the curl below yourself.\n")
