import { describe, it, expect } from "vitest";
import {
  scenarioReason,
  type DemoTarget,
  type DemoScenario,
} from "./demo-targets";
const scenario: DemoScenario = {
  id: "repair",
  title: "Repair",
  description: "",
  disabled_reason: null,
};
const repo: DemoTarget = {
  id: "repo",
  kind: "repository",
  name: "Repo",
  facts: { dependency_install_required: true },
  scenarios: [scenario],
};
describe("Demo Lab capability boundaries", () => {
  it("requires explicit dependency approval for repository runs", () => {
    expect(
      scenarioReason(repo, scenario, false, "Restore acceptance tests"),
    ).toContain("Approve isolated");
    expect(
      scenarioReason(repo, scenario, true, "Restore acceptance tests"),
    ).toBeNull();
  });
  it("keeps unsupported scenarios disabled even with approval", () => {
    expect(
      scenarioReason(
        repo,
        { ...scenario, disabled_reason: "Unsupported runner" },
        true,
        "Restore acceptance tests",
      ),
    ).toBe("Unsupported runner");
  });
  it("requires meaningful repair requirements", () => {
    expect(scenarioReason(repo, scenario, true, "fix")).toContain(
      "10 characters",
    );
  });
  it("does not apply repository gates to service monitoring", () => {
    expect(
      scenarioReason({ ...repo, kind: "service" }, scenario, false, ""),
    ).toBeNull();
  });
  it("retains a generic service's missing-fault-controls reason", () => {
    expect(
      scenarioReason(
        { ...repo, kind: "service" },
        { ...scenario, id: "fault", disabled_reason: "No demo fault controls" },
        false,
        "",
      ),
    ).toBe("No demo fault controls");
  });
});
