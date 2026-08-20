"""저시력·시각장애 고객을 위한 매장 사진 통합 서술 프롬프트.

가장 처음 설계는 1차로 매장 직원용 VMD 진단(services/prompt.py)을 이미지로
돌린 뒤, 그 결과 텍스트만 2차 호출에 넘겨 감각적 문장으로 "재서술"하는 2단계
구조였습니다. 2차 호출이 이미지를 못 보니 1차 분석이 애초에 안 뽑은 정보는
나올 수 없었고, "다양한 OO가 있어 원하는 OO를 찾을 수 있다"처럼 주제만 바꿔
같은 문장 구조를 반복하는 안내 방송체로 흘렀습니다(실측 확인 — 사용자가
직접 지적).

이미지를 직접 보고 사실을 추출하는 자유 문장 프롬프트로 바꿔도 문제가
남았습니다 — 사진에 진열대가 여러 칸/여러 품목으로 보이면 "하나만 골라
말하라"고 아무리 강하게 지시해도 이 모델은 선반마다·품목마다 번호를 매겨
전부 훑는 경향을 반복했습니다(실측 확인, 3차례 시도 모두 재발). 자유
문장에서는 "몇 문단을 쓸지" 자체가 모델 판단이라 지시가 잘 안 먹혔습니다.

그래서 accessibility_prompt.py와 같은 원리로 "몇 개를 말할지"를 모델이
정하지 못하게 JSON 스키마로 필드 개수를 고정합니다. 필드 개수 자체가 구조를
강제하고, 최종 문장은 코드에서 조립합니다(recommendation_prompt.py의
build_verdict()와 같이, 어떤 필드를 생략할지·어떤 순서로 이을지는 모델이
아니라 코드가 결정합니다).

한때는 품목 정보(item_type/color_pattern_count/brand/position)에 이동
안전·구역 구분 같은 매장 접근성 항목(luminance_contrast/aisle_width/
floor_condition/glare/zone_distinction)까지 9필드로 묶어 함께 서술했지만,
그 항목들은 accessibility_prompt.py(매장 사진 안내)가 이미 다루는 내용과
겹쳐서 "의류 안내"와 "매장 안내"의 경계가 흐려진다는 문제가 있었습니다
(사용자 피드백). 그래서 이 파일은 사진 속 한 품목을 식별하는 정보
(item_type/color_pattern_count/brand/position) 4필드만 다루고, 이동 안전·
구역 구분 등 매장 공간 전체에 대한 사실은 accessibility_prompt.py 쪽에만
맡깁니다.
"""

from __future__ import annotations

import json
import re
from typing import Any

_EMPTY_MARKERS = {"", "확인 불가", "확인불가", "없음", "모름", "알 수 없음", "미상", "해당 없음"}


