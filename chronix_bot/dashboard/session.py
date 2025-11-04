from itsdangerous import URLSafeTimedSerializer
import os

_SECRET = os.environ.get("CHRONIX_SESSION_SECRET") or "dev-secret-change-me"
_SALT = "chronix-session-salt"

_serializer = URLSafeTimedSerializer(_SECRET, salt=_SALT)


def make_session_token(data: dict) -> str:
    return _serializer.dumps(data)


def load_session_token(token: str, max_age: int = 3600) -> dict | None:
    try:
        return _serializer.loads(token, max_age=max_age)
    except Exception:
        return None
