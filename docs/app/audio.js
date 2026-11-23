/* Audio de la web app: banco de sonidos del kit, golpes con corte de hi-hat y secuenciador de estilos. */
export const SR = 44100;

export class Audio {
  constructor() {
    this.ctx = null;
    this.banco = new Map();   // nota -> {capas:[{desde,hasta,vref,buf,grupo}], db:[128]}
    this.grupos = new Map();  // grupo de corte -> {src, gain}
    this.alGolpe = null;      // (nota, velocidad, cuando) para iluminar pads
  }

  iniciar() {
    if (this.ctx) {
      if (this.ctx.state !== "running") this.ctx.resume();
      return this.ctx;
    }
    // iOS: que suene aunque el interruptor de silencio esté activado
    try { if (navigator.audioSession) navigator.audioSession.type = "playback"; } catch (e) { /* sin soporte */ }
    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = new AC({ latencyHint: "interactive", sampleRate: SR });
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.9;
    // limitador suave para que un estilo con muchos golpes no sature
    this.lim = this.ctx.createDynamicsCompressor();
    this.lim.threshold.value = -3;
    this.lim.knee.value = 3;
    this.lim.ratio.value = 12;
    this.lim.attack.value = 0.002;
    this.lim.release.value = 0.12;
    this.master.connect(this.lim).connect(this.ctx.destination);
    if (this.ctx.state !== "running") this.ctx.resume();
    return this.ctx;
  }

  set volumen(db) { if (this.master) this.master.gain.value = 0.9 * 10 ** (db / 20); }

  limpiar() { this.banco.clear(); this.grupos.clear(); }

  /** plan: [{nota, capas:[[desde,hasta,vref]], db}] · meta: [[nota, vref, inicio, frames, grupo]] · data: Float32 L/R */
  cargarBanco(plan, meta, data) {
    this.iniciar();
    const f32 = new Float32Array(data);
    const bufs = new Map();
    for (const [n, v, ini, frames, g] of meta) {
      const b = this.ctx.createBuffer(2, Math.max(1, frames), SR);
      const L = b.getChannelData(0), R = b.getChannelData(1);
      for (let i = 0, j = ini; i < frames; i++, j += 2) { L[i] = f32[j]; R[i] = f32[j + 1]; }
      bufs.set(`${n}/${v}`, { buf: b, grupo: g });
    }
    this.banco.clear();
    for (const p of plan) {
      const capas = p.capas.map(([desde, hasta, vref]) => ({ desde, hasta, vref, ...bufs.get(`${p.nota}/${vref}`) }))
        .filter((c) => c.buf);
      if (capas.length) this.banco.set(p.nota, { capas, db: p.db });
    }
  }

  get notas() { return [...this.banco.keys()]; }

  /** Toca una nota del kit. cuando = tiempo del AudioContext (0 = ya). */
  golpe(nota, vel, cuando = 0, ganancia = 1) {
    const k = this.banco.get(nota);
    if (!k || !this.ctx) return;
    vel = Math.max(1, Math.min(127, Math.round(vel)));
    const c = k.capas.find((x) => vel >= x.desde && vel <= x.hasta) || k.capas[k.capas.length - 1];
    const t = Math.max(cuando || 0, this.ctx.currentTime);
    const g = this.ctx.createGain();
    g.gain.value = ganancia * 10 ** ((k.db[vel] - k.db[c.vref]) / 20);
    const src = this.ctx.createBufferSource();
    src.buffer = c.buf;
    src.connect(g).connect(this.master);
    if (c.grupo) {
      // corte de hi-hat: el golpe nuevo apaga al anterior del mismo grupo
      const prev = this.grupos.get(c.grupo);
      if (prev && prev.fin > t) {
        try {
          prev.gain.gain.setTargetAtTime(0, t, 0.006);
          prev.src.stop(t + 0.06);
        } catch (e) { /* ya terminó */ }
      }
      this.grupos.set(c.grupo, { src, gain: g, fin: t + c.buf.duration });
    }
    src.start(t);
    if (this.alGolpe) this.alGolpe(nota, vel, t);
  }

  click(acento, cuando) {
    const o = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    o.frequency.value = acento ? 1800 : 1200;
    g.gain.setValueAtTime(acento ? 0.35 : 0.22, cuando);
    g.gain.exponentialRampToValueAtTime(0.0001, cuando + 0.05);
    o.connect(g).connect(this.master);
    o.start(cuando);
    o.stop(cuando + 0.06);
  }
}

/* ------------------------------------------------------------------ secuenciador
 * Toca un estilo como el PSR: Intro -> Main en bucle; Fill al cambiar de Main (Auto Fill) o al pulsar
 * el Main que suena; Break; Ending y parada. Los Fill entran en el siguiente pulso; Intro, Ending y
 * cambios de Main sin Fill, en el siguiente compás. También sirve para los ritmos sencillos.
 */
export function tipo(s) {
  s = s.toLowerCase();
  if (s.startsWith("intro")) return "intro";
  if (s.startsWith("main")) return "main";
  if (s === "fill in ba" || s.startsWith("break")) return "break";
  if (s.startsWith("fill")) return "fill";
  if (s.startsWith("ending")) return "ending";
  return "otro";
}

