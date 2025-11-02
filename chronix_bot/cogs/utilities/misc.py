"""Utility and miscellaneous commands (Phase 6).

This cog implements a broad set of utilities used across phases:
- serverinfo, userinfo, roleinfo, avatar
- choose, roll, poll, say (owner-only)
- banner, emojiinfo
- reminders and timers (file-backed persistence)
- translate (MyMemory fallback), define (dictionaryapi.dev)
- weather (wttr.in quick lookup) and fact (uselessfacts)
- convert (unit conversions) and eval-safe math expressions
- randomcolor (generate and preview a color)
- wiki (Wikipedia summary) and urban (Urban Dictionary)

Networked commands use aiohttp with timeouts and graceful fallback messages
when external APIs are unavailable.
"""
from __future__ import annotations


import random
import re
import math
import ast
import aiohttp
import asyncio
import time
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from chronix_bot.utils import helpers
from chronix_bot.utils import reminders as reminders_store
from pathlib import Path
import hashlib
import json


class Misc(commands.Cog):
    """Various small utility commands useful in many servers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx: commands.Context):
        g = ctx.guild
        if g is None:
            await ctx.send("This command must be used in a server.")
            return
        desc = (
            f"Name: {g.name}\n"
            f"ID: {g.id}\n"
            f"Members: {g.member_count}\n"
            f"Roles: {len(g.roles)}\n"
            f"Channels: {len(g.channels)}\n"
            f"Created: {g.created_at.isoformat()}"
        )
        await ctx.send(embed=helpers.make_embed("Server Info", desc))

    @commands.command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        desc = (
            f"Name: {member}\n"
            f"ID: {member.id}\n"
            f"Joined: {getattr(member, 'joined_at', 'N/A')}\n"
            f"Bot: {member.bot}"
        )
        await ctx.send(embed=helpers.make_embed("User Info", desc))

    @commands.command(name="roleinfo")
    async def roleinfo(self, ctx: commands.Context, *, role_name: str):
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f"Role '{role_name}' not found.")
            return
        members = [m for m in ctx.guild.members if role in m.roles]
        desc = f"Name: {role.name}\nID: {role.id}\nMembers: {len(members)}\nColor: {role.color}"
        await ctx.send(embed=helpers.make_embed("Role Info", desc))

    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        await ctx.send(member.display_avatar.url)

    @commands.command(name="banner")
    async def banner(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show the server or user banner if available."""
        member = member or ctx.author
        url = getattr(member, "banner", None)
        if url:
            await ctx.send(str(url.url))
            return
        g = ctx.guild
        if g and g.banner:
            await ctx.send(str(g.banner.url))
            return
        await ctx.send("No banner found for user or server.")

    @commands.command(name="emojiinfo")
    async def emojiinfo(self, ctx: commands.Context, emoji: str):
        """Show info about a custom emoji by mention or name."""
        # try to parse as emoji mention
        m = re.match(r"^<a?:([a-zA-Z0-9_]+):(\d+)>$", emoji)
        if m:
            name = m.group(1)
            eid = int(m.group(2))
            em = discord.utils.get(ctx.guild.emojis, id=eid)
        else:
            em = discord.utils.get(ctx.guild.emojis, name=emoji)
        if not em:
            await ctx.send("Emoji not found in this guild.")
            return
        desc = f"Name: {em.name}\nID: {em.id}\nAnimated: {em.animated}\nURL: {em.url}"
        await ctx.send(embed=helpers.make_embed("Emoji Info", desc))

    @commands.command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str):
        """Choose between options separated by `|` e.g. chro choose a|b|c"""
        parts = [p.strip() for p in options.split("|") if p.strip()]
        if not parts:
            await ctx.send("No options provided.")
            return
        pick = random.choice(parts)
        await ctx.send(embed=helpers.make_embed("Choice", pick))

    @commands.command(name="roll")
    async def roll(self, ctx: commands.Context, notation: Optional[str] = None):
        """Roll dice: NdM (e.g. 2d6) or simple integer to roll 1dN. Default 1d20."""
        if notation is None:
            notation = "1d20"
        m = re.match(r"^(?:(\d+)d)?(\d+)$", notation)
        if not m:
            await ctx.send("Invalid notation. Use NdM like 2d6 or just 20 for d20.")
            return
        n = int(m.group(1)) if m.group(1) else 1
        s = int(m.group(2))
        if n <= 0 or s <= 0 or n > 100:
            await ctx.send("Bad roll parameters.")
            return
        rolls = [random.randint(1, s) for _ in range(n)]
        await ctx.send(embed=helpers.make_embed("Roll", f"Rolls: {rolls} Total: {sum(rolls)}"))

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, *, question_and_options: str):
        """Create a quick reaction poll. Usage: chro poll Question | Option1 | Option2"""
        parts = [p.strip() for p in question_and_options.split("|") if p.strip()]
        if len(parts) < 2:
            await ctx.send("Provide a question and at least one option separated by `|`.")
            return
        # support an optional close:Xd suffix token to auto-close the poll
        question = parts[0]
        options = parts[1:][:10]
        close_seconds = None
        # detect tokens like close:1h or close:30m placed as last option
        if options:
            last = options[-1]
            if last.startswith("close:"):
                dur = last.split(":", 1)[1]
                try:
                    close_seconds = helpers.parse_duration(dur)
                    # remove the token from options
                    options = options[:-1]
                except Exception:
                    close_seconds = None
        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        desc = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
        msg = await ctx.send(embed=helpers.make_embed(f"Poll: {question}", desc))
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

        # schedule auto-close if requested
        if close_seconds and close_seconds > 0:
            self.bot.loop.create_task(self._auto_close_poll(msg, options, emojis[: len(options)], close_seconds, ctx.channel))

    async def _auto_close_poll(self, msg: discord.Message, options, emojis, delay: int, channel: discord.abc.Messageable):
        await asyncio.sleep(delay)
        try:
            # fetch fresh message to get reactions
            m = await channel.fetch_message(msg.id)
            results = []
            for i, e in enumerate(emojis):
                count = 0
                for r in m.reactions:
                    if getattr(r.emoji, "name", None) == getattr(e, "name", None) or str(r.emoji) == str(e):
                        count = r.count - (1 if r.me else 0)
                        break
                results.append((options[i] if i < len(options) else str(i+1), count))
            # build summary
            lines = [f"{emojis[i]} {opt} — {cnt} votes" for i, (opt, cnt) in enumerate(results)]
            await channel.send(embed=helpers.make_embed("Poll Closed", "\n".join(lines)))
        except Exception:
            pass

    # ----- reminders and timers
    @commands.command(name="remind")
    async def remind(self, ctx: commands.Context, when: str, *, message: str):
        """Set a reminder. When supports formats like 10m, 1h30m, 1d."""
        try:
            seconds = helpers.parse_duration(when)
        except ValueError as e:
            await ctx.send(str(e))
            return
        when_ts = int(time.time() + seconds)
        entry = reminders_store.add_reminder(ctx.author.id, when_ts, message, guild_id=ctx.guild.id if ctx.guild else None)
        # schedule background task
        self.bot.loop.create_task(self._deliver_reminder(entry))
        # Try to render the target time in user's configured timezone if present
        tz_file = Path.cwd() / "data" / "timezones.json"
        if tz_file.exists():
            try:
                d = json.loads(tz_file.read_text(encoding="utf-8"))
                tz = d.get(str(ctx.author.id))
                if tz:
                    try:
                        from zoneinfo import ZoneInfo
                        local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when_ts))
                        # best-effort: show UTC and TZ
                        await ctx.send(embed=helpers.make_embed("Reminder set", f"I'll remind you in {when}: {message} (ID: {entry['id']})\nTarget time (server local): {local}\nTimezone: {tz}"))
                        return
                    except Exception:
                        pass
            except Exception:
                pass
        await ctx.send(embed=helpers.make_embed("Reminder set", f"I'll remind you in {when}: {message} (ID: {entry['id']})"))

    async def _deliver_reminder(self, entry: dict):
        # entry["when"] is a UNIX timestamp
        now_ts = time.time()
        delay = int(entry.get("when", 0)) - int(now_ts)
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            user = await self.bot.fetch_user(entry["user_id"])
            await user.send(f"Reminder: {entry['message']}")
        except Exception:
            pass
        # remove reminder after delivery
        reminders_store.remove_reminder(entry["id"])

    @commands.command(name="timer")
    async def timer(self, ctx: commands.Context, duration: str):
        """Simple countdown timer in the current channel. e.g. chro timer 10m"""
        try:
            seconds = helpers.parse_duration(duration)
        except ValueError as e:
            await ctx.send(str(e))
            return
        msg = await ctx.send(embed=helpers.make_embed("Timer started", f"Timer: {duration} — I'll ping when done."))
        await asyncio.sleep(seconds)
        await ctx.send(embed=helpers.make_embed("Timer finished", f"{ctx.author.mention} timer for {duration} finished."))

    @commands.command(name="paste")
    async def paste(self, ctx: commands.Context, *, content: Optional[str] = None):
        """Create a local paste file from provided content or the last message attachment.

        If content is omitted and the invoking message has attachments, the first
        attachment is downloaded and saved as a paste. The paste is returned as
        a file attachment to the user.
        """
        data_dir = Path.cwd() / "data" / "pastes"
        data_dir.mkdir(parents=True, exist_ok=True)
        if content:
            txt = content
        else:
            # try to use message attachments
            if ctx.message.attachments:
                att = ctx.message.attachments[0]
                try:
                    txt = await att.read()
                    if isinstance(txt, bytes):
                        try:
                            txt = txt.decode("utf-8")
                        except Exception:
                            txt = str(txt)
                except Exception:
                    await ctx.send("Failed to read attachment.")
                    return
            else:
                await ctx.send("No content provided and no attachment found.")
                return

        # create a filename based on hash
        h = hashlib.sha1(txt.encode("utf-8") if isinstance(txt, str) else txt).hexdigest()
        fname = data_dir / f"paste_{h[:10]}.txt"
        try:
            with fname.open("w", encoding="utf-8") as f:
                f.write(txt if isinstance(txt, str) else str(txt))
            await ctx.send("Created paste:", file=discord.File(fp=str(fname), filename=fname.name))
        except Exception as e:
            await ctx.send(f"Failed to create paste: {e}")

    @commands.command(name="set_timezone")
    async def set_timezone(self, ctx: commands.Context, tz: Optional[str] = None):
        """Set your preferred timezone (IANA name) for reminder displays. e.g. set_timezone Europe/London"""
        data_dir = Path.cwd() / "data"
        tz_file = data_dir / "timezones.json"
        data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if tz is None:
                # clear
                if tz_file.exists():
                    d = json.loads(tz_file.read_text(encoding="utf-8"))
                    d.pop(str(ctx.author.id), None)
                    tz_file.write_text(json.dumps(d, indent=2), encoding="utf-8")
                await ctx.send("Cleared your timezone preference.")
                return
            # validate using zoneinfo
            try:
                from zoneinfo import ZoneInfo
                _ = ZoneInfo(tz)
            except Exception:
                await ctx.send("Invalid timezone. Provide an IANA timezone like Europe/London or America/New_York.")
                return
            if tz_file.exists():
                d = json.loads(tz_file.read_text(encoding="utf-8"))
            else:
                d = {}
            d[str(ctx.author.id)] = tz
            tz_file.write_text(json.dumps(d, indent=2), encoding="utf-8")
            await ctx.send(f"Timezone set to {tz}")
        except Exception as e:
            await ctx.send(f"Failed to set timezone: {e}")

    @commands.command(name="show_timezone")
    async def show_timezone(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Show the stored timezone for a user (default: you)."""
        target = member or ctx.author
        tz_file = Path.cwd() / "data" / "timezones.json"
        if not tz_file.exists():
            await ctx.send("No timezone set.")
            return
        try:
            d = json.loads(tz_file.read_text(encoding="utf-8"))
            tz = d.get(str(target.id))
            if not tz:
                await ctx.send(f"No timezone set for {target.display_name}.")
                return
            await ctx.send(f"Timezone for {target.display_name}: {tz}")
        except Exception as e:
            await ctx.send(f"Failed to read timezone: {e}")


async def setup(bot: commands.Bot):
    cog = Misc(bot)
    await bot.add_cog(cog)

    # Schedule outstanding reminders on startup (best-effort). We load stored
    # reminders and schedule delivery for those that are still pending.
    try:
        data = reminders_store.list_reminders()
        rems = data.get("reminders", []) if isinstance(data, dict) else []
        for entry in rems:
            # schedule only those with a valid timestamp
            try:
                when = int(entry.get("when", 0))
                if when <= 0:
                    continue
                # schedule delivery task
                bot.loop.create_task(cog._deliver_reminder(entry))
            except Exception:
                continue
    except Exception:
        # don't let the bot fail to start if scheduling fails
        pass

    # Register slash-command parity for major utilities
    try:
        @bot.tree.command(name="remind", description="Set a reminder (e.g. 10m, 1h)")
        async def _remind(interaction: discord.Interaction, when: str, message: str):
            await interaction.response.defer()
            try:
                seconds = helpers.parse_duration(when)
            except Exception as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
            when_ts = int(time.time() + seconds)
            entry = reminders_store.add_reminder(interaction.user.id, when_ts, message, guild_id=interaction.guild_id)
            # schedule delivery
            bot.loop.create_task(cog._deliver_reminder(entry))
            await interaction.followup.send(f"Reminder set: I'll remind you in {when}. (ID: {entry['id']})")

        @bot.tree.command(name="timer", description="Start a countdown timer in this channel")
        async def _timer(interaction: discord.Interaction, duration: str):
            await interaction.response.defer()
            try:
                seconds = helpers.parse_duration(duration)
            except Exception as e:
                await interaction.followup.send(str(e), ephemeral=True)
                return
            channel = interaction.channel
            await interaction.followup.send(f"Timer started for {duration}.")

            async def _timer_wait():
                await asyncio.sleep(seconds)
                try:
                    await channel.send(f"Timer finished: {interaction.user.mention} ({duration})")
                except Exception:
                    pass

            bot.loop.create_task(_timer_wait())

        @bot.tree.command(name="define", description="Get a dictionary definition")
        async def _define(interaction: discord.Interaction, word: str):
            await interaction.response.defer()
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=6) as r:
                        if r.status != 200:
                            await interaction.followup.send(f"No definition found for {word}.", ephemeral=True)
                            return
                        data = await r.json()
            except Exception:
                await interaction.followup.send("Lookup failed (network error).", ephemeral=True)
                return
            try:
                meanings = data[0].get("meanings", [])
                defs = meanings[0].get("definitions", [])
                definition = defs[0].get("definition")
                await interaction.followup.send(definition)
            except Exception:
                await interaction.followup.send(f"No definition found for {word}.", ephemeral=True)

        @bot.tree.command(name="translate", description="Translate text into a target language (e.g. en, es)")
        async def _translate(interaction: discord.Interaction, target_lang: str, text: str):
            await interaction.response.defer()
            url = "https://api.mymemory.translated.net/get"
            params = {"q": text, "langpair": f"auto|{target_lang}"}
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=8) as r:
                        if r.status != 200:
                            await interaction.followup.send("Translation failed.", ephemeral=True)
                            return
                        js = await r.json()
            except Exception:
                await interaction.followup.send("Translation failed (network).", ephemeral=True)
                return
            translated = js.get("responseData", {}).get("translatedText")
            if not translated:
                await interaction.followup.send("Translation unavailable.", ephemeral=True)
                return
            await interaction.followup.send(translated)

        @bot.tree.command(name="weather", description="Quick weather lookup via wttr.in")
        async def _weather(interaction: discord.Interaction, location: Optional[str] = ""):
            await interaction.response.defer()
            query = location or (interaction.guild.name if interaction.guild else "")
            url = f"https://wttr.in/{query}?format=3"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=6) as r:
                        text = await r.text()
                        await interaction.followup.send(text)
            except Exception:
                await interaction.followup.send("Weather lookup failed.", ephemeral=True)

        @bot.tree.command(name="fact", description="Get a random fact")
        async def _fact(interaction: discord.Interaction):
            await interaction.response.defer()
            url = "https://uselessfacts.jsph.pl/random.json?language=en"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=6) as r:
                        if r.status != 200:
                            await interaction.followup.send("Could not fetch fact.", ephemeral=True)
                            return
                        js = await r.json()
                        await interaction.followup.send(js.get("text"))
            except Exception:
                await interaction.followup.send("Fact service unavailable.", ephemeral=True)

        @bot.tree.command(name="wiki", description="Get a short Wikipedia summary")
        async def _wiki(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=6) as r:
                        if r.status != 200:
                            await interaction.followup.send("No wiki summary found.", ephemeral=True)
                            return
                        js = await r.json()
                        title = js.get("title")
                        extract = js.get("extract")
                        await interaction.followup.send(f"**{title}**\n{extract}")
            except Exception:
                await interaction.followup.send("Wikipedia lookup failed.", ephemeral=True)

        @bot.tree.command(name="urban", description="Lookup Urban Dictionary")
        async def _urban(interaction: discord.Interaction, term: str):
            await interaction.response.defer()
            url = "https://api.urbandictionary.com/v0/define"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params={"term": term}, timeout=6) as r:
                        js = await r.json()
                        if not js.get("list"):
                            await interaction.followup.send("No Urban Dictionary entry found.", ephemeral=True)
                            return
                        entry = js["list"][0]
                        await interaction.followup.send(entry.get("definition")[:1900])
            except Exception:
                await interaction.followup.send("Urban lookup failed.", ephemeral=True)

        @bot.tree.command(name="randomcolor", description="Generate a random color")
        async def _randomcolor(interaction: discord.Interaction):
            await interaction.response.defer()
            h = "%06x" % random.randint(0, 0xFFFFFF)
            await interaction.followup.send(f"#{h}")

        @bot.tree.command(name="convert", description="Simple unit conversions (c2f,f2c,m2ft,ft2m,km2mi,mi2km)")
        async def _convert(interaction: discord.Interaction, value: float, from_unit: str, to_unit: str):
            await interaction.response.defer()
            k = (from_unit.lower(), to_unit.lower())
            res = None
            if k == ("c", "f") or k == ("celsius", "fahrenheit"):
                res = value * 9/5 + 32
            elif k == ("f", "c") or k == ("fahrenheit", "celsius"):
                res = (value - 32) * 5/9
            elif k == ("m", "ft") or k == ("meter", "feet"):
                res = value * 3.28084
            elif k == ("ft", "m") or k == ("feet", "meter"):
                res = value / 3.28084
            elif k == ("km", "mi"):
                res = value * 0.621371
            elif k == ("mi", "km"):
                res = value / 0.621371
            else:
                await interaction.followup.send("Unsupported conversion.", ephemeral=True)
                return
            await interaction.followup.send(f"{value} {from_unit} = {res:.4f} {to_unit}")

        @bot.tree.command(name="eval", description="Evaluate a math expression (safe)")
        async def _eval(interaction: discord.Interaction, expr: str):
            await interaction.response.defer()
            try:
                v = cog._safe_eval_expr(expr)
                await interaction.followup.send(str(v))
            except Exception as e:
                await interaction.followup.send(f"Eval error: {e}", ephemeral=True)

        @bot.tree.command(name="emojiinfo", description="Show info about a custom emoji")
        async def _emojiinfo(interaction: discord.Interaction, emoji: str):
            await interaction.response.defer()
            # mimic prefix behavior (guild emojis)
            m = re.match(r"^<a?:([a-zA-Z0-9_]+):(\d+)>$", emoji)
            if m:
                eid = int(m.group(2))
                em = discord.utils.get(interaction.guild.emojis, id=eid) if interaction.guild else None
            else:
                em = discord.utils.get(interaction.guild.emojis, name=emoji) if interaction.guild else None
            if not em:
                await interaction.followup.send("Emoji not found in this guild.", ephemeral=True)
                return
            desc = f"Name: {em.name}\nID: {em.id}\nAnimated: {em.animated}\nURL: {em.url}"
            await interaction.followup.send(desc)

        @bot.tree.command(name="banner", description="Show user or server banner")
        async def _banner(interaction: discord.Interaction, member: Optional[discord.Member] = None):
            await interaction.response.defer()
            member = member or interaction.user
            url = getattr(member, "banner", None)
            if url:
                await interaction.followup.send(str(url.url))
                return
            g = interaction.guild
            if g and g.banner:
                await interaction.followup.send(str(g.banner.url))
                return
            await interaction.followup.send("No banner found.", ephemeral=True)
    except Exception:
        # app command registration can fail in restricted environments
        pass
    @commands.command(name="say")
    @commands.is_owner()
    async def say(self, ctx: commands.Context, *, text: str):
        """Owner-only say command to let the bot say something."""
        await ctx.send(text)

    # ----- external lookups (networked; graceful fallback)
    async def _fetch_json(self, url: str, params: dict | None = None, timeout: int = 8):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception:
            return None

    @commands.command(name="define")
    async def define(self, ctx: commands.Context, word: str):
        """Look up a dictionary definition (dictionaryapi.dev)."""
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=6) as r:
                    if r.status != 200:
                        await ctx.send(f"No definition found for {word}.")
                        return
                    data = await r.json()
        except Exception:
            await ctx.send("Lookup failed (network error).")
            return
        try:
            meanings = data[0].get("meanings", [])
            defs = meanings[0].get("definitions", [])
            definition = defs[0].get("definition")
            await ctx.send(embed=helpers.make_embed(f"Definition: {word}", definition))
        except Exception:
            await ctx.send(f"No definition found for {word}.")

    @commands.command(name="translate")
    async def translate(self, ctx: commands.Context, target_lang: str, *, text: str):
        """Translate text using MyMemory free API as a fallback."""
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"auto|{target_lang}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=8) as r:
                    if r.status != 200:
                        await ctx.send("Translation failed.")
                        return
                    js = await r.json()
        except Exception:
            await ctx.send("Translation failed (network).")
            return
        translated = js.get("responseData", {}).get("translatedText")
        if not translated:
            await ctx.send("Translation unavailable.")
            return
        await ctx.send(embed=helpers.make_embed("Translation", translated))

    @commands.command(name="weather")
    async def weather(self, ctx: commands.Context, *, location: str = ""):
        """Quick weather via wttr.in. Usage: chro weather London"""
        query = location or ctx.guild.name if ctx.guild else ""
        url = f"https://wttr.in/{query}?format=3"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=6) as r:
                    text = await r.text()
                    await ctx.send(text)
        except Exception:
            await ctx.send("Weather lookup failed.")

    @commands.command(name="fact")
    async def fact(self, ctx: commands.Context):
        """Random fact (uselessfacts API)."""
        url = "https://uselessfacts.jsph.pl/random.json?language=en"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=6) as r:
                    if r.status != 200:
                        await ctx.send("Could not fetch fact.")
                        return
                    js = await r.json()
                    await ctx.send(js.get("text"))
        except Exception:
            await ctx.send("Fact service unavailable.")

    # ----- math and conversions
    @commands.command(name="convert")
    async def convert(self, ctx: commands.Context, value: float, from_unit: str, to_unit: str):
        """Simple conversions: c2f, f2c, m2ft, ft2m, km2mi, mi2km"""
        k = (from_unit.lower(), to_unit.lower())
        res = None
        if k == ("c", "f") or k == ("celsius", "fahrenheit"):
            res = value * 9/5 + 32
        elif k == ("f", "c") or k == ("fahrenheit", "celsius"):
            res = (value - 32) * 5/9
        elif k == ("m", "ft") or k == ("meter", "feet"):
            res = value * 3.28084
        elif k == ("ft", "m") or k == ("feet", "meter"):
            res = value / 3.28084
        elif k == ("km", "mi"):
            res = value * 0.621371
        elif k == ("mi", "km"):
            res = value / 0.621371
        else:
            await ctx.send("Unsupported conversion.")
            return
        await ctx.send(embed=helpers.make_embed("Convert", f"{value} {from_unit} = {res:.4f} {to_unit}"))

    def _safe_eval_expr(self, expr: str):
        """Safely evaluate math expressions using ast with limited nodes."""
        allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Load, ast.operator, ast.unaryop, ast.Call, ast.Name, ast.Constant)
        node = ast.parse(expr, mode="eval")
        for n in ast.walk(node):
            if not isinstance(n, allowed_nodes):
                raise ValueError("Unsupported expression")
        # allow math functions
        safe_names = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_names.update({"abs": abs, "round": round})
        return eval(compile(node, "<ast>", "eval"), {"__builtins__": {}}, safe_names)

    @commands.command(name="eval")
    async def eval_cmd(self, ctx: commands.Context, *, expr: str):
        """Evaluate a math expression safely (supports math module)."""
        try:
            v = self._safe_eval_expr(expr)
            await ctx.send(embed=helpers.make_embed("Eval Result", str(v)))
        except Exception as e:
            await ctx.send(f"Eval error: {e}")

    @commands.command(name="randomcolor")
    async def randomcolor(self, ctx: commands.Context):
        h = "%06x" % random.randint(0, 0xFFFFFF)
        color = int(h, 16)
        embed = helpers.make_embed(f"#{h}", "Random color generated")
        embed.colour = color
        await ctx.send(embed=embed)

    # ----- wiki and urban dictionary
    @commands.command(name="wiki")
    async def wiki(self, ctx: commands.Context, *, query: str):
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=6) as r:
                    if r.status != 200:
                        await ctx.send("No wiki summary found.")
                        return
                    js = await r.json()
                    title = js.get("title")
                    extract = js.get("extract")
                    await ctx.send(embed=helpers.make_embed(title or "Wikipedia", extract or "No summary."))
        except Exception:
            await ctx.send("Wikipedia lookup failed.")

    @commands.command(name="urban")
    async def urban(self, ctx: commands.Context, *, term: str):
        url = "https://api.urbandictionary.com/v0/define"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"term": term}, timeout=6) as r:
                    js = await r.json()
                    if not js.get("list"):
                        await ctx.send("No Urban Dictionary entry found.")
                        return
                    entry = js["list"][0]
                    await ctx.send(embed=helpers.make_embed(entry.get("word"), entry.get("definition")[:1900]))
        except Exception:
            await ctx.send("Urban lookup failed.")

    @app_commands.command(name="serverinfo")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        await interaction.response.send_message("See prefix command chro serverinfo for details.")
