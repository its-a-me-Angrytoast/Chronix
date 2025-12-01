"""Temporary channels cog: create temporary voice/text channels with auto-deletion.

Features:
- `chro temp create [voice|text]` for users to create temporary channels
- Admin commands to configure per-guild settings
- Background pruning task to remove expired/empty channels
- on_voice_state_update listener to update last_active and enforce per-user limits
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from chronix_bot.utils import tempvc

logger = logging.getLogger("chronix.temp")


class TempChannels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._task = self.bot.loop.create_task(self._prune_loop())
        # in-memory trackers for rate limiting and join times
        # guild_id -> list of recent creation timestamps handled in tempvc but also keep an in-memory cache to avoid file churn
        self._user_joined_at: dict[tuple[int, int, int], datetime] = {}
        self._creation_lock = asyncio.Lock()
        # semaphore to limit concurrent deletion requests (avoid burst deletes)
        self._delete_semaphore = asyncio.Semaphore(3)

    def cog_unload(self):
        if not self._task.cancelled():
            self._task.cancel()

    async def _prune_loop(self):
        await self.bot.wait_until_ready()
        backoff = 1
        while True:
            try:
                # check all expired temp channels and attempt to delete them
                expired = await tempvc.cleanup_expired()
                if not expired:
                    await asyncio.sleep(60)
                    continue

                # avoid bursting deletes; pace them
                for cid in expired:
                    try:
                        ch = self.bot.get_channel(cid)
                        if ch is None:
                            # channel doesn't exist -> drop record
                            await tempvc.delete_channel_record(cid)
                            continue

                        cfg = await tempvc.get_config(ch.guild.id)
                        # Voice channels: delete only if empty
                        if isinstance(ch, discord.VoiceChannel):
                            if len(ch.members) == 0:
                                async with self._delete_semaphore:
                                    await ch.delete(reason="Temp channel auto-prune")
                                await tempvc.delete_channel_record(cid)
                                # small pause to avoid hitting rate limits
                                await asyncio.sleep(0.5)
                        # Text channels: check last message timestamp (best-effort)
                        elif isinstance(ch, discord.TextChannel):
                                try:
                                    last_msg = None
                                    async for m in ch.history(limit=1):
                                        last_msg = m
                                        break
                                    # if no messages, safe to delete
                                    if last_msg is None:
                                        async with self._delete_semaphore:
                                            await ch.delete(reason="Temp text channel auto-prune")
                                        await tempvc.delete_channel_record(cid)
                                    else:
                                        # if last message older than auto_delete_seconds, delete
                                        auto = cfg.get("auto_delete_seconds", 300)
                                        delta = (discord.utils.utcnow() - last_msg.created_at).total_seconds()
                                        if delta >= auto:
                                            async with self._delete_semaphore:
                                                await ch.delete(reason="Temp text channel auto-prune")
                                            await tempvc.delete_channel_record(cid)
                                    await asyncio.sleep(0.5)
                                except Exception:
                                    # if history fails (permissions), skip this channel
                                    logger.debug("Could not inspect history for channel %s", cid)
                                    continue
                    except Exception:
                        logger.exception("Failed pruning channel %s", cid)

                backoff = 1
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in temp channel prune loop")
                # exponential backoff on error
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)

    @commands.hybrid_command(name="temp_create", with_app_command=True)
    async def temp_create(self, ctx: commands.Context, kind: Optional[str] = "voice"):
        """Create a temporary channel (voice or text).

        Usage: chro temp_create voice|text
        """
        guild = ctx.guild
        cfg = await tempvc.get_config(guild.id)
        if not cfg.get("enabled", True):
            await ctx.send("Temporary channels are disabled on this server.")
            return

        # enforce per-user limit (active channels)
        existing = await tempvc.list_guild_channels(guild.id)
        user_count = sum(1 for r in existing if int(r.get("owner_id")) == int(ctx.author.id))
        if user_count >= cfg.get("max_per_user", 2):
            await ctx.send(f"You already have {user_count} temporary channels (limit {cfg.get('max_per_user')}).")
            return

        # enforce rate-limits (both per-guild and per-user) using persisted events
        allowed = await tempvc.can_create_now(guild.id, ctx.author.id, per_guild_limit=cfg.get("rate_per_guild", 10), per_user_limit=cfg.get("rate_per_user", 3), window_seconds=cfg.get("rate_window_seconds", 60))
        if not allowed:
            await ctx.send("Temporary channel creation rate limit exceeded; please wait a moment and try again.")
            return

        # generate name and create channel
        name = tempvc.generate_name(cfg.get("name_pattern", "{user}-vc"), getattr(ctx.author, "display_name", ctx.author.name))
        category = None
        if cfg.get("category_id"):
            category = guild.get_channel(int(cfg.get("category_id")))

        try:
            if kind == "text" and cfg.get("text_channels"):
                ch = await guild.create_text_channel(name, category=category, reason="Temporary channel created")
                await ctx.send(f"Created temporary text channel: {ch.mention}")
            else:
                ch = await guild.create_voice_channel(name, category=category, reason="Temporary channel created")
                await ctx.send(f"Created temporary voice channel: {ch.name}")

            # persist and record creation event
            await tempvc.create_channel_record(guild.id, ch.id, ctx.author.id, channel_type=("text" if isinstance(ch, discord.TextChannel) else "voice"))
            try:
                await tempvc.record_creation_event(guild.id, ctx.author.id, ch.id)
            except Exception:
                # non-fatal: creation event is best-effort
                logger.debug("Failed to persist creation event for guild %s", guild.id)

            # dispatch an event for other systems (rewards, analytics)
            try:
                self.bot.dispatch("tempvc_channel_created", guild.id, ch.id, ctx.author.id, ("text" if isinstance(ch, discord.TextChannel) else "voice"))
            except Exception:
                logger.debug("Failed to dispatch tempvc_channel_created")
        except Exception:
            logger.exception("Failed to create temp channel in guild %s", guild.id)
            await ctx.send("Failed to create temporary channel. Make sure I have Manage Channels permission.")

    @commands.hybrid_group(name="temp", with_app_command=True)
    @commands.has_permissions(manage_guild=True)
    async def temp(self, ctx: commands.Context):
        """Admin commands for temporary channels."""
        if ctx.invoked_subcommand is None:
            cfg = await tempvc.get_config(ctx.guild.id)
            await ctx.send(f"Temp config: {cfg}")

    @temp.command(name="set-category")
    async def set_category(self, ctx: commands.Context, category: Optional[discord.CategoryChannel] = None):
        cfg = await tempvc.get_config(ctx.guild.id)
        cfg["category_id"] = int(category.id) if category else None
        await tempvc.set_config(ctx.guild.id, cfg)
        await ctx.send("Category updated.")

    @temp.command(name="set-pattern")
    async def set_pattern(self, ctx: commands.Context, *, pattern: str):
        cfg = await tempvc.get_config(ctx.guild.id)
        cfg["name_pattern"] = pattern
        await tempvc.set_config(ctx.guild.id, cfg)
        await ctx.send("Name pattern updated.")

    @temp.command(name="set-auto-delete")
    async def set_auto_delete(self, ctx: commands.Context, seconds: int):
        cfg = await tempvc.get_config(ctx.guild.id)
        cfg["auto_delete_seconds"] = int(seconds)
        await tempvc.set_config(ctx.guild.id, cfg)
        await ctx.send("Auto-delete timeout updated.")

    @temp.command(name="set-max-per-user")
    async def set_max_per_user(self, ctx: commands.Context, n: int):
        cfg = await tempvc.get_config(ctx.guild.id)
        cfg["max_per_user"] = int(n)
        # provide sensible rate-limit defaults when configuring
        cfg.setdefault("rate_per_guild", 10)
        cfg.setdefault("rate_per_user", 3)
        cfg.setdefault("rate_window_seconds", 60)
        await tempvc.set_config(ctx.guild.id, cfg)
        await ctx.send("Max per-user updated.")

    @temp.command(name="set-log-channel")
    async def set_log_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set a channel where temp channel events (create/delete) will be posted."""
        cfg = await tempvc.get_config(ctx.guild.id)
        cfg["log_channel_id"] = int(channel.id) if channel else None
        await tempvc.set_config(ctx.guild.id, cfg)
        await ctx.send("Log channel updated.")

    @temp.command(name="list")
    async def list_channels(self, ctx: commands.Context):
        """List active temporary channels for this guild."""
        rows = await tempvc.list_guild_channels(ctx.guild.id)
        if not rows:
            await ctx.send("No active temporary channels.")
            return
        lines = []
        for r in rows:
            ch = ctx.guild.get_channel(int(r.get("channel_id")))
            owner = ctx.guild.get_member(int(r.get("owner_id")))
            lines.append(f"{ch.mention if ch else r.get('channel_id')} — owner: {owner.display_name if owner else r.get('owner_id')}")
        await ctx.send("Active temp channels:\n" + "\n".join(lines))

    @temp.command(name="delete")
    async def delete_channel(self, ctx: commands.Context, channel: discord.abc.GuildChannel):
        """Force-delete a temporary channel and remove its record."""
        try:
            # delete channel if exists
            if channel:
                async with self._delete_semaphore:
                    await channel.delete(reason=f"Manual temp delete by {ctx.author.id}")
            await tempvc.delete_channel_record(channel.id)
            await ctx.send("Temporary channel deleted.")
        except Exception:
            logger.exception("Failed to delete temp channel %s", getattr(channel, 'id', None))
            await ctx.send("Failed to delete temporary channel.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            # detect joins and leaves for tracked temp channels and update last_active
            tracked_ids = set(map(int, await tempvc.get_all_channel_ids()))
            # join
            if after.channel and after.channel.id in tracked_ids:
                # record join timestamp for possible voice-activity reward calculation
                self._user_joined_at[(after.channel.guild.id, member.id, after.channel.id)] = datetime.now(timezone.utc)
                await tempvc.update_last_active(after.channel.id)
            # leave
            if before.channel and before.channel.id in tracked_ids and (after.channel is None or after.channel.id != before.channel.id):
                await tempvc.update_last_active(before.channel.id)
                key = (before.channel.guild.id, member.id, before.channel.id)
                join_ts = self._user_joined_at.pop(key, None)
                if join_ts:
                    duration = (datetime.now(timezone.utc) - join_ts).total_seconds()
                    # dispatch a voice-activity event for other cogs to reward XP/coins
                    try:
                        self.bot.dispatch("tempvc_voice_activity", member.id, before.channel.guild.id, int(duration))
                    except Exception:
                        logger.debug("Failed to dispatch tempvc_voice_activity")
        except Exception:
            logger.exception("Error tracking voice state for member %s", member.id)


async def _channels_keys() -> List[str]:
    # compatibility helper kept for backwards-compatibility with existing callers; prefer get_all_channel_ids
    ids = await tempvc.get_all_channel_ids()
    return [str(x) for x in ids]


async def setup(bot: commands.Bot):
    await bot.add_cog(TempChannels(bot))
