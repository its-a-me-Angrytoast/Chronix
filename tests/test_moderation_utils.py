import pytest
from chronix_bot.cogs.moderation.moderation import parse_duration


def test_parse_duration_valid():
    assert parse_duration("1h") == 3600
    assert parse_duration("1h30m") == 5400
    assert parse_duration("45m") == 2700
    assert parse_duration("30s") == 30


def test_parse_duration_invalid():
    with pytest.raises(ValueError):
        parse_duration("5x")
