import os
import base64
import json
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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
def call_groq_vision(image_bytes: bytes, mime_type: str) -> dict:
    if not client:
        raise Exception("Groq API Key가 설정되지 않았습니다.")
        
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
    text_response = response.choices[0].message.content.strip()
    return parse_json_response(text_response)

def ask_ai_question(question: str, context_data: list) -> str:
    if not client:
        raise Exception("Groq API Key가 설정되지 않았습니다.")

    chat_prompt = f"""
당신은 스마트 소비 분석 비서입니다. 사용자의 영수증 내역 데이터를 바탕으로 질문에 친절하고 정확하게 답해주세요.

[소비 데이터 (최근 20건)]:
{json.dumps(context_data, ensure_ascii=False)}

[사용자 질문]:
{question}

답변은 한국어로 2-3문장 내외로 간결하게 해주세요. 데이터에 없는 내용은 유추하지 말고 모른다고 답하세요.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": chat_prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def parse_json_response(text: str) -> dict:
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())
