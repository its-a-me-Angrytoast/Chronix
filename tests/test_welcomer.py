import pytest

from chronix_bot.utils import welcomer as wl


def _fake_member(guild_name="TestGuild", name="Alice", display_name="Alice"):
    class G:
        name = guild_name

    class M:
        pass

    m = M()
    m.guild = G()
    m.name = name
    m.display_name = display_name
    m.mention = "@Alice"
    return m


def test_format_message_basic():
    m = _fake_member()
    tpl = "Welcome {mention} to {server}! Invited by {inviter_mention}"
    s = wl.format_message(tpl, m, inviter_id=123, inviter_mention="@Bob")
    assert "@Alice" in s and "TestGuild" in s and "@Bob" in s


def test_generate_banner_fallback():
    m = _fake_member()
    b = wl.generate_banner_bytes(m)
    # May be None if PIL not installed; ensure function doesn't raise
    assert (b is None) or isinstance(b, (bytes, bytearray))
