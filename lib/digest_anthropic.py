"""Daily digest via Claude (Anthropic API). Select with DIGEST_PROVIDER=anthropic.

Configuration:
  ANTHROPIC_API_KEY  required (or an `ant auth login` profile)
  ANTHROPIC_MODEL    optional, default claude-opus-5-5. claude-haiku-5-5 costs
                     ~$0.05/month for one digest a day.
"""

import os

import anthropic

from lib.digest import OUTPUT_SCHEMA, SYSTEM_PROMPT, DigestError, build_prompt, parse_json_text, validate

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept the server-side refusal fallback (`fallbacks="default"`).
_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5"}


def model():
    return os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL


def parse_response(response, allowed_ids):
    if response.stop_reason == "refusal":
        raise DigestError("model declined to write the digest")
    if response.stop_reason == "max_tokens":
        raise DigestError("digest was cut off at max_tokens")
    text = next((b.text for b in reversed(response.content) if b.type == "text"), None)
    return validate(parse_json_text(text), allowed_ids)


def generate(date, stories, client=None):
    client = client or anthropic.Anthropic()
    name = model()
    kwargs = {}
    if name in _FALLBACK_MODELS:
        # If a safety classifier declines (news about violence or extremism can
        # trip one), the API retries on its default fallback model instead of
        # leaving the day without a digest.
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    response = client.beta.messages.create(
        model=name,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(date, stories)}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        **kwargs,
    )
    result = parse_response(response, {s["id"] for s in stories})
    result["model"] = response.model
    return result
