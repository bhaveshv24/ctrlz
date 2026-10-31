import { describe, expect, it } from "vitest";
import { REWIND_REVEAL, rewindMotion } from "./rewind-motion";
describe("disc rewind sequence", () => {
  it("starts at rest and completes two whole rotations with no residual shadow", () => {
    expect(rewindMotion(0)).toMatchObject({turn:0, shadow:0, bank:0, reveal:false});
    expect(rewindMotion(1).turn).toBeCloseTo(Math.PI * 4);
    expect(rewindMotion(1).shadow).toBe(0);
    expect(rewindMotion(1).bank).toBeCloseTo(0);
  });
  it("holds back the screen until the shadow has covered the disc", () => {
    expect(rewindMotion(.68).shadow).toBe(1);
    expect(rewindMotion(REWIND_REVEAL - .001).reveal).toBe(false);
    expect(rewindMotion(REWIND_REVEAL).reveal).toBe(true);
    expect(rewindMotion(.9).shadow).toBeLessThan(1);
  });
  it("turns continuously forward with bounded shadow and tornado strength", () => {
    let previous = 0;
    for (let i = 0; i <= 1000; i++) {
      const motion = rewindMotion(i / 1000);
      expect(motion.turn).toBeGreaterThanOrEqual(previous);
      expect(motion.turn - previous).toBeLessThan(.03);
      expect(motion.shadow).toBeGreaterThanOrEqual(0);
      expect(motion.shadow).toBeLessThanOrEqual(1);
      previous = motion.turn;
    }
  });
  it("holds the completed turn through the landing instead of resetting it", () => {
    for (const progress of [.8, .9, .99, 1])
      expect(rewindMotion(progress).turn).toBeCloseTo(Math.PI * 4);
    expect(rewindMotion(.999).bank).toBeLessThan(.00001);
    expect(rewindMotion(.999).strength).toBeLessThan(.00001);
  });

});
