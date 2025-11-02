"""Core cog: basic commands and owner-only extension controls."""
from discord.ext import commands
import discord
import time
from chronix_bot.utils import logger as chronix_logger
import asyncio
import traceback
from chronix_bot.utils import telemetry as telemetry_utils
from chronix_bot.utils import persistence as persistence_utils


class Core(commands.Cog):
    """Core commands: ping, uptime and simple extension controls.

    Owner-only extension commands use the built-in is_owner check. In Phase 1
    this cog intentionally stays small and well-typed.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        # start owner daily digest loop if owner configured
        try:
            self._digest_task = self.bot.loop.create_task(self._daily_digest_loop())
        except Exception:
            self._digest_task = None

    async def _daily_digest_loop(self):
        # small startup delay, then daily digests
        await asyncio.sleep(60)
        while True:
            try:
                owner_id = getattr(self.bot.settings, "OWNER_ID", None)
                if owner_id:
                    owner = self.bot.get_user(owner_id)
                    if owner:
                        snap = telemetry_utils.get_snapshot()
                        cmd_stats = snap.get("commands", {})
                        lines = [f"Telemetry snapshot: {len(cmd_stats)} commands recorded"]
                        for cmd, info in list(cmd_stats.items())[:10]:
                            lines.append(f"{cmd}: count={info.get('count',0)} total_ms={info.get('total_time_ms',0)}")
                        try:
                            await owner.send("\n".join(lines))
                        except Exception:
                            pass
            except Exception:
                pass
            # sleep 24 hours
            await asyncio.sleep(60 * 60 * 24)

    # ----- telemetry hooks
    async def cog_before_invoke(self, ctx: commands.Context):
        try:
            telemetry_utils.record_command_start(ctx)
        except Exception:
            pass

    async def cog_after_invoke(self, ctx: commands.Context):
        try:
            telemetry_utils.record_command_end(ctx)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global command error handler for user-friendly messages and logging."""
        # Log the error to the background writer
        try:
            msg = {
                "type": "command_error",
                "command": getattr(ctx.command, "qualified_name", None),
                "user_id": getattr(ctx.author, "id", None),
                "error": str(error),
                "trace": traceback.format_exc(),
            }
            chronix_logger.enqueue_log(msg)
        except Exception:
            pass

        # Friendly message to user
        try:
            await ctx.send(embed=discord.Embed(title="Error", description="An error occurred while processing your command."))
        except Exception:
            # ignore send errors
            pass

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

    @commands.command(name="setprefix")
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx: commands.Context, *, prefix: str):
        """Set a per-guild command prefix (admin only)."""
        try:
            gid = int(ctx.guild.id)
            persistence_utils.set_guild_setting(gid, "prefix", prefix)
            await ctx.send(f"Prefix set to: `{prefix}`")
        except Exception as e:
            await ctx.send(f"Failed to set prefix: {e}")

    @commands.command(name="getprefix")
    async def getprefix(self, ctx: commands.Context):
        try:
            if ctx.guild is None:
                await ctx.send("No guild context; default prefix is `chro `")
                return
            gid = int(ctx.guild.id)
            p = persistence_utils.get_guild_setting(gid, "prefix", "chro ")
            await ctx.send(f"Prefix for this guild: `{p}`")
        except Exception as e:
            await ctx.send(f"Failed to read prefix: {e}")

    @commands.command(name="owner_digest")
    @commands.is_owner()
    async def owner_digest(self, ctx: commands.Context):
        """Send a small telemetry/log digest to the owner DM (manual trigger).

        This is a lightweight owner dashboard substitute for Phase 3 daily digest.
        """
        try:
            snap = telemetry_utils.get_snapshot()
            cmd_stats = snap.get("commands", {})
            lines = [f"Telemetry snapshot: {len(cmd_stats)} commands recorded"]
            for cmd, info in list(cmd_stats.items())[:10]:
                lines.append(f"{cmd}: count={info.get('count',0)} total_ms={info.get('total_time_ms',0)}")
            owner = self.bot.get_user(self.bot.settings.OWNER_ID) if getattr(self.bot, "settings", None) else None
            if owner:
                try:
                    await owner.send("\n".join(lines))
                    await ctx.send("Digest sent to owner DM.")
                    return
                except Exception:
                    pass
            await ctx.send("Could not DM owner; here is the digest:\n" + "\n".join(lines))
        except Exception as e:
            await ctx.send(f"Failed to prepare digest: {e}")

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
