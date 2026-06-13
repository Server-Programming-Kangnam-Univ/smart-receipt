from fastapi import APIRouter, HTTPException
from services import ai_service, receipt_service

router = APIRouter()

@router.post("/ask-ai/")
async def ask_ai(payload: dict):
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    receipts = receipt_service.get_all_receipts()

    context_data = []
    for r in receipts[:20]:
        analysis = r.get("analysis", {})
        store_info = analysis.get("store_info", {})
        payment_info = analysis.get("payment_info", {})
        items = analysis.get("items", [])

        categories = [i.get("category") for i in items if i.get("category")]
        top_category = max(set(categories), key=categories.count) if categories else None

        context_data.append({
            "date": payment_info.get("date") or r.get("created_at", "").split("T")[0],
            "store": store_info.get("name"),
            "amount": payment_info.get("total_price", 0),
            "currency": payment_info.get("currency", "KRW"),
            "category": top_category,
            "items": [{"name": i.get("name"), "price": i.get("price"), "category": i.get("category")} for i in items],
        })

    try:
        answer = ai_service.ask_ai_question(question, context_data)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 중 오류 발생: {str(e)}")
