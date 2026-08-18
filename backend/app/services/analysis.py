"""이미지 분석 오케스트레이션: 프롬프트 구성 -> NVIDIA NIM 호출(모델/스키마 fallback) -> 결과 정규화."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..config import settings
from ..utils import list_to_lines, resize_image_data_url_for_model
from .analysis_cache import build_cache_key, get_cached_result, store_result
from .nim_client import is_retriable_nim_error, nim_model_candidates, nim_request
from .prompt import build_user_text, schema_instruction, system_prompt, vmd_json_schema
from .zones import criteria_for_zone, grade_from_score, normalize_zone

# 프롬프트에서 번호 접두어를 쓰지 말라고 지시해도 작은 모델은 "강점 1.", "문제 2." 같은
# 한국어 목록 습관을 완전히 버리지 않는 경우가 있어, 응답을 받은 뒤 한 번 더 걷어냅니다.
_ORDINAL_PREFIX_RE = re.compile(r"^(?:강점|문제점?|이슈|개선(?:안|점)?)?\s*\d+\s*[.).:]\s*")

# prompt.py에서 예시 JSON을 없애 "베낄 대상"을 아예 제거했지만, 그래도 모델이 서로 다른
# 항목에 같은 문장을 반복하거나(예: evidence/issue/suggestion을 전부 동일 문장으로 채움)
# 근거 없이 한두 단어짜리 자리표시자만 채워 넣는 경우가 남을 수 있어 응답 내용을 한 번 더
# 검증합니다. 문제가 발견되면 그 문제를 구체적으로 지적하는 메시지를 덧붙이고 temperature를
# 올려 최대 _MAX_CONTENT_RETRIES회 재요청합니다.
_MAX_CONTENT_RETRIES = 1
_MIN_SENTENCE_LENGTH = 8

# Vercel Hobby 플랜 함수 상한(300초)은 요청 하나 전체(이미지 리사이즈 + NIM 호출 + 이후
# 엑셀/PDF 생성)에 적용됩니다. 콘텐츠 품질 재시도가 완전히 새로운 생성 호출을 한 번 더
# 만들기 때문에, 1차 호출이 느리게 성공하면 2차 호출이 상한을 그냥 넘길 수 있습니다.
# 그래서 이 함수 진입 시각부터 흐른 시간을 추적해 예산이 부족하면 재시도를 건너뛰고,
# 개별 NIM 호출의 timeout도 남은 예산을 넘지 않도록 잘라서 보냅니다.
_TOTAL_TIME_BUDGET_SECONDS = 220
_MIN_ATTEMPT_SECONDS = 30


def _strip_ordinal_prefix(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    return _ORDINAL_PREFIX_RE.sub("", text, count=1).strip()


def _normalize_for_dup_check(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", "", text).strip()


def _find_content_problems(parsed: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    seen_sentences: dict[str, str] = {}

    def check_list(field: str, min_len: int = _MIN_SENTENCE_LENGTH) -> None:
        items = parsed.get(field)
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text:
                continue
            if len(text) < min_len:
                problems.append(f"{field} 항목이 너무 짧거나 구체적이지 않습니다: '{text}'")
                continue
            key = _normalize_for_dup_check(text)
            if key in seen_sentences:
                problems.append(f"'{text}' 문장이 {seen_sentences[key]}와(과) {field}에서 중복됩니다.")
            else:
                seen_sentences[key] = field

    check_list("positive_points")
    check_list("critical_issues")
    check_list("improvement_suggestions")

    criteria = parsed.get("criteria_evaluations")
    if isinstance(criteria, list):
        for entry in criteria:
            if not isinstance(entry, dict):
                continue
            evidence = _normalize_for_dup_check(entry.get("evidence"))
            issue = _normalize_for_dup_check(entry.get("issue"))
            suggestion = _normalize_for_dup_check(entry.get("suggestion"))
            values = [v for v in (evidence, issue, suggestion) if v]
            if len(values) >= 2 and len(set(values)) < len(values):
                criterion = entry.get("criterion", "?")
                problems.append(f"criteria_evaluations의 '{criterion}' 항목은 evidence/issue/suggestion 중 일부가 동일한 문장입니다.")

    return problems


def _build_corrective_note(problems: list[str]) -> str:
    bullet_list = "\n".join(f"- {problem}" for problem in problems)
    return (
        "\n\n이전 응답에서 다음 문제가 발견되었습니다. 같은 문제를 반복하지 말고, 이번 사진에서 "
        "실제로 관찰한 서로 다른 내용으로 해당 항목들을 완전히 새로 작성하세요:\n" + bullet_list
    )


def apply_defaults(result: dict[str, Any], user_zone: str) -> dict[str, Any]:
    result.setdefault("user_selected_zone", user_zone)
    result.setdefault("ai_detected_zone", "UNKNOWN")
    if result.get("ai_detected_zone") == "UNKNOWN":
        # 모델이 AI 판단 존을 아예 빼먹거나 불확실해서 UNKNOWN을 반환하는 경우가 있어,
        # 화면에 의미 없는 UNKNOWN을 보여주는 대신 사용자가 지정한 존을 그대로 표시합니다.
        result["ai_detected_zone"] = user_zone
    result.setdefault("zone_confidence", 0)
    result.setdefault("store_type_assumption", "UNKNOWN")
    result.setdefault(
        "photo_quality",
        {
            "score": 0,
            "is_blurry": False,
            "is_tilted": False,
            "has_background_interference": False,
            "needs_retake": False,
            "comment": "",
        },
    )
    result.setdefault("mannequin", {"exists": False, "type": "none", "has_head": False, "comment": ""})
    result.setdefault("obstacles", [])
    result.setdefault(
        "scores",
        {
            "layout": 0,
            "presentation_mood": 0,
            "brand_fit": 0,
            "color_harmony": 0,
            "cleanliness": 0,
            "customer_attention": 0,
            "season_concept_fit": 0,
        },
    )
    result.setdefault("total_score", 0)
    result.setdefault("grade", grade_from_score(result.get("total_score")))
    result.setdefault("positive_points", [])
    result.setdefault("critical_issues", [])
    result.setdefault("improvement_suggestions", [])
    result["positive_points"] = [_strip_ordinal_prefix(item) for item in result["positive_points"]]
    result["critical_issues"] = [_strip_ordinal_prefix(item) for item in result["critical_issues"]]
    result["improvement_suggestions"] = [_strip_ordinal_prefix(item) for item in result["improvement_suggestions"]]
    result.setdefault("final_summary", "")
    result.setdefault("zone_evaluation_summary", result.get("final_summary", ""))
    result.setdefault("priority_action_summary", result.get("final_summary", ""))
    result.setdefault("detected_issues", result.get("critical_issues", []))
    result.setdefault("improvement_actions", result.get("improvement_suggestions", []))
    result.setdefault("overall_improvement_summary", list_to_lines(result.get("improvement_suggestions", [])))
    criteria = result.get("criteria_evaluations")
    if not isinstance(criteria, list):
        criteria = []
    by_name = {str(item.get("criterion", "")).strip(): item for item in criteria if isinstance(item, dict)}
    normalized_criteria = []
    for criterion in criteria_for_zone(user_zone):
        item = by_name.get(criterion, {})
        normalized_criteria.append(
            {
                "criterion": criterion,
                "score": item.get("score"),
                "evidence": _strip_ordinal_prefix(item.get("evidence", "")),
                "issue": _strip_ordinal_prefix(item.get("issue", "")),
                "suggestion": _strip_ordinal_prefix(item.get("suggestion", "")),
            }
        )
    result["criteria_evaluations"] = normalized_criteria
    return result


def image_content_items(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for image in images:
        data_url = image.get("dataUrl", "")
        if not data_url.startswith("data:image/"):
            raise ValueError(f"Invalid image data for {image.get('name', 'image')}")
        data_url = resize_image_data_url_for_model(
            data_url, settings.nim_image_max_dimension, settings.nim_image_max_bytes
        )
        items.append({"type": "image_url", "image_url": {"url": data_url}})
    return items


# "#### criteria_evaluations" 형태와 "**criteria_evaluations**" 형태(모델이 헤더 대신
# 볼드로 섹션을 표시하는 경우, 실측으로 확인) 둘 다 헤더로 인식합니다. **로 감싼 쪽은
# 줄 전체가 "**텍스트**"여야만 헤더로 취급합니다 — 그렇지 않으면 "**중요:** 문장..."처럼
# 문장 중간의 강조 표시까지 헤더로 오인합니다.
_MD_HEADER_RE = re.compile(r"^\s*(?:#{1,4}\s*(?P<h1>.+?)|\*\*(?P<h2>[^*].*?)\*\*)\s*$")
_MD_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
_MD_BULLET_RE = re.compile(r"^\s*[*\-]\s+(.+?)\s*$")
_MD_LABELED_BULLET_RE = re.compile(
    r"^\s*[*\-]\s+(evidence|issue|suggestion|score)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE
)
_MD_LABEL_PREFIX_RE = re.compile(r"^[^\n:：]{1,30}[:：]\s*")
_MD_EMPHASIS_RE = re.compile(r"^\*{1,2}(.+?)\*{1,2}$")


def _strip_md_emphasis(text: str) -> str:
    match = _MD_EMPHASIS_RE.match(text.strip())
    return match.group(1).strip() if match else text.strip()

_MD_TOP_LEVEL_FIELDS = (
    "positive_points",
    "critical_issues",
    "improvement_suggestions",
    "final_summary",
    "photo_quality",
    "criteria_evaluations",
)


def _match_top_level_field(title: str) -> str | None:
    normalized = title.replace(" ", "").lower()
    for field in _MD_TOP_LEVEL_FIELDS:
        if field in normalized:
            return field
    return None


def _header_title(match: re.Match) -> str:
    return (match.group("h1") or match.group("h2") or "").strip()


def _extract_block_text(lines: list[str]) -> str:
    bullets: list[str] = []
    for line in lines:
        match = _MD_BULLET_RE.match(line)
        if match:
            bullets.append(match.group(1))
    if bullets:
        return " ".join(bullets)
    # 불릿이 아니라 일반 문단으로 쓴 경우(final_summary/photo_quality.comment에서 흔함)
    plain = [line.strip() for line in lines if line.strip() and not _MD_HEADER_RE.match(line)]
    return " ".join(plain)


def _extract_list_items(lines: list[str]) -> list[str]:
    # 이 모델은 목록을 여러 형태로 씁니다 (실측으로 확인):
    #   A) 직속 불릿만: "* 문장"
    #   B) 번호 항목 + 중첩 불릿 1개에 실제 내용: "1. 항목명\n   * 실제 문장" (번호 항목
    #      텍스트는 criterion 이름 재사용이라 내용이 아님 -> 무시하고 중첩 불릿만 사용)
    #   C) 번호 항목 자체에 내용: "1. 실제 문장" (중첩 불릿 없음 -> 번호 항목 텍스트 사용)
    #   D) 번호 항목 + 중첩 불릿 여러 개, 각각 "관찰 근거:"/"효과:"처럼 프롬프트 지시
    #      문구를 라벨로 재사용(원래 한 문장이어야 할 내용을 필드별로 쪼갬) -> 한 항목의
    #      중첩 불릿들을 합쳐서 하나의 리스트 항목으로 취급합니다(라벨 접두어는 제거).
    items: list[str] = []
    pending_numbered: str | None = None
    pending_bullets: list[str] = []

    def flush_pending() -> None:
        if pending_bullets:
            cleaned = [_MD_LABEL_PREFIX_RE.sub("", text).strip() for text in pending_bullets]
            items.append(" ".join(part for part in cleaned if part))
        elif pending_numbered is not None:
            items.append(_strip_md_emphasis(pending_numbered))

    for line in lines:
        numbered_match = _MD_NUMBERED_RE.match(line)
        if numbered_match:
            flush_pending()
            pending_numbered = numbered_match.group(1)
            pending_bullets = []
            continue
        bullet_match = _MD_BULLET_RE.match(line)
        if bullet_match:
            if pending_numbered is not None:
                pending_bullets.append(bullet_match.group(1))
            else:
                items.append(bullet_match.group(1))  # 형태 A: 번호 없이 직속 불릿만
    flush_pending()
    return items


def _parse_criteria_block(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current_title: str | None = None
    current_fields: dict[str, str] = {}
    current_bullets: list[str] = []

    def flush() -> None:
        if current_title is None:
            return
        evidence = current_fields.get("evidence", "")
        issue = current_fields.get("issue", "")
        suggestion = current_fields.get("suggestion", "")
        if not (evidence or issue or suggestion) and current_bullets:
            # 라벨(evidence:/issue:/suggestion:) 없이 불릿만 있는 경우 순서로 추정합니다.
            # 항목이 2개뿐일 때 억지로 3필드를 다 채우면 evidence==suggestion 중복이
            # 생겨 _find_content_problems의 중복 검사에 잘못 걸리므로, 없는 필드는
            # 빈 문자열로 남겨둡니다.
            if len(current_bullets) >= 3:
                evidence, issue, suggestion = current_bullets[0], current_bullets[1], current_bullets[2]
            elif len(current_bullets) == 2:
                evidence, suggestion = current_bullets[0], current_bullets[1]
            else:
                evidence = current_bullets[0]
        score_value: int | None = None
        score_text = current_fields.get("score")
        if score_text:
            digits = re.sub(r"[^\d.]", "", score_text)
            if digits:
                try:
                    score_value = max(0, min(100, int(float(digits))))
                except ValueError:
                    score_value = None
        if evidence or issue or suggestion:
            entries.append(
                {
                    "criterion": current_title,
                    "score": score_value,
                    "evidence": evidence,
                    "issue": issue,
                    "suggestion": suggestion,
                }
            )

    for line in lines:
        header_match = _MD_HEADER_RE.match(line)
        numbered_match = _MD_NUMBERED_RE.match(line)
        title_text: str | None = None
        if header_match and _match_top_level_field(_header_title(header_match)) is None:
            title_text = _header_title(header_match)
        elif numbered_match:
            title_text = numbered_match.group(1)
        if title_text is not None:
            flush()
            # 번호 항목 제목에 "**연출 콘셉트의 시각적 일관성**"처럼 볼드가 섞여 오면
            # criterion 이름이 zones.py의 정확한 문자열과 안 맞아 apply_defaults()의
            # by_name 매칭이 실패하고 평가 전체가 빈 값으로 버려집니다(실측으로 확인
            # 및 수정한 버그) — 반드시 볼드 마크를 벗기고 criterion으로 씁니다.
            current_title = _strip_md_emphasis(title_text)
            current_fields = {}
            current_bullets = []
            continue
        labeled_match = _MD_LABELED_BULLET_RE.match(line)
        if labeled_match and current_title is not None:
            current_fields[labeled_match.group(1).lower()] = labeled_match.group(2)
            continue
        bullet_match = _MD_BULLET_RE.match(line)
        if bullet_match and current_title is not None:
            # "evidence/issue/suggestion: 문장"처럼 라벨을 슬래시로 합쳐 쓰는 경우가 있어
            # (실측으로 확인) _MD_LABELED_BULLET_RE에 안 걸립니다. 남아있는 라벨 프리픽스만
            # 걷어내고 나머지는 일반 불릿으로 취급합니다.
            text = _MD_LABEL_PREFIX_RE.sub("", bullet_match.group(1))
            current_bullets.append(text)
    flush()
    return entries


def _parse_markdown_sections(content: str) -> dict[str, Any] | None:
    # response_format=json_schema(strict)를 요청해도 이 모델은 JSON 대신 마크다운
    # 산문으로 응답할 때가 있습니다(실측으로 확인). 게다가 그 마크다운 형식 자체도
    # 매번 똑같지 않아서(예: 직속 불릿 vs 번호 항목+중첩 불릿, evidence: 라벨 유무),
    # 헤더 깊이가 아니라 알려진 필드 이름과의 매칭으로 블록 경계를 잡습니다. 순수 JSON
    # 파싱이 실패했을 때만 시도하는 최후 폴백입니다.
    blocks: list[tuple[str, list[str]]] = []
    current_field: str | None = None
    current_lines: list[str] = []
    for line in content.splitlines():
        header_match = _MD_HEADER_RE.match(line)
        if header_match:
            field = _match_top_level_field(_header_title(header_match))
            if field is not None:
                if current_field is not None:
                    blocks.append((current_field, current_lines))
                current_field = field
                current_lines = []
                continue
        if current_field is not None:
            current_lines.append(line)
    if current_field is not None:
        blocks.append((current_field, current_lines))
    if not blocks:
        return None

    result: dict[str, Any] = {}
    for field, body_lines in blocks:
        if field == "criteria_evaluations":
            entries = _parse_criteria_block(body_lines)
            if entries:
                result["criteria_evaluations"] = entries
        elif field == "photo_quality":
            comment = _extract_block_text(body_lines)
            if comment:
                result.setdefault("photo_quality", {})["comment"] = comment
        elif field == "final_summary":
            text = _extract_block_text(body_lines)
            if text:
                result["final_summary"] = text
        else:  # positive_points / critical_issues / improvement_suggestions
            items = _extract_list_items(body_lines)
            if items:
                result[field] = items

    # 실제로 뭔가 건진 필드가 하나도 없으면(전부 빈 채로 헤더만 매칭됐으면) 마크다운
    # 파싱도 실패로 취급해서 호출부가 다음 모델/변형으로 폴백하게 둡니다. 빈 리스트를
    # "성공"으로 착각해서 분석 실패나 다름없는 빈 결과를 그대로 승인하면 안 됩니다.
    if not result:
        return None
    return result


_HEADER_KEY_NAMES = (
    "TOTAL_SCORE",
    "AI_DETECTED_ZONE",
    "ZONE_CONFIDENCE",
    "PHOTO_QUALITY_SCORE",
    "MANNEQUIN_EXISTS",
    "MANNEQUIN_TYPE",
)
_HEADER_KEY_RE = re.compile(r"\b(" + "|".join(_HEADER_KEY_NAMES) + r")\s*[:：]\s*", re.IGNORECASE)


def _extract_header_fields(content: str) -> dict[str, Any]:
    # 프롬프트가 응답 맨 앞에 TOTAL_SCORE/AI_DETECTED_ZONE/ZONE_CONFIDENCE/
    # PHOTO_QUALITY_SCORE/MANNEQUIN_EXISTS/MANNEQUIN_TYPE 6줄을 "KEY: value" 형식으로
    # 강제합니다. 이 필드들은 JSON 중첩 객체/배열이라 모델이 마크다운 모드로 빠지면 자주
    # 통째로 빠뜨리는데(총점 0점, AI 판단 존 UNKNOWN, 마네킹 없음으로 잘못 표시되는 원인),
    # 단순 key:value 줄은 JSON/마크다운 어느 쪽이든 안정적으로 건질 수 있습니다.
    # 다만 모델이 6줄을 지시대로 줄바꿈해서 쓰지 않고 "**TOTAL_SCORE: 60** AI_DETECTED_ZONE:
    # VP ..." 처럼 한 줄에 붙여 쓰는 경우가 있어(실측으로 확인), 줄 단위가 아니라 각 키
    # 매치의 끝부터 다음 키 매치가 시작되는 지점까지(또는 줄바꿈)를 값으로 잘라냅니다.
    matches = list(_HEADER_KEY_RE.finditer(content))
    values: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(content), start + 80)
        raw_value = content[start:end].split("\n", 1)[0]
        value = raw_value.strip().strip("*# ").strip()
        if value:
            values.setdefault(key, value)

    result: dict[str, Any] = {}
    if "TOTAL_SCORE" in values:
        digits = re.sub(r"[^\d.]", "", values["TOTAL_SCORE"])
        if digits:
            try:
                result["total_score"] = max(0, min(100, int(float(digits))))
            except ValueError:
                pass
    if "AI_DETECTED_ZONE" in values:
        zone_value = values["AI_DETECTED_ZONE"].upper()
        if zone_value in {"VP", "PP", "IP", "UNKNOWN"}:
            result["ai_detected_zone"] = zone_value
    if "ZONE_CONFIDENCE" in values:
        try:
            result["zone_confidence"] = max(0.0, min(1.0, float(values["ZONE_CONFIDENCE"])))
        except ValueError:
            pass
    if "PHOTO_QUALITY_SCORE" in values:
        digits = re.sub(r"[^\d.]", "", values["PHOTO_QUALITY_SCORE"])
        if digits:
            try:
                result["photo_quality_score"] = max(0, min(100, int(float(digits))))
            except ValueError:
                pass
    if "MANNEQUIN_EXISTS" in values:
        exists = values["MANNEQUIN_EXISTS"].strip().lower() in {"true", "yes", "1", "예", "있음"}
        mannequin: dict[str, Any] = {"exists": exists}
        mannequin_type = values.get("MANNEQUIN_TYPE", "").strip()
        if mannequin_type:
            mannequin["type"] = mannequin_type
            lowered = mannequin_type.lower()
            if "headless" in lowered:
                mannequin["has_head"] = False
            elif "head" in lowered:
                mannequin["has_head"] = True
        result["mannequin"] = mannequin
    return result


def _merge_header_fields(parsed: dict[str, Any], content: str) -> None:
    # parsed에 이미 있는 값(정상 JSON 응답)은 절대 덮어쓰지 않고, 마크다운 폴백 등으로
    # 통째로 빠진 필드만 채웁니다. setdefault는 키의 '존재 여부'만 보므로, 모델이 JSON
    # 스키마를 제대로 지켜 이 필드들을 이미 채웠다면 아무 영향이 없습니다.
    header = _extract_header_fields(content)
    if "total_score" in header:
        parsed.setdefault("total_score", header["total_score"])
    if "ai_detected_zone" in header:
        parsed.setdefault("ai_detected_zone", header["ai_detected_zone"])
    if "zone_confidence" in header:
        parsed.setdefault("zone_confidence", header["zone_confidence"])
    if "photo_quality_score" in header:
        photo_quality = parsed.setdefault("photo_quality", {})
        if isinstance(photo_quality, dict):
            photo_quality.setdefault("score", header["photo_quality_score"])
    if "mannequin" in header:
        mannequin = parsed.setdefault("mannequin", {})
        if isinstance(mannequin, dict):
            for key, value in header["mannequin"].items():
                mannequin.setdefault(key, value)


def parse_model_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        markdown_result = _parse_markdown_sections(cleaned)
        if markdown_result is not None:
            return markdown_result
        raise


def _request_and_parse(
    base_payload: dict[str, Any], requested_model: str, deadline: float
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, list[str]]:
    # deadline은 time.monotonic() 기준 절대 시각입니다. 모델/스키마 폴백 후보가 여러 개일
    # 수 있어서, 각 후보에 남은 예산만큼만 timeout을 주고 예산이 바닥나면 더 시도하지 않고
    # 즉시 반환합니다 — 후보마다 고정된 timeout을 다시 다 주면 폴백 개수만큼 시간이
    # 곱해져서 analyze_images의 전체 예산을 쉽게 넘깁니다.
    errors: list[str] = []
    raw = None
    parsed = None
    model = requested_model
    for candidate_model in nim_model_candidates(requested_model):
        request_variants = [
            {
                **base_payload,
                "model": candidate_model,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "vmd_evaluation_result", "strict": True, "schema": vmd_json_schema()},
                },
            },
            {**base_payload, "model": candidate_model},
        ]
        for payload in request_variants:
            remaining = deadline - time.monotonic()
            if remaining < _MIN_ATTEMPT_SECONDS:
                errors.append(f"{candidate_model}: skipped, remaining budget {remaining:.0f}s < {_MIN_ATTEMPT_SECONDS}s")
                return raw, parsed, model, errors
            call_timeout = int(min(settings.nim_timeout_seconds, remaining))
            try:
                candidate_raw = nim_request(payload, timeout=call_timeout)
            except RuntimeError as exc:
                message = str(exc)
                errors.append(f"{candidate_model}: {message}")
                if "HTTP 400" not in message and not is_retriable_nim_error(message):
                    raise
                continue
            try:
                message = candidate_raw["choices"][0]["message"]
                content_text = message.get("content", "")
                candidate_parsed = parse_model_content(content_text)
            except Exception as exc:
                errors.append(f"{candidate_model}: invalid JSON response: {exc}")
                continue
            _merge_header_fields(candidate_parsed, content_text)
            raw = candidate_raw
            parsed = candidate_parsed
            model = candidate_model
            break
        if raw is not None:
            break
    return raw, parsed, model, errors


def analyze_images(images: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    if not images:
        raise ValueError("At least one image is required.")

    cache_key = build_cache_key(images, options)
    cached = get_cached_result(cache_key)
    if cached is not None:
        return cached

    request_start = time.monotonic()
    requested_model = (options.get("modelName") or settings.nim_model).strip()
    zone = normalize_zone(options.get("zoneMode"))
    base_text = build_user_text(options, len(images)) + "\n\n" + schema_instruction()
    image_items = image_content_items(images)
    base_temperature = float(options.get("temperature", 0.2) or 0.2)
    # 예시 JSON을 없앤 뒤로 모델이 예시의 문장 밀도를 참고하지 못해 criteria_evaluations를
    # 포함한 전체 응답이 예전보다 길어지고, 2200 토큰에서는 종종 응답이 중간에 잘려
    # (finish_reason="length") 파싱 실패 -> 모델/스키마 폴백 재시도로 이어져 훨씬 오래 걸리는
    # 것을 실측으로 확인했습니다. 여유 있게 잡아 잘림 자체를 없앱니다.
    max_tokens = int(options.get("maxTokens", 6000) or 6000)

    deadline = request_start + _TOTAL_TIME_BUDGET_SECONDS

    errors: list[str] = []
    raw = None
    parsed = None
    model = requested_model
    problems: list[str] = []
    corrective_note = ""
    for attempt in range(_MAX_CONTENT_RETRIES + 1):
        remaining = deadline - time.monotonic()
        if attempt > 0 and remaining < _MIN_ATTEMPT_SECONDS:
            # 콘텐츠 품질 재시도를 하기엔 남은 예산이 너무 적음 (1차 호출이 오래 걸렸다는
            # 뜻). Vercel 300초 벽을 넘기느니 문제가 있더라도 1차 결과를 그대로 반환합니다.
            break
        content = [{"type": "text", "text": base_text + corrective_note}]
        content.extend(image_items)
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": content},
            ],
            "temperature": min(base_temperature + 0.3 * attempt, 1.0),
            "max_tokens": max_tokens,
        }
        attempt_raw, attempt_parsed, attempt_model, attempt_errors = _request_and_parse(
            payload, requested_model, deadline=deadline
        )
        errors.extend(attempt_errors)
        if attempt_raw is None:
            continue
        raw, parsed, model = attempt_raw, attempt_parsed, attempt_model
        problems = _find_content_problems(parsed)
        if not problems:
            break
        corrective_note = _build_corrective_note(problems)
    if raw is None:
        raise RuntimeError("NIM request failed after model and JSON fallbacks: " + " | ".join(errors))

    parsed = apply_defaults(parsed, zone)
    parsed["user_selected_zone"] = zone
    parsed["grade"] = parsed.get("grade") or grade_from_score(parsed.get("total_score"))
    result = {"result": parsed, "raw": raw, "model": model}
    if problems:
        result["content_warnings"] = problems
    store_result(cache_key, result)
    return result
