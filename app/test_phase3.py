import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


async def run_tests():
    ts = int(time.time())
    student_email = f"student_p3_{ts}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("1. Admin Login...")
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@clubhub.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_token = res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        print("2. Student Signup & Onboarding...")
        res = await client.post("/api/auth/student/signup", json={
            "name": "Phase3 Student",
            "email": student_email,
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res.status_code in (200, 201), res.text
        student_token = res.json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}

        # Onboard student
        res = await client.post("/api/onboarding/student", json={
            "branch": "CSM",
            "section": "B",
            "phone_number": "9123456789",
            "academic_year": "2nd Year"
        }, headers=student_headers)
        assert res.status_code == 200, res.text
        student_profile_id = res.json()["id"]

        print("3. Admin Creating a 'current' Event...")
        now_utc = datetime.now(timezone.utc)
        event_payload = {
            "title": f"Phase 3 Hackathon {ts}",
            "description": "Interactive Web & AI Hackathon",
            "category": "current",
            "event_date": (now_utc + timedelta(days=2)).isoformat(),
            "event_year": 2026,
            "location": "Innovation Lab",
            "max_participants": 50,
            "registration_deadline": (now_utc + timedelta(days=1)).isoformat(),
            "is_active": True
        }
        res = await client.post("/api/events", json=event_payload, headers=admin_headers)
        print("Create Event Status:", res.status_code)
        assert res.status_code == 201, res.text
        event = res.json()
        event_id = event["id"]

        print("4. Testing GET /api/events and GET /api/events/years...")
        res = await client.get("/api/events?category=current")
        assert res.status_code == 200, res.text
        assert any(e["id"] == event_id for e in res.json()["items"])

        res = await client.get("/api/events/years")
        assert res.status_code == 200, res.text
        assert 206 in res.json() or 2025 in res.json() or 2026 in res.json()

        print("5. Student Registering for Event (QR Generation)...")
        res = await client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
        print("Registration Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 201, res.text
        reg_data = res.json()
        reg_num = reg_data["registration_number"]
        qr_url = reg_data["qr_code_image_url"]
        assert reg_num.startswith("CH-2026-")
        assert qr_url == f"/media/qr/{reg_num}.png"

        # Verify physical QR image file on disk
        qr_file_path = os.path.join(backend_dir, "media", "qr", f"{reg_num}.png")
        assert os.path.exists(qr_file_path), f"QR code file missing at {qr_file_path}"

        print("6. Duplicate Registration Attempt (Expect 409)...")
        res = await client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
        print("Duplicate Reg Status:", res.status_code)
        assert res.status_code == 409, res.text

        print("7. Student Viewing Registrations /me...")
        res = await client.get("/api/registrations/me", headers=student_headers)
        assert res.status_code == 200, res.text
        assert len(res.json()["items"]) >= 1

        print("8. Admin Listing Registrations for Event...")
        res = await client.get(f"/api/registrations/event/{event_id}", headers=admin_headers)
        assert res.status_code == 200, res.text
        assert len(res.json()["items"]) >= 1

        print("9. Admin Issuing Certificate to Student...")
        cert_payload = {
            "student_id": student_profile_id,
            "event_id": event_id,
            "certificate_type": "winner"
        }
        res = await client.post("/api/certificates", json=cert_payload, headers=admin_headers)
        print("Certificate Issue Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 201, res.text
        cert_data = res.json()
        cert_id = cert_data["id"]

        print("10. Downloading Certificate PDF Stream...")
        res = await client.get(f"/api/certificates/{cert_id}/download")
        print("Download Status:", res.status_code, "Headers:", res.headers.get("content-type"))
        assert res.status_code == 200, res.text
        assert res.headers.get("content-type") == "application/pdf"
        assert len(res.content) > 100

        print("11. Student Viewing Certificates /me...")
        res = await client.get("/api/certificates/me", headers=student_headers)
        assert res.status_code == 200, res.text
        assert len(res.json()["items"]) >= 1

        print("12. Admin Deleting Certificate...")
        res = await client.delete(f"/api/certificates/{cert_id}", headers=admin_headers)
        assert res.status_code == 204, res.text

        print("\nALL PHASE 3 TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
