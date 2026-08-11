# Fitsho Landing Premium Storytelling Design

## Scope

Refine the current public Landing only. Preserve routing, onboarding links, authentication, API behavior, i18n, accessibility, and the existing lightweight scroll-progress architecture.

## Story

The final order is cinematic hero, supervised training, supervised nutrition, meal-photo analysis, four-stage planning, body-photo analysis, interactive body intelligence, and a minimal Get Started action. The existing product-preview and adaptive-marketing sections are removed without replacement.

## Visual System

- Ink: `#020b0c`
- Petrol: `#061817`
- Smoked glass: `rgb(8 28 27 / 82%)`
- Mist: `#e8f4f1`
- Aqua: `#50dfce`
- Verification green: existing Fitsho success token

Keep Vazirmatn/Lalezar for Persian and Sora for English/utility text. Reduce oversized headlines after the hero. Use scanning as the signature motion; all other movement remains restrained.

## Components and Motion

`CinematicStory` keeps `landfilm` as one sticky environment. Scroll progress fades hero copy, darkens and blurs video, reveals large schematic training and nutrition documents, draws each verification seal, then dissolves the nutrition document into a `food` photo scan and compact estimated result.

`ProcessStory` remains sticky and scroll-driven but uses less scroll distance. Desktop is a substantial horizontal sequence; mobile is a centered vertical journey. Rings, copy, and connectors activate in strict order without percentage labels.

`BodyIntelligence` becomes a continuous two-state story. It first scans the `analyze` photo, then dissolves into `body`. The result keeps image, soft contour-following region masks, hotspots, SVG connectors, and one HTML callout. Shoulder and back states are mutually exclusive and work by hover, focus, and tap.

Reduced-motion mode shows all final information without scroll transforms or animated scans. Below-fold images are lazy-loaded and keep intrinsic dimensions.

## Responsive Rules

Mobile widths 360, 390, and 430 pixels use intentional single-column compositions. Documents and photos remain prominent, callouts stay inside the body frame, process steps use available width, and no element may create horizontal overflow. Section height follows required story beats rather than fixed full-screen padding.

## Verification

Automated tests cover required section order, removed content, asset use, estimate semantics, onboarding routes, language direction, interaction state, and reduced motion. Final verification includes lint, focused and full tests, production build, and screenshot-based desktop/tablet/360/390/430 inspection in Persian and English.
