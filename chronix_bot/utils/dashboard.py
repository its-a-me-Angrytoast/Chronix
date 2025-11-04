from pathlib import Path
import json
import os
from typing import Optional, Dict


def _data_dir() -> Path:
    p = Path(os.environ.get("CHRONIX_DATA_DIR", Path(__file__).parents[2] / "data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cog_config(cog_name: str) -> Dict:
    cfg_dir = _data_dir() / 'dashboard_cogs'
    cfg_dir.mkdir(parents=True, exist_ok=True)
    f = cfg_dir / f"{cog_name}.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding='utf-8') or '{}')
    except Exception:
        return {}


def list_cog_configs() -> Dict[str, Dict]:
    cfg_dir = _data_dir() / 'dashboard_cogs'
    cfg_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in cfg_dir.glob('*.json'):
        try:
            out[f.stem] = json.loads(f.read_text(encoding='utf-8') or '{}')
        except Exception:
            out[f.stem] = {}
    return out
