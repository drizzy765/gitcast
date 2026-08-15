import asyncio
import sys
from pathlib import Path

# Add project root to path so we can import config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.cloud_client import check_server_health

async def main():
    print("=== Gitcast Cloud Server Connectivity Test ===\n")
    health = check_server_health()
    print(f"Server Health: {health}")

def test_api_keys_script():
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
