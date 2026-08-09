#!/usr/bin/env python3
"""Submit 5 more Hedra #48195 runs, reusing the existing asset refs + audio."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2] / "packages" / "seedance-sdk"
sys.path.insert(0, str(ROOT))

from seedance import SeedanceClient                       # noqa: E402
from seedance.tos import TOSClient                         # noqa: E402
from seedance.credentials import load_api_key, load_asset_credentials  # noqa: E402

HERE = pathlib.Path(__file__).parent
BUCKET = "mittul-demo-1"

# Assets already created + Active from the first run — reuse them.
ASSET1 = "asset-20260722172156-c6d4q"
ASSET2 = "asset-20260722172208-kdkc4"

api_key = load_api_key()
ak, sk = load_asset_credentials()
tos = TOSClient(ak, sk)
client = SeedanceClient(api_key=api_key, ak=ak, sk=sk)

audio_url = tos.presign_get(BUCKET, "hedra/content3_audio.mp3", expires=86400)
prompt = (HERE / "content0_text_prompt.txt").read_text()

seeds = [101, 202, 303, 404, 505]
task_ids = []
for s in seeds:
    r = client.submit_image_to_video(
        prompt,
        image_urls=[f"asset://{ASSET1}", f"asset://{ASSET2}"],
        audio_urls=[audio_url],
        ratio="9:16",
        duration=10,
        resolution="720p",
        generate_audio=True,
        seed=s,
    )
    print(f"seed={s:<4}  task_id={r.task_id}  status={r.status}")
    task_ids.append(r.task_id)

(HERE / "batch_task_ids.txt").write_text("\n".join(task_ids) + "\n")
print("\nWrote batch_task_ids.txt")
