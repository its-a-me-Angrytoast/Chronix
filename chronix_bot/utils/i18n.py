"""Minimal i18n helper for Chronix.

This provides a tiny file-backed translation loader. It's intentionally
lightweight and only used as a helper until a full i18n system is added.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

DATA_DIR = Path.cwd() / "data" / "i18n"


def load_locale(locale: str) -> Dict[str, str]:
    p = DATA_DIR / f"{locale}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def t(key: str, locale: str = "en", **kwargs) -> str:
    d = load_locale(locale)
    val = d.get(key) or key
    try:
        return val.format(**kwargs)
    except Exception:
        return val
