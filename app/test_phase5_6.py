import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.ws.manager import ws_manager


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

        print("2. Student Signup & Onboarding...")
        res = await client.post("/api/auth/student/signup", json={
            "name": "Phase5 Verification Student",
            "email": f"student_p5_{ts}@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res.status_code in (200, 201), res.text
        student_token = res.json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}

        res = await client.post("/api/onboarding/student", json={
            "branch": "CSM",
            "section": "A",
            "phone_number": "9988776655",
            "academic_year": "2nd Year"
        }, headers=student_headers)
        assert res.status_code == 200, res.text

        print("3. Admin Creating Event & Student Registering...")
        now_utc = datetime.now(timezone.utc)
        res = await client.post("/api/events", json={
            "title": f"Verification Fest {ts}",
            "description": "Live check-in verification test event",
            "category": "current",
            "event_date": (now_utc + timedelta(days=2)).isoformat(),
            "event_year": 2026,
            "location": "Main Auditorium",
            "registration_deadline": (now_utc + timedelta(days=1)).isoformat(),
            "is_active": True
        }, headers=admin_headers)
        assert res.status_code == 201, res.text
        event_id = res.json()["id"]

        res = await client.post("/api/registrations", json={"event_id": event_id}, headers=student_headers)
        assert res.status_code == 201, res.text
        reg_data = res.json()
        registration_id = reg_data["id"]
        valid_qr_payload = reg_data["qr_code_data"]
        reg_num = reg_data["registration_number"]

        print("4. Scanning Valid QR Code (POST /api/verify/scan)...")
        res = await client.post("/api/verify/scan", json={"qr_payload": valid_qr_payload}, headers=admin_headers)
        print("Valid QR Scan Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        preview = res.json()
        assert preview["already_verified"] is False
        assert preview["student_name"] == "Phase5 Verification Student"

        print("5. Scanning Tampered QR Code (Expect INVALID_SIGNATURE 400)...")
        tampered_payload = valid_qr_payload.replace('"sig": "', '"sig": "invalid_sig_')
        res = await client.post("/api/verify/scan", json={"qr_payload": tampered_payload}, headers=admin_headers)
        print("Tampered Scan Status:", res.status_code, "Detail:", res.json()["detail"])
        assert res.status_code == 400, res.text
        assert "INVALID_SIGNATURE" in res.json()["detail"]

        print("6. Confirming Verification (POST /api/verify/confirm)...")
        res = await client.post("/api/verify/confirm", json={"registration_id": registration_id}, headers=admin_headers)
        print("Confirm Status:", res.status_code)
        assert res.status_code == 200, res.text
        assert res.json()["already_verified"] is True

        print("7. Re-scanning Same QR (Shows Already Verified)...")
        res = await client.post("/api/verify/scan", json={"qr_payload": valid_qr_payload}, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json()["already_verified"] is True
        assert res.json()["verified_by_name"] is not None

        print("8. Checking Live Verification Stats (GET /api/verify/stats/{event_id})...")
        res = await client.get(f"/api/verify/stats/{event_id}", headers=admin_headers)
        print("Stats Status:", res.status_code, "Body:", res.json())
        assert res.status_code == 200, res.text
        stats = res.json()
        assert stats["total_registered"] == 1
        assert stats["total_verified"] == 1
        assert stats["verification_rate"] == 100.0

        print("9. Manual Registrant Search (GET /api/verify/manual-search)...")
        res = await client.get(f"/api/verify/manual-search?event_id={event_id}&query={reg_num}", headers=admin_headers)
        assert res.status_code == 200, res.text
        assert len(res.json()) == 1

        print("10. Testing WebSocket Manager Broadcasting...")
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        await ws_manager.connect(mock_ws, user_id="test_admin", role="admin")

        # Trigger REST mutation
        res = await client.post("/api/events", json={
            "title": f"WS Test Event {ts}",
            "description": "Event created while socket listening",
            "category": "upcoming",
            "event_date": (now_utc + timedelta(days=5)).isoformat(),
            "event_year": 2026,
            "location": "Seminar Hall",
            "registration_deadline": (now_utc + timedelta(days=4)).isoformat(),
            "is_active": True
        }, headers=admin_headers)
        assert res.status_code == 201, res.text

        # Verify mock_ws received sent message
        assert mock_ws.send_json.called
        sent_args = mock_ws.send_json.call_args[0][0]
        print("WebSocket Manager Received Broadcast:", sent_args)
        assert sent_args["channel"] == "events"
        assert sent_args["event_type"] == "event.created"

        await ws_manager.disconnect(mock_ws)

        print("\nALL PHASE 5 & 6 TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
