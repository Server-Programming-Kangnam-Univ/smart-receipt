import os
import json
import base64
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from groq import Groq
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

load_dotenv()

app = FastAPI(title="Receipt AI Analysis API")

DATA_DIR = "data"
IMAGE_DIR = os.path.join(DATA_DIR, "images")
DATA_FILE = os.path.join(DATA_DIR, "receipts.json")
BUDGET_FILE = os.path.join(DATA_DIR, "budget.json")

def ensure_dirs():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "w", encoding="utf-8") as f:
            json.dump({"budget": 1000000}, f)

ensure_dirs()

# 이미지 파일 서빙을 위한 설정
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_receipts():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_receipt(data, image_bytes=None, content_type=None):
    receipts = load_receipts()
    
    # 이미지 저장
    if image_bytes:
        timestamp = int(time.time() * 1000)
        ext = content_type.split('/')[-1] if content_type else "png"
        filename = f"receipt_{timestamp}.{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        data["image_url"] = f"http://localhost:8000/images/{filename}"

    receipts.insert(0, data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(receipts, f, ensure_ascii=False, indent=2)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Warning: GROQ_API_KEY not found in environment variables.")

client = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

PROMPT = """
영수증 이미지를 분석하여 다음 정보를 추출하고 JSON 형식으로 응답해줘.
JSON 구조:
{
  "date": "YYYY-MM-DD (영수증에 적힌 날짜, 없으면 오늘 날짜)",
  "store_name": "가맹점명 또는 상호명",
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
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API Key가 설정되지 않았습니다.")

    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"

        text_response = _call_groq(image_bytes, mime_type)

        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]

        text_response = text_response.strip()

        if not text_response:
            raise HTTPException(
                status_code=422,
                detail="AI가 영수증을 인식하지 못했습니다. 더 선명한 이미지를 사용해주세요."
            )

        try:
            analysis_data = json.loads(text_response)
            save_receipt(analysis_data, image_bytes, mime_type) # 이미지와 함께 저장
        except json.JSONDecodeError:
            print(f"AI 응답 (JSON 파싱 실패): {text_response}")
            raise HTTPException(
                status_code=422,
                detail="영수증 인식에 실패했습니다. 이미지가 영수증인지, 글씨가 선명한지 확인해주세요."
            )

        return analysis_data

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        if _is_rate_limit_error(e):
            raise HTTPException(
                status_code=429,
                detail="Groq API 요청 한도에 도달했습니다. 잠시 후 다시 시도해주세요. (무료: 30회/분, 1,000회/일)"
            )
        raise HTTPException(status_code=500, detail=f"영수증 분석 중 오류가 발생했습니다: {error_msg}")


@app.get("/history/")
def get_history():
    return load_receipts()

@app.delete("/history/")
def clear_history():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    # 이미지 폴더도 비우기
    for f in os.listdir(IMAGE_DIR):
        os.remove(os.path.join(IMAGE_DIR, f))
    return {"message": "히스토리와 이미지가 초기화되었습니다."}

@app.get("/budget/")
def get_budget():
    with open(BUDGET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/budget/")
def update_budget(payload: dict):
    budget = payload.get("budget", 1000000)
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump({"budget": budget}, f)
    return {"message": "예산이 업데이트되었습니다.", "budget": budget}

@app.post("/ask-ai/")
async def ask_ai(payload: dict):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API Key가 설정되지 않았습니다.")
    
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    receipts = load_receipts()
    # 최근 20개의 영수증 요약 정보를 컨텍스트로 제공
    context_data = []
    for r in receipts[:20]:
        context_data.append({
            "date": r.get("date"),
            "store": r.get("store_name"),
            "amount": r.get("total_amount"),
            "category": r.get("top_category")
        })
    
    chat_prompt = f"""
    당신은 스마트 소비 분석 비서입니다. 사용자의 영수증 내역 데이터를 바탕으로 질문에 친절하고 정확하게 답해주세요.
    
    [소비 데이터 (최근 20건)]:
    {json.dumps(context_data, ensure_ascii=False)}
    
    [사용자 질문]:
    {question}
    
    답변은 한국어로 2-3문장 내외로 간결하게 해주세요. 데이터에 없는 내용은 유추하지 말고 모른다고 답하세요.
    """

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": chat_prompt}],
            temperature=0.7,
        )
        return {"answer": response.choices[0].message.content.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 중 오류 발생: {str(e)}")


@app.get("/")
def read_root():
    return {"message": "Receipt AI Analysis API is running (Groq)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
