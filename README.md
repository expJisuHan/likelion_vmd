# VMD Insight

매장 사진을 기반으로 VMD 평가와 소비자용 매장 안내를 제공하는 AI 웹 애플리케이션입니다. 관리자 페이지에서는 VP/PP/IP 존별 Visual Merchandising 평가, 점수, 개선 코멘트, Excel/PDF 리포트를 생성하고, 소비자 페이지에서는 사진 속 의류/공간을 분석해 상품 안내 또는 이동 안전 정보를 제공합니다.

현재 구현은 `FastAPI` 백엔드와 `React + Vite` 프론트엔드로 구성되어 있으며, 비전 언어 모델 호출은 NVIDIA NIM의 OpenAI-compatible API를 사용합니다.

## 주요 기능

- 관리자 페이지: 매장 사진 업로드, 카메라 촬영, VP/PP/IP 존 선택
- VMD 평가: 총점, 등급, 항목별 점수, 사진 품질, 마네킹, 방해물, 개선 제안
- 일괄 분석: 여러 이미지를 이미지별로 분석하고 Excel/PDF 결과 생성
- 소비자 페이지: 사진 기반 의류 안내 또는 공간 접근성 안내
- 상품 질의: 사진에서 탐지한 품목과 MCM 카탈로그 기반 제품 추천
- 접근성 UI: 글자 크기 조절, 고대비 모드, 키보드 포커스, 음성 읽기
- 운영 보호: 이미지 용량 제한, 요청 수 제한, 선택적 `X-App-Key` 보호, 분석 캐시

## 실행 방법

### 1. 백엔드 설정

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`backend/.env`에 NVIDIA NIM API 키를 입력합니다.

```text
NIM_API_KEY=your_api_key_here
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NIM_MODEL=meta/llama-3.2-11b-vision-instruct
```

백엔드를 실행합니다.

```powershell
python run.py
```

기본 주소는 `http://127.0.0.1:8000`입니다. 이 주소에서 빌드된 프론트엔드 정적 파일도 함께 서빙합니다.

### 2. 프론트엔드 개발 서버

프론트엔드를 별도 개발 서버로 실행하려면 다음을 사용합니다.

```powershell
cd frontend
npm install
npm run dev
```

프론트엔드를 별도 포트에서 실행할 경우 `backend/.env`의 `CORS_ORIGINS`에 해당 주소를 추가하세요.

## API 요약

- `GET /api/health`: 백엔드와 NIM 연결 상태 확인
- `POST /api/analyze`: 여러 사진을 하나의 장면으로 묶어 VMD 분석
- `POST /api/batch-analyze`: 사진별 독립 VMD 분석 후 Excel/PDF 생성
- `POST /api/consumer/photo-insight`: 소비자용 사진 안내 생성
- `POST /api/consumer/ask`: 카탈로그 기반 제품 질문 답변
- `POST /api/consumer/catalog-products`: 탐지 품목에 맞는 제품 카드 데이터 반환
- `GET /api/download?file=...`: 생성된 Excel/PDF/JSON 다운로드

## 폴더 구조

```text
.
├─ README.md
├─ PRD.md
├─ TECHNICAL_DESIGN.md
├─ CHECKLIST.md
├─ backend/
│  ├─ run.py
│  ├─ requirements.txt
│  ├─ .env.example
│  └─ app/
│     ├─ main.py
│     ├─ config.py
│     ├─ schemas.py
│     ├─ api/
│     ├─ services/
│     └─ export/
├─ frontend/
│  ├─ package.json
│  ├─ index.html
│  └─ src/
├─ data/
│  └─ samples/
└─ outputs/
   ├─ json/
   ├─ excel/
   └─ pdf/
```

## 현재 상태

MVP 기능은 FastAPI/React 구조로 구현되어 있습니다. 다음 검증의 초점은 실제 매장 샘플 사진으로 VMD 평가 품질, 소비자 안내 정확도, NIM 응답 안정성, Excel/PDF 리포트 품질을 확인하는 것입니다.