export class Secuenciador {
  constructor(audio, estilo, { alCambiar } = {}) {
    // estilo: {ppq, compas:[num,den], secciones:{nombre:{largo, eventos:[[tick,nota,vel,canal]]}}, ganancia}
    this.a = audio;
    this.est = estilo;
    this.alCambiar = alCambiar || (() => {});
    this.autofill = true;
    this.metronomo = false;
    this.bpm = estilo.tempo || 100;
    this.main = Object.keys(estilo.secciones).find((s) => tipo(s) === "main") || null;
    this.sec = null;
    this.timer = null;
    this.pedido = null;
    const [num, den] = estilo.compas || [4, 4];
    this.tc = Math.round(estilo.ppq * 4 * num / den);
    this.tp = Math.round(estilo.ppq * 4 / den);
  }

  get sonando() { return this.timer !== null; }
  get spt() { return 60 / Math.max(20, this.bpm) / this.est.ppq; }

  setBpm(b) {
    if (this.sonando) {
      const tCur = this.T0 + this.cur * this.spt;
      this.bpm = b;
      this.T0 = tCur - this.cur * this.spt;
    } else this.bpm = b;
  }

  start(seccion) {
    this.stop(true);
    const ctx = this.a.iniciar();
    if (seccion && tipo(seccion) === "main") this.main = seccion;
    const primera = seccion || this.main;
    if (!this.est.secciones[primera]) return;
    this._entrar(primera, 0, ctx.currentTime + 0.08);
    this.timer = setInterval(() => this._tick(), 25);
    this._tick();
  }

  stop(silencio = false) {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.pedido = null;
    this.sec = null;
    if (!silencio) this.alCambiar(null, 0);
  }

  pedir(s) {
    if (!this.est.secciones[s]) return;
    const t = tipo(s);
    const actual = this.sec ? tipo(this.sec) : "";
    if (t === "main" && (actual === "intro" || actual === "ending")) { this.main = s; return; }
    if (t === "main") {
      let f = `Fill In ${s.slice(-1)}${s.slice(-1)}`;
      if (!this.est.secciones[f] && this.main) f = `Fill In ${this.main.slice(-1)}${s.slice(-1)}`;
      this.pedido = this.autofill && this.est.secciones[f] ? ["pulso", f] : ["compas", s];
      this.main = s;
    } else if (t === "fill" || t === "break") this.pedido = ["pulso", s];
    else this.pedido = ["compas", s];
  }

  _entrar(sec, inicio, cuando) {
    this.sec = sec;
    this.inicio = inicio;
    this.cur = inicio;
    this.T0 = cuando - inicio * this.spt;
    this.salto = null;
    this.alCambiar(sec, cuando);
  }

  _tick() {
    const ctx = this.a.ctx;
    const horizonte = ctx.currentTime + 0.15;
    for (let guarda = 0; guarda < 64 && this.sec; guarda++) {
      const s = this.est.secciones[this.sec];
      if (this.pedido && !this.salto) {
        const [clase, destino] = this.pedido;
        this.pedido = null;
        const paso = clase === "pulso" ? this.tp : this.tc;
        const corte = Math.ceil(this.cur / paso) * paso;
        this.salto = { corte, destino, inicio: clase === "pulso" ? corte % this.tc : 0 };
      }
      const limite = this.salto ? Math.min(this.salto.corte, s.largo) : s.largo;
      const hTick = (horizonte - this.T0) / this.spt;
      const fin = Math.min(limite, hTick);
      if (fin > this.cur) {
        for (const [t, n, v, ch] of s.eventos) {
          if (t >= this.cur && t < fin) this.a.golpe(n, v, this.T0 + t * this.spt, (this.est.ganancia || {})[ch] ?? 1);
        }
        if (this.metronomo) {
          for (let p = Math.ceil(this.cur / this.tp) * this.tp; p < fin; p += this.tp) {
            this.a.click(p % this.tc === 0, this.T0 + p * this.spt);
          }
        }
        this.cur = fin;
      }
      if (this.cur < limite) break;
      // fin de la sección (o corte): ¿qué sigue?
      const cuando = this.T0 + limite * this.spt;
      let sig, ini = 0;
      if (this.salto) { sig = this.salto.destino; ini = this.salto.inicio; }
      else {
        const t = tipo(this.sec);
        sig = t === "main" || t === "otro" ? this.sec : t === "ending" ? null : this.main;
      }
      if (!sig || !this.est.secciones[sig]) {
        const espera = Math.max(0, (cuando - ctx.currentTime) * 1000);
        clearInterval(this.timer);
        this.timer = null;
        this.sec = null;
        setTimeout(() => this.alCambiar(null, cuando), espera);
        return;
      }
      this._entrar(sig, ini, cuando);
    }
  }
}

/** Ritmo sencillo (grooves) como un estilo de una sola sección en bucle. */
export function ritmoComoEstilo(r, bpm) {
  return {
    ppq: r.sub, tempo: bpm, compas: [r.pasos / r.sub, 4],
    secciones: { "Main A": { largo: r.pasos, eventos: r.eventos.map(([st, n, v]) => [st, n, v, 9]) } },
    ganancia: {},
  };
}
