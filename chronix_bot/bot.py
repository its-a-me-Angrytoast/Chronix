"""Bot factory for Chronix.

Creates and configures the commands.Bot instance and auto-loads the core cog.
"""
from typing import Optional
import discord
from discord.ext import commands
from discord import Object
from .config import Settings


class ChronixBot(commands.Bot):
    def __init__(self, settings: Settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings

    async def setup_hook(self) -> None:
        # Load core extensions asynchronously at startup
        try:
            await self.load_extension("chronix_bot.cogs.core.core")
            await self.load_extension("chronix_bot.cogs.core.health")
        except Exception as exc:
            print("Warning: failed to load core cogs at startup:", exc)

        # Register a lightweight ping command if not present
        try:
            @self.tree.command(name="ping", description="Check bot latency")
            async def _ping(interaction: discord.Interaction):
                latency = round(self.latency * 1000)
                embed = discord.Embed(title="Pong!", description=f"Latency: {latency}ms")
                await interaction.response.send_message(embed=embed)
        except Exception:
            # ignore registration errors during setup
            pass

        # Sync to dev guild for faster iteration when configured
        dev_guild = getattr(self.settings, "DEV_GUILD_ID", None)
        if dev_guild:
            try:
                guild_obj = Object(id=int(dev_guild))
                await self.tree.sync(guild=guild_obj)
                print(f"Synced app commands to dev guild {dev_guild}")
            except Exception as e:
                print("Failed to sync app commands:", e)


def create_bot(settings: Optional[Settings] = None) -> commands.Bot:
    """Create and return a configured ChronixBot instance."""
    if settings is None:
        settings = Settings()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = ChronixBot(settings, command_prefix="chro ", intents=intents)
    return bot
