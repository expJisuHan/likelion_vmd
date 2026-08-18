"""NVIDIA NIM(및 향후 다른 LLM)에 보낼 JSON 스키마와 프롬프트 텍스트."""

from __future__ import annotations

from typing import Any

from .zones import criteria_for_zone, normalize_zone


def vmd_json_schema() -> dict[str, Any]:
    # 아래 필드들은 스키마에서 뺐습니다 — apply_defaults()가 다른 필드에서 자동으로
    # 유도해주거나(zone_evaluation_summary/priority_action_summary <- final_summary,
    # detected_issues <- critical_issues, improvement_actions/overall_improvement_summary
    # <- improvement_suggestions), 실제 화면·Excel·PDF 어디서도 쓰이지 않는 구식 필드라
    # (scores) 모델에게 생성을 요구할 이유가 없습니다. 작은 모델(11B)이 스키마 복잡도 때문에
    # 응답이 잘리거나 플레이스홀더로 채워지는 문제가 있어 실제로 쓰이는 필드만 남겼습니다.
    # positive_points/critical_issues/improvement_suggestions/final_summary/photo_quality.comment의
    # 분량·내용 지침은 build_user_text()의 불릿에서만 서술합니다 — 이 텍스트는 schema 모드/비schema
    # 모드 요청 모두에 항상 실려가므로, 여기 description에 같은 문장을 또 넣으면 schema 모드
    # 요청(response_format 사용 시)에서만 토큰이 이중으로 나갑니다.
    return {
        "type": "object",
        "properties": {
            "user_selected_zone": {"type": "string", "enum": ["VP", "PP", "IP"]},
            "ai_detected_zone": {"type": "string", "enum": ["VP", "PP", "IP", "UNKNOWN"]},
            "zone_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "store_type_assumption": {"type": "string"},
            "photo_quality": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "is_blurry": {"type": "boolean"},
                    "is_tilted": {"type": "boolean"},
                    "has_background_interference": {"type": "boolean"},
                    "needs_retake": {"type": "boolean"},
                    "comment": {"type": "string"},
                },
                "required": ["score", "is_blurry", "is_tilted", "has_background_interference", "needs_retake", "comment"],
                "additionalProperties": False,
            },
            "mannequin": {
                "type": "object",
                "properties": {
                    "exists": {"type": "boolean"},
                    "type": {"type": "string"},
                    "has_head": {"type": "boolean"},
                    "comment": {
                        "type": "string",
                        "description": "마네킹이 있으면 판정 근거와 연출 상태를 1~2문장으로 설명하고, 없으면 빈 문자열",
                    },
                },
                "required": ["exists", "type", "has_head", "comment"],
                "additionalProperties": False,
            },
            "obstacles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "object": {"type": "string"},
                        "location": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
                        "reason": {
                            "type": "string",
                            "description": "해당 물체가 존의 목적, 상품 시야 또는 고객 동선에 미치는 영향을 1~2문장으로 설명",
                        },
                    },
                    "required": ["object", "location", "severity", "reason"],
                    "additionalProperties": False,
                },
            },
            "total_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "grade": {"type": "string"},
            "positive_points": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
            },
            "critical_issues": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 4,
            },
            "improvement_suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 4,
            },
            "final_summary": {"type": "string"},
            "criteria_evaluations": {
                "type": "array",
                "description": "사용자 지정 존의 평가항목별 점수, 근거, 문제점, 개선안",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "score": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                        "evidence": {"type": "string"},
                        "issue": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["criterion", "score", "evidence", "issue", "suggestion"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "user_selected_zone",
            "ai_detected_zone",
            "zone_confidence",
            "store_type_assumption",
            "photo_quality",
            "mannequin",
            "obstacles",
            "total_score",
            "grade",
            "positive_points",
            "critical_issues",
            "improvement_suggestions",
            "final_summary",
            "criteria_evaluations",
        ],
        "additionalProperties": False,
    }


