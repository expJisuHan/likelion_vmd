"""NVIDIA NIM(OpenAI 호환 /v1/chat/completions) 클라이언트.

다른 OpenAI 호환 API로 바꿀 때는 이 파일만 교체하면 되도록
NIM 통신 로직을 한 곳에 모아뒀습니다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import settings


def nim_request(payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.nim_base_url}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.nim_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or settings.nim_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body.strip() or exc.reason
        raise RuntimeError(f"NIM HTTP {exc.code}: {detail}") from exc


def nim_model_candidates(requested_model: str) -> list[str]:
    candidates: list[str] = []
    for model in [requested_model, *settings.nim_fallback_models]:
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def is_retriable_nim_error(message: str) -> bool:
    retriable_markers = [
        "HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503",
        "timed out", "timeout", "rate limit", "overloaded", "unavailable",
        "does not support", "vision",
    ]
    return any(marker.lower() in message.lower() for marker in retriable_markers)


def check_nim() -> tuple[bool, str]:
    try:
        request = urllib.request.Request(
            f"{settings.nim_base_url}/models",
            headers={"Authorization": f"Bearer {settings.nim_api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        count = len(data.get("data", [])) if isinstance(data, dict) else 0
        return True, f"NIM connected ({count} model entries)."
    except Exception as exc:
        return False, str(exc)
