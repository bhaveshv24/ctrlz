import { useEffect } from "react";

/** Ease coarse wheel steps; preserve native trackpad and nested panel scrolling. */
export function useSmoothWheel() {
  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0, target = 0, last = 0;
    const stop = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      last = 0;
    };
    const settle = (now: number) => {
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60;
      last = now;
      const gap = target - scrollY;
      if (Math.abs(gap) < 0.5) {
        scrollTo({ top: target, behavior: "instant" });
        stop();
        return;
      }
      scrollTo({ top: scrollY + gap * (1 - Math.exp(-dt / 0.11)), behavior: "instant" });
      frame = requestAnimationFrame(settle);
    };
    const wheel = (event: WheelEvent) => {
      if (event.defaultPrevented || reduced.matches || event.ctrlKey || event.metaKey || event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      // Fine trackpad input includes its own momentum.
      if (event.deltaMode === 0 && Math.abs(event.deltaY) < 45) { stop(); return; }
      let element = event.target instanceof Element ? event.target : null;
      if (element?.closest("dialog,[role=dialog],textarea,select,pre,input[type=number]")) { stop(); return; }
      while (element && element !== document.body && element !== document.documentElement) {
        if (element.scrollHeight > element.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(element).overflowY)) { stop(); return; }
        element = element.parentElement;
      }
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
      const delta = event.deltaY * unit;
      if (!delta) return;
      const start = frame && Math.sign(delta) === Math.sign(target - scrollY) ? target : scrollY;
      target = Math.max(0, Math.min(document.documentElement.scrollHeight - innerHeight, start + delta));
      if (target === scrollY && !frame) return;
      event.preventDefault();
      if (!frame) frame = requestAnimationFrame(settle);
    };
    const key = (event: KeyboardEvent) => {
      if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Tab"].includes(event.key)) stop();
    };
    window.addEventListener("wheel", wheel, { passive: false });
    window.addEventListener("keydown", key);
    window.addEventListener("pointerdown", stop, { passive: true });
    window.addEventListener("touchstart", stop, { passive: true });
    window.addEventListener("hashchange", stop);
    window.addEventListener("popstate", stop);
    window.addEventListener("blur", stop);
    window.addEventListener("resize", stop);
    document.addEventListener("visibilitychange", stop);
    reduced.addEventListener("change", stop);
    return () => {
      stop();
      window.removeEventListener("wheel", wheel);
      window.removeEventListener("keydown", key);
      window.removeEventListener("pointerdown", stop);
      window.removeEventListener("touchstart", stop);
      window.removeEventListener("hashchange", stop);
      window.removeEventListener("popstate", stop);
      window.removeEventListener("blur", stop);
      window.removeEventListener("resize", stop);
      document.removeEventListener("visibilitychange", stop);
      reduced.removeEventListener("change", stop);
    };
  }, []);
}