def system_prompt() -> str:
    return (
        "당신은 백화점과 패션 리테일 매장을 평가하는 Visual Merchandising(VMD) 전문가입니다. "
        "IP, PP, VP 존의 역할을 이해하고, 사진 속 매장 연출을 전문가 관점에서 평가합니다. "
        "답변은 반드시 JSON 스키마에 맞는 JSON 객체 하나만 반환합니다. 마크다운, 설명문, 코드블록은 금지합니다. "
        "평가는 칭찬 위주가 아니라 실제 개선 가능한 문제를 찾는 비판적 분석이어야 합니다. "
        "다만 표현은 사용자가 받아들이기 쉬운 부드러운 전문가 톤을 유지합니다. "
        "마네킹이 없는 사진에서는 마네킹 코멘트를 작성하지 말고, 먼저 마네킹 유무를 판단하세요. "
        "머리 있는 마네킹, 머리 없는 바디 마네킹, 옷걸이/상하의 진열을 구분하세요. "
        "의자, 상자, 공기청정기, 화분, 테이블, 적재물 등은 상품 시야나 동선을 방해하면 방해물로 기록하세요. "
        "구조물, 소품, 상품, 방해물을 혼동하지 마세요. "
        "사진의 선명도, 조명, 질감, 각도, 기울어짐, 배경 간섭, 핵심 존 가시성을 별도 평가하세요. "
        "사용자가 VP/PP/IP 존을 지정하면 그 존의 목적에 맞춰 평가하고, AI 판단 존과 신뢰도는 별도로 반환하세요. "
        "평가 문장은 사진에서 실제로 관찰한 대상과 위치를 근거로 작성하고, 점수만 되풀이하거나 한 문장으로 뭉뚱그리지 마세요. "
        "각 강점과 문제점은 관찰 사실과 VMD 영향을 포함하고, 각 개선안은 무엇을 어떻게 바꿀지와 기대 효과까지 설명하세요."
    )


def build_user_text(options: dict[str, Any], image_count: int) -> str:
    zone = normalize_zone(options.get("zoneMode"))
    store_type = options.get("storeType", "UNKNOWN")
    tone = options.get("tone", "SOFT_CRITICAL")
    criteria = options.get("criteria", [])
    focus_keywords = options.get("focusKeywords", [])
    extra = (options.get("extraCriteria") or "").strip()
    if not isinstance(focus_keywords, list):
        focus_keywords = []
    focus_keywords = [str(keyword).strip() for keyword in focus_keywords if str(keyword).strip()]

    zone_instruction = (
        f"사용자가 이 이미지를 {zone} 존으로 지정했습니다. "
        f"AI 판단 존도 반환하되, 평가는 {zone} 존 기준으로 하세요."
    )
    zone_criteria = criteria_for_zone(zone)
    return "\n".join(
        [
            f"이미지 {image_count}장을 함께 보고 하나의 VMD 평가 결과를 작성하세요.",
            zone_instruction,
            f"사용자 선택 존: {zone}",
            f"매장 유형 옵션: {store_type}",
            f"분석 톤 옵션: {tone}",
            "기본 평가 항목: " + (", ".join(criteria) if criteria else "전체 기본 항목"),
            f"{zone} 존 전용 평가 항목: " + ", ".join(zone_criteria),
            "참고 키워드: " + (", ".join(focus_keywords) if focus_keywords else "없음"),
            "추가 평가 요청: " + (extra if extra else "없음"),
            "다른 내용보다 먼저, 아래 6줄을 이 형식 그대로(설명 추가 없이, 줄바꿈 유지) "
            "응답의 맨 첫 줄부터 작성하세요. 이후에만 나머지 상세 평가를 이어서 작성하세요:",
            "TOTAL_SCORE: <0-100 정수>",
            "AI_DETECTED_ZONE: <VP 또는 PP 또는 IP 또는 UNKNOWN>",
            "ZONE_CONFIDENCE: <0.00~1.00>",
            "PHOTO_QUALITY_SCORE: <0-100 정수>",
            "MANNEQUIN_EXISTS: <true 또는 false>",
            "MANNEQUIN_TYPE: <mannequin_with_head 또는 headless_body_mannequin 또는 hanger_display 또는 none>",
            "결과 분량 기준을 반드시 지키세요.",
            "- criteria_evaluations: 아래 존 전용 평가 항목을 같은 이름과 같은 순서로 모두 작성하세요. "
            "항목마다 score(0~100 정수), evidence/issue/suggestion(각각 정확히 1문장)을 포함하세요.",
            *[f"  {index}. {criterion}" for index, criterion in enumerate(zone_criteria, start=1)],
            "- positive_points: 서로 다른 강점 2~3개. 각 항목은 관찰 근거와 효과를 담아 1문장으로 작성하세요.",
            "- critical_issues: 서로 다른 핵심 문제 3~4개. 각 항목은 위치/대상, 관찰 근거, VMD 영향을 담아 1문장으로 작성하세요.",
            "- improvement_suggestions: 문제점에 대응하는 실행안 3~4개. 각 항목은 수정 대상, 구체적인 방법, 기대 효과를 담아 1문장으로 작성하세요.",
            "- final_summary: 현재 상태와 우선순위를 종합한 3~5문장으로 작성하세요. 목록 내용을 그대로 반복하지 마세요.",
            "- photo_quality.comment: 촬영 상태와 분석 신뢰도 영향을 1~2문장으로 작성하세요.",
            "사진에서 확인할 수 없는 사실을 분량을 채우기 위해 추측하지 마세요.",
            "모든 점수는 0~100 정수로 작성하세요.",
        ]
    )


