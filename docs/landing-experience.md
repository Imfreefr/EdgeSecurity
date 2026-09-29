# EdgeSecurity — Antes do impacto

## Scope and architecture

The landing is a separate React entry at `/landing.html`. The login remains
`/index.html`; signup, payment and internal tools retain their HTML/JS entrypoints.
Vite builds only the landing and copies the internal files without transforming
them. Vercel serves `dist` and retains the existing Python API rewrite.

All landing selectors are under `.edge-landing`. Fonts are self-hosted. No
Tailwind, Preflight, shared providers or global React application were introduced.
Mount-time body/html changes are restored during cleanup. GSAP uses a scoped
context, Lenis removes its ticker and destroys its instance, and the dynamically
loaded Three scene disposes geometries, materials, renderer, observers and RAF.

Development: `npm ci`, then `npm run dev`, then open `/landing.html`.
Production: `npm run build`. `python serve.py` serves the compiled landing and
live internal sources, preserving the existing Python entrypoint. Rebuild after
editing landing sources. Internal pages do not require a Node runtime.

## Audit and regression findings

- Before this change, commit `9b736f1` replaced `css/landing.css`, removing
  `.cad-*`, `.pay-*`, `.admin-*` and `.lp-*` styles still imported by three pages.
- Recovered the stylesheet from `9b736f1^` into `css/legacy-public.css` and
  updated only the three dependent stylesheet links. The obsolete landing CSS
  was removed. Internal scripts, authentication and payment logic are unchanged.
- The older payment header used an unbounded direct logo image. The legacy
  stylesheet now sizes it and lays out the header correctly, including mobile.
- The original landing's permanent HUD, cyan/black palette, outline typography,
  generic rotating eye and repeated image competed with the product explanation.
  The replacement uses an industrial editorial composition and a spatial risk
  demonstration. The technological overlay is confined to that demonstration.

## Visual and motion decisions

Reference: [Casa di Solare](https://casadisolare.com/), studied for typographic
hierarchy, pacing and transitions, without copying its imagery or identity.
The brief delegates art direction: an industrial photographic essay, off-white
paper, charcoal ink, muted sage for the local-processing passage and restrained
semantic accents. Manrope contrasts with Instrument Serif and its italic.

The Impeccable passes covered audit/critique, bolder, animate, distill and polish.
The direction preserves the brief over unrelated concept-seed challengers.
The bolder pass makes typography asymmetric and photography bleed beyond the
column; distill removes ambient HUD, decorative particles and generic cards.
The detector reports only Instrument Serif as an overused font; this choice is
explicitly grounded in the user's requested serif/grotesk pairing.

Five authored moments:

1. Masked, staggered headline settles into the photographic opening.
2. Manifesto changes scale and alignment; its final word is revealed by scroll.
3. Desktop scroll pins a spatial person/machine scene and reduces the distance.
4. Bounding volumes, distance and semantic states explain computer vision.
5. The closing photograph expands from an inset while the opening idea returns.

Other passages vary the rhythm: overlapping camera perspectives, quiet local
processing, interactive camera permissions, event chronology, product details,
one existing subscription price and native FAQ accordions.

Mobile uses its own layout, a manual risk slider, no pinning, no smooth scroll and
no WebGL. Reduced motion disables spatial choreography and preserves content,
controls and the diagram. WebGL failures fall back to the diagram. No audio plays.
Illustrative distances, permission mappings and event data are labeled as such.

## Dependencies and provenance

Runtime: React, React DOM, GSAP/ScrollTrigger, Lenis and Three.js. Build: Vite.
Verification: Playwright. Three is imported only near the risk passage on desktop.
React Bits: **Magnet** only, adapted to Vite's JSX runtime and disabled on mobile
and reduced motion; original license retained in `src/landing/LICENSE.md`.
No R3F/Drei were added because this single demand-rendered scene uses Three directly.

Photo origins and font licenses are in `assets/landing/`. Photos are locally
served WebP, not runtime requests to a stock service. There are no generated
images, testimonials, invented customers, extra plans or invented performance metrics.

## Verification

`npm test` runs the browser checks against `EDGE_TEST_URL` (default port 5174).
It uses installed Microsoft Edge by default; `EDGE_BROWSER=chrome` selects Chrome.
The matrix is 1920×1080, 1440×900, 768×1024 and 390×844. Tests cover navigation,
keyboard menu dismissal/focus return, scroll narrative, risk states, vision toggle,
permissions, FAQ, local assets, reduced motion and no horizontal landing overflow.
Signup, login, payment and dashboard receive desktop/mobile screenshots. API
responses are intercepted with explicit fixtures; no accounts or charges are made.
This validates the browser integration, not a live payment gateway or real cameras.
Screenshots and detailed test output stay in the ignored `.impeccable/review/`.

`node tests/internal-flows.mjs` additionally exercises signup → payment → login
→ dashboard against intercepted responses, then opens cameras, users, alerts,
reports, activities, settings and administration. This passed at 1440 and 390px.
The production bundle also passed a browser smoke test both from `dist` and
through `serve.py`, including the local CSP and deferred WebGL import.

## Existing local work

Pre-existing edits in `js/admin.js`, `js/ai-local.js`, and `js/ai-worker.js` are
outside this change. They must remain unstaged and must not enter the landing commit.
