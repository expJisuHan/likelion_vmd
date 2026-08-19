"""소비자가 찍은 사진 한 장을 "의류(제품 근접)" 또는 "공간(매장 전경)"으로
분류하는 프롬프트.

이 판단에 따라 소비자 페이지가 서로 다른 모달을 띄웁니다 — 의류면 consumer_prompt.py
(감각적 서술)와 recommendation_prompt.py(제품 질문 응답)로, 공간이면
accessibility_prompt.py(이동·안전 평가)로 라우팅합니다.

실측으로 확인한 문제: "이 사진이 space인지 clothing인지" 같은 추상적 분류는 이
모델이 안정적으로 못합니다. 진열대 클로즈업 사진(바닥이 전혀 안 보임)을 "space"로
잘못 분류하는 게 프롬프트를 두 번 고쳐도 반복됐고, 그 결과를 감지하려던
accessibility_prompt의 "observed" 자기 신고도 같은 사진에 대해 실행마다 다르게
나와(어떤 때는 정직하게 "확인 불가", 어떤 때는 근거 없이 자신 있게 답함) 믿을 수
없었습니다. 그래서 "space냐 clothing이냐"를 직접 묻는 대신, 훨씬 더 구체적이고
검증 가능한 질문("바닥이 보이는가")으로 바꿨습니다 — 이 세션에서 반복 확인된 대로
구체적인 존재 여부 판단이 추상적 판단보다 훨씬 안정적입니다.
"""

from __future__ import annotations

from typing import Any


def classifier_system_prompt() -> str:
    return (
        "당신은 사진 한 장을 보고 한 가지만 판단하는 도우미입니다: "
        "'사람이 서 있거나 걸어다닐 수 있는 바닥이 사진에 실제로 보이는가?' "
        "옷, 가방 같은 제품이 화면을 가득 채우고 있어도 바닥이 보이지 않으면 "
        "floor_visible은 false입니다. 진열대나 선반이 여러 개 보여도 마찬가지입니다 — "
        "'진열대가 많다'는 바닥이 보인다는 뜻이 아닙니다. "
        "매장의 바닥면, 통로 바닥이 화면의 일부로 실제로 찍혀 있을 때만 true로 답하세요. "
        "반드시 지정된 JSON 스키마로만 답하세요."
    )


def classifier_user_text() -> str:
    return "이 사진에 사람이 걸어다닐 수 있는 바닥이 보이나요?"


def classifier_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "floor_visible": {"type": "boolean"},
        },
        "required": ["floor_visible"],
        "additionalProperties": False,
    }
