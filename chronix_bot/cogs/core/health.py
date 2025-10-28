"""Health cog: exposes a lightweight aiohttp endpoint for container health."""
import aiohttp.web
from discord.ext import commands
import time


class HealthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()
        self.app = aiohttp.web.Application()
        self.app.add_routes([aiohttp.web.get("/health", self.handle_health)])
        self.runner = aiohttp.web.AppRunner(self.app)
        # start the webserver on the bot loop
        bot.loop.create_task(self._start_web())

    async def _start_web(self):
        await self.runner.setup()
        site = aiohttp.web.TCPSite(self.runner, "0.0.0.0", 8080)
        await site.start()
        print("Health endpoint running at http://0.0.0.0:8080/health")

    async def handle_health(self, request):
        uptime = int(time.time() - self.start_time)
        data = {
            "uptime": uptime,
            "bot_ready": self.bot.is_ready(),
        }
        return aiohttp.web.json_response(data)


async def setup(bot: commands.Bot):
    await bot.add_cog(HealthCog(bot))
