"""GET /api/health — LM Studio(현재 LLM 백엔드) 연결 상태 확인."""

from typing import Any, Dict

from fastapi import APIRouter

from ..config import settings
from ..services.lmstudio_client import check_lmstudio, lmstudio_model_candidates

router = APIRouter()


@router.get("/api/health")
def api_health() -> Dict[str, Any]:
    ok, message = check_lmstudio()
    return {
        "ok": True,
        "lmstudio": ok,
        "message": message,
        "baseUrl": settings.lmstudio_base_url,
        "defaultModel": settings.lmstudio_model,
        "fallbackModels": lmstudio_model_candidates(settings.lmstudio_model)[1:],
    }
