import os
import json
import base64
import uuid
import cv2
import numpy as np
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from groq import Groq
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

load_dotenv()

app = FastAPI(title="Receipt AI Analysis API")

# 저장 폴더 및 데이터 파일 설정
UPLOAD_DIR = "uploads"
DATA_FILE = "receipts.json"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 이미지 파일을 서빙하기 위한 정적 파일 설정
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Warning: GROQ_API_KEY not found in environment variables.")

client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

PROMPT = """
영수증 이미지를 분석하여 다음 정보를 추출하고 JSON 형식으로 응답해줘.
JSON 구조:
{
  "items": [
    {"name": "품목명", "price": 가격(숫자), "quantity": 수량(숫자), "category": "카테고리"}
  ],
  "total_amount": 총액(숫자),
  "top_category": "가장 많이 지출한 카테고리",
  "most_expensive_item": "가장 비싼 품목명",
  "analysis": "소비 패턴 분석 요약 (한글로 2-3문장)"
}
반드시 순수 JSON 데이터만 반환해줘 (Markdown block ```json ... ``` 제외).
"""

def preprocess_image(image_bytes: bytes) -> bytes:
    # 1. 바이트를 numpy array로 변환 후 이미지 로드
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return image_bytes

    # 2. Grayscale 변환
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. 이진화 (Otsu's binarization)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 4. 모폴로지 팽창 (Dilation)
    # 글자 획을 조금 더 선명하게 만들기 위해 팽창 적용
    kernel = np.ones((2,2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)

    # 5. 다시 바이트로 변환
    _, encoded_img = cv2.imencode('.png', dilated)
    return encoded_img.tobytes()

def _is_rate_limit_error(exc: Exception) -> bool:
    return "429" in str(exc) or "rate_limit" in str(exc).lower() or "RateLimitError" in type(exc).__name__

@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_groq(image_bytes: bytes, mime_type: str) -> str:
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


@app.post("/analyze-receipt/")
async def analyze_receipt(file: UploadFile = File(...)):
    return await process_single_receipt(file)

@app.post("/analyze-receipts-bulk/")
async def analyze_receipts_bulk(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        try:
            res = await process_single_receipt(file)
            results.append(res)
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
    return results

async def process_single_receipt(file: UploadFile):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API Key가 설정되지 않았습니다.")

    try:
        # 파일 읽기
        original_bytes = await file.read()
        
        # --- 이미지 전처리 적용 (Binarization + Dilation) ---
        processed_bytes = preprocess_image(original_bytes)
        # ------------------------------------------------

        mime_type = "image/png" # 전처리 결과는 PNG

        # AI 분석 (전처리된 이미지 전달)
        text_response = _call_groq(processed_bytes, mime_type)

        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]

        analysis_data = json.loads(text_response.strip())

        # 파일 저장 (저장은 원본 보관)
        receipt_id = str(uuid.uuid4())
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        file_name = f"{receipt_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as f:
            f.write(original_bytes)

        receipt_entry = {
            "id": receipt_id,
            "filename": file.filename,
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

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/receipts/")
async def get_receipts():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/receipts/manual/")
async def add_manual_receipt(data: dict):
    """사용자가 직접 입력한 데이터를 저장합니다."""
    try:
        receipt_id = str(uuid.uuid4())
        receipt_entry = {
            "id": receipt_id,
            "filename": "manual_entry",
            "image_url": None, # 직접 입력은 이미지가 없음
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Receipt AI Analysis API is running (Groq)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
