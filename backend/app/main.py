"""FastAPI 앱 진입점.

라우트는 기능별로 api/ 하위 모듈에 분리되어 있습니다:
  api/health.py    -> GET /api/health
  api/analyze.py   -> POST /api/analyze, POST /api/batch-analyze
  api/download.py  -> GET /api/download
  api/static.py    -> GET /, GET /{file_path} (frontend/ 정적 파일 서빙)

도메인 로직은 services/(존 기준, 프롬프트, NVIDIA NIM 클라이언트, 분석 오케스트레이션,
레코드 변환)로, 결과 파일 생성은 export/(Excel, PDF)로 분리되어 있습니다.

주의: api/static.py의 `/{file_path:path}` 라우트는 다른 모든 경로와 매칭될 수 있으므로
아래 include_router 순서에서 반드시 마지막에 등록해야 합니다.
"""

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import analyze, consumer, download, health, static
from .config import settings
from .utils import friendly_error_message

app = FastAPI(title="AX R&D VMD Evaluation API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    settings.ensure_dirs()
    print(f"VMD FastAPI backend running at http://{settings.host}:{settings.port}")
    print(f"NIM endpoint: {settings.nim_base_url}")
    print(f"Default model: {settings.nim_model}")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 원본 예외 메시지/스택트레이스는 서버 로그에만 남깁니다. 클라이언트에는
    # 내부 구현 정보(파일 경로, 라이브러리 에러 문구 등)가 노출되지 않도록
    # friendly_error_message로 정제된 메시지만 돌려주고, DEBUG=true일 때만 원본을 곁들입니다.
    print(f"Unhandled exception on {request.method} {request.url.path}:")
    traceback.print_exc()
    content: dict[str, object] = {"ok": False, "error": friendly_error_message(exc)}
    if settings.debug:
        content["detail"] = str(exc)
    return JSONResponse(status_code=500, content=content)


# api/* 라우트를 먼저 등록하고, 정적 파일 서빙(static)은 반드시 마지막에 등록합니다.
app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(consumer.router)
app.include_router(download.router)
app.include_router(static.router)
