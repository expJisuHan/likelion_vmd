# Development Checklist

## 1. Project Setup

- [x] 프로젝트 폴더 구조 생성
- [x] `backend/`, `frontend/`, `outputs/`, `data/samples/` 분리
- [x] FastAPI 백엔드 구조 구성
- [x] React/Vite 프론트엔드 구조 구성
- [x] 환경변수 예시 파일 작성: `backend/.env.example`
- [x] 결과 저장 폴더 준비: `outputs/json`, `outputs/excel`
- [x] PDF 결과 저장 경로 지원: `outputs/pdf`
- [x] Vercel 배포 설정 파일 추가

## 2. Backend

- [x] `python run.py` 실행 진입점 구현
- [x] FastAPI 앱 및 라우터 등록
- [x] CORS 설정
- [x] 전역 예외 핸들러 구현
- [x] `.env` 기반 설정 로딩 구현
- [x] 로컬/Vercel 출력 경로 분기 구현
- [x] `GET /api/health` 구현
- [x] `POST /api/analyze` 구현
- [x] `POST /api/batch-analyze` 구현
- [x] `GET /api/download` 구현
- [x] `POST /api/consumer/photo-insight` 구현
- [x] `POST /api/consumer/ask` 구현
- [x] `POST /api/consumer/catalog-products` 구현
- [x] 정적 프론트엔드 서빙 구현

## 3. NIM Integration

- [x] NVIDIA NIM OpenAI-compatible client 구현
- [x] `NIM_API_KEY`, `NIM_BASE_URL`, `NIM_MODEL` 설정 지원
- [x] `/models` 연결 확인 구현
- [x] 비전 모델 요청 페이로드 구현
- [x] JSON schema 응답 요청 구현
- [x] 타임아웃 설정 지원
- [x] fallback model 후보 지원
- [x] 429/5xx/timeout 등 재시도 가능 오류 판정 구현
- [ ] 실제 NIM API 키로 `/api/health` 성공 확인
- [ ] 단일 VMD 이미지 분석 실측 성공 확인
- [ ] 소비자 사진 안내 실측 성공 확인

## 4. VMD Prompt and Result Schema

- [x] VMD 전문가 system prompt 작성
- [x] VP/PP/IP 존 정의 포함
- [x] 사용자 선택 존 기준 평가 규칙 작성
- [x] AI 판단 존/신뢰도 반환 규칙 작성
- [x] 마네킹 유무/유형/머리 유무 판단 규칙 작성
- [x] 마네킹이 없을 때 관련 개선 코멘트 제한
- [x] 구조물/소품/상품/방해물 구분 규칙 작성
- [x] 사진 품질 별도 평가 규칙 작성
- [x] 부드럽지만 비판적인 전문가 톤 정의
- [x] 결과 정규화 및 레코드 변환 구현
- [ ] 실제 샘플별 스키마 준수율 확인
- [ ] 마네킹 없는 사진에서 마네킹 언급 감소 확인
- [ ] 방해물 오판 사례 수집

## 5. Admin Frontend

- [x] 관리자 페이지 구현
- [x] 이미지 업로드
- [x] 모바일/브라우저 카메라 촬영
- [x] 이미지 미리보기 및 삭제
- [x] VP/PP/IP 존 선택 UI
- [x] 매장 타입 선택 UI
- [x] 평가 톤 선택 UI
- [x] 평가 항목 체크리스트
- [x] 사용자 추가 평가 기준 입력
- [x] 단일 분석 실행
- [x] 일괄 분석 실행
- [x] 진행 상태 메시지 표시
- [x] 요약 카드 표시
- [x] 상세 결과 드로어 구현
- [x] Excel 다운로드
- [x] PDF 저장
- [ ] 관리자 페이지 반응형 QA
- [ ] 긴 결과 텍스트 레이아웃 QA

## 6. Consumer Frontend

- [x] 소비자 페이지 구현
- [x] 사진 업로드
- [x] 카메라 촬영
- [x] 의류/공간 안내 모달
- [x] 관련 제품 보기
- [x] 제품 상세 보기
- [x] 제품 추가 질문
- [x] 질문/답변 히스토리
- [x] 음성 읽기
- [x] 읽기 속도 조절
- [x] 글자 크기 조절
- [x] 고대비 모드
- [x] 모달 포커스 이동 및 포커스 트랩
- [x] Esc 닫기
- [ ] 스크린리더 실기기 확인
- [ ] 모바일 카메라 권한/촬영 QA

## 7. Export

- [x] Excel exporter 구현
- [x] `openpyxl` 기반 XLSX 생성
- [x] pure-Python XLSX fallback 구현
- [x] 업로드 이미지 썸네일 삽입
- [x] 헤더 고정 및 컬럼 폭 설정
- [x] 피드백용 컬럼 포함
- [x] 처리 상태 및 오류 메시지 컬럼 포함
- [x] PDF exporter 구현
- [x] 다운로드 API 구현
- [ ] 생성된 Excel을 Microsoft Excel에서 열어 최종 확인
- [ ] 생성된 PDF 레이아웃 최종 확인

## 8. Reliability and Security

- [x] 이미지 개수 제한 구현
- [x] 이미지 용량 제한 구현
- [x] IP 기반 rate limit 구현
- [x] 선택적 `X-App-Key` 보호 구현
- [x] 분석 캐시 구현
- [x] friendly error message 처리
- [x] `DEBUG=false` 기본값 적용
- [ ] `/api/debug-env` 삭제 또는 운영 차단
- [ ] 배포 환경에서 `NIM_API_KEY` 마스킹 확인
- [ ] 다운로드 경로 traversal 방어 확인

## 9. Quality Checks

- [ ] VP/PP/IP 선택 시 해당 존 기준으로 평가하는지 확인
- [ ] 선택 존과 AI 판단 존이 별도로 반환되는지 확인
- [ ] 칭찬만 하지 않고 비판적 문제점이 나오는지 확인
- [ ] 너무 공격적이지 않은 톤인지 확인
- [ ] 사진 기울어짐/배경 간섭 코멘트 확인
- [ ] 머리 있는 마네킹과 바디 마네킹 구분 확인
- [ ] 의자/상자/공기청정기 등 방해물 판단 확인
- [ ] 소비자 의류 사진에서 실제 보이는 한 품목만 안내하는지 확인
- [ ] 소비자 공간 사진에서 이동 안전 정보가 나오는지 확인
- [ ] 카탈로그에 없는 품목 질문 시 범위를 명확히 안내하는지 확인

## 10. Demo Readiness

- [ ] 샘플 VMD 이미지 3~5장 준비
- [ ] 소비자 의류 샘플 이미지 준비
- [ ] 소비자 공간 샘플 이미지 준비
- [x] 백엔드 실행 절차 문서화
- [x] 프론트엔드 개발 서버 실행 절차 문서화
- [ ] 단일 VMD 분석 데모 성공
- [ ] 일괄 VMD 분석 데모 성공
- [ ] Excel/PDF 다운로드 데모 성공
- [ ] 소비자 사진 안내 데모 성공
- [ ] 음성 읽기 데모 성공

## 11. Future Work

- [ ] 전문가 피드백 Excel을 RAG 데이터로 변환
- [ ] 유사 이미지 검색 실험
- [ ] Before/After 비교 화면 설계
- [ ] 상품 배치 추천 기능 설계
- [ ] 개선안 이미지 생성 기능 검토
- [ ] 모델별 품질/속도 비교
- [ ] 자동화 테스트 추가
- [ ] 접근성 감사 체크리스트 작성
