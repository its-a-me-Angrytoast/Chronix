"""Render battle engine events into sequential text frames for embed-style updates.

The renderer is independent of Discord and returns a list of short strings
that can be used to update an embed or message per frame.
"""
from __future__ import annotations

from typing import List, Dict, Any


def render_battle_frames(events: List[Dict[str, Any]]) -> List[str]:
    frames: List[str] = []
    for ev in events:
        r = ev.get("round")
        a = ev.get("attacker")
        d = ev.get("defender")
        da = ev.get("dmg_to_def")
        db = ev.get("dmg_to_att")
        hp_a = ev.get("hp_a")
        hp_b = ev.get("hp_b")
        frames.append(f"Round {r}: {a} hits {d} for {da} dmg — {d} HP: {hp_b} | {a} HP: {hp_a}")
    if not frames:
        frames.append("No combat occurred.")
    return frames
