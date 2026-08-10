import React, { useState } from 'react';
import './new-home.css';

function Logo() {
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true" role="img">
      <rect width="56" height="56" rx="10" fill="#ffffff" />
      <g transform="translate(6 6)" fill="#ded8ce">
        <path d="M6 34v-4h6v-18H6v-4h20v4h-6v18h6v4H6z" />
      </g>
    </svg>
  );
}

export default function NewHomepage({ onAnalyze }) {
  const [showZoneInfo, setShowZoneInfo] = useState(false);
  const [newCriterion, setNewCriterion] = useState('');
  const [validationMessage, setValidationMessage] = useState('');
  const [criteriaItems, setCriteriaItems] = useState([
    { label: '구성/레이아웃', checked: true },
    { label: '연출/분위기', checked: true },
    { label: '브랜드 적합성', checked: true },
    { label: '사진 품질', checked: true },
  ]);

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const startAndRunAnalyze = () => {
    // 스크롤로 메인 분석 섹션을 보여주고 잠깐 하이라이트합니다.
    const el = document.getElementById('mainAnalysis');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('highlight-pulse');
      setTimeout(() => el.classList.remove('highlight-pulse'), 1500);
    }
  };

  const toggleCriterion = (label) => {
    setCriteriaItems((prev) =>
      prev.map((item) => (item.label === label ? { ...item, checked: !item.checked } : item))
    );
  };

  const addCriterion = () => {
    const trimmed = newCriterion.trim();
    if (!trimmed) {
      setValidationMessage('기준을 추가해주세요');
      return;
    }

    setCriteriaItems((prev) => [...prev, { label: trimmed, checked: true }]);
    setNewCriterion('');
    setValidationMessage('');
  };

  return (
    <div className="nh-hero">
      <header className="nh-header">
        <div className="nh-brand">
          <Logo />
          <div className="nh-brand-text">
            <strong>VMD Insight</strong>
            <small>매장 VMD를 전문가처럼 평가하는 도구</small>
          </div>
        </div>
        <nav className="nh-ctas">
          <button className="cta primary" onClick={startAndRunAnalyze}>분석</button>
          <button className="cta" onClick={() => scrollTo('features')}>기능과 특징</button>
          <button className="cta ghost" onClick={() => scrollTo('usecases')}>사용 사례</button>
        </nav>
      </header>

      <section className="nh-hero-panel">
        <div className="nh-hero-copy">
          <p className="eyebrow">AX R&D Visual Merchandising</p>
          <h1>VMD Insight — 전문가 수준의 매장 평가</h1>
          <p className="hero-copy">매장 사진을 분석해 VP, PP, IP 존 판단과 VMD 개선 코멘트를 구조화합니다.</p>
        </div>
      </section>

      {/* Removed legacy preview; modern analysis layout follows */}

      <section id="mainAnalysis" className="nh-analysis-layout modern" aria-label="빠른 분석">
        <div className="nh-left modern-left">
          <div className="card upload-card">
              <div className="card-head">
                <strong>이미지 업로드</strong>
                <span className="muted">이미지를 넣고 빠르게 분석해보세요</span>
              </div>
            <label className="dropzone" htmlFor="imageInput">
              <input id="imageInput" type="file" accept="image/*" multiple />
              <div className="drop-inner">
                <div className="drop-icon">📷</div>
                <div>
                  <div className="drop-title">이미지 선택 또는 드래그</div>
                  <div className="drop-copy">JPG/PNG, 최대 권장 해상도 4K</div>
                </div>
              </div>
            </label>
            <input id="cameraFallbackInput" className="visually-hidden" type="file" accept="image/*" capture="environment" />

            <div className="thumb-strip" id="previewGrid" aria-label="업로드 이미지 미리보기"></div>

            <div className="upload-actions">
              <button className="btn-outline" id="startCameraBtn" type="button">카메라</button>
              <button className="btn-ghost" id="capturePhotoBtn" type="button">촬영</button>
              <button className="btn-ghost" id="stopCameraBtn" type="button">중지</button>
            </div>
          </div>

          <div className="card quick-results">
            <div className="card-head">
              <strong>요약</strong>
              <span className="muted">모델의 예측 요약</span>
            </div>
            <div className="result-cards">
              <div className="result-card"><div className="label">존</div><div className="value">VP <span className="muted">(예시)</span></div></div>
              <div className="result-card"><div className="label">점수</div><div className="value">82 <span className="muted">(예시)</span></div></div>
              <div className="result-card"><div className="label">사진 품질</div><div className="value">양호 <span className="muted">(예시)</span></div></div>
            </div>
          </div>
        </div>

        <aside className="nh-right modern-right">
          <div className="card setup-card">
            <div className="card-head">
              <div className="card-head-title">
                <strong>평가 설정</strong>
                <span className="muted">존, 톤, 핵심 키워드를 설정하세요</span>
              </div>
              <button
                className="info-button"
                type="button"
                aria-label="존 설명 보기"
                onClick={() => setShowZoneInfo((prev) => !prev)}
              >
                ⓘ
              </button>
            </div>

            {showZoneInfo && (
              <div className="zone-info-box" role="dialog" aria-label="존 설명">
                <p><strong>VP</strong>: 전면 매장 또는 주요 시선 포인트를 기준으로 평가합니다.</p>
                <p><strong>PP</strong>: 보조 포인트나 부가 진열 구역의 연출을 확인합니다.</p>
                <p><strong>IP</strong>: 특정 브랜드, 캠페인, 시즌 상품의 집중도와 적합성을 봅니다.</p>
              </div>
            )}

            <div className="zone-row">
              <button className="zone-pill" data-value="VP">VP</button>
              <button className="zone-pill" data-value="PP">PP</button>
              <button className="zone-pill" data-value="IP">IP</button>
            </div>

            <div className="field-row compact">
              <div className="field">
                <label htmlFor="storeType">매장 타입</label>
                <select id="storeType">
                  <option value="UNKNOWN">모름</option>
                  <option value="SINGLE_BRAND">단일 브랜드</option>
                  <option value="MULTI_BRAND">편집샵/다중 브랜드</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="tone">가게 분위기</label>
                <select id="tone">
                  <option value="SOFT_CRITICAL">부드러운 비판형</option>
                  <option value="BALANCED">균형형</option>
                  <option value="CRITICAL">비판 강화형</option>
                </select>
              </div>
            </div>

            <div className="criteria compact">
              <label className="section-label">평가기준</label>
              <div className="criteria-chips">
                {criteriaItems.map((item) => (
                  <label className="chip" key={item.label}>
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={() => toggleCriterion(item.label)}
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            </div>

            <div className="keyword-builder compact" aria-label="마네킹 및 방해물 키워드">
              <div className="keyword-row">
                <input
                  id="keywordInput"
                  type="text"
                  placeholder="기준 입력"
                  value={newCriterion}
                  onChange={(e) => {
                    setNewCriterion(e.target.value);
                    if (validationMessage) setValidationMessage('');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addCriterion();
                    }
                  }}
                />
                <button id="addKeywordBtn" className="icon-button" type="button" aria-label="기준 추가" onClick={addCriterion}>+</button>
              </div>
              {validationMessage && <div className="validation-message">{validationMessage}</div>}
              <div id="keywordChips" className="keyword-chips" aria-live="polite"></div>
            </div>

            <div className="field">
              <label htmlFor="extraCriteria">추가 요청</label>
              <textarea id="extraCriteria" rows="3" placeholder="예: 머리 있는 마네킹 중심으로 봐주세요."></textarea>
            </div>

            <div className="actions modern-actions">
              <button className="primary" id="analyzeBtn" type="button">분석 시작</button>
              <button className="secondary" id="batchBtn" type="button">엑셀 추출</button>
            </div>
          </div>
        </aside>
      </section>

      <section id="features" className="nh-features">
        <h2>주요 기능</h2>
        <div className="feature-grid">
          <article className="feature-card">
            <h3>간편한 이미지 업로드</h3>
            <p>단일 또는 다중 이미지 업로드, 미리보기, 삭제 기능을 제공합니다.</p>
          </article>
          <article className="feature-card">
            <h3>존 선택 & 자동 판단</h3>
            <p>사용자 지정 존과 AI 자동 판단을 모두 지원해, 기준에 맞춘 분석이 가능합니다.</p>
          </article>
          <article className="feature-card">
            <h3>세부 평가 항목</h3>
            <p>구성/연출/브랜드 적합성/사진 품질 등 항목별 점수를 제공합니다.</p>
          </article>
          <article className="feature-card">
            <h3>Excel 내보내기</h3>
            <p>분석 결과를 표 형식으로 추출해 검토 및 공유가 쉽습니다.</p>
          </article>
        </div>
      </section>

      <section id="usecases" className="nh-usecases">
        <h2>추천 사용 사례</h2>
        <ul>
          <li>한 존을 여러 각도에서 촬영해 종합 평가 받기</li>
          <li>대량 이미지 일괄분석 후 Excel로 오류 패턴 수집</li>
          <li>시연용 데모나 내부 검토 자료로 사용</li>
        </ul>
      </section>
    </div>
  );
}
