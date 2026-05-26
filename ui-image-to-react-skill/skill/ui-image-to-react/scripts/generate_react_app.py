#!/usr/bin/env python3
"""Generate a React page from a reference image and optional notes."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import shutil
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_DIR = SKILL_DIR.parents[1]
TEMPLATE_DIR = SKILL_DIR / "assets" / "vite-react-template"
GENERATED_ROOT = PROJECT_DIR / "generated"

MOTHERDUCK_STYLE_PROMPT = """
Use these exact MotherDuck-inspired design constraints:
- Background #F4EFEA, text and borders #383838
- Primary CTA #6FC2FF with offset shadow effect
- Accent banners in #FFDE00, #53DBC9, or #FF7169
- White cards with 2px charcoal borders and almost-square corners
- Uppercase monospace headings with normal weight, not bold
- Inter-style body copy with light weight
- Editorial marquee bands between major sections
- Warm playful industrial SaaS tone
- No gradients, glassmorphism, soft shadows, or pill buttons
""".strip()


@dataclass
class GenerationConfig:
    mode: str
    page_goal: str
    content_notes: str
    constraints: str
    backend: str = "stub"
    openai_model: str = "gpt-4.1-mini"


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def brightness(rgb: tuple[int, int, int]) -> float:
    return (0.299 * rgb[0]) + (0.587 * rgb[1]) + (0.114 * rgb[2])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def section_name(page_type: str, index: int) -> str:
    landing = ["hero", "value props", "feature cards", "social proof", "cta"]
    dashboard = ["top bar", "summary metrics", "primary chart", "table or list", "secondary panels"]
    editorial = ["hero", "story block", "feature narrative", "highlight band", "cta"]
    names = {
        "landing": landing,
        "dashboard": dashboard,
        "editorial": editorial,
    }.get(page_type, landing)
    return names[index] if index < len(names) else f"section {index + 1}"


def derive_stub_theme(analysis: dict[str, Any], config: GenerationConfig) -> dict[str, Any]:
    tokens = analysis["style_tokens"]
    dominant = tokens["dominant_hex"]
    accent = tokens["accent_hex"]
    dark_mode = tokens["dark_mode"]
    motherduck = config.mode == "high-fidelity-motherduck"
    landing = tokens["page_type"] == "landing"

    if motherduck:
        return {
            "name": "motherduck",
            "bg": "#F4EFEA",
            "surface": "#FFFFFF",
            "text": "#383838",
            "primary": "#6FC2FF",
            "secondary": "#53DBC9",
            "highlight": "#FFDE00",
            "muted_bg": "#F8F8F7",
            "radius": "2px",
            "heading_font": '"Space Mono", monospace',
            "body_font": '"Inter", sans-serif',
            "heading_transform": "uppercase",
            "heading_weight": "400",
            "border_width": "2px",
            "card_style": "bordered",
            "page_shell": "playful-industrial",
        }

    text = "#F5F7FA" if dark_mode else "#1D2433"
    bg = "#111827" if dark_mode else rgb_to_hex(tokens["background_rgb"])
    surface = "#1A2234" if dark_mode else "#FFFFFF"
    highlight = accent if accent != dominant else "#FF8A3D"
    secondary = dominant if brightness(tokens["dominant_rgb"]) < 210 else "#6C8BFF"

    if landing:
        page_shell = "editorial-soft" if not dark_mode else "editorial-dark"
        radius = "18px"
        border_width = "1px"
        card_style = "soft"
    else:
        page_shell = "dashboard-grid"
        radius = "16px"
        border_width = "1px"
        card_style = "panel"

    return {
        "name": "adaptive",
        "bg": bg,
        "surface": surface,
        "text": text,
        "primary": dominant,
        "secondary": secondary,
        "highlight": highlight,
        "muted_bg": "#E9EEF5" if not dark_mode else "#0F172A",
        "radius": radius,
        "heading_font": '"Inter", sans-serif' if landing else '"Space Mono", monospace',
        "body_font": '"Inter", sans-serif',
        "heading_transform": "none" if landing else "uppercase",
        "heading_weight": "600" if landing else "400",
        "border_width": border_width,
        "card_style": card_style,
        "page_shell": page_shell,
    }


def make_run_dir() -> Path:
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = GENERATED_ROOT / f"run_{stamp}"
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            return run_dir
        except FileExistsError:
            continue
    raise RuntimeError("Unable to allocate a unique run directory.")


def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    else:
        mime = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def analyze_image_locally(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        sample = image.resize((48, 48))
        pixels = list(sample.getdata())
        avg_rgb = tuple(round(mean(channel)) for channel in zip(*pixels))

        top_band = image.crop((0, 0, width, max(1, height // 5))).resize((24, 24))
        bg_band = image.crop((0, 0, width, max(1, height // 12))).resize((24, 12))
        middle_band = image.crop((0, height // 3, width, min(height, (height // 3) * 2))).resize((24, 24))
        footer_band = image.crop((0, max(0, height - max(1, height // 6)), width, height)).resize((24, 16))

        top_pixels = list(top_band.getdata())
        bg_pixels = list(bg_band.getdata())
        mid_pixels = list(middle_band.getdata())
        footer_pixels = list(footer_band.getdata())

        def avg_of(pxs: list[tuple[int, int, int]]) -> tuple[int, int, int]:
            return tuple(round(mean(channel)) for channel in zip(*pxs))

        top_rgb = avg_of(top_pixels)
        bg_rgb = avg_of(bg_pixels)
        mid_rgb = avg_of(mid_pixels)
        footer_rgb = avg_of(footer_pixels)

        saturated = sorted(
            pixels,
            key=lambda rgb: (max(rgb) - min(rgb), abs(brightness(rgb) - brightness(avg_rgb))),
            reverse=True,
        )
        accent_rgb = saturated[0]

        rows = []
        probe = image.resize((12, 24))
        for y in range(probe.height):
            row = [probe.getpixel((x, y)) for x in range(probe.width)]
            rows.append(brightness(avg_of(row)))

        transitions = 0
        for prev, curr in zip(rows, rows[1:]):
            if abs(curr - prev) > 18:
                transitions += 1

        dark_mode = brightness(avg_rgb) < 145
        long_page = height > width * 1.55
        page_type = "landing" if long_page and transitions >= 3 else "dashboard"
        if long_page and abs(brightness(top_rgb) - brightness(mid_rgb)) < 10:
            page_type = "editorial"

        sections = []
        section_count = max(3, min(6, transitions + 2))
        for index in range(section_count):
            sections.append(
                {
                    "name": section_name(page_type, index),
                    "purpose": "Locally inferred section from brightness and layout rhythm.",
                    "layout": "full-width band" if index % 2 else "content container",
                    "visual_notes": "Derived from row transitions in the screenshot.",
                }
            )

    return {
        "summary": f"Local fallback inferred a {page_type} page with {section_count} major sections.",
        "sections": sections,
        "style_tokens": {
            "screenshot_width": width,
            "screenshot_height": height,
            "average_rgb": list(avg_rgb),
            "dominant_rgb": list(top_rgb if page_type == "landing" else mid_rgb),
            "accent_rgb": list(accent_rgb),
            "background_rgb": list(bg_rgb),
            "footer_rgb": list(footer_rgb),
            "average_hex": rgb_to_hex(avg_rgb),
            "dominant_hex": rgb_to_hex(top_rgb if page_type == "landing" else mid_rgb),
            "accent_hex": rgb_to_hex(accent_rgb),
            "background_hex": rgb_to_hex(bg_rgb),
            "footer_hex": rgb_to_hex(footer_rgb),
            "long_page": long_page,
            "page_type": page_type,
            "section_count": section_count,
            "dark_mode": dark_mode,
            "row_transitions": transitions,
        },
        "interaction_hints": [
            "Use larger section spacing for landing/editorial layouts.",
            "Prefer denser cards and metric rows for dashboard-like layouts.",
        ],
        "unknowns": ["Text content and precise component semantics still require OCR or multimodal analysis."],
    }


def post_openai_chat(messages: list[dict[str, Any]], model: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed: {detail}") from exc

    return data["choices"][0]["message"]["content"]


def parse_json_block(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0]
    return json.loads(raw_text)


def analyze_with_openai(image_path: Path, config: GenerationConfig) -> dict[str, Any]:
    data_url = image_to_data_url(image_path)
    mode_guidance = (
        MOTHERDUCK_STYLE_PROMPT
        if config.mode == "high-fidelity-motherduck"
        else "Preserve broad visual language and layout logic, but allow original content and moderate restructuring."
    )
    prompt = textwrap.dedent(
        f"""
        Analyze this webpage screenshot for React implementation.
        Return JSON only with keys: summary, sections, style_tokens, interaction_hints, unknowns.

        Mode: {config.mode}
        Page goal: {config.page_goal or "single-page landing page"}
        Content notes: {config.content_notes or "none"}
        Constraints: {config.constraints or "none"}

        {mode_guidance}

        Each item in sections must include: name, purpose, layout, visual_notes.
        style_tokens should include: colors, typography, borders, spacing, cards, banners, buttons.
        """
    ).strip()
    result = post_openai_chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        config.openai_model,
    )
    return parse_json_block(result)


def default_plan(analysis: dict[str, Any], config: GenerationConfig) -> str:
    sections = analysis.get("sections") or []
    section_names = ", ".join(section.get("name", "section") for section in sections[:8]) or "hero, feature grid, proof strip, footer"
    return textwrap.dedent(
        f"""
        # Implementation Plan

        - Mode: `{config.mode}`
        - Page goal: {config.page_goal or "single-page landing page"}
        - Section flow: {section_names}
        - Constraints: {config.constraints or "none"}

        ## Notes

        - Build desktop-first.
        - Preserve the section rhythm and border language from the reference.
        - Use placeholders where the screenshot text is unreadable.
        """
    ).strip() + "\n"


def fallback_app_jsx(config: GenerationConfig, analysis: dict[str, Any]) -> str:
    tokens = analysis["style_tokens"]
    theme = derive_stub_theme(analysis, config)
    motherduck = config.mode == "high-fidelity-motherduck"
    page_type = tokens["page_type"]
    hero_label = (
        "PLAYFUL INDUSTRIAL DATA PLATFORM"
        if motherduck
        else ("REFERENCE-DRIVEN DASHBOARD" if page_type == "dashboard" else "REFERENCE-DRIVEN LANDING PAGE")
    )
    title = (
        "ANALYTICS WITHOUT THE COLD ENTERPRISE FEEL"
        if motherduck
        else ("SEE THE SHAPE OF THE SYSTEM AT A GLANCE" if page_type == "dashboard" else "BUILD A PAGE FROM A VISUAL REFERENCE")
    )
    subtitle = (
        "Warm cream surfaces, blueprint borders, crisp data messaging, and playful motion cues inspired by MotherDuck's product storytelling."
        if motherduck
        else (
            "The stub generator inferred a denser information layout from the screenshot and shifted toward panels, metrics, and structured rows."
            if page_type == "dashboard"
            else "The stub generator inferred a longer marketing-style composition and shifted toward larger sections, stronger hero emphasis, and broader storytelling space."
        )
    )
    banner_text = (
        "METRICS • PANELS • TABLES • SIGNALS • DENSITY •"
        if page_type == "dashboard"
        else "QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •"
    )
    feature_cards = [
        {
            "title": "SECTION RHYTHM",
            "text": f"Inferred {tokens['section_count']} main sections from the screenshot's vertical transitions.",
        },
        {
            "title": "COLOR SYSTEM",
            "text": f"Primary color adapts to {tokens['dominant_hex'].upper()} with accent support from {tokens['accent_hex'].upper()}.",
        },
        {
            "title": "PAGE TYPE",
            "text": f"The local analyzer classified this input as a {page_type} layout and changed the composition accordingly.",
        },
    ]
    proof_items = [
        f"{page_type.upper()} COMPOSITION",
        f"{'DARK' if tokens['dark_mode'] else 'LIGHT'} SURFACE SYSTEM",
        f"{tokens['section_count']} INFERRED CONTENT BANDS",
        "DESKTOP-FIRST GENERATED OUTPUT",
    ]
    return textwrap.dedent(
        f"""
        const featureCards = {json.dumps(feature_cards, ensure_ascii=False, indent=2)};

        const proofItems = {json.dumps(proof_items, ensure_ascii=False, indent=2)};

        export default function App() {{
          return (
            <div className="page-shell">
              <div className="announcement-bar">
                <div className="container announcement-copy">
                  <span>NOW SUPPORTING IMAGE-TO-REACT WORKFLOWS</span>
                  <span>TURN LONG SCREENSHOTS INTO LIVE PAGES</span>
                </div>
              </div>

              <header className="site-header">
                <div className="container nav-row">
                  <a className="brand-mark" href="#top">DUCK/STACK</a>
                  <nav className="nav-links">
                    <a href="#features">PRODUCT</a>
                    <a href="#system">SYSTEM</a>
                    <a href="#stories">STORIES</a>
                    <a href="#contact">LOGIN</a>
                  </nav>
                  <a className="button-shadow small" href="#contact">
                    <span className="button-face primary">START FREE →</span>
                  </a>
                </div>
              </header>

              <main id="top">
                <section className="hero-section container">
                  <div className="hero-copy">
                    <div className="eyebrow">{hero_label}</div>
                    <h1>{title}</h1>
                    <p>{subtitle}</p>
                    <div className="hero-actions">
                      <a className="button-shadow" href="#contact">
                        <span className="button-face primary">BUILD THE PAGE →</span>
                      </a>
                      <a className="button-shadow" href="#features">
                        <span className="button-face secondary">SEE THE SYSTEM</span>
                      </a>
                    </div>
                  </div>

                  <div className="hero-card">
                    <div className="hero-card-label">REFERENCE ANALYSIS</div>
                    <div className="hero-card-grid">
                      <div>
                        <span className="stat-label">MODE</span>
                        <strong>{config.mode.upper()}</strong>
                      </div>
                      <div>
                        <span className="stat-label">GOAL</span>
                        <strong>{(config.page_goal or "LANDING PAGE").upper()}</strong>
                      </div>
                      <div>
                        <span className="stat-label">STYLE</span>
                        <strong>{'MOTHERDUCK' if motherduck else 'GENERALIZED'}</strong>
                      </div>
                      <div>
                        <span className="stat-label">STACK</span>
                        <strong>REACT + CSS</strong>
                      </div>
                    </div>
                    <div className="cloud cloud-a" />
                    <div className="cloud cloud-b" />
                  </div>
                </section>

                <section className="marquee-band yellow-band" aria-label="Scrolling banner">
                  <div className="marquee-track">
                    <span>{banner_text}</span>
                    <span>{banner_text}</span>
                    <span>{banner_text}</span>
                  </div>
                </section>

                <section className="feature-section container" id="features">
                    <div className="section-label">WHY THIS MATCHES THE INPUT</div>
                  <div className="section-heading">
                    <h2>{'THE LAYOUT LEANS DENSE AND STRUCTURED' if page_type == 'dashboard' else 'THE PAGE LEANS OPEN AND SECTIONAL' if not motherduck else 'THE PAGE FEELS FRIENDLY, BUT THE SYSTEM STAYS PRECISE'}</h2>
                    <p>
                      {subtitle}
                    </p>
                  </div>
                  <div className="feature-grid">
                    {{featureCards.map((card) => (
                      <article className="feature-card" key={{card.title}}>
                        <div className="card-illustration" />
                        <h3>{{card.title}}</h3>
                        <p>{{card.text}}</p>
                        <a href="#system">LEARN MORE →</a>
                      </article>
                    ))}}
                  </div>
                </section>

                <section className="marquee-band teal-band" aria-label="Scrolling banner">
                  <div className="marquee-track reverse">
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                  </div>
                </section>

                <section className="system-section container" id="system">
                  <div className="system-sidebar">
                    <div className="section-label dark">DESIGN SYSTEM</div>
                    <h2>{'PANELS, ROWS, AND METRICS SHAPE THE PAGE' if page_type == 'dashboard' else 'ONE VISUAL LANGUAGE, MANY SECTION TYPES'}</h2>
                    <p>
                      {'The screenshot suggested a tighter information rhythm, so the stub keeps proof rows and structured side-by-side blocks more prominent.' if page_type == 'dashboard' else 'The screenshot suggested a more spacious storytelling rhythm, so the stub keeps broader hero spacing, banners, and card-led sections.'}
                    </p>
                    <a className="text-link" href="#contact">REQUEST A CUSTOM BUILD →</a>
                  </div>
                  <div className="proof-panel">
                    {{proofItems.map((item) => (
                      <div className="proof-row" key={{item}}>
                        <span>{{item}}</span>
                        <span>OK</span>
                      </div>
                    ))}}
                  </div>
                </section>

                <section className="contact-section container" id="contact">
                  <div className="section-label coral">START WITH A SCREENSHOT</div>
                  <div className="contact-card">
                    <div className="contact-copy">
                      <h2>DROP IN THE REFERENCE, PICK A MODE, AND GENERATE A PAGE</h2>
                      <p>
                        This starter output is ready for replacement with model-generated content or your own production copy. Keep the typography and border system stable while iterating.
                      </p>
                    </div>
                    <form className="contact-form">
                      <label>
                        <span>EMAIL</span>
                        <input type="email" placeholder="team@example.com" />
                      </label>
                      <button type="button" className="button-shadow">
                        <span className="button-face primary">BOOK A BUILD →</span>
                      </button>
                    </form>
                  </div>
                </section>
              </main>

              <footer className="site-footer">
                <div className="container footer-grid">
                  <div>
                    <div className="footer-heading">{'DUCK/STACK' if motherduck else 'REFERENCE/STACK'}</div>
                    <p>{'A reference-driven front-end generation starter with MotherDuck-flavored visual rules.' if motherduck else 'A locally adaptive front-end generation starter that shifts layout and color based on the uploaded screenshot.'}</p>
                  </div>
                  <div>
                    <div className="footer-heading">PRODUCT</div>
                    <a href="#features">Features</a>
                    <a href="#system">System</a>
                  </div>
                  <div>
                    <div className="footer-heading">WORKFLOW</div>
                    <a href="#top">Generalized</a>
                    <a href="#top">High Fidelity</a>
                  </div>
                  <div>
                    <div className="footer-heading">CONTACT</div>
                    <a href="#contact">Start Free</a>
                    <a href="#contact">Talk to Sales</a>
                  </div>
                </div>
              </footer>
            </div>
          );
        }}
        """
    ).strip() + "\n"


def fallback_index_css(config: GenerationConfig, analysis: dict[str, Any]) -> str:
    theme = derive_stub_theme(analysis, config)
    tokens = analysis["style_tokens"]
    return textwrap.dedent(
        f"""
        @import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500&family=Space+Mono:wght@400;700&display=swap");

        :root {{
          --bg: {theme['bg']};
          --surface: {theme['surface']};
          --text: {theme['text']};
          --primary: {theme['primary']};
          --primary-active: {theme['secondary']};
          --yellow: {theme['highlight']};
          --teal: {theme['secondary']};
          --coral: {theme['highlight']};
          --deep-teal: {theme['secondary']};
          --off-white: {theme['muted_bg']};
          --muted: color-mix(in srgb, var(--text) 42%, var(--bg) 58%);
          --border: {theme['border_width']} solid var(--text);
          --radius: {theme['radius']};
          --container: 1302px;
        }}

        * {{
          box-sizing: border-box;
        }}

        html {{
          scroll-behavior: smooth;
        }}

        body {{
          margin: 0;
          min-width: 320px;
          background: var(--bg);
          color: var(--text);
          font-family: {theme['body_font']};
        }}

        a {{
          color: inherit;
          text-decoration: none;
        }}

        button,
        input {{
          font: inherit;
        }}

        .container {{
          width: min(var(--container), calc(100% - 60px));
          margin: 0 auto;
        }}

        .page-shell {{
          overflow-x: clip;
        }}

        .announcement-bar {{
          background: var(--yellow);
          border-top: var(--border);
          border-bottom: var(--border);
        }}

        .announcement-copy {{
          min-height: 55px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
          font-size: 15px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }}

        .site-header {{
          position: sticky;
          top: 0;
          z-index: 99;
          background: var(--bg);
          border-bottom: var(--border);
        }}

        .nav-row {{
          min-height: 90px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
        }}

        .brand-mark,
        .eyebrow,
        h1,
        h2,
        h3,
        .section-label,
        .footer-heading,
        .marquee-track {{
          font-family: {theme['heading_font']};
          text-transform: {theme['heading_transform']};
          font-weight: {theme['heading_weight']};
        }}

        .brand-mark {{
          font-size: {'20px' if tokens['page_type'] == 'dashboard' else '22px'};
          letter-spacing: 0.08em;
        }}

        .nav-links {{
          display: flex;
          align-items: center;
          gap: 22px;
          font-size: 14px;
          letter-spacing: 0.03em;
          text-transform: uppercase;
        }}

        .nav-links a,
        .text-link,
        .feature-card a,
        .site-footer a {{
          border-bottom: 2px solid transparent;
          transition: border-color 160ms ease, color 160ms ease;
        }}

        .nav-links a:hover,
        .text-link:hover,
        .feature-card a:hover,
        .site-footer a:hover {{
          border-bottom-color: var(--primary);
          color: var(--primary-active);
        }}

        .button-shadow {{
          display: inline-flex;
          padding: 0 2px 2px 0;
          background: var(--text);
        }}

        .button-shadow.small .button-face {{
          padding: 12px 16px;
          font-size: 14px;
        }}

        .button-face {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: var(--border);
          border-radius: var(--radius);
          padding: 16px 22px;
          transform: translate(-2px, -2px);
          text-transform: uppercase;
          letter-spacing: 0.03em;
          transition: transform 120ms ease, background 120ms ease;
        }}

        .button-shadow:hover .button-face {{
          transform: translate(0, 0);
        }}

        .button-face.primary {{
          background: var(--primary);
        }}

        .button-face.primary:hover {{
          background: var(--primary-active);
        }}

        .button-face.secondary {{
          background: var(--bg);
        }}

        .hero-section {{
          padding: 90px 0 80px;
          display: grid;
          grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
          gap: 36px;
          align-items: stretch;
        }}

        .hero-copy h1 {{
          margin: 18px 0 20px;
          font-size: clamp(42px, 7vw, 56px);
          line-height: 1.2;
          letter-spacing: 1.12px;
          max-width: 12ch;
        }}

        .hero-copy p,
        .section-heading p,
        .system-sidebar p,
        .contact-copy p,
        .site-footer p {{
          font-size: 20px;
          line-height: 1.5;
          font-weight: 300;
        }}

        .hero-actions {{
          margin-top: 34px;
          display: flex;
          flex-wrap: wrap;
          gap: 18px;
        }}

        .hero-card,
        .feature-card,
        .proof-panel,
        .contact-card {{
          position: relative;
          background: var(--surface);
          border: var(--border);
          border-radius: var(--radius);
        }}

        .hero-card {{
          min-height: 480px;
          padding: 26px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }}

        .hero-card-label,
        .stat-label {{
          font-family: "Space Mono", monospace;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }}

        .hero-card-label {{
          align-self: flex-start;
          padding: 10px 16px;
          background: var(--text);
          color: white;
        }}

        .hero-card-grid {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 18px;
          position: relative;
          z-index: 1;
        }}

        .hero-card-grid div {{
          padding: 18px;
          background: color-mix(in srgb, var(--bg) 84%, white 16%);
          border: var(--border);
        }}

        .hero-card-grid strong {{
          display: block;
          margin-top: 10px;
          font-size: 24px;
          font-family: "Space Mono", monospace;
          font-weight: 400;
          line-height: 1.3;
        }}

        .cloud {{
          position: absolute;
          border: 1px solid var(--text);
          background: var(--surface);
          opacity: 0.9;
        }}

        .cloud-a {{
          width: 200px;
          height: 110px;
          right: -10px;
          top: 80px;
          border-radius: 52% 48% 60% 40% / 58% 56% 44% 42%;
        }}

        .cloud-b {{
          width: 160px;
          height: 90px;
          bottom: 24px;
          left: -28px;
          border-radius: 54% 46% 43% 57% / 50% 60% 40% 50%;
        }}

        .marquee-band {{
          overflow: hidden;
          border-top: var(--border);
          border-bottom: var(--border);
        }}

        .yellow-band {{
          background: var(--yellow);
        }}

        .teal-band {{
          background: var(--teal);
        }}

        .marquee-track {{
          display: flex;
          gap: 40px;
          width: max-content;
          min-width: 100%;
          padding: 20px 0;
          font-size: clamp(28px, 4vw, 40px);
          line-height: 1.1;
          animation: marquee 28s linear infinite;
        }}

        .marquee-track.reverse {{
          animation-direction: reverse;
        }}

        @keyframes marquee {{
          from {{
            transform: translate3d(0, 0, 0);
          }}
          to {{
            transform: translate3d(-33.33%, 0, 0);
          }}
        }}

        .feature-section,
        .system-section,
        .contact-section {{
          padding: {'88px 0' if tokens['page_type'] == 'dashboard' else '110px 0'};
        }}

        .section-label {{
          display: inline-flex;
          margin-bottom: 24px;
          padding: 12px 24px;
          background: var(--text);
          color: white;
          letter-spacing: 0.05em;
        }}

        .section-label.dark {{
          margin-bottom: 28px;
        }}

        .section-label.coral {{
          background: var(--coral);
          color: var(--text);
        }}

        .section-heading {{
          display: grid;
          grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
          gap: 32px;
          align-items: start;
          margin-bottom: 36px;
        }}

        h2 {{
          margin: 0;
          font-size: clamp(32px, 5vw, 40px);
          line-height: 1.2;
        }}

        .feature-grid {{
          display: grid;
          grid-template-columns: repeat({'4' if tokens['page_type'] == 'dashboard' else '3'}, minmax(0, 1fr));
          gap: 24px;
        }}

        .feature-card {{
          padding: 24px;
          min-height: {'260px' if tokens['page_type'] == 'dashboard' else '340px'};
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
        }}

        .card-illustration {{
          position: relative;
          height: 148px;
          margin-bottom: 22px;
          overflow: hidden;
          background: white;
          border: var(--border);
        }}

        .card-illustration::before,
        .card-illustration::after {{
          content: "";
          position: absolute;
          border: var(--border);
          border-radius: {'16px' if theme['card_style'] != 'bordered' else '48% 52% 43% 57% / 50% 54% 46% 50%'};
          background: white;
        }}

        .card-illustration::before {{
          width: {'56px' if tokens['page_type'] == 'dashboard' else '86px'};
          height: 62px;
          left: 18px;
          top: 28px;
          background: var(--yellow);
        }}

        .card-illustration::after {{
          width: {'74px' if tokens['page_type'] == 'dashboard' else '112px'};
          height: 74px;
          right: 20px;
          bottom: 18px;
          background: var(--teal);
        }}

        .feature-card h3 {{
          margin: 0 0 14px;
          font-size: 18px;
          line-height: 1.2;
        }}

        .feature-card p {{
          margin: 0 0 22px;
          font-size: 18px;
          line-height: 1.6;
          font-weight: 300;
          flex: 1;
        }}

        .system-section {{
          display: grid;
          grid-template-columns: {'360px minmax(0, 1fr)' if tokens['page_type'] == 'dashboard' else '440px minmax(0, 1fr)'};
          gap: 122px;
          align-items: start;
        }}

        .proof-panel {{
          overflow: hidden;
        }}

        .proof-row {{
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 20px;
          align-items: center;
          padding: 24px 28px;
          border-bottom: var(--border);
          font-family: "Space Mono", monospace;
          font-size: 18px;
          text-transform: uppercase;
        }}

        .proof-row:last-child {{
          border-bottom: none;
        }}

        .contact-card {{
          padding: 32px;
          display: grid;
          grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
          gap: 28px;
          align-items: end;
        }}

        .contact-form {{
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 18px;
          align-items: end;
        }}

        .contact-form label {{
          display: grid;
          gap: 10px;
          text-transform: uppercase;
          font-size: 14px;
          letter-spacing: 0.04em;
        }}

        .contact-form input {{
          width: 100%;
          min-height: 58px;
          padding: 16px;
          border: var(--border);
          border-radius: var(--radius);
          background: rgba(248, 248, 247, 0.7);
        }}

        .contact-form input:focus {{
          outline: none;
          border-color: var(--primary-active);
        }}

        .site-footer {{
          margin-top: 40px;
          padding: 90px 0 72px;
          background: var(--text);
          color: white;
        }}

        .footer-grid {{
          display: grid;
          grid-template-columns: 1.2fr repeat(3, 1fr);
          gap: 24px;
        }}

        .footer-heading {{
          margin-bottom: 18px;
          font-size: 16px;
          letter-spacing: 0.05em;
        }}

        .site-footer a {{
          display: block;
          width: fit-content;
          margin-bottom: 12px;
          color: white;
        }}

        @media (max-width: 1080px) {{
          .hero-section,
          .section-heading,
          .system-section,
          .contact-card,
          .footer-grid {{
            grid-template-columns: 1fr;
          }}

          .feature-grid {{
            grid-template-columns: 1fr;
          }}

          .contact-form {{
            grid-template-columns: 1fr;
          }}

          .nav-row {{
            flex-wrap: wrap;
            padding: 18px 0;
          }}
        }}

        @media (max-width: 720px) {{
          .container {{
            width: min(var(--container), calc(100% - 32px));
          }}

          .announcement-copy,
          .nav-links {{
            flex-wrap: wrap;
          }}

          .hero-section,
          .feature-section,
          .system-section,
          .contact-section {{
            padding: 72px 0;
          }}

          .hero-card-grid {{
            grid-template-columns: 1fr;
          }}
        }}
        """
    ).strip() + "\n"


def fallback_preview_body(config: GenerationConfig, analysis: dict[str, Any]) -> str:
    tokens = analysis["style_tokens"]
    motherduck = config.mode == "high-fidelity-motherduck"
    page_type = tokens["page_type"]
    hero_label = "PLAYFUL INDUSTRIAL DATA PLATFORM" if motherduck else ("REFERENCE-DRIVEN DASHBOARD" if page_type == "dashboard" else "REFERENCE-DRIVEN LANDING PAGE")
    title = "ANALYTICS WITHOUT THE COLD ENTERPRISE FEEL" if motherduck else ("SEE THE SHAPE OF THE SYSTEM AT A GLANCE" if page_type == "dashboard" else "BUILD A PAGE FROM A VISUAL REFERENCE")
    subtitle = (
        "Warm cream surfaces, blueprint borders, crisp data messaging, and playful motion cues inspired by MotherDuck's product storytelling."
        if motherduck
        else (
            "This in-web preview adapted toward denser metrics and panels because the uploaded image looked more dashboard-like."
            if page_type == "dashboard"
            else "This in-web preview adapted toward a more open marketing layout because the uploaded image looked like a long-form landing page."
        )
    )
    section_title = "THE PAGE FEELS FRIENDLY, BUT THE SYSTEM STAYS PRECISE" if motherduck else ("THE LAYOUT LEANS DENSE AND STRUCTURED" if page_type == "dashboard" else "THE PAGE LEANS OPEN AND SECTIONAL")
    page_goal = html.escape(config.page_goal or "Single-page landing page")
    return textwrap.dedent(
        f"""
        <div class="page-shell">
          <div class="announcement-bar">
            <div class="container announcement-copy">
              <span>NOW SUPPORTING IMAGE-TO-REACT WORKFLOWS</span>
              <span>TURN LONG SCREENSHOTS INTO LIVE PAGES</span>
            </div>
          </div>

          <header class="site-header">
            <div class="container nav-row">
              <div class="brand-mark">DUCK/STACK</div>
              <nav class="nav-links">
                <a href="#features">PRODUCT</a>
                <a href="#system">SYSTEM</a>
                <a href="#contact">LOGIN</a>
              </nav>
              <div class="button-shadow small">
                <span class="button-face primary">START FREE →</span>
              </div>
            </div>
          </header>

          <main>
            <section class="hero-section container">
              <div class="hero-copy">
                <div class="eyebrow">{hero_label}</div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
                <div class="hero-actions">
                  <div class="button-shadow">
                    <span class="button-face primary">BUILD THE PAGE →</span>
                  </div>
                  <div class="button-shadow">
                    <span class="button-face secondary">SEE THE SYSTEM</span>
                  </div>
                </div>
              </div>

              <div class="hero-card">
                <div class="hero-card-label">REFERENCE ANALYSIS</div>
                <div class="hero-card-grid">
                  <div>
                    <span class="stat-label">MODE</span>
                    <strong>{html.escape(config.mode.upper())}</strong>
                  </div>
                  <div>
                    <span class="stat-label">GOAL</span>
                    <strong>{page_goal.upper()}</strong>
                  </div>
                  <div>
                    <span class="stat-label">STYLE</span>
                    <strong>{html.escape("MOTHERDUCK" if motherduck else page_type.upper())}</strong>
                  </div>
                  <div>
                    <span class="stat-label">STACK</span>
                    <strong>REACT + CSS</strong>
                  </div>
                </div>
                <div class="cloud cloud-a"></div>
                <div class="cloud cloud-b"></div>
              </div>
            </section>

            <section class="marquee-band yellow-band">
              <div class="marquee-track">
                <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
                <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
                <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
              </div>
            </section>

            <section class="feature-section container" id="features">
              <div class="section-label">WHY THIS STYLE WORKS</div>
              <div class="section-heading">
                <h2>{section_title}</h2>
                <p>Use bordered composition, spacious copy blocks, and small playful accents to keep the product legible without drifting into flat corporate UI.</p>
              </div>
              <div class="feature-grid">
                <article class="feature-card">
                  <div class="card-illustration"></div>
                  <h3>FLEXIBLE COMPUTE STORY</h3>
                  <p>Explain the product with bordered cards, concise value props, and illustration-friendly empty space.</p>
                </article>
                <article class="feature-card">
                  <div class="card-illustration"></div>
                  <h3>HUMAN TECH TONE</h3>
                  <p>Keep the UI technical, but approachable. Monospace headings do the heavy lifting instead of bold type.</p>
                </article>
                <article class="feature-card">
                  <div class="card-illustration"></div>
                  <h3>STRUCTURED CTA FLOW</h3>
                  <p>Use one strong primary action, one quieter secondary action, and in-line links with arrow cues.</p>
                </article>
              </div>
            </section>

            <section class="marquee-band teal-band">
              <div class="marquee-track reverse">
                <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
              </div>
            </section>

            <section class="contact-section container" id="contact">
              <div class="section-label coral">START WITH A SCREENSHOT</div>
              <div class="contact-card">
                <div class="contact-copy">
                  <h2>THIS IS THE IN-WEB PREVIEW</h2>
                  <p>The full React project is also saved beside this preview so you can open it with Vite for development or export.</p>
                </div>
              </div>
            </section>
          </main>
        </div>
        """
    ).strip()


def standalone_preview_html(config: GenerationConfig, analysis: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Generated Preview</title>
            <style>
        {fallback_index_css(config, analysis)}
            </style>
          </head>
          <body>
        {fallback_preview_body(config, analysis)}
          </body>
        </html>
        """
    ).strip() + "\n"


