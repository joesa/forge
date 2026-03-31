# FORGE — UI/UX Design Brief for Antigravity
## Complete specifications for all 22 routes, components, and interactions
## Source: FORGE_STITCH_V3.md — adapted for Antigravity agent consumption

> **INSTRUCTION TO ANTIGRAVITY**: Implement every screen exactly as specified
> in this document. Every color value, spacing measurement, typography choice,
> component state, animation, and interaction pattern must match precisely.
> This is not a suggestion — it is the contract. Do not invent alternatives.

---

## 1. DESIGN SYSTEM — DO NOT DEVIATE

### Color Tokens (use as CSS custom properties)
```css
--void:        #04040a;   /* page background */
--surface:     #080812;   /* code areas, modals */
--panel:       #0d0d1f;   /* cards, sidebars */
--card:        #111125;   /* nested cards */

--border:      rgba(255,255,255,0.06);
--border-bright: rgba(99,217,255,0.22); /* hover/active */

--forge:       #63d9ff;   /* primary — CTAs, active states, links */
--forge-dim:   rgba(99,217,255,0.10);
--ember:       #ff6b35;   /* alerts, secondary actions, warnings */
--ember-dim:   rgba(255,107,53,0.10);
--gold:        #f5c842;   /* highlights, special states */
--gold-dim:    rgba(245,200,66,0.08);
--jade:        #3dffa0;   /* success, online, connected, resolved */
--jade-dim:    rgba(61,255,160,0.08);
--violet:      #b06bff;   /* AI indicators, agent states */
--violet-dim:  rgba(176,107,255,0.10);

--text:        #e8e8f0;
--muted:       rgba(232,232,240,0.42);
--faint:       rgba(232,232,240,0.15);
```

### Typography — Google Fonts
```
Import:
  Syne:             wght 400;600;700;800  (ALL headings and body)
  JetBrains Mono:   wght 300;400;500;700  (code, tags, badges, mono)
  Instrument Serif: ital 1                (hero accent only)

Font scale:
  Hero title:   clamp(52px,7vw,96px)  wt:800  ls:-3px   lh:0.92
  Page title:   38-42px               wt:800  ls:-1.5px
  Section h2:   24-28px               wt:700  ls:-0.5px
  Card title:   14px                  wt:700
  Body:         14-16px               wt:400  lh:1.7
  Caption/label:11-12px               wt:600  ls:0.5-1px (uppercase)
  Code:         12px                  JetBrains Mono
  Tag/badge:    9-10px                JetBrains Mono  uppercase  ls:1px
```

### Spacing and Sizing
```
Page padding horizontal: 36-40px
Section padding vertical: 72-80px
Card padding:            22-28px
Card border-radius:      12px
Button heights:          40px (default), 48px (lg), 32px (sm)
Button border-radius:    8px
Input height:            44px
Input border-radius:     8px
Top navigation height:   62px
Activity bar width:      48px
File tree sidebar width: 220px
Chat panel width:        320px
```

### Background Decoration Pattern
```
All main pages use this combination:
  1. Grid: background-image: linear-gradient(rgba(99,217,255,0.022) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(99,217,255,0.022) 1px, transparent 1px)
           background-size: 60px 60px
  2. Noise texture overlay: subtle grain, opacity 0.3-0.4, pointer-events: none
  3. Glow orbs: 3-4 absolutely positioned divs, border-radius:50%, 
     filter:blur(130px), colors: violet/cyan/ember at very low opacity
     (e.g. rgba(99,217,255,0.04) for cyan orb)

Position all orbs and grid as absolute/fixed behind all content (z-index: 0)
All content positioned relative with z-index: 1
```

### Component Patterns

**Cards**
```
Base:   background:#0d0d1f  border:1px solid rgba(255,255,255,0.06)  radius:12px  padding:22px
Hover:  border-color → rgba(99,217,255,0.22)  transform:translateY(-2px)  transition: 200ms

Accent variants (use for feature/path cards):
  .fa (forge): bg linear-gradient(135deg, rgba(99,217,255,0.04), #0d0d1f)
               border: rgba(99,217,255,0.16)
  .ea (ember): bg linear-gradient(135deg, rgba(255,107,53,0.04), #0d0d1f)
               border: rgba(255,107,53,0.16)
  .ja (jade):  bg linear-gradient(135deg, rgba(61,255,160,0.04), #0d0d1f)
               border: rgba(61,255,160,0.16)
  .va (violet):bg linear-gradient(135deg, rgba(176,107,255,0.04), #0d0d1f)
               border: rgba(176,107,255,0.16)
```

**Buttons**
```
Primary:   bg:#63d9ff  color:#04040a  weight:700  radius:8px
           hover: opacity:0.88  transform:translateY(-1px)
Secondary: bg:transparent  border:1px solid rgba(99,217,255,0.22)  color:#63d9ff
           hover: bg:rgba(99,217,255,0.08)
Ghost:     bg:transparent  border:1px solid rgba(255,255,255,0.08)  color:rgba(232,232,240,0.5)
           hover: color:#e8e8f0  bg:rgba(255,255,255,0.04)
Danger:    bg:rgba(255,107,53,0.10)  border:rgba(255,107,53,0.22)  color:#ff6b35
```

**Tags/Badges**
```
All tags: font-family:JetBrains Mono  font-size:9px  padding:2px 7px  radius:4px  letter-spacing:0.5px

forge tag: bg:rgba(99,217,255,0.10)   color:#63d9ff  border:rgba(99,217,255,0.18)
ember tag: bg:rgba(255,107,53,0.10)   color:#ff6b35  border:rgba(255,107,53,0.18)
jade tag:  bg:rgba(61,255,160,0.08)   color:#3dffa0  border:rgba(61,255,160,0.18)
violet tag:bg:rgba(176,107,255,0.10)  color:#b06bff  border:rgba(176,107,255,0.18)
gold tag:  bg:rgba(245,200,66,0.08)   color:#f5c842  border:rgba(245,200,66,0.18)
muted tag: bg:rgba(255,255,255,0.05)  color:rgba(232,232,240,0.5)  border:rgba(255,255,255,0.08)
```

**Inputs**
```
Background: rgba(255,255,255,0.04)
Border:     1px solid rgba(255,255,255,0.08)
Radius:     8px
Height:     44px
Color:      #e8e8f0
Font:       Syne 13px
Placeholder:rgba(232,232,240,0.30)
Focus:      border-color → rgba(99,217,255,0.30)  outline:none
```

**Section label pattern (used above section headings)**
```
Font: JetBrains Mono 10px, letter-spacing:3px, text-transform:uppercase, color:#ff6b35
Layout: flex, align-items:center, gap:8px
Dot before text: 6px circle, background:#ff6b35
```

