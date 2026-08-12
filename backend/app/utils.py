from __future__ import annotations

import base64
import re
import struct
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from .config import settings

try:
    from PIL import Image as PillowImage
    from PIL import ImageOps
except Exception:  # pragma: no cover - image embedding is optional.
    PillowImage = None
    ImageOps = None


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def relative_output_path(path: Path) -> str:
    """outputs/ 파일의 참조용 경로 문자열.

    Vercel 배포에서는 output_dir이 /tmp 아래(project_root 밖)라 project_root 기준
    상대경로로 변환할 수 없습니다. 그 경우 절대경로를 그대로 반환합니다 —
    /api/download은 project_root와 절대경로를 이어붙여도 pathlib이 절대경로를
    그대로 쓰기 때문에 여전히 같은 인스턴스 안에서는 동작합니다.
    """
    try:
        return str(path.relative_to(settings.project_root))
    except ValueError:
        return str(path)


def safe_file_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_. -]+", "_", name or "").strip()
    return cleaned or "image"


def list_to_lines(value: Any) -> str:
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append("; ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                lines.append(str(item))
        return "\n".join(lines)
    if isinstance(value, dict):
        import json

        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def format_elapsed(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    total_seconds = max(0, int(round(float(seconds))))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    if minutes:
        return f"{minutes}분 {remaining_seconds}초"
    return f"{remaining_seconds}초"


def friendly_error_message(exc: Exception) -> str:
    """NIM 관련 예외를 사람이 읽을 메시지로 바꿉니다.

    각 메시지 앞에 [NIM_XXX] 코드를 붙여서, 서로 다른 원인이 뭉뚱그려지지 않고
    화면/응답 body만 보고도 정확히 어느 분기를 탔는지 구분할 수 있게 합니다.
    (예전엔 "Authorization"/"Bearer" 단어만 보고 401/403이 아닌 다른 에러까지
    전부 "인증 실패"로 잘못 뭉뚱그려지는 문제가 있었습니다.)
    """
    message = str(exc)

    # 키가 아예 비어있을 때 NIM 게이트웨이가 401 대신 이 구체적인 문구로 500을 돌려줍니다.
    if "Missing request extension" in message and "Authorization" in message:
        return "[NIM_AUTH_MISSING_KEY] NVIDIA NIM API 키가 비어있습니다. backend/.env(또는 Vercel 환경변수)의 NIM_API_KEY를 확인해 주세요."
    if "NIM HTTP 401" in message:
        return "[NIM_AUTH_401] NVIDIA NIM 인증에 실패했습니다 (401). NIM_API_KEY가 올바른지 확인해 주세요."
    if "NIM HTTP 403" in message:
        return "[NIM_AUTH_403] NVIDIA NIM 접근이 거부됐습니다 (403). 이 키로 해당 모델을 쓸 권한이 있는지 확인해 주세요."
    if "NIM HTTP 429" in message:
        return "[NIM_RATE_LIMIT] NVIDIA NIM 요청 한도(rate limit)에 도달했습니다 (429). 잠시 후 다시 시도해 주세요."
    if "NIM HTTP 400" in message:
        return "[NIM_BAD_REQUEST] NVIDIA NIM이 분석 요청을 거절했습니다 (400). 모델명이 정확한지, 현재 모델이 이미지 입력을 지원하는지 확인해 주세요."
    if "NIM HTTP 500" in message or "NIM HTTP 502" in message or "NIM HTTP 503" in message:
        return f"[NIM_SERVER_ERROR] NVIDIA NIM 서버 쪽 오류입니다. 잠시 후 다시 시도해 주세요. 원본 메시지: {message}"
    if "timed out" in message.lower() or "timeout" in message.lower():
        return "[NIM_TIMEOUT] NVIDIA NIM 응답이 시간 내에 오지 않았습니다. 네트워크 상태나 NIM_TIMEOUT_SECONDS 설정을 확인해 주세요."
    if "Connection refused" in message or "연결을 거부" in message or "WinError 10061" in message:
        return "[NIM_CONNECTION_FAILED] NVIDIA NIM 서버에 연결할 수 없습니다. 네트워크 연결과 NIM_BASE_URL 설정을 확인해 주세요."
    # 위 어느 패턴에도 안 걸리면 원본 메시지를 그대로 노출합니다 — 잘못 뭉뚱그려서
    # 실제 원인을 가리는 것보다, 낯선 메시지라도 있는 그대로 보여주는 쪽이 디버깅에 낫습니다.
    return f"[NIM_UNKNOWN] {message}"


# --- Image helpers (data URL <-> raw bytes, EXIF orientation, thumbnails) ---


def image_data_url_to_thumbnail(data_url: str, max_size: tuple[int, int] = (120, 90)) -> BytesIO | None:
    if not data_url.startswith("data:image/") or "," not in data_url or PillowImage is None:
        return None
    try:
        encoded = data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        image = PillowImage.open(BytesIO(raw))
        if ImageOps is not None:
            image = ImageOps.exif_transpose(image)
        image.thumbnail(max_size)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        stream = BytesIO()
        image.save(stream, format="PNG")
        stream.seek(0)
        return stream
    except Exception:
        return None


def resize_image_data_url_for_model(data_url: str, max_dimension: int, max_bytes: int) -> str:
    """NIM처럼 요청 본문에 직접 담는 base64 이미지 용량 제한이 있는 API에 보내기 전,
    긴 변을 max_dimension으로 줄이고 JPEG 품질을 낮춰가며 max_bytes 이하로 맞춥니다.
    실패하거나 이미 기준 이하면 원본 data_url을 그대로 반환합니다.
    """
    if not data_url.startswith("data:image/") or "," not in data_url or PillowImage is None:
        return data_url
    try:
        encoded = data_url.split(",", 1)[1]
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) <= max_bytes:
            return data_url
        image = PillowImage.open(BytesIO(raw))
        if ImageOps is not None:
            image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.thumbnail((max_dimension, max_dimension))
        for quality in (85, 70, 55, 40, 25):
            stream = BytesIO()
            image.save(stream, format="JPEG", quality=quality, optimize=True)
            if stream.tell() <= max_bytes:
                break
        return "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode("ascii")
    except Exception:
        return data_url


def jpeg_exif_orientation(data: bytes) -> int:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return 1
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            return 1
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            return 1
        segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
        segment = data[offset + 2 : offset + segment_length]
        offset += segment_length
        if marker != 0xE1 or not segment.startswith(b"Exif\x00\x00"):
            continue
        tiff = segment[6:]
        if len(tiff) < 8:
            return 1
        if tiff[:2] == b"II":
            endian = "<"
        elif tiff[:2] == b"MM":
            endian = ">"
        else:
            return 1
        if struct.unpack(endian + "H", tiff[2:4])[0] != 42:
            return 1
        ifd_offset = struct.unpack(endian + "I", tiff[4:8])[0]
        if ifd_offset + 2 > len(tiff):
            return 1
        entry_count = struct.unpack(endian + "H", tiff[ifd_offset : ifd_offset + 2])[0]
        entries_start = ifd_offset + 2
        for index in range(entry_count):
            entry_start = entries_start + index * 12
            entry = tiff[entry_start : entry_start + 12]
            if len(entry) < 12:
                return 1
            tag, value_type, count = struct.unpack(endian + "HHI", entry[:8])
            if tag == 0x0112 and value_type == 3 and count == 1:
                return struct.unpack(endian + "H", entry[8:10])[0]
    return 1


def image_size(data: bytes, extension: str) -> tuple[int, int] | None:
    if extension == "png" and len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if extension == "jpg" and len(data) >= 4 and data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 <= len(data):
            if data[offset] != 0xFF:
                return None
            marker = data[offset + 1]
            offset += 2
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
                segment = data[offset + 2 : offset + segment_length]
                if len(segment) >= 5:
                    height, width = struct.unpack(">HH", segment[1:5])
                    return width, height
                return None
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                return None
            segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
            offset += segment_length
    return None


def fit_image_extent(data: bytes, extension: str, orientation: int, max_width: int = 120, max_height: int = 90) -> tuple[int, int]:
    size = image_size(data, extension)
    if size is None:
        width, height = max_width, max_height
    else:
        width, height = size
    if orientation in {5, 6, 7, 8}:
        display_width, display_height = height, width
    else:
        display_width, display_height = width, height
    scale = min(max_width / max(1, display_width), max_height / max(1, display_height), 1)
    display_width_px = max(1, round(display_width * scale))
    display_height_px = max(1, round(display_height * scale))
    if orientation in {5, 6, 7, 8}:
        width_px, height_px = display_height_px, display_width_px
    else:
        width_px, height_px = display_width_px, display_height_px
    return width_px * 9525, height_px * 9525


def excel_rotation_from_orientation(orientation: int) -> int:
    rotations = {
        3: 180 * 60000,
        6: 90 * 60000,
        8: 270 * 60000,
    }
    return rotations.get(orientation, 0)


def image_data_url_to_media(data_url: str) -> dict[str, Any] | None:
    if not data_url.startswith("data:image/") or "," not in data_url:
        return None
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";", 1)[0].lower()
    if mime == "image/png":
        extension = "png"
    elif mime in {"image/jpeg", "image/jpg"}:
        extension = "jpg"
        mime = "image/jpeg"
    else:
        return None
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception:
        return None
    orientation = jpeg_exif_orientation(data) if extension == "jpg" else 1
    cx, cy = fit_image_extent(data, extension, orientation)
    return {
        "data": data,
        "extension": extension,
        "content_type": mime,
        "orientation": orientation,
        "rotation": excel_rotation_from_orientation(orientation),
        "cx": cx,
        "cy": cy,
    }
