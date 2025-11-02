"""Owner-only sandbox runner.

Runs provided Python code in a separate process with resource limits and a
timeout. This is intentionally conservative: it restricts CPU time and
address space where supported (Unix) and captures stdout/stderr.

Usage: chro sandbox <code block or single-line code>
Only the bot owner may execute this command.
"""
from __future__ import annotations

import io
import sys
import traceback
import multiprocessing
from typing import Tuple

import discord
from discord.ext import commands

from chronix_bot.utils import helpers


def _runner(code: str, conn: multiprocessing.connection.Connection):
    """Child process runner: set resource limits and execute code.

    Sends back a tuple (ok: bool, output: str).
    """
    try:
        # apply resource limits on Unix
        try:
            import resource

            # 50 MB address space
            resource.setrlimit(resource.RLIMIT_AS, (50 * 1024 * 1024, 50 * 1024 * 1024))
            # 2 seconds CPU
            resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        except Exception:
            pass

        stdout = io.StringIO()
        stderr = io.StringIO()
        # capture prints
        sys.stdout = stdout
        sys.stderr = stderr

        # Minimal builtins
        safe_builtins = {
            "__builtins__": {
                "print": print,
                "range": range,
                "len": len,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "sorted": sorted,
            }
        }

        # execute
        loc = {}
        exec(code, safe_builtins, loc)
        out = stdout.getvalue()
        err = stderr.getvalue()
        res = (True, (out + "\n" + err).strip())
        conn.send(res)
    except Exception:
        tb = traceback.format_exc()
        try:
            conn.send((False, tb))
        except Exception:
            pass


class SandboxCog(commands.Cog):
    """Owner-only sandbox command.

    Note: This is intentionally limited and should only be used by the bot
    owner. It does not (and cannot) provide a bulletproof security boundary
    but does restrict CPU and memory where the platform allows.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="sandbox")
    @commands.is_owner()
    async def sandbox(self, ctx: commands.Context, *, code: str):
        """Execute python code in a restricted child process with timeout.

        Example: chro sandbox print('hello')
        For multi-line code, pass a code block or wrap in triple quotes.
        """
        # strip code fences if present
        if code.startswith("```") and code.endswith("```"):
            # remove triple backticks and optional language tag
            lines = code.split("\n")
            if len(lines) >= 2:
                # drop first and last
                code = "\n".join(lines[1:-1])
        parent_conn, child_conn = multiprocessing.Pipe()
        p = multiprocessing.Process(target=_runner, args=(code, child_conn))
        p.start()
        p.join(3)
        if p.is_alive():
            try:
                p.terminate()
            except Exception:
                pass
            await ctx.send(embed=helpers.make_embed("Sandbox Timeout", "Code execution exceeded time limit and was terminated."))
            return
        result = None
        try:
            if parent_conn.poll(0.1):
                result = parent_conn.recv()
        except Exception:
            result = None

        if not result:
            await ctx.send(embed=helpers.make_embed("Sandbox", "No output or execution failed."))
            return

        ok, out = result
        title = "Sandbox Output" if ok else "Sandbox Error"
        if not out:
            out = "(no output)"
        # truncate long outputs
        if len(out) > 1900:
            out = out[:1896] + "..."

        await ctx.send(embed=helpers.make_embed(title, out))


async def setup(bot: commands.Bot):
    await bot.add_cog(SandboxCog(bot))
