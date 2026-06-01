from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"], headers_enabled=False)


if __name__ == "__main__":
    print("[RateLimit] Default limit: 60/minute")
