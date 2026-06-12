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
        context_data.append({
            "date": r.get("created_at", "").split("T")[0],
            "store": analysis.get("most_expensive_item"),
            "amount": analysis.get("total_amount"),
            "category": analysis.get("top_category"),
        })

    try:
        answer = ai_service.ask_ai_question(question, context_data)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 중 오류 발생: {str(e)}")
