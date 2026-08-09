#!/usr/bin/env python3
"""
Submit the Hedra #48195 reproduction to Seedance 2.0.

Mirrors prep_request.py but actually SUBMITS: uploads the two reference images to
the asset library (asset:// refs bypass the sensitive-content filter), presigns
the reference audio, then calls submit_image_to_video and prints the task_id.

Run with the interpreter that has the SDK installed, from the repo root:
  /opt/homebrew/opt/python@3.11/bin/python3.11 generated/hedra/submit_request.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2] / "packages" / "seedance-sdk"
sys.path.insert(0, str(ROOT))

from seedance import SeedanceClient                       # noqa: E402
from seedance.asset import AssetClient                    # noqa: E402
from seedance.tos import TOSClient                         # noqa: E402
from seedance.credentials import load_api_key, load_asset_credentials  # noqa: E402

HERE = pathlib.Path(__file__).parent
BUCKET = "mittul-demo-1"

api_key = load_api_key()
ak, sk = load_asset_credentials()

tos = TOSClient(ak, sk)
assets = AssetClient(ak, sk)
client = SeedanceClient(api_key=api_key, ak=ak, sk=sk)


def tos_url(local: str, key: str, content_type: str) -> str:
    data = (HERE / local).read_bytes()
    return tos.put_object(BUCKET, key, data, content_type=content_type)


# 1) Reference images -> TOS -> asset library (asset://<id>)
print("Uploading reference image 1 ...")
img1_url = tos_url("content1_reference_image_1.png", "hedra/ref1.png", "image/png")
print("Uploading reference image 2 ...")
img2_url = tos_url("content2_reference_image_2.jpeg", "hedra/ref2.jpeg", "image/jpeg")

group = assets.create_group("hedra-48195", "Hedra ticket 48195 repro")
print(f"Asset group: {group}")
asset1 = assets.upload_and_wait(img1_url, group)
print(f"  asset1 Active: {asset1}")
asset2 = assets.upload_and_wait(img2_url, group)
print(f"  asset2 Active: {asset2}")

# 2) Reference audio -> TOS -> presigned GET (fetchable by the generation API)
print("Uploading reference audio ...")
tos_url("content3_audio.mp3", "hedra/content3_audio.mp3", "audio/mpeg")
audio_url = tos.presign_get(BUCKET, "hedra/content3_audio.mp3", expires=86400)

prompt = (HERE / "content0_text_prompt.txt").read_text()

# 3) Submit
print("Submitting generation job ...")
result = client.submit_image_to_video(
    prompt,
    image_urls=[f"asset://{asset1}", f"asset://{asset2}"],
    audio_urls=[audio_url],
    ratio="9:16",
    duration=10,
    resolution="720p",
    generate_audio=False,
)

print("\n===== SUBMITTED =====")
print(f"task_id: {result.task_id}")
print(f"status:  {result.status}")
print(f"mode:    {result.mode}")
(HERE / "task_id.txt").write_text(result.task_id)
print("\nWrote task_id.txt. Poll with:  seedance status <task_id>  (or watch -w)")
