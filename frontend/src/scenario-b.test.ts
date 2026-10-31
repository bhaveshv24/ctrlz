import { expect, it } from "vitest";
import type { Incident } from "./api";
import { title } from "./presentation";

it("labels a workflow recovered only after successful independent verification", () => {
  const incident: Incident = {
    id: "scenario-b", project_id: "campuspass-b", kind: "workflow",
    resource: "order", status: "awaiting_approval", created: 1, updated: 2,
  };
  expect(title(incident)).toBe("Workflow needs recovery");
  expect(title({ ...incident, status: "resolved" })).toBe("Workflow needs recovery");
  expect(title({ ...incident, status: "resolved", verification: { passed: false, checks: {} } })).toBe("Workflow needs recovery");
  expect(title({ ...incident, status: "resolved", verification: { passed: true, checks: { exactly_one_ticket: true } } })).toBe("Ticket issuance recovered");
});
