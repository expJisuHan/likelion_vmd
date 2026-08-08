# AX R&D VMD Evaluation Web App

VMD 담당자가 매장 사진을 업로드하면 LM Studio에서 실행 중인 Gemma 12B 모델로 IP/PP/VP 존을 판별하고, VMD 평가 점수와 개선 코멘트를 JSON 및 Excel로 정리하는 로컬 웹앱입니다.

현재 단계의 목표는 속도 최적화보다 “AI 결과가 실제 VMD 평가에 쓸 만한지 확인할 수 있는 구조”를 만드는 것입니다. 따라서 Gemma 12B 원본 모델을 우선 사용하고, QAT 모델은 추후 경량화 비교 단계에서 검토합니다.

## 주요 기능

- 이미지 여러 장 업로드 및 미리보기
- IP/PP/VP 존 자동 판별 또는 사용자 지정
- 단일 브랜드/편집숍 등 매장 유형 선택
- 균형/비판적/부드러운 비판 톤 선택
- 평가 항목 선택 및 추가 기준 입력
- LM Studio OpenAI-compatible API 연동
- 고정 JSON 스키마 기반 VMD 분석 결과 수신
- 총점, 항목별 점수, 사진 품질, 마네킹, 방해물, 개선 제안 표시
- 단일 분석 결과 및 여러 이미지 일괄 분석 결과를 Excel로 저장
- 패디과/VMD 담당자 피드백용 Excel 컬럼 포함

## 실행 방법

1. LM Studio에서 Gemma 12B 원본 모델을 로드합니다.
2. LM Studio의 Local Server를 켭니다.
3. 기본 서버 주소가 아래와 같은지 확인합니다.

```text
http://127.0.0.1:1234/v1
```

4. 이 프로젝트 폴더에서 웹앱 서버를 실행합니다.

```powershell
python app/server.py
```

5. 브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

## 설정

환경변수로 LM Studio 주소와 모델명을 바꿀 수 있습니다.

```powershell
$env:LMSTUDIO_BASE_URL="http://127.0.0.1:1234/v1"
$env:LMSTUDIO_MODEL="google/gemma-4-12b"
python app/server.py
```

LM Studio에서 실제로 표시되는 모델명이 다르면 웹앱의 모델명 입력칸에 그대로 입력하면 됩니다.

## 폴더 구조

```text
.
├─ README.md
├─ PRD.md
├─ TECHNICAL_DESIGN.md
├─ CHECKLIST.md
├─ requirements.txt
├─ app/
│  ├─ server.py
│  └─ static/
│     ├─ index.html
│     ├─ styles.css
│     └─ app.js
├─ data/
│  └─ samples/
└─ outputs/
   ├─ excel/
   └─ json/
```

## 현재 프로토타입 범위

- 프론트엔드는 정적 HTML/CSS/JavaScript로 구현했습니다.
- 백엔드는 추가 설치를 줄이기 위해 Python 표준 라이브러리 기반 HTTP 서버로 구현했습니다.
- Excel 저장은 `openpyxl`을 우선 사용합니다.
- `openpyxl`이 없는 환경에서도 내장 XLSX 생성기로 `.xlsx` 파일을 저장합니다.
- 실제 분석 품질 검증은 LM Studio에서 Gemma 12B를 켠 뒤 샘플 이미지로 진행해야 합니다.
