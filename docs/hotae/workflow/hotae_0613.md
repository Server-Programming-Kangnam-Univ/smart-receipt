# 2026-06-13 작업 내역

## 작업 목표
세부기능명세서(`황호태_세부기능명세서.md`) 기반으로 AI 프롬프트 및 데이터 구조 전면 리팩토링 + 실행 환경 안정화

---

## 변경 파일

### `backend/services/ai_service.py`
- **PROMPT 전면 교체**: 기존 단순 프롬프트 → 명세서 기반 구조화된 프롬프트
- **출력 JSON 구조 변경**:
  - 기존: `items`, `total_amount`, `top_category`, `most_expensive_item`, `analysis`
  - 변경: `store_info`, `payment_info`, `items`, `quality_score`
- **카테고리 Enum 고정**: `식비, 교통비, 생필품, 문화생활, 전자기기, 기타` 6개로 제한
- **Hallucination 방지 강화**: 불확실 필드 `null`/`0` 강제, 순수 JSON만 반환 강력 지시
- **Few-shot 4케이스 추가**:
  - Example 1: 정상 영수증 (스타벅스 아메리카노 → 식비)
  - Example 2: 전자기기 특화 (엘레파츠 아두이노/케이블/컴퓨터 → 전자기기)
  - Example 3: 부분 훼손 (글자 훼손 항목 → `name: null`, 나머지 정상 반환)
  - Example 4: 완전 인식 실패 (풍경사진 등 → `is_readable: false`)

### `backend/services/receipt_service.py`
- `save_receipt_data()`: `is_readable: false`이면 이미지 파일 저장 스킵
- `add_manual_receipt()`: 수동 입력 데이터도 새 JSON 구조(`store_info`, `payment_info`, `items`, `quality_score`)로 저장

### `backend/api/receipt_route.py`
- `is_readable: false` → HTTP 400 + `"사진 인식이 실패했습니다. 또렷하거나, 선명한 영수증 사진을 올려주세요."` 반환
- `unrecognized_items_count > 0` → 응답에 `warning` 필드 추가 (`"해당 부분이 인식되지 않습니다. 직접 기입하거나 다시 찍어주세요."`)

### `backend/api/analysis_route.py`
- `context_data` 필드를 새 JSON 구조에서 올바르게 참조하도록 수정
  - `total_amount` → `payment_info.total_price`
  - `most_expensive_item` → `store_info.name`
  - `top_category` → `items` 배열에서 최다 빈도 카테고리 집계
  - AI에게 `items` 배열 전체 전달

### `run_all.py`
- 백엔드 스트림 스레드를 `Popen` **직후** 즉시 시작 (기존: 3초 대기 후 시작)
  - 파이프 버퍼가 꽉 차서 백엔드 프로세스가 블록되던 문제 해결
- 대기 시간 3초 → 5초 (uvicorn + watchfiles 재로더 기동 여유)
- 자식 프로세스 환경변수에 `PYTHONIOENCODING=utf-8` 주입
- 스트림 스레드 `UnicodeEncodeError` 예외 처리 추가

### `frontend/app.py`
- **구 JSON 구조 참조 전면 수정**: `_get_amount()`, `_get_category()`, `_get_store()`, `_get_date()` 헬퍼 함수 도입
- `update_storage()`: `image_url: null`인 수동입력 항목 갤러리에서 스킵
- `bulk_upload()`: Gradio 버전 호환성 처리 (`f.name` vs 문자열 경로)
- `chat_with_ai()`: Gradio 6 호환 메시지 형식으로 변경 (튜플 → 딕셔너리)
- **`gr.Tabs` → 버튼 기반 페이지 전환으로 전면 교체**
  - Gradio 6.13.0에서 `gr.Tabs` 클릭이 동작하지 않는 문제 우회
  - 각 페이지를 `gr.Column(visible=True/False)`로 구성
  - 상단 버튼 클릭 시 `gr.update(visible=...)` 토글 방식으로 페이지 전환
  - 탭 진입 시 해당 페이지 데이터 자동 갱신

---

## 트러블슈팅

### 백엔드 실행 실패 (`run_all.py`)
- **원인 1**: 파이프 버퍼 블록 — 스트림 스레드를 3초 후에 시작해 그 사이 백엔드 stdout이 버퍼를 채워 프로세스 블록 → `poll()`이 종료로 오판
- **원인 2**: conda Python(`anaconda3/python.exe`)에 `opencv-python` 미설치 — `ModuleNotFoundError: No module named 'cv2'`
  - 해결: `C:\Users\USER\anaconda3\python.exe -m pip install opencv-python`

### 프론트엔드 탭 미동작
- **원인**: Gradio 6.13.0에서 `gr.Tabs` 클릭 이벤트가 동작하지 않음
  - 추가 원인: `gr.Label`에 금액(큰 정수) 전달 시 JS 렌더링 오류로 전체 인터랙션 마비
- **해결**: `gr.Tabs` 완전 제거, 버튼 + `gr.Column` visible 토글 방식으로 우회

### 포트 충돌
- `run_all.py` 재실행 시 이전 Python 프로세스가 7860/8000 포트 점유
- 해결: `Get-Process python | Stop-Process -Force`

---

## Swagger 테스트
- 백엔드 실행 후 `http://localhost:8000/docs` 접속
- 영수증 단건 분석: `POST /analyze-receipt/`
- 영수증 일괄 분석: `POST /analyze-receipts-bulk/`
