"""Gem inventory and socketing system for Phase 4.

This module provides commands for managing gems, including inventory viewing,
merging gems for upgrades, and socketing gems into weapons. Uses the loot
tables and DB helpers for persistence.
"""
from __future__ import annotations

from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import db as db_utils
from chronix_bot.utils import inventory as inv


class GemConfirmView(discord.ui.View):
    """Confirmation view for merging or socketing gems."""
    def __init__(self, action: str):
        super().__init__(timeout=60.0)
        self.action = action
        self.confirmed = False
        
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User clicked confirm."""
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User clicked cancel."""
        await interaction.response.send_message(f"Cancelled {self.action}.", ephemeral=True)
        self.stop()


class Gems(commands.Cog):
    """Gem collection and socketing system.
    
    This cog provides commands for managing gems, including viewing your
    collection, merging gems for upgrades, and socketing gems into weapons
    for stat boosts.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="gems", aliases=["g", "inventory"])
    async def gems(self, ctx: commands.Context) -> None:
        """View your gem collection."""
        gems = inv.list_gems(ctx.author.id)
        if not gems:
            embed = helpers.make_embed(
                f"{ctx.author.name}'s Gems {helpers.EMOJI['gems']}",
                "No gems yet! Try using the hunt command to find some."
            )
            await ctx.send(embed=embed)
            return

        lines = [f"ID:{g['gem_id']} - {g['gem_type']} (Power {g['power']})" for g in gems]
        embed = helpers.make_embed(f"{ctx.author.name}'s Gems {helpers.EMOJI['gems']}", "\n".join(lines))
        await ctx.send(embed=embed)

    @commands.command(name="merge", aliases=["combine", "upgrade"])
    async def merge_gems(self, ctx: commands.Context, gem_name: str) -> None:
        """Merge multiple gems of the same type to create a higher tier gem."""
        view = GemConfirmView("gem merge")
        await ctx.send(
            f"Are you sure you want to merge your {gem_name} gems?\n"
            "This will consume the gems and attempt to create a higher tier version.",
            view=view
        )
        
        await view.wait()
        if not view.confirmed:
            return
        
        try:
            new = inv.merge_gems(ctx.author.id, gem_name, count=2)
        except ValueError as e:
            await ctx.send(str(e))
            return
        embed = helpers.make_embed("Gem Merge Success", f"Created {new['gem_type']} (Power {new['power']}) — ID: {new['gem_id']}")
        await ctx.send(embed=embed)

    @app_commands.command(name="gems")
    async def slash_gems(self, interaction: discord.Interaction) -> None:
        """View your gem collection."""
        gems = inv.list_gems(interaction.user.id)
        if not gems:
            embed = helpers.make_embed(
                f"{interaction.user.name}'s Gems {helpers.EMOJI['gems']}",
                "No gems yet! Try using the hunt command to find some."
            )
            await interaction.response.send_message(embed=embed)
            return
        lines = [f"ID:{g['gem_id']} - {g['gem_type']} (Power {g['power']})" for g in gems]
        embed = helpers.make_embed(f"{interaction.user.name}'s Gems {helpers.EMOJI['gems']}", "\n".join(lines))
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="merge")
    @app_commands.describe(gem_name="The name of the gems to merge")
    async def slash_merge(self, interaction: discord.Interaction, gem_name: str) -> None:
        """Merge multiple gems of the same type to create a higher tier gem."""
        view = GemConfirmView("gem merge")
        await interaction.response.send_message(
            f"Are you sure you want to merge your {gem_name} gems?\n"
            "This will consume the gems and attempt to create a higher tier version.",
            view=view,
            ephemeral=True
        )
        
        await view.wait()
        if not view.confirmed:
            return
        
        try:
            new = inv.merge_gems(interaction.user.id, gem_name, count=2)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return
        embed = helpers.make_embed("Gem Merge Success", f"Created {new['gem_type']} (Power {new['power']}) — ID: {new['gem_id']}")
        await interaction.followup.send(embed=embed)