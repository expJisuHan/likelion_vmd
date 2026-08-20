# Technical Design

## 1. Architecture Overview

VMD Insight는 React 프론트엔드와 FastAPI 백엔드로 구성된다. 백엔드는 NVIDIA NIM의 OpenAI-compatible `/v1/chat/completions` API를 호출해 비전 분석을 수행하고, 결과를 JSON/Excel/PDF로 저장한다.

```text
Browser
  |
  | React UI, image data URL, options
  v
FastAPI Backend
  |
  | OpenAI-compatible chat completions
  v
NVIDIA NIM
  |
  | structured JSON / text
  v
FastAPI Backend
  |
  | normalize, cache, export
  v
Browser / outputs
```

## 2. Runtime Assumptions

- OS: Windows local development
- Backend: FastAPI + Uvicorn
- Frontend: React 18 + Vite
- Default backend URL: `http://127.0.0.1:8000`
- NIM base URL: `https://integrate.api.nvidia.com/v1`
- Default model: `meta/llama-3.2-11b-vision-instruct`
- Output path: local `outputs/`, Vercel `/tmp/outputs`

## 3. Backend Design

### 3.1 Stack

- `fastapi`, `uvicorn`
- `pydantic` request validation
- `python-dotenv` environment loading
- `urllib.request` for OpenAI-compatible NIM calls
- `openpyxl` for Excel export with pure-Python XLSX fallback
- `reportlab` for PDF export
- `Pillow` for image resize/thumbnail handling

### 3.2 Entry Point

- `backend/run.py`: local Uvicorn runner
- `backend/app/main.py`: FastAPI app, middleware, router registration, global exception handler

Static routing is registered last because `api/static.py` includes catch-all frontend serving.

### 3.3 Configuration

`backend/app/config.py` loads `backend/.env` first and then project-root `.env`.

Important environment variables:

- `NIM_API_KEY`
- `NIM_BASE_URL`
- `NIM_MODEL`
- `NIM_FALLBACK_MODELS`
- `NIM_TIMEOUT_SECONDS`
- `NIM_IMAGE_MAX_BYTES`
- `NIM_IMAGE_MAX_DIMENSION`
- `HOST`, `PORT`, `RELOAD`, `DEBUG`
- `CORS_ORIGINS`
- `APP_ACCESS_KEY`
- `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`
- `MAX_IMAGES_PER_REQUEST`, `MAX_IMAGE_BYTES`
- `ANALYSIS_CACHE_ENABLED`, `ANALYSIS_CACHE_TTL_SECONDS`, `ANALYSIS_CACHE_MAX_ENTRIES`
- `FRONTEND_DIR`, `OUTPUT_DIR`

## 4. API Design

### 4.1 Health

`GET /api/health`

Checks `/models` on the configured NIM endpoint.

Response includes:

- `nim`
- `message`
- `baseUrl`
- `defaultModel`
- `fallbackModels`

### 4.2 VMD Single Analysis

`POST /api/analyze`

Request:

```json
{
  "images": [
    {
      "name": "store.jpg",
      "dataUrl": "data:image/jpeg;base64,..."
    }
  ],
  "options": {
    "zoneMode": "VP",
    "storeType": "UNKNOWN",
    "tone": "SOFT_CRITICAL",
    "criteria": ["구성/레이아웃", "사진 품질"],
    "focusKeywords": [],
    "extraCriteria": "",
    "modelName": null,
    "temperature": 0.2,
    "maxTokens": 6000
  }
}
```

Response:

```json
{
  "ok": true,
  "result": {},
  "jsonPath": "outputs/json/...",
  "excelPath": "outputs/excel/...",
  "excelBase64": "...",
  "downloadUrl": "/api/download?file=...",
  "pdfPath": "outputs/pdf/...",
  "pdfBase64": "...",
  "pdfDownloadUrl": "/api/download?file=...",
  "elapsedSeconds": 12.34
}
```

### 4.3 VMD Batch Analysis

`POST /api/batch-analyze`

Uses the same request body as `/api/analyze`, but each image is analyzed independently. Per-image failures are converted into error records so that the whole batch can still export.

### 4.4 Consumer Photo Insight

`POST /api/consumer/photo-insight`

Request:

```json
{
  "image": {
    "name": "photo.jpg",
    "dataUrl": "data:image/jpeg;base64,..."
  }
}
```

Flow:

1. Validate image and resize for model limits.
2. Demo image shortcut if applicable.
3. Run a floor-visible classifier.
4. If floor is visible, run accessibility/space prompt.
5. Otherwise run clothing/item prompt.
6. Return structured items and optional narration text.

