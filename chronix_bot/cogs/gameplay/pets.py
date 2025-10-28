"""Simple pets cog for Phase 4.

Provides adopt, feed, and show commands using the file-backed inventory
helpers in `chronix_bot.utils.inventory`.
"""
from __future__ import annotations

from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import inventory as inv
from chronix_bot.utils import helpers


class Pets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="adopt")
    async def adopt(self, ctx: commands.Context, species: str):
        pet = inv.add_pet(ctx.author.id, species)
        await ctx.send(embed=helpers.make_embed("Adopted Pet", f"You adopted a {species}! ID: {pet['pet_id']}"))

    @commands.command(name="pets")
    async def pets(self, ctx: commands.Context):
        pets = inv.list_pets(ctx.author.id)
        if not pets:
            await ctx.send(embed=helpers.make_embed("No Pets", "You have no pets. Adopt one with `chro adopt <species>`."))
            return
        lines = [f"ID:{p['pet_id']} - {p['species']} (Lvl {p.get('level',1)} XP:{p.get('xp',0)})" for p in pets]
        await ctx.send(embed=helpers.make_embed(f"{ctx.author.name}'s Pets", "\n".join(lines)))

    @commands.command(name="feed")
    async def feed(self, ctx: commands.Context, pet_id: int):
        try:
            pet = inv.feed_pet(ctx.author.id, pet_id)
            await ctx.send(embed=helpers.make_embed("Fed Pet", f"{pet['species']} gained xp. Now level {pet.get('level',1)} (XP {pet.get('xp',0)})"))
        except ValueError as e:
            await ctx.send(str(e))

    @app_commands.command(name="adopt")
    async def slash_adopt(self, interaction: discord.Interaction, species: str):
        pet = inv.add_pet(interaction.user.id, species)
        await interaction.response.send_message(embed=helpers.make_embed("Adopted Pet", f"You adopted a {species}! ID: {pet['pet_id']}"))

    @app_commands.command(name="pets")
    async def slash_pets(self, interaction: discord.Interaction):
        pets = inv.list_pets(interaction.user.id)
        if not pets:
            await interaction.response.send_message(embed=helpers.make_embed("No Pets", "You have no pets. Adopt one with /adopt <species>"))
            return
        lines = [f"ID:{p['pet_id']} - {p['species']} (Lvl {p.get('level',1)} XP:{p.get('xp',0)})" for p in pets]
        await interaction.response.send_message(embed=helpers.make_embed(f"{interaction.user.name}'s Pets", "\n".join(lines)))

    @app_commands.command(name="feed")
    async def slash_feed(self, interaction: discord.Interaction, pet_id: int):
        try:
            pet = inv.feed_pet(interaction.user.id, pet_id)
            await interaction.response.send_message(embed=helpers.make_embed("Fed Pet", f"{pet['species']} gained xp. Now level {pet.get('level',1)} (XP {pet.get('xp',0)})"))
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pets(bot))
