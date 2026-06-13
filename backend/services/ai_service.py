import os
import base64
import json
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

CATEGORIES = ["식비", "교통비", "생필품", "문화생활", "전자기기", "기타"]

PROMPT = """You are a receipt OCR parser. Analyze the receipt image and return structured data in JSON format.

[OUTPUT FORMAT]
Return ONLY a raw JSON object. No markdown code blocks (```json), no explanatory text, no sentences. Any violation causes a system error.

[JSON STRUCTURE]
{
  "store_info": {
    "name": "store name or null",
    "address": "address or null",
    "phone": "phone number or null"
  },
  "payment_info": {
    "date": "YYYY-MM-DD or null",
    "time": "HH:MM or null",
    "total_price": integer or 0,
    "currency": "KRW",
    "tax": integer or 0,
    "discount": integer or 0
  },
  "items": [
    {
      "name": "item name or null",
      "price": integer or 0,
      "quantity": integer or 1,
      "category": "one of: 식비, 교통비, 생필품, 문화생활, 전자기기, 기타"
    }
  ],
  "quality_score": {
    "is_readable": true or false,
    "unrecognized_items_count": integer
  }
}

[RULES]
1. category MUST be one of: 식비, 교통비, 생필품, 문화생활, 전자기기, 기타
2. date format: YYYY-MM-DD. time format: HH:MM. amounts: integer (no commas).
3. If a field is unclear or missing, use null (strings) or 0 (numbers). NEVER guess or infer.
4. If the image is not a receipt (photo, drawing, memo, etc.), set is_readable: false and return minimal JSON.
5. For partially damaged items, set that item's name or price to null. Return all other valid items normally.

[EXAMPLES]

Example 1 - Normal receipt:
Input: "스타벅스 강남점 / 2024-06-04 14:30 / 아이스 아메리카노 x2 4500원 / 합계 9000원"
Output:
{"store_info":{"name":"스타벅스 강남점","address":null,"phone":null},"payment_info":{"date":"2024-06-04","time":"14:30","total_price":9000,"currency":"KRW","tax":818,"discount":0},"items":[{"name":"아이스 아메리카노","price":4500,"quantity":2,"category":"식비"}],"quality_score":{"is_readable":true,"unrecognized_items_count":0}}

Example 2 - Electronics (engineering items):
Input: "엘레파츠 / 아두이노 키트 35000원, 점퍼 케이블 2500원, 조립형 컴퓨터 1200000원 / 합계 1237500원"
Output:
{"store_info":{"name":"엘레파츠","address":null,"phone":null},"payment_info":{"date":null,"time":null,"total_price":1237500,"currency":"KRW","tax":0,"discount":0},"items":[{"name":"아두이노 키트","price":35000,"quantity":1,"category":"전자기기"},{"name":"점퍼 케이블","price":2500,"quantity":1,"category":"전자기기"},{"name":"조립형 컴퓨터","price":1200000,"quantity":1,"category":"전자기기"}],"quality_score":{"is_readable":true,"unrecognized_items_count":0}}

Example 3 - Partial damage:
Input: "이마트 / [글자 훼손] 1000원 / 콜라 1500원"
Output:
{"store_info":{"name":"이마트","address":null,"phone":null},"payment_info":{"date":null,"time":null,"total_price":0,"currency":"KRW","tax":0,"discount":0},"items":[{"name":null,"price":1000,"quantity":1,"category":"생필품"},{"name":"콜라","price":1500,"quantity":1,"category":"식비"}],"quality_score":{"is_readable":true,"unrecognized_items_count":1}}

Example 4 - Unreadable image:
Input: landscape photo / drawing / random memo with no receipt content
Output:
{"store_info":{"name":null,"address":null,"phone":null},"payment_info":{"date":null,"time":null,"total_price":0,"currency":"KRW","tax":0,"discount":0},"items":[],"quality_score":{"is_readable":false,"unrecognized_items_count":0}}

Now analyze the receipt image provided.
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
