/* PPF Tester · web app para el móvil (iOS, Android y PC). */
import { Audio, Secuenciador, ritmoComoEstilo, tipo } from "./audio.js?v=1";

const VERSION = "1";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const audio = new Audio();

/* ------------------------------------------------------------------ Python en un worker */
const worker = new Worker(`worker.js?v=${VERSION}`, { type: "module" });
let sigId = 0;
const pendientes = new Map();
let motorListo = false;
let ultimoProgreso = { texto: "Preparando…", pct: 0 };
worker.onmessage = (ev) => {
  const m = ev.data;
  if (m.tipo === "progreso") {
    ultimoProgreso = m;
    if (m.pct >= 100) motorListo = true;
    if (!$("#carga").hidden) progreso(m.texto, m.pct);
    return;
  }
  if (m.tipo === "fallo") {
    toast("No se pudo cargar el motor: " + m.texto + ". Revisa la conexión y recarga.", "ERROR", 8000);
    for (const p of pendientes.values()) p.rej(new Error(m.texto));
    pendientes.clear();
    return;
  }
  const p = pendientes.get(m.id);
  if (!p) return;
  pendientes.delete(m.id);
  m.ok ? p.res(m.res) : p.rej(new Error(m.error));
};
function py(fn, ...args) {
  const transfer = args.filter((a) => a instanceof ArrayBuffer);
  return new Promise((res, rej) => {
    const id = ++sigId;
    pendientes.set(id, { res, rej });
    worker.postMessage({ id, fn, args }, transfer);
  });
}

/* ------------------------------------------------------------------ utilidades de interfaz */
let tToast = 0;
function toast(msg, kind = "OK", ms = 3200) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast ver " + kind;
  clearTimeout(tToast);
  tToast = setTimeout(() => (t.className = "toast"), ms);
}
function progreso(texto, pct) {
  $("#carga-t").textContent = texto;
  $("#carga-p").style.width = Math.max(3, pct || 0) + "%";
}
async function conCarga(texto, fn) {
  const c = $("#carga");
  c.hidden = false;
  $("#carga-n").hidden = motorListo;
  progreso(motorListo ? texto : ultimoProgreso.texto, motorListo ? 60 : ultimoProgreso.pct);
  try {
    if (!motorListo) {
      await new Promise((ok) => {
        const iv = setInterval(() => { if (motorListo) { clearInterval(iv); ok(); } }, 100);
      });
      progreso(texto, 60);
    }
    return await fn();
  } finally {
    c.hidden = true;
  }
}
const icono = (n) => `<svg><use href="#i-${n}"/></svg>`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/* ------------------------------------------------------------------ pestañas */
function ir(v) {
  $$(".vista").forEach((x) => x.classList.toggle("activa", x.id === "v-" + v));
  $$(".tabs button").forEach((b) => b.classList.toggle("activa", b.dataset.v === v));
}
$$(".tabs button").forEach((b) => b.addEventListener("click", () => { audio.iniciar(); ir(b.dataset.v); }));

/* ------------------------------------------------------------------ kit */
let kit = null;
let ritmos = {};
const abrirKit = () => { audio.iniciar(); $("#f-ppf").click(); };
$("#b-abrir").addEventListener("click", abrirKit);
$("#b-abrir2").addEventListener("click", abrirKit);
$("#f-ppf").addEventListener("change", (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (f) abrirArchivoKit(f);
});
async function abrirArchivoKit(f) {
  try {
    await conCarga("Abriendo " + f.name + "…", async () => {
      const info = JSON.parse(await py("abrir_kit", await f.arrayBuffer(), f.name));
      await cargarVoz(info);
    });
    toast(`«${kit.nombre}» listo para tocar`);
    ir("pads");
  } catch (err) {
    toast(err.message, "ERROR", 6000);
  }
}