# 예시(완성된 문장이든 <> 추상 템플릿이든)를 프롬프트에 실어 보내면 작은 모델(11B)이
# 사진 내용과 무관하게 그 예시를 그대로, 혹은 명사 몇 개만 바꿔서 베끼는 경향이 강합니다
# (요청마다 예시를 무작위로 바꿔봐도 "그 요청에 뽑힌 예시"를 통째로 베끼는 문제는 그대로
# 재현됨을 실측으로 확인). 베낄 대상 자체를 프롬프트에서 없애는 것이 유일하게 확실한 해법이라
# 예시 JSON을 완전히 제거하고, 형식·분량 요구사항은 문장으로만 지시합니다. 대신 이 텍스트만으로
# 모델이 실제로 관찰한 내용을 채워 넣는지는 analysis.py의 사후 중복·플레이스홀더 검증 및
# 자동 재시도(_find_content_problems/_MAX_CONTENT_RETRIES)가 한 번 더 걸러줍니다.
def schema_instruction() -> str:
    return (
        "TOTAL_SCORE로 시작하는 6줄 헤더는 예외로 그대로 유지하고, 그 다음부터 지정된 JSON 스키마와 "
        "정확히 같은 구조의 JSON 객체 하나만 반환하세요. "
        "마크다운, 설명 문장, 코드블록은 쓰지 마세요. "
        "예시나 템플릿 문장을 베끼지 말고, 이번에 첨부된 사진에서 실제로 관찰한 대상·위치·상태만 근거로 "
        "모든 문장을 새로 작성하세요. 서로 다른 항목에 같은 문장을 반복하지 마세요. "
        "positive_points/critical_issues/improvement_suggestions/criteria_evaluations의 각 항목 앞에 "
        "번호나 순서 표시(예: \"1.\", \"강점 1.\", \"문제 2.\")를 붙이지 말고 문장으로 바로 시작하세요. "
        "criteria_evaluations는 요청받은 평가 항목 전체에 대해 각각 작성하고, 항목마다 evidence/issue/suggestion을 "
        "서로 다르게, 그 항목에만 해당하는 내용으로 쓰세요."
    )
