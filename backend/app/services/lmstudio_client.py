"""LM Studio(OpenAI 호환 /v1/chat/completions) 클라이언트.

지금은 LM Studio 전용이지만, 나중에 다른 OpenAI 호환 API(NVIDIA NIM, GPT 등)로
바꿀 때는 이 파일만 교체하면 되도록 LM Studio 통신 로직을 한 곳에 모아뒀습니다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import settings


def lmstudio_request(payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.lmstudio_base_url}/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or settings.lmstudio_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body.strip() or exc.reason
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {detail}") from exc


def lmstudio_model_candidates(requested_model: str) -> list[str]:
    default_fallbacks = ["google/gemma-4-12b", "google/gemma-4-12b-qat", "google/gemma-3-4b"]
    fallback_models = [*settings.lmstudio_fallback_models, *default_fallbacks]
    candidates: list[str] = []
    for model in [requested_model, *fallback_models]:
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def is_retriable_lmstudio_error(message: str) -> bool:
    retriable_markers = ["Model unloaded", "Channel Error", "Failed to load model", "exited before becoming healthy", "vision", "image"]
    return any(marker.lower() in message.lower() for marker in retriable_markers)


def check_lmstudio() -> tuple[bool, str]:
    try:
        request = urllib.request.Request(f"{settings.lmstudio_base_url}/models", method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        count = len(data.get("data", [])) if isinstance(data, dict) else 0
        return True, f"LM Studio connected ({count} model entries)."
    except Exception as exc:
        return False, str(exc)
