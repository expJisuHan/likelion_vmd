"""POST /api/consumer/photo-insight, POST /api/consumer/ask — 소비자 페이지 전용 엔드포인트.

photo-insight: 사진 한 장을 clothing/space로 분류한 뒤, clothing이면 VMD 진단 +
consumer_prompt.py 감각적 서술을, space면 accessibility_prompt.py 공간 안전 평가를
반환합니다. ask: catalog.py 기반 제품 질문 응답(recommendation_prompt.py)입니다.

세 프롬프트 모두 이 파일에서 오케스트레이션합니다 — services/*.py는 프롬프트 텍스트와
판정 로직만 담당하고 실제 NIM 호출은 라우트 계층에 모아둔 기존 구조(analyze.py가
services/analysis.py를 호출하는 것과 같은 분리)를 따릅니다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..schemas import ConsumerAskRequest, ConsumerPhotoRequest
from ..services.accessibility_prompt import (
    accessibility_json_schema,
    accessibility_system_prompt,
    accessibility_user_text,
    consumer_items,
    parse_accessibility_content,
    render_consumer_text,
)
from ..services.analysis import analyze_images
from ..services.consumer_prompt import consumer_system_prompt, consumer_user_text, has_sufficient_content
from ..services.nim_client import is_retriable_nim_error, nim_model_candidates, nim_request
from ..services.photo_classifier import classifier_json_schema, classifier_system_prompt, classifier_user_text
from ..services.recommendation_prompt import (
    absent_category_response,
    build_candidates,
    find_absent_category,
    recommendation_system_prompt,
    recommendation_user_text,
)
from ..services.request_guard import enforce_app_key, enforce_payload_limits, enforce_rate_limit
from ..utils import friendly_error_message, resize_image_data_url_for_model

router = APIRouter(dependencies=[Depends(enforce_app_key), Depends(enforce_rate_limit)])

_FLOOR_VISIBLE_RE = re.compile(r'"?floor_visible"?\s*[:=]?\s*(true|false)', re.IGNORECASE)


def _as_text(content: Any) -> str:
    """message.content는 보통 문자열이지만, 가끔 [{"type": "text", "text": "..."}]
    형태의 콘텐츠 블록 배열로 오는 경우를 실측으로 확인했습니다. 어느 형태든 순수
    텍스트로 정규화합니다."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [block.get("text", "") for block in content if isinstance(block, dict)]
        return "".join(parts)
    return str(content)


_ATTEMPTS_PER_MODEL = 2


def _nim_request_resilient(payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """analyze.py의 analyze_images는 모델 후보/재시도를 자체적으로 처리하지만, 이 파일의
    단발성 호출(플로어 분류, 감각적 서술, 접근성 평가)은 그런 보호막이 없어서 NIM의 흔한
    일시적 실패(타임아웃/429/5xx) 하나에도 곧바로 502로 죽는 문제가 실측으로 확인됐습니다.
    같은 모델을 여러 번, 그리고 설정된 폴백 모델이 있으면 그것도 재시도합니다."""
    last_error: Exception | None = None
    for candidate_model in nim_model_candidates(payload["model"]):
        candidate_payload = {**payload, "model": candidate_model}
        for _ in range(_ATTEMPTS_PER_MODEL):
            try:
                return nim_request(candidate_payload, timeout=timeout)
            except RuntimeError as exc:
                last_error = exc
                if not is_retriable_nim_error(str(exc)):
                    raise
    raise last_error  # type: ignore[misc]


def _floor_visible(resized_data_url: str) -> bool:
    """사진에 바닥이 보이는지만 판단합니다("space냐 clothing이냐" 추상 분류보다
    안정적이라는 걸 실측으로 확인했습니다 — photo_classifier.py 모듈 docstring 참고)."""
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": classifier_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": classifier_user_text()},
                    {"type": "image_url", "image_url": {"url": resized_data_url}},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 50,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "floor_check", "strict": True, "schema": classifier_json_schema()},
        },
    }
    raw = _nim_request_resilient(payload, timeout=30)
    content = _as_text(raw["choices"][0]["message"]["content"])
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and isinstance(parsed.get("floor_visible"), bool):
            return parsed["floor_visible"]
        # 스키마를 무시하고 {"floor_visible": ...}가 아니라 true/false 리터럴
        # 하나만 돌려주는 경우가 실측으로 확인됐습니다(json.loads("false") -> False).
        if isinstance(parsed, bool):
            return parsed
    except json.JSONDecodeError:
        pass
    stripped = content.strip().strip('"').strip().lower()
    if stripped in {"true", "false"}:
        return stripped == "true"
    match = _FLOOR_VISIBLE_RE.search(content)
    # 판단이 애매하면 의류(제품 설명) 쪽이 더 안전한 기본값입니다 — 공간 정보로
    # 잘못 안내하는 것보다, 제품 설명으로 안내하는 쪽이 사실과 다를 위험이 적습니다.
    return match.group(1).lower() == "true" if match else False


