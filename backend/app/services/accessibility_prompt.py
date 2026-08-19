"""시각장애인·저시력 고객을 위한 매장 물리적 접근성 평가 프롬프트.

기존 VMD 진단(services/prompt.py)은 진열의 상품성(레이아웃, 색조화, 브랜드 적합성)만
평가하고, 명도 대비·통로 폭·점자 안내·조명 눈부심·바닥 단차 같은 물리적 접근성 요소는
전혀 다루지 않습니다. 이 모듈은 같은 사진을 접근성 관점에서 다시 평가하기 위한 별도의
Vision-LLM 호출용 프롬프트입니다(services/consumer_prompt.py처럼 기존 결과를 텍스트로
재서술하는 게 아니라, 이미지를 다시 봐야 하는 새로운 평가축입니다).

사진 한 장으로는 정밀한 명도 수치나 서비스 프로세스(직원 응대)를 측정할 수 없으므로,
항목마다 "사진에서 실제로 확인 가능한지"를 observed 필드로 스키마에 강제합니다. 프롬프트
지시("모르면 모른다고 답하라")만으로는 작은 모델이 안정적으로 지키지 못하는 걸 이미
확인했기 때문에(consumer_prompt.py의 has_sufficient_content 참고), 확인 불가 상태 자체를
빈 문자열이 아니라 별도 boolean으로 만들어 후처리에서도 걸러낼 수 있게 합니다.
"""

from __future__ import annotations

import json
import re
from typing import Any

_SECTION_ORDER = (
    "luminance_contrast",
    "zone_distinction",
    "aisle_width",
    "signage",
    "lighting_glare",
    "floor_condition",
    "staff_assistance_path",
)

_SECTION_LABELS = {
    "luminance_contrast": "바닥·벽·집기·통로 사이의 명도(밝기) 대비",
    "zone_distinction": "카테고리별 구역이 색이나 조명으로 명확히 구분되는지",
    "aisle_width": "진열대 사이 통로가 충분히 확보되어 촉각적으로도 인지 가능한 폭인지",
    "signage": "점자 또는 큰 글씨 안내 표시가 보이는지",
    "lighting_glare": "조명으로 인한 눈부심이나 강한 반사가 있는지",
    "floor_condition": "바닥 재질과 단차(높이 변화) 여부",
    "staff_assistance_path": "직원이나 안내 데스크로 이어지는 동선이 보이는지",
}


def accessibility_system_prompt() -> str:
    return (
        "당신은 시각장애인과 저시력 고객을 위해 매장의 물리적 접근성을 평가하는 전문가입니다. "
        "사진에 실제로 보이는 것만 근거로 판단하세요. 사진 각도나 프레임 밖이라 확인할 수 없는 "
        "항목은 반드시 observed를 false로 표시하고, 있다/없다를 단정하지 마세요. "
        "색과 분위기를 감성적으로 표현하지 말고, 이동과 안전에 실질적으로 영향을 주는 요소를 "
        "구체적으로 서술하세요. "
        "각 항목은 한 번만 판단해서 짧게 쓰고, 같은 색이나 표현을 반복해서 나열하지 마세요. "
        "명도 대비는 정확한 수치가 아니라 사진에서 육안으로 관찰되는 밝기 차이 정도(뚜렷함/약함/거의 "
        "없음)로 표현하세요 — 사진 한 장으로는 정밀한 명도 단계까지 측정할 수 없다는 점을 항상 "
        "유념하세요. "
        "staff_assistance_path는 사진에 직원, 안내 데스크, 콜벨 등이 실제로 보이지 않으면 반드시 "
        "observed를 false로 표시하세요. 이 항목은 서비스 영역이라 사진만으로는 대부분 판단할 수 "
        "없습니다. "
        "zone_distinction은 신중하게 판단하세요. 매장 전체가 비슷한 조명과 유사한 색상 톤으로 "
        "통일되어 있다면 '명확하게 구분된다'고 단정하지 말고 '약간 구분되지만 뚜렷하지 않다' 또는 "
        "'거의 구분되지 않는다'처럼 정직하게 표현하세요. 실제로 구역마다 조명 밝기나 배경색이 "
        "뚜렷하게 다를 때만 '명확하다'고 쓰세요. "
        "답변은 반드시 지정된 JSON 스키마와 정확히 같은 구조의 JSON 객체 하나만 반환하세요. "
        "마크다운, 설명문, 코드블록은 금지합니다."
    )