def generate_code_with_openai(analysis: dict[str, Any], config: GenerationConfig) -> dict[str, str]:
    prompt = textwrap.dedent(
        f"""
        Return JSON only with keys: app_jsx, index_css, implementation_plan.
        Build a single-page React app in App.jsx and page styles in index.css.
        Mode: {config.mode}
        Page goal: {config.page_goal or "single-page landing page"}
        Content notes: {config.content_notes or "none"}
        Constraints: {config.constraints or "none"}
        Analysis JSON:
        {json.dumps(analysis, ensure_ascii=False, indent=2)}

        Use a Vite React app with plain CSS. Keep headings uppercase and avoid over-abstraction.
        """
    ).strip()
    result = post_openai_chat(
        [{"role": "user", "content": prompt}],
        config.openai_model,
    )
    return parse_json_block(result)


def copy_template(app_dir: Path) -> None:
    shutil.copytree(TEMPLATE_DIR, app_dir, dirs_exist_ok=True)


def write_outputs(run_dir: Path, analysis: dict[str, Any], code: dict[str, str], config: GenerationConfig) -> None:
    (run_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "implementation_plan.md").write_text(
        code.get("implementation_plan", default_plan(analysis, config)),
        encoding="utf-8",
    )
    (run_dir / "prompt_trace.md").write_text(
        textwrap.dedent(
            f"""
            # Prompt Trace

            - mode: `{config.mode}`
            - backend: `{config.backend}`
            - model: `{config.openai_model}`
            - page_goal: {config.page_goal or "single-page landing page"}
            - constraints: {config.constraints or "none"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "preview.html").write_text(
        standalone_preview_html(config, analysis),
        encoding="utf-8",
    )


def generate(image_path: Path, config: GenerationConfig) -> Path:
    run_dir = make_run_dir()
    shutil.copy2(image_path, run_dir / image_path.name)

    if config.backend == "openai":
        analysis = analyze_with_openai(image_path, config)
        code = generate_code_with_openai(analysis, config)
    else:
        analysis = analyze_image_locally(image_path)
        code = {
            "app_jsx": fallback_app_jsx(config, analysis),
            "index_css": fallback_index_css(config, analysis),
            "implementation_plan": default_plan(analysis, config),
        }

    app_dir = run_dir / "app"
    copy_template(app_dir)
    (app_dir / "src" / "App.jsx").write_text(code["app_jsx"], encoding="utf-8")
    (app_dir / "src" / "index.css").write_text(code["index_css"], encoding="utf-8")
    write_outputs(run_dir, analysis, code, config)
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_path", help="Path to the reference image")
    parser.add_argument("--mode", default="generalized", choices=["generalized", "high-fidelity-motherduck"])
    parser.add_argument("--page-goal", default="")
    parser.add_argument("--content-notes", default="")
    parser.add_argument("--constraints", default="")
    parser.add_argument("--backend", default="stub", choices=["stub", "openai"])
    parser.add_argument("--openai-model", default="gpt-4.1-mini")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = GenerationConfig(
        mode=args.mode,
        page_goal=args.page_goal,
        content_notes=args.content_notes,
        constraints=args.constraints,
        backend=args.backend,
        openai_model=args.openai_model,
    )
    run_dir = generate(Path(args.image_path), config)
    print(run_dir)


if __name__ == "__main__":
    main()
