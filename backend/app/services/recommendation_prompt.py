"""고객의 의류 질문에 카탈로그 기반으로 답하는 제품 추천 프롬프트 (기능 3).

consumer_prompt.py(진열 서술)와 accessibility_prompt.py(공간 안전)에 이어지는
세 번째 소비자 기능입니다. 이미지를 다시 분석하지 않고, catalog.py의 제품 목록
중 이 프롬프트가 실제로 건네준 항목만 근거로 답하도록 강제합니다.

실측으로 확인한 핵심 문제: "있다/없다", "정확히 일치하는가" 같은 논리적 판단을
LLM에게 맡기면 신뢰할 수 없습니다.
  - "블랙 토트백"처럼 속성이 2개 이상 겹치는 질문에서, 정확히 맞는 제품이 후보에
    있는데도 "없다"고 잘못 답하는 경우가 여러 번 나왔습니다.
  - "신발 있어요?"처럼 카탈로그에 아예 없는 카테고리를 물었는데 "있다"고 답하고
    엉뚱한 가방을 신발인 것처럼 추천한 경우도 있었습니다.
  - 프롬프트 문구를 반복해서 다듬어도(정확히 일치 섹션 분리, 막연한 질문 처리 지시
    추가) 한쪽을 고치면 다른 쪽이 흔들리는 패턴이 계속됐습니다.

그래서 "있다/없다"·"정확히 일치하는가"의 최종 판단은 전부 코드에서 미리 확정하고,
LLM에게는 그 판단을 절대 뒤집지 못하게 "결론" 문장으로 못박아 건네준 뒤, 그걸
감각적인 문장으로 풀어 설명하는 역할만 맡깁니다. 카탈로그에 아예 없는 카테고리를
물었을 때는(예: 신발) LLM을 호출조차 하지 않고 고정 문구로 바로 답합니다 —
consumer_prompt.py의 has_sufficient_content()와 같은 원칙입니다.
"""

from __future__ import annotations

import re
from typing import Any

from .catalog import MOCK_CATALOG, search_catalog

_STOPWORDS = {
    "있어요", "있나요", "있을까요", "얼마", "얼마예요", "얼마인가요", "궁금해요",
    "추천", "추천해주세요", "해주세요", "보여주세요", "알려주세요", "무엇", "어떤",
    "이거", "그거", "저거", "이런", "그런",
}

# 카탈로그에 없는 카테고리를 고객이 콕 집어 물었을 때 LLM 호출 없이 바로 걸러내기
# 위한 카테고리 사전입니다. 실제 카탈로그(catalog.py)에 있는 카테고리는 "가방"뿐이라,
# 이 목록에서 "가방"을 뺀 나머지가 질문에 등장하면 코드 단계에서 곧바로 "없다"고
# 답합니다.
_CATEGORY_TERMS: dict[str, list[str]] = {
    "가방": ["가방", "백", "토트", "숄더", "크로스백", "쇼퍼", "보스턴백"],
    "신발": ["신발", "구두", "부츠", "슈즈", "스니커즈"],
    "아우터": ["코트", "자켓", "재킷", "아우터", "패딩"],
    "니트": ["니트", "스웨터", "가디건"],
    "스카프": ["스카프", "머플러"],
    "액세서리": ["지갑", "벨트", "목걸이", "귀걸이"],
}


