# Technical Design

## 1. Architecture Overview

브라우저에서 이미지를 업로드하면 로컬 Python 서버가 LM Studio의 OpenAI-compatible API를 호출하고, 모델 응답을 JSON으로 파싱한 뒤 화면 표시와 Excel 저장을 처리합니다.

```text
Browser
  |
  | images + options
  v
Local Python Web Server
  |
  | POST /v1/chat/completions
  v
LM Studio Server
  |
  | strict JSON result
  v
Local Python Web Server
  |
  | result rendering + Excel export
  v
Browser / outputs
```

## 2. Runtime Assumptions

- OS: Windows
- App server: `http://127.0.0.1:8000`
- LM Studio server: `http://127.0.0.1:1234/v1`
- Model: `google/gemma-4-12b`
- Priority: VMD 결과 정확도와 평가 가능성 확인
- Later option: Gemma 12B QAT로 속도/메모리 비교

## 3. Backend

### 3.1 Stack

- Python 3
- `http.server`, `urllib.request`, `json`, `base64`
- `openpyxl` for Excel export
- No FastAPI dependency in the first local prototype

### 3.2 Main Responsibilities

- 정적 웹앱 파일 제공
- 이미지 data URL 수신
- VMD 분석 프롬프트 생성
- LM Studio API 호출
- 모델 응답 JSON 파싱
- 결과 JSON 저장
- Excel 파일 생성
- Excel 다운로드 제공
- LM Studio 연결 상태 확인

### 3.3 API Endpoints

#### `GET /`

정적 웹앱 화면을 반환합니다.

#### `GET /api/health`

앱 서버 상태와 LM Studio `/models` 연결 상태를 확인합니다.

#### `POST /api/analyze`

업로드된 이미지들을 하나의 VMD 장면으로 묶어 분석합니다.

Request JSON:

```json
{
  "images": [
    {
      "name": "store.jpg",
      "data_url": "data:image/jpeg;base64,..."
    }
  ],
  "zone_mode": "VP",
  "store_type": "UNKNOWN",
  "tone": "SOFT_CRITICAL",
  "criteria": ["layout", "brand_fit"],
  "extra_criteria": "",
  "lmstudio_base_url": "http://127.0.0.1:1234/v1",
  "model": "google/gemma-4-12b"
}
```

Response JSON:

```json
{
  "ok": true,
  "mode": "single",
  "result": {},
  "excel_file": "outputs/excel/vmd_single_YYYYMMDD_HHMMSS.xlsx",
  "json_file": "outputs/json/vmd_result_YYYYMMDD_HHMMSS.json"
}
```

#### `POST /api/batch-analyze`

이미지별로 독립 분석을 수행하고 결과를 Excel 한 파일로 저장합니다.

#### `GET /api/download?file=...`

`outputs/` 하위에 생성된 Excel 또는 JSON 파일을 다운로드합니다.

## 4. Frontend

### 4.1 UI Direction

VMD 담당자가 쓰는 도구이므로 과한 장식보다 고급스럽고 조용한 업무 화면을 목표로 합니다.

- 프라다/애플 사이트처럼 절제된 여백
- 검정, 아이보리, 샴페인 골드 계열 포인트
- 큰 장식 요소보다 선명한 타이포그래피와 정돈된 패널
- 이미지 미리보기와 평가 결과가 바로 스캔되는 구조

### 4.2 Main Views

- Upload panel: 이미지 선택, 드래그 앤 드롭, 미리보기
- Control panel: 존, 매장 유형, 응답 톤, 모델명, 평가 항목
- Action panel: 단일 분석, 이미지별 일괄 분석
- Result panel: 총점, 존 판별, 품질, 마네킹, 방해물, 코멘트, Excel 다운로드

## 5. LM Studio Integration

### 5.1 Base URL

```text
http://127.0.0.1:1234/v1
```

### 5.2 Chat Completion Endpoint

```text
POST /chat/completions
```

### 5.3 Payload Shape

```json
{
  "model": "google/gemma-4-12b",
  "messages": [
    {
      "role": "system",
      "content": "VMD expert system prompt"
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Analyze these images..."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,..."
          }
        }
      ]
    }
  ],
  "temperature": 0.2,
  "max_tokens": 2400,
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "vmd_evaluation_result",
      "schema": {}
    }
  }
}
```

## 6. Prompt Rules

- 반드시 JSON만 반환하도록 요청합니다.
- IP/PP/VP 목적과 평가 기준을 프롬프트에 명시합니다.
- 사용자가 존을 지정하면 해당 존 기준으로 평가합니다.
- VP/PP/IP 중 사용자가 선택한 존 기준으로 평가하고, AI 판단 존과 신뢰도는 별도로 반환합니다.
- 마네킹이 없으면 마네킹 관련 개선 코멘트를 쓰지 않게 합니다.
- 마네킹, 행거, 착장, 구조물, 방해물을 구분하게 합니다.
- 사진 품질 문제는 별도 항목으로 기록합니다.
- 칭찬만 하지 않고 개선 가능한 문제점을 구체적으로 말하게 합니다.
- 비판적이되 사용자에게 전달 가능한 부드러운 전문가 톤을 유지합니다.

## 7. JSON Schema Fields

- `user_selected_zone`
- `ai_detected_zone`
- `zone_confidence`
- `store_type_assumption`
- `photo_quality`
- `mannequin`
- `obstacles`
- `scores`
- `total_score`
- `grade`
- `positive_points`
- `critical_issues`
- `improvement_suggestions`
- `final_summary`

## 8. Excel Export

Output path:

```text
outputs/excel/vmd_results_YYYYMMDD_HHMMSS.xlsx
```

Main columns:

- 이미지 파일명
- 사용자 지정 존
- AI 판단 존
- 존 판단 신뢰도
- 매장 유형
- 사진 품질 점수 및 코멘트
- 재촬영 필요 여부
- 마네킹 유무/유형/코멘트
- 방해물 유무/목록
- 총점/등급/항목별 점수
- 긍정 포인트
- 비판적 문제점
- 개선 제안
- 최종 요약
- 원본 JSON 경로
- 처리 상태/오류 메시지
- 패디과 피드백
- 수정 필요 여부
- 오류 유형

## 9. Error Handling

- LM Studio 연결 실패: 화면에 서버 확인 메시지 표시
- JSON 파싱 실패: 원본 응답 일부와 오류 메시지 반환
- 일부 이미지 실패: batch mode에서는 다음 이미지 분석을 계속 진행
- Excel 저장 실패: 오류 메시지 반환
- `openpyxl` 없음: CSV로 대체 저장

## 10. Development Phases

### Phase 1: Documentation

- README, PRD, technical design, checklist 작성

### Phase 2: Web App MVP

- 로컬 서버 구현
- 정적 프론트엔드 구현
- LM Studio 호출 구현
- JSON/Excel 저장 구현

### Phase 3: Model Quality Test

- Gemma 12B 원본 모델로 샘플 이미지 분석
- IP/PP/VP 판별 정확도 확인
- 마네킹/방해물/사진 품질 코멘트 검증
- 패디과 학생 피드백과 비교

### Phase 4: Refinement

- 프롬프트 수정
- Excel 컬럼 조정
- Before/After 비교 기능 검토
- RAG 기반 피드백 반영 검토