**Status badges**
```
Live:     color:#3dffa0  bg:rgba(61,255,160,0.1)   border:rgba(61,255,160,0.2)   text:"● Live"
Building: color:#63d9ff  bg:rgba(99,217,255,0.1)   border:rgba(99,217,255,0.2)   text:"◎ Building"  + pulse animation
Draft:    color:rgba(232,232,240,0.5)  bg:rgba(255,255,255,0.05)  border:rgba(255,255,255,0.1)  text:"✦ Draft"
Error:    color:#ff6b35  bg:rgba(255,107,53,0.1)   border:rgba(255,107,53,0.2)   text:"⚠ Error"
```

**Hex logo mark**
```
Width: 26px  Height: 26px
Background: linear-gradient(135deg, #63d9ff, #b06bff)
Clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)
```

**Logo wordmark text**
```
Font: Syne 800  font-size:18px  letter-spacing:-0.5px
Background: linear-gradient(135deg, #63d9ff, #b06bff)
-webkit-background-clip: text
-webkit-text-fill-color: transparent
```

**Toggle switch**
```
Track:  width:38px  height:20px  radius:10px
        Off: background:rgba(255,255,255,0.12)
        On:  background:#63d9ff
        Transition: background 200ms
Dot:    width:16px  height:16px  radius:50%  background:#fff  top:2px
        Off: left:2px  On: left:20px  transition:left 200ms
```

**Animations**
```
Pulse (for building/running states): keyframe 0%,100%{opacity:1} 50%{opacity:0.4} duration:1.8s ease-in-out infinite
Spin (for loading rings):            keyframe to{transform:rotate(360deg)} duration:1s linear infinite
Fade-in (for page/card transitions): keyframe from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} 280ms ease
Jade pulse (for LIVE indicator):     keyframe 0%,100%{box-shadow:0 0 0 0 rgba(61,255,160,0.4)} 50%{box-shadow:0 0 0 5px rgba(61,255,160,0)} 2s ease-in-out infinite
```

---

## 2. GLOBAL NAVIGATION

### Top Nav (authenticated pages)
```
Height: 62px
Background: rgba(4,4,10,0.88) with backdrop-filter:blur(24px)
Border-bottom: 1px solid rgba(255,255,255,0.06)
Position: sticky, top:0, z-index:100
Padding: 0 28px
Layout: flex, align-items:center, gap:14px

Left section:
  [Hex logo mark (26px)] [FORGE wordmark gradient]
  When in project context: [│ divider] [Project name ▼ — 12px, rgba(232,232,240,0.55), cursor:pointer]
  When in editor: [○ main — branch chip, 10px JetBrains Mono, rounded, muted bg]

Right section:
  [● All systems normal — jade, 9px JetBrains Mono]
  [When in editor: ● 2 errors ember count]
  [Vertical 1px divider]
  [User avatar: 32px circle, gradient cyan→violet, initials in void color]

Landing/auth nav (simplified):
  Left: [Hex + FORGE wordmark]
  Right: [Log In — ghost sm button] [Start Building → — primary sm button]
```

### Left Sidebar (dashboard/settings pages only, 220px)
```
Position: fixed, left:0, top:62px, bottom:0 (leave 50px for prototype nav)
Width: 220px
Background: rgba(4,4,10,0.70)
Border-right: 1px solid rgba(255,255,255,0.06)
Padding: 14px 10px
Overflow-y: auto
Z-index: 100

Top section (pad 8px 10px 14px, border-bottom):
  [Avatar 34px circle gradient] [Display name 12px 700wt] [PRO badge — forge tag]

Navigation items (each 38px, 8px 11px padding, radius:6px, margin-bottom:2px):
  🏠 Dashboard  → /dashboard
  📁 Projects   → /projects
  💡 Ideate     → /ideate
  [1px divider]
  "SETTINGS" label (9px JetBrains Mono, uppercase, rgba(232,232,240,0.20), non-clickable)
  ↳ 👤 Profile          → /settings/profile    (padding-left:32px)
  ↳ 🤖 AI Providers     → /settings/ai-providers
  ↳ ⚡ Model Routing    → /settings/model-routing
  ↳ 🔗 Integrations     → /settings/integrations
  ↳ 🔑 API Keys         → /settings/api-keys
  ↳ 🔒 Security         → /settings/security
  ↳ 💳 Billing          → /settings/billing

Item states:
  Default: color:rgba(232,232,240,0.45)
  Hover:   color:#e8e8f0  bg:rgba(255,255,255,0.03)
  Active:  color:#63d9ff  bg:rgba(99,217,255,0.10)
           border-left:2px solid #63d9ff  border-radius:0 6px 6px 0
           margin-left:-1px  padding-left:12px

Bottom section (border-top, padding-top:12px):
  "TOKEN USAGE" — 9px JetBrains Mono, rgba(232,232,240,0.30)
  Progress bar: height:3px, bg:rgba(255,255,255,0.07), radius:2px
    Fill: width:42%, background:#63d9ff, radius:2px
  "847k / 2M tokens" — 9px JetBrains Mono, rgba(232,232,240,0.30), margin-top:4px
```

---

## 3. ALL 22 ROUTES — COMPLETE SPECIFICATIONS

---

### `/` — Landing Page

**Layout**: Full-width, single column, void background + grid + noise + orbs

**Section 1 — Hero (100vh)**
```
Orbs: violet 700px top-right | cyan 550px bottom-left | ember 350px center-ish
Simplified top nav (not AppShell): logo left + [Log In ghost] [Start Building → primary]

Content (max-width:1160px, margin:0 auto, padding:0 32px, pt:100px, pb:72px):

  Eyebrow:
    [28px horizontal line — #63d9ff]
    ["AI-Native Development Platform" — 10px JetBrains Mono, ls:3px, uppercase, #63d9ff]

  h1 (hero title — clamp(48px,6.5vw,86px), wt:800, ls:-3px, lh:0.92, color:#e8e8f0):
    Line 1: "Build anything."
    Line 2: [Instrument Serif italic #63d9ff "Ship"] [#ff6b35 "everything."]

  Subtitle (16px, rgba(232,232,240,0.45), max-w:580px, lh:1.7, mb:34px):
    "FORGE takes your idea through a C-Suite of AI agents, a 10-layer
     reliability system, and delivers a live production application —
     zero broken builds, guaranteed."

  CTA row (display:flex, gap:11px, flex-wrap:wrap):
    [Start Building → — primary lg (h:48px, px:28px)]
    [💡 Generate an Idea — ghost lg]

  Stats row (display:flex, gap:36px, pt:40px, border-top:1px solid rgba(255,255,255,0.06), mt:52px, flex-wrap:wrap):
    Each stat: big number + label below
    Numbers: 28px, wt:800, ls:-1px, gradient(135deg, #63d9ff, #3dffa0), bg-clip:text
    Labels: 10px JetBrains Mono, rgba(232,232,240,0.42)
    Values: ["26+" AI Agents] ["10" Reliability Layers] ["12" Validation Gates]
            ["0" Broken Builds] ["1M+" Req/Day] ["<700ms" Preview]
```

