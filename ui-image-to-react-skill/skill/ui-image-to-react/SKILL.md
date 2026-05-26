---
name: ui-image-to-react
description: Convert webpage screenshots or UI mock images into single-page React implementations with a strong visual match. Use when Codex needs to inspect a reference image, extract layout and style signals, and build a React + CSS page from it. Supports a generalized mode for arbitrary SaaS or marketing pages and a high-fidelity MotherDuck mode for long screenshots that should closely match the MotherDuck product-page visual language.
---

# UI Image To React

## Overview

Turn a reference UI image into a React landing page without drifting into generic styling. Analyze the screenshot first, choose the right workflow, then generate a desktop-first page using the bundled Vite template and CSS rules.

## Workflow Selection

Choose one of two workflows before generating code:

- Use `generalized` when the user provides a webpage screenshot and wants a page with the same visual language, layout logic, and component style, but not a near-copy.
- Use `high-fidelity-motherduck` when the user provides a long screenshot and wants a page that is clearly modeled on MotherDuck's product-page aesthetic and structure.
- If the user mentions MotherDuck, warm cream backgrounds, playful-industrial SaaS, monospace uppercase headings, or the provided MotherDuck palette, use the MotherDuck workflow.

Read these references as needed:

- `references/workflow-selection.md` for mode choice and output expectations
- `references/image-analysis-checklist.md` for screenshot analysis fields
- `references/react-output-rules.md` for implementation constraints
- `references/motherduck-style-spec.md` when the target should look like MotherDuck

## Execution Steps

Follow this order:

1. Inspect the reference image and extract structure before writing code.
2. Write a short implementation brief covering page sections, hierarchy, CTAs, color system, typography, and decorative motifs.
3. Copy the bundled `assets/vite-react-template/` into the working output directory.
4. Replace `src/App.jsx` and `src/index.css` with code tailored to the reference.
5. Keep components simple unless the page clearly needs reusable sub-sections.
6. Prefer one polished single-page result over broad but shallow component abstraction.

## Image Analysis Requirements

Always capture:

- page type: product page, landing page, dashboard, pricing page, or mixed
- visual tone: technical, playful, editorial, corporate, minimal, etc.
- section order from top to bottom
- heading scale and casing
- spacing rhythm and content density
- card, panel, banner, and divider treatments
- CTA styles and priority
- illustration or decorative systems
- responsive risks, especially for long desktop-first compositions

If any text is unreadable, preserve the layout and use clear placeholders instead of inventing detailed copy.

## MotherDuck Workflow

When using `high-fidelity-motherduck`:

- Match MotherDuck's warm cream background and charcoal border system.
- Use uppercase monospace headings with normal weight, not bold display text.
- Use the exact palette and spacing guidance from `references/motherduck-style-spec.md`.
- Preserve the overall section rhythm: navigation, strong hero, colored banners, bordered cards, playful illustration moments, and dark footer.
- Stay close to structure and vibe, but avoid copying logos, proprietary artwork, or long verbatim marketing copy unless the user explicitly provides replacement assets and text.

## React Output Rules

- Output a Vite React app with plain CSS.
- Keep styling mostly in `src/index.css`.
- Avoid Tailwind, CSS-in-JS, glassmorphism, gradients, and pill buttons unless the reference explicitly demands them.
- Build desktop-first. Add enough small-screen CSS to prevent obvious breakage.
- Use semantic HTML and accessible button/link text.

## Resources

- `scripts/generate_react_app.py`: optional generation pipeline for analysis, prompt assembly, and template output
- `assets/vite-react-template/`: starter React app to copy before customizing
- `references/*.md`: mode rules, MotherDuck spec, analysis checklist, and output constraints
