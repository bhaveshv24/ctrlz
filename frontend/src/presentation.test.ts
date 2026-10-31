import { describe, expect, it } from "vitest";
import { duration, eventSummary, measuredDuration } from "./presentation";
import type { FlightEvent, Receipt } from "./api";
const event = (
  stage: string,
  payload: FlightEvent["payload"],
  timestamp = 150,
): FlightEvent => ({ id: 1, incident_id: "test", stage, payload, timestamp });
const receipt = (events: FlightEvent[]): Receipt => ({
  schema_version: 1,
  incident: {
    id: "test",
    project_id: "demo",
    kind: "outage",
    resource: "service",
    status: "verifying",
    created: 100,
    updated: 200,
  },
  events,
  success: false,
  reasoning_provider: "test fixture",
  integrity: {
    algorithm: "sha256",
    snapshot_digest: "test",
    scope: "test fixture",
  },
});
describe("evidence presentation", () => {
  it("does not invent a recovery time when acceptance has not passed", () => {
    expect(
      measuredDuration(receipt([event("verification", { passed: false })])),
    ).toBeNull();
  });
  it("measures to the first passing check, excluding later replay and export activity", () => {
    expect(
      measuredDuration(
        receipt([
          event("verification", { passed: true }, 140),
          event("replay_result", { verification: { passed: true } }, 700),
          event("verification", { passed: true }, 750),
        ]),
      ),
    ).toBe(40);
  });
  it("labels a failing acceptance result as unresolved", () => {
    expect(
      eventSummary(
        event("verification", {
          passed: false,
          checks: { healthy: true, entitlement: false },
        }),
      ),
    ).toBe("1/2 checks passed · unresolved");
  });
  it("keeps missing measurements distinct from zero", () => {
    expect(duration(null)).toBe("—");
    expect(duration(0)).toBe("0s");
  });
});
