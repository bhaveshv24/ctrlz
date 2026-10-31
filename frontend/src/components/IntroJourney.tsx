import { useLayoutEffect, useRef } from "react";
export type JourneyState = { active: boolean; progress: number };
const chapters = [
  {
    eyebrow: "INTRODUCING CTRLZ",
    lines: ["You built it.", "We keep it alive."],
    description:
      "AI made building software easier than ever. CtrlZ brings autonomous recovery to what happens after — detecting failures, investigating problems, and verifying solutions.",
    tagline: "Build like a team. Recover without one.",
  },
  {
    eyebrow: "Scenario A / Development recovery",
    lines: ["A broken build."],
    description:
      "Your AI-assisted development stops halfway. CtrlZ reconstructs the project state, identifies unfinished work, and helps you continue development without starting over.",
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
    eyebrow: "THE RECOVERY LAYER",
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
  const jump = useRef<(chapter: number) => void>(() => {});
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
      el.querySelectorAll(".journey-stops button").forEach((button, index) => {
        button.setAttribute("aria-current", String(index === active));
      });
      panels.forEach((panel, index) => {
        const distance = position - index,
          opacity = Math.max(
            0,
            Math.min(1, (0.7 - Math.abs(distance)) / 0.4),
          );
        panel.style.opacity = String(opacity * opacity * (3 - 2 * opacity));
        panel.style.transform = `translate3d(0,${-distance * 48}px,0)`;
        panel.inert = index !== active;
        panel.setAttribute("aria-hidden", String(index !== active));
        panel.style.visibility = opacity > 0 ? "visible" : "hidden";
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
    jump.current = (chapter) => {
      target = Math.max(0, Math.min(4, chapter)) / 4.25 * (el.scrollHeight - el.clientHeight);
      if (reduced.matches) { el.scrollTop = target; update(); }
      else if (!frame) frame = requestAnimationFrame(settle);
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
            <span>Recovery Control Center</span>
          </header>
          <div className="journey-copy">
            {chapters.map((chapter, index) => (
              <section
                className={"journey-chapter chapter-" + index}
                key={chapter.eyebrow}
                aria-label={chapter.eyebrow}
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
          <footer className="journey-footer">
            <span>SCROLL TO EXPLORE</span>
            <nav className="journey-stops" aria-label="Introduction chapters">
              {chapters.map((chapter, index) => (
                <button key={chapter.eyebrow} type="button"
                  aria-label={`Go to ${chapter.eyebrow}`}
                  onClick={() => jump.current(index)}>
                  {String(index + 1).padStart(2, "0")}
                </button>
              ))}
            </nav>
            <button className="journey-skip" type="button" onClick={enter}>
              Enter workspace <span aria-hidden="true">↗</span>
            </button>
          </footer>
        </div>
      </div>
    </div>
  );
}
