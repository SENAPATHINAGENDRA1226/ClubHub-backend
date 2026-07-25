import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.seed import seed_data

if __name__ == "__main__":
    asyncio.run(seed_data())
