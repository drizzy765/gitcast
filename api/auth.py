import uuid
from fastapi import Header, HTTPException

# [Auth] module for session-based API security

def generate_session_token():
    """Returns a random UUID string for session authentication."""
    return str(uuid.uuid4())

# SESSION_TOKEN global set on module import
SESSION_TOKEN = generate_session_token()

async def verify_token(x_session_token: str = Header(None)):
    """
    FastAPI dependency that raises 401 if the provided token 
    doesn't match the active session token.
    """
    if x_session_token != SESSION_TOKEN:
        raise HTTPException(
            status_code=401, 
            detail="Unauthorized: Invalid or missing X-Session-Token"
        )
    return x_session_token

def get_token():
    """Returns current SESSION_TOKEN for startup display."""
    return SESSION_TOKEN

if __name__ == "__main__":
    print("=== API AUTH TEST ===")
    token = get_token()
    print(f"Current Session Token: {token}")
    
    # Simple simulated verification
    import asyncio
    async def test_verify():
        try:
            await verify_token(token)
            print("Verification with correct token: PASSED")
        except HTTPException:
            print("Verification with correct token: FAILED")
            
        try:
            await verify_token("wrong-token")
            print("Verification with wrong token: FAILED")
        except HTTPException:
            print("Verification with wrong token: PASSED")
            
    asyncio.run(test_verify())
