import React, { useEffect, useRef, useState } from 'react';
import './new-home.css';

const UPLOAD_MAX_DIMENSION = 1920;
const UPLOAD_TARGET_BYTES = 700000;
const EXCEL_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const PDF_MIME_TYPE = 'application/pdf';

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

function dataUrlByteLength(dataUrl) {
  const base64 = dataUrl.split(',')[1] || '';
  return Math.floor((base64.length * 3) / 4);
}

function resizeImageDataUrl(dataUrl, maxDimension, targetBytes) {
  return new Promise((resolve) => {
    if (dataUrlByteLength(dataUrl) <= targetBytes) {
      resolve(dataUrl);
      return;
    }
    const source = new Image();
    source.onload = () => {
      const scale = Math.min(1, maxDimension / Math.max(source.naturalWidth, source.naturalHeight));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
      const context = canvas.getContext('2d');
      if (!context) {
        resolve(dataUrl);
        return;
      }
      context.drawImage(source, 0, 0, canvas.width, canvas.height);
      let output = dataUrl;
      for (const quality of [0.85, 0.75, 0.65, 0.5, 0.35]) {
        output = canvas.toDataURL('image/jpeg', quality);
        if (dataUrlByteLength(output) <= targetBytes) {
          break;
        }
      }
      resolve(output);
    };
    source.onerror = () => resolve(dataUrl);
    source.src = dataUrl;
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = await resizeImageDataUrl(reader.result, UPLOAD_MAX_DIMENSION, UPLOAD_TARGET_BYTES);
      resolve({ name: file.name, dataUrl });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function base64ToBlob(base64, mimeType) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

function downloadBase64File(base64, mimeType, fileName) {
  if (!base64) return;
  const url = URL.createObjectURL(base64ToBlob(base64, mimeType));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName || 'download';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function DetailDrawer({ payload, state, onDock, onCenter }) {
  const result = payload?.result || {};
  const photo = result.photo_quality || {};
  const mannequin = result.mannequin || {};
  const criteria = Array.isArray(result.criteria_evaluations)
    ? result.criteria_evaluations.filter((item) => item && item.criterion)
    : [];
  const obstacles = Array.isArray(result.obstacles) ? result.obstacles : [];
  const isDocked = state === 'docked';

  return (
    <>
      <div className={`nh-detail-overlay${state === 'center' ? ' open' : ''}`} onClick={onDock} />
      <aside
        className={`nh-detail-modal${state !== 'closed' ? ` ${state}` : ''}`}
        aria-hidden={state === 'closed'}
        role="dialog"
        aria-label="상세 분석 결과"
        onClick={() => isDocked && onCenter()}
      >
        <div className="nh-detail-head">
          <strong>상세 분석 결과</strong>
          <button
            type="button"
            className="icon-button"
            aria-label={isDocked ? '상세 결과 펼치기' : '상세 결과 옆으로 넣기'}
            onClick={(event) => {
              event.stopPropagation();
              isDocked ? onCenter() : onDock();
            }}
          >
            {isDocked ? '←' : '→'}
          </button>
        </div>
        {payload ? (
          <div className="nh-detail-body">
            <div className="result-cards nh-detail-scores">
              <div className="result-card"><div className="label">Total Score</div><div className="value">{result.total_score ?? '--'}</div></div>
              <div className="result-card"><div className="label">Zone</div><div className="value">{result.user_selected_zone || '--'} → {result.ai_detected_zone || 'UNKNOWN'}</div></div>
              <div className="result-card"><div className="label">Photo Quality</div><div className="value">{photo.score ?? '--'}</div></div>
              <div className="result-card"><div className="label">Mannequin</div><div className="value">{mannequin.exists ? '있음' : '없음'}</div></div>
            </div>

            <section className="nh-detail-section">
              <h4>영역별 평가항목</h4>
              {criteria.length ? (
                criteria.map((item) => (
                  <div className="nh-criteria-row" key={item.criterion}>
                    <strong>{item.criterion}</strong>
                    <span>{item.score ?? '--'}점</span>
                    <p>{item.suggestion || item.evidence || '내용 없음'}</p>
                  </div>
                ))
              ) : (
                <p className="body-text">평가 항목이 없습니다.</p>
              )}
            </section>

            <section className="nh-detail-section">
              <h4>잘된 점</h4>
              <ul>{(result.positive_points || []).map((point, i) => <li key={i}>{point}</li>)}</ul>
            </section>
            <section className="nh-detail-section">
              <h4>비판적 문제점</h4>
              <ul>{(result.critical_issues || []).map((point, i) => <li key={i}>{point}</li>)}</ul>
            </section>
            <section className="nh-detail-section">
              <h4>개선 제안</h4>
              <ul>{(result.improvement_suggestions || []).map((point, i) => <li key={i}>{point}</li>)}</ul>
            </section>
            <section className="nh-detail-section">
              <h4>감지된 방해물</h4>
              {obstacles.length ? (
                <div className="pill-list">
                  {obstacles.map((item, i) => (
                    <span className="pill" key={i}>{item.object || 'object'} · {item.location || ''}</span>
                  ))}
                </div>
              ) : (
                <p className="body-text">감지된 방해물이 없습니다.</p>
              )}
            </section>
            <section className="nh-detail-section">
              <h4>최종 요약</h4>
              <p className="body-text">{result.final_summary || '요약이 없습니다.'}</p>
            </section>

            <div className="nh-detail-downloads">
              {payload.excelBase64 && (
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => downloadBase64File(payload.excelBase64, EXCEL_MIME_TYPE, payload.excelFileName)}
                >Excel 다운로드</button>
              )}
              {payload.pdfBase64 && (
                <button
                  type="button"
                  className="btn-outline"
                  onClick={() => downloadBase64File(payload.pdfBase64, PDF_MIME_TYPE, payload.pdfFileName)}
                >PDF 저장</button>
              )}
            </div>
          </div>
        ) : (
          <p className="body-text nh-detail-empty">아직 분석 결과가 없습니다.</p>
        )}
      </aside>
    </>
  );
}

export default function NewHomepage({ onAnalyze }) {
  const [showZoneInfo, setShowZoneInfo] = useState(false);
  const [previewImages, setPreviewImages] = useState([]);
  const [selectedZone, setSelectedZone] = useState('VP');
  const [newCriterion, setNewCriterion] = useState('');
  const [validationMessage, setValidationMessage] = useState('');
  const [criteriaItems, setCriteriaItems] = useState([
    { label: '구성/레이아웃', checked: true },
    { label: '연출/분위기', checked: true },
    { label: '브랜드 적합성', checked: true },
    { label: '사진 품질', checked: true },
  ]);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [quickResult, setQuickResult] = useState(null);
  const [detailPayload, setDetailPayload] = useState(null);
  const [drawerState, setDrawerState] = useState('closed'); // 'closed' | 'center' | 'docked'
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const storeTypeRef = useRef(null);
  const toneRef = useRef(null);
  const extraCriteriaRef = useRef(null);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

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

  const handleImageInputChange = async (event) => {
    const files = Array.from(event.target.files || []).filter((file) => file.type.startsWith('image/'));
    const next = await Promise.all(files.map(readFileAsDataUrl));
    setPreviewImages((prev) => [...prev, ...next]);
    event.target.value = '';
  };

  const removePreviewImage = (index) => {
    setPreviewImages((prev) => prev.filter((_, i) => i !== index));
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

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      document.getElementById('cameraFallbackInput')?.click();
      return;
    }
    try {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      streamRef.current = stream;
      setIsCameraOpen(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (error) {
      setStatusMessage(`카메라를 열 수 없습니다: ${error.message}`);
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraOpen(false);
  };

  const capturePhoto = async () => {
    if (!streamRef.current || !videoRef.current) {
      return;
    }
    const video = videoRef.current;
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }
    context.drawImage(video, 0, 0, width, height);
    const dataUrl = await resizeImageDataUrl(
      canvas.toDataURL('image/jpeg', 0.92),
      UPLOAD_MAX_DIMENSION,
      UPLOAD_TARGET_BYTES
    );
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    setPreviewImages((prev) => [...prev, { name: `camera-${stamp}.jpg`, dataUrl }]);
  };

  const buildOptions = () => ({
    zoneMode: selectedZone,
    storeType: storeTypeRef.current?.value || 'UNKNOWN',
    tone: toneRef.current?.value || 'SOFT_CRITICAL',
    criteria: criteriaItems.filter((item) => item.checked).map((item) => item.label),
    focusKeywords: [],
    extraCriteria: extraCriteriaRef.current?.value.trim() || '',
    temperature: 0.2,
    maxTokens: 2200,
  });

  const applyQuickResult = (result) => {
    const photo = result?.photo_quality || {};
    setQuickResult({
      zone: result?.user_selected_zone || selectedZone,
      score: result?.total_score ?? '--',
      photoQuality: photo.needs_retake ? '재촬영 권장' : (photo.score != null ? `${photo.score}점` : '--'),
    });
  };

  const runAnalyze = async () => {
    if (!previewImages.length) {
      setStatusMessage('분석할 사진을 먼저 추가하세요.');
      return;
    }
    setIsAnalyzing(true);
    setStatusMessage('분석 중입니다...');
    try {
      const payload = await postJson('/api/analyze', { images: previewImages, options: buildOptions() });
      applyQuickResult(payload.result);
      setDetailPayload(payload);
      setStatusMessage(`분석 완료 · ${payload.elapsedSeconds}s`);
      setDrawerState('center');
    } catch (error) {
      setStatusMessage(`분석 실패: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const runBatchAnalyze = async () => {
    if (!previewImages.length) {
      setStatusMessage('엑셀로 정리할 사진을 먼저 추가하세요.');
      return;
    }
    setIsAnalyzing(true);
    setStatusMessage('이미지별 일괄 분석 중입니다...');
    try {
      const payload = await postJson('/api/batch-analyze', { images: previewImages, options: buildOptions() });
      const firstResult = payload.results?.[0]?.result;
      if (firstResult) {
        applyQuickResult(firstResult);
      }
      setDetailPayload({ ...payload, result: firstResult });
      setStatusMessage(`Excel·PDF 생성 완료 · ${payload.count}개 이미지 · ${payload.elapsedSeconds}s`);
      setDrawerState('center');
    } catch (error) {
      setStatusMessage(`Excel·PDF 생성 실패: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
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
              <input id="imageInput" type="file" accept="image/*" multiple onChange={handleImageInputChange} />
              <div className="drop-inner">
                <div className="drop-icon">📷</div>
                <div>
                  <div className="drop-title">이미지 선택 또는 드래그</div>
                  <div className="drop-copy">JPG/PNG, 최대 권장 해상도 4K</div>
                </div>
              </div>
            </label>
            <input id="cameraFallbackInput" className="visually-hidden" type="file" accept="image/*" capture="environment" onChange={handleImageInputChange} />

            <div className="thumb-strip" id="previewGrid" aria-label="업로드 이미지 미리보기">
              {previewImages.map((image, index) => (
                <div className="preview-card" key={`${image.name}-${index}`}>
                  <img src={image.dataUrl} alt={image.name} />
                  <button type="button" aria-label={`${image.name} 삭제`} onClick={() => removePreviewImage(index)}>×</button>
                </div>
              ))}
            </div>

            <div className="upload-actions">
              <button className="btn-outline" id="startCameraBtn" type="button" onClick={startCamera}>카메라</button>
              <button className="btn-ghost" id="capturePhotoBtn" type="button" onClick={capturePhoto}>촬영</button>
              <button className="btn-ghost" id="stopCameraBtn" type="button" onClick={stopCamera}>중지</button>
            </div>

            {isCameraOpen && (
              <div className="nh-camera-panel">
                <video ref={videoRef} autoPlay playsInline muted className="nh-camera-preview" />
              </div>
            )}
          </div>

          <div className="card quick-results">
            <div className="card-head">
              <strong>요약</strong>
              <span className="muted">{statusMessage || '모델의 예측 요약'}</span>
            </div>
            <div className="result-cards">
              <div className="result-card"><div className="label">존</div><div className="value">{quickResult ? quickResult.zone : <>VP <span className="muted">(예시)</span></>}</div></div>
              <div className="result-card"><div className="label">점수</div><div className="value">{quickResult ? quickResult.score : <>82 <span className="muted">(예시)</span></>}</div></div>
              <div className="result-card"><div className="label">사진 품질</div><div className="value">{quickResult ? quickResult.photoQuality : <>양호 <span className="muted">(예시)</span></>}</div></div>
            </div>
            {detailPayload && (
              <button type="button" className="nh-detail-trigger" onClick={() => setDrawerState('center')}>상세 결과 보기 →</button>
            )}
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
              <button
                type="button"
                className={`zone-pill${selectedZone === 'VP' ? ' active' : ''}`}
                data-value="VP"
                onClick={() => setSelectedZone('VP')}
              >VP</button>
              <button
                type="button"
                className={`zone-pill${selectedZone === 'PP' ? ' active' : ''}`}
                data-value="PP"
                onClick={() => setSelectedZone('PP')}
              >PP</button>
              <button
                type="button"
                className={`zone-pill${selectedZone === 'IP' ? ' active' : ''}`}
                data-value="IP"
                onClick={() => setSelectedZone('IP')}
              >IP</button>
            </div>

            <div className="field-row compact">
              <div className="field">
                <label htmlFor="storeType">매장 타입</label>
                <select id="storeType" ref={storeTypeRef}>
                  <option value="UNKNOWN">모름</option>
                  <option value="SINGLE_BRAND">단일 브랜드</option>
                  <option value="MULTI_BRAND">편집샵/다중 브랜드</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="tone">가게 분위기</label>
                <select id="tone" ref={toneRef}>
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
              <textarea id="extraCriteria" rows="3" placeholder="예: 머리 있는 마네킹 중심으로 봐주세요." ref={extraCriteriaRef}></textarea>
            </div>

            <div className="actions modern-actions">
              <button className="primary" id="analyzeBtn" type="button" onClick={runAnalyze} disabled={isAnalyzing}>
                {isAnalyzing ? '분석 중...' : '분석 시작'}
              </button>
              <button className="secondary" id="batchBtn" type="button" onClick={runBatchAnalyze} disabled={isAnalyzing}>
                {isAnalyzing ? '처리 중...' : '엑셀 추출'}
              </button>
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

      <DetailDrawer
        payload={detailPayload}
        state={drawerState}
        onDock={() => setDrawerState('docked')}
        onCenter={() => setDrawerState('center')}
      />
    </div>
  );
}
