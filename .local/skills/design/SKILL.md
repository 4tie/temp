---
name: design
description: Implement or refine 4tie frontend UX directly in templates and static assets. Use for page layout, styling, interaction polish, or UI refactors in the FastAPI-rendered app.
---

# Design

Use this skill when:
- The user wants UI changes in the current 4tie app.
- A page in `templates/` needs layout or interaction work.
- CSS or JS updates are needed under `static/`.

4tie UI surfaces:
- Markup in `templates/pages/`, `templates/layouts/`, and `templates/partials/`.
- Styling in `static/css/` and `static/css/pages/`.
- Behavior in `static/js/components/` and `static/js/core/`.

Workflow:
1. Preserve the existing server-rendered architecture.
2. Make the smallest HTML, CSS, and JS change set that solves the problem.
3. Keep selectors and route wiring aligned with the existing page structure.
4. Validate visually and with Playwright when the change is user-facing.
