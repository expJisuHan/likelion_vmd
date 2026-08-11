# VMD Backend (FastAPI)

기존 `app/server.py` (표준 라이브러리 `http.server` 단일 파일, ~1800줄)를 FastAPI 기반으로
재구성했습니다. 라우트 경로와 요청/응답 JSON 형태는 그대로 유지했기 때문에
`frontend/app.js`는 수정하지 않아도 됩니다.

## 무엇이 바뀌었나

| 이전 (`app/server.py`) | 이후 (`backend/`) |
|---|---|
| `BaseHTTPRequestHandler` + `ThreadingHTTPServer` | FastAPI + Uvicorn |
| 요청 body를 직접 `json.loads` | Pydantic 모델(`schemas.py`)로 자동 검증 |
| 모든 로직이 파일 1개에 순서 없이 혼재 | 역할별 모듈로 분리 (아래 구조 참고) |
| `os.environ.get(...)` 을 코드 여러 곳에서 직접 호출 | `config.py`의 `Settings` 하나로 통합, `.env` 지원 |
| 에러 시 매 핸들러마다 try/except로 직접 응답 작성 | 전역 예외 핸들러(`main.py`)가 일괄 처리 |

## 폴더 구조

```text
backend/
├─ .env.example        # 복사해서 backend/.env 로 사용
├─ requirements.txt
├─ run.py              # `python run.py` 로 서버 실행
└─ app/
   ├─ config.py         # 환경변수 (LMSTUDIO_*, HOST, PORT, CORS_ORIGINS ...)
   ├─ main.py            # FastAPI 라우트 (/api/health, /api/analyze, /api/batch-analyze, /api/download, 정적 파일)
   ├─ schemas.py         # 요청 바디 Pydantic 모델
   ├─ vmd_core.py        # VMD 존/스키마/프롬프트, LM Studio 호출, 결과 정규화
   ├─ excel_export.py    # Excel(.xlsx) 저장 (openpyxl, 없으면 순수 파이썬 fallback)
   ├─ pdf_export.py      # PDF 저장 (reportlab)
   └─ utils.py           # 공용 헬퍼 (파일명, 이미지 EXIF/썸네일, 에러 메시지 등)
```

## 실행 방법

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # 필요하면 LM Studio 주소/모델명 수정
python run.py
```

기본값으로 `http://127.0.0.1:8000` 에서 뜨고, 프론트엔드(`../frontend/index.html`)를 그대로 서빙합니다.
개발 중 코드 변경 시 자동 재시작을 원하면 `.env`에서 `RELOAD=true` (기본값)를 유지하세요.

## API (변경 없음)

- `GET /api/health` — LM Studio 연결 상태 확인
- `POST /api/analyze` — `{ images: [{name, dataUrl}], options: {...} }` → 단일 분석 결과
- `POST /api/batch-analyze` — 동일한 바디, 이미지별로 개별 분석 후 Excel/PDF 일괄 저장
- `GET /api/download?file=outputs/excel/xxx.xlsx` — 결과 파일 다운로드

요청/응답 필드는 기존 서버와 동일합니다 (`zoneMode`, `storeType`, `tone`, `criteria`,
`focusKeywords`, `extraCriteria`, `modelName`, `temperature`, `maxTokens`).

## 환경변수

`backend/.env.example` 참고. 주요 항목:

- `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `LMSTUDIO_FALLBACK_MODELS`, `LMSTUDIO_TIMEOUT_SECONDS`
- `HOST`, `PORT`, `RELOAD`
- `CORS_ORIGINS` — 프론트를 다른 origin(예: Vite dev server)에서 띄울 때 사용
- `FRONTEND_DIR`, `OUTPUT_DIR` — 기본값은 프로젝트 루트 기준 `frontend/`, `outputs/`

## 남은 작업 / 다음 단계 제안

- 기존 `app/server.py`, `app/static/`는 이번 변경으로 대체되므로, 검증이 끝나면
  루트의 `app/` 폴더를 삭제하고 `requirements.txt`(루트)를 지워도 됩니다.
- LM Studio가 켜져 있지 않을 때 `/api/health`를 프론트에서 주기적으로 호출해
  "LM Studio 연결 안 됨" 배너를 보여주면 CHECKLIST.md의 "LM Studio 연결 확인 구현" 항목과 더 잘 맞습니다.
- `analyze_images`가 동기(sync) 함수라 요청이 몰리면 워커 스레드가 막힐 수 있습니다.
  트래픽이 늘면 `httpx.AsyncClient` + `async def` 라우트로 바꾸는 것을 검토하세요 (지금 단계에서는 불필요).
