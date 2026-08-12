"""동일한 이미지+옵션 조합에 대한 NIM 분석 결과 캐시.

같은 사진을 같은 설정으로 다시 분석 요청하면(리허설 중 반복 테스트, 사용자가
"분석 시작"을 두 번 누르는 경우 등) 매번 유료 NIM 호출을 다시 하지 않도록
인메모리로 결과를 재사용합니다.

주의: 프로세스 인메모리 캐시라 Vercel Functions처럼 인스턴스가 새로 뜨는
서버리스 환경에서는 완전히 보장되진 않지만, 로컬/단일 프로세스 배포와 워밍된
서버리스 인스턴스에서는 온전히 동작합니다. 개발 서버(--reload)는 파일 저장 시
프로세스가 재시작되므로 프롬프트를 고치면 캐시도 자연히 비워집니다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

from ..config import settings

_CACHE_OPTION_KEYS = (
    "zoneMode",
    "storeType",
    "tone",
    "criteria",
    "focusKeywords",
    "extraCriteria",
    "modelName",
    "temperature",
    "maxTokens",
)

_store: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()
_lock = Lock()


def build_cache_key(images: list[dict[str, Any]], options: dict[str, Any]) -> str:
    hasher = hashlib.sha256()
    for image in images:
        hasher.update(str(image.get("dataUrl", "")).encode("utf-8"))
        hasher.update(b"|")
    relevant_options = {key: options.get(key) for key in _CACHE_OPTION_KEYS}
    hasher.update(json.dumps(relevant_options, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return hasher.hexdigest()


def get_cached_result(cache_key: str) -> dict[str, Any] | None:
    if not settings.analysis_cache_enabled:
        return None
    with _lock:
        entry = _store.get(cache_key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > settings.analysis_cache_ttl_seconds:
            del _store[cache_key]
            return None
        _store.move_to_end(cache_key)
        return copy.deepcopy(value)


def store_result(cache_key: str, value: dict[str, Any]) -> None:
    if not settings.analysis_cache_enabled:
        return
    with _lock:
        _store[cache_key] = (time.monotonic(), copy.deepcopy(value))
        _store.move_to_end(cache_key)
        while len(_store) > settings.analysis_cache_max_entries:
            _store.popitem(last=False)
