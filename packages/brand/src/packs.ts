import { bell, tick, tone, whoosh } from "./engine";

export const CUES = ["wake", "listen", "think", "tool", "confirm", "success", "error", "sleep", "click", "toggle"] as const;
export type Cue = (typeof CUES)[number];

/** `step` = index of this tool call in the turn, so progress rises in pitch. */
export type CueOpts = { step?: number };
export type Pack = Record<Cue, (o?: CueOpts) => void>;

// Note frequencies (Hz).
const C5 = 523.25, D5 = 587.33, E5 = 659.25, G5 = 783.99, A5 = 880, B5 = 987.77;
const C6 = 1046.5, E6 = 1318.5, G6 = 1568, Eb4 = 311.13, G4 = 392;

/** Major pentatonic from `root`: step 0,1,2… climbs and wraps an octave every 5 steps. */
export function pentatonic(root: number, step: number): number {
  const semis = [0, 2, 4, 7, 9];
  const s = Math.max(0, Math.min(step, 9));
  const octave = Math.floor(s / 5);
  return root * 2 ** ((semis[s % 5]! + 12 * octave) / 12);
}

/** Glassy, Apple-like chimes: FM glass + sine, a touch of room. */
const soft: Pack = {
  wake: () => {
    bell(E5, 0, { gain: 0.16, ratio: 2.0, index: 0.8, decay: 0.9, space: 0.35 });
    bell(B5, 0.08, { gain: 0.15, ratio: 2.0, index: 0.7, decay: 1.1, space: 0.4 });
  },
  listen: () => tone(A5, 0, 0.25, { gain: 0.12, space: 0.3 }),
  think: () => {
    tone(1400, 0, 0.05, { type: "triangle", gain: 0.04 });
    tone(1600, 0.08, 0.05, { type: "triangle", gain: 0.035 });
  },
  tool: (o) => bell(pentatonic(C6, o?.step ?? 0), 0, { gain: 0.07, ratio: 3.0, index: 0.5, decay: 0.35, space: 0.2 }),
  confirm: () => {
    bell(G5, 0, { gain: 0.15, ratio: 2.0, index: 0.9, decay: 0.7 });
    bell(C6, 0.13, { gain: 0.15, ratio: 2.0, index: 0.9, decay: 0.9 });
  },
  success: () => {
    [C6, E6, G6].forEach((f, i) => bell(f, i * 0.07, { gain: 0.12, ratio: 2.0, index: 0.6, decay: i === 2 ? 1.4 : 0.6, space: 0.45 }));
  },
  error: () => {
    tone(G4, 0, 0.22, { type: "triangle", gain: 0.2, space: 0.2 });
    tone(Eb4, 0.15, 0.4, { type: "triangle", gain: 0.2, space: 0.25 });
  },
  sleep: () => tone(E5, 0, 0.9, { gain: 0.09, glideTo: E5 / 2, attack: 0.08, space: 0.5 }),
  click: () => tick(0, 0.07, 3800),
  toggle: () => tone(1250, 0, 0.06, { type: "triangle", gain: 0.06 }),
};

/** Playful robot bleeps: filtered squares and pitch slides. */
const robo: Pack = {
  wake: () => {
    tone(C5, 0, 0.09, { type: "square", gain: 0.09, cutoff: 2600, glideTo: G5 });
    tone(C6, 0.1, 0.16, { type: "square", gain: 0.09, cutoff: 3200 });
  },
  listen: () => tone(G5, 0, 0.08, { type: "square", gain: 0.06, cutoff: 2400 }),
  think: () => {
    tone(900, 0, 0.04, { type: "square", gain: 0.035, cutoff: 2000 });
    tone(1200, 0.07, 0.04, { type: "square", gain: 0.035, cutoff: 2000 });
  },
  tool: (o) => tone(pentatonic(C5, o?.step ?? 0), 0, 0.07, { type: "square", gain: 0.05, cutoff: 2600 }),
  confirm: () => {
    tone(D5, 0, 0.09, { type: "square", gain: 0.08, cutoff: 2600 });
    tone(A5, 0.11, 0.14, { type: "square", gain: 0.08, cutoff: 2600, glideTo: B5 });
  },
  success: () => {
    [C5, E5, G5, C6].forEach((f, i) => tone(f, i * 0.06, 0.1, { type: "square", gain: 0.07, cutoff: 3000 }));
  },
  error: () => tone(320, 0, 0.35, { type: "sawtooth", gain: 0.09, cutoff: 1400, glideTo: 140 }),
  sleep: () => tone(600, 0, 0.7, { type: "square", gain: 0.045, cutoff: 1200, glideTo: 180, attack: 0.05 }),
  click: () => tone(2200, 0, 0.025, { type: "square", gain: 0.03, cutoff: 3000 }),
  toggle: () => tone(1000, 0, 0.05, { type: "square", gain: 0.045, cutoff: 2600, glideTo: 1300 }),
};

/**
 * Kovil — temple-bell inspired. Inharmonic FM bells (ratio ≈ 3.5) with long tails,
 * and a reedy nadaswaram-like glide for wake. A sound only a Tamil assistant would have.
 */
