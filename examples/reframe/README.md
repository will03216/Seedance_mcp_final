# Seedance Prompt Reframer (backend service)

Reproduces the **prompt-reframing brain** of the [Seedance skill](../../skills/seedance.md)
outside Claude Code, so a UI (e.g. a canvas studio) can optimize a raw user
prompt before sending it to the Seedance 2.0 API.

It **inlines the entire skill** — `seedance.md` plus all 20 `references/*.md`
files — into one prompt-cached system prompt (~40K tokens), then calls
Claude (`claude-opus-4-8`) to run the skill's mandatory 6-component
optimization pipeline and returns the result as structured JSON.

## Why this exists

The skill's reframing logic is **not** code — it lives in markdown the model
reads. The MCP server and SDK pass `prompt` straight through to Seedance
unchanged. To reframe before generation, you need an LLM that has been given
the skill instructions. That's what this module is.

## Architecture

```
raw prompt (+ optional ratio, references)
        │
        ▼
  reframe.py ──► Claude (entire skill as cached system prompt)
        │                └─ runs prompt-guidance + prompt-prose-craft + duration-calculus
        ▼
  { optimized_prompt, duration_seconds, ratio, reference_tags, changes }
        │
        ▼
  your backend ──► seedance_generate (MCP)  OR  seedance-sdk  ← send optimized_prompt
```

The skill's interactive parts (Director's Card confirmation, asset uploads,
MCP tool calls) are overridden by a runtime instruction appended after the
skill — this runs non-interactively and returns data.

## Install & run

```bash
pip install "anthropic>=0.40"
export ANTHROPIC_API_KEY=sk-ant-...

python reframe.py "a woman smiles softly, camera slowly pushes in" --ratio 9:16

# With references — positions become [image1], [audio1], ...
python reframe.py "she lip-syncs to the track" \
  --ref "https://.../portrait.jpg" \
  --ref "https://.../vocals.wav"
```

## Use from your UI backend

```python
from reframe import reframe

result = reframe(user_prompt, ratio="16:9")
# result.optimized_prompt  -> send this to Seedance, NOT the raw user input
# result.duration_seconds, result.ratio, result.reference_tags, result.changes
```

## Cost note

The ~40K-token skill prefix is sent on every call but is **prompt-cached**
(`cache_control: ephemeral`), so after the first request the cached portion
bills at ~0.1×. The log line prints `cache_read` tokens so you can confirm the
cache is hitting; if it stays at 0, something is mutating the system prefix
(see [`shared/prompt-caching.md`](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)).

To trim cost/latency, you can later switch to inlining only the three
mandatory references (`prompt-guidance.md`, `prompt-prose-craft.md`,
`duration-calculus.md`) and loading the rest on demand — but per your choice
this loads the full skill for maximum coverage.
