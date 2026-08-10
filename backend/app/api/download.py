"""GET /api/download — outputs/ 하위 결과 파일 다운로드."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter()


@router.get("/api/download")
def api_download(file: str) -> FileResponse:
    target = (settings.project_root / file).resolve()
    try:
        target.relative_to(settings.output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(target, filename=target.name)
