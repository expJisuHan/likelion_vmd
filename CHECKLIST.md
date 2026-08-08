# Development Checklist

## 1. Project Setup

- [x] 프로젝트 폴더 구조 생성
- [x] Python 실행 환경 결정
- [x] 추가 설치를 줄이는 로컬 Python 서버 방식 결정
- [x] Excel 저장용 `openpyxl` 사용 결정
- [x] 이미지 처리 방식 결정: 브라우저 data URL 전송
- [x] 환경변수 설정 방식 결정: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`
- [x] `outputs/` 폴더 생성
- [x] `data/samples/` 폴더 생성

## 2. LM Studio Preparation

- [x] LM Studio 설치 확인
- [x] Gemma 12B 원본 모델 다운로드 확인
- [x] Gemma 12B 모델 로드
- [x] LM Studio server 켜기
- [x] 기본 서버 주소 반영: `http://127.0.0.1:1234/v1`
- [x] 기본 모델명 변경: `google/gemma-4-12b`
- [ ] 단일 이미지 테스트 호출 성공
- [ ] 여러 이미지 테스트 호출 성공
- [ ] JSON schema 응답 테스트

## 3. Prompt and JSON Schema

- [x] VMD 전문가 system prompt 작성
- [x] IP/PP/VP 존 정의 포함
- [x] 사용자가 존을 지정한 경우 평가 규칙 작성
- [x] AI 자동 존 판단 규칙 작성
- [x] 마네킹 유무 판단 규칙 작성
- [x] 마네킹이 없을 때 마네킹 언급 금지 규칙 작성
- [x] 구조물/소품/상품/방해물 구분 규칙 작성
- [x] 사진 품질 평가 규칙 작성
- [x] 비판적이지만 부드러운 코멘트 규칙 작성
- [x] JSON schema 초안 작성
- [x] JSON 파싱 실패 시 오류 저장 방식 결정

## 4. Backend MVP

- [x] 로컬 Python 웹 서버 생성
- [x] 정적 파일 서빙 설정
- [x] `/api/health` 구현
- [x] LM Studio 연결 확인 구현
- [x] 이미지 업로드 API 구현
- [x] 이미지 data URL 전달 구현
- [x] prompt builder 구현
- [x] LM Studio client 구현
- [x] JSON 응답 파싱 구현
- [x] JSON schema 요청 구현
- [x] LM Studio JSON schema 400 오류 시 호환 모드 재시도 구현
- [x] LM Studio 모델 로드 실패 오류 메시지 처리
- [x] 결과 JSON 파일 저장 구현
- [x] Excel exporter 구현
- [x] Excel 다운로드 API 구현

## 5. Frontend MVP

- [x] 메인 화면 구성
- [x] 이미지 업로드 버튼
- [x] 모바일 촬영 input 지원
- [x] 업로드 이미지 미리보기
- [x] 이미지 제거 기능
- [x] 존 선택 UI: `VP`, `PP`, `IP`
- [x] 매장 유형 선택 UI
- [x] 분석 톤 선택 UI
- [x] 평가 항목 체크리스트
- [x] 사용자 추가 평가 항목 입력
- [x] 분석 실행 버튼
- [x] 분석 진행 상태 표시
- [x] 결과 카드 표시
- [x] 항목별 점수 표시
- [x] 상세 코멘트 표시
- [x] Excel 다운로드 버튼

## 6. Result Fields

- [x] 사용자 지정 존 표시
- [x] AI 판단 존 표시
- [x] 존 판단 신뢰도 표시
- [x] 사진 품질 점수 표시
- [x] 사진 품질 코멘트 표시
- [x] 재촬영 필요 여부 표시
- [x] 마네킹 유무 표시
- [x] 마네킹 유형 표시
- [x] 마네킹 코멘트 표시
- [x] 방해물 유무 표시
- [x] 방해물 목록 표시
- [x] 총점 표시
- [x] 등급 표시
- [x] 항목별 점수 표시
- [x] 긍정 포인트 표시
- [x] 비판적 문제점 표시
- [x] 개선 제안 표시
- [x] 최종 요약 표시

## 7. Excel Batch Mode

- [x] 여러 이미지 업로드 방식 결정
- [x] 이미지별 분석 loop 구현
- [x] 실패 이미지가 있어도 계속 진행
- [x] 처리 상태 컬럼 기록
- [x] 오류 메시지 컬럼 기록
- [x] 원본 JSON 경로 컬럼 기록
- [x] 패디과 피드백 컬럼 추가
- [x] 수정 필요 여부 컬럼 추가
- [x] 오류 유형 컬럼 추가
- [x] Excel 파일 생성 검증
- [x] Excel 파일 열림 검증

## 8. Quality Checks

- [ ] 마네킹 없는 사진에서 마네킹 언급이 줄었는지 확인
- [ ] 머리 있는 마네킹과 바디 마네킹 구분 확인
- [ ] 의자/상자/공기청정기 등 방해물 판단 확인
- [ ] 사진 기울어짐 코멘트 확인
- [ ] 배경 간섭 코멘트 확인
- [ ] IP/PP/VP 사용자 지정 시 해당 존 기준으로 평가하는지 확인
- [ ] 선택 존 기준 평가와 AI 존 판단 결과/신뢰도 반환 확인
- [ ] 칭찬만 하지 않고 비판적 문제점이 나오는지 확인
- [ ] 너무 공격적이지 않은 톤인지 확인
- [ ] Excel 결과가 피드백에 적합한지 확인

## 9. Demo Readiness

- [ ] 샘플 이미지 3~5장 준비
- [x] LM Studio 서버 실행 절차 문서화
- [x] 웹앱 실행 명령 정리
- [ ] 단일 분석 데모 성공
- [ ] 여러 장 분석 데모 성공
- [ ] Excel 저장 데모 성공
- [x] JSON 결과 원본 확인 가능
- [x] 발표용 설명 흐름 정리

## 10. Future Work

- [ ] 전문가 피드백 Excel을 RAG DB로 변환
- [ ] 유사 이미지 검색 실험
- [ ] Before/After 비교 화면 설계
- [ ] 상품 배치 추천 기능 설계
- [ ] 개선안 이미지 생성 기능 검토
- [ ] QAT 모델 성능/속도 비교
- [ ] React/Vite 전환 여부 검토
- [ ] 모바일 UI 개선
