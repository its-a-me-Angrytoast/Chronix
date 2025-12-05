import discord
from discord.ext import commands
import time

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'General Cog loaded.')

    @commands.command(name='ping', help='Checks the bot latency')
    async def ping(self, ctx):
        """
        Returns the bot's latency in milliseconds.
        """
        start_time = time.time()
        message = await ctx.send("Testing Ping...")
        end_time = time.time()
        
        api_latency = round(self.bot.latency * 1000)
        message_latency = round((end_time - start_time) * 1000)
        
        await message.edit(content=f"🏓 Pong! \nAPI Latency: `{api_latency}ms`\nMessage Latency: `{message_latency}ms`")

    @commands.command(name='info', help='Displays bot information')
    async def info(self, ctx):
        embed = discord.Embed(
            title="Chronix Bot Info",
            description="An all-rounder bot built with discord.py",
            color=discord.Color.blue()
        )
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        embed.add_field(name="Prefix", value="!", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
