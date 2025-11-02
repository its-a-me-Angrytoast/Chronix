"""Crate opening system for Phase 4.

This module implements the crate opening flow, including UI confirmation
and animated reveal embeds. Uses the loot util to determine drops based
on `data/loot_tables.yaml` tables.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, List
import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import loot as loot_util
from chronix_bot.utils import db as db_utils
from chronix_bot.utils import inventory as inventory_utils
from chronix_bot.utils import inventory_extras as inventory_extras
from chronix_bot.utils import logger as logger_utils
from chronix_bot.utils import persistence as persistence_utils
from pathlib import Path
import json
import time
from typing import Tuple

DATA_DIR = Path.cwd() / "data"
MARKET_FILE = DATA_DIR / "marketplace.json"
EVENTS_FILE = DATA_DIR / "event_crates.json"
TRADES_FILE = DATA_DIR / "trades.json"


def _load_market() -> dict:
    if not MARKET_FILE.exists():
        return {"next_id": 1, "listings": {}}
    try:
        return json.loads(MARKET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"next_id": 1, "listings": {}}


def _save_market(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _load_events() -> dict:
    if not EVENTS_FILE.exists():
        return {}
    try:
        return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_events(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _is_event_active(name: str) -> Tuple[bool, Optional[dict]]:
    ev = _load_events().get(name)
    if not ev:
        return False, None
    now = int(time.time())
    start = int(ev.get("start_ts", 0) or 0)
    end = int(ev.get("end_ts", 0) or 0)
    if (start == 0 or now >= start) and (end == 0 or now <= end):
        return True, ev
    return False, ev


def analyze_rarity(table_name: str) -> dict:
    """Analyze a loot table and return stats helpful for balancing.

    Returns a dict with items and computed rarity_score per loot_util policy.
    """
    tables = loot_util._load_tables()
    spec = tables.get(table_name) or tables.get("basic")
    items = spec.get("items", [])
    weights = [float(i.get("weight", 1)) for i in items] if items else [1.0]
    max_w = max(weights) if weights else 1.0
    out = {}
    for it in items:
        w = float(it.get("weight", 1))
        rarity_score = 1.0 - min(w / max_w, 1.0)
        out[it.get("name")] = {"weight": w, "rarity_score": round(rarity_score, 3), "rarity": it.get("rarity")}
    return out


def _load_trades() -> dict:
    if not TRADES_FILE.exists():
        return {"next_id": 1, "trades": {}}
    try:
        return json.loads(TRADES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"next_id": 1, "trades": {}}


def _save_trades(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

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

    Provides prefix and slash commands for opening crates, gifting unopened
    crates, and listing unopened crates/items. Persists drops to the
    inventory (DB-backed if available, otherwise file-backed) and logs crate openings via the async logger.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # track last known event active states to announce transitions
        self._last_event_active: dict[str, bool] = {}
        self._scheduler_task = self.bot.loop.create_task(self._event_scheduler_loop())

    def cog_unload(self) -> None:
        try:
            if self._scheduler_task and not self._scheduler_task.done():
                self._scheduler_task.cancel()
        except Exception:
            pass

    async def _event_scheduler_loop(self) -> None:
        """Background task: checks event activation windows and announces start/end.

        For each event, when it transitions from inactive->active we announce a start
        message to guilds that have configured a `rare_drop_channel`. On active->inactive
        we announce the end. This is best-effort and only uses file-backed guild settings.
        """
        await self.bot.wait_until_ready()
        from chronix_bot.utils import persistence as persistence_utils

        while True:
            try:
                evs = _load_events()
                now = int(time.time())
                # For each event compute active state
                for name, ev in evs.items():
                    start = int(ev.get("start_ts", 0) or 0)
                    end = int(ev.get("end_ts", 0) or 0)
                    active = (start == 0 or now >= start) and (end == 0 or now <= end)
                    prev = self._last_event_active.get(name, False)
                    # transition: inactive -> active
                    if active and not prev:
                        # announce start to guilds with configured channels
                        for g in list(self.bot.guilds):
                            try:
                                gid = int(g.id)
                                # per-guild event override may specify enabled/start/end
                                override = persistence_utils.get_guild_setting(gid, f"event_override:{name}", None)
                                if override is not None:
                                    # override can be dict {enabled: bool, start_ts:int, end_ts:int}
                                    if not override.get("enabled", True):
                                        continue
                                    ch_id = persistence_utils.get_guild_setting(gid, "rare_drop_channel", None)
                                else:
                                    ch_id = persistence_utils.get_guild_setting(gid, "rare_drop_channel", None)
                                if not ch_id:
                                    continue
                                ch = g.get_channel(int(ch_id))
                                if ch is None:
                                    continue
                                await ch.send(f"📢 Event **{name}** has started! Crates of type `{name}` now use loot table `{ev.get('loot_table')}` until {end or 'indefinite'}.")
                            except Exception:
                                continue
                    # transition: active -> inactive
                    if not active and prev:
                        for g in list(self.bot.guilds):
                            try:
                                gid = int(g.id)
                                override = persistence_utils.get_guild_setting(gid, f"event_override:{name}", None)
                                if override is not None and not override.get("enabled", True):
                                    continue
                                ch_id = persistence_utils.get_guild_setting(gid, "rare_drop_channel", None)
                                if not ch_id:
                                    continue
                                ch = g.get_channel(int(ch_id))
                                if ch is None:
                                    continue
                                await ch.send(f"🔔 Event **{name}** has ended.")
                            except Exception:
                                continue
                    self._last_event_active[name] = active
            except asyncio.CancelledError:
                break
            except Exception:
                # swallow errors to keep scheduler alive
                pass
            await asyncio.sleep(60)

    async def _reveal_crate(self, target: Any, crate_type: str) -> None:
        """Run the crate opening animation and reveal drops.

        `target` may be a `commands.Context` (prefix) or `discord.Interaction`
        (slash). The method adapts sending and followups accordingly.
        """
        # Initial "opening" message
        embed = helpers.make_embed("Opening Crate", f"Opening your {crate_type} crate...")
        if isinstance(target, commands.Context):
            message = await target.send(embed=embed)
            user = target.author
        else:
            message = await target.followup.send(embed=embed)
            user = target.user

        # Suspense updates
        embed.description = "The crate begins to glow..."
        await message.edit(embed=embed)
        await asyncio.sleep(1.0)

        embed.description = "Items materialize..."
        await message.edit(embed=embed)
        await asyncio.sleep(1.0)

        # If crate_type maps to an active event, use its configured loot table
        use_table = crate_type
        try:
            active, ev = _is_event_active(crate_type)
            if active and ev is not None:
                use_table = ev.get("loot_table", crate_type)
        except Exception:
            use_table = crate_type

        # Generate and reveal loot
        loot = loot_util.generate_loot(use_table)
        coins = int(loot.get("coins", 0))

        # Award coins if any (uses safe transaction)
        new_balance = None
        if coins > 0:
            try:
                new_balance = await db_utils.safe_execute_money_transaction(int(user.id), coins, f"crate reward ({crate_type})")
            except Exception as exc:
                try:
                    if isinstance(target, commands.Context):
                        await target.send(f"Error awarding crate coins: {exc}")
                    else:
                        await target.followup.send(f"Error awarding crate coins: {exc}", ephemeral=True)
                except Exception:
                    pass
                return

        # Persist item drops and build reveal embed
        description_lines: List[str] = []
        if coins > 0:
            description_lines.extend([
                f"You found {helpers.format_chrons(coins)}!",
                f"New balance: {helpers.format_chrons(new_balance)}"
            ])

        items = loot.get("items", [])
        rare_broadcasts: List[Dict[str, Any]] = []
        if items:
            item_lines: List[str] = []
            for i in items:
                item_lines.append(f"• {i.get('name')} ({i.get('rarity')})")
                # persist drop into inventory according to type
                itype = str(i.get("type", "misc")).lower()
                # Prefer async DB-backed item insertion if available
                try:
                    if hasattr(inventory_utils, "async_add_item"):
                        meta = {"rarity": i.get("rarity"), "type": itype}
                        await inventory_utils.async_add_item(int(user.id), i.get("name"), meta=meta)
                    else:
                        if itype == "gem":
                            inventory_utils.add_gem(int(user.id), i.get("name"), power=1)
                        elif itype == "pet":
                            inventory_utils.add_pet(int(user.id), i.get("name"))
                        else:
                            inventory_utils.add_item(int(user.id), i.get("name"), meta={"rarity": i.get("rarity")})
                except Exception:
                    # If DB path fails for any reason, fall back to file-backed sync calls
                    try:
                        if itype == "gem":
                            inventory_utils.add_gem(int(user.id), i.get("name"), power=1)
                        elif itype == "pet":
                            inventory_utils.add_pet(int(user.id), i.get("name"))
                        else:
                            inventory_utils.add_item(int(user.id), i.get("name"), meta={"rarity": i.get("rarity")})
                    except Exception:
                        # swallow any inventory persistence errors
                        pass

                # collect rare drops for broadcast/logging
                if i.get("is_rare"):
                    rare_broadcasts.append(i)

            description_lines.append("\nItems:\n" + "\n".join(item_lines))

        embed = helpers.make_embed("Crate Results", "\n".join(description_lines) or "The crate was empty!")
        await message.edit(embed=embed)

        # Enqueue a crate opening log (non-blocking)
        try:
            q = logger_utils.start_background_writer()
            q.put_nowait({
                "event": "crate_open",
                "user_id": int(user.id),
                "crate_type": crate_type,
                "coins": coins,
                "items": [dict(i) for i in items],
            })
        except Exception:
            # never raise for logging failures
            pass

        # Persist crate opening into DB (analytics) if supported
        try:
            guild_id = None
            try:
                if getattr(message, "guild", None) is not None:
                    guild_id = int(message.guild.id)
            except Exception:
                guild_id = None

            if hasattr(inventory_utils, "async_record_crate_opening"):
                await inventory_utils.async_record_crate_opening(int(user.id), guild_id, crate_type, coins, [dict(i) for i in items])
        except Exception:
            # don't fail the flow for analytics errors
            pass

        # Broadcast rare drops to the channel where the crate was opened
        if rare_broadcasts:
            try:
                # If guild-specific rare-drop channel is configured, use it.
                from chronix_bot.utils import persistence as persistence_utils

                chan = None
                try:
                    if getattr(message, "guild", None) is not None:
                        gid = int(message.guild.id)
                        ch_id = persistence_utils.get_guild_setting(gid, "rare_drop_channel", None)
                        if ch_id:
                            chan = message.guild.get_channel(int(ch_id))
                except Exception:
                    chan = None

                # fallback to the current channel if none configured
                if chan is None:
                    chan = message.channel

                if chan is not None:
                    for r in rare_broadcasts:
                        # permission check: ensure bot can send messages in channel
                        try:
                            perms = chan.permissions_for(message.guild.me) if getattr(message, "guild", None) else None
                            if perms and not perms.send_messages:
                                continue
                        except Exception:
                            pass
                        await chan.send(f"✨ {user.mention} just found **{r.get('name')}** ({r.get('rarity')}) in a {crate_type} crate!")
            except Exception:
                # ignore broadcast failures
                pass

    # ----- marketplace and admin tooling -----
    @commands.command(name="market_sell")
    async def market_sell(self, ctx: commands.Context, crate_type: str, price: int):
        """List one unopened crate for sale on the marketplace (consumes it).

        Usage: chro market_sell basic 100
        """
        if price <= 0:
            await ctx.send("Price must be positive.")
            return
        # consume unopened crate
        try:
            consumed = None
            if hasattr(inventory_utils, "async_consume_unopened_crate"):
                consumed = await inventory_utils.async_consume_unopened_crate(ctx.author.id, crate_type)
            else:
                consumed = inventory_utils.consume_unopened_crate(ctx.author.id, crate_type)
        except Exception:
            consumed = None

        if not consumed:
            await ctx.send("You don't have an unopened crate of that type to sell.")
            return

        # create listing
        m = _load_market()
        nid = int(m.get("next_id", 1))
        listing = {
            "id": nid,
            "seller": int(ctx.author.id),
            "crate_id": consumed.get("crate_id"),
            "crate_type": consumed.get("crate_type"),
            "price": int(price),
            "created_at": int(time.time()),
        }
        m.setdefault("listings", {})[str(nid)] = listing
        m["next_id"] = nid + 1
        _save_market(m)
        await ctx.send(embed=helpers.make_embed("Listing Created", f"Listing #{nid}: {crate_type} for {helpers.format_chrons(price)}"))

    @commands.command(name="market_listings")
    async def market_listings(self, ctx: commands.Context):
        """List active marketplace listings."""
        m = _load_market()
        listings = m.get("listings", {})
        if not listings:
            await ctx.send("No listings on the marketplace.")
            return
        lines = []
        for lid, l in sorted(listings.items(), key=lambda x: int(x[0])):
            lines.append(f"#{lid}: {l.get('crate_type')} — {helpers.format_chrons(l.get('price'))} (seller: <@{l.get('seller')}>)")
        await ctx.send(embed=helpers.make_embed("Marketplace Listings", "\n".join(lines)))

    @commands.command(name="market_sell_item")
    async def market_sell_item(self, ctx: commands.Context, item_id: int, price: int):
        """List an arbitrary inventory item for sale (consumes it from your inventory).

        Usage: chro market_sell_item <item_id> <price>
        """
        if price <= 0:
            await ctx.send("Price must be positive.")
            return

        # Attempt to remove the item (DB-aware or file-backed)
        removed = None
        try:
            if hasattr(inventory_extras, "async_remove_item"):
                removed = await inventory_extras.async_remove_item(ctx.author.id, int(item_id))
            else:
                removed = inventory_extras.remove_item(ctx.author.id, int(item_id))
        except Exception:
            removed = None

        if not removed:
            await ctx.send("Item not found in your inventory or failed to remove.")
            return

        # Store listing with payload so it can be recreated on buy
        m = _load_market()
        nid = int(m.get("next_id", 1))
        listing = {
            "id": nid,
            "seller": int(ctx.author.id),
            "kind": "item",
            "payload": removed,
            "price": int(price),
            "created_at": int(time.time()),
        }
        m.setdefault("listings", {})[str(nid)] = listing
        m["next_id"] = nid + 1
        _save_market(m)
        await ctx.send(embed=helpers.make_embed("Listing Created", f"Listing #{nid}: {removed.get('name')} for {helpers.format_chrons(price)}"))

    @commands.command(name="market_cancel")
    async def market_cancel(self, ctx: commands.Context, listing_id: int):
        """Cancel a marketplace listing you created and return the item/crate to your inventory."""
        m = _load_market()
        l = m.get("listings", {}).get(str(listing_id))
        if not l:
            await ctx.send("Listing not found.")
            return
        if int(l.get("seller")) != int(ctx.author.id) and not await helpers.is_owner_check(ctx):
            await ctx.send("You are not the seller of this listing.")
            return

        kind = l.get("kind", "crate")
        try:
            if kind == "item":
                payload = l.get("payload") or {}
                if hasattr(inventory_utils, "async_add_item"):
                    await inventory_utils.async_add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
                else:
                    inventory_utils.add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
            else:
                crate_type = l.get("crate_type") or l.get("payload", {}).get("crate_type")
                if hasattr(inventory_utils, "async_add_unopened_crate"):
                    await inventory_utils.async_add_unopened_crate(ctx.author.id, crate_type)
                else:
                    inventory_utils.add_unopened_crate(ctx.author.id, crate_type)
        except Exception:
            await ctx.send("Failed to return item/crate to inventory; contact an admin.")
            return

        # remove listing
        try:
            del m.get("listings", {})[str(listing_id)]
            _save_market(m)
        except Exception:
            pass

        await ctx.send(embed=helpers.make_embed("Listing Cancelled", f"Listing #{listing_id} cancelled and returned to your inventory."))

    @commands.command(name="market_buy")
    async def market_buy(self, ctx: commands.Context, listing_id: int):
        """Buy a marketplace listing by ID."""
        m = _load_market()
        l = m.get("listings", {}).get(str(listing_id))
        if not l:
            await ctx.send("Listing not found.")
            return

        price = int(l.get("price", 0))
        seller = int(l.get("seller"))

        pool = db_utils.get_pool()

        # Support item listings and crate listings
        if l.get("kind") == "item":
            payload = l.get("payload") or {}
            item_name = payload.get("name")

            # DB-backed: try to perform money transfer and insert item into user_items in one transaction
            if pool is not None:
                try:
                    async with db_utils.transaction() as conn:
                        # lock buyer
                        brow = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", int(ctx.author.id))
                        if brow is None:
                            buyer_bal = 0
                            await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", int(ctx.author.id), 0, db_utils.__import__('datetime').datetime.utcnow())
                        else:
                            buyer_bal = int(brow["balance"])
                        if buyer_bal < price:
                            await ctx.send("Insufficient funds to purchase this listing.")
                            return
                        new_buyer = buyer_bal - price
                        await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_buyer, int(ctx.author.id))
                        await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1,$2,$3,$4,$5)", int(ctx.author.id), -price, f"market_buy:{listing_id}", new_buyer, db_utils.__import__('datetime').datetime.utcnow())

                        # credit seller
                        srow = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", seller)
                        if srow is None:
                            s_bal = 0
                            await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", seller, 0, db_utils.__import__('datetime').datetime.utcnow())
                        else:
                            s_bal = int(srow["balance"])
                        new_s = s_bal + price
                        await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_s, seller)
                        await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1,$2,$3,$4,$5)", seller, price, f"market_sale:{listing_id}", new_s, db_utils.__import__('datetime').datetime.utcnow())

                        # insert item for buyer
                        try:
                            meta_json = json.dumps(payload.get("meta", {}))
                        except Exception:
                            meta_json = json.dumps({})
                        row = await conn.fetchrow("INSERT INTO user_items (user_id, item_type, name, meta) VALUES ($1,$2,$3,$4) RETURNING id", int(ctx.author.id), payload.get("meta", {}).get("type", "misc"), payload.get("name"), meta_json)
                        # remove listing at the end (file-backed)
                        try:
                            del m.get("listings", {})[str(listing_id)]
                            _save_market(m)
                        except Exception:
                            pass
                        await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought listing #{listing_id}: {item_name} for {helpers.format_chrons(price)}"))
                        return
                except Exception as e:
                    await ctx.send(f"Purchase failed: {e}")
                    return

            # File-backed path (or DB not available): use safe money helper and add item to inventory
            try:
                await db_utils.safe_execute_money_transaction(int(ctx.author.id), -price, f"market_buy:{listing_id}")
            except Exception as e:
                await ctx.send(f"Purchase failed: {e}")
                return
            try:
                await db_utils.safe_execute_money_transaction(seller, price, f"market_sale:{listing_id}")
            except Exception:
                try:
                    await db_utils.safe_execute_money_transaction(int(ctx.author.id), price, f"market_refund:{listing_id}")
                except Exception:
                    pass
                await ctx.send("Purchase failed while crediting seller; refunded if possible.")
                return

            # add item payload to buyer inventory
            try:
                if hasattr(inventory_utils, "async_add_item"):
                    await inventory_utils.async_add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
                else:
                    inventory_utils.add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
            except Exception:
                # attempt refund
                try:
                    await db_utils.safe_execute_money_transaction(seller, -price, f"market_refund_failed_transfer:{listing_id}")
                    await db_utils.safe_execute_money_transaction(int(ctx.author.id), price, f"market_refund_failed_transfer:{listing_id}")
                except Exception:
                    pass
                await ctx.send("Purchase failed while transferring item; refunded if possible.")
                return

            # remove listing
            try:
                del m.get("listings", {})[str(listing_id)]
                _save_market(m)
            except Exception:
                pass

            await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought listing #{listing_id}: {item_name} for {helpers.format_chrons(price)}"))
            return

        # Default: treat as a crate listing (backwards-compatible)
        crate_type = l.get("crate_type")

        # DB-backed atomic purchase: update balances and insert unopened crate for buyer inside one transaction
        if pool is not None:
            try:
                async with db_utils.transaction() as conn:
                    # lock buyer
                    brow = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", int(ctx.author.id))
                    if brow is None:
                        buyer_bal = 0
                        await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", int(ctx.author.id), 0, db_utils.__import__('datetime').datetime.utcnow())
                    else:
                        buyer_bal = int(brow["balance"])
                    if buyer_bal < price:
                        await ctx.send("Insufficient funds to purchase this listing.")
                        return
                    new_buyer = buyer_bal - price
                    await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_buyer, int(ctx.author.id))
                    await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1,$2,$3,$4,$5)", int(ctx.author.id), -price, f"market_buy:{listing_id}", new_buyer, db_utils.__import__('datetime').datetime.utcnow())

                    # credit seller
                    srow = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", seller)
                    if srow is None:
                        s_bal = 0
                        await conn.execute("INSERT INTO users (user_id, balance, created_at) VALUES ($1, $2, $3)", seller, 0, db_utils.__import__('datetime').datetime.utcnow())
                    else:
                        s_bal = int(srow["balance"])
                    new_s = s_bal + price
                    await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_s, seller)
                    await conn.execute("INSERT INTO transactions (user_id, delta, reason, balance_after, created_at) VALUES ($1,$2,$3,$4,$5)", seller, price, f"market_sale:{listing_id}", new_s, db_utils.__import__('datetime').datetime.utcnow())

                    # insert unopened crate for buyer
                    await conn.fetchrow("INSERT INTO unopened_crates (owner_id, crate_type, created_at) VALUES ($1, $2, $3) RETURNING id", int(ctx.author.id), crate_type, db_utils.__import__('datetime').datetime.utcnow())

                    # remove listing file-backed
                    try:
                        del m.get("listings", {})[str(listing_id)]
                        _save_market(m)
                    except Exception:
                        pass

                    await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought listing #{listing_id}: {crate_type} for {helpers.format_chrons(price)}"))
                    return
            except Exception as e:
                await ctx.send(f"Purchase failed: {e}")
                return

        # Fallback (old behaviour): debit buyer then credit seller then add unopened crate
        try:
            await db_utils.safe_execute_money_transaction(int(ctx.author.id), -price, f"market_buy:{listing_id}")
        except Exception as e:
            await ctx.send(f"Purchase failed: {e}")
            return
        # credit seller (best-effort)
        try:
            await db_utils.safe_execute_money_transaction(seller, price, f"market_sale:{listing_id}")
        except Exception:
            # try rollback to buyer
            try:
                await db_utils.safe_execute_money_transaction(int(ctx.author.id), price, f"market_refund:{listing_id}")
            except Exception:
                pass
            await ctx.send("Purchase failed while crediting seller; refunded if possible.")
            return
        # transfer unopened crate to buyer (file-backed insert)
        try:
            if hasattr(inventory_utils, "async_add_unopened_crate"):
                await inventory_utils.async_add_unopened_crate(ctx.author.id, crate_type)
            else:
                inventory_utils.add_unopened_crate(ctx.author.id, crate_type)
        except Exception:
            # attempt refund
            try:
                await db_utils.safe_execute_money_transaction(seller, -price, f"market_refund_failed_transfer:{listing_id}")
                await db_utils.safe_execute_money_transaction(int(ctx.author.id), price, f"market_refund_failed_transfer:{listing_id}")
            except Exception:
                pass
            await ctx.send("Purchase failed while transferring crate; refunded if possible.")
            return

        # remove listing
        try:
            del m.get("listings", {})[str(listing_id)]
            _save_market(m)
        except Exception:
            pass

        await ctx.send(embed=helpers.make_embed("Purchase Complete", f"You bought listing #{listing_id}: {crate_type} for {helpers.format_chrons(price)}"))

    # ----- event crate admin -----
    @commands.command(name="create_event_crate")
    @commands.has_permissions(manage_guild=True)
    async def create_event_crate(self, ctx: commands.Context, name: str, loot_table: str, start_ts: int = 0, end_ts: int = 0):
        """Create an event crate mapping a crate type (name) to a loot table and active window.

        Example: chro create_event_crate summer summer_table 0 0
        """
        evs = _load_events()
        evs[name] = {"loot_table": loot_table, "start_ts": int(start_ts), "end_ts": int(end_ts)}
        _save_events(evs)
        await ctx.send(embed=helpers.make_embed("Event Crate Created", f"{name} => {loot_table} (start={start_ts} end={end_ts})"))

    @commands.command(name="list_event_crates")
    async def list_event_crates(self, ctx: commands.Context):
        evs = _load_events()
        if not evs:
            await ctx.send("No event crates configured.")
            return
        lines = []
        now = int(time.time())
        for name, ev in evs.items():
            start = int(ev.get("start_ts", 0) or 0)
            end = int(ev.get("end_ts", 0) or 0)
            active = (start == 0 or now >= start) and (end == 0 or now <= end)
            lines.append(f"{name}: table={ev.get('loot_table')} start={start} end={end} active={'yes' if active else 'no'}")
        await ctx.send(embed=helpers.make_embed("Event Crates", "\n".join(lines)))

    @commands.command(name="set_rare_channel")
    @commands.has_permissions(manage_guild=True)
    async def set_rare_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set a guild channel to receive rare-drop announcements. Pass no channel to clear."""
        gid = ctx.guild.id if ctx.guild else 0
        if channel is None:
            persistence_utils.set_guild_setting(gid, "rare_drop_channel", None)
            await ctx.send("Cleared rare-drop announcement channel.")
            return
        # validate bot permissions in the target channel
        try:
            perms = channel.permissions_for(ctx.guild.me) if channel and ctx.guild else None
            if channel and perms and not perms.send_messages:
                await ctx.send("I don't have permission to send messages in that channel. Please grant Send Messages permission and try again.")
                return
        except Exception:
            # best-effort permission check; ignore failures
            pass

        persistence_utils.set_guild_setting(gid, "rare_drop_channel", int(channel.id))
        await ctx.send(f"Set rare-drop announcements to {channel.mention}.")

    @commands.command(name="show_rare_channel")
    async def show_rare_channel(self, ctx: commands.Context):
        """Show the configured rare-drop channel for this guild."""
        gid = ctx.guild.id if ctx.guild else 0
        ch_id = persistence_utils.get_guild_setting(gid, "rare_drop_channel", None)
        if not ch_id:
            await ctx.send("No rare-drop channel configured for this guild.")
            return
        ch = ctx.guild.get_channel(int(ch_id)) if ctx.guild else None
        if ch is None:
            await ctx.send("Configured rare-drop channel could not be found (maybe deleted).")
            return
        await ctx.send(f"Rare-drop announcements are configured to: {ch.mention}")

    @commands.command(name="enable_event_for_guild")
    @commands.has_permissions(manage_guild=True)
    async def enable_event_for_guild(self, ctx: commands.Context, event_name: str):
        """Enable an event crate for this guild (overrides global activation)."""
        gid = ctx.guild.id if ctx.guild else 0
        persistence_utils.set_guild_setting(gid, f"event_override:{event_name}", {"enabled": True})
        await ctx.send(f"Enabled event `{event_name}` for this guild.")

    @commands.command(name="disable_event_for_guild")
    @commands.has_permissions(manage_guild=True)
    async def disable_event_for_guild(self, ctx: commands.Context, event_name: str):
        """Disable an event crate for this guild (overrides global activation)."""
        gid = ctx.guild.id if ctx.guild else 0
        persistence_utils.set_guild_setting(gid, f"event_override:{event_name}", {"enabled": False})
        await ctx.send(f"Disabled event `{event_name}` for this guild.")

    @commands.command(name="set_event_window_guild")
    @commands.has_permissions(manage_guild=True)
    async def set_event_window_guild(self, ctx: commands.Context, event_name: str, start_ts: int = 0, end_ts: int = 0):
        """Set a per-guild start/end timestamp override for an event crate.

        Pass 0 for start or end to indicate open-ended.
        """
        gid = ctx.guild.id if ctx.guild else 0
        persistence_utils.set_guild_setting(gid, f"event_override:{event_name}", {"enabled": True, "start_ts": int(start_ts), "end_ts": int(end_ts)})
        await ctx.send(f"Set event `{event_name}` window for this guild: start={start_ts} end={end_ts}")

    @commands.command(name="rarity_stats")
    async def rarity_stats(self, ctx: commands.Context, table_name: str = "basic"):
        """Show rarity analysis for a loot table to help balancing."""
        try:
            stats = analyze_rarity(table_name)
            lines = []
            for name, s in stats.items():
                lines.append(f"{name}: weight={s['weight']} rarity={s['rarity']} score={s['rarity_score']}")
            await ctx.send(embed=helpers.make_embed(f"Rarity Stats: {table_name}", "\n".join(lines)))
        except Exception as e:
            await ctx.send(f"Failed to analyze rarity: {e}")

    @commands.command(name="rarity_dashboard")
    async def rarity_dashboard(self, ctx: commands.Context, top: int = 10):
        """Aggregate crate opening logs and show top drops, counts, and rarity percentages.

        Uses file-backed `data/crate_openings.jsonl` when DB is not available.
        """
        logf = DATA_DIR / "crate_openings.jsonl"
        if not logf.exists():
            await ctx.send("No crate opening logs found.")
            return
        counts: dict[str, int] = {}
        rarity_map: dict[str, dict] = {}
        total_openings = 0
        total_coins = 0
        try:
            with open(logf, "r", encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        entry = json.loads(ln)
                    except Exception:
                        continue
                    total_openings += 1
                    total_coins += int(entry.get("coins", 0) or 0)
                    for it in entry.get("items", []):
                        name = it.get("name")
                        counts[name] = counts.get(name, 0) + 1
                        if name not in rarity_map:
                            rarity_map[name] = {"rarity": it.get("rarity"), "is_rare": bool(it.get("is_rare"))}
        except Exception as e:
            await ctx.send(f"Failed to read logs: {e}")
            return

        if not counts:
            await ctx.send("No drops recorded in logs.")
            return

        items = sorted(list(counts.items()), key=lambda x: x[1], reverse=True)[:int(top)]
        lines = [f"Total openings: {total_openings} | Total coins: {helpers.format_chrons(total_coins)}\n"]
        for name, cnt in items:
            meta = rarity_map.get(name, {})
            lines.append(f"{name}: {cnt} drops | rarity={meta.get('rarity')} | rare_flag={meta.get('is_rare')}")

        await ctx.send(embed=helpers.make_embed("Rarity Dashboard", "\n".join(lines)))

    @commands.command(name="rarity_tune")
    @commands.has_permissions(manage_guild=True)
    async def rarity_tune(self, ctx: commands.Context, table_name: str = "basic", pct_threshold: float = 0.9):
        """Compute rarity scores and suggest a threshold (percentile) for marking rare drops.

        pct_threshold is the percentile (0-1) above which items are recommended to be considered rare.
        """
        try:
            stats = analyze_rarity(table_name)
            # build list of (name, rarity_score)
            arr = [(n, s.get("rarity_score", 0.0)) for n, s in stats.items()]
            arr.sort(key=lambda x: x[1])
            scores = [s for _, s in arr]
            if not scores:
                await ctx.send("No items found in that table.")
                return
            import math

            idx = max(0, min(len(scores) - 1, int(math.floor(len(scores) * float(pct_threshold)))))
            suggested = scores[idx]
            lines = [f"Suggested rarity_score threshold at percentile {pct_threshold}: {suggested}\n"]
            for n, sc in arr:
                lines.append(f"{n}: score={sc} (rare if >= {suggested})")
            await ctx.send(embed=helpers.make_embed(f"Rarity Tune: {table_name}", "\n".join(lines)))
        except Exception as e:
            await ctx.send(f"Failed to compute rarity tuning: {e}")

    @commands.command(name="apply_rarity_threshold")
    @commands.has_permissions(manage_guild=True)
    async def apply_rarity_threshold(self, ctx: commands.Context, table_name: str = "basic", threshold: float = 0.8):
        """Apply a rarity threshold to a loot table by setting `is_rare` on items.

        This updates `data/loot_tables.yaml` in-place (file-backed). Threshold is a
        rarity_score cutoff (0-1) — items with rarity_score >= threshold will be marked `is_rare: true`.
        """
        lt_path = DATA_DIR / "loot_tables.yaml"
        if not lt_path.exists():
            await ctx.send("Loot tables file not found.")
            return
        try:
            import yaml
            tables = yaml.safe_load(lt_path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            await ctx.send(f"Failed to load loot tables: {e}")
            return

        stats = analyze_rarity(table_name)
        if table_name not in tables:
            await ctx.send(f"Table {table_name} not found in loot tables.")
            return

        items = tables[table_name].get("items", [])
        for it in items:
            name = it.get("name")
            s = stats.get(name, {})
            rs = float(s.get("rarity_score", 0.0))
            it["is_rare"] = rs >= float(threshold)

        # write back
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            lt_path.write_text(yaml.safe_dump(tables, sort_keys=False), encoding="utf-8")
            await ctx.send(embed=helpers.make_embed("Rarity Applied", f"Applied threshold {threshold} to table {table_name}. Updated loot_tables.yaml."))
        except Exception as e:
            await ctx.send(f"Failed to write loot tables: {e}")

    @commands.command(name="migrate_marketplace_to_db")
    @commands.is_owner()
    async def migrate_marketplace_to_db(self, ctx: commands.Context, out_sql: str = "migrations/import_marketplace.sql"):
        """Owner-only helper: generate SQL to import file-backed marketplace listings into a DB table.

        This helper does not execute SQL; it creates an SQL file with INSERT statements
        for a `marketplace_listings` table. This is a safe step to help migrate to DB.
        """
        m = _load_market()
        listings = list(m.get("listings", {}).values())
        if not listings:
            await ctx.send("No listings to migrate.")
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(out_sql, "w", encoding="utf-8") as fh:
                fh.write("-- Marketplace import SQL generated by migrate_marketplace_to_db\n")
                fh.write("-- Create table example:\n")
                fh.write("-- CREATE TABLE marketplace_listings (id bigint primary key, seller bigint, kind text, payload jsonb, price bigint, created_at timestamptz);\n\n")
                for l in listings:
                    lid = int(l.get("id"))
                    seller = int(l.get("seller"))
                    kind = l.get("kind", "crate")
                    payload = json.dumps(l.get("payload", {})).replace("'", "''")
                    price = int(l.get("price", 0))
                    created = int(l.get("created_at", 0))
                    # Use to_timestamp for portability
                    fh.write(f"INSERT INTO marketplace_listings (id, seller, kind, payload, price, created_at) VALUES ({lid}, {seller}, '{kind}', '{payload}', {price}, to_timestamp({created}));\n")
            await ctx.send(embed=helpers.make_embed("Migration SQL Generated", f"Wrote {out_sql} with {len(listings)} statements."))
        except Exception as e:
            await ctx.send(f"Failed to write SQL: {e}")

    @commands.command(name="crate", aliases=["opencrate", "open"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open_crate(self, ctx: commands.Context, crate_type: str = "basic") -> None:
        """Open a crate and receive random rewards (prefix)."""
        # Create confirmation view
        view = CrateView(crate_type)
        await ctx.send(f"Are you sure you want to open your {crate_type} crate?", view=view)

        # Wait for response
        await view.wait()
        if not view.confirmed:
            return

        # If user has an unopened crate of that type, try to consume it first.
        consumed = None
        try:
            if hasattr(inventory_utils, "async_consume_unopened_crate"):
                consumed = await inventory_utils.async_consume_unopened_crate(ctx.author.id, crate_type)
            else:
                consumed = inventory_utils.consume_unopened_crate(ctx.author.id, crate_type)
        except Exception:
            consumed = None

        if consumed:
            await ctx.send(f"Consumed one unopened {crate_type} crate from your inventory.")

        # Run reveal if confirmed
        await self._reveal_crate(ctx, crate_type)

    @app_commands.command(name="crate")
    @app_commands.describe(crate_type="The type of crate to open (basic, rare, etc)")
    async def slash_crate(self, interaction: discord.Interaction, crate_type: str = "basic") -> None:
        """Open a crate to receive random rewards (slash)."""
        view = CrateView(crate_type)
        await interaction.response.send_message(f"Are you sure you want to open your {crate_type} crate?", view=view, ephemeral=True)

        await view.wait()
        if not view.confirmed:
            return

        # If user has an unopened crate of that type, consume it first
        try:
            if hasattr(inventory_utils, "async_consume_unopened_crate"):
                consumed = await inventory_utils.async_consume_unopened_crate(interaction.user.id, crate_type)
            else:
                consumed = inventory_utils.consume_unopened_crate(interaction.user.id, crate_type)

            if consumed:
                await interaction.followup.send(f"Consumed one unopened {crate_type} crate from your inventory.", ephemeral=True)
        except Exception:
            pass

        # Run reveal if confirmed
        await self._reveal_crate(interaction, crate_type)

    @app_commands.command(name="crate_gift")
    @app_commands.describe(member="Member to gift the crate to", crate_type="Type of crate to gift")
    async def slash_gift_crate(self, interaction: discord.Interaction, member: discord.Member, crate_type: str = "basic") -> None:
        """Slash command: gift an unopened crate to another user."""
        try:
            if hasattr(inventory_utils, "async_add_unopened_crate"):
                crate = await inventory_utils.async_add_unopened_crate(member.id, crate_type)
            else:
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
        try:
            if hasattr(inventory_utils, "async_list_unopened_crates"):
                crates = await inventory_utils.async_list_unopened_crates(interaction.user.id)
            else:
                crates = inventory_utils.list_unopened_crates(interaction.user.id)
        except Exception:
            crates = []

        try:
            items = inventory_utils.list_items(interaction.user.id)
        except Exception:
            items = []
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

    @commands.command(name="crate_gift", aliases=["giftcrate", "crategift"])
    async def gift_crate(self, ctx: commands.Context, member: discord.Member, crate_type: str = "basic") -> None:
        """Gift an unopened crate to another user (adds to their inventory)."""
        if hasattr(inventory_utils, "async_add_unopened_crate"):
            try:
                crate = await inventory_utils.async_add_unopened_crate(member.id, crate_type)
            except Exception:
                crate = inventory_utils.add_unopened_crate(member.id, crate_type)
        else:
            crate = inventory_utils.add_unopened_crate(member.id, crate_type)

        await ctx.send(embed=helpers.make_embed("Crate Gifted", f"Gave a {crate_type} crate to {member.mention}! (ID: {crate.get('crate_id')})"))

    @commands.command(name="mycrates", aliases=["crates_list", "unopened"])
    async def my_crates(self, ctx: commands.Context) -> None:
        """List your unopened crates and misc items in inventory."""
        try:
            if hasattr(inventory_utils, "async_list_unopened_crates"):
                crates = await inventory_utils.async_list_unopened_crates(ctx.author.id)
            else:
                crates = inventory_utils.list_unopened_crates(ctx.author.id)
        except Exception:
            crates = []

        try:
            items = inventory_utils.list_items(ctx.author.id)
        except Exception:
            items = []
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

    # ----- trades (escrow for unopened crates) -----
    @commands.command(name="create_trade")
    async def create_trade(self, ctx: commands.Context, crate_type: str, note: str = ""):
        """Create a trade listing by placing one unopened crate into escrow.

        Usage: chro create_trade basic "Looking for epic sword"
        """
        # consume one unopened crate into escrow
        try:
            consumed = None
            if hasattr(inventory_utils, "async_consume_unopened_crate"):
                consumed = await inventory_utils.async_consume_unopened_crate(ctx.author.id, crate_type)
            else:
                consumed = inventory_utils.consume_unopened_crate(ctx.author.id, crate_type)
        except Exception:
            consumed = None

        if not consumed:
            await ctx.send("You don't have an unopened crate of that type to place into a trade.")
            return

        t = _load_trades()
        nid = int(t.get("next_id", 1))
        entry = {"id": nid, "owner": int(ctx.author.id), "kind": "crate", "crate_type": crate_type, "crate_id": consumed.get("crate_id"), "note": note, "created_at": int(time.time())}
        t.setdefault("trades", {})[str(nid)] = entry
        t["next_id"] = nid + 1
        _save_trades(t)
        await ctx.send(embed=helpers.make_embed("Trade Created", f"Trade #{nid}: {crate_type} (owner: <@{ctx.author.id}>)"))

    @commands.command(name="list_trades")
    async def list_trades(self, ctx: commands.Context):
        t = _load_trades()
        trades = t.get("trades", {})
        if not trades:
            await ctx.send("No active trades.")
            return
        lines = []
        for tid, tr in sorted(trades.items(), key=lambda x: int(x[0])):
            lines.append(f"#{tid}: {tr.get('kind')} {tr.get('crate_type')} (owner: <@{tr.get('owner')}>) note: {tr.get('note')}")
        await ctx.send(embed=helpers.make_embed("Active Trades", "\n".join(lines)))

    @commands.command(name="accept_trade")
    async def accept_trade(self, ctx: commands.Context, trade_id: int):
        """Accept a trade: transfers escrowed crate to the caller.

        Note: this simple flow does not auto-transfer payment; trading partners must
        agree externally or use marketplace listings for sales.
        """
        t = _load_trades()
        tr = t.get("trades", {}).get(str(trade_id))
        if not tr:
            await ctx.send("Trade not found.")
            return
        # transfer crate to buyer
        try:
            crate_type = tr.get("crate_type")
            if hasattr(inventory_utils, "async_add_unopened_crate"):
                await inventory_utils.async_add_unopened_crate(ctx.author.id, crate_type)
            else:
                inventory_utils.add_unopened_crate(ctx.author.id, crate_type)
        except Exception as e:
            await ctx.send(f"Failed to transfer crate: {e}")
            return

        # remove trade
        try:
            del t.get("trades", {})[str(trade_id)]
            _save_trades(t)
        except Exception:
            pass

        await ctx.send(embed=helpers.make_embed("Trade Completed", f"You accepted trade #{trade_id} and received a {crate_type} crate."))

    @commands.command(name="trade_item")
    async def trade_item(self, ctx: commands.Context, item_id: int, note: str = ""):
        """Place an arbitrary item into the trade escrow (consumes it from your inventory).

        Usage: chro trade_item <item_id> "note"
        """
        removed = None
        try:
            if hasattr(inventory_extras, "async_remove_item"):
                removed = await inventory_extras.async_remove_item(ctx.author.id, int(item_id))
            else:
                removed = inventory_extras.remove_item(ctx.author.id, int(item_id))
        except Exception:
            removed = None

        if not removed:
            await ctx.send("Item not found or failed to remove.")
            return

        t = _load_trades()
        nid = int(t.get("next_id", 1))
        entry = {"id": nid, "owner": int(ctx.author.id), "kind": "item", "payload": removed, "note": note, "created_at": int(time.time())}
        t.setdefault("trades", {})[str(nid)] = entry
        t["next_id"] = nid + 1
        _save_trades(t)
        await ctx.send(embed=helpers.make_embed("Trade Created", f"Trade #{nid}: item {removed.get('name')} (owner: <@{ctx.author.id}>)"))

    @commands.command(name="accept_trade_item")
    async def accept_trade_item(self, ctx: commands.Context, trade_id: int):
        """Accept a trade that contains an item; the item will be added to your inventory."""
        t = _load_trades()
        tr = t.get("trades", {}).get(str(trade_id))
        if not tr:
            await ctx.send("Trade not found.")
            return
        if tr.get("kind") != "item":
            await ctx.send("This trade does not contain an item.")
            return
        payload = tr.get("payload") or {}
        try:
            if hasattr(inventory_utils, "async_add_item"):
                await inventory_utils.async_add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
            else:
                inventory_utils.add_item(ctx.author.id, payload.get("name"), meta=payload.get("meta"))
        except Exception as e:
            await ctx.send(f"Failed to add item to inventory: {e}")
            return

        # remove trade
        try:
            del t.get("trades", {})[str(trade_id)]
            _save_trades(t)
        except Exception:
            pass

        await ctx.send(embed=helpers.make_embed("Trade Completed", f"You accepted trade #{trade_id} and received {payload.get('name')}."))


async def setup(bot: commands.Bot) -> None:
    """Add the crates cog to the bot."""
    await bot.add_cog(Crates(bot))