from __future__ import annotations

import asyncio
import json
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers, db

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BANK_FILE = DATA_DIR / "banks.json"
_lock = asyncio.Lock()


async def _read_banks() -> dict:
    if not BANK_FILE.exists():
        return {}
    def _load():
        with BANK_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return await asyncio.to_thread(_load)


async def _write_banks(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    def _dump():
        with BANK_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    await asyncio.to_thread(_dump)


class Bank(commands.Cog):
    """Simple bank: deposit and withdraw moving funds between on-hand balance
    and a bank store persisted in `data/banks.json`.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="deposit")
    async def deposit(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        uid = ctx.author.id
        try:
            await db.safe_execute_money_transaction(uid, -amount, "bank deposit")
        except Exception as e:
            await ctx.send(f"Deposit failed: {e}")
            return

        pool = db.get_pool()
        if pool is not None:
            # DB-backed bank: upsert into user_banks table
            async with pool.acquire() as conn:
                await conn.execute("INSERT INTO user_banks (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET balance = user_banks.balance + $2", uid, amount)
        else:
            async with _lock:
                banks = await _read_banks()
                banks[str(uid)] = banks.get(str(uid), 0) + amount
                await _write_banks(banks)

        await ctx.send(embed=helpers.make_embed("Deposit Complete", f"Deposited {helpers.format_chrons(amount)}"))

    @commands.command(name="withdraw")
    async def withdraw(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            await ctx.send("Amount must be positive.")
            return

        uid = ctx.author.id
        pool = db.get_pool()
        if pool is not None:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT balance FROM user_banks WHERE user_id = $1 FOR UPDATE", uid)
                    bal = row["balance"] if row else 0
                    if amount > bal:
                        await ctx.send("Insufficient bank balance.")
                        return
                    # deduct bank
                    await conn.execute("UPDATE user_banks SET balance = balance - $1 WHERE user_id = $2", amount, uid)
            try:
                await db.safe_execute_money_transaction(uid, amount, "bank withdraw")
            except Exception as e:
                # rollback bank deduction
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE user_banks SET balance = balance + $1 WHERE user_id = $2", amount, uid)
                await ctx.send(f"Withdrawal failed: {e}")
                return
            await ctx.send(embed=helpers.make_embed("Withdrawal Complete", f"Withdrew {helpers.format_chrons(amount)}"))
            return

        async with _lock:
            banks = await _read_banks()
            bal = banks.get(str(uid), 0)
            if amount > bal:
                await ctx.send("Insufficient bank balance.")
                return
            banks[str(uid)] = bal - amount
            await _write_banks(banks)

        # credit user
        try:
            await db.safe_execute_money_transaction(uid, amount, "bank withdraw")
        except Exception as e:
            # rollback bank file
            async with _lock:
                banks = await _read_banks()
                banks[str(uid)] = banks.get(str(uid), 0) + amount
                await _write_banks(banks)
            await ctx.send(f"Withdrawal failed: {e}")
            return

        await ctx.send(embed=helpers.make_embed("Withdrawal Complete", f"Withdrew {helpers.format_chrons(amount)}"))

    @commands.command(name="bankbal", aliases=["bank"])
    async def bankbal(self, ctx: commands.Context):
        uid = ctx.author.id
        pool = db.get_pool()
        if pool is not None:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT balance FROM user_banks WHERE user_id = $1", uid)
                bal = row["balance"] if row else 0
        else:
            banks = await _read_banks()
            bal = banks.get(str(uid), 0)
        await ctx.send(embed=helpers.make_embed("Bank Balance", f"{helpers.EMOJI['chrons']} {bal}"))

    @app_commands.command(name="deposit", description="Deposit funds to your bank")
    async def slash_deposit(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        uid = interaction.user.id
        try:
            await db.safe_execute_money_transaction(uid, -amount, "bank deposit")
        except Exception as e:
            await interaction.response.send_message(f"Deposit failed: {e}", ephemeral=True)
            return
        async with _lock:
            banks = await _read_banks()
            banks[str(uid)] = banks.get(str(uid), 0) + amount
            await _write_banks(banks)
        await interaction.response.send_message(embed=helpers.make_embed("Deposit Complete", f"Deposited {helpers.format_chrons(amount)}"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Bank(bot))
