# Workflow Selection

## Modes

### `generalized`

Use when the reference is any SaaS, dashboard, marketing, docs, or product page and the goal is:

- preserve style language
- preserve broad information architecture
- adapt content freely
- avoid page-by-page imitation

Expected output:

- same family of layout decisions
- similar component grammar
- original placeholder or user-provided content

### `high-fidelity-motherduck`

Use when the target should feel recognizably close to MotherDuck's product page.

Expected output:

- close section rhythm
- close palette
- close typography and border system
- close CTA and marquee treatment
- close decorative tone

Do not default to exact copy for:

- logo assets
- illustrations
- long marketing paragraphs
- testimonial names or brand marks

## Decision Rule

Choose `high-fidelity-motherduck` if at least one of these is true:

- the user explicitly asks for MotherDuck
- the user provides the MotherDuck palette and typography rules
- the screenshot is a long warm-cream bordered landing page with marquee banners and playful illustrations

Otherwise choose `generalized`.
