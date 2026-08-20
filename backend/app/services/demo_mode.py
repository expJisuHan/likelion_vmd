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


def is_vmd_demo_image(data_url: str) -> bool:
    """MCM_sample.jpg와 같은 사진인지(=위 소비자 데모 사진과 동일 사진) 판단합니다.
    같은 평균 해시를 공유하므로 is_demo_image()와 동일한 판정 로직을 그대로 씁니다."""
    return is_demo_image(data_url)


# 사용자가 이 사진을 보고 직접 작성한 예시 평가(PP 존 기준)입니다. 실측으로 확인한
# 것처럼 11B 모델은 이 정도의 구체성(색·소재·개수를 정확히 짚고, 항목마다 서로 다른
# 근거를 대는 것)을 프롬프트만으로 안정적으로 재현하지 못해, 시연에서는 이 고정
# 응답을 그대로 씁니다. apply_defaults()로 한 번 더 통과시켜 zone_evaluation_summary
# 등 실제 파이프라인이 항상 채우는 파생 필드도 동일하게 채웁니다.
def build_vmd_demo_result() -> dict[str, Any]:
    from .analysis import apply_defaults

    result: dict[str, Any] = {
        "user_selected_zone": "PP",
        "ai_detected_zone": "PP",
        "zone_confidence": 0.80,
        "store_type_assumption": "패션 잡화(백팩·토트백·스니커즈 등)를 판매하는 편집숍 또는 브랜드 단독매장으로 추정됩니다.",
        "photo_quality": {
            "score": 85,
            "is_blurry": False,
            "is_tilted": False,
            "has_background_interference": False,
            "needs_retake": False,
            "comment": "정면에서 초점이 선명하게 촬영되어 진열 상태를 판단하기에 충분한 화질입니다. 두 장 모두 동일한 각도의 사진으로 보입니다.",
        },
        "mannequin": {"exists": False, "type": "none", "has_head": False, "comment": ""},
        "obstacles": [],
        "total_score": 74,
        "grade": "B (양호, 개선 필요)",
        "positive_points": [
            "빨간색 포장 박스형 리세션을 4단으로 쌓아 만든 피라미드 진열대가 매장 중앙 통로에서 강한 색 블록으로 시선을 끌어 PP 존의 포컬 포인트 역할을 하고 있습니다.",
            "빨간색 리세션 위에 파란색 술 장식 백팩, 노란색-검정 그래픽 패턴 파우치, 빨강-노랑 패턴 토트백을 함께 배치해 3가지 색상 대비로 상품 라인의 다양성을 보여줍니다.",
            "천장의 종이 랜턴형 조명 군집과 매달린 전구들이 진열대 위쪽 시선을 자연스럽게 유도해 리세션과 조명 연출이 조화를 이룹니다.",
        ],
        "critical_issues": [
            "진열대 앞쪽에 놓인 흰색 카드로 보이는 태그의 글자가 사진에서 식별되지 않아, 가격이나 상품 정보가 실제로 부착되어 있는지 확인할 수 없습니다.",
            "신발 한 켤레가 피라미드 우측 하단 모서리에 다소 무심하게 걸쳐진 듯 배치되어, 가방 위주의 리세션 안에서 시각적으로 붕 뜬 느낌을 줍니다.",
            "리세션 표면이 붉은 셀로판/포장지 재질로 광택이 강해 천장 조명이 표면에 반사되어 일부 각도에서 상품보다 포장재 광택이 먼저 시선을 끕니다.",
            "리세션 뒤쪽 유리 쇼케이스와 우측 선반의 상품들이 리세션과 뚜렷한 색·톤 구분 없이 이어져, PP 존 리세션 자체의 독립적 존재감이 약해집니다.",
        ],
        "improvement_suggestions": [
            "흰색 태그 위치를 상품 정면으로 통일하고 글자 크기를 키워 고객이 멀리서도 가격·소재 정보를 읽을 수 있도록 재배치하세요.",
            "신발은 별도의 낮은 단이나 투명 아크릴 스탠드에 분리 배치해 가방 카테고리와 신발 카테고리 각각의 존재감을 살리세요.",
            "리세션 표면을 무광 마감재로 교체하거나 표면 각도를 조정해 조명 반사가 상품이 아닌 리세션 하단으로 떨어지도록 조정하세요.",
            "리세션 뒤에 짙은 색 배경 패널이나 낮은 파티션을 세워 유리 쇼케이스·선반과 시각적으로 분리하면 리세션의 포컬 포인트 효과가 강화됩니다.",
        ],
        "final_summary": (
            "이 사진은 매장 중앙 통로에 놓인 빨간색 4단 피라미드형 리세션 위에 백팩·토트·스니커즈 등 약 7개의 상품을 "
            "배치한 PP 진열로, 강렬한 레드 컬러 블록과 파란색·노란색 포인트 상품의 색 대비 덕분에 첫인상 임팩트는 준수한 "
            "편입니다. 다만 리세션 상단 단이 비어 있어 피라미드 라인의 밀도가 고르지 않고, 상품 정보로 보이는 흰색 카드의 "
            "글자를 확인할 수 없어 가격·소재 안내 여부가 불분명한 점이 가장 시급한 개선 포인트입니다. 또한 리세션과 뒤쪽 "
            "유리 쇼케이스·선반이 시각적으로 분리되지 않아 PP 진열의 경계가 흐려지는 점도 함께 보완이 필요합니다. 전반적으로 "
            "색과 조명 연출은 매력적이지만, 정보 전달력과 진열 밀도 측면에서 추가 정비가 필요한 상태입니다."
        ),
        "criteria_evaluations": [
            {
                "criterion": "포컬 포인트 임팩트",
                "score": 82,
                "evidence": "매장 중앙 통로 정면에 빨간색 4단 피라미드 리세션이 주변 집기보다 눈에 띄게 높이 솟아 있어 입구에서부터 시선이 먼저 닿습니다.",
                "issue": "피라미드 상단 1~2단에는 상품이 거의 보이지 않아 하단에 비해 시각적 밀도가 낮습니다.",
                "suggestion": "상단 단에도 파우치나 카드지갑 같은 소형 아이템을 1~2개 추가해 피라미드 전체 라인의 밀도를 맞추세요.",
            },
            {
                "criterion": "컬러 코디네이션",
                "score": 78,
                "evidence": "빨간색 리세션을 기본 톤으로 하고 그 위에 파란색 백팩 1개, 노란색-검정 그래픽 파우치 1개, 빨강-노랑 패턴 토트·크로스백 2개를 배치해 총 3가지 색 계열이 섞여 있습니다.",
                "issue": "빨간 계열 상품이 빨간 리세션과 명도 차이가 크지 않아 사진상 리세션 표면과 상품 경계가 잘 구분되지 않는 구간이 있습니다.",
                "suggestion": "빨간 계열 상품 아래에 흰색이나 검정색의 작은 받침을 깔아 리세션과 상품 사이에 명도 대비를 만들어 주세요.",
            },
            {
                "criterion": "리세션/집기 활용",
                "score": 75,
                "evidence": "택배 상자를 쌓은 듯한 형태의 4단 리세션이 상품 크기 대비 한 칸의 높이가 상당히 높게 제작되어 있습니다.",
                "issue": "리세션 각 단의 폭이 앞쪽 가방이 놓인 자리 외에는 비어 있어, 집기 부피에 비해 상품 개수가 상대적으로 적어 보입니다.",
                "suggestion": "리세션 단수를 줄이거나 각 단에 상품을 2~3개씩 추가 배치해 집기와 상품 수량의 비율을 맞추세요.",
            },
            {
                "criterion": "가격·정보 사이니지",
                "score": 55,
                "evidence": "리세션 중앙 하단, 검정 재질 가방 앞쪽에 작은 흰색 사각형 카드 한 장이 놓여 있습니다.",
                "issue": "그 카드의 글자가 사진 해상도에서 식별되지 않아 가격이나 소재 정보가 실제로 안내되고 있는지 확인할 수 없습니다.",
                "suggestion": "가격 태그를 상품마다 눈높이에 맞춰 부착하고, 큰 글씨의 가격 안내 카드를 리세션 정면에 별도로 세워 정보 접근성을 높이세요.",
            },
            {
                "criterion": "배경과의 시각적 구분",
                "score": 70,
                "evidence": "리세션 뒤쪽으로 유리 쇼케이스 상판과 우측 벽면 선반의 가방들이 별도의 배경 처리 없이 같은 프레임 안에 이어져 있습니다.",
                "issue": "리세션과 뒤쪽 쇼케이스·선반 사이에 색이나 조명 톤의 구분이 없어 이번 PP 진열의 범위가 한눈에 파악되지 않습니다.",
                "suggestion": "리세션 뒤에 짙은 색 배경 패널을 세우거나 리세션 위쪽에만 집중 조명을 추가해 PP 진열 영역을 시각적으로 분리하세요.",
            },
        ],
    }
    # apply_defaults()는 criteria_evaluations를 zones.py의 PP 기본 항목 이름 기준으로
    # 다시 채우면서 이름이 일치하지 않는 항목은 버립니다. 이 사진에 맞춰 직접 지은
    # 항목 이름(포컬 포인트 임팩트 등)을 그대로 유지하기 위해 호출 전에 백업해두고
    # 다른 파생 필드(zone_evaluation_summary 등)만 채운 뒤 되돌려놓습니다.
    custom_criteria = result["criteria_evaluations"]
    result = apply_defaults(result, "PP")
    result["criteria_evaluations"] = custom_criteria
    return {"result": result, "raw": {"demo": True}, "model": "demo"}
