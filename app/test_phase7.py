import asyncio
import os
import sys
import time
from pathlib import Path
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


async def run_tests():
    ts = int(time.time())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("1. Admin Login...")
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@clubhub.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_token = res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        print("2. Admin Creating 2 Committees: Coding & Sports...")
        res = await client.post("/api/committees", json={
            "name": f"Coding Club {ts}",
            "category": "student",
            "sub_category": "coding",
            "description": "Coding Committee"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        coding_committee_id = res.json()["id"]

        res = await client.post("/api/committees", json={
            "name": f"Sports Club {ts}",
            "category": "student",
            "sub_category": "sports",
            "description": "Sports Committee"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        sports_committee_id = res.json()["id"]

        print("3. Admin Creating Members in both Committees...")
        res = await client.post(f"/api/committees/{coding_committee_id}/members", json={
            "full_name": "Coding Member 1",
            "email": f"coding_m1_{ts}@example.com",
            "role_title": "Lead Dev",
            "order_index": 1
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        coding_member_id = res.json()["id"]

        res = await client.post(f"/api/committees/{sports_committee_id}/members", json={
            "full_name": "Sports Member 1",
            "email": f"sports_m1_{ts}@example.com",
            "role_title": "Captain",
            "order_index": 1
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        sports_member_id = res.json()["id"]

        print("4. Admin Creating Sports Lead Account (assigned only to Sports Committee)...")
        sports_email = f"sports_lead_{ts}@clubhub.com"
        sports_password = "SportsPassword123"
        res = await client.post("/api/users", json={
            "email": sports_email,
            "password": sports_password,
            "role": "committee",
            "full_name": "Sports Lead Admin",
            "committee_ids": [sports_committee_id]
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("5. Sports Lead Login...")
        res = await client.post("/api/auth/committee/login", json={
            "email": sports_email,
            "password": sports_password
        })
        assert res.status_code == 200, res.text
        sports_token = res.json()["access_token"]
        sports_headers = {"Authorization": f"Bearer {sports_token}"}

        print("6. Testing GET /api/committees/my-scope for Sports Lead...")
        res = await client.get("/api/committees/my-scope", headers=sports_headers)
        assert res.status_code == 200, res.text
        scope_committees = res.json()
        assert len(scope_committees) == 1
        assert scope_committees[0]["id"] == sports_committee_id

        print("7. Denial Test 1: Sports Lead attempts POST to Coding Committee (Expect 403)...")
        res = await client.post(f"/api/committees/{coding_committee_id}/members", json={
            "full_name": "Unpermitted Coding Member",
            "email": "unpermitted@example.com",
            "role_title": "Hacker",
            "order_index": 9
        }, headers=sports_headers)
        print("Add Member to Coding Status:", res.status_code)
        assert res.status_code == 403, res.text

        print("8. Denial Test 2: Sports Lead attempts PUT to edit Coding Member (Expect 403)...")
        res = await client.put(f"/api/committee-members/{coding_member_id}", json={
            "role_title": "Hacked Role Title"
        }, headers=sports_headers)
        print("Edit Coding Member Status:", res.status_code)
        assert res.status_code == 403, res.text

        print("9. Denial Test 3: Sports Lead attempts DELETE on Coding Member (Expect 403)...")
        res = await client.delete(f"/api/committee-members/{coding_member_id}", headers=sports_headers)
        print("Delete Coding Member Status:", res.status_code)
        assert res.status_code == 403, res.text

        print("10. Allowed Test: Sports Lead edits member in their OWN Sports Committee (Expect 200)...")
        res = await client.put(f"/api/committee-members/{sports_member_id}", json={
            "role_title": "Head Captain"
        }, headers=sports_headers)
        print("Edit Sports Member Status:", res.status_code)
        assert res.status_code == 200, res.text
        assert res.json()["role_title"] == "Head Captain"

        print("11. Admin Bypass Test: Admin edits Coding Member (Expect 200)...")
        res = await client.put(f"/api/committee-members/{coding_member_id}", json={
            "role_title": "Admin Updated Lead"
        }, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["role_title"] == "Admin Updated Lead"

        print("\nALL PHASE 7 COMMITTEE-SCOPED ACCESS CONTROL TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
