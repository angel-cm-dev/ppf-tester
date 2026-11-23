/* PPF Tester web: el núcleo en Python (Pyodide) corre aquí, fuera del hilo de la interfaz (worker de módulo). */
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/pyodide.mjs";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const MODULOS = ["ppf_format", "sig", "dsp", "modelos", "sonido", "motor", "grooves", "estilos",
  "analisis", "compat", "importar_wav", "demo", "web_api"];
const VERSION = new URL(self.location).searchParams.get("v") || "";

let py = null;
let api = null;

function avisar(texto, pct) { postMessage({ tipo: "progreso", texto, pct }); }

async function iniciar() {
  avisar("Descargando el motor de audio…", 5);
  py = await loadPyodide({ indexURL: PYODIDE });
  avisar("Cargando numpy…", 45);
  await py.loadPackage("numpy");
  avisar("Cargando PPF Tester…", 80);
  py.FS.mkdirTree("/app");
  await Promise.all(MODULOS.map(async (m) => {
    const r = await fetch(`py/${m}.py?v=${VERSION}`);
    if (!r.ok) throw new Error(`No se pudo cargar ${m}.py`);
    py.FS.writeFile(`/app/${m}.py`, await r.text());
  }));
  py.runPython("import sys; sys.path.insert(0, '/app'); import web_api");
  api = py.pyimport("web_api");
  avisar("Listo", 100);
}

const listo = iniciar().catch((e) => { postMessage({ tipo: "fallo", texto: String(e && e.message || e) }); throw e; });

function aBuffer(x) {
  // bytes de Python -> ArrayBuffer transferible
  const u8 = x.toJs ? x.toJs() : x;
  if (x.destroy) x.destroy();
  return u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength);
}

const FUNCIONES = {
  abrir_kit: (datos, nombre) => api.abrir_kit(datos, nombre),
  elegir_voz: (i) => api.elegir_voz(i),
  plan_banco: () => api.plan_banco(),
  render_lote: (pedidos) => {
    const r = api.render_lote(pedidos);
    const meta = r.get(0);
    const data = aBuffer(r.get(1));
    r.destroy();
    return { meta, data, transferir: [data] };
  },
  revisar: () => api.revisar(),
  ritmos: () => api.ritmos(),
  abrir_estilo: (datos, nombre) => api.abrir_estilo(datos, nombre),
  estilo_json: () => api.estilo_json(),
  crear_demo: (opciones) => {
    const data = aBuffer(api.crear_demo(opciones));
    return { data, transferir: [data] };
  },
};

onmessage = async (ev) => {
  const { id, fn, args } = ev.data;
  try {
    await listo;
    const conv = (args || []).map((a) => (a instanceof ArrayBuffer ? new Uint8Array(a) : a));
    let res = FUNCIONES[fn](...conv);
    let transferir = [];
    if (res && res.transferir) { transferir = res.transferir; delete res.transferir; }
    postMessage({ id, ok: true, res }, transferir);
  } catch (e) {
    let msg = String(e && e.message || e);
    // de un error de Python, quedarse con la última línea (el mensaje)
    const lineas = msg.trim().split("\n");
    msg = lineas[lineas.length - 1].replace(/^\w+(Error|Exception): /, "");
    postMessage({ id, ok: false, error: msg });
  }
};
