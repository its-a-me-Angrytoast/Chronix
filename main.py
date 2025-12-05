import discord
import os
import asyncio
import logging
from discord.ext import commands
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ChronixBot")

# Load environment variables
    load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('BOT_OWNER_ID')) # Convert to int
BOT_NAME = os.getenv('BOT_NAME', 'Chronix Bot') # Default to 'Chronix Bot' if not set

# Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

class ChronixBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=commands.DefaultHelpCommand(),
            case_insensitive=True,
            owner_id=OWNER_ID
        )

    async def setup_hook(self):
        """
        This method is called before the bot logs in.
        It's the perfect place to load extensions.
        """
        logger.info("Loading extensions...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'Loaded extension: {filename}')
                except Exception as e:
                    logger.error(f'Failed to load extension {filename}.', exc_info=e)
        
        logger.info("Syncing command tree...")
        # Sync application commands (slash commands)
        # Note: In production, you might want to sync specific guilds for faster updates
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} application commands.")
        except Exception as e:
            logger.error("Failed to sync command tree.", exc_info=e)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"!help | {BOT_NAME}"))


    @commands.command(name='sync', help='Syncs application commands globally (owner only)')
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context):
        """
        Syncs application commands (slash commands) with Discord.
        Only usable by the bot owner.
        """
        if ctx.author.id != self.owner_id: # Simplified check, commands.is_owner() handles owner_ids
            await ctx.send("You must be the bot owner to use this command.")
            return

        await ctx.send("Attempting to sync application commands...")
        try:
            synced = await self.tree.sync()
            await ctx.send(f"Successfully synced {len(synced)} application commands globally.")
            logger.info(f"Bot owner {ctx.author} manually synced {len(synced)} application commands.")
        except Exception as e:
            await ctx.send(f"Failed to sync application commands: {e}")
            logger.error(f"Failed to manually sync application commands by {ctx.author}.", exc_info=e)

async def main():
    if not TOKEN or TOKEN == "your_token_here":
        logger.error("DISCORD_TOKEN not found in .env file. Please set it up.")
        return

    bot = ChronixBot()
    async with bot:
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
