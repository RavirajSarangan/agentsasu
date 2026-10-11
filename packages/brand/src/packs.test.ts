import { describe, expect, it } from "vitest";
import { panFromScreenX } from "./engine";
import { CUES, packs, pentatonic } from "./packs";

describe("sound kit", () => {
  it("every pack has every cue", () => {
    for (const pack of Object.values(packs)) expect(Object.keys(pack).sort()).toEqual([...CUES].sort());
  });

  it("progress climbs the pentatonic scale", () => {
    const steps = [0, 1, 2, 3, 4, 5].map((s) => pentatonic(440, s));
    for (let i = 1; i < steps.length; i++) expect(steps[i]!).toBeGreaterThan(steps[i - 1]!);
    expect(pentatonic(440, 5)).toBeCloseTo(880);
    expect(pentatonic(440, 99)).toBe(pentatonic(440, 9));
  });

  it("pans gently with the robot position", () => {
    expect(panFromScreenX(0)).toBe(-0.7);
    expect(panFromScreenX(0.5)).toBe(0);
    expect(panFromScreenX(1)).toBe(0.7);
    expect(panFromScreenX(4)).toBe(0.7);
  });
});