def accessibility_user_text() -> str:
    lines = [
        "이 매장 사진을 시각장애인·저시력 고객의 접근성 관점에서 평가하세요. "
        "아래 7개 항목을 모두 작성하세요:",
    ]
    for index, key in enumerate(_SECTION_ORDER, start=1):
        lines.append(f"{index}. {key}: {_SECTION_LABELS[key]}")
    lines.append(
        "각 항목마다 observed(사진에서 실제로 판단 가능하면 true, 확인할 수 없으면 false)와 "
        "description(관찰 내용 또는 확인 불가 사유)을 작성하세요. "
        "description은 반드시 1문장, 40자 이내로 짧고 간결하게 쓰세요. 같은 표현이나 색상 비교를 "
        "여러 번 반복하지 말고, 한 번만 명확하게 판단해서 쓰세요."
    )
    return "\n".join(lines)


def accessibility_json_schema() -> dict[str, Any]:
    def item_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "observed": {"type": "boolean"},
                "description": {"type": "string"},
            },
            "required": ["observed", "description"],
            "additionalProperties": False,
        }

    return {
        "type": "object",
        "properties": {key: item_schema() for key in _SECTION_ORDER},
        "required": list(_SECTION_ORDER),
        "additionalProperties": False,
    }


_OBSERVED_RE = re.compile(r"observed\s*:\s*\**\s*(true|false)", re.IGNORECASE)
_DESCRIPTION_RE = re.compile(r"description\s*:?\s*\**\s*:?\s*(.+)", re.IGNORECASE)


def parse_accessibility_content(content: str) -> dict[str, Any]:
    """response_format=json_schema(strict)를 요청해도 이 모델은 여기서도 JSON 대신
    마크다운 산문(굵게 표시된 번호 헤더 + observed/description 불릿)으로 응답할 때가
    있습니다(실측 확인, services/analysis.py가 메인 파이프라인에서 겪은 것과 같은 패턴).
    순수 JSON 파싱이 실패했을 때만 이 마크다운 폴백을 시도합니다.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    positions: list[tuple[int, str]] = []
    for key in _SECTION_ORDER:
        match = re.search(re.escape(key), cleaned)
        if match:
            positions.append((match.start(), key))
    positions.sort()

    result: dict[str, Any] = {}
    for index, (start, key) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(cleaned)
        chunk = cleaned[start:end]
        observed_match = _OBSERVED_RE.search(chunk)
        observed = observed_match.group(1).lower() == "true" if observed_match else False
        description = ""
        for line in chunk.splitlines():
            desc_match = _DESCRIPTION_RE.search(line)
            if desc_match:
                description = desc_match.group(1).strip().strip("*").strip()
                break
        result[key] = {"observed": observed, "description": description}
    return result


_CONSUMER_LABELS = {
    "luminance_contrast": "바닥과 벽의 밝기 차이",
    "zone_distinction": "구역 구분",
    "aisle_width": "통로 폭",
    "signage": "점자·큰 글씨 안내",
    "lighting_glare": "조명 눈부심",
    "floor_condition": "바닥 상태",
    "staff_assistance_path": "직원 안내",
}


def render_consumer_text(parsed: dict[str, Any]) -> str:
    """접근성 평가 결과를 소비자가 바로 읽거나 들을 수 있는 문자열로 변환합니다.

    consumer_prompt.py의 감각적 서술(장점만 전달)과 달리, 이 내용은 이동·안전에 관한
    사실 정보이므로 부정적인 내용도 감추지 않고 그대로 전달합니다.

    observed는 "사진에 그 대상 자체가 안 보임"(signage, staff_assistance_path)과
    "정도를 판단하기엔 근거가 약함"(zone_distinction, luminance_contrast 등)을 모델이
    구분 없이 같은 필드로 씁니다(실측 확인) — 그래서 description이 이미 실제 판단
    문장을 담고 있을 때 observed만 보고 "확인 불가"로 바꿔치기하면 있는 정보를
    지우게 됩니다. description이 있으면 그 문장을 그대로 보여주고, description
    자체가 비어 있을 때만 "확인하기 어려웠다"는 문구로 대신합니다.
    """
    lines = ["매장 접근성을 살펴본 결과예요."]
    for key in _SECTION_ORDER:
        item = parsed.get(key) or {}
        label = _CONSUMER_LABELS.get(key, key)
        description = (item.get("description") or "").strip()
        if description:
            lines.append(f"- {label}: {description}")
        else:
            lines.append(f"- {label}: 이 사진만으로는 확인하기 어려웠어요.")
    return "\n".join(lines)
