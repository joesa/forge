---
trigger: always_on
---

---
globs: ["frontend/**/*.tsx", "frontend/**/*.ts", "frontend/**/*.css"]
---

# Frontend Rules

## CRITICAL — READ THIS FIRST ON EVERY FRONTEND TASK

Before writing ANY frontend code, read DESIGN_BRIEF.md in full.
It contains the exact specification for every component, page, color
value, spacing measurement, font, animation, and interaction in FORGE.
Implement exactly as specified. Do not deviate, simplify, or invent
alternatives.

## Key Design System Values (summary — full spec in DESIGN_BRIEF.md)

Colors (all as CSS custom properties on :root):
  --void: #04040a  --surface: #080812  --panel: #0d0d1f
  --forge: #63d9ff  --ember: #ff6b35  --jade: #3dffa0
  --violet: #b06bff  --gold: #f5c842  --text: #e8e8f0

Fonts (always import from Google Fonts):
  Syne:           all headings and body text
  JetBrains Mono: all code, tags, badges, monospace elements
  Instrument Serif Italic: hero accent text only

Critical sizes (from DESIGN_BRIEF.md — do not change these):
  Top nav height:    62px
  Left sidebar:      220px wide
  Chat panel:        320px wide (editor)
  Activity bar:      48px wide (editor)
  Card border-radius: 12px
  Button height:     40px (default), 48px (lg), 32px (sm)
  Input height:      44px

Background pattern (apply to ALL main pages):
  Grid: 60px × 60px at rgba(99,217,255,0.022)
  Noise: grain texture overlay at ~0.35 opacity
  Orbs: 3-4 blurred radial divs (blur:130px) in violet/cyan/ember

## TypeScript Rules
- Strict mode always — tsconfig.json has strict: true
- No 'any' types. Use 'unknown' with type guards if truly unknown.
- All API response types in frontend/src/types/api.ts
- All component props have explicit TypeScript interfaces

## React Patterns
- Functional components only
- Custom hooks in hooks/ — one hook per concern
- Zustand stores in stores/ — never useState for shared state
- TanStack Query for all server data — never fetch directly in components
- Lazy load all page components with React.lazy()

## Verification after every frontend change
Run: cd frontend && npm run typecheck
Run: cd frontend && npm run lint
Both must pass with zero errors before reporting complete.