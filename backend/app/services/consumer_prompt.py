"""저시력·시각장애 고객을 위한 감각적 서술 프롬프트.

내부 VMD 진단(services/prompt.py)은 매장 직원을 위한 평가자 언어(점수, 문제점, 개선안)로
짜여 있어 고객에게 그대로 노출하면 브랜드 톤을 해칩니다. 이 모듈은 이미 계산된 분석
결과 중 고객에게 안전한 항목(positive_points, 평가항목의 evidence, 마네킹 연출 설명)만
골라 프롬프트에 실어, critical_issues/improvement_suggestions/obstacles/photo_quality/
점수류는 애초에 모델 입력에 존재하지 않도록 원천 차단합니다.

final_summary는 프롬프트 입력에서 의도적으로 뺐습니다 — services/prompt.py의 지시상
"현재 상태와 우선순위를 종합"하는 필드라 구조적으로 비판 내용을 포함하고, 실측 결과
positive_points/criteria_evaluations.evidence에도 "그러나 ~ 무난합니다"처럼 긍정 서술
뒤에 비판이 붙는 패턴이 실제로 나타났습니다(실측 확인). 프롬프트 지시("문제점은
언급하지 마라")만으로는 작은 모델이 안정적으로 걸러내지 못하는 걸 확인했기 때문에,
_positive_clause()가 "그러나/다만/하지만/그런데" 이후를 코드에서 아예 잘라내는
방식으로 한 번 더 막습니다.

이미지를 다시 보내지 않고 이미 있는 텍스트만 넘기므로 NIM 호출이 가볍고 빠르며,
구조화된 JSON이 아니라 자연스러운 문장 하나만 필요해 response_format 없이 일반
채팅 완성으로 충분합니다.
"""

from __future__ import annotations

import re
from typing import Any

# 실측 결과 이 모델은 긍정 서술 뒤에 이 접속어들로 비판·유보를 붙이는 패턴을 반복해서
# 보였습니다("...유지하고 있습니다. 그러나, 전체적으로 약간 무난하고..."). 프롬프트
# 지시만으로는 안정적으로 안 걸러져서, 접속어 이후 내용을 코드에서 잘라냅니다.
_HEDGE_MARKER_RE = re.compile(r"(그러나|다만|하지만|그런데)")


def consumer_system_prompt() -> str:
    return (
        "당신은 저시력 고객과 시각장애 고객에게 매장 진열을 다정하게 설명해주는 안내인입니다. "
        "전문 평가자가 아니라, 고객 옆에서 지금 눈앞의 모습을 말로 그려주는 사람처럼 이야기하세요. "
        "이 진열의 장점과 매력만 이야기하세요 — 부족한 점, 문제점, 개선할 점은 절대 언급하지 마세요. "
        "'무난하다', '보통이다', '괜찮은 편이다', '나쁘지 않다'처럼 애매하고 모호한 표현은 "
        "절대 쓰지 마세요. 대신 색감과 분위기를 중심 내용으로 삼아 구체적이고 생생하게 설명하세요. "
        "색을 말할 때는 색 이름만 말하지 말고, 온도감(따뜻한/차가운), 촉감(부드러운/까슬한), "
        "익숙한 사물이나 자연물에 빗댄 표현을 곁들이세요. 예: '베이지색'이 아니라 "
        "'따뜻한 모래빛'. 분위기도 '아늑하다', '생기 있다', '차분하다'처럼 구체적인 무드 "
        "언어로 표현하세요. "
        "점수, 등급, '적합성이 높다', '일관성을 유지한다' 같은 평가자 언어나 사무적 표현도 "
        "쓰지 말고, 색과 분위기 중심의 묘사로 풀어서 말하세요. "
        "제공된 내용에 없는 사실(가격, 소재, 정확한 치수, 재고 등)은 절대 지어내지 말고, "
        "모르면 그 부분은 그냥 언급하지 말고 넘어가세요. "
        "문장은 소리 내어 읽었을 때 자연스럽도록 짧고 명확하게 쓰고, 목록이나 기호(-, *, 1. 등)는 "
        "쓰지 마세요. 전체 분량은 소리 내어 읽었을 때 30~45초 정도(4~6문장)로 맞추세요. "
        "존댓말을 쓰고, 구매를 재촉하는 표현 없이 자연스럽게 설명하세요."
    )


def _positive_clause(text: str) -> str:
    """'그러나/다만/하지만/그런데' 이후에 이어지는 비판·유보 내용을 잘라내고 앞부분만 남깁니다."""
    text = (text or "").strip()
    match = _HEDGE_MARKER_RE.search(text)
    if match:
        text = text[: match.start()]
    return text.strip().rstrip(".,;:").strip()


def _safe_evidence_lines(result: dict[str, Any]) -> list[str]:
    criteria = result.get("criteria_evaluations")
    if not isinstance(criteria, list):
        return []
    lines: list[str] = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        evidence = _positive_clause(item.get("evidence") or "")
        if evidence:
            lines.append(evidence)
    return lines


def _safe_positive_points(result: dict[str, Any]) -> list[str]:
    raw_points = result.get("positive_points") or []
    points = [_positive_clause(p) for p in raw_points if isinstance(p, str)]
    return [p for p in points if p]


def _safe_mannequin_comment(result: dict[str, Any]) -> str:
    mannequin = result.get("mannequin")
    if not isinstance(mannequin, dict):
        return ""
    return _positive_clause(mannequin.get("comment") or "")


def has_sufficient_content(result: dict[str, Any]) -> bool:
    """LLM 호출 전에 실제로 서술할 내용이 남아 있는지 확인합니다.

    내용이 부족한데도 호출하면 모델이 없는 매장 풍경(가방, 신발 등)을 통째로
    지어내는 걸 실측으로 확인했습니다. "지어내지 마라"는 프롬프트 지시보다,
    호출 자체를 막는 쪽이 훨씬 안전합니다.
    """
    return bool(_safe_positive_points(result) or _safe_evidence_lines(result) or _safe_mannequin_comment(result))


def consumer_user_text(result: dict[str, Any]) -> str:
    positive_points = _safe_positive_points(result)
    evidence_lines = _safe_evidence_lines(result)
    mannequin_comment = _safe_mannequin_comment(result)

    parts = [
        "아래는 매장 진열을 분석해 얻은 관찰 내용입니다. "
        "이 안에 있는 사실만 근거로, 색감과 분위기를 중심으로 감각적인 문장으로 다시 설명해 주세요.",
    ]
    if positive_points:
        parts.append("눈에 띄는 점: " + " / ".join(positive_points))
    if evidence_lines:
        parts.append("세부 관찰: " + " / ".join(evidence_lines))
    if mannequin_comment:
        parts.append(f"마네킹 연출: {mannequin_comment}")
    if len(parts) == 1:
        parts.append("구체적인 관찰 내용이 부족합니다. 무리해서 지어내지 말고, 짧고 담백한 안내 문구만 작성하세요.")
    return "\n".join(parts)
