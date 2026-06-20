import threading
from supabase import Client, create_client, ClientOptions
from config.settings import SUPABASE_SERVICE_KEY, SUPABASE_URL

_thread_local = threading.local()

def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured")
    
    if not hasattr(_thread_local, "client"):
        _thread_local.client = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_KEY,
            options=ClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=10
            )
        )
    return _thread_local.client


if __name__ == "__main__":
    client = get_client()
    print(f"[Supabase] Client initialized: {bool(client)}")
