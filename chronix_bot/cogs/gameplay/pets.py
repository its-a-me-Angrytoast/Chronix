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
from pathlib import Path
import yaml
import random
from chronix_bot.utils import inventory_extras as inv_extras
from chronix_bot.utils import db as db_utils
import json
import time

DATA_DIR = Path.cwd() / "data"
SPEC_FILE = DATA_DIR / "pet_species.yaml"

MARKET_FILE = DATA_DIR / "pet_marketplace.json"

def _load_market():
    try:
        if not MARKET_FILE.exists():
            return []
        return json.loads(MARKET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_market(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _load_species():
    if not SPEC_FILE.exists():
        return {}
    try:
        return yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


class Pets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.species = _load_species()
        # background spawner task
        self._spawner_task = bot.loop.create_task(self._spawn_loop())

    def cog_unload(self):
        if hasattr(self, "_spawner_task") and not self._spawner_task.done():
            self._spawner_task.cancel()

    async def _spawn_loop(self):
        """Background loop that occasionally creates discoverable pets saved to data/pet_spawns.json"""
        import asyncio
        from pathlib import Path

        SPAWN_FILE = DATA_DIR / "pet_spawns.json"
        while True:
            try:
                # sleep random between 10 and 30 minutes (shorter for dev)
                await asyncio.sleep(60 * 10)
                # 20% chance to spawn
                if random.random() > 0.2:
                    continue
                # pick species weighted by rarity
                species_keys = list(self.species.keys())
                if not species_keys:
                    continue
                sp = random.choice(species_keys)
                spawn = {"species": sp, "id": int(time.time() * 1000), "rarity": self.species.get(sp, {}).get('rarity','common'), "ts": int(time.time())}
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                old = []
                try:
                    if SPAWN_FILE.exists():
                        old = json.loads(SPAWN_FILE.read_text(encoding="utf-8"))
                except Exception:
                    old = []
                old.append(spawn)
                SPAWN_FILE.write_text(json.dumps(old, indent=2), encoding="utf-8")
            except asyncio.CancelledError:
                break
            except Exception:
                # ignore spawn errors
                await asyncio.sleep(60)

    @commands.command(name="adopt")
    async def adopt(self, ctx: commands.Context, species: str):
        # normalize species
        species = species.lower()
        if species not in self.species:
            await ctx.send(embed=helpers.make_embed("Unknown Species", f"Species `{species}` is unknown. Try common names like: {', '.join(list(self.species.keys())[:5])}"))
            return
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

    @commands.command(name="release_pet")
    async def release(self, ctx: commands.Context, pet_id: int):
        removed = inv.release_pet(ctx.author.id, pet_id)
        if not removed:
            await ctx.send("Pet not found or failed to release.")
            return
        await ctx.send(embed=helpers.make_embed("Pet Released", f"You released {removed.get('species')}."))

    @commands.command(name="pet_sell")
    async def pet_sell(self, ctx: commands.Context, pet_id: int, price: int):
        """List a pet for sale on the pet marketplace. Removes the pet from user's inventory and creates a listing."""
        pet = inv.get_pet(ctx.author.id, pet_id)
        if not pet:
            await ctx.send("Pet not found.")
            return
        # remove pet
        removed = inv.release_pet(ctx.author.id, pet_id)
        if not removed:
            await ctx.send("Failed to remove pet for listing.")
            return
        # create listing
        data = _load_market()
        lid = int(time.time() * 1000)
        listing = {"id": lid, "pet": removed, "seller_id": ctx.author.id, "price": int(price), "created_at": int(time.time())}
        data.append(listing)
        _save_market(data)
        await ctx.send(embed=helpers.make_embed("Pet Listed", f"Listing #{lid} — {removed.get('species')} for {helpers.format_chrons(price)}"))

    @commands.command(name="pet_listings")
    async def pet_listings(self, ctx: commands.Context):
        data = _load_market()
        if not data:
            await ctx.send(embed=helpers.make_embed("Marketplace", "No pet listings."))
            return
        lines = [f"#{l['id']}: {l['pet'].get('species')} — {helpers.format_chrons(l['price'])} — Seller: <@{l['seller_id']}>" for l in data]
        await ctx.send(embed=helpers.make_embed("Pet Marketplace", "\n".join(lines)))

    @commands.command(name="pet_buy")
    async def pet_buy(self, ctx: commands.Context, listing_id: int):
        data = _load_market()
        listing = None
        for l in data:
            if int(l.get('id')) == int(listing_id):
                listing = l
                break
        if not listing:
            await ctx.send("Listing not found.")
            return
        price = int(listing.get('price', 0))
        seller = int(listing.get('seller_id'))
        # attempt DB transactional buy if pool present
        pool = db_utils.get_pool()
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        # debit buyer
                        from chronix_bot.utils.db import safe_execute_money_transaction
                        new_bal = await safe_execute_money_transaction(ctx.author.id, -price, f"Buy pet {listing_id}", pool=pool)
                        # credit seller
                        await safe_execute_money_transaction(seller, price, f"Sold pet {listing_id}", pool=pool)
                        # deliver pet as item
                        await inv.async_add_item(ctx.author.id, listing['pet'].get('species'), meta={'type':'pet','pet': listing['pet']})
                        # remove listing
                        data = _load_market()
                        data = [x for x in data if int(x.get('id')) != int(listing_id)]
                        _save_market(data)
                        await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought {listing['pet'].get('species')} for {helpers.format_chrons(price)}"))
                        return
            except Exception as e:
                await ctx.send(f"Purchase failed: {e}")
                return

        # File-backed fallback: ensure buyer has enough in-memory balance via db.safe_execute_money_transaction
        try:
            from chronix_bot.utils.db import safe_execute_money_transaction
            new_bal = await safe_execute_money_transaction(ctx.author.id, -price, f"Buy pet {listing_id}")
            # credit seller (best-effort)
            await safe_execute_money_transaction(seller, price, f"Sold pet {listing_id}")
        except Exception as e:
            await ctx.send(f"Purchase failed: {e}")
            return
        # deliver pet as an item
        await inv.async_add_item(ctx.author.id, listing['pet'].get('species'), meta={'type':'pet','pet': listing['pet']})
        # remove listing
        data = _load_market()
        data = [x for x in data if int(x.get('id')) != int(listing_id)]
        _save_market(data)
        await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought {listing['pet'].get('species')} for {helpers.format_chrons(price)}"))

    @commands.command(name="pet_cancel")
    async def pet_cancel(self, ctx: commands.Context, listing_id: int):
        data = _load_market()
        listing = None
        for l in data:
            if int(l.get('id')) == int(listing_id):
                listing = l
                break
        if not listing:
            await ctx.send("Listing not found.")
            return
        if int(listing.get('seller_id')) != ctx.author.id and not await ctx.bot.is_owner(ctx.author):
            await ctx.send("You cannot cancel someone else's listing.")
            return
        # return pet to seller's inventory (add as pet)
        pet = listing.get('pet')
        inv.add_pet(listing.get('seller_id'), pet.get('species'))
        # remove listing
        data = [x for x in data if int(x.get('id')) != int(listing_id)]
        _save_market(data)
        await ctx.send(embed=helpers.make_embed("Listing Cancelled", f"Listing #{listing_id} cancelled and pet returned to seller."))

    @commands.command(name="inspect_pet")
    async def inspect_pet(self, ctx: commands.Context, pet_id: int):
        p = inv.get_pet(ctx.author.id, pet_id)
        if not p:
            await ctx.send("Pet not found.")
            return
        spec = self.species.get(p.get('species'), {})
        power = spec.get('base_power', 5) + int(p.get('level', 1)) * 2
        rarity = p.get('rarity', 'common')
        img = p.get('image') or spec.get('image') or None
        lines = [f"Species: {p.get('species')} ({rarity.title()})", f"Level: {p.get('level',1)}", f"XP: {p.get('xp',0)}", f"Power (est): {power}", f"Wins: {p.get('wins',0)} Losses: {p.get('losses',0)}"]
        e = helpers.make_embed(f"Pet #{pet_id}", "\n".join(lines))
        if img:
            try:
                e.set_thumbnail(url=img)
            except Exception:
                pass
        # include last 3 pet log entries if available
        try:
            plf = DATA_DIR / "pet_logs.jsonl"
            recent = []
            if plf.exists():
                for line in plf.read_text(encoding="utf-8").splitlines()[-200:]:
                    try:
                        j = json.loads(line)
                        if int(j.get('pet_id', 0)) == int(pet_id):
                            recent.append(j)
                    except Exception:
                        continue
            if recent:
                snippet = "\n".join([f"{r.get('action')} @{r.get('ts')}" for r in recent[-3:]])
                e.add_field(name="Recent", value=snippet, inline=False)
        except Exception:
            pass
        await ctx.send(embed=e)

    @commands.command(name="train_pet")
    async def train_pet(self, ctx: commands.Context, pet_id: int, xp: int = 50):
        """Spend time to train a pet (grant XP)."""
        try:
            pet = inv.feed_pet(ctx.author.id, pet_id, xp=xp)
            await ctx.send(embed=helpers.make_embed("Trained Pet", f"{pet['species']} trained for {xp} XP. Now level {pet.get('level',1)} (XP {pet.get('xp',0)})"))
        except ValueError:
            await ctx.send("Pet not found.")

    @commands.command(name="pet_leaderboard")
    async def pet_leaderboard(self, ctx: commands.Context, by: str = "level", top: int = 10):
        lb = inv.pet_leaderboard(top=top, by=by)
        if not lb:
            await ctx.send(embed=helpers.make_embed("Pet Leaderboard", "No pets found."))
            return
        lines = [f"#{i+1}: {item['pet'].get('species')} (Lvl {item['pet'].get('level',1)}) — Trainer: <@{item['user_id']}> — Score: {item['score']}" for i, item in enumerate(lb)]
        await ctx.send(embed=helpers.make_embed("Pet Leaderboard", "\n".join(lines)))

    @commands.command(name="discover_pet")
    async def discover_pet(self, ctx: commands.Context):
        """Attempt to discover a spawned pet. This consumes the next available spawn in the channel/global list."""
        SPAWN_FILE = DATA_DIR / "pet_spawns.json"
        try:
            if not SPAWN_FILE.exists():
                await ctx.send("No pets are discoverable right now.")
                return
            spawns = json.loads(SPAWN_FILE.read_text(encoding="utf-8"))
            if not spawns:
                await ctx.send("No pets are discoverable right now.")
                return
            # pick a spawn (first) and remove it
            spawn = spawns.pop(0)
            SPAWN_FILE.write_text(json.dumps(spawns, indent=2), encoding="utf-8")
            # adopt the spawn for the user
            pet = inv.add_pet(ctx.author.id, spawn.get('species'))
            await ctx.send(embed=helpers.make_embed("Discovery!", f"You discovered and adopted a {spawn.get('species')} (rarity: {spawn.get('rarity')}). ID: {pet.get('pet_id')}"))
        except Exception as e:
            await ctx.send(f"Discovery failed: {e}")

    @commands.command(name="pet_clan_battle")
    async def pet_clan_battle(self, ctx: commands.Context, *members: discord.Member):
        """Run a simplified clan-style battle using one top pet from each mentioned member.

        Usage: chro pet_clan_battle @member1 @member2 @member3 ...
        """
        if not members or len(members) < 2:
            await ctx.send("Provide at least two members to run a clan battle.")
            return
        teams = []
        for m in members:
            pets = inv.list_pets(m.id)
            if not pets:
                continue
            # choose top-level pet
            pets_sorted = sorted(pets, key=lambda x: int(x.get('level', 1)), reverse=True)
            top = pets_sorted[0]
            sp = top.get('species')
            power = self.species.get(sp, {}).get('base_power', 5) + int(top.get('level',1))*2
            teams.append({'member': m, 'pet': top, 'power': power})
        if len(teams) < 2:
            await ctx.send("Not enough participants with pets to run a battle.")
            return
        # compute scores and rank
        for t in teams:
            t['score'] = t['power'] * (1 + random.random() * 0.25)
        teams.sort(key=lambda x: x['score'], reverse=True)
        winner = teams[0]
        # award xp to winner's pet
        inv.record_battle_result(winner['member'].id, winner['pet'].get('pet_id'), 'win', opponent={'contestants': [t['member'].id for t in teams[1:]]}, xp=50, coins=0)
        # mark others as losses
        for loser in teams[1:]:
            inv.record_battle_result(loser['member'].id, loser['pet'].get('pet_id'), 'loss', opponent={'winner': winner['member'].id}, xp=0, coins=0)
        lines = [f"{i+1}. {t['member'].mention}'s {t['pet'].get('species')} (Lvl {t['pet'].get('level')}) — Score: {int(t['score'])}" for i, t in enumerate(teams)]
        await ctx.send(embed=helpers.make_embed("Clan Battle Result", "\n".join(lines)))

    @commands.command(name="evolve_pet")
    async def evolve_pet(self, ctx: commands.Context, pet_id: int):
        """Attempt to evolve a pet if it meets species evolution conditions."""
        p = inv.get_pet(ctx.author.id, pet_id)
        if not p:
            await ctx.send("Pet not found.")
            return
        sp = p.get('species')
        meta = self.species.get(sp, {})
        evo = meta.get('evolve_to')
        need = int(meta.get('evolve_level', 0) or 0)
        if not evo:
            await ctx.send("This species cannot evolve.")
            return
        if int(p.get('level', 1)) < need:
            await ctx.send(f"Pet needs to be level {need} to evolve.")
            return
        # apply evolution
        p['species'] = evo
        # small stat bump
        p['level'] = int(p.get('level', 1)) + 0
        await ctx.send(embed=helpers.make_embed("Pet Evolved", f"Your pet evolved into {evo}!"))

    # Simple PvE battle against a generated wild pet
    @commands.command(name="pet_battle")
    async def pet_battle(self, ctx: commands.Context, pet_id: int):
        p = inv.get_pet(ctx.author.id, pet_id)
        if not p:
            await ctx.send("Pet not found.")
            return
        # generate wild opponent from species list
        species_list = list(self.species.keys())
        opp_species = random.choice(species_list)
        opp_power = self.species.get(opp_species, {}).get('base_power', 5) + random.randint(0,5)
        my_power = self.species.get(p.get('species'), {}).get('base_power', 5) + int(p.get('level',1))*2
        # simple outcome
        roll = random.random()
        my_score = my_power * (1 + random.random()*0.2)
        opp_score = opp_power * (1 + random.random()*0.2)
        if my_score >= opp_score:
            # win: grant xp and coins
            inv.record_battle_result(ctx.author.id, pet_id, 'win', opponent={'species': opp_species}, xp=30, coins=0)
            await ctx.send(embed=helpers.make_embed("Battle Won", f"Your {p.get('species')} defeated a wild {opp_species}! You earned XP."))
        else:
            inv.record_battle_result(ctx.author.id, pet_id, 'loss', opponent={'species': opp_species}, xp=0, coins=0)
            await ctx.send(embed=helpers.make_embed("Battle Lost", f"Your {p.get('species')} was defeated by a wild {opp_species}. Better luck next time."))

    # PvP duel between two users' pets
    @commands.command(name="pet_duel")
    async def pet_duel(self, ctx: commands.Context, opponent: discord.Member, my_pet_id: int, their_pet_id: int):
        myp = inv.get_pet(ctx.author.id, my_pet_id)
        if not myp:
            await ctx.send("Your pet not found.")
            return
        theirp = inv.get_pet(opponent.id, their_pet_id)
        if not theirp:
            await ctx.send("Opponent pet not found.")
            return
        my_power = self.species.get(myp.get('species'), {}).get('base_power',5) + int(myp.get('level',1))*2
        their_power = self.species.get(theirp.get('species'), {}).get('base_power',5) + int(theirp.get('level',1))*2
        my_score = my_power * (1 + random.random()*0.2)
        their_score = their_power * (1 + random.random()*0.2)
        if my_score >= their_score:
            inv.record_battle_result(ctx.author.id, my_pet_id, 'win', opponent={'user': opponent.id, 'species': theirp.get('species')}, xp=40, coins=0)
            inv.record_battle_result(opponent.id, their_pet_id, 'loss', opponent={'user': ctx.author.id, 'species': myp.get('species')}, xp=0, coins=0)
            await ctx.send(embed=helpers.make_embed("Duel Result", f"{ctx.author.mention}'s {myp.get('species')} won against {opponent.mention}'s {theirp.get('species')}!"))
        else:
            inv.record_battle_result(opponent.id, their_pet_id, 'win', opponent={'user': ctx.author.id, 'species': myp.get('species')}, xp=40, coins=0)
            inv.record_battle_result(ctx.author.id, my_pet_id, 'loss', opponent={'user': opponent.id, 'species': theirp.get('species')}, xp=0, coins=0)
            await ctx.send(embed=helpers.make_embed("Duel Result", f"{opponent.mention}'s {theirp.get('species')} won against {ctx.author.mention}'s {myp.get('species')}!"))

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
