import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 현재 디렉터리를 sys.path에 추가하여 패키지 임포트 가능하게 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from services import receipt_service, budget_service
from api import receipt_route, budget_route, analysis_route

load_dotenv()

app = FastAPI(title="Receipt AI Analysis API")

# 저장 폴더 및 데이터 파일 초기화
receipt_service.init_receipt_storage()
budget_service.init_budget_storage()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 이미지 파일을 서빙하기 위한 정적 파일 설정
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
app.include_router(receipt_route.router)
app.include_router(budget_route.router)
app.include_router(analysis_route.router)

@app.get("/")
def read_root():
    return {"message": "Receipt AI Analysis API is running (Layered Architecture)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
