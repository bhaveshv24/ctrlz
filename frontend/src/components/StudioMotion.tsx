import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { damping, pointerDepth } from "./motion-math";
import { useSmoothWheel } from "../hooks/useSmoothWheel";

/** A persistent overlay above the opening journey, workspace and dialogs. */
export default function StudioMotion() {
  useSmoothWheel();
  const canvas = useRef<HTMLCanvasElement>(null);
  const ring = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const surface = canvas.current!;
    const context = surface.getContext("2d");
    if (!context) return;
    const media = matchMedia("(prefers-reduced-motion: reduce), (pointer: coarse)");
    const color = getComputedStyle(document.documentElement).getPropertyValue("--motion-trail-rgb").trim() || "";
    const points = Array.from({ length: 18 }, () => ({ x: 0, y: 0 }));
    let frame = 0, last = 0, movedAt = 0, visible = false;
    let rx = 0, ry = 0;
    let x = 0, y = 0, target: Element | null = null;
    let active: HTMLElement | null = null, card: HTMLElement | null = null;
    const reset = () => {
      active?.style.removeProperty("translate");
      card?.style.removeProperty("--tilt");
      card?.style.removeProperty("--light");
      card?.style.removeProperty("--tilt-x");
      card?.removeAttribute("data-depth-active");
      rx = 0; ry = 0;
      active = null;
      card = null;
    };
    const resize = () => {
      const ratio = Math.min(devicePixelRatio || 1, 1.5);
      surface.width = Math.round(innerWidth * ratio);
      surface.height = Math.round(innerHeight * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    const stop = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      last = 0;
      visible = false;
      context.clearRect(0, 0, innerWidth, innerHeight);
      if (ring.current) ring.current.hidden = true;
      reset();
    };
    const draw = (now: number) => {
      frame = 0;
      if (media.matches || document.hidden || !visible) { stop(); return; }
      const dt = last ? Math.min((now - last) / 1000, 0.05) : 1 / 60;
      last = now;
      const follow = 1 - Math.exp(-dt / 0.026);
      points[0].x = x;
      points[0].y = y;
      for (let i = 1; i < points.length; i++) {
        points[i].x += (points[i - 1].x - points[i].x) * follow;
        points[i].y += (points[i - 1].y - points[i].y) * follow;
      }
      context.clearRect(0, 0, innerWidth, innerHeight);
      const fade = Math.max(0, 1 - (now - movedAt - 90) / 480);
      context.lineCap = "round";
      context.lineJoin = "round";
      for (let i = points.length - 1; i > 0; i--) {
        const weight = 1 - i / points.length;
        context.strokeStyle = `rgba(${color}, ${weight * Math.min(1, fade) * 0.65})`;
        context.lineWidth = 0.5 + weight * 2.8;
        context.beginPath();
        context.moveTo(points[i].x, points[i].y);
        context.lineTo(points[i - 1].x, points[i - 1].y);
        context.stroke();
      }
      if (ring.current) {
        ring.current.hidden = false;
        ring.current.style.transform = `translate3d(${x}px,${y}px,0)`;
        ring.current.dataset.hit = String(!!target?.closest("button,a,input,select,textarea,[role=button]"));
      }
      const nextActive = target?.closest<HTMLElement>(".button:not(:disabled)") ?? null;
      const nextCard = target?.closest<HTMLElement>(".signal-card,.metric,.scenario-card,.main-content .card,.login-form,.project-dialog,.scene-plate") ?? null;
      if (active !== nextActive || card !== nextCard) { reset(); active = nextActive; card = nextCard; }
      if (document.documentElement.dataset.motion === "on") {
        // Read geometry before applying styles; pointer events only schedule this frame.
        const buttonRect = active?.getBoundingClientRect();
        const cardRect = card?.getBoundingClientRect();
        if (active && buttonRect) active.style.translate = `${(x - buttonRect.left - buttonRect.width / 2) * 0.055}px ${(y - buttonRect.top - buttonRect.height / 2) * 0.1}px`;
        if (card && cardRect) {
          const offset = Math.max(0, Math.min(1, (x - cardRect.left) / cardRect.width));
          const depth = pointerDepth((offset - 0.5) * 2, ((y - cardRect.top) / cardRect.height - 0.5) * 2);
          const follow = damping(dt, 12);
          rx += (depth.x - rx) * follow;
          ry += (depth.y - ry) * follow;
          card.dataset.depthActive = "true";
          card.style.setProperty("--tilt", `${ry}deg`);
          card.style.setProperty("--tilt-x", `${rx}deg`);
          card.style.setProperty("--light", `${offset * 100}%`);
        }
      } else reset();
      if (fade > 0) frame = requestAnimationFrame(draw);
      else { last = 0; reset(); }
    };
    const move = (event: PointerEvent) => {
      if (media.matches || event.pointerType === "touch") return;
      x = event.clientX;
      y = event.clientY;
      target = event.target instanceof Element ? event.target : null;
      movedAt = performance.now();
      if (!visible) {
        points.forEach((point) => { point.x = x; point.y = y; });
        visible = true;
      }
      if (!frame) frame = requestAnimationFrame(draw);
    };
    const scroll = () => { target = null; reset(); };
    const leave = (event: PointerEvent) => { if (!event.relatedTarget) stop(); };
    resize();
    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerout", leave);
    document.addEventListener("visibilitychange", stop);
    window.addEventListener("blur", stop);
    window.addEventListener("resize", resize);
    window.addEventListener("hashchange", reset);
    window.addEventListener("scroll", scroll, {passive: true});
    window.addEventListener("ctrlz-quality", stop);
    media.addEventListener("change", stop);
    return () => {
      stop();
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerout", leave);
      document.removeEventListener("visibilitychange", stop);
      window.removeEventListener("blur", stop);
      window.removeEventListener("resize", resize);
      window.removeEventListener("hashchange", reset);
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("ctrlz-quality", stop);
      media.removeEventListener("change", stop);
    };
  }, []);
  return createPortal(
    <div className="pointer-overlay" aria-hidden="true">
      <canvas ref={canvas} className="pointer-trail" />
      <span ref={ring} hidden className="studio-cursor" />
    </div>, document.body,
  );
}
