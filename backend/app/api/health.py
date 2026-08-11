"""GET /api/health — NVIDIA NIM(현재 LLM 백엔드) 연결 상태 확인."""

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
