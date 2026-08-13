from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.auth_middleware import get_current_user, register_session, unregister_session
from config.settings import APP_BASE_URL


router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    token: str


@router.post("/magic-link")
def magic_link(body: MagicLinkRequest):
    return {"success": False, "error": "Supabase authentication is disabled in PyPI package"}


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpRequest):
    raise HTTPException(status_code=401, detail="Authentication is disabled in PyPI package")


@router.get("/github")
def github_login():
    raise HTTPException(status_code=500, detail="OAuth authentication is disabled in PyPI package")


@router.get("/callback")
def auth_callback(request: Request):
    raise HTTPException(status_code=401, detail="OAuth callback is disabled in PyPI package")


@router.post("/logout")
def logout(
    authorization: str = Header(None),
    user_id: str = Depends(get_current_user),
):
    _, _, token = (authorization or "").partition(" ")
    unregister_session(token)
    return {"success": True}


if __name__ == "__main__":
    print("[AuthRoutes] Router loaded")
