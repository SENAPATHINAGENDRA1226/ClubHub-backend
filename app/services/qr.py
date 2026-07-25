import hmac
import hashlib
import json
import os
import uuid
from typing import Tuple
import qrcode

from app.core.config import settings


def generate_registration_qr(
    registration_number: str,
    event_id: uuid.UUID,
    student_id: uuid.UUID,
) -> Tuple[str, str]:
    # 1. Create raw payload
    data_dict = {
        "reg_num": registration_number,
        "event_id": str(event_id),
        "student_id": str(student_id),
    }
    raw_json = json.dumps(data_dict, sort_keys=True)

    # 2. Sign with short HMAC-SHA256 signature
    signature = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        raw_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]

    payload_dict = {
        "data": data_dict,
        "sig": signature,
    }
    qr_code_data = json.dumps(payload_dict)

    # 3. Generate QR image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_code_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # 4. Save to media/qr/{registration_number}.png
    media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "qr")
    os.makedirs(media_dir, exist_ok=True)

    filename = f"{registration_number}.png"
    file_path = os.path.join(media_dir, filename)
    img.save(file_path)

    qr_code_image_url = f"/media/qr/{filename}"
    return qr_code_data, qr_code_image_url
