# Final interface refinement

Polish of the existing CtrlZ app, using Hallmark. No routes, API handlers, forms,
permission checks, animations or supported operations were removed. No statistics,
customer claims or testimonials were invented.

## Shared system

The green recovery scene remains the signature. Workspace pages use a capped
1440px content measure, 24px panel gaps, 36px page titles (28px on small screens),
14–16px working text, 44px action targets and instant keyboard focus. Panels use
quiet surfaces without stacked decorative shadows. Dialog refinements target the
actual shared `.dialog` component. Existing palette literals were lifted into root
tokens without changing their values, and body labels no longer use tracked capitals.

## Copy changes

- Overview: “Back to building.” → “Workspace overview”.
- Incidents: “Every incident has a story.” → “Incidents”.
- Projects: “Their systems. Your control.” → “Projects”.
- Evidence: “The proof travels with you.” → “Evidence library”.
- Settings: “Know what’s connected.” → “Workspace settings”.
- Demo: “Your target. A provable recovery.” → “Demo Lab”.
- Login: “Back to building.” → “Sign in to CtrlZ” / “Create your account”.
- Overview sections: “Health is more than a green homepage.” → “Project health”;
  “What happened. What happens next.” → “Recent incidents”.
- Runtime incident: “Observed failure. Reviewable response.” → “Runtime incident”;
  the incident reference remains visible.
- Demo history: “The rehearsal record.” → “Rehearsal history”.

Repeated decorative section labels were removed where the heading supplies the
same context. Metadata uses slashes instead of repeated middle dots. Consent,
authorization and verification limitations remain intact. The intro accent line
and green 3D motion are retained at the user's explicit request.

## Verification and limits

Production build and all 59 frontend tests passed without changing tests. Hallmark
source lint was run across shared CSS, App, components and pages. The remaining
sticky-header finding is a static false positive: the intro stage and workspace
header belong to different scroll contexts. The intro accent is recorded as an
explicit retained-brand waiver. Remaining warnings include deliberately wrapping
long controls, legacy surface composition, and checks needing rendered inspection.

The independent finish review found and corrected a missing dialog selector,
semantic-text overrides, light-mode focus contrast, and undersized dialog guidance.
Browser access is disabled in Work settings, so no fresh screenshots, rendered
contrast measurements, or mobile visual review are claimed. The real product is
the visual material; no replacement image assets or placeholder photos are needed.
