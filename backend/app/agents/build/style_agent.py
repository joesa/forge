"""
Style Agent (Agent 8) — generates CSS, theming, animations.

UNIQUENESS: every app gets a unique visual identity:
  - Generates a unique color palette based on the app domain
  - Picks complementary fonts from Google Fonts (not generic defaults)
  - Creates CSS custom properties consistent with the palette
Layer 10: css_validator validates all Tailwind classes compile.
Files: globals.css, tailwind.config.ts overrides.
Gate G7 after.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog

from app.agents.ai_router import AIRouter
from app.agents.build.context_window_manager import ContextWindowManager
from app.agents.state import PipelineState

logger = structlog.get_logger(__name__)

AGENT_NAME = "style"

_SYSTEM_PROMPT = """You are a senior design engineer generating a unique visual identity.
Every application MUST have a distinct, professional color palette and typography.

Return a JSON object where keys are file paths and values are file contents.
Requirements:
- globals.css with CSS custom properties for the full palette
- Tailwind config overrides extending the default theme
- @import for Google Fonts — pick fonts that match the app's personality
- Smooth transitions and micro-animations via CSS
- Dark mode support with prefers-color-scheme
- Responsive typography scale"""

# ── Color palette generation ─────────────────────────────────────────
# Maps domain keywords to hue ranges for HSL palette generation

_DOMAIN_HUES: dict[str, int] = {
    "finance": 210, "banking": 215, "money": 200, "payment": 205,
    "health": 150, "medical": 155, "fitness": 145, "wellness": 140,
    "education": 260, "learning": 255, "school": 250, "course": 245,
    "food": 25, "recipe": 30, "restaurant": 20, "cooking": 35,
    "travel": 185, "booking": 190, "hotel": 195, "flight": 200,
    "social": 290, "chat": 285, "community": 295, "forum": 280,
    "ecommerce": 340, "shop": 345, "store": 335, "market": 330,
    "music": 275, "audio": 270, "podcast": 265,
    "game": 120, "gaming": 115, "play": 125,
    "ai": 230, "ml": 235, "data": 220, "analytics": 215,
    "photo": 45, "video": 40, "media": 50,
    "crypto": 170, "blockchain": 175, "web3": 165,
    "productivity": 195, "task": 200, "project": 190, "tool": 205,
}

# Font pairs: (heading_font, body_font)
_FONT_PAIRS: list[tuple[str, str]] = [
    ("Space Grotesk", "Inter"),
    ("Outfit", "DM Sans"),
    ("Sora", "Nunito Sans"),
    ("Manrope", "Source Sans 3"),
    ("Plus Jakarta Sans", "Work Sans"),
    ("Satoshi", "General Sans"),
    ("Cabinet Grotesk", "Switzer"),
    ("Clash Display", "Synonym"),
    ("Bricolage Grotesque", "Instrument Sans"),
    ("Urbanist", "Figtree"),
]


def _generate_palette(seed: str) -> dict[str, str]:
    """Generate a unique HSL color palette from a seed string."""
    digest = hashlib.md5(seed.lower().encode()).hexdigest()
    seed_int = int(digest[:8], 16)

    # Try to match domain keywords for contextual hue
    base_hue = seed_int % 360
    for keyword, hue in _DOMAIN_HUES.items():
        if keyword in seed.lower():
            base_hue = hue
            break

    return {
        "--color-primary": f"hsl({base_hue}, 72%, 50%)",
        "--color-primary-light": f"hsl({base_hue}, 72%, 65%)",
        "--color-primary-dark": f"hsl({base_hue}, 72%, 35%)",
        "--color-secondary": f"hsl({(base_hue + 30) % 360}, 55%, 55%)",
        "--color-accent": f"hsl({(base_hue + 180) % 360}, 65%, 55%)",
        "--color-bg": "hsl(0, 0%, 100%)",
        "--color-bg-secondary": "hsl(0, 0%, 97%)",
        "--color-surface": "hsl(0, 0%, 100%)",
        "--color-text": "hsl(0, 0%, 10%)",
        "--color-text-secondary": "hsl(0, 0%, 40%)",
        "--color-border": "hsl(0, 0%, 88%)",
        "--color-success": "hsl(145, 65%, 42%)",
        "--color-warning": "hsl(38, 92%, 50%)",
        "--color-error": "hsl(0, 72%, 51%)",
        "--color-info": f"hsl({base_hue}, 60%, 55%)",
        # Dark mode overrides
        "--dark-bg": "hsl(0, 0%, 8%)",
        "--dark-bg-secondary": "hsl(0, 0%, 12%)",
        "--dark-surface": "hsl(0, 0%, 14%)",
        "--dark-text": "hsl(0, 0%, 93%)",
        "--dark-text-secondary": "hsl(0, 0%, 60%)",
        "--dark-border": "hsl(0, 0%, 22%)",
    }


def _pick_fonts(seed: str) -> tuple[str, str]:
    """Deterministically pick a font pair based on seed."""
    digest = hashlib.md5(seed.lower().encode()).hexdigest()
    idx = int(digest[8:12], 16) % len(_FONT_PAIRS)
    return _FONT_PAIRS[idx]


def _build_default_styles(state: PipelineState) -> dict[str, str]:
    """Build deterministic default styles with unique palette."""
    idea = state.get("idea_spec", {})
    title = str(idea.get("title", "App"))
    desc = str(idea.get("description", ""))
    seed = f"{title} {desc}"

    palette = _generate_palette(seed)
    heading_font, body_font = _pick_fonts(seed)

    files: dict[str, str] = {}

    # ── globals.css ──────────────────────────────────────────────
    css_vars = "\n".join(f"  {k}: {v};" for k, v in palette.items() if not k.startswith("--dark"))
    dark_vars = "\n".join(
        f"  {k.replace('--dark-', '--color-')}: {v};"
        for k, v in palette.items() if k.startswith("--dark")
    )

    google_import = (
        f"@import url('https://fonts.googleapis.com/css2?"
        f"family={heading_font.replace(' ', '+')}:wght@400;500;600;700&"
        f"family={body_font.replace(' ', '+')}:wght@300;400;500;600&"
        f"display=swap');\n"
    )

    globals_css = (
        f"{google_import}\n"
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
        ":root {\n"
        f"  --font-heading: '{heading_font}', sans-serif;\n"
        f"  --font-body: '{body_font}', sans-serif;\n"
        f"{css_vars}\n"
        "  --radius-sm: 6px;\n  --radius-md: 10px;\n  --radius-lg: 16px;\n"
        "  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);\n"
        "  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);\n"
        "  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1);\n"
        "}\n\n"
        "@media (prefers-color-scheme: dark) {\n"
        f"  :root {{\n{dark_vars}\n  }}\n"
        "}\n\n"
        "body {\n"
        "  font-family: var(--font-body);\n"
        "  background: var(--color-bg);\n"
        "  color: var(--color-text);\n"
        "  line-height: 1.6;\n"
        "  -webkit-font-smoothing: antialiased;\n"
        "}\n\n"
        "h1, h2, h3, h4, h5, h6 { font-family: var(--font-heading); font-weight: 600; }\n\n"
        "/* Micro-animations */\n"
        "@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }\n"
        "@keyframes slideIn { from { opacity: 0; transform: translateX(-12px); } to { opacity: 1; transform: translateX(0); } }\n"
        "@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }\n\n"
        ".animate-fade-in { animation: fadeIn 0.3s ease-out; }\n"
        ".animate-slide-in { animation: slideIn 0.3s ease-out; }\n\n"
        "/* Focus styles */\n"
        "*:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }\n\n"
        "/* Scrollbar */\n"
        "::-webkit-scrollbar { width: 8px; }\n"
        "::-webkit-scrollbar-track { background: var(--color-bg-secondary); }\n"
        "::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 4px; }\n"
    )
    files["src/styles/globals.css"] = globals_css

    # ── Tailwind config overrides ────────────────────────────────
    tailwind_override = (
        "import type { Config } from 'tailwindcss';\n\n"
        "// Unique palette generated by FORGE style_agent\n"
        "const config: Config = {\n"
        "  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],\n"
        "  theme: {\n"
        "    extend: {\n"
        "      colors: {\n"
        "        primary: { DEFAULT: 'var(--color-primary)', light: 'var(--color-primary-light)', dark: 'var(--color-primary-dark)' },\n"
        "        secondary: 'var(--color-secondary)',\n"
        "        accent: 'var(--color-accent)',\n"
        "        surface: 'var(--color-surface)',\n"
        "        success: 'var(--color-success)',\n"
        "        warning: 'var(--color-warning)',\n"
        "        error: 'var(--color-error)',\n"
        "      },\n"
        "      fontFamily: {\n"
        f"        heading: ['var(--font-heading)', 'sans-serif'],\n"
        f"        body: ['var(--font-body)', 'sans-serif'],\n"
        "      },\n"
        "      borderRadius: { sm: 'var(--radius-sm)', md: 'var(--radius-md)', lg: 'var(--radius-lg)' },\n"
        "      boxShadow: { sm: 'var(--shadow-sm)', md: 'var(--shadow-md)', lg: 'var(--shadow-lg)' },\n"
        "      animation: { 'fade-in': 'fadeIn 0.3s ease-out', 'slide-in': 'slideIn 0.3s ease-out' },\n"
        "    },\n"
        "  },\n"
        "  plugins: [],\n"
        "};\n\nexport default config;\n"
    )
    files["tailwind.config.ts"] = tailwind_override

    return files


async def run_style_agent(
    state: PipelineState,
    ai_router: AIRouter,
    context_window_manager: ContextWindowManager,
) -> dict[str, str]:
    """Generate unique visual identity. temp=0."""
    start = time.monotonic()
    idea = state.get("idea_spec", {})

    user_prompt = (
        f"Project: {idea.get('title', 'Untitled')}\n"
        f"Description: {idea.get('description', '')}\n"
        f"Target Audience: {idea.get('target_audience', 'general')}\n"
        f"Generate: unique color palette, Google Font pair, globals.css, tailwind overrides\n"
    )

    try:
        files = await context_window_manager.generate(
            system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt, agent_name=AGENT_NAME,
        )
        if files:
            logger.info("style_agent.complete", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
            return files
    except Exception as exc:
        logger.warning("style_agent.llm_fallback", error=str(exc))

    files = _build_default_styles(state)
    logger.info("style_agent.complete_default", elapsed_s=round(time.monotonic() - start, 3), files=len(files))
    return files
