import asyncio
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
    student_email = f"janestudent_{ts}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("1. Testing Health Check...")
        res = await client.get("/api/health")
        assert res.status_code == 200, res.text

        print("2. Testing Student Login with Non-Existent Email (ACCOUNT_NOT_FOUND)...")
        res = await client.post("/api/auth/student/login", json={
            "email": f"nonexistent_{ts}@example.com",
            "password": "somepassword123"
        })
        print("Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 404, res.text
        assert res.json()["detail"] == "ACCOUNT_NOT_FOUND", res.text

        print(f"3. Testing Student Signup ({student_email})...")
        signup_payload = {
            "name": "Jane Student",
            "email": student_email,
            "password": "Password123",
            "confirm_password": "Password123"
        }
        res = await client.post("/api/auth/student/signup", json=signup_payload)
        print("Signup Status:", res.status_code)
        assert res.status_code in (200, 201), res.text
        tokens = res.json()
        student_access_token = tokens["access_token"]
        student_refresh_token = tokens["refresh_token"]
        assert tokens["role"] == "student"
        assert tokens["onboarding_completed"] is False

        print("4. Testing Admin Login...")
        res = await client.post("/api/auth/admin/login", json={
            "email": "admin@csmd-dlides-club.com",
            "password": "admin123"
        })
        print("Admin Login Status:", res.status_code)
        assert res.status_code == 200, res.text
        admin_tokens = res.json()
        assert admin_tokens["role"] == "admin"

        print("5. Testing GET /api/auth/me (Student)...")
        headers = {"Authorization": f"Bearer {student_access_token}"}
        res = await client.get("/api/auth/me", headers=headers)
        print("Me Status:", res.status_code, "Me Body:", res.json())
        assert res.status_code == 200, res.text

        print("6. Testing POST /api/onboarding/student...")
        onboarding_payload = {
            "branch": "CSE",
            "section": "A",
            "phone_number": "+919876543210",
            "academic_year": "3rd Year",
            "cgpa": 8.9,
            "linkedin_url": "https://linkedin.com/in/janestudent",
            "github_url": "https://github.com/janestudent"
        }
        res = await client.post("/api/onboarding/student", json=onboarding_payload, headers=headers)
        print("Onboarding Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        assert res.json()["onboarding_completed"] is True

        print("7. Testing Re-submitting Onboarding without force (expect 400)...")
        res = await client.post("/api/onboarding/student", json=onboarding_payload, headers=headers)
        print("Duplicate Onboarding Status:", res.status_code)
        assert res.status_code == 400, res.text

        print("8. Testing Re-submitting Onboarding with force=true...")
        res = await client.post("/api/onboarding/student?force=true", json=onboarding_payload, headers=headers)
        print("Forced Onboarding Status:", res.status_code)
        assert res.status_code == 200, res.text

        print("9. Testing Token Refresh...")
        res = await client.post("/api/auth/refresh", json={"refresh_token": student_refresh_token})
        print("Refresh Status:", res.status_code)
        assert res.status_code == 200, res.text
        new_tokens = res.json()
        new_refresh_token = new_tokens["refresh_token"]

        print("10. Testing Logout (revokes refresh token)...")
        res = await client.post("/api/auth/logout", json={"refresh_token": new_refresh_token})
        print("Logout Status:", res.status_code)
        assert res.status_code == 200, res.text

        print("11. Testing Refreshing with Revoked Token (expect 401)...")
        res = await client.post("/api/auth/refresh", json={"refresh_token": new_refresh_token})
        print("Revoked Refresh Status:", res.status_code)
        assert res.status_code == 401, res.text

        print("\nALL PHASE 2 TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
