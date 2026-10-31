import { describe, it, expect } from "vitest";
import { parseFrame } from "./api";
describe("persisted recovery event protocol", () => {
  it("ignores heartbeats", () => expect(parseFrame(": heartbeat")).toBeNull());
  it("decodes SSE event data", () =>
    expect(
      parseFrame(
        'id: 9\nevent: recovery\ndata: {"id":9,"stage":"verification"}',
      ),
    ).toEqual({ id: 9, stage: "verification" }));
});
