export type DemoScenario = {
  id: string;
  title: string;
  description: string;
  disabled_reason: string | null;
};
export type DemoTarget = {
  id: string;
  kind: "repository" | "service";
  name: string;
  scenarios: DemoScenario[];
  facts: {
    profile?: string;
    profile_label?: string;
    test_file_count?: number;
    source_count?: number;
    tests?: string[];
    editable_files?: string[];
    dependency_install_required?: boolean;
    adapter?: string;
    origin?: string;
    health_path?: string;
    workflow_path?: string;
    operations?: string[];
    contract?: unknown;
    monitoring_enabled?: boolean;
  };
};
export function scenarioReason(
  target: DemoTarget,
  scenario: DemoScenario,
  approved: boolean,
  requirements: string,
) {
  return (
    scenario.disabled_reason ||
    (target.kind === "repository" &&
    target.facts.dependency_install_required &&
    !approved
      ? "Approve isolated dependency setup before running this scenario."
      : target.kind === "repository" && requirements.trim().length < 10
        ? "Enter repair requirements of at least 10 characters."
        : null)
  );
}
