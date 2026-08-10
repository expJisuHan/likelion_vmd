"""POST /api/analyze, POST /api/batch-analyze — VMD 이미지 분석."""

import time
import urllib.parse
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..export.excel_export import save_excel
from ..export.pdf_export import save_pdf
from ..schemas import AnalyzeRequest, BatchAnalyzeRequest
from ..services.analysis import analyze_images
from ..services.records import make_record, record_zone
from ..services.zones import normalize_zone
from ..utils import friendly_error_message, safe_file_name

router = APIRouter()


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


@router.post("/api/analyze")
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


@router.post("/api/batch-analyze")
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
