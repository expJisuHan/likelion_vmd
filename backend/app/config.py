"""애플리케이션 설정.

기존 server.py는 `os.environ.get(...)` 을 코드 곳곳에서 직접 호출했습니다.
FastAPI 전환과 함께 환경변수를 한 곳(Settings)에서만 읽도록 정리했습니다.

.env 파일은 backend/ 폴더에 두면 자동으로 로드됩니다 (backend/.env.example 참고).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# backend/.env 를 우선 로드하고, 없으면 상위 폴더의 .env 도 시도합니다.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- NVIDIA NIM ---
    nim_base_url: str = os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    nim_api_key: str = os.environ.get("NIM_API_KEY", "")
    nim_model: str = os.environ.get("NIM_MODEL", "meta/llama-3.2-11b-vision-instruct")
    nim_fallback_models: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("NIM_FALLBACK_MODELS", ""))
    )
    nim_timeout_seconds: int = int(os.environ.get("NIM_TIMEOUT_SECONDS", "180"))
    # 요청에 직접 담아 보내는 base64 이미지 용량 제한 (NIM 호스팅 VLM 엔드포인트 기준, 이보다 크면 리사이즈)
    nim_image_max_bytes: int = int(os.environ.get("NIM_IMAGE_MAX_BYTES", "180000"))
    nim_image_max_dimension: int = int(os.environ.get("NIM_IMAGE_MAX_DIMENSION", "1280"))

    # --- App server ---
    host: str = os.environ.get("HOST", "127.0.0.1")
    port: int = int(os.environ.get("PORT", "8000"))
    reload: bool = os.environ.get("RELOAD", "false").lower() in {"1", "true", "yes"}
    # true면 처리되지 않은 예외의 원본 메시지를 응답에 그대로 포함합니다 (로컬 디버깅용).
    # 배포본에서는 기본값(false)을 유지해 내부 구현 정보가 노출되지 않도록 합니다.
    debug: bool = os.environ.get("DEBUG", "false").lower() in {"1", "true", "yes"}

    # --- CORS (프론트를 별도 origin/포트에서 띄울 때 사용) ---
    cors_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.environ.get("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
        )
    )

    # --- 분석 엔드포인트 오남용 방어 ---
    # 비워두면 X-App-Key 검사를 건너뜁니다 (기본값: 비활성화).
    app_access_key: str = os.environ.get("APP_ACCESS_KEY", "")
    # IP당 윈도우 내 허용 요청 수. 0 이하로 설정하면 레이트리밋을 끕니다.
    rate_limit_requests: int = int(os.environ.get("RATE_LIMIT_REQUESTS", "12"))
    rate_limit_window_seconds: int = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    max_images_per_request: int = int(os.environ.get("MAX_IMAGES_PER_REQUEST", "20"))
    max_image_bytes: int = int(os.environ.get("MAX_IMAGE_BYTES", "8000000"))

    # --- 동일 요청(이미지+옵션) 분석 결과 캐시 ---
    analysis_cache_enabled: bool = os.environ.get("ANALYSIS_CACHE_ENABLED", "true").lower() in {"1", "true", "yes"}
    analysis_cache_ttl_seconds: int = int(os.environ.get("ANALYSIS_CACHE_TTL_SECONDS", "1800"))
    analysis_cache_max_entries: int = int(os.environ.get("ANALYSIS_CACHE_MAX_ENTRIES", "200"))

    # --- Paths ---
    # Vercel Functions는 배포 파일시스템이 읽기 전용이라 /tmp에만 쓸 수 있습니다.
    # Vercel은 함수 환경에 VERCEL=1을 자동으로 주입하므로 이를 기준으로 출력 경로를 분기합니다.
    project_root: Path = PROJECT_ROOT
    frontend_dir: Path = PROJECT_ROOT / os.environ.get("FRONTEND_DIR", "frontend")
    output_dir: Path = (
        Path("/tmp/outputs") if os.environ.get("VERCEL") == "1" else PROJECT_ROOT / os.environ.get("OUTPUT_DIR", "outputs")
    )

    @property
    def json_dir(self) -> Path:
        return self.output_dir / "json"

    @property
    def excel_dir(self) -> Path:
        return self.output_dir / "excel"

    @property
    def pdf_dir(self) -> Path:
        return self.output_dir / "pdf"

    def ensure_dirs(self) -> None:
        for path in (self.json_dir, self.excel_dir, self.pdf_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