def recommendation_system_prompt() -> str:
    return (
        "당신은 시각장애인과 저시력 고객을 돕는 매장 제품 안내인입니다. "
        "아래에 주어지는 '결론'은 이미 코드로 확정된 사실입니다 — 절대 의심하거나 "
        "뒤집거나 다른 결론으로 바꾸지 마세요. 당신의 역할은 그 결론을 감각적이고 "
        "다정한 문장으로 풀어서 전달하는 것뿐입니다. "
        "'결론'에 등장하는 제품이 아닌 다른 제품이나, 목록에 없는 색상·소재·가격은 "
        "절대 언급하거나 지어내지 마세요. "
        "가격은 정가가 아니라 참고 가격이니 '~원 정도예요'처럼 자연스럽게 표현하세요. "
        "결론에 나온 실제 색상에 맞춰 온도감·촉감을 느낄 수 있는 표현을 덧붙이세요 — "
        "결론에 없는 색상 비유를 다른 제품에서 가져와 쓰면 안 됩니다. "
        "점수, 순위, 사무적 표현 없이 다정한 안내인 말투로 말하세요. 소리 내어 읽었을 때 "
        "자연스럽도록 목록이나 기호(-, *, 1. 등) 없이 짧고 명확한 문장 2~4개로 답하세요."
    )


def _extract_keywords(question: str) -> list[str]:
    tokens = re.findall(r"[가-힣]{2,}|[a-zA-Z]{2,}", question)
    return [token for token in tokens if token not in _STOPWORDS]


def _haystack(product: dict[str, Any]) -> str:
    return " ".join(
        [
            product["name"],
            product.get("name_en", ""),
            product["category"],
            product["color"],
            product.get("material", ""),
            product.get("pattern", ""),
            " ".join(product.get("style_tags", [])),
        ]
    ).lower()


def _and_match(keywords: list[str], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(keywords) < 2:
        return []
    return [product for product in candidates if all(kw in _haystack(product) for kw in keywords)]


def find_absent_category(question: str) -> str | None:
    """카탈로그에 아예 없는 카테고리를 고객이 콕 집어 물었으면 그 카테고리명을
    반환합니다. 이 경우는 LLM을 부를 필요 없이 바로 고정 문구로 답합니다."""
    catalog_categories = {product["category"] for product in MOCK_CATALOG}
    for category, terms in _CATEGORY_TERMS.items():
        if category in catalog_categories:
            continue
        if any(term in question for term in terms):
            return category
    return None


def absent_category_response(category: str) -> str:
    return f"지금 안내해드릴 수 있는 {category} 제품은 없어요. 혹시 다른 제품도 궁금하세요?"


def build_candidates(question: str) -> dict[str, list[dict[str, Any]]]:
    keywords = _extract_keywords(question)
    loose_matches = search_catalog(keywords)
    related = loose_matches if loose_matches else MOCK_CATALOG
    exact = _and_match(keywords, related)
    return {"exact": exact, "related": related}


def _format_product(product: dict[str, Any]) -> str:
    material_part = f", 소재는 {product['material']}" if product.get("material") else ""
    price = product.get("price_krw_approx")
    price_part = f", 약 {price:,}원" if price else ""
    return f"{product['name']} ({product['color']}{material_part}{price_part}, {product['description']})"


def build_verdict(candidates: dict[str, list[dict[str, Any]]]) -> str:
    """"있다/없다", "정확히 일치하는가"를 코드에서 확정해 한 문장으로 못박습니다.
    LLM은 이 문장을 논리적으로 바꿀 수 없고, 문장으로 풀어 설명만 합니다."""
    exact = candidates.get("exact") or []
    related = candidates.get("related") or []
    if exact:
        items = "; ".join(_format_product(p) for p in exact)
        return f"고객 질문에 정확히 일치하는 제품이 있습니다: {items}"
    if related:
        items = "; ".join(_format_product(p) for p in related[:3])
        return f"정확히 일치하는 제품은 없지만, 관련 있는 제품이 있습니다: {items}"
    return "안내할 수 있는 제품이 없습니다."


def recommendation_user_text(question: str, candidates: dict[str, list[dict[str, Any]]]) -> str:
    verdict = build_verdict(candidates)
    return (
        f"고객 질문: {question}\n\n"
        f"결론: {verdict}\n\n"
        "위 결론을 그대로 인정하고, 결론에 나온 제품만 근거로 고객에게 자연스럽게 답하세요."
    )
