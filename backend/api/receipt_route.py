from fastapi import APIRouter, UploadFile, File, HTTPException
from services import receipt_service, ai_service

router = APIRouter()

@router.post("/analyze-receipt/")
async def analyze_receipt(file: UploadFile = File(...)):
    return await process_single_receipt(file)

@router.post("/analyze-receipts-bulk/")
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
    try:
        original_bytes = await file.read()
        processed_bytes = receipt_service.preprocess_image(original_bytes)
        
        # AI 분석
        analysis_data = ai_service.call_groq_vision(processed_bytes, "image/png")

        # 데이터 저장
        receipt_entry = receipt_service.save_receipt_data(original_bytes, file.filename, analysis_data)
        return receipt_entry

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/receipts/")
async def get_receipts():
    return receipt_service.get_all_receipts()

@router.delete("/receipts/{receipt_id}")
async def delete_receipt(receipt_id: str):
    success, message = receipt_service.delete_receipt_by_id(receipt_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"message": f"영수증 {receipt_id} 삭제 완료", "id": receipt_id}

@router.post("/receipts/manual/")
async def add_manual_receipt(data: dict):
    try:
        return receipt_service.add_manual_receipt(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
