"""Welcome system utilities: file-backed per-guild welcome settings and helpers.

Features:
- get/set per-guild config (channel, dm, template, auto_role, banner_enabled, xp_boost, starter_kit)
- format a welcome message with variables
- optional banner image generation using Pillow (if installed)
"""
from __future__ import annotations

import json
import os
import asyncio
from typing import Dict, Any, Optional

_LOCK = asyncio.Lock()
PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "welcome_configs.json")
PATH = os.path.normpath(PATH)


async def _ensure_file():
    d = os.path.dirname(PATH)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(PATH):
        async with _LOCK:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)


async def _read_all() -> Dict[str, Any]:
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}


async def _write_all(data: Dict[str, Any]):
    await _ensure_file()
    async with _LOCK:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def get_config(guild_id: int) -> Dict[str, Any]:
    data = await _read_all()
    key = str(guild_id)
    cfg = data.get(key, {})
    # sensible defaults
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "channel_id": cfg.get("channel_id"),
        "dm": bool(cfg.get("dm", False)),
        "template": cfg.get(
            "template",
            "Welcome {mention} to {server}! Say hi 👋\n\nInvited by: {inviter_mention}".replace("\\n", "\n"),
        ),
        "auto_role_id": cfg.get("auto_role_id"),
        "banner_enabled": bool(cfg.get("banner_enabled", False)),
        "xp_boost": float(cfg.get("xp_boost", 0.0)),
        "starter_kit": cfg.get("starter_kit", []),
    }


async def set_config(guild_id: int, cfg: Dict[str, Any]):
    data = await _read_all()
    data[str(guild_id)] = cfg
    await _write_all(data)


async def set_channel(guild_id: int, channel_id: Optional[int]):
    data = await _read_all()
    key = str(guild_id)
    cur = data.get(key, {})
    cur["channel_id"] = int(channel_id) if channel_id is not None else None
    data[key] = cur
    await _write_all(data)


def format_message(template: str, member, inviter_id: Optional[int] = None, inviter_mention: Optional[str] = None) -> str:
    """Replace tokens in the template.

    Supported tokens: {username}, {mention}, {server}, {inviter}, {inviter_mention}
    """
    server = getattr(member.guild, "name", "this server")
    vals = {
        "username": getattr(member, "name", str(member)),
        "mention": getattr(member, "mention", str(member)),
        "server": server,
        "inviter": str(inviter_id) if inviter_id else "",
        "inviter_mention": inviter_mention or (f"<@{inviter_id}>" if inviter_id else ""),
    }
    try:
        return template.format(**vals)
    except Exception:
        # fallback to simple replacement if format fails
        t = template
        for k, v in vals.items():
            t = t.replace("{" + k + "}", str(v))
        return t


def generate_banner_bytes(member) -> Optional[bytes]:
    """Generate a simple banner image with Pillow if available. Returns PNG bytes or None.

    This is optional; if Pillow isn't installed, callers should handle None.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    # simple banner: 800x200, background color, username text
    try:
        width, height = 800, 200
        im = Image.new("RGBA", (width, height), (54, 57, 63, 255))
        draw = ImageDraw.Draw(im)
        # try to use a default font
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
        except Exception:
            font = ImageFont.load_default()
        text = f"Welcome {getattr(member, 'display_name', getattr(member, 'name', 'guest'))}!"
        w, h = draw.textsize(text, font=font)
        draw.text(((width - w) / 2, (height - h) / 2), text, font=font, fill=(255, 255, 255, 255))
        from io import BytesIO

        bio = BytesIO()
        im.save(bio, "PNG")
        bio.seek(0)
        return bio.read()
    except Exception:
        return None


__all__ = ["get_config", "set_config", "set_channel", "format_message", "generate_banner_bytes", "set_config"]
