import threading
from supabase import Client, create_client, ClientOptions
import config.settings

_thread_local = threading.local()

def get_client() -> Client:
    url = getattr(config.settings, "SUPABASE_URL", "")
    key = getattr(config.settings, "SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured")
    
    # Check if config changed and recreate if needed
    if hasattr(_thread_local, "client"):
        if getattr(_thread_local, "client_url", None) != url or getattr(_thread_local, "client_key", None) != key:
            if hasattr(_thread_local, "client"):
                delattr(_thread_local, "client")

    if not hasattr(_thread_local, "client"):
        _thread_local.client = create_client(
            url,
            key,
            options=ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=10
            )
        )
        _thread_local.client_url = url
        _thread_local.client_key = key
    return _thread_local.client


if __name__ == "__main__":
    client = get_client()
    print(f"[Supabase] Client initialized: {bool(client)}")
