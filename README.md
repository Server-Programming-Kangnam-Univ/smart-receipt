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
