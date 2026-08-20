import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Camera,
  CaretDoubleRight,
  CaretLeft,
  CircleHalf,
  Pause,
  Play,
  SpeakerHigh,
  SpinnerGap,
  Stop,
  TextAa,
  Trash,
  WarningCircle,
  X,
} from '@phosphor-icons/react';
import './consumer-page.css';
import {
  UPLOAD_MAX_DIMENSION,
  UPLOAD_TARGET_BYTES,
  resizeImageDataUrl,
  readFileAsDataUrl,
  postJson,
} from './mediaUtils';
import { useSpeechNarration, TTS_RATE_LABELS } from './useSpeechNarration';

const TEXT_SIZE_KEY = 'vmd-consumer-text-size';
const CONTRAST_KEY = 'vmd-consumer-high-contrast';

const FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function formatKrw(amount) {
  return typeof amount === 'number' ? `약 ${amount.toLocaleString('ko-KR')}원` : '';
}

// "대표 제품(사진/이름/가격/디자인) + 연관 제품" 카드 뷰. 연관 제품을 누르면
// 그 제품이 새 대표 제품이 되고, 방금까지 대표였던 제품이 연관 제품 목록에
// 다시 나타납니다(카탈로그가 5개뿐이라 전체를 자연스럽게 돌아볼 수 있도록).
// image_url은 제3자 CDN(Lyst)이라 깨질 수 있어(catalog.py 참고), 실패하면
// 이미지 없이 텍스트만 보이도록 숨깁니다.
function ProductDetailPanel({
  product,
  relatedProducts,
  onSelectProduct,
  onBack,
  askQuestion,
  onAskQuestionChange,
  askHistory,
  latestAnswer,
  isAsking,
  onAsk,
}) {
  const nameRef = useRef(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, [product]);

  const metaLine = [product.color, product.material, product.pattern].filter(Boolean).join(' · ');
  const others = (relatedProducts || []).filter((item) => item.id !== product.id);

  return (
    <div className="cp-product-detail">
      <button type="button" className="cp-btn cp-btn-outline cp-product-back" onClick={onBack}>
        <CaretLeft size={16} aria-hidden="true" />
        상품 정보로 돌아가기
      </button>

      <div className="cp-product-main">
        <img
          src={product.image_url}
          alt=""
          className="cp-product-image"
          onError={(event) => {
            event.currentTarget.style.display = 'none';
          }}
        />
        <h3 className="cp-product-name" tabIndex={-1} ref={nameRef}>
          {product.name}
        </h3>
        {formatKrw(product.price_krw_approx) && (
          <p className="cp-product-price">{formatKrw(product.price_krw_approx)}</p>
        )}
        {metaLine && <p className="cp-product-meta">{metaLine}</p>}
        {product.description && <p className="cp-product-desc">{product.description}</p>}
      </div>

      {others.length > 0 && (
        <div className="cp-related-products">
          <h4 className="cp-related-heading">연관 제품</h4>
          <ul className="cp-related-list">
            {others.map((related) => (
              <li key={related.id}>
                <button type="button" className="cp-related-item" onClick={() => onSelectProduct(related)}>
                  <img
                    src={related.image_url}
                    alt=""
                    onError={(event) => {
                      event.currentTarget.style.display = 'none';
                    }}
                  />
                  <span className="cp-related-name">{related.name}</span>
                  {formatKrw(related.price_krw_approx) && (
                    <span className="cp-related-price">{formatKrw(related.price_krw_approx)}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="cp-ask-box">
        <label htmlFor="cpAskInput" className="cp-ask-label">이 제품에 대해 더 물어보세요</label>
        <div className="cp-ask-row">
          <input
            id="cpAskInput"
            type="text"
            value={askQuestion}
            onChange={(event) => onAskQuestionChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                onAsk();
              }
            }}
            placeholder="예: 다른 색상도 있어요?"
          />
          <button type="button" className="cp-btn cp-btn-primary" onClick={() => onAsk()} disabled={isAsking}>
            {isAsking ? '...' : '묻기'}
          </button>
        </div>

        {/* 답변이 새로 올 때만 한 번 안내하는 화면 밖 알림 — 목록 전체를
            aria-live로 걸면 질문할 때마다 스크린리더가 지난 대화까지
            전부 다시 읽어서 번거롭습니다. */}
        <p className="cp-sr-only" aria-live="polite">{latestAnswer}</p>

        {askHistory.length > 0 && (
          <ul className="cp-ask-history">
            {askHistory.map((item, index) => (
              <li key={index}>
                <p className="cp-ask-q">Q. {item.question}</p>
                <p className="cp-ask-a">{item.answer}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// 의류 사진이면 감각적 서술 + 제품 질문(질문하기), 공간 사진이면 접근성 안내를
// 보여주는 모달. 유니버설 디자인 원칙(인지 가능한 정보, 오류 허용, 적은 신체적
// 노력, 공평한 사용)에 맞춰: 열리면 포커스가 제목으로 이동하고, 닫히면 이 모달을
// 연 버튼으로 포커스가 돌아오며, Esc로 닫을 수 있고, 열려 있는 동안 Tab이 모달
// 밖으로 새어나가지 않도록 포커스를 가둡니다. 닫기 버튼도 아이콘 대신 글자 라벨을
// 함께 달아 이 페이지의 다른 버튼들과 같은 톤을 유지합니다.
function PhotoInsightModal({
  type,
  content,
  isOpen,
  onClose,
  triggerRef,
  askQuestion,
  onAskQuestionChange,
  askHistory,
  latestAnswer,
  isAsking,
  onAsk,
  itemType,
  onCatalogLookup,
  isCatalogLoading,
  catalogProducts,
  selectedProduct,
  onSelectProduct,
  onBackFromProduct,
  narration,
  narrationText,
}) {
  const isClothing = type === 'clothing';
  const dialogRef = useRef(null);
  const headingRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      window.requestAnimationFrame(() => headingRef.current?.focus());
    } else {
      triggerRef?.current?.focus();
      narration?.stop();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, triggerRef]);

  // 새 사진을 살펴봐서 내용이 바뀌면(이전 모달 내용과 다른 서술/항목이 오면),
  // 읽고 있던 이전 내용을 계속 읽지 않도록 멈춥니다.
  useEffect(() => {
    narration?.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [narrationText]);

  // 제품 상세 화면으로 전환되거나(대표 제품이 바뀌거나) 연관 제품을 눌러 다른
  // 제품으로 넘어가면, 화면이 바뀐 것을 놓치지 않도록 그 제품 정보를 자동으로
  // 읽어줍니다. 위 effect가 먼저 이전 내용을 멈추고, 그다음 이 effect가 새
  // 내용을 읽기 시작합니다(선언 순서대로 실행되는 React effect 순서를 이용).
  useEffect(() => {
    if (selectedProduct && narration?.isSupported && narrationText) {
      narration.speak(narrationText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProduct]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const node = dialogRef.current;
      if (!node) return;
      const focusable = Array.from(node.querySelectorAll(FOCUSABLE_SELECTOR));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      <div className={`cp-modal-overlay${isOpen ? ' open' : ''}`} onClick={onClose} />
      <aside
        ref={dialogRef}
        className={`cp-modal${isOpen ? ' open' : ''}`}
        aria-hidden={!isOpen}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cpModalHeading"
      >
        <div className="cp-modal-head">
          <h2 id="cpModalHeading" className="cp-modal-title" tabIndex={-1} ref={headingRef}>
            {isClothing ? '의류 안내' : '공간 안내'}
          </h2>
          <button type="button" className="cp-modal-close" onClick={onClose}>
            <X size={18} aria-hidden="true" />닫기
          </button>
        </div>

        <div className="cp-modal-body">
          {narration && (
            <div className="cp-narration" role="group" aria-label="음성으로 결과 듣기">
              {narration.isSupported ? (
                <>
                  <div className="cp-narration-controls">
                    <button
                      type="button"
                      className="cp-btn cp-btn-primary"
                      onClick={() => {
                        if (narration.status === 'playing') {
                          narration.pause();
                        } else if (narration.status === 'paused') {
                          narration.resume();
                        } else {
                          narration.speak(narrationText);
                        }
                      }}
                      disabled={!narrationText}
                    >
                      {narration.status === 'playing' ? (
                        <><Pause size={18} aria-hidden="true" />일시정지</>
                      ) : narration.status === 'paused' ? (
                        <><Play size={18} aria-hidden="true" />이어 듣기</>
                      ) : (
                        <><SpeakerHigh size={18} aria-hidden="true" />결과 읽어주기</>
                      )}
                    </button>
                    {(narration.status === 'playing' || narration.status === 'paused') && (
                      <button type="button" className="cp-btn cp-btn-outline" onClick={narration.stop}>
                        <Stop size={18} aria-hidden="true" />정지
                      </button>
                    )}
                  </div>

                  <div className="cp-narration-rate" role="group" aria-label="읽는 속도 선택">
                    <span className="cp-toolbar-label">읽는 속도</span>
                    {Object.entries(TTS_RATE_LABELS).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        aria-pressed={narration.rateKey === key}
                        onClick={() => narration.setRateKey(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>

                  <p className="cp-narration-status" role="status" aria-live="polite">
                    {narration.status === 'playing' && '음성으로 읽는 중입니다.'}
                    {narration.status === 'paused' && '일시정지했습니다.'}
                    {narration.status === 'done' && '읽기를 마쳤습니다.'}
                    {narration.status === 'error' && '음성 읽기 중 오류가 발생했습니다.'}
                  </p>
                </>
              ) : (
                <p className="cp-help-text">이 브라우저는 결과를 음성으로 읽어주는 기능을 지원하지 않습니다.</p>
              )}
            </div>
          )}

          {isClothing ? (
            selectedProduct ? (
              <ProductDetailPanel
                product={selectedProduct}
                relatedProducts={catalogProducts}
                onSelectProduct={onSelectProduct}
                onBack={onBackFromProduct}
                askQuestion={askQuestion}
                onAskQuestionChange={onAskQuestionChange}
                askHistory={askHistory}
                latestAnswer={latestAnswer}
                isAsking={isAsking}
                onAsk={onAsk}
              />
            ) : (
            <>
              <ul className="cp-space-list">
                {(content?.items || []).map((item, index) => (
                  <li className="cp-space-item" key={index}>
                    <strong className="cp-space-label">{item.label}</strong>
                    <p className="cp-space-desc">{item.description}</p>
                  </li>
                ))}
              </ul>

              {itemType && (
                <div className="cp-catalog-trigger">
                  <button
                    type="button"
                    className="cp-btn cp-btn-outline cp-catalog-btn"
                    onClick={onCatalogLookup}
                    disabled={isCatalogLoading}
                  >
                    {isCatalogLoading ? '찾는 중...' : `${itemType} 관련 MCM 제품 보기`}
                    {!isCatalogLoading && <CaretDoubleRight size={16} aria-hidden="true" />}
                  </button>

                  {catalogProducts !== null && catalogProducts.length === 0 && (
                    <p className="cp-help-text">지금 안내해드릴 수 있는 {itemType} 관련 제품이 없어요.</p>
                  )}
                </div>
              )}
            </>
            )
          ) : (
            <ul className="cp-space-list">
              {(content?.items || []).map((item, index) => (
                <li className="cp-space-item" key={index}>
                  <strong className="cp-space-label">{item.label}</strong>
                  <p className="cp-space-desc">{item.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}

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
  // 사진을 올리면 "1. 사진 올리기" 섹션이 헤더 바로 아래로 올라오도록 글자
  // 크기·고대비 설정 패널을 자동으로 접습니다. 필요하면 헤더의 토글 버튼으로
  // 언제든 다시 펼칠 수 있습니다.
  const [isA11yPanelOpen, setIsA11yPanelOpen] = useState(true);

  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  const [isInsightLoading, setIsInsightLoading] = useState(false);
  const [insightError, setInsightError] = useState('');
  const [photoModalType, setPhotoModalType] = useState(null); // 'clothing' | 'space'
  const [photoModalContent, setPhotoModalContent] = useState(null);
  const [isPhotoModalOpen, setIsPhotoModalOpen] = useState(false);
  const [askQuestion, setAskQuestion] = useState('');
  const [askHistory, setAskHistory] = useState([]);
  const [latestAnswer, setLatestAnswer] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  // catalogProducts: null이면 아직 조회 전, []이면 조회했지만 관련 제품이 없음.
  const [catalogProducts, setCatalogProducts] = useState(null);
  const [isCatalogLoading, setIsCatalogLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const captureButtonRef = useRef(null);
  const insightTriggerRef = useRef(null);

  const narration = useSpeechNarration();
  // clothing 응답은 narration 필드, space 응답은 text 필드에 TTS용 평문이 들어있습니다
  // (services/consumer_prompt.py·accessibility_prompt.py 참고). 제품 상세 화면을
  // 보고 있을 때는 사진 분석 내용 대신 그 제품 정보를 읽도록 바꿉니다.
  const narrationText = useMemo(() => {
    if (selectedProduct) {
      const metaLine = [selectedProduct.color, selectedProduct.material, selectedProduct.pattern]
        .filter(Boolean)
        .join(', ');
      const priceLine = formatKrw(selectedProduct.price_krw_approx);
      return [selectedProduct.name, priceLine, metaLine, selectedProduct.description].filter(Boolean).join('. ');
    }
    return photoModalContent?.narration || photoModalContent?.text || '';
  }, [photoModalContent, selectedProduct]);
  // 의류 안내에서 탐색된 품목명 — "이 품목 관련 MCM 카탈로그 제품 보기" 버튼에 씁니다.
  const detectedItemType = photoModalContent?.item_type || '';

  useEffect(() => {
    window.localStorage.setItem(TEXT_SIZE_KEY, textSize);
  }, [textSize]);

  useEffect(() => {
    window.localStorage.setItem(CONTRAST_KEY, highContrast ? '1' : '0');
  }, [highContrast]);

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => {
    document.body.style.overflow = isPhotoModalOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isPhotoModalOpen]);

  const handleImageInputChange = async (event) => {
    const files = Array.from(event.target.files || []).filter((file) => file.type.startsWith('image/'));
    const next = await Promise.all(files.map(readFileAsDataUrl));
    setPreviewImages((prev) => [...prev, ...next]);
    setIsA11yPanelOpen(false);
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
    setIsA11yPanelOpen(false);
    setStatusMessage('사진을 촬영해서 목록에 추가했습니다.');
  };

  const runPhotoInsight = async () => {
    if (!previewImages.length) {
      setInsightError('먼저 사진을 추가해 주세요.');
      return;
    }
    setInsightError('');
    setIsInsightLoading(true);
    setAskHistory([]);
    setAskQuestion('');
    setLatestAnswer('');
    setCatalogProducts(null);
    setSelectedProduct(null);
    narration.stop();
    try {
      const lastImage = previewImages[previewImages.length - 1];
      const payload = await postJson('/api/consumer/photo-insight', { image: lastImage });
      setPhotoModalType(payload.type);
      setPhotoModalContent({
        items: payload.items,
        narration: payload.narration,
        text: payload.text,
        item_type: payload.item_type,
      });
      setIsPhotoModalOpen(true);
    } catch (error) {
      setInsightError(`사진을 살펴보는 데 실패했어요: ${error.message}`);
    } finally {
      setIsInsightLoading(false);
    }
  };

  // 이미 받아온 결과가 있으면(같은 세션 안에서) 새로 요청하지 않고 그대로 다시 엽니다 —
  // 매번 새 API 호출을 만들지 않는 게 비용·시간 면에서 낫습니다.
  const reopenPhotoModal = () => {
    setIsPhotoModalOpen(true);
  };

  const runAsk = async (overrideQuestion) => {
    const question = (overrideQuestion ?? askQuestion).trim();
    if (!question || isAsking) return;
    setIsAsking(true);
    try {
      const payload = await postJson('/api/consumer/ask', { question });
      setAskHistory((prev) => [...prev, { question, answer: payload.answer }]);
      setLatestAnswer(payload.answer);
      setAskQuestion('');
    } catch (error) {
      const answer = `답을 가져오지 못했어요: ${error.message}`;
      setAskHistory((prev) => [...prev, { question, answer }]);
      setLatestAnswer(answer);
    } finally {
      setIsAsking(false);
    }
  };

  // ">> {품목} 관련 MCM 제품 보기" 버튼 — 사진에서 탐색된 품목명으로 카탈로그를
  // 조회합니다. LLM 재서술 없이 실제 제품 데이터(사진/이름/가격/설명)를 그대로
  // 받아와, 첫 번째 매칭 제품을 곧바로 대표 제품으로 선택해 모달을 제품 상세
  // 화면으로 전환합니다(중간에 "제품을 골라주세요" 목록 단계 없이 바로 이동).
  // 카탈로그에 없는 카테고리(예: 니트)면 빈 배열이 오고, 그 경우 상품 정보
  // 화면에 "관련 제품이 없다"고 안내합니다(백엔드 find_absent_category와 동일
  // 판정 로직 재사용).
  const runCatalogLookup = async () => {
    if (!detectedItemType || isCatalogLoading) return;
    setIsCatalogLoading(true);
    try {
      const payload = await postJson('/api/consumer/catalog-products', { item_type: detectedItemType });
      const products = payload.products || [];
      setCatalogProducts(products);
      setSelectedProduct(products[0] || null);
    } catch (error) {
      setCatalogProducts([]);
      setSelectedProduct(null);
    } finally {
      setIsCatalogLoading(false);
    }
  };

  const selectProduct = (product) => {
    setSelectedProduct(product);
  };

  const backFromProduct = () => {
    setSelectedProduct(null);
  };

  return (
    <div className={`cp-page cp-text-${textSize}${highContrast ? ' cp-contrast' : ''}`}>
      <a className="cp-skip-link" href="#cp-main">본문으로 바로가기</a>

      <header className="cp-header">
        {isA11yPanelOpen ? (
          <div className="cp-a11y-toolbar" id="cpA11yToolbar">
            <div className="cp-toolbar-group" role="group" aria-label="글자 크기 선택">
              <span className="cp-toolbar-label"><TextAa size={20} aria-hidden="true" />글자 크기</span>
              <button type="button" aria-pressed={textSize === 'normal'} onClick={() => setTextSize('normal')}>보통</button>
              <button type="button" aria-pressed={textSize === 'large'} onClick={() => setTextSize('large')}>크게</button>
              <button type="button" aria-pressed={textSize === 'xlarge'} onClick={() => setTextSize('xlarge')}>아주 크게</button>
            </div>
            <div className="cp-toolbar-secondary">
              <button
                type="button"
                className="cp-contrast-toggle"
                aria-pressed={highContrast}
                onClick={() => setHighContrast((prev) => !prev)}
              >
                <CircleHalf size={18} aria-hidden="true" />
                {highContrast ? '고대비 화면 끄기' : '고대비 화면 켜기'}
              </button>
              <button
                type="button"
                className="cp-a11y-toggle"
                aria-expanded="true"
                aria-controls="cpA11yToolbar"
                onClick={() => setIsA11yPanelOpen(false)}
              >
                <TextAa size={18} aria-hidden="true" />
                보기 설정 접기
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="cp-a11y-toggle"
            aria-expanded="false"
            aria-controls="cpA11yToolbar"
            onClick={() => setIsA11yPanelOpen(true)}
          >
            <TextAa size={18} aria-hidden="true" />
            보기 설정 펼치기
          </button>
        )}
      </header>

      <main id="cp-main" className="cp-main">
        <ol className="cp-steps">
          <li className="cp-step cp-step-photo" aria-labelledby="cp-step1-heading">
            <h2 id="cp-step1-heading"><span className="cp-step-num" aria-hidden="true">1</span>사진 올리기</h2>
            <p className="cp-step-desc">매장 사진을 선택하거나 직접 촬영해서 추가하세요.</p>

            <div className="cp-upload-row">
              <label className="cp-dropzone" htmlFor="cpImageInput">
                <span className="cp-dropzone-icon" aria-hidden="true"><Camera size={56} /></span>
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
                  {isCameraOpen ? <X size={56} /> : <Camera size={56} />}
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
              <div className="cp-insight-trigger">
                <div className="cp-insight-actions">
                  <button
                    type="button"
                    className="cp-btn cp-btn-primary"
                    onClick={runPhotoInsight}
                    disabled={isInsightLoading}
                    ref={insightTriggerRef}
                  >
                    {isInsightLoading && <SpinnerGap size={18} className="cp-spin" aria-hidden="true" />}
                    {isInsightLoading ? '살펴보는 중입니다...' : '방금 찍은 사진 살펴보기'}
                  </button>
                  {photoModalContent && !isPhotoModalOpen && (
                    <button type="button" className="cp-btn cp-btn-outline" onClick={reopenPhotoModal}>
                      마지막 결과 다시 보기
                    </button>
                  )}
                </div>
                <p className="cp-step-desc">
                  옷이나 가방을 찍으셨으면 그 제품에 대해, 매장 공간을 찍으셨으면 이동 안전 정보를 안내해드려요.
                </p>
                {statusMessage && (
                  <p className="cp-status-text" role="status">{statusMessage}</p>
                )}
                {(insightError || errorMessage) && (
                  <p className="cp-error-text" role="alert">
                    <WarningCircle size={18} weight="fill" aria-hidden="true" />{insightError || errorMessage}
                  </p>
                )}
              </div>
            )}

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
        </ol>
      </main>

      <PhotoInsightModal
        type={photoModalType}
        content={photoModalContent}
        isOpen={isPhotoModalOpen}
        onClose={() => setIsPhotoModalOpen(false)}
        triggerRef={insightTriggerRef}
        askQuestion={askQuestion}
        onAskQuestionChange={setAskQuestion}
        askHistory={askHistory}
        latestAnswer={latestAnswer}
        isAsking={isAsking}
        onAsk={runAsk}
        itemType={detectedItemType}
        onCatalogLookup={runCatalogLookup}
        isCatalogLoading={isCatalogLoading}
        catalogProducts={catalogProducts}
        selectedProduct={selectedProduct}
        onSelectProduct={selectProduct}
        onBackFromProduct={backFromProduct}
        narration={narration}
        narrationText={narrationText}
      />
    </div>
  );
}
