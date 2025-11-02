"""Welcome cog: customizable welcomes, DMs, auto-role, banner images, and starter kit hooks.

Commands for server admins to configure welcome behavior are provided. The cog
tries to be non-blocking and defers heavy work (banner generation) to optional
slow paths. Configuration is file-backed via `chronix_bot.utils.welcomer`.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import welcomer as wl
from chronix_bot.utils import invites as inv_utils

logger = logging.getLogger("chronix.welcome")


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # main welcome flow: find config, resolve inviter via snapshot heuristics,
        # post channel welcome, DM if enabled, assign auto-role, dispatch starter events.
        try:
            cfg = await wl.get_config(member.guild.id)
            if not cfg.get("enabled", True):
                return

            # attempt to resolve inviter by comparing cached invites (best-effort)
            inviter = None
            try:
                snap = await inv_utils.SNAP.get_snapshot(member.guild.id)
                current = {inv.code: inv.uses or 0 for inv in await member.guild.invites()}
                for code, old in snap.items():
                    new_uses = current.get(code, 0)
                    if new_uses > (old.get("uses") or 0):
                        inviter = await inv_utils.increment_invite_use(member.guild.id, code, joined_user_id=member.id, account_created_iso=member.created_at.isoformat())
                        break
            except Exception:
                logger.exception("Invite resolution failed for guild %s", getattr(member.guild, "id", None))

            # format message and optionally attach banner
            templ = cfg.get("template")
            content = wl.format_message(templ, member, inviter_id=inviter)

            # try to send to configured channel
            try:
                ch_id = cfg.get("channel_id")
                if ch_id:
                    ch = member.guild.get_channel(int(ch_id))
                else:
                    ch = None
                if ch is None:
                    # fallback to system channel
                    ch = member.guild.system_channel

                if ch and ch.permissions_for(member.guild.me).send_messages:
                    # attempt to attach banner if enabled
                    banner_bytes = None
                    if cfg.get("banner_enabled"):
                        banner_bytes = wl.generate_banner_bytes(member)
                    if banner_bytes:
                        from io import BytesIO

                        bio = BytesIO(banner_bytes)
                        bio.seek(0)
                        await ch.send(content, file=discord.File(fp=bio, filename="welcome.png"))
                    else:
                        await ch.send(content)
            except Exception:
                logger.exception("Failed to send welcome channel message for guild %s", member.guild.id)

            # DM if enabled
            try:
                if cfg.get("dm"):
                    try:
                        await member.send(content)
                    except Exception:
                        # user may have DMs closed
                        logger.debug("Could not DM member %s", member.id)
            except Exception:
                logger.exception("DM welcome failed for member %s", member.id)

            # auto-role
            try:
                role_id = cfg.get("auto_role_id")
                if role_id:
                    role = member.guild.get_role(int(role_id))
                    if role and member.guild.me.guild_permissions.manage_roles:
                        await member.add_roles(role, reason="Auto-role on join")
            except Exception:
                logger.exception("Failed to assign auto-role in guild %s", member.guild.id)

            # dispatch events for starter kit and xp boost
            try:
                starter = cfg.get("starter_kit") or []
                if starter:
                    # allow other cogs to handle starter kit awarding
                    self.bot.dispatch("welcome_starter_kit", member.guild, member, starter)

                xp_boost = float(cfg.get("xp_boost", 0.0) or 0.0)
                if xp_boost > 0:
                    self.bot.dispatch("welcome_xp_boost", member.guild, member, xp_boost)
            except Exception:
                logger.exception("Failed to dispatch welcome hooks for guild %s", member.guild.id)

        except Exception:
            logger.exception("Unhandled error in welcome flow for guild %s", getattr(member.guild, "id", None))

    @commands.hybrid_group(name="welcome", with_app_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context):
        """Manage welcome settings for this guild."""
        if ctx.invoked_subcommand is None:
            cfg = await wl.get_config(ctx.guild.id)
            await ctx.send(f"Welcome config: {cfg}")

    @welcome.command(name="set-channel")
    async def set_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set the channel for welcome messages. Omit to clear."""
        cfg = await wl.get_config(ctx.guild.id)
        cfg["channel_id"] = int(channel.id) if channel else None
        await wl.set_config(ctx.guild.id, cfg)
        await ctx.send("Welcome channel updated.")

    @welcome.command(name="set-dm")
    async def set_dm(self, ctx: commands.Context, on: bool):
        """Enable or disable DM welcomes."""
        cfg = await wl.get_config(ctx.guild.id)
        cfg["dm"] = bool(on)
        await wl.set_config(ctx.guild.id, cfg)
        await ctx.send(f"DM welcomes set to {on}.")

    @welcome.command(name="set-template")
    async def set_template(self, ctx: commands.Context, *, template: str):
        """Set the welcome template. Use tokens: {username}, {mention}, {server}, {inviter_mention}."""
        cfg = await wl.get_config(ctx.guild.id)
        cfg["template"] = template
        await wl.set_config(ctx.guild.id, cfg)
        await ctx.send("Template updated.")

    @welcome.command(name="set-auto-role")
    async def set_auto_role(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set an auto-role to grant on join. Omit to clear."""
        cfg = await wl.get_config(ctx.guild.id)
        cfg["auto_role_id"] = int(role.id) if role else None
        await wl.set_config(ctx.guild.id, cfg)
        await ctx.send("Auto-role updated.")

    @welcome.command(name="set-banner")
    async def set_banner(self, ctx: commands.Context, on: bool):
        """Enable/disable generated banner images for the welcome message."""
        cfg = await wl.get_config(ctx.guild.id)
        cfg["banner_enabled"] = bool(on)
        await wl.set_config(ctx.guild.id, cfg)
        await ctx.send(f"Banner enabled set to {on}.")

    @welcome.command(name="preview")
    async def preview(self, ctx: commands.Context):
        """Preview the current welcome template as the invoking user."""
        cfg = await wl.get_config(ctx.guild.id)
        content = wl.format_message(cfg.get("template"), ctx.author, inviter_id=None)
        banner = None
        if cfg.get("banner_enabled"):
            banner = wl.generate_banner_bytes(ctx.author)
        if banner:
            from io import BytesIO

            bio = BytesIO(banner)
            bio.seek(0)
            await ctx.send(content, file=discord.File(fp=bio, filename="preview.png"))
        else:
            await ctx.send(content)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
