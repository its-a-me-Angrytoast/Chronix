from __future__ import annotations

from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import loot as loot_util
from chronix_bot.utils import db as db_utils


class Hunt(commands.Cog):
	"""Simple hunt command for Phase 4.

	This cog provides a manual `hunt` command (and slash equivalent) that
	awards coins and occasional item drops using the loot tables.
	"""

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot

	@commands.command(name="hunt", aliases=["h", "search"])
	@commands.cooldown(1, 10, commands.BucketType.user)
	async def hunt(self, ctx: commands.Context) -> None:
		"""Perform a hunt and award rewards."""
		await ctx.trigger_typing()
		user_id = ctx.author.id

		loot = loot_util.generate_loot("basic")
		coins = int(loot.get("coins", 0))

		# Award coins using the atomic money helper (works with in-memory fallback).
		try:
			new_balance = await db_utils.safe_execute_money_transaction(user_id, coins, "hunt reward")
		except Exception as exc:
			await ctx.send(embed=helpers.make_embed("Hunt failed", str(exc)))
			return

		# Build embed
		description_lines = [f"You found {helpers.format_chrons(coins)}!", f"New balance: {helpers.format_chrons(new_balance)}"]
		items = loot.get("items", [])
		if items:
			item_lines = [f"• {i.get('name')} ({i.get('rarity')})" for i in items]
			description_lines.append("\nItems:\n" + "\n".join(item_lines))

		embed = helpers.make_embed("Hunt Results", "\n".join(description_lines))
		await ctx.send(embed=embed)

	@app_commands.command(name="hunt")
	async def slash_hunt(self, interaction: discord.Interaction) -> None:
		"""Slash command equivalent for hunt."""
		await interaction.response.defer()
		user_id = interaction.user.id
		loot = loot_util.generate_loot("basic")
		coins = int(loot.get("coins", 0))

		try:
			new_balance = await db_utils.safe_execute_money_transaction(user_id, coins, "hunt reward")
		except Exception as exc:
			await interaction.followup.send(embed=helpers.make_embed("Hunt failed", str(exc)), ephemeral=True)
			return

		description_lines = [f"You found {helpers.format_chrons(coins)}!", f"New balance: {helpers.format_chrons(new_balance)}"]
		items = loot.get("items", [])
		if items:
			item_lines = [f"• {i.get('name')} ({i.get('rarity')})" for i in items]
			description_lines.append("\nItems:\n" + "\n".join(item_lines))

		embed = helpers.make_embed("Hunt Results", "\n".join(description_lines))
		await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(Hunt(bot))
