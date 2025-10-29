"""Moderation cog (Phase 4).

Provides moderation commands: ban, kick, mute, unmute, tempmute, warn, purge,
slowmode, nickname and role edits, lock/unlock channel, and mass actions with
confirmation. All significant actions are enqueued to the async logger.

This cog intentionally uses role-based permission checks (`manage_messages`,
`ban_members`, etc.) and owner-only safeguards for destructive mass actions.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import logger as chronix_logger


def parse_duration(s: str) -> int:
    """Parse simple duration strings like '1h', '30m', '45s' -> seconds."""
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", s)
    if not m:
        raise ValueError("Invalid duration format. Use e.g. 1h30m, 45m, 30s")
    h = int(m.group(1)) if m.group(1) else 0
    mm = int(m.group(2)) if m.group(2) else 0
    s = int(m.group(3)) if m.group(3) else 0
    return h * 3600 + mm * 60 + s


class ConfirmView(discord.ui.View):
    def __init__(self, *, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        self.stop()
        await interaction.response.edit_message(embed=helpers.make_embed("Confirmed", "Action confirmed."), view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        self.stop()
        await interaction.response.edit_message(embed=helpers.make_embed("Cancelled", "Action cancelled."), view=None)


class Moderation(commands.Cog):
    """Moderation cog with safety and logging."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # simple in-memory warn store: {guild_id: {user_id: [reasons]}}
        self._warns: dict[int, dict[int, List[str]]] = {}

    # ----- helpers
    def _log(self, payload: object) -> None:
        try:
            chronix_logger.enqueue_log(payload)
        except Exception:
            pass

    async def _ensure_muted_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name="Muted")
        if role is None:
            role = await guild.create_role(name="Muted", reason="Created by Chronix for mutes")
            # set channel overwrites for existing text channels
            for ch in guild.text_channels:
                try:
                    await ch.set_permissions(role, send_messages=False, add_reactions=False)
                except Exception:
                    # ignore permission errors
                    pass
        return role

    # ----- commands
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        """Ban a member from the server."""
        try:
            await member.ban(reason=reason)
            await ctx.send(embed=helpers.make_embed("Banned", f"{member} was banned. Reason: {reason or 'No reason.'}"))
            self._log({"type": "ban", "guild": ctx.guild.id if ctx.guild else None, "target": member.id, "by": ctx.author.id, "reason": reason})
        except Exception as e:
            await ctx.send(f"Failed to ban: {e}")

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        """Kick a member from the server."""
        try:
            await member.kick(reason=reason)
            await ctx.send(embed=helpers.make_embed("Kicked", f"{member} was kicked. Reason: {reason or 'No reason.'}"))
            self._log({"type": "kick", "guild": ctx.guild.id if ctx.guild else None, "target": member.id, "by": ctx.author.id, "reason": reason})
        except Exception as e:
            await ctx.send(f"Failed to kick: {e}")

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """Warn a member (stored in-memory and logged)."""
        gid = ctx.guild.id if ctx.guild else 0
        self._warns.setdefault(gid, {}).setdefault(member.id, []).append(reason)
        await ctx.send(embed=helpers.make_embed("Warned", f"{member.mention} was warned. Reason: {reason}"))
        self._log({"type": "warn", "guild": gid, "target": member.id, "by": ctx.author.id, "reason": reason})

    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int = 10):
        """Bulk delete messages from the current channel."""
        if amount <= 0 or amount > 1000:
            await ctx.send("Amount must be between 1 and 1000.")
            return
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(embed=helpers.make_embed("Purged", f"Deleted {len(deleted)} messages."), delete_after=5.0)
        self._log({"type": "purge", "guild": ctx.guild.id if ctx.guild else None, "by": ctx.author.id, "count": len(deleted)})

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int = 0):
        """Set slowmode for the current channel (seconds)."""
        try:
            await ctx.channel.edit(reason=f"Slowmode set by {ctx.author}", slowmode_delay=seconds)
            await ctx.send(embed=helpers.make_embed("Slowmode", f"Set slowmode to {seconds}s"))
            self._log({"type": "slowmode", "guild": ctx.guild.id if ctx.guild else None, "by": ctx.author.id, "seconds": seconds})
        except Exception as e:
            await ctx.send(f"Failed to set slowmode: {e}")

    @commands.command(name="nick")
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: Optional[str] = None):
        """Change a member's nickname."""
        try:
            await member.edit(nick=nickname)
            await ctx.send(embed=helpers.make_embed("Nickname", f"Updated nickname for {member.mention} to {nickname or '(cleared)'}"))
            self._log({"type": "nick", "guild": ctx.guild.id if ctx.guild else None, "target": member.id, "by": ctx.author.id, "nick": nickname})
        except Exception as e:
            await ctx.send(f"Failed to update nickname: {e}")

    @commands.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def role_cmd(self, ctx: commands.Context, member: discord.Member, action: str, *, role_name: str):
        """Add or remove a role: chro role @user add Role Name"""
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f"Role '{role_name}' not found.")
            return
        if action.lower() in ("add", "give"):
            await member.add_roles(role)
            await ctx.send(embed=helpers.make_embed("Role", f"Added {role.name} to {member.mention}"))
            self._log({"type": "role_add", "guild": ctx.guild.id, "target": member.id, "role": role.id, "by": ctx.author.id})
        else:
            await member.remove_roles(role)
            await ctx.send(embed=helpers.make_embed("Role", f"Removed {role.name} from {member.mention}"))
            self._log({"type": "role_remove", "guild": ctx.guild.id, "target": member.id, "role": role.id, "by": ctx.author.id})

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        """Lock the current channel (disable send_messages for @everyone)."""
        overwrites = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
        await ctx.send(embed=helpers.make_embed("Locked", "Channel locked."))
        self._log({"type": "lock", "guild": ctx.guild.id, "channel": ctx.channel.id, "by": ctx.author.id})

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        """Unlock the current channel (enable send_messages for @everyone)."""
        overwrites = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrites)
        await ctx.send(embed=helpers.make_embed("Unlocked", "Channel unlocked."))
        self._log({"type": "unlock", "guild": ctx.guild.id, "channel": ctx.channel.id, "by": ctx.author.id})

    @commands.command(name="mute")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        """Mute a member by applying the 'Muted' role."""
        role = await self._ensure_muted_role(ctx.guild)
        await member.add_roles(role, reason=reason)
        await ctx.send(embed=helpers.make_embed("Muted", f"{member.mention} has been muted."))
        self._log({"type": "mute", "guild": ctx.guild.id, "target": member.id, "by": ctx.author.id, "reason": reason})

    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Unmute a member by removing the 'Muted' role."""
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if role is None:
            await ctx.send("No Muted role configured.")
            return
        await member.remove_roles(role)
        await ctx.send(embed=helpers.make_embed("Unmuted", f"{member.mention} has been unmuted."))
        self._log({"type": "unmute", "guild": ctx.guild.id, "target": member.id, "by": ctx.author.id})

    @commands.command(name="tempmute")
    @commands.has_permissions(manage_roles=True)
    async def tempmute(self, ctx: commands.Context, member: discord.Member, duration: str):
        """Temporarily mute a member. Duration examples: 10m, 1h, 30s."""
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await ctx.send(str(e))
            return
        role = await self._ensure_muted_role(ctx.guild)
        await member.add_roles(role)
        await ctx.send(embed=helpers.make_embed("Tempmuted", f"{member.mention} muted for {duration}"))
        self._log({"type": "tempmute", "guild": ctx.guild.id, "target": member.id, "by": ctx.author.id, "duration_s": seconds})

        async def _unmute_later():
            await asyncio.sleep(seconds)
            try:
                await member.remove_roles(role)
                # best-effort notify
                try:
                    await member.send("You have been unmuted.")
                except Exception:
                    pass
                self._log({"type": "tempmute_unmute", "guild": ctx.guild.id, "target": member.id})
            except Exception:
                pass

        # schedule unmute
        self.bot.loop.create_task(_unmute_later())

    @commands.command(name="massban")
    @commands.is_owner()
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def massban(self, ctx: commands.Context, role: discord.Role):
        """Ban all members with a given role (owner-only, destructive)."""
        members = [m for m in ctx.guild.members if role in m.roles and not m.bot]
        if not members:
            await ctx.send("No members with that role to ban.")
            return
        view = ConfirmView()
        await ctx.send(embed=helpers.make_embed("Confirm massban", f"Ban {len(members)} members with role {role.name}?"), view=view)
        await view.wait()
        if not view.result:
            return
        failed = 0
        for m in members:
            try:
                await m.ban(reason=f"Mass ban by {ctx.author}")
            except Exception:
                failed += 1
        await ctx.send(embed=helpers.make_embed("Massban complete", f"Banned {len(members)-failed} members; failed: {failed}"))
        self._log({"type": "massban", "guild": ctx.guild.id, "by": ctx.author.id, "role": role.id, "count": len(members), "failed": failed})

    @commands.command(name="modhelp")
    async def modhelp(self, ctx: commands.Context):
        """Show moderation commands and usage."""
        desc = (
            "ban @user [reason] — Ban a member\n"
            "kick @user [reason] — Kick a member\n"
            "warn @user reason — Warn a member (stored)\n"
            "purge N — Bulk delete messages\n"
            "slowmode seconds — Set channel slowmode\n"
            "nick @user name — Change nickname\n"
            "role @user add|remove Role Name — Manage roles\n"
            "mute/unmute/tempmute — Mute controls (Muted role)\n"
            "massban Role — Owner-only destructive action (confirm)\n"
        )
        await ctx.send(embed=helpers.make_embed("Moderation Help", desc))

    # ----- slash commands (examples)
    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.checks.has_permissions(ban_members=True)
    async def slash_ban(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        await interaction.response.defer()
        try:
            await member.ban(reason=reason)
            await interaction.followup.send(embed=helpers.make_embed("Banned", f"{member} was banned."))
            self._log({"type": "ban", "guild": interaction.guild_id, "target": member.id, "by": interaction.user.id, "reason": reason})
        except Exception as e:
            await interaction.followup.send(f"Ban failed: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = Moderation(bot)
    await bot.add_cog(cog)

    # Register app command wrappers for major moderation actions to provide slash parity
    try:
        @bot.tree.command(name="kick", description="Kick a member")
        async def _kick(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
            await interaction.response.defer()
            try:
                await member.kick(reason=reason)
                await interaction.followup.send(embed=helpers.make_embed("Kicked", f"{member} was kicked."))
                cog._log({"type": "kick", "guild": interaction.guild_id, "target": member.id, "by": interaction.user.id, "reason": reason})
            except Exception as e:
                await interaction.followup.send(f"Kick failed: {e}", ephemeral=True)

        @bot.tree.command(name="warn", description="Warn a member")
        async def _warn(interaction: discord.Interaction, member: discord.Member, reason: str):
            await interaction.response.defer()
            gid = interaction.guild_id or 0
            cog._warns.setdefault(gid, {}).setdefault(member.id, []).append(reason)
            await interaction.followup.send(embed=helpers.make_embed("Warned", f"{member.mention} was warned. Reason: {reason}"))
            cog._log({"type": "warn", "guild": gid, "target": member.id, "by": interaction.user.id, "reason": reason})

        @bot.tree.command(name="purge", description="Bulk delete messages from channel")
        async def _purge(interaction: discord.Interaction, amount: int = 10):
            await interaction.response.defer()
            chan = interaction.channel
            if not isinstance(chan, discord.TextChannel):
                await interaction.followup.send("This command must be used in a text channel.", ephemeral=True)
                return
            if amount <= 0 or amount > 1000:
                await interaction.followup.send("Amount must be between 1 and 1000.", ephemeral=True)
                return
            try:
                deleted = await chan.purge(limit=amount)
                await interaction.followup.send(embed=helpers.make_embed("Purged", f"Deleted {len(deleted)} messages."))
                cog._log({"type": "purge", "guild": interaction.guild_id, "by": interaction.user.id, "count": len(deleted)})
            except Exception as e:
                await interaction.followup.send(f"Purge failed: {e}", ephemeral=True)

        @bot.tree.command(name="mute", description="Mute a member")
        async def _mute(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
            await interaction.response.defer()
            guild = interaction.guild
            if not isinstance(guild, discord.Guild):
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            try:
                role = await cog._ensure_muted_role(guild)
                await member.add_roles(role, reason=reason)
                await interaction.followup.send(embed=helpers.make_embed("Muted", f"{member.mention} has been muted."))
                cog._log({"type": "mute", "guild": guild.id, "target": member.id, "by": interaction.user.id, "reason": reason})
            except Exception as e:
                await interaction.followup.send(f"Mute failed: {e}", ephemeral=True)

        @bot.tree.command(name="unmute", description="Unmute a member")
        async def _unmute(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer()
            guild = interaction.guild
            if not isinstance(guild, discord.Guild):
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            try:
                role = discord.utils.get(guild.roles, name="Muted")
                if role:
                    await member.remove_roles(role)
                await interaction.followup.send(embed=helpers.make_embed("Unmuted", f"{member.mention} has been unmuted."))
                cog._log({"type": "unmute", "guild": guild.id, "target": member.id, "by": interaction.user.id})
            except Exception as e:
                await interaction.followup.send(f"Unmute failed: {e}", ephemeral=True)

        @bot.tree.command(name="tempmute", description="Temporarily mute a member (e.g. 10m, 1h)")
        async def _tempmute(interaction: discord.Interaction, member: discord.Member, duration: str):
            await interaction.response.defer()
            guild = interaction.guild
            if not isinstance(guild, discord.Guild):
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            try:
                seconds = parse_duration(duration)
            except ValueError as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
            try:
                role = await cog._ensure_muted_role(guild)
                await member.add_roles(role)
                await interaction.followup.send(embed=helpers.make_embed("Tempmuted", f"{member.mention} muted for {duration}"))
                cog._log({"type": "tempmute", "guild": guild.id, "target": member.id, "by": interaction.user.id, "duration_s": seconds})

                async def _unmute_later():
                    await asyncio.sleep(seconds)
                    try:
                        await member.remove_roles(role)
                        try:
                            await member.send("You have been unmuted.")
                        except Exception:
                            pass
                        cog._log({"type": "tempmute_unmute", "guild": guild.id, "target": member.id})
                    except Exception:
                        pass

                interaction.client.loop.create_task(_unmute_later())
            except Exception as e:
                await interaction.followup.send(f"Tempmute failed: {e}", ephemeral=True)

        @bot.tree.command(name="massban", description="Owner: ban all members with a role")
        async def _massban(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer()
            # owner-only enforcement
            settings_owner = getattr(interaction.client, "settings", None)
            owner_id = None
            if settings_owner:
                owner_id = getattr(settings_owner, "OWNER_ID", None)
            if interaction.user.id != owner_id:
                await interaction.followup.send("Only the configured owner can run this command.", ephemeral=True)
                return
            guild = interaction.guild
            if not isinstance(guild, discord.Guild):
                await interaction.followup.send("This command must be used in a server.", ephemeral=True)
                return
            members = [m for m in guild.members if role in m.roles and not m.bot]
            if not members:
                await interaction.followup.send("No members with that role to ban.", ephemeral=True)
                return
            # confirmation is harder in app commands; for safety, require explicit confirm text
            await interaction.followup.send(f"This will ban {len(members)} members. Use the prefix massban command to confirm.", ephemeral=True)
            cog._log({"type": "massban_attempt", "guild": guild.id, "by": interaction.user.id, "role": role.id, "count": len(members)})
    except Exception:
        # app command registration may fail in some environments; ignore
        pass
