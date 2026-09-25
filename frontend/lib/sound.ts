"use client";

/**
 * Tiny synthesized sound effects (Web Audio API), so no audio files ship with
 * the app. Callers check the learner's `sound_effects` setting first.
 */
export type SoundName = "correct" | "wrong" | "complete" | "heart";

let context: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined" || !("AudioContext" in window)) return null;
  context ??= new AudioContext();
  if (context.state === "suspended") void context.resume();
  return context;
}

function tone(ctx: AudioContext, frequency: number, start: number, duration: number, type: OscillatorType, volume = 0.12) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = frequency;
  const t0 = ctx.currentTime + start;
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
  osc.connect(gain).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + duration + 0.05);
}

const SOUNDS: Record<SoundName, (ctx: AudioContext) => void> = {
  correct: (ctx) => {
    tone(ctx, 659.25, 0, 0.12, "sine");
    tone(ctx, 987.77, 0.1, 0.22, "sine");
  },
  wrong: (ctx) => {
    tone(ctx, 196, 0, 0.18, "square", 0.05);
    tone(ctx, 164.81, 0.16, 0.28, "square", 0.05);
  },
  complete: (ctx) => {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(ctx, f, i * 0.11, 0.3, "triangle"));
  },
  heart: (ctx) => {
    tone(ctx, 880, 0, 0.12, "sine");
    tone(ctx, 1318.51, 0.09, 0.2, "sine");
  },
};

export function playSound(name: SoundName, enabled: boolean): void {
  if (!enabled) return;
  try {
    const ctx = audio();
    if (ctx) SOUNDS[name](ctx);
  } catch {
    // Audio is decorative; never break the lesson over it.
  }
}
