"""로컬 실행 진입점.

    python run.py

기존 `python app/server.py` 를 대체합니다. HOST/PORT/RELOAD 는 .env 로 조정하세요.
"""

import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
