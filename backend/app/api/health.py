"""GET /api/health — NVIDIA NIM(현재 LLM 백엔드) 연결 상태 확인."""

import os
from typing import Any, Dict

from fastapi import APIRouter

from ..config import settings
from ..services.nim_client import check_nim, nim_model_candidates

router = APIRouter()


@router.get("/api/health")
def api_health() -> Dict[str, Any]:
    ok, message = check_nim()
    return {
        "ok": True,
        "nim": ok,
        "message": message,
        "baseUrl": settings.nim_base_url,
        "defaultModel": settings.nim_model,
        "fallbackModels": nim_model_candidates(settings.nim_model)[1:],
    }


def _mask(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:8]}...{value[-4:]} (len={len(value)})"


# 임시 진단용 라우트 — Vercel에 NIM_API_KEY가 어떤 이름/값으로 들어갔는지 확인하고 나면 반드시 삭제할 것.
@router.get("/api/debug-env")
def debug_env() -> Dict[str, Any]:
    raw = os.environ.get("NIM_API_KEY")
    matching_names = sorted(k for k in os.environ if "NIM" in k.upper() or "API_KEY" in k.upper())
    return {
        "NIM_API_KEY_found": raw is not None,
        "NIM_API_KEY_raw": _mask(raw),
        "NIM_API_KEY_after_cleanup": _mask(settings.nim_api_key),
        "env_var_names_containing_NIM_or_KEY": matching_names,
    }
