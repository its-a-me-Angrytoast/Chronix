from __future__ import annotations

import random
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import db, helpers


class Gambling(commands.Cog):
    """Simple gambling commands (coinflip, gamble).

    This cog uses the existing `db.safe_execute_money_transaction` helper so
    it works with either the in-memory dev store or a real Postgres pool.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_balance(self, user_id: int) -> int:
        pool = db.get_pool()
        if pool is None:
            return db._inmemory_store.get(user_id, 0)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
            return row["balance"] if row else 0

    @commands.command(name="coinflip")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def coinflip(self, ctx: commands.Context, choice: str, amount: int):
        """Bet on a coinflip. choice = heads|tails, amount = positive int."""
        choice = choice.lower()
        if choice not in ("heads", "tails", "h", "t"):
            await ctx.send("Choose 'heads' or 'tails'.")
            return

        if amount <= 0:
            await ctx.send("Bet amount must be positive.")
            return

        bal = await self._get_balance(ctx.author.id)
        if amount > bal:
            await ctx.send("Insufficient funds for that bet.")
            return

        # perform outcome
        flip = random.choice(("heads", "tails"))
        won = flip.startswith(choice[0])

        try:
            if won:
                # user wins amount (profit = amount)
                new_bal = await db.safe_execute_money_transaction(ctx.author.id, amount, f"coinflip win {flip}")
                embed = helpers.make_embed("Coinflip — You won!", f"Result: **{flip}**\nYou won {helpers.format_chrons(amount)}\nNew balance: {helpers.EMOJI['chrons']} {new_bal}")
            else:
                new_bal = await db.safe_execute_money_transaction(ctx.author.id, -amount, f"coinflip lose {flip}")
                embed = helpers.make_embed("Coinflip — You lost", f"Result: **{flip}**\nYou lost {helpers.format_chrons(amount)}\nNew balance: {helpers.EMOJI['chrons']} {new_bal}")
        except Exception as e:
            await ctx.send(f"Bet failed: {e}")
            return

        await ctx.send(embed=embed)

    @app_commands.command(name="coinflip", description="Bet on a coinflip (heads/tails)")
    async def slash_coinflip(self, interaction: discord.Interaction, choice: str, amount: int):
        choice = choice.lower()
        if choice not in ("heads", "tails", "h", "t"):
            await interaction.response.send_message("Choose 'heads' or 'tails'.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("Bet amount must be positive.", ephemeral=True)
            return

        bal = await self._get_balance(interaction.user.id)
        if amount > bal:
            await interaction.response.send_message("Insufficient funds for that bet.", ephemeral=True)
            return

        flip = random.choice(("heads", "tails"))
        won = flip.startswith(choice[0])

        try:
            if won:
                new_bal = await db.safe_execute_money_transaction(interaction.user.id, amount, f"coinflip win {flip}")
                embed = helpers.make_embed("Coinflip — You won!", f"Result: **{flip}**\nYou won {helpers.format_chrons(amount)}\nNew balance: {helpers.EMOJI['chrons']} {new_bal}")
            else:
                new_bal = await db.safe_execute_money_transaction(interaction.user.id, -amount, f"coinflip lose {flip}")
                embed = helpers.make_embed("Coinflip — You lost", f"Result: **{flip}**\nYou lost {helpers.format_chrons(amount)}\nNew balance: {helpers.EMOJI['chrons']} {new_bal}")
        except Exception as e:
            await interaction.response.send_message(f"Bet failed: {e}", ephemeral=True)
            return

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gambling(bot))
