"""시연용 고정 응답 — 특정 샘플 사진이 올라오면 실제 NIM 호출 없이 미리 써둔
결과를 보여줍니다.

NIM 응답 시간이 편차가 크고(수 초~90초 이상) 가끔 형식이 무너지는 걸 이번
세션 내내 실측으로 확인했기 때문에, 라이브 데모에서는 이 불확실성 자체가
리스크입니다. 프런트가 이미지를 캔버스로 재인코딩해서 올리므로(mediaUtils.js의
resizeImageDataUrl) 원본과 바이트가 달라져 단순 해시 비교로는 못 알아봅니다.
그래서 시각적으로 거의 동일하면 값이 같게 나오는 평균 해시(average hash)로
식별합니다 — 원본/프런트 재인코딩/백엔드 재압축을 모두 실측으로 비교했을 때
해밍 거리 0으로 완전히 안정적이었습니다.
"""

from __future__ import annotations

import base64
import time
from io import BytesIO
from typing import Any

from PIL import Image

# mcm3.jpg(매장 중앙에 빨간 상자 계단식 진열대) 기준 16x16 평균 해시.
_DEMO_IMAGE_HASH = 0x73FF3FFF1ED81FFA3FF0D7A7E30F601E0000200000004200C600FFC1FFFFFFFF
_HASH_SIZE = 16
# 실측상 해밍 거리 0으로 나왔지만, 다른 각도로 찍거나 조명이 살짝 달라질 수
# 있는 실제 시연 상황을 감안해 약간의 여유를 둡니다. 256비트 중 20비트 이내
# 차이면 같은 사진으로 판단합니다.
_HAMMING_THRESHOLD = 20

DEMO_LOADING_SECONDS = 15


def _average_hash(image: Image.Image, hash_size: int = _HASH_SIZE) -> int:
    small = image.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return int(bits, 2)


def is_demo_image(data_url: str) -> bool:
    if not data_url.startswith("data:image/") or "," not in data_url:
        return False
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
        image = Image.open(BytesIO(raw))
        candidate_hash = _average_hash(image)
    except Exception:
        return False
    distance = bin(candidate_hash ^ _DEMO_IMAGE_HASH).count("1")
    return distance <= _HAMMING_THRESHOLD


def build_demo_response() -> dict[str, Any]:
    items = [
        {
            "label": "상품 정보",
            "description": (
                "빨간 상자를 계단식으로 쌓아 만든 진열대 위에 상품이 놓여 있습니다. "
                "빨간색 백팩 2개, 파란색 백팩 2개, 빨간 바탕에 검은색 기하학 무늬가 "
                "있는 가방 1개, 노란색과 검은색 무늬가 섞인 가방 1개가 있습니다. "
                "진열대 오른쪽 끝에는 파란색과 빨간색이 섞인 스니커즈 1켤레가 놓여 있습니다."
            ),
        },
        {
            "label": "위치·방향",
            "description": (
                "이 진열대는 매장 중앙, 촬영자 정면에 있습니다. 왼쪽 벽면에는 작은 "
                "가방들이 걸린 별도 진열 공간이 있고, 오른쪽 벽면에도 여러 단으로 된 "
                "선반 진열대가 있습니다. 정면 안쪽으로는 나무 패널로 마감된 벽이 보입니다."
            ),
        },
        {
            "label": "이동 안전",
            "description": (
                "천장에 종이 재질의 등이 여러 높이로 낮게 매달려 있습니다. 위치에 따라 "
                "머리 높이까지 내려온 조명이 있을 수 있는데, 이런 건 지팡이로는 감지되지 "
                "않는 높이라 특히 주의가 필요합니다. 바닥은 무광에 가까운 밝은 색 패턴 "
                "타일로 보이고, 단차는 확인되지 않습니다. 중앙의 빨간 상자 진열대는 "
                "계단식으로 쌓여 있어 바닥에서 튀어나온 장애물로 작용할 수 있으며, "
                "진열대 양옆으로 지나갈 수 있는 공간이 있는 것으로 보입니다."
            ),
        },
        {
            "label": "구역 구분",
            "description": "색이나 조명으로 명확히 구분된 카테고리 구역은 확인되지 않습니다.",
        },
        {
            "label": "안내 정보",
            "description": (
                "점자 안내는 사진으로 확인이 어렵습니다. 큰 글씨 안내판은 보이지 않습니다. "
                "사진에 보이는 범위 안에서 직원이나 안내데스크는 확인되지 않습니다."
            ),
        },
        {
            "label": "가격 정보",
            "description": "진열대 위에 흰색 카드가 하나 보이지만 글씨가 작아 가격은 확인할 수 없습니다.",
        },
    ]
    narration = " ".join(f"{item['label']}. {item['description']}" for item in items)
    return {"ok": True, "type": "clothing", "items": items, "narration": narration}


def run_demo_delay() -> None:
    """실제 분석처럼 느껴지도록 약 15초 대기합니다. 진짜 NIM 호출을 흉내내는
    용도이지 성능 최적화 대상이 아니라서, time.sleep으로 충분합니다."""
    time.sleep(DEMO_LOADING_SECONDS)
