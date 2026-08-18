import React, { useEffect, useRef, useState } from 'react';
import {
  Camera,
  CheckCircle,
  CircleHalf,
  DownloadSimple,
  SpinnerGap,
  TextAa,
  Trash,
  WarningCircle,
  X,
} from '@phosphor-icons/react';
import './consumer-page.css';
import {
  UPLOAD_MAX_DIMENSION,
  UPLOAD_TARGET_BYTES,
  EXCEL_MIME_TYPE,
  PDF_MIME_TYPE,
  resizeImageDataUrl,
  readFileAsDataUrl,
  downloadBase64File,
  postJson,
} from './mediaUtils';

const TEXT_SIZE_KEY = 'vmd-consumer-text-size';
const CONTRAST_KEY = 'vmd-consumer-high-contrast';

const DEFAULT_CRITERIA_LABELS = ['구성/레이아웃', '연출/분위기', '브랜드 적합성', '사진 품질'];

export default function ConsumerPage() {
  const [textSize, setTextSize] = useState(() => {
    if (typeof window === 'undefined') return 'normal';
    return window.localStorage.getItem(TEXT_SIZE_KEY) || 'normal';
  });
  const [highContrast, setHighContrast] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(CONTRAST_KEY) === '1';
  });

  const [previewImages, setPreviewImages] = useState([]);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [result, setResult] = useState(null);
  const [batchInfo, setBatchInfo] = useState(null);
  const [downloads, setDownloads] = useState(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const resultHeadingRef = useRef(null);
  const captureButtonRef = useRef(null);

  useEffect(() => {
    window.localStorage.setItem(TEXT_SIZE_KEY, textSize);
  }, [textSize]);

  useEffect(() => {
    window.localStorage.setItem(CONTRAST_KEY, highContrast ? '1' : '0');
  }, [highContrast]);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const handleImageInputChange = async (event) => {
    const files = Array.from(event.target.files || []).filter((file) => file.type.startsWith('image/'));
    const next = await Promise.all(files.map(readFileAsDataUrl));
    setPreviewImages((prev) => [...prev, ...next]);
    event.target.value = '';
  };

  const removePreviewImage = (index) => {
    setPreviewImages((prev) => prev.filter((_, i) => i !== index));
  };

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      document.getElementById('cpCameraFallbackInput')?.click();
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
      captureButtonRef.current?.focus();
    } catch (error) {
      setErrorMessage(`카메라를 열 수 없습니다: ${error.message}`);
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
    if (!streamRef.current || !videoRef.current) return;
    const video = videoRef.current;
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(video, 0, 0, width, height);
    const dataUrl = await resizeImageDataUrl(
      canvas.toDataURL('image/jpeg', 0.92),
      UPLOAD_MAX_DIMENSION,
      UPLOAD_TARGET_BYTES
    );
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    setPreviewImages((prev) => [...prev, { name: `camera-${stamp}.jpg`, dataUrl }]);
    setStatusMessage('사진을 촬영해서 목록에 추가했습니다.');
  };

  const buildOptions = () => ({
    zoneMode: 'AUTO',
    storeType: 'UNKNOWN',
    tone: 'SOFT_CRITICAL',
    criteria: DEFAULT_CRITERIA_LABELS,
    focusKeywords: [],
    extraCriteria: '',
    temperature: 0.2,
    maxTokens: 6000,
  });

  const focusResultHeading = () => {
    window.requestAnimationFrame(() => {
      resultHeadingRef.current?.focus();
      resultHeadingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const runAnalyze = async () => {
    if (!previewImages.length) {
      setErrorMessage('분석할 사진을 먼저 추가해 주세요.');
      return;
    }
    setErrorMessage('');
    setIsAnalyzing(true);
    setStatusMessage('분석 중입니다. 잠시만 기다려 주세요...');
    try {
      const payload = await postJson('/api/analyze', { images: previewImages, options: buildOptions() });
      setResult(payload.result || null);
      setBatchInfo(null);
      setDownloads({
        excelBase64: payload.excelBase64,
        excelFileName: payload.excelFileName,
        pdfBase64: payload.pdfBase64,
        pdfFileName: payload.pdfFileName,
      });
      setStatusMessage(`분석이 끝났습니다. (${payload.elapsedSeconds}초 걸림)`);
      focusResultHeading();
    } catch (error) {
      setResult(null);
      setStatusMessage('');
      setErrorMessage(`분석에 실패했습니다: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const runBatchAnalyze = async () => {
    if (!previewImages.length) {
      setErrorMessage('엑셀로 정리할 사진을 먼저 추가해 주세요.');
      return;
    }
    setErrorMessage('');
    setIsAnalyzing(true);
    setStatusMessage('이미지를 하나씩 분석해서 엑셀로 정리하는 중입니다...');
    try {
      const payload = await postJson('/api/batch-analyze', { images: previewImages, options: buildOptions() });
      const firstResult = payload.results?.[0]?.result || null;
      setResult(firstResult);
      setBatchInfo({ count: payload.count, elapsedSeconds: payload.elapsedSeconds });
      setDownloads({
        excelBase64: payload.excelBase64,
        excelFileName: payload.excelFileName,
        pdfBase64: payload.pdfBase64,
        pdfFileName: payload.pdfFileName,
      });
      setStatusMessage(`이미지 ${payload.count}개 분석과 엑셀·PDF 만들기를 마쳤습니다. (${payload.elapsedSeconds}초 걸림)`);
      focusResultHeading();
    } catch (error) {
      setResult(null);
      setStatusMessage('');
      setErrorMessage(`엑셀 만들기에 실패했습니다: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const photo = result?.photo_quality || {};
  const mannequin = result?.mannequin || {};
  const criteriaEvaluations = Array.isArray(result?.criteria_evaluations)
    ? result.criteria_evaluations.filter((item) => item && item.criterion)
    : [];
  const obstacles = Array.isArray(result?.obstacles) ? result.obstacles : [];
  const doneMessage = !isAnalyzing && !errorMessage && statusMessage;

  return (
    <div className={`cp-page cp-text-${textSize}${highContrast ? ' cp-contrast' : ''}`}>
      <a className="cp-skip-link" href="#cp-main">본문으로 바로가기</a>

      <header className="cp-header">
        <div className="cp-a11y-toolbar">
          <div className="cp-toolbar-group" role="group" aria-label="글자 크기 선택">
            <span className="cp-toolbar-label"><TextAa size={20} aria-hidden="true" />글자 크기</span>
            <button type="button" aria-pressed={textSize === 'normal'} onClick={() => setTextSize('normal')}>보통</button>
            <button type="button" aria-pressed={textSize === 'large'} onClick={() => setTextSize('large')}>크게</button>
            <button type="button" aria-pressed={textSize === 'xlarge'} onClick={() => setTextSize('xlarge')}>아주 크게</button>
          </div>
          <button
            type="button"
            className="cp-contrast-toggle"
            aria-pressed={highContrast}
            onClick={() => setHighContrast((prev) => !prev)}
          >
            <CircleHalf size={18} aria-hidden="true" />
            {highContrast ? '고대비 화면 끄기' : '고대비 화면 켜기'}
          </button>
        </div>
      </header>

      <main id="cp-main" className="cp-main">
        <ol className="cp-steps">
          <li className="cp-step cp-step-photo" aria-labelledby="cp-step1-heading">
            <h2 id="cp-step1-heading"><span className="cp-step-num" aria-hidden="true">1</span>사진 올리기</h2>
            <p className="cp-step-desc">매장 사진을 선택하거나 직접 촬영해서 추가하세요.</p>

            <div className="cp-upload-row">
              <label className="cp-dropzone" htmlFor="cpImageInput">
                <span className="cp-dropzone-icon" aria-hidden="true"><Camera size={34} /></span>
                <span>
                  <span className="cp-dropzone-title">사진 선택하기</span>
                  <span className="cp-dropzone-copy">JPG, PNG 파일을 여러 장 고를 수 있어요.</span>
                </span>
              </label>

              <button
                type="button"
                className="cp-dropzone cp-capture-box"
                aria-pressed={isCameraOpen}
                onClick={isCameraOpen ? stopCamera : startCamera}
              >
                <span className="cp-dropzone-icon" aria-hidden="true">
                  {isCameraOpen ? <X size={34} /> : <Camera size={34} />}
                </span>
                <span>
                  <span className="cp-dropzone-title">{isCameraOpen ? '카메라 닫기' : '카메라로 촬영하기'}</span>
                  <span className="cp-dropzone-copy">
                    {isCameraOpen ? '촬영을 마치면 눌러 주세요.' : '매장에서 바로 사진을 찍어요.'}
                  </span>
                </span>
              </button>
            </div>
            <input
              id="cpImageInput"
              type="file"
              accept="image/*"
              multiple
              className="cp-sr-only"
              onChange={handleImageInputChange}
            />
            <input
              id="cpCameraFallbackInput"
              type="file"
              accept="image/*"
              capture="environment"
              className="cp-sr-only"
              onChange={handleImageInputChange}
            />

            {isCameraOpen && (
              <div className="cp-camera-panel">
                <p className="cp-camera-status" role="status">카메라가 켜져 있습니다.</p>
                <video ref={videoRef} className="cp-camera-preview" autoPlay playsInline muted aria-label="카메라 미리보기" />
                <button type="button" ref={captureButtonRef} className="cp-btn cp-btn-primary" onClick={capturePhoto}>
                  지금 촬영하기
                </button>
              </div>
            )}

            <p className="cp-image-count" aria-live="polite">
              {previewImages.length > 0
                ? `현재 ${previewImages.length}장의 사진이 추가되어 있습니다.`
                : '아직 추가된 사진이 없습니다.'}
            </p>

            {previewImages.length > 0 && (
              <ul className="cp-thumb-list" aria-label="추가한 사진 목록">
                {previewImages.map((image, index) => (
                  <li className="cp-thumb-card" key={`${image.name}-${index}`}>
                    <img src={image.dataUrl} alt={`업로드한 사진: ${image.name}`} />
                    <button
                      type="button"
                      className="cp-thumb-remove"
                      aria-label={`${image.name} 삭제`}
                      onClick={() => removePreviewImage(index)}
                    >
                      <Trash size={16} aria-hidden="true" />삭제
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>

          <li className="cp-step" aria-labelledby="cp-step2-heading">
            <h2 id="cp-step2-heading"><span className="cp-step-num" aria-hidden="true">2</span>분석 시작하기</h2>
            <p className="cp-step-desc">사진 한 세트를 바로 분석하거나, 여러 사진을 한 번에 엑셀 파일로 정리할 수 있어요.</p>

            <div className="cp-actions">
              <button
                type="button"
                className="cp-btn cp-btn-primary"
                onClick={runAnalyze}
                disabled={isAnalyzing}
              >
                {isAnalyzing && <SpinnerGap size={18} className="cp-spin" aria-hidden="true" />}
                {isAnalyzing ? '분석 중입니다...' : '사진 분석하기'}
              </button>
              <button
                type="button"
                className="cp-btn cp-btn-outline"
                onClick={runBatchAnalyze}
                disabled={isAnalyzing}
              >
                {isAnalyzing && <SpinnerGap size={18} className="cp-spin" aria-hidden="true" />}
                {isAnalyzing ? '처리 중입니다...' : '엑셀·PDF로 저장하기'}
              </button>
            </div>

            {statusMessage && (
              <p className="cp-status-text" role="status">
                {doneMessage && <CheckCircle size={18} weight="fill" aria-hidden="true" />}
                {statusMessage}
              </p>
            )}
            {errorMessage && (
              <p className="cp-error-text" role="alert">
                <WarningCircle size={18} weight="fill" aria-hidden="true" />{errorMessage}
              </p>
            )}
          </li>
        </ol>

        <section className="cp-result" aria-labelledby="cp-result-heading">
          <h2 id="cp-result-heading" tabIndex={-1} ref={resultHeadingRef}>분석 결과</h2>

          {!result ? (
            <p className="cp-help-text">아직 분석 결과가 없습니다. 위에서 사진을 올리고 분석을 시작해 주세요.</p>
          ) : (
            <>
              {batchInfo && (
                <p className="cp-help-text">사진 {batchInfo.count}장 중 첫 번째 사진의 결과를 아래에 보여드려요. 전체 결과는 엑셀 파일에서 확인하세요.</p>
              )}

              <dl className="cp-summary-list">
                <div className="cp-summary-item">
                  <dt>총점</dt>
                  <dd>{result.total_score ?? '정보 없음'}점</dd>
                </div>
                <div className="cp-summary-item">
                  <dt>구역</dt>
                  <dd>{result.ai_detected_zone || '알 수 없음'}</dd>
                </div>
                <div className="cp-summary-item">
                  <dt>사진 품질</dt>
                  <dd>
                    {photo.score != null ? `${photo.score}점` : '정보 없음'}
                    {photo.needs_retake && (
                      <span className="cp-retake-flag"><WarningCircle size={16} weight="fill" aria-hidden="true" />다시 찍는 것을 권해요</span>
                    )}
                  </dd>
                </div>
                <div className="cp-summary-item">
                  <dt>마네킹</dt>
                  <dd>{mannequin.exists ? '있음' : '없음'}</dd>
                </div>
              </dl>

              {criteriaEvaluations.length > 0 && (
                <section className="cp-result-section" aria-labelledby="cp-criteria-heading">
                  <h3 id="cp-criteria-heading">항목별 평가</h3>
                  <ul className="cp-criteria-results">
                    {criteriaEvaluations.map((item) => (
                      <li key={item.criterion}>
                        <strong>{item.criterion}</strong>
                        <span>{item.score != null ? `${item.score}점` : '점수 없음'}</span>
                        <p>{item.suggestion || item.evidence || '설명이 없습니다.'}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="cp-result-section" aria-labelledby="cp-positive-heading">
                <h3 id="cp-positive-heading">잘된 점</h3>
                {result.positive_points?.length ? (
                  <ul>{result.positive_points.map((point, i) => <li key={i}>{point}</li>)}</ul>
                ) : (
                  <p className="cp-help-text">알려드릴 잘된 점이 없습니다.</p>
                )}
              </section>

              <section className="cp-result-section" aria-labelledby="cp-critical-heading">
                <h3 id="cp-critical-heading">고치면 좋은 점</h3>
                {result.critical_issues?.length ? (
                  <ul>{result.critical_issues.map((point, i) => <li key={i}>{point}</li>)}</ul>
                ) : (
                  <p className="cp-help-text">특별히 고칠 점이 없습니다.</p>
                )}
              </section>

              <section className="cp-result-section" aria-labelledby="cp-improve-heading">
                <h3 id="cp-improve-heading">개선 제안</h3>
                {result.improvement_suggestions?.length ? (
                  <ul>{result.improvement_suggestions.map((point, i) => <li key={i}>{point}</li>)}</ul>
                ) : (
                  <p className="cp-help-text">추가 제안이 없습니다.</p>
                )}
              </section>

              <section className="cp-result-section" aria-labelledby="cp-obstacle-heading">
                <h3 id="cp-obstacle-heading">방해물</h3>
                {obstacles.length ? (
                  <ul>
                    {obstacles.map((item, i) => (
                      <li key={i}>{item.object || '알 수 없는 물건'} · {item.location || '위치 정보 없음'}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="cp-help-text">감지된 방해물이 없습니다.</p>
                )}
              </section>

              <section className="cp-result-section" aria-labelledby="cp-summary-heading">
                <h3 id="cp-summary-heading">최종 요약</h3>
                <p>{result.final_summary || '요약이 없습니다.'}</p>
              </section>

              {(downloads?.excelBase64 || downloads?.pdfBase64) && (
                <div className="cp-downloads">
                  {downloads.excelBase64 && (
                    <button
                      type="button"
                      className="cp-btn cp-btn-outline"
                      onClick={() => downloadBase64File(downloads.excelBase64, EXCEL_MIME_TYPE, downloads.excelFileName)}
                    >
                      <DownloadSimple size={18} aria-hidden="true" />엑셀 파일 내려받기
                    </button>
                  )}
                  {downloads.pdfBase64 && (
                    <button
                      type="button"
                      className="cp-btn cp-btn-outline"
                      onClick={() => downloadBase64File(downloads.pdfBase64, PDF_MIME_TYPE, downloads.pdfFileName)}
                    >
                      <DownloadSimple size={18} aria-hidden="true" />PDF 파일 내려받기
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </main>
    </div>
  );
}
