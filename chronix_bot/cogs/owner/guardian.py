"""Guardian cog: ensure the configured OWNER_ID is unbanned and notified.

If the configured owner is banned from a guild where the bot is present, this
cog will attempt to unban them immediately (if the bot has permission). If
unban is not possible, it will create an invite and DM the owner with the
invite link so they can rejoin.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import logger as chronix_logger


class Guardian(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _log(self, payload: object) -> None:
        try:
            chronix_logger.enqueue_log(payload)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """If the banned user is the configured OWNER_ID, attempt to unban and notify."""
        try:
            settings = getattr(self.bot, "settings", None)
            owner_id = getattr(settings, "OWNER_ID", None) if settings else None
            if owner_id is None:
                return
            if int(user.id) != int(owner_id):
                return

            # Attempt to unban immediately
            try:
                await guild.unban(user, reason="Auto-unban owner")
                self._log({"type": "owner_unban", "guild": guild.id, "owner": owner_id, "result": "unbanned"})
                # Create invite for convenience
                invite = None
                try:
                    # pick a visible text channel
                    ch = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
                    if ch:
                        inv = await ch.create_invite(max_age=3600, max_uses=1, unique=True, reason="Owner rejoin invite")
                        invite = inv.url
                except Exception:
                    invite = None

                # DM owner the success + invite
                try:
                    owner_user = await self.bot.fetch_user(owner_id)
                    msg = f"You were banned from {guild.name} but I have unbanned you."
                    if invite:
                        msg += f" Here's a one-time invite (1h): {invite}"
                    await owner_user.send(msg)
                except Exception:
                    # best-effort only
                    pass
                return
            except Exception as e:
                # Couldn't unban (likely missing permissions). Create invite and DM owner.
                self._log({"type": "owner_unban_failed", "guild": guild.id, "owner": owner_id, "error": str(e)})
                invite = None
                try:
                    ch = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
                    if ch:
                        inv = await ch.create_invite(max_age=3600 * 24, max_uses=1, unique=True, reason="Owner rejoin invite")
                        invite = inv.url
                except Exception:
                    invite = None

                try:
                    owner_user = await self.bot.fetch_user(owner_id)
                    msg = f"You were banned from {guild.name}. I couldn't unban you (missing permissions)."
                    if invite:
                        msg += f" Here's an invite: {invite}"
                    else:
                        msg += " I couldn't create an invite either. Please contact the server admins."
                    await owner_user.send(msg)
                except Exception:
                    pass
        except Exception:
            # never crash the event loop
            self._log({"type": "guardian_error", "guild": getattr(guild, "id", None), "user": getattr(user, "id", None)})


async def setup(bot: commands.Bot):
    await bot.add_cog(Guardian(bot))
