"""Invite tracker cog: listens to invite events and tracks counts.

Works in DB-first mode if a DB pool is present; otherwise falls back to file-backed
in `data/invites.json` via `chronix_bot.utils.invites`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands, tasks

from chronix_bot.utils import invites as inv_utils
from chronix_bot.utils import invite_config as inv_config

logger = logging.getLogger("chronix.invite")


class InviteTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Periodically refresh invite snapshots to keep caches up to date
        self.refresh_task = self.bot.loop.create_task(self._periodic_refresh())

    def cog_unload(self):
        if not self.refresh_task.cancelled():
            self.refresh_task.cancel()

    async def _refresh_guild(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            # convert discord.Invite to serializable dict
            inv_list = []
            for i in invites:
                inv_list.append({"code": i.code, "uses": i.uses or 0, "inviter_id": getattr(i.inviter, "id", None)})
            await inv_utils.SNAP.set_snapshot(guild.id, inv_list)
        except Exception:
            logger.exception("Failed to refresh invites for guild %s", guild.id)

    async def _periodic_refresh(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                for g in list(self.bot.guilds):
                    await self._refresh_guild(g)
                await asyncio.sleep(300)  # refresh every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in invite refresh loop")
                await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._refresh_guild(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        try:
            inviter_id = getattr(invite.inviter, "id", None)
            await inv_utils.record_invite_create(invite.guild.id, invite.code, inviter_id, invite.uses or 0)
            await self._refresh_guild(invite.guild)
        except Exception:
            logger.exception("Error handling invite create")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        try:
            await inv_utils.record_invite_delete(invite.guild.id, invite.code)
            await self._refresh_guild(invite.guild)
        except Exception:
            logger.exception("Error handling invite delete")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Try to determine inviter by comparing cached invites
        try:
            snapshot = await inv_utils.SNAP.get_snapshot(member.guild.id)
            current = {inv.code: inv.uses or 0 for inv in await member.guild.invites()}
            # find which code increased
            increased_code = None
            for code, old in snapshot.items():
                new_uses = current.get(code, 0)
                if new_uses > (old.get("uses") or 0):
                    increased_code = code
                    break
            if increased_code:
                # pass account creation timestamp for fake-detection
                inviter = await inv_utils.increment_invite_use(
                    member.guild.id, increased_code, joined_user_id=member.id, account_created_iso=member.created_at.isoformat()
                )
                if inviter:
                    logger.info("Member %s joined via inviter %s in guild %s", member.id, inviter, member.guild.id)
                    # Friendly lightweight welcome integration: try to post to a welcome channel if available
                    try:
                        chan = None
                        # prefer channel named 'welcome' if present
                        for c in member.guild.text_channels:
                            if c.name.lower().startswith("welcome"):
                                chan = c
                                break
                        if chan is None:
                            chan = member.guild.system_channel
                        if chan and chan.permissions_for(member.guild.me).send_messages:
                            await chan.send(f"👋 {member.mention} joined — invited by <@{inviter}>. Welcome!")
                    except Exception:
                        logger.exception("Failed to post welcome message for guild %s", member.guild.id)

                    # Check milestones and dispatch event for reward hooks
                    try:
                        cfg = await inv_config.get_config(member.guild.id)
                        counts = await inv_utils.get_user_counts(member.guild.id, inviter)
                        if cfg.get("enable_rewards", True):
                            milestones = cfg.get("milestones", []) or []
                            # if this invite count matches a milestone, dispatch an event
                            if int(counts.get("invites", 0)) in milestones:
                                # allow other cogs (e.g., economy) to award rewards by listening to this event
                                try:
                                    self.bot.dispatch("invite_milestone", member.guild, int(inviter), int(counts.get("invites", 0)))
                                except Exception:
                                    logger.exception("Failed to dispatch invite_milestone event")
                        # also write to configured log channel if present
                        log_chan_id = cfg.get("log_channel_id")
                        if log_chan_id:
                            ch = member.guild.get_channel(int(log_chan_id))
                            if ch and ch.permissions_for(member.guild.me).send_messages:
                                await ch.send(f"📥 {member.mention} joined — invited by <@{inviter}> (total invites: {counts.get('invites',0)})")
                    except Exception:
                        logger.exception("Failed to process invite milestones/logging for guild %s", member.guild.id)
            # refresh snapshot regardless
            await self._refresh_guild(member.guild)
        except Exception:
            logger.exception("Error resolving inviter for member %s", getattr(member, "id", None))

    @commands.hybrid_command(name="invite_leaderboard", with_app_command=True)
    async def invite_leaderboard(self, ctx: commands.Context, limit: Optional[int] = 10):
        """Show top inviters in this guild."""
        rows = await inv_utils.get_leaderboard(ctx.guild.id, limit=limit or 10)
        if not rows:
            await ctx.send("No invite data available for this server.")
            return
        lines = []
        for uid, cnt in rows:
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else str(uid)
            lines.append(f"{name} — {cnt} invites")
        await ctx.send("Top inviters:\n" + "\n".join(lines))

    @commands.hybrid_command(name="invite_stats", with_app_command=True)
    async def invite_stats(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show invite stats for a member (or yourself)."""
        target = member or ctx.author
        pool = None
        try:
            rows = await inv_utils.get_leaderboard(ctx.guild.id, limit=100)
            # find target in rows
            for uid, cnt in rows:
                if int(uid) == int(target.id):
                    await ctx.send(f"{target.display_name} — {cnt} invites")
                    return
            await ctx.send(f"No invite stats for {target.display_name}.")
        except Exception:
            logger.exception("Failed to fetch invite stats")
            await ctx.send("Failed to fetch invite stats.")

    @commands.hybrid_command(name="invite_clear", with_app_command=True)
    @commands.has_permissions(administrator=True)
    async def invite_clear(self, ctx: commands.Context):
        """Clear invite snapshots and file-based cache for this guild (doesn't delete DB rows)."""
        try:
            await inv_utils.SNAP.set_snapshot(ctx.guild.id, [])
            await ctx.send("Invite snapshot cache cleared.\nNote: DB rows are untouched. Use invite_reset to clear DB counts.")
        except Exception:
            logger.exception("Failed to clear invite snapshot cache")
            await ctx.send("Failed to clear invite snapshot cache.")

    @commands.hybrid_command(name="invite_reset", with_app_command=True)
    @commands.has_permissions(manage_guild=True)
    async def invite_reset(self, ctx: commands.Context):
        """Reset invite stats for this guild."""
        await inv_utils.reset_guild_invites(ctx.guild.id)
        await ctx.send("Invite stats reset for this guild.")


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))
