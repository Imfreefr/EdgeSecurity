import React, { useEffect, useRef } from "react";
import { gsap } from "gsap";

/**
 * RouteTransition — camada global de transição landing ↔ auth.
 * Mesma linguagem do StaggeredMenu: 3 camadas staggered + marca,
 * mesmos tokens (#0a1430, #2f6fed, paper) e easing expo.
 * Escala de z: conteúdo < webgl < menu (141–146) < transição (160).
 */
const LAYERS = ["#0a1430", "#2f6fed", "#eeede8"];

export function beginRouteTransition(href, mode = "enter") {
  window.dispatchEvent(
    new CustomEvent("edge:route", { detail: { href, mode } }),
  );
}

export default function RouteTransition({ onCover }) {
  const root = useRef(null);
  const layers = useRef([]);
  const brand = useRef(null);
  const busy = useRef(false);
  const coverRef = useRef(onCover);
  coverRef.current = onCover;

  useEffect(() => {
    // Chegada vinda do login: consome o flag, landing carrega limpa.
    sessionStorage.removeItem("edge_fx");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = matchMedia("(max-width: 700px)").matches;
    gsap.set(layers.current, { xPercent: 101 });
    gsap.set(brand.current, { autoAlpha: 0, y: 14 });
    const go = (e) => {
      const { href } = e.detail;
      if (busy.current || !href) return;
      if (reduced) {
        sessionStorage.setItem("edge_fx", e.detail.mode);
        location.href = href;
        return;
      }
      busy.current = true;
      coverRef.current?.(true);
      window.__edgeMenuClose?.();
      const d = small ? 0.4 : 0.58;
      gsap
        .timeline({
          onComplete: () => {
            sessionStorage.setItem("edge_fx", e.detail.mode);
            location.href = href;
          },
        })
        .to(layers.current, {
          xPercent: 0,
          duration: d,
          ease: "expo.inOut",
          stagger: small ? 0.05 : 0.08,
        })
        .to(
          brand.current,
          { autoAlpha: 1, y: 0, duration: 0.28, ease: "power2.out" },
          "-=0.22",
        )
        .to({}, { duration: small ? 0.08 : 0.22 });
    };
    window.addEventListener("edge:route", go);
    return () => window.removeEventListener("edge:route", go);
  }, []);

  return (
    <div ref={root} className="rt-scope" aria-hidden="true">
      {LAYERS.map((c, i) => (
        <div
          key={c}
          className="rt-layer"
          style={{ background: c }}
          ref={(el) => (layers.current[i] = el)}
        />
      ))}
      <div className="rt-brand" ref={brand}>
        EDGE<span>SECURITY</span>
      </div>
    </div>
  );
}
