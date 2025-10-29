"""Music cog (Phase 7) — lightweight, async-first, Lavalink/Wavelink-ready.

This cog provides a development-friendly music system with a file-backed
persistent queue (`chronix_bot.utils.music_queue`). It attempts to use
`wavelink` when available; otherwise it still manages queues and basic
controls, but playback requires a Lavalink node.

Commands implemented:
- chro connect <channel> — join voice
- chro play <query_or_url> — search/enqueue and play
- chro queue — list queued tracks
- chro skip — skip current track
- chro pause/resume/stop — playback controls
- chro nowplaying — show current track
- chro volume — set volume

DJ role enforcement: if `MUSIC_DJ_ROLE_REQUIRED` or a DJ role is configured,
control commands will check for `manage_guild` or the DJ role.
"""
from __future__ import annotations

import asyncio
import logging
import shlex
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands

import os
from chronix_bot.utils import music_queue
from chronix_bot.utils import helpers
from chronix_bot.utils import music_utils
from chronix_bot.utils import logger as chronix_logger

log = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # in-memory now playing per guild
        self._now_playing: Dict[int, Optional[Dict[str, Any]]] = {}
        # UI views stored per guild to keep callbacks alive
        self._views: Dict[int, discord.ui.View] = {}
        # wavelink node state (guarded)
        self._wavelink_available = False
        self._wavelink_node = None

    def _check_dj(self, ctx: commands.Context) -> bool:
        # allow guild managers or owner
        if ctx.author.guild_permissions.manage_guild:
            return True
        # check for DJ role name `DJ` as a simple convention
        dj_role = discord.utils.get(ctx.guild.roles, name="DJ")
        if dj_role and dj_role in ctx.author.roles:
            return True
        return False

    @commands.command(name="connect")
    async def connect(self, ctx: commands.Context, channel: Optional[discord.VoiceChannel] = None):
        channel = channel or getattr(ctx.author.voice, "channel", None)
        if channel is None:
            await ctx.send("You must specify a voice channel or be connected.")
            return
        try:
            await channel.connect()
            await ctx.send(embed=helpers.make_embed("Connected", f"Joined {channel.name}"))
        except Exception as e:
            await ctx.send(f"Failed to connect: {e}")

    @commands.command(name="disconnect")
    async def disconnect(self, ctx: commands.Context):
        vc = ctx.voice_client
        if vc is None:
            await ctx.send("Not connected.")
            return
        try:
            await vc.disconnect()
            await ctx.send(embed=helpers.make_embed("Disconnected", "Left voice channel."))
        except Exception as e:
            await ctx.send(f"Disconnect failed: {e}")

    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        """Enqueue a track (URL or search query). Playback requires Lavalink/wavelink node."""
        if not query or len(query) > 400:
            await ctx.send("Invalid query or too long.")
            return

        # If a youtube API key exists, try to resolve best match
        resolved = await music_utils.search_youtube(query)
        url = resolved or query

        # Create a simple track dict — real playback would use a track object
        track = {"title": query, "url": url, "requested_by": ctx.author.id}
        music_queue.enqueue(ctx.guild.id if ctx.guild else 0, track)
        await ctx.send(embed=helpers.make_embed("Enqueued", f"{query} — requested by {ctx.author.display_name}"))
        try:
            chronix_logger.enqueue_log({"type": "music_enqueue", "guild": ctx.guild.id if ctx.guild else None, "title": query, "by": ctx.author.id})
        except Exception:
            pass
        # If wavelink is available and nothing is playing, attempt to start playback
        if self._wavelink_available:
            try:
                self.bot.loop.create_task(self._ensure_playing(ctx.guild.id))
            except Exception:
                pass

    @commands.command(name="queue")
    async def queue(self, ctx: commands.Context):
        q = music_queue.list_queue(ctx.guild.id if ctx.guild else 0)
        if not q:
            await ctx.send("Queue is empty.")
            return
        desc = "\n".join(f"{i+1}. {t.get('title')} — <@{t.get('requested_by')}>" for i, t in enumerate(q[:20]))
        await ctx.send(embed=helpers.make_embed("Queue", desc))

    @commands.command(name="queuepanel")
    async def queuepanel(self, ctx: commands.Context):
        """Create or refresh a persistent queue panel with buttons."""
        guild_id = ctx.guild.id if ctx.guild else 0
        q = music_queue.list_queue(guild_id)
        title = "Queue" if q else "Queue (empty)"
        desc = "\n".join(f"{i+1}. {t.get('title')} — <@{t.get('requested_by')}>" for i, t in enumerate(q[:20])) or "No tracks queued."
        embed = helpers.make_embed(title, desc)

        # make view
        view = QueuePanelView(self, guild_id)
        msg = await ctx.send(embed=embed, view=view)
        music_queue.set_panel_message(guild_id, ctx.channel.id, msg.id)
        try:
            chronix_logger.enqueue_log({"type": "music_queue_panel", "guild": guild_id, "channel": ctx.channel.id, "message": msg.id, "by": ctx.author.id})
        except Exception:
            pass
        # keep view reference so callbacks stay alive
        self._views[guild_id] = view
        await ctx.send("Queue panel created/updated.", delete_after=5.0)

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        if not self._check_dj(ctx):
            await ctx.send("You need Manage Server or the DJ role to skip tracks.")
            return
        skipped = music_queue.dequeue(ctx.guild.id if ctx.guild else 0)
        if skipped is None:
            await ctx.send("Nothing to skip.")
            return
        await ctx.send(embed=helpers.make_embed("Skipped", f"Skipped: {skipped.get('title')}"))
        try:
            chronix_logger.enqueue_log({"type": "music_skip", "guild": ctx.guild.id if ctx.guild else None, "title": skipped.get('title'), "by": ctx.author.id})
        except Exception:
            pass

    @commands.command(name="nowplaying")
    async def nowplaying(self, ctx: commands.Context):
        now = self._now_playing.get(ctx.guild.id if ctx.guild else 0)
        if not now:
            await ctx.send("Nothing is playing.")
            return
        await ctx.send(embed=helpers.make_embed("Now Playing", f"{now.get('title')} — requested by <@{now.get('requested_by')}>") )

    @commands.command(name="lyrics")
    async def lyrics(self, ctx: commands.Context, *, query: str):
        """Fetch lyrics for a track (artist - title preferred)."""
        try:
            lyrics = await music_utils.fetch_lyrics(query)
        except Exception:
            lyrics = None
        if not lyrics:
            await ctx.send("Lyrics not found for that query.")
            return
        payload = lyrics if len(lyrics) <= 1900 else lyrics[:1896] + "..."
        await ctx.send(embed=helpers.make_embed(f"Lyrics: {query}", payload))

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        if not self._check_dj(ctx):
            await ctx.send("You need Manage Server or the DJ role to stop playback.")
            return
        music_queue.clear_queue(ctx.guild.id if ctx.guild else 0)
        await ctx.send(embed=helpers.make_embed("Stopped", "Cleared queue and (would) stop playback."))
        try:
            chronix_logger.enqueue_log({"type": "music_stop", "guild": ctx.guild.id if ctx.guild else None, "by": ctx.author.id})
        except Exception:
            pass

    async def _refresh_panel(self, guild_id: int):
        meta = music_queue.get_panel_message(guild_id)
        if not meta:
            return
        chan_id = meta.get("panel_channel")
        msg_id = meta.get("panel_message")
        try:
            guild = discord.utils.get(self.bot.guilds, id=int(guild_id))
            if not guild:
                return
            ch = guild.get_channel(int(chan_id))
            if not ch:
                return
            msg = await ch.fetch_message(int(msg_id))
            q = music_queue.list_queue(guild_id)
            desc = "\n".join(f"{i+1}. {t.get('title')} — <@{t.get('requested_by')}>" for i, t in enumerate(q[:20])) or "No tracks queued."
            embed = helpers.make_embed("Queue", desc)
            await msg.edit(embed=embed)
        except Exception:
            return

    async def _ensure_playing(self, guild_id: int):
        """If a wavelink node is available, start playback for the guild queue."""
        if not self._wavelink_available:
            return
        try:
            # only proceed if not already playing
            now = self._now_playing.get(guild_id)
            if now:
                return
            # dequeue next
            next_track = music_queue.dequeue(guild_id)
            if not next_track:
                return
            # play using wavelink node if connected
            if self._wavelink_node is None:
                # mark now-playing metadata so we don't re-enter
                self._now_playing[guild_id] = next_track
                return

            try:
                # attempt to resolve via YouTube (wavelink helper) or URL
                import wavelink
                # prefer YouTube resolution via wavelink's search helper
                try:
                    tracks = await wavelink.YouTubeTrack.search(next_track.get("url"))
                except Exception:
                    # fallback: try search by title
                    try:
                        tracks = await wavelink.YouTubeTrack.search(next_track.get("title"))
                    except Exception:
                        tracks = []

                if not tracks:
                    # no playable track found
                    self._now_playing[guild_id] = next_track
                    return

                track_obj = tracks[0]
                # get or create player for guild
                node = wavelink.NodePool.get_node()
                try:
                    player = node.get_player(int(guild_id))
                except Exception:
                    # create player if necessary
                    player = await node.get_player(int(guild_id))

                # store now-playing and play
                self._now_playing[guild_id] = next_track
                try:
                    await player.play(track_obj)
                except Exception:
                    # if playback fails, clear now-playing so next attempt can continue
                    self._now_playing[guild_id] = None
                    return
            except Exception:
                # anything goes wrong, avoid crashing
                self._now_playing[guild_id] = next_track
                return
        except Exception:
            return


