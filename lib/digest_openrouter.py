"""Daily digest via OpenRouter's free models ($0).

By default the request goes to OpenRouter's Free Router (`openrouter/free`,
https://openrouter.ai/docs/guides/routing/routers/free-router): it picks a
currently available free model at random, from those that support what the
request needs (here, structured output), so there's no list of free model ids to
keep up to date as they come and go. The response's `model` field names the
model that actually served the request; that's what gets stored with the digest
and shown on the site.

A failed attempt (a model that thinks until max_tokens, ignores the schema and
returns prose, or a rate limit) is retried; see ATTEMPTS. The last attempt drops
`response_format` and relies on the prompt's "respond with only JSON". The JSON is validated the same way as the
Claude provider's (lib/digest.py). Reasoning is capped at low effort so a
thinking model can't spend the whole token budget before writing the answer.

Configuration:
  OPENROUTER_API_KEY   required
  OPENROUTER_MODELS    optional comma-separated model ids to use instead of the
                       Free Router, tried in order via OpenRouter's `models`
                       fallback list (e.g. "google/gemma-4-31b-it:free,...")
"""

import os

import requests

from lib.digest import OUTPUT_SCHEMA, SYSTEM_PROMPT, DigestError, build_prompt, parse_json_text, validate

API_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_ROUTER = "openrouter/free"


def models():
    raw = os.getenv("OPENROUTER_MODELS", "")
    configured = [m.strip() for m in raw.split(",") if m.strip()]
    return configured or [FREE_ROUTER]


def _request_body(date, stories, structured):
    chosen = models()
    body = {
        # A single id goes in `model`; several become OpenRouter's fallback list.
        **({"model": chosen[0]} if len(chosen) == 1 else {"models": chosen}),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(date, stories)},
        ],
        # Some free models reason before answering, and reasoning tokens count
        # against max_tokens: with no cap, one spent all 4000 thinking and wrote
        # nothing. effort "low" reserves ~20% of the limit for reasoning, leaving
        # ~6400 for the JSON; exclude keeps the reasoning text out of the
        # response. Models that don't reason ignore it.
        "max_tokens": 8000,
        "reasoning": {"effort": "low", "exclude": True},
    }
    if structured:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "daily_digest", "strict": True, "schema": OUTPUT_SCHEMA},
        }
    return body


def _post(body, session):
    response = session.post(
        API_URL,
        json=body,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            # Optional attribution headers OpenRouter uses for its app rankings.
            "HTTP-Referer": "https://trumpoftheday.com",
            "X-Title": "Trump of the Day",
        },
        timeout=120,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or "error" in payload:
        message = (payload.get("error") or {}).get("message") or response.text[:300]
        raise DigestError(f"OpenRouter {response.status_code}: {message}")
    return payload


def parse_response(payload, allowed_ids):
    choices = payload.get("choices") or []
    if not choices:
        raise DigestError("OpenRouter returned no choices")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        usage = payload.get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        raise DigestError(
            f"digest was cut off at max_tokens ({payload.get('model', 'unknown model')}: "
            f"{usage.get('completion_tokens')} output tokens, {reasoning} of them reasoning)"
        )
    content = (choice.get("message") or {}).get("content")
    return validate(parse_json_text(content), allowed_ids)


# Each attempt goes back through the router, which may pick a different model.
# Some free models ignore the reasoning cap and think until max_tokens (seen in
# about a third of attempts), so one retry wasn't enough. The last attempt drops
# response_format for models that reject it or ignore it and return prose,
# relying on the prompt's "respond with only JSON" instead.
ATTEMPTS = (True, True, False)  # structured?


def generate(date, stories, session=None):
    session = session or requests.Session()
    allowed = {s["id"] for s in stories}
    for attempt, structured in enumerate(ATTEMPTS, start=1):
        try:
            payload = _post(_request_body(date, stories, structured=structured), session)
            result = parse_response(payload, allowed)
            break
        except DigestError as error:
            if attempt == len(ATTEMPTS):
                raise
            print(f"  ↻ OpenRouter attempt {attempt} failed ({error}); retrying")
    # The model that actually wrote it (e.g. "upstage/solar-pro-3:free"), not the
    # router id; the site shows this next to the summary.
    result["model"] = payload.get("model") or models()[0]
    print(f"  🤖 Digest written by {result['model']}")
    return result