async function cargarVoz(info) {
  pararTodo();
  kit = info;
  progreso("Preparando los sonidos como en el PSR…", 70);
  const plan = JSON.parse(await py("plan_banco"));
  const pedidos = plan.flatMap((p) => p.capas.map((c) => [p.nota, c[2]]));
  const r = await py("render_lote", JSON.stringify(pedidos));
  audio.cargarBanco(plan, JSON.parse(r.meta), r.data);
  progreso("Revisando el kit…", 90);
  const [rev, rit] = await Promise.all([py("revisar"), py("ritmos")]);
  ritmos = JSON.parse(rit);
  pintarKit(JSON.parse(rev));
  pintarPads();
  pintarRitmos();
  if (estilo) {
    estilo = JSON.parse(await py("estilo_json"));
    pintarEstilo();
  }
}

function pintarKit(rev) {
  $("#kitnom").textContent = kit.nombre;
  $("#kit-vacio").hidden = true;
  $("#kit-info").hidden = false;
  $("#k-muestras").textContent = kit.muestras;
  $("#k-mb").textContent = kit.mb.toFixed(1) + " MB";
  $("#k-notas").textContent = kit.notas.length;
  const sel = $("#sel-voz");
  $("#fila-voz").hidden = kit.voces.length < 2;
  sel.innerHTML = kit.voces.map((v, i) => `<option value="${i}" ${i === kit.voz ? "selected" : ""}>${esc(v)}</option>`).join("");
  const ico = { OK: "check", AVISO: "alert", ERROR: "alert", INFO: "check" };
  $("#k-compat").innerHTML = rev.compat.map((c) => `<div class="item ${c.estado}">${icono(ico[c.estado] || "check")}
    <div><b>${esc(c.modelo)}</b><div class="det">${esc(c.resumen)}${c.detalles.length ? "<br>" + c.detalles.map(esc).join("<br>") : ""}</div></div></div>`).join("");
  $("#k-problemas").innerHTML = rev.problemas.length
    ? rev.problemas.map((p) => `<div class="item ${p.nivel}">${icono(ico[p.nivel] || "alert")}<div>${esc(p.texto)}</div></div>`).join("")
    : `<div class="item OK">${icono("check")}<div>Sin problemas: el kit está en buen estado.</div></div>`;
}
$("#sel-voz").addEventListener("change", async (e) => {
  try {
    await conCarga("Cambiando de voz…", async () => cargarVoz(JSON.parse(await py("elegir_voz", +e.target.value))));
  } catch (err) { toast(err.message, "ERROR"); }
});

/* ------------------------------------------------------------------ pads */
const pads = new Map();
function pintarPads() {
  const g = $("#pads");
  g.innerHTML = "";
  pads.clear();
  for (const n of kit.notas.slice(0, 48)) {
    if (!audio.banco.has(n.nota)) continue;
    const d = document.createElement("div");
    d.className = "pad";
    d.innerHTML = `<b>${esc(n.nombre)}</b><span>${esc(n.tecla)}</span>`;
    d.title = n.muestra || "";
    d.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      audio.iniciar();
      const r = d.getBoundingClientRect();
      const frac = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
      audio.golpe(n.nota, 35 + frac * 92);
    });
    g.appendChild(d);
    pads.set(n.nota, d);
  }
  const cols = pads.size > 24 ? 6 : 4;
  g.style.setProperty("--cols", innerWidth >= 600 ? Math.max(cols, 6) : cols);
}
audio.alGolpe = (nota, vel, cuando) => {
  const d = pads.get(nota);
  if (!d) return;
  const espera = Math.max(0, (cuando - audio.ctx.currentTime) * 1000);
  setTimeout(() => {
    d.classList.add("golpe");
    d.style.setProperty("--brillo", (0.35 + 0.6 * vel / 127).toFixed(2));
    requestAnimationFrame(() => { d.classList.remove("golpe"); d.style.setProperty("--brillo", 0); });
  }, espera);
};

