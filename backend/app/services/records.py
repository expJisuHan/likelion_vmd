"""분석 레코드 <-> Excel/PDF 행 변환, JSON 저장. export/의 excel_export·pdf_export가 공용으로 사용합니다."""

from __future__ import annotations

import json
from typing import Any

from ..config import settings
from ..utils import format_elapsed, list_to_lines, safe_file_name, timestamp
from .zones import criteria_for_zone, normalize_zone

EXCEL_COMMON_HEADERS = [
    "사진",
    "지정 구역",
    "모델 감지 구역",
    "총점",
    "사진 품질 점수",
    "사진 품질 코멘트",
    "영역별 평가",
    "최종 요약 답변",
    "감지된 문제점",
    "개선 방향",
    "전체 개선 요약",
    "분석 시간",
]


def excel_headers_for_zone(zone: str | None) -> list[str]:
    headers = list(EXCEL_COMMON_HEADERS)
    for criterion in criteria_for_zone(zone):
        headers.extend([f"{criterion} 점수", f"{criterion} 근거", f"{criterion} 문제점", f"{criterion} 개선안"])
    return headers


def excel_column_widths_for_zone(zone: str | None) -> dict[int, float]:
    if normalize_zone(zone) == "VP":
        values = [18, 14, 14, 14, 14, 22, 14, 22, 14, 42, 42, 14, 42, 42, 22, 22, 22, 22, 22, 14, 36, 36, 36, 22, 14, 36, 36, 36, 22, 14, 36, 36]
    else:
        values = [18, 14, 14, 22, 14, 42, 42, 42, 42, 42, 42, 14]
        for _criterion in criteria_for_zone(zone):
            values.extend([14, 36, 36, 36])
    return {index: width for index, width in enumerate(values, start=1)}


def record_zone(record: dict[str, Any]) -> str:
    result = record.get("result", {})
    return normalize_zone(result.get("user_selected_zone"))


def criteria_evaluation_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evaluations = result.get("criteria_evaluations", [])
    if not isinstance(evaluations, list):
        return {}
    return {
        str(item.get("criterion", "")).strip(): item
        for item in evaluations
        if isinstance(item, dict) and str(item.get("criterion", "")).strip()
    }


def format_elapsed_export(seconds: float | int | None) -> str:
    return format_elapsed(seconds)


def result_to_row(record: dict[str, Any], zone: str | None = None) -> list[Any]:
    result = record.get("result", {})
    photo = result.get("photo_quality", {})
    selected_zone = normalize_zone(zone or result.get("user_selected_zone"))
    row = [
        "",
        result.get("user_selected_zone", ""),
        result.get("ai_detected_zone", ""),
        result.get("total_score", ""),
        photo.get("score", ""),
        photo.get("comment", ""),
        result.get("zone_evaluation_summary", ""),
        result.get("priority_action_summary", result.get("final_summary", "")),
        list_to_lines(result.get("detected_issues", result.get("critical_issues", []))),
        list_to_lines(result.get("improvement_actions", result.get("improvement_suggestions", []))),
        result.get("overall_improvement_summary", list_to_lines(result.get("improvement_suggestions", []))),
        format_elapsed_export(record.get("elapsed_seconds")),
    ]
    by_criterion = criteria_evaluation_map(result)
    for criterion in criteria_for_zone(selected_zone):
        item = by_criterion.get(criterion, {})
        row.extend([item.get("score"), item.get("evidence", ""), item.get("issue", ""), item.get("suggestion", "")])
    return row


def save_json(name: str, payload: dict[str, Any]) -> str:
    settings.ensure_dirs()
    path = settings.json_dir / f"{safe_file_name(name)}_{timestamp()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(settings.project_root))


def make_record(
    image_names: str,
    analysis: dict[str, Any],
    status: str = "success",
    error: str = "",
    image_data_url: str = "",
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    json_path = save_json(safe_file_name(image_names[:80]), analysis)
    return {
        "image_names": image_names,
        "image_data_url": image_data_url,
        "result": analysis.get("result", {}),
        "raw": analysis.get("raw", {}),
        "json_path": json_path,
        "status": status,
        "error": error,
        "elapsed_seconds": elapsed_seconds,
    }
