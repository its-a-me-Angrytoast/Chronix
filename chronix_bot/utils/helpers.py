"""Small helpers and embed templates for Phase 1."""
from typing import Dict, Optional
import discord
import re
from datetime import timedelta

EMOJI: Dict[str, str] = {
    "chrons": "💠",
    "gems": "💎",
    "pets": "🐾",
}


def make_embed(title: str, description: str, colour: Optional[int] = None) -> discord.Embed:
    """Create a small embed used by many commands.

    Args:
        title: embed title
        description: embed body
        colour: optional integer colour
    """
    e = discord.Embed(title=title, description=description)
    if colour is not None:
        e.colour = colour
    return e


def latency_embed(latency_ms: int) -> discord.Embed:
    return make_embed("Pong!", f"Latency: {latency_ms}ms")


def format_chrons(amount: int) -> str:
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

