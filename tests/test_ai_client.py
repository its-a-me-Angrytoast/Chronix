from chronix_bot.utils.ai_client import generate_text, _mock_response


def test_mock_response_deterministic():
    r1 = generate_text("Hello world", seed=42)
    r2 = generate_text("Hello world", seed=42)
    assert r1["text"] == r2["text"]


def test_generate_text_structure():
    out = generate_text("Summarize this", mode="summarize", seed=7)
    assert isinstance(out, dict)
    assert "text" in out and "meta" in out
