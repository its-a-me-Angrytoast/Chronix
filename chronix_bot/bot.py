"""Bot factory for Chronix.

Creates and configures the commands.Bot instance and auto-loads the core cog.
"""
from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands
from .config import Settings


def create_bot(settings: Optional[Settings] = None) -> commands.Bot:
    """Create a commands.Bot configured for Chronix.

    The function returns the Bot instance but does not call run().
    This attaches a small /ping command and, if `DEV_GUILD_ID` is set,
    syncs app commands to that guild for fast dev iteration.
    """
    if settings is None:
        settings = Settings()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="chro ", intents=intents)
    # attach settings for cogs to use
    bot.settings = settings  # type: ignore

    # attempt to load the core cog immediately so we have base commands
    try:
        bot.load_extension("chronix_bot.cogs.core.core")
        bot.load_extension("chronix_bot.cogs.core.health")
    except Exception as exc:
        print("Warning: failed to load core cogs at startup:", exc)

    # lightweight slash command for ping (mirrors prefix ping)
    @bot.tree.command(name="ping", description="Check bot latency")
    async def _ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        embed = discord.Embed(title="Pong!", description=f"Latency: {latency}ms")
        await interaction.response.send_message(embed=embed)

    # schedule a dev-guild sync once the bot is ready
    async def _sync_dev_guild():
        await bot.wait_until_ready()
        dev_guild = getattr(settings, "DEV_GUILD_ID", None)
        try:
            if dev_guild:
                guild_obj = discord.Object(id=int(dev_guild))
                await bot.tree.sync(guild=guild_obj)
                print(f"Synced app commands to dev guild {dev_guild}")
            else:
                # global sync is optional in dev; skip to avoid long propagation
                print("DEV_GUILD_ID not set — skipping guild sync")
        except Exception as e:
            print("Failed to sync app commands:", e)

    bot.loop.create_task(_sync_dev_guild())

    return bot