let secRitmo = null;
function pintarRitmos() {
  const sel = $("#sel-ritmo");
  const prev = sel.value;
  sel.innerHTML = Object.keys(ritmos).map((r) => `<option>${esc(r)}</option>`).join("");
  if (prev && ritmos[prev]) sel.value = prev;
  $("#d-ritmos").innerHTML = ["Worship 4/4 (toms)", "Balada 4/4", "Worship 6/8", "Pop 4/4"].filter((r) => ritmos[r])
    .map((r, i) => `<label class="chk"><input type="checkbox" data-r="${esc(r)}" ${i < 2 && !estilo ? "checked" : ""}><span>Ritmo: ${esc(r)}</span></label>`).join("");
}
function botonRitmo(on) {
  $("#b-ritmo").innerHTML = on ? `${icono("stop")}<span>Parar</span>` : `${icono("play")}<span>Ritmo</span>`;
}
$("#b-ritmo").addEventListener("click", () => {
  if (!kit) return toast("Abre un kit primero.", "AVISO");
  if (secRitmo && secRitmo.sonando) { secRitmo.stop(); secRitmo = null; botonRitmo(false); return; }
  pararEstilo();
  const r = ritmos[$("#sel-ritmo").value];
  const bpm = +$("#bpm-ritmo").value || 76;
  secRitmo = new Secuenciador(audio, ritmoComoEstilo(r, bpm));
  secRitmo.start("Main A");
  botonRitmo(true);
});
$("#bpm-ritmo").addEventListener("change", (e) => secRitmo && secRitmo.setBpm(+e.target.value || 76));
$("#sel-ritmo").addEventListener("change", () => {
  if (secRitmo && secRitmo.sonando) { secRitmo.stop(); secRitmo = null; $("#b-ritmo").click(); }
});

/* MIDI (Android con Chrome y PC; en iPhone el navegador no lo permite) */
if (navigator.requestMIDIAccess) {
  const b = $("#b-midi");
  b.hidden = false;
  let acceso = null;
  b.addEventListener("click", async () => {
    try {
      audio.iniciar();
      acceso = acceso || await navigator.requestMIDIAccess();
      const entradas = [...acceso.inputs.values()];
      if (!entradas.length) return toast("Conecta el teclado por USB y vuelve a pulsar.", "AVISO");
      for (const i of entradas) {
        i.onmidimessage = (m) => {
          const [st, n, v] = m.data;
          if ((st & 0xf0) === 0x90 && v > 0) audio.golpe(n, v);
        };
      }
      b.classList.add("prim");
      toast("MIDI: " + entradas.map((i) => i.name).join(", "));
    } catch (e) { toast("El navegador no dio acceso al MIDI.", "AVISO"); }
  });
}

/* ------------------------------------------------------------------ estilos */
let estilo = null;
let sec = null;
let introSel = null;
let mainSel = null;
const GRUPOS = {
  Intro: ["Intro A", "Intro B", "Intro C", "Intro D"],
  Main: ["Main A", "Main B", "Main C", "Main D"],
  Fill: ["Fill In AA", "Fill In BB", "Fill In CC", "Fill In DD", "Fill In BA"],
  Ending: ["Ending A", "Ending B", "Ending C", "Ending D"],
};
const OPCIONALES = new Set(["Intro D", "Ending D"]);
for (const [g, lista] of Object.entries(GRUPOS)) {
  const caja = $(`.botones[data-g="${g}"]`);
  if (g === "Fill") caja.style.gridTemplateColumns = "repeat(5,1fr)";
  for (const s of lista) {
    const b = document.createElement("button");
    b.className = "sb";
    b.dataset.s = s;
    b.disabled = true;
    b.innerHTML = s === "Fill In BA" ? "<small>Break</small>⏸" : s.startsWith("Fill") ? `<small>Fill</small>${s.slice(-1)}` : s.slice(-1);
    if (OPCIONALES.has(s)) b.hidden = true;
    b.addEventListener("click", () => botonEstilo(s));
    caja.appendChild(b);
  }
}
$("#b-sty").addEventListener("click", () => {
  if (!kit) return toast("Abre primero un kit: el estilo se toca con él.", "AVISO");
  $("#f-sty").click();
});
$("#f-sty").addEventListener("change", (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (f) abrirArchivoEstilo(f);
});
async function abrirArchivoEstilo(f) {
  try {
    await conCarga("Leyendo el estilo…", async () => {
      estilo = JSON.parse(await py("abrir_estilo", await f.arrayBuffer(), f.name));
    });
    pararEstilo();
    introSel = null;
    mainSel = estilo.orden.find((s) => tipo(s) === "main") || null;
    $("#e-tempo").value = Math.round(estilo.tempo);
    pintarEstilo();
    pintarRitmos();
    toast(`Estilo «${estilo.nombre}» cargado`);
  } catch (err) { toast(err.message, "ERROR", 6000); }
}

