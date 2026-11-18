import json
from types import SimpleNamespace

import pytest

from lib import digest, digest_anthropic, digest_openrouter


def story(i, description=""):
    return {"id": i, "title": f"Headline {i}", "news_source": f"pub{i}.com", "description": description}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ["DIGEST_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODELS",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"]:
        monkeypatch.delenv(name, raising=False)


# --- shared --------------------------------------------------------------------

def test_prompt_lists_ids_and_truncates_long_descriptions():
    prompt = digest.build_prompt("2025-03-01", [story(7, "word " * 200), story(8)])
    assert "[7] Headline 7 (pub7.com)" in prompt
    assert "[8] Headline 8 (pub8.com)" in prompt
    assert max(len(line) for line in prompt.splitlines()) < 420


def test_prompt_caps_story_count():
    prompt = digest.build_prompt("2025-03-01", [story(i) for i in range(100)])
    assert f"[{digest.MAX_STORIES - 1}]" in prompt
    assert f"[{digest.MAX_STORIES}]" not in prompt


@pytest.mark.parametrize("text", [
    '{"summary": "S", "top_story_ids": [1]}',
    '```json\n{"summary": "S", "top_story_ids": [1]}\n```',
    'Here is the brief:\n{"summary": "S", "top_story_ids": [1]}\nHope that helps.',
])
def test_parse_json_text_tolerates_fences_and_prose(text):
    assert digest.parse_json_text(text) == {"summary": "S", "top_story_ids": [1]}


@pytest.mark.parametrize("text", ["", "no json here", "{not: json}"])
def test_parse_json_text_rejects_garbage(text):
    with pytest.raises(digest.DigestError):
        digest.parse_json_text(text)


def cited(*paragraphs):
    """Model output in the citation schema: each paragraph a list of (text, ids)."""
    return {"paragraphs": [{"sentences": [{"text": t, "story_ids": ids} for t, ids in p]} for p in paragraphs]}


def test_validate_keeps_sentence_citations_and_builds_the_plain_summary():
    data = cited(
        [(" First. ", [1, 2]), ("Second.", [3])],
        [("Third.", [2])],
    ) | {"top_story_ids": [1]}
    result = digest.validate(data, allowed_ids={1, 2, 3})
    assert result == {
        "summary": "First. Second.\n\nThird.",
        "paragraphs": [
            [{"text": "First.", "story_ids": [1, 2]}, {"text": "Second.", "story_ids": [3]}],
            [{"text": "Third.", "story_ids": [2]}],
        ],
        "top_story_ids": [1],
    }


def test_validate_cleans_citations_without_dropping_sentences():
    data = cited(
        [("Unknown, duplicate and non-int ids go.", [9, 1, 1, "2", 2, 3, 4])],
        [("  ", [1])],  # empty sentence, so the paragraph goes too
        [("Uncited stays.", [])],
    ) | {"top_story_ids": []}
    result = digest.validate(data, allowed_ids={1, 2, 3, 4})
    assert result["paragraphs"] == [
        [{"text": "Unknown, duplicate and non-int ids go.", "story_ids": [1, 2, 3]}],  # capped at 3
        [{"text": "Uncited stays.", "story_ids": []}],
    ]


def test_validate_drops_unknown_duplicate_and_non_int_top_story_ids():
    result = digest.validate(cited([("A day.", [1])]) | {"top_story_ids": [3, 99, 3, "1", 1]}, allowed_ids={1, 2, 3})
    assert result["top_story_ids"] == [3, 1]


def test_validate_accepts_a_plain_summary_without_citations():
    # A model that ignores the schema (e.g. on the plain retry) still yields a digest.
    result = digest.validate({"summary": " A day. ", "top_story_ids": [1]}, allowed_ids={1})
    assert result == {"summary": "A day.", "paragraphs": None, "top_story_ids": [1]}


@pytest.mark.parametrize("data", [
    {"summary": "  ", "top_story_ids": []},
    {"top_story_ids": [1]},
    {"paragraphs": [{"sentences": [{"text": " ", "story_ids": [1]}]}], "top_story_ids": []},
    ["x"],
])
def test_validate_rejects_missing_summary(data):
    with pytest.raises(digest.DigestError):
        digest.validate(data, allowed_ids={1})


def test_provider_selection(monkeypatch):
    assert digest.provider() is None and not digest.is_configured()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert digest.provider() == "anthropic"
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert digest.provider() == "openrouter"  # the free option wins when both are set
    monkeypatch.setenv("DIGEST_PROVIDER", "Anthropic")
    assert digest.provider() == "anthropic"


def test_generate_refuses_empty_days(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    with pytest.raises(digest.DigestError):
        digest.generate_digest("2025-03-01", [])


# --- OpenRouter ----------------------------------------------------------------

class FakeHttpResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.bodies = []

    def post(self, url, json=None, headers=None, timeout=None):
        assert url == digest_openrouter.API_URL
        assert headers["Authorization"] == "Bearer test-key"
        self.bodies.append(json)
        return self.responses.pop(0)


def completion(content, model="upstage/solar-pro-3:free", finish_reason="stop"):
    return FakeHttpResponse({"model": model, "choices": [{"message": {"content": content}, "finish_reason": finish_reason}]})


@pytest.fixture
def openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


def test_openrouter_uses_the_free_router_and_records_the_serving_model(openrouter_key):
    output = json.dumps(cited([("S.", [2])]) | {"top_story_ids": [2]})
    session = FakeSession(completion(output, model="upstage/solar-pro-3:free"))
    result = digest_openrouter.generate("2025-03-01", [story(1), story(2)], session=session)

    # The stored model is the one that wrote the summary, not the router id.
    assert result == {
        "summary": "S.",
        "paragraphs": [[{"text": "S.", "story_ids": [2]}]],
        "top_story_ids": [2],
        "model": "upstage/solar-pro-3:free",
    }
    body = session.bodies[0]
    assert body["model"] == "openrouter/free"
    assert "models" not in body
    assert body["response_format"]["json_schema"]["schema"] == digest.OUTPUT_SCHEMA
    assert body["messages"][0] == {"role": "system", "content": digest.SYSTEM_PROMPT}
    # Reasoning models must leave room for the answer (reasoning counts against max_tokens).
    assert body["reasoning"] == {"effort": "low", "exclude": True}
    assert body["max_tokens"] >= 8000


def test_openrouter_models_override_becomes_a_fallback_list(openrouter_key, monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODELS", "a/b:free, c/d:free")
    session = FakeSession(completion('{"summary": "S.", "top_story_ids": []}', model="c/d:free"))
    result = digest_openrouter.generate("2025-03-01", [story(1)], session=session)
    assert session.bodies[0]["models"] == ["a/b:free", "c/d:free"]
    assert "model" not in session.bodies[0]
    assert result["model"] == "c/d:free"


def test_openrouter_single_override_uses_model_field(openrouter_key, monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODELS", "google/gemma-4-31b-it:free")
    session = FakeSession(completion('{"summary": "S.", "top_story_ids": []}'))
    digest_openrouter.generate("2025-03-01", [story(1)], session=session)
    assert session.bodies[0]["model"] == "google/gemma-4-31b-it:free"


def test_openrouter_retries_when_a_model_thinks_until_max_tokens(openrouter_key):
    output = json.dumps(cited([("S.", [1])]) | {"top_story_ids": [1]})
    session = FakeSession(
        completion(None, model="slow/thinker:free", finish_reason="length"),
        completion(output, model="fast/writer:free"),
    )
    result = digest_openrouter.generate("2025-03-01", [story(1)], session=session)
    assert result["model"] == "fast/writer:free"
    assert all("response_format" in body for body in session.bodies)


def test_openrouter_last_attempt_drops_structured_output(openrouter_key):
    rejected = lambda: FakeHttpResponse({"error": {"message": "response_format not supported"}}, status=400)  # noqa: E731
    session = FakeSession(rejected(), rejected(), completion('Sure! {"summary": "S.", "top_story_ids": [1]}'))
    result = digest_openrouter.generate("2025-03-01", [story(1)], session=session)
    assert result["summary"] == "S."
    assert ["response_format" in body for body in session.bodies] == [True, True, False]


def test_openrouter_gives_up_after_the_last_attempt(openrouter_key):
    limited = lambda: FakeHttpResponse({"error": {"message": "rate limited"}}, status=429)  # noqa: E731
    session = FakeSession(*(limited() for _ in digest_openrouter.ATTEMPTS))
    with pytest.raises(digest.DigestError, match="429"):
        digest_openrouter.generate("2025-03-01", [story(1)], session=session)
    assert session.responses == []


def test_openrouter_rejects_truncated_output_and_names_the_model(openrouter_key):
    session = FakeSession(*(
        completion('{"summary": "S', model="slow/thinker:free", finish_reason="length")
        for _ in digest_openrouter.ATTEMPTS
    ))
    with pytest.raises(digest.DigestError, match="slow/thinker:free"):
        digest_openrouter.generate("2025-03-01", [story(1)], session=session)


# --- Anthropic -----------------------------------------------------------------

def claude_response(payload, stop_reason="end_turn", model="claude-opus-5-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        model=model,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(payload))],
    )


class FakeAnthropic:
    def __init__(self, response):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._response = response

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_anthropic_request_uses_structured_output_and_fallbacks():
    client = FakeAnthropic(claude_response(cited([("S.", [1, 2])]) | {"top_story_ids": [2]}))
    result = digest_anthropic.generate("2025-03-01", [story(1), story(2)], client=client)

    assert result == {
        "summary": "S.",
        "paragraphs": [[{"text": "S.", "story_ids": [1, 2]}]],
        "top_story_ids": [2],
        "model": "claude-opus-5-5",
    }
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["schema"] == digest.OUTPUT_SCHEMA
    assert call["fallbacks"] == "default"
    assert "thinking" not in call and "temperature" not in call


def test_anthropic_haiku_skips_unsupported_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    client = FakeAnthropic(claude_response({"summary": "S.", "top_story_ids": []}, model="claude-haiku-5-5"))
    digest_anthropic.generate("2025-03-01", [story(1)], client=client)
    assert client.calls[0]["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in client.calls[0] and "betas" not in client.calls[0]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_anthropic_rejects_refusals_and_truncation(stop_reason):
    client = FakeAnthropic(claude_response({"summary": "S.", "top_story_ids": []}, stop_reason=stop_reason))
    with pytest.raises(digest.DigestError):
        digest_anthropic.generate("2025-03-01", [story(1)], client=client)
