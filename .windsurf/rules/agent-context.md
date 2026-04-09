---
trigger: model_decision
---
Use `.local/skill-index.md` as the canonical skill registry for this repo.

Before multi-step work:
- Scan `.local/skills` for 4tie-specific workflows.
- Scan `.local/secondary_skills` only for portable extras.
- Prefer the smallest relevant skill set.
- Treat skill folder names and frontmatter names as lowercase hyphen-case identifiers.

Do not look for a mirrored Windsurf skill tree. Read the canonical `.local/*` skill files directly.