const SA = 440 * 2 ** (-9 / 12) * 2; // ~C5 "Sa"
const MAYAMALAVAGOWLA = [0, 1, 4, 5, 7, 8, 11]; // the first raga students learn
const swara = (i: number) => SA * 2 ** ((MAYAMALAVAGOWLA[i % 7]! + 12 * Math.floor(i / 7)) / 12);

const kovil: Pack = {
  wake: () => {
    tone(swara(4) * 0.97, 0, 0.42, { type: "sawtooth", gain: 0.05, cutoff: 1800, glideTo: swara(4), attack: 0.06, space: 0.3 });
    bell(swara(7), 0.32, { gain: 0.16, ratio: 3.5, index: 2.4, decay: 2.2, space: 0.55 });
  },
  listen: () => bell(swara(4), 0, { gain: 0.09, ratio: 3.5, index: 1.2, decay: 0.9 }),
  think: () => tick(0, 0.05, 2400),
  tool: (o) => bell(swara(o?.step ?? 0) * 2, 0, { gain: 0.06, ratio: 3.5, index: 1.0, decay: 0.5, space: 0.3 }),
  confirm: () => {
    bell(swara(4), 0, { gain: 0.13, ratio: 3.5, index: 1.6, decay: 1.0 });
    bell(swara(7), 0.16, { gain: 0.13, ratio: 3.5, index: 1.6, decay: 1.3 });
  },
  success: () => {
    bell(swara(7), 0, { gain: 0.17, ratio: 3.5, index: 2.6, decay: 2.6, space: 0.6 });
    bell(swara(11), 0.18, { gain: 0.1, ratio: 3.5, index: 1.8, decay: 2.0, space: 0.6 });
  },
  error: () => bell(swara(1) / 2, 0, { gain: 0.18, ratio: 1.41, index: 3, decay: 0.9, space: 0.25 }),
  sleep: () => bell(swara(0) / 2, 0, { gain: 0.1, ratio: 3.5, index: 1.0, decay: 2.8, space: 0.7 }),
  click: () => tick(0, 0.06, 3000),
  toggle: () => bell(swara(4) * 2, 0, { gain: 0.05, ratio: 3.5, index: 0.8, decay: 0.3 }),
};

/**
 * Toon — a cartoon sidekick. Slide whistle to wake, boing, kazoo "huh?", rubber squeaks
 * that climb with progress, a ta-da, a sad trombone, and a little snore.
 */
const WOBBLE = { rate: 7, depth: 35 };
const toon: Pack = {
  wake: () => {
    tone(480, 0, 0.32, { gain: 0.11, glideTo: 1500, vibrato: { rate: 9, depth: 25 }, attack: 0.02 });
    tone(220, 0.3, 0.28, { type: "triangle", gain: 0.13, glideTo: 110, vibrato: { rate: 18, depth: 120 } }); // boing
  },
  listen: () => {
    tone(392, 0, 0.09, { type: "triangle", gain: 0.1, vibrato: WOBBLE });
    tone(587, 0.1, 0.14, { type: "triangle", gain: 0.1, glideTo: 660, vibrato: WOBBLE }); // "hm?"
  },
  think: () => {
    tone(900, 0, 0.06, { gain: 0.06, glideTo: 450 });
    tone(800, 0.1, 0.06, { gain: 0.05, glideTo: 400 }); // bloop bloop
  },
  tool: (o) => tone(pentatonic(G5, o?.step ?? 0), 0, 0.07, { type: "square", gain: 0.04, cutoff: 3200, glideTo: pentatonic(G5, (o?.step ?? 0) + 1) }), // squeak
  confirm: () => tone(330, 0, 0.35, { type: "sawtooth", gain: 0.06, cutoff: 1600, glideTo: 520, vibrato: { rate: 11, depth: 40 } }), // kazoo "huh?"
  success: () => {
    tone(C5, 0, 0.12, { type: "sawtooth", gain: 0.06, cutoff: 2200 });
    [C5, E5, G5].forEach((f) => tone(f * 2, 0.14, 0.55, { type: "sawtooth", gain: 0.045, cutoff: 2600, vibrato: { rate: 6, depth: 18 }, space: 0.3 })); // ta-da!
    bell(C6 * 2, 0.2, { gain: 0.05, ratio: 2, index: 0.5, decay: 0.6 });
  },
  error: () => {
    // sad trombone: wah, wah, wah, waaah
    [311, 294, 277].forEach((f, i) => tone(f, i * 0.32, 0.28, { type: "sawtooth", gain: 0.07, cutoff: 1100, vibrato: { rate: 5, depth: 15 } }));
    tone(262, 0.96, 0.9, { type: "sawtooth", gain: 0.07, cutoff: 1000, glideTo: 247, vibrato: { rate: 6, depth: 45 } });
  },
  sleep: () => {
    whoosh(0, 0.9, 300, 900, 0.07, 3); // zzz in…
    whoosh(1.0, 0.9, 900, 250, 0.06, 3); // …and out
  },
  click: () => tone(650, 0, 0.05, { gain: 0.08, glideTo: 200 }), // pop
  toggle: () => tone(500, 0, 0.08, { type: "triangle", gain: 0.07, glideTo: 900 }), // boop
};

export const packs = { soft, robo, kovil, toon } as const;
export type PackName = keyof typeof packs;
