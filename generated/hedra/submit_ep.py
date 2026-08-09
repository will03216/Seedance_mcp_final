#!/usr/bin/env python3
"""Submit to a custom endpoint (content filter disabled), Dialogue line removed, generate_audio=True."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2] / "packages" / "seedance-sdk"
sys.path.insert(0, str(ROOT))

from seedance import SeedanceClient                       # noqa: E402
from seedance.tos import TOSClient                         # noqa: E402
from seedance.credentials import load_api_key, load_asset_credentials  # noqa: E402
from seedance.config import SUBMIT_TIMEOUT                 # noqa: E402

HERE = pathlib.Path(__file__).parent
BUCKET = "mittul-demo-1"
MODEL = "ep-20260722180039-wnh2c"          # custom endpoint, content filter disabled

# Reuse the already-Active reference assets from the first run.
ASSET1 = "asset-20260722172156-c6d4q"
ASSET2 = "asset-20260722172208-kdkc4"

api_key = load_api_key()
ak, sk = load_asset_credentials()
tos = TOSClient(ak, sk)
client = SeedanceClient(api_key=api_key, ak=ak, sk=sk)

audio_url = tos.presign_get(BUCKET, "hedra/content3_audio.mp3", expires=86400)

# Prompt with the Dialogue: "None" line removed.
raw = (HERE / "content0_text_prompt.txt").read_text()
prompt = "\n".join(l for l in raw.splitlines() if l.strip() != 'Dialogue: "None"')
(HERE / "prompt_no_dialogue.txt").write_text(prompt)
assert 'Dialogue: "None"' not in prompt, "Dialogue line not removed"

payload = {
    "model": MODEL,
    "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"asset://{ASSET1}"}, "role": "reference_image"},
        {"type": "image_url", "image_url": {"url": f"asset://{ASSET2}"}, "role": "reference_image"},
        {"type": "audio_url", "audio_url": {"url": audio_url}, "role": "reference_audio"},
    ],
    "ratio": "9:16",
    "duration": 10,
    "resolution": "720p",
    "generate_audio": True,
    "watermark": False,
}

resp = client._http("/contents/generations/tasks", method="POST", payload=payload, timeout=SUBMIT_TIMEOUT)
task_id = resp.get("id") or resp.get("task_id", "")
print(f"model:   {MODEL}")
print(f"task_id: {task_id}")
print(f"status:  {resp.get('status', 'queued')}")
(HERE / "ep_task_id.txt").write_text(task_id)
