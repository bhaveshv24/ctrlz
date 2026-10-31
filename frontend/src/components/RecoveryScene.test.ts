import { describe, it, expect } from "vitest";
import { sceneEligible } from "./RecoveryScene";
describe("Recovery Core progressive enhancement policy", () => {
  it.each([
    ["capable desktop", 1280, false, false, 8, 8, true],
    ["mobile", 390, false, false, 8, 8, false],
    ["reduced motion", 1280, true, false, 8, 8, false],
    ["touch-first device", 1280, false, true, 8, 8, false],
    ["low CPU budget", 1280, false, false, 2, 8, false],
    ["low memory budget", 1280, false, false, 8, 2, false],
    [
      "optional hardware hints absent",
      1280,
      false,
      false,
      undefined,
      undefined,
      true,
    ],
  ] as const)(
    "%s uses the correct enhancement path",
    (_name, width, reduced, coarse, cores, memory, enabled) => {
      expect(sceneEligible(width, reduced, coarse, cores, memory)).toBe(
        enabled,
      );
    },
  );
});
