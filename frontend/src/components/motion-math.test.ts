import { describe, expect, it } from "vitest";
import { angleDelta, damping, pointerDepth } from "./motion-math";
describe("continuous scene motion", () => {
  it("returns across the rotation seam using the short arc", () => {
    expect(angleDelta(6.2, 0.1)).toBeCloseTo(0.1831853);
    expect(angleDelta(0.1, 6.2)).toBeCloseTo(-0.1831853);
  });
  it("converges equally at 30 and 60 fps without overshoot", () => {
    const advance = (fps: number) => {
      let value = 0;
      for (let i = 0; i < fps; i++) value += (1 - value) * damping(1 / fps);
      return value;
    };
    expect(advance(30)).toBeCloseTo(advance(60), 10);
    expect(damping(-1)).toBe(0);
    expect(damping(2)).toBeLessThan(1);
  });
  it("bounds card tilt and rests flat at the center", () => {
    expect(pointerDepth(0,0)).toEqual({x:-0,y:0});
    expect(pointerDepth(99,-99)).toEqual({x:1.4,y:1.8});
  });
});
