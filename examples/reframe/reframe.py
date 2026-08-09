"""Seedance prompt reframer — backend service for a canvas studio UI.

Loads the ENTIRE Seedance skill (seedance.md + every references/*.md) into one
prompt-cached system prompt, then asks Claude to run the skill's mandatory
optimization pipeline on a raw user prompt and return the optimized prompt as
structured JSON — ready to hand to `seedance_generate` (MCP) or the SDK.

This reproduces the *prompt-reframing brain* of the skill outside Claude Code.
The skill's interactive bits (Director's Card confirmation, asset uploads, task
tracking) are explicitly overridden — this runs non-interactively and returns
data, not a chat turn.

Install:
    pip install "anthropic>=0.40"

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python reframe.py "a woman smiles softly, camera slowly pushes in" --ratio 9:16
"""

from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

# claude-opus-4-8 is the skill's default and the most capable model for this.
MODEL = "claude-opus-4-8"

# The skill lives at <repo>/skills. examples/reframe/reframe.py -> ../../skills
SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


# --------------------------------------------------------------------------- #
# 1. Inline the entire skill into one cached system prompt
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=1)
def build_system_prompt() -> str:
    """Concatenate seedance.md + every references/*.md into one string.

    Cached in-process: the bytes are identical on every call, which is also
    what lets Anthropic prompt-caching reuse the prefix across API requests.
    """
    parts: list[str] = []

    router = SKILLS_DIR / "seedance.md"
    parts.append(f"===== FILE: seedance.md =====\n{router.read_text()}")

    # Sort for a deterministic, cache-stable order (any reordering would bust
    # the prompt cache — see shared/prompt-caching.md).
    for ref in sorted((SKILLS_DIR / "references").glob("*.md")):
        parts.append(f"===== FILE: references/{ref.name} =====\n{ref.read_text()}")

    skill = "\n\n".join(parts)

    # Override the skill's interactive contract for non-interactive backend use.
    override = """
===== RUNTIME OVERRIDE (operator instruction — takes precedence) =====

You are running as a NON-INTERACTIVE prompt-optimization service inside a
backend, not as an interactive Claude Code session. Apply the skill above as
follows:

- Run MANDATORY PRE-FLIGHT RULE #1 (the references/prompt-guidance.md
  6-component optimization pipeline) plus prompt-prose-craft.md and
  duration-calculus.md on the user's raw input. These are still mandatory.
- Do NOT print a Director's Card, do NOT ask the user to confirm, do NOT call
  any seedance_* / MCP tools, do NOT upload assets. There is no human in the
  loop on this turn.
- If references are supplied, tag every one in the optimized prompt as
  [image1], [video1], [audio1], ... (1-indexed, in the order given), exactly
  as the skill requires.
- Compute --duration with duration-calculus.md; never guess it.
- Return ONLY the structured JSON result. The optimized prompt is the single
  most important field — it must be submission-ready for Seedance 2.0.
"""
    return skill + "\n\n" + override


# --------------------------------------------------------------------------- #
# 2. Structured output schema the UI consumes
# --------------------------------------------------------------------------- #
class ReframedPrompt(BaseModel):
    optimized_prompt: str = Field(
        description="The submission-ready Seedance 2.0 prompt, one paragraph "
        "(or Shot N: blocks for multi-shot), with reference tags applied."
    )
    duration_seconds: int = Field(
        description="Computed --duration via duration-calculus.md, clamped 4-15."
    )
    ratio: str = Field(description='Aspect ratio, e.g. "16:9" or "9:16".')
    reference_tags: list[str] = Field(
        default_factory=list,
        description='Tags used, e.g. ["image1", "audio1"]. Empty if none.',
    )
    changes: str = Field(
        description="One-sentence note on what the optimization added/fixed."
    )


# --------------------------------------------------------------------------- #
# 3. The call
# --------------------------------------------------------------------------- #
def reframe(
    raw_prompt: str,
    *,
    ratio: str | None = None,
    references: list[str] | None = None,
    client: anthropic.Anthropic | None = None,
) -> ReframedPrompt:
    """Reframe a raw user prompt into a Seedance-ready prompt.

    Args:
        raw_prompt: The user's natural-language idea.
        ratio: Optional desired aspect ratio hint ("16:9", "9:16", ...).
        references: Optional ordered list of reference descriptions/URLs. Their
            1-indexed positions become [image1]/[video1]/[audio1] tags.
    """
    client = client or anthropic.Anthropic()

    user_lines = [f"Raw prompt to optimize:\n{raw_prompt}"]
    if ratio:
        user_lines.append(f"\nDesired ratio: {ratio}")
    if references:
        listed = "\n".join(f"  {i + 1}. {r}" for i, r in enumerate(references))
        user_lines.append(f"\nReferences (tag these in order):\n{listed}")

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},  # let the model reason through the pipeline
        system=[
            {
                "type": "text",
                "text": build_system_prompt(),
                # Cache the ~40K-token skill prefix; ~0.1x cost on repeat calls.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": "\n".join(user_lines)}],
        output_format=ReframedPrompt,
    )

    # Surface cache effectiveness for ops visibility.
    u = response.usage
    print(
        f"[tokens] input={u.input_tokens} "
        f"cache_write={u.cache_creation_input_tokens} "
        f"cache_read={u.cache_read_input_tokens} output={u.output_tokens}"
    )

    result = response.parsed_output
    if result is None:
        raise RuntimeError(f"Model did not return valid structured output: {response.stop_reason}")
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Reframe a prompt for Seedance 2.0.")
    parser.add_argument("prompt", help="Raw natural-language prompt")
    parser.add_argument("--ratio", help='Aspect ratio hint, e.g. "9:16"')
    parser.add_argument(
        "--ref",
        action="append",
        dest="references",
        metavar="DESC",
        help="A reference (repeatable); position becomes [image1]/[video1]/...",
    )
    args = parser.parse_args()

    result = reframe(args.prompt, ratio=args.ratio, references=args.references)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
