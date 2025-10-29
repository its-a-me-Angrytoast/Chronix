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
<<<<<<< HEAD
=======
from chronix_bot.utils import inventory as inventory_utils
from chronix_bot.utils import logger as logger_utils
>>>>>>> Cursor-Branch


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
<<<<<<< HEAD
        
        # Generate and reveal loot
        loot = loot_util.generate_loot(crate_type)
        coins = int(loot.get("coins", 0))
        
=======

        # Generate and reveal loot
        loot = loot_util.generate_loot(crate_type)
        coins = int(loot.get("coins", 0))

>>>>>>> Cursor-Branch
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
<<<<<<< HEAD
        
        # Build reveal embed
=======

        # Persist item drops and build reveal embed
>>>>>>> Cursor-Branch
        description_lines = []
        if coins > 0:
            description_lines.extend([
                f"You found {helpers.format_chrons(coins)}!",
                f"New balance: {helpers.format_chrons(new_balance)}"
            ])
<<<<<<< HEAD
            
        items = loot.get("items", [])
        if items:
            item_lines = [f"• {i.get('name')} ({i.get('rarity')})" for i in items]
            description_lines.append("\nItems:\n" + "\n".join(item_lines))
            
=======

        items = loot.get("items", [])
        rare_broadcasts = []
        if items:
            item_lines = []
            for i in items:
                item_lines.append(f"• {i.get('name')} ({i.get('rarity')})")
                # persist drop into inventory according to type
                itype = str(i.get("type", "misc")).lower()
                if itype == "gem":
                    inventory_utils.add_gem(interaction.user.id, i.get("name"), power=1)
                elif itype == "pet":
                    inventory_utils.add_pet(interaction.user.id, i.get("name"))
                else:
                    inventory_utils.add_item(interaction.user.id, i.get("name"), meta={"rarity": i.get("rarity")})

                # collect rare drops for broadcast/logging
                if i.get("is_rare"):
                    rare_broadcasts.append(i)

            description_lines.append("\nItems:\n" + "\n".join(item_lines))

>>>>>>> Cursor-Branch
        embed = helpers.make_embed(
            "Crate Results",
            "\n".join(description_lines) or "The crate was empty!"
        )
        await message.edit(embed=embed)

<<<<<<< HEAD
=======
        # Enqueue a crate opening log (non-blocking)
        try:
            q = logger_utils.start_background_writer()
            q.put_nowait({
                "event": "crate_open",
                "user_id": int(interaction.user.id),
                "crate_type": crate_type,
                "coins": coins,
                "items": [dict(i) for i in items],
            })
        except Exception:
            # never raise for logging failures
            pass

        # Broadcast rare drops to the channel where the crate was opened
        if rare_broadcasts:
            try:
                chan = interaction.channel or getattr(interaction, "channel", None)
                if chan is not None:
                    for r in rare_broadcasts:
                        await chan.send(f"✨ {interaction.user.mention} just found **{r.get('name')}** ({r.get('rarity')}) in a {crate_type} crate!")
            except Exception:
                # ignore broadcast failures
                pass

>>>>>>> Cursor-Branch
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
            
<<<<<<< HEAD
=======
        # If user has an unopened crate of that type, consume it first
        consumed = inventory_utils.consume_unopened_crate(ctx.author.id, crate_type)
        if consumed:
            await ctx.send(f"Consumed one unopened {crate_type} crate from your inventory.")

>>>>>>> Cursor-Branch
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
            
<<<<<<< HEAD
        # Run reveal if confirmed
        await self._reveal_crate(interaction, crate_type)

<<<<<<< Updated upstream
=======
    @app_commands.command(name="crate_gift")
    @app_commands.describe(member="Member to gift the crate to", crate_type="Type of crate to gift")
    async def slash_gift_crate(self, interaction: discord.Interaction, member: discord.Member, crate_type: str = "basic") -> None:
        """Slash command: gift an unopened crate to another user."""
        try:
            crate = inventory_utils.add_unopened_crate(member.id, crate_type)
            await interaction.response.send_message(f"Gave a {crate_type} crate to {member.mention}! (ID: {crate.get('crate_id')})", ephemeral=True)
            # attempt to DM the recipient
            try:
                await member.send(f"You received a {crate_type} crate from {interaction.user.display_name}! Use the bot to open it.")
            except Exception:
                # ignore DM failures
                pass
        except Exception as exc:
            await interaction.response.send_message(f"Failed to gift crate: {exc}", ephemeral=True)

    @app_commands.command(name="mycrates")
    async def slash_mycrates(self, interaction: discord.Interaction) -> None:
        """Slash command: list your unopened crates and misc inventory items."""
        crates = inventory_utils.list_unopened_crates(interaction.user.id)
        items = inventory_utils.list_items(interaction.user.id)
        lines = []
        if crates:
            for c in crates:
                lines.append(f"Crate: {c.get('crate_type')} (ID: {c.get('crate_id')})")
        else:
            lines.append("No unopened crates.")

        if items:
            lines.append("\nMisc Items:")
            for it in items:
                lines.append(f"• {it.get('name')} (ID: {it.get('item_id')})")

        await interaction.response.send_message(embed=helpers.make_embed("Your Inventory", "\n".join(lines)), ephemeral=True)