**Section 2 — Three Paths** (bg:#0d0d1f, border-top, py:72px)
```
Section tag: ● Core Flow (ember)
h2: "Every path leads to production" (clamp(24px,3.2vw,34px), wt:800, ls:-1.2px)

3-column card grid (gap:12px):
  Card 1 .fa accent: icon ✍️ (22px, mb:9px)
    title "Direct Prompt" (13px, 700wt)
    desc "Describe your app. AI optionally enriches it before the pipeline."
    tags: [forge "Instant"] [jade "AI Enhancement"]
    → onClick navigate to /projects/new

  Card 2 .va accent: icon 💡
    title "AI Ideation Engine"
    desc "8 adaptive questions, all skippable → 5 unique high-value ideas."
    tags: [violet "5 Ideas"] [gold "Skippable Q&A"] [ember "Private 7d"]
    → onClick navigate to /ideate

  Card 3 .ea accent: icon 🎲
    title "Full AI Generation"
    desc "Zero input. AI generates ideas from live market signals."
    tags: [ember "Zero Input"] [forge "Market-Aware"]
    → onClick navigate to /ideate
```

**Section 3 — Preview System Highlight** (bg with forge tint, border, radius:16px, p:36px, mb:72px)
```
2-column layout (gap:32px, align-items:center):
  Left:
    Section tag: ● Live Preview System (jade)
    h2: "Watch your app take shape in real time" (26px, 800wt)
    Checklist (display:flex flex-col gap:9px):
      ✓ (jade) "HMR live reload <700ms after file save"
      ✓ "Build snapshot timeline — 10 screenshots per build"
      ✓ "Click-to-annotate overlay with AI context"
      ✓ "Dev console (logs, network, errors, source maps)"
      ✓ "Shareable preview links (24h, no auth required)"
    [See Editor Preview → secondary button, mt:20px]

  Right: preview pane mini-mockup (see prototype for reference)
```

**Section 4 — Pricing** (py:72px)
```
Section tag: ● Pricing (ember)
h2: "Simple, transparent pricing" (30px, 800wt, ls:-1.2px, mb:28px)

3-column card grid:
  Free card ($0/month):  standard card
  Pro card ($49/month):  FEATURED — border:2px solid #63d9ff, transform:scale(1.02)
                         bg: linear-gradient(135deg, rgba(99,217,255,0.06), #0d0d1f)
  Enterprise (Custom):   standard card

Each card:
  Plan name (14px, 700wt, color:#e8e8f0)
  [Featured only: forge tag "MOST POPULAR"]
  Price (30px, 800wt, color:#63d9ff, ls:-1px)
    + "/month" suffix (14px, wt:400, rgba(232,232,240,0.40))
  Feature list (display:flex flex-col gap:5px, mt:14px, mb:18px):
    Each: [✓ jade] [feature text 11px, rgba(232,232,240,0.50)]
  CTA button (full width)
```

---

### `/login` — Login Page

**Layout**: Full viewport centered, glow orbs in bg, simplified top nav (logo only)

**Auth card** (bg:#0d0d1f, border:1px solid rgba(255,255,255,0.08), radius:16px, padding:42px, max-w:440px, w:100%)
```
Top (text-align:center, mb:28px):
  [Hex logo mark — centered, display:flex, justify-content:center]
  [FORGE wordmark — gradient, 22px, 800wt, mt:10px]
  h1: "Welcome back" (22px, 800wt, color:#e8e8f0, mt:16px)
  p: "Sign in to your workspace" (12px, rgba(232,232,240,0.40), mt:5px)

Form (display:flex flex-col gap:13px):
  Email field:
    label: "EMAIL ADDRESS" (10px JetBrains Mono, uppercase, ls:1px, rgba(232,232,240,0.40), mb:6px)
    input (full width, standard input styles)
  Password field:
    label: "PASSWORD"
    input type=password + show/hide toggle (eye icon, right side)
  Remember me row (display:flex, justify-content:space-between):
    [checkbox + "Remember me" — 11px, rgba(232,232,240,0.45)]
    ["Forgot password?" — 11px, color:#63d9ff, cursor:pointer]
  [Sign In → primary button, full width, height:48px, mt:4px]

Divider: [1px line] "or continue with" [1px line] (rgba(232,232,240,0.25), 11px)

OAuth buttons (display:flex gap:9px):
  [🐙 GitHub — ghost button, flex:1]
  [G Google — ghost button, flex:1]

Footer:
  "Don't have an account?" [Create account → — forge color, cursor:pointer]
  → onClick navigate to /register
```

---

### `/register` — Register Page

**Same layout as login, card width 480px**
```
Form additions vs login:
  [Display name input — FIRST field]
  Password strength meter (below password input):
    4 segments, height:3px, radius:2px, gap:4px
    Strength coloring by length:
      < 8 chars: all gray rgba(255,255,255,0.08)
      8-11:  1 segment #63d9ff
      12-15: 2 segments #63d9ff
      16+:   4 segments #63d9ff
  [Terms checkbox: "I agree to the Terms of Service and Privacy Policy" — 11px]
  [Create Account → button]
```

---

### `/onboarding` — Onboarding (3 steps)

**Layout**: Full viewport centered, simplified top nav (logo + "Step X of 3" on right)

**Progress indicator** (display:flex, gap:6px, justify-content:center, mb:28px):
```
Each step = pill component:
  Done: width:8px, height:8px, radius:50%, bg:#3dffa0
  Current: width:28px, height:8px, radius:4px, bg:#63d9ff
  Future: width:8px, height:8px, radius:50%, bg:rgba(255,255,255,0.12)
  Transition: all 0.25s ease on width and background
```

**Step 1 — Welcome** (card, max-w:580px, padding:36px)
```
Content (text-align:center):
  Icon: "⬡" hex emoji or SVG hex, fontSize:44px, mb:14px
  h2: "Welcome to FORGE" (26px, 800wt, ls:-0.8px, mb:9px, color:#e8e8f0)
  p: "The AI-native platform that builds production apps for you.
      Let's get you set up in 2 minutes." (13px, rgba(232,232,240,0.45), lh:1.7)
[Let's go → primary button, full width, h:48px]
```

**Step 2 — How to start** (same card)
```
h2: "How do you want to start?" (22px, 800wt, mb:5px)
p: "You can always change this later" (12px, rgba(232,232,240,0.40), mb:20px)

3 option cards (display:flex flex-col gap:9px, mb:22px):
  Each: display:flex, align-items:center, gap:13px, textAlign:left
  Layout: [icon 22px] [title 13px 700wt + desc 11px muted] [✓ forge right when selected]
  
  Default: bg:rgba(255,255,255,0.03), border:2px solid rgba(255,255,255,0.06), radius:10px, padding:13px 16px
  Selected: border-color:#63d9ff, bg:rgba(99,217,255,0.08)
  Hover: border-color:rgba(99,217,255,0.25)

  Options:
    ✍️ "I have an idea" / "Describe my app and FORGE builds it"
    💡 "Help me find an idea" / "Answer questions, get 5 AI-generated ideas"
    🎲 "Surprise me" / "AI generates ideas with zero input from me"

[Continue → primary button, full width, h:48px]
```

**Step 3 — Connect AI** (same card)
```
h2: "Connect an AI provider" (22px, 800wt, mb:5px)
p: "FORGE includes Anthropic Claude on Free tier. Add your keys for
    unlimited usage." (12px, rgba(232,232,240,0.40), mb:20px)

3 provider rows (display:flex flex-col gap:8px, mb:22px):
  Each: display:flex, align-items:center, gap:11px
        bg:rgba(255,255,255,0.03), border:1px solid rgba(255,255,255,0.07)
        radius:8px, padding:11px 13px
  Layout: [logo 18px] [name 12px 600wt + note 10px muted flex:1] [badge or button]

  Anthropic: "FORGE Default — no key needed" → [jade tag "Active"]
  OpenAI:    "Add your API key" → [ghost sm button "Add Key"]
  Gemini:    "Add your API key" → [ghost sm button "Add Key"]

Buttons row (display:flex gap:9px):
  [Skip for now — ghost button, flex:1]
  [Get Started → primary button, flex:1, h:48px]
```

---

### `/dashboard` — Main Dashboard

**Layout**: AppShell (TopNav + Sidebar) + page content

**Page content** (padding:34px 32px, max-width:1160px)
```
Header:
  h1: "Good morning 👋" (28px, 800wt, ls:-1px, color:#e8e8f0, mb:4px)
  p: "Here's what's happening in your workspace" (13px, rgba(232,232,240,0.40))

Stats row (4-column grid, gap:12px, mb:36px):
  Each stat card: bg:rgba(255,255,255,0.03), border:1px solid rgba(255,255,255,0.06), radius:10px, padding:18px
    Icon (18px, mb:7px)
    Number: 28px, 800wt, ls:-1px, gradient(135deg, #63d9ff, #3dffa0), bg-clip:text
    Label: JetBrains Mono, 10px, rgba(232,232,240,0.40), mt:4px
  [📁 "7" "Total Projects"] [⚙️ "2" "Active Builds"]
  [▲ "14" "Deployments"] [⚡ "847k / 2M" "Tokens"] (with 3px progress bar)

Continue Building section (mb:32px):
  Header: h2 "Continue Building" (17px, 700wt, color:#e8e8f0) + [View all ghost sm button RIGHT]
  3-column project card grid:
    Each card: base card + hover effect
      [Thumbnail: 80px height, radius:8px, gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08)), centered ⬡ icon 28px]
      [Status badge + framework chip (9px JetBrains Mono muted)]
      [Project name: 13px, 700wt, mb:3px]
      [Description: 11px, rgba(232,232,240,0.40), mb:13px, lh:1.5]
      [Open Editor → secondary sm button, full width]

Quick Actions section:
  h2 "Quick Actions" (17px, 700wt, mb:13px)
  Row of buttons (display:flex, gap:9px, flex-wrap:wrap):
    [+ New Project — primary] [💡 Generate Idea — secondary]
    [📁 All Projects — ghost] [⚙ Settings — ghost]

Recent Activity section:
  h2 "Recent Activity" (17px, 700wt, mb:13px)
  List (display:flex flex-col):
    Each item (display:flex, align-items:center, gap:12px, padding:9px 0, border-bottom:1px solid rgba(255,255,255,0.05)):
      [7px dot — colored] [activity text 12px, color:#e8e8f0, flex:1]
      [project forge tag] [time 9px JetBrains Mono, rgba(232,232,240,0.35)]
```

---

### `/projects` — Projects List

**Layout**: AppShell + page content
```
Header row (display:flex, align-items:center, justify-content:space-between, mb:22px):
  Left: h1 "Projects" (28px, 800wt, ls:-1px) + route chip "/projects"
  Right: [Search input 200px] [+ New Project primary button]

Filter tabs (display:flex, gap:5px, mb:22px):
  Each tab: sm button. Active = secondary style. Inactive = ghost.
  Options: All | Live | Building | Draft | Error

Project grid (3-column, gap:12px):
  Each ProjectCard: card with hover
    [Thumbnail 90px height with gradient bg + ⬡ icon]
    [Status badge + framework chip]
    [name 14px 700wt] [desc 11px muted lh:1.5 mb:14px]
    Bottom row: [last-updated 9px mono muted] [Open Editor → secondary sm]

Empty state (no projects):
  Centered illustration area (SVG geometric, ~200px)
  "No projects yet" (20px 700wt)
  "Start building your first application" (muted)
  [Start with an idea → primary] [Build from prompt → ghost]
```

---

### `/projects/new` — New Project

**Layout**: AppShell + content (max-w:800px)
```
Header: [← Projects ghost sm] + h1 "New Project" (24px 800wt) + route chip

Two-path choice (2-column grid, gap:12px, mb:24px):
  Card 1: centered, padding:26px, ✍️ (28px mb:9px) "I have an idea" (13px 700wt)
    Selected: border:2px solid #63d9ff + forge-dim bg
  Card 2: centered, padding:26px, 💡 "Generate an idea"
    → clicks navigate to /ideate

IF "I have an idea" selected — show below:

Prompt textarea section:
  label: "DESCRIBE YOUR APPLICATION" (standard label style)
  textarea: 5 rows, resize:none, full width, standard input styles
  Char count: display:flex justify-content:flex-end, mt:4px
    "0 / 2000" (9px JetBrains Mono, rgba(232,232,240,0.30))

AI Enhancement toggle row:
  Container: display:flex, align-items:center, gap:12px
             bg:rgba(255,255,255,0.03), border:1px solid rgba(255,255,255,0.07)
             radius:8px, padding:11px 14px, mb:18px
  [Toggle switch (ON by default)] [title 12px 600wt + desc 11px muted]

Cloud Services (mb:18px):
  label: "CLOUD SERVICES"
  Chips: display:flex, flex-wrap:wrap, gap:7px
    Each: padding:5px 13px, radius:6px, font-size:11px, weight:600, cursor:pointer
    Unselected: border:1px solid rgba(255,255,255,0.08), color:rgba(232,232,240,0.45), bg:transparent
    Selected:   border:1px solid #63d9ff, color:#63d9ff, bg:rgba(99,217,255,0.10)
  Options: Supabase | Stripe | OpenAI | Resend | Twilio | AWS S3 | Cloudflare | Auth0 | Pinecone | SendGrid

Framework selector (mb:26px):
  label: "FRAMEWORK"
  4-column grid:
    Each: padding:9px 7px, radius:7px, text-align:center, font-size:10px, weight:600, cursor:pointer
    Unselected: border:1px solid rgba(255,255,255,0.07), color:rgba(232,232,240,0.45), bg:transparent
    Selected:   border:1px solid #63d9ff, color:#63d9ff, bg:rgba(99,217,255,0.08)
  Options: Next.js | React + Vite | Remix | FastAPI + React

[Start Building → primary button, full width, h:50px, font-size:14px]
Note: "Estimated build time: 8–15 minutes · Zero broken builds guaranteed"
      (9px JetBrains Mono, text-align:center, rgba(232,232,240,0.30), mt:9px)
```

---

### `/ideate` — Ideation Page

**Layout**: Full viewport, no AppShell, simplified top nav (logo + "← Dashboard" button)

```
Centered content (max-w:580px, margin:0 auto, min-height:calc(100vh - 112px), display:flex flex-col align-items:center justify-content:center, padding:40px 20px):

Hero:
  Icon: 💡 (44px, mb:14px, text-align:center)
  h1: "What will you build?" (38px, 800wt, ls:-1.2px, mb:10px, color:#e8e8f0, text-align:center)
  p: "Let AI help you find your next million-dollar idea" (14px, rgba(232,232,240,0.45), text-align:center, mb:44px)

3 option cards (display:flex flex-col gap:10px, width:100%):
  Card 1 .va accent: 💡 "Help me find an idea" / "8 adaptive questions · all skippable · 5 unique ideas generated"
    → navigate to /ideate/questionnaire/:newSessionId
  Card 2 .fa accent: ✍️ "I already have an idea" / "Describe it and AI will enhance it before building"
    → navigate to /projects/new
  Card 3 .ea accent: 🎲 "Surprise me" / "Zero input — AI generates from market signals instantly"
    → POST /api/v1/ideation/generate-direct, then navigate to /ideate/ideas/:sessionId

  Each card layout (display:flex, align-items:center, gap:14px, padding:18px 22px):
    [icon 26px flex-shrink:0] [title 14px 700wt mb:3px + desc 11px muted] [→ forge 18px]
```

---

### `/ideate/questionnaire/:sessionId` — Questionnaire

**Layout**: Full viewport, fixed top nav, content centered

**Top nav**:
```
Logo | "Question X of 8" (10px JetBrains Mono, rgba(232,232,240,0.35)) | [Skip All → ember sm button]
```

**Progress bar** (display:flex, align-items:center, gap:6px, justify-content:center, mb:28px):
```
8 pill elements, transition all 0.25s:
  Done:    8px × 8px, radius:50%, bg:#3dffa0
  Current: 28px × 8px, radius:4px, bg:#63d9ff
  Future:  8px × 8px, radius:50%, bg:rgba(255,255,255,0.12)
```

**Question card** (max-w:620px, w:100%, card style, padding:36px, fade-in animation on question change):
```
Step number: "01" through "08"
  52px, 800wt, ls:-2px, color:rgba(232,232,240,0.10), lh:1, mb:7px

Question text: 21px, 700wt, ls:-0.5px, mb:22px, color:#e8e8f0

ANSWER TYPE A — Chip multi-select:
  display:flex, flex-wrap:wrap, gap:7px, mb:26px
  Chips: padding:7px 15px, radius:20px (pill), font-size:11px, weight:600, cursor:pointer
  Unselected: border:1px solid rgba(255,255,255,0.08), color:rgba(232,232,240,0.50), bg:transparent
  Selected:   border:1px solid #63d9ff, color:#63d9ff, bg:rgba(99,217,255,0.10)

ANSWER TYPE B — Option cards (2-column grid, gap:9px, mb:26px):
  Each: text-align:center, padding:13px 16px, radius:10px, cursor:pointer
  Unselected: border:2px solid rgba(255,255,255,0.06), bg:transparent
  Selected:   border:2px solid #63d9ff, bg:rgba(99,217,255,0.08)
  Hover:      border-color:rgba(99,217,255,0.25)
  Content: [icon 22px mb:6px] [label 11px 600wt color:#e8e8f0]

ANSWER TYPE C — Slider (mb:26px):
  input[type=range], full width, accent-color:#63d9ff
  Min/max labels: display:flex, justify-content:space-between, font-size:10px, rgba(232,232,240,0.40)

ANSWER TYPE D — Text input: standard input, mb:26px

Bottom row (display:flex, justify-content:space-between, align-items:center):
  [← Back — ghost button, opacity:0.3 when on first question]
  [Skip this → — ghost sm, color:rgba(232,232,240,0.40)]
  [Next → primary] OR [Generate Ideas → primary] on last question
```

---

### `/ideate/ideas/:sessionId` — Ideas Display

**Layout**: AppShell + content
```
Header (display:flex, justify-content:space-between, align-items:flex-start, mb:26px):
  Left:
    Row: [← Ideate ghost sm] [h1 "Your Ideas" 26px 800wt] [route chip]
    p: "5 AI-generated ideas · Private for 7 days · Based on your answers" (12px muted)
  Right: [↻ Regenerate All ghost sm]

Ideas grid layout:
  Top 3: 3-column grid (gap:12px, mb:12px)
  Bottom 2: 2-column grid (gap:12px)

Each IdeaCard (radius:13px, border:1px solid rgba(255,255,255,0.07), overflow:hidden):
  HEADER (gradient bg, padding:16px 16px 12px, border-bottom):
    bg: linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))
    Row: [★ X.X/10 uniqueness — 8px JetBrains Mono, #f5c842] [◆ X/10 complexity — violet tag RIGHT]
    Title: 16px, 800wt, ls:-0.5px, mb:3px, color:#e8e8f0
    Tagline: 11px, rgba(232,232,240,0.45), font-style:italic

  CONTENT (padding:13px 16px, border-bottom):
    Problem section: label "PROBLEM" (8px mono muted uppercase ls:1px, mb:3px) + text (11px, rgba(232,232,240,0.60), lh:1.5)
    Solution section: same pattern
    Metrics row (display:flex, gap:14px):
      [Market label + value forge 12px 700wt] [Revenue label + value]

  TECH STACK (padding:10px 16px, border-bottom, display:flex flex-wrap gap:4px):
    Forge tags for each technology

  ACTIONS (padding:10px 16px, display:flex, gap:7px):
    [💾 Save — ghost sm, jade color when saved]
    [↻ — ghost sm]
    [🚀 Build This — primary sm, flex:1]

Stagger animation: each card fades in with 150ms delay between cards

Footer: "Ideas private for 7 days · Similar ideas may surface to other users after expiry"
  (9px JetBrains Mono, rgba(232,232,240,0.20), text-align:center, mt:22px)
```

---

### `/pipeline/:pipelineId` — Pipeline Progress

**Layout**: AppShell + content (max-w:1100px)
```
Header:
  [← Projects ghost sm] + h1 "Building: [Project Name]" (22px, 800wt, ls:-0.8px) + route chip
  Status row: [◎ Running — Stage 3 of 6 — forge tag + pulse animation] [Elapsed: 4:32 — 10px mono muted]

2-column layout (gap:18px, mb:18px):
  LEFT (350px wide): Stage list card
    Label: "PIPELINE STAGES" (9px mono uppercase muted, mb:13px)
    6 stage items (each border-bottom, padding:10px 7px, cursor:pointer):
      [Status circle 26px] [Stage name 12px 600wt + status text] [Duration RIGHT]

      Status circles:
        Done:    bg:#3dffa0, color:#04040a, "✓"
        Running: bg:#63d9ff, color:#04040a, + spinning ring shadow
        Pending: bg:rgba(255,255,255,0.07), color:rgba(232,232,240,0.35), step number
        Failed:  bg:#ff6b35, "✕"
      
      Stage names: Input Layer, C-Suite Analysis, Synthesis, Spec Layer, Bootstrap, Build

  RIGHT (flex:1): Active stage detail card
    When C-Suite active:
      h2 "C-Suite Analysis" + [X/8 Complete jade tag RIGHT]
      "8 executive agents analyzing in parallel" (11px muted)
      2x4 agent grid (gap:10px):
        Each agent card (bg:#111125, border, radius:8px, padding:12px 13px):
          [emoji 18px] [role name 12px 700wt flex:1] [status icon right]
          output text below (10px muted, appears after done)
          Done:    border:rgba(61,255,160,0.2), ✓ jade
          Running: border:rgba(99,217,255,0.22), spinning ring
          Pending: default border, ○ muted

    When Synthesis active: show synthesizer progress panel
    When Build active: show 10-agent sequential list with progress

Live event log (below 2-col, full width, max-height:180px, overflow:hidden):
  Label: "LIVE EVENT LOG" (9px mono uppercase muted, mb:10px)
  Lines: [timestamp rgba(232,232,240,0.18)] [level colored] [message muted] — JetBrains Mono 9px

Skip button (mt:18px, text-align:center):
  [Skip to Editor Preview → primary lg]
  "In production this auto-redirects when build completes" (9px mono muted, mt:7px)

Completion overlay (when pipeline done):
  Confetti animation (forge + violet particles, 2s burst)
  Card: "🎉 Your app is ready!" (24px 700wt) + stats + [Open in Editor → primary lg]
  Countdown: "Opening automatically in 3..." (muted mono)
```

---

### `/projects/:id/editor` — The Editor (FULL VIEWPORT)

**CRITICAL**: This page uses NO AppShell. No TopNav, no Sidebar. Custom layout fills 100vh exactly.

**Overall grid** (height:100vh, display:flex flex-direction:column, overflow:hidden)

**Top bar** (height:46px, bg:#080812, border-bottom, flex-shrink:0, z-index:50):
```
display:flex, align-items:center, padding:0 14px, gap:11px

LEFT: [Hex logo 22px] [FORGE gradient wordmark 16px 800wt] [│ divider] [Project Name ▼ 12px muted] [branch chip]
RIGHT: [● errors count — 9px mono ember] [⊟/⊞ Preview toggle — ghost sm] [▲ Deploy — primary sm] [Avatar 28px]
```

**Body** (flex:1, display:grid, grid-template-columns: 46px 210px 1fr [310px when preview on] 295px, overflow:hidden, min-height:0)

**Activity bar** (46px, bg:rgba(4,4,10,0.90), border-right):
```
display:flex flex-direction:column align-items:center padding:10px 0 gap:5px
Icons (34px × 34px each, radius:6px, cursor:pointer, font-size:14px):
  Default: color:rgba(232,232,240,0.40)
  Active/hover: color:#63d9ff, bg:rgba(99,217,255,0.08)
  Active: border-left:2px solid #63d9ff, border-radius:0 6px 6px 0, margin-left:-1px
Icons: 📁 🔍 ⚡ 🔀 🐛 🧪 [spacer flex:1] ⚙️
```

**File tree sidebar** (210px, border-right, display:flex flex-direction:column):
```
Header (9px mono uppercase muted, padding:9px 12px, border-bottom, display:flex justify-content:space-between):
  "Explorer" | [+ icon forge]

File tree items (padding:6px 0, overflow-y:auto, flex:1):
  Each item (display:flex, align-items:center, gap:6px, padding:3px 8px + depth*11px, JetBrains Mono 11px):
    Dot indicator (8px circle):
      Active:   #63d9ff
      Modified: #ff6b35
      New:      #3dffa0
      Directory:triangle ▶ #f5c842
    Filename color:
      Active:   #63d9ff
      Directory:#e8e8f0
      Default:  rgba(232,232,240,0.42)
    Active item: bg:rgba(99,217,255,0.08)
    Hover: bg:rgba(255,255,255,0.03), color:#e8e8f0
```

**Main editor area** (display:flex flex-direction:column overflow:hidden):
```
Tab bar (34px, border-bottom, display:flex overflow-x:auto flex-shrink:0):
  Each tab (min-w:90px, display:flex align-items:center gap:7px padding:0 13px JetBrains Mono 10px):
    [● dot 8px ember if modified] [filename] [× close 10px muted right]
    Active: color:#e8e8f0, border-bottom:2px solid #63d9ff, bg:rgba(255,255,255,0.02)
    Inactive: color:rgba(232,232,240,0.40)

Breadcrumb (5px 14px padding, bg:rgba(255,255,255,0.015), border-bottom, 10px JetBrains Mono muted):
  "src › app › dashboard › page.tsx" (active file in #63d9ff)

Code area (flex:1, padding:16px 18px, bg:#04040a, overflow-y:auto, JetBrains Mono 12px lh:1.85):
  Monaco editor with FORGE dark theme:
    editor.background:         #04040a
    editor.foreground:         #e8e8f0
    keyword tokens:            #b06bff
    function name tokens:      #63d9ff
    string tokens:             #3dffa0
    type/class tokens:         #f5c842
    comment tokens:            rgba(232,232,240,0.28) italic
    operator tokens:           #ff6b35
    parameter tokens:          #e8e8f0
    lineHighlightBackground:   rgba(255,255,255,0.025)
    selectionBackground:       rgba(99,217,255,0.12)
  Line numbers: color rgba(232,232,240,0.15), width:26px, text-align:right, margin-right:14px
  Minimap: enabled, width:80px
  Font size: 12px, line height: 1.85
```

**Preview pane** (310px when visible, border-left, display:flex flex-direction:column):
```
Preview toolbar (38px, bg:rgba(4,4,10,0.95), border-bottom, padding:0 10px, gap:5px, flex-shrink:0):
  [← →] [URL bar flex:1 — 9px mono muted, radius:4px, bg:rgba(255,255,255,0.04)]
  [📱 mobile btn] [💻 desktop btn] (active: forge border + forge-dim bg)
  [📷 screenshot] [✏️ annotate toggle — ember when active] [🔗 share] [● N errors — ember]

Preview body (flex:1, bg:#04040a, display:flex align-items:center justify-content:center, position:relative):
  iframe: src={previewUrl + route}, width depends on device selection
  
  When selectedSnapshot ≠ null: show R2 snapshot image instead of iframe
  
  Loading state: skeleton shimmer (same dimensions as iframe)
  
  Annotation dots (when annotations exist):
    position:absolute at x_pct%, y_pct%
    12px circle, border:2px solid #fff, cursor:pointer
    Unresolved: bg:#ff6b35, pulsing animation
    Resolved: bg:#3dffa0, opacity:0.50
    Hover: scale to 16px, show comment tooltip

Dev console (collapsible, bg:rgba(4,4,10,0.97), border-top, flex-shrink:0):
  Tab bar (display:flex gap:2px, padding:6px 10px 0):
    Each: 9px JetBrains Mono, cursor:pointer
    Active: color:#63d9ff, border:1px solid rgba(99,217,255,0.25), bg:rgba(99,217,255,0.08), radius:4px
  Console lines: [time rgba(232,232,240,0.16)] [type colored] [message]
    log: rgba(232,232,240,0.45), warn: #f5c842, error: #ff6b35
  Max-height: 100px, overflow-y:auto

Snapshot timeline (38px, bg:rgba(4,4,10,0.95), border-top, display:flex align-items:center padding:0 10px gap:5px, flex-shrink:0):
  "BUILD" label (7px JetBrains Mono muted)
  Track (flex:1, display:flex align-items:center):
    10 dots (8px circles): done=jade, pending=muted, active=forge+glow
    Connecting segments (flex:1, height:1px, bg:rgba(255,255,255,0.07))
  LIVE dot (8px jade circle, jade-pulse animation, cursor:pointer)
  Label (7px JetBrains Mono: "● LIVE" jade or "After Agent N" muted)
```

**Chat panel** (295px, border-left, bg:#080812, display:flex flex-direction:column):
```
Header (padding:10px 12px, border-bottom, display:flex align-items:center gap:9px, flex-shrink:0):
  [Gradient circle 26px — ⚡] [title "Forge AI" 12px 700wt + "● active · claude-sonnet-4" 8px mono jade] [⚙ muted right]

Messages (flex:1, padding:12px, overflow-y:auto, display:flex flex-col gap:9px):
  FROM label: 8px JetBrains Mono 700wt, ls:0.5px, mb:3px
    User: rgba(232,232,240,0.35)
    AI: #63d9ff
  User bubble: bg:rgba(255,255,255,0.04), border:rgba(255,255,255,0.06), radius:8px, padding:9px 11px, 11px, lh:1.6, color:rgba(232,232,240,0.65)
  AI bubble: bg:rgba(99,217,255,0.08), border:rgba(99,217,255,0.14), radius:8px, padding:9px 11px, 11px, lh:1.6
  Code block (in AI message):
    Container: bg:#04040a, border:rgba(255,255,255,0.08), radius:7px, overflow:hidden, mt:6px
    Header: padding:6px 10px, border-bottom, display:flex justify-content:space-between
      [filename 9px mono forge] [[Copy ghost sm 22px] [Apply primary sm 22px]]
      Applied state: bg:rgba(61,255,160,0.10), color:#3dffa0, border:rgba(61,255,160,0.20)
    Code body: padding:9px 11px, JetBrains Mono 9px, lh:1.7

Input area (padding:9px 10px, border-top, flex-shrink:0):
  Command chips (display:flex gap:4px flex-wrap mb:6px):
    Each: 8px JetBrains Mono, padding:2px 6px, bg:rgba(99,217,255,0.08), color:#63d9ff
          border:rgba(99,217,255,0.18), radius:3px, cursor:pointer
    Options: /build /deploy /test /lint
  
  Input row (display:flex gap:5px):
    Textarea: flex:1, JetBrains Mono 10px, 2 rows, resize:none
              bg:rgba(255,255,255,0.04), border:rgba(255,255,255,0.07), radius:5px, padding:6px 9px
              Focus: border-color rgba(99,217,255,0.25)
    Send button: 28×28px, bg:#63d9ff, border:none, radius:5px, color:#04040a, font-size:13px, 700wt
```

**Status bar** (22px, bg:#63d9ff, flex-shrink:0):
```
display:flex, align-items:center, padding:0 12px, gap:16px
Items: JetBrains Mono 9px, color:#04040a, weight:700
Content: "⚡ Forge" | "TypeScript" | "Ln X, Col Y" | "No errors" | "Sandbox: ● Running" | "main"
```

---

### `/settings/ai-providers` — AI Providers

**Layout**: AppShell + settings layout (sub-sidebar 200px + content)

**Settings sub-sidebar** (border-right, padding:20px 0):
```
Nav items (same styling as main sidebar but smaller):
  👤 Profile, 🤖 AI Providers (active), ⚡ Model Routing, 🔗 Integrations,
  🔑 API Keys, 🔒 Security, 💳 Billing
```

**Content** (max-w:900px, padding:32px 36px):
```
Header:
  h1 "AI Providers" (26px 800wt) + route chip
  p: "Connect your API keys · All keys encrypted with AES-256-GCM" (12px muted)

2-column provider grid:
  Each ProviderCard (bg:#0d0d1f, border:1px solid rgba(255,255,255,0.07), radius:10px, padding:16px 18px):
    Layout: display:flex, align-items:center, justify-content:space-between
    Left: [Logo circle 34px bg:rgba(255,255,255,0.06)] [name 13px 700wt + connection info]
    Right: action buttons

    CONNECTED:
      Name row: name + [forge tag "Default"] or [jade tag "Connected"]
      Info: "sk-ant-...c3x1 · 142ms" (9px mono rgba(232,232,240,0.35))
      Buttons: [Edit ghost sm] [Test ember sm]
    
    NOT CONNECTED:
      Info: "Not connected" (9px mono rgba(232,232,240,0.30))
      Button: [Connect → secondary sm]

Connect Modal (overlay + modal card):
  Overlay: bg:rgba(0,0,0,0.75), backdrop-filter:blur(8px), z-index:500
  Card: bg:#0d0d1f, border:rgba(99,217,255,0.22), radius:16px, padding:34px, max-w:460px
  Content: [Logo + title] [API key password input] [Test + Save buttons]
  Success state: jade-dim bg + jade border + "✓ Connected — 8 models · 142ms"
  Error state: ember-dim bg + ember border + "✗ Invalid API key"
```

---

### `/settings/model-routing` — Model Routing

```
Header: h1 "Model Routing" + route chip + description

Full-width table (bg:#0d0d1f, border, radius:12px, overflow:hidden):
  TH: Stage | Provider | Model | Fallback | Est. Cost
  TH style: 9px JetBrains Mono uppercase ls:1px muted, border-bottom
  
  6 data rows (one per pipeline stage):
    Stage cell: 12px 700wt color:#e8e8f0
    Provider/Model/Fallback: styled select elements
      select: bg:#080812, border:1px solid rgba(255,255,255,0.08), color:#e8e8f0
              padding:4px 9px, radius:5px, font-size:11px
    Cost cell: 10px JetBrains Mono #63d9ff 700wt

Cost estimator card (mt:18px, bg:rgba(99,217,255,0.06), border:rgba(99,217,255,0.18), radius:10px, p:18px):
  Label: "Estimated cost per full pipeline run" (11px 700wt #63d9ff)
  Amount: "~$0.83" (22px 800wt #63d9ff ls:-1px)
  Note: "vs. $2.40 with all-Opus · 60% saved via semantic cache" (11px muted)

[Save Routing primary button]
```

---

### `/settings/profile` — Profile

```
Avatar section (display:flex, align-items:center, gap:18px, mb:26px):
  [68px avatar circle gradient cyan→violet]
  [Upload Photo ghost sm] + "JPG, PNG or GIF · Max 2MB" (10px muted, mt:5px)

Form (display:flex flex-direction:column gap:14px, max-w:480px):
  [Display name input]
  [Email input — disabled, opacity:0.6]
  [Timezone select]
  [Save Changes primary width:fit-content]

Danger Zone (mt:28px, bg:rgba(255,107,53,0.08), border:rgba(255,107,53,0.20), radius:10px, p:18px):
  "Danger Zone" (12px 700wt #ff6b35)
  "Permanently delete your account..." (11px muted)
  [Delete Account ember sm button]
```

---

### `/settings/api-keys` — API Keys

```
Header: h1 + route chip + [+ Create API Key primary RIGHT]

Keys table (bg:#0d0d1f, border, radius:12px, overflow:hidden):
  TH: Name | Prefix | Last Used | Expires | Actions
  Rows with [Delete ember ghost sm button]

Create Key Modal:
  [Key name input] [Expiry select: Never/30d/90d] [Create primary]

SUCCESS MODAL (shown once after creation):
  ⚠️ "This key will only be shown once" (gold, 11px)
  Code block with full key (JetBrains Mono, #63d9ff on dark bg)
  [⎘ Copy to Clipboard primary full-width]
  [I've saved this key safely ghost]
```

---

### `/settings/security` — Security

```
3 sections (each a card, gap:13px):

Change Password card:
  h3 "Change Password" (14px 700wt)
  [Current password input] [New password + strength meter] [Confirm password]
  [Update Password primary width:fit-content]

2FA card:
  h3 "Two-Factor Authentication"
  Row: name/description flex:1 | [Disabled muted badge] | [Enable 2FA secondary sm]

Active Sessions card:
  h3 "Active Sessions"
  Session rows: device + location flex:1 | [Sign Out ember ghost sm]
  [Sign Out All Other Sessions ember button, mt:13px]
```

---

### `/settings/billing` — Billing

```
Plan card (gradient bg forge/violet tint, border:rgba(99,217,255,0.20), radius:14px, p:26px, mb:18px):
  Left: "CURRENT PLAN" label + "Pro Plan" + "$49/month"
  Right: [Manage Subscription → primary button]

Usage grid (4-column, mb:18px):
  Each stat card: label + value + progress bar (where applicable)
  [Tokens Used 847k/2M] [Builds 38/∞] [Deployments 14/∞] [Storage 2.1/10GB]

Invoice table (bg:#0d0d1f, border, radius:12px):
  Columns: Date | Amount | Status | Download
  Status: jade tag "Paid"
  Download: "#63d9ff cursor:pointer Download PDF"
```

---

## 4. INTERACTION PATTERNS

```
Route transitions:     150ms fade (opacity 0→1) on all page navigations
Card hover:            200ms ease — translateY(-2px) + border-color to border-bright
Button press:          100ms — scale(0.97)
Modal open:            200ms — scale(0.95→1) + opacity + backdrop-filter blur
Sidebar active item:   transition all 0.15s

Loading skeleton (for data loading):
  background: rgba(255,255,255,0.04)
  Shimmer: animated gradient sweeping left to right
  Use on: project thumbnails, stat cards, idea cards while loading

Toast notifications:
  Position: fixed top-right, 16px from edge, z-index:9999
  Width: 360px
  Each: panel bg, border-left 3px colored, radius:8px, padding:14px 16px
  Auto-dismiss: 4 seconds (hover pauses timer)
  Success: jade border + jade dot
  Error: ember border + ember dot
  Info: forge border + forge dot

Empty states: always show icon + title + primary CTA (never just text)
Form validation: inline errors below field in ember, field border turns ember on error
```

---

## 5. RESPONSIVE BREAKPOINTS

```
1280px+:  Full layout as specified
1024px:   Sidebar collapsible, 2-column grids become standard
768px:    Single column, sidebar hidden, bottom navigation
<768px:   Mobile: stack all content, hide sidebar

Editor page: DESKTOP ONLY (show "Editor requires desktop" notice on <1024px)
```

---

*FORGE UI/UX Design Brief for Antigravity — v3.0*
*Source: FORGE_STITCH_V3.md · Adapted for agent consumption*
*Implement exactly as specified. Do not invent alternatives.*
