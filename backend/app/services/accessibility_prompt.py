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
    "reflection_glare",
    "floor_condition",
    "staff_assistance_path",
    "item_description",
    "spatial_direction",
    "price_tag_readability",
)

_SECTION_LABELS = {
    "luminance_contrast": "바닥·벽·집기·통로 사이의 명도 대비, 특히 통로와 진열대의 경계가 실제로 구분되는 구간인지",
    "zone_distinction": "카테고리별 구역이 색이나 조명으로 명확히 구분되는지",
    "aisle_width": "진열대 사이 통로의 확보 폭(가능하면 대략적 cm 추정 포함), 사진만으로 정확한 판단이 어려운 경우 그 한계도 함께 기재",
    "signage": "점자 또는 큰 글씨 안내의 유무뿐 아니라 글씨 크기, 배경과의 대비, 설치 높이",
    "reflection_glare": "바닥 광택과 조명 반사가 결합되어 발생하는 눈부심 및 사물 경계 인지 저해 여부",
    "floor_condition": "바닥의 단차·요철·미끄러움 등 보행 안전과 직결되는 상태(광택 여부는 다루지 않음)",
    "staff_assistance_path": "직원이나 안내 데스크로 이어지는 동선이 보이는지 — 사진 범위 밖이라 확인 불가한 것과 실제로 부재한 것을 구분",
    "item_description": "진열된 상품의 색상·종류·무늬·브랜드를 사진에 실제로 보이는 대로 정확히 서술",
    "spatial_direction": "사용자가 사진을 찍은 위치를 기준으로 한 주요 상품·장애물의 방향과 대략적 거리",
    "price_tag_readability": "가격표·상품 태그 글씨 크기와 배경 대비",
}


