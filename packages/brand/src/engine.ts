// Tiny Web Audio synth. Every Sasu sound is generated here — no audio files to ship
// or license. One shared context, master volume, stereo pan that follows the robot,
// a generated stereo plate reverb and a soft limiter.

type Graph = {
  ctx: AudioContext;
  master: GainNode;
  pan: StereoPannerNode;
  dry: GainNode;
  wet: GainNode;
};

export type ToneOpts = {
  type?: OscillatorType;
  gain?: number;
  attack?: number;
  release?: number;
  /** Slide the pitch to this frequency over the tone. */
  glideTo?: number;
  /** Low-pass cutoff in Hz, softens square/saw waves. */
  cutoff?: number;
  /** 0–1 reverb send. */
  space?: number;
  detune?: number;
  /** Wobble: rate in Hz, depth in cents. Cartoon voices live here. */
  vibrato?: { rate: number; depth: number };
};

export type BellOpts = {
  gain?: number;
  /** Modulator / carrier frequency ratio. Non-integer ratios sound metallic (bells). */
  ratio?: number;
  /** FM depth at the strike; decays to `index * 0.1`. */
  index?: number;
  decay?: number;
  space?: number;
};

let graph: Graph | null = null;
let volume = 0.6;
let panValue = 0;

/** Stereo plate: early reflections + dense decaying noise, slightly different per side. */
function plate(ctx: AudioContext, seconds: number): AudioBuffer {
  const len = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const data = buf.getChannelData(ch);
    const taps = [0.011, 0.019, 0.027, 0.041].map((t) => Math.floor((t + ch * 0.003) * ctx.sampleRate));
    for (const [i, t] of taps.entries()) if (t < len) data[t] = (i % 2 ? -0.5 : 0.6) / (i + 1);
    for (let i = 0; i < len; i++) {
      const env = Math.exp((-5.5 * i) / len);
      data[i] = (data[i] ?? 0) + (Math.random() * 2 - 1) * env * 0.5;
    }
  }
  return buf;
}

/** Gentle tanh curve: catches stacked cues without audible clipping. */
function softClip(): Float32Array<ArrayBuffer> {
  const n = 1024;
  const curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1;
    curve[i] = Math.tanh(1.4 * x) / Math.tanh(1.4);
  }
  return curve;
}

function get(): Graph | null {
  if (graph) return graph;
  if (typeof AudioContext === "undefined") return null;
  const ctx = new AudioContext({ latencyHint: "interactive" });

  const limiter = ctx.createWaveShaper();
  limiter.curve = softClip();
  limiter.oversample = "4x";
  const master = ctx.createGain();
  master.gain.value = volume;
  const pan = ctx.createStereoPanner();
  pan.pan.value = panValue;
  pan.connect(master).connect(limiter).connect(ctx.destination);

  const dry = ctx.createGain();
  dry.connect(pan);
  const reverb = ctx.createConvolver();
  reverb.buffer = plate(ctx, 1.6);
  const tone = ctx.createBiquadFilter(); // darken the tail
  tone.type = "lowpass";
  tone.frequency.value = 6500;
  const wet = ctx.createGain();
  wet.gain.value = 0.9;
  wet.connect(reverb).connect(tone).connect(pan);

  graph = { ctx, master, pan, dry, wet };
  return graph;
}

/** Browsers (and WKWebView) start audio suspended until a user gesture. */
export function unlock() {
  const g = get();
  if (g && g.ctx.state === "suspended") void g.ctx.resume();
}

export function setVolume(v: number) {
  volume = Math.max(0, Math.min(1, v));
  const g = graph;
  if (g) g.master.gain.setTargetAtTime(volume, g.ctx.currentTime, 0.02);
}

/** -1 (left) … 1 (right). Sasu's sounds come from where the robot sits on screen. */
export function setPan(p: number) {
  panValue = Math.max(-1, Math.min(1, p));
  const g = graph;
  if (g) g.pan.pan.setTargetAtTime(panValue, g.ctx.currentTime, 0.05);
}

/** Robot x position (0 = left edge, 1 = right edge) → a gentle pan that never hard-pans. */
export function panFromScreenX(fraction: number): number {
  const f = Math.max(0, Math.min(1, fraction));
  return Math.round((f * 2 - 1) * 0.7 * 100) / 100;
}

