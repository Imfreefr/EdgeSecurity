import React, { useEffect, useRef } from "react";
import { gsap } from "gsap";

const WORDS = ["PERCEBER.", "ANTECIPAR.", "PROTEGER."];

function wasPlayed() {
  try {
    return sessionStorage.getItem("edgeIntroPlayed") === "true";
  } catch (_) {
    return false;
  }
}

function markPlayed() {
  try {
    sessionStorage.setItem("edgeIntroPlayed", "true");
  } catch (_) {}
}

export default function TypographicIntro({ reduced = false, onComplete }) {
  const root = useRef(null);
  const played = useRef(wasPlayed());

  useEffect(() => {
    if (played.current || reduced) {
      markPlayed();
      onComplete?.();
      return;
    }

    const scope = root.current;
    const words = scope?.querySelectorAll(".typo-intro-word");
    const finish = () => {
      markPlayed();
      onComplete?.();
      scope?.remove();
    };
    if (!scope || !words?.length) return finish();

    try {
      const timeline = gsap.timeline({ onComplete: finish });
      gsap.set(words, { yPercent: 110, autoAlpha: 0 });
      gsap.set(words[0], { yPercent: 0, autoAlpha: 1 });
      timeline
        .to(words[0], { yPercent: -110, duration: 0.58, delay: 0.42, ease: "expo.inOut" })
        .fromTo(words[1], { yPercent: 110, autoAlpha: 1 }, { yPercent: 0, duration: 0.58, ease: "expo.inOut" }, "<")
        .to({}, { duration: 0.18 })
        .to(words[1], { yPercent: -110, duration: 0.58, ease: "expo.inOut" })
        .fromTo(words[2], { yPercent: 110, autoAlpha: 1 }, { yPercent: 0, duration: 0.58, ease: "expo.inOut" }, "<")
        .to({}, { duration: 0.2 })
        .to(scope.querySelector(".typo-intro-wordmark"), { autoAlpha: 1, y: 0, duration: 0.34, ease: "expo.out" })
        .to(scope, { clipPath: "inset(0 0 100% 0)", duration: 0.62, ease: "expo.inOut" }, "+=0.28");
      return () => timeline.kill();
    } catch (_) {
      finish();
    }
  }, [onComplete, reduced]);

  if (played.current || reduced) return null;

  return (
    <div ref={root} className="typo-intro" aria-hidden="true">
      <div className="typo-intro-top"><span>EDGESECURITY</span><span>001</span></div>
      <div className="typo-intro-window">
        {WORDS.map((word) => <span className="typo-intro-word" key={word}>{word}</span>)}
      </div>
      <div className="typo-intro-bottom"><span>INDUSTRIAL VISION SYSTEM</span><span>2026</span></div>
      <div className="typo-intro-wordmark">EDGE<span>SECURITY</span></div>
    </div>
  );
}