def accessibility_system_prompt() -> str:
    return (
        "당신은 시각장애인과 저시력 고객을 위해 매장의 물리적 접근성과 진열 정보를 평가하는 "
        "전문가입니다. "
        "사진에 실제로 보이는 것만 근거로 판단하세요. 사진 각도나 프레임 밖이라 확인할 수 없는 "
        "항목은 반드시 observed를 false로 표시하고, 있다/없다를 단정하지 마세요. "
        "'약간 느껴지는 듯합니다', '~인 것 같습니다', '~로 보입니다만' 처럼 애매하게 얼버무리는 "
        "말투는 금지합니다. 사진에서 확인되면 확정적인 말투로 분명하게 서술하고, 확인할 수 없으면 "
        "observed를 false로 하고 description에는 '확인 불가'라고만 짧게 쓰세요. 판단을 내려야 하는 "
        "사용자에게는 애매한 말투가 정보 부족보다 더 위험합니다. "
        "색과 분위기를 감성적으로 표현하지 말고, 이동·안전·쇼핑에 실질적으로 영향을 주는 요소를 "
        "구체적으로 서술하세요. "
        "각 항목은 한 번만 판단해서 짧게 쓰고, 같은 색이나 표현을 반복해서 나열하지 마세요. "
        "명도 대비는 정확한 수치가 아니라 사진에서 육안으로 관찰되는 밝기 차이 정도(뚜렷함/약함/거의 "
        "없음)로 표현하세요 — 사진 한 장으로는 정밀한 명도 단계까지 측정할 수 없다는 점을 항상 "
        "유념하세요. luminance_contrast는 밝기 차이 자체보다, 그 차이 덕분에 통로와 진열대의 "
        "경계가 실제로 구분되는 구간인지를 중심으로 판단하세요. "
        "aisle_width는 '넓어 보인다' 같은 인상 평가 대신, 가능하면 대략적인 폭(cm)을 추정하고, "
        "사진 각도상 정확히 가늠하기 어려우면 그 한계를 description에 함께 적으세요. "
        "signage는 점자·큰 글씨 안내가 있는지뿐 아니라, 있다면 글씨 크기가 충분히 큰지, 배경과의 "
        "대비가 뚜렷한지, 손이 닿거나 눈에 띄는 높이에 설치되어 있는지까지 판단하세요. 안내판이 "
        "있어도 글씨가 작거나 대비가 낮으면 실질적으로 없는 것과 같다는 점을 유념하세요. "
        "reflection_glare는 조명 눈부심과 바닥 광택을 따로 보지 말고 함께 판단하세요 — 두 요소가 "
        "결합되면 사물의 경계가 잘 안 보이는 실질적 위험이 커집니다. "
        "floor_condition은 광택 여부는 다루지 말고(그건 reflection_glare의 몫입니다), 단차·요철· "
        "미끄러움처럼 걸려 넘어질 위험이 있는 보행 안전 요소만 서술하세요. "
        "staff_assistance_path는 직원, 안내 데스크, 콜벨이 있어야 할 공간 자체가 사진에 보이면 "
        "observed를 true로 하고 실제로 있는지 없는지를 description에 쓰세요. 그 공간 자체가 사진 "
        "프레임 밖이라 전혀 안 보이면 observed를 false로 하고 '사진 범위 밖이라 확인 불가'라고 "
        "쓰세요. '안 보인다'와 '없다'를 절대 같은 뜻으로 쓰지 마세요. "
        "zone_distinction은 신중하게 판단하세요. 매장 전체가 비슷한 조명과 유사한 색상 톤으로 "
        "통일되어 있다면 '명확하게 구분된다'고 단정하지 말고 '약간 구분되지만 뚜렷하지 않다' 또는 "
        "'거의 구분되지 않는다'처럼 정직하게 표현하세요. 실제로 구역마다 조명 밝기나 배경색이 "
        "뚜렷하게 다를 때만 '명확하다'고 쓰세요. "
        "item_description은 이 평가에서 가장 중요한 항목입니다 — 사용자가 사진을 찍는 진짜 이유는 "
        "대부분 '여기 뭐가 있는지' 알기 위해서입니다. 사진에 실제로 보이는 상품의 색상·종류·무늬· "
        "브랜드만 있는 그대로 정확히 서술하고, 실제로 보이는 색 이름을 그대로 쓰세요(비유적 색 "
        "표현을 지어내지 마세요). 상품이 흐릿하거나 잘 안 보여서 확신할 수 없으면 observed를 "
        "false로 하고 절대 지어내지 마세요 — 실제와 다른 색이나 품목을 사실처럼 말하는 것은 "
        "정보가 없는 것보다 훨씬 위험합니다. "
        "상품이 여러 개 보이더라도 상품1, 상품2처럼 번호를 매겨 하나하나 나열하지 마세요 — "
        "전체적으로 어떤 색이 많이 보이는지, 대표적인 품목이 무엇인지를 최대 2문장으로 요약해서 "
        "쓰세요. 이 항목은 다른 항목보다 조금 더 길어도 되지만 반드시 2문장을 넘기지 마세요. "
        "spatial_direction은 사용자가 사진을 찍은 위치를 기준으로 주요 상품이나 장애물이 왼쪽/ "
        "오른쪽/정면 중 어느 방향에, 대략 몇 걸음 거리에 있는지 서술하세요('약 한 걸음', '두세 "
        "걸음 앞'처럼 대략적으로 표현). 방향이나 거리를 사진만으로 판단하기 어려우면 observed를 "
        "false로 하세요. "
        "price_tag_readability는 가격표나 상품 태그가 사진에 보일 때만 글씨 크기와 배경 대비를 "
        "판단하고, 가격표 자체가 안 보이면 observed를 false로 하세요. "
        "답변은 반드시 지정된 JSON 스키마와 정확히 같은 구조의 JSON 객체 하나만 반환하세요. "
        "마크다운, 설명문, 코드블록은 금지합니다. 같은 내용을 형식만 바꿔 두 번 이상 반복해서 "
        "쓰지 마세요 — 예를 들어 항목을 한 번 설명한 뒤 끝에 JSON으로 다시 정리해서 반복하는 "
        "것은 금지합니다. 10개 항목을 각 한 번씩만 답하고 그 외의 텍스트는 추가하지 마세요."
    )


