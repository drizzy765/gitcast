import hashlib
import json
from typing import Optional
from fastapi import Header, Query, HTTPException
from jose import JWTError, jwt

from config.settings import CONFIG_DIR, SUPABASE_JWT_AUDIENCE, SUPABASE_JWT_SECRET
from storage.supabase_client import get_client

LOCAL_USER_ID = "local_user"
KNOWN_SESSIONS: dict[str, str] = {}
SESSION_CACHE_FILE = CONFIG_DIR / "auth_sessions.json"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_session_cache() -> dict[str, str]:
    try:
        if SESSION_CACHE_FILE.exists():
            with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items()}
    except Exception:
        return {}
    return {}


def _save_session_cache(cache: dict[str, str]) -> None:
    try:
        SESSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as file:
            json.dump(cache, file, indent=2)
    except Exception:
        pass


def _unauthorized(message: str = "Unauthorized") -> HTTPException:
    return HTTPException(status_code=401, detail=message)


def verify_jwt(token: str) -> dict:
    if not token:
        raise _unauthorized("Missing bearer token")

    known_user_id = KNOWN_SESSIONS.get(token)
    if known_user_id:
        return {"user_id": known_user_id, "sub": known_user_id}
    cached_user_id = _load_session_cache().get(_token_hash(token))
    if cached_user_id:
        KNOWN_SESSIONS[token] = cached_user_id
        return {"user_id": cached_user_id, "sub": cached_user_id}

    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=SUPABASE_JWT_AUDIENCE,
            )
        except JWTError as exc:
            raise _unauthorized("Invalid bearer token") from exc

        user_id = payload.get("sub")
        if not user_id:
            raise _unauthorized("Invalid bearer token")
        payload["user_id"] = user_id
        return payload

    try:
        response = get_client().auth.get_user(token)
        user = getattr(response, "user", None)
        user_id = getattr(user, "id", None)
        if not user_id:
            raise _unauthorized("Invalid bearer token")
        return {"user_id": str(user_id), "sub": str(user_id)}
    except HTTPException:
        raise
    except Exception as exc:
        raise _unauthorized("Invalid bearer token") from exc


def register_session(access_token: str, user_id: str) -> None:
    if access_token and user_id:
        user_id = str(user_id)
        KNOWN_SESSIONS[access_token] = user_id
        cache = _load_session_cache()
        cache[_token_hash(access_token)] = user_id
        _save_session_cache(cache)


def unregister_session(access_token: str) -> None:
    if access_token:
        KNOWN_SESSIONS.pop(access_token, None)
        cache = _load_session_cache()
        cache.pop(_token_hash(access_token), None)
        _save_session_cache(cache)


async def get_current_user(
    authorization: str = Header(None),
    x_session_token: str = Header(None),
    token: Optional[str] = Query(None),
) -> str:
    from api.auth import get_token
    session_token = x_session_token or token
    if session_token and session_token == get_token():
        return LOCAL_USER_ID

    if not authorization and token:
        payload = verify_jwt(token.strip())
        return str(payload["user_id"])

    if not authorization:
        raise _unauthorized("Missing Authorization header")

    scheme, _, bearer_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not bearer_token:
        raise _unauthorized("Authorization header must be Bearer token")

    payload = verify_jwt(bearer_token.strip())
    return str(payload["user_id"])


if __name__ == "__main__":
    print("[AuthMiddleware] Import OK")
