import { useEffect, useState } from 'react';
import './App.css';
import NewHomepage from './NewHomepage';

export default function App() {
  const [view, setView] = useState('app'); // 'app' or 'home'

  useEffect(() => {
    import('../app.js').catch((error) => {
      console.error('Failed to load legacy app logic', error);
    });
  }, []);

  return (
    <main className="shell">
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 12 }}>
        <button className={`tab-button ${view === 'home' ? 'active' : ''}`} type="button" onClick={() => setView('home')}>홈페이지</button>
        <button className={`tab-button ${view === 'app' ? 'active' : ''}`} type="button" onClick={() => setView('app')}>앱(분석)</button>
      </div>

      {view === 'home' ? (
        <NewHomepage onAnalyze={() => setView('app')} />
      ) : (
      <>
      <section className="hero">
        <div className="hero-content">
          <p className="eyebrow">AX R&D Visual Merchandising</p>
          <h1 className="banner-title">VMD Evaluation Studio</h1>
          <p className="hero-copy">
            매장 사진을 분석해 VP, PP, IP 존 판단과 VMD 개선 코멘트를 구조화합니다.
          </p>
        </div>
      </section>

      <nav className="tab-nav" aria-label="화면 선택">
        <button className="tab-button active" type="button" data-tab-target="mainTab">분석</button>
        <button className="tab-button" type="button" data-tab-target="historyTab">결과 <span id="historyCount">0</span></button>
      </nav>

      <div id="mainTab" className="tab-panel active">
        <section className="workspace">
          <div className="panel input-panel">
            <div className="panel-heading">
              <span>01</span>
              <div>
                <h2>Images</h2>
                <p>한 존을 여러 각도에서 찍은 사진은 함께 분석할 수 있습니다.</p>
              </div>
            </div>

            <label className="dropzone" htmlFor="imageInput">
              <input id="imageInput" type="file" accept="image/*" multiple />
              <span className="drop-title">사진 선택 또는 드래그</span>
              <span className="drop-copy">JPG, PNG 이미지를 지원합니다.</span>
            </label>
            <input id="cameraFallbackInput" className="visually-hidden" type="file" accept="image/*" capture="environment" />

            <div className="image-actions">
              <button className="secondary" id="startCameraBtn" type="button">사진 촬영</button>
            </div>

            <div id="cameraPanel" className="camera-panel hidden">
              <video id="cameraPreview" autoPlay playsInline muted></video>
              <div className="camera-actions">
                <button className="primary" id="capturePhotoBtn" type="button">촬영</button>
                <button className="secondary" id="stopCameraBtn" type="button">닫기</button>
              </div>
            </div>

            <div className="preview-grid" id="previewGrid" aria-label="업로드 이미지 미리보기"></div>
          </div>

          <div className="panel settings-panel">
            <div className="panel-heading">
              <span>02</span>
              <div>
                <h2>Evaluation Setup</h2>
                <p>개발 단계에서는 모델과 평가 조건을 명확히 남깁니다.</p>
              </div>
            </div>

            <div className="field">
              <label>Zone</label>
              <div className="segmented" role="radiogroup" aria-label="존 선택">
                <label><input type="radio" name="zone" value="VP" defaultChecked /><span>VP</span></label>
                <label><input type="radio" name="zone" value="PP" /><span>PP</span></label>
                <label><input type="radio" name="zone" value="IP" /><span>IP</span></label>
              </div>
            </div>

            <div className="field-row">
              <div className="field">
                <label htmlFor="storeType">Store type</label>
                <select id="storeType">
                  <option value="UNKNOWN">모름</option>
                  <option value="SINGLE_BRAND">단일 브랜드</option>
                  <option value="MULTI_BRAND">편집샵/다중 브랜드</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="tone">Tone</label>
                <select id="tone">
                  <option value="SOFT_CRITICAL">부드러운 비판형</option>
                  <option value="BALANCED">균형형</option>
                  <option value="CRITICAL">비판 강화형</option>
                </select>
              </div>
            </div>

            <div className="criteria">
              <label className="section-label">Criteria</label>
              <div className="criteria-grid">
                <label><input type="checkbox" value="구성 및 레이아웃" defaultChecked />구성/레이아웃</label>
                <label><input type="checkbox" value="연출 및 분위기" defaultChecked />연출/분위기</label>
                <label><input type="checkbox" value="브랜드 이미지 적합성" defaultChecked />브랜드 적합성</label>
                <label><input type="checkbox" value="고객 시선 유도" defaultChecked />시선 유도</label>
                <label><input type="checkbox" value="상품군/컬러 통일감" defaultChecked />컬러/상품군</label>
                <label><input type="checkbox" value="청결/정돈" defaultChecked />청결/정돈</label>
                <label><input type="checkbox" value="시즌 컨셉 부합도" defaultChecked />시즌 컨셉</label>
                <label><input type="checkbox" value="사진 품질" defaultChecked />사진 품질</label>
                <label><input type="checkbox" value="마네킹/구조물/방해물" defaultChecked />마네킹/방해물</label>
                <div className="keyword-builder" aria-label="마네킹 및 방해물 키워드">
                  <div className="keyword-row">
                    <input id="keywordInput" type="text" placeholder="키워드" />
                    <button id="addKeywordBtn" className="icon-button" type="button" aria-label="키워드 추가">+</button>
                  </div>
                  <div id="keywordChips" className="keyword-chips" aria-live="polite"></div>
                </div>
              </div>
            </div>

            <div className="field">
              <label htmlFor="extraCriteria">추가 평가 요청</label>
              <textarea id="extraCriteria" rows="4" placeholder="예: 머리 있는 마네킹과 주변 소품 균형을 중점적으로 봐줘."></textarea>
            </div>

            <div className="actions">
              <button className="primary" id="analyzeBtn" type="button">Analyze View</button>
              <button className="secondary" id="batchBtn" type="button">Export Excel Batch</button>
            </div>
          </div>
        </section>

        <section className="panel result-panel">
          <div className="panel-heading">
            <span>03</span>
            <div>
              <h2>Result</h2>
              <p id="progressText">사진을 넣고 분석을 시작하세요.</p>
            </div>
          </div>

          <div className="result-grid">
            <article className="score-card">
              <p>Total Score</p>
              <strong id="totalScore">--</strong>
              <span id="grade">대기 중</span>
            </article>
            <article className="metric-card">
              <p>Zone</p>
              <strong id="zoneResult">--</strong>
              <span id="zoneConfidence">confidence --</span>
            </article>
            <article className="metric-card">
              <p>Photo Quality</p>
              <strong id="photoScore">--</strong>
              <span id="retakeFlag">retake --</span>
            </article>
            <article className="metric-card">
              <p>Mannequin</p>
              <strong id="mannequinFlag">--</strong>
              <span id="mannequinType">type --</span>
            </article>
          </div>

          <div className="detail-layout">
            <section className="detail-block">
              <h3>영역별 평가항목</h3>
              <div id="scoreBars" className="score-bars"></div>
            </section>
            <section className="detail-block">
              <h3>사진 품질</h3>
              <p id="photoComment" className="body-text">아직 분석 결과가 없습니다.</p>
            </section>
            <section className="detail-block">
              <h3>잘된 점</h3>
              <ul id="positivePoints"></ul>
            </section>
            <section className="detail-block">
              <h3>마네킹 판정 근거</h3>
              <p id="mannequinComment" className="body-text">아직 분석 결과가 없습니다.</p>
            </section>
            <section className="detail-block">
              <h3>비판적 문제점</h3>
              <ul id="criticalIssues"></ul>
            </section>
            <section className="detail-block">
              <h3>개선 제안</h3>
              <ul id="improvements"></ul>
            </section>
            <section className="detail-block wide">
              <h3>최종 요약</h3>
              <p id="finalSummary" className="body-text">분석을 실행하면 요약이 표시됩니다.</p>
            </section>
            <section className="detail-block wide">
              <h3>감지된 방해물</h3>
              <div id="obstacles" className="pill-list"></div>
            </section>
          </div>

          <div className="download-row">
            <a id="downloadLink" className="download-link hidden" href="#">Excel 다운로드</a>
            <a id="pdfDownloadLink" className="download-link pdf-download-link hidden" href="#" download>PDF 저장</a>
            <span id="jsonPath" className="muted"></span>
          </div>
        </section>
      </div>

      <section id="historyTab" className="tab-panel hidden">
        <div className="panel history-panel">
          <div className="panel-heading history-heading">
            <span>04</span>
            <div>
              <h2>Saved Results</h2>
              <p>분석 결과를 저장해 두고 필요한 항목을 다시 확인합니다.</p>
            </div>
            <button id="clearHistoryBtn" className="icon-button history-clear" type="button" aria-label="저장된 결과 모두 삭제" title="저장된 결과 모두 삭제">×</button>
          </div>
          <div id="historyEmpty" className="history-empty">
            <strong>저장된 결과가 없습니다.</strong>
            <span>메인 탭에서 사진을 분석하면 이곳에 결과 카드가 쌓입니다.</span>
          </div>
          <div id="historyGrid" className="history-grid"></div>
          <div id="historyPagination" className="history-pagination hidden" aria-label="Result pages">
            <button id="historyPrevBtn" className="icon-button" type="button" aria-label="Previous results" title="Previous results">←</button>
            <span id="historyPageLabel" className="muted">1 / 1</span>
            <button id="historyNextBtn" className="icon-button" type="button" aria-label="Next results" title="Next results">→</button>
          </div>
        </div>
      </section>

      <div id="historyModal" className="history-modal hidden" role="dialog" aria-modal="true" aria-labelledby="historyDetailTitle">
        <div className="history-dialog">
          <div className="history-dialog-heading">
            <div>
              <p id="historyDetailMeta" className="eyebrow">Saved Result</p>
              <h2 id="historyDetailTitle">분석 결과</h2>
            </div>
            <button id="closeHistoryBtn" className="icon-button" type="button" aria-label="결과 상세 닫기" title="결과 상세 닫기">×</button>
          </div>
          <div className="history-photo-browser">
            <aside className="history-photo-list-panel">
              <div className="history-photo-list-heading">
                <span className="eyebrow">Images</span>
                <span id="historyPhotoListCount" className="muted">0</span>
              </div>
              <div id="historyPhotoList" className="history-photo-list"></div>
            </aside>
            <div className="history-photo-detail">
              <div className="history-story" aria-live="polite">
                <div className="history-story-heading">
                  <span id="historyStorySection" className="eyebrow">Overview</span>
                  <span id="historyStoryProgress" className="muted">1 / 1</span>
                </div>
                <div id="historyStoryViewport" className="history-story-viewport"></div>
                <div className="history-story-controls">
                  <button id="historyStoryPrevBtn" className="icon-button" type="button" aria-label="Previous section" title="Previous section">←</button>
                  <button id="historyStoryNextBtn" className="icon-button" type="button" aria-label="Next section" title="Next section">→</button>
                </div>
              </div>
            </div>
          </div>
          <div className="result-grid history-result-grid">
            <article className="score-card">
              <p>Total Score</p>
              <strong id="historyTotalScore">--</strong>
              <span id="historyGrade">--</span>
            </article>
            <article className="metric-card">
              <p>Zone</p>
              <strong id="historyZoneResult">--</strong>
              <span id="historyZoneConfidence">confidence --</span>
            </article>
            <article className="metric-card">
              <p>Photo Quality</p>
              <strong id="historyPhotoScore">--</strong>
              <span id="historyRetakeFlag">retake --</span>
            </article>
            <article className="metric-card">
              <p>Mannequin</p>
              <strong id="historyMannequinFlag">--</strong>
              <span id="historyMannequinType">type --</span>
            </article>
          </div>
          <div className="detail-layout">
            <section className="detail-block">
              <h3>영역별 평가항목</h3>
              <div id="historyScoreBars" className="score-bars"></div>
            </section>
            <section className="detail-block">
              <h3>사진 품질</h3>
              <p id="historyPhotoComment" className="body-text"></p>
            </section>
            <section className="detail-block">
              <h3>잘된 점</h3>
              <ul id="historyPositivePoints"></ul>
            </section>
            <section className="detail-block">
              <h3>마네킹 판정 근거</h3>
              <p id="historyMannequinComment" className="body-text"></p>
            </section>
            <section className="detail-block">
              <h3>비판적 문제점</h3>
              <ul id="historyCriticalIssues"></ul>
            </section>
            <section className="detail-block">
              <h3>개선 제안</h3>
              <ul id="historyImprovements"></ul>
            </section>
            <section className="detail-block wide">
              <h3>최종 요약</h3>
              <p id="historyFinalSummary" className="body-text"></p>
            </section>
            <section className="detail-block wide">
              <h3>감지된 방해물</h3>
              <div id="historyObstacles" className="pill-list"></div>
            </section>
          </div>
          <div className="download-row">
            <a id="historyDownloadLink" className="download-link hidden" href="#">Excel 다운로드</a>
            <a id="historyPdfDownloadLink" className="download-link pdf-download-link hidden" href="#" download>PDF 저장</a>
            <span id="historyJsonPath" className="muted"></span>
          </div>
        </div>
      </div>
      </>
      )}

    </main>
  );
}
