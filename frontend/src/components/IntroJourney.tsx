import { useLayoutEffect, useRef } from "react";
import { chapterTransition } from "./journey-transition";
export type JourneyState = { active: boolean; progress: number };
const chapters = [
  {
    eyebrow: "CtrlZ",
    lines: ["You built it.", "We keep it alive."],
    description:
      "AI made building software easier than ever. CtrlZ brings autonomous recovery to what happens after — detecting failures, investigating problems, and verifying solutions.",
    tagline: "Build like a team. Recover without one.",
  },
  {
    eyebrow: "Scenario A / Development recovery",
    lines: ["A broken build."],
    description:
      "Your AI-assisted development stops halfway, or the code is complete but you don’t trust it yet. CtrlZ inspects it for bugs and potential vulnerabilities, checks its health, and helps you move forward.",
  },
  {
    eyebrow: "Scenario B / Workflow recovery",
    lines: ["Tests passed.", "Reality didn't."],
    description:
      "A payment succeeds, but the customer’s ticket never arrives. CtrlZ inspects the configured workflow evidence, compares safe recovery strategies, rejects duplicate issuance, and verifies that the intended result is accessible.",
  },
  {
    eyebrow: "Scenario C / Incident recovery",
    lines: ["When systems", "go dark."],
    description:
      "A service stops responding. CtrlZ examines authorized diagnostics and runbooks, compares permitted mitigations, requests approval for high-impact actions, and verifies the service afterward. Provider outages can require escalation.",
  },
  {
    eyebrow: "Recovery",
    lines: ["Failure happens.", "Recovery is engineered."],
    description:
      "One platform. From interrupted builds to unexpected defects and live incidents.",
    tagline: "Build like a team. Recover without one.",
  },
];
export default function IntroJourney({
  state,
  enter,
}: {
  state: JourneyState;
  enter: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = host.current!,
      panels = Array.from(el.querySelectorAll<HTMLElement>(".journey-chapter"));
    const update = () => {
      const progress = Math.max(
        0,
        Math.min(
          1,
          el.scrollTop / Math.max(1, el.scrollHeight - el.clientHeight),
        ),
      );
      state.progress = Math.min(1, (progress * 4.25) / 4);
      el.dataset.progress = progress.toFixed(5);
      const position = Math.min(4, progress * 4.25),
        active = Math.min(4, Math.round(position));
      if (el.scrollHeight - el.clientHeight - el.scrollTop <= 8) {
        enter();
        return;
      }
      panels.forEach((panel, index) => {
        const { opacity, visible, offset } = chapterTransition(position, index);
        panel.style.opacity = String(opacity);
        panel.style.transform = `translate3d(0,${offset}px,0)`;
        panel.inert = index !== active || !visible;
        panel.setAttribute("aria-hidden", String(index !== active || !visible));
        panel.style.visibility = visible ? "visible" : "hidden";
      });
    };
    let frame = 0,
      target = el.scrollTop,
      last = 0;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const stop = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      last = 0;
      target = el.scrollTop;
    };
    const settle = (now: number) => {
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60;
      last = now;
      const gap = target - el.scrollTop;
      if (Math.abs(gap) < 0.5) {
        el.scrollTop = target;
        frame = 0;
        last = 0;
        update();
        return;
      }
      el.scrollTop += gap * (1 - Math.exp(-dt / 0.16));
      frame = requestAnimationFrame(settle);
    };
    const wheel = (event: WheelEvent) => {
      if (
        event.ctrlKey ||
        event.metaKey ||
        Math.abs(event.deltaX) > Math.abs(event.deltaY) ||
        reduced.matches
      )
        return;
      // Precision trackpads already provide inertia; don't smooth them twice.
      if (event.deltaMode === 0 && Math.abs(event.deltaY) < 45) {
        stop();
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      // Reversing the wheel should reverse the scene immediately.
      if (frame && Math.sign(event.deltaY) !== Math.sign(target - el.scrollTop))
        target = el.scrollTop;
      const unit =
        event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? el.clientHeight
            : 1;
      target = Math.max(
        0,
        Math.min(
          el.scrollHeight - el.clientHeight,
          (frame ? target : el.scrollTop) + event.deltaY * unit,
        ),
      );
      if (!frame) frame = requestAnimationFrame(settle);
    };
    const key = (event: KeyboardEvent) => {
      if (
        [
          "ArrowUp",
          "ArrowDown",
          "PageUp",
          "PageDown",
          "Home",
          "End",
          " ",
        ].includes(event.key)
      )
        stop();
    };
    el.addEventListener("wheel", wheel, { passive: false });
    el.addEventListener("touchstart", stop, { passive: true });
    el.addEventListener("pointerdown", stop);
    el.addEventListener("keydown", key);
    reduced.addEventListener("change", stop);
    el.scrollTop = 0;
    target = 0;
    update();
    el.focus({ preventScroll: true });
    el.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      stop();
      el.removeEventListener("wheel", wheel);
      el.removeEventListener("touchstart", stop);
      el.removeEventListener("pointerdown", stop);
      el.removeEventListener("keydown", key);
      reduced.removeEventListener("change", stop);
      observer.disconnect();
      el.removeEventListener("scroll", update);
    };
  }, [state, enter]);
  return (
    <div
      className="intro-journey"
      ref={host}
      tabIndex={0}
      aria-label="Explore CtrlZ"
      onWheel={(e) => e.stopPropagation()}
    >
      <div className="journey-distance">
        <div className="journey-stage">
          <header className="film-mast">
            <span>CtrlZ.</span>
            <button type="button" className="journey-skip" onClick={enter}>Enter workspace</button>
            <span>Recovery Control Center</span>
          </header>
          <div className="journey-copy">
            {chapters.map((chapter, index) => (
              <section
                className={"journey-chapter chapter-" + index}
                key={chapter.eyebrow}
                aria-label={chapter.eyebrow}
                aria-hidden={index !== 0}
                inert={index !== 0}
                style={{ opacity: index === 0 ? 1 : 0, visibility: index === 0 ? "visible" : "hidden" }}
              >
                <small>{chapter.eyebrow}</small>
                <h1>
                  {chapter.lines.map((line, i) => (
                    <span
                      key={line}
                      className={index === 0 && i === 1 ? "accent-line" : ""}
                    >
                      {line}
                    </span>
                  ))}
                </h1>
                <p>{chapter.description}</p>
                {chapter.tagline && (
                  <p className="journey-tagline">{chapter.tagline}</p>
                )}
              </section>
            ))}
          </div>
          {/* Keep this footer free of numbered chapter navigation. */}
          <footer className="journey-footer">
            <span>Scroll to explore</span>
          </footer>
        </div>
      </div>
    </div>
  );
}
