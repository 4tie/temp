---
name: recreate-screenshot
description: Recreate a UI from a screenshot or image reference with close visual fidelity, covering layout, color, typography, spacing, and component structure.
---

# Recreate Screenshot

Use this skill when:
- The user provides a screenshot and wants it rebuilt in code.
- The task is visual reproduction rather than product ideation.
- Accuracy matters more than new feature design.

Workflow:
1. Analyze layout, spacing, color, typography, and repeated components before writing code.
2. Extract the smallest reusable design tokens needed for the match.
3. Implement the screen in the target codebase or a repo-local prototype.
4. Compare the result against the reference and iterate on the most visible mismatches first.
5. Keep the output self-contained and avoid editor-only preview surfaces.
