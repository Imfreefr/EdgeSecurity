// Teste funcional do editor visual: extrai o <script> da pagina servida e o
// executa em Node com um DOM minimo. Sem dependencias. Uso: node <este-arquivo>.
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(HERE, "opencode_review_server.py");
const src = fs.readFileSync(SRC, "utf-8");
const m = src.match(/PAGE = """[\s\S]*?<script>\r?\n([\s\S]*?)<\/script>"""/);
if (!m) { console.error("script nao extraido"); process.exit(1); }
const pageJS = m[1];

// ---- DOM minimo ----
const calls = { paint: 0 };
const ctxs = [];
function mkEl() {
  return { innerHTML: "", textContent: "", className: "", value: "", checked: false,
    style: {}, width: 0, height: 0, clientWidth: 800,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }),
    getContext: () => { const p = new Proxy({ _sets: [] }, {
      get: (t, k) => { if (k === "_sets") return t._sets; return (...a) => { calls[k] = (calls[k] || 0) + 1; }; },
      set: (t, k, v) => { t._sets.push([k, v]); return true; } }); ctxs.push(p); return p; },
  };
}
const lastSets = () => ctxs.length ? ctxs[ctxs.length - 1]._sets : [];
const els = {};
global.document = {
  getElementById: (id) => (els[id] ||= mkEl()),
  querySelector: () => ({ clientWidth: 800, style: {} }),
  onkeydown: null,
};
global.Image = class {
  set src(u) {
    this.width = 800; this.height = 600;
    setTimeout(() => (this._fail ? this.onerror?.() : this.onload?.()), 0);
  }
  get naturalWidth() { return this.width; } get naturalHeight() { return this.height; }
};
const posted = [];
const QUEUE = { rows: [
  { id: "a", platform_name: "A", status: "pending_individual_visual_review", width: 800, height: 600,
    boxes: [{ class_id: 0, xc: 0.5, yc: 0.5, w: 0.4, h: 0.4 }], nboxes: 1, amb: [], amb_reasons: {}, amb_resolved: [] },
  { id: "b", platform_name: "B", status: "pending_individual_visual_review", width: 800, height: 600,
    boxes: [], nboxes: 0, amb: [], amb_reasons: {}, amb_resolved: [] },
  { id: "c", platform_name: "C", status: "pending_individual_visual_review", width: 800, height: 600,
    boxes: [{ class_id: 0, xc: 0.5, yc: 0.5, w: 0.4, h: 0.4 },
             { class_id: 0, xc: 0.52, yc: 0.52, w: 0.4, h: 0.4 },
             { class_id: 0, xc: 0.1, yc: 0.1, w: 0.1, h: 0.1 }],
    nboxes: 3, amb: [0, 1], amb_reasons: {}, amb_resolved: [] } ], decided: 0, total: 3 };
global.fetch = async (url, opts) => {
  if (url === "/api/queue") return { json: async () => JSON.parse(JSON.stringify(QUEUE)) };
  if (url === "/api/decide") { posted.push(JSON.parse(opts.body)); return { json: async () => ({ ok: true, kept: 1 }) }; }
  throw new Error("url inesperada " + url);
};

const assert = (c, msg) => { if (!c) { console.error("FALHOU:", msg); process.exit(1); } console.log("ok:", msg); };
// navegadores expoem ids como globals; reproduz aqui (menos 'list', que e funcao)
for (const id of ["c", "q", "boxes", "t", "note", "cov", "msg", "prog", "zi", "f", "dirty"])
  globalThis[id] = document.getElementById(id);
els.f.value = "pending";
// expõe internals p/ inspeção (o script usa let no top-level do eval)
const hook = "\n;globalThis.__T={get DRAW(){return DRAW},get CUR(){return CUR},get SEL(){return SEL},set SEL(v){SEL=v},get DIRTY(){return DIRTY},get AMB(){return AMB},openImg,save,form,paint,setBox,boxAt,cornerAt,markDirty,list,computeAmb,resolveAmb,reopenAmb,ambOf,reasonOf,liveResolved};";
eval(pageJS + hook);
const T = globalThis.__T;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await sleep(30);

assert(T.CUR?.id === "a", "abre primeira pendente sozinho");
assert(els.boxes.innerHTML.includes("empilhadeira"), "seletor mostra nomes legiveis");
assert(!els.boxes.innerHTML.includes('class="box ') || !/class="box[^"]*" onclick/.test(els.boxes.innerHTML),
  "sem onclick no container (causa dos controles mortos)");

