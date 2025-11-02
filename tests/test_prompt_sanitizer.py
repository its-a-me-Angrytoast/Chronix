from chronix_bot.utils.prompt_sanitizer import sanitize_prompt


def test_sanitize_basic():
    prompt = "Hello, explain recursion. @everyone `rm -rf /`"
    sanitized, removed = sanitize_prompt(prompt)
    assert "everyone" not in sanitized
    assert "rm -rf" not in sanitized.lower()
    assert "backticks" in removed or any(x.startswith("danger:") for x in removed)


def test_truncation():
    long = "a" * 5000
    s, removed = sanitize_prompt(long)
    assert len(s) <= 2000
    assert "truncated" in removed