function pintarEstilo() {
  if (!estilo) return;
  const [num, den] = estilo.compas;
  $("#e-nombre").textContent = estilo.nombre;
  $("#e-datos").textContent = `${estilo.tempo} BPM · ${num}/${den} · ${estilo.orden.length} secciones`;
  const f = estilo.faltan;
  const box = $("#e-falta");
  box.hidden = !f;
  if (f && f.lista.length) {
    box.className = "falta";
    box.innerHTML = `<b>Al kit le faltan ${f.lista.length} sonidos del estilo</b> (${f.pct} % de los golpes): ` +
      f.lista.slice(0, 10).map(([n, c]) => `${esc(n)} (${c})`).join(", ") + (f.lista.length > 10 ? "…" : "");
  } else if (f) {
    box.className = "falta ok";
    box.textContent = "El kit tiene todos los sonidos que usa el estilo.";
  }
  $("#e-tempo-v").textContent = $("#e-tempo").value;
  $("#b-start").disabled = !mainSel;
  $("#d-sty").disabled = false;
  $("#d-sty").checked = true;
  $("#d-sty-t").textContent = `Estilo «${estilo.nombre}»: Intro, cada Main con su Fill y Ending`;
  for (const b of $$(".sb")) {
    const s = b.dataset.s;
    const hay = !!estilo.secciones[s];
    b.disabled = !hay;
    if (OPCIONALES.has(s)) b.hidden = !hay;
    b.title = hay ? `${s} · ${estilo.secciones[s].compases} comp.` : `${s}: este estilo no la tiene`;
  }
  pintarBotones();
}

function pintarBotones(actual = sec && sec.sec) {
  const main = (sec && sec.sonando && sec.main) || mainSel;
  for (const b of $$(".sb")) {
    const s = b.dataset.s;
    b.classList.toggle("on", s === actual);
    b.classList.toggle("sel", s !== actual && (s === main || s === introSel));
  }
  const nombre = actual ? (actual === "Fill In BA" ? "Break" : actual.startsWith("Fill") ? "Fill " + actual.slice(-1) : actual) : "";
  $("#e-ahora").textContent = nombre;
}

function botonStart(on) {
  $("#b-start").innerHTML = on ? `${icono("stop")}<span>Stop</span>` : `${icono("play")}<span>Start</span>`;
}

function empezar(seccion) {
  if (!estilo || !kit) return;
  if (secRitmo) { secRitmo.stop(); secRitmo = null; botonRitmo(false); }
  if (sec) sec.stop(true);
  sec = new Secuenciador(audio, estilo, {
    alCambiar: (s, cuando) => {
      const espera = Math.max(0, ((cuando || 0) - audio.ctx.currentTime) * 1000);
      setTimeout(() => {
        if (s === null) {
          if (sec && !sec.sonando) { if (sec.main) mainSel = sec.main; botonStart(false); }
          pintarBotones(null);
        } else pintarBotones(s);
      }, espera);
    },
  });
  sec.autofill = $("#chk-fill").checked;
  sec.metronomo = $("#chk-metro").checked;
  sec.bpm = +$("#e-tempo").value;
  if (mainSel) sec.main = mainSel;
  if (["ending", "break", "fill"].includes(tipo(seccion))) sec.main = null;   // suelto: no sigue con un Main
  sec.start(seccion);
  introSel = null;
  botonStart(true);
}