def _run_clothing_flow(image: dict[str, Any]) -> dict[str, Any]:
    options = {
        "zoneMode": "IP",
        "storeType": "UNKNOWN",
        "tone": "SOFT_CRITICAL",
        "criteria": [],
        "focusKeywords": [],
        "extraCriteria": "",
    }
    analysis = analyze_images([image], options)
    result = analysis["result"]
    if not has_sufficient_content(result):
        return {"narration": "이 사진에서는 자세한 특징을 확인하기 어려웠어요. 조금 더 가까이서 다시 찍어봐 주시겠어요?"}
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": consumer_system_prompt()},
            {"role": "user", "content": consumer_user_text(result)},
        ],
        "temperature": 0.4,
        "max_tokens": 400,
    }
    raw = _nim_request_resilient(payload, timeout=60)
    return {"narration": raw["choices"][0]["message"]["content"]}


def _run_space_flow(resized_data_url: str) -> dict[str, Any]:
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": accessibility_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": accessibility_user_text()},
                    {"type": "image_url", "image_url": {"url": resized_data_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 900,
        "frequency_penalty": 0.6,
        "presence_penalty": 0.3,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "accessibility_result", "strict": True, "schema": accessibility_json_schema()},
        },
    }
    raw = _nim_request_resilient(payload, timeout=60)
    content = raw["choices"][0]["message"]["content"]
    parsed = parse_accessibility_content(content)
    # items: 프론트가 항목별로 시각적으로 구분해서 보여주기 위한 구조화된 목록.
    # text: TTS 등 순수 텍스트 한 덩어리가 필요할 때를 위해 그대로 유지.
    return {"items": consumer_items(parsed), "text": render_consumer_text(parsed)}


@router.post("/api/consumer/photo-insight")
def api_consumer_photo_insight(payload: ConsumerPhotoRequest) -> dict[str, Any]:
    image = payload.image.model_dump()
    enforce_payload_limits([image])
    data_url = image.get("dataUrl", "")
    if not data_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="이미지 데이터가 올바르지 않습니다.")
    resized = resize_image_data_url_for_model(data_url, settings.nim_image_max_dimension, settings.nim_image_max_bytes)
    try:
        if _floor_visible(resized):
            data = _run_space_flow(resized)
            return {"ok": True, "type": "space", **data}
        data = _run_clothing_flow(image)
        return {"ok": True, "type": "clothing", **data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=friendly_error_message(exc)) from exc


@router.post("/api/consumer/ask")
def api_consumer_ask(payload: ConsumerAskRequest) -> dict[str, Any]:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해 주세요.")

    absent = find_absent_category(question)
    if absent:
        return {"ok": True, "answer": absent_category_response(absent)}

    candidates = build_candidates(question)
    user_text = recommendation_user_text(question, candidates)
    request_payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": recommendation_system_prompt()},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.3,
    }
    try:
        raw = _nim_request_resilient(request_payload, timeout=60)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=friendly_error_message(exc)) from exc
    return {"ok": True, "answer": raw["choices"][0]["message"]["content"]}
