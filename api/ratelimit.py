from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_client_ip(request: Request) -> str:
    client_host = request.client.host if request.client else None
    if client_host in ["127.0.0.1", "localhost", "::1"]:
        return None
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"], headers_enabled=False)


if __name__ == "__main__":
    print("[RateLimit] Default limit: 60/minute (bypassed for localhost)")

