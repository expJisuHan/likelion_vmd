"""GET /, GET /{file_path} — frontend/ 정적 파일 서빙.

주의: `/{file_path:path}` 라우트는 그 외 모든 GET 경로와 매칭될 수 있으므로,
main.py에서 라우터를 등록할 때 반드시 다른 api/* 라우터보다 나중에 등록해야 합니다.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter()

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


@router.get("/")
def serve_index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html", media_type="text/html; charset=utf-8")


@router.get("/{file_path:path}")
def serve_static(file_path: str) -> FileResponse:
    target = (settings.frontend_dir / file_path).resolve()
    try:
        target.relative_to(settings.frontend_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    suffix = target.suffix.lower()
    return FileResponse(target, media_type=_CONTENT_TYPES.get(suffix))
