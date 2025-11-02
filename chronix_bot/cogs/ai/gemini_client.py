"""AI cog providing /ask, /explain, /summarize and guild opt-in features.

This cog is intentionally lightweight and file-backed. If `discord` is
available, commands are registered. The underlying AI client is an
abstraction and will use mock responses when no GEMINI_API_KEY is set.
"""
from __future__ import annotations

import os
import json
import time
from typing import Optional, Any, Dict
from pathlib import Path

try:
    import discord
    from discord.ext import commands
    from discord import app_commands
except Exception:  # pragma: no cover - optional dependency
    discord = None
    commands = None
    app_commands = None

from chronix_bot.utils.ai_client import generate_text, async_generate_text, HAVE_AIOHTTP
from chronix_bot.utils.prompt_sanitizer import sanitize_prompt

DATA_DIR = Path.cwd() / "data"
AI_GUILDS = DATA_DIR / "ai_guilds.json"
AI_LOGS = DATA_DIR / "ai_logs.jsonl"

# cooldowns in seconds per command per user
COOLDOWN_SECONDS = 6
_last_used: Dict[str, float] = {}


def _load_guilds() -> Dict[str, Any]:
    if not AI_GUILDS.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        AI_GUILDS.write_text(json.dumps({}, indent=2), encoding="utf-8")
        return {}
    try:
        return json.loads(AI_GUILDS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_guilds(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AI_GUILDS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _log_ai_request(entry: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with AI_LOGS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _check_cooldown(user_id: int, cmd: str) -> Optional[int]:
    key = f"{user_id}:{cmd}"
    now = time.time()
    last = _last_used.get(key, 0)
    if now - last < COOLDOWN_SECONDS:
        return int(COOLDOWN_SECONDS - (now - last))
    _last_used[key] = now
    return None


def _guild_ai_enabled(guild_id: Optional[int]) -> bool:
    if guild_id is None:
        return True
    data = _load_guilds()
    return data.get(str(guild_id), {}).get("enabled", False)


if commands is not None:
    class GeminiAI(commands.Cog):
        """Cog exposing AI commands (prefix + slash parity where possible)."""

        def __init__(self, bot: Any):
            self.bot = bot

        async def _run_query(self, prompt: str, mode: str = "chat", ctx: Optional[Any] = None) -> str:
            s_prompt, removed = sanitize_prompt(prompt)
            if ctx is not None and getattr(ctx, "guild", None) is not None:
                gid = getattr(ctx.guild, "id", None)
            else:
                gid = None
            if not _guild_ai_enabled(gid):
                return "AI features are not enabled on this server. Ask an admin to run `chro ai-enable` to opt-in."
            # check cooldown
            if ctx is not None:
                cd = _check_cooldown(getattr(ctx.author, "id", 0), mode)
                if cd is not None:
                    return f"Please wait {cd}s before using AI again."
            # if remote provider configured but aiohttp missing, advise
            if (not HAVE_AIOHTTP) and (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")):
                return "Server missing `aiohttp` dependency required for remote AI. Please install dependencies."
            # call AI
            try:
                res = await async_generate_text(s_prompt, mode=mode, temperature=0.7, max_tokens=512)
                text = res.get("text") if isinstance(res, dict) else str(res)
            except Exception as exc:
                text = f"AI request failed: {exc}"
            # log
            log = {"ts": int(time.time()), "guild_id": gid, "user_id": getattr(ctx.author, "id", None) if ctx else None, "mode": mode, "prompt": s_prompt, "removed": removed, "response": text}
            _log_ai_request(log)
            return text

        @commands.command(name="ai", aliases=["ask"])  # prefix
        async def ai(self, ctx: Any, *, prompt: str):
            """Ask the AI a question. Alias: ask"""
            text = await self._run_query(prompt, mode="chat", ctx=ctx)
            await ctx.send(text)

        @commands.command(name="explain")
        async def explain(self, ctx: Any, *, prompt: str):
            """Ask the AI to explain something succinctly."""
            text = await self._run_query(prompt, mode="explain", ctx=ctx)
            await ctx.send(text)

        @commands.command(name="summarize")
        async def summarize(self, ctx: Any, *, prompt: str):
            """Ask the AI to summarize input text."""
            text = await self._run_query(prompt, mode="summarize", ctx=ctx)
            await ctx.send(text)

        @commands.command(name="ai-enable")
        async def ai_enable(self, ctx: Any):
            """Enable AI features for this guild (admin only)."""
            if getattr(ctx, "guild", None) is None:
                await ctx.send("This command must be run in a server.")
                return
            # check admin
            if not getattr(ctx.author, "guild_permissions", None) or not getattr(ctx.author.guild_permissions, "administrator", False):
                await ctx.send("You must be a server administrator to enable AI features.")
                return
            data = _load_guilds()
            data[str(ctx.guild.id)] = {"enabled": True}
            _save_guilds(data)
            await ctx.send("AI features enabled for this server.")

        @commands.command(name="ai-disable")
        async def ai_disable(self, ctx: Any):
            """Disable AI features for this guild (admin only)."""
            if getattr(ctx, "guild", None) is None:
                await ctx.send("This command must be run in a server.")
                return
            if not getattr(ctx.author, "guild_permissions", None) or not getattr(ctx.author.guild_permissions, "administrator", False):
                await ctx.send("You must be a server administrator to disable AI features.")
                return
            data = _load_guilds()
            data[str(ctx.guild.id)] = {"enabled": False}
            _save_guilds(data)
            await ctx.send("AI features disabled for this server.")


    def setup(bot):
        if commands is not None:
            bot.add_cog(GeminiAI(bot))