### 4.5 Consumer Q&A

- `POST /api/consumer/ask`: answers product questions from catalog candidates.
- `POST /api/consumer/catalog-products`: returns actual product card data for a detected item type.

### 4.6 Download

`GET /api/download?file=...`

Only generated output paths should be downloadable. The API returns Excel, PDF, or JSON files created under the configured output directory.

## 5. Frontend Design

### 5.1 Stack

- React 18
- Vite
- `@phosphor-icons/react`
- CSS by page-level stylesheet files

### 5.2 App Views

`frontend/src/App.jsx` switches between:

- `NewHomepage`: 관리자/VMD 분석 페이지
- `ConsumerPage`: 소비자 사진 안내 페이지

### 5.3 Admin Page

Main capabilities:

- Image upload and browser camera capture
- VP/PP/IP zone selection
- Store type and tone selection
- Criteria checkboxes and custom criteria
- Single analysis and batch Excel/PDF export
- Quick result cards
- Detail drawer with score, zone, photo quality, mannequin, obstacles, criteria, comments

### 5.4 Consumer Page

Main capabilities:

- Image upload and browser camera capture
- Text size and high-contrast preferences saved in `localStorage`
- Photo insight modal
- Audio narration using Web Speech API
- Product detail view with related products
- Product Q&A history
- Keyboard focus management and modal focus trap

## 6. NIM Integration

`backend/app/services/nim_client.py` owns all NIM HTTP calls.

Key behavior:

- Adds `Authorization: Bearer {NIM_API_KEY}`
- Calls `{NIM_BASE_URL}/chat/completions`
- Calls `{NIM_BASE_URL}/models` for health
- Supports fallback model candidates
- Treats 429, 5xx, timeout, overload, unavailable, and vision capability errors as retriable

## 7. Prompt and Schema Strategy

### 7.1 VMD Analysis

VMD prompts define:

- VP/PP/IP zone criteria
- User-selected zone evaluation rule
- Separate AI-detected zone and confidence
- Mannequin existence/type/head judgment
- Obstacle distinction between product, prop, structure, and obstruction
- Photo quality scoring
- Soft but critical expert tone
- Structured result fields for export

Expected result fields:

- `user_selected_zone`
- `ai_detected_zone`
- `zone_confidence`
- `store_type_assumption`
- `photo_quality`
- `mannequin`
- `obstacles`
- `scores`
- `criteria_evaluations`
- `total_score`
- `grade`
- `positive_points`
- `critical_issues`
- `improvement_suggestions`
- `final_summary`

### 7.2 Consumer Insight

The consumer flow uses separate prompts for:

- floor-visible classification
- clothing item extraction
- accessibility/space guidance
- catalog-based recommendation answers

The clothing flow retries when the model ignores the expected schema or leaks stale accessibility fields into product output.

## 8. Export Design

### 8.1 Excel

`backend/app/export/excel_export.py`

- Uses `openpyxl` when installed.
- Falls back to a pure-Python XLSX writer.
- Embeds uploaded image thumbnails when possible.
- Freezes the header row.
- Adjusts columns by zone and selected criteria.

Excel rows include:

- Uploaded image thumbnail/name
- Selected zone and detected zone
- Confidence, score, grade
- Photo quality fields
- Mannequin fields
- Obstacle fields
- Criteria scores
- Positive/critical/improvement text
- JSON path, status, error
- Feedback columns for later expert review

### 8.2 PDF

`backend/app/export/pdf_export.py`

Creates a human-readable summary report for single or batch results using ReportLab.

### 8.3 JSON

`services/records.py` stores normalized raw result records under `outputs/json`.

## 9. Reliability and Safety

- `request_guard.py` enforces optional app key, rate limit, image count, and image byte size.
- `analysis_cache.py` caches identical image/options analysis requests.
- Global exception handler returns friendly errors and hides internals unless `DEBUG=true`.
- Batch mode records per-image errors and continues processing.
- Consumer flow resizes model-bound images to NIM limits before request.

## 10. Deployment Notes

- `vercel.json` exists at project root and frontend level.
- On Vercel, outputs must be written to `/tmp/outputs`.
- `NIM_API_KEY` must be set in deployment environment variables.
- `DEBUG=false` should remain the production default.
- `/api/debug-env` is a temporary diagnostic route and should be removed or protected before public deployment.

## 11. Future Technical Work

- Remove or protect `/api/debug-env`.
- Add automated backend tests for request guards, schema parsing, and batch error records.
- Add frontend build/interaction checks.
- Add sample image fixtures for repeatable VMD and consumer flow validation.
- Consider async HTTP client if concurrent traffic grows.