function pararEstilo() {
  if (sec) {
    if (sec.main) mainSel = sec.main;
    sec.stop(true);
    sec = null;
  }
  botonStart(false);
  pintarBotones(null);
}
function pararTodo() {
  pararEstilo();
  if (secRitmo) { secRitmo.stop(); secRitmo = null; botonRitmo(false); }
}

function botonEstilo(s) {
  audio.iniciar();
  const t = tipo(s);
  if (sec && sec.sonando && sec.main !== null) { sec.pedir(s); pintarBotones(); return; }
  if (t === "intro") introSel = introSel === s ? null : s;
  else if (t === "main") mainSel = s;
  else { empezar(s); return; }      // Fill, Break o Ending sueltos para escucharlos
  pintarBotones();
}
$("#b-start").addEventListener("click", () => {
  audio.iniciar();
  if (sec && sec.sonando) pararEstilo();
  else empezar(introSel || mainSel);
});
$("#chk-fill").addEventListener("change", (e) => { if (sec) sec.autofill = e.target.checked; });
$("#chk-metro").addEventListener("change", (e) => { if (sec) sec.metronomo = e.target.checked; });
$("#e-tempo").addEventListener("input", (e) => {
  $("#e-tempo-v").textContent = e.target.value;
  if (sec) sec.setBpm(+e.target.value);
});

/* ------------------------------------------------------------------ demo */
$("#b-demo").addEventListener("click", async () => {
  if (!kit) return toast("Abre un kit primero.", "AVISO");
  const opciones = {
    recorrido: $("#d-rec").checked,
    estilo: $("#d-sty").checked && !!estilo,
    ritmos: $$("#d-ritmos input:checked").map((i) => i.dataset.r),
    bpm: +$("#d-bpm").value || 76,
    compases: 4,
    bpm_estilo: estilo ? +$("#e-tempo").value : null,
  };
  if (!opciones.recorrido && !opciones.estilo && !opciones.ritmos.length) return toast("Elige al menos el recorrido, el estilo o un ritmo.", "AVISO");
  try {
    const r = await conCarga("Creando la demo… (puede tardar un poco)", () => py("crear_demo", JSON.stringify(opciones)));
    const nombre = `${kit.nombre.replace(/[^\w\- ]+/g, "").trim() || "kit"}_demo.wav`;
    const archivo = new File([r.data], nombre, { type: "audio/wav" });
    const url = URL.createObjectURL(archivo);
    const seg = Math.round((r.data.byteLength - 44) / 4 / 44100);
    $("#d-res").innerHTML = `<audio controls src="${url}" style="width:100%"></audio>
      <p>${seg} s · ${(r.data.byteLength / 1e6).toFixed(1)} MB · <a href="${url}" download="${esc(nombre)}">${icono("download")} Descargar</a></p>`;
    if (navigator.canShare && navigator.canShare({ files: [archivo] })) {
      const b = document.createElement("button");
      b.className = "b prim grande";
      b.style.width = "100%";
      b.innerHTML = `${icono("share")}<span>Compartir (WhatsApp…)</span>`;
      b.addEventListener("click", () => navigator.share({ files: [archivo], title: kit.nombre }).catch(() => {}));
      $("#d-res").appendChild(b);
    }
  } catch (err) { toast(err.message, "ERROR", 6000); }
});

/* Abrir archivos también arrastrándolos (PC) */
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  for (const f of e.dataTransfer.files) {
    if (/\.ppf$/i.test(f.name)) abrirArchivoKit(f);
    else if (/\.(sty|prs|sst|bcs|pcs|fps)$/i.test(f.name)) kit ? abrirArchivoEstilo(f) : toast("Abre primero un kit.", "AVISO");
  }
});
window.ppfTester = { abrirArchivoKit, abrirArchivoEstilo, audio, estado: () => ({ kit, estilo, sec }) };

/* ------------------------------------------------------------------ instalación (PWA) */
if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register(`sw.js?v=${VERSION}`).catch(() => {});
}
document.addEventListener("visibilitychange", () => { if (document.hidden) pararTodo(); });
