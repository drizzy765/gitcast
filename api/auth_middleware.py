from fastapi import Header, HTTPException
from jose import JWTError, jwt

from config.settings import SUPABASE_JWT_AUDIENCE, SUPABASE_JWT_SECRET
from storage.supabase_client import get_client


def _unauthorized(message: str = "Unauthorized") -> HTTPException:
    return HTTPException(status_code=401, detail=message)


def verify_jwt(token: str) -> dict:
    if not token:
        raise _unauthorized("Missing bearer token")

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


async def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Authorization header must be Bearer token")

    payload = verify_jwt(token.strip())
    return str(payload["user_id"])


if __name__ == "__main__":
    print("[AuthMiddleware] Import OK")
