from __future__ import annotations

from typing import Optional
from discord.ext import commands
import discord

from chronix_bot.utils import xp as xp_utils


class XPAdmin(commands.Cog):
    """Administrative commands to configure per-guild XP settings.

    Commands require Manage Guild permission or Administrator.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_guild_admin(self, member: discord.Member) -> bool:
        return member.guild_permissions.manage_guild or member.guild_permissions.administrator

    @commands.hybrid_command(name="xpsettings", with_app_command=True, description="Show XP settings for this guild")
    @commands.guild_only()
    async def xpsettings(self, ctx: commands.Context) -> None:
        settings = await xp_utils.get_guild_settings(ctx.guild.id)
        if not settings:
            await ctx.reply("No XP settings configured for this guild. Using defaults.")
            return
        await ctx.reply(f"XP settings: `{settings}`")

    @commands.hybrid_command(name="xpset", with_app_command=True, description="Set a guild XP setting: multiplier/base")
    @commands.guild_only()
    async def xpset(self, ctx: commands.Context, key: str, value: str) -> None:
        if not self._is_guild_admin(ctx.author):
            await ctx.reply("You need Manage Guild permissions to change XP settings.")
            return
        settings = await xp_utils.get_guild_settings(ctx.guild.id)
        # simple casts
        if key == "multiplier":
            try:
                settings["multiplier"] = float(value)
            except Exception:
                await ctx.reply("Invalid multiplier; must be a float")
                return
        elif key == "base":
            try:
                settings["base"] = int(value)
            except Exception:
                await ctx.reply("Invalid base; must be an integer")
                return
        else:
            settings[key] = value

        await xp_utils.set_guild_settings(ctx.guild.id, settings)
        await ctx.reply("XP settings updated.")

    @commands.hybrid_command(name="xprole", with_app_command=True, description="Map a role reward to a level: xprole add 10 @role")
    @commands.guild_only()
    async def xprole(self, ctx: commands.Context, action: str, level: int, role: discord.Role) -> None:
        if not self._is_guild_admin(ctx.author):
            await ctx.reply("You need Manage Guild permissions to change XP settings.")
            return
        settings = await xp_utils.get_guild_settings(ctx.guild.id)
        role_map = settings.get("level_roles", {})
        if action.lower() in ("add", "set"):
            role_map[str(level)] = role.id
            settings["level_roles"] = role_map
            await xp_utils.set_guild_settings(ctx.guild.id, settings)
            await ctx.reply(f"Role {role.name} will be awarded at level {level}.")
            return
        if action.lower() in ("remove", "rm"):
            if str(level) in role_map:
                del role_map[str(level)]
                settings["level_roles"] = role_map
                await xp_utils.set_guild_settings(ctx.guild.id, settings)
                await ctx.reply(f"Removed role mapping for level {level}.")
                return
            await ctx.reply("No role mapping for that level.")

    @commands.hybrid_command(name="xpreset", with_app_command=True, description="Reset XP for the guild")
    @commands.guild_only()
    async def xpreset(self, ctx: commands.Context, confirm: Optional[bool] = False) -> None:
        if not self._is_guild_admin(ctx.author):
            await ctx.reply("You need Manage Guild permissions to reset XP.")
            return
        if not confirm:
            await ctx.reply("This will wipe all XP for this server. Re-run with `true` to confirm.")
            return
        await xp_utils.reset_guild_xp(ctx.guild.id)
        await ctx.reply("Guild XP reset.")

    @commands.hybrid_command(name="xpbackup", with_app_command=True, description="Create a backup of file-backed XP (returns path)")
    @commands.guild_only()
    async def xpbackup(self, ctx: commands.Context) -> None:
        if not self._is_guild_admin(ctx.author):
            await ctx.reply("You need Manage Guild permissions to create backups.")
            return
        path = await xp_utils.backup_xp()
        await ctx.reply(f"XP backup created: `{path}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(XPAdmin(bot))
