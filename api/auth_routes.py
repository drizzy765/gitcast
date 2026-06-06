from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.auth_middleware import get_current_user
from config.settings import APP_BASE_URL
from storage.supabase_client import get_client


router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    token: str


@router.post("/magic-link")
def magic_link(body: MagicLinkRequest):
    try:
        get_client().auth.sign_in_with_otp({"email": body.email})
        return {"success": True, "message": "check your email"}
    except Exception as e:
        print(f"[AuthRoutes] Magic link failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpRequest):
    try:
        response = get_client().auth.verify_otp({
            "email": body.email,
            "token": body.token,
            "type": "email",
        })
        session = getattr(response, "session", None)
        user = getattr(response, "user", None)
        access_token = getattr(session, "access_token", "")
        user_id = getattr(user, "id", "")
        if not access_token or not user_id:
            raise HTTPException(status_code=401, detail="Invalid OTP")
        return {"access_token": access_token, "user_id": str(user_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AuthRoutes] OTP verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid OTP") from e


@router.get("/github")
def github_login():
    try:
        redirect_to = f"{APP_BASE_URL.rstrip('/')}/auth/callback"
        response = get_client().auth.sign_in_with_oauth({
            "provider": "github",
            "options": {"redirect_to": redirect_to},
        })
        return RedirectResponse(str(response.url))
    except Exception as e:
        print(f"[AuthRoutes] GitHub OAuth failed: {e}")
        raise HTTPException(status_code=500, detail="GitHub OAuth failed") from e


@router.get("/callback")
def auth_callback(request: Request):
    code = request.query_params.get("code", "")
    code_verifier = request.query_params.get("code_verifier", "")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    try:
        response = get_client().auth.exchange_code_for_session({
            "auth_code": code,
            "code_verifier": code_verifier,
            "redirect_to": f"{APP_BASE_URL.rstrip('/')}/auth/callback",
        })
        session = getattr(response, "session", None)
        user = getattr(response, "user", None)
        access_token = getattr(session, "access_token", "")
        refresh_token = getattr(session, "refresh_token", "")
        user_id = getattr(user, "id", "")
        if not access_token:
            raise HTTPException(status_code=401, detail="OAuth exchange failed")

        fragment = f"access_token={access_token}&refresh_token={refresh_token}&user_id={user_id}"
        return RedirectResponse(f"/app#{fragment}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AuthRoutes] OAuth callback failed: {e}")
        raise HTTPException(status_code=401, detail="OAuth callback failed") from e


@router.post("/logout")
def logout(
    authorization: str = Header(None),
    user_id: str = Depends(get_current_user),
):
    try:
        _, _, token = (authorization or "").partition(" ")
        if token:
            get_client().auth.admin.sign_out(token, "global")
        return {"success": True}
    except Exception as e:
        print(f"[AuthRoutes] Logout failed for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("[AuthRoutes] Router loaded")
