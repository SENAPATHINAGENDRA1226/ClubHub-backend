import asyncio
import io
import os
import sys
import time
import zipfile
from pathlib import Path
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app


async def run_tests():
    ts = int(time.time())
    admin_headers = {}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("1. Admin Login...")
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@clubhub.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

        print("2. Testing Bulk Student CSV Import...")
        student_csv = f"""email,full_name,branch,section,phone_number,academic_year,cgpa
bulk_student1_{ts}@example.com,Bulk Student One,CSE,A,9876543210,3rd Year,8.5
bulk_student2_{ts}@example.com,Bulk Student Two,ECE,B,9876543211,2nd Year,7.9
"""
        files = {"file": ("students.csv", student_csv.encode("utf-8"), "text/csv")}
        res = await client.post("/api/admin/import/students", files=files, headers=admin_headers)
        print("Student Import Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["created_count"] == 2

        print("3. Testing Bulk Past Events CSV Import...")
        past_events_csv = f"""title,description,event_date,event_year,location
Legacy Hackathon {ts},Annual hackathon event,2024-11-10,2024,Main Campus Hall
Legacy CodeFest {ts},Winter coding challenge,2023-12-15,2023,Auditorium
"""
        files = {"file": ("past_events.csv", past_events_csv.encode("utf-8"), "text/csv")}
        res = await client.post("/api/admin/import/past-events", files=files, headers=admin_headers)
        print("Past Events Import Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["imported_count"] == 2

        print("4. Testing Bulk Alumni CSV Import...")
        alumni_csv = f"""full_name,graduation_year,branch,current_company,current_role
Alumni Alpha,2022,CSE,Google,Software Engineer
Alumni Beta,2021,CSM,Microsoft,Product Manager
"""
        files = {"file": ("alumni.csv", alumni_csv.encode("utf-8"), "text/csv")}
        res = await client.post("/api/admin/import/alumni", files=files, headers=admin_headers)
        print("Alumni Import Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["imported_count"] == 2

        print("5. Testing Bulk Achievements CSV Import...")
        achievements_csv = f"""title,description,position,year,student_email
Top Coder 2024,Winner of Coding Competition,winner,2024,bulk_student1_{ts}@example.com
Runner Up 2024,Runner up in ML Hackathon,runner_up,2024,bulk_student2_{ts}@example.com
"""
        files = {"file": ("achievements.csv", achievements_csv.encode("utf-8"), "text/csv")}
        res = await client.post("/api/admin/import/achievements", files=files, headers=admin_headers)
        print("Achievements Import Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["imported_count"] == 2

        print("6. Testing Bulk Certificate ZIP Upload...")
        # Create an event to attach certificates to
        event_res = await client.post("/api/events", json={
            "title": f"Bulk Cert Event {ts}",
            "description": "Event for testing bulk ZIP upload",
            "category": "past",
            "event_date": "2025-10-10T10:00:00Z",
            "event_year": 2025,
            "location": "Auditorium",
            "registration_deadline": "2025-10-09T10:00:00Z",
            "is_active": True
        }, headers=admin_headers)
        assert event_res.status_code == 201, event_res.text
        event_id = event_res.json()["id"]

        # Create zip in memory with matching student email
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr(f"bulk_student1_{ts}@example.com.pdf", b"%PDF-1.4 Mock PDF Content")
            zf.writestr("unmatched_student.pdf", b"%PDF-1.4 Mock PDF Content")
        zip_buf.seek(0)

        data = {
            "event_id": str(event_id),
            "certificate_type": "participation"
        }
        files = {
            "file": ("certificates.zip", zip_buf.getvalue(), "application/zip")
        }
        res = await client.post("/api/certificates/bulk-upload", data=data, files=files, headers=admin_headers)
        print("Bulk Cert ZIP Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["total_files"] == 2
        assert res.json()["matched_count"] == 1
        assert "unmatched_student.pdf" in res.json()["unmatched_files"]

        print("\nALL BULK IMPORT TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
