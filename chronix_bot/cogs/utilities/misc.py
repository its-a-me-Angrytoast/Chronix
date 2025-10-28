"""Utility and miscellaneous commands (Phase 6 initial set).

Implements serverinfo, userinfo, roleinfo, avatar, choose, roll, poll, say
and simple embed helper. Slash parity is provided where sensible.
"""
from __future__ import annotations

import random
import re
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers


class Misc(commands.Cog):
    """Various small utility commands useful in many servers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx: commands.Context):
        g = ctx.guild
        if g is None:
            await ctx.send("This command must be used in a server.")
            return
        desc = (
            f"Name: {g.name}\n"
            f"ID: {g.id}\n"
            f"Members: {g.member_count}\n"
            f"Roles: {len(g.roles)}\n"
            f"Channels: {len(g.channels)}\n"
            f"Created: {g.created_at.isoformat()}"
        )
        await ctx.send(embed=helpers.make_embed("Server Info", desc))

    @commands.command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        desc = (
            f"Name: {member}\n"
            f"ID: {member.id}\n"
            f"Joined: {getattr(member, 'joined_at', 'N/A')}\n"
            f"Bot: {member.bot}"
        )
        await ctx.send(embed=helpers.make_embed("User Info", desc))

    @commands.command(name="roleinfo")
    async def roleinfo(self, ctx: commands.Context, *, role_name: str):
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f"Role '{role_name}' not found.")
            return
        members = [m for m in ctx.guild.members if role in m.roles]
        desc = f"Name: {role.name}\nID: {role.id}\nMembers: {len(members)}\nColor: {role.color}"
        await ctx.send(embed=helpers.make_embed("Role Info", desc))

    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        await ctx.send(member.display_avatar.url)

    @commands.command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str):
        """Choose between options separated by `|` e.g. chro choose a|b|c"""
        parts = [p.strip() for p in options.split("|") if p.strip()]
        if not parts:
            await ctx.send("No options provided.")
            return
        pick = random.choice(parts)
        await ctx.send(embed=helpers.make_embed("Choice", pick))

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, notation: Optional[str] = None):
        """Roll dice: NdM (e.g. 2d6) or simple integer to roll 1dN. Default 1d20."""
        if notation is None:
            notation = "1d20"
        m = re.match(r"^(?:(\d+)d)?(\d+)$", notation)
        if not m:
            await ctx.send("Invalid notation. Use NdM like 2d6 or just 20 for d20.")
            return
        n = int(m.group(1)) if m.group(1) else 1
        s = int(m.group(2))
        if n <= 0 or s <= 0 or n > 100:
            await ctx.send("Bad roll parameters.")
            return
        rolls = [random.randint(1, s) for _ in range(n)]
        await ctx.send(embed=helpers.make_embed("Roll", f"Rolls: {rolls} Total: {sum(rolls)}"))

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, *, question_and_options: str):
        """Create a quick reaction poll. Usage: chro poll Question | Option1 | Option2"""
        parts = [p.strip() for p in question_and_options.split("|") if p.strip()]
        if len(parts) < 2:
            await ctx.send("Provide a question and at least one option separated by `|`.")
            return
        question = parts[0]
        options = parts[1:][:10]
        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        desc = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
        msg = await ctx.send(embed=helpers.make_embed(f"Poll: {question}", desc))
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

    @commands.command(name="say")
    @commands.is_owner()
    async def say(self, ctx: commands.Context, *, text: str):
        """Owner-only say command to let the bot say something."""
        await ctx.send(text)

    @app_commands.command(name="serverinfo")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        await interaction.response.send_message("See prefix command chro serverinfo for details.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
