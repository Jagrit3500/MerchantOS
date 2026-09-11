# MerchantOS design system

## Direction

MerchantOS uses an editorial financial command-desk aesthetic: a warm paper-like canvas, deep ink typography, a restrained evergreen signal color, and calm data surfaces. The workspace prioritizes evidence, money, and next actions over decorative effects.

## Typography

- Editorial headings: Newsreader, weight 500, with Georgia as the local fallback.
- Interface text and financial figures: DM Sans, with Segoe UI as the local fallback.
- Page titles use sentence case, tight tracking, and compact line height.
- Small operational labels use uppercase and wider tracking.
- Financial values use tabular figures; transaction IDs use a monospace face.

## Palette

| Role | Value |
| --- | --- |
| Canvas | `#F3F1EB` |
| Light surface | `#FFFEFB` / `#F8F7F2` |
| Navigation rail | `#15251F` |
| Heading | `#17211D` |
| Body | `#43504A` |
| Accent | `#176B50` |
| Accent hover | `#0D4E3A` |
| Brand detail | `#F5C85C` |
| Success | `#176B50` |
| Warning | `#95610C` |
| Danger | `#A53D34` |

Palette values are design tokens, not runtime merchant configuration.

## Composition

- The landing page contains exactly a hero and an about section.
- Desktop navigation is horizontal; mobile navigation uses an accessible full-screen menu.
- The Streamlit workspace uses one compact dark rail on every page. It expands on hover or keyboard focus and becomes a bottom navigation on small screens.
- Main content is capped at 1380px and uses responsive `clamp()` spacing.
- Panels and financial cards use warm flat surfaces, thin dividers, moderate radii, and restrained shadows.
- Primary buttons use evergreen with clear, sentence-case labels.
- Tables scroll horizontally on narrow screens.

## Page patterns

### Landing

Video-led hero, six-line staircase heading, primary workspace action, followed by a concise two-column product explanation. Runtime configuration supplies video sources and application destinations.

### Command center

Zero-state recovery pulse, three workflow cards, latest real exception ledger, and local service status. Demonstration data remains isolated from command-center metrics.

### KYC diagnosis

Three-stage journey, one question at a time, contextual guidance, then action-plan, support-request, and evidence tabs.

### Reconciliation

Upload/manual/sample entry modes, grouped exceptions, full ledger, balanced financial equation, editable recovery request, and CSV export.

### Escalation

Case details, evidence checklist, editable correspondence, filing guidance, and elapsed-time recommendation.

## Interaction and accessibility

- Keep one clear primary action per stage.
- Preserve native form labels and keyboard behavior.
- Provide visible focus rings.
- Mark decorative video/SVG content as hidden from assistive technology.
- Escape dynamic strings before inserting them into raw HTML.
- Keep navigation destinations labelled with titles while the desktop rail is collapsed.
- Respect reduced-motion settings.
- Never make video playback a prerequisite for navigation or core workflow use.

## Implementation ownership

- `landing.css`: public-site styling and responsive behavior.
- `src/styles.css`: Streamlit workspace styling.
- `src/ui.py`: shared workspace components.
- `.streamlit/config.toml`: native widget theme.
- `index.html`, `home.py`, and `Agent1`–`Agent3/app.py`: page composition.

Functional/business rules belong in Python and shared configuration, not in the design layer.
