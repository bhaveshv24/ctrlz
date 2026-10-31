import { describe, expect, it } from "vitest";
import { chapterTransition } from "./journey-transition";

describe("intro chapter transitions", () => {
  it("never overlays chapters at any scroll position in either direction", () => {
    for (let step = 0; step <= 4000; step++) {
      for (const position of [step / 1000, 4 - step / 1000]) {
        const frames = Array.from({length: 5}, (_, index) => chapterTransition(position, index));
        expect(frames.filter(frame => frame.visible).length).toBeLessThanOrEqual(1);
      }
    }
  });

  it("holds each chapter at full opacity and completely clears the halfway handoff", () => {
    for (let index = 0; index < 5; index++) {
      expect(chapterTransition(index, index).opacity).toBe(1);
      if (index < 4) {
        expect(chapterTransition(index + 0.5, index).visible).toBe(false);
        expect(chapterTransition(index + 0.5, index + 1).visible).toBe(false);
      }
    }
  });

  it("fades continuously toward the handoff rather than snapping the text", () => {
    let previous = 1;
    for (let step = 0; step <= 500; step++) {
      const frame = chapterTransition(step / 1000, 0);
      expect(frame.opacity).toBeLessThanOrEqual(previous);
      expect(Math.abs(frame.opacity - previous)).toBeLessThan(0.01);
      previous = frame.opacity;
    }
    expect(previous).toBe(0);
  });
});