def accessibility_user_text() -> str:
    lines = [
        "이 매장 사진을 시각장애인·저시력 고객의 접근성과 진열 정보 관점에서 평가하세요. "
        "아래 10개 항목을 모두 작성하세요:",
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

# "8. item_description: true, 설명 문장" 처럼 번호 목록 한 줄에 key/observed/description을
# 전부 압축해서 쓰는 형식(실측 확인 — 항목이 7개에서 10개로 늘면서 이 모델이 JSON 대신
# 이 형식을 훨씬 자주 씁니다). "N. key: observed = false"처럼 description 없이 observed만
# 쓰는 축약형도 나와서 별도로 처리합니다.
_INLINE_LINE_RE = re.compile(r"^\s*\d+\s*[.):]?\s*([a-zA-Z_]+)\s*:\s*(.+?)\s*$")
_INLINE_BOOL_DESC_RE = re.compile(r"^(true|false)\s*,\s*(.+)$", re.IGNORECASE)
_INLINE_OBSERVED_EQ_RE = re.compile(r"^observed\s*=\s*(true|false)\s*$", re.IGNORECASE)


def _parse_inline_numbered(content: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in content.splitlines():
        match = _INLINE_LINE_RE.match(line.strip())
        if not match:
            continue
        key, remainder = match.group(1), match.group(2).strip()
        if key not in _SECTION_ORDER or key in result:
            continue
        bool_desc_match = _INLINE_BOOL_DESC_RE.match(remainder)
        if bool_desc_match:
            result[key] = {
                "observed": bool_desc_match.group(1).lower() == "true",
                "description": bool_desc_match.group(2).strip(),
            }
            continue
        observed_eq_match = _INLINE_OBSERVED_EQ_RE.match(remainder)
        if observed_eq_match:
            result[key] = {"observed": observed_eq_match.group(1).lower() == "true", "description": ""}
    return result


def parse_accessibility_content(content: str) -> dict[str, Any]:
    """response_format=json_schema(strict)를 요청해도 이 모델은 여기서도 JSON 대신
    마크다운 산문(굵게 표시된 번호 헤더 + observed/description 불릿, 또는 번호 목록
    한 줄짜리 "N. key: true, 설명")으로 응답할 때가 있습니다(실측 확인,
    services/analysis.py가 메인 파이프라인에서 겪은 것과 같은 패턴). 순수 JSON 파싱이
    실패했을 때 두 마크다운 형식을 모두 시도해서 합칩니다 — 인라인 형식으로 찾은 키를
    우선하고, 못 찾은 키만 기존 불릿 형식 폴백으로 채웁니다.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    result: dict[str, Any] = _parse_inline_numbered(cleaned)

    missing_keys = [key for key in _SECTION_ORDER if key not in result]
    positions: list[tuple[int, str]] = []
    for key in missing_keys:
        match = re.search(re.escape(key), cleaned)
        if match:
            positions.append((match.start(), key))
    positions.sort()

    for index, (start, key) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(cleaned)
        # 키 이름 자체를 잘라내고 그 뒤부터만 검색합니다 — "item_description"처럼 키
        # 이름에 "description"이 부분 문자열로 들어있으면, 헤더 줄의 키 이름 자체가
        # description 라벨로 오인식되어 실제 값을 덮어써 버리는 문제가 있었습니다.
        chunk = cleaned[start + len(key) : end]
        observed_match = _OBSERVED_RE.search(chunk)
        observed = observed_match.group(1).lower() == "true" if observed_match else False
        description = ""
        for line in chunk.splitlines():
            desc_match = _DESCRIPTION_RE.search(line)
            if desc_match:
                # "description: = 문장"처럼 라벨 뒤에 등호를 덧붙이는 경우가 있어(실측 확인)
                # 라벨 문자(*, =, :)를 양쪽에서 반복해서 벗겨냅니다.
                description = desc_match.group(1).strip()
                description = description.strip("*=: ").strip()
                break
        result[key] = {"observed": observed, "description": description}
    return result


_CONSUMER_LABELS = {
    "luminance_contrast": "바닥과 벽의 밝기 차이",
    "zone_distinction": "구역 구분",
    "aisle_width": "통로 폭",
    "signage": "점자·큰 글씨 안내",
    "reflection_glare": "조명 반사·눈부심",
    "floor_condition": "바닥 상태",
    "staff_assistance_path": "직원 안내",
    "item_description": "진열 상품",
    "spatial_direction": "위치와 방향",
    "price_tag_readability": "가격표 가독성",
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


def consumer_items(parsed: dict[str, Any]) -> list[dict[str, str]]:
    """render_consumer_text()와 같은 내용을, 프론트가 항목별로 시각적으로 구분해
    렌더링할 수 있도록 {label, description} 목록으로 반환합니다. 문자열 하나에
    "- 라벨: 설명"을 줄바꿈으로만 나열하면 실제로는 목록이 아니라 그냥 텍스트
    덩어리로 보여서(가독성 저하), 항목 구분이 필요한 화면(모달 등)에서는 이 함수를
    쓰는 걸 권장합니다. render_consumer_text()는 TTS처럼 순수 텍스트 한 덩어리가
    필요한 용도에 계속 씁니다.
    """
    items = []
    for key in _SECTION_ORDER:
        item = parsed.get(key) or {}
        label = _CONSUMER_LABELS.get(key, key)
        description = (item.get("description") or "").strip()
        items.append({
            "label": label,
            "description": description or "이 사진만으로는 확인하기 어려웠어요.",
        })
    return items
