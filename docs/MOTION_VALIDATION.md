# Whole-site motion pass — 1 November 2026

Reference supplied by the user: https://activetheory.net/ . Its response requires JavaScript.
Live inspection was attempted but computer/browser use is disabled in Work settings.
This implementation follows the requested cinematic, pointer-responsive direction; it is
not represented as a pixel-accurate or visually verified reproduction of that reference.

## Preserved system

The existing green palette, fonts, routes, forms, login/API wiring and Three.js visual
language remain. No page or component tree was removed. The global recovery world already
supports overview, projects, incidents, repair, demo, evidence and settings; this pass
improves its continuity rather than creating competing canvases on each page.

| Surface | Motion behavior |
|---|---|
| Intro / A / B / C / closing | Sequential non-overlapping text fades; shorter 820svh track; numbered chapter controls and direct workspace entry; existing mouse/touch/keyboard support retained |
| Login | Continuous procedural world; shallow pointer depth on the form; authenticated loading/error states remain functional |
| Overview and project cards | Frame-independent two-axis card tilt with bounded angles; reset on scroll, navigation, blur and pointer exit |
| Incidents / repository repair / Demo Lab / evidence | Existing route-specific 3D geometry and evidence plates; geometry morphs damped in either scrolling direction |
| Settings and navigation | Shortest-arc camera rotation; lower camera plunge; sequential old/new page fades; fallback arrival animations canceled on rapid route changes |
| Dialogs | Brief perspective entrance, stable controls and focus behavior |
| Reduced motion / touch / disabled quality | Existing static visual paths remain; new 3D transforms and entrance animations are disabled by reduced-motion preference |
| GPU context loss | Stops rendering, exposes the static fallback and rebuilds the scene if the context is restored |

## Performance changes

Cinematic GPU simulation: 224×224 particles, down from 320×320 (50,176 versus 102,400).
Balanced mode: 144×144, down from 160×160. Pixel-ratio adaptation, hidden-tab pause and
resource disposal remain. Panel DOM measurements are batched at 30 Hz rather than on every
GPU frame. This reduces work; it is not a measured FPS claim. Pointer smoothing uses elapsed
time; tests cover equal convergence at 30 and 60 fps and bounded tilt/shortest-angle behavior.

## Validation and limits

Frontend production build passed; 29 frontend tests passed before the final context-loss
listener addition, with a final build/test run recorded in the task. Tests cover chapter
visibility across forward/backward scroll samples, smooth opacity, short rotational paths,
frame-independent damping, card tilt limits, accessibility capability policy and existing
functional behavior. No backend changes were made.

Hallmark static inspection ran across the existing frontend: 77 FAIL, 18 REFLEX, 14 WARN.
The report is saved locally in .hallmark/motion-lint.json (ignored). These are outstanding
whole-project style findings, including existing literal colors, labels, metadata and
superseded CSS rules. This is not a clean Hallmark audit. New effective cursor CSS animates
transform rather than width/height, though the static scanner still flags the superseded
original declaration. The existing stylesheet was extended additively to preserve its system.

Browser access is disabled, so the rendered sweep, a live Active Theory comparison, mobile
hardware, actual FPS and forced GPU-loss behavior have not been visually verified. No
cloud deploy or push was performed. Check intro progression and reversal, all dashboard
routes, dialogs, pointer exit, touch and reduced motion after deploying the local commit.
