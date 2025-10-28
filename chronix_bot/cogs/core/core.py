"""Core cog: basic commands and owner-only extension controls."""
from discord.ext import commands
import discord
import time


class Core(commands.Cog):
    """Core commands: ping, uptime and simple extension controls.

    Owner-only extension commands use the built-in is_owner check. In Phase 1
    this cog intentionally stays small and well-typed.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Core cog: bot ready as {self.bot.user} (id: {self.bot.user.id})")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Respond with latency (ms)."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(title="Pong!", description=f"Latency: {latency}ms")
        await ctx.send(embed=embed)

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context):
        uptime = int(time.time() - self.start_time)
        await ctx.send(f"Uptime: {uptime}s")

    @commands.command(name="load")
    @commands.is_owner()
    async def load(self, ctx: commands.Context, *, extension: str):
        try:
            self.bot.load_extension(extension)
            await ctx.send(f"Loaded {extension}")
        except Exception as e:
            await ctx.send(f"Load failed: {e}")

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, *, extension: str):
        try:
            self.bot.reload_extension(extension)
            await ctx.send(f"Reloaded {extension}")
        except Exception as e:
            await ctx.send(f"Reload failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
