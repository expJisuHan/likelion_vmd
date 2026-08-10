"""VMD 존(IP/PP/VP) 정의와 등급 산정 로직."""

from __future__ import annotations

from typing import Any

ZONE_CRITERIA: dict[str, list[str]] = {
    "VP": [
        "연출 콘셉트의 시각적 일관성",
        "시각적 핵심 상품의 가시성과 강조도",
        "포컬 포인트 및 시선 유도",
        "구성·비례·여백의 균형",
        "색채·조명·소품의 조화",
    ],
    "IP": [
        "상품 분류 및 구획의 명확성",
        "컬러 배열의 규칙성과 연속성",
        "사이즈 배열의 정확성",
        "상품 비교 및 선택 편의성",
        "진열 수량과 공간 점유의 적절성",
        "행거 간 간격 및 페이싱·진열 정돈 상태",
    ],
    "PP": [
        "핵심 제안 상품의 차별화와 위계",
        "상품 그룹화 및 연계 제안의 명확성",
        "페이스아웃과 상품 특징 노출",
        "진열 밀도와 공간 점유의 적절성",
        "상품 간격·방향·배열선의 정돈",
        "POP·가격·프로모션 정보의 연결성과 가독성",
    ],
}


def normalize_zone(value: str | None) -> str:
    value = (value or "VP").upper().strip()
    return value if value in {"VP", "PP", "IP"} else "VP"


def grade_from_score(score: Any) -> str:
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return "평가 보류"
    if numeric >= 90:
        return "매우 우수"
    if numeric >= 80:
        return "우수"
    if numeric >= 70:
        return "보통"
    if numeric >= 60:
        return "개선 필요"
    return "집중 개선"


def criteria_for_zone(zone: str | None) -> list[str]:
    return ZONE_CRITERIA[normalize_zone(zone)]
