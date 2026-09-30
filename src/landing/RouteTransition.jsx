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
  const tlRef = useRef(null);
  coverRef.current = onCover;

  useEffect(() => {
    // Chegada vinda do login: consome o flag, landing carrega limpa.
    sessionStorage.removeItem("edge_fx");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = matchMedia("(max-width: 700px)").matches;
    const reset = () => {
      tlRef.current?.kill();
      tlRef.current = null;
      busy.current = false;
      root.current?.classList.remove("is-active");
      coverRef.current?.(false);
      try {
        gsap.set(layers.current, { xPercent: 101 });
        gsap.set(brand.current, { autoAlpha: 0, y: 14 });
      } catch (_) {
        // CSS already holds the safe, off-screen state.
      }
    };
    reset();

    const navigate = (href, mode) => {
      try {
        sessionStorage.setItem("edge_fx", mode);
      } catch (_) {
        // Navigation must still work when storage is blocked by policy.
      }
      reset();
      location.href = href;
    };

    const go = (e) => {
      const { href } = e.detail;
      if (busy.current || !href) return;
      if (reduced) {
        navigate(href, e.detail.mode);
        return;
      }
      busy.current = true;
      coverRef.current?.(true);
      root.current?.classList.add("is-active");

      // Coreografar: menu começa a fechar + transition começa junto
      // window.__edgeMenuClose fecha o menu, mas não esperamos - ambos correm em paralelo
      window.__edgeMenuClose?.();

      const d = small ? 0.4 : 0.58;
      try {
        tlRef.current = gsap
          .timeline({ onComplete: () => navigate(href, e.detail.mode) })
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
      } catch (_) {
        navigate(href, e.detail.mode);
      }
    };

    window.addEventListener("edge:route", go);
    return () => {
      window.removeEventListener("edge:route", go);
      reset();
    };
  }, []);

  // Cleanup ao desmontar
  useEffect(() => {
    return () => {
      tlRef.current?.kill();
      coverRef.current?.(false);
      root.current?.classList.remove("is-active");
      document.body.style.overflow = "";
    };
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
