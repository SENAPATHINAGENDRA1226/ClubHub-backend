import asyncio
import io
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
            "email": "admin@csmd-dlides-club.com",
            "password": "admin123"
        })
        assert res.status_code == 200, res.text
        admin_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

        print("2. Student Signup & Onboarding...")
        res = await client.post("/api/auth/student/signup", json={
            "name": "Phase 4 Student",
            "email": f"student_p4_{ts}@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res.status_code in (200, 201), res.text
        student_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

        res = await client.post("/api/onboarding/student", json={
            "branch": "CSE",
            "section": "A",
            "phone_number": "9876543210",
            "academic_year": "3rd Year"
        }, headers=student_headers)
        assert res.status_code == 200, res.text

        print("3. Testing Committees & Members CRUD...")
        res = await client.post("/api/committees", json={
            "name": f"Robotics Club {ts}",
            "category": "student",
            "sub_category": "coding",
            "description": "Building autonomous robots"
        }, headers=admin_headers)
        print("Committee Create Status:", res.status_code)
        assert res.status_code == 201, res.text
        committee_id = res.json()["id"]

        res = await client.get("/api/committees?category=student&sub_category=coding")
        assert res.status_code == 200, res.text
        assert any(c["id"] == committee_id for c in res.json())

        res = await client.post(f"/api/committees/{committee_id}/members", json={
            "full_name": "Robotics Lead",
            "email": f"lead_{ts}@example.com",
            "role_title": "President",
            "order_index": 1
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("4. Testing Alumni CRUD...")
        res = await client.post("/api/alumni", json={
            "full_name": "Senior Alumni",
            "graduation_year": 2021,
            "branch": "CSE",
            "current_company": "Amazon"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        res = await client.get("/api/alumni?branch=CSE")
        assert res.status_code == 200, res.text

        print("5. Testing Achievements CRUD...")
        res = await client.post("/api/achievements", json={
            "title": f"Robotics Cup {ts}",
            "description": "1st place in National Competition",
            "position": "winner",
            "year": 2026
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("6. Testing Resources CRUD...")
        res = await client.post("/api/resources", json={
            "title": "DSA Handbook",
            "description": "Data structures guide",
            "resource_url": "https://example.com/dsa.pdf",
            "category": "DSA"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("7. Testing Opportunities CRUD...")
        res = await client.post("/api/opportunities", json={
            "title": "SDE Intern",
            "company_name": "Google",
            "description": "Summer 2026 internship",
            "apply_url": "https://careers.google.com",
            "opportunity_type": "internship"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("8. Testing Media File Upload & Item CRUD...")
        files = {"file": ("test_cover.jpg", b"fake_jpeg_header_data", "image/jpeg")}
        res = await client.post("/api/media/upload", files=files, headers=admin_headers)
        assert res.status_code == 201, res.text
        upload_url = res.json()["file_url"]
        assert upload_url.startswith("/media/uploads/")

        res = await client.post("/api/media", json={
            "title": f"Annual Magazine {ts}",
            "type": "magazine",
            "file_url": upload_url,
            "published_date": "2026-07-20T10:00:00Z"
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        print("9. Testing Grievances Flow...")
        res = await client.post("/api/grievances", json={
            "subject": "Lab Equipment Request",
            "message": "We need additional GPUs for ML workshop"
        }, headers=student_headers)
        assert res.status_code == 201, res.text
        grievance_id = res.json()["id"]

        res = await client.get("/api/grievances", headers=admin_headers)
        assert res.status_code == 200, res.text

        res = await client.put(f"/api/grievances/{grievance_id}", json={
            "status": "resolved",
            "admin_response": "Approved. GPUs allocated."
        }, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "resolved"

        print("10. Testing Contact Message Submission & Read...")
        res = await client.post("/api/contact", json={
            "name": "Visitor Student",
            "email": f"visitor_{ts}@example.com",
            "subject": "Inquiry about Membership",
            "message": "How do I join the coding club?"
        })
        assert res.status_code == 201, res.text
        contact_id = res.json()["id"]

        res = await client.get("/api/contact?is_read=false", headers=admin_headers)
        assert res.status_code == 200, res.text

        res = await client.put(f"/api/contact/{contact_id}/read", headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["is_read"] is True

        print("11. Testing Student & Admin Dashboards (Recharts data)...")
        res = await client.get("/api/dashboard/student", headers=student_headers)
        assert res.status_code == 200, res.text
        s_dash = res.json()
        assert "total_events" in s_dash and "active_members_count" in s_dash

        res = await client.get("/api/dashboard/admin", headers=admin_headers)
        assert res.status_code == 200, res.text
        a_dash = res.json()
        assert isinstance(a_dash["registrations_over_time"], list)
        assert isinstance(a_dash["most_popular_events"], list)

        print("12. Testing Admin Manage Users (Committee Scoped Account Creation)...")
        res = await client.post("/api/users", json={
            "email": f"committee_lead_{ts}@csmd-dlides-club.com",
            "password": "CommitteePass123",
            "role": "committee",
            "full_name": "Committee Admin Lead",
            "committee_ids": [committee_id]
        }, headers=admin_headers)
        print("Admin Create User Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 201, res.text
        u_data = res.json()
        assert committee_id in u_data["committee_ids"]

        print("\nALL PHASE 4 TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
