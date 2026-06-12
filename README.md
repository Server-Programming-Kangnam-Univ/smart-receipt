# 영수증 AI 소비 분석 서비스 (Receipt AI Analysis Service)

이 프로젝트는 FastAPI와 Groq API를 사용하여 영수증 이미지를 분석하고 소비 패턴을 요약해주는 서비스입니다.

## 사전 준비

1. [Groq Console](https://console.groq.com/keys)에서 Groq API 키를 발급받으세요.
2. 각 폴더의 의존성을 설치합니다.

## 실행 방법

### 1. API 키 설정

`backend/.env` 파일을 열고 아래 키를 입력하세요.

```
GROQ_API_KEY=발급받은_Groq_키
```

### 2. 통합 실행 (권장)

루트 폴더에서 다음 명령어 하나로 백엔드와 프론트엔드를 동시에 실행할 수 있습니다.

```bash
# 의존성 설치 (최초 1회)
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# 통합 실행
python run_all.py
```

### 3. 개별 실행 (직접 실행 시)

... (기존 내용 유지)

## 주요 기능

- **구매 품목 인식**: 이미지에서 상품명, 가격, 수량 추출
- **카테고리 분류**: 각 품목을 자동으로 카테고리화
- **소비 분석**: AI가 지출 패턴을 분석하여 요약 제공

---

## GitHub 사용법

### 처음 한 번만 — 파일 받기

```bash
git clone https://github.com/Server-Programming-Kangnam-Univ/smart-receipt.git
```

### 작업 시작할 때 — 최신 파일 받기

```bash
git pull origin main
```

### 작업 끝났을 때 — 파일 올리기

```bash
git add .
git commit -m "feat : 작업 내용 한 줄 설명"
git push origin main
```

### 커밋 메시지 타입

| 타입    | 설명      |
| ------- | --------- |
| `feat`  | 기능 추가 |
| `fix`   | 버그 수정 |
| `docs`  | 문서 수정 |
| `chore` | 기타      |

---

## 🏗️ System Architecture (Backend)

본 프로젝트는 유지보수와 확장이 용이하도록 **계층형 아키텍처(Layered Architecture)**를 채택하여 리팩토링되었습니다.

- **API Layer (`backend/api/`)**: 클라이언트의 HTTP 요청을 접수하고 응답을 반환하는 라우팅 계층 (Router)
- **Service Layer (`backend/services/`)**: 비즈니스 로직(AI 분석, 이미지 처리, 데이터 저장 등)을 수행하는 핵심 계층 (Logic)
- **Model Layer (`backend/models/`)**: 데이터의 구조와 규격을 정의하는 계층 (Data Structure)

이러한 구조적 분리를 통해 코드의 가독성을 높이고, 향후 기능 확장 및 데이터베이스 연동 시 유연하게 대처할 수 있도록 설계되었습니다.
