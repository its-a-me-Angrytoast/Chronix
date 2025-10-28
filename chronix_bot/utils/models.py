"""Pydantic models for Chronix domain objects.

These are typed models used across cogs and utilities. They are intentionally
lightweight, documented, and include JSON (de)serialization helpers for JSONB
fields when using Postgres.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class User(BaseModel):
    user_id: int = Field(..., alias="id")
    balance: int = 0
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class GuildUser(BaseModel):
    guild_id: int
    user_id: int
    xp: int = 0
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True


class Pet(BaseModel):
    pet_id: int
    owner_id: int
    species: str
    level: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Weapon(BaseModel):
    weapon_id: int
    owner_id: int
    name: str
    rarity: str
    stats: Dict[str, Any] = Field(default_factory=dict)


class Gem(BaseModel):
    gem_id: int
    owner_id: int
    gem_type: str
    power: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutohuntSession(BaseModel):
    session_id: int
    user_id: int
    enabled: bool = True
    last_run: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class BattleState(BaseModel):
    battle_id: int
    players: Dict[str, Any]
    turn: int = 0
    state: Dict[str, Any] = Field(default_factory=dict)


class Clan(BaseModel):
    clan_id: int
    name: str
    owner_id: int
    treasury: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Ticket(BaseModel):
    ticket_id: int
    opener_id: int
    channel_id: Optional[int] = None
    status: str = "open"
    data: Dict[str, Any] = Field(default_factory=dict)


class Announcement(BaseModel):
    announcement_id: int
    author_id: int
    channel_id: int
    content: str
    scheduled_at: Optional[datetime] = None


def jsonb_serialize(obj: BaseModel) -> Dict[str, Any]:
    """Serialize a pydantic model to a JSON-ready dict for JSONB columns."""
    return obj.dict(by_alias=True)


def jsonb_deserialize(model_cls, data: Dict[str, Any]):
    """Deserialize data (dict) into a pydantic model instance."""
    return model_cls.parse_obj(data)
