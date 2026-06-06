from functools import lru_cache

from supabase import Client, create_client

from config.settings import SUPABASE_SERVICE_KEY, SUPABASE_URL


@lru_cache(maxsize=1)
def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


if __name__ == "__main__":
    client = get_client()
    print(f"[Supabase] Client initialized: {bool(client)}")