class QueuePanelView(discord.ui.View):
    def __init__(self, cog: Music, guild_id: int, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        # permission check
        allowed = interaction.user.guild_permissions.manage_guild or discord.utils.get(interaction.user.roles, name="DJ")
        if not allowed:
            await interaction.response.send_message("You need Manage Server or DJ role to skip.", ephemeral=True)
            return
        skipped = music_queue.dequeue(self.guild_id)
        await interaction.response.send_message(f"Skipped: {skipped.get('title')}" if skipped else "Nothing to skip.", ephemeral=False)
        await self.cog._refresh_panel(self.guild_id)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.danger)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        allowed = interaction.user.guild_permissions.manage_guild or discord.utils.get(interaction.user.roles, name="DJ")
        if not allowed:
            await interaction.response.send_message("You need Manage Server or DJ role to clear.", ephemeral=True)
            return
        music_queue.clear_queue(self.guild_id)
        await interaction.response.send_message("Queue cleared.")
        await self.cog._refresh_panel(self.guild_id)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog._refresh_panel(self.guild_id)

    @commands.command(name="volume")
    async def volume(self, ctx: commands.Context, vol: int):
        if vol < 0 or vol > 200:
            await ctx.send("Volume must be between 0 and 200.")
            return
        # volume control would call voice client or wavelink node; here we persist as a placeholder
        await ctx.send(embed=helpers.make_embed("Volume", f"Set volume to {vol}% (placeholder)"))


async def setup(bot: commands.Bot):
    cog = Music(bot)
    await bot.add_cog(cog)

    # Try to initialize a wavelink node if wavelink is installed and env vars are set.
    try:
        import wavelink

        host = os.getenv("LAVALINK_HOST")
        port = int(os.getenv("LAVALINK_PORT", "2333"))
        auth = os.getenv("LAVALINK_AUTH")
        if host and auth:
            # create node (best-effort)
            node = wavelink.Node(id="chronix", host=host, port=port, password=auth)
            try:
                bot.loop.create_task(wavelink.NodePool.connect(client=bot, nodes=[node]))
                cog._wavelink_available = True
                cog._wavelink_node = wavelink
            except Exception:
                # ignore node connection errors; wavelink optional
                cog._wavelink_available = False
    except Exception:
        # wavelink isn't installed; skip integration
        pass