// 1. selecionar clicando na caixa (centro 400,300 -> 0.5,0.5)
els.c.onmousedown({ button: 0, clientX: 400, clientY: 300 });
assert(T.SEL === 0, "clique na imagem seleciona a caixa");
// 2. arrastar p/ mover (+80px,+60px -> +0.1,+0.1)
els.c.onmousemove({ clientX: 480, clientY: 360 });
els.c.onmouseup({ clientX: 480, clientY: 360 });
assert(Math.abs(T.DRAW[0].xc - 0.6) < 1e-9 && Math.abs(T.DRAW[0].yc - 0.6) < 1e-9, "drag move a caixa");
assert(els.dirty.style.display === "inline", "badge nao-salvo aparece");
// 3. redimensionar pela alca SE (caixa agora 0.4..0.8 x 0.4..0.8; canto SE=640,480)
els.c.onmousedown({ button: 0, clientX: 640, clientY: 480 });
els.c.onmousemove({ clientX: 680, clientY: 520 });
els.c.onmouseup({ clientX: 680, clientY: 520 });
assert(T.DRAW[0].w > 0.4 && T.DRAW[0].h > 0.4, "alca redimensiona");
assert(T.DRAW[0].xc <= 1 - T.DRAW[0].w / 2 + 1e-9, "integridade YOLO contida");
// 4. setBox com classe legivel + clamp
T.setBox(0, "class_id", 3);
assert(T.DRAW[0].class_id === 3, "classe 3 via seletor");
T.setBox(0, "w", 99);
assert(T.DRAW[0].w === 1 && T.DRAW[0].xc === 0.5, "clamp de largura/centro");
T.setBox(0, "class_id", 9);
assert(T.DRAW[0].class_id === 3, "classe invalida rejeitada");
// 5. salvar -> POST + avanca p/ proxima pendente
els.note.value = "teste"; els.cov = { checked: true };
await T.save();
assert(posted.length === 1 && posted[0].image_id === "a", "decisao postada");
assert(posted[0].boxes.every((b) => [0, 1, 2, 3].includes(b.class_id)), "só classes 0..3 no POST");
await sleep(30); // onload da proxima imagem e assincrono
assert(T.CUR.id === "b", "avanca para proxima pendente apos salvar");
assert(els.dirty.style.display === "none", "badge limpa apos salvar");
// 6. clique no vazio adiciona caixa
els.c.onmousedown({ button: 0, clientX: 100, clientY: 100 });
els.c.onmouseup({ button: 0, clientX: 100, clientY: 100 });
assert(T.DRAW.length === 1 && T.DRAW[0].approved === true, "clique no vazio adiciona");
// 7. duas caixas mesma classe: uma ambigua (vermelha) e outra nao (verde)
T.openImg("c");
await sleep(30);
assert(T.AMB.idx.length === 2, "par sobreposto detectado ao vivo");
const styles = lastSets().filter(([k]) => k === "strokeStyle").map(([, v]) => v);
assert(styles.includes("#ff0000"), "ambigua em vermelho");
assert(styles.includes("#00ff70"), "nao-ambigua mesma classe em verde");
assert(els.boxes.innerHTML.includes("duplicata (mesma classe"), "motivo exibido");
// 8. resolver exige justificativa; com nota, persiste no POST
els.ambnote0 = { value: "" };
T.resolveAmb(0);
assert(T.CUR.amb_resolved.length === 0, "sem nota nao resolve");
els.ambnote0 = { value: "duplicata real, mantida a maior" };
T.resolveAmb(0);
assert(T.CUR.amb_resolved.length === 1, "resolucao registrada");
assert(els.boxes.innerHTML.includes("amb. resolvida"), "tag de resolvida");
// 9. trocar classe NAO resolve sozinho: par muda -> resolucao orfa descartada com aviso
T.setBox(1, "class_id", 1);
assert(T.CUR.amb_resolved.length === 1, "troca de classe nao apaga registro");
els.note.value = "t";
await T.save();
await sleep(30);
const last = posted[posted.length - 1];
assert(last.image_id === "c" && last.amb_resolutions.length === 0, "orfa descartada no save");
assert(els.msg.textContent.includes("órfã"), "aviso de orfa");
console.log("EDITOR OK");
