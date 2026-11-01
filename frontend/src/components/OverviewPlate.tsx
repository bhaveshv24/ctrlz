import { useMemo } from "react";
import type { Overview } from "../api";
import { ScenePlate, type Plate } from "./ScenePlate";
export function OverviewPlate({ overview }: { overview: Overview }) {
  const model = useMemo(() => {
    const graph: Plate = { marks: [], links: [] };
    const { verified_recoveries, open_incidents } = overview.summary;
    for (let i = 0; i < verified_recoveries; i++)
      graph.marks.push({
        label: "Verified recovery",
        state: "verified",
        shape: "layer",
        x: 0,
        y:
          (i - (verified_recoveries - 1) / 2) *
          Math.min(0.13, 1.8 / verified_recoveries),
        z: 0,
      });
    overview.projects.forEach(({ project, state }, i) => {
      const angle = ((i + 0.12) * Math.PI * 2) / overview.projects.length;
      graph.marks.push({
        label: project.name,
        annotate: overview.projects.length <= 10,
        state,
        x: 3.4 * Math.cos(angle),
        y: Math.sin(angle),
        z: 0.4 * Math.sin(angle),
      });
    });
    for (let i = 0; i < open_incidents; i++) {
      const a = i * 2.4,
        index = graph.marks.length;
      for (let j = 0; j < 12; j++) {
        const u = j / 11;
        graph.marks.push({
          label: "Open incident",
          state: "open",
          shape: "thread",
          x: Math.cos(a) * (0.6 + u * 1.5),
          y: Math.sin(a + u) * u,
          z: 0.3 * Math.sin(u * 4),
        });
        if (j) graph.links.push([index + j - 1, index + j]);
      }
    }
    return graph;
  }, [overview]);
  return (
    <ScenePlate
      title="Recovery field"
      model={model}
      caption={[
        ...overview.projects.map((p) => p.project.name + " / " + p.state),
        overview.summary.verified_recoveries + " verified layers",
        overview.summary.open_incidents + " open threads",
      ].join(" / ")}
    />
  );
}
