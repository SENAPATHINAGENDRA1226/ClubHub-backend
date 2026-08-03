import asyncio
import sys
from pathlib import Path
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


async def run_debug():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@csmd-dlides-club.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Test GET /api/users?limit=200
        res_users = await client.get("/api/users?limit=200", headers=headers)
        print("GET /api/users?limit=200 status:", res_users.status_code)
        if res_users.status_code != 200:
            print("Users error detail:", res_users.text)

        # 2. Test GET /api/certificates?limit=200
        res_certs = await client.get("/api/certificates?limit=200", headers=headers)
        print("GET /api/certificates?limit=200 status:", res_certs.status_code)
        if res_certs.status_code != 200:
            print("Certs error detail:", res_certs.text)

        # 3. Test GET /api/settings
        res_settings = await client.get("/api/settings", headers=headers)
        print("GET /api/settings status:", res_settings.status_code)
        if res_settings.status_code != 200:
            print("Settings error detail:", res_settings.text)


if __name__ == "__main__":
    asyncio.run(run_debug())
