"""Small helpers and embed templates used across cogs.

This module centralizes embed styling so all cogs present a consistent
visual theme. The `make_embed` helper adds a default colour, timestamp and
footer. Callers may override the colour with the `colour` argument.
"""
from typing import Dict, Optional
import discord
import re
from datetime import datetime


# Basic emoji map used by economy / UI helpers
EMOJI: Dict[str, str] = {
    "chrons": "💠",
    "gems": "💎",
    "pets": "🐾",
}


# Default theme colour (hex). Change to match your brand.
DEFAULT_COLOUR = 0x5B6EAE
_FOOTER_TEXT = "Chronix"


def make_embed(title: str, description: str, colour: Optional[int] = None) -> discord.Embed:
    """Create a small embed used by many commands.

    Embeds produced by this helper include a consistent colour (unless
    overridden), a timestamp and a footer to help with visual consistency.

    Args:
        title: embed title
        description: embed body
        colour: optional integer colour (0xRRGGBB)
    """
    e = discord.Embed(title=title, description=description)
    e.colour = colour if colour is not None else DEFAULT_COLOUR
    e.timestamp = datetime.utcnow()
    # keep footer minimal — can be expanded to include version or shard.
    e.set_footer(text=_FOOTER_TEXT)
    return e


def latency_embed(latency_ms: int) -> discord.Embed:
    return make_embed("Pong!", f"Latency: {latency_ms}ms")


def format_chrons(amount: int) -> str:
<<<<<<< Updated upstream
    """Format a chron amount with emoji."""
    return f"{EMOJI['chrons']} {amount}"


def parse_duration(s: str) -> int:
    """Parse simple duration strings like '1d2h30m45s' into seconds.

    Accepts numbers followed by d/h/m/s. Returns total seconds or raises ValueError.
    """
    if not s or not isinstance(s, str):
        raise ValueError("Invalid duration")
    pattern = r"(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$"
    m = re.match(pattern, s)
    if not m:
        raise ValueError("Invalid duration format. Use e.g. 1d2h30m, 45m, 30s")
    days = int(m.group('days')) if m.group('days') else 0
    hours = int(m.group('hours')) if m.group('hours') else 0
    minutes = int(m.group('minutes')) if m.group('minutes') else 0
    seconds = int(m.group('seconds')) if m.group('seconds') else 0
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        raise ValueError("Duration must be greater than zero")
    return total
=======
    """Format a Chrons amount with emoji and thousands separators.

    Examples:
        format_chrons(1234) -> '💠 1,234'
    """
    try:
        n = int(amount)
    except Exception:
        return f"{EMOJI.get('chrons', '')} {amount}"
    return f"{EMOJI.get('chrons', '')} {n:,}"
>>>>>>> Stashed changes

