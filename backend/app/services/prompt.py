"""LM Studio(및 향후 다른 LLM)에 보낼 JSON 스키마와 프롬프트 텍스트."""

from __future__ import annotations

import json
from typing import Any

from .zones import criteria_for_zone, normalize_zone


def vmd_json_schema() -> dict[str, Any]:
    score_props = {
        "layout": {"type": "integer", "minimum": 0, "maximum": 100},
        "presentation_mood": {"type": "integer", "minimum": 0, "maximum": 100},
        "brand_fit": {"type": "integer", "minimum": 0, "maximum": 100},
        "color_harmony": {"type": "integer", "minimum": 0, "maximum": 100},
        "cleanliness": {"type": "integer", "minimum": 0, "maximum": 100},
        "customer_attention": {"type": "integer", "minimum": 0, "maximum": 100},
        "season_concept_fit": {"type": "integer", "minimum": 0, "maximum": 100},
    }
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
                    "comment": {
                        "type": "string",
                        "description": "촬영 상태와 평가 신뢰도에 미치는 영향을 근거와 함께 설명한 2~3문장",
                    },
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
            "scores": {
                "type": "object",
                "properties": score_props,
                "required": list(score_props.keys()),
                "additionalProperties": False,
            },
            "total_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "grade": {"type": "string"},
            "positive_points": {
                "type": "array",
                "description": "사진에서 확인 가능한 근거를 포함한 강점 2~3개",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
            },
            "critical_issues": {
                "type": "array",
                "description": "문제의 위치, 관찰 근거, VMD 영향을 포함한 핵심 문제 3~4개",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 4,
            },
            "improvement_suggestions": {
                "type": "array",
                "description": "담당자가 바로 실행할 수 있도록 대상, 방법, 기대 효과를 포함한 개선안 3~4개",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 4,
            },
            "final_summary": {
                "type": "string",
                "description": "현재 상태, 핵심 강점과 문제, 우선 조치 순서를 종합한 3~5문장",
            },
            "zone_evaluation_summary": {
                "type": "string",
                "description": "사용자가 지정한 VP/IP/PP 영역 기준으로 본 종합 평가. reference Excel의 영역별 평가 컬럼에 들어갈 내용",
            },
            "priority_action_summary": {
                "type": "string",
                "description": "가장 먼저 조치할 사항과 이유를 설명한 최종 요약 답변",
            },
            "detected_issues": {
                "type": "array",
                "description": "감지된 문제점을 줄 단위로 정리",
                "items": {"type": "string"},
            },
            "improvement_actions": {
                "type": "array",
                "description": "개선 방향을 줄 단위로 정리",
                "items": {"type": "string"},
            },
            "overall_improvement_summary": {
                "type": "string",
                "description": "전체 개선 요약. improvement_actions를 종합해 한 문단 또는 줄바꿈 목록으로 작성",
            },
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
            "scores",
            "total_score",
            "grade",
            "positive_points",
            "critical_issues",
            "improvement_suggestions",
            "final_summary",
            "zone_evaluation_summary",
            "priority_action_summary",
            "detected_issues",
            "improvement_actions",
            "overall_improvement_summary",
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
            "결과 분량 기준을 반드시 지키세요.",
            "- zone_evaluation_summary: 지정 존의 목적과 이미지 관찰 근거를 연결해 3~5문장으로 작성하세요.",
            "- priority_action_summary: 가장 먼저 해야 할 조치와 이유를 3~5문장으로 작성하세요.",
            "- detected_issues: 감지된 문제점을 0~4개 작성하세요. 문제가 거의 없으면 빈 배열로 두세요.",
            "- improvement_actions: 실행 가능한 개선 방향을 2~4개 작성하세요.",
            "- overall_improvement_summary: 개선 방향 전체를 한 문단 또는 줄바꿈 목록으로 요약하세요.",
            "- criteria_evaluations: 아래 존 전용 평가 항목을 같은 이름과 같은 순서로 모두 작성하세요.",
            *[f"  {index}. {criterion}" for index, criterion in enumerate(zone_criteria, start=1)],
            "- positive_points: 서로 다른 강점 2~3개. 각 항목은 관찰 근거와 효과를 담은 1~2문장으로 작성하세요.",
            "- critical_issues: 서로 다른 핵심 문제 3~4개. 각 항목은 위치/대상, 관찰 근거, VMD 영향을 담은 2문장 내외로 작성하세요.",
            "- improvement_suggestions: 문제점에 대응하는 실행안 3~4개. 각 항목은 수정 대상, 구체적인 방법, 기대 효과를 담은 2문장 내외로 작성하세요.",
            "- final_summary: 현재 상태와 우선순위를 종합한 3~5문장으로 작성하세요. 목록 내용을 그대로 반복하지 마세요.",
            "- photo_quality.comment: 촬영 상태와 분석 신뢰도 영향을 2~3문장으로 작성하세요.",
            "사진에서 확인할 수 없는 사실을 분량을 채우기 위해 추측하지 마세요.",
            "모든 점수는 0~100 정수로 작성하세요.",
        ]
    )


def schema_instruction() -> str:
    # 예시 1건을 모델에 함께 제시해 응답 형식을 고정합니다.
    example = {
        "user_selected_zone": "VP",
        "ai_detected_zone": "VP",
        "zone_confidence": 0.85,
        "store_type_assumption": "UNKNOWN",
        "photo_quality": {
            "score": 80,
            "is_blurry": False,
            "is_tilted": False,
            "has_background_interference": False,
            "needs_retake": False,
            "comment": "사진은 핵심 연출과 주요 상품의 형태를 식별할 수 있을 만큼 선명합니다.",
        },
        "mannequin": {"exists": True, "type": "headless_body_mannequin", "has_head": False, "comment": "헤드리스 바디 마네킹으로 판단됩니다."},
        "obstacles": [{"object": "chair", "location": "right bottom", "severity": "medium", "reason": "시선을 분산시킵니다."}],
        "scores": {
            "layout": 80,
            "presentation_mood": 80,
            "brand_fit": 80,
            "color_harmony": 80,
            "cleanliness": 80,
            "customer_attention": 80,
            "season_concept_fit": 80,
        },
        "total_score": 80,
        "grade": "우수",
        "positive_points": ["강점 1", "강점 2"],
        "critical_issues": ["문제 1", "문제 2", "문제 3"],
        "improvement_suggestions": ["개선안 1", "개선안 2", "개선안 3"],
        "final_summary": "현재 상태와 우선순위를 종합한 요약입니다.",
        "zone_evaluation_summary": "지정 존 기준 종합 평가입니다.",
        "priority_action_summary": "가장 먼저 할 조치입니다.",
        "detected_issues": ["감지된 문제 1"],
        "improvement_actions": ["개선 방향 1"],
        "overall_improvement_summary": "개선 방향 전체 요약입니다.",
        "criteria_evaluations": [
            {"criterion": "예시 항목", "score": 80, "evidence": "근거", "issue": "문제점", "suggestion": "개선안"}
        ],
    }
    return (
        "반드시 아래 예시와 같은 JSON 객체만 반환하세요. 설명 문장, markdown, 코드블록은 쓰지 마세요.\n"
        + json.dumps(example, ensure_ascii=False, indent=2)
    )
