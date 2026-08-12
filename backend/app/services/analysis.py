"""이미지 분석 오케스트레이션: 프롬프트 구성 -> NVIDIA NIM 호출(모델/스키마 fallback) -> 결과 정규화."""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings
from ..utils import list_to_lines, resize_image_data_url_for_model
from .analysis_cache import build_cache_key, get_cached_result, store_result
from .nim_client import is_retriable_nim_error, nim_model_candidates, nim_request
from .prompt import build_user_text, schema_instruction, system_prompt, vmd_json_schema
from .zones import criteria_for_zone, grade_from_score, normalize_zone


def apply_defaults(result: dict[str, Any], user_zone: str) -> dict[str, Any]:
    result.setdefault("user_selected_zone", user_zone)
    result.setdefault("ai_detected_zone", "UNKNOWN")
    result.setdefault("zone_confidence", 0)
    result.setdefault("store_type_assumption", "UNKNOWN")
    result.setdefault(
        "photo_quality",
        {
            "score": 0,
            "is_blurry": False,
            "is_tilted": False,
            "has_background_interference": False,
            "needs_retake": False,
            "comment": "",
        },
    )
    result.setdefault("mannequin", {"exists": False, "type": "none", "has_head": False, "comment": ""})
    result.setdefault("obstacles", [])
    result.setdefault(
        "scores",
        {
            "layout": 0,
            "presentation_mood": 0,
            "brand_fit": 0,
            "color_harmony": 0,
            "cleanliness": 0,
            "customer_attention": 0,
            "season_concept_fit": 0,
        },
    )
    result.setdefault("total_score", 0)
    result.setdefault("grade", grade_from_score(result.get("total_score")))
    result.setdefault("positive_points", [])
    result.setdefault("critical_issues", [])
    result.setdefault("improvement_suggestions", [])
    result.setdefault("final_summary", "")
    result.setdefault("zone_evaluation_summary", result.get("final_summary", ""))
    result.setdefault("priority_action_summary", result.get("final_summary", ""))
    result.setdefault("detected_issues", result.get("critical_issues", []))
    result.setdefault("improvement_actions", result.get("improvement_suggestions", []))
    result.setdefault("overall_improvement_summary", list_to_lines(result.get("improvement_suggestions", [])))
    criteria = result.get("criteria_evaluations")
    if not isinstance(criteria, list):
        criteria = []
    by_name = {str(item.get("criterion", "")).strip(): item for item in criteria if isinstance(item, dict)}
    normalized_criteria = []
    for criterion in criteria_for_zone(user_zone):
        item = by_name.get(criterion, {})
        normalized_criteria.append(
            {
                "criterion": criterion,
                "score": item.get("score"),
                "evidence": item.get("evidence", ""),
                "issue": item.get("issue", ""),
                "suggestion": item.get("suggestion", ""),
            }
        )
    result["criteria_evaluations"] = normalized_criteria
    return result


def image_content_items(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for image in images:
        data_url = image.get("dataUrl", "")
        if not data_url.startswith("data:image/"):
            raise ValueError(f"Invalid image data for {image.get('name', 'image')}")
        data_url = resize_image_data_url_for_model(
            data_url, settings.nim_image_max_dimension, settings.nim_image_max_bytes
        )
        items.append({"type": "image_url", "image_url": {"url": data_url}})
    return items


def parse_model_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def analyze_images(images: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    if not images:
        raise ValueError("At least one image is required.")

    cache_key = build_cache_key(images, options)
    cached = get_cached_result(cache_key)
    if cached is not None:
        return cached

    requested_model = (options.get("modelName") or settings.nim_model).strip()
    zone = normalize_zone(options.get("zoneMode"))
    content = [{"type": "text", "text": build_user_text(options, len(images)) + "\n\n" + schema_instruction()}]
    content.extend(image_content_items(images))

    base_payload = {
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": content},
        ],
        "temperature": float(options.get("temperature", 0.2) or 0.2),
        "max_tokens": int(options.get("maxTokens", 2200) or 2200),
    }

    errors: list[str] = []
    raw = None
    parsed = None
    model = requested_model
    for candidate_model in nim_model_candidates(requested_model):
        request_variants = [
            {
                **base_payload,
                "model": candidate_model,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "vmd_evaluation_result", "strict": True, "schema": vmd_json_schema()},
                },
            },
            {**base_payload, "model": candidate_model},
        ]
        for payload in request_variants:
            try:
                candidate_raw = nim_request(payload)
            except RuntimeError as exc:
                message = str(exc)
                errors.append(f"{candidate_model}: {message}")
                if "HTTP 400" not in message and not is_retriable_nim_error(message):
                    raise
                continue
            try:
                message = candidate_raw["choices"][0]["message"]
                candidate_parsed = parse_model_content(message.get("content", ""))
            except Exception as exc:
                errors.append(f"{candidate_model}: invalid JSON response: {exc}")
                continue
            raw = candidate_raw
            parsed = candidate_parsed
            model = candidate_model
            break
        if raw is not None:
            break
    if raw is None:
        raise RuntimeError("NIM request failed after model and JSON fallbacks: " + " | ".join(errors))

    parsed = apply_defaults(parsed, zone)
    parsed["user_selected_zone"] = zone
    parsed["grade"] = parsed.get("grade") or grade_from_score(parsed.get("total_score"))
    result = {"result": parsed, "raw": raw, "model": model}
    store_result(cache_key, result)
    return result
