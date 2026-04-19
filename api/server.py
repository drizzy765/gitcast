import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from config.settings import missing_api_keys

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Context Engine",
    description="Local AI server for build-in-public post generation",
    version="0.1.0",
    docs_url="/docs",   # available at http://127.0.0.1:8000/docs
    redoc_url=None,
)

# allow the UI layer to call the API from localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# register routes
app.include_router(router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    missing = missing_api_keys()
    return {
        "status": "ok",
        "missing_api_keys": missing,
        "ready": len(missing) == 0,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def start_server():
    """Starts the FastAPI server. Called from main.py in a background thread."""
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # keep console clean — only show warnings and errors
        reload=False,
    )


if __name__ == "__main__":
    print("[Server] Starting Context Engine API on http://127.0.0.1:8000")
    print("[Server] Docs available at http://127.0.0.1:8000/docs")
    start_server()