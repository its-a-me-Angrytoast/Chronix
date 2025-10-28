"""Economy cog (Phase 3): chro balance, chro pay, chro daily.

Uses `chronix_bot.utils.db.safe_execute_money_transaction` for monetary ops and
supports an in-memory fallback when Postgres isn't configured.
"""
from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import random
import time

from chronix_bot.utils import db, helpers
from discord.ui import View, Button
from typing import Any


class Economy(commands.Cog):
    """Economy commands and slash equivalents."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # simple daily cooldown store: user_id -> last_claim_ts
        self._daily_claims: dict[int, float] = {}

    async def _get_balance(self, user_id: int) -> int:
        pool = db.get_pool()
        if pool is None:
            return db._inmemory_store.get(user_id, 0)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
            return row["balance"] if row else 0

    @commands.command(name="balance", aliases=["bal", "wallet"])
    async def balance(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show a user's balance (defaults to invoker)."""
        member = member or ctx.author
        bal = await self._get_balance(member.id)
        embed = helpers.make_embed(f"{member.display_name}'s Balance", f"{helpers.EMOJI['chrons']} {bal}")
        await ctx.send(embed=embed)

    @app_commands.command(name="balance", description="Show a user's balance")
    async def slash_balance(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        bal = await self._get_balance(member.id)
        embed = helpers.make_embed(f"{member.display_name}'s Balance", f"{helpers.EMOJI['chrons']} {bal}")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="pay")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Pay another user a certain amount of Chrons."""
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        # confirmation flow for prefix command
        confirm_embed = helpers.make_embed("Confirm Payment", f"Transfer {helpers.format_chrons(amount)} to {member.mention}?")

        class ConfirmView(View):
            def __init__(self, timeout: float = 30.0):
                super().__init__(timeout=timeout)
                self.result: Optional[bool] = None

            @Button(label="Confirm", style=discord.ButtonStyle.green)
            async def confirm(self, interaction: discord.Interaction, button: Button):
                self.result = True
                self.stop()
                await interaction.response.edit_message(content=None, embed=helpers.make_embed("Confirmed", "Payment will be processed."), view=None)

            @Button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                self.result = False
                self.stop()
                await interaction.response.edit_message(content=None, embed=helpers.make_embed("Cancelled", "Payment cancelled."), view=None)

        view = ConfirmView()
        msg = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()
        if not view.result:
            await ctx.send("Payment cancelled or timed out.")
            return

        try:
            new_bal = await self._transfer(ctx.author.id, member.id, amount)
            await ctx.send(f"Transferred {helpers.format_chrons(amount)} to {member.mention}. Your new balance: {new_bal}")
        except Exception as e:
            await ctx.send(f"Payment failed: {e}")

    @app_commands.command(name="pay", description="Pay another user Chrons")
    async def slash_pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        # Slash commands: use ephemeral confirmation with buttons
        confirm_embed = helpers.make_embed("Confirm Payment", f"Transfer {helpers.format_chrons(amount)} to {member.mention}?")

        class SlashConfirmView(View):
            def __init__(self, requester_id: int, timeout: float = 30.0):
                super().__init__(timeout=timeout)
                self.requester_id = requester_id
                self.result: Optional[bool] = None

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                # only the requester can confirm
                return interaction.user.id == self.requester_id

            @Button(label="Confirm", style=discord.ButtonStyle.green)
            async def confirm(self, interaction: discord.Interaction, button: Button):
                self.result = True
                self.stop()
                await interaction.response.edit_message(content=None, embed=helpers.make_embed("Confirmed", "Payment will be processed."), view=None)

            @Button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                self.result = False
                self.stop()
                await interaction.response.edit_message(content=None, embed=helpers.make_embed("Cancelled", "Payment cancelled."), view=None)

        view = SlashConfirmView(requester_id=interaction.user.id)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
        # wait for view to finish
        await view.wait()
        if not view.result:
            # if cancelled or timed out
            return
        try:
            new_bal = await self._transfer(interaction.user.id, member.id, amount)
            await interaction.followup.send(f"Transferred {helpers.format_chrons(amount)} to {member.mention}. Your new balance: {new_bal}")
        except Exception as e:
            await interaction.followup.send(f"Payment failed: {e}", ephemeral=True)

    async def _transfer(self, from_id: int, to_id: int, amount: int) -> int:
        """Atomically transfer amount from from_id to to_id.

        Uses a DB transaction when a pool is available; otherwise uses the
        in-memory lock to perform an atomic update.
        Returns the new balance for the payer.
        """
        pool = db.get_pool()
        if pool is None:
            # in-memory atomic transfer
            async with db._inmemory_lock:
                payer = db._inmemory_store.get(from_id, 0)
                if payer < amount:
                    raise RuntimeError("Insufficient funds")
                db._inmemory_store[from_id] = payer - amount
                db._inmemory_store[to_id] = db._inmemory_store.get(to_id, 0) + amount
                return db._inmemory_store[from_id]

        # DB-backed transfer: lock both rows in a consistent order to avoid deadlocks
        async with pool.acquire() as conn:
            async with conn.transaction():
                # lock smaller id first for deterministic ordering
                first, second = (from_id, to_id) if from_id < to_id else (to_id, from_id)
                await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1 FOR UPDATE", first)
                await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1 FOR UPDATE", second)

                row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", from_id)
                payer = row["balance"] if row else 0
                if payer < amount:
                    raise RuntimeError("Insufficient funds")

                # ensure receiver exists
                rrow = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", to_id)
                if rrow is None:
                    await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", to_id, amount, db.datetime.utcnow())
                else:
                    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, to_id)

                await conn.execute("UPDATE users SET balance = balance - $1 WHERE user_id = $2", amount, from_id)

                # log transactions
                await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1, $2, $3, $4, $5)",
                                   from_id, -amount, f"pay to {to_id}", payer - amount, db.datetime.utcnow())
                await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1, $2, $3, $4, $5)",
                                   to_id, amount, f"pay from {from_id}", (rrow["balance"] if rrow else 0) + amount, db.datetime.utcnow())

                # return new payer balance
                new_row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", from_id)
                return new_row["balance"]

    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claim daily reward (cooldown 24h)."""
        uid = ctx.author.id
        now = time.time()
        last = self._daily_claims.get(uid, 0)
        if now - last < 24 * 3600:
            await ctx.send("You have already claimed your daily reward. Come back later.")
            return

        # reward logic: simple fixed reward + small RNG
        base = 100
        bonus = random.randint(0, 50)
        total = base + bonus
        await db.safe_execute_money_transaction(uid, total, "daily reward")
        self._daily_claims[uid] = now
        await ctx.send(f"You claimed your daily reward: {helpers.EMOJI['chrons']} {total}")

    @app_commands.command(name="daily", description="Claim your daily Chrons")
    async def slash_daily(self, interaction: discord.Interaction):
        uid = interaction.user.id
        now = time.time()
        last = self._daily_claims.get(uid, 0)
        if now - last < 24 * 3600:
            await interaction.response.send_message("You have already claimed your daily reward. Come back later.", ephemeral=True)
            return

        base = 100
        bonus = random.randint(0, 50)
        total = base + bonus
        await db.safe_execute_money_transaction(uid, total, "daily reward")
        self._daily_claims[uid] = now
        await interaction.response.send_message(f"You claimed your daily reward: {helpers.EMOJI['chrons']} {total}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
