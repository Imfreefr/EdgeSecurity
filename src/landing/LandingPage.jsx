import React, { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import Magnet from "./Magnet";
import StaggeredMenu from "./StaggeredMenu";
import RouteTransition, { beginRouteTransition } from "./RouteTransition";
import { distanceAt, riskState } from "./riskState";
gsap.registerPlugin(ScrollTrigger);
const Arrow = () => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 12h15M12 5l7 7-7 7" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);
const Photo = ({ name, alt, eager = false }) => (
  <img
    src={`/assets/landing/${name}.webp`}
    alt={alt}
    width="1600"
    height="1067"
    loading={eager ? "eager" : "lazy"}
    fetchPriority={eager ? "high" : "auto"}
    decoding="async"
  />
);
const features = [
  [
    "Câmeras centralizadas",
    "Webcams e câmeras de rede em um só painel. Teste a imagem antes de cadastrar e acompanhe o status de conexão.",
  ],
  [
    "Alertas de proximidade",
    "Acompanhe a aproximação entre pessoas e máquinas, com alertas visuais e sonoros para apoiar a operação.",
  ],
  [
    "Permissões por câmera",
    "Administradores organizam os acessos. Operadores visualizam as câmeras autorizadas para sua função.",
  ],
  [
    "Histórico e relatórios",
    "Consulte eventos, filtre registros e acompanhe o que aconteceu ao longo da operação.",
  ],
  [
    "Processamento local",
    "Na instalação local, a análise acontece no seu computador. Os vídeos permanecem dentro da sua operação.",
  ],
];
export default function LandingPage() {
  const root = useRef(null),
    scene = useRef(null);
  const lenisRef = useRef(null);
  const progress = useRef(0),
    sceneUpdate = useRef(null);
  const [reduced, setReduced] = useState(true),
    [desktop, setDesktop] = useState(false);
  const [vision, setVision] = useState(true),
    [distance, setDistance] = useState(4.8),
    [role, setRole] = useState("admin");
  const status = riskState(distance).label;
  const phase = distance > 4 ? 0 : distance > 3 ? 1 : distance > 1.5 ? 2 : 3;
  useEffect(() => {
    const motion = matchMedia("(prefers-reduced-motion: reduce)"),
      pointer = matchMedia("(min-width: 900px) and (pointer: fine)");
    const sync = () => {
      setReduced(motion.matches);
      setDesktop(pointer.matches);
    };
    sync();
    motion.addEventListener("change", sync);
    pointer.addEventListener("change", sync);
    const bodyStyle = document.body.getAttribute("style"),
      htmlStyle = document.documentElement.getAttribute("style");
    document.body.style.margin = "0";
    document.body.style.background = "#eeede8";
    document.documentElement.style.scrollBehavior = "auto";
    return () => {
      motion.removeEventListener("change", sync);
      pointer.removeEventListener("change", sync);
      for (const [el, style] of [
        [document.body, bodyStyle],
        [document.documentElement, htmlStyle],
      ]) {
        if (style === null) el.removeAttribute("style");
        else el.setAttribute("style", style);
      }
    };
  }, []);
  useEffect(() => {
    if (reduced) return;
    let lenis;
    const tick = (time) => lenis?.raf(time * 1000);
    if (desktop) {
      lenis = new Lenis({ duration: 1.05, anchors: true });
      lenisRef.current = lenis;
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(tick);
    }
    const ctx = gsap.context(() => {
      gsap.set(".hero-word span", { transformOrigin: "left bottom" });
      gsap
        .timeline({ defaults: { ease: "expo.out" } })
        .fromTo(
          ".hero-word span",
          { yPercent: 105, rotate: 3 },
          { yPercent: 0, rotate: 0, stagger: 0.12, duration: 1.3 },
        )
        .fromTo(
          ".hero-photo",
          { clipPath: "inset(10% 12% 10% 12%)", scale: 1.06 },
          { clipPath: "inset(0% 0% 0% 0%)", scale: 1, duration: 1.4 },
          0.15,
        );
      if (desktop) {
        gsap
          .timeline({
            scrollTrigger: {
              trigger: ".hero",
              start: "top top",
              end: "bottom top",
              scrub: 1,
            },
          })
          .to(".hero-photo img", { yPercent: 18, scale: 1.12, ease: "none" }, 0)
          .to(".hero-serif", { xPercent: -12, ease: "none" }, 0);
        gsap.fromTo(
          ".manifesto-emphasis",
          { clipPath: "inset(0 100% 0 0)" },
          {
            clipPath: "inset(0 0% 0 0)",
            ease: "none",
            scrollTrigger: {
              trigger: ".manifesto",
              start: "top 65%",
              end: "bottom 30%",
              scrub: 1,
            },
          },
        );
        if (innerHeight >= 800) ScrollTrigger.create({
          trigger: ".risk-stage",
          start: "top top",
          end: () => `+=${Math.min(innerHeight * 1.6, 1600)}`,
          invalidateOnRefresh: true,
          pin: true,
          scrub: true,
          onUpdate: (self) => {
            progress.current = self.progress;
            setDistance(distanceAt(self.progress));
            sceneUpdate.current?.(self.progress);
          },
        });
        gsap.fromTo(
          ".feed-secondary",
          { y: 100 },
          {
            y: -70,
            ease: "none",
            scrollTrigger: {
              trigger: ".observe",
              start: "top bottom",
              end: "bottom top",
              scrub: 1,
            },
          },
        );
        gsap.fromTo(
          ".feed-camera",
          { y: -70 },
          {
            y: 50,
            ease: "none",
            scrollTrigger: {
              trigger: ".observe",
              start: "top bottom",
              end: "bottom top",
              scrub: 1,
            },
          },
        );
        gsap
          .timeline({
            scrollTrigger: {
              trigger: ".finale",
              start: "top 85%",
              end: "bottom bottom",
              scrub: 1,
            },
          })
          .fromTo(
            ".final-photo",
            { clipPath: "inset(18% 28% 18% 28%)" },
            { clipPath: "inset(0% 0% 0% 0%)", ease: "none" },
            0,
          )
          .fromTo(".finale h2", { y: 80 }, { y: 0, ease: "none" }, 0);
      }
      gsap.utils
        .toArray(".reveal-photo")
        .forEach((el) =>
          gsap.fromTo(
            el,
            { clipPath: "inset(0 0 15% 0)" },
            {
              clipPath: "inset(0 0 0% 0)",
              duration: 1.1,
              ease: "expo.out",
              scrollTrigger: { trigger: el, start: "top 85%", once: true },
            },
          ),
        );

      ScrollTrigger.create({
        start: 0,
        end: "max",
        onUpdate: (self) =>
          gsap.set(".scroll-progress", { scaleX: self.progress }),
      });

      const rise = (selector, distance = 46) => {
        gsap.utils.toArray(selector).forEach((el, i) => {
          if (el.closest(".risk-stage")) return;
          gsap.fromTo(
            el,
            { y: distance, opacity: 0 },
            {
              y: 0,
              opacity: 1,
              duration: 1,
              ease: "expo.out",
              delay: Math.min(i * 0.07, 0.42),
              scrollTrigger: { trigger: el, start: "top 90%", once: true },
            },
          );
        });
      };

      rise(".section-meta", 26);
      rise(".section-label", 26);
      // Major chapters own their choreography; do not double-animate headings.
      rise(".detect h2, .control h2, .trace h2", 40);
      rise(".hero-bottom", 30);
      rise(".hero-title > p", 24);
      rise(".event-list li", 34);

      const flow = root.current.querySelector(".local-flow");
      if (flow)
        gsap.fromTo(
          flow,
          { scaleX: 0.8, opacity: 0, transformOrigin: "left center" },
          {
            scaleX: 1,
            opacity: 1,
            duration: 1.2,
            ease: "expo.out",
            scrollTrigger: { trigger: flow, start: "top 88%", once: true },
          },
        );

      const wire = root.current.querySelector(".connections svg path");
      if (wire) {
        const length = wire.getTotalLength();
        gsap.fromTo(
          wire,
          { strokeDasharray: length, strokeDashoffset: length },
          {
            strokeDashoffset: 0,
            ease: "none",
            scrollTrigger: {
              trigger: ".connections",
              start: "top 92%",
              end: "bottom 70%",
              scrub: 1,
            },
          },
        );
      }
    }, root);
    let active = true;
    document.fonts.ready.then(() => {
      if (active) ScrollTrigger.refresh();
    });
    return () => {
      active = false;
      lenisRef.current = null;
      ctx.revert();
      gsap.ticker.remove(tick);
      lenis?.destroy();
    };
  }, [reduced, desktop]);
  useEffect(() => {
    if (!desktop || reduced) return;
    let disposed = false,
      cleanup;
    const observer = new IntersectionObserver(
      async ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        try {
          const { mountScene } = await import("./riskScene");
          if (disposed) return;
          const result = mountScene(scene.current);
          cleanup = result.dispose;
          sceneUpdate.current = result.update;
          result.update(progress.current);
        } catch {
          /* The DOM diagram remains available without WebGL. */
        }
      },
      { rootMargin: "350px" },
    );
    observer.observe(scene.current);
    return () => {
      disposed = true;
      observer.disconnect();
      sceneUpdate.current = null;
      cleanup?.();
    };
  }, [desktop, reduced]);
  // Navbar adaptativa: amostra múltiplos pontos ao longo da barra
  // para decidir tema dark/light com base na luminância média.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    let raf = 0;
    const probe = () => {
      const bar = el.querySelector(".sm-bar");
      if (!bar) return;
      const rect = bar.getBoundingClientRect();
      const y = rect.top + rect.height / 2;
      let totalLum = 0, samples = 0;
      for (let x = rect.left + 20; x < rect.right - 20; x += Math.max(40, rect.width / 8)) {
        let node = document.elementFromPoint(x, y);
        while (node && node !== el && node !== document.documentElement) {
          const bg = getComputedStyle(node).backgroundColor;
          const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
          if (m && Number(m[4] ?? 1) > 0.6) {
            const lum = (0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3]) / 255;
            totalLum += lum;
            samples++;
            break;
          }
          node = node.parentElement;
        }
      }
      const avgLum = samples ? totalLum / samples : 0;
      const theme = avgLum > 0.5 ? "light" : "dark";
      el.setAttribute("data-nav", theme);
    };
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(probe);
    };
    probe();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    return () => {
      removeEventListener("scroll", schedule);
      removeEventListener("resize", schedule);
      cancelAnimationFrame(raf);
    };
  }, []);
  function manualDistance(value) {
    const n = Number(value);
    setDistance(n);
    progress.current = (4.8 - n) / 4;
    sceneUpdate.current?.(progress.current);
  }
  function onMenuToggle(open) {
    if (open) lenisRef.current?.stop();
    else lenisRef.current?.start();
  }
  // Transição cinematográfica landing → auth: intercepta ENTRAR/cadastro,
  // executa o cover e só então troca a rota (handoff via sessionStorage).
  useEffect(() => {
    const el = root.current;
    const onClick = (e) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
        return;
      const a = e.target.closest?.(
        'a[href="/index.html"], a[href="/pages/cadastro.html"]',
      );
      if (!a || !el.contains(a)) return;
      e.preventDefault();
      beginRouteTransition(a.getAttribute("href"), "enter");
    };
    el.addEventListener("click", onClick);
    return () => el.removeEventListener("click", onClick);
  }, []);
  return (
    <div ref={root} className="edge-landing">
      <div className="scroll-progress" aria-hidden="true" />
      <a className="skip" href="#manifesto">
        Pular para o conteúdo
      </a>
      <StaggeredMenu
        position="right"
        displayItemNumbering
        displaySocials={false}
        logo={{ src: "/assets/logo.png", alt: "EdgeSecurity" }}
        onToggle={onMenuToggle}
      />
      <RouteTransition
        onCover={() => {
          lenisRef.current?.stop();
        }}
      />
      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-title">
            <h1 id="hero-title">
              <span className="hero-word">
                <span>Antes do</span>
              </span>
              <span className="hero-word hero-serif">
                <span>impacto.</span>
              </span>
            </h1>
            <p>
              Visão computacional para
              <br />
              a segurança industrial.
              <br />
              <strong>Perceber. Antecipar. Proteger.</strong>
              <a className="hero-action" href="#risk">
                Veja como funciona <Arrow />
              </a>
            </p>
          </div>
          <figure className="hero-photo">
            <Photo
              name="factory"
              alt="Trabalhador com equipamento de proteção soldando uma peça industrial"
              eager
            />
            <figcaption>
              <span>UM NOVO OLHAR PARA A SEGURANÇA INDUSTRIAL</span>
              <span>EdgeSecurity / Visão computacional</span>
            </figcaption>
          </figure>
          <div className="hero-bottom">
            <span>
              Explore a experiência <span aria-hidden="true">↓</span>
            </span>
            <p>
              Câmeras que observam.
              <br />
              Inteligência que antecipa.
            </p>
            <a className="text-link" href="/pages/cadastro.html">
              Cadastrar minha empresa <Arrow />
            </a>
          </div>
        </section>
        <section id="manifesto" className="manifesto section-pad">
          <div className="section-meta">
            <span>01 / O olhar</span>
            <span>PREVENIR COMEÇA POR PERCEBER</span>
          </div>
          <h2>
            A indústria
            <br />
            não para.
            <br />
            <span className="manifesto-indent">
              O cuidado <em>também não.</em>
            </span>
          </h2>
          <div className="manifesto-bottom">
            <span className="manifesto-emphasis" aria-hidden="true">
              Antes.
            </span>
            <p>
              Entre uma pessoa e uma máquina, cada aproximação importa. A
              EdgeSecurity transforma imagens em percepção de risco — para que
              sua equipe possa agir antes do impacto.
            </p>
          </div>
        </section>
        <section id="risk" className="risk" aria-labelledby="risk-title">
          <div className="risk-stage" data-status={status}>
            <div className="section-meta">
              <span>02 / A distância</span>
              <span>DEMONSTRAÇÃO INTERATIVA · VALORES ILUSTRATIVOS</span>
            </div>
            <div className="risk-heading">
              <h2 id="risk-title">
                O risco se aproxima.
                <br />
                <em>O olhar se antecipa.</em>
              </h2>
              <div className="distance">
                  <output aria-label="Distância ilustrativa" aria-live="off">
                  {distance.toFixed(1)}
                  <small>m</small>
                </output>
                <span className="risk-state" aria-live="polite">{status}</span>
              </div>
            </div>
            <div
              className={`risk-model ${vision ? "vision-on" : ""}`}
              ref={scene}
              style={{ "--approach": (4.8 - distance) / 4 }}
            >
              <div
                className="risk-fallback"
                aria-label="Diagrama de pessoa se aproximando de uma máquina"
              >
                <span
                  className="diagram-person"
                  style={{
                    transform: `translateX(${(4.8 - distance) * 28}px)`,
                  }}
                >
                  <svg viewBox="0 0 50 120" aria-hidden="true">
                    <circle cx="25" cy="12" r="10" />
                    <path d="M14 29h22l8 48-10 2-5-26v61H19V53l-5 26-10-2z" />
                  </svg>
                </span>
                <span className="diagram-zone" />
                <span className="diagram-machine">
                  <i />
                  <i />
                  <i />
                </span>
              </div>
              <div className="vision-label person-label">PERSON</div>
              <div className="vision-label machine-label">MACHINE</div>
              <div className="vision-line">
                <span>{distance.toFixed(1)} m</span>
              </div>
              <div className="vision-label zone-label">
                ZONE / ÁREA DE ATENÇÃO
              </div>
            </div>
            <ol className="risk-sequence" aria-label="Etapas da prevenção">
              {["Observar", "Identificar", "Medir", "Alertar"].map((label, i) => (
                <li key={label} data-active={i <= phase} aria-current={i === phase ? "step" : undefined}>
                  <span aria-hidden="true">0{i + 1}</span>{label}
                </li>
              ))}
            </ol>
            <div className="risk-controls">
              <p>
                Ao reduzir a distância, a atenção muda de nível.
                <br />
                Um alerta dá à equipe a chance de reagir.
              </p>
              <label className="distance-control">
                Explore a aproximação
                <input
                  aria-label="Distância entre pessoa e máquina"
                  type="range"
                  min="0.8"
                  max="4.8"
                  step="0.1"
                  value={distance}
                  onChange={(e) => manualDistance(e.target.value)}
                />
              </label>
              <button
                className="vision-toggle"
                aria-pressed={vision}
                onClick={() => setVision(!vision)}
              >
                {vision ? "Desativar" : "Ativar"} visão computacional{" "}
                <span aria-hidden="true">{vision ? "−" : "+"}</span>
              </button>
            </div>
            <p className="risk-note">
              Representação conceitual. Limites e calibração dependem do
              ambiente; o sistema apoia a prevenção e não substitui
              procedimentos de segurança.
            </p>
          </div>
        </section>
        <section id="observe" className="observe section-pad">
          <div className="section-meta">
            <span>03 / Observar</span>
            <span>VÁRIOS PONTOS DE VISTA. UMA OPERAÇÃO.</span>
          </div>
          <h2>
            Veja o todo.
            <br />
            <em>Cuide de cada detalhe.</em>
          </h2>
          <div className="feed-composition">
            <figure className="feed-main reveal-photo">
              <Photo
                name="warehouse"
                alt="Corredor de um armazém com prateleiras de estoque"
              />
              <figcaption>01 — Armazenagem</figcaption>
            </figure>
            <figure className="feed-secondary">
              <Photo
                name="robotics"
                alt="Braços robóticos em uma estação industrial"
              />
              <figcaption>02 — Automação</figcaption>
            </figure>
            <figure className="feed-camera">
              <Photo
                name="camera"
                alt="Câmera de monitoramento instalada na parede"
              />
              <figcaption>03 — Seu ponto de vista</figcaption>
            </figure>
            <p>
              Webcams e câmeras de rede.
              <br />
              Conexões diferentes,
              <br />
              um único lugar para olhar.
            </p>
          </div>
        </section>
        <section className="detect section-pad">
          <div className="detect-photo reveal-photo">
            <Photo
              name="worker"
              alt="Profissional com equipamento de proteção junto a uma máquina"
            />
          </div>
          <div className="detect-copy">
            <span className="section-label">04 / Interpretar</span>
            <h2>
              Não é só ver.
              <br />É <em>entender.</em>
            </h2>
            <p>
              A visão computacional identifica pessoas e máquinas, acompanha a
              proximidade e sinaliza situações que precisam de atenção.
            </p>
            <div className="detect-sequence">
              <span>Imagem</span>
              <Arrow />
              <span>Contexto</span>
              <Arrow />
              <span>Alerta</span>
            </div>
            <small>Da observação à ação, na mesma operação.</small>
          </div>
        </section>
        <section id="system" className="local section-pad">
          <div className="section-meta">
            <span>05 / Permanecer</span>
            <span>INTELIGÊNCIA NA BORDA</span>
          </div>
          <h2>
            Suas câmeras.
            <br />
            <em>Seus dados.</em>
            <br />
            <span className="local-last">Seu espaço.</span>
          </h2>
          <div className="local-bottom">
            <div className="local-flow">
              <span>CÂMERA</span>
              <i aria-hidden="true" />
              <strong>SISTEMA LOCAL</strong>
              <span className="local-boundary">DENTRO DA SUA OPERAÇÃO</span>
            </div>
            <div>
              <p>
                Na instalação local, o processamento acontece no seu computador.
                Os vídeos não precisam sair da empresa para que o risco seja
                analisado.
              </p>
              <small>
                A disponibilidade da análise depende da instalação e dos
                recursos do equipamento. A versão web de demonstração tem
                recursos de IA limitados.
              </small>
            </div>
          </div>
        </section>
        <section className="control section-pad">
          <div className="control-copy">
            <span className="section-label">06 / Controlar</span>
            <h2>
              Acesso certo.
              <br />
              <em>Para cada olhar.</em>
            </h2>
            <p>
              Defina quem administra e quais câmeras cada operador pode
              visualizar.
            </p>
            <div className="role-switch" aria-label="Explorar perfis de acesso">
              <button
                aria-pressed={role === "admin"}
                onClick={() => setRole("admin")}
              >
                Administrador
              </button>
              <button
                aria-pressed={role === "operator"}
                onClick={() => setRole("operator")}
              >
                Operador
              </button>
            </div>
            <small>Exemplo ilustrativo de permissões.</small>
          </div>
          <div className="connections">
            <span className="connection-person">
              {role === "admin" ? "ADMIN" : "OPERADOR"}
            </span>
            <svg
              viewBox="0 0 500 220"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path d="M250 0V90H60V220M250 90V220M250 90H440V220" />
            </svg>
            <div className="camera-nodes">
              {["01", "02", "03"].map((cam, i) => (
                <span
                  key={cam}
                  className={role === "operator" && i === 2 ? "restricted" : ""}
                >
                  <span className="camera-icon" aria-hidden="true" />
                  CAM {cam}
                  <small>
                    {role === "operator" && i === 2 ? "Restrita" : "Autorizada"}
                  </small>
                </span>
              ))}
            </div>
          </div>
        </section>
        <section className="trace section-pad">
          <div>
            <span className="section-label">07 / Registrar</span>
            <h2>
              Cada evento
              <br />
              deixa um <em>rastro.</em>
            </h2>
            <p>
              Uma linha do tempo para consultar, entender e acompanhar sua
              operação.
            </p>
            <small>Sequência ilustrativa de eventos.</small>
          </div>
          <ol className="event-list">
            {[
              ["08:42", "Acesso autorizado", "Administrador"],
              ["08:45", "Câmera conectada", "Área de produção"],
              ["09:11", "Risco identificado", "Aproximação detectada"],
              ["09:11", "Alerta emitido", "Aviso à operação"],
              ["09:12", "Ocorrência consultada", "Histórico de eventos"],
            ].map(([t, title, desc], i) => (
              <li key={i}>
                <time>{t}</time>
                <span>
                  <strong>{title}</strong>
                  <small>{desc}</small>
                </span>
                <span className="event-dot" />
              </li>
            ))}
          </ol>
        </section>
        <section className="product section-pad">
          <div className="section-meta">
            <span>08 / EdgeSecurity</span>
            <span>DA IMAGEM AO CONTROLE</span>
          </div>
          <div className="product-grid">
            <h2>
              Uma visão
              <br />
              <em>mais completa.</em>
            </h2>
            <div className="feature-list">
              {features.map(([title, body], i) => (
                <details key={title} open={i === 0}>
                  <summary>
                    <span>{title}</span>
                    <span className="plus" aria-hidden="true" />
                  </summary>
                  <p>{body}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
        <section id="pricing" className="pricing section-pad">
          <div className="section-meta">
            <span>09 / Começar</span>
            <span>UMA ASSINATURA POR EMPRESA</span>
          </div>
          <div className="pricing-grid">
            <div>
              <h2>
                O próximo passo
                <br />é <em>proteger.</em>
              </h2>
              <p>
                Todos os usuários da sua empresa.
                <br />
                Um único plano mensal.
              </p>
            </div>
            <div className="price-block">
              <div className="price">
                <span>R$</span>149<em>,90</em>
              </div>
              <p>por mês / por empresa</p>
              <Magnet
                disabled={reduced || !desktop}
                padding={15}
                magnetStrength={12}
              >
                <a className="subscribe" href="/pages/cadastro.html">
                  Cadastrar minha empresa <Arrow />
                </a>
              </Magnet>
              <small>
                Crie sua empresa e o administrador primário.
                <br />O acesso é liberado após a confirmação do pagamento.
              </small>
              <p className="installation-note">
                A análise de risco requer instalação local, câmeras e equipamento
                compatível. A demonstração web tem recursos de IA limitados.
              </p>
            </div>
          </div>
        </section>
        <section className="faq section-pad">
          <h2>
            Antes de
            <br />
            <em>começar.</em>
          </h2>
          <div>
            {[
              [
                "Cada pessoa precisa pagar?",
                "Não. A assinatura é por empresa: um pagamento libera o acesso dos usuários, conforme as permissões definidas pelo administrador.",
              ],
              [
                "Onde ficam os vídeos?",
                "Na instalação local, o processamento e a gravação ficam no computador da sua empresa. A implantação e os recursos disponíveis devem ser verificados no ambiente de uso.",
              ],
              [
                "E se a mensalidade atrasar?",
                "O acesso é pausado até a regularização da assinatura. Os registros existentes não são apagados por esse motivo.",
              ],
              [
                "Como minha assinatura é ativada?",
                "Cadastre sua empresa e siga para o pagamento. Assim que o pagamento for confirmado, o acesso dos usuários da empresa será liberado, conforme as permissões definidas pelo administrador.",
              ],
              [
                "Posso acessar pela internet?",
                "Sim. A interface pode ser publicada na web. A análise local depende do computador, das câmeras e da configuração da instalação; a demonstração hospedada não equivale a uma implantação industrial.",
              ],
            ].map(([q, a]) => (
              <details key={q}>
                <summary>
                  {q}
                  <span className="plus" aria-hidden="true" />
                </summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </section>
        <section className="finale">
          <div className="final-photo">
            <Photo
              name="machine"
              alt="Máquinas e estruturas em uma instalação industrial"
            />
          </div>
          <div className="final-content">
            <span>O MESMO OLHAR. UM NOVO COMEÇO.</span>
            <h2>
              A proteção
              <br />
              começa <em>antes.</em>
            </h2>
            <a className="text-link" href="/pages/cadastro.html">
              Dê o próximo passo <Arrow />
            </a>
          </div>
        </section>
      </main>
      <footer className="footer">
        <a className="wordmark" href="#top">
          EDGE<span>SECURITY</span>
        </a>
        <span>Tecnologia a favor de quem faz.</span>
        <a href="/index.html">
          Acessar o sistema <Arrow />
        </a>
        <small>© {new Date().getFullYear()} EdgeSecurity</small>
      </footer>
    </div>
  );
}
