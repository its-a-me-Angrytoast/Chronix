from __future__ import annotations

import asyncio
from datetime import timedelta

import discord
from discord.ext import commands, tasks

from chronix_bot.utils import helpers
from chronix_bot.utils import interest


class InterestCog(commands.Cog):
    """Cog to expose interest application commands and a daily task."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_interest.start()

    def cog_unload(self) -> None:
        self.daily_interest.cancel()

    @tasks.loop(hours=24)
    async def daily_interest(self):
        try:
            updated = await interest.apply_interest(rate_percent=0.1)  # default 0.1%
            if updated:
                # post to owner DM if available
                owner = self.bot.owner_id
                if owner:
                    try:
                        user = await self.bot.fetch_user(owner)
                        await user.send(f"Applied interest to {updated} accounts.")
                    except Exception:
                        pass
        except Exception:
            pass

    @commands.command(name="apply_interest")
    @commands.has_permissions(administrator=True)
    async def apply_interest_cmd(self, ctx: commands.Context, rate_percent: float = 0.1):
        updated = await interest.apply_interest(rate_percent=rate_percent)
        await ctx.send(embed=helpers.make_embed("Interest Applied", f"Credited {updated} accounts with {rate_percent}%"))


async def setup(bot: commands.Bot):
    await bot.add_cog(InterestCog(bot))
