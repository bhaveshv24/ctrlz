import { useEffect } from "react";
export function useRecoveryMotion(route: string, ready: boolean) {
  useEffect(() => {
    if (
      !ready ||
      localStorage.getItem("ctrlz-visual-quality") === "Off" ||
      window.matchMedia(
        "(prefers-reduced-motion: reduce), (max-width: 700px), (pointer: coarse)",
      ).matches
    )
      return;
    let disposed = false,
      cleanup: (() => void) | undefined;
    void Promise.all([import("gsap"), import("gsap/ScrollTrigger")])
      .then(([{ gsap }, { ScrollTrigger }]) => {
        if (disposed) return;
        gsap.registerPlugin(ScrollTrigger);
        const media = gsap.matchMedia();
        media.add(
          "(prefers-reduced-motion: no-preference) and (min-width: 701px) and (pointer: fine)",
          () => {
            const targets = document.querySelectorAll(
              ".main-content .section-heading, .main-content .dashboard-bottom, .main-content .continuity-guide, .main-content .code-comparison",
            );
            targets.forEach((target) => {
              gsap.fromTo(
                target,
                { y: 8 },
                {
                  y: 0,
                  duration: 0.45,
                  ease: "power2.out",
                  immediateRender: false,
                  scrollTrigger: {
                    trigger: target,
                    start: "top 94%",
                    toggleActions: "play none none none",
                    once: true,
                  },
                },
              );
            });
          },
        );
        cleanup = () => media.revert();
      })
      .catch(() => {});
    return () => {
      disposed = true;
      cleanup?.();
    };
  }, [route, ready]);
}
