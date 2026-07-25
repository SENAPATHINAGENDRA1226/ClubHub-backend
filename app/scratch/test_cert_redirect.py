import asyncio
import os
import sys
import time
from pathlib import Path
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


async def test_redirect():
    ts = int(time.time())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Admin login
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@clubhub.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_token = res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Student Signup & Onboarding
        res = await client.post("/api/auth/student/signup", json={
            "name": f"Redirect Student {ts}",
            "email": f"student_redir_{ts}@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res.status_code in (200, 201), res.text
        student_token = res.json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}

        # Complete onboarding to create StudentProfile
        res = await client.post("/api/onboarding/student", json={
            "branch": "CSE",
            "section": "A",
            "phone_number": "9988776655",
            "academic_year": "2nd Year"
        }, headers=student_headers)
        assert res.status_code == 200, res.text
        student_profile_id = res.json()["id"]

        # 3. Create Event
        res = await client.post("/api/events", json={
            "title": f"Redirect Fest {ts}",
            "description": "Event for redirect check",
            "category": "upcoming",
            "event_date": "2026-08-20T10:00:00Z",
            "event_year": 2026,
            "location": "Online",
            "registration_deadline": "2026-08-19T10:00:00Z",
            "is_active": True
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        event_id = res.json()["id"]

        # 4. Issue certificate with external link
        external_link = "https://external-certificates.com/verify/CH-2026-9999"
        res = await client.post("/api/certificates", json={
            "student_id": student_profile_id,
            "event_id": event_id,
            "certificate_type": "participation",
            "file_url": external_link
        }, headers=admin_headers)
        print("Issue Certificate status:", res.status_code)
        assert res.status_code == 201, res.text
        cert_id = res.json()["id"]
        assert res.json()["file_url"] == external_link

        # 5. Download certificate -> Expect Redirect response (302 or 307)
        res = await client.get(f"/api/certificates/{cert_id}/download", follow_redirects=False)
        print("Download Certificate redirect status:", res.status_code)
        print("Redirect target location:", res.headers.get("location"))
        assert res.status_code in (302, 307)
        assert res.headers.get("location") == external_link

        print("EXTERNAL CERTIFICATE REDIRECT TEST PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_redirect())
