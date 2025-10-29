"""Music helper utilities (search scaffolds).

Provides a small helper to search YouTube using the Data API if
`YOUTUBE_API_KEY` is configured. Returns a URL string on success or None
if not resolvable.
"""
from __future__ import annotations

import os
from typing import Optional

import aiohttp


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


async def search_youtube(query: str) -> Optional[str]:
    """Search YouTube and return a video URL or None.

    Behavior:
    - If `YOUTUBE_API_KEY` is set, call the YouTube Data API `search.list`
      and return the first video's watch URL on success.
    - If no API key is set or the request fails, return None (caller may
      use the original query as-is which works for direct URLs).
    """
    if not YOUTUBE_API_KEY:
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "key": YOUTUBE_API_KEY,
        "maxResults": 1,
        "type": "video",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=6) as r:
                if r.status != 200:
                    return None
                js = await r.json()
                items = js.get("items", [])
                if not items:
                    return None
                vid = items[0].get("id", {}).get("videoId")
                if not vid:
                    return None
                return f"https://www.youtube.com/watch?v={vid}"
    except Exception:
        return None


async def search_spotify(query: str) -> Optional[str]:
    """Placeholder for Spotify search.

    If `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are configured this
    function should call Spotify's API and return a playable source or
    external URL. For now it returns None (caller should fallback to query).
    """
    # TODO: implement Spotify client credentials flow and search
    return None


async def spotify_search_client(query: str) -> Optional[str]:
    """Search Spotify using Client Credentials flow and return a track URL.

    Requires `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in env.
    Returns the Spotify track external URL or None if not resolvable.
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    # Obtain token
    token_url = "https://accounts.spotify.com/api/token"
    data = {"grant_type": "client_credentials"}
    import base64

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, headers=headers, timeout=6) as r:
                if r.status != 200:
                    return None
                tok = await r.json()
                access = tok.get("access_token")
            if not access:
                return None
            search_url = "https://api.spotify.com/v1/search"
            params = {"q": query, "type": "track", "limit": 1}
            h2 = {"Authorization": f"Bearer {access}"}
            async with session.get(search_url, params=params, headers=h2, timeout=6) as sr:
                if sr.status != 200:
                    return None
                js = await sr.json()
                items = js.get("tracks", {}).get("items", [])
                if not items:
                    return None
                track = items[0]
                return track.get("external_urls", {}).get("spotify")
    except Exception:
        return None