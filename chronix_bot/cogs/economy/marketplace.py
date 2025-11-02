from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers, db

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MARKET_FILE = DATA_DIR / "marketplace.json"
_lock = asyncio.Lock()


async def _read_market() -> List[Dict]:
    if not MARKET_FILE.exists():
        return []
    def _load():
        with MARKET_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return await asyncio.to_thread(_load)


async def _write_market(data: List[Dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    def _dump():
        with MARKET_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    await asyncio.to_thread(_dump)


async def _read_market_db() -> List[Dict]:
    pool = db.get_pool()
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, seller_id, item, price FROM marketplace_listings ORDER BY id")
        return [{"id": r["id"], "seller_id": r["seller_id"], "item": r["item"], "price": r["price"]} for r in rows]


async def _write_market_db(entry: Dict) -> int:
    pool = db.get_pool()
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO marketplace_listings (seller_id, item, price) VALUES ($1, $2, $3) RETURNING id", entry["seller_id"], entry["item"], entry["price"])
        return row["id"]


async def _remove_market_db(listing_id: int) -> None:
    pool = db.get_pool()
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM marketplace_listings WHERE id = $1", listing_id)


async def _edit_market_db(listing_id: int, price: Optional[int], item: Optional[str]) -> None:
    pool = db.get_pool()
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    async with pool.acquire() as conn:
        if price is not None:
            await conn.execute("UPDATE marketplace_listings SET price = $1 WHERE id = $2", price, listing_id)
        if item is not None:
            await conn.execute("UPDATE marketplace_listings SET item = $1 WHERE id = $2", item, listing_id)


class Marketplace(commands.Cog):
    """Simple marketplace: users can list items for sale and buy listings.

    Listings are stored in `data/marketplace.json` with fields:
    {"id": int, "seller_id": int, "item": str, "price": int}
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="list_item")
    async def list_item(self, ctx: commands.Context, price: int, *, item: str):
        """List an item for sale: chro list_item <price> <item description>"""
        if price <= 0:
            await ctx.send("Price must be positive.")
            return

        async with _lock:
                pool = db.get_pool()
                if pool is not None:
                    nid = await _write_market_db({"seller_id": ctx.author.id, "item": item, "price": price})
                else:
                    data = await _read_market()
                    nid = max((l.get("id", 0) for l in data), default=0) + 1
                    entry = {"id": nid, "seller_id": ctx.author.id, "item": item, "price": price}
                    data.append(entry)
                    await _write_market(data)

        await ctx.send(embed=helpers.make_embed("Item Listed", f"ID: {nid}\n{item}\nPrice: {helpers.format_chrons(price)}"))

    @commands.command(name="market_remove")
    @commands.has_permissions(manage_guild=True)
    async def market_remove(self, ctx: commands.Context, listing_id: int):
        """Admin command: remove a listing by ID."""
        pool = db.get_pool()
        if pool is not None:
            await _remove_market_db(listing_id)
            await ctx.send(embed=helpers.make_embed("Listing Removed", f"Removed listing {listing_id}"))
            return

        async with _lock:
            data = await _read_market()
            if not any(l for l in data if l.get("id") == listing_id):
                await ctx.send("Listing not found.")
                return
            data = [l for l in data if l.get("id") != listing_id]
            await _write_market(data)
        await ctx.send(embed=helpers.make_embed("Listing Removed", f"Removed listing {listing_id}"))

    @commands.command(name="market_edit")
    @commands.has_permissions(manage_guild=True)
    async def market_edit(self, ctx: commands.Context, listing_id: int, price: int = None, *, item: str = None):
        """Admin command: edit a listing's price and/or item description."""
        pool = db.get_pool()
        if pool is not None:
            await _edit_market_db(listing_id, price, item)
            await ctx.send(embed=helpers.make_embed("Listing Updated", f"ID: {listing_id} updated."))
            return

        async with _lock:
            data = await _read_market()
            listing = next((l for l in data if l.get("id") == listing_id), None)
            if listing is None:
                await ctx.send("Listing not found.")
                return
            if price is not None:
                listing["price"] = price
            if item is not None:
                listing["item"] = item
            await _write_market(data)
        await ctx.send(embed=helpers.make_embed("Listing Updated", f"ID: {listing_id} updated."))

    @commands.command(name="market_list")
    async def market_list(self, ctx: commands.Context):
        """List marketplace items."""
        pool = db.get_pool()
        if pool is not None:
            data = await _read_market_db()
        else:
            data = await _read_market()
        if not data:
            await ctx.send("The marketplace is empty.")
            return

        lines = [f"ID:{l['id']} — {l['item']} — {helpers.format_chrons(l['price'])} — Seller:<@{l['seller_id']}>" for l in data]
        embed = helpers.make_embed("Marketplace Listings", "\n".join(lines[:20]))
        await ctx.send(embed=embed)

    @commands.command(name="sell_crate")
    async def sell_crate(self, ctx: commands.Context, crate_type: str, price: int):
        """List an unopened crate for sale: chro sell_crate <crate_type> <price>

        This will consume one unopened crate from the seller and create a
        marketplace listing with the special item payload `unopened_crate:<type>`.
        """
        if price <= 0:
            await ctx.send("Price must be positive")
            return

        # try to consume a crate using async inventory helpers
        try:
            from chronix_bot.utils.inventory import async_consume_unopened_crate
        except Exception:
            async_consume_unopened_crate = None

        consumed = None
        if async_consume_unopened_crate is not None:
            try:
                consumed = await async_consume_unopened_crate(ctx.author.id, crate_type)
            except Exception:
                consumed = None

        # If DB-backed path didn't return a consumed crate, try synchronous fallback
        if consumed is None:
            try:
                from chronix_bot.utils.inventory import consume_unopened_crate
                consumed = consume_unopened_crate(ctx.author.id, crate_type)
            except Exception:
                consumed = None

        if consumed is None:
            await ctx.send("You have no unopened crates of that type to sell.")
            return

        item_desc = f"unopened_crate:{crate_type}:{consumed.get('crate_id')}"
        # Reuse existing listing creation logic
        async with _lock:
            pool = db.get_pool()
            if pool is not None:
                nid = await _write_market_db({"seller_id": ctx.author.id, "item": item_desc, "price": price})
            else:
                data = await _read_market()
                nid = max((l.get("id", 0) for l in data), default=0) + 1
                entry = {"id": nid, "seller_id": ctx.author.id, "item": item_desc, "price": price}
                data.append(entry)
                await _write_market(data)

        await ctx.send(embed=helpers.make_embed("Crate Listed", f"Listing ID: {nid}\n{crate_type} — {helpers.format_chrons(price)}"))

    @commands.command(name="my_unopened")
    async def my_unopened(self, ctx: commands.Context):
        """Show your unopened crates."""
        try:
            from chronix_bot.utils.inventory import async_list_unopened_crates
        except Exception:
            async_list_unopened_crates = None

        if async_list_unopened_crates is not None:
            crates = await async_list_unopened_crates(ctx.author.id)
        else:
            from chronix_bot.utils.inventory import list_unopened_crates
            crates = list_unopened_crates(ctx.author.id)

        if not crates:
            await ctx.send("You have no unopened crates.")
            return

        lines = [f"ID:{c.get('crate_id')} — {c.get('crate_type')}" for c in crates]
        await ctx.send(embed=helpers.make_embed("Your Unopened Crates", "\n".join(lines)))

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, listing_id: int):
        """Buy a marketplace listing by ID."""
        pool = db.get_pool()
        if pool is not None:
            # DB-backed flow: lock via transaction to avoid races
            async with pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT id, seller_id, item, price FROM marketplace_listings WHERE id = $1 FOR UPDATE", listing_id)
                    if row is None:
                        await ctx.send("Listing not found.")
                        return
                    price = int(row["price"])
                    buyer_id = ctx.author.id
                    try:
                        await db.safe_execute_money_transaction(buyer_id, -price, f"market buy {listing_id}")
                    except Exception as e:
                        await ctx.send(f"Purchase failed: {e}")
                        return
                    try:
                        await db.safe_execute_money_transaction(row["seller_id"], price, f"market sell {listing_id}")
                    except Exception:
                        await db.safe_execute_money_transaction(buyer_id, price, f"market refund {listing_id}")
                        await ctx.send("Purchase failed while crediting seller; refunded.")
                        return
                    # deliver unopened crate item to buyer if applicable
                    item = row["item"]
                    try:
                        if isinstance(item, str) and item.startswith("unopened_crate:"):
                            _, ctype, cid = item.split(":", 2)
                            try:
                                from chronix_bot.utils.inventory import async_add_unopened_crate
                            except Exception:
                                async_add_unopened_crate = None
                            if async_add_unopened_crate is not None:
                                await async_add_unopened_crate(buyer_id, ctype)
                            else:
                                from chronix_bot.utils.inventory import add_unopened_crate
                                add_unopened_crate(buyer_id, ctype)
                    except Exception:
                        pass
                    await conn.execute("DELETE FROM marketplace_listings WHERE id = $1", listing_id)
                    await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought **{row['item']}** for {helpers.format_chrons(price)}"))
            return

        # fallback to file-backed flow
        async with _lock:
            data = await _read_market()
            listing = next((l for l in data if l.get("id") == listing_id), None)
            if listing is None:
                await ctx.send("Listing not found.")
                return

            price = int(listing["price"])
            buyer_id = ctx.author.id

            try:
                await db.safe_execute_money_transaction(buyer_id, -price, f"market buy {listing_id}")
            except Exception as e:
                await ctx.send(f"Purchase failed: {e}")
                return

            try:
                await db.safe_execute_money_transaction(listing["seller_id"], price, f"market sell {listing_id}")
            except Exception:
                await db.safe_execute_money_transaction(buyer_id, price, f"market refund {listing_id}")
                await ctx.send("Purchase failed while crediting seller; refunded.")
                return

            # deliver unopened crate to buyer if needed
            item = listing.get("item")
            try:
                if isinstance(item, str) and item.startswith("unopened_crate:"):
                    _, ctype, cid = item.split(":", 2)
                    try:
                        from chronix_bot.utils.inventory import async_add_unopened_crate
                    except Exception:
                        async_add_unopened_crate = None
                    if async_add_unopened_crate is not None:
                        await async_add_unopened_crate(buyer_id, ctype)
                    else:
                        from chronix_bot.utils.inventory import add_unopened_crate
                        add_unopened_crate(buyer_id, ctype)
            except Exception:
                pass

            data = [l for l in data if l.get("id") != listing_id]
            await _write_market(data)

        await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought **{listing['item']}** for {helpers.format_chrons(price)}"))

    @app_commands.command(name="market_list", description="Show marketplace listings")
    async def slash_market_list(self, interaction: discord.Interaction):
        data = await _read_market()
        if not data:
            await interaction.response.send_message("The marketplace is empty.")
            return
        lines = [f"ID:{l['id']} — {l['item']} — {helpers.format_chrons(l['price'])} — Seller:<@{l['seller_id']}>" for l in data]
        embed = helpers.make_embed("Marketplace Listings", "\n".join(lines[:20]))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Marketplace(bot))
