import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='kick', help='Kicks a member from the server')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        if member == ctx.author:
            await ctx.send("You cannot kick yourself!")
            return
        
        try:
            await member.kick(reason=reason)
            await ctx.send(f'👢 {member.mention} has been kicked. Reason: {reason}')
        except discord.Forbidden:
            await ctx.send("I do not have permission to kick this user.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name='ban', help='Bans a member from the server')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        if member == ctx.author:
            await ctx.send("You cannot ban yourself!")
            return

        try:
            await member.ban(reason=reason)
            await ctx.send(f'🔨 {member.mention} has been banned. Reason: {reason}')
        except discord.Forbidden:
            await ctx.send("I do not have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name='clear', aliases=['purge'], help='Clears a specified number of messages')
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 5):
        if amount < 1:
            await ctx.send("Amount must be at least 1.")
            return
            
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(f'Deleted {len(deleted) - 1} messages.')
        await msg.delete(delay=3)

    # Error handling for moderation commands
    @kick.error
    @ban.error
    @clear.error
    async def mod_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing arguments. Please check command usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Member not found or invalid argument.")
        else:
            await ctx.send(f"❌ An unexpected error occurred: {error}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
