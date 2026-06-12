import os
import json
import uuid
import cv2
import numpy as np
from datetime import datetime

UPLOAD_DIR = "uploads"
DATA_FILE = "receipts.json"

def init_receipt_storage():
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def preprocess_image(image_bytes: bytes) -> bytes:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return image_bytes

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    _, encoded_img = cv2.imencode('.png', dilated)
    return encoded_img.tobytes()

def save_receipt_data(original_bytes: bytes, filename: str, analysis_data: dict):
    receipt_id = str(uuid.uuid4())
    file_ext = filename.split(".")[-1] if "." in filename else "jpg"
    file_name = f"{receipt_id}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    with open(file_path, "wb") as f:
        f.write(original_bytes)

    receipt_entry = {
        "id": receipt_id,
        "filename": filename,
        "image_url": f"/uploads/{file_name}",
        "created_at": datetime.now().isoformat(),
        "analysis": analysis_data
    }

    with open(DATA_FILE, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append(receipt_entry)
        f.seek(0)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.truncate()

    return receipt_entry

def add_manual_receipt(data: dict):
    receipt_id = str(uuid.uuid4())
    receipt_entry = {
        "id": receipt_id,
        "filename": "manual_entry",
        "image_url": None,
        "created_at": data.get("date", datetime.now().isoformat()),
        "analysis": {
            "items": [],
            "total_amount": int(data.get("amount", 0)),
            "top_category": data.get("category", "기타"),
            "most_expensive_item": data.get("merchant", "-"),
            "analysis": f"직접 입력 내역: {data.get('status', '')}"
        },
        "status": data.get("status", "")
    }

    with open(DATA_FILE, "r+", encoding="utf-8") as f:
        receipts = json.load(f)
        receipts.append(receipt_entry)
        f.seek(0)
        json.dump(receipts, f, ensure_ascii=False, indent=2)
        f.truncate()
    
    return receipt_entry

def get_all_receipts():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def delete_receipt_by_id(receipt_id: str):
    if not os.path.exists(DATA_FILE):
        return False, "데이터 파일이 존재하지 않습니다."

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        receipts = json.load(f)

    target_receipt = next((r for r in receipts if r["id"] == receipt_id), None)
    if not target_receipt:
        return False, "해당 ID의 영수증을 찾을 수 없습니다."

    image_url = target_receipt.get("image_url")
    if image_url:
        relative_path = image_url.lstrip("/")
        full_path = os.path.join(os.getcwd(), relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    new_receipts = [r for r in receipts if r["id"] != receipt_id]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(new_receipts, f, ensure_ascii=False, indent=2)

    return True, "삭제 완료"
