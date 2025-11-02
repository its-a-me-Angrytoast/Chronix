from __future__ import annotations

import asyncio
import os
import time
from typing import Optional
from discord.ext import commands
from discord import app_commands
import discord
import random

from chronix_bot.utils import xp as xp_utils

DEFAULT_COOLDOWN = int(os.getenv("XP_MESSAGE_COOLDOWN", "60"))
DEFAULT_MIN_XP = int(os.getenv("XP_MIN_PER_MESSAGE", "5"))
DEFAULT_MAX_XP = int(os.getenv("XP_MAX_PER_MESSAGE", "12"))
LEVEL_ROLE_MULTIPLE = int(os.getenv("XP_ROLE_MULTIPLE", "5"))


class XP_Cog(commands.Cog):
    """Cog that awards XP for messages and exposes XP commands.

    Uses file-backed XP utilities. Cooldowns are enforced per user per guild in-memory.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (guild_id, user_id) -> last_award_ts
        self._last_award: dict[tuple[int, int], float] = {}
        self._lock = asyncio.Lock()
        # (guild_id, user_id) -> last_message_content
        self._last_message: dict[tuple[int, int], str] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        key = (guild_id, user_id)
        now = time.time()
        last = self._last_award.get(key, 0)
        if now - last < DEFAULT_COOLDOWN:
            return

        # simple anti-spam: require message length > 5 and not a duplicate
        content = (message.content or "").strip()
        if len(content) < 6:
            return
        last_msg = self._last_message.get(key)
        if last_msg and last_msg == content:
            # duplicate message — skip awarding
            return

        amount = random.SystemRandom().randint(DEFAULT_MIN_XP, DEFAULT_MAX_XP)
        settings = await xp_utils.get_guild_settings(guild_id)
        # respect per-guild channel whitelist/blacklist
        ch_whitelist = settings.get("channels_whitelist")
        ch_blacklist = settings.get("channels_blacklist")
        if ch_whitelist:
            if str(message.channel.id) not in [str(x) for x in ch_whitelist]:
                return
        if ch_blacklist:
            if str(message.channel.id) in [str(x) for x in ch_blacklist]:
                return
        multiplier = float(settings.get("multiplier", 1.0))

        result = await xp_utils.add_xp(guild_id, user_id, amount, base=int(settings.get("base", 100)), multiplier=multiplier)

        # store last message content for duplicate detection
        self._last_message[key] = content

        self._last_award[key] = now

        if result.get("leveled"):
            new_level = result["new_level"]
            # announce level up in the channel
            try:
                await message.channel.send(f":tada: {message.author.mention} leveled up to **{new_level}**! 🎉")
            except Exception:
                pass

            # role reward: if level is multiple of configured value, try to grant role if mapping exists
            role_map = settings.get("level_roles", {})
            role_id = role_map.get(str(new_level)) or role_map.get(str(new_level - (new_level % LEVEL_ROLE_MULTIPLE)))
            if role_id:
                try:
                    role = message.guild.get_role(int(role_id))
                    if role:
                        await message.author.add_roles(role, reason="Level reward")
                except Exception:
                    pass

    @commands.hybrid_command(name="xp", with_app_command=True, description="Show your XP and level")
    async def xp(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        member = member or ctx.author
        gid = ctx.guild.id if ctx.guild else 0
        xp = await xp_utils.get_xp(gid, member.id)
        settings = await xp_utils.get_guild_settings(gid)
        base = int(settings.get("base", 100))
        level = xp_utils.level_from_xp(xp, base)
        next_level_xp = xp_utils.xp_for_level(level + 1, base)
        bar_len = 20
        prog = (xp - xp_utils.xp_for_level(level, base)) / max(1, (next_level_xp - xp_utils.xp_for_level(level, base)))
        filled = int(prog * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        await ctx.reply(f"{member.display_name} — Level {level} — XP: {xp}/{next_level_xp}\n{bar}")

    @commands.hybrid_command(name="xpleaderboard", with_app_command=True, description="Show XP leaderboard for this server")
    async def xpleaderboard(self, ctx: commands.Context, top: int = 10) -> None:
        gid = ctx.guild.id if ctx.guild else 0
        # support global leaderboard via flag: use /xpleaderboard global:true
        params = getattr(ctx, "interaction", None)
        global_flag = False
        if params and params.data and params.data.get("options"):
            # app_commands may pass options; fallback: check keyword
            for o in params.data.get("options", []):
                if o.get("name") == "global":
                    global_flag = bool(o.get("value"))

        if global_flag:
            items = await xp_utils.get_global_top(limit=top)
        else:
            items = await xp_utils.get_top(gid, limit=top)
        if not items:
            await ctx.reply("No XP data yet.")
            return
        lines = []
        for idx, (user_id, xp_amount) in enumerate(items, start=1):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            # use guild base when available (best-effort)
            settings = await xp_utils.get_guild_settings(gid)
            base = int(settings.get("base", 100))
            lvl = xp_utils.level_from_xp(xp_amount, base=base)
            lines.append(f"`{idx}.` **{name}** — Level {lvl} — {xp_amount} XP")
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(XP_Cog(bot))
