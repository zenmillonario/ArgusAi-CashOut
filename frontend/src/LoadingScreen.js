import React, { useCallback, useEffect, useRef, useState } from 'react';
import peacockVideo from './assets/peacock-animation.mp4';
import peacockPoster from './assets/peacock-poster.webp';
import './LoadingScreen.css';

const INTRO_MS = 6500;
const EXIT_MS = 240;
const RAIN_CHARACTERS = '01アイウエオカキクケコサシスセソタチツテト';
const prefersStill = () => typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

function makeRain() {
  const width = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const count = Math.min(48, Math.max(16, Math.ceil(width / 32)));
  return Array.from({ length: count }, (_, index) => {
    const duration = 15 + Math.random() * 9;
    return {
      text: Array.from({ length: 26 + Math.floor(Math.random() * 19) }, () => RAIN_CHARACTERS[Math.floor(Math.random() * RAIN_CHARACTERS.length)]).join('\n'),
      left: `${((index + 0.5) / count) * 100}%`, duration: `${duration}s`,
      delay: `${-duration * ((index + 0.4) / count)}s`,
      opacity: 0.25 + Math.random() * 0.4, blue: index % 3 === 0,
    };
  });
}

/** Decorative introduction only. App.js owns account checks and the next route. */
export default function LoadingScreen({ onComplete, isDarkTheme }) {
  const [rain] = useState(makeRain);
  const [reducedMotion, setReducedMotion] = useState(prefersStill);
  const [visiblePage, setVisiblePage] = useState(() => typeof document === 'undefined' || !document.hidden);
  const [leaving, setLeaving] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const videoRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  const motionRef = useRef(reducedMotion);
  const mountedRef = useRef(false);
  const closingRef = useRef(false);
  const completedRef = useRef(false);
  const startedRef = useRef(null);
  const introTimer = useRef(null);
  const exitTimer = useRef(null);
  onCompleteRef.current = onComplete;
  motionRef.current = reducedMotion;

  const finish = useCallback(() => {
    if (!mountedRef.current || closingRef.current || completedRef.current) return;
    closingRef.current = true;
    clearTimeout(introTimer.current);
    setLeaving(true);
    videoRef.current?.pause();
    exitTimer.current = setTimeout(() => {
      if (!mountedRef.current || completedRef.current) return;
      completedRef.current = true;
      if (typeof onCompleteRef.current === 'function') onCompleteRef.current();
    }, motionRef.current ? 0 : EXIT_MS);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (startedRef.current === null) startedRef.current = performance.now();
    return () => {
      mountedRef.current = false;
      clearTimeout(introTimer.current);
      clearTimeout(exitTimer.current);
    };
  }, []);

  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const updateMotion = () => setReducedMotion(Boolean(preference?.matches));
    const updateVisibility = () => setVisiblePage(!document.hidden);
    const key = event => { if (event.key === 'Escape') finish(); };
    if (preference?.addEventListener) preference.addEventListener('change', updateMotion);
    else preference?.addListener?.(updateMotion);
    document.addEventListener('visibilitychange', updateVisibility);
    window.addEventListener('keydown', key);
    return () => {
      if (preference?.removeEventListener) preference.removeEventListener('change', updateMotion);
      else preference?.removeListener?.(updateMotion);
      document.removeEventListener('visibilitychange', updateVisibility);
      window.removeEventListener('keydown', key);
    };
  }, [finish]);

  useEffect(() => {
    if (closingRef.current) return undefined;
    const remaining = Math.max(0, INTRO_MS - (performance.now() - startedRef.current));
    introTimer.current = setTimeout(finish, reducedMotion ? Math.min(1200, remaining) : remaining);
    return () => clearTimeout(introTimer.current);
  }, [finish, reducedMotion]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    let disposed = false;
    if (reducedMotion || !visiblePage || leaving || videoFailed) video.pause();
    else {
      video.muted = true;
      const playback = video.play();
      playback?.catch(() => { if (!disposed && mountedRef.current) setVideoReady(false); });
    }
    return () => { disposed = true; video.pause(); };
  }, [reducedMotion, visiblePage, leaving, videoFailed]);

  return <main className={`cashout-startup${leaving ? ' is-exiting' : ''}${reducedMotion || !visiblePage ? ' is-still' : ''}`}
    data-theme={isDarkTheme ? 'dark' : 'light'} aria-labelledby="cashout-startup-title">
    <div className="cashout-startup-rain" aria-hidden="true">{rain.map((column, index) =>
      <span key={index} className={column.blue ? 'is-blue' : ''} style={{
        left: column.left, animationDuration: column.duration, animationDelay: column.delay, opacity: column.opacity,
      }}>{column.text}</span>)}</div>
    <div className="cashout-startup-atmosphere" aria-hidden="true" />

    <header className="cashout-startup-header">
      <span className="cashout-startup-origin"><span aria-hidden="true">✦</span> ZENMILLIONAIRES</span>
      <span className="cashout-startup-edition">A NEW PERSPECTIVE</span>
    </header>

    <div className="cashout-startup-composition">
      <div className="cashout-startup-art" aria-hidden="true">
        <div className="cashout-startup-orbit" />
        <div className="cashout-startup-orbit is-inner" />
        <div className="cashout-startup-media">
          <img src={peacockPoster} alt="" width="480" height="360" draggable="false" />
          {!reducedMotion && !videoFailed && <video ref={videoRef} autoPlay loop muted playsInline preload="metadata"
            className={videoReady ? 'is-ready' : ''} poster={peacockPoster}
            onPlaying={() => setVideoReady(true)} onWaiting={() => setVideoReady(false)}
            onStalled={() => setVideoReady(false)} onError={() => { setVideoReady(false); setVideoFailed(true); }}
            disablePictureInPicture tabIndex={-1}>
            <source src={peacockVideo} type="video/mp4" />
          </video>}
          <div className="cashout-startup-media-shade" />
        </div>
        <span className="cashout-startup-corner is-top" />
        <span className="cashout-startup-corner is-bottom" />
      </div>

      <section className="cashout-startup-welcome">
        <p className="cashout-startup-eyebrow"><span aria-hidden="true" /> SEE THE MARKET DIFFERENTLY</p>
        <h1 id="cashout-startup-title">CashOut<span>AI</span></h1>
        <p className="cashout-startup-description">Your perspective. Your practice.<br />Your next move.</p>
        <div className="cashout-startup-actions">
          <button type="button" onClick={finish} disabled={leaving} className="cashout-startup-enter">
            Enter CashOutAI <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
          <p>Intro ends automatically · Continue any time</p>
        </div>
      </section>
    </div>

    <footer className="cashout-startup-footer">
      <span>OBSERVE <i aria-hidden="true" /> PRACTICE <i aria-hidden="true" /> REVIEW</span>
      <span className="cashout-startup-signature">CASHOUTAI <b aria-hidden="true">/</b> ZENMILLIONAIRES</span>
    </footer>
  </main>;
}
