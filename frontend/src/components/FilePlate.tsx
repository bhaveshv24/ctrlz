import { useMemo, useState } from "react";
import type { FlightEvent } from "../api";
import { ScenePlate, type Plate } from "./ScenePlate";
type Inspection = {
  files?: string[];
  tests?: string[];
  editable_files?: string[];
};
const none: FlightEvent[] = [];
export function FilePlate({
  inspection,
  events = none,
}: {
  inspection: Inspection;
  events?: FlightEvent[];
}) {
  const [focus, setFocus] = useState("");
  const evidence = useMemo(() => {
    const tests = new Set(inspection.tests),
      editable = new Set(inspection.editable_files);
    const read = new Set<string>(),
      proposed = new Set<string>();
    for (const { stage, payload } of events) {
      if (
        stage === "tool_result" &&
        payload.tool === "read_repository_file" &&
        typeof payload.path === "string"
      )
        read.add(payload.path);
      if (stage === "code_proposal")
        for (const change of [
          ...(payload.changes || []),
          ...(payload.edits || []),
        ])
          if (typeof change.path === "string") proposed.add(change.path);
    }
    return [
      ...new Set([
        ...(inspection.files || []),
        ...tests,
        ...editable,
        ...read,
        ...proposed,
      ]),
    ]
      .sort()
      .map((path) => ({
        path,
        locked: tests.has(path),
        state: tests.has(path)
          ? "locked"
          : proposed.has(path)
            ? "proposed"
            : read.has(path)
              ? "read"
              : editable.has(path)
                ? "editable"
                : "other",
        read: read.has(path),
      }));
  }, [inspection, events]);
  const graph = useMemo(() => {
    const model: Plate = { marks: [], links: [] };
    const dirs = new Map<string, typeof evidence>();
    evidence.forEach((file) => {
      const dir = file.path.includes("/")
        ? file.path.slice(0, file.path.lastIndexOf("/"))
        : ".";
      if (!dirs.has(dir)) dirs.set(dir, []);
      dirs.get(dir)!.push(file);
    });
    let i = 0;
    for (const [dir, files] of dirs) {
      const a = (2 * Math.PI * i++) / dirs.size;
      const x = dirs.size === 1 ? 0 : 2.6 * Math.cos(a),
        y = dirs.size === 1 ? 0 : 0.85 * Math.sin(a);
      const parent =
        model.marks.push({ label: dir, state: "other", x, y, z: -0.2 }) - 1;
      files.forEach((file, j) => {
        const angle = j * 2.39996,
          radius = 0.28 + 0.85 * Math.sqrt((j + 1) / files.length);
        const node =
          model.marks.push({
            label: file.path,
            state: file.state,
            shape: file.locked ? "lock" : undefined,
            x: x + Math.cos(angle) * radius,
            y: y + Math.sin(angle) * radius * 0.65,
            z: 0.22 * Math.sin(j),
          }) - 1;
        model.links.push([parent, node]);
        if (file.path === focus || (file.read && file.locked))
          model.marks.push({
            ...model.marks[node],
            shape: "layer",
            state: file.read ? "read" : file.state,
          });
      });
    }
    return model;
  }, [evidence, focus]);
  const file = evidence.find((f) => f.path === focus),
    check = events.filter((e) => e.stage === "verification").at(-1)
      ?.payload.passed;
  return (
    <section className="file-field">
      <ScenePlate
        title="Repository file graph"
        model={graph}
        caption={
          evidence.length +
          " recorded paths / Locked tests · Editable source · Other files" +
          (typeof check === "boolean"
            ? " / Verification " + (check ? "passed" : "failed")
            : "")
        }
      />
      <label>
        Inspect file
        <select value={focus} onChange={(e) => setFocus(e.target.value)}>
          <option value="">Choose a path</option>
          {evidence.map((f) => (
            <option key={f.path}>{f.path}</option>
          ))}
        </select>
      </label>
      {file && (
        <p>
          {file.path} · {file.state}
          {file.read ? " · read by agent" : ""}
        </p>
      )}
    </section>
  );
}