def _josa(word: str, with_batchim: str, without_batchim: str) -> str:
    """한글 음절의 마지막 글자에 받침이 있는지로 조사를 고릅니다(예: 이/가, 은/는).
    "니트이(가)"처럼 표기용 괄호 병기를 그대로 음성 문장에 쓰면 어색해서, 코드에서
    직접 골라 자연스러운 문장을 만듭니다."""
    if not word:
        return without_batchim
    code = ord(word[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return with_batchim if code % 28 != 0 else without_batchim
    return with_batchim


def consumer_system_prompt() -> str:
    return (
        "당신은 시각장애인·저시력 고객 바로 옆에 서서, 지금 이 사람이 촬영한 "
        "사진을 이 사람 한 명에게 직접 설명해주는 접근성 안내 도우미입니다. "
        "불특정 다수를 향한 홍보 문구가 아니라, 지금 이 사진을 보고 있는 한 "
        "사람에게 답한다고 생각하고 서술하세요. "
        "\n\n"
        "[절대 규칙 — 하나라도 어기면 안 됨]\n"
        "1. 사진에 실제로 보이는 것만 서술하세요. 사진에 없는 색·형태·분위기를 "
        "추측하거나 지어내지 마세요. "
        "2. '아름답다', '매력적이다', '분위기가 좋다', '자연의 따뜻함을 느끼게 "
        "한다', '부드러운 촉감이 가득하다'처럼 주관적 감상·미사여구는 어느 "
        "필드에도 쓰지 마세요. "
        "3. '여러분', '고객님들께', '저희 매장은 ~합니다', '~도와드리겠습니다' "
        "같은 광고성·안내방송 어투는 쓰지 마세요. "
        "4. '다양한'이라는 표현은 사진에서 실제로 보이는 색상·형태 이름과 "
        "개수를 함께 밝힐 때만 쓰세요. 이름과 개수를 구체적으로 밝힐 수 없다면 "
        "이 표현 자체를 쓰지 마세요. "
        "5. 같은 문장 구조나 표현을 두 번 이상 반복하지 마세요. "
        "6. 확실하지 않은 정보는 '~인 듯하다', '~처럼 보인다' 대신 각 필드에 "
        "빈 문자열을 넣거나 '확인 불가'라고 명확히 쓰세요. "
        "\n\n"
        "[필드 — item_type/color_pattern_count/brand/position 모두 사진에 여러 "
        "품목·구역이 보이더라도 그중 가장 가까이 있거나 눈에 띄는 딱 하나만 "
        "골라 채우세요. 나머지 품목·구역은 무시하세요. 이동 안전·통로·바닥 "
        "상태 같은 매장 접근성 정보는 이 안내의 대상이 아니니 어떤 필드에도 "
        "쓰지 마세요.]\n"
        "item_type: 고른 그 품목이 사진에서 실제로 무엇인지 나타내는 명사 "
        "딱 하나만, 사진에서 직접 관찰한 대로 쓰세요. 쉼표나 '와/과/그리고'로 여러 "
        "품목을 이어 쓰지 마세요."
        "color_pattern_count: 그 하나의 품목에서 실제로 보이는 색상·무늬 "
        "종류마다, 사진에서 셀 수 있는 만큼의 개수를 함께 쓰세요. 개수를 셀 "
        "수 없으면 색상·무늬 이름만 쓰고 개수는 넣지 마세요. 다른 품목의 "
        "색은 포함하지 마세요. 형식 예시(아래와 똑같은 색·개수를 쓰라는 뜻이 "
        "아니라, 이런 형태로 실제 관찰값을 채우라는 뜻입니다): 검정색 1개 / "
        "베이지색 2개, 갈색 1개 / 빨간색 3벌 / 네이비 1개, 흰색 2개 / 카키색 "
        "1벌 / 회색 2켤레 / 노란색 1개, 초록색 1개, 파란색 1개 / 핑크색 4개 / "
        "은색 1개 / 체크무늬 2벌. "
        "brand: 그 품목에서 실제로 보이는 브랜드명·로고. 안 보이면 빈 문자열. "
        "position: 촬영자 기준 왼쪽/오른쪽/정면 중 하나와, 눈높이인지 손이 "
        "닿기 어려운 높이인지를 한 구절로. 몇 걸음·몇 미터 같은 거리 추정치는 "
        "사진만으로는 부정확하니 쓰지 마세요. "
        "\n\n"
        "모든 필드는 쉼표나 세미콜론으로 서로 다른 품목·구역을 여러 개 나열 "
        "하지 말고, 한 문장 이내의 짧은 구절 하나로만 쓰세요(color_pattern_count "
        "안에서 같은 품목의 색상별 개수를 나열하는 것은 허용). "
        "'쇼핑을 즐기세요', '즐거운 쇼핑 되세요' 같은 마무리 인사는 어느 "
        "필드에도 넣지 마세요. "
        "답변은 반드시 지정된 JSON 스키마와 정확히 같은 구조의 JSON 객체 하나만 "
        "반환하세요. 마크다운, 설명문, 코드블록, 목록은 금지합니다."
    )


def consumer_user_text() -> str:
    return (
        "이 사진을 시각장애인·저시력 고객에게 설명하세요. 사진 속 하나의 "
        "품목·구역만 골라 상품 정보를 채우세요. "
        "확인할 수 없는 항목은 지어내지 말고 빈 문자열로 두세요."
    )


_FIELD_ORDER = (
    "item_type",
    "color_pattern_count",
    "brand",
    "position",
)


def consumer_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {key: {"type": "string"} for key in _FIELD_ORDER},
        "required": list(_FIELD_ORDER),
        "additionalProperties": False,
    }


_FIELD_LINE_RE = re.compile(
    r"(" + "|".join(_FIELD_ORDER) + r")\s*[:：=]\s*\**\s*(.+)", re.IGNORECASE
)

# ": 왼쪽" 처럼 값에 따옴표가 빠진 경우만 골라 따옴표를 채웁니다. 이미 따옴표로 시작하는
# 값(정상 문자열), 중첩 객체/배열, true/false/null, 숫자는 건드리지 않습니다.
_BARE_VALUE_RE = re.compile(r'(:\s*)([^"\s{}\[\],][^,}\]]*)')


def _quote_bare_values(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix, value = match.group(1), match.group(2).strip()
        if not value or value[0] in '"{[' or value in {"true", "false", "null"}:
            return match.group(0)
        if re.match(r"^-?\d+(\.\d+)?$", value):
            return match.group(0)
        return f'{prefix}"{value}"'

    return _BARE_VALUE_RE.sub(repl, text)


RAW_PROSE_KEY = "_raw_prose"

# 모델이 자기 답변 자체에 대해 코멘트하는 문장(실제 관찰 내용이 아님)만 걸러냅니다.
_META_COMMENTARY_RE = re.compile(
    r"(설명하지 않았으므로|정보는 제공되지 않았습니다|언급하지 않았습니다|"
    r"이상입니다|이상으로 설명을 마칩니다|쇼핑을 즐기세요|즐거운 쇼핑|"
    r"빈 문자열|필드에|json|스키마)",
    re.IGNORECASE,
)


def _clean_raw_prose(text: str) -> str:
    # 자연스러운 문단으로 다 답해놓고 끝에 같은 내용을 JSON으로 한 번 더
    # 붙이는 경우가 실측으로 확인됐습니다(중복 응답). "{"가 나오는 지점부터는
    # 문장이 아니라 그 JSON 덩어리이므로 통째로 버립니다.
    brace_index = text.find("{")
    if brace_index != -1:
        text = text[:brace_index]
    # 마크다운 코드블록(```)이 문단 끝에 덩그러니 남는 경우도 실측으로
    # 확인됐습니다 — 문장이 아니라 서식 잔재이므로 통째로 제거합니다.
    text = text.replace("```", "")
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    kept = [s.strip() for s in sentences if s.strip() and not _META_COMMENTARY_RE.search(s)]
    return " ".join(kept)


def parse_consumer_content(content: str) -> dict[str, str]:
    """response_format=json_schema(strict)를 요청해도 이 모델은 마크다운 목록으로
    답할 때가 있습니다(실측 확인, accessibility_prompt.py와 같은 패턴). 더 흔한 경우는
    JSON 키는 정확히 쓰면서 값 하나만 따옴표를 빼먹는 것입니다(예: "position": 왼쪽,
    실측 확인) — 이건 온전한 JSON이 아니라서 파싱이 실패하지만, 형태는 거의 JSON이라
    따옴표만 채워 넣으면 복구됩니다. JSON 파싱과 복구가 모두 실패하면 "key: value"
    줄 단위로 값을 회수합니다."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    for candidate in (cleaned, _quote_bare_values(cleaned)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return {key: str(parsed.get(key, "") or "").strip() for key in _FIELD_ORDER}
        except json.JSONDecodeError:
            continue

    result = {key: "" for key in _FIELD_ORDER}
    for line in cleaned.splitlines():
        match = _FIELD_LINE_RE.search(line)
        if match:
            key = match.group(1).lower()
            value = match.group(2).strip().strip("*\"'").strip()
            if key in result and not result[key]:
                result[key] = value

    # 필드가 여러 개로 늘면서, 이 모델이 JSON도 "key: value" 형식도 아니라 그냥
    # 자연스러운 문단으로 통째로 답하는 경우가 실측으로 확인됐습니다. 내용
    # 자체는 규칙(사실만·반복 금지·확인불가 명시)을 잘 지켜서 나쁘지 않았기
    # 때문에, 필드를 하나도 못 건졌을 때는 이 문단을 다듬어서 그대로 씁니다.
    if not any(result.values()):
        result[RAW_PROSE_KEY] = _clean_raw_prose(cleaned)
    return result


# 필드가 파싱 폴백을 거치면서 JSON 구문 조각("}", 남은 따옴표 등)이 값 안에
# 그대로 남는 경우가 실측으로 확인됐습니다("가격은 }입니다." 같은 결과). 어느
# 파싱 경로를 거쳤든 문장에 쓰기 전에 여기서 한 번 더 걸러냅니다.
_STRAY_JSON_CHARS_RE = re.compile(r'^[\s"{}\[\],:]+|[\s"{}\[\],:]+$')


def _get_field(fields: dict[str, str], key: str) -> str:
    value = fields.get(key, "").strip()
    value = _STRAY_JSON_CHARS_RE.sub("", value).strip()
    return "" if value in _EMPTY_MARKERS else value


# position에서 방향·높이만 남기고 거리 추정치는 제거합니다. 프롬프트에서 거리를
# 묻지 않도록 바꿔도 이 모델은 종종 "약 1미터 떨어진 곳" 같은 표현을 넣길래(실측
# 확인 — 사진만으로 추정한 거리라 부정확할 위험이 큼) 파싱 단계에서 한 번 더
# 걸러냅니다.
_DISTANCE_RE = re.compile(
    r"(?:약\s*)?\d+(?:[~\-]\d+)?\s*(?:미터|m\b|걸음|보)\s*(?:정도|가량)?\s*"
    r"(?:떨어진\s*(?:곳|거리)?(?:에서|에)?)?\s*"
)


def _strip_distance(text: str) -> str:
    stripped = _DISTANCE_RE.sub("", text)
    stripped = re.sub(r"\s*,\s*,\s*", ", ", stripped)
    stripped = re.sub(r"^[,\s]+|[,\s]+$", "", stripped)
    return stripped.strip()


def _product_sentences(fields: dict[str, str]) -> list[str]:
    """상품 정보(품목/색상·무늬/브랜드/위치) 문장들을 만듭니다."""
    item_type = _get_field(fields, "item_type")
    color_pattern_count = _get_field(fields, "color_pattern_count")
    brand = _get_field(fields, "brand")
    position = _strip_distance(_get_field(fields, "position"))

    sentences: list[str] = []

    # position은 "왼쪽" 같은 짧은 구절이어야 하지만, 실측 결과 이 모델이 가끔
    # 마침표로 끝나는 완전한 문장을 넣습니다("...높이입니다."). 그대로 "{position}에
    # {item_type}"로 이어붙이면 "...높이입니다.에 니트가"처럼 문장이 깨지므로,
    # 문장부호로 끝나는 경우는 이어붙이지 말고 별도 문장으로 앞에 둡니다.
    if position and position[-1] in ".!?":
        sentences.append(position)
        position = ""

    if item_type:
        lead = f"{position}에 {item_type}" if position else item_type
        josa = _josa(item_type, "이", "가")
        if color_pattern_count:
            sentences.append(f"{lead}{josa} 있습니다. {color_pattern_count}입니다.")
        else:
            sentences.append(f"{lead}{josa} 있습니다.")
        if brand:
            sentences.append(f"브랜드는 {brand}입니다.")
    elif position:
        sentences.append(f"{position} 방향입니다.")

    return sentences


def render_consumer_sections(fields: dict[str, str]) -> list[dict[str, str]]:
    """모델이 채운 4개 상품 식별 필드를 하나의 "상품 정보" 블록으로 모읍니다.
    이동 안전·구역 구분 등 매장 접근성 정보는 이 파일이 다루지 않고
    accessibility_prompt.py(매장 사진 안내)에 맡깁니다 — 두 안내를 섞으면
    "의류 안내"와 "매장 안내"의 경계가 흐려진다는 사용자 피드백에 따른
    분리입니다.

    프론트가 항목별로 시각적으로 구분해서 보여줄 수 있도록 accessibility_prompt.py의
    consumer_items()와 같은 {label, description} 목록 형태로 반환합니다."""
    raw_prose = fields.get(RAW_PROSE_KEY, "").strip()
    if raw_prose:
        return [{"label": "상품 정보", "description": raw_prose}]

    product_sentences = _product_sentences(fields)
    if not product_sentences:
        return [
            {
                "label": "상품 정보",
                "description": "이 사진에서는 구체적인 정보를 확인하기 어려웠어요. 조금 더 가까이서 다시 찍어봐 주시겠어요?",
            }
        ]
    return [{"label": "상품 정보", "description": " ".join(product_sentences)}]


def render_consumer_narration(fields: dict[str, str]) -> str:
    """render_consumer_sections()와 같은 내용을, TTS처럼 순수 텍스트 한 덩어리가
    필요한 용도를 위해 하나의 문자열로 이어붙입니다."""
    sections = render_consumer_sections(fields)
    return " ".join(f"{section['label']}. {section['description']}" for section in sections)
