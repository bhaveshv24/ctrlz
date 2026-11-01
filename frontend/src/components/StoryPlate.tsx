import { useMemo, useState } from "react";
import type { Receipt } from "../api";
import { ScenePlate, type Plate } from "./ScenePlate";
export function StoryPlate({ receipt }: { receipt: Receipt }) {
  const [cursor, setCursor] = useState<number | null>(null);
  const events = receipt.events,
    end = Math.min(cursor ?? events.length - 1, events.length - 1);
  const model = useMemo(() => {
    const graph: Plate = { marks: [], links: [] },
      strategies = new Map<string, number>();
    let previous = -1,
      executed: string | undefined;
    for (let index = 0; index <= end; index++) {
      const { stage, payload } = events[index],
        x = -4 + (8 * index) / Math.max(1, events.length - 1);
      const mark = {
        label: stage,
        x,
        y: 0.22 * Math.sin(index * 0.45),
        z: 0.26 * Math.cos(index * 0.45),
        state: "other",
      };
      if (stage === "verification")
        mark.state =
          payload.passed === true
            ? "verified"
            : payload.passed === false
              ? "failed"
              : "other";
      const node = graph.marks.push(mark) - 1;
      if (previous >= 0) graph.links.push([previous, node]);
      previous = node;
      if (stage === "tournament" && Array.isArray(payload.results)) {
        strategies.clear();
        executed = undefined;
        payload.results.forEach((s, j) => {
          const id = s.candidate_id || s.id,
            blocked = s.eligible === false;
          const branch =
            graph.marks.push({
              label: String(id),
              x: x + 0.18 + j * 0.12,
              y: (blocked ? -1 : 1) * (0.64 + j * 0.14),
              z: 0.16 * j,
              state: blocked ? "blocked" : "other",
              shape: blocked ? "reject" : undefined,
            }) - 1;
          if (!blocked) strategies.set(id, branch);
          graph.links.push([node, branch]);
        });
      }
      if (stage === "operation_result")
        executed = receipt.incident.selected?.id;
      if (stage === "verification") {
        const strategy = strategies.get(payload.selected_strategy || executed);
        if (strategy !== undefined) graph.links.push([strategy, node]);
      }
    }
    return graph;
  }, [events, end, receipt.incident.selected]);
  if (!events.length) return null;
  const event = events[end];
  const rejected = model.marks
    .filter((m) => m.shape === "reject")
    .map((m) => m.label);
  return (
    <section className="story-field">
      <ScenePlate
        title="Incident timeline"
        model={model}
        caption={
          `${end + 1} / ${events.length} / ${event.stage.replaceAll("_", " ")}` +
          (event.stage === "verification" &&
          typeof event.payload.passed === "boolean"
            ? event.payload.passed
              ? " / passed"
              : " / failed"
            : "")
        }
      />
      {rejected.length > 0 && (
        <p className="branch-key">
          Blocked strategies / {[...new Set(rejected)].join(", ")}
        </p>
      )}
      <label>
        Recorded event
        <input
          type="range"
          min={0}
          max={events.length - 1}
          value={end}
          onChange={(e) =>
            setCursor(
              +e.target.value === events.length - 1 ? null : +e.target.value,
            )
          }
        />
      </label>
    </section>
  );
}
