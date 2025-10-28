"""Small helpers and embed templates for Phase 1."""
from typing import Dict, Optional
import discord

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

