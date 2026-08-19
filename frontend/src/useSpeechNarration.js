import { useCallback, useEffect, useRef, useState } from 'react';

const RATE_STORAGE_KEY = 'vmd-consumer-tts-rate';

export const TTS_RATE_OPTIONS = { slow: 0.8, normal: 1, fast: 1.3 };
export const TTS_RATE_LABELS = { slow: '느리게', normal: '보통', fast: '빠르게' };

function isSpeechSynthesisSupported() {
  return (
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    typeof window.SpeechSynthesisUtterance === 'function'
  );
}

// 한국어 음성을 우선 고르되, 없으면 기본 음성을 그대로 씁니다.
function pickKoreanVoice(voices) {
  if (!voices?.length) return null;
  const koreanVoices = voices.filter((voice) => voice.lang?.toLowerCase().startsWith('ko'));
  if (!koreanVoices.length) return null;
  return (
    koreanVoices.find((voice) => /google|neural|online|natural/i.test(voice.name)) || koreanVoices[0]
  );
}

/**
 * 브라우저 내장 Web Speech API(SpeechSynthesis)를 감싸서
 * 분석 결과 텍스트를 소리로 읽어주는 재생/일시정지/정지/속도 조절 기능을 제공합니다.
 * 별도의 백엔드 호출이나 API 키 없이 동작합니다.
 */
export function useSpeechNarration() {
  const isSupported = isSpeechSynthesisSupported();

  // idle: 대기 | playing: 읽는 중 | paused: 일시정지 | done: 다 읽음 | error: 오류
  const [status, setStatus] = useState('idle');
  const [rateKey, setRateKeyState] = useState(() => {
    if (typeof window === 'undefined') return 'normal';
    const saved = window.localStorage.getItem(RATE_STORAGE_KEY);
    return TTS_RATE_OPTIONS[saved] != null ? saved : 'normal';
  });

  const voicesRef = useRef([]);
  const textRef = useRef('');
  const statusRef = useRef(status);
  const utteranceRef = useRef(null);
  const isFirstRateEffect = useRef(true);
  // 지금까지 읽은 위치(글자 인덱스). Chrome/Edge(Windows)는 speechSynthesis.pause()
  // 이후 resume()을 호출해도 실제로 이어 읽지 않는 고질적인 버그가 있어,
  // 네이티브 pause/resume 대신 이 위치부터 다시 speak()하는 방식으로 이어 듣기를 구현합니다.
  const spokenOffsetRef = useRef(0);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    if (!isSupported) return undefined;
    const loadVoices = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    loadVoices();
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
  }, [isSupported]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(RATE_STORAGE_KEY, rateKey);
  }, [rateKey]);

  const stop = useCallback(() => {
    if (!isSupported) return;
    utteranceRef.current = null;
    spokenOffsetRef.current = 0;
    window.speechSynthesis.cancel();
    setStatus('idle');
  }, [isSupported]);

  // 언마운트 시(또는 다른 화면으로 이동 시) 재생 중인 음성을 반드시 멈춥니다.
  useEffect(() => {
    return () => {
      if (!isSupported) return;
      utteranceRef.current = null;
      window.speechSynthesis.cancel();
    };
  }, [isSupported]);

  // baseOffset: textRef.current 중 이번에 새로 읽기 시작하는 지점(글자 인덱스).
  // 처음부터 읽을 땐 0, 이어 듣기일 땐 지난번에 멈춘 지점을 넘겨받습니다.
  const speakFrom = useCallback(
    (fullText, baseOffset) => {
      if (!isSupported || !fullText) return;
      const remaining = fullText.slice(baseOffset);
      if (!remaining) {
        setStatus('done');
        return;
      }
      utteranceRef.current = null;
      window.speechSynthesis.cancel();

      const utterance = new window.SpeechSynthesisUtterance(remaining);
      utterance.lang = 'ko-KR';
      utterance.rate = TTS_RATE_OPTIONS[rateKey] ?? 1;

      const voices = voicesRef.current.length ? voicesRef.current : window.speechSynthesis.getVoices();
      const voice = pickKoreanVoice(voices);
      if (voice) utterance.voice = voice;

      // cancel() 이후에도 이전 utterance의 이벤트가 뒤늦게 도착할 수 있어,
      // 지금 재생 중인 utterance가 맞는지 확인한 뒤에만 상태를 갱신합니다.
      const isCurrent = () => utteranceRef.current === utterance;
      utterance.onstart = () => isCurrent() && setStatus('playing');
      utterance.onresume = () => isCurrent() && setStatus('playing');
      utterance.onpause = () => isCurrent() && setStatus('paused');
      utterance.onend = () => isCurrent() && setStatus('done');
      utterance.onerror = () => isCurrent() && setStatus('error');
      // 단어 경계마다 지금까지 읽은 위치를 기억해둡니다(일시정지 시 사용).
      utterance.onboundary = (event) => {
        if (!isCurrent()) return;
        if (typeof event.charIndex === 'number') {
          spokenOffsetRef.current = baseOffset + event.charIndex;
        }
      };

      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [isSupported, rateKey]
  );

  const speak = useCallback(
    (text) => {
      if (!isSupported || !text) return;
      textRef.current = text;
      spokenOffsetRef.current = 0;
      speakFrom(text, 0);
    },
    [isSupported, speakFrom]
  );

  // Chrome/Edge(Windows)는 speechSynthesis.pause() 이후 resume()을 호출해도
  // 실제로 이어 읽지 않는 고질적인 버그가 있어, 네이티브 pause 대신
  // 지금까지 읽은 위치를 기억해두고 재생을 취소하는 방식으로 대체합니다.
  const pause = useCallback(() => {
    if (!isSupported) return;
    utteranceRef.current = null;
    window.speechSynthesis.cancel();
    setStatus('paused');
  }, [isSupported]);

  // 네이티브 resume() 대신, 멈췄던 위치부터 새로 speak()해 이어 듣기를 구현합니다.
  const resume = useCallback(() => {
    if (!isSupported || !textRef.current) return;
    speakFrom(textRef.current, spokenOffsetRef.current);
  }, [isSupported, speakFrom]);

  const setRateKey = useCallback((key) => {
    if (TTS_RATE_OPTIONS[key] == null) return;
    setRateKeyState(key);
  }, []);

  // 재생 중/일시정지 중에 속도를 바꾸면, 새 속도로 처음부터 다시 읽어줍니다.
  // (브라우저 음성엔진은 재생 중간 지점부터 속도만 바꿔 이어 읽는 기능을 지원하지 않습니다.)
  useEffect(() => {
    if (isFirstRateEffect.current) {
      isFirstRateEffect.current = false;
      return;
    }
    if (!isSupported || !textRef.current) return;
    if (statusRef.current === 'playing' || statusRef.current === 'paused') {
      speak(textRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rateKey]);

  return { isSupported, status, rateKey, setRateKey, speak, pause, resume, stop };
}
