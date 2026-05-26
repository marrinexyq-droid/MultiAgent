# React Output Rules

## Stack

- Use Vite + React
- Use plain CSS in `src/index.css`
- Use a single `App.jsx` unless the page clearly benefits from one or two small local components

## Design Discipline

- Favor strong visual intent over generic component-library aesthetics
- Match the screenshot's spacing rhythm before adding extra sections
- Use CSS variables for palette, borders, spacing, and fonts
- Prefer border-driven depth over box shadows
- Keep motion small and purposeful

## Avoid

- Tailwind
- heavy runtime dependencies
- generic gradients
- glassmorphism
- neon glows
- over-rounded corners
- default system-looking landing-page patterns unless the screenshot itself uses them

## Minimum Deliverable

Provide:

- a working `package.json`
- `src/main.jsx`
- `src/App.jsx`
- `src/index.css`
- enough content to make the page legible without external CMS data
