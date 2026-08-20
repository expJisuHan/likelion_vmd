"""POST /api/consumer/photo-insight, POST /api/consumer/ask — 소비자 페이지 전용 엔드포인트.

photo-insight: 사진 한 장을 clothing/space로 분류한 뒤, clothing이면
consumer_prompt.py로 진열 사실(품목/색상/개수/사이즈/가격/위치)을, space면
accessibility_prompt.py 공간 안전 평가를 반환합니다. 두 플로우 모두 이미지를
직접 보고 사실을 추출합니다(재서술 2단계 구조 아님). ask: catalog.py 기반
제품 질문 응답(recommendation_prompt.py)입니다.

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
from ..services.consumer_prompt import (
    consumer_json_schema,
    consumer_system_prompt,
    consumer_user_text,
    parse_consumer_content,
    render_consumer_narration,
    render_consumer_sections,
)
from ..services.demo_mode import build_demo_response, is_demo_image, run_demo_delay
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


def _run_clothing_flow(resized_data_url: str) -> dict[str, Any]:
    """예전에는 매장 직원용 VMD 분석(services/analysis.py)을 먼저 돌려 그 결과
    텍스트만 재서술했지만, 그 2단계 구조 자체가 문제였습니다 — 재서술 단계가
    이미지를 못 보니 1차 분석이 애초에 안 뽑은 정보(구체적 색상·개수·사이즈·가격·
    위치)는 절대 나올 수 없고, 대신 "다양하다"류의 빈 문장만 반복됐습니다(실측
    확인 — 사용자가 직접 지적).

    이미지를 직접 보고 자유 문장으로 사실을 서술하게 바꿔봤지만, "여러 품목·
    구역이 보이면 하나만 골라라"는 지시를 아무리 강하게 줘도 이 모델은 선반·
    품목마다 번호를 매겨 전부 나열하는 경향을 반복했습니다(실측 확인, 3차례
    시도 모두 재발). 몇 문단을 쓸지 자체가 모델의 자유였기 때문입니다. 그래서
    accessibility_prompt.py와 같은 원리로 JSON 스키마로 필드 개수를 고정해서
    "하나만 고르기"를 구조적으로 강제하고, 최종 문장은 여기서 코드로 조립합니다.

    이후 사용자 스펙에 맞춰 상품 정보 5필드에 접근성 항목(이동 안전/구역 구분/
    안내 정보) 7필드를 더해 12필드로 확장했습니다 — accessibility_prompt.py의
    space 플로우와 카테고리가 겹치지만, 이 플로우는 사진에 상품이 함께 보일 때
    상품 정보까지 한 번에 주는 것이 목적이라 별도로 유지합니다."""
    payload = {
        "model": settings.nim_model,
        "messages": [
            {"role": "system", "content": consumer_system_prompt()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": consumer_user_text()},
                    {"type": "image_url", "image_url": {"url": resized_data_url}},
                ],
            },
        ],
        "temperature": 0.3,
        "max_tokens": 700,
        "frequency_penalty": 0.6,
        "presence_penalty": 0.3,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "consumer_item_result", "strict": True, "schema": consumer_json_schema()},
        },
    }
    raw = _nim_request_resilient(payload, timeout=90)
    content = raw["choices"][0]["message"]["content"]
    fields = parse_consumer_content(content)
    # items: 프론트가 [상품 정보]/[이동 정보]를 시각적으로 구분해서 보여주기 위한
    # 구조화된 목록(accessibility_prompt.py의 consumer_items()와 같은 패턴).
    # narration: TTS 등 순수 텍스트 한 덩어리가 필요할 때를 위해 그대로 유지.
    return {"items": render_consumer_sections(fields), "narration": render_consumer_narration(fields)}


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
        "max_tokens": 1500,
        "frequency_penalty": 0.6,
        "presence_penalty": 0.3,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "accessibility_result", "strict": True, "schema": accessibility_json_schema()},
        },
    }
    raw = _nim_request_resilient(payload, timeout=90)
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

    # 시연용 샘플 사진이면 NIM을 아예 호출하지 않고 미리 써둔 응답을 돌려줍니다
    # (services/demo_mode.py 참고 — NIM 응답 시간·형식 편차가 라이브 데모
    # 리스크라 판단).
    if is_demo_image(data_url):
        run_demo_delay()
        return build_demo_response()

    resized = resize_image_data_url_for_model(data_url, settings.nim_image_max_dimension, settings.nim_image_max_bytes)
    try:
        if _floor_visible(resized):
            data = _run_space_flow(resized)
            return {"ok": True, "type": "space", **data}
        data = _run_clothing_flow(resized)
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
