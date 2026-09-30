/* MicroSlats — background animado do painel visual do login.
   Equivalente vanilla ao preset "storm": grade de micro-slatos com
   onda direcional, glint, fog e interação de cursor com trail.
   Tokens EdgeSecurity: primary #3B82F6, glint #06B6D4, bg #120F17.
   Otimizado: DPR limitado, render scale, FPS cap, visibility pause,
   quality tiers, static fallback, cleanup robusto. */
(function () {
  "use strict";
  function hex(h) {
    if (typeof h !== "string") return [0, 0, 0];
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  }
  function mix(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  }

  function detectQualityTier() {
    var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    var isMobile = matchMedia("(max-width: 700px)").matches;
    var isCoarse = matchMedia("(pointer: coarse)").matches;
    var dpr = window.devicePixelRatio || 1;
    var cores = navigator.hardwareConcurrency || 4;
    var mem = navigator.deviceMemory || 4;

    if (reduced) return { tier: "static", dpr: 1, renderScale: 1, fps: 0, interactive: false, trail: 0 };
    if (isMobile || isCoarse || dpr >= 2.5 || cores < 4 || mem < 4) {
      return { tier: "low", dpr: Math.min(dpr, 1.25), renderScale: 0.65, fps: 30, interactive: false, trail: 0.8 };
    }
    if (dpr >= 2 || cores < 8 || mem < 8) {
      return { tier: "medium", dpr: Math.min(dpr, 1.25), renderScale: 0.75, fps: 45, interactive: true, trail: 1.0 };
    }
    return { tier: "high", dpr: Math.min(dpr, 1.25), renderScale: 0.85, fps: 60, interactive: true, trail: 1.4 };
  }

  function init(canvas, o) {
    var ctx = canvas.getContext("2d");
    if (!ctx) return;

    var tier = detectQualityTier();
    if (tier.tier === "static") {
      ctx.fillStyle = o.bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      return;
    }

    var BG = hex(o.bg), PRI = hex(o.primary), GLINT = hex(o.glint);
    var W = 0, H = 0, rW = 0, rH = 0;
    var raf = 0, running = false, t0 = performance.now(), born = 0;
    var trail = [], lastFrameTime = 0;
    var frameInterval = 1000 / tier.fps;
    var pointerThrottle = 0;
    var ctxLossHandler = null;

    var dpr = tier.dpr;
    var renderScale = tier.renderScale;
    var interactive = tier.interactive && o.interactive;
    var trailDur = o.trail * (tier.trail || 1);

    function resize() {
      var r = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: canvas.clientWidth, height: canvas.clientHeight };
      W = Math.max(2, Math.round(r.width));
      H = Math.max(2, Math.round(r.height));
      rW = Math.max(2, Math.round(W * renderScale));
      rH = Math.max(2, Math.round(H * renderScale));
      canvas.width = Math.round(rW * dpr);
      canvas.height = Math.round(rH * dpr);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function onMove(e) {
      var now = performance.now();
      if (now - pointerThrottle < 16) return;
      pointerThrottle = now;
      var r = canvas.getBoundingClientRect();
      trail.push({ x: (e.clientX - r.left) * renderScale, y: (e.clientY - r.top) * renderScale, t: now });
      if (trail.length > 14) trail.shift();
    }

    function energy(x, y, now) {
      var e = 0, R = o.cursorSize * renderScale;
      for (var i = 0; i < trail.length; i++) {
        var p = trail[i], age = (now - p.t) / 1000;
        if (age > trailDur) continue;
        var dx = x - p.x, dy = y - p.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d < R) e = Math.max(e, (1 - d / R) * (1 - age / trailDur));
      }
      return Math.min(1, e * o.cursorStrength);
    }

    function frame(now) {
      if (!running) return;
      if (now - lastFrameTime < frameInterval) {
        raf = requestAnimationFrame(frame);
        return;
      }
      lastFrameTime = now;

      var t = ((now - t0) / 1000) * o.speed;
      var rad = (o.direction * Math.PI) / 180;
      var dx = Math.cos(rad), dy = Math.sin(rad);
      var cw = o.slatWidth * o.scale, ch = o.slatHeight * o.scale, gp = o.gap * o.scale;
      var radius = Math.min(cw, ch) * (o.roundness || 0) * 0.5;
      var intro = Math.min(1, (now - born) / 1200);

      ctx.fillStyle = o.bg;
      ctx.fillRect(0, 0, rW, rH);

      var stepX = cw + gp, stepY = ch + gp;
      for (var y = gp / 2; y < rH; y += stepY) {
        for (var x = gp / 2; x < rW; x += stepX) {
          var ph = (x * dx + y * dy) * 0.018 - t * 2.1;
          var wv = 0.5 + 0.5 * Math.sin(ph);
          var gl = Math.pow(Math.max(0, Math.sin(ph * 2 + 1.3)), 3) * o.glintAmt;
          var cur = interactive ? energy(x, y, now) : 0;
          var b = Math.min(1, 0.17 + wv * 0.5 + gl * 0.45 + cur * 0.6);
          b = Math.max(0, (b - 0.5) * o.contrast + 0.5) * intro;
          var depth = (y / rH) * o.perspective;
          b *= 1 - o.fog * depth * 0.9;
          if (b < 0.02) continue;
          var col = b < 0.6 ? mix(BG, PRI, b / 0.6) : mix(PRI, GLINT, (b - 0.6) / 0.4);
          ctx.fillStyle = "rgb(" + (col[0] | 0) + "," + (col[1] | 0) + "," + (col[2] | 0) + ")";
          var h = ch * (1 + o.stretch * wv);
          if (ctx.roundRect) {
            ctx.roundRect(x, y, cw, h, radius);
            ctx.fill();
          } else {
            var r = radius;
            ctx.beginPath();
            ctx.moveTo(x + r, y);
            ctx.lineTo(x + cw - r, y);
            ctx.quadraticCurveTo(x + cw, y, x + cw, y + r);
            ctx.lineTo(x + cw, y + h - r);
            ctx.quadraticCurveTo(x + cw, y + h, x + cw - r, y + h);
            ctx.lineTo(x + r, y + h);
            ctx.quadraticCurveTo(x, y + h, x, y + h - r);
            ctx.lineTo(x, y + r);
            ctx.quadraticCurveTo(x, y, x + r, y);
            ctx.closePath();
            ctx.fill();
          }
        }
      }
      raf = requestAnimationFrame(frame);
    }

    function start() {
      if (running) return;
      resize();
      born = performance.now();
      running = true;
      lastFrameTime = 0;
      raf = requestAnimationFrame(frame);
    }

    function stop() {
      running = false;
      cancelAnimationFrame(raf);
    }

    function pause() { stop(); }
    function resume() { if (!running) start(); }

    var ro = null;
    if ("ResizeObserver" in window) {
      ro = new ResizeObserver(function () { resize(); });
      ro.observe(canvas.parentElement);
    }

    if (interactive) {
      canvas.parentElement.addEventListener("pointermove", onMove, { passive: true });
    }

    var observer = null;
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) { entry.isIntersecting ? resume() : pause(); });
      }, { rootMargin: "100px" });
      observer.observe(canvas.parentElement);
    }

    document.addEventListener("visibilitychange", function () {
      document.hidden ? pause() : resume();
    });

    window.addEventListener("pagehide", function () {
      stop();
      if (ro) { ro.disconnect(); ro = null; }
      if (observer) { observer.disconnect(); observer = null; }
      if (ctxLossHandler) { canvas.removeEventListener("webglcontextlost", ctxLossHandler); }
    });

    ctxLossHandler = function (e) {
      e.preventDefault();
      stop();
      setTimeout(function () {
        var gl = canvas.getContext("2d");
        if (gl) { ctx = gl; start(); }
      }, 1000);
    };
    canvas.addEventListener("webglcontextlost", ctxLossHandler);

    window.__edgeMicroSlatsStop = stop;

    start();
  }

  var canvases = document.querySelectorAll("canvas[data-micro-slats]");
  canvases.forEach(function (c) {
    if (c.dataset.msInit) return;
    c.dataset.msInit = "1";
    init(c, {
      bg: "#120F17", primary: "#3B82F6", glint: "#06B6D4",
      slatWidth: 10, slatHeight: 25, gap: 3, roundness: 0.75,
      interactive: true, cursorStrength: 1, cursorSize: 40,
      trail: 1.4, scale: 0.55, speed: 1.6, direction: 236,
      stretch: 0.3, glintAmt: 1.3, contrast: 1.8, perspective: 0.8, fog: 0.35
    });
  });
})();