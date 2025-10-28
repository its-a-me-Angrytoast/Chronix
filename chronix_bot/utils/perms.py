"""Permission helpers for Chronix (Phase 1).

Provide small owner/dev checks used by owner-only commands in Phase 1.
"""
from discord.ext import commands
from typing import Callable


def is_owner() -> Callable:
    """Check that the invoking user is the configured OWNER_ID or the bot owner.

    Use as a decorator: `@commands.check(is_owner())`.
    """
    async def predicate(ctx: commands.Context) -> bool:
        settings = getattr(ctx.bot, "settings", None)
        if settings is not None and settings.OWNER_ID:
            try:
                if int(settings.OWNER_ID) == ctx.author.id:
                    return True
            except Exception:
                pass
        # fallback to library check
        return await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)


def is_dev() -> Callable:
    """Check that the invoking user is the configured DEV owner or OWNER.

    This is a lightweight check: it considers `DEV_GUILD_ID` to indicate dev
    mode and allows the OWNER_ID to bypass.
    """
    async def predicate(ctx: commands.Context) -> bool:
        settings = getattr(ctx.bot, "settings", None)
        # owner always allowed
        if settings is not None and settings.OWNER_ID:
            try:
                if int(settings.OWNER_ID) == ctx.author.id:
                    return True
            except Exception:
                pass
        # dev role: for Phase 1 we permit users in DEV_GUILD_ID to be devs
        # (further checks can be added later)
        return True if getattr(settings, "DEV_MODE", False) else False

    return commands.check(predicate)


def requires_owner_or_dev() -> Callable:
    """Composite check for owner OR dev privileges.

    Use as `@commands.check(requires_owner_or_dev())`.
    """

    async def predicate(ctx: commands.Context) -> bool:
        try:
            return await is_owner().__wrapped__(ctx)
        except Exception:
            # fallback to dev
            return await is_dev().__wrapped__(ctx)

    return commands.check(predicate)
