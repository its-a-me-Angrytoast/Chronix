"""Crate opening system for Phase 4.

This module implements the crate opening flow, including UI confirmation
and animated reveal embeds. Uses the loot util to determine drops based
on crate_pools.yaml tables.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import loot as loot_util
from chronix_bot.utils import db as db_utils


class CrateView(discord.ui.View):
    """Confirmation view for opening crates."""
    def __init__(self, crate_type: str):
        super().__init__(timeout=60.0)
        self.crate_type = crate_type
        self.confirmed = False
        
    @discord.ui.button(label="Open Crate", style=discord.ButtonStyle.primary)
    async def confirm_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User clicked confirm - enable result delivery."""
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User clicked cancel - just stop view."""
        await interaction.response.send_message("Cancelled opening the crate.", ephemeral=True)
        self.stop()


class Crates(commands.Cog):
    """Crate opening and reward system.
    
    This cog provides commands for opening crates and receiving randomized
    rewards. Uses crate_pools.yaml for loot tables and displays animated
    reveal embeds.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _reveal_crate(self, interaction: discord.Interaction, crate_type: str) -> None:
        """Run the crate opening animation and reveal drops.
        
        Shows a series of embed edits to build suspense, then reveals
        the final loot table results.
        """
        # Initial "opening" message
        embed = helpers.make_embed("Opening Crate", f"Opening your {crate_type} crate...")
        message = await interaction.followup.send(embed=embed)
        
        # Suspense updates
        embed.description = "The crate begins to glow..."
        await message.edit(embed=embed)
        await asyncio.sleep(1.0)
        
        embed.description = "Items materialize..."
        await message.edit(embed=embed)
        await asyncio.sleep(1.0)
        
        # Generate and reveal loot
        loot = loot_util.generate_loot(crate_type)
        coins = int(loot.get("coins", 0))
        
        # Award coins if any (uses safe transaction)
        new_balance = None
        if coins > 0:
            try:
                new_balance = await db_utils.safe_execute_money_transaction(
                    interaction.user.id, coins, f"crate reward ({crate_type})"
                )
            except Exception as exc:
                await interaction.followup.send(
                    f"Error awarding crate coins: {exc}", ephemeral=True
                )
                return
        
        # Build reveal embed
        description_lines = []
        if coins > 0:
            description_lines.extend([
                f"You found {helpers.format_chrons(coins)}!",
                f"New balance: {helpers.format_chrons(new_balance)}"
            ])
            
        items = loot.get("items", [])
        if items:
            item_lines = [f"• {i.get('name')} ({i.get('rarity')})" for i in items]
            description_lines.append("\nItems:\n" + "\n".join(item_lines))
            
        embed = helpers.make_embed(
            "Crate Results",
            "\n".join(description_lines) or "The crate was empty!"
        )
        await message.edit(embed=embed)

    @commands.command(name="crate", aliases=["opencrate", "open"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open_crate(self, ctx: commands.Context, crate_type: str = "basic") -> None:
        """Open a crate and receive random rewards."""
        # Create confirmation view
        view = CrateView(crate_type)
        await ctx.send(
            f"Are you sure you want to open your {crate_type} crate?",
            view=view
        )
        
        # Wait for response
        await view.wait()
        if not view.confirmed:
            return
            
        # Run reveal if confirmed
        await self._reveal_crate(ctx, crate_type)
        
    @app_commands.command(name="crate")
    @app_commands.describe(crate_type="The type of crate to open (basic, rare, etc)")
    async def slash_crate(self, interaction: discord.Interaction, crate_type: str = "basic") -> None:
        """Open a crate to receive random rewards."""
        # Create confirmation view
        view = CrateView(crate_type)
        await interaction.response.send_message(
            f"Are you sure you want to open your {crate_type} crate?",
            view=view,
            ephemeral=True
        )
        
        # Wait for response
        await view.wait()
        if not view.confirmed:
            return
            
        # Run reveal if confirmed
        await self._reveal_crate(interaction, crate_type)


async def setup(bot: commands.Bot) -> None:
    """Add the crates cog to the bot."""
    await bot.add_cog(Crates(bot))