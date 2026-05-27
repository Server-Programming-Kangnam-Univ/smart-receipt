import os
import json
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

load_dotenv()

app = FastAPI(title="Receipt AI Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        analysis_data = json.loads(text_response.strip())
        return analysis_data

    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        if _is_rate_limit_error(e):
            raise HTTPException(
                status_code=429,
                detail="Groq API 요청 한도에 도달했습니다. 잠시 후 다시 시도해주세요. (무료: 30회/분, 1,000회/일)"
            )
        raise HTTPException(status_code=500, detail=f"영수증 분석 중 오류가 발생했습니다: {error_msg}")


@app.get("/")
def read_root():
    return {"message": "Receipt AI Analysis API is running (Groq)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
