# Aspect Ratio & Delivery

Two jobs: pick the **creative frame** (the emotion — see also
[`visual-language.md`](visual-language.md) §1) and plan the **delivery
containers** (where it ships). Keep the two separate.

## Creative frame (emotion)

| Ratio | Reads as | Compose for |
|-------|----------|-------------|
| 2.39:1 | epic scale, isolation | wide negative space; hero large enough to survive generation/review |
| 1.85:1 | modern theatrical, balanced | performance headroom without scope's extremity |
| 16:9 | web/broadcast default | strongest general cinematic frame |
| 4:3 / 1.33 | trapped, vintage, boxed-in | tight verticals, the frame closing in |
| 1:1 | symmetrical product/social grid | centered, balanced |
| 4:5 | social feed | headroom + caption room |
| 9:16 | vertical, subjective phone-POV | center the hero, avoid edge-critical action |

Say the ratio and the composition goal **early** in the prompt — it's an
"earliest strong instruction" lever ([`prompt-guidance.md`](prompt-guidance.md)).

## Delivery container (where it ships)

Separate the composition from the platform:

| Layer | Decision |
|-------|----------|
| Creative ratio | the frame the shot is designed for |
| Container | web / broadcast / DCP / social / pitch deck |
| Safe area | where faces, products, captions, logos stay readable |
| Reframe plan | crop / letterbox / pillarbox / alternate render |
| Text policy | on-screen text usually added in post, not generated into motion |

## Campaign version matrix (commercial work)

| Version | Purpose | Planning |
|---------|---------|----------|
| 30s hero | full story | more shots, full arc, strongest product proof |
| 15s cutdown | paid social/broadcast | keep hook + product proof + end state |
| 10s / 6s bumper | recall / fast placement | one beat + final product or title card |
| 9:16 vertical | mobile | center action, captions lower-third |
| 1:1 / 4:5 | feed | product and face readable without edge detail |
| textless | localization / VFX | no burned-in copy, captions, or end-card text |

## Multi-crop framing rules

- If several crops are needed, keep faces, products, and logos **away from the
  edges** so one render survives multiple reframes.
- For vertical, simplify camera moves and avoid fast lateral action that exits
  frame.
- For 2.39 / very wide, keep the hero large enough to survive generation.
- Title cards, packshots, captions, legal text → clean visual plate + post-added
  typography, not generated text.

## What the API accepts (`--ratio` / `ratio=`)

The creative table above is design vocabulary; the API takes a fixed set:
`21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `adaptive`. Map 2.39:1 and 1.85:1
onto `21:9`, and 4:5 onto `3:4`, then compose for the difference.

The SDK/CLI/MCP default is `auto`, which is **not** an API value — it resolves
to `adaptive` for task types that require it and `16:9` otherwise. Leaving
`ratio` unset is the safe move.

### Ratio is locked for three task types on Seedance 2.5

| Task type | Ratio | Why |
|---|---|---|
| First frame / first+last frame | **`adaptive` only** | Output matches the first-frame image |
| Video edit | **`adaptive` only** | Output matches the clip being edited |
| Video extend | **`adaptive` only** | Output matches the clip being extended |
| Text-to-video, reference-to-video | any value | Nothing to inherit from |

Passing `16:9` to a first-frame job on 2.5 raises a `ValidationError` before
submission. If it reaches the API — because the model classified an edit or
extend from the *prompt* rather than the parameters — it comes back as
`InvalidParameter.TaskTypeConstraint` **asynchronously**, after the task has
queued and been consumed. Seedance 2.0 had none of these restrictions.

**Practical consequence:** on 2.5 you choose the delivery ratio when you make
the *source* asset, not when you animate it. A 9:16 vertical cut of a
16:9 first-frame job is a post-production crop, not a generation parameter.

### Pixel dimensions

| Ratio | 480p | 720p |
|---|---|---|
| 16:9 | 854×480 | 1280×720 |
| 4:3 | 752×560 | 1112×834 |
| 1:1 | 640×640 | 960×960 |
| 3:4 | 560×752 | 834×1112 |
| 9:16 | 480×854 | 720×1280 |
| 21:9 | 992×432 | 1470×630 |

Seedance 2.5 has no 1080p tier. For a higher-resolution master, generate at
720p and finish with `byteplus_upscale_video` (up to 4K) — that path beats
Seedance 2.0's native 1080p on detail. Only drop back to `--model 2.0` when you
specifically need 1080p straight out of generation.

## Caveat

Plan ratio and crop strategy here, but the buyer / broadcaster / festival spec
controls the final master — verify it before export.
