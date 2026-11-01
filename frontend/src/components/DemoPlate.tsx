import type { DemoRun } from "../api";
import type { DemoTarget, DemoScenario } from "../demo-targets";
import { ScenePlate, type Plate } from "./ScenePlate";
export function DemoPlate({
  target,
  scenario,
  runs,
  observed,
}: {
  target: DemoTarget;
  scenario: DemoScenario | null;
  runs: DemoRun[];
  observed: boolean;
}) {
  const choices = scenario ? [scenario] : target.scenarios;
  const graph: Plate = {
    marks: [
      {
        label: target.name,
        state: "editable",
        x: -3,
        y: 0,
        z: 0.2,
        shape: "layer",
      },
    ],
    links: [],
  };
  const captions = choices.map((s, i) => {
    const y =
      (i - (choices.length - 1) / 2) * Math.min(0.62, 2.5 / choices.length);
    const node =
      graph.marks.push({
        label: s.title,
        state: s.disabled_reason ? "paused" : "other",
        x: 0,
        y,
        z: 0,
      }) - 1;
    graph.links.push([0, node]);
    const run = runs.find(
      (r) => r.project_id === target.id && r.scenario === s.id,
    );
    if (run) {
      const status = run.incident_status || run.status;
      const end =
        graph.marks.push({
          label: status,
          state: status === "failed" ? "failed" : "read",
          x: 3,
          y,
          z: 0.24,
        }) - 1;
      graph.links.push([node, end]);
      return s.title + " / " + status;
    }
    return (
      s.title +
      " / " +
      (s.disabled_reason
        ? "unavailable"
        : observed
          ? "no recorded run"
          : "history unavailable")
    );
  });
  return (
    <ScenePlate
      title={target.name}
      model={graph}
      caption={captions.join(" / ")}
    />
  );
}
