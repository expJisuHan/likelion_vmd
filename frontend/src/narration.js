// 분석 결과 JSON을 TTS로 자연스럽게 읽을 수 있는 한국어 문장으로 바꿔줍니다.

function toSentence(text) {
  if (!text) return '';
  const trimmed = String(text).trim();
  if (!trimmed) return '';
  return /[.!?다요]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

function toNumberedList(items) {
  const clean = (items || []).map((item) => String(item).trim()).filter(Boolean);
  if (!clean.length) return '';
  return clean.map((item, index) => `${index + 1}번, ${toSentence(item)}`).join(' ');
}

export function buildResultNarration(result, batchInfo) {
  if (!result) return '';
  const parts = [];

  parts.push(
    batchInfo?.count
      ? `사진 ${batchInfo.count}장 중 첫 번째 사진의 분석 결과를 읽어 드립니다.`
      : '분석 결과를 읽어 드립니다.'
  );

  parts.push(
    `총점은 ${result.total_score ?? '정보 없음'}점이고, 구역은 ${result.ai_detected_zone || '알 수 없음'}입니다.`
  );

  const photo = result.photo_quality || {};
  if (photo.score != null) {
    parts.push(
      `사진 품질 점수는 ${photo.score}점입니다.${photo.needs_retake ? ' 다시 촬영하는 것을 권장합니다.' : ''}`
    );
  }

  const mannequin = result.mannequin || {};
  parts.push(mannequin.exists ? '마네킹이 있습니다.' : '마네킹은 없습니다.');

  const criteria = Array.isArray(result.criteria_evaluations)
    ? result.criteria_evaluations.filter((item) => item && item.criterion)
    : [];
  if (criteria.length) {
    parts.push('항목별 평가입니다.');
    criteria.forEach((item) => {
      const scoreText = item.score != null ? `${item.score}점` : '점수 없음';
      const detail = toSentence(item.suggestion || item.evidence || '설명이 없습니다');
      parts.push(`${item.criterion}, ${scoreText}. ${detail}`);
    });
  }

  if (result.positive_points?.length) {
    parts.push('잘된 점입니다.');
    parts.push(toNumberedList(result.positive_points));
  }

  if (result.critical_issues?.length) {
    parts.push('고치면 좋은 점입니다.');
    parts.push(toNumberedList(result.critical_issues));
  }

  if (result.improvement_suggestions?.length) {
    parts.push('개선 제안입니다.');
    parts.push(toNumberedList(result.improvement_suggestions));
  }

  const obstacles = Array.isArray(result.obstacles) ? result.obstacles : [];
  if (obstacles.length) {
    parts.push('감지된 방해물입니다.');
    parts.push(
      obstacles
        .map(
          (item, index) =>
            `${index + 1}번, ${item.object || '알 수 없는 물건'}, 위치는 ${item.location || '위치 정보 없음'}입니다.`
        )
        .join(' ')
    );
  }

  if (result.final_summary) {
    parts.push(`최종 요약입니다. ${toSentence(result.final_summary)}`);
  }

  parts.push('읽기를 마쳤습니다.');

  return parts.filter(Boolean).join(' ');
}
