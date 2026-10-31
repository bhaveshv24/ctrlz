import IntroJourney from "./IntroJourney";
import { useCallback, useEffect, useRef, useState } from "react";

export function sceneEligible(
  width: number,
  reduced: boolean,
  coarse: boolean,
  cores?: number,
  memory?: number,
) {
  return (
    width > 700 &&
    !reduced &&
    !coarse &&
    (cores === undefined || cores > 2) &&
    (memory === undefined || memory > 2)
  );
}
const preference = () =>
  localStorage.getItem("ctrlz-visual-quality") || "Cinematic";
export function QualitySetting() {
  const [value, set] = useState(preference);
  return (
    <label className="quality-setting">
      Visual quality
      <select
        value={value}
        onChange={(event) => {
          const next = event.target.value;
          localStorage.setItem("ctrlz-visual-quality", next);
          set(next);
          window.dispatchEvent(new Event("ctrlz-quality"));
        }}
      >
        {["Cinematic", "Balanced", "Off"].map((q) => (
          <option key={q}>{q}</option>
        ))}
      </select>
    </label>
  );
}
export default function RecoveryScene({
  children,
}: {
  children: React.ReactNode;
}) {
  const [opening, setOpening] = useState(() => new URLSearchParams(window.location.search).get("intro") === "1");
  const [departing, setDeparting] = useState(false);
  const departure = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (departure.current) clearTimeout(departure.current); }, []);
  const finish = useCallback(() => {
    if (departure.current) return;
    setDeparting(true);
    departure.current = setTimeout(() => {
      intro.current.active = false;
      setOpening(false);
      setDeparting(false);
      departure.current = null;
    }, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 380);
  }, []);
  useEffect(() => {
    const restart = () => {
      if (intro.current.rewinding || departure.current) return;
      const reveal = () => {
        intro.current.progress = 0;
        intro.current.active = true;
        setOpening(true);
      };
      intro.current.reveal = reveal;
      if (
        document.documentElement.dataset.motion !== "on" ||
        !host.current?.dataset.ready
      ) {
        reveal();
        return;
      }
      intro.current.rewinding = true;
      intro.current.rewindElapsed = 0;
    };
    window.addEventListener("ctrlz-replay-intro", restart);
    return () => window.removeEventListener("ctrlz-replay-intro", restart);
  }, []);
  useEffect(() => {
    if (!opening)
      document
        .querySelector<HTMLElement>("#email, #main-content")
        ?.focus({ preventScroll: true });
  }, [opening]);

  const intro = useRef({
    active: opening,
    progress: 0,
    rewinding: false,
    rewindElapsed: 0,
    reveal: () => {},
  });
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = matchMedia(
      "(prefers-reduced-motion: reduce), (pointer: coarse), (max-width: 700px)",
    );
    let generation = 0,
      dispose: (() => void) | undefined;
    async function start() {
      const id = ++generation;
      if (intro.current.rewinding) {
        intro.current.rewinding = false;
        intro.current.reveal();
      }
      dispose?.();
      dispose = undefined;

      const enabled =
        preference() !== "Off" &&
        sceneEligible(
          innerWidth,
          media.matches,
          false,
          navigator.hardwareConcurrency,
          (navigator as Navigator & { deviceMemory?: number }).deviceMemory,
        );
      document.documentElement.dataset.motion = enabled ? "on" : "off";
      if (!enabled) {
        return;
      }

      try {
        const { mountStudio } = await import("./recovery-scene");
        if (id !== generation || !host.current) return;

        dispose = mountStudio(
          host.current,
          preference() === "Cinematic",
          () => {},
          intro.current,
        );
      } catch {
        if (generation === id) {
          document.documentElement.dataset.motion = "off";
        }
      }
    }
    void start();
    media.addEventListener("change", start);
    window.addEventListener("ctrlz-quality", start);
    return () => {
      generation++;
      dispose?.();
      media.removeEventListener("change", start);
      window.removeEventListener("ctrlz-quality", start);
    };
  }, []);
  return (
    <>
      <div className="studio" ref={host} aria-hidden="true" />
      {opening && <div className="journey-layer" data-departing={departing}>
        <IntroJourney state={intro.current} enter={finish} />
      </div>}
      <div
        className="world-interface"
        inert={opening}
        aria-hidden={opening || undefined}
        data-opening={opening}
      >
        {children}
      </div>
    </>
  );
}
