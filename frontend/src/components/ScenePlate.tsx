import { useLayoutEffect, useRef } from "react";
export type Mark = {
  label: string;
  annotate?: boolean;
  state: string;
  x: number;
  y: number;
  z: number;
  shape?: "layer" | "lock" | "thread" | "reject";
};
export type Plate = { marks: Mark[]; links: [number, number][] };
export const plates = new WeakMap<Element, Plate>();
export function ScenePlate({
  title,
  model,
  caption,
}: {
  title: string;
  model: Plate;
  caption: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = ref.current!;
    plates.set(el, model);
    return () => {
      plates.delete(el);
    };
  }, [model]);
  return (
    <figure className="scene-plate">
      <div
        className="plate-window"
        ref={ref}
        role="img"
        aria-label={title + ". " + caption}
      >
        <svg
          aria-hidden="true"
          viewBox="-5 -2 10 4"
          preserveAspectRatio="xMidYMid meet"
        >
          {model.links.map(([a, b], i) => (
            <line
              key={i}
              x1={model.marks[a].x}
              y1={-model.marks[a].y}
              x2={model.marks[b].x}
              y2={-model.marks[b].y}
            />
          ))}
          {model.marks.map((m, i) => {
            if (m.shape === "thread") return null;
            const paint = color(m.state);
            return (
              <g
                key={i}
                transform={`translate(${m.x} ${-m.y})`}
                fill={paint}
                stroke={paint}
              >
                {m.shape === "layer" ? (
                  <ellipse rx=".38" ry=".11" strokeWidth=".025" fill="none" />
                ) : m.shape === "lock" ? (
                  <path
                    d="M-.075 -.015v.11h.15v-.11z M-.045 -.015v-.04a.045 .045 0 0 1 .09 0v.04"
                    strokeWidth=".018"
                  />
                ) : m.shape === "reject" ? (
                  <path d="m-.08 .07 .16 -.14" strokeWidth=".03" />
                ) : (
                  <circle r=".075" />
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption>
        <strong>{title}</strong>
        <span>{caption}</span>
      </figcaption>
    </figure>
  );
}
export function color(state: string) {
  const colors: Record<string, string> = {
    healthy: "#c5f2a5",
    disrupted: "#ff986f",
    attention: "#f4cc76",
    paused: "#8da6a0",
    stale: "#b9a8d6",
    verified: "#c5f2a5",
    open: "#edb47c",
    editable: "#77e3ae",
    locked: "#b1c9e1",
    read: "#82dff5",
    proposed: "#ffc678",
    blocked: "#ed967c",
    failed: "#ff986f",
  };
  return colors[state] || "#748781";
}
