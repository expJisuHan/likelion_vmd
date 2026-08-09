"""FastAPI 앱.

기존 server.py의 BaseHTTPRequestHandler(VmdHandler)를 대체합니다.
라우트 매핑은 그대로 유지해서 프론트엔드(app.js) 수정 없이 붙습니다.

  GET  /                     -> frontend/index.html
  GET  /{static file}        -> frontend/ 정적 파일 서빙 (app.js, styles.css ...)
  GET  /api/health           -> 앱/LM Studio 연결 상태
  GET  /api/download?file=.. -> outputs/ 하위 결과 파일 다운로드
  POST /api/analyze          -> 단일 분석 (이미지 여러 장 -> 결과 1건)
  POST /api/batch-analyze    -> 이미지별 개별 분석 + Excel/PDF 일괄 저장
"""

import time
import traceback
import urllib.parse
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .excel_export import save_excel
from .pdf_export import save_pdf
from .schemas import AnalyzeRequest, BatchAnalyzeRequest
from .utils import friendly_error_message, safe_file_name
from .vmd_core import analyze_images, check_lmstudio, lmstudio_model_candidates, make_record, normalize_zone, record_zone

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
    print(f"LM Studio endpoint: {settings.lmstudio_base_url}")
    print(f"Default model: {settings.lmstudio_model}")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"ok": False, "error": friendly_error_message(exc), "detail": str(exc)})


# --- Health ---


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    ok, message = check_lmstudio()
    return {
        "ok": True,
        "lmstudio": ok,
        "message": message,
        "baseUrl": settings.lmstudio_base_url,
        "defaultModel": settings.lmstudio_model,
        "fallbackModels": lmstudio_model_candidates(settings.lmstudio_model)[1:],
    }


# --- Analyze ---


def _error_result(options_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_selected_zone": normalize_zone(options_dict.get("zoneMode")),
        "ai_detected_zone": "UNKNOWN",
        "zone_confidence": 0,
        "store_type_assumption": options_dict.get("storeType", "UNKNOWN"),
        "photo_quality": {
            "score": 0,
            "is_blurry": False,
            "is_tilted": False,
            "has_background_interference": False,
            "needs_retake": False,
            "comment": "",
        },
        "mannequin": {"exists": False, "type": "unknown", "has_head": False, "comment": ""},
        "obstacles": [],
        "scores": {
            "layout": 0,
            "presentation_mood": 0,
            "brand_fit": 0,
            "color_harmony": 0,
            "cleanliness": 0,
            "customer_attention": 0,
            "season_concept_fit": 0,
        },
        "total_score": 0,
        "grade": "분석 실패",
        "positive_points": [],
        "critical_issues": [],
        "improvement_suggestions": [],
        "final_summary": "",
    }


@app.post("/api/analyze")
def api_analyze(payload: AnalyzeRequest) -> Dict[str, Any]:
    images = [image.model_dump() for image in payload.images]
    options = payload.options.to_dict()
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required.")

    started = time.time()
    try:
        analysis = analyze_images(images, options)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=friendly_error_message(exc)) from exc
    elapsed_seconds = time.time() - started

    image_names = ", ".join(safe_file_name(img.get("name", "image")) for img in images)
    image_data_url = images[0].get("dataUrl", "") if images else ""
    record = make_record(image_names, analysis, image_data_url=image_data_url, elapsed_seconds=elapsed_seconds)
    result_prefix = f"{record_zone(record).lower()}_results"
    excel_path = save_excel([record], prefix=result_prefix)
    pdf_path = save_pdf([record], prefix=result_prefix)

    return {
        "ok": True,
        "result": analysis["result"],
        "jsonPath": record["json_path"],
        "excelPath": excel_path,
        "downloadUrl": f"/api/download?file={urllib.parse.quote(excel_path)}",
        "pdfPath": pdf_path,
        "pdfDownloadUrl": f"/api/download?file={urllib.parse.quote(pdf_path)}",
        "elapsedSeconds": round(elapsed_seconds, 2),
    }


@app.post("/api/batch-analyze")
def api_batch_analyze(payload: BatchAnalyzeRequest) -> Dict[str, Any]:
    images = [image.model_dump() for image in payload.images]
    options = payload.options.to_dict()
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required.")

    records = []
    batch_results = []
    started = time.time()
    for image in images:
        name = safe_file_name(image.get("name", "image"))
        original_name = image.get("name", "image")
        try:
            image_started = time.time()
            analysis = analyze_images([image], options)
            record = make_record(
                name,
                analysis,
                image_data_url=image.get("dataUrl", ""),
                elapsed_seconds=time.time() - image_started,
            )
            records.append(record)
            batch_results.append(
                {
                    "imageName": original_name,
                    "result": record["result"],
                    "jsonPath": record["json_path"],
                    "status": record["status"],
                }
            )
        except Exception as exc:
            friendly = friendly_error_message(exc)
            error_result = {"result": _error_result(options), "raw": {"error": friendly, "original_error": str(exc)}}
            record = make_record(
                name,
                error_result,
                status="error",
                error=friendly,
                image_data_url=image.get("dataUrl", ""),
                elapsed_seconds=None,
            )
            records.append(record)
            batch_results.append(
                {
                    "imageName": original_name,
                    "result": record["result"],
                    "jsonPath": record["json_path"],
                    "status": record["status"],
                    "error": record["error"],
                }
            )

    zone = normalize_zone(options.get("zoneMode"))
    result_prefix = f"{zone.lower()}_results"
    excel_path = save_excel(records, prefix=result_prefix)
    pdf_path = save_pdf(records, prefix=result_prefix)

    return {
        "ok": True,
        "count": len(records),
        "results": batch_results,
        "excelPath": excel_path,
        "downloadUrl": f"/api/download?file={urllib.parse.quote(excel_path)}",
        "pdfPath": pdf_path,
        "pdfDownloadUrl": f"/api/download?file={urllib.parse.quote(pdf_path)}",
        "elapsedSeconds": round(time.time() - started, 2),
    }


# --- Download ---


@app.get("/api/download")
def api_download(file: str) -> FileResponse:
    target = (settings.project_root / file).resolve()
    try:
        target.relative_to(settings.output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target, filename=target.name)


# --- Static frontend (index.html, app.js, styles.css ...) ---
# /api/* 라우트가 위에서 먼저 매칭되므로, 아래 static mount는 그 외 모든 경로를 처리합니다.

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html", media_type="text/html; charset=utf-8")


@app.get("/{file_path:path}")
def serve_static(file_path: str) -> FileResponse:
    target = (settings.frontend_dir / file_path).resolve()
    try:
        target.relative_to(settings.frontend_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    suffix = target.suffix.lower()
    return FileResponse(target, media_type=_CONTENT_TYPES.get(suffix))
