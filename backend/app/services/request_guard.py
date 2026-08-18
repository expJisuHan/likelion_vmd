"""분석 엔드포인트(/api/analyze, /api/batch-analyze) 오남용 방어.

유료 NIM API를 호출하는 엔드포인트가 인증 없이 공개돼 있으면 배포 URL만 알아도
비용이 발생할 수 있습니다. 여기서는 세 가지를 최소 방어선으로 둡니다:

1. enforce_app_key   - APP_ACCESS_KEY가 설정된 경우에만 X-App-Key 헤더를 검사.
2. enforce_rate_limit - IP별 슬라이딩 윈도우 레이트리밋(인메모리).
3. enforce_payload_limits - 이미지 장수/용량 상한.

주의: 인메모리 카운터는 프로세스 단위입니다. Vercel Functions처럼 요청마다
인스턴스가 새로 뜰 수 있는 서버리스 환경에서는 완벽히 정확하진 않지만, 워밍된
인스턴스에 몰리는 가장 흔한 오남용 패턴(같은 브라우저/스크립트의 연속 호출)은
막아주고, 로컬/단일 프로세스 배포에서는 온전히 동작합니다.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from fastapi import HTTPException, Request

from ..config import settings

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_app_key(request: Request) -> None:
    if not settings.app_access_key:
        return
    if request.headers.get("x-app-key", "") != settings.app_access_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def enforce_rate_limit(request: Request) -> None:
    if settings.rate_limit_requests <= 0:
        return
    ip = client_ip(request)
    window = settings.rate_limit_window_seconds
    now = time.monotonic()
    with _lock:
        hits = _hits[ip]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= settings.rate_limit_requests:
            retry_after = max(1, int(window - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail=f"요청이 너무 많습니다. {retry_after}초 후 다시 시도해 주세요.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


def enforce_payload_limits(images: list[dict[str, Any]]) -> None:
    if len(images) > settings.max_images_per_request:
        raise HTTPException(
            status_code=400,
            detail=f"한 번에 최대 {settings.max_images_per_request}장까지 분석할 수 있습니다.",
        )
    for image in images:
        data_url = image.get("dataUrl", "") or ""
        approx_bytes = int(len(data_url) * 0.75)  # base64 -> 원본 바이트 근사치
        if approx_bytes > settings.max_image_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"이미지 용량이 너무 큽니다 (최대 {settings.max_image_bytes // 1_000_000}MB).",
            )
