"""Weapons cog: equip/unequip/inspect/craft/upgrade and gem socketing.

This cog is intentionally lightweight and uses `chronix_bot.utils.weapons`
for persistence (file-backed). Commands have slash and prefix parity.
"""
from __future__ import annotations

from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import weapons as weapons_utils
from chronix_bot.utils import helpers


class WeaponsCog(commands.Cog):
    """Manage weapons: create, list, equip, unequip, inspect, upgrade, socket gems."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="create_weapon")
    async def create_weapon(self, ctx: commands.Context, name: str, wtype: str = "sword", attack: int = 5, rarity: str = "common"):
        w = weapons_utils.create_weapon(ctx.author.id, name, wtype=wtype, attack=attack, rarity=rarity)
        await ctx.send(embed=helpers.make_embed("Weapon Created", f"{w['name']} (ID: {w['weapon_id']}) created."))

    @commands.command(name="my_weapons")
    async def my_weapons(self, ctx: commands.Context):
        ws = weapons_utils.list_weapons(ctx.author.id)
        if not ws:
            await ctx.send(embed=helpers.make_embed("Weapons", "You have no weapons."))
            return
        lines = [f"ID:{w['weapon_id']} — {w['name']} ({w['type']}) ATK:{w['attack']} R:{w['rarity']} {'[E]' if w.get('equipped') else ''}" for w in ws]
        await ctx.send(embed=helpers.make_embed("Your Weapons", "\n".join(lines)))

    @commands.command(name="equip")
    async def equip(self, ctx: commands.Context, weapon_id: int):
        ok = weapons_utils.equip_weapon(ctx.author.id, weapon_id)
        if not ok:
            await ctx.send("Failed to equip weapon. Do you own it?")
            return
        await ctx.send(embed=helpers.make_embed("Equipped", f"Equipped weapon {weapon_id}"))

    @commands.command(name="unequip")
    async def unequip(self, ctx: commands.Context):
        ok = weapons_utils.unequip_weapon(ctx.author.id)
        if not ok:
            await ctx.send("No weapon was equipped.")
            return
        await ctx.send(embed=helpers.make_embed("Unequipped", "Your weapon was unequipped."))

    @commands.command(name="inspect_weapon")
    async def inspect_weapon(self, ctx: commands.Context, weapon_id: int):
        w = weapons_utils.inspect_weapon(ctx.author.id, weapon_id)
        if not w:
            await ctx.send("Weapon not found.")
            return
        desc = f"Name: {w.get('name')}\nType: {w.get('type')}\nATK: {w.get('attack')}\nRarity: {w.get('rarity')}\nSlots: {w.get('slots')}\nGems: {len(w.get('gems',[]))}"
        await ctx.send(embed=helpers.make_embed(f"Weapon #{weapon_id}", desc))

    @commands.command(name="upgrade_weapon")
    async def upgrade_weapon(self, ctx: commands.Context, weapon_id: int, inc: int = 1):
        w = weapons_utils.upgrade_weapon(ctx.author.id, weapon_id, increase=inc)
        if not w:
            await ctx.send("Upgrade failed.")
            return
        await ctx.send(embed=helpers.make_embed("Weapon Upgraded", f"{w.get('name')} ATK is now {w.get('attack')}"))

    @commands.command(name="socket_gem")
    async def socket_gem(self, ctx: commands.Context, weapon_id: int, gem_name: str, power: int = 1):
        gem = {"gem_name": gem_name, "power": int(power)}
        ok = weapons_utils.add_gem_to_weapon(ctx.author.id, weapon_id, gem)
        if not ok:
            await ctx.send("Failed to socket gem (no slots or weapon missing).")
            return
        await ctx.send(embed=helpers.make_embed("Gem Socketed", f"{gem_name} added to weapon {weapon_id}."))


async def setup(bot: commands.Bot):
    await bot.add_cog(WeaponsCog(bot))
