import { useEffect, useState } from "react";
import { flushSync } from "react-dom";
import { routeValue } from "../navigation";

/** Restore each history entry independently, including repeat visits to a page. */
export function useRouteMotion(onNavigate: () => void) {
  const [route, setRoute] = useState(routeValue);
  useEffect(() => {
    const restoration = history.scrollRestoration;
    history.scrollRestoration = "manual";
    let index = history.state?.ctrlzEntry ?? 0;
    let nextIndex = index;
    history.replaceState({ ...history.state, ctrlzEntry: index }, "");
    const positions = new Map<number, number>();
    let transition: ViewTransition | undefined;
    let disposed = false;
    let revision = 0;
    const listener = () => {
      const request = ++revision;
      const next = routeValue();
      positions.set(index, window.scrollY);
      let destination = history.state?.ctrlzEntry;
      if (typeof destination !== "number") {
        destination = ++nextIndex;
        history.replaceState({ ...history.state, ctrlzEntry: destination }, "");
      }
      const direction = destination < index ? "backward" : "forward";
      index = destination;
      const top = positions.get(index) ?? 0;
      transition?.skipTransition();
      document.documentElement.dataset.navigation = direction;
      const commit = () => {
        if (disposed || request !== revision) return;
        flushSync(() => { setRoute(next); onNavigate(); });
        window.scrollTo({ top, behavior: "instant" });
        document.getElementById("main-content")?.focus({ preventScroll: true });
      };
      if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        transition = document.startViewTransition(commit);
        void transition.finished.catch(() => {});
      } else {
        commit();
        if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
          document.getElementById("main-content")?.animate(
            [{ opacity: 0, transform: `translateX(${direction === "backward" ? -18 : 18}px)` }, { opacity: 1, transform: "translateX(0)" }],
            { duration: 360, easing: "cubic-bezier(.22,1,.36,1)" },
          );
        }
      }
    };
    window.addEventListener("hashchange", listener);
    return () => {
      disposed = true;
      transition?.skipTransition();
      history.scrollRestoration = restoration;
      window.removeEventListener("hashchange", listener);
    };
  }, [onNavigate]);
  return route;
}
