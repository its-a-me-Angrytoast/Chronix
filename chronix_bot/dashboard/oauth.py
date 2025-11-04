"""Discord OAuth helpers using Authlib Starlette integration.

This module registers a Discord OAuth client when the environment variables
are present. The dashboard uses Starlette's SessionMiddleware to store the
OAuth token in the session (cookie). For production, consider storing tokens
in secure storage and implementing refresh/rotation logic.
"""
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
import os

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DASHBOARD_REDIRECT_URI", "http://localhost:8080/oauth/callback")

oauth = OAuth()

if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
    oauth.register(
        name="discord",
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        access_token_url="https://discord.com/api/oauth2/token",
        authorize_url="https://discord.com/api/oauth2/authorize",
        api_base_url="https://discord.com/api/",
        client_kwargs={"scope": "identify guilds"},
    )


def is_oauth_configured() -> bool:
    return bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET)


async def get_user_and_token(request: Request) -> tuple[dict | None, dict | None]:
    """Return (user, token) if present in the session, otherwise (None, None)."""
    token = request.session.get("discord_token")
    user = request.session.get("discord_user")
    return user, token


async def fetch_user_from_token(token: dict) -> dict | None:
    if not token:
        return None
    client = oauth.create_client("discord")
    try:
        resp = await client.get("/users/@me", token=token)
        return resp.json()
    except Exception:
        return None