=======
        # If user has an unopened crate of that type, consume it first
        try:
            consumed = inventory_utils.consume_unopened_crate(interaction.user.id, crate_type)
            if consumed:
                await interaction.followup.send(f"Consumed one unopened {crate_type} crate from your inventory.", ephemeral=True)
        except Exception:
            pass

        # Run reveal if confirmed
        await self._reveal_crate(interaction, crate_type)

<<<<<<< Updated upstream
>>>>>>> Cursor-Branch
=======
    @app_commands.command(name="crate_gift")
    @app_commands.describe(member="Member to gift the crate to", crate_type="Type of crate to gift")
    async def slash_gift_crate(self, interaction: discord.Interaction, member: discord.Member, crate_type: str = "basic") -> None:
        """Slash command: gift an unopened crate to another user."""
        try:
            crate = inventory_utils.add_unopened_crate(member.id, crate_type)
            await interaction.response.send_message(f"Gave a {crate_type} crate to {member.mention}! (ID: {crate.get('crate_id')})", ephemeral=True)
            # attempt to DM the recipient
            try:
                await member.send(f"You received a {crate_type} crate from {interaction.user.display_name}! Use the bot to open it.")
            except Exception:
                # ignore DM failures
                pass
        except Exception as exc:
            await interaction.response.send_message(f"Failed to gift crate: {exc}", ephemeral=True)

    @app_commands.command(name="mycrates")
    async def slash_mycrates(self, interaction: discord.Interaction) -> None:
        """Slash command: list your unopened crates and misc inventory items."""
        crates = inventory_utils.list_unopened_crates(interaction.user.id)
        items = inventory_utils.list_items(interaction.user.id)
        lines = []
        if crates:
            for c in crates:
                lines.append(f"Crate: {c.get('crate_type')} (ID: {c.get('crate_id')})")
        else:
            lines.append("No unopened crates.")

        if items:
            lines.append("\nMisc Items:")
            for it in items:
                lines.append(f"• {it.get('name')} (ID: {it.get('item_id')})")

        await interaction.response.send_message(embed=helpers.make_embed("Your Inventory", "\n".join(lines)), ephemeral=True)

>>>>>>> Stashed changes
    @commands.command(name="crate_gift", aliases=["giftcrate", "crategift"])
    async def gift_crate(self, ctx: commands.Context, member: discord.Member, crate_type: str = "basic") -> None:
        """Gift an unopened crate to another user (adds to their inventory)."""
        crate = inventory_utils.add_unopened_crate(member.id, crate_type)
        await ctx.send(embed=helpers.make_embed("Crate Gifted", f"Gave a {crate_type} crate to {member.mention}! (ID: {crate.get('crate_id')})"))

    @commands.command(name="mycrates", aliases=["crates_list", "unopened"])
    async def my_crates(self, ctx: commands.Context) -> None:
        """List your unopened crates and misc items in inventory."""
        crates = inventory_utils.list_unopened_crates(ctx.author.id)
        items = inventory_utils.list_items(ctx.author.id)
        lines = []
        if crates:
            for c in crates:
                lines.append(f"Crate: {c.get('crate_type')} (ID: {c.get('crate_id')})")
        else:
            lines.append("No unopened crates.")

        if items:
            lines.append("\nMisc Items:")
            for it in items:
                lines.append(f"• {it.get('name')} (ID: {it.get('item_id')})")

        await ctx.send(embed=helpers.make_embed("Your Inventory", "\n".join(lines)))

<<<<<<< HEAD
>>>>>>> Stashed changes
=======
>>>>>>> Cursor-Branch

async def setup(bot: commands.Bot) -> None:
    """Add the crates cog to the bot."""
    await bot.add_cog(Crates(bot))