"""i18n commands: set guild language and translate helper commands."""
from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from chronix_bot.utils import i18n as i18n_utils
from chronix_bot.utils import persistence as persistence_utils
from chronix_bot.utils import helpers


class I18nCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setlang")
    @commands.has_permissions(manage_guild=True)
    async def setlang(self, ctx: commands.Context, locale: str):
        """Set the guild default locale (e.g., 'en')."""
        gid = ctx.guild.id if ctx.guild else 0
        persistence_utils.set_guild_setting(gid, "locale", locale)
        await ctx.send(embed=helpers.make_embed("Locale Set", f"Guild locale set to {locale}"))

    @commands.command(name="translate")
    async def translate(self, ctx: commands.Context, key: str, *, args: Optional[str] = ""):
        """Translate a key using the guild locale. Optional args as key=value pairs separated by spaces."""
        gid = ctx.guild.id if ctx.guild else 0
        locale = persistence_utils.get_guild_setting(gid, "locale", "en")
        params = {}
        if args:
            for part in args.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k] = v
        txt = i18n_utils.t(key, locale=locale, **params)
        await ctx.send(embed=helpers.make_embed(f"Translation ({locale})", txt))


async def setup(bot: commands.Bot):
    await bot.add_cog(I18nCog(bot))
