import React, { useCallback, useEffect, useRef, useState } from "react";
import { gsap } from "gsap";

/**
 * StaggeredMenu — adaptado do React Bits (padrão free StaggeredMenu)
 * para os tokens da EdgeSecurity. Isolado sob `.edge-landing`.
 *
 * Tokens: accent #2f6fed, deep #101d33 / #0a1430, neutros paper/ink.
 * Sem cores do exemplo (#B497CF, #5227FF, #ff6b6b).
 * Sem socials (displaySocials=false — EdgeSecurity não possui links reais).
 */
const LAYERS = ["#0a1430", "#1b3a8f", "#2f6fed"];
const ACCENT = "#2f6fed";
const PANEL_BG = "#eeede8";
const PANEL_INK = "#242824";

const ITEMS = [
  { label: "A ideia", link: "#manifesto" },
  { label: "O risco", link: "#risk" },
  { label: "O produto", link: "#observe" },
  { label: "O sistema", link: "#system" },
  { label: "Assinatura", link: "#pricing" },
];

export default function StaggeredMenu({
  position = "right",
  displayItemNumbering = true,
  displaySocials = false,
  logo = { src: "/assets/logo.png", alt: "EdgeSecurity" },
  onToggle,
}) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const layers = useRef([]);
  const panel = useRef(null);
  const links = useRef([]);
  const meta = useRef(null);
  const tl = useRef(null);
  const trigger = useRef(null);
  const reduced = useRef(false);
  const openRef = useRef(false);

  useEffect(() => {
    reduced.current = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dir = position === "left" ? -1 : 1;
    gsap.set(layers.current, { xPercent: 100 * dir });
    gsap.set(panel.current, { xPercent: 100 * dir });
    gsap.set([...links.current, meta.current], { autoAlpha: 0, y: 34 });
    tl.current = gsap
      .timeline({ paused: true })
      .to(layers.current, {
        xPercent: 0,
        duration: 0.55,
        ease: "expo.inOut",
        stagger: 0.07,
      })
      .to(
        panel.current,
        { xPercent: 0, duration: 0.55, ease: "expo.inOut" },
        "-=0.35",
      )
      .to(
        links.current,
        { autoAlpha: 1, y: 0, duration: 0.5, ease: "expo.out", stagger: 0.06 },
        "-=0.25",
      )
      .to(
        meta.current,
        { autoAlpha: 1, y: 0, duration: 0.45, ease: "expo.out" },
        "-=0.35",
      );
    return () => tl.current?.kill();
  }, [position]);

  const setBodyLock = (locked) => {
    document.body.style.overflow = locked ? "hidden" : "";
  };

  const toggle = useCallback(
    (next) => {
      const value = next ?? !openRef.current;
      openRef.current = value;
      setOpen(value);
      setBodyLock(value);
      onToggle?.(value);
      if (reduced.current) {
        const dir = position === "left" ? -1 : 1;
        gsap.set(layers.current, { xPercent: value ? 0 : 100 * dir });
        gsap.set(panel.current, { xPercent: value ? 0 : 100 * dir });
        gsap.set([links.current, meta.current], {
          autoAlpha: value ? 1 : 0,
          y: value ? 0 : 34,
        });
      } else if (value) {
        tl.current?.timeScale(1).play();
      } else {
        tl.current?.timeScale(1.4).reverse();
      }
      if (!value) trigger.current?.focus({ preventScroll: true });
    },
    [onToggle, position],
  );

  // Fecha/reset quando a PageTransition assume a navegação.
  useEffect(() => {
    window.__edgeMenuClose = () => {
      if (openRef.current) toggle(false);
    };
    return () => {
      if (window.__edgeMenuClose) delete window.__edgeMenuClose;
    };
  }, [toggle]);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape" && openRef.current) toggle(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [toggle]);

  const go = () => {
    // Reativa o Lenis antes da navegação por âncora.
    onToggle?.(false);
    openRef.current = false;
    setOpen(false);
    setBodyLock(false);
    if (reduced.current) {
      const dir = position === "left" ? -1 : 1;
      gsap.set(layers.current, { xPercent: 100 * dir });
      gsap.set(panel.current, { xPercent: 100 * dir });
      gsap.set([links.current, meta.current], { autoAlpha: 0, y: 34 });
    } else {
      tl.current?.timeScale(1.8).reverse();
    }
  };

  return (
    <div
      ref={root}
      className={`sm-scope sm-${position}`}
      data-open={open || undefined}
    >
      <div className="sm-bar">
        <a className="sm-brand" href="#top" aria-label="EdgeSecurity início">
          <img src={logo.src} alt={logo.alt} width="28" height="28" />
          <span>
            EDGE<strong>SECURITY</strong>
          </span>
        </a>
        <div className="sm-bar-actions">
          <a className="sm-enter" href="/index.html">
            Entrar
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 12h15M12 5l7 7-7 7"
                stroke="currentColor"
                strokeWidth="1.3"
              />
            </svg>
          </a>
          <button
            ref={trigger}
            type="button"
            className="sm-toggle"
            aria-expanded={open}
            aria-controls="staggered-panel"
            aria-label={open ? "Fechar menu" : "Abrir menu"}
            onClick={() => toggle()}
          >
            <span className="sm-toggle-label">{open ? "Fechar" : "Menu"}</span>
            <span className="sm-burger" aria-hidden="true">
              <i />
              <i />
            </span>
          </button>
        </div>
      </div>

      <div
        className="sm-backdrop"
        aria-hidden="true"
        onClick={() => open && toggle(false)}
      />
      {LAYERS.map((c, i) => (
        <div
          key={c}
          aria-hidden="true"
          className="sm-layer"
          style={{ background: c }}
          ref={(el) => (layers.current[i] = el)}
        />
      ))}
      <aside
        id="staggered-panel"
        ref={panel}
        className="sm-panel"
        aria-label="Navegação principal"
        aria-hidden={!open}
        inert={!open}
      >
        <p className="sm-kicker">EdgeSecurity — navegação</p>
        <nav>
          {ITEMS.map((item, i) => (
            <a
              key={item.link}
              href={item.link}
              onClick={go}
              tabIndex={open ? 0 : -1}
              ref={(el) => (links.current[i] = el)}
            >
              {displayItemNumbering && (
                <small style={{ color: ACCENT }}>
                  0{i + 1}
                </small>
              )}
              {item.label}
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M4 12h15M12 5l7 7-7 7"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
              </svg>
            </a>
          ))}
        </nav>
        <div className="sm-meta" ref={meta}>
          <a className="sm-cta" href="/pages/cadastro.html">
            Cadastrar minha empresa
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 12h15M12 5l7 7-7 7"
                stroke="currentColor"
                strokeWidth="1.3"
              />
            </svg>
          </a>
          <a className="sm-login" href="/index.html">
            Já sou cliente — entrar
          </a>
          {displaySocials && <div className="sm-socials" />}
        </div>
      </aside>
    </div>
  );
}
