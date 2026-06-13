# 2026-06-12 작업 내역

## 작업 목표
`000/` 폴더를 제거하고 바깥 프로젝트에 병합

---

## 변경 파일

### `backend/main.py`
- `BUDGET_FILE = "budget.json"` 상수 추가
- 앱 시작 시 `budget.json` 자동 생성 (기본값 1,000,000원)
- `GET /budget/` — 현재 예산 조회 API 추가
- `POST /budget/` — 예산 업데이트 API 추가
- `POST /ask-ai/` — 최근 20건 영수증 데이터를 컨텍스트로 활용한 AI 질문 응답 API 추가

### `frontend/app.py`
- `BUDGET_URL`, `ASK_AI_URL` 상수 추가
- `fetch_budget()`, `set_budget()` 함수 추가
- `update_home()` 반환값에 예산 값 포함 (4→5개로 확장)
- `chat_with_ai()` 함수 추가 — `/ask-ai/` 연동
- `export_to_csv()` 함수 추가 — 전체 내역 CSV 다운로드
- 홈 탭: 예산 입력 + 저장 버튼 + 진행률 바 추가
- **"AI 소비 비서" 탭 신규 추가** — 채팅 인터페이스
- 영수증 보관함 탭: CSV 내보내기 버튼 추가
- 모든 이벤트 핸들러를 새 반환 구조에 맞게 수정

---

## 삭제된 항목
- `000/` 폴더 전체 삭제 (하위 파일 포함)
  - `000/backend/main.py`
  - `000/backend/.env`
  - `000/frontend/app.py`
  - `000/run_all.py`
  - `000/내용 메모.txt`

### `run_all.py`
- print 문의 이모지 전체 제거
- **원인**: Windows 터미널 인코딩(cp949)이 이모지(UTF-8)를 처리하지 못해 `UnicodeEncodeError` 발생
- **증상**: `python run_all.py` 실행 시 즉시 크래시

---

## 트러블슈팅

### 프로젝트 시작 안 되는 문제
- **1차 원인**: `run_all.py` 이모지 → `UnicodeEncodeError` (cp949 인코딩 충돌) → `run_all.py` 수정으로 해결
- **2차 현상**: 프론트엔드 재시작 시 `OSError: port 7860 already in use`
  - 이전 실행 세션의 Python 프로세스가 남아있어 포트 충돌
  - 해결: `taskkill /F /IM python.exe` 후 재시작

---

## 병합 기준
- **베이스**: 바깥 버전 (이미지 전처리 cv2, UUID 파일명, 삭제 API, 수동 입력 API, Plotly 차트 유지)
- **이식**: `000/` 버전의 예산 관리 기능 + AI 채팅 기능 + CSV 내보내기
