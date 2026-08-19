"""소비자용 제품 추천 기능(3번)을 위한 제품 카탈로그.

MCM 공식 사이트(us.mcmworldwide.com)는 Cloudflare 봇 차단이 걸려 있어 직접
스크래핑할 수 없었습니다(우회 시도하지 않음). 대신 MCM 정품을 취급하는 리테일
마켓플레이스(Lyst 등)에서 실제로 판매 중인 MCM 가방의 제품명·색상·이미지를
확인해 구성했습니다 — 파트너사 QnA에서 "브랜드 로고, 제품 이미지는 해커톤 목적
하에 사용 가능"이라고 명시적으로 허용한 범위입니다.

주의:
- price는 검색 시점에 제3자 리테일러에서 확인한 참고 가격입니다. 세일 여부와
  리테일러에 따라 실제 가격은 다를 수 있어 MCM 공식 정가로 취급하면 안 됩니다.
- material은 제품명에서 명확히 확인되는 경우만 채웠고, 확인 안 된 경우 빈 문자열로
  남겨 모델이 소재를 지어내지 않도록 했습니다.
- image_url은 제3자 마켓플레이스(Lyst) CDN에 호스팅된 이미지입니다. 링크가
  깨지거나 변경될 수 있어 데모 전 재확인을 권장합니다.

이 데이터가 필요한 이유: LLM이 고객의 의류 질문에 답할 때 존재하지 않는 제품이나
틀린 가격을 지어내면(환각) 실제 구매로 이어질 수 있는 신뢰 문제가 됩니다. 그래서
추천/응답은 반드시 이 카탈로그 안의 항목만 근거로 하도록 설계해야 합니다
(consumer_prompt.py가 진단 결과 중 안전한 필드만 쓰는 것과 같은 원칙).
"""

from __future__ import annotations

from typing import Any

MOCK_CATALOG: list[dict[str, Any]] = [
    {
        "id": "bag-001",
        "name": "뮌헨 나일론 퀄팅 쇼핑백",
        "name_en": "MCM München Nylon Quilted Shopping Bag",
        "category": "가방",
        "color": "블랙",
        "material": "퀄팅 나일론",
        "pattern": "다이아몬드 퀄팅",
        "price_krw_approx": 990_000,
        "price_source": "Lyst (정가 $1,160 대비 세일가 $725 확인, 2026년 기준 참고가)",
        "style_tags": ["미니멀", "포멀", "숄더백"],
        "description": "블랙 퀄팅 나일론 쇼핑백. 은은한 광택의 퀄팅 패턴이 특징.",
        "image_url": "https://cdna.lystit.com/300/375/tr/photos/thefashionsquare/57c0c87b/900x1200/mcm-Black-Munchen-Nylon-Quilted-Shopping-Bag.jpeg",
        "source_url": "https://www.lyst.com/shop/mcm-totes/",
    },
    {
        "id": "bag-002",
        "name": "미니 토니 탑집 쇼퍼",
        "name_en": "MCM Mini Toni Top-Zip Shopper",
        "category": "가방",
        "color": "코냑",
        "material": "",
        "pattern": "모노그램",
        "price_krw_approx": 990_000,
        "price_source": "Lyst 확인가 $730 (2026년 기준 참고가)",
        "style_tags": ["데일리", "미니 사이즈", "쇼퍼백"],
        "description": "코냑 톤의 미니 사이즈 탑집 쇼퍼백. 가벼운 데일리 사용에 적합.",
        "image_url": "https://cdna.lystit.com/300/375/n/photos/nordstrom/46c2a1f9/500x767/mcm-Cognac-Mini-Toni-Top-Zip-Shopper.jpeg",
        "source_url": "https://www.lyst.com/shop/mcm-totes/",
    },
    {
        "id": "bag-003",
        "name": "엘라 미디엄 보스턴백",
        "name_en": "MCM Ella Medium Boston Bag",
        "category": "가방",
        "color": "코냑 브라운",
        "material": "",
        "pattern": "무지",
        "price_krw_approx": 650_000,
        "price_source": "Lyst 확인가 $480 (2026년 기준 참고가)",
        "style_tags": ["보스턴백", "클래식 실루엣", "데일리"],
        "description": "코냑 브라운 톤의 미디엄 보스턴백. 둥근 실루엣의 클래식한 형태.",
        "image_url": "https://cdna.lystit.com/300/375/tr/photos/nordstromrack/141960f6/1024x1024/mcm-COGNAC-Ella-Medium-Boston-Bag.jpeg",
        "source_url": "https://www.lyst.com/shop/mcm-totes/",
    },
    {
        "id": "bag-004",
        "name": "아렌 로고 프린트 토트백",
        "name_en": "MCM Aren Logo-Print Tote Bag",
        "category": "가방",
        "color": "브라운",
        "material": "코팅 캔버스",
        "pattern": "로고 프린트",
        "price_krw_approx": 1_700_000,
        "price_source": "Lyst 확인가 $1,255 (2026년 기준 참고가)",
        "style_tags": ["토트백", "오피스", "로고 플레이"],
        "description": "브라운 톤 코팅 캔버스에 로고 패턴이 프린트된 토트백. 넉넉한 수납공간.",
        "image_url": "https://cdna.lystit.com/300/375/tr/photos/farfetch/663782c7/1000x1334/mcm-brown-Aren-Logo-Print-Tote-Bag.jpeg",
        "source_url": "https://www.lyst.com/shop/mcm-totes/",
    },
    {
        "id": "bag-005",
        "name": "스몰 뉴 리즈 모노그램 프린트 토트백",
        "name_en": "MCM Small New Liz Monogram-Print Tote Bag",
        "category": "가방",
        "color": "블랙",
        "material": "코팅 캔버스",
        "pattern": "모노그램 프린트",
        "price_krw_approx": 1_080_000,
        "price_source": "Lyst 확인가 $792 (2026년 기준 참고가)",
        "style_tags": ["토트백", "스몰 사이즈", "모노그램"],
        "description": "블랙 톤 모노그램 프린트의 스몰 사이즈 토트백.",
        "image_url": "https://cdna.lystit.com/300/375/tr/photos/farfetch/02305e87/1000x1334/mcm-black-Small-New-Liz-Monogram-Print-Tote-Bag.jpeg",
        "source_url": "https://www.lyst.com/shop/mcm-totes/",
    },
]


def search_catalog(keywords: list[str]) -> list[dict[str, Any]]:
    """키워드(색상/카테고리/소재/스타일 태그)로 카탈로그를 느슨하게 매칭합니다.

    복잡한 추천 알고리즘 대신, 고객 질문에 담긴 단어가 제품의 필드 중 하나와
    겹치면 후보로 뽑는 단순 필터링입니다. LLM은 이 결과에 있는 제품만 언급하도록
    프롬프트에서 강제합니다.
    """
    if not keywords:
        return MOCK_CATALOG

    normalized_keywords = [kw.strip().lower() for kw in keywords if kw and kw.strip()]
    if not normalized_keywords:
        return MOCK_CATALOG

    matches = []
    for product in MOCK_CATALOG:
        haystack = " ".join(
            [
                product["name"],
                product["name_en"],
                product["category"],
                product["color"],
                product["material"],
                product["pattern"],
                " ".join(product["style_tags"]),
            ]
        ).lower()
        if any(keyword in haystack for keyword in normalized_keywords):
            matches.append(product)
    return matches