function connectOut(g: Graph, node: AudioNode, space = 0) {
  node.connect(g.dry);
  if (space > 0) {
    const send = g.ctx.createGain();
    send.gain.value = space;
    node.connect(send).connect(g.wet);
  }
}

/** Schedule one enveloped tone `at` seconds from now. */
export function tone(freq: number, at: number, dur: number, o: ToneOpts = {}) {
  const g = get();
  if (!g) return;
  const { ctx } = g;
  const t0 = ctx.currentTime + 0.005 + at;
  const peak = o.gain ?? 0.3;
  const attack = o.attack ?? 0.006;
  const release = o.release ?? dur * 0.8;

  const osc = ctx.createOscillator();
  osc.type = o.type ?? "sine";
  osc.frequency.setValueAtTime(freq, t0);
  if (o.glideTo) osc.frequency.exponentialRampToValueAtTime(o.glideTo, t0 + dur);
  if (o.detune) osc.detune.value = o.detune;
  let lfo: OscillatorNode | null = null;
  if (o.vibrato) {
    lfo = ctx.createOscillator();
    lfo.frequency.value = o.vibrato.rate;
    const depth = ctx.createGain();
    depth.gain.value = o.vibrato.depth;
    lfo.connect(depth).connect(osc.detune);
  }

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(peak, t0 + attack);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + release);

  let out: AudioNode = env;
  if (o.cutoff) {
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = o.cutoff;
    env.connect(lp);
    out = lp;
  }
  osc.connect(env);
  connectOut(g, out, o.space);
  osc.start(t0);
  osc.stop(t0 + attack + release + 0.05);
  if (lfo) {
    lfo.start(t0);
    lfo.stop(t0 + attack + release + 0.05);
  }
}

/** Filtered noise whose band sweeps from `from` to `to` Hz: whooshes, snores, swishes. */
export function whoosh(at: number, dur: number, from: number, to: number, gain = 0.1, q = 2) {
  const g = get();
  if (!g) return;
  const { ctx } = g;
  const t0 = ctx.currentTime + 0.005 + at;
  const len = Math.floor(ctx.sampleRate * dur);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.Q.value = q;
  bp.frequency.setValueAtTime(from, t0);
  bp.frequency.exponentialRampToValueAtTime(to, t0 + dur);
  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(gain, t0 + dur * 0.4);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  src.connect(bp).connect(env);
  connectOut(g, env, 0.15);
  src.start(t0);
}

/** Two-operator FM strike: bells, glass, temple bells. */
export function bell(freq: number, at: number, o: BellOpts = {}) {
  const g = get();
  if (!g) return;
  const { ctx } = g;
  const t0 = ctx.currentTime + 0.005 + at;
  const decay = o.decay ?? 1.2;
  const ratio = o.ratio ?? 1.4;
  const index = o.index ?? 2.2;

  const carrier = ctx.createOscillator();
  carrier.frequency.value = freq;
  const mod = ctx.createOscillator();
  mod.frequency.value = freq * ratio;
  const modGain = ctx.createGain();
  modGain.gain.setValueAtTime(freq * index, t0);
  modGain.gain.exponentialRampToValueAtTime(Math.max(1, freq * index * 0.1), t0 + decay * 0.6);
  mod.connect(modGain).connect(carrier.frequency);

  const env = ctx.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(o.gain ?? 0.2, t0 + 0.004);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + decay);
  carrier.connect(env);
  connectOut(g, env, o.space ?? 0.4);

  for (const osc of [carrier, mod]) {
    osc.start(t0);
    osc.stop(t0 + decay + 0.05);
  }
}

/** A short filtered noise tick (UI clicks). */
export function tick(at = 0, gain = 0.12, freq = 3200) {
  const g = get();
  if (!g) return;
  const { ctx } = g;
  const t0 = ctx.currentTime + 0.005 + at;
  const len = Math.floor(ctx.sampleRate * 0.03);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len) ** 4;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = freq;
  bp.Q.value = 1.2;
  const env = ctx.createGain();
  env.gain.value = gain;
  src.connect(bp).connect(env);
  connectOut(g, env, 0.1);
  src.start(t0);
}
